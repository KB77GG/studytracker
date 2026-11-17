# C3 性能实施与验收

当前实施树 `/private/tmp/studytracker-vocabulary-error-pilot-20261117`，分支
`codex/vocabulary-error-pilot-20261117`，输入 HEAD `513c732f`。本目录为合成数据验收，
未连接或修改生产、没有替学生领取/答题；本阶段结果尚未 commit/push/deploy。
根 agent 负责最终 CI、规范交接和生产启用，本文不能替代生产回读。

## 实施

- 每日额度与每批题数分开：每日30/40仍只可分别领取20+10、20+20；单批上限20。
- 新策略的选择/计数在首次写之前完成。SQL只取下一批<=20题；抽查按原稳定hash排序、
  同能力多来源去重后最多4题。领题拿写锁后核对 enrollment version，再验证有限题目，
  不在锁内重新扫描旧到期池或新队列。版本改变返回409并回滚。
- 清理分开“逻辑投影”和“实际落盘”：每请求最多清理100条过期队列/错过的抽查，
  加本批最多20条暂停到期恢复；只读统计仍展示全部应转移数量。空领取也推进有限清理。
  写入 `INSERT SELECT/UPDATE` 都有预选ID限制，不是全量写藏在一条SQL里。
- 领题前生成并冻结题目。写锁内只校验目标词、Sense、实际目标词书、能力和阶段等有限元数据；
  答题/结算使用冻结题目。空的听音选项也明确冻结，避免返回载荷时重新读取整本词库。
- 试点 context/listening 题库只读取题目需要的标量；每请求每书预解析一次候选元数据，
  复用原出题器、原hash和排序。只有纯字符串 lemma 解析做跨请求有界LRU（16384项，
  key包含单词及accepted_answers原文），没有ORM、学生状态或题目缓存；词库修改换key。
- 可选领取共享同一份候选词库，去掉逐题重读整书。SQL先排除所有到期能力都被挡住的词义；
  部分被挡的词义仍按旧顺序先找首个合格能力，该能力若被挡就跳过整个词义，不偷换成另一能力。
  分页资格判断使用标量输入，只有最终可返回的最多10项才物化ORM；原资格函数完整复用。
  非context资格的有界LRU只缓存完整不可变词源输入的纯结果，不缓存学生状态或词库context资格。
- 试点首次建学习flow在SAVEPOINT之前取得SQLite真实writer，修复DELETE模式并发
  read→write升级死锁。首次flow的大词库标量准备也在拿writer之前完成，writer内仅创建
  本任务的有限flow/题目。OFF保持原路径；回滚测试确认未留下flow。

## 正式断言

`tests/test_vocabulary_policy_performance.py` 共15项，无易波动的时钟阈值：

1. 添加旧mastery历史0/2400/10000时，36个完整service请求的SQL执行次数及实际DBAPI
   fetch行数逐项完全相等，覆盖首页、门禁、领取、四能力首答、忘记、订正、重放、结算、
   恢复领取、会话快照、continue、空领取与完整学习flow。统计包含commit，不包含fixture初始化。
2. 每日30/40额度仍每批<=20。
3. 10000条新增队列积压不会全量ORM物化，且每次清理100条；写锁后调用全量规划即失败。
4. 构建catalog/空听音选项补题不能发生在writer内。
5. 原始/准备后的题目在多种轮次、题型、重复释义/同义词过滤上完整payload等价。
6. SQL标量catalog和原ORM题目等价，修改源单词后不会复用旧解析。
7. 可选题顺序及答案与旧逻辑相同，每书仅加载一次catalog。
8. 首次flow的SAVEPOINT之前必须有真实事务，随后rollback不能留下flow。
9. 可选全部到期能力被挡时不做旧池资格物化；部分被挡仍保留原first-eligible语义。
10. 可选标量资格与原ORM的四能力/两goal/数字/同义词等价，词源编辑后不命中旧资格缓存。
11. 140词部分被挡的真实数据库场景跨越首128/续1024页，前10项仍与旧迭代器完全同序；
    页大小改变只减少往返，不截断候选，也不放宽能力选择。
12. 词条所属书缺失时，保留旧逻辑从mastery代表书回退到listening目标的资格（真实数据库
    孤儿词条反例先红后绿）。仅缺书页批量读取fallback，正常数据不增加查询。
13. 题目准备后、拿writer前，同义Sense的key/答案发生修改时返回409并完整回滚。
14. 缺书词条的mastery代表书目标在同一窗口修改时，同样重验拒绝，不发错题型。
15. 代表词已被改挂到另一Sense时，必做项转unanswerable/maintenance留记录；可选领取
    跳过错配词源，仍可领取其它10题，不把别的能力答案记到原队列。

重现命令（从上述工作树运行）：

