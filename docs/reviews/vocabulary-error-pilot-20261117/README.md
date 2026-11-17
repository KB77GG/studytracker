# 错词复习试点实现与发布验收

状态：本会话已确认B2方案的B3默认关闭版本已部署并完成生产回读。未启用学生、未导入历史错误，小程序精确增量已应用但未上传/提审/发布。后续审计分支新增C2建议未确认，C3完整验收未完成，不能据本报告直接启用试点。

实施树 `/private/tmp/studytracker-vocabulary-error-pilot-20261117`，分支 `codex/vocabulary-error-pilot-20261117`，基线 `f414a126`（main309397dd加三份模拟文档）。原桌面main与固定小程序均有其他未提交工作，未整包覆盖。

## 已确认并实现的规则

- 新的正式首答错误按“学生、词义、能力”入队；次日到期，只复测出错能力。学习中的讲解、订正和重试不算独立成功。
- 两次独立首答成功相隔至少2个上海自然日后退出必做；保留学习记录，不认定永久掌握。再次错误清零成功次数。
- 每日20题，包括最多4道D7/D30抽查；没有抽查候选时名额用于错词。固定的是每日4个名额，不另加每词概率；未按目标日观察到的抽查标记missed，后补答案不伪装为D7/D30保持率。
- 连续3个不同复测日失败后暂停7天；老师按词义查看每周清单，暂停后自动重入，历史保留。没有逐条消息推送。
- 当天到期优先；仅在过载时将逾期超过7天的错词移入低频，留下原因事件。没有过载时仍可正常复测旧错词。
- 不导入任何历史错误标记。仅从明确入组时间后产生的新错误开始，初始必做记录为0。
- 可选低频巩固每天最多10题，不拦截新任务；老师布置页显示队列过载提醒。
- 上述7参数可配置，默认20/4/10/2/3/7/7。额外“仅过载学生自动提高到30/40题”的讨论未获实施指令，本轮未加入。

## 实现边界

5张新表分别保存入组、错词状态、抽查机会、每日分配和事件。75个旧模型class AST未变，旧schema的create_all实测仅增加5空表，无ALTER/DROP或业务DML。普通请求不做DDL；标准部署旧 `create_plan_table.py` 的 `db.create_all()` 创建新表。

总开关 `VOCABULARY_ERROR_REVIEW_ENABLED` 默认false，另需逐学生enabled及starts_at。关闭时不查询新表、旧协议与门禁保持；新字段另加，已用旧客户端HTTP协议验收。未开启任何生产学生。

新逻辑拆入 `services/vocabulary_error_queue.py`、`vocabulary_error_review.py`、`vocabulary_error_reporting.py` 和独立教师蓝图；旧巨型文件只接入口。所有首答与新队列在同一外层事务，SQLite首次SAVEPOINT不能先提交首答。入组和旧批领取互相取得写锁后重验，日限额和幂等用真实双连接验证。

独立复核关闭的主要问题：空批仍需持久化过载转移；旧冻结题不能提前消化当天新错；陈旧不可用计划不能降级后来的新错误；教师抽查异常漏报；可选额度用尽但有活动批时仍可恢复；小程序空继续响应需清旧批和旧数字。详见 `independent/README.md`、`integration/README.md`、`teacher/README.md`。

## 验证

首轮产品：Python3.10与3.13各342项通过（259既有+32核心+22集成+18教师+11管理），分别41.700/35.575秒，见 `full-python310.log`、`full-python313.log`。随后管理摘要绑定/可选筛选优化完成，最终同一份23文件manifest在Python3.10与3.13各 **349/349** 通过（259既有+32核心+24集成+18教师+16管理），分别43.233/37.046秒，见final-python310.log/final-python313.log；新文件Ruff/Black及产品diff检查通过。

```sh
TZ=UTC PYTHONWARNINGS=ignore /private/tmp/studytracker-stage2-py310/bin/python -B -m unittest tests.test_classroom_vocabulary tests.test_classroom_vocabulary_learning tests.test_dictation_answers tests.test_vocabulary_mastery tests.test_vocabulary_group_learning tests.test_vocabulary_group_learning_api tests.test_vocabulary_autonomous_review tests.test_dictation_review tests.test_vocabulary_numeric_learning tests.test_vocabulary_numeric_review tests.test_vocabulary_review_performance tests.test_vocabulary_context_availability tests.test_vocabulary_flow_backlog_gate tests.test_vocabulary_due_cache tests.test_vocabulary_review_selection tests.test_vocabulary_stage2_adversarial tests.test_vocabulary_cache_lifecycle tests.test_vocabulary_error_queue tests.test_vocabulary_error_review_integration tests.test_vocabulary_error_reports tests.test_vocabulary_policy_management -q
```

