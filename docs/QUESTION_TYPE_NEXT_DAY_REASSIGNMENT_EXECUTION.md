# 题型专项跨日再次布置与历史记录执行报告

## 结论与范围

- 用户问题已在本机候选中修复：同一题型专项的旧任务若仍未完成，且旧任务日期严格早于新任务目标日期，老师可在新日期直接再次布置；原任务、PlanItem、快照、作答、成绩和计时均独立保留。
- 老师可从昨日任务、重复历史矩阵或任务列表打开无 token 的专项记录。未开始、仅计时/进行中、已提交但缺逐题记录、已完成但缺逐题记录及正常已提交结果均有只读展示；查看不会创建 attempt 或改写旧任务。
- 本轮仅涉及网页任务中心、题型专项 API、老师历史页及其测试。没有修改微信页面、小程序、题库 JSON、音频、schema 或生产配置，也没有写生产或真实学生数据。
- 执行工作树：`/Users/zhouxin/.codex/worktrees/86d7/studytracker`；分支 `codex/question-type-review-audio`；基线 `7b7e9fa2ec874a0f4d7b838250020ddb066a4115`；业务提交 `675a34731d54410738a4499b0c55eaf349624d20` 已推送并部署。
- 最终独立本机审阅与生产验收结论均为 **GO**，无阻断项。

## 实现结果

1. 日期策略集中在 `services/task_assignment_duplicates.py`：
   - 题型专项的 `pending / in_progress` 旧任务只在 `old_date < target_date` 时标记为可跨日再次布置。
   - 同日、倒序、缺失或非法日期继续保守阻断；既有 `force_repeat + confirm_repeat + 至少 2 字原因` 的人工覆盖权限保持不变。
   - 已提交/已完成状态使用 `task_workflow_status`，综合 Task、`student_submitted`、`submitted_at` 与 PlanItem，不能被陈旧的 `Task.status` 误判为未完成。
   - 返回每条历史的服务端 `blocking / requires_confirmation / reassignable`，同一学生×题组保留全部匹配，并只从仍受保护的历史生成自动排除题组。
2. 昨日专项复用在 `services/task_assignment_history.py` 恢复科目、标准题型、完整 `group_ids`、节奏、用时和备注，只暴露安全字段，不复制答案或完整冻结 payload；已提交专项不会伪装成未完成复用项。
3. `api/question_type_practice.py` 严格校验目标日期；自动选题复用统一重复策略；新发布仍生成独立 Task、PlanItem、token 和 snapshot，幂等键重试不重复创建。
4. 新增老师只读历史页 `templates/question_type_practice/history.html`：
   - 无 attempt 的 GET 不再 404，也不会创建 attempt。
   - 任务计时已启动但没有专项 attempt 时显示“进行中”；已提交/已完成但缺逐题记录时明确显示“无逐题记录/暂无可展示成绩”。
   - 页面不显示内部 snapshot hash、token 或机器时间字段，也没有写入/提交控件。
5. `templates/tasks.html` 与 `static/js/task_assignment_matrix.js`：
   - 昨日专项可精确回填并同步题组数；目标日期变化会重新查询历史并丢弃过期异步响应。
   - 前端只使用服务端决策，不再自行按状态猜阻断；每个题组展示全部历史。
   - 未提交专项在普通任务行提供无 token 的“专项记录”；已提交仍保留既有“逐题结果”，不重复入口。

## 不变量与边界

- 跨日再次布置只创建新记录，不更新旧 Task/PlanItem、旧快照、旧答案、旧成绩、旧提交时间或旧计时。
- 次日 03:00 仍只控制旧任务的学生写权限，不控制老师是否可以提前规划新任务。
- `retraining_mode` 等客户端字段不能绕过服务端冲突检查。
- 已提交、已完成及其他受保护历史继续要求二次确认与原因；非题型专项的原重复策略未改变。
- 老师历史链接一律使用 `/tasks/question-types/<task_id>/result`，不暴露学生 assignment token。

