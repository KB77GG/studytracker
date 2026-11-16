# 学生今日任务 / 历史任务接口：数据库锁风险专项核查（2026-11-16）

范围：`GET /api/miniprogram/student/tasks/today`（`get_student_today_tasks`）与
`GET /api/miniprogram/student/task-history`（`list_student_task_history`）。
基线：`main@69a99a7`，分支 `claude/student-tasks-db-lock-audit-67jm7t`。

**本轮没有修改任何产品代码、没有访问生产服务器或生产数据库、没有部署。**
修复只以补丁文件形式给出（`proposed-fix-*.patch`），在独立临时工作树里验证，等待批准。
所有复现都用合成学生、合成任务和临时目录里的一次性 SQLite 文件。

下面三类结论严格分开：**A 日志里已确认的**、**B 源码里看到的**、**C 合成测试实际复现的**。
生产上那 3 次 500 的根因**仍未确认**，第 D 节说明还差哪一步证据。

---

## 结论摘要

1. **令牌写入分支不是那 3 次 500 的充分解释。** 3 次 500 里有 2 次落在历史任务接口，而该接口在任何条件下都不写库（合成测试全程 0 条写语句）。今日任务那 1 次 500 与一次历史任务 500 发生在同一秒、同一设备类型，更像共同原因，而不是令牌分支。
2. **令牌写入分支本身确有两个可复现的缺陷**，但表现不是锁异常：
   - 并发请求各自生成令牌并互相覆盖，先返回的客户端拿到的令牌随即失效（之后用它访问得到 403）；
   - 数据库忙时，这个"可有可无"的补写失败会让**整个今日任务列表**返回 500，小程序首页静默显示"今天老师暂未布置任务"。
3. **发现一个与这两个接口直接相关、此前未记录的机制（合成环境已复现，生产是否适用取决于日志模式）：**
   SQLite 回滚日志（DELETE）模式下，`COMMIT` 因锁失败后，SQLAlchemy 把连接归还连接池时**不回滚**，空闲连接继续持锁。之后今日任务、历史任务这类**纯读请求**会逐个等待 5 秒后报 `database is locked`，直到那个连接碰巧被再次取出。`get_student_today_tasks` 的无回滚提交是触发点之一，两个接口都可能是受害者。WAL 模式下未复现。
4. **生产库的日志模式、SQLAlchemy/SQLite 版本在仓库里没有记录**，本轮无法确认。这是判断第 3 点是否适用于生产的关键事实，第 D 节给出零副作用的确认办法。

---

## A. 日志中已确认的事实

来源只有仓库里的脱敏文件 `docs/reviews/miniprogram-entry-20261116/log-summary.json` 及其生成脚本 `audit_logs.py`。本轮没有重新取日志。

| 事实 | 数值 |
| --- | --- |
| 今日任务接口（journal，11-15 00:00 起） | 129 次 200，1 次 500 |
| 历史任务接口 | 119 次 200，2 次 500 |
| journal 文本匹配 | `OperationalError` 12 处，`database is locked` 8 处；**没有匹配到其他任何 `*Error` 类型** |
| nginx 中 `/api/miniprogram/` 下全部 5xx | 仅 3 条，见下 |

三次 500 的明细（nginx，已脱敏）：

| 时间（北京） | 接口 | 设备 | 响应体 |
| --- | --- | --- | --- |
| 11-15 14:52:46 | tasks/today | Android | 265 字节 |
| 11-15 14:52:46 | task-history | Android | 265 字节 |
| 11-15 18:12:36 | task-history | iPhone | 265 字节 |

同一份日志还显示：同一设备会在同一秒内重复请求今日任务（11-16 10:44:27 两次、字节数相同；11-15 17:12:16–18 三次）。

按交接文档，11-15 的两次部署在 19:54 和 23:36，与这两个时间点不重合。

**日志不能说明的：** 每条异常属于哪个请求、哪条 SQL；3 次 500 是否都是锁异常；数据库日志模式；是否与词汇加载超时同因。

---

## B. 源码核查结论（静态阅读，`main@69a99a7`）

**B1. GET 何时写库。** `get_student_today_tasks`（`api/miniprogram.py:1802-1821`）在同时满足以下条件时执行 `UPDATE task` 并 `db.session.commit()`：
任务有 `listening_exercise_id` 或 `reading_test_id`；对应令牌列为 `NULL` 或空串；任务状态为 `today` 或 `completed`（五日窗口内）。
过期未完成、未来、窗口外、无任务的日期、普通作业、令牌已齐全时不写。
`get_task_detail`（`:1944-1958`）有同样的补写，而且听力、阅读各提交一次。

