# 语法候选题 v0.2 第十轮独立复审（Codex）

审核日期：2026-10-27（Asia/Shanghai）。**结论：不通过，以剑桥题为准。** W1–W4 的42道点名回归已全部离开自动池，W6统计更正通过；W5精度问题和既有A8多解继续保留。新的定向检查确认 **0阻断、3应修（X1–X3）、1建议（X4）**。X1–X3共涉及17道不同的剑桥auto题、12个来源句；它们在第九轮已存在，**不是本轮代码新引入**。降级规则验收通过，不能据此宣布整个自动池内容正确。

固定审查 `efc030c746d043d8477fcd25f2d92b478193eec0..8a0660b688111319e1c8086e1b419419cde90588`。工作树 `/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker`，分支 `codex/grammar-item-candidates`。开工干净，读入口和交接后fetch并按授权快进到8a0660b；没有合并main、rebase或带入其他提交。只新增本报告、更新CODEX_HANDOFF和WORKLOG；未修改被审代码、数据、原文、标注和交付文件。生成、反事实、扫描和导入均在仓库外快照/临时库进行。

“局部答案成立”“完整高亮”“题干前提成立”“整句可给学生”分别判定。待复核题只验证降级理由，不算进自动题正确率。机经单列，不计上述分级数量。

## 1. 上轮编号的关闭情况

| 编号 | 结论 | 依据与边界 |
|---|---|---|
| W1 | 点名问题关闭；规则字面边界有建议X4 | 17道T3均needs；只影响T3，未改type_matches。原44目标上的35道T2逐字段不变。另10道auto下降：8道有从属范围歧义、2道保守误伤；已有27道needs增原因。不能说并列与从属两维分类问题已从教学设计上消除。 |
| W2 | 点名问题关闭 | E-06及其余回归共17道T1/T5降级；109个旧auto冒号/分号T1仅原10句降级；额外1道T5合理。全库0道T6带本原因，相关来源的104道T6逐字段不变。引语/括号的启发式边界仍有限。 |
| W3 | 关闭 | 两条难点语法与时态准确；8道题全带source_quality，其中6道原auto、2道原needs；没有修改剑桥原文。 |
| W4 | 点名问题关闭；扩展边界保留 | 两题needs，其余5道auto不变；3个ADJ控制目标的5道题不变。逗号年龄结构只提示歧义，不强定为定语从句；省去面向出题人的元说明合理。实际入口也接受where/why，见X4。 |
| W5 | 保留，接受本轮保守误降取舍 | noun挂靠不是定语从句的证明；既有9/22保守误降未修。优先降低错误自动通过时可接受，不把它写成语法结论或已提升精度。 |
| W6 | 关闭 | 第九轮更正区分41道共同ID状态变化、固定旧标注的7+40规则反事实、1题roles元数据变化；第十轮三种口径均独立复现。 |

既有A8（T2多解）**未关闭**；本轮样本再次出现真实实例，见第8节。它不在这版W1–W4的实施范围，不能用解析器粗筛误报较多作为“没有多解”的证明。

## 2. 十二项检查结果

| 项 | 结果 | 独立证据/实际执行入口 |
|---|---|---|
| 1 范围 | 通过 | `git diff --stat efc030c..8a0660b`：14文件、998增/474删，均在白名单。保护路径0变化。3个JSON逐字节只替换指定DP字符串；规则4函数AST未读取三个ID字段。命令A、D。 |
| 2 W1 | 点名验收通过，保守范围可接受 | 17+10新增needs、27原needs；10均属于原27控制目标；其余17控制目标保持auto，35道关联T2不变。引语正常并列不触发。各题见第4节；and/or的字面差异见X4。命令E。 |
| 3 W2 | 点名验收通过 | 109旧T1→仅10降级；17回归+1额外T5；54旧needs的来源均存在两个完整分句。104相关T6不变；引语补修只去掉9道既有needs的原因（剑桥8/机经1），状态不变。控制例见第5节。命令E。 |
| 4 W3 | 通过 | 两句各指定DP准确；8道全needs。两个原needs的名词性目标自身还不完整，不能因降级正确而宣称答案正确。命令D、E。 |
| 5 W4 | 点名验收通过 | 仅A-01两道新增possible_relative_adverb，同句其余5道与3个ADJ控制目标5道逐字段相同。无逗号年龄句、cold/happy控制不触发。命令E。 |
| 6 W6及统计 | 通过 | 三种原因口径均与FIXES相等；131道原needs增原因（剑桥83/机经48）未误算为71道实际降级。命令C。 |
| 7 W5/A8 | 披露真实，未解决 | W5保守误降本轮接受；A8仍有确定实例。继承限界不是本轮新应修计数；不作整个题池可直接给学生的批准。 |
| 8 剑桥抽查/扫描 | 不通过 | seed20261031，6×20=120，全为auto：120个给定局部答案可成立、120处目标/答案高亮本次未发现缺漏；1题干扰项错（X2），另1题T2唯一性不成立（既有A8），其余118本次未发现内容问题。定向扫描另确认X1/X3，均未混入随机分母。命令F。 |
| 9 全池差分 | 通过 | 50,243，ID全等，非status/reasons字段0变化；71道auto→needs=剑桥53+机经18；auto40,501，其中剑桥27,976。命令C。 |
| 10 双跑/表格 | 通过 | JSONL/XLSX与提交逐字节一致，两报告只有Python版本行不同；双跑4份完全一致。78回归对象不变，7过滤一致；13旧题号、0同位置；剑桥231=196auto+35needs，机经129；7表/6×60/四项下拉/盲审。命令B、C、D。 |
| 11 测试/数据 | 通过 | 专项113；Flask-only181运行、180通过、1按设计跳过；Node通过；reading22通过；validator和--check均0；raw171篇content/groups完全一致；图谱字节一致；4个改动Python Ruff check/format通过。负测失败类型核实，见第10节。命令G、H、D。 |
| 12 导入 | 通过 | 完整main676569c快照317篇先导入，再导8a0660b：updated236/skipped81/failed0。main→第九轮dry-run也是236/81/0，同一236篇；两篇确实此前仅因标签归一化已updated。命令I。 |

## 3. 剑桥问题清单

### X1 — 应修：连字符动词按解析token拆成词片段，13道auto的答案、高亮或干扰项不完整

位置：`scripts/grammar_items/templates.py:166`（verb_unit）、`:372`（main_distractors）、`:728`（finite_or_not）；下面逐题给出来源。这里的“完整单位”还需要保持原文单词边界：aux/neg/prt完整并不能证明`re`、`pre`或连字符本身是一个动词。解析器把三个连字符标成POS=VERB，但它们的`is_punct`仍为true，主句干扰项直接收了进去。

复现：生成全池后取下表ID，看`answer.spans`、`grading.required_root`、`target.parts`及`distractors[*].parts`；使用`teacher_row()`渲染会得到`【could】, in theory, 【re】-establish`、`【is not pre】-set`。**不要只看target.text**：`to be road-tested`看似完整，实际parts只有`to be`和`tested`。13道均auto，且与76aeb12逐字段相等。

