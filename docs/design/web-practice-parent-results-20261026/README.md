# 网页练习指引与家长结果 — 2026-10-26 验收与部署

> 当前状态：后端业务80f215b5已commit/push/deploy并通过生产验收；小程序尚未发布。最新发布状态与复验命令见[DEPLOYMENT.md](DEPLOYMENT.md)。下方为发布前本机验收记录，保留基线与过程限制。

## 工作树与发布边界

- 后端实施：`/Users/zhouxin/.codex/worktrees/web-practice-parent-results/studytracker`，`codex/web-practice-parent-results@65f1859683c94ef41c938319515702e12709e96c`；从 fetch 后的 origin/main 建立，开工 clean，无来源不明改动。本轮源码全部未 commit/push/deploy。
- 小程序唯一发布源：`/Users/zhouxin/Desktop/studytracker-release/miniprogram`，所在树 `codex/miniprogram-release@d03a2749eb99cde041cdae18305b624956d46e90`，本地 origin/main behind 61。本轮前有75 modified/34 untracked入口（展开110文件）；现76 modified/35 untracked。既有精听、词汇、数字等内容完整保留；本轮10个前端文件+1新测试，101个无关既有脏文件逐个SHA未变（更新交接之前核对）。所有小程序改动仍仅本机。
- 桌面资料树：`/Users/zhouxin/Desktop/studytracker`，`main@6ded77d24586327ad94e151e172ae4811b4a2eed`，fetch后behind83；仍7 modified/22 untracked入口。本轮只更新两份交接，未pull/切分支/覆盖业务代码。
- 只读核对生产：`/root/apps/studytracker@aa394ef09da2e1e84d71df71dc6b5439ee436857`，tracked clean，`studytracker.service=active`。线上 `api/writing_library.py`、`services/writing_assignments.py`、`api/question_type_practice.py`、`templates/tasks.html` SHA与实施树HEAD逐字一致，因此已有网页写作布置/专项功能确实已上线。没有连接生产数据库、运行迁移、重启服务、发送学生通知或代学生提交。
- 本轮无数据库schema变更，不需要新迁移。后端新增功能未部署，小程序未上传/提审/发布；真机、完整微信GUI编译与新后端线上联调未验证。之前精听250ms滞后模型/真机限制仍见发布树旧交接，不能把本轮通过等同于整包发布验收通过。

## 完成内容

1. 已有后台 `/tasks` →「写作练习」可布置真题打字/母题；创建任务后会尝试既有微信订阅提醒，但送达依赖学生订阅授权，不能保证每条提醒送达。本轮没有创建真实任务或发送通知。
2. 学生today/detail输出 `web_practice={kind,label,instruction,url}`；小程序首页及详情明确「去刷题网页练习」，可复制绑定当前任务的网页链接。没有把网页练习改成微信内答题。通用计时、图片/录音上传、提交入口均屏蔽；后端Task和PlanItem备用路径的submit/start/stop也拒绝，避免伪完成。
3. `Task.question_ids.writing_attempt_ids` 在写作start时同事务绑定，finish从已有绑定恢复原任务并核学生/资源/日期。旧的自主练习、同题旧attempt不能完成新的任务；重放只读，并发start/finish有条件更新，避免覆盖原绑定与首次完成结果。母题持久化 `writing_topic_result`。修复原门禁异常字段 `exc.code` 为实际 `exc.error`。
4. 家长已绑定学生的报告可读专属写作结果：打字准确率、范文档位、已输入/目标词数、速度、用时、完成时间、输入原文；母题显示完成与用时、不显示打字分。范文Band明确不是学生雅思成绩。家长首页写作近况同步标注打字准确率。
5. 题型专项从 `QuestionTypePracticeAttempt.results_json` 读取保存成绩与逐题答案/判定，多选部分得分保留，不重新判分；未提交不显示默认0分、不泄漏标准答案。真实提交0分保留。家长接口不提供可写token链接，GET不创建attempt或修改数据。
6. 旧写作任务没有可靠attempt绑定时只显示Task已有结果和明细缺失说明，不能通过同学生同题最近一条记录猜测；不回填、不重算历史。范围为任务对应结果，自主练习历史没有凭空加入任务报告。

