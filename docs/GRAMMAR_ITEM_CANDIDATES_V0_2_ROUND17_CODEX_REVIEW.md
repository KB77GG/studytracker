# 语法候选题 v0.2 第十七轮独立复审（Codex）

审核日期：2026-10-28，Asia/Shanghai。**结论：有条件通过，以剑桥题为准。AC1、AC2 的本轮修复关闭。新增 0 阻断、0 应修、1 建议（AD1，复核原因的措辞）。机经本轮新确认问题 0 项。**

这里的“有条件”是：本轮通用规则和点名修复可接受，保留 needs_review 隔离、既有教学口径和人工验收边界；不表示 27,824 道剑桥 auto 已全部逐题人工审定，或可据此直接上线。AC2 的原文恢复仍待单独授权，本轮完成的是撤出自动池。抽样120道均来自剑桥auto：120个局部答案/高亮可成立，119题未见影响本题判读的问题；另1题保留已披露的非并列T2多目标提醒，不能称120题均可唯一判分。待复核题单独统计，不计入此120。

## 1. 范围、工作树与关闭情况

- 工作树：`/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker`；分支 `codex/grammar-item-candidates`。
- 开工读目录链 AGENTS、CLAUDE、HANDOFF 最新两节、WORKLOG 顶部，再核对 Git。起点 `dd9f6e7cf7c2d4b6acbf93db1a82aa2c7df29c97` 干净，fetch 后 ff-only 到 `29701e71ca953452dd3e06e3bd233ea9d0ac331f`。没有普通 merge、rebase、改写历史或合 main。
- `git diff --stat dd9f6e7..29701e7`：14文件，672插入/440删除；4个Python、2份阅读解析、4份交付、4份文档。全部在授权范围。raw、static（含指定剑桥原文）、修订表、models.py、app.py、api、miniprogram、.github/workflows 均零改动。
- 两份JSON按对象和原始文本双核对：E-02只改1个role和第4条难点；A-03只改第1条难点。用这些字符串替换即可逐字节得到新文件，其他字段、排版不变，未知role未增加。
- 新规则及接入不读取 passage_id / sentence_id / item_id，唯一调用者为 `adverbial_relations`。题号生成用ID定位来源不是黑名单。
- 所有生成/探针/SQLite在仓库外 `O=/Users/zhouxin/.codex/audits/grammar-v02-round17-20261028`。只向仓库写本报告和两份交接文档。
- `O/source` 是完整29701e7快照；`O/baseline` 为此前完整8e04e17快照，其代码/数据与dd9f6e7相同（两者只差3份审核文档）。`O/main` 完整676569c快照的2853个Git blob全部核验；没有只拿main的数据拼当前代码。

| 编号 | 关闭情况 | 独立结论 |
| --- | --- | --- |
| AC1 | 关闭 | 规则单独命中15题，8控制不变；E-02外层改为介词短语正确，新增T3答案唯一可成立。复合连词和after+-ing只送审，不能一律宣判类别错误，见AD1。 |
| AC2 | 本轮隔离修复关闭 | A-03共12题全needs，点名6道auto撤出自动池；说明与原版10⁹一致。原文仍109，恢复原文不是本轮已完成事项。 |

## 2. 用户8项清单逐项结果

精确命令与路径见§10。下表不沿用Claude数字；均来自本机重新生成、比较或执行。

| 项 | 结果 | 主要独立证据 / 命令 |
| --- | --- | --- |
| 1 范围 | 通过 | git diff --stat / --name-only；audit_data.py按白名单核验14文件、JSON对象及字节替换；AST只见T4调用新规则；禁止路径diff为空。 |
| 2 AC1 | 本轮通过，措辞建议AD1 | rule_probe.py用新代码collect旧dd9数据：50243 IDs不变、其他字段0变；Cam12/Jij3命中；8控制逐字段不变；24种真实句子现解析与缓存一致；新T3及删3题、少1拒绝记录核对见§4。 |
| 3 AC2 | 隔离通过 | 全12题含source_quality，6新降+6原needs；原版PDF图像复看为10⁹；static没有改。恢复建议及引用位置见§8。 |
| 4 120题与新扫描 | 完成 | seed20261106、各模板20；120局部答案可成立，1题保留旧多解提醒；全池定向扫描32题/17目标，未见新类别错误，见§6–7。 |
| 5 全池比较 | 与预期一致 | 50243→50241，只E-02增1删3；共同题号Cam6/Jij2降级，其他字段0变；auto40298、Cam27824；原因计数吻合，见§9。 |
| 6 双生成/交付 | 通过 | G连续两次generate --seed 20261018；4文件双跑字节一致，JSONL/XLSX与提交一致，两报告仅Python版本一行差；78回归/7过滤不变；批次旧ID10/同位置0；7表、6×60、四下拉、盲审。 |
| 7 测试/数据 | 通过 | 专项155；Flask-only轻量223运行=222通过+1跳过；Node退出0；reading22；validator0、textfix --check0、raw171篇content+groups全等、graph字节一致；4Python Ruff check/format通过；4负测2断言失败/2接口错误。 |
| 8 临时导入 | 通过，解释成立 | 完整676569c→297：236updated/81skipped/0failed。另新SQLite独立跑676569c→dd9，同为236/81/0，且两篇早已因标签字段变化updated，见§9。 |

## 3. 问题分级

### 剑桥：阻断0、应修0、建议1

**AD1 — 建议：把“送复核信号”与“必定不是从句”区分。**

位置：`scripts/grammar_items/templates.py:691` 的说明，`scripts/grammar_items/reporting.py:285` 的counting_notes。现文字把该条件命中的目标概括为“介词短语而非从句”。实测含 `by the time...`、`in case...` 等常按复合连词分析的完整结构；此外无显式主语的-ing可以采用非限定从句分析。它们进入needs可接受，不能据解析器prep/pobj/pcomp标签断言英语类别必错。

复现：用297代码对dd9阅读解析运行collect，按prepositional_target筛出§4的15题，比较定义与目标；尤其 `gi_v02_ef40a9bd0501`、`gi_v02_17aacda1199d`。建议说明改为“目标疑似介词结构，或涉及复合连词/非限定结构，类别需人工复核”，并说明项目暂按传统有限从句/非谓语分组。无需为此撤销送审，也不建议凭词形批量改标。

