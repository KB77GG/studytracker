# Claude 审查五项修复与主线整合复验

2026-11-15；分支 `codex/exam-integrity-review`，工作树 `/private/tmp/studytracker-exam-integrity-20261114`。起点 `14c64d2e8bc29818e088480eb3e4d4a68d1215f0`，开工clean；修复提交 `9ba382610e90f096388a5cf744d18dd012c88a09`，合并提交 `6066e8a7216a7cacb92c1c2ebcddac9822fd2ec8`，合入最新抓取的 `origin/main@cb2610166d7654c81238f53c000e37eafa7e68e1`。仅两交接文档冲突，保留双方记录；其他代码和CI自动合并。

用户授权只在本审查分支修复、合入main、推送并等CI。**未 push／合并到 main，未部署，未访问生产服务器／数据库或改变外部服务。** 主线自带的小程序词汇代码随合并保留，不是本任务新增小程序功能，也未上传／提审／发布。第二期、SEB、托福继续不做。

## 五项修复及复现场景

| 问题 | 行为与证据 |
| --- | --- |
| 章节页绕过 | 后端由真实 started/submitted 字段判断活动科目；reading hello→hidden→process hello→600秒后reading hello，计1次、600秒。三科均测，听力仍不锁。正常已交卷或未开始不计；章节刷新保留区间，9.999/10秒边界覆盖。原页面BFCache重入先hello，再补旧事件，旧hidden/visible不重计。service及route复现测试。 |
| 事件上限 | 每state_id普通事件2000条软上限；heartbeat只更新last_seen_at，heartbeat_gap仍按原规则记。15学生33分钟共1980次heartbeat后只有15条hello，后续hidden/visible/leave/locked齐全。填满一生2000条也不影响别人；leave/locked/unlock/device_conflict始终插入，允许总数超过软上限。 |
| SQLite繁忙 | 每个独立连接设busy_timeout=500ms并在finally恢复旧值，写事务用BEGIN IMMEDIATE；不在进程事件锁中等待。外部BEGIN IMMEDIATE时4并发record_event均快速ok:false/无mode，测试总耗时<1.5秒；释放后恢复。内部失败API503，权威off才停止；模板策略读取失败仍为空。独立池探针4连接均恢复原5000ms。 |
| 断网绕过 | 已知锁定从首个连续失败起保留至多60秒，失败重试不续期；未锁/听力故障立即放行。只权威ok:true/off才stop。hidden/visible内存FIFO保留原时间及queued_ms补发，beacon成功不等于ACK，重复重发不双计。过期响应和BFCache恢复反例覆盖。每生面板独立明显显示距最后联系/离线时长，20秒宽限，锁定与冲突行也显示。 |
| 急停重置阈值 | 新mode-only入口只改mode与审计字段；自定义7次/321秒急停后DB、接口、面板回读仍7/321，保留原状态记录。 |

`docs/EXAM_INTEGRITY_PLAN.md` 顶部已记录用户本轮明确修订，优先于旧3.14等条款。手册与在线帮助同步60秒规则、章节页规则和离线补发限制。没有改旧模型或增加字段、没有改原草稿/计时/交卷/复盘；数据库脚本不变。

## 合并后验证

- Python模考／诚信相关 **181/181**（16.144秒）；合入主线的课堂词汇／学习／判分 **50/50**（1.552秒）；合计231项，非全仓测试。
- Node相关与合入主线客户端 **130/130**，其中guard49项。
- 9个诚信Python定向Ruff、Black通过；新只读审计脚本同样通过；JS语法和完整diff检查通过。
- 范围审计15项通过：11个旧关键文件含deploy.yml不变、旧模型AST不变、合入主线非共享产品逐字节保留、CI同时保留诚信和同义词测试，main已是祖先。相对合入main的27个诚信产品文件SHA在 `scope-audit.json`。

cwd为本工作树，实际命令：