```sh
/private/tmp/studytracker-stage2-py310/bin/python -m unittest tests.test_vocabulary_policy_performance -v
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_vocabulary_policy_performance -v
/private/tmp/studytracker-stage2-py310/bin/python docs/reviews/vocabulary-pilot-launch-20261117/performance/capture_request_work.py --output docs/reviews/vocabulary-pilot-launch-20261117/performance/request-work-py310.json
```

`request-work-py310.json`和`request-work-py313.json`保存最终36请求完整三规模结果，
两个Python版本逐项相同。例如summary 12 SQL/20行，preflight15/22，claim69/110，
正常answer27/13，settle40/76，首次学习queue42/58，均不随旧历史增长。
这是“保持当前目标词/词库不变，只添加旧个人历史”的断言；不能推论词库本身增长没有成本。

另测新队列0/2400/10000（额外旧逾期项，当前22项不变）：summary固定13 SQL/29行，
claim从93/214变为95/414、95/414，后两者均只持久化100清理行。
索引COUNT和排序仍有数据库CPU成本，绝不据fetch行数恒定声称新队列计算是O(1)。
JSON附带的单次wall_ms仅作诊断，不是隔离的延迟基准；时钟结论采用独立并发矩阵。

## 并发与限制

完整矩阵由独立 agent 的 `benchmark_delete_concurrency.py` 执行：文件SQLite明确DELETE、
1/3/6学生、旧池2400、ON/OFF、reading/context、三轮；每case清空纯解析LRU，统计真实
HTTP响应、重试、SQL/fetch、首次DML执行和提交。DML执行时间含等待与SQL执行，不能直接
叫作纯锁等待；DML完成至commit是持锁下界，额外记录BEGIN IMMEDIATE以及隐式SAVEPOINT提交。

完整数表、精确命令与源码版本区别见 [concurrency-results.md](concurrency-results.md)。
每版本必做矩阵2220/2220 HTTP200、零重试，所有请求<1秒；大书选10词扩展每版本
777/777通过，首次flow六并发最大3.10为829ms、3.13为675ms。

**严格C3门槛仍有一项未完全满足**：可选partial极端2400池六并发，最终三轮最大
3.10为1071ms、3.13为1144ms。每版本可选63/63请求成功，无重试，但不能写“所有可选
请求都<1秒”，也不能说每项ON都比OFF快（首答增加约2ms固定写事件成本）。是否接受
该明确限制开启小试点，由主agent记录判断；本报告不将完整C3标为全通过。

可选旧池仍存在索引元数据扫描/排序和资格检查；不能将其描述为恒定复杂度。全被挡住
与部分被挡住的2400池曾分别测到6并发4.59s和3.27s，都是实测后进一步修复，不能只展示
必做路径的好结果。1万词可选最终只测单人：全排除42ms、可领10题207ms、partial274ms，
后者实际读取40011行；1万词六人或更大规模不作1秒保证。
全局OFF旧路径未扩改，基线6并发首次flow已有409会如实单列，不归功于试点修复。

## 最终本机验证与文件冻结

最终完整词汇回归在Python3.10与3.13分别396/396通过（53.078s/45.300s），56源码SHA
保持一致，精确模块和日志见[`../validation/README.md`](../validation/README.md)。此前
定向130项有一个新增测试调用旧函数废弃参数的错误，修正测试后已由最终完整运行覆盖。
Ruff定向7文件全过；新模块/adapter/selector/
perf测试Black通过，巨型旧文件只格式化本轮函数且验证AST相同。`git diff --check`通过。

本agent产品改动为：`services/vocabulary_error_queue.py`（与core共编）、
`services/vocabulary_error_review.py`、`services/vocabulary_autonomous_review.py`、
`services/vocabulary_group_learning.py`、`services/vocabulary_context.py`、
`services/vocabulary_review_selection.py`，新增`services/vocabulary_policy_planning.py`、
`services/vocabulary_context_catalog.py`、`services/vocabulary_optional_selection.py`；
正式测试新增`tests/test_vocabulary_policy_performance.py`。旧`_iter_due_candidates`完整保留
HEAD原实现；新可选迭代独立模块。最终哈希见`integration-final-files.json`。

完整并发矩阵先完成，随后做格式/未用临时入口清理、独审缺书fallback和有限题源重验修复；
因此早先矩阵JSON的源码SHA与最终源码不同，不能冒称逐字节同一版。修后完整396双版本
通过；最终字节源码的一轮大书222/222及可选18/18请求全部200、零重试，前后SHA稳定。
大书全路径最大718ms，可选三场景最大分别908/197/932ms。该单轮不抹掉此前三轮1.144秒
尾延迟限制。独立报告记录精确命令及`final-source-*.json`。根交接/部署状态由主agent统一更新；本agent没有提交、推送、
部署、启用学生或生产写入。
