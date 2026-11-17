# 词汇复习规则与学习证据审计（2026-11-17）

结论：**优先处理前一天的错词、按出错能力复习、达标后退出强制错题队列，是合理的减负方向；“三天内做过两次就永久掌握”没有足够依据。** 宜把退出条件定义为不同日期的、无提示的首次作答成功，并把退出紧急错题队列与以后低频巩固分开。当前代码不是这个错题方案，而是正确、错误及部分未测试维度都可进入的多维间隔复习系统。

Claude 报告中“每任务净增 35–39、积压只增不减”不能由其截面统计和代码推出。**20 是一批上限，不是每天总上限；做完一批还能继续。** 但任务入口结算后自动返回任务，加上多个维度和后续到期会持续带来负担，因此实际负担问题值得处理。不能用纠正统计推断来否认负担，也不能通过删掉学习记录掩盖性能缺陷。

## 范围与证据边界

- 审计工作树：`/private/tmp/studytracker-vocabulary-entry-stage2-20261117`。
- 分支：`codex/vocabulary-entry-stage2-20261117`；规则基线：`e19a81045da782bd2a245caee0222dcbdf87b84b`。
- 阅读对象：`services/vocabulary_mastery.py`、`services/vocabulary_group_learning.py`、`services/vocabulary_autonomous_review.py`、`services/vocabulary_remediation.py`、`services/dictation_review.py`、复习页 JS/WXML 及现有合成测试。下列行号参考该基线，函数名为稳定定位点。
- 编写时同一隔离树已有其他 agent 的性能改动：`services/vocabulary_autonomous_review.py`、新增 `services/vocabulary_due_cache.py`、`services/vocabulary_review_selection.py`；本审计没有修改这些产品文件。测试在当时工作树执行，不能当成纯净基线完整回归。
- 本审计没有读取生产数据库、重放生产接口或新增学生数据；不复制报告中个案表格。没有 commit、push、部署、小程序上传/提审/发布或数据迁移。本文是本机审计材料，主审统一更新总 README 与规范交接。

## 当前规则到底是什么

| 问题 | 代码事实 | 对用户理解的影响 |
| --- | --- | --- |
| 只有昨天错的词进入吗？ | 不是。`_apply_dimension_answer` 给首次正确也排期；错误重置为 stage 0、约 24 小时后到期。`_due_candidates` 查任一维度 `next_due_at <= now`，包括较早逾期及正常复习。 | “到期”不等于“答错”，也不是按昨天错题记录直接生成。 |
| 全部词书都自动进入吗？ | 也不是。必须有该学生的 mastery 行、相应到期时间及可出题材料。尚未建立学习状态的整本词书不会仅因存在于目录就全部进入。 | 应区分已建状态、已作答、已错误、今日可领取四种集合。 |
| 未测能力能进入吗？ | 能。`_initialize_flow` 的综合任务对 `meaning_recall`、`audio_form_recall` 调用 `_schedule_comprehensive_review_dimensions`，未测能力排到约 24 小时后。首次非语境成功也会按任务目标引导其他未启动能力。 | 当前有些“复习”实际是该能力第一次正式检测，不是原错题再测。 |
| 能力如何分？ | `meaning_recall`、`form_recall`、`audio_form_recall`、`context_use` 独立 stage/due。阅读目标含意思和语境，写作含拼写和语境，听力含意思和听音拼写，综合含四维。 | 不是整个单词共用一个正确/错误状态；一个维度成功不会自动证明其他维度。 |
| 是否每次四维重做？ | 不是。自主复习每词义选一个到期且合格的维度，优先补救、真实错误、未测能力，再按到期等排序；同一词义当日有正式首答后，整词义冷却至下一上海自然日。 | 多批也不会同日把同一词义剩余四维一次刷完；其他维度可留到后续日期。 |
| 是否仅复现原来错的轮次？ | 不是原题轮次逐一重放。自主复习依据词义、维度、阶段重建题目。组内语境阶段还优先使用产出题（缺失时用降级题）更新语境状态，不把每个辨析/产出轮次作为独立长期队列。 | “原维度”与“原轮次/原题”须分开。只复用完全相同题面可能测到题面记忆。 |
| 能否扩展到别的维度？ | 能。`RELATED_DIMENSION_BY_ERROR` 为意思→语境、拼写→语境、听音拼写→拼写、语境→拼写；同维延迟补救失败且完成订正，或选择忘记时，可安排关联维度。 | 当前不是严格的“只练原错维度”。这类扩展应有目标与负担依据。 |
| 成功会退出吗？ | 会把本维度的下次到期推到未来；当日整个词义还会冷却。但不删除 mastery，也不永久取消后续复习。另一个维度的旧到期时间可能仍保留。 | 今日列表下降、所有历史到期时间清空、长期掌握，是三件不同的事。 |
| 到最高阶段还来吗？ | 会。stage 6 后正确仍安排约 60 天后；该维度标记长期掌握，四维都到 6 才有整体长期标记，标记不等于退休。 | 不能说现行规则“两次就移出”，也不能把长期维护总量全称为紧急错题欠账。 |