**B2. 令牌平时在哪里生成。** 所有布置路径（后台表单、小程序老师端、任务规划、题型作业）创建任务时都会生成令牌；`services/task_deletion.py` 取消任务时清空，但已取消任务被全局过滤，读不到。所以这个写分支只对**历史遗留的无令牌任务**生效，生产上有多少条未知。

**B3. 没有任何异常处理。** 两个接口都没有 `try/except`，提交失败后也没有 `rollback()`，异常直接变成 Flask 默认 500 页。鉴权装饰器 `require_api_user` 只读。

**B4. 数据库连接配置。** `config.py` 没有 `SQLALCHEMY_ENGINE_OPTIONS`：pysqlite 默认等待 5 秒，没有设置 `journal_mode`，默认 `QueuePool`（5 个常驻连接）。

**B5. 历史任务接口的查询路径。** 纯读：一次查出该学生全部已完成/已提交任务，再用 `task_id IN (...)` 查全部听力、阅读提交记录的**整行**（含答案 JSON 大字段），即使首页用的是 `summary_only=1`。任务数没有上限，绑定变量数等于任务数。

**B6. 相邻观察。** `get_task_detail` 的 `except` 把 `str(e)` 原样返回给客户端，锁异常时响应体里带有 SQL 文本和绑定参数（包括刚生成的令牌）。`vocabulary-queue`、`vocabulary-review/today` 等其他 GET 也会提交，不在本次范围内，未核查。

---

## C. 合成测试实际复现的结果

环境：Python 3.13.18，SQLite 3.53.1，SQLAlchemy 2.1.8，Flask 3.1.3，Werkzeug 3.1.9；真实 `api.miniprogram` 蓝图；不设引擎参数（与 `config.Config` 一致）；DELETE 与 WAL 两种日志模式各跑一遍；6 个并发线程（对应生产 gthread threads=6）。原始结果：`probe-main.json`、`probe-starvation.json`、`probe-failed-commit-sa2.{0,1}.json`、`client-home-on-500.json`。

**C1. 写入条件矩阵**与 B1 完全一致（两种模式相同）。

**C2. 缺失令牌时的并发请求：没有锁错误，但令牌互相覆盖。**
- 强制交错（6 个请求都先读到"无令牌"再提交）：6 个 200，返回 5–6 个不同令牌，其中 5 个响应里的令牌不是最终入库的那个；用失效令牌访问受令牌保护的接口得到 **403**。
- 不加干预、6 线程同时发起，各 100 轮：77–96 轮出现令牌分歧（三次运行间波动，留档的最后一次是 77 和 87）；每次运行 1200 个请求里 0 个非 200。
- 这个比例是"同时起跑"的上限，不代表生产发生率。

**C3. 已有令牌时的重复读取：真正只读。** 90 个请求（30 串行 + 60 并发）0 条写语句，SQLite `data_version` 不变，令牌不变。另一连接持有写锁（RESERVED）时仍 200。另一连接持有独占锁（EXCLUSIVE）时：DELETE 模式等 5 秒后 500；WAL 模式 200。

**C4. 缺失令牌 + 另一连接持写锁超过 5 秒：整个列表 500。**
- 今日任务：**500，265 字节 HTML，耗时 5.03 秒**（两种模式相同）。同一把锁下，令牌齐全的日期 200，历史任务 200——也就是说任务数据本来都读得出来，只是补写失败拖垮了整个响应。
- 同一把锁下任务详情：500 JSON，响应体含 SQL 文本和绑定参数。
- 失败后的状态：令牌未入库，连接已归还；锁释放后再请求 200，令牌补写一次，之后稳定。

**C5. 一次这样的 500 在日志里的"指纹"。** 用 `audit_logs.py` 同一个正则统计：每条锁异常 traceback 恰好产生 3 处 `OperationalError` + 2 处 `database is locked`；响应体恰好 265 字节（Werkzeug 默认 500 页）。