```sh
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_exam_integrity_service tests.test_exam_integrity_routes tests.test_exam_integrity_adversarial tests.test_exam_integrity_e2e tests.test_mock_exam_runtime tests.test_mock_exam_runtime_routes tests.test_mock_exam_review tests.test_mock_exam_review_workflow tests.test_mock_exam_student_review tests.test_mock_exam_template_isolation tests.test_selection_highlight_contract tests.test_practice_highlight_coordinates tests.test_migrate_mock_exam_review -q
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_classroom_vocabulary tests.test_classroom_vocabulary_learning tests.test_dictation_answers -q
node --test tests/test_exam_guard.js tests/test_practice_shell.js tests/test_mock_exam_review_frames.js tests/test_practice_renderers.js tests/test_mock_review_paper.js tests/test_simulation_audio.js tests/test_classroom_vocabulary.js tests/test_task_dictation_preset.js tests/test_classroom_synonym_client.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check api/exam_integrity.py services/exam_integrity.py services/exam_integrity_rules.py scripts/create_exam_integrity_tables.py tests/test_exam_integrity_service.py tests/test_exam_integrity_routes.py tests/test_exam_integrity_adversarial.py tests/test_exam_integrity_e2e.py tests/exam_integrity_e2e_support.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m black --check api/exam_integrity.py services/exam_integrity.py services/exam_integrity_rules.py scripts/create_exam_integrity_tables.py tests/test_exam_integrity_service.py tests/test_exam_integrity_routes.py tests/test_exam_integrity_adversarial.py tests/test_exam_integrity_e2e.py tests/exam_integrity_e2e_support.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/exam-integrity-review-fixes-20261115/verify_revision.py
node --check static/js/exam_guard.js
node --check docs/reviews/exam-integrity-20261114/browser-check.cjs
node --check docs/reviews/exam-integrity-20261114/browser-resilience.cjs
git diff --check
```

日志：`python-tests.log`、`merged-main-tests.log`、`node-tests.log`。所有运行使用临时SQLite及合成数据，不导入真实生产配置。

## 本机浏览器复验

Chrome157.0.8103.78、独立context、网络限制loopback，两个临时服务5098/5099退出时清理。实际命令：

```sh
INTEGRITY_EVIDENCE_DIR=/private/tmp/studytracker-exam-integrity-20261114/docs/reviews/exam-integrity-review-fixes-20261115 node docs/reviews/exam-integrity-20261114/browser-check.cjs
INTEGRITY_EVIDENCE_DIR=/private/tmp/studytracker-exam-integrity-20261114/docs/reviews/exam-integrity-review-fixes-20261115 node docs/reviews/exam-integrity-20261114/browser-resilience.cjs
```

- 三模式完整登录→听力→阅读→写作→成绩→复盘成功；off无诚信请求；听力三次离开无遮罩；阅读锁定/老师解锁/到时自动提交、外部粘贴阻断和内部放行均成功。紧急关闭约 **2.855秒**撤罩。
- 网络中断隐藏/返回后恢复，计 **1次**，保留约 **2.156秒**原隐藏时长，不把补发延迟累加。
- 两浏览器设备冲突→允许换机→新设备接管，旧页不抢回；原生鼠标选词高亮、答题点击和导航成功，几何无偏移。
- 临时库删除仅三张诚信表，接口返回503/ok:false不再假off。已有锁定在故障初期仍可见，真实旧draft PUT可保存；实际 **63.443秒**后撤罩，guard节点保留继续重试，随后阅读/写作交卷到成绩成功。无假时钟代替此60秒等待。
- 两套浏览器pageerror为0。证据 `browser-results.json`、`browser-resilience-results.json` 和截图。可见性与ClipboardEvent仍是控制注入，网络故障是浏览器请求拦截；不是iPad真实切App/原生剪贴板验证。

## 状态与剩余限制

本报告准备随审查分支提交并push；远端CI实际结果待完成后附 `ci-review.json`。此前14c64d2的55文件清单/158+86日志仍是历史快照，不冒充新修复验收。现行文件清单由当前Git相对main取得。

用户真实iPad/Mac Safari、锁屏/通知/分屏/侧拉/台前调度/系统剪贴板、真实网络、微信web-view、SEB配置与线上负载仍未验。离线队列只在当前页内存，刷新/关闭可能丢失；不承诺记录无法到达服务器的所有行为。已知锁定时CSS/JS本身失败仍立即撤限制，避免破坏原考试。关键事件无2000硬上限是保留审查证据的明确取舍。

完成分支CI和交接后停止等审查；不继续第二期，不触碰生产。
