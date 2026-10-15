# 词汇“忘了”后端部署记录（2026-10-15）

> 2026-10-15：生产库已一致性备份、显式迁移并逐行核验；后端 `3990007c` 已提交、推送、部署和只读验收。小程序尚未上传，由用户操作。

## 范围与来源

- 实施树：`/Users/zhouxin/.codex/worktrees/9ee5/studytracker`，`codex/vocabulary-forgot-button`，基线 `14b665cdec243615d50baa8e1b55abf3fdd0e29c`；2026-10-15 `git fetch origin main` 后与 `origin/main` 相同（ahead/behind 0/0）。固定小程序源是独立的 `/Users/zhouxin/Desktop/studytracker-release/miniprogram`，前端 11 路径已本机合入，后端部署不复制、不上传它。旧脏主树 `/Users/zhouxin/Desktop/studytracker` 未触碰。
- 仅提交已审的 9 个后端业务路径、5 个 Python 测试路径和本部署/交接文档；隔离前端审阅包 `docs/design/vocabulary-forgot-client-candidate/` 留在本机，不包含在后端部署提交。9 个运行时源文件与 `/private/tmp/studytracker-forgot-deploy-reviewed-sha.json` 的 SHA-256 逐一一致；没有因合并或冲突修改业务候选。该本地清单的基线 HEAD 为 `14b665cd`，迁移脚本 SHA-256 为 `305acf3420a0ed48e3e932fc9ad1983dadce5694ec76341648b7d1e601ff9712`。
- 精确后端业务路径：`api/dictation.py`、`api/miniprogram.py`、`api/vocab_review.py`、`models.py`、`services/vocabulary_autonomous_review.py`、`services/vocabulary_group_learning.py`、`services/vocabulary_mastery.py`、`services/vocabulary_attempt_reporting.py`、`scripts/migrate_vocabulary_forgot_response.py`。必要测试：`tests/test_miniprogram_parent_report.py`、`tests/test_vocabulary_autonomous_review.py`、`tests/test_vocabulary_group_learning.py`、`tests/test_vocabulary_group_learning_api.py`、`tests/test_migrate_vocabulary_forgot_response.py`。

| 已审源文件 | SHA-256 |
| --- | --- |
| `api/dictation.py` | `faaf3b987573f095e79d7bdfdba10f3d21e061899296a88fef6ca610e8f95c9d` |
| `api/miniprogram.py` | `ed2b41ebc9800695380dcde03eb195f2046d0d563c4d607c10f963e48e3fd5b0` |
| `api/vocab_review.py` | `809b032131866aab5498d29d8750f1534f24edaea56da6f21107b29e70884ab1` |
| `models.py` | `bf72e9951f489ce69177045c99023de840a4a2cd31e021e289fb83cf6edd91df` |
| `services/vocabulary_group_learning.py` | `df3264b78ff4b621402de9b510edb95e544b46d22431560d4bad0dec3c298ffe` |
| `services/vocabulary_autonomous_review.py` | `a90aa127751648410157c0964ec89a6def6d7efdd11b89cd170bf24e55ac19f9` |
| `services/vocabulary_mastery.py` | `4a1b86c2fba1ee31e93245ec46236fa8720b60b4dc836971ae218f8670368a44` |
| `services/vocabulary_attempt_reporting.py` | `e4debf68f45acf57996d27431175b69de0f70b2fbe5a4bd3045bb6021ae63989` |
| `scripts/migrate_vocabulary_forgot_response.py` | `305acf3420a0ed48e3e932fc9ad1983dadce5694ec76341648b7d1e601ff9712` |

## 提交前验证