主要源码定位：`vocabulary_mastery.py:57`（目标与间隔）、`:802`（整体掌握）、`:820`（引导其他维度）、`:834`（答题状态）；`vocabulary_group_learning.py:80`（综合能力）、`:135`、`:651`（预排未测能力）、`_apply_context_once`、首次答题状态应用段；`vocabulary_autonomous_review.py:396`（自然日冷却）、`:430`（候选选择）；`vocabulary_remediation.py:26`（关联能力映射）。

### 间隔不是固定的学习后第 1、3、7 天

`REVIEW_INTERVALS_DAYS = (1, 3, 7, 14, 30, 60)` 是**从每次到期成功的实际答题时间往后加**。例如没有失败且准时回答：D0 首次正确 → D1 复习 → D4 → D11 → D25 → D55，到 stage 6 后下一次 D115。提前回答且 stage > 0 不推进阶段；错误则重置该维度，约 24 小时后再来。

若 D0 首答错误，D1 正确仅升到 stage 1、下一次 D2；D2 再正确升 stage 2、下一次 D5。这可以在前三天出现两次成功复习，但现行代码仍安排后续，而不是第三天永久退出。未启动语境维度由非语境成功引导时，默认先设 +7 天；若实际语境首答发生，其结果仍按该维度的规则应用，不能把所有语境题都理解成强制等七天。

代码的“次日”是 `now + timedelta(days=1)`，不是次日零点。因此昨晚错误的题，今天上午未必已到期。如果产品承诺“每天复习昨天全部错题”，还需另行明确自然日领取窗口和最小间隔，不能假定现有 +24 小时已经实现。

### 订正、延迟重测和结算不是一回事

- 自主复习的首答即应用掌握状态（幂等），不必等整批结算。错误/忘记保留为首次错误。
- 订正记录为 `is_first_attempt=False`；订正正确不把首次错误改成正确，也不算一次独立延迟成功。订正最多两次；耗尽也允许结束该订正并留待以后，不代表已会。
- 组内错题再测、间隔若干其他题后的同维补救、关联能力补救，是受预算限制的当次教学流程，不能等同不同日期的独立记忆证据。
- 一批完整结算不要求全部正确。完成所需首答和订正流程（或规则允许的明确延期/隔离）可以结算；放行新任务是防止被旧题无限阻塞的负担保护，不是“已掌握全部到期词”的证明。

对应：`_apply_review_item_state`、`submit_review_correction`、`settle_review_session`；`vocabulary_remediation.py` 的 `MAX_CORRECTION_ATTEMPTS=2`、`MAX_REMEDIATION_PER_WORD=2`、`MIN_OTHER_FORMAL_QUESTIONS=5`、`MAX_FORMAL_QUESTIONS_PER_WORD=4`。这些常量约束不同层级，不宜合并成“所有词每天只可复习两次”。

### 20、每日放行、多批及“清零”

`MAX_REVIEW_BATCH=20` 限制一次冻结领取的题数。`settle_review_session` 结算后清除 claim key，返回 `remaining_due_count` 和 `continue_available`；`continue_review` 可领取下一批。因此服务端没有每天 20 词总额上限，现有测试明确验证一批 20 后可再领余下 2 词（均为合成数据）。

`review_preflight` 对同一学生及复习归属日期，只需已有一批结算且没有未完新批次，即可放行尚未开始的教师任务；已开始的任务不会被中途复习门槛打断。任务午夜宽限期会保留任务归属日期，不能简单等同所有情况都按当前零点切换。若随后主动开了另一批但未做完，它可能重新影响未开始任务的入口。

UI 有实际引导差异：从首页自主进入，可点“继续复习”；从具体任务进入，一批结算后约 0.5 秒自动返回该任务，隐藏/拦截继续操作。故“常规路径可能每天只做一批”是合理的产品风险，但“代码每天最多 20”不成立。源码：`miniprogram/pages/student/vocabulary-review/index.js` 的 `settle`、`continueReview`；`index.wxml` 继续按钮条件。

