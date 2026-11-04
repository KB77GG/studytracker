# 学生端独立复核（2026-11-04）

工作树 `/private/tmp/studytracker-recovery-e2e-20261104`，detached HEAD
`f0e04041`。本报告与新增测试仅本机，未 commit/push/deploy；没有访问生产或
操作真实学生。开工树 clean，当前其他 agent 的恢复截止修复及验收文件属于同轮工作，
本子任务只新增本文和 `tests/test_task_planner_recovery_student_contract_e2e.py`。

## 本次执行结果

真实 `app.py`、Flask 路由、SQLAlchemy 写入和鉴权，独立临时 SQLite 与合成资源，
受控北京时间；使用 `tests/recovery_e2e_support.py`。测试通过助教正式接口创建、
确认、发布学习线，再预览及确认恢复，没有手工插入补做任务。

- 阅读整套补做：学生小程序服务端 `tasks/today`、`tasks/<id>`、
  `reading/cambridge/<id>` 均显示三个新任务，各自一个篇章、合计 40 题。
  三个新 token 互异且不同于原任务 token；补做详情包含原日期说明，新成绩为 null。
- 原 token 用于新任务的阅读 GET 或提交均返回 403 `invalid_token`。
  另一合成学生读取详情为 403、读取阅读内容为 404，其首页没有该补做任务。
- 补做次日 02:59:59，小程序首页宽限提示、详情和网页任务列表均可写；
  03:00:00 首页宽限提示关闭，任务只读，网页真实提交返回 403 `task_expired`。
- 外连守卫记录为空。合成数据与临时库随 fixture 清理；未发送通知。

精确命令（工作目录为上述隔离树）：

```bash
TZ=UTC PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_task_planner_recovery_student_contract_e2e -v
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check --no-cache tests/test_task_planner_recovery_student_contract_e2e.py
```

结果：**2 tests OK / 1.558s**；Ruff 通过。日志 `/private/tmp/recovery-student-contract-e2e.log`。
初次运行发现测试支撑使用 `patch.dict(sys.modules)` 导致第二次装载 app 时蓝图重复
注册，已由支撑文件负责人改为只恢复 `config` 模块后整组通过。这是验收夹具问题，
不算产品缺陷。另因应用不挂载通用 `/api/v1/auth/login`，测试通过 `issue_token`
为合成用户提供 JWT，再走实际 `require_api_user`；未模拟微信凭据交换。

## 源码核对结论（与运行验证分开）

- `services/task_planner_resources.py:966` 每次创建原生阅读任务生成新 token，
  任务与计划项共享该任务自己的 token。
- `app.py:566` 的有效 token 页面上下文携带 task_id。
  `templates/reading/test_practice.html:615` 的作业草稿键包含 task_id；
  新补做与原任务草稿使用不同键。这里只核对了代码，浏览器实际草稿操作由主验收另记。
- `app.py:7985` 提交核对 task_id、token、资源，并使用服务端任务的篇章范围。
  `ReadingTestSubmission` / `PracticeSubmissionAttempt` 关联 task_id；
  `app.py:1096` 的 ScoreRecord assessment_name 包含任务编号。
  原成绩的逐字段保持由主师生流程测试负责，本两项不重复计数。
- `static/js/practice_task_lists.js` 使用服务器日期状态分类：新补做进入当前任务，
  原截止未完成保留历史。具体渲染与按钮点击以主浏览器验收为准。
- 非阻断体验备注：补做标记位于 Task.note（小程序详情 instructions），
  原生 Task.detail 保持资源标题；网页任务卡片暂不显示 note，因此卡片没有“补做”字样。
  新任务所属日期、链接和权限正确，本轮未扩大修改界面文案。

## 隔离检查与剩余实际验收

真实 `config.py` 会自动读取本目录 `.env`，并硬编码本目录 `app.db` 为默认 URI；
仅设置 DATABASE_URL 不能保障隔离。当前 fixture 在 app 导入前注入合成 Config，
断言 engine 指向临时数据库，startup 建表也留在临时库；上传和题库路径另行隔离，
网络连接与 requests 有守卫。未读取私有 `.env`、真实库或生产凭据。

这两项是合成账号的服务端跨模块测试，**不是微信设备验收**。尚需获批环境中通过
实际已发布的小程序版本确认：首页刷新及日期切换、阅读原生页面三个篇章、
WebView 返回/重开、切后台后截止提示、旧链接只读、新任务提交回到任务列表后的状态。
本轮没有上传、提审或发布小程序，也没有替任何真实学生决定补做或忽略。

下一位可直接运行上述命令；真实设备验收不能由这两项通过替代。规范交接由主 agent
统一更新，避免并行覆盖 `docs/CODEX_HANDOFF.md` / `docs/WORKLOG.md`。