这只是措辞建议，没有新auto受害题。Cambridge也把某些after+-ing称为非限定从句，说明术语框架需要明确，不能以“无主语”本身定义“不是从句”。[Cambridge English Grammar Today: finite and non-finite clauses](https://dictionary.cambridge.org/us/grammar/british-grammar/clauses-finite-and-non-finite)。

### 既有边界（不另计新问题）

随机样本§6第35题 `gi_v02_18543efdcecd`、ielts15_test3_p3 G-02：机器选 `that may be faced there`，句中另有 `that's relevant to survival`，泛称“划出句中的定语从句”仍不唯一。局部边界/类别正确，原句可读，但不能当唯一答案题直接判分。这属于此前已披露的非并列T2多目标问题；第十二轮的连词题干只解决并列分句，本轮未改它。建议沿用后续题干定位/多答案或送审决策，不重复立项。

此前已披露的系表判分中心、介词化分词、substring查重、未并入单位的小品词/连字符动词/分词、插入语隔开的并列目标、盲审范围等继续保留；本轮没有以“未重新查到”认定它们关闭。

### 机经（暂缓）

本轮新确认问题0项，旧暂缓不重复列入数量。此次规则涉及3题的处理见§4：2道新降、1道原needs加原因；这3题是修复验收对象，不是新增机经问题。

## 4. AC1逐题检查

### 4.1 规则单独生效（旧阅读解析）

独立调用当前collect，root指向旧dd9代码/数据等价快照；使用同环境、同句文本的解析缓存，输出到O，不改旧快照。序列化统一tuple/list后逐字段比对：50243题及ID集合不变，唯一变化是T4的status/reasons。Cam12=1新降+11原needs；Jij3=2新降+1原needs。

条件依赖目标的**外层中心**，prep+pobj可发现外层名词短语，prep+pcomp/VBG且无主语/助动词可将“after doing”交给人工统一口径。没有把所有finite=false、省略主语或所有when/if结构降级。它是局部启发式，解析错挂、复合连词和其他依存仍须人工判断。

| 题号 | 来源 | 模板 | 旧→规则单独状态 | 目标 / 机器关系 | 独立判断 |
| --- | --- | --- | --- | --- | --- |
| gi_v02_cf28b13ef739 | ielts14_test2_p3 E-02 | T4 | auto_pass→needs_review | until the point where any further increase in order reduces productivity → 时间 | 明确外层PP，原T4题干前提错；送审正确，改标后此题已删除。 |
| gi_v02_ef40a9bd0501 | ielts18_test3_p2 G-04 | T4 | needs_review→needs_review | By the time the company folded in 1931 → 时间 | by the time+完整从句可按复合连词；时间答案成立，保守送审可接受，不能说必错。 |
| gi_v02_dcaab39eefd8 | ielts20_test4_p1 B-05 | T4 | needs_review→needs_review | By the time she graduated from high school in 1905 → 时间 | by the time+完整从句；同上，原有subordinator_unknown已needs。 |
| gi_v02_3b706d95f6aa | ielts4_test4_p3 C-08 | T4 | needs_review→needs_review | at exactly the same time as this new realization of the finite character of health-care resources was sinking in → 时间 | 整体时间结构可按复合连词或PP分析；时间意义成立，送审统一口径。 |
| gi_v02_824dcbe57dbc | ielts5_test2_p2 C-13 | T4 | needs_review→needs_review | in order to understand not only humour but language understanding and reasoning in machines → 目的 | in order to+不定式目的结构；按项目非谓语口径不应直接称有限状语从句，送审合理。 |
| gi_v02_4eecbb855617 | ielts5_test4_p1 C-40 | T4 | needs_review→needs_review | in order to balance their needs and aspirations with the demands of tourism → 目的 | in order to+不定式；同上，目的意义成立不等于类别正确。 |
| gi_v02_a0d1afa0dd1a | ielts6_test2_p1 A-05 | T4 | needs_review→needs_review | In the years that have followed → 时间 | In+the years名词短语，内部that定语从句；外层PP，送审合理。 |
| gi_v02_00fa5312fcd1 | ielts6_test2_p3 B-06 | T4 | needs_review→needs_review | by the time humans had formed even semi-permanent settlements → 时间 | by the time+完整从句；可作复合连词，保守复核而非判错。 |
| gi_v02_7810978899fa | ielts7_test3_p1 J-03 | T4 | needs_review→needs_review | in order to observe what her team might do → 目的 | in order to+不定式；目的意义可成立，类别待复核。 |
| gi_v02_08b90fd335c4 | ielts8_test1_p1 D-01 | T4 | needs_review→needs_review | In order to track temporal hours during the day → 目的 | in order to+不定式；目的意义可成立，类别待复核。 |
| gi_v02_17aacda1199d | ielts9_test1_p2 B-13 | T4 | needs_review→needs_review | in case any really convincing evidence emerges in the future → 目的 | in case+完整从句有复合连词分析；这里有预防/目的意味，送审不等于否定时间之外的关系。 |
| gi_v02_2e204092c1f9 | ielts9_test4_p3 E-01 | T4 | needs_review→needs_review | in order to make everything in heritage more 'real' → 目的 | in order to+不定式；目的结构，按项目分类应复核。 |
| gi_v02_defb9fe75282 | reading_jijing_56_test_64_p1 A-07 | T4 | auto_pass→needs_review | before the next harvest → 时间 | before+名词短语the next harvest；原题将PP称从句，降级合理。 |
| gi_v02_6ea08e210929 | reading_jijing_65_test_69_p1 F-02 | T4 | needs_review→needs_review | for fear that they will run around in my head all day → 原因 | for fear that有复合连词/PP加内容从句的分析；因果/目的也需统一，原needs合理。 |
| gi_v02_f1a02bfcf0ac | reading_jijing_83_test_95_p1 F-02 | T4 | auto_pass→needs_review | after listening to and observing Alex → 时间 | after+-ing存在非限定从句/介词加动名词两种术语口径；扩大到此例送审合理，不应断言所有after+-ing均错误。 |

### 4.2 八个控制例

8题当前与旧池逐字段相同、均auto，无prepositional_target。现解析也复查；不只检索题号。

| 题号 | 来源 | 目标 | 状态 | 判断 |
| --- | --- | --- | --- | --- |
| gi_v02_3cfba0eafd9a | ielts14_test2_p3 F-01 | when innovating | auto→auto | when引出的省略结构，时间成立，head为动词而非prep+pobj。 |
| gi_v02_e9f70015c6df | ielts14_test2_p3 H-01 | if overused | auto→auto | if overused可还原条件省略句，不因无显式主语排除。 |
| gi_v02_bda011edf0d9 | ielts14_test4_p3 K-02 | until after they've happened | auto→auto | until的补足部分含they have happened；pcomp是有限动词且有主语。 |
| gi_v02_8b11cffee970 | ielts4_test2_p3 C-19 | after training stops | auto→auto | 实际training stops有主谓，虽stops误标NNS pcomp，仍不满足VBG条件。 |
| gi_v02_0628b13312c2 | ielts4_test4_p1 F-27 | as long as our training continues to improve | auto→auto | as long as引出有主语/谓语的条件结构，不能凭as的错挂当PP。 |
| gi_v02_315ddcb542db | ielts5_test2_p1 G-30 | although treated with disdain in its early years | auto→auto | although treated为合法让步省略，未误伤。 |
| gi_v02_839c85588857 | ielts7_test4_p1 C-03 | if sustained over a long time | auto→auto | if sustained为合法条件省略，未误伤。 |
| gi_v02_57876a908e1c | ielts9_test1_p2 E-33 | if faced with a superior and much older civilization | auto→auto | if faced可还原主语+be的条件省略，未误伤。 |

### 4.3 E-02改标及新增题重点核对

`data/reading_study/ielts14_test2_p3.json:1119` 外层role改为prepositional_phrase正确；第4条难点明确until为介词、the point为名词中心、where修饰point，整段作时间状语，解释准确。`resolve_role('prepositional_phrase')` 返回concept=prepositional_phrase、中文“介词短语”。阅读页按导入后的标签显示；本轮只是临时SQLite核验，生产没有导入。

新题 `gi_v02_67b08c4eb2c2`：

- 题干：判断句中【】标出的部分是什么。
- 范围：字符[150,222)，完整 `until the point where any further increase in order reduces productivity`。
- 外层为until+名词短语，内部where从句只是该名词的修饰语。五选项为定语/名词性/状语/并列分句/不是从句（短语或非谓语）；**按所标整个范围，“不是从句”是唯一可成立答案**。
- “作时间状语”是功能，不使整个结构变成状语从句；“里面有where从句”也不使外层变成定语从句。学生可能误选是正常的内外层辨析，不是第二个正确答案。可在讲解里强调“整个【】”，无需因此降级。
- 原句可阅读，新题局部答案、高亮和题干成立，auto可接受。这里不是把有内部从句的所有短语一律判为从句。

until可兼作介词和连词，具体须看补足结构。[Cambridge English Grammar Today: Until](https://dictionary.cambridge.org/grammar/british-grammar/until)。

| 题号 | 模板 | 旧→现 | 独立判断 |
| --- | --- | --- | --- |
| gi_v02_cf28b13ef739 | T4 | auto→删除 | 旧时间意义可理解，但外层类别前提错；删除正确。 |
| gi_v02_b8929c66e100 | T2 | needs→删除 | 旧把外层PP作为状语从句目标；删除正确。 |
| gi_v02_e4ae9c9ac17d | T3 | needs→删除 | 旧“状语从句”选项不对；被新类型题替代。 |
| gi_v02_67b08c4eb2c2 | T3 | 新增auto | 外层PP、内部定语从句；整体答案唯一。 |

T6旧拒绝记录确实少1条：temporal_clause外层until此前因finiteness_mismatch拒绝；改标后不再生成该从句谓语目标。另4条旧拒绝记录完全不变，没有把“少拒绝”误说为新增T6。

补充漏网扫描：全剑桥auto T4中，中心finite=false剩8题，恰为§4.2的8个合法/解析错挂控制；未发现第二个同型PP目标漏入auto。该检查不证明任意解析误挂都能被新规则发现。

## 5. AC2逐题复核

A-03仍有12道候选，全部needs_review并含source_quality：6道旧auto降级、6道旧needs仅增加原因。难点仍4条，第一条先说明原版10⁹、现文本丢上标，给出十亿和中文理解，适合学生纠正当前显示；没有悄悄改剑桥句子或static。

原版证据重新查看出版社PDF第9页（印刷页18）的图像：9确为上标。纯文本抽取仍会变成109，故不用纯文本作为排版证据。[Cambridge IELTS 11 官方样章](https://assets.cambridge.org/97813165/03850/excerpt/9781316503850_excerpt.pdf#page=9)。

以下12题的原句均暂不宜未经解释直接用于学生自动练习。旧needs里有非谓语被标成从句的问题，本轮没有声称改正那些机器答案。

| 题号 | 模板 | 旧→现 | 目标 / 答案 | 逐题判断 |
| --- | --- | --- | --- | --- |
| gi_v02_e9c210fd1e2b | T1 | auto_pass→needs_review | will / be / needed / will / be / needed | will be needed是主句谓语；局部正确，数值原句必须隔离。 |
| gi_v02_9f372d4f852c | T3 | needs_review→needs_review | to grow enough food / 状语从句 | to grow enough food是非谓语，选状语从句不适合；原边界/类别原因仍在。 |
| gi_v02_b92ae321acc5 | T3 | needs_review→needs_review | to feed them / 状语从句 | to feed them是不定式，选状语从句不适合；原类别原因仍在。 |
| gi_v02_b0d13b157ddc | T3 | auto_pass→needs_review | if traditional farming methods continue as they are practised today / 状语从句 | if...完整条件从句；局部类别正确，原句数值问题隔离。 |
| gi_v02_eeade093260d | T4 | needs_review→needs_review | to grow enough food / 目的 | 目的意义可理解，但题干把不定式直接称状语从句且边界需看；原needs保留。 |
| gi_v02_72156777d594 | T4 | needs_review→needs_review | to feed them / 目的 | 目的意义可理解，但不是项目所称有限状语从句；原needs保留。 |
| gi_v02_3de81a78963f | T4 | auto_pass→needs_review | if traditional farming methods continue as they are practised today / 条件 | if...条件关系正确；原句数值问题隔离。 |
| gi_v02_f00864c296fb | T5 | auto_pass→needs_review | An estimated 109 hectares of new land (about 20% larger than Brazil) / An estimated 109 hectares of new land (about 20% larger than Brazil) | 完整主语含括注，边界正确；数值显示错误，隔离。 |
| gi_v02_6b030d70d081 | T6 | auto_pass→needs_review | will be needed / 主句谓语 | will be needed主句谓语身份正确；原句数值问题隔离。 |
| gi_v02_d0a124f43461 | T6 | needs_review→needs_review | to grow / 从句里的谓语 | to grow为非谓语，不是从句里的谓语；原finiteness_mismatch仍在。 |
| gi_v02_a0724f3a9a89 | T6 | needs_review→needs_review | to feed / 从句里的谓语 | to feed为非谓语，不是从句里的谓语；原finiteness_mismatch仍在。 |
| gi_v02_d4ea719b03d3 | T6 | auto_pass→needs_review | continue / 从句里的谓语 | continue为条件从句谓语；局部正确，原句数值问题隔离。 |

## 6. 120道剑桥auto抽样逐题结果

抽样算法：只保留source_kind=reading_test、passage_id以ielts开头、status=auto_pass；按T1–T6顺序，各模板先按item_id排序；同一个 `random.Random(20261106)` 连续sample20，不在各模板重置。不是从交付360行中抽；没有混入needs。

全部120题已读原句、teacher_row显示、高亮、答案和T1干扰项。下表“局部成立”不等于整个库已人工认证。T2第35题标注目标成立，但题干不唯一；其他119题未发现妨碍本题作答的新问题。原句均可阅读，T1/T6准情态和介词搭配按当前项目“谓语中心/aux+neg+prt单位”口径，不擅自扩大答案范围。第72题原句逗号略别扭，但完整让步目标和答案不受影响，未据此再立原文修改项。

按状态计：120auto、0needs；局部答案/高亮120可成立；唯一题干119未见问题、1既有多解提醒。以下T2“唯一”判断是本次人工阅读所见，不替代对全库多解的系统验收。

### T1：20道，全部auto_pass

| # | 题号 | 来源 | 答案 / 高亮 | 局部、题干与干扰项 | 整句/教学 |
| --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_abbd4a2a0944 | ielts18_test2_p3 D-03 | inspired | inspired为主谓；to rethink不是主句谓语。；干扰项：to rethink | 原句可阅读；本题可成立 |
| 2 | gi_v02_0c84c3b73f22 | ielts12_test6_p3 C-03 | creates | creates为主谓；accesses在宾语内容中，given修饰time，均非主谓。；干扰项：accesses; given | 原句可阅读；本题可成立 |
| 3 | gi_v02_160cdb2e1fcb | ielts18_test3_p1 C-03 | make | make为主谓，to beat是补足结构。；干扰项：无 | 原句可阅读；本题可成立 |
| 4 | gi_v02_223e64e96ae1 | ielts12_test7_p1 D-02 | ca / n't / be / reintroduced | 完整被动否定can’t be reintroduced；其他动词在从句/修饰语中。；干扰项：'re; weigh; hardened; are; to protect | 原句可阅读；本题可成立 |
| 5 | gi_v02_3daea3e6cb34 | ielts12_test5_p1 F-02 | is / caused | is caused完整被动；called修饰compound，forms为定语从句谓语。；干扰项：called; forms | 原句可阅读；本题可成立 |
| 6 | gi_v02_0203313e96e0 | ielts6_test2_p3 F-03 | seems | seems为主句系动词；is/show在that/while结构中。；干扰项：is; show | 原句可阅读；本题可成立 |
| 7 | gi_v02_a2abedd68f69 | ielts13_test2_p1 B-08 | could / set | could set为主句；两个because从句不改变主谓定位。；干扰项：无 | 原句可阅读；本题可成立 |
| 8 | gi_v02_e33d343d1691 | ielts18_test1_p1 E-02 | is / booming | is booming为主句谓语，范围完整。；干扰项：无 | 原句可阅读；本题可成立 |
| 9 | gi_v02_54a46cc11311 | ielts13_test4_p2 G-05 | is | is为系动词；can help等在定语从句中。；干扰项：can help; shape; encourage | 原句可阅读；本题可成立 |
| 10 | gi_v02_6916c5adeddf | ielts4_test3_p3 F-30 | can / be / elicited | can be elicited完整被动；to say非谓语。；干扰项：to say | 原句可阅读；本题可成立 |
| 11 | gi_v02_4915a7196646 | ielts20_test3_p3 H-01 | was | was为系动词中心；have/seen为that宾语从句谓语。；干扰项：have / seen | 原句可阅读；本题可成立 |
| 12 | gi_v02_ec2922c34c33 | ielts10_test4_p1 F-03 | becomes | becomes为主句系动词；整句引语无外置报告句竞争。；干扰项：无 | 原句可阅读；本题可成立 |
| 13 | gi_v02_b17335c9b5a6 | ielts18_test2_p3 B-03 | were / called | were called为被动谓语中心；for是后接介词，按项目单位定义不强并。；干扰项：to revolutionise; lived | 原句可阅读；本题可成立 |
| 14 | gi_v02_02cbdac52e77 | ielts10_test4_p2 G-01 | began | began为主谓，人名同位成分不混入。；干扰项：无 | 原句可阅读；本题可成立 |
| 15 | gi_v02_0661ca60f452 | ielts20_test4_p3 F-35 | can / influence | can influence为主谓；by creating是状语。；干扰项：无 | 原句可阅读；本题可成立 |
| 16 | gi_v02_f24303974e8a | ielts7_test1_p3 B-08 | seem | seem为主句系动词中心；to have gone为其补足结构。；干扰项：无 | 原句可阅读；本题可成立 |
| 17 | gi_v02_1ca5c8521df6 | ielts18_test2_p3 H-03 | is | is为主谓，前插入PP很长但不影响定位；can be found在定语从句中。；干扰项：can be found | 原句可阅读；本题可成立 |
| 18 | gi_v02_38713c743e2f | ielts17_test4_p1 D-02 | include | include为主谓，枚举物种不另生分句。；干扰项：无 | 原句可阅读；本题可成立 |
| 19 | gi_v02_4774fcc3d4d1 | ielts15_test2_p2 E-01 | is | is为主句系动词。；干扰项：无 | 原句可阅读；本题可成立 |
| 20 | gi_v02_fedeb2a60c70 | ielts10_test4_p1 H-01 | have / been / fulfilled | have been fulfilled完整被动；to provide/to fight为非谓语。；干扰项：to provide; to fight | 原句可阅读；本题可成立 |

### T2：20道，全部auto_pass

| # | 题号 | 来源 | 答案 / 高亮 | 局部、题干与干扰项 | 整句/教学 |
| --- | --- | --- | --- | --- | --- |
| 21 | gi_v02_2ede77740a7a | ielts4_test4_p1 H-36 | that lies behind many improvements in athletic performance | that lies...修饰element，冒号后同位解释不划入。；无干扰项 | 原句可阅读；本题可成立 |
| 22 | gi_v02_38ec62f90e74 | ielts11_test3_p2 C-03 | that aren't available within a single area year-round | that aren’t...修饰resources，包含year-round。；无干扰项 | 原句可阅读；本题可成立 |
| 23 | gi_v02_65a115d8fce1 | ielts5_test4_p2 J-45 | that took around six months to complete | that took...修饰process；句末引语边界不属于从句核心。；无干扰项 | 原句可阅读；本题可成立 |
| 24 | gi_v02_bdef00cf560b | ielts19_test4_p1 E-02 | you see flying in the spring | you see...省略关系词，修饰butterflies；边界完整。；无干扰项 | 原句可阅读；本题可成立 |
| 25 | gi_v02_2ce69e16566d | ielts13_test2_p2 E-03 | Where once researchers took no notice of such findings | Where once...为对照状语从句，目标前提成立。；无干扰项 | 原句可阅读；本题可成立 |
| 26 | gi_v02_6ec46b249252 | ielts9_test2_p1 D-01 | While the detrimental effects of noise in classroom situations are not limited to children experiencing disability | While...为让步/对照，完整目标含experiencing disability。；无干扰项 | 原句可阅读；本题可成立 |
| 27 | gi_v02_e130ff3c5bda | ielts17_test3_p3 G-04 | until they reach bedrock | until they reach bedrock为时间从句，未混入which大从句。；无干扰项 | 原句可阅读；本题可成立 |
| 28 | gi_v02_00afa6a44fac | ielts6_test1_p3 E-29 | for whom these have never before been problems | for whom...介词+关系词引导定语从句。；无干扰项 | 原句可阅读；本题可成立 |
| 29 | gi_v02_5133622ecf00 | ielts10_test2_p2 A-03 | when children's IQ scores were compared with their home educational provision | when...有主谓被动，文献括注在目标之外合理。；无干扰项 | 原句可阅读；本题可成立 |
| 30 | gi_v02_ec8b305d65a0 | ielts5_test1_p3 L-43 | that we look at the facts | that we look at the facts为外置主语内容，if条件可修饰矩阵要求。；无干扰项 | 原句可阅读；本题可成立 |
| 31 | gi_v02_ffe99bd5a175 | ielts20_test3_p2 B-02 | while their photosynthesising of the sun’s rays provides nutrients for the polyps | while...为对照状语从句，边界完整。；无干扰项 | 原句可阅读；本题可成立 |
| 32 | gi_v02_e60828a6cc4c | ielts12_test6_p3 B-03 | what that word might be | what that word might be为guess宾语内容从句。；无干扰项 | 原句可阅读；本题可成立 |
| 33 | gi_v02_a54291f1668a | ielts12_test5_p3 F-03 | that the end is good in an ethical sense | that the end is good...为被动结构的内容从句。；无干扰项 | 原句可阅读；本题可成立 |
| 34 | gi_v02_01cd88eb0b2e | ielts15_test1_p3 A-03 | Long before the first caveman slumped down beside the fire and grunted news that there were plenty of wildebeest over yonder | Long before...完整时间从句，包含并列谓语及news的内容从句。；无干扰项 | 原句可阅读；本题可成立 |
| 35 | gi_v02_18543efdcecd | ielts15_test3_p3 G-02 | that may be faced there | 所选that may be faced there正确；另有that’s relevant to survival，题干不唯一（既有提醒）。；无干扰项 | 原句可；题目不宜唯一判分 |
| 36 | gi_v02_bbe7f177498c | ielts18_test1_p3 D-04 | If you knew precisely where everything was | If...含where宾语从句，外层条件范围完整。；无干扰项 | 原句可阅读；本题可成立 |
| 37 | gi_v02_a472449e98bd | ielts16_test2_p1 A-04 | that are much older | that are much older修饰one or two。；无干扰项 | 原句可阅读；本题可成立 |
| 38 | gi_v02_f210dc0b7f6e | ielts5_test2_p1 D-14 | that could be manufactured on an industrial scale | that could be manufactured...修饰material。；无干扰项 | 原句可阅读；本题可成立 |
| 39 | gi_v02_9db7dffeab44 | ielts14_test4_p3 L-02 | that look or sound most dramatic | that look or sound...为定语从句，内部并列谓语完整。；无干扰项 | 原句可阅读；本题可成立 |
| 40 | gi_v02_a8c443a6db74 | ielts18_test2_p3 C-01 | that killed half the population in Milan, Italy | that killed...修饰pestilence，包含地点同位Italy。；无干扰项 | 原句可阅读；本题可成立 |

### T3：20道，全部auto_pass

| # | 题号 | 来源 | 答案 / 高亮 | 局部、题干与干扰项 | 整句/教学 |
| --- | --- | --- | --- | --- | --- |
| 41 | gi_v02_75ff9255643f | ielts15_test3_p1 G-03 | At times → 不是从句（短语或非谓语） | At times为介词短语。；无干扰项 | 原句可阅读；本题可成立 |
| 42 | gi_v02_65e0f9a8380a | ielts18_test1_p3 F-04 | to designate its orbit → 不是从句（短语或非谓语） | to designate its orbit为目的不定式。；无干扰项 | 原句可阅读；本题可成立 |
| 43 | gi_v02_24f865966fe3 | ielts11_test3_p3 F-02 | who simply want to sharpen their analytical skills → 定语从句 | who...修饰readers，是定语从句。；无干扰项 | 原句可阅读；本题可成立 |
| 44 | gi_v02_b874e77778e0 | ielts18_test4_p3 E-03 | interested in a particular aspect of Wegener's life but perhaps not all of it → 不是从句（短语或非谓语） | interested...为形容词/分词修饰语，按项目非谓语类。；无干扰项 | 原句可阅读；本题可成立 |
| 45 | gi_v02_d2d45f1f8b9e | ielts14_test1_p3 L-01 | that can be adopted at the organizational level → 定语从句 | that can be adopted...修饰actions。；无干扰项 | 原句可阅读；本题可成立 |
| 46 | gi_v02_d9c8d571b7cb | ielts9_test4_p3 B-01 | it should be presented → 定语从句 | it should be presented为修饰way的省略关系词从句。；无干扰项 | 原句可阅读；本题可成立 |
| 47 | gi_v02_284f6a930c0b | ielts18_test4_p1 D-04 | that installing green roofs is worthwhile → 名词性从句 | that installing green roofs is worthwhile为convince的内容宾语。；无干扰项 | 原句可阅读；本题可成立 |
| 48 | gi_v02_51bf8388e1f0 | ielts11_test2_p3 H-06 | While the fashions of the time might shape what is currently popular → 状语从句 | While...含what宾语内容，外层让步/对照从句。；无干扰项 | 原句可阅读；本题可成立 |
| 49 | gi_v02_d13e7288023c | ielts16_test1_p1 A-04 | to suffer from diabetes and heart disease → 不是从句（短语或非谓语） | to suffer...不定式补足语。；无干扰项 | 原句可阅读；本题可成立 |
| 50 | gi_v02_2e50b420987a | ielts20_test1_p2 C-03 | for beetles to lay eggs → 不是从句（短语或非谓语） | for beetles to lay eggs有逻辑主语，仍为不定式；按项目非谓语分组。；无干扰项 | 原句可阅读；本题可成立 |
| 51 | gi_v02_8ecaa6a58f09 | ielts10_test2_p3 H-02 | by the sheer volume of exhibits → 不是从句（短语或非谓语） | by the sheer volume of exhibits为介词短语。；无干扰项 | 原句可阅读；本题可成立 |
| 52 | gi_v02_59144def3837 | ielts17_test1_p1 B-03 | who lived in the inner-city slums → 定语从句 | who lived...修饰workers。；无干扰项 | 原句可阅读；本题可成立 |
| 53 | gi_v02_c7426a6e3727 | ielts13_test3_p1 B-06 | after the green part of the leaf has been stripped away → 状语从句 | after the green part...为带主谓的时间从句。；无干扰项 | 原句可阅读；本题可成立 |
| 54 | gi_v02_dbe351025120 | ielts16_test4_p1 B-05 | to measure the depth of the shaft → 不是从句（短语或非谓语） | to measure...为不定式目的结构。；无干扰项 | 原句可阅读；本题可成立 |
| 55 | gi_v02_69c267ce0f3c | ielts5_test4_p1 C-32 | that does not depend on outside visitors → 定语从句 | that does not depend...修饰source/income所指对象，类别无疑。；无干扰项 | 原句可阅读；本题可成立 |
| 56 | gi_v02_e4d798357af0 | ielts18_test2_p1 B-02 | to dig a massive circular ditch and bank, or henge → 不是从句（短语或非谓语） | to dig...含bank同位henge，为不定式结构。；无干扰项 | 原句可阅读；本题可成立 |
| 57 | gi_v02_75ced2baa9db | ielts10_test1_p3 F-02 | at solving problems → 不是从句（短语或非谓语） | at solving problems为介词加动名词。；无干扰项 | 原句可阅读；本题可成立 |
| 58 | gi_v02_a0f78cf4acd8 | ielts20_test1_p1 E-05 | With them → 不是从句（短语或非谓语） | With them为前置介词短语，后面倒装不改变本目标。；无干扰项 | 原句可阅读；本题可成立 |
| 59 | gi_v02_1e6532e5d6a6 | ielts11_test2_p1 E-05 | that it might be possible to raise the hull → 名词性从句 | that it might be possible...为shown的内容从句。；无干扰项 | 原句可阅读；本题可成立 |
| 60 | gi_v02_6af54124d237 | ielts17_test4_p3 A-04 | for human performance → 不是从句（短语或非谓语） | for human performance为介词短语。；无干扰项 | 原句可阅读；本题可成立 |

### T4：20道，全部auto_pass

| # | 题号 | 来源 | 答案 / 高亮 | 局部、题干与干扰项 | 整句/教学 |
| --- | --- | --- | --- | --- | --- |
| 61 | gi_v02_0de68effbee9 | ielts5_test4_p1 B-15 | because there is insufficient labour to maintain terraces and irrigation systems and tend to crops → 原因 | because...给出劳动力不足的原因，边界完整。；无干扰项 | 原句可阅读；本题可成立 |
| 62 | gi_v02_a3bfb5b8f50c | ielts5_test4_p3 B-09 | when the day is less than a certain critical length → 时间 | when...说明开花时机，时间关系成立。；无干扰项 | 原句可阅读；本题可成立 |
| 63 | gi_v02_f2b37431a238 | ielts17_test2_p2 D-03 | because the plant has a sprawling growth habit and the small fruits fall off the branches when ripe → 原因 | because...含并列原因及when ripe，范围完整。；无干扰项 | 原句可阅读；本题可成立 |
| 64 | gi_v02_c2107f7e0b5a | ielts4_test2_p1 D-21 | When the next generation reaches their teens → 时间 | When...为时间从句，引号不属于从句词汇范围。；无干扰项 | 原句可阅读；本题可成立 |
| 65 | gi_v02_d9e6758b2bd3 | ielts5_test4_p3 G-39 | because they have a low photosynthetic rate → 原因 | because...解释低光生存，原因成立。；无干扰项 | 原句可阅读；本题可成立 |
| 66 | gi_v02_159b6d3612b5 | ielts5_test3_p3 D-27 | If it works → 条件 | If it works为条件，外部as评述不影响。；无干扰项 | 原句可阅读；本题可成立 |
| 67 | gi_v02_e5a85a7c964c | ielts8_test4_p3 E-05 | although larger sizes are generally better → 让步 | although...为括号内让步从句。；无干扰项 | 原句可阅读；本题可成立 |
| 68 | gi_v02_28b9c5156164 | ielts16_test1_p2 D-06 | If someone wished to enter → 条件 | If someone wished...为假设条件。；无干扰项 | 原句可阅读；本题可成立 |
| 69 | gi_v02_3e48a1404dd0 | ielts9_test4_p1 B-02 | Because her father lost his savings through bad investment → 原因 | Because...交代因果，完整。；无干扰项 | 原句可阅读；本题可成立 |
| 70 | gi_v02_8011157bad1a | ielts8_test3_p1 H-05 | if all goes well → 条件 | if all goes well为条件。；无干扰项 | 原句可阅读；本题可成立 |
| 71 | gi_v02_db89688be8b2 | ielts4_test2_p1 C-16 | If it is spoken by children → 条件 | If it is spoken by children为条件，be被动完整。；无干扰项 | 原句可阅读；本题可成立 |
| 72 | gi_v02_9e1b96af1770 | ielts6_test4_p3 E-10 | although other sanctions may be needed for those who continue with persistent bullying → 让步 | although...为让步，包含who定语从句；主句逗号不改变目标答案。；无干扰项 | 原句可阅读；本题可成立 |
| 73 | gi_v02_23908fd7c6e7 | ielts13_test4_p2 C-01 | If the soil loses its ability to perform these functions → 条件 | If the soil loses...为条件。；无干扰项 | 原句可阅读；本题可成立 |
| 74 | gi_v02_b0a6d97c8615 | ielts8_test1_p1 D-05 | Although these devices performed satisfactorily around the Mediterranean → 让步 | Although...为让步，后句表示限制。；无干扰项 | 原句可阅读；本题可成立 |
| 75 | gi_v02_62777bccae1b | ielts8_test2_p3 D-02 | because the specific vocabulary simply doesn't exist → 原因 | because...为原因，simply及否定完整。；无干扰项 | 原句可阅读；本题可成立 |
| 76 | gi_v02_4eee4d9b70a9 | ielts20_test2_p2 C-18 | If we engage in more enjoyable tasks instead → 条件 | If we engage...为条件。；无干扰项 | 原句可阅读；本题可成立 |
| 77 | gi_v02_bf18d8697612 | ielts20_test4_p3 E-26 | If we are not working with everybody → 条件 | If we are not working...为条件，后句并列不混入。；无干扰项 | 原句可阅读；本题可成立 |
| 78 | gi_v02_079246b7c2a3 | ielts8_test1_p1 E-01 | although it could be adjusted to maintain temporal hours → 让步 | although...位于that内容从句中，仍是让步从句。；无干扰项 | 原句可阅读；本题可成立 |
| 79 | gi_v02_8e553e9d5a7b | ielts8_test4_p3 B-08 | if the ants are known not to sting → 条件 | if the ants are known not to sting为条件。；无干扰项 | 原句可阅读；本题可成立 |
| 80 | gi_v02_1027fe884e1c | ielts7_test4_p2 C-06 | if Alaska was an independent nation → 条件 | if Alaska was...为假设条件；非正式were/was选择不改变答案。；无干扰项 | 原句可阅读；本题可成立 |

### T5：20道，全部auto_pass

| # | 题号 | 来源 | 答案 / 高亮 | 局部、题干与干扰项 | 整句/教学 |
| --- | --- | --- | --- | --- | --- |
| 81 | gi_v02_17882a432a9a | ielts11_test2_p2 B-08 | Soil erosion | Soil erosion完整主语。；无干扰项 | 原句可阅读；本题可成立 |
| 82 | gi_v02_6ce59976b66d | ielts16_test3_p2 G-02 | Trade networks connecting Scandinavia with Europe and the Middle East | Trade networks含connecting...后置修饰，范围完整。；无干扰项 | 原句可阅读；本题可成立 |
| 83 | gi_v02_82cbd2be8266 | ielts20_test3_p1 I-03 | refrigerator technology | refrigerator technology为主语，by the 1950s不属主语。；无干扰项 | 原句可阅读；本题可成立 |
| 84 | gi_v02_adcec73212c2 | ielts7_test2_p3 C-10 | The use of bicycles | The use of bicycles含of修饰，完整。；无干扰项 | 原句可阅读；本题可成立 |
| 85 | gi_v02_075cca69cf9a | ielts11_test1_p2 F-02 | Two hydraulic steel gates | Two hydraulic steel gates完整名词主语。；无干扰项 | 原句可阅读；本题可成立 |
| 86 | gi_v02_3c95bb32565b | ielts19_test2_p1 C-03 | steam-powered boats and ships | steam-powered boats and ships完整并列主语。；无干扰项 | 原句可阅读；本题可成立 |
| 87 | gi_v02_12a7ba3fe538 | ielts13_test1_p1 E-03 | Overall tourism expenditure | Overall tourism expenditure完整主语。；无干扰项 | 原句可阅读；本题可成立 |
| 88 | gi_v02_ae35c38634a7 | ielts11_test3_p3 F-02 | This book | This book为主语；who修饰宾语readers。；无干扰项 | 原句可阅读；本题可成立 |
| 89 | gi_v02_87c5689481ef | ielts13_test4_p3 A-04 | This pronouncement by Richard Layard, an economist and advocate of 'positive psychology' | This pronouncement含by Richard Layard及其同位语，完整；闭合逗号不计词。；无干扰项 | 原句可阅读；本题可成立 |
| 90 | gi_v02_3b29139d45d0 | ielts13_test2_p3 D-01 | A further example of this strategy | A further example of this strategy为完整主语。；无干扰项 | 原句可阅读；本题可成立 |
| 91 | gi_v02_5a9bc840a5ca | ielts5_test2_p1 F-24 | The design of Bakelite objects, everything from earrings to television sets | The design of Bakelite objects含补充说明everything...，完整。；无干扰项 | 原句可阅读；本题可成立 |
| 92 | gi_v02_03d8b9794577 | ielts16_test4_p1 D-04 | Tunnels | Tunnels为完整主语。；无干扰项 | 原句可阅读；本题可成立 |
| 93 | gi_v02_8920bc151436 | ielts19_test2_p3 H-07 | Children | Children为完整主语。；无干扰项 | 原句可阅读；本题可成立 |
| 94 | gi_v02_9151d8c8df14 | ielts5_test1_p2 G-01 | An alternative to this notion of genetic programming | An alternative to this notion of genetic programming完整。；无干扰项 | 原句可阅读；本题可成立 |
| 95 | gi_v02_ebedde9856b3 | ielts6_test4_p3 C-02 | schools | schools为主语，Perhaps as a consequence是状语。；无干扰项 | 原句可阅读；本题可成立 |
| 96 | gi_v02_51fbaf42499b | ielts6_test4_p2 C-05 | the government of Nicaragua | the government of Nicaragua含of修饰。；无干扰项 | 原句可阅读；本题可成立 |
| 97 | gi_v02_d376b15a5bdc | ielts16_test4_p3 E-01 | we | we为主语，Fortunately不属主语。；无干扰项 | 原句可阅读；本题可成立 |
| 98 | gi_v02_64293b732d58 | ielts16_test3_p1 F-03 | Goods from all over the world | Goods from all over the world含后置修饰。；无干扰项 | 原句可阅读；本题可成立 |
| 99 | gi_v02_a6c6c8a3df25 | ielts19_test3_p3 D-03 | The efficiency of the translator | The efficiency of the translator完整。；无干扰项 | 原句可阅读；本题可成立 |
| 100 | gi_v02_67d177336ba7 | ielts16_test2_p1 E-02 | It | It为主语，后面which修饰Lambourn Seven Barrows。；无干扰项 | 原句可阅读；本题可成立 |

### T6：20道，全部auto_pass

| # | 题号 | 来源 | 答案 / 高亮 | 局部、题干与干扰项 | 整句/教学 |
| --- | --- | --- | --- | --- | --- |
| 101 | gi_v02_a822f13efc53 | ielts7_test1_p1 B-04 | have → 主句谓语 | have为主句谓语。；无干扰项 | 原句可阅读；本题可成立 |
| 102 | gi_v02_8d6dd7121cd6 | ielts7_test1_p3 F-25 | are stimulated → 从句里的谓语 | are stimulated为at which定语从句谓语。；无干扰项 | 原句可阅读；本题可成立 |
| 103 | gi_v02_0c58cd3c231f | ielts10_test4_p3 C-01 | called → 非谓语（不定式、分词、动名词） | called修饰palaeontologist，为过去分词非谓语。；无干扰项 | 原句可阅读；本题可成立 |
| 104 | gi_v02_c4a2c77c814f | ielts9_test1_p3 A-03 | have succeeded → 从句里的谓语 | have succeeded为that定语从句谓语。；无干扰项 | 原句可阅读；本题可成立 |
| 105 | gi_v02_d6819f87d8ee | ielts15_test1_p1 E-01 | were ruled → 主句谓语 | were ruled完整被动主谓。；无干扰项 | 原句可阅读；本题可成立 |
| 106 | gi_v02_5f92813b6398 | ielts20_test4_p3 A-03 | have been made → 从句里的谓语 | have been made为as从句完整被动谓语。；无干扰项 | 原句可阅读；本题可成立 |
| 107 | gi_v02_2fb02c9debd8 | ielts9_test3_p3 D-20 | interfere → 从句里的谓语 | interfere为which定语从句谓语。；无干扰项 | 原句可阅读；本题可成立 |
| 108 | gi_v02_f3725bc99e41 | ielts10_test2_p1 B-03 | allows → 从句里的谓语 | allows为that定语从句谓语。；无干扰项 | 原句可阅读；本题可成立 |
| 109 | gi_v02_7e5f699736b4 | ielts8_test3_p1 I-03b | could discharge → 从句里的谓语 | could discharge为if从句谓语。；无干扰项 | 原句可阅读；本题可成立 |
| 110 | gi_v02_8d5a88a480aa | ielts20_test2_p3 I-53 | take → 主句谓语 | take为主句谓语，I have met修饰players。；无干扰项 | 原句可阅读；本题可成立 |
| 111 | gi_v02_e5c0b95b41c3 | ielts12_test5_p2 G-01 | was → 主句谓语 | was为主句系动词。；无干扰项 | 原句可阅读；本题可成立 |
| 112 | gi_v02_ae7d86d61454 | ielts8_test2_p1 F-04 | delivers → 从句里的谓语 | delivers为that定语从句谓语。；无干扰项 | 原句可阅读；本题可成立 |
| 113 | gi_v02_e3d6728e6d01 | ielts12_test5_p3 C-03 | could have approached → 从句里的谓语 | could have approached为省略关系词定语从句谓语。；无干扰项 | 原句可阅读；本题可成立 |
| 114 | gi_v02_b042835567e5 | ielts19_test2_p2 B-05 | include → 主句谓语 | include为主句谓语。；无干扰项 | 原句可阅读；本题可成立 |
| 115 | gi_v02_0e7b97694b51 | ielts6_test3_p1 G-04 | watch → 从句里的谓语 | watch为because从句谓语。；无干扰项 | 原句可阅读；本题可成立 |
| 116 | gi_v02_ff26c4a07a8e | ielts19_test4_p1 D-03 | estimated → 主句谓语 | estimated为主句谓语。；无干扰项 | 原句可阅读；本题可成立 |
| 117 | gi_v02_d90cca3d1ddc | ielts7_test1_p1 C-06 | have → 从句里的谓语 | have为since从句谓语中心；have to的准情态整体口径属既有边界。；无干扰项 | 原句可阅读；本题可成立 |
| 118 | gi_v02_bc607a9bb4fc | ielts6_test2_p2 K-36 | found → 主句谓语 | found为主句谓语。；无干扰项 | 原句可阅读；本题可成立 |
| 119 | gi_v02_fc9bdd1fd221 | ielts4_test1_p3 B-05 | To show → 非谓语（不定式、分词、动名词） | To show为目的不定式。；无干扰项 | 原句可阅读；本题可成立 |
| 120 | gi_v02_b5417589b233 | ielts10_test1_p2 B-02 | have been abolished → 从句里的谓语 | have been abolished为as从句被动谓语。；无干扰项 | 原句可阅读；本题可成立 |

## 7. 新角度全池定向扫描

此次改从**抽象名词后的that内容从句与定语从句的区别**入手，区别于此前动词单位、并列/系表、主语、外层PP、数值排印等扫描。遍历全部27,824道剑桥auto，检查T2/T3目标。

- 通道一：目标以that/whether起始且解析中心挂名词，共986题；用fact、idea、belief、claim、evidence、assumption、news、theory、knowledge、fear等内容名词词表筛出23题。对这些逐题判断关系词是否填补从句中的主语/宾语位置，而非“名词后面就算定语从句”。
- 通道二：独立于解析挂靠，直接看目标前最近英文词是否为同一内容名词词表；命中28题。该通道也会抓到动词doubt/claim，人工作为反例剔除。
- 两路并集32题、17个不同目标，全部人工核对如下。未发现新的类别误判；并不声称人工读完了986题或全部auto。完整词表、探针和JSON留在O/scan_nominal_complements.py等文件，方法可重做。
- 表中“类别正确”仅判断本次扫描的问题；T2若句内另有同类从句，仍服从已有多目标限制。例如15_2_p1 A-05外层及内部we have now都可构成定语从句，本次不把它重报为新类别错误。

| 题号 | 来源 | 模板 | 目标 / 答案 | 独立判断 |
| --- | --- | --- | --- | --- |
| gi_v02_554e7bc340ea | ielts10_test4_p3 A-02 | T2 | that says 'evolution cannot run backwards' / that says 'evolution cannot run backwards' | 类别正确；that在says中作主语，回指principle；内部直接引语不把外层变内容从句。 |
| gi_v02_9b66be233913 | ielts10_test4_p3 A-02 | T3 | that says 'evolution cannot run backwards' / 定语从句 | 类别正确；that在says中作主语，回指principle；内部直接引语不把外层变内容从句。 |
| gi_v02_9bbffc20be59 | ielts12_test8_p3 D-04 | T3 | that part-time non-executive directors lacked / 定语从句 | 类别正确；that为lacked的宾语，回指information；不是无空位的内容从句。 |
| gi_v02_f3f07fae9f01 | ielts14_test3_p1 J-01 | T2 | that are then taken as scientific contributions / that are then taken as scientific contributions | 类别正确；that作are taken的主语；修饰theories/designs并列名词。 |
| gi_v02_06332ade3281 | ielts14_test3_p1 J-01 | T3 | that are then taken as scientific contributions / 定语从句 | 类别正确；that作are taken的主语；修饰theories/designs并列名词。 |
| gi_v02_834fd13d204e | ielts15_test2_p1 A-05 | T2 | that led to the creation of the energy-consuming transport systems we have now / that led to the creation of the energy-consuming transport systems we have now | 类别正确；that作led的主语，回指assumptions；不是陈述assumptions的内容。T2另有嵌套目标提醒。 |
| gi_v02_64950a9e5de4 | ielts15_test2_p1 A-05 | T3 | that led to the creation of the energy-consuming transport systems we have now / 定语从句 | 类别正确；that作led的主语，回指assumptions；不是陈述assumptions的内容。T2另有嵌套目标提醒。 |
| gi_v02_9f5e92bdb579 | ielts17_test3_p3 H-02 | T2 | that may serve as a distraction to readers primarily interested in New York / that may serve as a distraction to readers primarily interested in New York | 类别正确；that为may serve主语；无论回指discussions还是theory，定语类别不变。 |
| gi_v02_f27d473b91a7 | ielts17_test3_p3 H-02 | T3 | that may serve as a distraction to readers primarily interested in New York / 定语从句 | 类别正确；that为may serve主语；无论回指discussions还是theory，定语类别不变。 |
| gi_v02_1d3bd7ce5bea | ielts18_test2_p3 H-03 | T2 | that can be found in Georges-Eugène Haussmann's renovation of Paris under Emperor Napoleon III between 1853 and 1870 / that can be found in Georges-Eugène Haussmann's renovation of Paris under Emperor Napoleon III between 1853 and 1870 | 类别正确；that作can be found的主语，回指idea。 |
| gi_v02_5f73c84c1abd | ielts18_test2_p3 H-03 | T3 | that can be found in Georges-Eugène Haussmann's renovation of Paris under Emperor Napoleon III between 1853 and 1870 / 定语从句 | 类别正确；that作can be found的主语，回指idea。 |
| gi_v02_34d3a47cf06e | ielts18_test3_p3 J-03 | T3 | that you yourself have just mastered / 定语从句 | 类别正确；that为have mastered宾语，回指skills and knowledge。 |
| gi_v02_7a10c2c931ca | ielts18_test4_p3 B-03 | T2 | that guides Earth sciences today / that guides Earth sciences today | 类别正确；目标that guides以that作主语，修饰theory；另一个that the continents move才是idea的内容。 |
| gi_v02_7cebfd18659b | ielts18_test4_p3 B-03 | T3 | that guides Earth sciences today / 定语从句 | 类别正确；目标that guides以that作主语，修饰theory；另一个that the continents move才是idea的内容。 |
| gi_v02_12f7f4a1c3fa | ielts19_test1_p3 E-02 | T2 | that is false / that is false | 类别正确；that作is false主语，回指information。 |
| gi_v02_37614b7ac702 | ielts19_test1_p3 E-02 | T3 | that is false / 定语从句 | 类别正确；that作is false主语，回指information。 |
| gi_v02_f95289f35e55 | ielts19_test3_p3 I-06 | T2 | that comes with knowledge of a language / that comes with knowledge of a language | 类别正确；that作comes主语，修饰understanding。 |
| gi_v02_ffda5230c8aa | ielts19_test3_p3 I-06 | T3 | that comes with knowledge of a language / 定语从句 | 类别正确；that作comes主语，修饰understanding。 |
| gi_v02_106a4e6c02e5 | ielts20_test1_p3 K-01 | T2 | that is not always justified / that is not always justified | 类别正确；所标that is not always justified的that作主语，修饰fear；前方fact/likelihood内容从句不同。 |
| gi_v02_bd1ab24389c5 | ielts20_test1_p3 K-01 | T3 | that is not always justified / 定语从句 | 类别正确；所标that is not always justified的that作主语，修饰fear；前方fact/likelihood内容从句不同。 |
| gi_v02_083a89184959 | ielts4_test1_p1 K-01 | T2 | that suggested that they appreciated the complexity of causes of rainforest destruction / that suggested that they appreciated the complexity of causes of rainforest destruction | 类别正确；外that作suggested主语，回指ideas；内部that they appreciated为内容宾语。 |
| gi_v02_0d96e49bf784 | ielts4_test1_p1 K-01 | T3 | that suggested that they appreciated the complexity of causes of rainforest destruction / 定语从句 | 类别正确；外that作suggested主语，回指ideas；内部that they appreciated为内容宾语。 |
| gi_v02_decedee9a371 | ielts4_test2_p1 A-05 | T2 | that any native speakers of Navajo will remain in a hundred years' time / that any native speakers of Navajo will remain in a hundred years' time | 类别正确；doubt在此为动词，不是抽象名词；that后成分完整，是宾语内容从句。 |
| gi_v02_fc1e6dc6cdaf | ielts4_test2_p1 A-05 | T3 | that any native speakers of Navajo will remain in a hundred years' time / 名词性从句 | 类别正确；doubt在此为动词，不是抽象名词；that后成分完整，是宾语内容从句。 |
| gi_v02_0d13cbb08fa7 | ielts5_test3_p3 E-34 | T2 | that their system, based on a cluster of 30 processors, could be used to spot camouflaged vehicles on a battlefield or extract a voice signal from a noisy background / that their system, based on a cluster of 30 processors, could be used to spot camouflaged vehicles on a battlefield or extract a voice signal from a noisy background | 类别正确；claim在此为动词；that后主谓完整，是内容宾语。 |
| gi_v02_1b428973cb03 | ielts5_test3_p3 E-34 | T3 | that their system, based on a cluster of 30 processors, could be used to spot camouflaged vehicles on a battlefield or extract a voice signal from a noisy background / 名词性从句 | 类别正确；claim在此为动词；that后主谓完整，是内容宾语。 |
| gi_v02_dc588a50e9b9 | ielts7_test2_p1 G-31 | T2 | that were, more than a thousand years later, applied in the construction of Japan's first skyscraper / that were, more than a thousand years later, applied in the construction of Japan's first skyscraper | 类别正确；that作were applied主语，回指principles，插入语不变类别。 |
| gi_v02_b5fa3403ef00 | ielts7_test2_p1 G-31 | T3 | that were, more than a thousand years later, applied in the construction of Japan's first skyscraper / 定语从句 | 类别正确；that作were applied主语，回指principles，插入语不变类别。 |
| gi_v02_bf7fc0471f8b | ielts9_test3_p1 E-02 | T2 | that is concerned less with standards than with the facts of linguistic usage / that is concerned less with standards than with the facts of linguistic usage | 类别正确；that作is concerned主语，回指point of view。 |
| gi_v02_3dc8b6ca0d9c | ielts9_test3_p1 E-02 | T3 | that is concerned less with standards than with the facts of linguistic usage / 定语从句 | 类别正确；that作is concerned主语，回指point of view。 |
| gi_v02_364e1e18f75c | ielts9_test4_p2 D-01 | T2 | that children gain of themselves as active agents / that children gain of themselves as active agents | 类别正确；that为gain的宾语，回指understanding；children为自有主语，不构成无空位内容从句。 |
| gi_v02_c140d4758391 | ielts9_test4_p2 D-01 | T3 | that children gain of themselves as active agents / 定语从句 | 类别正确；that为gain的宾语，回指understanding；children为自有主语，不构成无空位内容从句。 |

## 8. 恢复10⁹的建议（未执行，待单独授权）

优先在正文保留原版 **10⁹**（Unicode上标9），难点补“10的9次方，即1,000,000,000，十亿”。这样与原版一致；不需要往纯文本字段塞HTML `<sup>`。若某个客户端/字体或导出格式确实不能稳定显示上标，备用纯文本用 `10^9`；`1,000,000,000`适合辅助解释，单独替代原版会失去原版记法。上线前需要在网页、小程序、复制/导出及朗读链路验证显示与读音，本轮未做这些发布操作。

同步位置清单：

1. `static/reading_tests/ielts11_test1_reading.json:43`，passages[0].content.paragraphs[0].text。逐字符串查本文件 `109/10⁹/10^9`，目前只有此正文命中，groups/题干/答案/定位句没有该数字的重复引用；仍须在修改后再全字段复查。
2. `data/reading_study/ielts11_test1_p1.json` A-03 sentence、structure[0].text、difficult_points[0]；中文译文“十亿公顷”已正确，不需要改错成109。四条难点的数量与学生讲解保留；只有正文/结构真恢复后才去掉source_quality前缀。
3. 构建来源：`build_reading_test_practice.py`的剑桥RAW_PATH默认指向 `data/idictation_reading/raw.json`，但任务树当前没有此文件。未来若从原始抓取重建，须在获得授权的可追溯修订层同步，避免109回流；不能只手改static，也不能本轮擅自把剑桥数据塞进仅机经修订表。此缺文件不妨碍本轮指定的机经171篇重建检查。
4. 重新生成依赖句子字符偏移的候选、解析缓存、报告、JSONL、XLSX及图谱复核文档；不要手改题号和答案偏移。10⁹改变文本哈希，须实际重解析及复核题号/状态变化，不能先承诺恰好6题恢复。
5. 部署授权后，用新代码重新导入该篇ReadingPassageAnalysis，使sentence/structure/难点同步到数据库；再核验网页和小程序阅读页、相应练习/复盘卡。不涉及现在操作生产。

本轮已复看官方原版，给出显示建议；没有恢复原文、没有去掉前缀、没有将任何A-03题改回auto。

## 9. 全池、双生成、表格和导入证据

### 9.1 全池差异

旧池dd9与新池297分别由同一Mac环境生成。旧基线代码/数据核实相同；按item_id比较完整对象（status/reasons另计）。

| 项目 | 独立实测 |
| --- | --- |
| 候选 | 50243→50241；E-02删3增1，其余题号不变 |
| 共同题号状态 | Cam6 auto→needs；Jij2 auto→needs；needs→auto 0 |
| 共同题号其他字段 | 全部0变化（含题干、答案、高亮、干扰项、解析证据、来源） |
| auto各模板 | 5821 / 4678 / 11401 / 395 / 5364 / 12639 |
| auto合计 | 40298；剑桥27824；机经12474 |
| prepositional_target最终 | Cam11、Jij3；只因该原因needs的Cam0、Jij2 |
| Cam source_quality | 全量17→29；只因此原因15→21 |
| E-02 T6拒绝 | 5条旧总拒绝→4条，少until外层的1条finite_or_not；其他4条全等 |

### 9.2 双跑环境、SHA-256

Mac27.0.1（arm64，build26A434），Python3.13.3、spaCy3.8.16、en_core_web_trf3.8.0、torch2.14.1、CPU、openpyxl3.1.5；seed20261018。模型本地运行，未调用大模型API。

在O/source完整快照，用指定G连续两次执行generate。沿用同版本、同句文本的全库缓存；这是重新生成全部候选/交付，**不是全库从零解析**。另外把规则命中、8控制及A-03来源共24种不同句子实际送本地spaCy，结果与缓存逐token字段相同。用户本轮未要求清空缓存。

两次4文件逐字节相同；JSONL/XLSX与提交版完全相同；两报告只出现Python3.13.3与Claude3.11.15的一行差异，其他行/结构不变。

| 文件 | Mac第1次SHA-256 | Mac第2次SHA-256 | 提交版SHA-256 |
| --- | --- | --- | --- |
| generation_report_v0_2.json | 90a78794bd52d901bd0330c718d62c55f837fba7282e851e92080be906f42d5f | 90a78794bd52d901bd0330c718d62c55f837fba7282e851e92080be906f42d5f | c4a2d04be11bd3e6e1dacea3011d32980cefc261ca9f22bf3454118073b9d028 |
| generation_report_v0_2.md | fc72118b2af53408fb81cd6f0ab7aa1bc8d4b608652d035bc66241b912e68781 | fc72118b2af53408fb81cd6f0ab7aa1bc8d4b608652d035bc66241b912e68781 | 9a0fd8a29803053e09dc5cbbff6c797ee0da230ef2cec39121299f0b9f1097c7 |
| review_batch_v0_2.jsonl | 782ecd3c5b34ed8ebb38e7288ce6994722ad9aa4b866fe34c39eb8c10bf604e4 | 782ecd3c5b34ed8ebb38e7288ce6994722ad9aa4b866fe34c39eb8c10bf604e4 | 782ecd3c5b34ed8ebb38e7288ce6994722ad9aa4b866fe34c39eb8c10bf604e4 |
| review_batch_v0_2.xlsx | 3a36f72b67d8516e9fe54eb43285ff68c99e4e4177982338537248eb8672e05d | 3a36f72b67d8516e9fe54eb43285ff68c99e4e4177982338537248eb8672e05d | 3a36f72b67d8516e9fe54eb43285ff68c99e4e4177982338537248eb8672e05d |

78项回归（13句×6模板）的完整记录与dd9相同，7项过滤记录也完整相同。逐项expected/actual：

| 过滤 | expected | actual |
| --- | --- | --- |
| tagged_fragment | 30 | 30 |
| clause_attached_to_conjunction | 2 | 2 |
| glued_sentence_boundary | 0 | 0 |
| multi_sentence_unit | 1 | 1 |
| suspected_split_word | 0 | 0 |
| leading_stray_punctuation | 0 | 0 |
| control_character | 0 | 0 |

### 9.3 XLSX与抽查表

检查ZIP/XML全部7表，并把6张题型表的360行与teacher_row生成的实际文本逐格比对：各60题（含标题61行），教师判定H2:H61的list为“正确,答案错,题目有歧义,句子不适合出题”。没有auto_pass/needs_review或机器降级原因出现在教师可见单元格中；未预填教师结论。说明表仍在。

剑桥232行=196auto+36needs，机经128行=104auto+24needs。与dd9交付比：按题号保留10个；按(工作表,行号)保留0个。老师旧判定不能按行号迁移，应按题号及内容比对。抽查表重抽不改变盲审原则，但要固定发给老师的版本。

### 9.4 临时SQLite与两篇已更新原因

两个独立数据库，均先导入完整676569c快照（自己的代码、models、static、data），创建317篇，再运行相应当前快照的导入器：

| 第二次导入快照 | created | updated | skipped | failed |
| --- | --- | --- | --- | --- |
| dd9代码/数据等价基线 | 0 | 236 | 81 | 0 |
| 29701e7 | 0 | 236 | 81 | 0 |

两次每篇的状态记录也相同。两篇在旧基线时已有normalize_payload差异：

- ielts14_test2_p3：B-04/B-05的interrogative_clause由兜底“状语从句”变“疑问句”；E-02/F-01的temporal_clause标签由“状语从句”变“时间状语从句”；H-02 clause变“分句”。因此旧基线已经updated。本轮E-02还新增role/难点变更，不再新增一篇updated。
- ielts11_test1_p1：B-08的elliptical_conditional_clause由兜底“状语从句”变“条件状语从句”，旧基线已updated；本轮A-03难点在同一篇内更新，总数不变。

新导入的E-02标签实测为“介词短语”。生产标签要等新代码部署后导入才生效；本轮全部连接仅O下SQLite，没有生产连接。origin/main实际ee94abb，本轮按用户指定固定676569c，不偷换基线、不合main。

## 10. 实际命令、测试与复现方法

路径缩写：R为任务工作树；O为本机仓库外审核目录；G为R/.venv-grammar-tools/bin/python；P为桌面项目.venv/bin/python；F为O/flask-only/bin/python。以下命令本轮实际执行；O里的脚本仅辅助审核，未提交，也未修改被审代码。另一台电脑可从本节方法重建快照，正式结论和逐题表均保存在本报告。


```sh
R=/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker
O=/Users/zhouxin/.codex/audits/grammar-v02-round17-20261028
G="$R/.venv-grammar-tools/bin/python"
P=/Users/zhouxin/Desktop/studytracker/.venv/bin/python
F="$O/flask-only/bin/python"

git status --short --branch
git log -5 --oneline
git fetch origin claude/word-memorization-system-eval-55v2y5
git merge --ff-only 29701e71ca953452dd3e06e3bd233ea9d0ac331f
git diff --stat dd9f6e7..29701e7
git diff --name-only dd9f6e7..29701e7 -- data/idictation_reading_jijing/raw.json static data/reading_jijing_text_fixes.json models.py app.py api miniprogram .github/workflows
git diff --name-only 8e04e17..dd9f6e7
git archive 29701e7
git ls-tree -r -z 676569c

# O/source中由generate.py依次执行两遍，输出分别复制到O/first、O/second：
"$G" scripts/generate_grammar_candidates.py --seed 20261018
"$G" scripts/generate_grammar_candidates.py --seed 20261018
# 其余下列仓库脚本的cwd均为R，graph在O/source：
"$G" -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary tests.test_grammar_graph_draft -v
"$G" scripts/validate_reading_study.py
"$G" scripts/reading_jijing_text_fixes.py --check
"$P" -m unittest tests.test_reading_study -v
/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tests/test_dictation_spell_queue.js
"$G" -m venv "$O/flask-only"
"$F" -m pip install --cert /etc/ssl/cert.pem Flask
"$F" -m unittest tests.test_miniprogram_guest_access tests.test_miniprogram_dictation_grouping tests.test_inventory_toefl_materials tests.test_organize_toefl_materials tests.test_extract_toefl_answer_keys tests.test_map_toefl_answers_to_practice_docs tests.test_import_toefl_official_reading tests.test_reading_vocab_grading tests.test_stats_utils tests.test_grammar_graph_draft tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary -v
"$F" -m pip list
"$G" scripts/render_grammar_graph_review.py
"$P" -m ruff check --config 'extend-exclude=[]' scripts/grammar_items/templates.py scripts/grammar_items/checks.py scripts/grammar_items/reporting.py tests/test_grammar_item_candidates.py
"$P" -m ruff format --check --config 'extend-exclude=[]' scripts/grammar_items/templates.py scripts/grammar_items/checks.py scripts/grammar_items/reporting.py tests/test_grammar_item_candidates.py

"$G" "$O/audit_runtime.py"
"$G" "$O/audit_data.py"
"$G" "$O/negative_tests.py"
"$G" "$O/rule_probe.py"
"$G" "$O/scan_nominal_complements.py"
"$G" "$O/final_checks.py"
"$P" "$O/import_snapshot.py" "$O/main" main
"$P" "$O/import_snapshot.py" "$O/source" current
"$P" "$O/import_snapshot.py" "$O/main" main-baseline
"$P" "$O/import_snapshot.py" "$O/baseline" old-baseline
/opt/homebrew/bin/gh run view 40612434680 --repo KB77GG/studytracker --json status,conclusion,headSha,url,jobs
/opt/homebrew/bin/gh run view 40612434680 --repo KB77GG/studytracker --log
```

专项155全部通过；Flask-only223运行=222通过+1设计跳过；Node退出0；reading22通过。Flask-only除pip外仅Flask及其传递依赖，没有spaCy、SQLAlchemy等项目依赖。Ruff0.15.21对4个改动Python的check和format --check均通过。

validator报告0错误（317篇就绪；70篇缺解析为既有状态），text_fixes --check输出0。raw重建调用build_reading_test_practice.build_tests，localize_image仅按既有URL规则返回本地路径、不下载图片；171篇的content整体（含summary）及groups与static逐对象全等。图谱在O/source重渲染，与提交文档逐字节相同，介词短语句数2638。

### 新测试在旧代码上的负测

AST比较dd9和297取得4个新增测试；每项独立子进程加载旧checks/templates、现测试，其余代码不变。不把缺新Reason常量的接口错误称作断言失败。

| 测试 | 旧dd9结果 | 说明 |
| --- | --- | --- |
| PrepositionalTargetTests.test_conjunction_led_elliptical_clause_stays | 接口错误 | 测试引用缺失的PREPOSITIONAL_TARGET枚举；不是控制例被旧代码误降 |
| PrepositionalTargetTests.test_preposition_taking_a_clause_stays | 接口错误 | 测试引用缺失的PREPOSITIONAL_TARGET枚举；不是控制例被旧代码误降 |
| PrepositionalTargetTests.test_preposition_with_noun_object_goes_to_review | 断言失败 | 两类介词结构仍auto，状态断言失败 |
| PrepositionalTargetTests.test_preposition_with_subjectless_gerund_goes_to_review | 断言失败 | 两类介词结构仍auto，状态断言失败 |

合计2断言失败、2接口错误；当前4项通过。题干/数据问题与这个测试接口现象分开判断。

审核辅助脚本有两次本机问题，已更正重跑：内存tuple与JSON list未规范化引起一次比较断言，规范化后全字段一致；可选的剑桥raw路径不存在引起一次FileNotFoundError，改为明确报告缺文件，正式机经171篇检查从未依赖它。均未修改被审代码，也未将失败算作测试通过。

## 11. CI、交接、限制与下一步

被审head29701e7的[CI40612434680](https://github.com/KB77GG/studytracker/actions/runs/40612434680)整体success；test成功（223运行/1跳过、Node成功），lint advisory失败112条、format步骤跳过。全局lint与本轮4文件Ruff通过分开报告。审核正文与交接三文档已commit/push到本分支，精确head为 `2d746a2c4da97748bf361581c087ff1309d20b27`；[CI40624557217](https://github.com/KB77GG/studytracker/actions/runs/40624557217)已completed/success。**test成功：223运行/1跳过，Node成功；lint advisory失败：112条诊断与297基线逐条相同，format步骤跳过。** 本CI补记仅改相同三文档，再普通commit/push，不amend、无skip-ci；末次提交及它的精确head CI在最终回复报告。

- 本轮按任务优先级只对剑桥做120随机题和定向扫描，机经只核验新规则3题；不是机经全量人工审定。
- 必做8项均完成，没有跳过或变更用户基线。使用仓库外快照避免覆盖交付文件；使用同环境缓存生成两遍，另24句现解析。报告版本行差异如预期。
- 原始语料复杂，spaCy依存不是独立语法真值。AD1建议只改措辞，不撤销保守复核。
- 当前A-03的10⁹恢复、既有教学口径、非并列T2多目标、老师盲审范围及上线授权未解决；明确保留，不因本轮有条件通过消失。
- 桌面工作树 `/Users/zhouxin/Desktop/studytracker` 仍main@6ded77d24586327ad94e151e172ae4811b4a2eed，behind87，既有7modified/22untracked入口未改；本轮仅借用其venv。O里的脚本/全池/缓存/日志/SQLite只本机可见。
- 本轮交接更新本报告、docs/CODEX_HANDOFF.md和docs/WORKLOG.md；提交/推送仅codex/grammar-item-candidates，无skip-ci。最终SHA和精确CI以补记及最终回复为准。
- 没有推main、开PR、后端部署、小程序上传/提审/发布、生产服务器或生产数据库操作、调用大模型API。其他任务上线状态不算本轮部署。
- 下一位先读本报告的AC1/AC2关闭范围；如获授权，再按§8恢复10⁹并重新生成/导入验证，按后续决定安排教师盲审，避免把机器auto标签当作人工验收完成。