- 在实施树重跑：

  ```sh
  TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q --disable-warnings --tb=short -p no:cacheprovider tests/test_migrate_vocabulary_forgot_response.py tests/test_vocabulary_group_learning.py tests/test_vocabulary_group_learning_api.py tests/test_vocabulary_autonomous_review.py tests/test_vocabulary_mastery.py tests/test_dictation_review.py tests/test_miniprogram_parent_report.py tests/test_miniprogram_vocabulary_learning.py tests/test_task_date_gate.py tests/test_vocabulary_review_performance.py
  node tests/test_dictation_spell_queue.js
  git diff --check
  ```

  结果：**173 passed / 2 subtests passed**；工作流 Node 守卫及差异检查 exit 0。14 个相关 Python 文件以 3.10 grammar 解析通过；生产 `/root/apps/studytracker/.venv/bin/python` 是 3.10.12，迁移与核验脚本在该解释器下编译并在一次性合成 SQLite 上完成 inspect/backup/migrate/verify 全流程，exit 0。该合成测试不读写生产学生数据。

## 生产迁移（先于后端 push）

- 生产部署树 `/root/apps/studytracker` 起始 `main@675a34731d54410738a4499b0c55eaf349624d20`，tracked clean，17 个既有 untracked 入口保留；服务 5002、`workers=1`、gthread、`threads=6`，生产 Python 3.10.12，SQLite 3.37.2。既有 `/usr/local/sbin/deploy-studytracker` 会拉取 main、`git reset --hard origin/main` 并重启，但**不运行本次迁移**；因此先完成显式迁移与核验才允许 push。生产实际数据库经 `config.py` 与 `readlink -f` 确认是 `/root/apps/studytracker/app.db`，非符号链接。迁移前 `quick_check=ok`、外键错误 0、四张目标表存在、五列均不存在；磁盘可用约 13.8 GB。
- 2026-10-15 09:28:56–09:29:03 CST 短维护窗口停服务，先用 Python `sqlite3.Connection.backup` 做同机一致性备份：

  ```text
  /root/backups/studytracker/vocabulary-forgot-20261015-14b665cd/app.db
  ```

  备份 190,242,816 字节，SHA-256 `c8572b2fd6e3670282f919352bec01701528f407eccd18df16730a31d3e8997a`，`quick_check=ok`、外键错误 0；目录权限 0700、文件 0600。备份保留在生产机，未复制到本地或仓库，包含真实数据，须限制访问。迁移前行数：`dictation_record` 62,680、`vocabulary_learning_question` 38,867、`vocabulary_review_item` 6,887、`vocabulary_review_attempt` 9,026。
- 使用与已审 SHA 相同、暂存于根用户受限目录的脚本执行：

  ```sh
  /root/apps/studytracker/.venv/bin/python /root/.codex-vocabulary-forgot-rollout-20261015/migrate_vocabulary_forgot_response.py --database /root/apps/studytracker/app.db
  ```

  输出准确为五列：`dictation_record.response_kind`、`vocabulary_learning_question.first_response_kind`、`vocabulary_learning_question.retry_response_kind`、`vocabulary_review_item.first_response_kind`、`vocabulary_review_attempt.response_kind`。生产脚本不导入应用，事务使用 `BEGIN IMMEDIATE`。随后以生产 Python 3.10 执行 `/root/.codex-vocabulary-forgot-rollout-20261015/studytracker_forgot_prod_db_guard.py verify --database /root/apps/studytracker/app.db --backup /root/backups/studytracker/vocabulary-forgot-20261015-14b665cd/app.db`：五列均 `NOT NULL=1`、默认 `answer`、NULL=0；新旧库 `quick_check=ok`、外键错误 0。
- 停服窗口内逐行比较了四张迁移表的全部原有列，及 `task.id/accuracy/completion_rate`（6,106 行）、`vocabulary_task_settlement.id/result_json`（393 行）、`vocabulary_review_session.id/result_json`（350 行）、`vocabulary_review_settlement.id/result_json`（311 行）；全部相等，行数相同。没有重算/改写真实学生的答案、成绩或结算记录。原服务于 09:29:03 恢复 active，`NRestarts=0`，`http://127.0.0.1:5002/` 返回 302；生产仍是旧 HEAD `675a3473`，tracked clean。
- 服务端非 Git 操作日志留在根用户受限目录 `/root/.codex-vocabulary-forgot-rollout-20261015/` 的 `backup.json`、`migration.txt`、`verify.json`。线上数据库的当前行数会随正常学习继续增长；上述逐行相等结论只针对维护窗口的冻结快照。