## 验证

主任务最终相关回归（最后一项 workflow 一致性调整前，调整后另有窄集覆盖）：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_question_type_catalog_ui_contract.py \
  tests/test_question_type_practice.py \
  tests/test_question_type_practice_contract.py \
  tests/test_question_type_practice_routes.py \
  tests/test_question_type_review.py \
  tests/test_role_attempt_history.py \
  tests/test_task_assignment_deduplication.py \
  tests/test_task_assignment_history.py \
  tests/test_task_assignment_routes.py \
  tests/test_task_date_gate.py \
  tests/test_task_date_gate_display_contract.py
```

- 结果：**129 passed，7 subtests passed**；693 个 warning 均为既有 `datetime.utcnow` / SQLAlchemy legacy 警告。

```bash
node --test \
  tests/test_listening_clip_player.js \
  tests/test_practice_renderers.js \
  tests/test_question_type_review_readonly.js \
  tests/test_task_assignment_matrix_renderer.js \
  tests/test_tasks_workspace_structure.js
```

- 结果：**46 passed**。

最后一项“昨日专项也使用 workflow 状态”调整后的窄集：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_task_assignment_history.py \
  tests/test_task_assignment_deduplication.py
```

- 结果：**23 passed**。

静态检查：

```bash
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check \
  api/question_type_practice.py \
  services/task_assignment_duplicates.py \
  services/task_assignment_history.py \
  tests/test_question_type_practice_routes.py \
  tests/test_task_assignment_deduplication.py \
  tests/test_task_assignment_history.py
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m py_compile \
  api/question_type_practice.py \
  services/task_assignment_duplicates.py \
  services/task_assignment_history.py
node --check static/js/task_assignment_matrix.js
git diff --check
```

- 结果：全部通过。

独立复核：

- Python 主组合 **101 passed / 2 subtests passed**，旧布置/计时/日期显示补充组合 **31 passed**，Node **59 passed**。
- 隔离内存数据库与 5093 Chrome 已确认：昨日专项精确恢复原题组；同组三条历史均可见；目标日从同日改为次日后确认区消失；次日直接发布由 3 条增至 4 条；原任务快照、作答、计时不变；Reading 与 Listening 路由 probe 均生成独立 Task/PlanItem，幂等与同日 409 正常；未提交历史页只读且学生无权访问。
- 最终候选再次运行三份变动 Python 模块相关测试 **41 passed**、Node 矩阵 **4 passed**；Reading 与 Listening 独立路由 probe 再次全部通过。
- 最终 Chrome 确认：昨日卡恢复原题组、组数 1、用时 12；三条历史分别保留具体“未开始/进行中”状态；同日显示确认、次日隐藏确认并能真实创建新任务；未提交历史不显示 0 分，已保存草稿保持只读，截止时间显示北京时间 03:00；普通任务列表的“更多操作 → 专项记录”可直达未开始历史。最终结论 **GO**。
- 最终六个运行时文件 SHA-256：`api/question_type_practice.py` `357f29877bf627b378529e7ec3b407ba06df0eaf92e3ad818c6a37c97e4cac6c`；`services/task_assignment_duplicates.py` `75d3fadd19be991d9719b669f81c44c56d3949ae4ac7acb38709b705e97f92a9`；`services/task_assignment_history.py` `f2095190d887be9aa2a49bfaef4c9a6f42eb1b868072f26d6e9c432eb278cb24`；`static/js/task_assignment_matrix.js` `e67a2d3271107f85279f5c931176ee7bc39eede5f1c5936ecb1a673049f32378`；`templates/tasks.html` `b007474cd0b28e88c7ce08b37dc3f4af1854e8125bb43ef397037dfae1e1cb36`；`templates/question_type_practice/history.html` `f7220182d4587b9044fb98b0d8d24ad35e36faa12c96752a46b8a802d191cc6a`。
- 5093 是隔离终审预览，不是交付或生产服务；独立审阅已核对命令后停止最终 PID 54517，并关闭两张验收标签。内存数据随服务终止消失；匿名验证脚本和日志仍保留在 `/var/folders/ly/2q45cg3x51zdj5g09p6p56gh0000gn/T/studytracker-reassignment-review-pfya96ut` 供本机复核。5092/PID 45861 未受影响，`/preview` 复核为 200。

