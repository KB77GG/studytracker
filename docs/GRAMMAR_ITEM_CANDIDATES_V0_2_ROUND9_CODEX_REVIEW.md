# 语法候选题 v0.2 第九轮独立复审（Codex）

审核日期：2026-10-27（Asia/Shanghai）。**结论：不通过，以剑桥题为准。** 第八轮 **V1、V3 点名修复关闭**；本轮独立发现 **0 阻断、4 应修（W1–W4）、2 建议（W5–W6）**。这些应修均有剑桥自动通过题实例，并非机经问题，也不是断言由第九轮代码新引入。自动测试通过不能代替内容验收。

只审核 `3b7efb37822f38ca973767183d54c8ca75e5e418..76aeb1251d951393d256dd8900a2340644ba332e`。工作树 `/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker`，分支 `codex/grammar-item-candidates`；开工干净，先读入口约定和交接，再 fetch / fast-forward 到指定 HEAD。没有合并 main 或后续 Claude 提交，没有 rebase。只新增本报告并更新 CODEX_HANDOFF、WORKLOG；被审代码、数据和交付文件未修改。

范围与语法判断须区分：下文“局部答案成立”不保证题干唯一；“有并列关系”不排除它同时是宾语/定语/状语从句。把后一类目标送进互斥单选，恰是 W1 的问题。W3 的局部答案正确，问题是整句未经说明就给学生使用。所有待复核题单列，不计入自动题正确率。

## 前审关闭情况

| 编号 | 状态 | 独立核对 |
| --- | --- | --- |
| V1 | 关闭点名问题及本轮同类修复 | 6句改为表语从句合理，难点同步；旧标注上单独应用新规则确使7道auto降级。H-04原3道错误类别题不再auto。全库be挂靠、上下文及说明交叉扫描没有另确认同型表语从句仍作为状语从句auto；不等于所有从句类别均正确，见W1/W4。 |
| V3 | 关闭文档问题 | FIXES:455明确summary/target_para不显示，Q27解析/中心句在网页复盘卡显示。真实Q27调用renderReviewCard的analysisVisible、centralVisible均为true；没有进入生产环境。错误解析数据仍按用户决定暂缓。 |

## 10项检查结果

| 项 | 结果 | 实测与证据 |
| --- | --- | --- |
| 1 | 通过 | 18文件、757插入/511删除；授权外0。6解析文件只改指定句structure/difficult_points，句数及其他对象完全相同。raw、static全目录、修订表、models/app、api、小程序、workflows均无diff。 |
| 2 | 点名修复通过 | 6句/说明正确；相邻be检查避开前置及插入条件句。反事实仅检查裸be会额外误降10句24题；收紧后无此额外降级。旧标注反事实V1降7道。候选减少的T6表语内谓语符合既定白名单，是覆盖损失而非答案错误，可接受。详见规则复核。 |
| 3 | 通过 | 文档更正与静态调用链及真实数据纯函数渲染一致。 |
| 4 | 完成 | 指定60题全部找到；当前59auto局部答案/高亮/干扰项可成立，1needs（century before）存在合理类别争议。当前状态不能写成“60道auto全部正确”。逐题表见后。 |
| 5 | 完成；有保守误降和漏网 | 全库40降级/剑桥22吻合。22题中13题有合理复核疑点；9题是正常if/while/比较状语从句，保守误降可接受但需披露（W5）。另有年龄短语后when两道auto漏入，见W4。 |
| 6 | 完成；不通过 | seed20261030，剑桥auto每模板20，共120：给定局部答案120均可成立；其中1道T1题干/判分不成立（W2），119未发现新的局部/题干问题，原句120均可阅读。全池定向扫描另发现W1–W4；未将随机样本外的发现混入120分母。 |
| 7 | 总量通过；差分叙述须细化 | 50248→50243、−22/+17、auto40572（剑桥28029），各模板准确。实际共同题号只有41道状态改变：40 noun原因+1主语题歧义；7道V1是固定旧标注的规则反事实，不能与最终共有题计数混用。另1题干扰项roles元数据变化，见W6。 |
| 8 | 通过 | Mac双跑四文件字节一致；JSONL/XLSX与提交完全一致；两报告唯一差Python版本一行。13句×6模板回归对象全等；7过滤吻合。表内剑桥233=196auto+37needs，机经127=104auto+23needs。7工作表、6×60行、盲审、H2:H61四项下拉验证通过。 |
| 9 | 通过 | 专项106；新Flask-only完整轻量列表174运行/173通过/1按设计跳过；Node通过；reading22；validator317篇0错误、text --check=0；171篇raw内存重建content含summary/groups字节序列化前对象一致；图谱重生成字节一致；4改动Python Ruff check/format通过。5新测试对旧代码2断言失败/3反例通过、0接口错误。 |
| 10 | 通过 | main676569c完整快照先导created317，再导76aeb12：updated236/skipped81/failed0，最终317行；数据库仅AUDIT下临时SQLite。 |

## 剑桥问题清单

### W1 — 应修：并列关系与从句功能混为互斥选项，17道T3自动题需要复核

位置：`scripts/grammar_items/templates.py:423` 的 `type_matches`；`TYPE_OPTIONS`；具体题号/来源见“并列目标定向扫描”表中17个“需复核”目标。当前只要求 `conj`、自身主语、直接mark不含从属连词；wh词常是advmod/dobj等，省略的共享从属标记又不在第二分句子节点里，因而通过。

最明确的5例：

- `ielts12_test5_p1 C-04`，`gi_v02_0bd648f0066e`：`why today it accounts ...`与前一个why从句并列，同作explains的宾语，仍是名词性从句。
- 同篇D-07，`gi_v02_cced38be072a`：`when the air is damp`与`when it's too cold`并列，修饰a day，定语从句分析成立。
- `ielts16_test1_p2 E-05`，`gi_v02_d01f41961eff`：`what they were supposed to represent`与why从句同作on的宾语。
- `ielts16_test2_p3 J-02`，`gi_v02_60cb6a4601fa`：两个how从句都是形式主语it对应的内容；第二项仍是名词性从句。
- `ielts6_test3_p2 A-05`，`gi_v02_23f3ec6f71a5`：`where there is independence and feedback`与when从句并列，仍承担条件/情境状语作用。

