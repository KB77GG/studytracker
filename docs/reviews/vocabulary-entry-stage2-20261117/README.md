# 词汇入口第二层优化与复习规则审计（2026-11-17）

**最终发布事实**：产品 `df4124d3d52f849ce162d398335071e1dc45abf9` 已commit/push任务分支及main，分支CI43987181418、main CI43987703914三个业务job均成功（既有advisory lint失败仍保留）；Deploy43987703920成功。生产08:27:36 CST重启，08:28只读验收确认HEAD/4产品SHA一致、tracked clean、active/running、NRestarts0、实际单worker/gthread6/5002，公网登录200。两组实际数据preflight为776.631/705.578ms，随后缓存summary为1.643/1.274ms；新增分页选择在生产3.10/SQLite只读取最多20候选分别223.481/339.920ms。全部query_only、0 changes、无ORM待写或阻止的SQL，没有领取/答题/结算，没有真机全流程。这里是当前生产样本耗时，不能用与昨天不同数据状态直接计算提速倍数。

证据为branch-ci.json、main-ci.json、deploy.json、production-entry-acceptance.json、production-finite-selection.json、production-postdeploy-readback.txt。验收复用仓库既有`docs/reviews/miniprogram-entry-20261116/verify_production_entry.py`，参数expected-head为上述产品SHA，context-sha为e082b83db53965cc57a56ede669dc330e0ccaef4c724e727af947c76a5d5af95，review-sha为d5d39ceb72e8a37175e7fd0158f13c0709604358652085886565125d8fc50f8c；在生产cwd执行`PYTHONDONTWRITEBYTECODE=1 PYTHONWARNINGS=ignore .venv/bin/python <script> --expected-head ... --context-sha ... --review-sha ...`。有限选择的实际执行代码保存为verify_finite_selection.py，经SSH `python -c`调用，复用同样的只读连接与禁写authorizer；没有复制真实数据到本机。最终JSON去除了逐学生业务表计数和完整响应，仅保留状态、时间及安全断言。

标准部署链原有幂等迁移与重启照常执行，本轮无新schema/生产配置/人工数据修改。复习政策尚未改，小程序新包仍未上传/提审/发布。报告与两交接最后以skip-ci文档提交共享，不再次部署；最终文档HEAD以Git回读为准。

第二层产品提交：`df4124d3d52f849ce162d398335071e1dc45abf9`。基线 `e19a81045da782bd2a245caee0222dcbdf87b84b`，包含已部署的第一层 `c7e85214`。用户要求实施第二层，并选择保留精确数、短时缓存；按本会话此前“把所有修复都部署”的授权执行后台发布。教学规则本轮只审计和建议，不实施。生产发布与独立验收结果见本文开头。

## 实施与不变条件

- `services/vocabulary_review_selection.py` 把到期候选的稳定排序交给SQL轻量元数据查询，按页加载词和掌握度；资格检查可在门禁找到一个、领取凑满20个后停止。选词、优先维度、代表词fallback、当日冷却、补救预算、实际题面与旧算法等价。
- `services/vocabulary_due_cache.py` 缓存合格词义ID集合30秒，用于非封顶数字展示。按Flask应用、DB引擎、学生、本地日期隔离；相关ORM写入使缓存失效，未提交事务绕过共享缓存，commit/rollback再次失效，避免发布未提交数据。同生并发冷查询合并，其他学生不共用结果。最多128条/总100,000词义ID，超预算不缓存。
- `vocabulary_autonomous_review.py` 的精确计数只判每词义是否有合格维度，不做完整排名。实际门禁、领取名单和结算的继续资格均查新鲜数据；缓存数字不授权、不选题。
- 领取/结算把冷全量计数移到写锁前；锁内重验本批。并发导致资格/题面改变时409并回滚。SQLite legacy模式首次SAVEPOINT可能独立提交的边界已以局部显式外层BEGIN修复，未改全局事务配置。
- 学习间隔、每日放行、20词每批、错题判分、首次成绩、schema、小程序源码均未变。没有人工清积压、重算成绩或发送通知。

## 已知性能边界

保留精确数意味着**冷缓存仍需检查全部到期词义**；30秒内显示值可能短时滞后，外部进程/raw SQL写入最迟靠TTL失效。新鲜门禁不受这类显示滞后影响。没有宣称所有请求O(1)，也没有把“入口工作量不随积压增长”作为已实现的绝对结论。

SQL仍可能扫描/排序到期元数据；大量不可出题候选时，早停前仍可能检查很多词。锁内最多重验本批词，但题目物化仍受整本词书大小/题型影响，不等于锁内成本与书大小无关。若需要冷入口也有严格固定预算，后续应做持久化的资格/计数索引或异步预计算，并另行验证一致性。

## 最终本机验证

- Python **3.10.20：246/246**（30.269秒）；Python **3.13.3：246/246**（25.938秒）。包括原216项与缓存14、选批8、独立对抗8。
- 12个随机混合数据集：参考算法与新算法的资格集合、全顺序、前20题快照相同；跨页无效词、代表词fallback、NULL、同词义去重、午夜冷却、任务宽限、过期显示缓存不放行/不选题均有覆盖。
- 独立文件SQLite双连接并发反例验证：选批后冷却/改期/词条变无效时冲突回滚；禁用防护确实失败。无前置写入的首次领取冲突也不再留空active批次。
- 只读生产验收器原有7项安全测试在3.10下通过（0.187秒）。本轮8个产品/测试文件及基准脚本Ruff通过，git diff-check通过；新文件Black通过，未扩大修整巨型旧文件的历史风格。
- 完整命令与日志：`final-python310-suite.log`、`final-python313-suite.log`、`backend/implementation-validation.md`、`independent-review.md`。`backend/python313-suite.log`是最后原子性/导航修订之前的237项中间日志，不能代替最终246项。