**C6. 历史任务接口。** 全程 0 条写语句；并发 30 次全 200。200 / 1000 / 3000 条已完成任务时 `summary_only=1` 耗时约 0.02 / 0.1 / 0.3 秒（本机，无其他负载），完整列表响应 0.18 / 0.9 / 2.7 MB。把绑定变量上限模拟成旧版 SQLite 的 999 时，1000 条任务即 500（`too many SQL variables`）；本机 SQLite 无此限制。

**C7. `COMMIT` 失败后的连接池持锁（DELETE 模式）。**
- 构造：一个读者还在取大结果集（持 SHARED 锁）超过 5 秒，此时今日任务接口的补写 `COMMIT` 失败 → 500。
- 读者离开后本应没有任何锁，但随后**连续 4 个纯读请求（历史、今日交替）各等待 5.0 秒后 500**，第 5 个才成功（连接池里正好 5 个空闲连接，第 5 个请求取回了那个带锁连接）。
- 换成"任意一个提交后不回滚的处理函数"当触发者，结果相同：4 个纯读请求连带失败。
- SQLAlchemy 2.0.36 与 2.1.8 表现一致。显式 `session.rollback()` 可以释放；只靠请求结束时的 `session.remove()` 不行。
- 复用到带锁连接的那个请求还会读到失败请求**未提交**的改动。
- WAL 模式下这个场景里 `COMMIT` 不会失败，未出现连带失败。

**C8. 什么会让 `COMMIT` 等过 5 秒（假设检验，非生产证据）。** 同一进程里有 1 个 CPU 密集线程时，3000 条任务的完整历史查询从 0.25–0.4 秒变成 43–60 秒（每取一行都要重新抢 GIL），其读锁被长时间持有。DELETE 模式下：独立写者提交 5.08 秒后报锁，其间到达的纯读请求被拖慢 2.2–5.1 秒；用真实今日任务补写当写者时，写者 500，之后 0.4–3 秒内到达的 8 个纯读请求**全部** 500，连那个大历史查询也 500。WAL 模式下所有纯读请求 0.13 秒内 200。

**C9. 首页是否因此不可用。** 用仓库里的 `miniprogram/pages/student/home/index.js` 实际执行：今日任务返回 500 后，已显示的 2 条任务被清空，页面进入空状态文案"今天老师暂未布置任务"，没有错误提示或重试入口；待复盘任务数归零。页面其余部分照常。下次进入页面会重新请求。
注意：这是仓库源码的行为，**线上 105 包来自另一份固定发布目录，未核对**。

---

## D. 三者如何对应，以及仍未确认的部分

**有证据支持的推断（不是结论）：**
- 265 字节与 C5 的指纹一致 → 3 次 500 都是未被捕获的异常走了 Flask 默认 500 页（前提：生产 Werkzeug 版本的默认页也是 265 字节，未核对）。
- 12 : 8 恰好等于 4 条 C5 形态的 traceback，且 journal 里没有其他 `*Error` → 3 次 500 很可能都是锁异常，另有 1 条锁异常不在 `/api/miniprogram/` 的 5xx 里（可能是网页端路由、后台线程，或被处理函数捕获后记录）。
- 历史任务是纯读接口却 500：在合成环境里，纯读请求报锁只在 DELETE 模式出现（C3、C7、C8），WAL 模式下一次也没有 → 如果那 2 次确实是锁异常，生产库更可能是回滚日志模式。

**不能下的结论：**
- 不能说令牌写入分支导致了任何一次 500。它解释不了历史任务那 2 次；今日任务那 1 次也不需要它来解释。
- 不能说 C7/C8 就是生产上发生的事。它们证明了"这套代码在 DELETE 模式下可以这样出错"，没有证明"11-15 就是这样出的错"。
- 不能说与词汇加载慢同因。C8 说明 CPU 密集请求**可以**放大锁等待，而 11-15 正是词汇慢路径最严重的一天，但两个 500 时间点前后有没有慢请求在跑，脱敏日志里没有。
- 不能说 11-16 的性能修复已经顺带解决了这些 500。

**确认根因还差的证据（都是只读，本轮均未执行，需要你决定是否做）：**

1. **日志模式**（零交互，只读文件头两个字节，不经过 SQLite）：
   `xxd -s 18 -l 2 /root/apps/studytracker/app.db`（`0101` 回滚日志，`0202` WAL），以及 `ls -la /root/apps/studytracker/app.db*`。