建议：加通用的原文词边界/连字符词一致性检查；纯标点不得作为动词中心。在确认词性后把同一词的组成部分视为完整词，或无法可靠判断时降needs_review。不要只删掉`-`而保留`to re`/`establish`两个伪单位。计划冻结T1答案时，可先降级并记录原因，再明确批准答案规则的修订；不能为保持旧答案而继续auto。控制例应包含真正的插入破折号、数字范围、合法复合形容词和下表完整动词。词典也将[road-test列为动词](https://dictionary.cambridge.org/dictionary/english/road-test?topic=driving-and-operating-road-vehicles)；将它截成tested不是对词性分析分歧的处理；[Oxford tape-record词条](https://www.oxfordlearnersdictionaries.com/definition/english/tape-record)也把tape-record作为完整动词列出。

| 题号 | 题型 | 来源 | 状态 | 独立判定 |
| --- | --- | --- | --- | --- |
| gi_v02_39a5639ec9f7 | T1 | ielts12_test8_p2 G-02 | auto_pass | 干扰项把 to re-establish 拆成 to re、-、establish；连字符被当作VERB |
| gi_v02_2612039eb0fc | T1 | ielts16_test1_p3 M-03 | auto_pass | 干扰项把 to pre-empt 拆成 to pre、-、empt；连字符被当作VERB |
| gi_v02_9d25c9be58aa | T1 | ielts7_test3_p3 A-04 | auto_pass | 干扰项把 to co-ordinate 拆成 to co、-、ordinate；连字符被当作VERB |
| gi_v02_4f9aff5be0d3 | T1 | ielts10_test1_p3 D-02 | auto_pass | T1答案 are / wired，未包含完整 hard-wired |
| gi_v02_ada51e0516f7 | T6 | ielts10_test1_p3 D-02 | auto_pass | 实际 parts 高亮【are】hard-【wired】，未包含完整 hard-wired |
| gi_v02_d3ad4b5fc6b8 | T1 | ielts15_test2_p2 D-06 | auto_pass | T1答案 could / re，错误把前缀re作为required_root，漏-establish |
| gi_v02_facbcdde7ef5 | T6 | ielts15_test2_p2 D-06 | auto_pass | 实际 parts 高亮【could】, in theory, 【re】-establish，目标不是完整动词 |
| gi_v02_411c43f579e8 | T1 | ielts4_test3_p3 D-13 | auto_pass | T1只接受record，漏掉同一动词的tape- |
| gi_v02_7bd50392fc2c | T6 | ielts4_test3_p3 D-13 | auto_pass | 实际高亮tape-【record】，目标不是完整tape-record |
| gi_v02_177f2e3cb51e | T1 | ielts7_test4_p2 E-04 | auto_pass | T1答案is / not / pre，漏-set，前缀pre不是动词 |
| gi_v02_96c3342be4bf | T6 | ielts7_test4_p2 E-04 | auto_pass | 实际高亮【is not pre】-set，前缀pre不是动词 |
| gi_v02_9102debcb432 | T1 | ielts18_test3_p2 F-02 | auto_pass | 主答案shipped正确；干扰项parts为to be / tested，漏同一动词的road- |
| gi_v02_f0cf657b23e2 | T6 | ielts18_test3_p2 F-02 | auto_pass | 实际parts高亮【to be】road-【tested】，漏同一动词的road- |

### X2 — 应修：两个名词性定语被当作动词干扰项

位置：`templates.py:387`只按POS=VERB/AUX筛选，再在`:391`按prt拼单位。`back-up air conditioning`指备用空调；`supermarket check-out lasers`指结账扫描设备。两处都不是句中实际发生的back up/check out动词行为。解析器把back/check误标VERB、up/out挂prt，规则据此生成了错误的“动词”干扰项。主句答案仍正确，原句正常，因此本项是干扰项质量问题，不能统计成主句答案错误。

复现：取下表两ID，查看`distractors`和解析缓存：back/check均amod修饰名词。建议增加词性冲突/词内连字符检查并降待审，不要把所有amod的VBN/VBG一概删除（正常分词定语很多）。[Cambridge backup词条](https://dictionary.cambridge.org/us/dictionary/english/backup)把back-up列为名词写法，与[back up动词词条](https://dictionary.cambridge.org/dictionary/english/back-up?q=back-up_1)不同；[checkout词条](https://dictionary.cambridge.org/dictionary/english/checkout)也将结账处列为名词。结合本句名词定语环境作上述判断。

| 题号 | 题型 | 来源 | 状态 | 独立判定 |
| --- | --- | --- | --- | --- |
| gi_v02_1213768264f6 | T1 | ielts14_test2_p2 I-02 | auto_pass | back-up air conditioning中的back-up为名词/定语，不是back up动词；被做成back / up动词干扰项 |
| gi_v02_b983993a8787 | T1 | ielts9_test3_p3 E-28 | auto_pass | supermarket check-out lasers中的check-out为结账设备的定语，不是check out动词；被做成check / out干扰项 |

### X3 — 应修：完整主语去标点时删掉百分号，2道auto答案错误

位置：`scripts/grammar_items/parse_view.py:64`的trim_tokens，`templates.py:672`/`:679`在答案和解析树两边都用同样的裁剪，`:683`再补符号。`%`被spaCy标为is_punct，尾部裁剪把它删掉；两边同时裁剪后仍“相等”，所以复核未发现。J-40裁到53后，`close_quotes`看见后方仍有非空的`%`，也不会补回闭合破折号。

复现：两ID的answer.span.end正好落在原句`%`之前；渲染为`【A full 94】%`和`【only a small majority ... – 53】% –`。这不是可忽略的句末标点：百分号是数量表达的一部分，J-40还涉及同位说明完整性。建议对数字单位符号保留语义范围，再在原标注边界内恢复成对标点；复核不能在答案与参照两侧同时删掉关键符号。增加94%、53%插入语及普通句尾逗号/句点的正反例，不改原文。

| 题号 | 题型 | 来源 | 状态 | 独立判定 |
| --- | --- | --- | --- | --- |
| gi_v02_50bd636fe569 | T5 | ielts4_test1_p3 J-33 | auto_pass | 完整主语应为A full 94%，答案截成A full 94 |
| gi_v02_45648a820455 | T5 | ielts4_test1_p3 J-40 | auto_pass | 完整主语应保留插入同位语53%及闭合破折号，答案截在53 |

### X4 — 建议：规则的字面边界和说明有两处差异；当前语料未确认受害题

- `templates.py:560`的mark集合只减去`{for,so,yet}`，没有按本轮说明排除and/or。构造正常并列首项的and被解析为mark时，会错误增加coordinate_function_overlap；全库实际带此原因的82道里，未发现由and/or mark触发的实例。建议显式排除并列连词并加这种解析误标控制例，而非依赖“通常是cc”。W1真实回归仍通过。
- `templates.py:199`的年龄风险入口使用`RELATIVE_ADVERBS={when,where,why}`，没有另限制为when；因此字面实现比“只覆盖…when”的文字更宽。当前新增仍只有A-01两题，没有另确认实际误伤。建议限制到已验收的when或将说明与扩展控制例补齐。

这些是范围一致性建议，不计为新错误auto题。W2另构造`He bought a book: (it was expensive).`会触发多主句原因，说明它没有通用括号深度规则；常规`(note: it was expensive)`控制不触发。这种边缘保守待审不作为本轮应修，但不要声称所有括号内说明均已被排除。

### 机经（暂缓）

本轮新增确认机经内容问题 **0**；未开展与剑桥同强度的机经人工题审。只复现规则影响：18道实际降级（W1 13、W2 5），另48道原needs增加原因；引语补修去掉1道机经原needs的原因。用户已决定暂缓的V2三处排印、Q27错误解析、V4/V5及历史项未重复计数，不把18道状态变化当成18个新问题。

## 4. W1逐题复核

实现仅在classify_clauses的coordinate分支追加原因；type_matches没有改，T2不连带。沿conj链回到首项后，只检查首项自己的mark或开头wh；没有遍历全部从属祖先。这样能保护“并列主句内另嵌从句”和普通引语内并列，但不能可靠判断报告that的语义作用域。缺少and/or显式排除已记X4。

### 4.1 点名17道：全部auto→needs，互斥分类仍有重叠

| 题号 | 来源 | 目标 | 当前状态 | 判断 |
| --- | --- | --- | --- | --- |
| gi_v02_8d37d96a8c41 | ielts10_test1_p1 E-01 | the wells no longer reach the water table | needs_review | 降级合理；as管辖两个原因分句 |
| gi_v02_ac9f8535a872 | ielts10_test4_p3 A-03 | modern genetics enters the scene | needs_review | 降级合理；as管辖两个时间/原因分句 |
| gi_v02_db4a94e67ec4 | ielts11_test2_p2 B-07 | they could no longer construct wooden canoes for fishing | needs_review | 降级合理；as管辖两个原因分句 |
| gi_v02_5098e4ecac73 | ielts11_test3_p3 G-07 | purely theoretical discoveries find unanticipated applications | needs_review | 降级合理；as管辖questions与discoveries两个分句 |
| gi_v02_0bd648f0066e | ielts12_test5_p1 C-04 | why today it accounts for roughly half of all cork production around the world | needs_review | 降级合理；why从句与前一why从句并列，共同作explains的宾语 |
| gi_v02_cced38be072a | ielts12_test5_p1 D-07 | when the air is damp | needs_review | 降级合理；when从句修饰a day，不能与定语从句互斥 |
| gi_v02_1a3f8293a80a | ielts13_test4_p2 D-01 | agriculture had to be run on more commercial lines | needs_review | 降级合理；as管辖人口增长及农业商业化 |
| gi_v02_4c275b496ac1 | ielts14_test1_p3 K-03 | manager support for fun had a favorable impact in reducing turnover | needs_review | 降级合理；that后两项都是found的内容 |
| gi_v02_d01f41961eff | ielts16_test1_p2 E-05 | what they were supposed to represent | needs_review | 降级合理；what从句与why从句并列，共同作on的宾语 |
| gi_v02_60cb6a4601fa | ielts16_test2_p3 J-02 | how much stronger such contextual effects are for understanding the relationship between wise judgment and its social and affective outcomes as compared to the generalized “traits” | needs_review | 降级合理；how从句与前一how从句并列，共同作形式主语it对应的内容 |
| gi_v02_48bddfc51ad7 | ielts18_test1_p2 F-04 | the money that comes in is spread out over a decade or more | needs_review | 降级合理；so that管辖两个目的/结果分句 |
| gi_v02_d661a884e51f | ielts20_test1_p1 I-04 | the birds were more intensively managed | needs_review | 降级合理；until管辖两个改变条件 |
| gi_v02_077495b556b8 | ielts6_test2_p2 A-02 | when they do strike, it is much later in life | needs_review | 降级合理；reveal that管辖疾病发生率和发生时间两项 |
| gi_v02_23f3ec6f71a5 | ielts6_test3_p2 A-05 | where there is independence and feedback | needs_review | 降级合理；where与when从句并列，仍表达工作条件/情境 |
| gi_v02_4919084edc4c | ielts7_test2_p3 D-07 | there were no resources to repair them | needs_review | 降级合理；because管辖车辆坏及无修理资源两项 |
| gi_v02_7f0cf16fab32 | ielts8_test2_p2 F-05 | greenhouse gas levels continued to soar | needs_review | 降级合理；as管辖化石燃料使用与温室气体上升 |
| gi_v02_8e07cbab650d | ielts8_test3_p2 E-02 | the once outrageous shapes and colours of an artist like Paul Klee so soon appear on the fabrics we wear | needs_review | 降级合理；fact that同位内容含两项并列 |

### 4.2 原27个控制目标：10道T3降级、17道保持auto；相关T2均不变

8道新增降级有共享从属范围的合理分析；D-03的末项位于闭破折号之后，独立评注的分析也成立，因此应描述为“有歧义而待审”，不能断定它一定仍在that里。E-20第三项和C-11是已披露的保守误伤，接受本轮降级但不把解析器挂靠当作正确语法。E-20可利用分号、插入they thought和并列平行性提高判断；C-11涉及报告内容与作者判断的语义范围，单靠conj树很难安全放回auto。可设计通用的标点/作用域复核证据，不能为了恢复这两题加ID例外。

| 来源 | 目标 | T3题号 | T3状态 | 判断 | 关联T2（均auto不变） |
| --- | --- | --- | --- | --- | --- |
| ielts10_test1_p3 D-01 | under that pressure we, as a species, behave differently | gi_v02_639f4d1c3c98 | auto_pass→needs_review | 共享because可成立，降级合理 | gi_v02_c324b643ee50 |
| ielts10_test1_p3 E-05 | I'm going to take you with me | gi_v02_af4e1c611a73 | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_ff994a4069ff |
| ielts10_test3_p3 F-01 | they had the ability to sail them | gi_v02_4f1586e5e1d4 | auto_pass→needs_review | say is that后的共享that，降级合理 | gi_v02_3d2a6007a572 |
| ielts10_test4_p1 I-02 | we were not able to communicate adequately with them | gi_v02_8c4d04bc06e4 | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_06e1e2f9ba92 |
| ielts10_test4_p2 E-06 | it wasn't anywhere near what I thought it was | gi_v02_da3ede52e68d | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_e51e03c47627 |
| ielts11_test2_p2 C-04 | that required both a lot of wood and a lot of people | gi_v02_006fc94977d5 | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_6aa39bfe587c |
| ielts13_test1_p2 C-04 | in actual fact it can lead to all kinds of amazing things | gi_v02_afcf87117d94 | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_940ff66626a3 |
| ielts13_test1_p2 D-12 | if they are not successful there's that frustration and irritability | gi_v02_d82df31e5691 | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_c126dd8d3bc8 |
| ielts15_test1_p2 B-02 | it is the primary cause in the vast majority | gi_v02_925caa02156b | auto_pass→needs_review | demonstrated that的并列内容，降级合理 | 无T2 |
| ielts15_test1_p2 G-03 | the need to be flexible in response to this will be vital for those involved in manufacturing the vehicles that will deliver future mobility | gi_v02_56c920700d5a | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_60bb5cc29ad1 |
| ielts15_test1_p3 D-03 | that's not including bacteria | gi_v02_82667617514f | auto_pass→needs_review | 闭破折号后评注也可独立；有范围歧义，待审合理 | gi_v02_40b28d51f5de |
| ielts15_test1_p3 E-04 | an explorer changes the world | gi_v02_8da77e8bcf24 | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_cc6a54ffebec |
| ielts15_test3_p3 F-02 | there are lots of other details that can evolve quite freely | gi_v02_6ae0d712a189 | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_95d810c53541 |
| ielts16_test3_p3 B-01 | the pace at which they change is 'directly proportional to temperature' | gi_v02_7df93d463602 | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_434d1eea68ad |
| ielts17_test4_p2 F-07 | this has implications for today | gi_v02_620aaa549187 | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_8d58d7038716 |
| ielts18_test3_p1 E-07 | the process, it seems, is quieter | gi_v02_6fdf9d85cba9 | auto_pass→needs_review | say that的并列内容，降级合理 | gi_v02_556b2510f4ce |
| ielts20_test1_p2 A-06 | it's only then that you realise the impact [elms had] | gi_v02_2e8e11b959ad | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | 无T2 |
| ielts20_test3_p2 A-05 | we want to show people how wonderful they are | gi_v02_eaf84cb0004b | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_28dc3a20eae4 |
| ielts20_test3_p3 L-03 | that is why the worlds seem to collide at times | gi_v02_623c99a4447e | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_c63d755c3225 |
| ielts20_test4_p3 E-25 | in others only one or two have dogs | gi_v02_3dbe868ef621 | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_5bcddb5b8cda |
| ielts4_test1_p3 E-20 | the bent spokes were taken as a sign that the wheel was jerking | gi_v02_4448f9965e25 | auto_pass→needs_review | 误伤：三独立分句，分号与they thought提供反证 | 无T2 |
| ielts4_test2_p1 E-26 | they have had to adapt to socio-economic pressures | gi_v02_057908d6801b | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_ef1cfa644d9c |
| ielts5_test1_p3 C-11 | four factors seem to cause this disjunction between perception and reality | gi_v02_41f5455f8875 | auto_pass→needs_review | 误伤：four factors是作者判断，非polls suggest的内容 | gi_v02_0b9764d87eff |
| ielts5_test3_p3 G-44 | AI can now be judged by what it can do, rather than by how well it matches up to a 30-year-old science-fiction film | gi_v02_fe6ea70522cb | auto_pass→needs_review | It may be that的并列内容，降级合理 | gi_v02_d5aa28db47a5 |
| ielts6_test4_p1 E-23 | it doesn't make me prescribe their medicine | gi_v02_9153e2c0a553 | auto_pass→auto_pass | 正常并列/引语内并列，保持auto合理 | gi_v02_8d12000ccc0a |
| ielts6_test4_p2 J-27 | similar campaigns elsewhere might not work as well | gi_v02_9ece9d16f2e3 | auto_pass→needs_review | warns that的并列内容，降级合理 | gi_v02_04483badd323 |
| ielts7_test4_p1 A-07 | the men were using it to lift a heavy object | gi_v02_e5a3f4435aa3 | auto_pass→needs_review | wondered if的并列内容，降级合理 | gi_v02_37a02e15f857 |

### 4.3 原已needs的27道：仅增加原因

这些题保持needs，不能算作27道新增降级。多数目标共享that/wh/关系词；一些原本只是共用主语的并列谓语，已有clause_type_mismatch等原因。新增重叠风险可以保留，但不证明“并列分句”答案本身正确。E-20第二项是同一已披露句子的保守误伤。

| 题号 | 来源 | 目标 | 状态 | 新增原因判断 |
| --- | --- | --- | --- | --- |
| gi_v02_b0ed79f0fa3d | ielts10_test2_p1 F-01 | also had no sanitation | needs→needs | which范围内共用主语谓语；原类别问题保留 |
| gi_v02_98f18d8a15c4 | ielts10_test2_p3 J-03 | is absent from most art history | needs→needs | which范围内共用主语谓语 |
| gi_v02_82a456a93fa9 | ielts10_test3_p1 E-02 | it ranks second or third | needs→needs | suggest that内容并列；前置状语边界另审 |
| gi_v02_fb957ebe1602 | ielts10_test4_p2 A-01 | that the key traits of personality are determined at a very young age | needs→needs | that名词性内容并列 |
| gi_v02_88669354444f | ielts10_test4_p3 F-04 | that some might survive as long as 10 million years | needs→needs | that名词性内容并列 |
| gi_v02_045a877651d1 | ielts11_test2_p2 C-06 | civil war began | needs→needs | 共享when的时间从句 |
| gi_v02_380725635b75 | ielts11_test3_p2 E-05 | therefore helps guide researchers towards understanding how evolution has produced them all | needs→needs | 共享that但后项共用主语 |
| gi_v02_af9ab1287989 | ielts11_test4_p1 D-01 | coined the phrase 'nature and nurture' | needs→needs | 共享when/关系范围，后项为谓语 |
| gi_v02_29be89046ecb | ielts12_test5_p1 G-04 | prevent desertification in the regions where they are planted | needs→needs | 共享which且共用主语 |
| gi_v02_231185a01aa5 | ielts12_test6_p1 F-01 | allow for investment in improvements | needs→needs | 共享that且共用主语 |
| gi_v02_acf1a9d11a4e | ielts12_test6_p2 F-03 | whether it could also have been what chroniclers described as 'the last city of the Incas' | needs→needs | whether名词性内容并列 |
| gi_v02_7cce27eae97b | ielts12_test7_p1 D-02 | weigh at least 4.5 kilograms | needs→needs | 共享until且共用主语 |
| gi_v02_343ee2159e90 | ielts13_test1_p3 C-02 | the creativity of the computer begin | needs→needs | where does的疑问结构并列，省略需另审 |
| gi_v02_e72f982988f9 | ielts13_test2_p2 A-03 | triggers the motherly behaviour that sheep show towards their newborn lambs | needs→needs | 共享that且共用主语 |
| gi_v02_fafe00b0137d | ielts13_test2_p2 E-09 | improves our ability to identify emotions | needs→needs | 共享why且共用主语 |
| gi_v02_5de70d003d55 | ielts13_test3_p1 F-05 | that they were native to America | needs→needs | that名词性内容并列（两个起源假说） |
| gi_v02_89700bd7f2ea | ielts15_test1_p2 G-01 | these can most probably be conquered within the next 10 years | needs→needs | that内容范围有歧义，复核合理 |
| gi_v02_a0d43bb44b28 | ielts15_test1_p3 B-02 | that in all sorts of professions – whether artist, marine biologist or astronomer – borders of the unknown are being tested each day | needs→needs | the fact that的内容并列 |
| gi_v02_58685a4fc642 | ielts15_test2_p2 F-03 | therefore how we could use it to make genetic modifications | needs→needs | how名词性内容并列，目标边界另审 |
| gi_v02_450ce9434d26 | ielts16_test1_p2 D-07 | had Imhotep's name carved on it as well | needs→needs | so...that结果范围内共用主语 |
| gi_v02_e6c65ad05cf0 | ielts16_test2_p1 B-04 | was created between the 11th and 15th centuries | needs→needs | 共享that且共用主语 |
| gi_v02_4eaa6e90835a | ielts16_test2_p3 C-01 | that our ability to reason wisely depends on a variety of external factors | needs→needs | not so much that...but that名词性并列 |
| gi_v02_3dbce947b643 | ielts16_test2_p3 E-02 | we reason more broadly and focus more on interpersonal and moral ideals | needs→needs | suggests that的内容并列，前置when边界另审 |
| gi_v02_a88fc7d61238 | ielts4_test1_p3 E-20 | the wavy spokes, they thought, suggested that the wheel was wobbling | needs→needs | 误伤：E-20第二独立分句；保留其它待审原因 |
| gi_v02_05d6a5b66604 | ielts4_test1_p3 E-21 | that dashed spokes indicated the wheel was spinning quickly | needs→needs | that宾语内容并列 |
| gi_v02_400674320aa8 | ielts7_test4_p1 G-02 | do know how to deal with wind, sailing and basic mechanical principles | needs→needs | 共享where且共用主语 |
| gi_v02_3c104522dc2f | ielts9_test3_p1 C-01 | that this ought to be imposed on the whole of the speech community | needs→needs | view that的内容并列 |

## 5. W2逐题复核

independent_clauses只看ROOT的ccomp/parataxis/conj子节点，要求限定、自己的主语、与ROOT范围之间有冒号/分号、非wh/mark/引语入口。E-06前句误挂ccomp仍能识别；T1与T5入口增加原因，finite_targets排除T1_ONLY_REASONS中的该原因。相关来源全库104道T6与第九轮逐字段相同；全池唯一变化的两道T6属于W3，并非W2泄漏。

### 5.1 点名17道和额外1道T5

以下局部谓语/主语可成立，但题干指向整句“唯一主句”不成立；降级合理。109个旧auto T1冒号/分号来源中只有下列10道T1降级，另99道仍auto。完整109个ID对比保存在本机probes/main_punctuation证据，不用标点一刀切。

| 题号 | 题型 | 来源 | 局部答案 | 当前状态 | 判断 |
| --- | --- | --- | --- | --- | --- |
| gi_v02_fa5a06f81026 | T1 | ielts12_test8_p2 E-02 | could / not / be | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_ec4d82f4d263 | T5 | ielts12_test8_p2 E-02 | the fishing industry's insistence on scouring every inch of seabed, leaving no breeding reserves | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_88f13fac6658 | T1 | ielts13_test4_p2 B-06 | costs | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_e76742369569 | T5 | ielts13_test4_p2 B-06 | damage to buildings, roads and bridges from floods caused by soil degradation | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_d5e448590295 | T1 | ielts14_test3_p3 F-04 | are | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_5be941a91aed | T5 | ielts14_test3_p3 F-04 | the means | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_2e69d0c43c2e | T1 | ielts14_test3_p3 F-07 | must / be | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_cf9221c3ec44 | T5 | ielts14_test3_p3 F-07 | Players | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_5690b731fad2 | T1 | ielts17_test1_p2 E-06 | have / become | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_3d42601b8d9c | T5 | ielts17_test1_p2 E-06 | the mixed-use facilities at Wembley and Old Trafford | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_45903e2a439d | T1 | ielts20_test2_p3 A-03 | was / mounted | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_039e5b6e4241 | T1 | ielts4_test3_p2 C-04 | inch | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_2a33047fcd6c | T5 | ielts4_test3_p2 C-04 | vast bubbles of magma - molten rock from the mantle - | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_99249b0927cf | T1 | ielts5_test4_p1 A-03 | requires | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_fc21ccd2630c | T1 | ielts6_test4_p3 E-08 | should / be | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_4445ed6322d4 | T1 | ielts8_test2_p3 F-03 | may / be | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_bdd363f085d7 | T5 | ielts8_test2_p3 F-03 | smells that are considered to be offensive in some cultures | needs_review | 多独立分句，唯一主句题不成立；降级合理 |
| gi_v02_7cae4d95b415 | T5 | ielts12_test6_p1 A-01 | Two things | needs_review | 多独立分句，唯一主句题不成立；降级合理 |

额外T5 `ielts12_test6_p1 A-01`中的`Two things distinguish...`、`every single person needs...`、`it is hugely dependent...`均是限定分句；给定Two things局部正确，但不是整句唯一主语。

### 5.2 原已needs的54道

逐句检查确认冒号/分号两侧均有完整限定分句。只确认新增multiple_independent_clauses理由合理，**不宣称这54个原答案全对**；原来的ROOT/主语/边界等问题仍在。例如9_3_p3 C-19的he不等于the process的主语，原needs应保留。

| 题号 | 题型 | 来源 | 保留的机器答案 | 状态 | 新增原因判断 |
| --- | --- | --- | --- | --- | --- |
| gi_v02_667e3f4c9e30 | T5 | ielts11_test2_p1 A-04 | Accounts of what happened to the ship | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_c193a358be83 | T1 | ielts11_test2_p1 A-04 | mishandled | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_c48e0101596d | T1 | ielts12_test5_p1 A-03 | sealed | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_cfcfd17dca21 | T5 | ielts12_test5_p1 A-03 | It | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_10ebcd6a0f46 | T5 | ielts12_test5_p2 A-02 | Many forms of collecting | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_127374526f08 | T5 | ielts12_test5_p3 E-05 | One | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_df006dcbe14c | T1 | ielts12_test5_p3 E-05 | is | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_e43356b545ea | T5 | ielts12_test5_p3 E-06 | The other attitude | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_128b8fec5fa5 | T1 | ielts12_test8_p1 A-03 | took | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_4cd264220a2e | T5 | ielts12_test8_p1 A-03 | Archaeologists | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_f46cd4ea64d0 | T1 | ielts12_test8_p2 G-01 | is | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_e40fde69d907 | T5 | ielts13_test1_p2 B-05 | The most useful | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_791e76799727 | T1 | ielts13_test1_p3 G-02 | reckons | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_de89da86a2ef | T5 | ielts13_test1_p3 G-02 | Paul Bloom of Yale University | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_8859d1e99295 | T5 | ielts13_test2_p2 D-03 | Carsten De Dreu at the University of Amsterdam in the Netherlands | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_c84ce947a8dd | T1 | ielts13_test2_p2 D-03 | became | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_508de928df79 | T5 | ielts13_test4_p3 D-04 | money | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_c5b46b7b6aa0 | T1 | ielts13_test4_p3 D-04 | claimed | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_0bae714297f4 | T5 | ielts13_test4_p3 E-07 | Yet Watson's reductive model | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_80a170beb947 | T1 | ielts13_test4_p3 E-07 | established | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_3105d1fdb8c8 | T1 | ielts15_test2_p3 C-04 | were | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_4a53a7e34ff4 | T5 | ielts15_test2_p3 C-04 | the results | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_5e1e9a44bf3d | T5 | ielts15_test2_p3 D-06 | low-status individuals | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_9c969e968b0d | T1 | ielts15_test2_p3 D-06 | produced | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_b867c18b6c7e | T1 | ielts15_test4_p3 B-05 | declared | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_f0e2f1eef76f | T5 | ielts15_test4_p3 B-05 | The car manufacturer Henry Ford | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_6446d7255e5d | T1 | ielts16_test3_p3 C-01 | cause | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_fc1c4b8c7ea1 | T5 | ielts16_test3_p3 C-01 | Farmers and gardeners | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_e4030eefe04d | T5 | ielts16_test4_p2 A-05 | an invisible, game-changing transformation | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_49c0846f6d10 | T5 | ielts17_test2_p1 D-02 | The only entire book of the Hebrew Bible preserved among the manuscripts from Qumran | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_acf9b8c9d916 | T1 | ielts17_test2_p1 D-02 | considered | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_551808637f8b | T1 | ielts17_test2_p3 D-03 | exist | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_caa431b4fd71 | T5 | ielts17_test2_p3 D-03 | These successes | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_3e2a6e12dcd1 | T5 | ielts17_test4_p3 A-10 | The skill | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_b111f0938a52 | T1 | ielts17_test4_p3 A-10 | calls | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_74c02f0da2b6 | T5 | ielts20_test3_p3 F-02 | it | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_4d5231dd1680 | T1 | ielts7_test2_p2 E-02 | are | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_9968ba53012d | T5 | ielts7_test2_p2 E-02 | Professor Pretty | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_9dccf80f30fe | T1 | ielts7_test4_p1 D-06 | used | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_c986d9709e4b | T5 | ielts7_test4_p1 D-06 | Clemmons | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_445dca35fbb6 | T5 | ielts8_test1_p1 F-02 | The revolutionary aspect of this new timekeeper | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_640faeb12b85 | T1 | ielts8_test1_p1 F-02 | was | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_ff8120274c1f | T1 | ielts8_test1_p3 C-12 | be | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_052e715a8508 | T1 | ielts8_test3_p3 B-10 | is | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_1ef08e7ad2e5 | T5 | ielts8_test4_p1 B-02 | Virtually all pupils at this stage | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_89d52f43482d | T1 | ielts8_test4_p1 B-02 | are | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_36720f476b08 | T5 | ielts8_test4_p1 D-03 | Pupils | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_a8f3b7d7cbe3 | T1 | ielts8_test4_p1 D-03 | is | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_680de7a255bd | T5 | ielts9_test3_p3 C-19 | process he | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_74202e5aad13 | T1 | ielts9_test3_p3 C-19 | is | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_59d019c3a194 | T5 | ielts9_test3_p3 E-27 | The Voyager spacecraft | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_e435356c040c | T1 | ielts9_test3_p3 E-27 | was | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_054063ee891e | T1 | ielts9_test4_p3 D-03 | are | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |
| gi_v02_3a7a7cfa06f0 | T5 | ielts9_test4_p3 D-03 | Heritage and museum experts | needs→needs | 两侧有完整分句；本原因合理，原有问题保留 |

### 5.3 引语补修及控制例

用当前数据、当前其它规则，只把independent_clauses替换成5bf45ac父提交版本做反事实：恰好9道题原会多带原因；补修后9道都仍needs，没有增加auto。检查分隔符后一token能处理“引语为ROOT、报告句为子节点”的反向挂靠；它是保守跳过引语的规则，不能证明引语内外绝无两个主句。16_1_p3 I-01确有引语+报告句的分析，但本来已needs，本轮没有放入自动池，接受作为已披露限界。

| 题号 | 题型 | 来源 | 源类别 | 当前状态 | 判断 |
| --- | --- | --- | --- | --- | --- |
| gi_v02_68615c30f7b3 | T5 | ielts14_test1_p2 D-03 | reading_test | needs_review | 仅去W2原因；其他原因保留 |
| gi_v02_f9317457d3b6 | T1 | ielts15_test1_p3 E-03 | reading_test | needs_review | 仅去W2原因；其他原因保留 |
| gi_v02_52a27ba90b65 | T5 | ielts15_test1_p3 E-03 | reading_test | needs_review | 仅去W2原因；其他原因保留 |
| gi_v02_9d1840087ca4 | T1 | ielts16_test1_p3 I-01 | reading_test | needs_review | 仅去W2原因；其他原因保留 |
| gi_v02_e889dc32c972 | T1 | ielts17_test1_p3 B-04 | reading_test | needs_review | 仅去W2原因；其他原因保留 |
| gi_v02_084c3534be1c | T5 | ielts17_test1_p3 B-04 | reading_test | needs_review | 仅去W2原因；其他原因保留 |
| gi_v02_da7329f17b6c | T1 | ielts20_test3_p3 C-01 | reading_test | needs_review | 仅去W2原因；其他原因保留 |
| gi_v02_296a9624917a | T5 | ielts20_test3_p3 C-01 | reading_test | needs_review | 仅去W2原因；其他原因保留 |
| gi_v02_6cf32194f36c | T5 | reading_jijing_23_test_46_p1 B-04b | reading_jijing | needs_review | 仅去W2原因；其他原因保留 |

| 控制例 | 实际W2原因 | 判断 |
| --- | --- | --- |
| He bought three things: milk, bread and cheese. | 无 | 不新增，符合控制要求 |
| He asked the question: why did prices rise? | 无 | 不新增，符合控制要求 |
| He said: 'We will win.' | 无 | 不新增，符合控制要求 |
| Charles commenced his story: 'I began to run.' | 无 | 不新增，符合控制要求 |
| He bought a book (price: ten dollars). | 无 | 不新增，符合控制要求 |
| He bought a book (note: it was expensive). | 无 | 不新增，符合控制要求 |
| The report says that prices rose because demand increased. | 无 | 不新增，符合控制要求 |
| Prices rose; wages fell. | 有 | 正例命中 |
| He bought a book: (it was expensive). | 有 | 边缘括号例保守命中；限界已披露 |

## 6. W3、W4逐题复核

### W3：难点改写与8道题

“分号一般连接两个独立分句……标点不够规范”是适度表述，不宣称独立主格本身有语病。F-04可用逗号保留being，或分号后把being改为was（前句set/后面had的过去叙事）；B-07可用逗号或把being learned改为are learned（一般事实、skills复数）。两种改法、时态和措辞均合理；本轮只解释，没有改剑桥原文。

| 题号 | 题型 | 来源 | 原→现状态 | 局部答案/高亮 | 整句与原因 |
| --- | --- | --- | --- | --- | --- |
| gi_v02_7b702aabb705 | T2 | ielts15_test1_p3 F-04 | auto→needs | 局部成立、完整 | source_quality合理；不给学生直接使用原题 |
| gi_v02_47296056bc7a | T2 | ielts15_test1_p3 F-04 | needs→needs | 目标that they all had不完整，仍需修边界 | source_quality合理；不给学生直接使用原题 |
| gi_v02_783436998ebf | T3 | ielts15_test1_p3 F-04 | needs→needs | 目标that they all had不完整，仍需修边界 | source_quality合理；不给学生直接使用原题 |
| gi_v02_9ab094841299 | T3 | ielts15_test1_p3 F-04 | auto→needs | 局部成立、完整 | source_quality合理；不给学生直接使用原题 |
| gi_v02_237c28eb99a6 | T6 | ielts15_test1_p3 F-04 | auto→needs | 局部成立、完整 | source_quality合理；不给学生直接使用原题 |
| gi_v02_604e3328ad97 | T2 | ielts7_test3_p1 B-07 | auto→needs | 局部成立、完整 | source_quality合理；不给学生直接使用原题 |
| gi_v02_c88af5a29c0e | T3 | ielts7_test3_p1 B-07 | auto→needs | 局部成立、完整 | source_quality合理；不给学生直接使用原题 |
| gi_v02_10587d4ba8fd | T6 | ielts7_test3_p1 B-07 | auto→needs | 局部成立、完整 | source_quality合理；不给学生直接使用原题 |

### W4：年龄目标2题、其余5题

有逗号时，when可作为年龄/时间表达的补充说明；无逗号`He was ten years old when he moved`通常直接是时间状语。当前有限规则以风险提示处理这一区别，合理；不承诺覆盖at the age of或更复杂年龄表达。难点说明保留两种语法分析，没有把无病句打source_quality；删去草稿最后一句面向出题人的指令适合学生阅读页。

| 题号 | 题型 | 局部答案/目标 | 当前状态 | 判定 |
| --- | --- | --- | --- | --- |
| gi_v02_4a4c60413c27 | T1 | start | auto_pass | 局部答案与题干成立；逐字段不变 |
| gi_v02_7e2180fd8faf | T2 | when babies begin to laugh and smile in response to stimuli | needs_review | 边界成立、类别有歧义；降级合理 |
| gi_v02_7b4122b362c5 | T3 | when babies begin to laugh and smile in response to stimuli | needs_review | 边界成立、类别有歧义；降级合理 |
| gi_v02_26e57db4cc84 | T3 | in response to stimuli | auto_pass | 局部答案与题干成立；逐字段不变 |
| gi_v02_0cfe5e7e5b3e | T5 | Humans | auto_pass | 局部答案与题干成立；逐字段不变 |
| gi_v02_b5cfbbd18131 | T6 | start | auto_pass | 局部答案与题干成立；逐字段不变 |
| gi_v02_052fe0402447 | T6 | begin | auto_pass | 局部答案与题干成立；逐字段不变 |

| ADJ控制题号 | 来源 | 目标 | 结果 |
| --- | --- | --- | --- |
| gi_v02_09919dc354ed | ielts10_test3_p3 F-04 | as landing on the moon is for us today | auto，逐字段不变 |
| gi_v02_db0e4b729593 | ielts10_test3_p3 F-04 | as landing on the moon is for us today | auto，逐字段不变 |
| gi_v02_a707ca268e81 | ielts11_test4_p1 B-02 | than fraternal twins are | auto，逐字段不变 |
| gi_v02_be2ea2538a97 | ielts20_test1_p2 A-05 | if you hadn't seen what was there before | auto，逐字段不变 |
| gi_v02_bd1ac0c5d58a | ielts20_test1_p2 A-05 | if you hadn't seen what was there before | auto，逐字段不变 |

## 7. 差分与计数口径

候选ID集合50,243完全相同；逐字段比较除status/reasons外0处变化。理由变化202道，其中71道auto→needs、131道原needs增加原因；无needs→auto，无原因删除。四类实际降级互不重叠，每道只增加一个原因。

| 模板 | auto | needs | rejected |
| --- | --- | --- | --- |
| T1 main_verb_tap | 5912 | 467 | 6367 |
| T2 clause_boundary | 4680 | 2582 | 2694 |
| T3 clause_type_classify | 11401 | 3486 | 1331 |
| T4 adverbial_relation | 399 | 657 | 2561 |
| T5 subject_span | 5366 | 818 | 6562 |
| T6 finite_or_not | 12743 | 1732 | 6549 |

| 原因 | 全量带原因（剑桥/机经） | 只因此待审（剑桥/机经） | 实际auto→needs（剑桥/机经） |
| --- | --- | --- | --- |
| coordinate_function_overlap | 54/28 | 27/13 | 27/13 |
| multiple_independent_clauses | 72/38 | 18/5 | 18/5 |
| possible_relative_adverb | 144/92 | 97/46 | 2/0 |
| source_quality | 17/607 | 15/407 | 6/0 |

实际剑桥53=W1 27+W2 18+W3 6+W4 2；机经18=W1 13+W2 5。auto合计40,501，剑桥27,976、机经12,525。只因source_quality待审的机经409→407，是两道又增加其他原因，并非删前缀或恢复auto。

W6更正与第九轮复审一致。新的report counting_notes分别说明了功能重叠、分号/冒号主句不唯一、年龄when风险、T6隔离，与主要调用链一致；它们是筛选口径，不是证明所有待审答案错或所有auto答案对。

## 8. 剑桥120道随机抽查与定向扫描

方法：从本机重新生成的全量候选中筛`source_kind == reading_test`、`passage_id.startswith('ielts')`、`status == auto_pass`。按T1–T6固定顺序，每个模板先以item_id排序，然后使用**同一个连续的**`random.Random(20261031)`依次`sample(...,20)`，共120个不同ID。检查原文、机器答案、target.parts的实际高亮、所有干扰项、唯一性/类别前提和整句可用性。不是从360行表中抽，也不是Claude的旧种子。

按状态计数：**120 auto，0 needs**。给定局部答案本次均能成立，高亮本次均完整，120个原句均可阅读；但X2一个干扰项错误，另一个A8唯一性问题，所以只有118题在全部检查维度未发现问题。后面的定向命中不混进这120题的分母；不据此估计整个自动池零错误。

| 序 | 题号 | 型 | 来源 | 机器答案 | 状态 | 局部答案 | 高亮 | 干扰项 | 题干前提 | 原句 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_4ec61887a123 | T1 | ielts20_test4_p1 B-04 | was / raised | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 2 | gi_v02_3e2375853b55 | T1 | ielts5_test4_p1 B-20 | tend | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 3 | gi_v02_c85279c60cac | T1 | ielts17_test3_p2 F-03 | is | auto | 成立 | 完整 | 成立 | 成立 | 可用 | 本次未发现问题 |
| 4 | gi_v02_c10ead1a11f9 | T1 | ielts12_test7_p1 A-01 | cover | auto | 成立 | 完整 | 成立 | 成立 | 可用 | 本次未发现问题 |
| 5 | gi_v02_6006da60acc1 | T1 | ielts20_test1_p1 E-01 | were | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 6 | gi_v02_1213768264f6 | T1 | ielts14_test2_p2 I-02 | have / worked | auto | 成立 | 完整 | 错误（X2） | 成立 | 可用 | 主答案正确，但back-up不是动词干扰项 |
| 7 | gi_v02_855808000c82 | T1 | ielts13_test3_p1 F-04 | has / been | auto | 成立 | 完整 | 成立 | 成立 | 可用 | 本次未发现问题 |
| 8 | gi_v02_0a49d4a9993d | T1 | ielts20_test3_p1 G-01 | was | auto | 成立 | 完整 | 成立 | 成立 | 可用 | 本次未发现问题 |
| 9 | gi_v02_35e84aa65574 | T1 | ielts5_test3_p1 F-04 | contrasts | auto | 成立 | 完整 | 成立 | 成立 | 可用 | 本次未发现问题 |
| 10 | gi_v02_3fb76f68424d | T1 | ielts19_test1_p1 C-06 | are / sent | auto | 成立 | 完整 | 成立 | 成立 | 可用 | 本次未发现问题 |
| 11 | gi_v02_7b2102730b73 | T1 | ielts9_test4_p2 D-01 | continues | auto | 成立 | 完整 | 成立 | 成立 | 可用 | 本次未发现问题 |
| 12 | gi_v02_396162218856 | T1 | ielts4_test4_p1 E-24 | understand | auto | 成立 | 完整 | 成立 | 成立 | 可用 | 本次未发现问题 |
| 13 | gi_v02_a33ba7824db3 | T1 | ielts4_test4_p1 A-06 | set | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 14 | gi_v02_26f2f4db7f13 | T1 | ielts18_test1_p3 C-09 | are / not / going | auto | 成立 | 完整 | 成立 | 成立 | 可用 | 本次未发现问题 |
| 15 | gi_v02_1a779bce5ad0 | T1 | ielts14_test3_p2 H-01 | does / n't / solve | auto | 成立 | 完整 | 成立 | 成立 | 可用 | 本次未发现问题 |
| 16 | gi_v02_f0592efd44d5 | T1 | ielts19_test3_p2 A-04 | have / been / damaged | auto | 成立 | 完整 | 成立 | 成立 | 可用 | 本次未发现问题 |
| 17 | gi_v02_cb5ac65800a5 | T1 | ielts4_test3_p2 A-04 | has / shaped | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 18 | gi_v02_957ee3dbfe3e | T1 | ielts20_test3_p1 G-02 | developed | auto | 成立 | 完整 | 成立 | 成立 | 可用 | 本次未发现问题 |
| 19 | gi_v02_e57c24f3e7ae | T1 | ielts14_test1_p1 H-01 | agrees | auto | 成立 | 完整 | 成立 | 成立 | 可用 | 本次未发现问题 |
| 20 | gi_v02_c7276ed36ca2 | T1 | ielts19_test2_p2 D-06 | has / been / associated | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 21 | gi_v02_fc4501731543 | T2 | ielts19_test4_p1 F-02 | whose colonies are up to a hundred strong | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 22 | gi_v02_c0a29b9d49c6 | T2 | ielts14_test3_p1 B-01 | in which people perceive and evaluate their own intelligence and that of others | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 23 | gi_v02_09890252b3cc | T2 | ielts13_test4_p1 B-03 | Although many were built | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 24 | gi_v02_5977622893c6 | T2 | ielts7_test3_p3 B-13 | what for humans is the essential role of an immense, non-polluting power plant | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 25 | gi_v02_4b80fc1b6ee5 | T2 | ielts4_test3_p2 B-07 | where the collisions occur | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 26 | gi_v02_189adf55c658 | T2 | ielts11_test1_p3 A-05 | if Plan A - reducing our dependency on fossil fuels – fails | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 27 | gi_v02_4bc151f487b6 | T2 | ielts12_test6_p3 B-07 | because the Russian word for 'stamp', marka, sounds like the English word he or she heard, 'marker' | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 28 | gi_v02_b87df140bc20 | T2 | ielts20_test1_p2 D-06 | that experienced high levels of impact | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 29 | gi_v02_9b5406cb1434 | T2 | ielts10_test2_p1 B-02 | before the revolution can happen | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 30 | gi_v02_3d144948ccc6 | T2 | ielts10_test1_p3 H-02 | that prove that even something as simple as writing deepens every individual's engagement in the project | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 31 | gi_v02_ff994a4069ff | T2 | ielts10_test1_p3 E-05 | I'm going to take you with me | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 32 | gi_v02_7d20efdd2988 | T2 | ielts10_test1_p3 I-01 | it often does | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 33 | gi_v02_de36c49c43e8 | T2 | ielts20_test4_p3 G-36 | that these consequences aren’t always negative | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 34 | gi_v02_768dd138f9b6 | T2 | ielts15_test2_p2 F-05 | we have to be willing to take some calculated and measured risks | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 35 | gi_v02_ca27c196e126 | T2 | ielts9_test4_p3 F-05 | which in the seventeenth century was occupied by approximately the same number of inhabitants as today | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 36 | gi_v02_50755112939d | T2 | ielts14_test2_p3 B-05 | what is expected | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 37 | gi_v02_220fb0770ace | T2 | ielts12_test5_p1 G-03 | that can be recycled without difficulty | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 38 | gi_v02_0d5ac847615f | T2 | ielts14_test1_p1 G-01 | we are interested in | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 39 | gi_v02_8bab1bef8487 | T2 | ielts14_test1_p3 K-04 | the framing of that fun must be carefully aligned with both organizational goals and employee characteristics | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 40 | gi_v02_35c7914eb701 | T2 | ielts17_test4_p2 B-04 | they industrialised late | auto | 成立 | 完整 | 不适用 | 不唯一（既有A8） | 可用 | their economies grew slowly和they industrialised late均为并列分句；固定唯一末项不妥 |
| 41 | gi_v02_d1b7e112fe2d | T3 | ielts7_test3_p3 B-13 | 名词性从句 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 42 | gi_v02_f738a15282cc | T3 | ielts18_test3_p2 C-05 | 状语从句 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 43 | gi_v02_a87ac13ed520 | T3 | ielts6_test2_p1 A-03 | 不是从句（短语或非谓语） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 44 | gi_v02_e6945d5eb730 | T3 | ielts20_test4_p1 B-05 | 不是从句（短语或非谓语） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 45 | gi_v02_b86a1cf8c47d | T3 | ielts5_test1_p1 A-02 | 不是从句（短语或非谓语） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 46 | gi_v02_c50da06f06c4 | T3 | ielts13_test1_p3 G-07 | 状语从句 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 47 | gi_v02_bd6850929262 | T3 | ielts13_test2_p2 D-04 | 不是从句（短语或非谓语） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 48 | gi_v02_c8849e1599df | T3 | ielts5_test4_p2 H-30 | 定语从句 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 49 | gi_v02_ba7889c26b26 | T3 | ielts13_test4_p1 D-03 | 不是从句（短语或非谓语） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 50 | gi_v02_3cfa1bc8e123 | T3 | ielts10_test2_p3 I-01 | 不是从句（短语或非谓语） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 51 | gi_v02_8002fa118663 | T3 | ielts5_test3_p1 D-09 | 不是从句（短语或非谓语） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 52 | gi_v02_5eb41f2d2fd6 | T3 | ielts17_test4_p3 E-02 | 不是从句（短语或非谓语） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 53 | gi_v02_1730776b0cd4 | T3 | ielts11_test3_p2 A-04 | 定语从句 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 54 | gi_v02_db2156dd32e2 | T3 | ielts20_test3_p1 D-01 | 不是从句（短语或非谓语） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 55 | gi_v02_27165dad101f | T3 | ielts13_test4_p3 F-01 | 不是从句（短语或非谓语） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 56 | gi_v02_9195488fdd80 | T3 | ielts6_test4_p3 D-09 | 定语从句 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 57 | gi_v02_bf37503869ff | T3 | ielts14_test1_p1 D-01 | 并列分句 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 58 | gi_v02_3c3b40ea0105 | T3 | ielts17_test3_p2 A-03 | 不是从句（短语或非谓语） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 59 | gi_v02_79ae14533def | T3 | ielts16_test4_p1 B-04 | 名词性从句 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 60 | gi_v02_633e5c3e86c6 | T3 | ielts7_test1_p3 D-20 | 不是从句（短语或非谓语） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 61 | gi_v02_253f3c0d8c9b | T4 | ielts9_test4_p2 G-04 | 条件 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 62 | gi_v02_248a24f416f0 | T4 | ielts15_test1_p1 E-11 | 条件 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 63 | gi_v02_c18daabb7c74 | T4 | ielts7_test1_p1 B-05 | 让步 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 64 | gi_v02_41a93ecf389e | T4 | ielts4_test4_p3 C-10 | 条件 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 65 | gi_v02_1a5108714938 | T4 | ielts6_test2_p2 G-23 | 条件 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 66 | gi_v02_3428c100ada3 | T4 | ielts9_test1_p3 C-16 | 条件 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 67 | gi_v02_bc1224a98cd2 | T4 | ielts16_test3_p2 B-05 | 条件 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 68 | gi_v02_526074a0ab5d | T4 | ielts5_test1_p3 L-43 | 条件 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 69 | gi_v02_1b52f7fdd1d5 | T4 | ielts7_test2_p1 A-05 | 让步 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 70 | gi_v02_0730f5303e1c | T4 | ielts5_test2_p2 H-31 | 让步 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 71 | gi_v02_57876a908e1c | T4 | ielts9_test1_p2 E-33 | 条件 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 72 | gi_v02_dcb2ae6ed686 | T4 | ielts5_test4_p2 I-36 | 条件 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 73 | gi_v02_806aa1561597 | T4 | ielts8_test3_p1 I-03b | 条件 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 74 | gi_v02_8b11cffee970 | T4 | ielts4_test2_p3 C-19 | 时间 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 75 | gi_v02_bdc38966997f | T4 | ielts7_test1_p1 D-09 | 时间 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 76 | gi_v02_4ceaaa9aef08 | T4 | ielts5_test4_p2 E-19 | 时间 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 77 | gi_v02_71ca70f2575d | T4 | ielts4_test4_p3 A-01 | 目的 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 78 | gi_v02_c507f787ce4e | T4 | ielts6_test4_p3 D-08 | 时间 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 79 | gi_v02_c0b30a8aca60 | T4 | ielts19_test1_p2 B-11 | 时间 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 80 | gi_v02_3cfba0eafd9a | T4 | ielts14_test2_p3 F-01 | 时间 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 81 | gi_v02_3f7061ccedd0 | T5 | ielts19_test1_p3 D-02 | people who encounter misinformation | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 82 | gi_v02_838460b476fe | T5 | ielts12_test8_p1 B-01 | Glass blowing | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 83 | gi_v02_7dc7020fafb4 | T5 | ielts7_test1_p1 A-01 | Bats | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 84 | gi_v02_b75aea623ac5 | T5 | ielts11_test4_p3 F-02 | A Sumerian word like munintuma'a ('when he had made it suitable for her') | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 85 | gi_v02_bbf74f9f5223 | T5 | ielts17_test1_p2 D-03 | Many such stadiums | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 86 | gi_v02_a09e88c0722b | T5 | ielts5_test3_p3 F-36 | Another factor that may boost the prospects for AI in the near future | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 87 | gi_v02_26834811e586 | T5 | ielts4_test3_p2 C-08 | It | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 88 | gi_v02_8f51224e217b | T5 | ielts4_test1_p2 F-06 | Some of the more complicated sounds | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 89 | gi_v02_e97fe51bf95b | T5 | ielts15_test1_p3 C-03 | This | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 90 | gi_v02_a7357868cc0a | T5 | ielts17_test1_p2 C-04 | the ruins of the amphitheatre | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 91 | gi_v02_a9b577360267 | T5 | ielts8_test1_p2 D-02 | This | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 92 | gi_v02_0f716c3325c4 | T5 | ielts19_test2_p1 F-03 | Samuel Morse and other inventors | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 93 | gi_v02_fb09ff851b4a | T5 | ielts9_test2_p2 B-04 | He | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 94 | gi_v02_787b6cf9f904 | T5 | ielts5_test4_p2 J-42 | a photographer | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 95 | gi_v02_c850d2125c67 | T5 | ielts14_test3_p3 A-04 | Researchers and educators | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 96 | gi_v02_2b97f1e671ac | T5 | ielts13_test4_p2 B-03 | A single gram of healthy soil | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 97 | gi_v02_11e101a5d8ab | T5 | ielts11_test3_p1 B-04 | silk | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 98 | gi_v02_49b02d9b7512 | T5 | ielts7_test3_p3 A-01 | Forests | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 99 | gi_v02_0a0d6f3e8126 | T5 | ielts20_test2_p1 B-08 | They | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 100 | gi_v02_1037c8b1d4cf | T5 | ielts11_test1_p1 B-04 | One such proposal | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 101 | gi_v02_3084911129e5 | T6 | ielts19_test3_p1 E-01 | 非谓语（不定式、分词、动名词） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 102 | gi_v02_00caa3927010 | T6 | ielts15_test4_p3 B-04 | 从句里的谓语 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 103 | gi_v02_217f5ca31b1d | T6 | ielts20_test4_p1 D-12 | 主句谓语 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 104 | gi_v02_8a3056fcc2aa | T6 | ielts14_test2_p3 G-07 | 非谓语（不定式、分词、动名词） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 105 | gi_v02_621e8cfe3891 | T6 | ielts4_test3_p2 A-15 | 主句谓语 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 106 | gi_v02_b36a74ed2679 | T6 | ielts9_test2_p2 B-03 | 主句谓语 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 107 | gi_v02_75509c6a7c8f | T6 | ielts11_test1_p3 C-03 | 非谓语（不定式、分词、动名词） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 108 | gi_v02_fcc56b303445 | T6 | ielts10_test2_p3 K-02 | 主句谓语 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 109 | gi_v02_adc1b097be86 | T6 | ielts4_test1_p3 D-16 | 主句谓语 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 110 | gi_v02_8ca22b8db909 | T6 | ielts15_test3_p1 H-04 | 非谓语（不定式、分词、动名词） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 111 | gi_v02_62f10622a742 | T6 | ielts5_test4_p2 J-45 | 从句里的谓语 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 112 | gi_v02_9074f3b4f34c | T6 | ielts15_test1_p2 A-01 | 主句谓语 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 113 | gi_v02_71e6269f64c2 | T6 | ielts20_test3_p3 F-03 | 非谓语（不定式、分词、动名词） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 114 | gi_v02_a49378ece630 | T6 | ielts20_test3_p3 H-01 | 主句谓语 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 115 | gi_v02_9e556780ea73 | T6 | ielts17_test3_p3 B-02 | 非谓语（不定式、分词、动名词） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 116 | gi_v02_56a0cf149b2b | T6 | ielts6_test1_p1 C-11 | 非谓语（不定式、分词、动名词） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 117 | gi_v02_e791b3baf3a4 | T6 | ielts10_test4_p1 G-01 | 非谓语（不定式、分词、动名词） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 118 | gi_v02_dbe3bba25c2d | T6 | ielts11_test1_p1 C-01 | 非谓语（不定式、分词、动名词） | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 119 | gi_v02_fb2911563f2e | T6 | ielts7_test3_p3 A-05 | 主句谓语 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |
| 120 | gi_v02_1b75e5484f8f | T6 | ielts5_test1_p3 B-07 | 从句里的谓语 | auto | 成立 | 完整 | 不适用 | 成立 | 可用 | 本次未发现问题 |

A8复现：`gi_v02_35c7914eb701`（ielts17_test4_p2 B-04）同时有`their economies grew slowly`与`they industrialised late`两个并列分句，题干只说“划出句中的并列分句”，却只接受末项。给定末项本身正确，唯一答案前提不成立。需要未来给定更明确的目标线索或接受多答案/降待审；本轮未改T2符合既定范围，风险仍然开放。

### 与W1–W4不同角度的全池扫描

扫描对象是全部27,976道剑桥auto，主要检查词边界、语义符号、干扰项词性、关系类型与补语，不复用W1–W4作为筛选标准。机器筛选是候选疑点，逐项看上下文后才确认错误。

| 独立筛选 | 命中 | 人工判断 |
| --- | --- | --- |
| T1干扰项中心amod/compound等名词修饰依存，或含连字符 | 167题 | 逐题检查；大部分是合法分词或分词定语，不能按amod一刀切。确认3道纯连字符/词片段干扰项（X1）、2道名词性定语误作动词（X2）；另外复核road-test词内parts（X1）。未把167道全判错。 |
| T6目标parts边界落在无空格的连字符单词内部 | 5题 | 全部确认缺词的一部分，追查同句T1得到4道答案和1道干扰项问题；合并X1共13个不同题号。 |
| T1干扰项完全不含英文字母 | 3题 | 均为单个连字符，已归X1，不重复计数。 |
| 目标/答案end紧邻未包含的%、°、℃、℉ | 2题 | 均是T5百分号被截断（X3）；未发现本筛选下的温度符号例子。 |
| T5主语中心的appos/relcl/acl/prep/poss/conj直接子节点在答案外 | 1题 | J-40的%同位结构；与X3重复，不新增计数。 |
| auto T4 so that | 7题 | 逐题均有目的语境；没有发现把已发生结果误标目的。 |
| auto状语目标以as if/as though开头 | 7题/5目标 | 均修饰动作/情境，未发现本筛选下的系动词补语误作状语。 |
| when/where/why/how等状语目标挂在know/say/ask等认知报告动词 | 10题/5目标 | 均是时间从句而非它的名词性宾语；没有把挂在认知动词上当作必错。 |
| T3非从句选项却以常见从属词开头 | 11题 | 8个because of介词结构成立；3个while+分词按本项目“短语或非谓语”口径成立。该口径不等于学术语法否认非限定从句。 |
| T3定语从句以what/whether/how/because/if/although开头 | 0题 | 此粗筛无命中，不代表全部定语类别已被形式化证明。 |
| T6非谓语中心为amod等名词修饰依存 | 8题 | 均有合法分词分析；不把分词定语当错误。 |

X1–X3的17道均在旧池中已经auto且对象不变；这是本次不同角度的查漏，不归咎于第十轮改动。机经没有采用相同强度的逐题内容审核。

## 9. 环境、双跑SHA和表格

Mac：macOS 27.0.1 arm64；Python 3.13.3；spaCy 3.8.16；en_core_web_trf 3.8.0；torch 2.14.1；CPU；openpyxl 3.1.5；生成seed20261018。使用指定`.venv-grammar-tools`；源句未变，复用本机已验证缓存。提示未要求本轮冷解析。生成只写仓库外完整8a快照，不覆盖被审交付文件。

输入reading_study SHA-256：`55b808e1a69cfb7fc06670a6ac3bb36d2861923f229183875ed309ea3a747f37`；graph：`c7b35ddb68db7601ccd01e38a210ad3dd772ff507302190f68a351e408b85a29`。

| 文件 | 第一次SHA-256 | 第二次SHA-256 | 与提交比较 |
| --- | --- | --- | --- |
| generation_report_v0_2.json | e3280d73ca91b19d7209abb912aa8ab7c4d61802fa03153f883b3970d6c603e1 | e3280d73ca91b19d7209abb912aa8ab7c4d61802fa03153f883b3970d6c603e1 | 仅Python版本3.13.3/3.11.15一行；提交SHA 274d989b44eb2eb393d2b16c74bdd8872c9e631a85ccdf2e4c83f690265e5aba |
| generation_report_v0_2.md | 8c4d5f0ae4ab6c648ce00dc52cc0fb47f17729e2098a8645a2d11771413e1368 | 8c4d5f0ae4ab6c648ce00dc52cc0fb47f17729e2098a8645a2d11771413e1368 | 仅Python版本3.13.3/3.11.15一行；提交SHA c1076ca682cbc2f13d74f7362a88e2981d13187a3ebfc0d4a0ac9457e63be11e |
| review_batch_v0_2.jsonl | e3a503b8742d15181daf6e5e0e5a6e71db18371f28a514ae8af8882a72acf170 | e3a503b8742d15181daf6e5e0e5a6e71db18371f28a514ae8af8882a72acf170 | 逐字节相同 |
| review_batch_v0_2.xlsx | 386ea7e0564e91c629762259689aaa13c7200b6e01c223c877f6b03ef0f40e33 | 386ea7e0564e91c629762259689aaa13c7200b6e01c223c877f6b03ef0f40e33 | 逐字节相同 |

两个报告比较不是“忽略全部环境字段”：逐行严格比对，差异恰好1行，长度也相同。其余字段和78条回归对象完全相同。

7项整句过滤：tagged_fragment30、clause_attached_to_conjunction2、glued_sentence_boundary0、multi_sentence_unit1、suspected_split_word0、leading_stray_punctuation0、control_character0；实际/预期一致，与上一版相同。过滤明细对象也相等。

xlsx只读检查：ZIP/XML中7个工作表（说明+6题型），每型60道数据行。对每行与JSONL通过teacher_row渲染的所有教师字段逐格比对；H2:H61是`正确,答案错,题目有歧义,句子不适合出题`四项下拉。可见字段没有auto_pass/needs_review或新增原因。剑桥196 auto+35 needs=231，机经104 auto+25 needs=129。按题号交集保留13道；按(工作表,review_row)比较0行同题。已有教师结论只能按题号迁移，不能沿用旧行号；盲审本身仍成立。

## 10. 测试、负测和导入

专项113项通过。Flask-only新环境仅Flask3.1.3及其传递依赖、pip，按ci.yml原13模块完整跑181项：180通过、1因可选Excel依赖未安装按设计跳过；专项环境已覆盖Excel。Node拼写队列通过；reading_study22项通过。validator0、修订表--check=0、raw171篇content（含summary）/groups与static一致，不下载图片。图谱重新渲染字节相同。4个改动Python文件check和format --check通过，未扩大为全仓lint通过。

负测采用每次新增测试所在提交的测试源码，以及该改动前的checks/templates，在独立Python进程执行；不覆写被审模块。实际结果：

| 组 | 测试版本/实现版本 | 结果 | 含义 |
| --- | --- | --- | --- |
| W1 | d54e03a / efc030c | 3运行：1断言失败、2AttributeError | 正例auto≠needs；两个接口错误实际是Reason.COORDINATE_FUNCTION_OVERLAP常量不存在，FIXES括号里“函数不存在”不精确。 |
| W2 | aa00ab6 / d54e03a | 模块ImportError | independent_clauses函数不存在；不能写成2个断言失败。 |
| W4 | 4b8001a / aa00ab6 | 2运行：1断言失败、1通过 | 有逗号正例失败，无逗号控制在旧实现也通过。 |
| 引语补修 | 5bf45ac / 5bf45ac^ | 1断言失败 | 引语作为ROOT的边界控制失败；新实现通过。 |

导入用完整origin/main `676569c6935962ee463fb467be703eb962c9fd43`快照，2853个跟踪文件逐一核对Git blob SHA（含代码、static、data），不是只换data。明确指定本机SQLite路径，未import生产app配置。先main创建317篇，再用第九轮代码dry-run236/81/0，再用8a真实导入236/81/0，236个updated的passage集合完全相同。

解释也复核了：main与76aeb12的`ielts15_test1_p3.json`、`ielts15_test2_p3.json`源文件逐字节相同，但导入归一化不同。前者A-04 bare_infinitive_clause从“状语从句”变“不定式”，E-01 inversion_clause变“倒装”，F-03 elliptical_clause变“省略结构”；后者F-06 elliptical_clause变“省略结构”。所以它们第九轮已updated，本轮增加DP不增加篇数。`65f1859..676569c`在data/reading_study、导入脚本和models.py无差异，Claude的基线说明成立。

## 11. 实际命令与复现材料

以下变量仅用于简写实际路径，不是运行项目的新依赖。临时脚本、日志、池、缓存和SQLite只在本机AUDIT，未提交；跨电脑可按相同仓库版本、种子及下列逐题ID重新核对。

```sh
REVIEW_ROOT=/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker
AUDIT_ROOT=/Users/zhouxin/.codex/audits/grammar-v02-round10-20261027
GRAMMAR_PY="$REVIEW_ROOT/.venv-grammar-tools/bin/python"
APP_PY=/Users/zhouxin/Desktop/studytracker/.venv/bin/python
NODE_BIN=/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
```

A. 工作树与范围（cwd=REVIEW_ROOT）：

```sh
git status --short --branch
git log -5 --oneline
git fetch origin claude/word-memorization-system-eval-55v2y5
git merge --ff-only 8a0660b688111319e1c8086e1b419419cde90588
git rev-parse HEAD
git diff --stat efc030c..8a0660b
git diff --name-only efc030c..8a0660b
git diff --quiet 65f1859 676569c -- data/reading_study scripts/import_reading_study.py models.py
git diff --quiet 676569c 76aeb12 -- data/reading_study/ielts15_test1_p3.json data/reading_study/ielts15_test2_p3.json
```

B. 双跑（generate.py对AUDIT/source完整快照执行下列命令两次，并分别复制四文件到first/second）：

```sh
"$GRAMMAR_PY" "$AUDIT_ROOT/generate.py"
# 两次子进程的cwd均为$AUDIT_ROOT/source：
"$GRAMMAR_PY" scripts/generate_grammar_candidates.py --seed 20261018
```

C–F. 独立比较、结构验证、反事实与扫描：

```sh
"$GRAMMAR_PY" "$AUDIT_ROOT/audit_runtime.py"
"$GRAMMAR_PY" "$AUDIT_ROOT/audit_data.py"
"$GRAMMAR_PY" "$AUDIT_ROOT/probes.py"
"$GRAMMAR_PY" "$AUDIT_ROOT/negative_tests.py"
"$GRAMMAR_PY" "$AUDIT_ROOT/focus.py"
"$GRAMMAR_PY" "$AUDIT_ROOT/scan_categories.py"
"$GRAMMAR_PY" "$AUDIT_ROOT/scan_edges.py"
"$GRAMMAR_PY" "$AUDIT_ROOT/inspect_issues.py"
"$GRAMMAR_PY" "$AUDIT_ROOT/prepare_judgments.py"
```

其中audit_data直接调用build_reading_test_practice.build_tests(raw,'jijing')，localize_image只替换为同规则的确定性本地相对路径函数，避免下载；按passage_id比较171篇完整content/groups。重渲染命令（cwd=AUDIT/source）：

```sh
"$GRAMMAR_PY" scripts/render_grammar_graph_review.py
```

G. 专项和改动文件检查（cwd=REVIEW_ROOT）：

```sh
"$GRAMMAR_PY" -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary tests.test_grammar_graph_draft -v
"$APP_PY" -m unittest tests.test_reading_study -v
"$GRAMMAR_PY" scripts/validate_reading_study.py
"$GRAMMAR_PY" scripts/reading_jijing_text_fixes.py --check
"$NODE_BIN" tests/test_dictation_spell_queue.js
"$APP_PY" -m ruff check --config 'extend-exclude=[]' scripts/grammar_items/checks.py scripts/grammar_items/reporting.py scripts/grammar_items/templates.py tests/test_grammar_item_candidates.py
"$APP_PY" -m ruff format --check --config 'extend-exclude=[]' scripts/grammar_items/checks.py scripts/grammar_items/reporting.py scripts/grammar_items/templates.py tests/test_grammar_item_candidates.py
```

H. 新Flask-only环境和CI原列表：

```sh
"$GRAMMAR_PY" -m venv "$AUDIT_ROOT/flask-only"
"$AUDIT_ROOT/flask-only/bin/python" -m pip install --cert /etc/ssl/cert.pem Flask
"$AUDIT_ROOT/flask-only/bin/python" -m pip list
"$AUDIT_ROOT/flask-only/bin/python" -m unittest  tests.test_miniprogram_guest_access tests.test_miniprogram_dictation_grouping  tests.test_inventory_toefl_materials tests.test_organize_toefl_materials  tests.test_extract_toefl_answer_keys tests.test_map_toefl_answers_to_practice_docs  tests.test_import_toefl_official_reading tests.test_reading_vocab_grading  tests.test_stats_utils tests.test_grammar_graph_draft tests.test_grammar_item_candidates  tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary -v
```

I. 完整快照临时导入（数据库只在AUDIT/main-to-current.sqlite）：

```sh
"$APP_PY" "$AUDIT_ROOT/import_snapshot.py" "$AUDIT_ROOT/main" main
"$APP_PY" "$AUDIT_ROOT/import_snapshot.py" "$AUDIT_ROOT/baseline" round9 dry
"$APP_PY" "$AUDIT_ROOT/import_snapshot.py" "$AUDIT_ROOT/source" round10
```

J. 不依赖本机扫描脚本也可重现错误核心（在生成过候选的快照根运行）：

```python
import json
from pathlib import Path
rows = [json.loads(x) for x in Path('output/grammar_items/candidates_v0_2.jsonl').read_text().splitlines()]
ids = {'gi_v02_d3ad4b5fc6b8', 'gi_v02_facbcdde7ef5',
       'gi_v02_39a5639ec9f7', 'gi_v02_1213768264f6',
       'gi_v02_50bd636fe569', 'gi_v02_45648a820455'}
for i in rows:
    if i['item_id'] in ids:
        print(i['item_id'], i['status'], i['source']['sentence'])
        print(i['answer'], i['target'], i['distractors'])
```

## 12. 交付、CI与限制

本机审计材料：`/Users/zhouxin/.codex/audits/grammar-v02-round10-20261027`。包含完整固定快照、两个生成目录、统计JSON、120题及所有降级明细、词性/边界扫描、真实与手工控制例、负测日志、临时SQLite。它们不随Git交付；本报告给出了全部已确认问题题号、抽样方法、结果和SHA。

截至报告正文落盘，代码/数据仍固定8a0660b，新增只有本报告及两交接；报告将按用户授权提交并只推任务分支，不含skip-ci。GitHub CI待推送后按同一headSha核实，test与advisory lint分开补记。没有推main、PR、部署、生产操作、调用大模型API或小程序上传/提审/发布。

与提示不一致/范围限制：无因权限或环境而省略的指定检查；使用同Mac指定环境的仓库外快照及已有解析缓存，保护被审文件。两报告的Python行差异符合预期。W1缺少and/or字面排除、W4入口不限when已记X4；W1两个负测接口错误实际为缺Reason常量，不是函数。其余数字与提示预期吻合。新增3项内容问题使总体验收不通过，但不否认W1–W4点名修复已奏效。未替用户实施修复。
