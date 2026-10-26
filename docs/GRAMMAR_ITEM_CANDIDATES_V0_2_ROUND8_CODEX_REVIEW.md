# 语法候选题 v0.2 第八轮独立复审（Codex）

审核日期：2026-10-27（Asia/Shanghai）。结论：**不通过**。新增 **0 阻断、3 应修、2 建议**；另保留前审 A8 的题干多解建议。第八轮指定修复大部分已独立复现，但抽查找到3道仍自动通过的从句类别/题干前提错误，定向查漏还有3处排印错误，文档错误声称网页不显示已有错误解析。代码、数据、交付文件均未修。

被审边界为 `26fc46d80d0d716b0ee6922935b45eb9af9fcdef..5eb9922607a191b405b9c0139886b3a583ddae53`。工作树 `/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker`，分支 `codex/grammar-item-candidates`，按授权 fetch 后 fast-forward 至上述精确 HEAD；没有合并 main、rebase、改写历史。候选差分基线按要求为 `4a43124`，26fc46d 相对它只有前审文档。开始时本工作树干净。

本报告中的“通过”限于具体检查；“局部答案成立”不等于题干唯一，也不等于整句可直接用于教学。自动通过题和待复核题分开计数。V1/V2是本次抽查/查漏发现的存量问题，不能归因于第八轮代码引入；V3是本轮新增记录的风险描述错误。

## 前审编号关闭情况

| 编号 | 被审版本状态 | 独立验证与保留范围 |
| --- | --- | --- |
| U1 | 点名事项关闭 | 9条补前缀、44_29_p2 E-03两种修法准确；2处引号修原文有依据；85_12_p1 B-02币种不能臆补。重新检索165条无前缀说明，未另确认已经明确描述缺陷却漏标的句子。 |
| U2 | 关闭 | 13条去前缀后讲解可成立；27_33_p2 A-03改为能力/实际数量语义不符；5条保守待审没有继续断言唯一写法。7句恢复的34道题给定答案与高亮均成立。保守待审不代表已证明这5句全有语病。 |
| U3 | 点名事项关闭 | 全库仅新增32_20_p2 G-01、I-01两个列表命中；I-01两题不再auto。合成格式与相邻人名缩写边界见V4，不算已出现的自动题泄漏。 |
| U4 | 原文恢复关闭；显示范围说明未关闭 | 补回两句与raw sub_title（去尾换行）一致，四处引用可定位，3篇逐段拼接一致。summary/target_para未显示，但第27题解析/中心句在网页显示，见V3。 |
| U5 | 19处点名修复关闭；全库查漏未关闭 | 19处改法正确、14处同步题目；另找到pre-modem、Fischer-Price、Witthof，见V2。 |
| U6 | 关闭 | 625个含破折号来源句同parse反事实仅1题变化，真实T5闭破折号恢复；5–10和5 - 10仍不补。 |
| A7 | FIXES已更正；被审交接仍有旧句 | 第七轮FIXES已写333新题/27保留/360行全换；被审CODEX_HANDOFF:35仍写333/360行换题。本次获准更新交接时已明确纠正该旧句；第八轮是304新题/56保留/359行换题。 |
| A8 | E-22措辞关闭；T2多解未关闭 | 粗解析计数确有大量假阳性，但存在明确同类多从句，不能据此关闭。独立口径与30例二次核对见下文。 |
| 第二至四轮 A3 | 已点名案例和排除机制关闭；全池适用性不作保证 | 已标原句问题/实际识别列表的auto泄漏为0，按句抽50未见明显源句残缺。未写说明的缺陷仍可能漏网，V2也说明原文准确性不能凭此保证。 |
| 第五轮 A5 | 关闭（本次U6补齐） | 数字区间不补、单侧数字插入语正常补，原实际回归已消除；未承诺所有排版都能靠启发式识别。 |
| 第五轮 A6 | 点名F-01与既定策略关闭；全量质量持续验收 | 动名词复合结构和既有点名残缺句已处理；不把抽样0源句缺陷写成全池0缺陷。 |

## 14项检查结果

实际命令统一在后面的“执行命令”节列出；本表的辅助脚本均在仓库外 AUDIT 目录，报告保留关键复现方法和全部抽查题号。

| 项 | 结果 | 独立结果及命令/证据 |
| --- | --- | --- |
| 1 | 通过 | git diff --stat：53文件，1158插入/715删除；白名单外0，受保护路径diff为空。1619630的22个阅读文件只改difficult_points；24a0f28只有23_46 B-04b、91_49 C-01/C-02、32_20 A段（其余仅index）。audit_data.py/final_evidence.py。 |
| 2 | 点名修复通过 | 9条前缀紧跟缺陷；44 E-03分号后无限定谓语，改warn或逗号+with结构均可。91 C-01末开引号移到C-02、23 B-04b闭引号有题目来源依据；85 B-02不臆补币种。无前缀165条复查见覆盖表与方法。 |
| 3 | 通过 | 13去前缀、7保留改写；34恢复题逐题给定答案成立、原句可用。表语位置的连字符、不可数/复数research、时态参照等新说明没有重复旧的绝对化错误。 |
| 4 | 通过当前语料；合成边界建议 | list_letters同篇相邻字母上下文；姓名例外及小数/区间不误伤；全库29命中，较旧版仅G-01/I-01新增。无实际em-dash列表遗漏；双星脚注未命中但均无候选。probes.py。 |
| 5 | 恢复/数据通过；文档不通过 | 17篇sub_title逐篇核对，直接缺失的中心/定位原句只有32_20_p3；65_69_p2仅6词题干主题重合，不等于原句引文。显示段号答案27–31为E/D/C/B/G成立；Q27解析已知不对应答案仍会显示(V3)。新两句解析准确，原A-01c除ID/index外不变；at_start幂等/报错及旧代码负测通过，组合防御见V5。 |
| 6 | 点名19处通过；查漏不通过 | 19处均为明确OCR/排印，14条questions同步；这些旧串在本篇groups残留0。独立扫1198处带连字符词及专名上下文，新增V2三处。 |
| 7 | 通过 | 625来源句在同parse上只替换旧/新DASH：唯一变化gi_v02_ed4743fde6b9；恢复[0,47)完整主语。旧代码1项断言失败，新代码测试通过。 |
| 8 | 部分关闭 | A7文档已改，但交接旧句尚存；本次交接纠正。A8 E-22不再说永远必须完整分句；T2多解存在，不能用粗解析假阳性作为全免理由。 |
| 9 | 通过 | 第七轮FIXES现在记1断言失败/3接口错误，与上轮实测一致；列表29句中15句出题，当前与旧版未适用/整句过滤区别核实，原另3句无适用题型说明与前审一致。 |
| 10 | 通过 | 50230→50248，+21(14auto/7needs)、−3；34升/13降；共同ID72道reasons改变；排除status/reasons后仅U6那1题内容改变。不是“只有47道对象任何字段变了”。auto各模板5926/4705/11465/404/5377/12749；已标记auto泄漏0。audit_runtime.py。 |
| 11 | 通过 | Mac双跑四文件逐字节一致；JSONL/XLSX同提交；两报告唯一差Python版本行。78回归记录不变，7过滤匹配。表内保留56题，按(template,review_row)仅1行未换/359行换；XLSX盲审与下拉均通过。 |
| 12 | 通过 | 101专项；Flask-only169运行/168通过/1按设计跳过；Node通过；reading22；validator317有效/0错误（全目录规划387、70未标注是存量）；--check=0；raw171篇content含summary/groups一致；3篇20段拼接一致；graph字节一致；6改动Python Ruff check/format通过。 |
| 13 | 通过 | 完整main676569c先导入317篇，再导5eb：updated233/skipped84/failed0，最终317行；SQLite仅AUDIT本机。468个相关main文件与git对象验证一致。 |
| 14 | 完成；发现V1 | seed20261030：表内auto30、恢复auto34、新增auto14、U6auto1、新降needs13、新增needs7、auto来源50句/198题；分别判断答案与整句，见全部明细。 |

## 新问题

### V1 — 应修：表语位置的 because 从句仍作为状语从句自动通过，影响3题

位置：`data/reading_study/ielts16_test3_p2.json:1798`，H-04；role在1818，难点1829；判型入口 `scripts/grammar_items/templates.py:385`。

原句：`The researchers say that could be because many of those artefacts have already disintegrated or are still frozen in the ice.` 这里that是指示代词，could be后面的because从句解释“那种现象”的原因，充当表语/补足成分。本项目难点自己也写“because 引导表语原因从句”；structure却用reason_clause，把“原因语义”直接送进“状语从句”类别。在本项目名词性/表语从句分类下，不能把它作为独立确定的状语从句答案。即使采用其他语法分析体系，也至少应待审，不能同时教两种冲突分类。

| 题号 | 模板/状态 | 问题 |
| --- | --- | --- |
| gi_v02_bdee163d3f00 | T2 / auto_pass | 要求划状语从句，给出because整段；从句文字边界可成立，但题干类别错误。 |
| gi_v02_bfb7654efc10 | T3 / auto_pass | 把because整段判为“状语从句”；按本项目表语从句体系应属名词性从句。 |
| gi_v02_6e7951e2acc7 | T4 / auto_pass | “原因”语义成立，但题干预设这是状语从句，不应据此进入T4自动池。 |

复现：生成全量池后按上述ID取status、target、answer；再读取H-04 structure与difficult_points。解析器advcl与原role吻合，只证明二者一致，未排除系词补足语。该来源句本身完整、可给学生；问题是3道题，不能把整句错杀。同句其余6道auto的给定局部答案可成立。

同库对照ielts12_test7_p3 D-02把is后的两个when从句标为predicative_clause；解析器虽也给advcl，模板会把相关T3留待复核。这支持应区分“语义为时间/原因”与“句法作表语”，而不是把所有because/when从句归状语。

建议：校正原标注/说明的分类一致性，并为“系词be + because等补足语”增加通用判型或至少降级复核；补真实例及普通because原因状语反例。不要按句ID或题号屏蔽。以上是本轮按句抽50新发现的存量题目错误，不是第八轮新增回归。

### V2 — 应修：定向查漏仍有3处可确定的排印错误，部分流入自动题