2. **库版本**（只 import 库，不 import 应用）：
   `.venv/bin/python -c "import sqlalchemy, sqlite3, werkzeug; print(sqlalchemy.__version__, sqlite3.sqlite_version)"`，另 `pip show werkzeug`。
3. **那 4 条 traceback 各自是哪个路由、哪条语句**：本目录 `audit_lock_tracebacks.py`，只读 journalctl 文本，输出不含参数、查询串、姓名、ID、IP（已在合成日志上验证会丢弃这些）。如果历史任务的失败语句是 `SELECT`，即可确认是"读者被锁"；如果今日任务的失败语句是 `UPDATE task`/`COMMIT`，才说明令牌分支参与了。
4. **11-16 14:35 部署之后是否还有锁异常**：对新时间窗重跑同一脚本。
5. **窗口内无令牌任务的数量**（只要一个聚合计数，不取任何行）：需要以只读方式打开数据库，会短暂持有读锁，是否执行由你决定。

不建议也没有做：用真实学生身份调用今日任务或任务详情接口（可能触发令牌写入）。

---

## E. 修复方案（待批准，未应用）

两个补丁相互独立，都只在临时工作树里验证过。

### 补丁 1：`proposed-fix-1-task-access-tokens.patch`（针对本次两个接口，建议采纳）

改动：新增 `services/task_access_tokens.py`（73 行）；`api/miniprogram.py` 两处调用点改为调用它（净减 18 行）；新增 `tests/test_student_task_access_tokens.py`。

- 令牌齐全时不开启任何写事务（原本也是，现在有测试锁定）。
- 补写改为条件更新：只有该列仍为空时才写入。并发时第一个提交者胜出，其余请求读回同一个令牌。
- 补写失败（数据库忙）时回滚并继续返回任务列表，该任务本次不带令牌，下次请求再补；不再让整个列表 500，也不再留下带锁连接。
- 任务详情接口补写失败返回 `503 task_access_busy` 和"系统繁忙，请稍后重试"，不再回显 SQL。把详情接口一并改掉是必要的：两个接口写同一列，只改一个仍会互相覆盖。
- 授权逻辑不变：仍按学生姓名过滤、仍只给 `today`/`completed` 状态补写、令牌校验接口未动。

未解决的：数据库忙时这次请求仍会等满 5 秒才返回（只是结果从 500 变成 200）。缩短这类可选写入的等待时间可以另做。

### 补丁 2：`proposed-fix-2-pool-reset-guard.patch`（全局兜底，建议单独评估）

改动：`models.py` 增加一个 15 行的连接池 `reset` 事件监听，连接归还时若仍在事务中则回滚；新增 `tests/test_sqlite_pool_reset.py`。

它影响所有请求而不只是这两个接口，所以单列。只有 C7 的情形（`COMMIT` 失败且处理函数没有显式回滚）会走到这次回滚；正常请求不受影响。若生产确认是 WAL 模式，它的必要性下降，但保留无害。

### 验证结果

| 检查 | main | 补丁 1 | 补丁 1+2 |
| --- | --- | --- | --- |
| 新增回归测试 `test_student_task_access_tokens`（8 项） | 3 失败 / 5 通过 | 8 通过 | 8 通过 |
| 新增 `test_sqlite_pool_reset`（2 项） | 1 失败 / 1 通过 | 1 失败 / 1 通过 | 2 通过 |
| 强制并发：返回的不同令牌数 / 失效令牌响应数 | 5–6 / 5 | 1 / 0 | 1 / 0 |
| 自然并发 100 轮 ×2 模式：令牌分歧轮数 | 77 / 87（此前两次运行 91–96） | 0 / 0 | 0 / 0 |
| 缺令牌 + 写锁：今日任务 | 500（265 字节） | 200（列表完整，无令牌） | 200 |
| 缺令牌 + 写锁：任务详情 | 500，含 SQL 与参数 | 503，不含 | 503，不含 |
| 今日任务 `COMMIT` 失败后的连带纯读失败（DELETE） | 4 | 0 | 0 |
| 其他处理函数 `COMMIT` 失败后的连带纯读失败（DELETE） | 4 | 4 | 0 |
| 相关既有测试模块（13 个，共 168 项） | 全通过 | 全通过 | 全通过（见下方全量回归） |

