# 小班课后作业分发修复（2026-11-14，后端已部署）

## 当前状态

用户先授权修复，随后明确“要的，你部署吧”。实现/发布树 `/private/tmp/studytracker-small-class-homework-20261114`，分支 `codex/small-class-homework-20261114`，基线 `44f3bccdc9d4cb978c6df4b4c9ab7a5b2baa1211`；12个产品/测试/CI文件已提交 **63fa27f9cefc974ab15c76c90f96e8e1ee0468a7**，推送任务分支及main并完成后端部署。报告与两交接另以 `[skip ci]` 文档提交同步，最终文档HEAD以Git为准。小程序源码已推送，但微信端尚未上传、提审或发布，不能把后端部署当作小程序全功能已经可用。

主资料树 `/Users/zhouxin/Desktop/studytracker` 保留旧main@`6ded77d24586327ad94e151e172ae4811b4a2eed`和原7 modified/23 untracked入口，本轮只更新两交接，未pull或改其他业务。新实现树最终应clean。其他机器可从远端取得修复；旧主树其他未提交资料仍只在Mac。

## 已实现

- 作业页从教师真实课表核验接收名单。支持排课服务已有 `student_profiles` 成员，以及可信排课记录内 `/`、`／` 分隔的旧合并姓名；不拆英文姓名中的空格、逗号。不信任客户端自报成员，原合并排课ID不绑定任一成员。
- 各成员需唯一匹配未删除的个人档案；缺失、同名、名单冲突均阻止整批。页面列明缺失成员，不能静默跳过。签名名单确认绑定操作者、课程、日期和每个个人档案；提交前实时复查，名单变更或过期需刷新。
- 三人两项练习一次请求原子创建六份Task，每个学生拥有独立完成状态和听读访问令牌；不会因为首个成员已经绑定而只发给该成员。名单字段、学科权限和课程来源由服务器核验；管理员可操作明确指定老师的真实课表，普通老师仅自己的课程。
- 利用既有 Task.assignment_idempotency_key 和 AuditLogEntry 保存整批回执，无schema新增。SQLite BEGIN IMMEDIATE串行化保存，冲突整批回滚；相同请求重试不重复建任务或发提醒，已删除批次不自动重建。页面按登录账号及课表缓存最近未确认提交的幂等键，网络失败重开页面仍能复用，不缓存签名令牌。
- 保存成功后逐人发送提醒，失败单独列明，不把微信提醒失败误报为作业保存失败。无微信绑定、停用账号或无订阅不会丢失已保存Task。提醒仍同步发送，极大批次可能导致客户端先超时，重试可确认保存但不会补发提醒。
- 小班列表按人显示作业、完成状态、听读成绩和历史结果，单独修改/删除。快捷入口继续检查学科限制；A班名单不能搭配B学生快捷token。小班隐藏旧单人“加布精听”快捷按钮，仍可正常选择精听群发。
- 旧单人创建入口遇合并姓名（包括快捷入口可信课表里的合并名单）返回409 group_assignment_required，防止旧客户端误发首人。

## 文件

修改6个既有产品/CI文件：`.github/workflows/ci.yml`、`api/__init__.py`、`api/miniprogram.py`、`miniprogram/pages/teacher/homework/index.js`、`index.wxml`、`index.wxss`。巨型miniprogram.py仅一个import及两行委托拦截。

新增6个产品/测试文件：`api/teacher_group_homework.py`、`services/teacher_homework_recipients.py`、`miniprogram/utils/teacher-group-homework.js`、`tests/test_teacher_group_homework.py`、`tests/test_teacher_homework_recipients.py`、`tests/test_teacher_group_homework.js`。这12个文件已纳入业务提交。另新增本报告、只读验收脚本及脱敏结果，修改本树两交接，以文档提交同步。

## 验证

以下cwd均为实现树，Python使用主资料树既有venv，测试仅合成内存数据库，外部课表和通知mock，不import生产app/config：