## Git、预览与发布状态

- 业务提交包含：
  - `api/question_type_practice.py`
  - `services/task_assignment_duplicates.py`
  - `services/task_assignment_history.py`
  - `static/js/task_assignment_matrix.js`
  - `templates/tasks.html`
  - `templates/question_type_practice/history.html`
  - `tests/test_question_type_practice_routes.py`
  - `tests/test_task_assignment_deduplication.py`
  - `tests/test_task_assignment_history.py`
  - `tests/test_task_assignment_matrix_renderer.js`
- 文档计划、执行报告和两份规范交接由部署验收后的 `[skip ci]` 纯文档提交同步，不触发第二次业务部署。
- 用户原有 `127.0.0.1:5092`、PID 45861 预览保持运行且未触碰；它仍对应上一轮解析/音频模块预览，不是本轮生产验收环境。
- 业务提交 `675a34731d54410738a4499b0c55eaf349624d20`（`fix: allow next-day question type reassignment`）已用非强制原子推送同步任务分支与 `main`。任务分支 CI [35234417214](https://github.com/KB77GG/studytracker/actions/runs/35234417214)、主线 CI [35234417432](https://github.com/KB77GG/studytracker/actions/runs/35234417432)、Deploy [35234417419](https://github.com/KB77GG/studytracker/actions/runs/35234417419) 均为 **success**；test 与拼写门禁通过，advisory Ruff 只列仓库既有旧迁移脚本问题，本任务目标 Ruff 通过。
- 生产 `/root/apps/studytracker` 已核对为 `main@675a3473`、tracked 干净，原 17 个 untracked 备份/静态快照/调度文件保留；六个本轮运行时文件及八个既有解析/音频保护文件共 14 个 SHA-256 与候选一致，公网 matrix SHA 为 `e67a2d32…32378`。`studytracker.service` 自 2026-09-17 22:34:34 CST 起 active，`NRestarts=0`；`127.0.0.1:5002`、`workers=1 / gthread / threads=6`，实际一主一 worker。SQLite 只读 `quick_check=ok`、外键错误 0，服务启动后 warning journal 为 0。
- 独立生产只读探针位于 `/tmp/studytracker-reassignment-deploy-rhP5Sy/`。`verify_runtime_reviews.py` 确认既有 submitted Listening 12/12 均有 analysis/evidence/clip、3/3 题组可播放，Reading 17/17 均有 analysis/evidence；相关页面均 200 / `read_only=true`，GET 前后 snapshot/hash/answers/results/submission/grade/duration 完全不变。
- `verify_staff_history.py` 使用生产 SQLite `mode=ro/query_only` 和仅服务器内存中的合法 staff 会话，未输出或保存密钥、会话或学生信息；仅执行 GET 与无写入 duplicate-history POST。Listening/Reading 各抽查无 attempt 与 saved draft 共四类样本：staff 历史页 200、匿名访问被拒、未提交不显示成绩；同日 `blocking=true`，次日 `reassignable=true` 且无需确认；矩阵保留完整历史、任务中心入口存在、昨日一条专项 repeat 字段精确；Task/PlanItem/attempt 整行前后不变且未创建 attempt。正式发布写路径只使用本机内存库和 Chrome 验收，没有用真实学生执行发布写入。
- 生产验收初版探针曾误读 repeat payload 字段，且未设置 `period=year` 导致旧任务不在默认周范围；两项均只修正临时探针后通过，未修改业务代码或生产数据。
- 本轮已完成发布，不再需要业务部署。后续只观察真实网页反馈；小程序、微信页面、schema、题库和音频均未改，小程序未上传/提审/发布。