`due_count` 是当前可领取的合格词义数（每词义一个），排除了当日已正式答过的词义；并非所有逾期维度个数。故一批做完显示剩余 0，也可能是当天冷却后的 0，其他维度仍有过去的 due 时间；反过来，有正常长期维护到期也不代表此前复习无效。

## 对 Claude “净增 35–39 / 只增不减”的审查

被审查来源：`docs/reviews/vocabulary-flow-latency-20261116/README.md:26` 起，尤其 `:33`、`:177`。其中本次只引用需要审查的结论，不复制个案数据。

| 原推断 | 审计判断 |
| --- | --- |
| 每任务约新增若干十词，所以所有这些都会次日成为错题 | 前半需检查去重与学习定义，后半把正常复习和未测能力错称为错题。不同目标和实际答题时间会影响到期。 |
| 每批 20，因此每天只能消化 20 | 不成立。批量与每日总额不同；但任务入口默认返回会限制学生主动继续的机会。 |
| 当前到期存量 ÷ 已完成任务数 ≈ 每任务净增 35–39 | 不成立。这是截面比值，没有前后时点差分，没有扣除复习、重到期和任务间重叠；不是观测到的净流入。 |
| 积压必然只增不减、永远清不完 | 不成立。暂停新学、完成更多批次、到期维度成功推迟等都能使当前可领取量下降；未来再到期是维护，不是现有债务从未被处理。 |
| 大积压会使每步重复扫描变慢 | 与以上统计推断不同，属于可直接测量的计算路径问题。仍应以性能回放和复杂度证据评估；改教学政策不能代替修复全量扫描。 |

若新到期与再次到期的工作量长期超过实际完成量，积压当然可能增长；目前还不能据截面证明其增长率或单调性。准确分析至少需要按天记录：新进入的词义×维度、正常再次到期、失败重排、成功推迟、当天冷却、实际完成批次/分钟。把原始逾期维度数与可领取词义数混算，会进一步失真。

一个更准确的判断是：**系统把新学后的计划巩固、未测能力、真实错题和长期维护合并为“到期”；如果学生只沿默认一批路径学习，而新任务不断增加，这种队列很容易超出日常容量。具体增长速度需要时间序列，不能由当前存量除任务数得到。**

## 一手学习研究支持什么、不支持什么