全量回归（`python -B -m unittest discover -s tests -p "test_*.py"`，同一环境）：main 1453 项，补丁 1+2 的工作树 1463 项（多出的 10 项即新增测试，全部通过）；两边都是 4 失败 + 4 错误 + 1 跳过，**失败用例集合逐条相同**（`test_exam_sprint_weekly` 4 项、`test_static_audio_headers` 3 项、`test_toefl_practice_v2_rescue` 1 项，与本补丁无关，是本机环境下的存量失败，未进一步排查）。

新文件 `ruff`、`black --check` 通过；`api/miniprogram.py`、`models.py` 的既有 lint 计数前后相同（8 条存量）。导出的两个补丁已在全新工作树上 `git apply` 并重跑 10 项新增测试通过。

### 回归标准（合并前应全部满足）

1. 令牌齐全的任务：今日任务、任务详情、历史任务重复请求产生 0 条写语句。
2. 缺令牌任务：首次请求只写一次，后续请求返回同一令牌且不再写。
3. 6 个并发请求同时遇到缺令牌：全部 200，返回的令牌只有一个，且等于库中值；用它访问令牌保护接口不被 403。
4. 另一连接持写锁期间：今日任务 200 且任务齐全；任务详情 503 且响应体不含 `UPDATE`、`parameters`。锁释放后令牌正常补上。
5. 过期未完成、未来、普通作业任务：不写库。
6. 其他学生的任务不被补写、不可见；错误令牌仍 403。
7. 历史任务：0 条写语句，另一连接持写锁时仍 200，列表与汇总内容不变。
8. （补丁 2）`COMMIT` 失败且未显式回滚后，其他连接可立即读写，后续请求读不到失败请求的未提交改动。
9. 既有 `tests.test_miniprogram_task_visibility`、`test_miniprogram_web_practice`、`test_cambridge_same_day_retry`、`test_teacher_group_homework`、`test_task_planner_resources` 等保持通过。

### 没有放进补丁、需要你另行决定的

- **历史任务接口**：本轮没有找到它自身的锁缺陷，所以补丁没有动它。它的两个结构性风险（`summary_only` 仍加载全部行和大字段；`IN` 列表无上限）会拉长读锁持有时间，是 C8 里的放大因素，建议后续单独优化。
- **切换 WAL 或调整 busy timeout**：属于生产数据库/配置变更，超出本阶段，且要先确认当前模式。
- **首页对 500 的处理**（清空列表、无提示）：属于小程序发包链路。
- **存量无令牌任务的一次性回填**：需要写生产库，超出本阶段。
- **其他提交后不回滚的处理函数**：全仓范围，未核查。

---

## F. 复现命令

```sh
# 依赖（独立 venv）：Flask Flask-Login Flask-SQLAlchemy SQLAlchemy PyJWT pypinyin pyphen openpyxl requests websocket-client
D=docs/reviews/student-tasks-db-lock-20261116
python -B $D/probe_task_endpoints.py --repo . --output $D/probe-main.json          # 约 3 分钟
python -B $D/probe_reader_starvation.py --repo . --output $D/probe-starvation.json  # 约 6 分钟，CPU 密集
python -B $D/probe_failed_commit_lock.py --output $D/probe-failed-commit-sa2.1.json
node $D/client_home_on_500.cjs

# 验证补丁（在临时工作树里，不要直接改 main）
git worktree add --detach /tmp/fix-tree HEAD && cd /tmp/fix-tree
git apply <repo>/$D/proposed-fix-1-task-access-tokens.patch
git apply <repo>/$D/proposed-fix-2-pool-reset-guard.patch      # 可选
python -B -m unittest tests.test_student_task_access_tokens tests.test_sqlite_pool_reset -v
python -B <repo>/$D/probe_task_endpoints.py --repo . --output /tmp/probe-fix.json
```

`probe-fix-endpoint.json` 是只应用补丁 1 的结果，`probe-fix-endpoint-and-pool.json` 是两个补丁都应用的结果。

## G. 局限

- 本机 SQLite 3.53.1、SQLAlchemy 2.1.8（另测 2.0.36）；生产版本未知，`models.py` 注释称生产仍为 Python 3.10。
- 并发比例、耗时都是本机 4 核容器的数字，不是生产预测。
- C8 用纯 Python 死循环代替"CPU 密集请求"，没有用真实词汇接口。
- 小程序行为基于仓库 `miniprogram/` 源码，不是线上 105 包。
- 没有跑真机、没有跑生产、没有全仓 lint。
