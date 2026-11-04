# 独立覆盖审阅与 03:00 回归

审阅日期：2026-11-04。审阅者为独立 coverage agent；本文件区分历史验证、服务/API 回归和完整学生流程，不以数量相加宣称端到端验收。

## 基线与范围

- 先读 `/Users/zhouxin/.codex/worktrees/task-planner-beta/studytracker` 的 AGENTS、CLAUDE、交接相关记录，并核对该树为 `codex/task-planner-beta@6904252e`、clean；该树保持只读。
- 本轮测试树：`/private/tmp/studytracker-recovery-e2e-20261104`，detached HEAD `f0e04041`。包含补做业务 `d636398e` 与 11 月 3 日学生任务列表修复；本轮开始时 recovery 核心与 `d636398e` 相同。
- 旧主资料树 `/Users/zhouxin/Desktop/studytracker` 为旧 main 且有既有改动，本 agent 仅借用其 `.venv`，未修改其业务或交接。
- 不读取生产学生、不调用生产 API、不发送通知或调用付费模型。此处使用的姓名、账号、题目与 SQLite 均为测试夹具合成内容。

## 历史 335 项实际覆盖

来源为 `6904252e:docs/CODEX_HANDOFF.md` 的 2026-11-02 条目及对应源码：原 planner 160 + 新 recovery 26 + 旧回归 71 + Node 78。历史记录明确包含一次 185 项整组、最终 26 项 recovery 单跑等批次，不能改写为 335 项单次或师生端到端验证。

| 环节 | 已有验证 | 本轮应补的证据 |
| --- | --- | --- |
| 助教收件箱、预览、确认 | 服务/API 合约、模拟 DOM；Chrome 合成甲补做、乙继续、丙当日已发布阻断 | 师生同一数据链、学生完成后下一次自动运行 |
| 补做完成 | `tests/test_task_planner_recovery.py::settle()` 直接改 Task/PlanItem 提交字段或插入词汇结算 | 学生真实开始/答题/提交 HTTP 入口及成绩记录 |
| 后续布置 | recovery 场景主要直接调用 `publish_entry()` | 受控时间调用 `run_due()`，03:04:59 不发、03:05 发、重复运行不重发 |
| 03:00 宽限 | 旧日期门禁已有单独回归 | 收件箱与恢复操作是否尊重同一截止时间；旧链接合法提交与恢复的交叉行为 |
| 阅读整套 | 三原生任务/bundle 完整性、部分补做、原子失败回滚 | 学生逐篇完成、13/13/14 题、部分未交仍挡后续 |
| 连续多天 | 服务级多次补做与祖先去重 | 多天真实学生链路与调度结果 |
| 原成绩 | 原 Task 部分字段保持、历史相关旧回归 | 原 Task/PlanItem/ReadingTestSubmission/attempt 前后对比，新提交属于新 Task |
| 微信 | Chrome 390×844 无溢出 | 真机微信 WebView、登录/跳转/返回/刷新及实际凌晨服务运行 |

本轮没有重复运行整个历史 335 项。新测试第一次使用类导入时，unittest 意外额外收集了 26 个旧 recovery 方法（均通过）；随即改为模块导入，之后单独运行只收集 11 个新增方法，历史 26 不计入新增验证。

## 新发现：仍在合法宽限期的任务可以被提前补做

旧 `list_inbox()` 与 `_source()` 仅检查 `source_date < today`。到北京时间午夜，昨天任务便进入收件箱并允许确认；学生任务门禁却允许它继续写入至 03:00。

独立服务探针在修复前观察到：

1. 10 月 30 日 02:59，10 月 29 日原阅读三任务均 `can_write=true`，收件箱已有一组，补做预览 `can_apply=true`，无宽限警告。
2. 确认生成三条新补做后，原三任务在 02:59:30 仍可写。
3. 将原任务模拟为此时有效提交后，10 月 31 日 03:05 的 `run_due()` 返回 `eligible=3,published=0,blocked=3`；新补做仍未完成，学生必须再做一次才能恢复该线。

第 3 步的早期独立探针直接写合成完成字段，仅用于定位，**不作为学生 HTTP 提交验收**。主验收另以真实提交接口重现，原始证据见同目录 `baseline-grace-race.json`。