3.13使用同命令替换解释器为 `/Users/zhouxin/Desktop/studytracker/.venv/bin/python`。新正式测试及教师JS6项已纳入CI。独立7边界、2并发在两解释器通过；只读验收器12mock及旧7安全测通过，命令见各独审报告。

必做summary的合成规模探针：低频/旧mastery各0、5000、20000条，固定8SQL、0旧mastery查询，中位约1.1–2.0ms。COUNT仍有索引扫描成本，不能称数学O(1)；大量active错词和可选旧资格筛选仍有成本，不能从合成测试推断生产并发SLA。

学生端候选115 Node通过、两JS语法、两页官方wcc/wcsc通过；固定源451文件SHA检查，精确4产品增量，447不变，新增1测试。见 `client/README.md`。未声称微信整包编译、真机或上传/提审/发布完成。

## 管理与后续试点

`scripts/manage_vocabulary_error_pilot.py` 默认SQLite URI只读、query_only、拒写/拒身份列，10秒查询预算，只输出汇总。显式ID预演或默认最近28天活跃集合预演均不产生记录；后者不能直接apply。

实际入组必须显式ID、开始时间、经审阅的摘要和 `--apply`，最多50人、BEGIN IMMEDIATE下重新核对、整批回滚。已有活动复习批次必须先正常完成；不替学生结算。该脚本不改总开关。生产本轮只运行预演，不运行apply。

后续B4：用户指定试点学生后，重新只读预演并审阅规则/目标库/人数/旧批情况，确认后才启用；不得把本轮参数确认当成名单与启用确认。观察两周看负担、按期率、7日抽查保持率及覆盖率；D30至少继续4–6周。不以未观察到的抽查当答对，不以退出必做等同永久掌握。

回退：首选关闭总开关并重启，或撤销本轮产品提交再走CI/部署。新表与记录保留，不DROP、不逆迁移、不改旧掌握度；目前默认关闭、无入组，回退没有教学数据恢复工作。

## 生产发布记录

部署前13:28CST只读验收通过：生产7742a802、active/running、NRestarts0、单worker/gthread6/5002、公网200/匿名401；五新表尚不存在，原schema摘要已冻结。两例真实历史数据preflight399/533ms、暖summary1.9/1.3ms；0写入、无app/config或重模型导入。`production-before.json` 不保留学生标识、答案或逐学生数量。

产品提交188d29f6，发布HEAD **79dd34f4f07ff435e882908b5454f46fd8dff4f5** 已push任务分支与main。分支CI [44025269334](https://github.com/KB77GG/studytracker/actions/runs/44025269334)、main CI [44026399459](https://github.com/KB77GG/studytracker/actions/runs/44026399459)三个业务job均通过，旧非阻断lint失败如实保留；[Deploy44026399460](https://github.com/KB77GG/studytracker/actions/runs/44026399460)成功。

13:46:47CST服务重启，13:48:36生产只读验收ok：HEAD/23SHA一致、tracked clean、active/running/NRestarts0、单worker/gthread6/5002、公网200/匿名401；5新表全部0行，旧schema摘要与部署前完全一致，总开关env/.env和代码默认off。两历史学生数据preflight586/600ms，暖summary1.77/1.26ms；0写入、无身份/答案输出、不import app/config或重模型。前后是不同时间的只读单次观测，不把毫秒差当因果性能比较。

14:02CST默认预演：最近28天20活跃，18满足新入组前提、2有旧active批次，0已入组；初始队列0、历史导入0，参数20/4/10/2/3/7/7。仅预演，不含--apply；摘要已过期，不能拿它直接启用，指定试点后重新预演。`production-preview.json`只有汇总与不含身份的digest。

固定小程序4产品文件+1测试已精确应用，447非目标SHA保持，实际固定源115/115、官方两页wcc/wcsc与两JS语法复验通过。固定源完整其他未提交代码仍仅本机；本轮增量归档随后台分支可跨机取得，但不是完整小程序包。未整包编译/真机/上传/提审/发布。

发布前fresh fetch另看到审计分支45167aad的C节：三日练到答对不清零只是新的待确认建议，没有替换本次已确认规则。已保留原文在计划，并补独立C3差距报告 `independent/new-plan-gap.md`：双Python七路径在0/2400/10000无关旧mastery的SQL/fetch行数相同，但未纳CI/未覆盖所有题型；daily_limit30/40会物化30/40，锁内新队列扫描与完整1/3/6并发、ON/OFF、写锁及试点前后一周499仍待。当前默认20且OFF没有这些启用风险；启用任何试点前须明确最终规则并补对应验收，不宣称C2/C3完成。

交接同步到各树CODEX_HANDOFF/WORKLOG；本次生产回读和后续说明通过单独[skip ci]文档提交共享，不重复部署，最终文档HEAD以Git为准。