```sh
TZ=UTC PYTHONWARNINGS=ignore /private/tmp/studytracker-stage2-py310/bin/python -B -m unittest tests.test_classroom_vocabulary tests.test_classroom_vocabulary_learning tests.test_dictation_answers tests.test_vocabulary_mastery tests.test_vocabulary_group_learning tests.test_vocabulary_group_learning_api tests.test_vocabulary_autonomous_review tests.test_dictation_review tests.test_vocabulary_numeric_learning tests.test_vocabulary_numeric_review tests.test_vocabulary_review_performance tests.test_vocabulary_context_availability tests.test_vocabulary_flow_backlog_gate tests.test_vocabulary_due_cache tests.test_vocabulary_review_selection tests.test_vocabulary_stage2_adversarial -q
# 同一命令将解释器替换为 /Users/zhouxin/Desktop/studytracker/.venv/bin/python 验证3.13。
TZ=UTC PYTHONWARNINGS=ignore /private/tmp/studytracker-stage2-py310/bin/python -B docs/reviews/vocabulary-entry-stage2-20261117/benchmark_entry.py --repo /private/tmp/studytracker-vocabulary-entry-stage2-20261117 --output docs/reviews/vocabulary-entry-stage2-20261117/benchmark-candidate-py310.json
TZ=UTC PYTHONWARNINGS=ignore /private/tmp/studytracker-stage2-py310/bin/python -B docs/reviews/vocabulary-flow-latency-20261116/probe_write_lock_hold.py --repo /private/tmp/studytracker-vocabulary-entry-stage2-20261117 --output docs/reviews/vocabulary-entry-stage2-20261117/lock-candidate-py310.json
```

基线相同两命令使用 `--repo /private/tmp/studytracker-stage2-baseline-20261117`，输出分别为benchmark-baseline-py310.json和lock-baseline-py310.json。基准仅合成SQLite、合成学生、真实Flask路由，不访问生产。最终源码哈希见 `verified-source-sha256.json`；最后基准在产品冻结后执行。

| 2400词合成场景 | 第一层基线 | 第二层最终候选 |
| --- | ---: | ---: |
| 首页冷计数 | 465ms | 459ms |
| 同生紧接着再次读首页 | 464ms | 1.3ms |
| 6学生并发、直接冷门禁，最大耗时 | 3.87s | 4.02s |
| 6学生并发、随后领取，最大耗时 | 9.43s | 2.72s |
| 单生领取持写锁 | 484ms | 163ms |
| 单生结算持写锁 | 483ms | 9.5ms |

所有基准请求HTTP成功（包含并发status及ok检查）；新脚本还记录每请求资格判断次数，避免把快速错误响应当提速。**旧持锁探针的backlog_scans字段只计旧`_due_candidates`调用；新count-only loader仍会冷扫描，所以其0不能被解释成没有全量工作。**时间为本机单次测量，不是生产SLA/真机实测；冷门禁未改善是保留精确数的明确限制。

## 生产与教学审计

第一层独立回读已核对 `c7e85214`、active/running、NRestarts0、07:41:05 CST启动、Python3.10.12、loopback登录200与公网登录200（138.6ms），见 `production-health-readback.txt`。子任务额外SSH stdin探针的权限请求被中止，未取得执行证据；`production-audit/stage1-production.json`明确标未执行，不能当作健康/日志验收。未完成部署前后499同窗口比较，499也不等于确定超时。

学习规则审计见 `review-policy-audit.md`。已确认20是每批非每日上限；任务入口一批结算会默认返回新任务，首页可以继续。当前包含正确词、错误词、未测能力和长期维护；仅用截面“到期数÷任务数”不能推出净增率或永远清不完。建议的D1/D3错维度巩固、两次独立成功后退出必做队列、后续低频检查尚未实施，不删除历史或标记永久掌握。

## 工作树与发布边界

- 实施树：`/private/tmp/studytracker-vocabulary-entry-stage2-20261117`，分支`codex/vocabulary-entry-stage2-20261117`，初始e19a8104 clean；产品8文件已提交df4124d3并推任务分支及main，部署和只读验收完成。报告和两交接单独skip-ci同步，不重复部署。
- 对照树：`/private/tmp/studytracker-stage2-baseline-20261117`，detached e19a8104，未改源码；合成数据库在测试临时目录，未触碰项目app.db。
- 主资料树：`/Users/zhouxin/Desktop/studytracker`，main6ded77d2，保留原7M/23U，只增报告镜像和两交接；不pull或覆盖旧业务改动。
- 固定小程序源：`/Users/zhouxin/Desktop/studytracker-release/miniprogram`，所属分支codex/miniprogram-release@d03a2749、既有76M/37U，本轮未改；用户明确新包尚未发布。本轮不上传/提审/发布小程序。完整固定源码仍仅本机，不可用主线整包替代。
- 隔离Python3.10测试环境在`/private/tmp/studytracker-stage2-py310`，生产Python/依赖未因此变更。