因此问题不是显示文案偏差：提前恢复可在学生合法完成原任务后留下新的未完成任务并继续阻塞计划。最小候选修复由主 agent 实施于 `services/task_planner_recovery.py`：复用 `task_date_cutoff_local()`，截止前隐藏该来源组，并在共用 `_source()` 对 preview/apply 两种动作返回 HTTP 409 / `source_still_open`。更早积压、03:00 恰好截止和已成功请求重放仍可用。

## 新增独立回归结果

新增 `tests/test_task_planner_recovery_cutoff.py` 的 11 个测试方法：

- 午夜与 02:59:59 不展示仍开放任务；学生 `can_write` 同时为 true。
- 北京时间、带时区 UTC、无时区 UTC 的 03:00 截止保持一致。
- `makeup` / `continue` 服务 preview 与 apply 不得绕过截止；拒绝前后 Task、PlanItem、entry、decision 与冻结定义不变。
- 助教已登录且 CSRF 有效的真实蓝图 GET/POST 返回相同门禁结果。
- 03:00:00 两种动作开放；原任务仍保持原字段且只读。
- 02:59 可处理前天及更早积压；下一次午夜旧成功 request key 可幂等重放。

精确命令（cwd 为上述隔离测试树）：

```bash
TZ=UTC PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_task_planner_recovery_cutoff -q
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check --no-cache tests/test_task_planner_recovery_cutoff.py
```

修复前：11 方法，6 方法失败，共 9 个失败断言/子测试，5 方法通过；退出 1，2.281 秒。API apply 实际返回 200，直接 apply 未抛出异常，午夜/02:59 收件箱仍列出原任务。详见 `baseline-cutoff-tests.log`。这是红测证据，不能计为通过。

修复后：同一新增测试 **11/11 通过**，退出 0，2.362 秒；Ruff 通过。独立审阅候选差异确认只增加共享截止判断，未改变任务日期、成绩、排程时间窗、已发布保护、原子事务和成功请求重放路径。

## 验收边界与交接

本文件中的 11 项是隔离服务/API 回归，完整师生提交链、浏览器操作及总体验收结果以同目录主报告为准。03:05 为函数受控时间运行，不能证明生产 systemd 下一次一定实际执行；Chrome 窄屏不等于微信真机。真实设备与真实学生操作仍需独立明确验收授权与执行记录。

本 agent 新增测试及此报告/红测记录均仅本机、未 commit/push；未合并、部署、修改生产库或发布小程序。仓库规范交接由主 agent 汇总本轮全部成果，避免并行覆盖。

## 最终候选只读复审

结论：**GO，可交用户审阅批准；不代表已批准合并或部署。** 未发现本候选范围内新的业务阻断。

- 运行代码差异为 recovery 服务 18 增/3 删与模板一处说明；核心新增判断与学生端复用同一 `task_date_cutoff_local()`。时区先归一化，03:00 为排他截止，已成功幂等请求仍在重新预览前返回；原成绩、其他学习线、03:05 调度、已发布保护和事务逻辑未改。
- 公开用法和页面说明均明确截止前不能补做/忽略，03:00 开放，更早积压不受当天宽限期限制；与候选行为一致。
- 只读审查新增 9 项师生 journey 与 2 项小程序接口合约：使用真实登录、CSRF/JWT 校验、任务读取、阅读提交/判分和 `run_due()`；不以直接改完成状态代替学生提交。阅读 13/13/14 题、2/3 未完成阻塞、连续三次补做、原 Task/PlanItem/submission/attempt/ScoreRecord 和其他线快照有对应断言。此 11 项通过 Flask test_client 执行真实 WSGI 路由；主 agent 的 Chrome 回环访问另构成实际浏览器/HTTP 证据，二者应分别报告。
- CI 将新增 11 项截止测试放入现有 model-light planner job；新增 9+2 放入已加载真实 app 的 account-provisioning job。该 job 已安装 Flask、SQLAlchemy、PyJWT、pypinyin、requests、certifi、websocket-client、openpyxl 等启动所需依赖，阅读判分无额外重模型依赖。静态复核未发现必需依赖缺口；本轮未在干净 Linux 或 GitHub runner 上实际执行，不能声称远端 CI 已通过。
- 主 agent 报告组合 48 项（新增 22 + 原 recovery 26）15.338 秒通过，Node recovery 16 项通过；这属于主验收结果，本 agent 未再次重复运行。本 agent 独立执行的 11 项与静态检查结果见上节。
- 微信登录凭据交换、真机 WebView 与生产下一次真实 systemd 触发仍待实测；此候选未新增词汇完整学习队列端到端验证，不把原词汇服务级回归扩写为该结论。