```sh
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_teacher_homework_recipients tests.test_teacher_group_homework tests.test_teacher_practice_access tests.test_miniprogram_teacher_intensive tests.test_miniprogram_teacher_jijing tests.test_miniprogram_task_visibility -q
node --test tests/test_teacher_group_homework.js tests/test_teacher_intensive_shortcut.js tests/test_teacher_jijing_options.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check api/teacher_group_homework.py services/teacher_homework_recipients.py tests/test_teacher_group_homework.py tests/test_teacher_homework_recipients.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m black --check api/teacher_group_homework.py services/teacher_homework_recipients.py tests/test_teacher_group_homework.py tests/test_teacher_homework_recipients.py
node --check miniprogram/pages/teacher/homework/index.js
node --check miniprogram/utils/teacher-group-homework.js
/Applications/wechatwebdevtools.app/Contents/Resources/app.asar.unpacked/node_modules/wcc-exec/wcc -o /private/tmp/group-homework-wxml-20261114.js miniprogram/pages/teacher/homework/index.wxml
/Applications/wechatwebdevtools.app/Contents/Resources/app.asar.unpacked/node_modules/wcc-exec/wcsc -o /private/tmp/group-homework-wxss-20261114.js miniprogram/pages/teacher/homework/index.wxss
git diff --check
```

主审最终复跑：**100 Python（28名单 + 34 API + 38相邻回归）、22 Node通过**；4新增Python文件Ruff/Black通过，6修改/新增Python文件`ast.parse(..., feature_version=(3,10))`通过，两JS语法、微信WXML/WXSS实际编译和diff检查通过。Node含真实page定义的VM调用、确认取消/双击/跨页重试与账号隔离；Python含真正学生任务列表读取、逐人隔离、听读token、事务注入失败、通知异常、管理员、旧入口和跨学生快捷token反例。状态/成绩由夹具预置，不冒称学生完成整条学习链路或真实微信端到端。新用例已接CI并在远端通过，状态见下方发布验收。

独立review发现的成绩卡缺失、课程对象/Infinity导致500、跨学生快捷上下文拼接风险均已补齐并纳入回归。没有残留已知阻断性代码缺陷。

## 发布验收

- [分支CI 43586388378](https://github.com/KB77GG/studytracker/actions/runs/43586388378)、[main CI 43586564442](https://github.com/KB77GG/studytracker/actions/runs/43586564442)整体success，test/account-provisioning/task-planner三测试job成功；原有advisory lint job仍failure，不能宣称全仓lint通过。本轮新增Python及验收脚本定向Ruff/Black通过。
- [Deploy 43586564446](https://github.com/KB77GG/studytracker/actions/runs/43586564446) success。生产 `/root/apps/studytracker` HEAD为 **63fa27f9cefc974ab15c76c90f96e8e1ee0468a7**，tracked clean，17 untracked顶层入口保留；2026-11-14 **18:43:19 CST**起active/running，PID737900、NRestarts0，验收时启动后warning以上0条。
- workers1/gthread/threads6/127.0.0.1:5002保持，真实worker子进程1个；9个部署文件（8运行源码+gunicorn配置）与本机SHA全部一致。内网5002和公网各3个GET：登录200；新名单/群发GET无登录均401 missing_token，证明路由已加载且鉴权保留。未冒用教师身份或向真实学生发任务。
- 验收脚本 `verify_release.py` 只读取Git、运行文件、systemd、匿名HTTP，不import应用/配置或查询学生数据库。证据 `release-audit.json`。一次SSH被本机沙箱拦截后按批准流程成功复跑。部署使用既有流水线，执行其既有幂等迁移步骤；本功能无新增schema迁移，未人工写生产档案/名单/Task/成绩，未发送真实通知或改变外部配置。

精确验收命令（cwd本发布树）：

```sh
ssh root@47.110.45.193 'cd /root/apps/studytracker && .venv/bin/python - 63fa27f9cefc974ab15c76c90f96e8e1ee0468a7' < docs/reviews/small-class-homework-20261114/verify_release.py > docs/reviews/small-class-homework-20261114/release-audit.json
gh run view 43586564442 --json databaseId,headSha,status,conclusion,jobs
gh run view 43586564446 --json databaseId,headSha,status,conclusion,jobs
```

`release-audit.json`的`local_file_matches`由主审逐个SHA256对比本机同名文件后添加，9/9一致；不依赖文档手写版本推断上线。

## 个案下一步

后端已完成发布，无剩余后端部署阻塞。小程序源码在本树 `miniprogram/`，仍需微信开发者工具上传、提审、发布，并做真机验收；上传时核对项目目录，不能使用旧桌面main代码。前端发布前旧版本遇合并名单会被后端409保护拦截。

真实个案还需管理员核实/补齐独立个人档案，并确认排课三人名单已保存，之后在新作业页核对全员就绪再布置；补档案不等于完成微信绑定/订阅。本轮授权是提交/推送及后端部署，未改学生资料或代布置作业。
