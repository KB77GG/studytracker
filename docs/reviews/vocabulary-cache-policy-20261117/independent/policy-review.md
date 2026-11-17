# B1 生产只读汇总独立复审

结论：冻结脚本可进行一次有预算限制的生产只读取数。没有发现阻止执行的写入、敏感输出或已知模型列不匹配问题；这不是生产执行成功的声明，实际生产 schema、运行结果与发布状态由主审核对。

- 工作树：`/private/tmp/studytracker-vocabulary-cache-policy-20261117`。
- 分支：`codex/vocabulary-cache-policy-audit-20261117`；本轮起点 `d67e147b`，期间主审另提交了 A。
- 冻结文件：`policy/aggregate_policy.py`，SHA256 `ee5332d4a64de44160b2b3d8e289618f517ba7b926648ae4808aa885d5f80575`。
- 独审仅新增本文件及 `test_policy_independent.py`，没有修改取数脚本、产品、学生数据或教学规则，没有连接生产、commit、push 或部署。规范交接由主审统一更新。

## 已确认的安全与兼容边界

1. 脚本只导入标准库，无 Flask/app/config、ORM、外部网络或模型推理；生产数据只在服务器进程内分组，不输出学生、任务、词义标识、答案、题面或身份信息。
2. 数据库 URI `mode=ro`、`query_only` 与列级 authorizer 三层保护。独测实际拒绝答案列、schema元数据、load_extension、DML、DDL、ATTACH 和关闭 query_only。仅在本机临时库中将 authorizer 改成允许并关闭 query_only，URI ro 仍阻止 CREATE；生产脚本没有这种解除保护的路径。
3. 正常最多8次查询（含 query_only 核对），每次3秒/50万行、总20秒、入口25秒闹钟、锁等待250毫秒；失败不输出部分结果或异常 SQL 内容。`rows()` 完整取出后关闭 cursor，不持跨查询长读事务。给定当前生产规模，未见需要取消预算的理由。
4. 用实际 `models.db.metadata` 创建临时 SQLite，核对全部白名单列存在，并完整运行 `analyze()`，没有依赖手写 fixture 去掩盖列名错误。尤其 `VocabularyTaskReview` 是逐题表，确有 student_id/task_id/sense_id/dimension；并非 JSON-only 队列表。此检查证明当前源码模型兼容，不能替代生产历史迁移状态检查。

## 口径审查与已经修订的风险

- SQL 时间窗口使用 UTC 存储、上海日期切分；行为指标只取前28/7个完整日，原始到期构成使用本次采集开始时间。
- 组学习通过任务/学生/首次 attempt ID 联表，仅纳入 score_eligible 且非补救记录，guide/订正排除。对应 `_apply_context_once` 的评分资格选择，不把指导题和产出题作为同一能力两个独立成绩。按词义去重输出任务错词数，并保留按能力统计。
- 完成记录原先可能将同任务 flow 和 legacy settlement 跨日双计，已修为优先已完成 flow，legacy 仅作无该完成证据时的回退。
- 任务跨窗口或尚未完成时，只能解释为窗口内观察到的错词比例；并非全任务最终错误率。当前容量保留有学习但零复习日，以及活跃学生的全窗口零日，不把“只算已做复习的日”作为唯一分母。
- 原始到期构成没有调用资格/可出题/当日冷却过滤，因此不是首页精确可领取数。stage0+last_answered_at 是错误状态代理，没有声称从全历史正式首答重建真实错误队列；不得直接用这些聚合行做存量迁移。
- 错误后“第几天”明确为自然日日差1/2/3；只选下一个有正式作答日期的第一结果。迟到第三天的结果不会在已经次日测过之后再算成“首次第三天复测”。缺测者留在观察覆盖率分母，不被自动判错；近期尚未成熟起点排除。
- 正确率是现有规则下返回者的条件比例，包含来源与难度选择偏差。语境产出前可能看过 guide，既有首答记录不能证明完全无提示；不能据此直接推断1天间隔优于2天，也不能将不同间隔组视作随机试验。
- 非原子多查询快照是刻意避免长读事务的取舍。`snapshot_utc` 是采集开始时间，不是历史状态重建；CLI 已去掉可误解为历史回放的 as-of 参数。并发作答可能改变少量跨查询边界，total_changes=0 只证明本连接没写入。
- 新错词表可以隔离低频巩固池的计算工作，但 SQL COUNT 的成本仍与匹配索引范围有关；不能将一次 COUNT 说成数学上 O(1)。

## 独立复核结果

8 项独测全部通过：Python3.10.20 **0.134秒**，Python3.13.3 **0.145秒**。覆盖真实模型列/整条空库查询、隐私读取与写入拒绝、单独 URI ro 保护、时间/行数预算、上海跨日、词义去重和能力分离、零学习/复习日分母、首个跨日复测及右截尾/观察覆盖率。Ruff 通过。

```sh
PYTHONPATH=. PYTHONWARNINGS=ignore TZ=UTC /private/tmp/studytracker-stage2-py310/bin/python -B docs/reviews/vocabulary-cache-policy-20261117/independent/test_policy_independent.py
PYTHONPATH=. PYTHONWARNINGS=ignore TZ=UTC /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/vocabulary-cache-policy-20261117/independent/test_policy_independent.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check docs/reviews/vocabulary-cache-policy-20261117/independent/test_policy_independent.py
```

独测初次两次修订仅涉及测试夹具：特殊字符文件路径须通过 SQLAlchemy URL.create，Python3.10的解除authorizer负对照使用允许回调而非None；不是取数脚本故障。最终全部通过后冻结，不用旧失败输出冒充生产失败。