## 后端发布与验收

- 2026-10-15 在实施树将精确 15 路径（上列 9 个业务源、5 个测试、本报告）提交为 `3990007cd8ab36eb2eff918153c244487499b9d2`（`feat: persist vocabulary forgotten responses`）；提交前 `origin/main` 仍为已审基线 `14b665cd`、生产 tracked clean 且备份存在。使用 `git push --atomic origin HEAD:refs/heads/codex/vocabulary-forgot-button HEAD:refs/heads/main` 非强制原子推送两分支。固定发布树和旧主树均未纳入该提交。
- [CI `38666056690`](https://github.com/KB77GG/studytracker/actions/runs/38666056690) 与 [Deploy `38666056649`](https://github.com/KB77GG/studytracker/actions/runs/38666056649) 均为 completed/success；CI 的全仓 Ruff advisory 仍有仓库既有旧脚本诊断，工作流总体成功。部署脚本由 main push 触发，未手动执行第二次部署。
- 生产 `/root/apps/studytracker` 的 `HEAD` 和 `origin/main` 均为 `3990007cd8ab36eb2eff918153c244487499b9d2`；tracked dirty=0，原 17 个未跟踪入口保留。上表 9 个生产源码 SHA-256 逐一等于已审候选。服务自 2026-10-15 09:31:36 CST active，`NRestarts=0`，`127.0.0.1:5002`、`workers=1`、`worker_class=gthread`、`threads=6`，监听为 master 与单 worker；回环 `GET /` 返回 302。自 09:30 起该 service 的 error 级 journal 条目 0。
- 部署后以 `/root/apps/studytracker/.venv/bin/python /root/.codex-vocabulary-forgot-rollout-20261015/studytracker_forgot_prod_db_guard.py inspect --database /root/apps/studytracker/app.db` 再查：`quick_check=ok`、外键错误 0，四表五列均 `NOT NULL=1`、默认 `answer`、NULL=0；四表行数仍与维护快照一致。未认证 `GET /api/miniprogram/student/vocabulary-review/today` 返回 401，证明权限闸门仍生效；未使用普通 today/queue GET 领取真实批次，因为这些路径会写入。
- 生产 Python 3.10 下的纯合成模块探针 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python /root/.codex-vocabulary-forgot-rollout-20261015/studytracker_forgot_runtime_probe.py` 通过：明确 `forgot` 被接受，无字段/NULL 仍为旧客户端 `answer`，无效类型被拒绝，五个 ORM 字段仍为非空且默认 `answer`。探针不创建 app、连接库、登录账号或发 HTTP 作答；结合上线前 173 项临时 SQLite 回归与生产文件 SHA，构成当前可做的无真实学生写入验收。完整新客户端在线联调和真机仍待用户上传后进行。

## 回滚入口与未完成项

- 如新后端出现故障，可回滚到部署前后端提交 `675a34731d54410738a4499b0c55eaf349624d20` 的业务代码并重启；五个加法列可保留，旧客户端默认 `answer`，无需破坏性删列。数据库备份只作灾难恢复入口；若其后已有真实写入，不可直接覆盖当前库，否则会丢失新作答。回滚或再次发布前先确认实际 Git/DB 状态。
- 小程序本轮未上传/提审/发布；用户将在后端上线后从固定目录 `/Users/zhouxin/Desktop/studytracker-release/miniprogram` 自行上传。完整微信项目、iOS/Android 真机、真实双端并发与线上新客户端端到端验收仍待用户完成。生产数据库是实际运行库，后续自然行数增长不代表本次迁移重写历史。