其余12例为共享as/because/so that/until/that等管辖的第二分句，说明及全部ID在表中。**不是说从属从句不能并列**：它们确实可以并列。问题是T3用`exact_option`把“并列分句”与“名词性/状语/定语从句”互斥；选了正确的功能类别会判错。项目G-C02目标“识别平级分句”也不能消除这个分类轴重叠。Cambridge的[Clauses: coordinated](https://dictionary.cambridge.org/grammar/british-grammar/clauses)明确区分主句、从句、非限定从句各自的同类并列，支持这一点。

复现：生成池取上述ID，全部`auto_pass`、答案`并列分句`、判分`exact_option`。追溯其conj祖先与控制它的从属结构，人工恢复共享引导词/wh词功能。全剑桥auto中筛到79道T2/T3、44个目标；17个目标的T3需改成待审或消除单选重叠，其他27个未确认此类问题。没有把79道全判错；T2只要求找并列成员时可有合理分析，未把关联T2全部计成错误题。

建议：明确题型考查的是从句功能还是并列关系；在现有互斥选项下，对嵌套/共享从属结构保守降级，或分别设计题干。wh词和祖先作用域不能只靠直接mark检查。修正相关标注与说明的一致性，补以上真实例和引语内正常并列的反例，不按ID屏蔽。

### W2 — 应修：两个独立分句仍生成“唯一主句”题，10道T1和7道T5自动通过

位置：`scripts/grammar_items/templates.py:375`、`:584`，以及下表来源标注。T1/T5依赖恰好一个一级谓语标签和解析器ROOT；第一独立分句被包进非谓语类以外的整体标签、解析器将其当parataxis等时，第二分句ROOT会单独通过。

随机120中的`gi_v02_5690b731fad2`（ielts17_test1_p2 E-06）原句为：`There have been many examples of this in the UK: the mixed-use facilities at Wembley and Old Trafford have become a blueprint for many other stadiums in the world.` 两边都是独立分句，have been与have become都是对应分句谓语。当前T1只接受后者；关联T5只接受后一个主语。局部给定答案本身正确，但“这句话的主句谓语/完整主语”不唯一。原句可以阅读，不应整句封禁。

对全部剑桥auto T1中含冒号/分号的109题逐条看上下文，确认以下10句有这一问题；没有把题目引用、名词列举、冒号引出同位/解释内容等其余99题一律判错。

| 来源 | 被忽略的前分句谓语 | 当前T1答案/题号 | 关联T5题号 |
| --- | --- | --- | --- |
| ielts12_test8_p2 E-02 | would ... boost | could / not / be / gi_v02_fa5a06f81026 | gi_v02_ec4d82f4d263 |
| ielts13_test4_p2 B-06 | store | costs / gi_v02_88f13fac6658 | gi_v02_e76742369569 |
| ielts14_test3_p3 F-04 | is | are / gi_v02_d5e448590295 | gi_v02_5be941a91aed |
| ielts14_test3_p3 F-07 | is ... engaged | must / be / gi_v02_2e69d0c43c2e | gi_v02_cf9221c3ec44 |
| ielts17_test1_p2 E-06 | have been | have / become / gi_v02_5690b731fad2 | gi_v02_3d42601b8d9c |
| ielts20_test2_p3 A-03 | looked | was / mounted / gi_v02_45903e2a439d | 无auto T5 |
| ielts4_test3_p2 C-04 | is | inch / gi_v02_039e5b6e4241 | gi_v02_2a33047fcd6c |
| ielts5_test4_p1 A-03 | is | requires / gi_v02_99249b0927cf | 无auto T5 |
| ielts6_test4_p3 E-08 | may ... have | should / be / gi_v02_fc21ccd2630c | 无auto T5 |
| ielts8_test2_p3 F-03 | are invested | may / be / gi_v02_4445ed6322d4 | gi_v02_bdd363f085d7 |

复现：取表中题号与原句，对照T1的`grading.required_root`及T5唯一答案；选择前分句谓语不会包含当前required_root。建议校正多独立分句标注，通用检测后不出单一主句T1/T5或明确限定“冒号/分号后这一分句”。不要用“含冒号即排除”代替句法判断。T6已经指定目标动词，其局部主句身份可能仍成立，本项未把这些T6连坐。

### W3 — 应修：两句分号后的非限定结构漏出自动池，6道局部正确题不宜无说明给学生

位置：`data/reading_study/ielts15_test1_p3.json` F-04、`ielts7_test3_p1.json` B-07；通用传播入口`checks.py:164`。

- F-04：`They each set their own particular criteria; the common factor in their approach being that ...`。难点已经说“分号后不是完整谓语句”，但未明确当前分号的规范问题、未加前缀。
- B-07：`Only basic instincts are carried in the genes of a newborn baby; other skills being learned ...`。being learned也是非限定独立主格，不能单凭“独立主格合法”解释当前分号。

这与前审已处理44_29_p2 E-03同型：分号连接独立分句时需要有限定谓语，独立主格可作为附加结构但通常用逗号衔接。[Purdue分号说明](https://owl.purdue.edu/owl/general_writing/punctuation/commas/commas_vs_semicolons.html)支持此标准。这里不要求修改剑桥原文，也不把独立主格本身判错；在本项目面向学生的完整规范例句要求下，应说明标点/结构关系并待审，不能裸称整句无问题。

| 来源 | 题号 | 模板 | 局部/整句 |
| --- | --- | --- | --- |
| ielts15_test1_p3 F-04 | gi_v02_7b702aabb705 | T2 | 局部答案/高亮成立；原句需说明后使用 |
| ielts15_test1_p3 F-04 | gi_v02_9ab094841299 | T3 | 局部答案/高亮成立；原句需说明后使用 |
| ielts15_test1_p3 F-04 | gi_v02_237c28eb99a6 | T6 | 局部答案/高亮成立；原句需说明后使用 |
| ielts7_test3_p1 B-07 | gi_v02_604e3328ad97 | T2 | 局部答案/高亮成立；原句需说明后使用 |
| ielts7_test3_p1 B-07 | gi_v02_c88af5a29c0e | T3 | 局部答案/高亮成立；原句需说明后使用 |
| ielts7_test3_p1 B-07 | gi_v02_10587d4ba8fd | T6 | 局部答案/高亮成立；原句需说明后使用 |

复现：筛剑桥auto来源中分号后含being，去重2句，6题均auto且无source_quality。建议在难点准确描述实际问题并通过既有通用前缀传播，或制定适用于此类原文的教师审核状态；不按句号ID黑名单，也不机械拒绝所有独立主格。

### W4 — 应修：年龄表达后的when仍只当状语从句自动通过，2题存在未排除的类别歧义

位置：`ielts15_test2_p3 A-01`；`templates.py:201`及possible_relative_adverb的相邻词检查。原句：`Humans start developing a sense of humour as early as six weeks old, when babies begin to laugh and smile in response to stimuli.`

`when ...`可解释为补充说明six weeks old所指年龄/时间（at which age/time），是非限制性关系从句分析的真实候选，不能只因解析器advcl就确定“状语从句”。当前挂靠在old/ADJ，前一词也是old；既不触发名词挂靠，也不触发紧邻名词的关系副词风险。关系副词when可回指时间的分析依据见[QMUL Academic English: Relative Clauses](https://aeo.sllf.qmul.ac.uk/grammar/relative-clauses/)。这是本报告对本句的语法判断，来源并没有审核这道题。

| 题号 | 模板/状态 | 问题 |
| --- | --- | --- |
| gi_v02_7e2180fd8faf | T2 / auto_pass | 给定边界完整，但预设它确定是状语从句。 |
| gi_v02_7b4122b362c5 | T3 / auto_pass | 唯一答案“状语从句”，未排除“定语从句”的合理分析。 |

本项不宣称所有逗号后的when都必为定语从句，建议至少待审此类“时间/年龄表达 + when”；通用风险应看完整前导短语而非只看一个POS。不要把所有ADJ挂靠均降级（其余3个ADJ挂靠目标是正常比较/条件状语）。本句其余5道auto局部答案可成立，不需整句降级。

### W5 — 建议：noun_attached_clause是保守筛选，不是名词挂靠即定语从句的证明

位置`templates.py:201`。22道剑桥降级题里，9道/4句仍是正常状语：ielts7_test2_p3 D-17的if条件（3题）、ielts7_test1_p3 D-13的while时间（2题）、ielts10_test2_p3 H-03和ielts16_test2_p3 G-03的than比较（各2题）。解析器挂到名词不等于实际句法功能改变。按这22题全集计算保守误降9/22=40.9%，不能外推全池比例。

只降为待复核、没有删题或改答案，符合本轮精度优先，可保留；教师应按整句判断，不把原因码视为错误判定。以后若优化召回，加入明确比较结构和普通if/while反例。其余13题也只是复核理由成立，并非证明13题全是定语从句。逐题表见后。

### W6 — 建议：第九轮统计需区分规则反事实与最终候选差分

位置`docs/GRAMMAR_ITEM_CANDIDATES_V0_2_FIXES.md:486`，被审交接第九轮“其余题目内容不变”的句子。

- 固定旧标注，仅换新规则：7道V1 + 40道noun降级，47这个数可复现。
- 最终池按item_id连接：共同ID只有41道auto→needs（40 noun + `gi_v02_76d0fac987f7` T5 ambiguous_span_location）；7道V1相关旧ID已随改标被替换/删除，不能算作共有题状态变化。
- −22=16auto+6needs；+17=3auto+14needs；40626−16+3−41=40572。
- 共有题另有`gi_v02_2af7bee3bda5`（H-04 T1）的两处`distractors.roles`从reason_clause改为predicative_clause；可见答案、高亮、干扰词范围没变，元数据确实变了。61个共有对象的reasons改变，不仅41个status改变。

建议以后用上面三种口径分别报告。本轮只在获准报告/交接中澄清，不修改被审FIXES。

## 机经（暂缓）

本轮**新增机经问题0**；用户明确指定的既有暂缓数据问题为**4处：V2三处排印 + 第27题错误解析**，不计本轮阻断/应修数量，不重复展开。84_73_p1等更早遗留仍以原报告为准，此处没有声称历史机经问题总计只有4处。V4列表边界、V5定位选项互斥仍按用户决定暂缓；没有改规则。机经18道noun降级只做数量验证，不将它们作为本轮剑桥人工审核结论。

## 规则与数据复核细节

`predicative_clause()`仅在advcl中心挂be、be无attr/acomp/oprd/ccomp/xcomp/prep/dobj等另一补足语、从句位于be之后且间隔词均在副词白名单时生效。`It was cold because ...`保留普通原因状语，前置if/when不误判。当前白名单是启发式，不覆盖任意插入语、未知副词或别的系词；未把本次未找到漏网写成理论完备。

实际读取全部**12,746句**（本轮6文件不改句数），取所有advcl挂be共780子树，规则命中41（剑桥32）。这些包括已有表语/非限定补足结构，不能把41当作“41道错误题”。再检查剑桥auto adverbial紧邻be的151题/75目标、说明含“表语”的46题/22目标，未确认同型表语漏判。裸be反事实会比当前规则多降10句24题，其中包括前置及插入/后置if，不能把所有10句笼统称“前置”。所有反事实仅在内存替换函数，未改被审文件。

| 改标来源 | 内容判定 |
| --- | --- |
| ielts11_test1_p2 E-04 | because作be的表语、说明原因；结构/层级和新难点可成立，其他字段不变 |
| ielts11_test4_p2 B-05 | because作be的表语、说明原因；结构/层级和新难点可成立，其他字段不变 |
| ielts16_test3_p2 H-04 | because作be的表语、说明原因；结构/层级和新难点可成立，其他字段不变 |
| ielts19_test4_p1 I-03 | because作be的表语、说明原因；结构/层级和新难点可成立，其他字段不变 |
| ielts4_test3_p2 D-02 | because作be的表语、说明原因；结构/层级和新难点可成立，其他字段不变 |
| ielts17_test1_p3 D-02 | because作be的表语、说明原因；结构/层级和新难点可成立，其他字段不变 |

同库ielts9_test4_p2 C-06、ielts16_test4_p1 E-04的既有表语标注一致。17_1_p3 D-02两个because也是并列表语；其整体complement_clause为存量标签，此轮改动不制造新题。改标后不再出表语内T6谓语身份，是计划T6只取定语/状语中心的覆盖限制，接受此取舍；表语T2/T3被解析器advcl判不一致时待审，也符合“答案来自标注，解析器复核”的既定机制。新增17题中3auto为非谓语/介词短语题，均可成立；14needs中有正确类别但解析不合者，也有空主语范围等不宜自动题，未算成全正确。

全剑桥自动池定向扫描（输入28029题，按目标去重后阅读上下文）：

| 扫描 | 题数/去重目标或句数 | 判断 |
| --- | --- | --- |
| be邻近 | 151 / 75目标 | 未确认额外表语被当状语auto |
| 说明含表语 | 46 / 22目标 | 多为同句另有真正状语，未按关键词错杀 |
| as开头状语目标 | 278 / 151目标 | 未一概当成定语从句；包括时间/原因/比较/评注。As we have seen等存在教学分析体系差异，不另报确定错误 |
| 并列中心位于从属祖先中 | 79 / 44目标 | 17个T3有分类轴冲突(W1)，27目标未确认同类问题，逐目标表见后 |
| advcl挂ADJ/ADV/ADP | 7 / 4目标 | W4一个目标两题需审；其余比较/条件正常 |
| before/after/since/until前一非标点词为名词类 | 74 / 38目标 | 大多数修饰谓语，不宜全降；matter of time before有可讨论分析，未另定为错误；与实现方约74的结论方向一致，但不声称两个抽取器完全同口径 |
| that/what/which/who/whether开头状语 | 20 / 11来源 | 实际均为whether让步/选择结构，未见类别新错 |
| auto T1带冒号/分号 | 109 / 109句 | 10句有多独立分句却唯一主句题(W2)；其余不机械判错 |
| 分号后being | 6 / 2句 | W3，独立主格本身成立，但当前标点/呈现方式须复核 |

as评注结构未硬判“错误”：British Council对[as she mentioned / as was mentioned](https://learnenglish.britishcouncil.org/free-resources/grammar/b1-b2/relative-clauses-non-defining-relative-clauses)的讨论允许状语分析。因此不能把中文教学中常用的as非限制性定语标签当唯一体系；本报告的应修限于有具体判分/前提冲突或真实呈现风险的题。

## 第4项：指定60题逐题复核

顺序严格按用户给出的T1–T6 ID列表。表内“成立”表示给定答案、目标/动词单位高亮、所列干扰项和题干前提在本次阅读中可成立；原句均可阅读。不以当前59auto+1needs冒称60auto。第19题的for different weather systems可外接adjusting，因此当前关系从句范围可成立；若教师选另一挂靠应复核，不把解析器选择当唯一语义。

| 序 | 题号 | 模板 | 来源 | 当前状态 | 局部/题干 | 原句 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_25e1e8cd2f07 | T1 | ielts11_test4_p2 I-01 | auto_pass | 成立 | 可阅读 |
| 2 | gi_v02_0c84c3b73f22 | T1 | ielts12_test6_p3 C-03 | auto_pass | 成立 | 可阅读 |
| 3 | gi_v02_d2df2d43f22a | T1 | ielts7_test3_p3 D-31 | auto_pass | 成立 | 可阅读 |
| 4 | gi_v02_1ffaa8ded8ad | T1 | ielts15_test2_p1 B-01 | auto_pass | 成立 | 可阅读 |
| 5 | gi_v02_3085a3ab4279 | T1 | ielts20_test4_p2 D-21 | auto_pass | 成立 | 可阅读 |
| 6 | gi_v02_9b017b7e9b49 | T1 | ielts9_test1_p2 D-28 | auto_pass | 成立 | 可阅读 |
| 7 | gi_v02_2fce45016970 | T1 | ielts17_test4_p3 E-05 | auto_pass | 成立 | 可阅读 |
| 8 | gi_v02_67d77e1fcd58 | T1 | ielts15_test1_p1 F-02 | auto_pass | 成立 | 可阅读 |
| 9 | gi_v02_18bfdc17350b | T1 | ielts5_test4_p1 C-28 | auto_pass | 成立 | 可阅读 |
| 10 | gi_v02_3a9a831b1649 | T1 | ielts13_test1_p2 F-01 | auto_pass | 成立 | 可阅读 |
| 11 | gi_v02_06e81ae713f6 | T2 | ielts11_test4_p2 A-05 | auto_pass | 成立 | 可阅读 |
| 12 | gi_v02_078c9cc86e0f | T2 | ielts14_test1_p3 F-03 | auto_pass | 成立 | 可阅读 |
| 13 | gi_v02_a0f2df7cc7c7 | T2 | ielts4_test1_p1 K-01 | auto_pass | 成立 | 可阅读 |
| 14 | gi_v02_8aa29071970e | T2 | ielts17_test4_p2 D-07 | auto_pass | 成立 | 可阅读 |
| 15 | gi_v02_8a32f8b12f8d | T2 | ielts6_test3_p3 H-31 | auto_pass | 成立 | 可阅读 |
| 16 | gi_v02_b4c35ae6a851 | T2 | ielts5_test2_p2 H-31 | auto_pass | 成立 | 可阅读 |
| 17 | gi_v02_0cd7f126d3ee | T2 | ielts16_test3_p3 F-02 | auto_pass | 成立 | 可阅读 |
| 18 | gi_v02_1882947d282b | T2 | ielts6_test3_p3 F-22 | auto_pass | 成立 | 可阅读 |
| 19 | gi_v02_f0b2f38eac31 | T2 | ielts13_test3_p3 G-02 | auto_pass | 成立；PP可外接adjusting | 可阅读 |
| 20 | gi_v02_8d90646a5159 | T2 | ielts11_test3_p3 B-06 | auto_pass | 成立 | 可阅读 |
| 21 | gi_v02_7615892876c0 | T3 | ielts5_test1_p1 A-01 | needs_review | 待审：before修饰century有类别争议 | 可阅读 |
| 22 | gi_v02_f90956730604 | T3 | ielts15_test3_p3 A-03 | auto_pass | 成立 | 可阅读 |
| 23 | gi_v02_684e631bf59e | T3 | ielts17_test1_p2 B-01 | auto_pass | 成立 | 可阅读 |
| 24 | gi_v02_814c06dd647d | T3 | ielts12_test8_p2 D-02 | auto_pass | 成立 | 可阅读 |
| 25 | gi_v02_c2db85be5311 | T3 | ielts12_test5_p1 E-06 | auto_pass | 成立 | 可阅读 |
| 26 | gi_v02_583244cd49b8 | T3 | ielts17_test3_p2 G-01 | auto_pass | 成立 | 可阅读 |
| 27 | gi_v02_656a7b7a7928 | T3 | ielts19_test1_p2 D-06 | auto_pass | 成立 | 可阅读 |
| 28 | gi_v02_f3b59c649dbc | T3 | ielts5_test4_p2 J-40 | auto_pass | 成立 | 可阅读 |
| 29 | gi_v02_a4d565fca760 | T3 | ielts8_test3_p3 G-43 | auto_pass | 成立 | 可阅读 |
| 30 | gi_v02_cd0f64e9f6ee | T3 | ielts10_test4_p3 E-05 | auto_pass | 成立 | 可阅读 |
| 31 | gi_v02_253f3c0d8c9b | T4 | ielts9_test4_p2 G-04 | auto_pass | 成立 | 可阅读 |
| 32 | gi_v02_596d4f08542a | T4 | ielts16_test1_p1 D-05 | auto_pass | 成立 | 可阅读 |
| 33 | gi_v02_8011157bad1a | T4 | ielts8_test3_p1 H-05 | auto_pass | 成立 | 可阅读 |
| 34 | gi_v02_7028667a6d36 | T4 | ielts18_test3_p3 F-05 | auto_pass | 成立 | 可阅读 |
| 35 | gi_v02_1b52f7fdd1d5 | T4 | ielts7_test2_p1 A-05 | auto_pass | 成立 | 可阅读 |
| 36 | gi_v02_03d993c9864f | T4 | ielts19_test4_p3 F-05 | auto_pass | 成立 | 可阅读 |
| 37 | gi_v02_241a8109b046 | T4 | ielts7_test4_p3 B-01 | auto_pass | 成立 | 可阅读 |
| 38 | gi_v02_e2080683cbad | T4 | ielts19_test1_p2 G-06 | auto_pass | 成立 | 可阅读 |
| 39 | gi_v02_45ff223cfc7b | T4 | ielts20_test2_p3 B-07 | auto_pass | 成立 | 可阅读 |
| 40 | gi_v02_5cb5e07fd58b | T4 | ielts7_test2_p1 D-15 | auto_pass | 成立 | 可阅读 |
| 41 | gi_v02_591c0a74c90c | T5 | ielts9_test2_p2 A-03 | auto_pass | 成立 | 可阅读 |
| 42 | gi_v02_a26361e2b04e | T5 | ielts5_test3_p3 C-16 | auto_pass | 成立 | 可阅读 |
| 43 | gi_v02_bb1ab9e4aee4 | T5 | ielts8_test4_p1 C-03 | auto_pass | 成立 | 可阅读 |
| 44 | gi_v02_9ae67bbd53dc | T5 | ielts7_test1_p1 C-02 | auto_pass | 成立 | 可阅读 |
| 45 | gi_v02_b4e300c00ca4 | T5 | ielts19_test3_p2 E-03 | auto_pass | 成立 | 可阅读 |
| 46 | gi_v02_36d45affb0c6 | T5 | ielts15_test2_p2 A-05 | auto_pass | 成立 | 可阅读 |
| 47 | gi_v02_4ec96e1b4236 | T5 | ielts19_test3_p2 C-01 | auto_pass | 成立 | 可阅读 |
| 48 | gi_v02_17f358955bcd | T5 | ielts20_test2_p2 E-31 | auto_pass | 成立 | 可阅读 |
| 49 | gi_v02_58cdfa66707b | T5 | ielts9_test1_p1 E-04 | auto_pass | 成立 | 可阅读 |
| 50 | gi_v02_2b3787831a45 | T5 | ielts13_test2_p1 C-05 | auto_pass | 成立 | 可阅读 |
| 51 | gi_v02_fac79d4ca595 | T6 | ielts16_test3_p2 F-04 | auto_pass | 成立 | 可阅读 |
| 52 | gi_v02_bc10b3d0e0e1 | T6 | ielts16_test3_p3 C-02 | auto_pass | 成立 | 可阅读 |
| 53 | gi_v02_9c0673df9f36 | T6 | ielts10_test4_p3 B-02 | auto_pass | 成立 | 可阅读 |
| 54 | gi_v02_b0c2db6d70cc | T6 | ielts4_test1_p1 D-03 | auto_pass | 成立 | 可阅读 |
| 55 | gi_v02_2f3cef9512f4 | T6 | ielts8_test3_p1 J-04 | auto_pass | 成立 | 可阅读 |
| 56 | gi_v02_b92d4e75aaca | T6 | ielts6_test4_p2 E-12 | auto_pass | 成立 | 可阅读 |
| 57 | gi_v02_b95a574190e4 | T6 | ielts10_test4_p1 E-02 | auto_pass | 成立 | 可阅读 |
| 58 | gi_v02_9e06dd6972b7 | T6 | ielts16_test3_p1 A-02 | auto_pass | 成立 | 可阅读 |
| 59 | gi_v02_aab97f0d9cc5 | T6 | ielts12_test7_p3 E-03 | auto_pass | 成立 | 可阅读 |
| 60 | gi_v02_cfd23e8d8f16 | T6 | ielts7_test3_p1 J-02 | auto_pass | 成立 | 可阅读 |

## 第5项：全部22道剑桥noun降级题

全部当前needs_review。13道降级理由合理，9道原答案可成立而被保守降级；源句22题均可阅读。比较从句仍可按本项目传统体系归比较状语，不能因解析器noun挂靠就改成定语。

| 序 | 题号 | 模板 | 来源 | 状态 | 局部/降级判断 |
| --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_1c5fee6c5425 | T4 | ielts8_test2_p2 C-03 | needs_review | 复核合理：time before的名词修饰/时间关系待判 |
| 2 | gi_v02_21f5d2b040ad | T2 | ielts7_test2_p3 D-17 | needs_review | 答案可成立；保守误降：普通if条件状语 |
| 3 | gi_v02_573206ab9792 | T2 | ielts10_test2_p3 H-03 | needs_review | 答案可成立；保守误降：正常than比较状语 |
| 4 | gi_v02_66b065fe92ea | T3 | ielts8_test2_p2 C-03 | needs_review | 复核合理：同上time before |
| 5 | gi_v02_6d981dad7ca6 | T2 | ielts15_test2_p2 B-03 | needs_review | 复核合理：decades since的名词修饰关系待判 |
| 6 | gi_v02_7615892876c0 | T3 | ielts5_test1_p1 A-01 | needs_review | 复核合理：century before类别有争议 |
| 7 | gi_v02_7822d024d02c | T2 | ielts11_test2_p2 A-01 | needs_review | 复核合理：as it is known为补充命名/评注，需统一体系 |
| 8 | gi_v02_7bd12fc027b9 | T3 | ielts10_test2_p3 H-03 | needs_review | 答案可成立；保守误降：正常than比较状语 |
| 9 | gi_v02_81b7b81f5e74 | T3 | ielts15_test2_p2 B-03 | needs_review | 复核合理：decades since待判 |
| 10 | gi_v02_9404c52d4a5d | T3 | ielts11_test2_p2 A-01 | needs_review | 复核合理：as it is known待判 |
| 11 | gi_v02_960aa84fa6a4 | T2 | ielts5_test1_p1 A-01 | needs_review | 复核合理：century before待判 |
| 12 | gi_v02_ab52b079ac04 | T3 | ielts7_test1_p3 D-13 | needs_review | 答案可成立；保守误降：正常while时间状语 |
| 13 | gi_v02_b21cc9fe9bb9 | T2 | ielts7_test1_p3 D-13 | needs_review | 答案可成立；保守误降：正常while时间状语 |
| 14 | gi_v02_b78b28d74f7b | T2 | ielts16_test2_p3 G-03 | needs_review | 答案可成立；保守误降：正常than比较状语 |
| 15 | gi_v02_bc4c3449f101 | T3 | ielts17_test3_p2 H-01 | needs_review | 复核合理：as Ellwood describes them评注/关系分析待判 |
| 16 | gi_v02_c51b95a26134 | T3 | ielts12_test7_p2 E-03 | needs_review | 复核合理：as it relates限定方面/关系分析待判 |
| 17 | gi_v02_d177845d359a | T3 | ielts16_test2_p3 G-03 | needs_review | 答案可成立；保守误降：正常than比较状语 |
| 18 | gi_v02_d531c3c76a55 | T3 | ielts7_test2_p3 D-17 | needs_review | 答案可成立；保守误降：普通if条件状语 |
| 19 | gi_v02_d6f0d401aaca | T2 | ielts12_test7_p2 E-03 | needs_review | 复核合理：as it relates待判 |
| 20 | gi_v02_ee704a2ff83a | T2 | ielts17_test3_p2 H-01 | needs_review | 复核合理：as Ellwood describes them待判 |
| 21 | gi_v02_f12a8931874e | T2 | ielts8_test2_p2 C-03 | needs_review | 复核合理：time before待判 |
| 22 | gi_v02_f7c639d38957 | T4 | ielts7_test2_p3 D-17 | needs_review | 答案可成立；保守误降：普通if条件状语 |

## 第6项：独立随机120题

方法：全量候选中筛source_kind=reading_test、passage_id以ielts开头、status=auto_pass；按T1至T6处理，每模板先按item_id升序，用同一个`random.Random(20261030)`依次`sample(...,20)`。无放回、不沿用Claude种子20261027。此样本与指定60允许自然重叠，未为规避或制造结果而换种子。

120题给定的局部答案可成立，1道存在W2题干/判分前提问题；其余119未发现新的答案/高亮/干扰项问题。原句120均适合阅读。这个分层题目样本不是按句随机样本，也不是全库错误率估计。既有T2多目标建议A8仍开放，本次没有宣称证明全池唯一性。

| 序 | 题号 | 模板 | 来源 | 状态 | 答案/高亮/干扰项 | 题干/整句 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_8debec628f77 | T1 | ielts18_test3_p3 H-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 2 | gi_v02_389e15b18411 | T1 | ielts6_test1_p3 B-07 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 3 | gi_v02_91e89a937b1c | T1 | ielts19_test1_p1 A-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 4 | gi_v02_54f57f0c7857 | T1 | ielts5_test2_p1 D-13 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 5 | gi_v02_e2ec19bb1c67 | T1 | ielts12_test5_p3 B-05 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 6 | gi_v02_686434f1fb63 | T1 | ielts16_test4_p1 B-05 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 7 | gi_v02_093871177306 | T1 | ielts14_test3_p1 E-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 8 | gi_v02_c0503e0cbf0a | T1 | ielts8_test1_p1 E-04 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 9 | gi_v02_ced61c068943 | T1 | ielts15_test3_p1 C-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 10 | gi_v02_86321d92e084 | T1 | ielts8_test4_p3 D-06 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 11 | gi_v02_991ac9467130 | T1 | ielts7_test3_p1 G-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 12 | gi_v02_de253252455c | T1 | ielts12_test5_p1 E-05 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 13 | gi_v02_43527d6fcfd5 | T1 | ielts16_test4_p2 H-04 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 14 | gi_v02_a37d78ce4b4a | T1 | ielts12_test6_p2 F-06 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 15 | gi_v02_4560230c1986 | T1 | ielts18_test4_p1 C-07 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 16 | gi_v02_1e6b9f42672b | T1 | ielts6_test3_p3 A-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 17 | gi_v02_5690b731fad2 | T1 | ielts17_test1_p2 E-06 | auto_pass | 局部成立 | W2：多主句，题干/判分需改；原句可阅读 |
| 18 | gi_v02_49baf1367a5c | T1 | ielts7_test4_p2 F-05 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 19 | gi_v02_68b5dcf76338 | T1 | ielts15_test2_p2 E-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 20 | gi_v02_232b93659500 | T1 | ielts6_test2_p3 D-05 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 21 | gi_v02_da2b02a8d022 | T2 | ielts6_test2_p2 F-16 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 22 | gi_v02_328fa8677284 | T2 | ielts4_test1_p1 F-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 23 | gi_v02_360b8ce6d37c | T2 | ielts13_test1_p2 E-07 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 24 | gi_v02_197680b2ec09 | T2 | ielts7_test1_p1 A-05 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 25 | gi_v02_06d4920995ff | T2 | ielts18_test3_p3 A-07 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 26 | gi_v02_5dc3683d6f05 | T2 | ielts16_test3_p2 C-05 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 27 | gi_v02_2fe24b305749 | T2 | ielts6_test2_p1 C-13 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 28 | gi_v02_de8827aadb3f | T2 | ielts6_test1_p3 G-41 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 29 | gi_v02_731a83d97e9d | T2 | ielts5_test1_p3 F-20 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 30 | gi_v02_f561b9e3937b | T2 | ielts8_test3_p3 F-37 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 31 | gi_v02_9058b09d403e | T2 | ielts7_test3_p3 A-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 32 | gi_v02_b0248766aaf1 | T2 | ielts13_test2_p3 E-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 33 | gi_v02_898015198ec9 | T2 | ielts10_test4_p2 D-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 34 | gi_v02_6981f6766c1c | T2 | ielts18_test3_p2 C-04 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 35 | gi_v02_1ca8fd648fb8 | T2 | ielts11_test3_p1 D-04 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 36 | gi_v02_116b919d406b | T2 | ielts13_test3_p1 B-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 37 | gi_v02_9e60f21a5117 | T2 | ielts14_test2_p3 F-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 38 | gi_v02_6e1cce9b5d2d | T2 | ielts4_test2_p2 A-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 39 | gi_v02_820b117e2a76 | T2 | ielts10_test4_p3 E-04 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 40 | gi_v02_a1fef47f29da | T2 | ielts8_test3_p1 H-04 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 41 | gi_v02_5db5cba1fe1e | T3 | ielts6_test1_p3 F-33 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 42 | gi_v02_7a0881326110 | T3 | ielts9_test4_p1 K-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 43 | gi_v02_99c51b1c3006 | T3 | ielts10_test3_p1 E-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 44 | gi_v02_bdde8845d209 | T3 | ielts18_test3_p3 A-08 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 45 | gi_v02_4ef85ce86fa1 | T3 | ielts16_test2_p3 A-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 46 | gi_v02_5f09baee9674 | T3 | ielts9_test2_p1 C-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 47 | gi_v02_02d6501aa4fd | T3 | ielts20_test1_p1 J-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 48 | gi_v02_e6e23fd687aa | T3 | ielts13_test2_p3 C-08 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 49 | gi_v02_265e92f4433d | T3 | ielts12_test5_p2 G-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 50 | gi_v02_5b92cbb47415 | T3 | ielts20_test2_p2 B-11 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 51 | gi_v02_855d7f244ccd | T3 | ielts18_test4_p2 H-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 52 | gi_v02_f08e21de8a18 | T3 | ielts12_test7_p1 F-04 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 53 | gi_v02_65e2a5ac4c5f | T3 | ielts16_test4_p3 D-06 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 54 | gi_v02_42a738ef8685 | T3 | ielts19_test2_p1 H-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 55 | gi_v02_2b8de9ad3509 | T3 | ielts18_test2_p3 C-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 56 | gi_v02_342bea44be87 | T3 | ielts5_test1_p1 F-07 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 57 | gi_v02_f1ba0f7785dc | T3 | ielts15_test4_p3 B-05 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 58 | gi_v02_7ae12d78706a | T3 | ielts11_test4_p1 D-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 59 | gi_v02_25d025d1cb25 | T3 | ielts9_test3_p3 C-19 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 60 | gi_v02_fa65f20b6639 | T3 | ielts18_test1_p2 G-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 61 | gi_v02_85798ad7a59e | T4 | ielts13_test4_p3 D-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 62 | gi_v02_b74effb3a4a4 | T4 | ielts5_test4_p2 D-15 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 63 | gi_v02_c9c0708a2d16 | T4 | ielts12_test8_p2 H-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 64 | gi_v02_130f98d89646 | T4 | ielts9_test4_p2 D-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 65 | gi_v02_315ddcb542db | T4 | ielts5_test2_p1 G-30 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 66 | gi_v02_4f1d8c9e6e95 | T4 | ielts13_test4_p3 E-06 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 67 | gi_v02_1cb7a8ad8f61 | T4 | ielts9_test4_p2 G-05 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 68 | gi_v02_1a5108714938 | T4 | ielts6_test2_p2 G-23 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 69 | gi_v02_95e5ff5ea769 | T4 | ielts5_test4_p2 J-45b | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 70 | gi_v02_e46aa5ddd529 | T4 | ielts13_test4_p3 A-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 71 | gi_v02_81259412f14b | T4 | ielts20_test4_p2 D-19b | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 72 | gi_v02_19d70ab9f1b4 | T4 | ielts9_test2_p2 E-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 73 | gi_v02_ed10def280ce | T4 | ielts13_test4_p2 C-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 74 | gi_v02_e1a0d044006b | T4 | ielts6_test3_p2 B-05 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 75 | gi_v02_22c11d651099 | T4 | ielts15_test2_p1 F-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 76 | gi_v02_45ff223cfc7b | T4 | ielts20_test2_p3 B-07 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 77 | gi_v02_9ed4233cb9e3 | T4 | ielts6_test3_p2 B-06 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 78 | gi_v02_d1f93631029c | T4 | ielts8_test4_p2 G-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 79 | gi_v02_5d08c14a73b7 | T4 | ielts7_test4_p2 D-05 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 80 | gi_v02_4c972ce0bfc7 | T4 | ielts4_test2_p1 F-31 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 81 | gi_v02_db4e432606f0 | T5 | ielts14_test2_p3 A-07 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 82 | gi_v02_5b4ed1b7dd03 | T5 | ielts4_test3_p1 H-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 83 | gi_v02_1cac1bede731 | T5 | ielts6_test1_p1 B-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 84 | gi_v02_f3ee8efa45f4 | T5 | ielts16_test4_p1 A-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 85 | gi_v02_4fa7c6018aa2 | T5 | ielts15_test2_p2 A-04 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 86 | gi_v02_ab2e8851d444 | T5 | ielts6_test1_p1 A-06 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 87 | gi_v02_4ac242148b7e | T5 | ielts11_test2_p2 A-06 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 88 | gi_v02_ef2a6d0b37d0 | T5 | ielts10_test3_p3 B-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 89 | gi_v02_9579d9b1b008 | T5 | ielts13_test3_p1 D-04 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 90 | gi_v02_4f1f476638df | T5 | ielts10_test3_p3 A-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 91 | gi_v02_3a519788430d | T5 | ielts13_test4_p1 I-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 92 | gi_v02_95ff2753c3f0 | T5 | ielts16_test2_p1 D-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 93 | gi_v02_9a4356fdb016 | T5 | ielts16_test2_p3 A-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 94 | gi_v02_0ce609c2a8aa | T5 | ielts9_test4_p2 C-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 95 | gi_v02_4d232530a641 | T5 | ielts14_test1_p1 H-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 96 | gi_v02_66521ac38e26 | T5 | ielts20_test4_p3 F-28 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 97 | gi_v02_bf02e065c8ec | T5 | ielts13_test3_p3 D-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 98 | gi_v02_ed7cf8eb591d | T5 | ielts17_test4_p2 E-05 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 99 | gi_v02_2a30e2a5d827 | T5 | ielts11_test2_p1 F-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 100 | gi_v02_bacd77816766 | T5 | ielts5_test3_p1 C-06 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 101 | gi_v02_2806c82a6218 | T6 | ielts20_test1_p3 B-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 102 | gi_v02_13e8de9b2e3c | T6 | ielts16_test2_p3 E-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 103 | gi_v02_b27f00f009c7 | T6 | ielts20_test4_p1 G-20 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 104 | gi_v02_e0f660f1576d | T6 | ielts15_test1_p2 E-02 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 105 | gi_v02_da83d71533fa | T6 | ielts14_test2_p3 B-04 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 106 | gi_v02_4997f34933fd | T6 | ielts20_test3_p1 K-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 107 | gi_v02_9eaf38c150ea | T6 | ielts20_test2_p1 E-06 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 108 | gi_v02_06a70d639878 | T6 | ielts6_test2_p2 F-16 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 109 | gi_v02_151040b4e359 | T6 | ielts10_test4_p1 D-04 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 110 | gi_v02_b554e8cb665c | T6 | ielts10_test1_p1 B-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 111 | gi_v02_8d6dd7121cd6 | T6 | ielts7_test1_p3 F-25 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 112 | gi_v02_af50bffe65bb | T6 | ielts20_test4_p1 E-15 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 113 | gi_v02_cb52d5fbacf7 | T6 | ielts5_test3_p1 E-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 114 | gi_v02_2afc6bade43f | T6 | ielts5_test4_p2 E-17 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 115 | gi_v02_aeb0990486c8 | T6 | ielts10_test4_p1 A-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 116 | gi_v02_9ac59daaefb3 | T6 | ielts4_test4_p3 A-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 117 | gi_v02_4164ead1a2f2 | T6 | ielts20_test3_p3 A-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 118 | gi_v02_5f347a4d2da9 | T6 | ielts4_test3_p1 B-03 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 119 | gi_v02_b68052c764b6 | T6 | ielts17_test3_p3 C-04 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |
| 120 | gi_v02_5d0c3ee84a5b | T6 | ielts13_test3_p2 A-01 | auto_pass | 局部成立 | 此次未见新问题；原句可阅读 |

## 并列目标定向扫描明细

按全池原顺序去重(passsage_id, sentence_id, target.text)，共44目标/79题。下列“需复核”只将该目标的T3互斥单选计入W1，共17题；未把所有T2或所有conj一律判错。引语内两个完整主句可以正常并列；解析器祖先ccomp本身不证明出题错误。

| 序 | 来源 | T2/T3题号 | 目标 | 判断 |
| --- | --- | --- | --- | --- |
| 1 | ielts10_test1_p1 E-01 | T3:gi_v02_8d37d96a8c41 | the wells no longer reach the water table | 需复核：分类轴不互斥；as管辖两个原因分句 |
| 2 | ielts10_test1_p3 D-01 | T2:gi_v02_c324b643ee50<br>T3:gi_v02_639f4d1c3c98 | under that pressure we, as a species, behave differently | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 3 | ielts10_test1_p3 E-05 | T2:gi_v02_ff994a4069ff<br>T3:gi_v02_af4e1c611a73 | I'm going to take you with me | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 4 | ielts10_test3_p3 F-01 | T2:gi_v02_3d2a6007a572<br>T3:gi_v02_4f1586e5e1d4 | they had the ability to sail them | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 5 | ielts10_test4_p1 I-02 | T2:gi_v02_06e1e2f9ba92<br>T3:gi_v02_8c4d04bc06e4 | we were not able to communicate adequately with them | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 6 | ielts10_test4_p2 E-06 | T2:gi_v02_e51e03c47627<br>T3:gi_v02_da3ede52e68d | it wasn't anywhere near what I thought it was | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 7 | ielts10_test4_p3 A-03 | T3:gi_v02_ac9f8535a872 | modern genetics enters the scene | 需复核：分类轴不互斥；as管辖两个时间/原因分句 |
| 8 | ielts11_test2_p2 B-07 | T3:gi_v02_db4a94e67ec4 | they could no longer construct wooden canoes for fishing | 需复核：分类轴不互斥；as管辖两个原因分句 |
| 9 | ielts11_test2_p2 C-04 | T2:gi_v02_6aa39bfe587c<br>T3:gi_v02_006fc94977d5 | that required both a lot of wood and a lot of people | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 10 | ielts11_test3_p3 G-07 | T2:gi_v02_7bb7b9a7e2c5<br>T3:gi_v02_5098e4ecac73 | purely theoretical discoveries find unanticipated applications | 需复核：分类轴不互斥；as管辖questions与discoveries两个分句 |
| 11 | ielts12_test5_p1 C-04 | T2:gi_v02_000ff9f282b7<br>T3:gi_v02_0bd648f0066e | why today it accounts for roughly half of all cork production around the world | 需复核：分类轴不互斥；why从句与前一why从句并列，共同作explains的宾语 |
| 12 | ielts12_test5_p1 D-07 | T2:gi_v02_79669dcfa68c<br>T3:gi_v02_cced38be072a | when the air is damp | 需复核：分类轴不互斥；when从句修饰a day，不能与定语从句互斥 |
| 13 | ielts13_test1_p2 C-04 | T2:gi_v02_940ff66626a3<br>T3:gi_v02_afcf87117d94 | in actual fact it can lead to all kinds of amazing things | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 14 | ielts13_test1_p2 D-12 | T2:gi_v02_c126dd8d3bc8<br>T3:gi_v02_d82df31e5691 | if they are not successful there's that frustration and irritability | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 15 | ielts13_test4_p2 D-01 | T3:gi_v02_1a3f8293a80a | agriculture had to be run on more commercial lines | 需复核：分类轴不互斥；as管辖人口增长及农业商业化 |
| 16 | ielts14_test1_p3 K-03 | T3:gi_v02_4c275b496ac1 | manager support for fun had a favorable impact in reducing turnover | 需复核：分类轴不互斥；that后两项都是found的内容 |
| 17 | ielts15_test1_p2 B-02 | T3:gi_v02_925caa02156b | it is the primary cause in the vast majority | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 18 | ielts15_test1_p2 G-03 | T2:gi_v02_60bb5cc29ad1<br>T3:gi_v02_56c920700d5a | the need to be flexible in response to this will be vital for those involved in manufacturing the vehicles that will deliver future mobility | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 19 | ielts15_test1_p3 D-03 | T2:gi_v02_40b28d51f5de<br>T3:gi_v02_82667617514f | that's not including bacteria | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 20 | ielts15_test1_p3 E-04 | T2:gi_v02_cc6a54ffebec<br>T3:gi_v02_8da77e8bcf24 | an explorer changes the world | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 21 | ielts15_test3_p3 F-02 | T2:gi_v02_95d810c53541<br>T3:gi_v02_6ae0d712a189 | there are lots of other details that can evolve quite freely | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 22 | ielts16_test1_p2 E-05 | T2:gi_v02_e5f66f0079cd<br>T3:gi_v02_d01f41961eff | what they were supposed to represent | 需复核：分类轴不互斥；what从句与why从句并列，共同作on的宾语 |
| 23 | ielts16_test2_p3 J-02 | T2:gi_v02_8d4990efb031<br>T3:gi_v02_60cb6a4601fa | how much stronger such contextual effects are for understanding the relationship between wise judgment and its social and affective outcomes as compared to the generalized “traits” | 需复核：分类轴不互斥；how从句与前一how从句并列，共同作形式主语it对应的内容 |
| 24 | ielts16_test3_p3 B-01 | T2:gi_v02_434d1eea68ad<br>T3:gi_v02_7df93d463602 | the pace at which they change is 'directly proportional to temperature' | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 25 | ielts17_test4_p2 F-07 | T2:gi_v02_8d58d7038716<br>T3:gi_v02_620aaa549187 | this has implications for today | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 26 | ielts18_test1_p2 F-04 | T2:gi_v02_293af2cbcc52<br>T3:gi_v02_48bddfc51ad7 | the money that comes in is spread out over a decade or more | 需复核：分类轴不互斥；so that管辖两个目的/结果分句 |
| 27 | ielts18_test3_p1 E-07 | T2:gi_v02_556b2510f4ce<br>T3:gi_v02_6fdf9d85cba9 | the process, it seems, is quieter | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 28 | ielts20_test1_p1 I-04 | T2:gi_v02_b9644cad329a<br>T3:gi_v02_d661a884e51f | the birds were more intensively managed | 需复核：分类轴不互斥；until管辖两个改变条件 |
| 29 | ielts20_test1_p2 A-06 | T3:gi_v02_2e8e11b959ad | it's only then that you realise the impact [elms had] | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 30 | ielts20_test3_p2 A-05 | T2:gi_v02_28dc3a20eae4<br>T3:gi_v02_eaf84cb0004b | we want to show people how wonderful they are | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 31 | ielts20_test3_p3 L-03 | T2:gi_v02_c63d755c3225<br>T3:gi_v02_623c99a4447e | that is why the worlds seem to collide at times | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 32 | ielts20_test4_p3 E-25 | T2:gi_v02_5bcddb5b8cda<br>T3:gi_v02_3dbe868ef621 | in others only one or two have dogs | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 33 | ielts4_test1_p3 E-20 | T3:gi_v02_4448f9965e25 | the bent spokes were taken as a sign that the wheel was jerking | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 34 | ielts4_test2_p1 E-26 | T2:gi_v02_ef1cfa644d9c<br>T3:gi_v02_057908d6801b | they have had to adapt to socio-economic pressures | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 35 | ielts5_test1_p3 C-11 | T2:gi_v02_0b9764d87eff<br>T3:gi_v02_41f5455f8875 | four factors seem to cause this disjunction between perception and reality | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 36 | ielts5_test3_p3 G-44 | T2:gi_v02_d5aa28db47a5<br>T3:gi_v02_fe6ea70522cb | AI can now be judged by what it can do, rather than by how well it matches up to a 30-year-old science-fiction film | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 37 | ielts6_test2_p2 A-02 | T2:gi_v02_0294c71616c4<br>T3:gi_v02_077495b556b8 | when they do strike, it is much later in life | 需复核：分类轴不互斥；reveal that管辖疾病发生率和发生时间两项 |
| 38 | ielts6_test3_p2 A-05 | T2:gi_v02_d3f5311a9963<br>T3:gi_v02_23f3ec6f71a5 | where there is independence and feedback | 需复核：分类轴不互斥；where与when从句并列，仍表达工作条件/情境 |
| 39 | ielts6_test4_p1 E-23 | T2:gi_v02_8d12000ccc0a<br>T3:gi_v02_9153e2c0a553 | it doesn't make me prescribe their medicine | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 40 | ielts6_test4_p2 J-27 | T2:gi_v02_04483badd323<br>T3:gi_v02_9ece9d16f2e3 | similar campaigns elsewhere might not work as well | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 41 | ielts7_test2_p3 D-07 | T2:gi_v02_403f9ba46d05<br>T3:gi_v02_4919084edc4c | there were no resources to repair them | 需复核：分类轴不互斥；because管辖车辆坏及无修理资源两项 |
| 42 | ielts7_test4_p1 A-07 | T2:gi_v02_37a02e15f857<br>T3:gi_v02_e5a3f4435aa3 | the men were using it to lift a heavy object | 未确认类别错误（完整并列主句/引语内并列/挂靠可疑但整句可成立） |
| 43 | ielts8_test2_p2 F-05 | T3:gi_v02_7f0cf16fab32 | greenhouse gas levels continued to soar | 需复核：分类轴不互斥；as管辖化石燃料使用与温室气体上升 |
| 44 | ielts8_test3_p2 E-02 | T2:gi_v02_2ff29d9d5ea2<br>T3:gi_v02_8e07cbab650d | the once outrageous shapes and colours of an artist like Paul Klee so soon appear on the fabrics we wear | 需复核：分类轴不互斥；fact that同位内容含两项并列 |

## 环境、回归与两次SHA-256

Mac：macOS 27.0.1 arm64；Python 3.13.3；spaCy 3.8.16；en_core_web_trf 3.8.0；torch 2.14.1；CPU；openpyxl 3.1.5；生成种子20261018。Flask-only环境除pip只有Flask3.1.3及其传递依赖（blinker/click/itsdangerous/Jinja2/MarkupSafe/Werkzeug），没有spaCy/openpyxl等；其1项skip是Excel可选依赖测试，专项环境已执行对应检查。

为保护被审文件，在仓库外完整76aeb12快照运行两次原生成命令。复用上轮本机已验证解析缓存；本轮句子文本完全未变，未声称冷解析。两次均重新收集全库、判型、抽样及写四份产物。旧池为本机独立生成的5eb9922完整快照，3b7efb3只增加前审文档；核对477个输入/实现文件与git对象一致。main使用完整676569c快照，并核对468个导入相关代码/static/data文件。不存在只替换data却复用新static的导入混搭。

输入reading_study SHA-256：`8744a42e86c57399b2b592959b1044f7dcd3550ddfd0a066713ffebeffc5435a`；graph SHA：`c7b35ddb68db7601ccd01e38a210ad3dd772ff507302190f68a351e408b85a29`。

| 文件 | 第一次 | 第二次 | 提交版比较 |
| --- | --- | --- | --- |
| generation_report_v0_2.md | 5d73eec0b13941ef8b45cfef26e801f614db7269fb1a6e2038e325451d2d8840 | 5d73eec0b13941ef8b45cfef26e801f614db7269fb1a6e2038e325451d2d8840 | 仅Python版本3.13.3/3.11.15一行不同；提交SHA cc9bbe1008faa795ea063a84a20be1de3975f3d8a2cc85d61a40942982cdc9eb |
| generation_report_v0_2.json | 43bc54a281a2c2351343bc839bac8090acbcd478d7d1eb39be960fbf76b40674 | 43bc54a281a2c2351343bc839bac8090acbcd478d7d1eb39be960fbf76b40674 | 仅Python版本3.13.3/3.11.15一行不同；提交SHA afbedc9fdff924386e9021095f530c4a861ba783e354a3c878c3219ffdb7790b |
| review_batch_v0_2.xlsx | 5c9ae0ea5bd36b25d34cd89c1fb1d0337e04cd2fa099e599f6b0c50be2825e8f | 5c9ae0ea5bd36b25d34cd89c1fb1d0337e04cd2fa099e599f6b0c50be2825e8f | 完全一致 |
| review_batch_v0_2.jsonl | 2120789b34b5bed49e5f54586c221f8024b073d713b91530e749e026d266fc4c | 2120789b34b5bed49e5f54586c221f8024b073d713b91530e749e026d266fc4c | 完全一致 |

两报告逐字节diff各只有环境Python版本一行，不只是删掉整个environment后比较。78个回归模板记录（13来源×6）连状态、原因、题号一起与旧版全等。7个整句过滤独立核对如下：

| 过滤 | expected | actual |
| --- | --- | --- |
| tagged_fragment | 30 | 30 |
| clause_attached_to_conjunction | 2 | 2 |
| glued_sentence_boundary | 0 | 0 |
| multi_sentence_unit | 1 | 1 |
| suspected_split_word | 0 | 0 |
| leading_stray_punctuation | 0 | 0 |
| control_character | 0 | 0 |

XLSX每个工作表60题，360行每个老师字段与teacher_row逐格一致；未暴露auto_pass/needs_review；判定下拉为“正确 / 答案错 / 题目有歧义 / 句子不适合出题”。新表保留39个旧题号；这是题号交集，不代表39行原位保留，不宜按旧行号续审。

## 实际执行命令及复现方法

以下变量均为本次实际路径。辅助脚本、全量池、日志、快照、SQLite仅本机，未越权提交到仓库；报告保留算法、全部抽样ID和输出摘要供跨机器重做。

```sh
ROOT=/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker
AUDIT=/Users/zhouxin/.codex/audits/grammar-v02-round9-20261027
G="$ROOT/.venv-grammar-tools/bin/python"
P=/Users/zhouxin/Desktop/studytracker/.venv/bin/python
NODE=/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
cd "$ROOT"
git status --short --branch
git log -5 --oneline
git fetch origin claude/word-memorization-system-eval-55v2y5
git merge --ff-only 76aeb1251d951393d256dd8900a2340644ba332e
git rev-parse HEAD
git diff --stat 3b7efb3..76aeb12
git diff --name-only 3b7efb3..76aeb12
```

审计脚本读取git diff路径白名单，并用旧新JSON深比较6个文件：除指定句structure/difficult_points外全部键值相等。受保护路径没有任何diff。用完整git archive建立AUDIT/source；生成脚本两次执行的实际命令（cwd均为source）：

```sh
"$G" scripts/generate_grammar_candidates.py --seed 20261018
"$G" scripts/generate_grammar_candidates.py --seed 20261018
```

由`"$G" "$AUDIT/generate.py"`顺序执行，并把每次四文件另存first/second。`audit_runtime.py`用SHA-256、字节比较、按item_id连接旧新候选、openpyxl校验工作表/数据验证/盲审，并按上述固定顺序抽样；`audit_data.py`做6句差分、角色查漏、raw重建、图谱比较、快照核实。精确实际调用：

```sh
"$G" "$AUDIT/audit_runtime.py"
"$G" "$AUDIT/audit_data.py"
"$G" "$AUDIT/probes.py"
"$G" "$AUDIT/compact_scans.py"
"$G" "$AUDIT/focus.py"
"$G" "$AUDIT/extra_probe.py"
"$G" "$AUDIT/adjudicate.py"
"$NODE" "$AUDIT/verify_display.js"
```

raw重建：导入本版本`build_reading_test_practice`，将`localize_image`替换为只计算确定性本地相对路径的函数；调用`build_tests(raw, 'jijing')`，逐passage比较完整content及groups，171篇无差异，不联网下载图片。图谱在source执行`"$G" scripts/render_grammar_graph_review.py`，与被审文件bytes相等。

规则反事实：旧数据、同一缓存、相同review_reasons，只用本轮generate_templates取代旧实现；按共同ID比较旧auto到新needs，得7+40。进一步只把predicative_clause换成“advcl挂无其他补足语be”的宽版，得到额外10句24题；函数只在内存替换。旧代码负测：`git show 3b7efb3:scripts/grammar_items/templates.py`编译进独立模块，将测试模块的generate_templates暂指向旧函数，执行PredicativeClauseTests：5运行、2断言失败、3通过、0错误。新代码5项均通过。

所有常规检查由`"$G" "$AUDIT/run_checks.py"`执行，展开为：

```sh
cd "$ROOT"
"$G" -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary tests.test_grammar_graph_draft -v
"$G" scripts/validate_reading_study.py
"$G" scripts/reading_jijing_text_fixes.py --check
"$P" -m unittest tests.test_reading_study -v
"$NODE" tests/test_dictation_spell_queue.js
"$P" -m ruff check --config 'extend-exclude=[]' scripts/grammar_items/checks.py scripts/grammar_items/reporting.py scripts/grammar_items/templates.py tests/test_grammar_item_candidates.py
"$P" -m ruff format --check --config 'extend-exclude=[]' scripts/grammar_items/checks.py scripts/grammar_items/reporting.py scripts/grammar_items/templates.py tests/test_grammar_item_candidates.py
"$G" -m venv "$AUDIT/flask-only"
"$AUDIT/flask-only/bin/python" -m pip install --cert /etc/ssl/cert.pem Flask
"$AUDIT/flask-only/bin/python" -m pip list
"$AUDIT/flask-only/bin/python" -m unittest tests.test_miniprogram_guest_access tests.test_miniprogram_dictation_grouping tests.test_inventory_toefl_materials tests.test_organize_toefl_materials tests.test_extract_toefl_answer_keys tests.test_map_toefl_answers_to_practice_docs tests.test_import_toefl_official_reading tests.test_reading_vocab_grading tests.test_stats_utils tests.test_grammar_graph_draft tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary -v
"$P" "$AUDIT/import_snapshot.py" "$AUDIT/main"
"$P" "$AUDIT/import_snapshot.py" "$AUDIT/source"
```

导入helper每次在新进程把对应完整快照放入sys.path，验证实际import路径，`make_app(database_uri='sqlite:///.../main-to-current.sqlite')`，只创建ReadingPassageAnalysis表，再调用run_import(...,load_source_passages())。main先created317，本版updated236/skipped81/failed0；未连接生产库。validator覆盖317/387、70未标注为存量，不是本轮验证错误。

## 与提示要求的差异及未完成范围

没有因权限/环境而跳过的指定检查。生成在同一Mac、指定虚拟环境的仓库外完整快照进行，保护被审交付文件；使用已验证解析缓存而非重新冷解析，提示未要求本轮冷解析。两报告仅Python版本差，符合预期。实际共同题差分与提示摘要不完全相同，已在W6列明；指定60题的当前状态为59auto+1needs。未改被审数据、未修发现的问题。

“全池定向扫描”是规则筛选后人工判读，不是宣称人工通读28029道。教师360题盲审、修改代码/数据、部署与生产导入均未实施。机经暂缓按用户优先级执行；两处源句缺陷仍给出了局部正确与整句适用性的区别。

## 交接、提交与CI

本报告与CODEX_HANDOFF、WORKLOG同步交接。正文已commit/push `3a3bb6a1920c778fd1772e769332ce32b19f149f`，远端同SHA；[GitHub CI 40426142680](https://github.com/KB77GG/studytracker/actions/runs/40426142680) 已完成、整体success。test任务成功：174运行、173通过、1按设计跳过；Node拼写队列步骤成功。lint任务Ruff check存量advisory failure，format skipped；日志错误文件与本轮4个改动Python文件无交集。本机对这4文件显式取消exclude后check/format通过。

本CI补记随后独立commit/push，仍只改获准三文档、不含skip-ci标记；最后HEAD以git log及最终汇报为准，最后提交CI另行核实，不把正文SHA冒称最后SHA。提交后任务树干净；桌面main已有7 modified/22 untracked入口未动。报告与交接已通过限定分支跨电脑共享，AUDIT辅助证据仅本机。

只推codex任务分支，不推main、不PR、不部署后端/前端，不操作生产服务器/数据库，不上传/提审/发布小程序，不调用大模型API。

<a id="w1-w4-proposal-v01"></a>

## 附录：W1–W4 修订方案 v0.1（供 Claude 复核，尚未实施）

2026-10-27 按用户“做一个版本放在完整复审报告里，给 Claude 看”的要求补充。**本附录是实现建议，不是修复完成记录。W1–W4 仍开放，原复审结论不变。** 本次只修改报告和两份交接，未运行或验证下面拟议的新规则。

方案依据的代码、标注及候选池固定为 `76aeb1251d951393d256dd8900a2340644ba332e`；写方案前任务分支为 `61c0352937daad1cf79968e424d7d99544f038e5`，其后两次提交仅补审查文档，运行基线相同。实现时应先检查是否已出现后续改动，不能把本方案的数量直接套在另一版池子上。

### 1. 推荐的第一版行为

先在现有 v0.2 候选题流程内修复“有明确风险却自动通过”的问题：题干前提不唯一或分类有合理争议时进入 `needs_review`，由老师决定改题、改答案还是淘汰。**降级不等于已经把这些题改成了可直接给学生的正确题。** 本版保留既有题型、答案来源和判分结构，不自动把争议分析写成唯一正确类别；如果需要保留为自动题，再单独设计限定分句的题干或把“语法功能 / 并列关系”拆成两个问题。

| 项 | 最小修订 | 作用范围 | 已确认回归集 |
| --- | --- | --- | --- |
| W1 | 新增并列目标的功能重叠复核原因，建议名 `coordinate_function_overlap` | 仅 T3；不因这个新增原因连带修改 T2 | 17 道 T3 |
| W2 | 新增主句不唯一复核原因，建议名 `multiple_independent_clauses` | 仅 T1、T5；同句 T6 重新按自身目标判断 | 10 道 T1 + 7 道 T5 |
| W3 | 两句难点准确说明分号与非限定结构的关系，并加既有“原句问题：”前缀 | 复用 `source_quality`，该句全部候选待审 | 6 道原 auto |
| W4 | 将完整年龄表达纳入关系副词风险，复用 `possible_relative_adverb` | 同一目标的 T2 / T3 / T4；不影响其他目标 | 2 道 T2 / T3 |

这四组在基线中是 **42 个不同题号、30 个来源句**，均为剑桥 auto。它们是必须覆盖的回归集，不是生产黑名单，也不是通用规则命中数的上限。逐题 ID 已列在正文 W2/W3/W4 和“并列目标定向扫描明细”中；W1 取该表17行“需复核”的 T3。

建议实现涉及 `scripts/grammar_items/{templates,checks,reporting}.py`、对应测试、下述三句的难点说明及重新生成的交付文件。只改难点时不改 sentence、translation、structure、expressions；不修改 IELTS 原文或机经数据。**这是拟议实施范围，本次文档提交没有实施这些改动，也不扩大此前只审核的代码写入授权。**

### 2. W1：在 T3 判断分类轴重叠，不能简单禁止从属从句并列

入口建议放在 `classify_clauses()` 的 `kind == "coordinate"` 分支，新增返回原因与证据的纯函数。`type_matches()` 同时供 T2 使用，把新规则直接写成该函数返回 False 会扩大影响，因此本版不采用这一接入方式。现有直接从属标记等检查仍保留，不趁本次放宽旧规则。

判读步骤建议如下：

1. 从当前并列中心沿 `conj` 链找到首项，检查首项和当前项承担的句法功能；不能只检查当前中心的直接 `mark` 子节点。
2. 联合检查当前项的 wh 成分（可能标成 `advmod`、`dobj`、`nsubj` 等）、首项的从属引导词、控制整个并列结构的谓语/名词，以及已有 span 的角色和包含关系。覆盖显式 `and why / or when / and what / and how`，也覆盖第二项省略共享 `as / because / so that / until / that` 的情形。
3. 若目标既有并列关系，又明确或很可能承担名词性、定语或状语从句功能，给 T3 增加 `coordinate_function_overlap`，保留原标注答案供人工审，不再自动认定互斥单选成立。记录目标、并列首项、外层作用域和触发信号，方便复核。
4. 引语里的独立分句也可能被解析器挂成 `ccomp`。只看到某个祖先是 `ccomp/advcl/relcl` 不能判定重叠；应识别引语层级、说话人插入语和实际从属范围。分析不确定时明确记录不确定性，不伪造确定类别。

回归至少覆盖正文最明确五例：12_5_p1 C-04 的 `why` 宾语、D-07 的 `when` 修饰 day、16_1_p2 E-05 的 `what` 宾语、16_2_p3 J-02 的 `how` 真正主语、6_3_p2 A-05 的共享情境从句；另覆盖表内12个省略共享引导词的目标。

反例必须包含正常并列主句、引语内并列、并列主句内另嵌状语从句，以及正文44个目标里另外27个未确认类别错误的目标。不要把“`and/but + 从属连词` 整句排除”或“有从属祖先就排除”作为替代实现，旧计划已记录前一种方法的误伤。T2 的“划出并列成员”与 T3 的互斥类别单选是不同要求，本项不自动否定关联 T2。

本版不批量重写这些目标的 role：从属功能与并列关系可以同时成立，当前一个 role 字段难以完整表示二者。后续若改成两轴分类，需要同步题干、选项、判分与标注规范，不能只把所有 `coordinated_clause` 改为某一种从句。

### 3. W2：识别多个独立分句，只限制“唯一主句”的两种题

在 T1、T5 的候选复核阶段共用一个检查函数；对已经因旧选句规则拒绝的题保持原行为。对现存、但发现多独立分句风险的候选增加 `multiple_independent_clauses` 并进入 `needs_review`。这一版保留题号和原答案以便复核，不改题干为“冒号后的分句”，也不把多个答案偷偷塞进现有单根判分。

检查应同时看句法和位置：在非引语、非括号内部的冒号/分号等候选边界两侧，查找各自的限定谓语单位和主语（包括 `expl` 的 there be）；结合 span 判断它们是否各自成句，排除从句、名词列举、解释性补足语等。还应检查解析器的 `parataxis/conj` 及边界两侧的其他有限定中心，避免只认某一个 dep。

特别要保留真实反例 `ielts17_test1_p2 E-06`：解析器将前半 `There have been ...` 的 been 标为后半 become 的 **ccomp**，不是 parataxis。只查 ROOT 的 parataxis 子节点会漏掉本报告点名实例；反过来，把所有 ccomp 都当独立句会误伤正常宾语从句。应依据边界、前半的完整主谓与后半是否真能管辖它共同判断，存疑就待审。

**T6 隔离是本项必要部分。** 当前 `finite_targets()` 会复制 `main_item["reasons"]`。如果仅向 T1 加原因，T6 主句动词题会被连带降级。建议在该复制点只排除本次新增的 `multiple_independent_clauses`，继续保留 `source_quality`、解析冲突等其他原因，并照常复核 T6 自己的动词单位及身份。不要把新检查加进 `main_selection()` 后直接拒绝 T1，否则还会经 main_item=None 让原本局部成立的 T6 消失。

验收包括正文10句的17道题全部不再 auto；所有同句其余题逐项对比。对含冒号/分号的109个基线 T1 来源复看，另外99个不能仅凭标点降级。构造正常名词列举、`He asked the question: why ...`、直接引语、括号内说明、带从句的单主句等控制例；这些控制例只要求“不新增本项原因”，不强迫原本因别的原因待审的题变为 auto。不能用改成一句简单题、拆改原文或整句 `source_quality` 来避开题干问题。

### 4. W3：两处面向学生的说明草稿

沿用 `checks.review_reasons()` 对“原句问题：”开头难点的既有规则，不增加按 ID 判断的过滤器。只改各句下列一条说明，保留其他字段。

`ielts15_test1_p3 F-04` 第一条建议替换为：

> 原句问题：分号后 the common factor in their approach being ... 是独立主格结构，being 不是限定谓语。按通常书面语中分号连接两个独立分句的写法，这里需要调整：可把分号改为逗号，保留独立主格作补充；也可保留分号，将 being 改为 was，使后半成为完整分句。意思是这些探索者各有标准，但都从一开始就有明确目标和记录发现的愿望。

`ielts7_test3_p1 B-07` 第一条建议替换为：

> 原句问题：分号后 other skills being learned ... 是非限定的独立主格结构。按通常书面语中分号连接独立分句的写法，可把分号改为逗号，保留补充说明；也可保留分号，将 being learned 改为 are learned，使后半成为完整分句。这里对比先天的基本本能与成长过程中向他人学到的技能。

这两段是解释可采用的规范改写，**不是要求改动剑桥原文**。不声称独立主格本身不合法，也不建立“所有分号后非谓语都错”的绝对规则，列表等语境需另看。Claude 应独立复核说明的语法与时态；若不同意原句适用性判断，应给出具体依据并保留争议记录，不能先把 W3 写成已关闭。

基线六道 auto 应带 `source_quality` 变为 needs_review；两句本来已待审的题也应增加该原因。题号、答案、目标范围与干扰项不变。

### 5. W4：年龄表达后的 when 作风险提示，不强改为定语从句

扩展 `relative_adverb_risk()`，保留原“紧邻名词”的检查，增加有限、可解释的年龄短语识别。首先覆盖 `six weeks old, when ...` 这一类：在同一局部短语内识别数词（含英文数词）+ 时间单位 + old，允许当前例子的 as early as 修饰，when 与其间仅有逗号等边界标点。记录完整先行表达的范围，不靠 `old` 一个词或 `ADJ` 一个 POS 触发。不要在整句任意远处发现年龄就匹配末尾 when。

以同一个风险原因接入 T2、T3、T4 现有调用处；只表示存在回指年龄/时间的合理分析，不自动把答案改成“定语从句”。正文两题进入 needs_review，同句其他五道基线 auto 的答案与状态保持。若通用识别发现其他目标，逐项阅读并报告，不为凑“只降2题”收窄到本句。

同时建议只将 `ielts15_test2_p3 A-01` 的第三条难点改成：

> when 从句补充说明婴儿在六周左右的表现；它既有时间说明作用，也可以分析为回指前面年龄表达的补充关系从句，近似 at which age/time。若题目要求在“状语从句”和“定语从句”中单选，本句需要先明确采用的分析口径。

不加“原句问题：”，因为这里是分析歧义，并非原句有语病；不改 structure 来强行确定一种答案。控制例包括 `She was cold when she arrived.`、普通形容词后的 when、没有年龄先行表达的比较/条件从句，以及正文 ADJ 挂靠扫描中其他3个正常目标；它们不得仅因形容词挂靠而新增该风险。扩展到 `at the age of ...` 等形式时也需独立样例，不先承诺覆盖所有时间表达。

### 6. 实施后的验收和 Claude 需反馈的内容

建议按 W1、W2、W3、W4 分开提交实现与测试，最后统一重生成，便于将新增命中归因。可实施前先由 Claude 评论本方案；本附录不代表已经执行，也不替代完成后的独立复审。

| 验收 | 必须给出的证据 |
| --- | --- |
| 已知问题 | 42个基线题号逐题列出修复前后状态、原因、局部答案和题干判断；不得只报总数。规则不得读取 passage_id、sentence_id 或 item_id 作为分类条件。 |
| 反例与传播 | 每条规则有正例和上述控制例；新正例在旧代码失败、新代码通过；控制例不得新增对应风险。专门断言 W2 的 T6 原因隔离、W1 的 T2 不被新增原因连带、W4 同句其他5题不变、W3 整句原因完整传播。 |
| 全池差分 | 按此最小版设计应仍有50243个候选、题号集合不变；题干、选项、答案、范围、干扰项及判分规则不变，仅风险命中项的状态/原因/说明性证据变化。若实际改变选题或标注角色，先明确方案变更及理由，不把它混成上述最小版结果。 |
| 新命中与误伤 | 列出所有额外命中和原因，剑桥逐目标判读，机经影响另列。已知42题都离开auto只是下限，不预先宣称最终只降42题。另复查44个并列目标、109个冒号/分号T1来源和4个ADJ挂靠目标，解释每项变化。 |
| 内容与格式 | 三句除指定difficult_points外字段逐字节不变；不新增未知role；validator为0。W3的两句不能仍有auto，W4不能整句降级。 |
| 重生成 | 同一Mac环境/模型、种子20261018双跑；四份交付文件彼此字节一致；逐文件SHA、环境版本入记录；78项既有回归和7项整句过滤复核。新增风险属于题目复核，不应改变整句过滤数量。 |
| 报告口径 | 区分全量带原因、只因该原因降级、实际共同ID状态变化，分别统计剑桥/机经。不要把固定旧标注的反事实计数当最终池差分（W6）。本来needs的题增加原因不能算新增降级。 |
| 抽查表 | 池子变化后重新检查盲审、六表各60行、四项下拉；同时报告题号保留数与(工作表,行号)保留数，老师结果按题号迁移。 |
| 验证和导入 | 跑专项及ci.yml完整轻量列表、Node、reading、改动Python的Ruff；难点变更时用main完整快照到修订版的临时SQLite模拟导入，实测数量，不沿用236/81/0为新预期。GitHub test与存量lint分开记录，不操作生产。 |

实施后专项命令仍为 `.venv-grammar-tools/bin/python -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary tests.test_grammar_graph_draft`；生成命令为 `.venv-grammar-tools/bin/python scripts/generate_grammar_candidates.py --seed 20261018`，执行两次并分别保存四文件。其余命令沿用正文“实际执行命令”中的完整步骤，旧快照换成明确记录的实施基线，新快照换成待审提交，不覆盖原审计证据。

Claude 优先反馈三个决定：W1 的作用域证据如何避开引语内正常并列；W2 如何识别 E-06 这种被误挂成 ccomp 的独立分句且不误降 T6；W3 两段规范改写是否准确。对规则无法可靠区分的案例保留 needs_review，报告缺口，不用句号ID补丁。W5 的保守误降和既有 T2 多解等建议不在本版四项修复里悄悄扩大处理范围。

### 7. 本次仅写方案的核对记录

已重新读取上述调用链，确认 `finite_targets()` 的原因继承、T2/T3 共享 `type_matches()` 和 W4 的三模板风险入口；逐字读取三句现有难点。对基线全量候选重核 W1/W2/W3 的17/17/6条及W4两题，得到42个不同ID、30句，全部与本机审计快照对象一致且为auto。这里验证的是**现有问题集和方案接入位置**，不是证明拟议算法已经能准确命中。

文档检查：`git diff --check`；确认相对 `61c03529` 只改本报告、`docs/CODEX_HANDOFF.md`、`docs/WORKLOG.md`，原报告正文保持不变、只追加本附录。没有重新运行语法生成或冒称新规则测试通过。上一文档提交 `61c03529` 的 [CI 40426443967](https://github.com/KB77GG/studytracker/actions/runs/40426443967) test成功、lint存量advisory失败；本方案提交也不带skip-ci，最终SHA和该次CI在交付汇报核实。