| 位置 | 当前 → 建议 | 题目数据/解析/候选影响 |
| --- | --- | --- |
| static/reading_jijing/reading_jijing_26_test_72.json:1871，26_72_p2 F段 | pre-modem societies → pre-modern societies | groups有10个字符串字段含旧串；该篇无reading_study/候选。上下文为考古、早期木船和前现代社会，不是调制解调器。 |
| static/reading_jijing/reading_jijing_92_test_58.json:61，92_58_p1 E-02；reading_study同篇:850、874、879 | Fischer-Price → Fisher-Price | groups有8字段；译文已写Fisher-Price，英文与译文不一致。 |
| 同一E-02，reading_study同篇:850、854 | Dr Witthof → Dr Witthoft | groups有8字段；研究者姓氏最后的t丢失，与2013论文作者不符。 |

后两项可由直接相关的2013原始研究 [Learning, Memory, and Synesthesia](https://pmc.ncbi.nlm.nih.gov/articles/PMC3648671/) 核实：作者Nathan Witthoft、Jonathan Winawer，文中玩具品牌Fisher-Price；不靠同类题库转载猜专名。三处已在被审基线前存在，第八轮未新引入。

E-02共有11候选，8 auto/3 needs；8道auto为 `gi_v02_dbe60c543fc1`、`gi_v02_c1c2f8bbd515`、`gi_v02_0e8fd8a92bc2`、`gi_v02_1b5e8e78829c`、`gi_v02_bf45b9c4afd7`、`gi_v02_1463a1c6a4eb`、`gi_v02_8e6136128aad`、`gi_v02_1e597c4cd097`。这不等于8个语法答案都错，而是显示的原句含已可核实的专名错误。

复现：对171篇paragraphs扫描连字符/孤词，沿同篇groups递归搜上述完整词串；Witthof用`\bWitthof\b`避免匹配正确Witthoft。把passage+sentence连接全量池即可复现影响数字（字段数不是去重文本数）。建议按已有修订表修原文、题目及解析所有相关成分并重生成；不要对未经确认的复合词一律去连字符。

### V3 — 应修：把已知错误解析记成“不显示”，与网页实际渲染相反

位置：`docs/GRAMMAR_ITEM_CANDIDATES_V0_2_FIXES.md:455`，把32_20_p3的summary、target_para和第27题解析一起描述为“数据源原样（不显示）”。summary和target_para确实不由当前网页/小程序阅读页显示，但第27题analysis及central_sentences会在网页复盘卡显示。

调用链：`templates/reading/test_practice.html:987`、`:1248` → `static/js/practice_renderers.js:674`读取analysis，`:679`读取central_sentences，`:698`/`:700`渲染“解析”“答案依据”。用真实第27题调用纯函数renderReviewCard，analysisVisible与centralVisible均为true。小程序原生阅读页未找到对这两个展示字段的消费，不能把网页结论也套成“不显示”。提交后的网页代码复核也确认提交成功会在test_practice.html:1463切换review模式，practice_modes.js的review能力允许显示正确性/解析；并非仅存在一个未调用函数。这次没有运行服务器或打开生产页面。

第27题答案E与现显示段落一致，但解析用A段“盲人摸象”支撑E，已有披露；本报告不把已知错误解析重新算一个新数据问题。**新增问题是暴露范围声明不实**，可能使后续审核跳过学生确实能看到的内容。

建议：修订记录明确“summary/target_para不显示；Q27错误analysis/中心句在网页复盘显示”。在上线验收时实际处理该解析或显示策略，另行授权后实施；本轮仅记录。

### V4 — 建议：列表启发式仍有合成漏判/误判，当前没有对应自动题受害

位置：`scripts/grammar_items/checks.py:36` LIST_ITEM与LETTER_LABEL/list_letters。

- `IV. Item`、`(IV) Item`、`•Item`、`-Item`和真正em-dash列表均可能漏识别；去掉—可避免对话误伤，但不能同时保证识别所有以—排版的列表。
- 同篇出现正常姓名主语`B. Smith wrote this.`与`C. Jones agreed.`，相邻B/C会被判列表。姓名“A. K. Lakhina”“K. Anders Ericsson”的实际语料没误伤不代表所有姓名缩写安全。
- 全库对这些格式再查：3个`**`脚注未命中list_item，但当前没有候选；`-Louis Debierne...`也是已过滤残片。S.K.I./A. K./K. Anders为合法缩写，不应误报。没有新增真实的auto列表漏网。

复现：用review_reasons分别喂上述字符串；姓名例先把两句传list_letters，再传所得letters。建议未来扩充格式时结合段落/list上下文和保守待审，补这些反例，勿只逐个扩正则字符。

### V5 — 建议：at_start与at_end可同时开启，校验不拒绝且实际按末尾处理

位置：`scripts/reading_jijing_text_fixes.py:60` apply_fix、`:128` check_fix_kind。

复现：构造find=`A`、replace=`A!`、paragraph_label=`A`、`at_start=True`、`at_end=True`，输入`Z A`。check_fix_kind接受；apply_fix返回`Z A!`、True，尽管输入不以A开头。这是两个互相矛盾的定位选项，被at_end的先行分支静默覆盖。本轮725条表中没有双开条目，所以不计当前数据损坏。

建议：定位选项互斥校验，并考虑summary与段首/段尾定位组合的明确规则。实际新增at_start条目的幂等、首部校验和questions互斥均通过。

## 第八轮说明和原文修订覆盖

1619630的29条说明逐条比较旧/新文本，9补、13去、7保留改写；去掉前缀后实际文字改写25条。22个文件除difficult_points之外相同，句子数不变。下表序号是本报告稳定排序，不是清单第十一节行号。

| 序 | 位置/难点序号 | 判定 |
| --- | --- | --- |
| 1 | ielts4_test4_p1 E-22/1 | 保留；已限定一般情况与本句不可恢复的省略，A8措辞关闭 |
| 2 | 11_103_p1 D-04/2 | 补前缀；缺陷说明准确且位于前部 |
| 3 | 11_103_p2 F-04/2 | 补前缀；缺陷说明准确且位于前部 |
| 4 | 11_103_p2 F-05/1 | 补前缀；缺陷说明准确且位于前部 |
| 5 | 13_6_p1 B-03/1 | 去前缀；合法用法/文风建议讲解成立 |
| 6 | 16_97_p1 B-08/2 | 去前缀；合法用法/文风建议讲解成立 |
| 7 | 18_53_p1 C-02/2 | 去前缀；合法用法/文风建议讲解成立 |
| 8 | 18_53_p1 D-01/1 | 补前缀；缺陷说明准确且位于前部 |
| 9 | 18_53_p2 F-09/2 | 去前缀；合法用法/文风建议讲解成立 |
| 10 | 22_90_p2 D-12/1 | 去前缀；合法用法/文风建议讲解成立 |
| 11 | 24_56_p3 C-05/3 | 去前缀；合法用法/文风建议讲解成立 |
| 12 | 27_33_p2 A-03/2 | 保留；triple动词合法，ability与数量比值语义不符的理由成立 |
| 13 | 44_29_p2 E-03/1 | 补前缀；分号后无限定谓语，两种建议均可 |
| 14 | 46_84_p1 E-01/3 | 补前缀；缺陷说明准确且位于前部 |
| 15 | 48_21_p3 K-02/2 | 保留待审；已承认可数/不可数两解，不当作必错 |
| 16 | 48_21_p3 K-04/2 | 去前缀；合法用法/文风建议讲解成立 |
| 17 | 50_30_p3 B-03/2 | 保留待审；语域讲解成立，口语本身非必然语病 |
| 18 | 53_83_p1 C-01/2 | 保留待审；补出名词需上文，独立题句依赖语境 |
| 19 | 53_83_p3 C-06/3 | 去前缀；合法用法/文风建议讲解成立 |
| 20 | 62_44_p1 E-01/1 | 去前缀；合法用法/文风建议讲解成立 |
| 21 | 62_44_p3 C-05/2 | 保留待审；嗅觉与某种气味区别正确 |
| 22 | 62_44_p3 F-01/2 | 去前缀；合法用法/文风建议讲解成立 |
| 23 | 62_44_p3 H-05/2 | 去前缀；合法用法/文风建议讲解成立 |
| 24 | 65_69_p2 D-04/3 | 补前缀；缺陷说明准确且位于前部 |
| 25 | 65_69_p2 E-05/2 | 保留待审；已承认复数并列/同一过程两解 |
| 26 | 71_1_p2 E-02/2 | 去前缀；合法用法/文风建议讲解成立 |
| 27 | 71_1_p2 H-05/1 | 补前缀；缺陷说明准确且位于前部 |
| 28 | 76_43_p1 B-01/3 | 去前缀；合法用法/文风建议讲解成立 |
| 29 | 76_43_p3 C-06/2 | 补前缀；缺陷说明准确且位于前部 |

无前缀复扫：逐句检索“原文、源文、疑为、应为、拼写、误写、笔误、OCR、识别、转录、残缺、脱漏、排版、不规范、不完整、缺少、不一致、生硬、规范写法、断裂、截断、语病、不自然、不通顺、不平行、没有谓语、没有主谓、不合、悬垂、误植、错位、不准确、缺失、乱码”，去除该句已有前缀者后165条，全部阅读句子与说明。多为词义/合法省略/修辞片段/标题/引语跨句/风格选择，没有新确认“已经描述明确缺陷却漏前缀”。这不是语法正确性的全量证明：V1的说明并未说源句有问题，错误在题目类别；V2也说明未被难点覆盖的排印仍可漏。

725条修订相对702条新增23条（当前数组1基索引如下）：2处原文引号、1处对应题目弯引号、1处段首恢复、19处排印。19处中14条questions=true；旧串在各自groups均不再残留；另外5篇对应串原未出现在题目中。整个第八轮groups有66个字符串字段变化，逐条均可归到这些替换，未顺带改答案。

| 修订表1基索引 | 位置 | 修订 | 判定 |
| --- | --- | --- | --- |
| 34 | 91_49_p1 C | processing." There's → processing. "There's | 正确；C-01末开引号移至C-02 |
| 35 | 91_49_p1 None | processing.” There’s → processing. “There’s | 正确；题目弯引号同步，3字段 |
| 540 | 23_46_p1 B | compiled. → compiled.' | 正确；依据现有题目中的闭合引号；未改其已有正确引语 |
| 554 | 32_20_p3 A | The various findings → [raw sub_title两句] The various findings | 正确；仅段首，原A-01改A-01c |
| 702 | 77_16_p3 E | unpre-pared → unprepared | 正确；题目已同步 |
| 703 | 77_16_p3 F | e-busi-ness → e-business | 正确；题目已同步 |
| 704 | 77_16_p3 G | under-mining → undermining | 正确；题目已同步 |
| 705 | 77_16_p3 J | legiti-mately → legitimately | 正确；题目无对应旧串 |
| 707 | 26_72_p2 C | post- glacial → post-glacial | 正确；题目已同步 |
| 712 | 26_72_p3 B | modern- day → modern-day | 正确；题目已同步 |
| 713 | 26_72_p3 E | post- classical → post-classical | 正确；题目已同步 |
| 714 | 47_86_p3 H | sacri-lice → sacrifice | 正确；题目无对应旧串 |
| 715 | 52_62_p1 F | mountain- climbing → mountain-climbing | 正确；题目已同步 |
| 716 | 52_62_p2 G | Noil-Rapid → Non-Rapid | 正确；题目无对应旧串 |
| 717 | 49_105_p1 H | your- shoulder → your shoulder | 正确；题目已同步 |
| 718 | 57_37_p1 B | attention- absorbing → attention-absorbing | 正确；题目已同步 |
| 719 | 31_99_p1 I | Urbana- Champaign → Urbana-Champaign | 正确；题目已同步 |
| 720 | 77_16_p1 F | Terra- Cotta → Terra-Cotta | 正确；题目已同步 |
| 721 | 60_101_p2 A | love-bate → love-hate | 正确；题目已同步 |
| 722 | 60_101_p2 F | built- in → built-in | 正确；题目已同步 |
| 723 | 60_101_p2 G | attention-al → attentional | 正确；题目无对应旧串 |
| 724 | 23_46_p3 J | long- lasting → long-lasting | 正确；题目无对应旧串 |
| 725 | 28_76_p3 C | leaf- eaters → leaf-eaters | 正确；题目已同步 |

32_20_p3新A-01“减肥领域像盲人摸象寓言”、A-01b“各人调查象的不同部分、回报后发现互不相容”的译文、成分、难点、表达均对应本句；A-01c与原A-01除ID/index完全相同。旧ID没有代码中的硬编码引用；保存词表达的sentence_id是来源元数据、读取按normalized_text等字段，当前未找到以旧A-01查取解析内容的依赖。本轮没有查询生产收藏数据，不能声称已有外部记录都自动迁移。

17篇subtitle全部核对：32_20_p3在4个中心/定位字段有20词原句引用；65_69_p2题干与subtitle共6词“the future population of the world”是主题用词重合，其余均无直接原句引用。不能把“只有这一篇有直接缺失引文”扩大成“其他subtitle与任何题干没有相同词”。summary与target_para原始编号偏移仍保留；Q27解析仍有已知不对应内容，见V3。

复扫1198处连字符命中时保留正常复合词、作者用作破折号的连接、悬挂连字符和Co-lor分音节读法；没有依据把历史拼法或专有形式机械全部合词。新确定问题详见V2。

## 规则、计数与A8补充

DASH只在两侧数字时排除区间的判断，使用相同文本、相同已缓存parse分别运行26fc46d与5eb的正则；625个相关来源句仅U6的T5答案不同，旧[0,45)→新[0,47)。句中数字右侧相邻插入语的`2010–a`与真实`increase - 93% of it -`测试旧版失败；5–10/5 - 10不补回。

负向测试准确口径：旧DASH实现1项断言失败；旧at_start实现3项断言失败；新字母列表测试在旧模块导入list_letters时报ImportError（接口不存在），另用原review_reasons既有测试断言失败。不能将接口错误写成全部断言失败。第七轮旧测试1失败/3错误及另3个列表无适用题型的文档更正，与上轮记录一致。

当前29个列表命中中只有15句出候选；0 auto泄漏。source_quality有149句、616题，只有该类审核原因的418题；list_item有15句、55题，只因此待审50题。实际reason总数允许同题还有其他原因，不应把616或55都当“新增降级题”。两个池以source_quality/list_item计数，所有已识别句的题均needs_review。

T2多解：独立对4705道auto T2找同类依存中心，733道有额外中心，其中436道额外中心均不满足finite；再要求finite并通过现type_matches后剩279道（名词性146、定语70、状语55、并列8）。所以“粗解析有大量把非谓语算成从句的假阳性”有依据；Claude的约440没有提交同一口径脚本，本报告不声称复现那个精确数字。

对279道排序后用20261030抽30道，再人工看额外目标：12道明确同类多解、17道解析/类别假阳性、1道评注结构需统一体系。明确多解原例gi_v02_14851b9ac5f7、gi_v02_603bed69f245仍auto；本轮表内和50句也再次抽到。建议T2给定位线索/指定先行词或接受多个有效跨度，不能以“粗估多误报”免除实际多解；T5同句多独立主语也应在题干指定主句。属于前审A8延续，不算新增应修数。

### A8补充30例（同种子20261030）

| 序 | 题号 | 来源 | 额外同类从句判断 |
| --- | --- | --- | --- |
| 1 | gi_v02_5acc4763fc65 | ielts20_test2_p1 C-04 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 2 | gi_v02_5977622893c6 | ielts7_test3_p3 B-13 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 3 | gi_v02_5f0ef54d09d6 | 22_90_p2 F-18 | 明确有另一同类从句，题干多解 |
| 4 | gi_v02_c3ef84ad9afa | ielts12_test7_p3 D-02 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 5 | gi_v02_7e4b2d2af464 | 85_12_p1 A-05 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 6 | gi_v02_96670a2318b3 | ielts4_test4_p1 I-41 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 7 | gi_v02_85aa120e3c73 | ielts5_test1_p1 D-04 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 8 | gi_v02_3441424f2e77 | ielts15_test2_p1 E-01 | 明确有另一同类从句，题干多解 |
| 9 | gi_v02_c622947f5a2f | ielts7_test4_p1 G-03 | 明确有另一同类从句，题干多解 |
| 10 | gi_v02_862b06a517e7 | ielts5_test3_p3 D-27 | as评注结构需统一教学分类，保留待判 |
| 11 | gi_v02_d33dd4c9083b | 22_90_p2 G-22 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 12 | gi_v02_0623f11e7d49 | ielts15_test3_p3 J-02 | 明确有另一同类从句，题干多解 |
| 13 | gi_v02_fae6e08ca96a | ielts16_test1_p3 I-01 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 14 | gi_v02_b46694839f1b | ielts16_test4_p2 D-01 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 15 | gi_v02_b5d7b7e007a1 | ielts14_test2_p3 D-02 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 16 | gi_v02_de9eb638dce2 | ielts11_test4_p1 H-01 | 明确有另一同类从句，题干多解 |
| 17 | gi_v02_b214981b5ee3 | ielts5_test3_p2 C-04 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 18 | gi_v02_6a0127a076c2 | ielts9_test1_p3 E-32 | 明确有另一同类从句，题干多解 |
| 19 | gi_v02_eada17f28b37 | 40_75_p2 A-02 | 明确有另一同类从句，题干多解 |
| 20 | gi_v02_d8f21b346abf | 92_58_p2 C-02 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 21 | gi_v02_ceb9f95d0589 | 22_90_p3 C-01 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 22 | gi_v02_8d12000ccc0a | ielts6_test4_p1 E-23 | 明确有另一同类从句，题干多解 |
| 23 | gi_v02_b9e365d3791d | ielts14_test3_p1 G-01 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 24 | gi_v02_7f34f75b0e68 | ielts13_test2_p2 B-03 | 明确有另一同类从句，题干多解 |
| 25 | gi_v02_c67e629acd96 | 72_15_p2 C-06 | 明确有另一同类从句，题干多解 |
| 26 | gi_v02_a17290f02a9f | ielts7_test4_p1 D-08 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 27 | gi_v02_6c40d4341647 | 16_97_p2 D-28 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |
| 28 | gi_v02_6ddd214b1085 | 76_43_p2 A-02 | 明确有另一同类从句，题干多解 |
| 29 | gi_v02_4285f7c2a9c4 | ielts19_test1_p3 C-01 | 明确有另一同类从句，题干多解 |
| 30 | gi_v02_7e6afffd550d | ielts20_test3_p3 F-02 | 假阳性：主句/引语/其他类别或重叠解析，不能当成额外同类目标 |

## 生成环境与两次SHA-256

Mac/macOS27.0.1 arm64；Python3.13.3；spaCy3.8.16；en_core_web_trf3.8.0；torch2.14.1；openpyxl3.1.5；CPU；生成seed20261018。reading_study_sha256=`b5d17e8c949a0ce5e005c05dfea7ecbff5a802404bc6129f462953521f0d6c6b`；grammar_graph_sha256=`c7b35ddb68db7601ccd01e38a210ad3dd772ff507302190f68a351e408b85a29`。

在仓库外完整5eb快照运行生成器，避免覆盖被审交付文件。复用上轮本机已独立验证的parse缓存，新增/变化文本按原缓存键自动解析；本提示未要求删缓存冷启动。本轮两次均运行完整候选生成。4a基线候选池使用前轮本机独立生成结果，并重新验证327个相关源码/语料文件均与4a git对象一致，基线报告也仅Python版本行不同。不是把Claude报告当作旧候选池。

| 文件 | 第一次SHA-256 | 第二次SHA-256 | 与提交版 |
| --- | --- | --- | --- |
| generation_report_v0_2.md | `0353206509a9f9d9befa2efe15ae802abeebcd6a08f1bcee19e124f02e0d047c` | `0353206509a9f9d9befa2efe15ae802abeebcd6a08f1bcee19e124f02e0d047c` | 仅Python版本行3.11.15→3.13.3；提交SHA `d840e8303e1eda912a1ab4344ab587c737f7f3183e8b37a8370f3ac2cf8be927` |
| generation_report_v0_2.json | `44244b1a15cc18b42211439d94aa087e19be0f065b37524117e83f1294dec346` | `44244b1a15cc18b42211439d94aa087e19be0f065b37524117e83f1294dec346` | 仅Python版本行3.11.15→3.13.3；提交SHA `64c628fe0dc672506583eaa709a2063551d532f7fd2e4c2cf991422805b80549` |
| review_batch_v0_2.xlsx | `4d18539cfee9c1638690bbcc2233786a9b270ada3da8e98ea113526dc264ead9` | `4d18539cfee9c1638690bbcc2233786a9b270ada3da8e98ea113526dc264ead9` | 完全一致 |
| review_batch_v0_2.jsonl | `ba6bbe12e9f79956a923149b018f1be8c068b36a343ba4aea2a3522028a71c67` | `ba6bbe12e9f79956a923149b018f1be8c068b36a343ba4aea2a3522028a71c67` | 完全一致 |

四文件两次byte相等；两报告把单一Python版本字节替换回3.11.15后与提交文件完全相等。JSONL/XLSX与用户给出的完整SHA一致。

| 模板/工作表 | auto_pass | needs_review | rejected |
| --- | --- | --- | --- |
| T1 / 主句谓语 | 5926 | 452 | 6368 |
| T2 / 从句边界 | 4705 | 2559 | 2692 |
| T3 / 从句类型 | 11465 | 3422 | 1331 |
| T4 / 状语关系 | 404 | 653 | 2565 |
| T5 / 完整主语 | 5377 | 806 | 6563 |
| T6 / 动词身份 | 12749 | 1730 | 6550 |

总候选50248；全库句子12746。resplit固定基线12657，added96/removed7/net_change89。七项整句过滤实际/预期分别为tagged_fragment30、clause_attached_to_conjunction2、glued0、multi_sentence_unit1、suspected_split_word0、leading_stray_punctuation0、control_character0。

13句×6模板回归记录与4a完全相同（状态、原因、拒绝/无适用均逐对象比较），逐句汇总如下。A/R分别为auto_pass/needs_review；“-”为该模板没有候选，并不统一解释为拒绝。

| 来源 | T1 | T2 | T3 | T4 | T5 | T6 | 拒绝/说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ielts7_test3_p1 K-03 | - | - | - | - | - | - | too_short,unbalanced_quotes_or_brackets |
| ielts8_test4_p1 C-04 | - | - | 1A/0R | - | - | 1A/0R | no_main_verb_tag |
| 76_43_p2 H-02 | 1A/0R | - | - | - | 0A/1R | 1A/0R | 无整句拒绝；保持此前逐题预期 |
| 73_5_p2 F-05 | - | - | - | - | - | - | tagged_fragment,unknown_span |
| 56_64_p2 C-01 | - | - | - | - | - | - | clause_attached_to_conjunction |
| ielts13_test2_p2 C-04 | - | - | - | - | - | - | clause_attached_to_conjunction |
| 91_49_p3 D-02 | 1A/0R | - | 2A/1R | - | 1A/0R | 3A/0R | 无整句拒绝；保持此前逐题预期 |
| ielts11_test3_p2 A-04 | 1A/0R | 1A/0R | 1A/0R | - | 1A/0R | 2A/0R | 无整句拒绝；保持此前逐题预期 |
| ielts15_test2_p3 D-05 | 1A/0R | 1A/0R | 2A/0R | - | 1A/0R | 1A/0R | 无整句拒绝；保持此前逐题预期 |
| ielts4_test2_p2 G-31 | - | 0A/1R | 0A/1R | 0A/1R | - | 1A/0R | no_main_verb_tag,split_subject |
| ielts6_test3_p1 C-06 | 0A/1R | 1A/0R | 1A/0R | - | 0A/1R | 1A/1R | 无整句拒绝；保持此前逐题预期 |
| 88_98_p2 G-04 | 1A/0R | 1A/0R | 1A/0R | - | 1A/0R | 2A/0R | 无整句拒绝；保持此前逐题预期 |
| 88_98_p2 G-04b | 1A/0R | 2A/0R | 2A/0R | - | 1A/0R | 2A/0R | 无整句拒绝；保持此前逐题预期 |

XLSX含说明+6题型共7工作表，各题型60数据行（Excel物理行2–61）；老师可见单元格没有auto_pass/needs_review，判定H2:H61为“正确 / 答案错 / 题目有歧义 / 句子不适合出题”四项下拉。360行与teacher_row逐单元格一致；说明中的连续/分段动词高亮写法与实际一致。

相对第七轮表：按item_id集合保留56道、304道新题；按(template,review_row)比较359行变化，唯一原位保留是T1序号14（Excel行15）gi_v02_f6daee0eb7f0。若老师已审旧表，按题号及版本迁移56道并核对内容，不能复制旧行号判定；本轮未联系老师或修改审核结果。

## 第14项抽查方法及分状态结果

种子均为20261030。表内抽查按T1–T6固定顺序，每表先筛pool_status=auto_pass、按item_id排序，用同一个random.Random连续sample5。恢复34、新增auto14、新降13、新增needs7、U6一题全数核对，按item_id排序，不随机删例。来源句抽查先把全auto池按(passage_id,sentence_id)去重排序，共9635句，另起Random(20261030)抽50；人工阅读全部50句及它们的198道auto题。不同抽查组可能重叠，不将分母相加冒充不同题总数。

- 表内30 auto：给定局部答案均可成立；28道未见题干歧义，2道存在多目标歧义（T2/T5）；30原句均可作阅读教学材料。
- 恢复34 + 新增auto14 + U6一题：49道给定局部答案与高亮均成立，原句可用。
- 新降13 needs：13道局部答案可成立；来源确有缺陷或属于用户决定排除的列表，降级合理，不计作自动题正确数。
- 新增7 needs：1道给定答案明确成立；3道有边界/答案问题；3道须统一报道插入语/主句分析，保留人工复核合理。来源原句可阅读，但题目不能一并称为“全正确”。
- 按句50/198 auto：50句未见所要求的残缺、明显语病、截断、列表片段（0/50）；局部答案195道可成立，其中2道明显T2多目标，另3道类别/题干前提不成立（V1）。0/50仅为该随机样本，源句缺陷率点估计0%，单侧95%二项上界约5.8%，不能据此写全池无缺陷。姓名错字V2来自另一次定向检查，没有混入随机比例。

各表“适合”仅指源句本身；须与“局部判断”同时阅读。题号保留完整，机经来源简写如32_20_p3=reading_jijing_32_test_20_p3。

### 14a 表内30道auto

“表序号/Excel行”避免把review_row与物理行混用。

| 序 | 题号 | 工作表 | 表序号/Excel行 | 来源 | 局部判断 | 整句 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_a3c38640b493 | 主句谓语 | 20 / 21 | 73_5_p1 J-02 | 答案、高亮成立 | 适合 |
| 2 | gi_v02_3dec9a07b93e | 主句谓语 | 42 / 43 | 44_29_p2 B-01 | 答案、高亮成立 | 适合 |
| 3 | gi_v02_a479ac7e4bac | 主句谓语 | 12 / 13 | ielts16_test3_p3 E-01 | 答案、高亮成立 | 适合 |
| 4 | gi_v02_61028905d351 | 主句谓语 | 21 / 22 | 83_95_p3 F-04 | 答案、高亮成立 | 适合 |
| 5 | gi_v02_737330ab63fd | 主句谓语 | 43 / 44 | 10_78_p3 E-01 | 答案、高亮成立 | 适合 |
| 6 | gi_v02_0351cf44000e | 从句边界 | 24 / 25 | ielts5_test2_p2 I-39 | 给定边界成立；另有that becomes active…同类定语，T2多解（A8） | 适合 |
| 7 | gi_v02_ed8fb1baf64e | 从句边界 | 46 / 47 | 32_20_p1 A-01 | 答案、高亮成立 | 适合 |
| 8 | gi_v02_a3b52ae0a74b | 从句边界 | 20 / 21 | ielts13_test1_p3 A-01 | 答案、高亮成立 | 适合 |
| 9 | gi_v02_ba8852fcbfea | 从句边界 | 14 / 15 | ielts9_test1_p2 A-01 | 答案、高亮成立 | 适合 |
| 10 | gi_v02_4ea6ad4aa7c8 | 从句边界 | 10 / 11 | 29_63_p1 C-01 | 答案、高亮成立 | 适合 |
| 11 | gi_v02_d4752091969b | 从句类型 | 11 / 12 | ielts8_test4_p1 E-04 | 答案、高亮成立 | 适合 |
| 12 | gi_v02_49251d88ac1f | 从句类型 | 15 / 16 | ielts12_test6_p1 H-05 | 答案、高亮成立 | 适合 |
| 13 | gi_v02_216edb07b2d2 | 从句类型 | 28 / 29 | ielts10_test3_p2 F-02 | 答案、高亮成立 | 适合 |
| 14 | gi_v02_5981761cf2aa | 从句类型 | 3 / 4 | ielts17_test2_p1 G-03 | 答案、高亮成立 | 适合 |
| 15 | gi_v02_5460edf88817 | 从句类型 | 40 / 41 | ielts9_test1_p1 J-07 | 答案、高亮成立 | 适合 |
| 16 | gi_v02_815e7e5061e0 | 状语关系 | 21 / 22 | 48_21_p3 G-05 | 答案、高亮成立 | 适合 |
| 17 | gi_v02_4c972ce0bfc7 | 状语关系 | 49 / 50 | ielts4_test2_p1 F-31 | 答案、高亮成立 | 适合 |
| 18 | gi_v02_cfba8980f839 | 状语关系 | 27 / 28 | 16_97_p3 A-04 | 答案、高亮成立 | 适合 |
| 19 | gi_v02_4f610b65dea0 | 状语关系 | 1 / 2 | 46_84_p3 I-02 | 答案、高亮成立 | 适合 |
| 20 | gi_v02_3bee56937208 | 状语关系 | 8 / 9 | 13_6_p2 E-22 | 答案、高亮成立 | 适合 |
| 21 | gi_v02_08d18a89f1d9 | 完整主语 | 33 / 34 | ielts20_test2_p3 H-41 | 答案、高亮成立 | 适合 |
| 22 | gi_v02_6694490dbc12 | 完整主语 | 39 / 40 | ielts12_test8_p2 H-06 | 答案、高亮成立 | 适合 |
| 23 | gi_v02_3b31d567de6a | 完整主语 | 27 / 28 | ielts11_test2_p2 C-03 | 答案、高亮成立 | 适合 |
| 24 | gi_v02_d432012fe04e | 完整主语 | 50 / 51 | ielts4_test3_p1 E-02 | 答案、高亮成立 | 适合 |
| 25 | gi_v02_74d818b03e17 | 完整主语 | 8 / 9 | 9_81_p1 J-01 | 给定主语成立；and后另有projects主语，题干未指定分句，T5多目标 | 适合 |
| 26 | gi_v02_f638bc92e93b | 动词身份 | 15 / 16 | ielts9_test1_p1 G-02 | 答案、高亮成立 | 适合 |
| 27 | gi_v02_93f4c297e2e7 | 动词身份 | 31 / 32 | ielts16_test3_p1 F-02 | 答案、高亮成立 | 适合 |
| 28 | gi_v02_bba6ba5ed14d | 动词身份 | 11 / 12 | ielts9_test2_p3 F-07 | 答案、高亮成立 | 适合 |
| 29 | gi_v02_8039d2e2fcdb | 动词身份 | 49 / 50 | ielts10_test3_p2 I-03 | 答案、高亮成立 | 适合 |
| 30 | gi_v02_5e0034c6decb | 动词身份 | 3 / 4 | 84_73_p1 A-06 | 答案、高亮成立 | 适合 |

### 14b 全部34道恢复auto

| 序 | 题号 | 模板 | 来源 | 机器答案 | 局部判断 | 整句 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_0192d4c5fa60 | T3 | 76_43_p1 B-01 | 不是从句（短语或非谓语） | 答案/高亮成立 | 适合 |
| 2 | gi_v02_0691c9c1f328 | T6 | 76_43_p1 B-01 | 非谓语（不定式、分词、动名词） | 答案/高亮成立 | 适合 |
| 3 | gi_v02_07b9515951ec | T5 | 24_56_p3 C-05 | The immediate impact on sailors' health and incidence of scurvy on board ship | 答案/高亮成立 | 适合 |
| 4 | gi_v02_1531cbc45969 | T6 | 16_97_p1 B-08 | 主句谓语 | 答案/高亮成立 | 适合 |
| 5 | gi_v02_1ac748427583 | T1 | 48_21_p3 K-04 | will / try | 答案/高亮成立 | 适合 |
| 6 | gi_v02_25ddb831282f | T3 | 13_6_p1 B-03 | 不是从句（短语或非谓语） | 答案/高亮成立 | 适合 |
| 7 | gi_v02_262f33110265 | T2 | 24_56_p3 C-05 | that the curative effect was acid based | 答案/高亮成立 | 适合 |
| 8 | gi_v02_2c32f0907835 | T5 | 62_44_p1 E-01 | Controversy | 答案/高亮成立 | 适合 |
| 9 | gi_v02_2d02c212cf17 | T1 | 16_97_p1 B-08 | argued | 答案/高亮成立 | 适合 |
| 10 | gi_v02_31aef76eca37 | T2 | 24_56_p3 C-05 | as Lind and other physicians remained convinced that the curative effect was acid based | 答案/高亮成立 | 适合 |
| 11 | gi_v02_34d65907e146 | T1 | 22_90_p2 D-12 | was | 答案/高亮成立 | 适合 |
| 12 | gi_v02_47a154891c02 | T1 | 24_56_p3 C-05 | was | 答案/高亮成立 | 适合 |
| 13 | gi_v02_4b0da9e4b63b | T6 | 62_44_p1 E-01 | 主句谓语 | 答案/高亮成立 | 适合 |
| 14 | gi_v02_4b66e7a77c08 | T5 | 16_97_p1 B-08 | paleoecologist John Alroy of the University of California at Santa Barbara | 答案/高亮成立 | 适合 |
| 15 | gi_v02_51d720a95be3 | T6 | 22_90_p2 D-12 | 主句谓语 | 答案/高亮成立 | 适合 |
| 16 | gi_v02_530b1a7710f5 | T6 | 13_6_p1 B-03 | 非谓语（不定式、分词、动名词） | 答案/高亮成立 | 适合 |
| 17 | gi_v02_682532435235 | T6 | 48_21_p3 K-04 | 主句谓语 | 答案/高亮成立 | 适合 |
| 18 | gi_v02_6e7613284d43 | T3 | 24_56_p3 C-05 | 名词性从句 | 答案/高亮成立 | 适合 |
| 19 | gi_v02_869abf87a507 | T6 | 62_44_p1 E-01 | 从句里的谓语 | 答案/高亮成立 | 适合 |
| 20 | gi_v02_8a0553c46ba2 | T1 | 62_44_p1 E-01 | surrounds | 答案/高亮成立 | 适合 |
| 21 | gi_v02_8aaaaf0eb86e | T1 | 13_6_p1 B-03 | saw | 答案/高亮成立 | 适合 |
| 22 | gi_v02_94617917d17e | T2 | 48_21_p3 K-04 | how rising temperatures would affect the ratio of sex reversal in their growth | 答案/高亮成立 | 适合 |
| 23 | gi_v02_9716e32b633b | T5 | 13_6_p1 B-03 | The government | 答案/高亮成立 | 适合 |
| 24 | gi_v02_9b4fa0fdc112 | T6 | 24_56_p3 C-05 | 从句里的谓语 | 答案/高亮成立 | 适合 |
| 25 | gi_v02_a1dbb84b3abd | T3 | 16_97_p1 B-08 | 名词性从句 | 答案/高亮成立 | 适合 |
| 26 | gi_v02_a58faf112fdf | T2 | 16_97_p1 B-08 | that, in fact, hunting-driven extinction is not only plausible, it was unavoidable | 答案/高亮成立 | 适合 |
| 27 | gi_v02_ab777d0dff86 | T3 | 62_44_p1 E-01 | 名词性从句 | 答案/高亮成立 | 适合 |
| 28 | gi_v02_aecb04245d92 | T3 | 24_56_p3 C-05 | 状语从句 | 答案/高亮成立 | 适合 |
| 29 | gi_v02_af52c096bf63 | T5 | 22_90_p2 D-12 | the average amount of sleep | 答案/高亮成立 | 适合 |
| 30 | gi_v02_d83aa7c70e7b | T5 | 48_21_p3 K-04 | Further researches | 答案/高亮成立 | 适合 |
| 31 | gi_v02_e3b7bbd98166 | T6 | 13_6_p1 B-03 | 主句谓语 | 答案/高亮成立 | 适合 |
| 32 | gi_v02_eb2384f857a0 | T2 | 62_44_p1 E-01 | that Reiki may offer only a perceived improvement in health and therefore only a 'placebo' effect | 答案/高亮成立 | 适合 |
| 33 | gi_v02_f310ee02ef3c | T3 | 13_6_p1 B-03 | 不是从句（短语或非谓语） | 答案/高亮成立 | 适合 |
| 34 | gi_v02_f48aa0b22507 | T3 | 48_21_p3 K-04 | 名词性从句 | 答案/高亮成立 | 适合 |

### 14c 全部14道新增auto

| 序 | 题号 | 模板 | 来源 | 机器答案 | 局部判断 | 整句 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_05f0902060b5 | T6 | 32_20_p3 A-01b | 非谓语（不定式、分词、动名词） | 答案/高亮成立 | 适合 |
| 2 | gi_v02_3d3b7ca923be | T3 | 32_20_p3 A-01 | 不是从句（短语或非谓语） | 答案/高亮成立 | 适合 |
| 3 | gi_v02_4576af99d437 | T6 | 23_46_p1 B-04b | 从句里的谓语 | 答案/高亮成立 | 适合 |
| 4 | gi_v02_5a5fbdea3bfa | T2 | 32_20_p3 A-01b | their findings are bafflingly incompatible | 答案/高亮成立 | 适合 |
| 5 | gi_v02_5b1537405925 | T2 | 23_46_p1 B-04b | we have compiled | 答案/高亮成立 | 适合 |
| 6 | gi_v02_6b90d51fbb71 | T3 | 32_20_p3 A-01b | 不是从句（短语或非谓语） | 答案/高亮成立 | 适合 |
| 7 | gi_v02_7ab398c5bc8f | T3 | 32_20_p3 A-01b | 名词性从句 | 答案/高亮成立 | 适合 |
| 8 | gi_v02_7b30d37c4f54 | T1 | 32_20_p3 A-01c | are | 答案/高亮成立 | 适合 |
| 9 | gi_v02_7e19909ddc80 | T5 | 32_20_p3 A-01c | The various findings by public-health experts, physicians, psychologists, geneticists, molecular biologists, and nutritionists | 答案/高亮成立 | 适合 |
| 10 | gi_v02_7f16e9da0193 | T3 | 23_46_p1 B-04b | 定语从句 | 答案/高亮成立 | 适合 |
| 11 | gi_v02_ab2130e7e047 | T6 | 32_20_p3 A-01c | 主句谓语 | 答案/高亮成立 | 适合 |
| 12 | gi_v02_d36c4614247e | T5 | 32_20_p3 A-01 | The field of weight loss | 答案/高亮成立 | 适合 |
| 13 | gi_v02_d4bd7eaee9a9 | T6 | 32_20_p3 A-01 | 主句谓语 | 答案/高亮成立 | 适合 |
| 14 | gi_v02_d6e0e9cae61d | T1 | 32_20_p3 A-01 | is | 答案/高亮成立 | 适合 |

### 14d U6唯一内容变化auto

| 序 | 题号 | 模板 | 来源 | 机器答案 | 局部判断 | 整句 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_ed4743fde6b9 | T5 | 29_63_p3 A-03 | Some $265 billion of the increase - 93% of it - | 答案/高亮成立 | 适合 |

### 14e 全部13道新降needs_review

| 序 | 题号 | 模板 | 来源 | 局部判断 | 降级理由 | 整句 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_1bf875b153ab | T1 | 11_103_p1 D-04 | 给定局部答案成立 | 列举缺分隔标点；降级合理 | 暂不作规范孤立例句 |
| 2 | gi_v02_27d3c08223ec | T2 | 18_53_p1 D-01 | 给定局部答案成立 | amount与were数不一致；降级合理 | 暂不作规范孤立例句 |
| 3 | gi_v02_2d357f01c108 | T6 | 71_1_p2 H-05 | 给定局部答案成立 | Being unique悬垂；降级合理 | 暂不作规范孤立例句 |
| 4 | gi_v02_3c7d9ae46f32 | T2 | 71_1_p2 H-05 | 给定局部答案成立 | Being unique悬垂；降级合理 | 暂不作规范孤立例句 |
| 5 | gi_v02_591bc49301cc | T3 | 71_1_p2 H-05 | 给定局部答案成立 | Being unique悬垂；降级合理 | 暂不作规范孤立例句 |
| 6 | gi_v02_86aa87e33ae9 | T1 | 44_29_p2 E-03 | 给定局部答案成立 | 分号后无限定谓语；降级合理 | 暂不作规范孤立例句 |
| 7 | gi_v02_c851a19e35f7 | T3 | 18_53_p1 D-01 | 给定局部答案成立 | amount与were数不一致；降级合理 | 暂不作规范孤立例句 |
| 8 | gi_v02_da792cb22d98 | T1 | 32_20_p2 I-01 | 给定局部答案成立 | 列表编号B项；降级合理 | 暂不作规范孤立例句 |
| 9 | gi_v02_dae615711704 | T5 | 44_29_p2 E-03 | 给定局部答案成立 | 分号后无限定谓语；降级合理 | 暂不作规范孤立例句 |
| 10 | gi_v02_e11e0f28ba87 | T6 | 44_29_p2 E-03 | 给定局部答案成立 | 分号后无限定谓语；降级合理 | 暂不作规范孤立例句 |
| 11 | gi_v02_e93a03c0a486 | T6 | 32_20_p2 I-01 | 给定局部答案成立 | 列表编号B项；降级合理 | 暂不作规范孤立例句 |
| 12 | gi_v02_f5424d51fb10 | T6 | 11_103_p1 D-04 | 给定局部答案成立 | 列举缺分隔标点；降级合理 | 暂不作规范孤立例句 |
| 13 | gi_v02_ffa3d1f99b40 | T6 | 18_53_p1 D-01 | 给定局部答案成立 | amount与were数不一致；降级合理 | 暂不作规范孤立例句 |

### 14f 全部7道新增needs_review

| 题号 | 模板 | 来源 | 局部判断 | 降级/整句 |
| --- | --- | --- | --- | --- |
| gi_v02_19d199aabbd6 | T6 | 91_49_p1 C-01 | is为从句谓语，给定答案成立；ambiguous_span_location保守复核 | 保留待审合理；原句可阅读 |
| gi_v02_26b0a5dfa347 | T3 | 91_49_p1 C-01 | 定语类别对；who…范围漏掉Mascoma的同位说明a leading developer…，边界不完整 | 保留待审合理；原句可阅读 |
| gi_v02_4a157b567ec4 | T1 | 91_49_p1 C-01 | reports可作报道主句谓语；are working内容主句分析也存在，需统一主句口径 | 保留待审合理；原句可阅读 |
| gi_v02_4a2c0e237eb8 | T5 | 91_49_p1 C-01 | scientists and engineers是内容分句主语；与reports分析需统一，题干需指定 | 保留待审合理；原句可阅读 |
| gi_v02_6cf32194f36c | T5 | 23_46_p1 B-04b | 答案错误：however不属主语；应为Some scientists | 保留待审合理；原句可阅读 |
| gi_v02_7633c07eecaf | T2 | 91_49_p1 C-01 | who…从句边界漏掉a leading developer…同位成分，不完整 | 保留待审合理；原句可阅读 |
| gi_v02_ae32591c90ff | T6 | 91_49_p1 C-01 | reports身份依赖同句报道插入语的主句分析，保留待审 | 保留待审合理；原句可阅读 |

### 14g 按句抽50：全部来源及其auto题号

| 序 | 来源 | 原句 | auto数 | 全部题号 | 局部判断 | 整句适用性 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 83_95_p3 F-04 | The role of the chief is crucial. | 3 | T6:gi_v02_286c671eb2dc<br>T1:gi_v02_61028905d351<br>T5:gi_v02_b55f7b86f5d9 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 2 | ielts19_test1_p3 E-04 | Descartes argued that a person only accepts or rejects information after considering its truth or falsehood; Spinoza argued that people accept all encountered information (or misinformation) by default and then subsequently verify or reject it through a separate cognitive process. | 4 | T3:gi_v02_804b7cc8566b<br>T3:gi_v02_bce5f1761b83<br>T3:gi_v02_c2d0496b1437<br>T2:gi_v02_db5f3603425c | 给定答案成立；T2另有Spinoza后的that从句，题干多解 | 未见指定源句缺陷，可阅读 |
| 3 | 88_98_p1 G-03 | The Mweru and Bangweulu Lake Basins are the main areas of year-round fishing, but the Luapula River is also exploited during the latter part of the dry season. | 2 | T2:gi_v02_3beba37fd94b<br>T3:gi_v02_7b0fa3260e3a | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 4 | ielts7_test2_p1 I-44b | Here again, Japanese master builders of a thousand years ago anticipated concepts of modern structural engineering. | 3 | T1:gi_v02_436efdce5920<br>T5:gi_v02_4c741b101b62<br>T6:gi_v02_f0ffd8f66d08 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 5 | 14_23_p3 H-02 | It just takes the pressure off driving. | 3 | T1:gi_v02_4a11d324d296<br>T6:gi_v02_7beae49d2d46<br>T5:gi_v02_c72805140757 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 6 | ielts11_test3_p1 A-03 | One account of the story goes that as she was taking a walk in her husband's gardens, she discovered that silkworms were responsible for the destruction of several mulberry trees. | 8 | T6:gi_v02_15836e0f991f<br>T3:gi_v02_338fe04896e1<br>T6:gi_v02_452048b4a85b<br>T2:gi_v02_798904d67b97<br>T5:gi_v02_95c338453c34<br>T3:gi_v02_bf0e05edfdd9<br>T3:gi_v02_d84fb909f527<br>T1:gi_v02_f62d1e12f91a | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 7 | 73_5_p3 D-01 | Modern ecologists throw up their hands in horror at what they see as Hooker's environmental anarchy. | 4 | T6:gi_v02_17c12caa77fe<br>T5:gi_v02_8573a7e9175f<br>T3:gi_v02_8a4e22d6b8da<br>T1:gi_v02_d39f9bce1703 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 8 | ielts20_test4_p3 C-14 | 'If they are managed and used properly, livestock guard dogs are the most efficient control method that we have in terms of the amount of livestock that they save from predation,' says van Bommel. | 7 | T3:gi_v02_1055093311c3<br>T2:gi_v02_2f325d0df326<br>T6:gi_v02_65cc0022cff9<br>T4:gi_v02_83c7daa56698<br>T6:gi_v02_a97836d73e14<br>T3:gi_v02_acd785bd7463<br>T2:gi_v02_bd570cd789ff | 给定答案成立；T2另有that method…同类从句，题干多解 | 未见指定源句缺陷，可阅读 |
| 9 | ielts4_test2_p1 E-24 | The former US policy of running Indian reservation schools in English, for example, effectively put languages such as Navajo on the danger list. | 2 | T6:gi_v02_3cc400c5e2b9<br>T1:gi_v02_6af1a7aa856a | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 10 | ielts15_test1_p1 C-05 | As prices for pepper, nutmeg, and other spices soared across Europe, they decided to fight back. | 5 | T2:gi_v02_26506da0eb90<br>T6:gi_v02_26f369893e63<br>T6:gi_v02_2b080e3f276a<br>T3:gi_v02_80ef797ed3c5<br>T3:gi_v02_f76b316221a2 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 11 | ielts7_test3_p1 J-01 | And in a twelve-year programme of work, Ryabko and Reznikova have found evidence that ants can transmit very complex messages. | 3 | T5:gi_v02_228ae4379b22<br>T6:gi_v02_3d2ccba4f267<br>T1:gi_v02_520d19c49218 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 12 | ielts5_test1_p3 K-41 | Yet the cost of reducing carbon dioxide emissions, for the United States alone, will be higher than the cost of solving the world's single, most pressing health problem: providing universal access to clean drinking water and sanitation. | 2 | T6:gi_v02_0c103d59c50d<br>T1:gi_v02_2699fabdddaf | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 13 | 16_97_p1 B-08 | But at the annual meeting of the Society of Vertebrate Paleontology in Mexico City last October, paleoecologist John Alroy of the University of California at Santa Barbara argued that, in fact, hunting-driven extinction is not only plausible, it was unavoidable. | 5 | T6:gi_v02_1531cbc45969<br>T1:gi_v02_2d02c212cf17<br>T5:gi_v02_4b66e7a77c08<br>T3:gi_v02_a1dbb84b3abd<br>T2:gi_v02_a58faf112fdf | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 14 | ielts15_test4_p1 G-06 | 'I am investing in the future.' | 3 | T6:gi_v02_2e15b97bd418<br>T1:gi_v02_36a75d3813ec<br>T5:gi_v02_c9a4f6a1642b | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 15 | ielts16_test1_p2 C-03 | It had several plans … before it became the first Step Pyramid in history, piling six levels on top of one another … | 6 | T5:gi_v02_1dbcd4174d83<br>T6:gi_v02_2cf8b5692062<br>T6:gi_v02_78082f7291df<br>T3:gi_v02_9c6ef82b4ee8<br>T1:gi_v02_9dd58363e68b<br>T6:gi_v02_b27e8aceed63 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 16 | ielts16_test3_p2 H-04 | The researchers say that could be because many of those artefacts have already disintegrated or are still frozen in the ice. | 9 | T6:gi_v02_00eddfad0990<br>T1:gi_v02_2af7bee3bda5<br>T2:gi_v02_3bc99c523a8b<br>T6:gi_v02_63c4f6b2c59d<br>T4:gi_v02_6e7951e2acc7<br>T3:gi_v02_ba7e3ccad450<br>T2:gi_v02_bdee163d3f00<br>T3:gi_v02_bfb7654efc10<br>T5:gi_v02_fefbd914ffcc | 9题中6题局部成立；T2/T3/T4共3题类别/前提错误（V1） | 未见指定源句缺陷，可阅读 |
| 17 | ielts13_test2_p2 D-01 | Another discovery is that oxytocin's effects vary depending on who we are interacting with. | 4 | T3:gi_v02_56dd6233ca52<br>T3:gi_v02_a68c95f36041<br>T6:gi_v02_aad6d39743f0<br>T3:gi_v02_f16f1ee8ccba | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 18 | ielts11_test1_p1 A-05 | Historically, some 15% of that has been laid waste by poor management practices. | 3 | T6:gi_v02_5c246cc965c0<br>T1:gi_v02_accc901cac7a<br>T5:gi_v02_eeefdc1370cf | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 19 | ielts5_test1_p1 D-05 | Johnson signed the contract for the Dictionary with the bookseller Robert Dodsley at a breakfast held at the Golden Anchor Inn near Holborn Bar on 18 June 1764. | 7 | T6:gi_v02_0b1800e296c1<br>T5:gi_v02_4898e1aeb7e8<br>T1:gi_v02_54baa8f5df17<br>T3:gi_v02_791a18ecbe13<br>T3:gi_v02_a81999dcb195<br>T3:gi_v02_c9fbe40d0127<br>T6:gi_v02_f00229028fab | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 20 | ielts15_test4_p1 E-04 | In order to stop the Middle Ica Valley going the same way as the Lower Ica Valley, Whaley is encouraging locals to love the huarangos again. | 6 | T6:gi_v02_04d761b03932<br>T3:gi_v02_130718edc324<br>T1:gi_v02_1391362c7f09<br>T6:gi_v02_b469ac8d3746<br>T3:gi_v02_e22e35bc098f<br>T5:gi_v02_e70249150c2b | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 21 | ielts8_test1_p2 E-05 | Controlled airspace is that airspace in which FAA regulations apply. | 6 | T2:gi_v02_0799453b2d1d<br>T3:gi_v02_218537f93e76<br>T6:gi_v02_534f837a3533<br>T5:gi_v02_85816b89186a<br>T1:gi_v02_8e958ba8963f<br>T6:gi_v02_c69cc734a161 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 22 | 29_63_p3 G-04 | It is smaller even than India's 52%. | 3 | T5:gi_v02_31b36dc3b30b<br>T1:gi_v02_b4d6164148aa<br>T6:gi_v02_d7765d80524d | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 23 | 82_4_p3 F-06 | It would be just another forgotten drug that people hadn't bothered to explore. | 6 | T6:gi_v02_56edae7f05ba<br>T2:gi_v02_63b3ecf17970<br>T1:gi_v02_9b8b23ea2f73<br>T6:gi_v02_adea0437e7bb<br>T3:gi_v02_bd6655f29773<br>T5:gi_v02_f17c7a9527be | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 24 | 16_97_p3 C-01 | "Video games change your brain," according to University of Wisconsin psychologist Shawn Green. | 3 | T1:gi_v02_06297a46eca1<br>T6:gi_v02_444c70c73911<br>T5:gi_v02_fb011d2a5732 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 25 | ielts6_test4_p2 C-06 | By 1985, about 300,000 illiterate adults from all over the country, many of whom had never attended primary school, had learnt how to read, write and use numbers. | 6 | T6:gi_v02_259c1a3cb319<br>T2:gi_v02_3470c286f1b7<br>T6:gi_v02_34c56cc8e93a<br>T5:gi_v02_3d369aa6e3db<br>T3:gi_v02_49d30e490c4c<br>T1:gi_v02_9921980bf457 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 26 | ielts13_test3_p3 H-01 | Petrie believes that archaeologists are in a unique position to investigate how past societies responded to environmental and climatic change. | 4 | T6:gi_v02_336b5da5a57c<br>T3:gi_v02_4ad27b591110<br>T3:gi_v02_5e3d87b53902<br>T3:gi_v02_b2707dfc35f6 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 27 | ielts12_test5_p3 F-05 | As we have seen, someone could use the very same knowledge of means to achieve a much less noble end, such as personal profit via destructive, dangerous, reckless activity. | 5 | T3:gi_v02_199fe318f590<br>T3:gi_v02_48750ff8524a<br>T6:gi_v02_6fbbddd092f6<br>T6:gi_v02_b56d9bd7d7ff<br>T2:gi_v02_d2a927320702 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 28 | 56_64_p3 I-03 | One of the worst things you can do in terms of looking old is to go on a low-fat diet. | 3 | T5:gi_v02_397ec92a0812<br>T1:gi_v02_6e50b8b7fcf2<br>T6:gi_v02_788672f119d5 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 29 | ielts7_test2_p3 D-13 | Donkeys, which were imported to the district, have become more common and contribute, in particular, to the transportation of crops and goods to market. | 3 | T6:gi_v02_0eee62ae3df9<br>T3:gi_v02_560065448b15<br>T2:gi_v02_7308b5776041 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 30 | 10_78_p1 H-50 | The research, when applied to real-life situations, did not always improve the management process in real-life practice. | 2 | T6:gi_v02_1021599dc279<br>T1:gi_v02_6fbc49d2708c | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 31 | 65_69_p1 F-02 | 'I know certain pieces that are kind of "sticky" to me, so I will not play them in the early morning for fear that they will run around in my head all day,' says Steven Brown, who trained as a classical pianist but is now a neuroscientist at the University of Texas Health Science Center at San Antonio. | 4 | T6:gi_v02_149dd0cbff7d<br>T3:gi_v02_3f98d4f671aa<br>T3:gi_v02_54490f83925b<br>T6:gi_v02_a367f8c9dc90 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 32 | ielts17_test3_p2 F-06 | Crops vary in the degree to which they sequester carbon – in other words, the amount of carbon they capture from the atmosphere and store within the plant. | 7 | T6:gi_v02_1ff3682c1758<br>T3:gi_v02_40e22b9137ac<br>T6:gi_v02_45a278edd3f1<br>T5:gi_v02_64abc2895185<br>T6:gi_v02_78fd256e7457<br>T1:gi_v02_91d9fd7d79d6<br>T3:gi_v02_dfc7bf8738e4 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 33 | ielts20_test1_p2 D-02 | Not only was elm common in European forests, it became a key component of birch, ash and hazel woodlands. | 1 | T3:gi_v02_dad83c327e12 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 34 | ielts5_test4_p2 F-23 | Just a tenth of a gram of nickel in the furnace can create up to 50,000 crystals. | 3 | T6:gi_v02_b73b5e76620b<br>T1:gi_v02_dfb6cd649bf1<br>T5:gi_v02_ec261321d242 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 35 | ielts9_test2_p2 B-01 | For centuries, transits of Venus have drawn explorers and astronomers alike to the four corners of the globe. | 3 | T1:gi_v02_05f3aa86892c<br>T5:gi_v02_490ea4854dfa<br>T6:gi_v02_4f1d8041517d | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 36 | 85_12_p2 G-02 | It was decided that the force exerted by the pedestrians had to be quantified and related to the motion of the bridge. | 4 | T3:gi_v02_1fd35648e071<br>T3:gi_v02_6139690cbf97<br>T6:gi_v02_97bb04f4cb0f<br>T2:gi_v02_f8bb28aed6ba | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 37 | ielts16_test2_p2 G-04 | 'They actually help us become who we are,' says Yong. | 2 | T2:gi_v02_0200532761cc<br>T3:gi_v02_1751ba7cd480 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 38 | ielts17_test4_p1 A-05 | The result is devastating habitat and biodiversity loss on the island, but not all species are suffering. | 2 | T2:gi_v02_a39dfa34b9e1<br>T3:gi_v02_bb2fc9c4f692 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 39 | ielts10_test1_p3 E-05 | You can't brief people just by saying, 'We're going in this direction and I'm going to take you with me.' | 3 | T3:gi_v02_32fbc341d1be<br>T3:gi_v02_af4e1c611a73<br>T2:gi_v02_ff994a4069ff | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 40 | 44_29_p1 D-01 | Faced with such predation, cockroaches usually conceal themselves during the day, and with their ability to flatten their bodies, they can disappear into just about any tiny nook, crevice, and cranny. | 2 | T6:gi_v02_790922fb9d18<br>T3:gi_v02_d8b76de4d267 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 41 | ielts13_test1_p1 F-05 | It has also been found that visitors enjoy cultural activities most when they are interactive, such as visiting a marae (meeting ground) to learn about traditional Maori life. | 4 | T2:gi_v02_1fb70772e9c0<br>T3:gi_v02_e92ba31d8512<br>T6:gi_v02_f008899ca963<br>T3:gi_v02_fdb24f95191e | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 42 | ielts17_test2_p3 G-03 | The solution to both these problems was the invention of the brilliantly simple yet phenomenally successful Post-It note. | 3 | T5:gi_v02_0c018ebe38e5<br>T1:gi_v02_6f021d66bff3<br>T6:gi_v02_cebf38645c3e | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 43 | ielts4_test1_p1 E-03 | Fewer students responded that rainforests provide plant habitats, and even fewer mentioned the indigenous populations of rainforests. | 3 | T3:gi_v02_138e696e4464<br>T3:gi_v02_ac1a50f4a407<br>T2:gi_v02_c2dee2d22cba | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 44 | 53_83_p2 F-02 | Streetcar's model works very similarly to those of its main rivals, Citycarclub and Whizzgo. | 3 | T6:gi_v02_5b07b95cbaf2<br>T1:gi_v02_62e412446ade<br>T5:gi_v02_79bbdacfdd5b | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 45 | 91_49_p2 B-01 | Historians believe the Maya people of Central America first learned to farm cacao plants around two thousand years ago. | 4 | T2:gi_v02_003303fc6e45<br>T3:gi_v02_13af533b81b5<br>T6:gi_v02_6642c7f98c39<br>T3:gi_v02_de9e96de2308 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 46 | ielts18_test3_p1 B-01 | The problem with replacing concrete is that it is so very good at what it does. | 3 | T3:gi_v02_60fbe2a1e990<br>T3:gi_v02_9d6def203f6f<br>T3:gi_v02_ff10ea6f401b | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 47 | ielts15_test2_p1 D-03 | According to Sennett, this failed because its designers had invested too much faith in computer-aided design to tell them how it would operate. | 4 | T3:gi_v02_65d4fa76407e<br>T3:gi_v02_8da9a62c2cb7<br>T6:gi_v02_c493c5b5694e<br>T6:gi_v02_f527055b067b | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 48 | 91_49_p2 C-03 | In 1519, Cortes arrived in current-day Mexico. | 4 | T5:gi_v02_64e75b6da0a9<br>T3:gi_v02_83d7df94b250<br>T1:gi_v02_85c1123bcbc4<br>T6:gi_v02_df062d30fdef | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 49 | ielts13_test2_p3 D-04 | Like points earned on regular purchases, these green points can be redeemed for cash. | 6 | T3:gi_v02_068ffff10afc<br>T6:gi_v02_6859d14e2984<br>T6:gi_v02_9c9a658ec48d<br>T1:gi_v02_9d4f73dab773<br>T3:gi_v02_add9d188e954<br>T5:gi_v02_ba7c3fc83676 | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |
| 50 | ielts14_test1_p2 D-03 | It worked on a deposit: 'You dropped a coin in the bike and when you returned it, you got your money back.' | 3 | T3:gi_v02_17058ce491d0<br>T6:gi_v02_247c066d3604<br>T2:gi_v02_990805081bef | 各给定局部答案可成立 | 未见指定源句缺陷，可阅读 |

## 实际执行命令和证据

以下变量只为缩短绝对路径；每条命令对应本轮实际执行（脚本内subprocess的完整参数也列出）。生成/graph写入source快照，导入只使用新SQLite URI；没有修改被审工作树文件来运行探针。辅助脚本和日志仅本机AUDIT可见，关键抽查题号、判断、SHA与探针已写进本报告，另一台机器可按相同git版本/种子重新生成。

```sh
R=/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker
A=/Users/zhouxin/.codex/audits/grammar-v02-round8-20261026
G="$R/.venv-grammar-tools/bin/python"
P=/Users/zhouxin/Desktop/studytracker/.venv/bin/python
N=/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
cd "$R"
git status --short --branch
git log -5 --oneline
git fetch origin claude/word-memorization-system-eval-55v2y5
git merge --ff-only 5eb9922607a191b405b9c0139886b3a583ddae53
git rev-parse HEAD
git diff --stat 26fc46d..5eb9922
git diff --name-only 26fc46d..5eb9922
git diff 26fc46d..5eb9922 -- data/idictation_reading_jijing/raw.json static/reading_tests models.py app.py api miniprogram .github/workflows scripts/build_reading_test_practice.py
# source由git archive固定5eb版本解包；不在工作树原位生成
# 以下generate.py在source cwd执行相同命令两次并分别复制四文件到first/second
"$G" "$A/generate.py"
# subprocess实际命令（cwd=$A/source），共两次：
# "$G" scripts/generate_grammar_candidates.py --seed 20261018
"$G" "$A/audit_runtime.py"
"$G" "$A/audit_data.py"
"$G" "$A/details.py"
"$G" "$A/probes.py"
"$G" "$A/t2_analysis.py"
"$G" "$A/final_evidence.py"
"$G" "$A/findings_final.py"
"$N" "$A/visibility-probe.js"
"$G" -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary tests.test_grammar_graph_draft -v
"$G" scripts/validate_reading_study.py
"$G" scripts/reading_jijing_text_fixes.py --check
"$P" -m unittest tests.test_reading_study -v
"$N" tests/test_dictation_spell_queue.js
"$G" -m venv "$A/flask-only"
"$A/flask-only/bin/python" -m pip install --cert /etc/ssl/cert.pem Flask
"$A/flask-only/bin/python" -m pip list
"$A/flask-only/bin/python" -m unittest   tests.test_miniprogram_guest_access tests.test_miniprogram_dictation_grouping   tests.test_inventory_toefl_materials tests.test_organize_toefl_materials   tests.test_extract_toefl_answer_keys tests.test_map_toefl_answers_to_practice_docs   tests.test_import_toefl_official_reading tests.test_reading_vocab_grading   tests.test_stats_utils tests.test_grammar_graph_draft tests.test_grammar_item_candidates   tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary -v
"$P" -m ruff check --config 'extend-exclude=[]'   scripts/generate_grammar_candidates.py scripts/grammar_items/checks.py   scripts/grammar_items/templates.py scripts/reading_jijing_text_fixes.py   tests/test_grammar_item_candidates.py tests/test_reading_jijing_text_fixes.py
"$P" -m ruff format --check --config 'extend-exclude=[]'   scripts/generate_grammar_candidates.py scripts/grammar_items/checks.py   scripts/grammar_items/templates.py scripts/reading_jijing_text_fixes.py   tests/test_grammar_item_candidates.py tests/test_reading_jijing_text_fixes.py
# cwd=$A/source：
# "$G" scripts/render_grammar_graph_review.py
# 然后与$R/docs/GRAMMAR_GRAPH_V0_REVIEW.md按bytes比较
"$P" "$A/import_snapshot.py" "$A/main"
"$P" "$A/import_snapshot.py" "$A/source"
```

Flask-only实际第三方包仅Flask3.1.3及其必需的blinker/click/itsdangerous/Jinja2/MarkupSafe/Werkzeug，无openpyxl，所以XLSX相关轻量用例按设计跳过；G环境的该测试与独立xlsx检查都执行通过。`extend-exclude=[]`避免仓库排除项使Ruff实际没有检查指定文件。

内存重建核心（audit_data.py）：用builder.build_tests(raw,'jijing')；localize_image只按url路径推算本地静态图片名，不下载、不改变文本。对全部171篇逐个比较整个content与groups字典；非只数文件或只比较paragraphs。3篇逐段以单空格拼sentence，20段全等。导入核心：分别把main完整快照和source完整快照放到sys.path；make_app(database_uri='sqlite:///'+AUDIT+'/main-to-current.sqlite')，只创建ReadingPassageAnalysis表，调用run_import各自data及load_source_passages；执行前断言数据库URI指向AUDIT。未访问生产库。

新发现与抽样关键复现代码（在已生成候选的独立快照根运行）：

```python
import json, random
from pathlib import Path
from scripts.grammar_items.templates import TEMPLATES
pool = [json.loads(s) for s in Path('output/grammar_items/candidates_v0_2.jsonl').read_text().splitlines()]
batch = [json.loads(s) for s in Path('data/grammar_items/review_batch_v0_2.jsonl').read_text().splitlines()]
rng = random.Random(20261030)
chosen = [i for t in TEMPLATES for i in rng.sample(sorted(
    (i for i in batch if i['template'] == t and i['pool_status'] == 'auto_pass'),
    key=lambda i: i['item_id']), 5)]
keys = sorted({(i['source']['passage_id'], i['source']['sentence_id'])
               for i in pool if i['status'] == 'auto_pass'})
sentence_keys = random.Random(20261030).sample(keys, 50)
wrong_ids = {'gi_v02_bdee163d3f00', 'gi_v02_bfb7654efc10', 'gi_v02_6e7951e2acc7'}
print([(i['item_id'], i['status'], i['answer']) for i in pool if i['item_id'] in wrong_ids])
# 正文和题目递归匹配pre-modem、Fischer-Price、完整词Witthof；以passage+sentence连接pool。
```

网页显示探针只调用纯渲染函数，无需服务/生产权限：

```javascript
const data = require('./static/reading_jijing/reading_jijing_32_test_20.json');
const renderer = require('./static/js/practice_renderers.js');
const q = data.passages.find(p => p.id === 'reading_jijing_32_test_20_p3').groups[0].questions[0];
const html = renderer.renderReviewCard(q, {status: 'incorrect'}, 'A');
console.log(html.includes(renderer.escapeHtml(q.analysis))); // true
```

## 与提示要求的差异、已披露遗留及交接

没有因工具不可用而跳过必做检查。按只审核约束，用仓库外完整快照生成并做反事实，不覆盖被审四文件；复用已验证本机parse缓存，未另做全量冷启动。两个报告只有预期Python版本行不同，其他文件及两次生成一致。T2约440未用未提供的原脚本复刻，采用公开口径独立复算并人工复核，不冒称精确一致。未读取生产数据来证明任何线上状态；以上“显示”结论来自本地当前代码与真实数据的纯函数调用。

8句/28题的无终止句号引导句/脚注仍可复现，未简单按句末标点新增排除；已披露84_73_p1缺失中心句、约85处含混role、年代/嵌套引语启发式、截短引用大小写、IELTS的控制字符及两个旧结构问题均未修，也未重复记作新增问题。32_20_p3原始摘要/定位段号和解析遗留的可见范围已在V3澄清。关于推送前amend的作者说明，本地git不能独立证明从未有历史远端状态变化，本次只审已获取的固定提交，不把该声明当成已验证的外部事实。

本轮仅新增本审核记录，并更新CODEX_HANDOFF/WORKLOG；辅助快照、SQLite、脚本及原始日志在AUDIT，只在本机共享文件系统可见。桌面另一树 `/Users/zhouxin/Desktop/studytracker` 的main及原有7 modified/22 untracked没有动，不应误认为它已拥有此任务分支。未推main、未开PR、未部署后端/前端、未操作生产服务器/数据库、未上传/提审/发布小程序、未调用大模型API。

下一步：实现方按V1–V3处理并补证据；A8多解及V4/V5按优先级决定。老师盲审必须使用第八轮版本并以题号管理旧结果；本轮不替老师提交判定。

## 提交与GitHub CI

审核正文提交 `5483d2571e4805dbbfee0c9efa33bdffd3986abe` 已push到 `origin/codex/grammar-item-candidates`。该提交的 [GitHub CI 40360754191](https://github.com/KB77GG/studytracker/actions/runs/40360754191) 已完成：

- **test：success**。GitHub日志实际169项运行、168通过、1跳过；Node spelling queue步骤success。
- **lint：failure（存量advisory）**。Ruff check失败，format步骤skipped；与本轮6个改动Python文件单独check/format全通过应分开看。
- workflow整体success是因为lint允许失败，不代表lint通过。

实际取证：`gh run view 40360754191 --json headSha,status,conclusion,url,jobs`，分别读取job `121705201615`（test）和`121705200708`（lint）的`--log`；完整JSON/日志保存于AUDIT的ci-body文件。该CI补记独立commit/push，最终HEAD及其CI在最终用户汇报中提供；补记仍只改三份授权文档，未改被审内容。