| 原始研究 | 直接支持的方向 | 对此产品的边界 |
| --- | --- | --- |
| Karpicke & Roediger (2008), *The Critical Importance of Retrieval for Learning*, Science, DOI 10.1126/science.1152408 | 外语词对实验中，首次成功后继续检索有利于延迟保持；首次会答不等于学习已经完成。 | 支持保留一些后续检索；不证明每个已会词每天强制出现，也不证明固定六阶段是最优。[PubMed 原文摘要](https://pubmed.ncbi.nlm.nih.gov/18276894/) |
| Pashler, Cepeda, Wixted & Rohrer (2005), *When Does Feedback Facilitate Learning of Words?*, DOI 10.1037/0278-7393.31.1.3 | 词对学习中，错误后提供正确答案改善一周后保持。 | 支持及时纠错；看过答案后的当场订正不能单独作为延迟掌握证明。[作者提供的论文全文](https://www.yorku.ca/ncepeda/publications/PCWR2005.pdf) |
| Cepeda et al. (2008), *Spacing Effects in Learning: A Temporal Ridgeline of Optimal Retention*, DOI 10.1111/j.1467-9280.2008.02209.x | 事实学习实验中，合适间隔随希望保持的时长而变；更长间隔并非无限更好。 | “D1/D3”可做产品初始参数，不能宣称适合所有年龄、词难度与考试时间，更不能保证长期记住。[出版社原始研究摘要](https://journals.sagepub.com/doi/10.1111/j.1467-9280.2008.02209.x) |
| Karpicke & Bauernschmidt (2011), *Spaced retrieval: Absolute spacing enhances learning regardless of relative spacing*, DOI 10.1037/a0023436 | 在其重复检索实验里，总体间隔比扩张/均匀/收缩排列的差别更关键。 | 支持把练习分开；不能把某条递增数字链当作普适定律。[作者实验论文](https://learninglab.psych.purdue.edu/downloads/2011/2011_Karpicke_Bauernschmidt_JEPLMC.pdf) |
| Vaughn, Dunlosky & Rawson (2016), *Effects of successive relearning on recall*, DOI 10.3758/s13421-016-0606-y | 外语词对在后续每周的多次重新学习中获得收益；初次同一场反复到很高正确次数的优势会随后续学习缩小。 | 支持跨时段成功检索，而非只堆当场重复。本研究采用四/五次后续周间隔学习，不能用来证明三天两次足够。[原始研究摘要](https://pubmed.ncbi.nlm.nih.gov/27027887/) |

这些研究主要来自受控词对或事实学习，不能直接等同真实英语听力、拼写、语境运用全部能力，也没有直接检验本项目学生的“只错维度+D1/D3退出”方案。以下是结合证据与产品容量的设计建议，不是研究已验证的最优算法。

## 对用户方案的具体建议（尚未实施）

1. **把强制错题队列定义清楚。** 按词义×能力保存正式首次错误；优先前一天及更早未解决的错误。不把所有曾经学过、正常复习到期或从未测过的能力都称为错题。
2. **原错能力优先，但不要把原题轮次当作唯一证据。** 意思错先测意思，拼写错先测拼写；使用等价的新题面检查同一能力。有明确课程目标或新错误证据时再检测相关能力，避免无条件给每个错词补齐四维。
3. **用“独立成功”退出，而不是“参加两次”。** 可试行错误后次日第一次无提示检测、约第三天第二次检测，均以正式首次作答为准；二次都成功后从强制错题队列退出。精确天数是可调整的初始参数。当天看答案后答对、订正次数耗尽、点击完成，都不能充当这两个成功。
4. **失败不因到了第三天而自动删除。** 新失败重建巩固需求，保留原始证据；持续困难的词应降低新学负担、补充讲解或交教师处理，避免把学生困在无限循环里。“限定每次时间”与“误标已掌握”分开。
5. **退出强制队列后保留低频检查。** 可进入非阻塞的维护区，后续按目标保留期限做抽测或复习；不宣称永久掌握。对首次一直正确的词也保留适量延迟检测，否则从来没暴露的遗忘无从发现。7/14/30 天可作为评估时点示例，仍不是对每个词的保证。
6. **容量按每天时间核算，而不是只按 20。** 每批 20 可以保留作交互分页；若昨日错误超过可用时间，透明列出留待后续的错误，并同步减少新词或安排补习。不能一面承诺“全部”，一面静默截断；也不应为清零无限加课。
7. **存量迁移保留历史。** 将真实错题、未测能力、正常维护分层处理；不能因现有 stage 或“做过两次”就批量删记录、改成长期掌握。旧记录是否足够识别两次无提示延迟成功，需要单独的数据审计。

判断改进是否有效，应同时看延迟的无提示首次正确率、目标能力迁移、实际分钟数、完成/放弃率和仍未解决错误；不能只看首页数字变小。建议先对有限范围试行，比较延迟保持与负担，再调整间隔和成功门槛。当前性能修复应独立保留，使任何合理教学政策都不会因为数据量增加而卡住入口。

## 本机验证与下一步

在本报告工作树使用现有合成 SQLite 内存测试验证了批次继续、单词义每日轮换、错误 +24 小时、后期 30/60 天间隔、同维错误触发关联能力、提前正确不推进。命令：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q tests/test_vocabulary_autonomous_review.py::AutonomousVocabularyReviewTest::test_cross_book_batch_is_real_questions_and_repeat_claim_is_idempotent tests/test_vocabulary_autonomous_review.py::AutonomousVocabularyReviewTest::test_comprehensive_sense_rotates_one_dimension_per_day tests/test_vocabulary_autonomous_review.py::AutonomousVocabularyReviewTest::test_wrong_is_plus_24h_and_30_60_day_intervals_are_consumed tests/test_vocabulary_autonomous_review.py::AutonomousVocabularyReviewTest::test_autonomous_failed_delayed_retry_releases_one_related_dimension tests/test_vocabulary_autonomous_review.py::AutonomousVocabularyReviewTest::test_forgot_delayed_retry_releases_related_without_correction_or_reschedule tests/test_vocabulary_mastery.py::VocabularyMasteryFlowTest::test_schedule_wrong_resets_to_tomorrow_and_early_correct_does_not_advance
```

结果：**6 passed, 1513 warnings in 1.37s**。警告为现有 SQLAlchemy/SQLite/UTC 旧接口弃用警告；无失败。本审计未创建新的产品测试，未对研究建议进行在线教学实验，也未证明生产每天的实际复习容量或长期记忆效果。规则代码审阅与这六项验证不能替代第二阶段性能改动的完整回归。

下一步：由主审先把“可确认的代码事实”“负担与流程设计判断”“待验证的教学参数”分别呈现给用户；若推进教学方案，先定义成功口径、容量、存量迁移和评价窗口，再另行实现。主审应在总交接中注明本文及其测试只在上述隔离树本机可见，并记录最终产品修改、提交、部署状态；本子任务未执行发布动作。