## 文件与增量

后端修改：`api/miniprogram.py`（仅序列化、guard与报告dispatch胶水）、`api/writing_library.py`、`services/writing_assignments.py`、`tests/test_writing_library_routes.py`。
新增：`services/web_practice_tasks.py`、`services/web_practice_reporting.py`、`tests/test_miniprogram_web_practice.py`、`tests/test_parent_web_practice_report.py`；两份交接及本目录证据。`.tmp/client-before`保留本轮前原文快照和全脏diff，`.tmp/client-result`保留验证产物，不要拿旧业务diff整包提交。

小程序修改：`pages/student/{home,task}/index.{js,wxml,wxss}`、`pages/parent/task-detail/index.{js,wxml,wxss}`、`pages/parent/home/index.wxml`（均在miniprogram/）；新增 `tests/test_web_practice_client.js`。本目录 `CLIENT_INCREMENT.patch` 只含本轮增量，SHA-256 `e042b0efbca77ef6d1508f2f204b45a06d5430259b091e00d25bd9de4926abf6`，已反向apply-check确认实际发布树包含该增量。它以本机发布树的未提交源码为基线，不能不核基线就应用到origin/main。`client-before-*`记录原脏状态；`verification.json`记录最终前端SHA与精确编译命令；`backend-sha256.json`记录五个后端运行文件SHA。

## 精确验证

后端 cwd 为实施树：

```bash
TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q --disable-warnings --tb=short -p no:cacheprovider tests/test_miniprogram_web_practice.py tests/test_parent_web_practice_report.py tests/test_miniprogram_parent_report.py tests/test_parent_stats_route.py tests/test_miniprogram_task_visibility.py tests/test_miniprogram_task_routing.py tests/test_task_date_gate.py tests/test_writing_library_routes.py tests/test_writing_library_service.py tests/test_task_assignment_routes.py tests/test_task_assignment_history.py tests/test_task_assignment_deduplication.py tests/test_question_type_practice_routes.py
```

最终 **172 passed / 31 subtests passed / exit0**，既有依赖/SQLAlchemy警告未扩大处理。包括真实路由写作start→finish→家长detail/stats、专项HTTP submit→家长多选部分分/空答案、权限隔离、绑定/跨任务重放、并发陈旧更新、截止规则、Task/PlanItem通用提交与计时门禁。独立复审先复现PlanItem别名绕过，补齐后独立20 passed/23subtests确认关闭，无新增阻断。

```bash
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check services/web_practice_tasks.py services/web_practice_reporting.py services/writing_assignments.py api/writing_library.py tests/test_miniprogram_web_practice.py tests/test_parent_web_practice_report.py tests/test_writing_library_routes.py
git diff --check
```

均通过；五个运行Python文件用 `ast.parse(..., feature_version=(3,10))` 全通过。未运行无关完整ML套件。

小程序 cwd 为固定发布树：`node --test tests/*.js` **185/185**；最后仅追加家长首页标签一行改动后 `node --test tests/test_web_practice_client.js` **11/11**、该WXML重新编译通过。三个JS `node --check`、四个变更WXML官方wcc、整包WXSS官方wcsc、diff-check均通过，绝对编译器路径及完整命令在verification.json。没有伪称完整GUI/真机/线上联调通过。

生产只读命令：

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 aliyun-server 'cd /root/apps/studytracker && git rev-parse HEAD && git status --short --untracked-files=no && sha256sum api/writing_library.py services/writing_assignments.py api/question_type_practice.py templates/tasks.html && systemctl is-active studytracker.service'
```

输出生产HEAD、无tracked改动、四个SHA匹配HEAD、active；没有执行HTTP任务写操作或SQL。

## 下一位 agent

先读三树交接并核git状态/manifest。若用户明确授权上线，从实施树提交并推送已审后端（先fetch核远端变化，勿发布旧Desktop树），按既有链路验证后端；本任务无新增schema迁移。随后从唯一固定小程序目录完整编译、真机验证写作/听力专项/阅读专项及家长结果，再由用户上传/提审/发布。关注旧任务明细缺失降级与微信订阅授权，不承诺自动恢复旧明细或必达提醒。
