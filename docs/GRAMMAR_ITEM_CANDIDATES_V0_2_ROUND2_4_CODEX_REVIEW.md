# 语法候选题 v0.2 第二、三、四轮 — Codex 独立复审

审核日期：2026-10-20、2026-10-26（Asia/Shanghai）。固定审核范围：`f9aebc7..1f03c846c192d939ade43a5902204cb1bea6f9a5`。本报告替代此前等待 role 例数确认的临时记录。

## 结论：不通过

**本次新记录 0 项阻断、5 项应修、3 项建议；上一轮 1 项阻断仍未关闭。** 逐条修订、运行复现、数据导入大体符合计划，但教学标注和标签仍有明确错误，部分题目数据未同步，报告拆句基数错误，源文问题清单也不完整。不能把测试通过或可重复生成等同于语言质量验收通过。

- 第二轮：拆句及通用排除规则基本合理；新拆句有主语被标进谓语的问题；23 道降级中本次抽到 1 道原答案正确的保守误降。
- 第三轮：乱码、CO2 英文正文和温度修订合理；标签修复限制在原兜底分支，但 4 个 role 的新标签仍错。
- 第四轮及追加：548+2 条修订的局部改法未发现需要撤回的明确错误；正文、标注和题目数据间仍有遗漏和解释错误。
- 上轮阻断 R1：`gi_v02_eb01375e183f`、`gi_v02_20551c6d1cef` 的 T1 越界干扰项仍 auto_pass。第三例因本轮文本变化、重新解析已消失，不据此关闭另外两例。上轮数字单引号问题也仍有尾引号缺失（当前题号 `gi_v02_50076d525594`，括号已补回）。这些是继承问题，不重复计入本次新增数。

第一轮修复 `8f273e9..f9aebc7` 的独立复审已完成，见 [第一轮修复独立复审](GRAMMAR_ITEM_CANDIDATES_V0_2_FIXES_CODEX_REVIEW.md)，未重复开展整轮审核。本人没有修改被审核实现、数据或交付文件，本轮续办未委派子 agent 或调用大模型 API。

## 执行现场、例外与证据保全

- 工作树：`/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker`，分支 `codex/grammar-item-candidates`。原桌面项目 `/Users/zhouxin/Desktop/studytracker` 的 main 和既有 7 modified / 22 untracked 入口均未触碰。
- 已按授权 fetch，合并指定 `1f03c846c192d939ade43a5902204cb1bea6f9a5`。合并提交 `1cdc4e5eeac7eef3c9562282306679abd6510af1`；只在两份交接冲突中保留双方内容，没有 rebase、没有合并 main 或 Claude 后续提交。临时阻塞报告提交 `57bc1c515413d5d937855f3ed54e591d73c5ca93` 已推送，后续本报告接续它。
- 用户已明确确认“**不足2例时审核全部现有例子**”。本次按该确认检查当前 38 个单例 role；已从当前语料消失的 `run_on_passive_clause` 审第三轮的两例，明确区分历史例与当前例。没有伪造第二例。
- 10月20日的 `/tmp/studytracker-grammar-round2-4-audit.H4JlOk` 在10月26日续办时已不存在。此前人工逐条/逐句阅读结论继续核实；运行、生成、抽样、结构和导入证据于26日在持久目录重建，不把已丢失的日志当作现存附件。
- 本轮 `$AUDIT`：`/Users/zhouxin/.codex/audits/grammar-v02-round2-4-20261026`。原样 `git archive` 副本、审计脚本、输出、缓存、日志和 SQLite 留在本机仓库外。使用原样副本生成，以同时满足重生成和不覆盖被审核文件的要求。
- main 模拟基线是审核时 `origin/main` 的完整 **`cc6323e0cfa85342a34711480eac9def9c3fefaf`**，代码/static/data 均取该提交。没有只换 main 的 data，也没有实际生产导入。
- 与提示文字的差异：第2项“IELTS 只改难点”不能字面用于整个三轮（第二轮明确拆 IELTS）；即使只看第四轮，`ielts4_test4_p1 A-04/A-05` 还发生提示第11项已要求检查的合并，sentence/structure/translation/expressions 也变化。IELTS 原始 static 未改；这是清单表述不一致，不认定为擅自修改原文。
- Python 3.10 兼容检查针对本次在线模块 glossary：语法按3.10解析通过，新增逻辑只用3.10已有标准库/API；没有可用的生产3.10解释器实际执行，也没有连接生产。离线生成器按用户指定的3.13独立环境运行。

## 21 项检查结果

| # | 独立结果 | 实际命令/证据 |
|---:|---|---|
| 1 | 通过。197 files、12,420 insertions / 4,729 deletions，均在列出的路径范围。构建脚本只移动 groups 构建并传入修订函数；CI 只加一行测试。 | `git diff --stat f9aebc7..1f03c84；git diff --name-only f9aebc7..1f03c84`，逐 Python/CI diff。 |
| 2 | 保护路径差异为空；api 仅 glossary。IELTS 字段例外见上文，不能报告成全部只改难点。 | protected diff、`audit_static.py` 三阶段字段对比。 |
| 3 | 60条已逐条看上下文，局部改法通过。段首点、同位语/书名/状语后的错句点、引号位置、美元/CO2/温度/logging 均合理。 | 修订表第34–93条及三阶段 static/句子对照；附录修订表。 |
| 4 | 548+2条全部核对；没有发现应撤回的明确替换，但同名同词遗漏见 N1/N2，重写标注问题见 N3。 | 表内查找窗口与完整段落、原标注/新标注；附录逐条结果。 |
| 5 | 全库关键词独立检索，清单外207条命中，人工区分108条源文异常记录与99条词汇/正常形式等信息性命中。不能把207当207个错句；附录全部列出。难点中六类过时保留说法为0，expressions仍有一处过时说明。 | `audit_static.py`、`prepare_verdicts.py`、N1/N3。 |
| 6 | 通过：0 fix(es) not yet applied；643条不变量均成立，10条at_end均以find开头且不带questions。 | `python scripts/reading_jijing_text_fixes.py --check`；全表断言。 |
| 7 | 当前实际修订幂等、逐步回放吻合，所有真实questions命中均在词边界；合成子串反例会误改，见 A2。找不到段落/替换及非法at_end组合会报错；同时带正文的questions修订并不要求题目字段必须命中。 | `audit_static.py` 顺序回放及重复应用；合成探针。 |
| 8 | 1,065+11个字符串改动复现；50处独立抽查替换本身均合理。332种的去重口径未给出：完整字符串对是510种（追加4种），字符编辑对145种，不能确认332。发现未带questions的13处残留，连同其他残留见 N2。 | `groups-fourth.json`、`groups-additional.json`、50行表、N2/N5。 |
| 9 | 171篇paragraphs和groups与raw重建完全一致；机经static控制字符0。英文正文/题目中的裸CO为0；但29_63_p1中文summary仍有CO一处，见A3。 | `audit_static.py` 内存build_tests，禁用图片网络下载、仅计算同样的本地图片路径；不下载图片。 |
| 10 | 12688→12726→12726→12745；第四轮新增24、删5。未改对象除index外原始JSON字节一致；indent=2保持，新增ID/index检查通过；validator0错误。 | `audit_static.py` JSONDecoder提取原始对象字节；validator。 |
| 11 | 已读第二轮97、第三轮17、第四轮630个最终变化对象的四类内容，覆盖拆出/合并结果和119句说明等。11处明确教学内容问题见N3；其余覆盖ID表列明。未发现新增插入字符被边界平移吃掉；6处词内子串定位是旧问题。 | 三阶段句子diff、原/新structure及DP/EX；附录逐句覆盖。 |
| 12 | 51单元34拆/9修文/7误报/1保留分类合理；119句20/12/70/17分类大体可接受，但保留原文不代表改写讲解都正确。第六节18条不凭猜测改原文合理；另有清单遗漏。 | ROUND2、SOURCE_ERRORS一至七节全读；N1/N3、A3。 |
| 13 | resolver变化仅原兜底分支；当前71role/403处，历史72/407。全72逐例审核，4role仍错；38单例按用户确认全审。unknown无新增。3.10语法/API检查通过。 | `audit_static.py` old resolver对同一语料；附录72行与实例。 |
| 14 | 标签在normalize_payload时写入payload_json；只部署新resolver不会改既有数据库内容，需重新导入。 | `scripts/import_reading_study.py:69`、`:108`；import分区133/94/90。 |
| 15 | leading/control规则正确且无ID黑名单；已构造缩写在真句末被误跳过等反例。全库28处被例外抑制的匹配逐条看，无新增真实句界误吞。不能据此推断所有未匹配文本都完整。 | `checks.py:14–30,114–125`；suppressed-boundaries和synthetic-parses。 |
| 16 | 155→2、122自动题补括号、23/167/10降级均复现；补回未越调用者允许的边界（T5使用已有的subject起点至predicate起点区间，并非单个subject原标注）。抽样9/10第二轮降级成立、1误降；第四轮20并列谓语+20并列分句+10for均符合人工判断。47个so that目标判型不变；两新测试在旧type_matches上均失败。 | `counterfactual.py`、`audit_runtime.py`、附录60行。 |
| 17 | 实测tagged32、split0、multi1、leading0、control0，均等于预期；不是仅读expected字段。4个fragment随合并消失（包括ielts4_test4_p1 A-04和A-05两个旧fragment）。报告resplit总数却错，见N5。 | 独立生成报告actual与原始标签计数。 |
| 18 | 两次四文件彼此字节一致；JSONL/XLSX与提交版一致，报告仅Python版本行不同。50188候选、六auto数一致。78回归状态/原因一致。85专项测试、Flask-only153运行/1跳过、reading22、Node通过；图谱生成一致；Ruff仅构建脚本存量UP017/format不通过。 | 下节精确命令、SHA表、日志。 |
| 19 | 完整main先created317，再当前updated227/skipped90/failed0；独立分区133数据文件不同+94纯标签+90无变化。 | `import_snapshot.py` 两次全快照临时SQLite；`import-partition.json`。 |
| 20 | seed20261027，30表内+60改动句+第16项60，共150题；逐题表附后。分类/答案均核查，特别区分原句质量和标点显示问题；未把样本全外推到池。 | 按item_id排序后random.Random.sample（groups50按有序路径池抽取）；方法及明细见附录。 |
| 21 | 通过：7表，六题型各60数据行，360行逐格与teacher_row吻合；无auto_pass/needs_review，判定列H2:H61四项下拉。 | openpyxl只读解析；没有回写Excel、没有改变其SHA。 |

## 问题清单

### B1 — 继承阻断：T1干扰项越界仍未降级（不计新增）

位置 `scripts/grammar_items/templates.py:317`、`:335`。按来源核查全部候选，上轮两道 `gi_v02_eb01375e183f`（ielts9_test3_p2 A-03）、`gi_v02_20551c6d1cef`（24_56_p3 B-03）仍为auto_pass且reasons为空。前者原span从close开始，干扰项把外部to加回来；后者把名词对比的not错误并入would be identified。复现：取完整候选对应item，按中心动词直接aux/auxpass/neg/prt子节点对照raw span。建议将干扰项来源越界原因合并进题目reasons，保留T1正确答案范围不变的约束。上轮完整证据仍有效，本轮只确认现状。

### N1 — 应修：源文问题清单未覆盖全库，同篇专名仍不一致

位置 `docs/READING_STUDY_SOURCE_ERRORS_2026-10.md`“怎么找出来的”及清单一至七；`reading_jijing_9_test_81_p2 B-01/I-05`。

- B-09改Couran之后，B-01仍写Conran Cove（包括翻译括注）；I-06改Prideaux之后，I-05仍写Pridcaux，包括structure及译文。不是不能确定的人名，分别可由[度假村官网](https://www.courancove.com.au/)与[作者上传的原论文](https://www.researchgate.net/publication/222853040_The_Resort_Development_Spectrum_a_New_Approach_to_Modelling_Resort_Development)核实。应同步同篇同一实体的全部出现，不按句ID黑名单屏蔽。
- 用更宽关键词重新检索，清单外仍有108条源文异常记录待分类，如10_78_p2 E-35b的his/her、62_44_p2 B-05的从句被句号截断、76_43_p3 D-07的句法残缺。部分应保留作者表达，部分应修说明或文本，不能把它们一律自动纠错；但“把这些记录全部列出分类”尚未做到。附录给出207条全部检索命中与分类，便于排除误命中。

复现：扫描全317文件的difficult_points，关键词正则及对清单句ID的集合差见命令/方法；再读列出的句子全文。建议补全清单后分别按可确定排印错误、作者表达、无法恢复等处理，并核对同实体和同词的其他出现。

### N2 — 应修：题目字段与修复后的正文仍不一致，超过已披露的同义词遗留

位置 `data/reading_jijing_text_fixes.json` 第138/229/237/241/249/263/298/427/463/510/518等条对应的 `static/reading_jijing/* groups`。附录列确切JSON路径（0基数组下标）。

- 未带questions的266条中，确认6条修订对应13个仍错误的题目字符串：40_75_p3 `stressed end`（1），46_84_p1 `(China’s rise`（3），48_21_p3 `6oC`（2），84_73_p2 `nearbyfriends`（5），18_53_p2 `was,’less`（1），22_90_p3 `potential, Once`（1）。曲直引号、截短引用和替换窗口差异使简单子串漏过。
- 另有已带questions的窗口没覆盖另一上下文：18_53_p1题干/定位词的modem version，40_75_p3答案依据的self-certificaion及两处analysis的hypothrsie，5_59_p1的analysis中unsuccessfull，92_58_p1的dierent senses等。
- 已披露“10处同义词”实际上是10种写法、12个字段；加漏掉的nearbyfriends共11种、13个synonym字段。上述具体范围共至少34个错误/旧格式字段（13 synonym、21其他字段），不把普通词of/in/the等合法出现或合理截短句末标点当错误。
- 代码全局检索未发现在线后端/小程序对locating_words.synonym的读取；但`static/js/practice_renderers.js:675–699`会显示analysis、central_sentences，本次残留并非都不可见。

复现：以d548a54→2051ff0→1f03c84逐路径比较groups字符串；逐修订提取被改词/标点窗口，再在同篇最终groups检索并人工排除正常上下文。建议按明确字段和上下文同步错词，支持曲直引号差异；同步题干/答案依据后重新核对判分答案，不能全库无边界替换。

### N3 — 应修：重写后的教学标注、解释或译文仍有明确错误

以下11处逐项为N3的子例，不将11处夸大成11个独立工程问题。位置与建议见下表；读取对应JSON中的sentence/translation/structure/difficult_points/expressions即可复现。

| 来源（完整passage_id）/句ID | 问题 | 建议 |
|---|---|---|
| ielts8_test3_p3 A-03b | 新拆句把 we think of 全标为 verb_phrase，主语 we 被吞入谓语。 | 分出 we 主语，think of 谓语。 |
| reading_jijing_24_test_56_p2 G-03 | 新难点称 searching 与 inspection 都是动名词；inspection 是普通派生名词。 | 改为并列名词性成分；分别说明动名词 searching 和名词 inspection。 |
| reading_jijing_46_test_84_p1 D-06 | 新难点称 fell 是单数形式；一般过去时 fell 没有单复数区别。 | 说明主语中心为 number；fell 是 fall 的过去式，不作为单数例证。 |
| reading_jijing_81_test_93_p2 F-01 | What, if anything, can be done? 的 What 标为宾语，新难点也说被动时仍为宾语。 | What 是本被动问句的主语；改 role 和说明。 |
| reading_jijing_69_test_40_p2 F-01 | has helped promote 中没有宾语，新说明却把 promote 称作宾语补足语。 | 说明 help 后接不带 to 的不定式补语；不要虚构宾语。 |
| reading_jijing_83_test_95_p2 D-01 | rich in wildlife 仍被标/解释为分词短语，中心 rich 是形容词。 | 改为形容词短语；原句其他语病按已披露保留策略处理。 |
| reading_jijing_5_test_59_p1 I-01 | signs that more companies... 是说明迹象内容的名词性从句，仍标 relative_clause，新难点沿用修饰关系说法。 | 改为内容/同位语从句并说明 that 在从句内不充当成分；原始边界约定另审。 |
| reading_jijing_27_test_33_p1 D-01b | 新拆句 photos 译成一张照片，擅自变成单数。 | 改为照片或多张照片。 |
| reading_jijing_92_test_58_p2 H-03 | the rest 被解释成可收集部分之外的剩余水量，与前文 much cannot be captured 相反。 | 应指无法收集部分之外的其余水量。 |
| reading_jijing_85_test_12_p2 C-10 | 正文已改 In order to，expressions 仍说原文误写为 in older to。 | 删除过时括注，保留面向学生的表达解释。 |
| reading_jijing_32_test_20_p1 B-03 | 本轮重新标注仍把 for they shared... 标成 cause_clause，与第四轮明确采用的并列连词教学口径冲突。 | 按本项目口径改为并列分句；出题器降级不能替代阅读页标注修正。 |


建议修复这11处之后增加针对教学语义的人工复核；JSON校验与spaCy一致性不足以验证中文解释。另有“Perhaps是否纳入名词短语”等可分析分歧没有计作明确错误。

### N4 — 应修：4个role的新展示标签仍与真实成分不符

位置 `api/reading_study_glossary.py:436–447`。关系词片段先于省略结构规则被处理，且角色名中出现reason/result不代表整个范围都是状语从句。

| role / 来源 | 当前标签的问题 | 建议 |
|---|---|---|
| first_result_clause / 48_21_p1 E-05 | the pearl may be deformed是主句，却显示结果状语从句。 | 根据成分本身映射主句，不能只看result。 |
| alternative_result_clause / 同句 | or the oyster may die是并列分句，却显示结果状语从句。 | 显示并列分句或修正原role。 |
| elliptical_contrast_clause / 32_20_p3 C-03、78_102_p2 A-02 | less so for the gut、deadly ones, bitter是省略的对比分句，显示对比状语从句。 | 先识别省略结构，再说明对比关系。 |
| predicate_with_reason_clause / 23_46_p1 E-05 | reduces carbon emissions because...包含主句谓语及其原因从句，整个范围被显示成原因状语从句。 | 显示谓语并拆出because子层，或以更准确的原role表达。 |

复现：对上述role调用resolve_role并对照附录中的真实span。它们原先泛化为状语从句也不正确；本轮新增精确标签未解决语义问题，不声称“原来正确、这次才错”。建议显式处理复合/省略结构，补真实语料测试，不按句ID特判。约85处已披露含混role仍需另行逐条整治，不能用这次映射覆盖全部。

### N5 — 应修：报告拆句基数不正确，部分自查数字缺可复现口径

位置 `scripts/grammar_items/reporting.py:167–180` 和提交版 `generation_report_v0_2.json.resplit`。

- 当前报告before=12,652、after=12,745、added=93。实际最初12,657，第一轮+31、第二轮+38、第四轮+24−5，净增88；第三轮未增句。93只是仍在库内的后缀ID数，不是净增句数。注释“splitting only adds”在合并后失效。
- counting_notes仍写suspected_split_word只报告不设expected，而当前expected已经为0。应同步说明。
- 1,065个题目字符串变化可复现，但“332种不同改动”没有定义去重单位。完整before/after字符串对510种、SequenceMatcher非equal片段对145种；不拿任何一个不同口径证明332必错，但当前材料不足以复核该数字，应给算法/基线或改为明确定义的计数。

复现：三阶段句子ID集合增删，与报告resplit字段对比；groups按JSON路径比较，使用相同基线独立去重。建议显式记录基线句数、新增和删除，不用ID后缀推断before；补含合并的回归测试。

### A1 — 建议：把保守降级与确认答案错误区分开

位置 `templates.py:362–374`；第二轮样本 `gi_v02_d73a253b0286`，ielts5_test2_p2 D-16。`that sudden mental 'Aha!' is the buzz that makes us laugh`的that是指示限定词，sudden mental Aha是主语，原“并列分句”答案合理；spaCy却将that解析为mark，使其降级。

复现：同句的原始parse tokens可见that/mark；在23个降级池按种子抽10，本例是1个误降，其余9个是并列的从属从句。建议保留needs_review这一保守结果，但修正文档中“均确认不是并列分句”的全称说法；需要提高自动率时再识别det/mark混淆，不为了此例放松所有that。

祈使句省略主语本来可以形成并列分句；当前主语要求会保守降级。倒装、there be只要依存关系正确，nsubj/expl仍能通过；解析把主语误标dep时会降级。这是规则边界，不是证明每个降级都错题。

### A2 — 建议：通用启发式有可复现边界，当前真实命中安全不等于普适

- `scripts/reading_jijing_text_fixes.py:69–83`：`replace_in_place({'title':'out sidecar'}, 'out side', 'outside')`得到outsidecar，会改词内部。当前所有实际questions替换逐位置扫描均无此越界；建议校验替换边界及字段用途，不把合成风险说成已造成真实误改。
- `checks.py:24–30,114–125`：`We hired Acme Inc. They arrived early.`的Inc.兼任真句末，但缩写例外吞掉边界。`She left at 5 p.m. "We stayed."`也说明缩写后开引号不能一律排除句界。全库28处被抑制的匹配已看，没有发现这种实际误吞；已有跨段截断和不符合正则形状的坏句另列，不宣称正则识别了所有残句。
- 30题样本的ielts8_test2_p1 F-02（`gi_v02_46a92ce02130`）与60题样本40_75_p2 C-05（`gi_v02_fa439f1d87c3`）的主语内部闭破折号落在高亮外。核心答案成分完整，不计答案错；建议将内部成对标点的显示策略扩展到破折号，同时保持各模板允许的范围。

### A3 — 建议：已知源文残缺与交付适用性、summary遗漏应明确

保留无法确定的原文合理，但不等于适合自动出题。60题改动句样本中的9/11/19/56/57虽可判局部答案，整句分别存在缺插入标点、vibration fell、welcomed to as、末尾and截断、vein/spine语义错乱，不能按“局部答案正确”算成整句可直接交学生。这些大多已在保留原文类别披露，本次不重复当新增源文修复要求。建议将这类不适合出题的状态用可解释的通用质量规则或审核状态表达，不写ID黑名单。

`reading_jijing_29_test_63_p1 content.summary`仍有“大气中的CO浓度”，英文段落和groups均已CO2。提示“不再有CO”若覆盖整个JSON，这一处不满足；summary应同步为CO2或二氧化碳，不能把英文正文扫描结果扩成整文件无遗漏。IELTS18_test3的\x02、两处存量层级/顺序和heading单元本轮只核实，不擅自修复。

## 主要运行命令及方法

以下命令于本机实际运行；`ROOT`/`AUDIT`为任务专用变量。审计辅助脚本留在AUDIT，不在被审核仓库里。用户只授权三份文档，因此未把辅助脚本、候选池、模型缓存或数据库混入提交。

```sh
ROOT=/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker
AUDIT=/Users/zhouxin/.codex/audits/grammar-v02-round2-4-20261026
cd "$ROOT"
git status --short --branch
git log -5 --oneline
git diff --stat f9aebc7..1f03c84
git diff --name-only f9aebc7..1f03c84
git diff f9aebc7..1f03c84 -- data/idictation_reading_jijing/raw.json static/reading_tests/ models.py app.py miniprogram/ .github/workflows/deploy.yml
git diff f9aebc7..1f03c84 -- scripts/build_reading_test_practice.py .github/workflows/ci.yml
# 原样归档：source=1f03c84，baseline=f9aebc7，r2=d83858b，r3=d548a54，main=cc6323e
# 每个目标目录预先mkdir，git archive <ref> [paths] | tar -x -C <target>
.venv-grammar-tools/bin/python "$AUDIT/audit_static.py"
.venv-grammar-tools/bin/python "$AUDIT/prepare_verdicts.py"
.venv-grammar-tools/bin/python -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary tests.test_grammar_graph_draft -v
.venv-grammar-tools/bin/python scripts/validate_reading_study.py
.venv-grammar-tools/bin/python scripts/reading_jijing_text_fixes.py --check
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_reading_study -v
.venv-grammar-tools/bin/python -m venv "$AUDIT/flask-only"
# 默认pip首次因本机CA失败；改用系统证书重试成功，未关闭TLS验证。
"$AUDIT/flask-only/bin/python" -m pip install --cert /etc/ssl/cert.pem Flask
"$AUDIT/flask-only/bin/python" -m unittest tests.test_miniprogram_guest_access tests.test_miniprogram_dictation_grouping tests.test_inventory_toefl_materials tests.test_organize_toefl_materials tests.test_extract_toefl_answer_keys tests.test_map_toefl_answers_to_practice_docs tests.test_import_toefl_official_reading tests.test_reading_vocab_grading tests.test_stats_utils tests.test_grammar_graph_draft tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary -v
/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tests/test_dictation_spell_queue.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check scripts/build_reading_test_practice.py scripts/reading_jijing_text_fixes.py scripts/grammar_items/checks.py scripts/grammar_items/templates.py scripts/grammar_items/reporting.py api/reading_study_glossary.py tests/test_grammar_item_candidates.py tests/test_reading_jijing_text_fixes.py tests/test_reading_study_glossary.py
# 同一9文件列表运行 ruff format --check；f9aebc7构建脚本用相同pyproject.toml检查，确认两UP017原已存在。
/Users/zhouxin/Desktop/studytracker/.venv/bin/python "$AUDIT/import_snapshot.py" "$AUDIT/main"
/Users/zhouxin/Desktop/studytracker/.venv/bin/python "$AUDIT/import_snapshot.py" "$AUDIT/source"
cd "$AUDIT/source"
PYTHONDONTWRITEBYTECODE=1 "$ROOT/.venv-grammar-tools/bin/python" scripts/generate_grammar_candidates.py --seed 20261018
# 保存四份首次输出到AUDIT/run1，再执行同一命令第二次（暖缓存）。
"$ROOT/.venv-grammar-tools/bin/python" "$AUDIT/audit_runtime.py"
"$ROOT/.venv-grammar-tools/bin/python" "$AUDIT/counterfactual.py"
"$ROOT/.venv-grammar-tools/bin/python" scripts/render_grammar_graph_review.py
cmp docs/GRAMMAR_GRAPH_V0_REVIEW.md "$ROOT/docs/GRAMMAR_GRAPH_V0_REVIEW.md"
```

Flask-only环境的唯一直接安装项为Flask及其传递依赖，没有spaCy/openpyxl；153项中跳过1项依赖openpyxl的写表测试。85项专项在完整工具环境执行，不跳过该测试。Ruff只有builder原有的279/336行UP017与格式问题；原基线对应279/335行同样报错，其他8文件通过。生产3.10兼容是保留timezone.utc的合理理由，格式问题本身仍是存量。

审计脚本自身两次开发时的小错误（把openpyxl values属性当函数、旧探针过度比较偏移字段）已修正后重跑；不是产品测试失败，不以它们改变被审结果。

## 环境、双次生成和回归

10月26日第一次在空`parse_cache_v0_2.jsonl`目录完整解析，第二次复用首次缓存。不是依赖10月20日已丢失缓存。Python3.13.3，spaCy3.8.16，en_core_web_trf3.8.0，torch2.14.1，openpyxl3.1.5，CPU，seed20261018。reading_study指纹`d9480bf485c7bf5f416212b3bea38581af0051fb9bec0c6a6895b5fe1715212c`；grammar_graph指纹`c7b35ddb68db7601ccd01e38a210ad3dd772ff507302190f68a351e408b85a29`。

| 文件 | 第1次 SHA-256 | 第2次 SHA-256 | 提交版对比 |
|---|---|---|---|
| generation_report_v0_2.md | 4f8f6de5fc78bf9521511c1c56f1de7c03325dbdf79a25ac3b6cde67483e9d68 | 4f8f6de5fc78bf9521511c1c56f1de7c03325dbdf79a25ac3b6cde67483e9d68 | 仅Python版本行不同；提交SHA ddeae95c685000616bc265baff4b04577c69db4edcec2bafb106165db9432f39 |
| generation_report_v0_2.json | a9c3e575eae02a002bc6944ebbad73253dafa43cca67e6e21dbdccce6764a181 | a9c3e575eae02a002bc6944ebbad73253dafa43cca67e6e21dbdccce6764a181 | 仅Python版本行不同；提交SHA ad5178ea7a54ff74867c22a458156698f91f475314a3db2d5ee82854d316a2dc |
| review_batch_v0_2.xlsx | 3fa09b550cfc21ce738d72b4f7cd6631b8b410ee22f3931ef5fa9170e9cf8d3e | 3fa09b550cfc21ce738d72b4f7cd6631b8b410ee22f3931ef5fa9170e9cf8d3e | 完全一致 |
| review_batch_v0_2.jsonl | 0c727e740e89f03c4acaf5cd2f5acbfc5b7599c082caeeade3990a6e61795db8 | 0c727e740e89f03c4acaf5cd2f5acbfc5b7599c082caeeade3990a6e61795db8 | 完全一致 |


六模板auto_pass依次为5987、4755、11582、411、5428、12886，总候选50188。回归以来源+模板匹配，逐个比较候选status/reasons、rejections和not_applicable，13句×6模板=78项与f9aebc7一致。H-02的high- rise→high-rise同时导致文本、偏移、题号和解析token索引变化；这些不是状态/原因回归，不能只比较共同题号而漏掉它。

| 来源 | 六模板现状（与f9状态/原因一致） |
|---|---|
| ielts7_test3_p1 K-03 | 主句谓语: rejected(too_short,unbalanced_quotes_or_brackets)<br>从句边界: rejected(too_short,unbalanced_quotes_or_brackets)<br>从句类型: rejected(too_short,unbalanced_quotes_or_brackets)<br>状语关系: rejected(too_short,unbalanced_quotes_or_brackets)<br>完整主语: rejected(too_short,unbalanced_quotes_or_brackets)<br>动词身份: rejected(too_short,unbalanced_quotes_or_brackets) |
| ielts8_test4_p1 C-04 | 主句谓语: rejected(no_main_verb_tag)<br>从句边界: not_applicable<br>从句类型: auto_pass<br>状语关系: not_applicable<br>完整主语: rejected(no_main_verb_tag)<br>动词身份: auto_pass; rejected(no_main_verb_tag) |
| reading_jijing_76_test_43_p2 H-02 | 主句谓语: auto_pass<br>从句边界: not_applicable<br>从句类型: not_applicable<br>状语关系: not_applicable<br>完整主语: needs_review(subject_mismatch)<br>动词身份: auto_pass |
| reading_jijing_73_test_5_p2 F-05 | 主句谓语: rejected(tagged_fragment,unknown_span)<br>从句边界: rejected(tagged_fragment,unknown_span)<br>从句类型: rejected(tagged_fragment,unknown_span)<br>状语关系: rejected(tagged_fragment,unknown_span)<br>完整主语: rejected(tagged_fragment,unknown_span)<br>动词身份: rejected(tagged_fragment,unknown_span) |
| reading_jijing_56_test_64_p2 C-01 | 主句谓语: rejected(clause_attached_to_conjunction)<br>从句边界: rejected(clause_attached_to_conjunction)<br>从句类型: rejected(clause_attached_to_conjunction)<br>状语关系: rejected(clause_attached_to_conjunction)<br>完整主语: rejected(clause_attached_to_conjunction)<br>动词身份: rejected(clause_attached_to_conjunction) |
| ielts13_test2_p2 C-04 | 主句谓语: rejected(clause_attached_to_conjunction)<br>从句边界: rejected(clause_attached_to_conjunction)<br>从句类型: rejected(clause_attached_to_conjunction)<br>状语关系: rejected(clause_attached_to_conjunction)<br>完整主语: rejected(clause_attached_to_conjunction)<br>动词身份: rejected(clause_attached_to_conjunction) |
| reading_jijing_91_test_49_p3 D-02 | 主句谓语: auto_pass<br>从句边界: not_applicable<br>从句类型: auto_pass; auto_pass; needs_review(span_not_constituent)<br>状语关系: not_applicable<br>完整主语: auto_pass<br>动词身份: auto_pass; auto_pass; auto_pass |
| ielts11_test3_p2 A-04 | 主句谓语: auto_pass<br>从句边界: auto_pass<br>从句类型: auto_pass<br>状语关系: not_applicable<br>完整主语: auto_pass<br>动词身份: auto_pass; auto_pass |
| ielts15_test2_p3 D-05 | 主句谓语: auto_pass<br>从句边界: auto_pass<br>从句类型: auto_pass; auto_pass<br>状语关系: not_applicable<br>完整主语: auto_pass<br>动词身份: auto_pass |
| ielts4_test2_p2 G-31 | 主句谓语: rejected(no_main_verb_tag)<br>从句边界: needs_review(possible_relative_adverb)<br>从句类型: needs_review(possible_relative_adverb)<br>状语关系: needs_review(possible_relative_adverb)<br>完整主语: rejected(no_main_verb_tag,split_subject)<br>动词身份: auto_pass; rejected(no_main_verb_tag) |
| ielts6_test3_p1 C-06 | 主句谓语: needs_review(ambiguous_span_location)<br>从句边界: auto_pass<br>从句类型: auto_pass<br>状语关系: not_applicable<br>完整主语: needs_review(ambiguous_span_location)<br>动词身份: needs_review(ambiguous_span_location); auto_pass |
| reading_jijing_88_test_98_p2 G-04 | 主句谓语: auto_pass<br>从句边界: auto_pass<br>从句类型: auto_pass<br>状语关系: not_applicable<br>完整主语: auto_pass<br>动词身份: auto_pass; auto_pass |
| reading_jijing_88_test_98_p2 G-04b | 主句谓语: auto_pass<br>从句边界: auto_pass; auto_pass<br>从句类型: auto_pass; auto_pass<br>状语关系: not_applicable<br>完整主语: auto_pass<br>动词身份: auto_pass; auto_pass |


## 原文与拆句的人工判断

60条第二/三轮修订：14处段首点均是孤立多余标点，`. the prerequisites`修为The合理；Will同位语、Free Flight书名后的逗号、saving分词、saying后直引、并列who及地名层级均不应硬拆成独立句。73_5_p1的he says留在所属引语句，下一段引语另成句并补闭引号合理。

五个NUL金额按同篇美元计价及16 trillion yuan ($1.9 trillion)转换语境补$合理；其他NUL按语境补逗号/空格/撇号合理。9个CO下标与9个游离2逐项对应；2°C to 5°C是温升区间。fagging→logging位于83_95_p2 D-04（不要误记为29_63_p1）。三处“美元”翻译已同步。

第四轮553处与548条修订不是同一计量：句表按改动处、修订表按可执行窗口。错字/漏字220、标点162、空格138、大小写22、补句末标点11均逐上下文核查；多改动可共用窗口。10个at_end和另外1处普通替换补句号均落在内容完整的段末。没有发现补句号掩盖被截断段落的实例。少数maxi-misers→maximizers兼作拼写统一，但同篇已有maximizer，不要求撤回。

专名/年份验证还参照[NASA的Hansen 1988记录](https://www.giss.nasa.gov/research/news/20130402/)、[Stanford的Pfeffer资料](https://www.gsb.stanford.edu/faculty-research/faculty/jeffrey-pfeffer)、[Michigan的David Meyer资料](https://lsa.umich.edu/psych/people/emeriti-faculty/demeyer.html)。这些只佐证相应专名/年份，不充当全文来源验证。DINA→DNA按上下文明确；catching→caching由cache food/cacher/caches同篇语义直接支持，题目另外11字符串已同步。

拆句重点：ielts4_test2_p3 C-19/C-20、G-37和83_95_p1 H-05跨句引语不应给每句机械补一对引号；说话人归属保留。ielts4_test4_p1 C-14末尾残片并入下一句、ielts4_test1_p3 I-31拆三问句、ielts5_test2_p2两组笑话问答分别成句均合理。第四轮5处合并为ielts4_test4_p1 A-04+A-05、22_90_p2 G-20+G-21、65_69_p3 E-01+E-02、73_5_p1 I-02+I-03、82_4_p3 H-03+H-04；删除ID均有对应保留句，不复用消失ID冒充新增。

85_12_p1 E-02在错字消除后改main_clause合理。对所有变化成分核对新句内位置，没有发现因新增字母使相邻成分边界错位的新例；6个词内匹配（如is在issues/this/autism中、I在In中）在原标注/定位逻辑中已存在，属于另行治理的问题。

保留原文的119句及第六节18句均已阅读；一般不凭不唯一的恢复猜测改作者文字。不过“规范写法”必须自身正确，N3的宾补/动名词/被动主语等解释不能用保留原文来辩护。

## 抽样方法与结果读法

全部抽题种子为**20261027**。batch30：固定T1到T6顺序，每表从pool_status=auto_pass按item_id排序，用同一个Random对象顺次sample5。changed60：取三阶段变化对象来源键的并集（包括拆出/合并保留句），最终全候选auto_pass池1856题，按item_id排序，重新初始化同种子sample60。第16项四组分别重置同种子，在同语料/同解析上只替换被比较版本模板函数，取得23/167/1052/10各池，再排序抽10/20/20/全10。

表内30题：30个核心答案正确，1题内部闭破折号显示在高亮外（A2）。改动句60题：核心答案均可按本项目口径判断正确；1题有同样标点显示问题，5句原句不适合直接出题（A3），两者不混算成“全部交付合格”。第二轮降级10题9合理/1保守误降；并列谓语20、仍自动并列分句20、for10均与人工判断一致。教师判定表本身仍留空，没有将本次审核答案写入被审核xlsx。

下表行号如有，为Excel实际行号（数据序号+1）；题号和来源为复核的主要标识。来源简写a_b_pN对应reading_jijing_a_test_b_pN，IELTS ID不缩写。


## 附录A：盲审表自动池30题

| # | 题目编号 | 工作表/模板 | Excel行 | 来源 | 机器答案 | 独立判定 |
|---|---|---|---|---|---|---|
| 1 | gi_v02_41c8a0d21b85 | 主句谓语 | 61 | 22_90_p3 B-01 | Louise Edwards of HR Success 【says】 that one of the barriers she comes across time and time again is that corporate heads often seem to understand that 'team building' is important but are not quite sure what it is or how to achieve it. | 正确；高亮完整 |
| 2 | gi_v02_0762e0f0a758 | 主句谓语 | 16 | ielts18_test4_p1 D-05 | The term 'natural capital' 【has been developed】 to explain the economic value of nature; for example, measuring the money saved by installing natural solutions to protect against flood damage, adapt to climate change or help people lead healthier and happier lives. | 正确；高亮完整 |
| 3 | gi_v02_40aac4b9445b | 主句谓语 | 49 | ielts20_test3_p1 J-06 | Within a year, Swanson 【had sold】 13 million TV dinners. | 正确；高亮完整 |
| 4 | gi_v02_4ea83e1daee1 | 主句谓语 | 56 | ielts19_test1_p2 B-08 | Before the invention of ocean-going caravels* in the 15th century, ships 【could not】 easily 【cross】 long distances over open water. | 正确；高亮完整 |
| 5 | gi_v02_c14afddc421b | 主句谓语 | 52 | ielts6_test3_p1 F-04 | We 【shall be known】 better than any preceding generations. | 正确；高亮完整 |
| 6 | gi_v02_4122ce7b213b | 从句边界 | 56 | ielts5_test3_p1 E-08 | The one factor 【that was found to affect the child's development】 was family stress leading to a poor quality of parent-child interaction. | 正确；高亮完整 |
| 7 | gi_v02_719f1ba55a0c | 从句边界 | 27 | 29_63_p2 E-07 | "We think that anything 【that can take freight off the roads】 needs to be fully explored," says Tony Bosworth, transport campaigner for Friends of the Earth. | 正确；高亮完整 |
| 8 | gi_v02_20776042c9aa | 从句边界 | 20 | 44_29_p3 E-03 | This is probably because the very poor live in less safe neighbourhoods, and have fewer friends or family 【who can step in, in case of emergency】. | 正确；高亮完整 |
| 9 | gi_v02_438696a50cbf | 从句边界 | 10 | ielts17_test2_p1 D-03 | Along with biblical texts, the scrolls include documents about sectarian regulations and religious writings 【that do not appear in the Old Testament】. | 正确；高亮完整 |
| 10 | gi_v02_028a89c46692 | 从句边界 | 28 | 53_83_p1 D-08 | Mr. Joseph said 【the only danger is sending cash to the wrong mobile number and the recipient redeeming it straight away】. | 正确；高亮完整 |
| 11 | gi_v02_126c1ee49ae6 | 从句类型 | 15 | ielts14_test4_p2 B-04 | 不是从句（短语或非谓语） | 正确；高亮完整 |
| 12 | gi_v02_9516e834ecd4 | 从句类型 | 13 | 24_56_p3 F-01 | 并列分句 | 正确；高亮完整 |
| 13 | gi_v02_852ed94eab15 | 从句类型 | 4 | ielts5_test4_p1 B-15 | 状语从句 | 正确；高亮完整 |
| 14 | gi_v02_ad43310ec26c | 从句类型 | 34 | ielts8_test4_p3 E-04 | 不是从句（短语或非谓语） | 正确；高亮完整 |
| 15 | gi_v02_159bab5bfd7d | 从句类型 | 33 | ielts4_test4_p3 D-13 | 名词性从句 | 正确；高亮完整 |
| 16 | gi_v02_315ddcb542db | 状语关系 | 52 | ielts5_test2_p1 G-30 | 让步 | 正确；高亮完整 |
| 17 | gi_v02_e9143bf426fa | 状语关系 | 16 | ielts6_test2_p2 F-19 | 让步 | 正确；高亮完整 |
| 18 | gi_v02_a1db38f71729 | 状语关系 | 50 | 16_97_p2 B-09 | 条件 | 正确；高亮完整 |
| 19 | gi_v02_4feabec39c84 | 状语关系 | 61 | 22_90_p1 D-05 | 原因 | 正确；高亮完整 |
| 20 | gi_v02_f4786fc2897f | 状语关系 | 3 | ielts5_test4_p2 H-30 | 时间 | 正确；高亮完整 |
| 21 | gi_v02_ade77261a1f1 | 完整主语 | 20 | ielts10_test1_p3 B-01 | For Robert B. Cialdini, Professor of Psychology at Arizona State University, 【one reason that companies don't succeed as often as they should】 is that innovation starts with recruitment. | 正确；高亮完整 |
| 22 | gi_v02_f1f07b875c20 | 完整主语 | 37 | ielts5_test1_p3 G-26 | 【Newspapers and broadcasters】 are there to provide what the public wants. | 正确；高亮完整 |
| 23 | gi_v02_ee2fc3e7fad0 | 完整主语 | 18 | ielts5_test3_p3 A-05 | 【Researchers, executives and marketing people】 are now using the expression without irony or inverted commas. | 正确；高亮完整 |
| 24 | gi_v02_46a92ce02130 | 完整主语 | 38 | ielts8_test2_p1 F-02 | 【Several processes - melting, refining, homogenising】 - take place simultaneously in the 2000 tonnes of molten glass in the furnace. | 核心答案正确；闭破折号在高亮外（A2） |
| 25 | gi_v02_63439afffe6e | 完整主语 | 60 | ielts6_test2_p2 K-37 | 【The research】 suggests that older people fare best when they feel independent but know they can get help when they need it. | 正确；高亮完整 |
| 26 | gi_v02_9a45c44a4e19 | 动词身份 | 8 | ielts18_test3_p3 H-01 | 非谓语（不定式、分词、动名词） | 正确；高亮完整 |
| 27 | gi_v02_4ea25ca438c2 | 动词身份 | 7 | 13_6_p2 D-17 | 非谓语（不定式、分词、动名词） | 正确；高亮完整 |
| 28 | gi_v02_50214827aaec | 动词身份 | 52 | 77_16_p2 E-01 | 从句里的谓语 | 正确；高亮完整 |
| 29 | gi_v02_c4202beb758b | 动词身份 | 34 | 92_58_p3 D-05 | 主句谓语 | 正确；高亮完整 |
| 30 | gi_v02_f978ac417e36 | 动词身份 | 30 | 72_15_p2 H-02 | 主句谓语 | 正确；高亮完整 |


## 附录B：改动句自动池60题

| # | 题目编号 | 工作表/模板 | Excel行 | 来源 | 机器答案 | 独立判定 |
|---|---|---|---|---|---|---|
| 1 | gi_v02_2c105d512ccd | 动词身份 | — | ielts20_test4_p2 D-19 | 主句谓语 | 正确；高亮完整 |
| 2 | gi_v02_0eb128addb05 | 动词身份 | — | 50_30_p2 A-01 | 从句里的谓语 | 正确；高亮完整 |
| 3 | gi_v02_e3b7bbd98166 | 动词身份 | — | 13_6_p1 B-03 | 主句谓语 | 正确；高亮完整 |
| 4 | gi_v02_250c2a77cee8 | 动词身份 | — | 38_22_p1 I-01 | 主句谓语 | 正确；高亮完整 |
| 5 | gi_v02_34c0d93ec911 | 主句谓语 | — | 91_49_p3 E-01 | Perhaps the most significant work done at the WCDR meetings 【was】 the drafting and adoption of the Hyogo Declaration. | 正确；高亮完整 |
| 6 | gi_v02_a9d4d0bc5bef | 完整主语 | — | 81_93_p2 B-04 | 【The proportion of adults with higher educational qualifications in developed countries】 almost doubled between 1975 and 2000. | 正确；高亮完整 |
| 7 | gi_v02_341e237229b0 | 从句边界 | — | 14_23_p2 B-02 | At that time there existed a game known as caturanga, 【which means 'four division'】, those divisions being of the military, represented by the infantry, cavalry, elephants, and chariotry. | 正确；高亮完整 |
| 8 | gi_v02_6f5f11690409 | 完整主语 | — | ielts7_test1_p3 C-11 | In suggestopedia, as he called his method, 【consciousness】 is shifted away from the curriculum to focus on something peripheral. | 正确；高亮完整 |
| 9 | gi_v02_1da79e71d441 | 主句谓语 | — | 73_5_p1 D-02 | The building the country's largest commercial and shopping complex 【uses】 less than 10% of the energy of a conventional building of its size. | 局部答案正确；整句不适合出题（A3） |
| 10 | gi_v02_3d126cde1372 | 动词身份 | — | 40_75_p3 H-07 | 从句里的谓语 | 正确；高亮完整 |
| 11 | gi_v02_07309feeea7a | 从句类型 | — | 27_33_p1 D-02 | 定语从句 | 局部答案正确；整句不适合出题（A3） |
| 12 | gi_v02_07660c7238dc | 状语关系 | — | 73_5_p1 H-01 | 原因 | 正确；高亮完整 |
| 13 | gi_v02_880a48ffe8be | 从句类型 | — | 65_69_p2 I-02 | 状语从句 | 正确；高亮完整 |
| 14 | gi_v02_72efbc70bdf6 | 从句类型 | — | 73_5_p1 D-03 | 状语从句 | 正确；高亮完整 |
| 15 | gi_v02_7279e31a6117 | 从句类型 | — | 48_21_p3 I-02 | 定语从句 | 正确；高亮完整 |
| 16 | gi_v02_9a8df6ebaba8 | 从句类型 | — | 40_75_p2 B-04 | 定语从句 | 正确；高亮完整 |
| 17 | gi_v02_e7f3c938664b | 从句类型 | — | ielts20_test2_p3 I-51 | 不是从句（短语或非谓语） | 正确；高亮完整 |
| 18 | gi_v02_0baec921d557 | 完整主语 | — | 22_90_p1 D-04 | 【A position 60 degrees to the right of the sun】 will prompt the bee to fly downwards at a 60 degrees angle toward the right of the nest. | 正确；高亮完整 |
| 19 | gi_v02_15d13a5a7130 | 主句谓语 | — | 92_58_p3 B-01 | The indigenous people of the area at the time of European settlement 【have】 generally 【been welcomed】 to as the Sydney people or the Eora (Eora means "the people"). | 局部答案正确；整句不适合出题（A3） |
| 20 | gi_v02_c980c657ddac | 动词身份 | — | 24_56_p3 C-07 | 从句里的谓语 | 正确；高亮完整 |
| 21 | gi_v02_76f321f42de6 | 动词身份 | — | 91_49_p2 C-06 | 非谓语（不定式、分词、动名词） | 正确；高亮完整 |
| 22 | gi_v02_3e8f6f43b412 | 从句类型 | — | 65_69_p1 G-01 | 不是从句（短语或非谓语） | 正确；高亮完整 |
| 23 | gi_v02_d8f4e8ec3204 | 从句类型 | — | 53_83_p3 D-08 | 名词性从句 | 正确；高亮完整 |
| 24 | gi_v02_88f91d3cc4cb | 从句类型 | — | 78_102_p1 G-01 | 不是从句（短语或非谓语） | 正确；高亮完整 |
| 25 | gi_v02_ce2766b4c054 | 从句边界 | — | 83_95_p2 H-02 | They say every bird must sing its own throat 【while we say every traveller should find his own way out of variegated and unblemished paths of deep valleys and steep mountains】. | 正确；高亮完整 |
| 26 | gi_v02_fdc29540241e | 从句类型 | — | 82_4_p1 C-01 | 不是从句（短语或非谓语） | 正确；高亮完整 |
| 27 | gi_v02_fa439f1d87c3 | 完整主语 | — | 40_75_p2 C-05 | 【The icy blast that howls over the ice cap and out to sea—the so-called katabatic wind】—can reach 300 km/hr, creating fearsome wind-chill effects, | 核心答案正确；闭破折号在高亮外（A2） |
| 28 | gi_v02_c384bc10d471 | 从句类型 | — | 27_33_p1 C-03 | 状语从句 | 正确；高亮完整 |
| 29 | gi_v02_3825d0c18103 | 主句谓语 | — | 32_20_p2 N-04 | They 【may】 also 【have】 difficulty managing the ordinary activities of daily living, understanding the behaviour of others, and determining their own appropriate social responses (adaptive behaviour). | 正确；高亮完整 |
| 30 | gi_v02_456b69bd5bf8 | 动词身份 | — | 32_20_p1 G-01 | 主句谓语 | 正确；高亮完整 |
| 31 | gi_v02_67cd64e74e8a | 从句类型 | — | 78_102_p1 C-02 | 不是从句（短语或非谓语） | 正确；高亮完整 |
| 32 | gi_v02_e4acc4b7cd2b | 从句类型 | — | 48_21_p3 C-04 | 名词性从句 | 正确；高亮完整 |
| 33 | gi_v02_2fc2b1077837 | 动词身份 | — | 85_12_p2 E-10 | 从句里的谓语 | 正确；高亮完整 |
| 34 | gi_v02_36547e5b696e | 动词身份 | — | 78_102_p3 F-02 | 非谓语（不定式、分词、动名词） | 正确；高亮完整 |
| 35 | gi_v02_86926bb17e23 | 主句谓语 | — | 24_56_p2 I-01 | In a classic demonstration of the power of sunk costs, people 【were offered】 season subscriptions to a local theatre company. | 正确；高亮完整 |
| 36 | gi_v02_d9aa6a819983 | 从句边界 | — | 65_69_p3 C-01 | According to the vaguely worded United Nations Outer Space Treaty of 1967, 【what it terms 'space junk'】 remains the property of the country that sent the craft or probe into space. | 正确；高亮完整 |
| 37 | gi_v02_573385d95ce7 | 主句谓语 | — | 91_49_p3 D-03 | The January meeting of the WCDR in Kobe 【provided】 experts and scientists from over 150 countries, government officials, Non-Government Organisation (NGOs) and United Nations representatives an opportunity to review the Yokohama Strategy. | 正确；高亮完整 |
| 38 | gi_v02_6f42a4fb909d | 动词身份 | — | 83_95_p2 D-04 | 主句谓语 | 正确；高亮完整 |
| 39 | gi_v02_4678dd055de9 | 完整主语 | — | 73_5_p3 L-06 | 【Such questions】 go to the heart of how rainforests happen. | 正确；高亮完整 |
| 40 | gi_v02_63b99779b346 | 从句类型 | — | 69_40_p2 C-02 | 定语从句 | 正确；高亮完整 |
| 41 | gi_v02_fbff4bc1cd78 | 从句边界 | — | 81_93_p3 H-09 | 【When summer comes】, we go to barbecues at family or friends' houses. | 正确；高亮完整 |
| 42 | gi_v02_5579d7efa2d5 | 从句类型 | — | 62_44_p2 D-03 | 不是从句（短语或非谓语） | 正确；高亮完整 |
| 43 | gi_v02_183ff8062075 | 从句类型 | — | 18_53_p1 E-04 | 并列分句 | 正确；高亮完整 |
| 44 | gi_v02_031090de09c5 | 从句边界 | — | 50_30_p2 D-04 | Further elegant experiments showed that naive adults could develop the skill if they were provided with cones 【from which the first complete spiral of scales had been removed】, rather like our new photocopier which you can work out how to use once someone has shown you how to switch it on. | 正确；高亮完整 |
| 45 | gi_v02_eb82a68433f1 | 动词身份 | — | ielts19_test4_p3 H-02b | 主句谓语 | 正确；高亮完整 |
| 46 | gi_v02_e1ec51c118aa | 主句谓语 | — | ielts4_test2_p2 B-06b | In many other industrialized countries, orthodox and alternative medicines 【have worked】 "hand in glove" for years. | 正确；高亮完整 |
| 47 | gi_v02_22ac7a742df1 | 主句谓语 | — | 84_73_p1 A-07 | And a similar revelation 【is】 now 【dawning】 on hydrologists. | 正确；高亮完整 |
| 48 | gi_v02_b8a9caf6bac5 | 动词身份 | — | 91_49_p3 F-05 | 非谓语（不定式、分词、动名词） | 正确；高亮完整 |
| 49 | gi_v02_39f8799e3258 | 主句谓语 | — | 83_95_p1 D-01 | Thirty years after the Alex studies began, Pepperberg and a changing collection of assistants 【were】 still 【giving】 him English lessons. | 正确；高亮完整 |
| 50 | gi_v02_47c610160819 | 完整主语 | — | 9_81_p3 A-01 | Of the world's 6,500 living languages, 【around half】 are expected to die out by the end of this century, according to UNESCO. | 正确；高亮完整 |
| 51 | gi_v02_5217981d167b | 动词身份 | — | 46_84_p1 D-09 | 非谓语（不定式、分词、动名词） | 正确；高亮完整 |
| 52 | gi_v02_9db73bd6088e | 主句谓语 | — | 32_20_p1 B-04 | The idea of childhood 【corresponds】 to awareness about the peculiar nature of childhood, which distinguishes the child from adult, even the young adult. | 正确；高亮完整 |
| 53 | gi_v02_b6c9bfacf3bb | 主句谓语 | — | 73_5_p1 H-02b | 'Perhaps you 【could store】 the summer's heat in water somehow.' | 正确；高亮完整 |
| 54 | gi_v02_9716e32b633b | 完整主语 | — | 13_6_p1 B-03 | 【The government】 saw the solution in the providing of Physical Education programmes in schools, delivered by better prepared and specifically educated PE teachers. | 正确；高亮完整 |
| 55 | gi_v02_b1182c070935 | 主句谓语 | — | 76_43_p2 H-02 | By the late 1980s the Modern Movement, unfairly blamed for the social experiments implicit in high-rise housing, 【had lost out】 to irony and spectacle in the shape of post-modernism, with its cheerful borrowings from anywhere and any period. | 正确；高亮完整 |
| 56 | gi_v02_3434eced01a1 | 动词身份 | — | 24_56_p3 G-02 | 主句谓语 | 局部答案正确；整句不适合出题（A3） |
| 57 | gi_v02_482a11c03b2f | 从句边界 | — | 10_78_p3 F-01 | Incidents 【where vein has been injected intrathecally instead of spine】 are a classic example of how poor design can contribute to harm. | 局部答案正确；整句不适合出题（A3） |
| 58 | gi_v02_17343ceb1d4f | 动词身份 | — | 48_21_p1 G-05 | 从句里的谓语 | 正确；高亮完整 |
| 59 | gi_v02_51af3faa6332 | 动词身份 | — | 26_72_p1 G-12 | 主句谓语 | 正确；高亮完整 |
| 60 | gi_v02_2bab41be9806 | 动词身份 | — | 84_73_p3 B-03 | 从句里的谓语 | 正确；高亮完整 |


## 附录C1：第二轮从属连词降级10题

| # | 题目编号 | 工作表/模板 | Excel行 | 来源 | 机器答案 | 独立判定 |
|---|---|---|---|---|---|---|
| 1 | gi_v02_18cf6e86cb6c | 从句类型 | — | 85_12_p2 D-05 | 并列分句 | 降级合理：目标是从属从句 |
| 2 | gi_v02_0c74f14af556 | 从句边界 | — | ielts10_test4_p2 A-01 | Psychologists have long held that a person's character cannot undergo a transformation in any meaningful way and 【that the key traits of personality are determined at a very young age】. | 降级合理：目标是从属从句 |
| 3 | gi_v02_fe3397036eee | 从句边界 | — | ielts9_test3_p1 C-01 | In its most general sense, prescriptivism is the view that one variety of language has an inherently higher value than others, and 【that this ought to be imposed on the whole of the speech community】. | 降级合理：目标是从属从句 |
| 4 | gi_v02_3c104522dc2f | 从句类型 | — | ielts9_test3_p1 C-01 | 并列分句 | 降级合理：目标是从属从句 |
| 5 | gi_v02_d73a253b0286 | 从句类型 | — | ielts5_test2_p2 D-16 | 并列分句 | 保守误降：that为指示限定词，确为并列分句（A1） |
| 6 | gi_v02_aa379bf5395a | 从句边界 | — | ielts10_test4_p3 F-04 | The team calculated that there is a good chance of silent genes surviving for up to 6 million years in at least a few individuals in a population, and 【that some might survive as long as 10 million years】. | 降级合理：目标是从属从句 |
| 7 | gi_v02_14154ac28357 | 从句类型 | — | 92_58_p1 B-06 | 并列分句 | 降级合理：目标是从属从句 |
| 8 | gi_v02_488fefba68ca | 从句边界 | — | 92_58_p1 B-02 | This might mean that words have a particular taste (for example, the word "door" might taste like bacon), or 【that certain smells produce a particular colour】. | 降级合理：目标是从属从句 |
| 9 | gi_v02_05d6a5b66604 | 从句类型 | — | ielts4_test1_p3 E-21 | 并列分句 | 降级合理：目标是从属从句 |
| 10 | gi_v02_acf1a9d11a4e | 从句类型 | — | ielts12_test6_p2 F-03 | 并列分句 | 降级合理：目标是从属从句 |


## 附录C2：第四轮并列谓语降级20题

| # | 题目编号 | 工作表/模板 | Excel行 | 来源 | 机器答案 | 独立判定 |
|---|---|---|---|---|---|---|
| 1 | gi_v02_3fff40c90474 | 从句边界 | — | ielts8_test1_p2 G-10 | These correspond roughly to small municipal, medium-sized metropolitan and major metropolitan airports respectively, and 【encompass an increasingly rigorous set of regulations】. | 降级合理：共用主语的并列谓语 |
| 2 | gi_v02_16cee0add28f | 从句类型 | — | 83_95_p3 D-01 | 并列分句 | 降级合理：共用主语的并列谓语 |
| 3 | gi_v02_37bf292cffd1 | 从句类型 | — | ielts6_test2_p1 C-12 | 并列分句 | 降级合理：共用主语的并列谓语 |
| 4 | gi_v02_4e2ee3a2e96d | 从句类型 | — | ielts11_test4_p2 A-02 | 并列分句 | 降级合理：共用主语的并列谓语 |
| 5 | gi_v02_ed63019c349a | 从句类型 | — | 88_98_p1 E-02 | 并列分句 | 降级合理：共用主语的并列谓语 |
| 6 | gi_v02_a453effc0653 | 从句类型 | — | ielts12_test5_p2 K-02 | 并列分句 | 降级合理：共用主语的并列谓语 |
| 7 | gi_v02_2d90c33fe329 | 从句边界 | — | ielts6_test3_p3 G-27 | It has proved toxic at some doses in animals and 【so cannot be used in humans】. | 降级合理：共用主语的并列谓语 |
| 8 | gi_v02_59167bc15347 | 从句类型 | — | ielts10_test3_p2 B-05 | 并列分句 | 降级合理：共用主语的并列谓语 |
| 9 | gi_v02_108b2c50e6f4 | 从句边界 | — | ielts11_test3_p1 D-09 | Venetian merchants traded extensively in silk and 【encouraged silk growers to settle in Italy】. | 降级合理：共用主语的并列谓语 |
| 10 | gi_v02_11c3868bad0f | 从句边界 | — | ielts11_test2_p3 A-01 | An emerging discipline called neuroaesthetics is seeking to bring scientific objectivity to the study of art, and 【has already given us a better understanding of many masterpieces】. | 降级合理：共用主语的并列谓语 |
| 11 | gi_v02_c69e45b72046 | 从句类型 | — | 88_98_p1 I-05 | 并列分句 | 降级合理：共用主语的并列谓语 |
| 12 | gi_v02_a9f9fd5a50f0 | 从句边界 | — | ielts12_test5_p1 G-04 | Moreover, cork forests are a resource which support local biodiversity, and 【prevent desertification in the regions where they are planted】. | 降级合理：共用主语的并列谓语 |
| 13 | gi_v02_d6246062661e | 从句类型 | — | ielts7_test1_p3 G-33 | 并列分句 | 降级合理：共用主语的并列谓语 |
| 14 | gi_v02_159e11af2f5f | 从句类型 | — | 83_95_p2 C-02 | 并列分句 | 降级合理：共用主语的并列谓语 |
| 15 | gi_v02_27de6f44859f | 从句类型 | — | ielts12_test6_p1 H-02 | 并列分句 | 降级合理：共用主语的并列谓语 |
| 16 | gi_v02_abb7c2fafb39 | 从句类型 | — | 22_90_p2 F-18 | 并列分句 | 降级合理：共用主语的并列谓语 |
| 17 | gi_v02_59e17d26676f | 从句边界 | — | 83_95_p3 G-02 | He uses these to maintain his retainers, and 【may use them for redistribution to his subjects】. | 降级合理：共用主语的并列谓语 |
| 18 | gi_v02_54be556ec702 | 从句类型 | — | ielts10_test1_p1 B-01 | 并列分句 | 降级合理：共用主语的并列谓语 |
| 19 | gi_v02_666f62fdd3fc | 从句类型 | — | 84_73_p3 D-01 | 并列分句 | 降级合理：共用主语的并列谓语 |
| 20 | gi_v02_998c14e2853b | 从句类型 | — | 88_98_p2 J-04 | 并列分句 | 降级合理：共用主语的并列谓语 |


## 附录C3：仍自动通过的并列分句20题

| # | 题目编号 | 工作表/模板 | Excel行 | 来源 | 机器答案 | 独立判定 |
|---|---|---|---|---|---|---|
| 1 | gi_v02_47a154450c6e | 从句类型 | — | ielts14_test2_p1 B-04 | 并列分句 | 自动通过合理：有独立主语的并列分句 |
| 2 | gi_v02_1786ba149567 | 从句类型 | — | ielts9_test4_p2 B-02 | 并列分句 | 自动通过合理：有独立主语的并列分句 |
| 3 | gi_v02_3fa593e84c7d | 从句边界 | — | ielts20_test2_p3 D-16 | In response, MLB decided to tweak the dimensions of the zone, and 【the following year the consensus was that ABS is profoundly consistent】. | 自动通过合理：有独立主语的并列分句 |
| 4 | gi_v02_5ae9d97a82b4 | 从句边界 | — | ielts10_test1_p2 A-05 | The number of cars on European Union (EU) roads saw an increase of three million cars each year from 1990 to 2010, and 【in the next decade the EU will see a further substantial increase in its fleet】. | 自动通过合理：有独立主语的并列分句 |
| 5 | gi_v02_58690eb1eeb4 | 从句类型 | — | ielts6_test3_p3 C-14 | 并列分句 | 自动通过合理：有独立主语的并列分句 |
| 6 | gi_v02_c551e0084b5d | 从句边界 | — | ielts8_test3_p3 D-22 | There are striking differences in life span between different species, but 【within one species the parameter is relatively constant】. | 自动通过合理：有独立主语的并列分句 |
| 7 | gi_v02_30ce4cd0026f | 从句类型 | — | 14_23_p1 D-04 | 并列分句 | 自动通过合理：有独立主语的并列分句 |
| 8 | gi_v02_6c790d8ac73c | 从句类型 | — | ielts14_test4_p2 A-02 | 并列分句 | 自动通过合理：有独立主语的并列分句 |
| 9 | gi_v02_0b9764d87eff | 从句边界 | — | ielts5_test1_p3 C-11 | Yet opinion polls suggest that many people nurture the belief that environmental standards are declining and 【four factors seem to cause this disjunction between perception and reality】. | 自动通过合理：有独立主语的并列分句 |
| 10 | gi_v02_0c915c4b2313 | 从句边界 | — | 32_20_p3 C-01 | The government has long espoused moderate daily exercise - of the evening-walk or take-the-stairs variety - but 【that may not do much to budge the needle on the scale】. | 自动通过合理：有独立主语的并列分句 |
| 11 | gi_v02_f4ce504dc77b | 从句边界 | — | ielts13_test3_p1 F-07 | In Asia, there is a large degree of coconut diversity and evidence of millennia of human use—but 【there are no relatives growing in the wild】. | 自动通过合理：有独立主语的并列分句 |
| 12 | gi_v02_cd8b7b098da7 | 从句边界 | — | 81_93_p2 B-08 | China doubled its student population in the late 1990s, and 【India is trying to follow suit】. | 自动通过合理：有独立主语的并列分句 |
| 13 | gi_v02_cd0ba903127c | 从句类型 | — | ielts15_test1_p1 C-04 | 并列分句 | 自动通过合理：有独立主语的并列分句 |
| 14 | gi_v02_138507178960 | 从句类型 | — | ielts20_test1_p1 H-04 | 并列分句 | 自动通过合理：有独立主语的并列分句 |
| 15 | gi_v02_2318bfc8997d | 从句类型 | — | ielts7_test1_p1 C-03 | 并列分句 | 自动通过合理：有独立主语的并列分句 |
| 16 | gi_v02_d3a88b8e5028 | 从句类型 | — | ielts14_test4_p2 B-08 | 并列分句 | 自动通过合理：有独立主语的并列分句 |
| 17 | gi_v02_6fc3bdf20301 | 从句类型 | — | ielts10_test3_p3 C-01 | 并列分句 | 自动通过合理：有独立主语的并列分句 |
| 18 | gi_v02_f60f3642e591 | 从句边界 | — | 6_71_p3 H-04 | Whether this condition has shaped the sound systems of these languages is unknown, says Evans, but 【it is important to consider the idea】. | 自动通过合理：有独立主语的并列分句 |
| 19 | gi_v02_62f61e8595c4 | 从句边界 | — | 11_103_p3 D-01 | Despite an indigenous tradition of rain-water harvesting and irrigation systems going back to the third century BC, policy-makers in modern times have often overlooked the value of such technologies, and 【it is only recently that officials have taken much interest in household-level structures】. | 自动通过合理：有独立主语的并列分句 |
| 20 | gi_v02_7837012985a0 | 从句类型 | — | ielts8_test3_p1 E-03 | 并列分句 | 自动通过合理：有独立主语的并列分句 |


## 附录C4：全部10道for降级题

| # | 题目编号 | 工作表/模板 | Excel行 | 来源 | 机器答案 | 独立判定 |
|---|---|---|---|---|---|---|
| 1 | gi_v02_40f5921221d7 | 从句类型 | — | 32_20_p1 B-03 | 状语从句 | 降级合理：for为因为义并列连词 |
| 2 | gi_v02_0b1f7a5f4aa5 | 从句边界 | — | ielts10_test3_p3 C-04 | 'It's an important discovery,' says Matthew Spriggs, professor of archaeology at the Australian National University and head of the international team digging up the site, '【for it conclusively identifies the remains as Lapita】.' | 降级合理：for为因为义并列连词 |
| 3 | gi_v02_f824df4bd989 | 从句类型 | — | ielts8_test2_p2 D-04 | 状语从句 | 降级合理：for为因为义并列连词 |
| 4 | gi_v02_288df3f88b7d | 从句类型 | — | ielts10_test3_p3 C-04 | 状语从句 | 降级合理：for为因为义并列连词 |
| 5 | gi_v02_566cda1eb8ff | 从句边界 | — | 32_20_p1 B-03 | After scrutinising medieval pictures and diaries, he concluded that there was no distinction between children and adults 【for they shared similar leisure activities and work】. | 降级合理：for为因为义并列连词 |
| 6 | gi_v02_c4331e43e111 | 从句类型 | — | ielts9_test1_p3 B-13 | 状语从句 | 降级合理：for为因为义并列连词 |
| 7 | gi_v02_4e986e6f5301 | 从句边界 | — | ielts9_test1_p3 B-13 | However, they are, in one respect, less fully given back to the water than whales or dugongs, 【for turtles still lay their eggs on beaches】. | 降级合理：for为因为义并列连词 |
| 8 | gi_v02_ce6023896761 | 从句边界 | — | ielts8_test2_p2 D-04 | It was not a time of uniform warmth, 【for then, as always since the Great Ice Age, there were constant shifts in rainfall and temperature】. | 降级合理：for为因为义并列连词 |
| 9 | gi_v02_ce0601ba46bb | 从句边界 | — | 44_29_p1 G-03 | The latter is more important, 【for these insects are actually somewhat gregarious】. | 降级合理：for为因为义并列连词 |
| 10 | gi_v02_b2ba54a3efe8 | 从句类型 | — | 44_29_p1 G-03 | 状语从句 | 降级合理：for为因为义并列连词 |


## 附录D：题目数据50处独立抽查

种子20261027；以d548a54至2051ff0的1065条变更字符串池按实际文件/篇章/JSON路径遍历顺序（完整选中路径列在下表），用Random.sample抽50，不抽未变字段。判定只针对替换本身，不为原题全部推理背书。

| # | passage_id | JSON路径 | 字符改动（前→后） | 判定 |
|---|---|---|---|---|
| 1 | reading_jijing_73_test_5_p3 | groups[2].questions[1].analysis | '-' → '' | 替换合理 |
| 2 | reading_jijing_65_test_69_p3 | groups[1].questions[2].locating_words[2].syn_ary[0].target_sen[0].target_sen | 'b' → 'E' | 替换合理 |
| 3 | reading_jijing_73_test_5_p1 | groups[0].questions[1].locating_words[1].syn_ary[0].target_sen[0].target_sen | ' ' → '' | 替换合理 |
| 4 | reading_jijing_91_test_49_p3 | groups[2].questions[1].locating_words[2].syn_ary[0].target_sen[0].target_sen | 'r' → '' | 替换合理 |
| 5 | reading_jijing_91_test_49_p3 | groups[2].questions[0].locating_words[0].syn_ary[0].target_sen[0].target_sen | ',' → '.' | 替换合理 |
| 6 | reading_jijing_5_test_59_p2 | groups[2].questions[2].locating_words[3].syn_ary[1].target_sen[0].target_sen | '' → 'ff' | 替换合理 |
| 7 | reading_jijing_50_test_30_p2 | groups[0].questions[0].locating_words[2].syn_ary[0].target_sen[0].target_sen | 'd' → 'k' | 替换合理 |
| 8 | reading_jijing_85_test_12_p2 | groups[0].questions[0].analysis | '' → ' ' | 替换合理 |
| 9 | reading_jijing_48_test_21_p3 | groups[1].questions[0].central_sentences[0].sentence | 'e' → 'at' | 替换合理 |
| 10 | reading_jijing_48_test_21_p3 | groups[1].questions[0].locating_words[2].syn_ary[0].target_sen[0].target_sen | 'e' → 'at' | 替换合理 |
| 11 | reading_jijing_44_test_29_p3 | groups[3].questions[2].locating_words[1].syn_ary[0].target_sen[0].target_sen | 'l' → 't' | 替换合理 |
| 12 | reading_jijing_79_test_24_p1 | groups[2].questions[0].locating_words[2].syn_ary[0].target_sen[3].target_sen | '' → ',' | 替换合理 |
| 13 | reading_jijing_79_test_24_p1 | groups[1].questions[3].locating_words[1].syn_ary[1].target_sen[0].target_sen | '' → ',' | 替换合理 |
| 14 | reading_jijing_65_test_69_p2 | groups[1].questions[5].locating_words[1].syn_ary[0].target_sen[0].target_sen | ' ' → '' | 替换合理 |
| 15 | reading_jijing_22_test_90_p1 | groups[1].questions[1].locating_words[3].syn_ary[2].target_sen[0].target_sen | '' → 'a' | 替换合理 |
| 16 | reading_jijing_9_test_81_p2 | groups[1].questions[4].locating_words[1].syn_ary[0].target_sen[0].target_sen | 'il' → 'h'；'il' → 'n' | 替换合理 |
| 17 | reading_jijing_85_test_12_p2 | groups[1].questions[0].central_sentences[0].sentence | '' → ' ' | 替换合理 |
| 18 | reading_jijing_69_test_40_p2 | groups[0].questions[1].locating_words[1].syn_ary[1].target_sen[0].target_sen | 'l' → 't' | 替换合理 |
| 19 | reading_jijing_18_test_53_p2 | groups[2].questions[1].central_sentences[0].sentence | '/' → ",' " | 替换合理 |
| 20 | reading_jijing_40_test_75_p1 | groups[1].questions[3].analysis | '-' → '' | 替换合理 |
| 21 | reading_jijing_78_test_102_p1 | groups[0].questions[2].locating_words[4].syn_ary[0].synonym | '' → 'as ' | 替换合理 |
| 22 | reading_jijing_82_test_4_p3 | groups[1].questions[3].locating_words[3].syn_ary[0].target_sen[0].target_sen | '0' → '9' | 替换合理 |
| 23 | reading_jijing_18_test_53_p1 | groups[0].questions[3].central_sentences[0].sentence | 'm' → 'rn' | 替换合理 |
| 24 | reading_jijing_44_test_29_p1 | groups[1].questions[2].locating_words[2].syn_ary[0].target_sen[0].target_sen | ' ' → '' | 替换合理 |
| 25 | reading_jijing_88_test_98_p2 | groups[2].questions[0].locating_words[0].syn_ary[3].target_sen[0].target_sen | '' → ' ' | 替换合理 |
| 26 | reading_jijing_5_test_59_p2 | groups[2].questions[2].locating_words[1].syn_ary[0].target_sen[0].target_sen | '' → 'ff' | 替换合理 |
| 27 | reading_jijing_40_test_75_p2 | groups[0].questions[1].central_sentences[0].sentence | '-' → '' | 替换合理 |
| 28 | reading_jijing_10_test_78_p3 | groups[0].questions[2].locating_words[0].syn_ary[0].target_sen[0].target_sen | ':' → '' | 替换合理 |
| 29 | reading_jijing_77_test_16_p2 | groups[1].questions[0].locating_words[3].syn_ary[0].target_sen[0].target_sen | '' → ' ' | 替换合理 |
| 30 | reading_jijing_22_test_90_p3 | groups[2].questions[3].central_sentences[0].sentence | '' → ' ' | 替换合理 |
| 31 | reading_jijing_48_test_21_p1 | groups[1].questions[5].locating_words[7].syn_ary[0].target_sen[1].target_sen | 'l' → 't' | 替换合理 |
| 32 | reading_jijing_62_test_44_p1 | groups[0].questions[2].central_sentences[0].sentence | '' → 'a' | 替换合理 |
| 33 | reading_jijing_76_test_43_p2 | groups[0].questions[0].central_sentences[0].sentence | ' ' → '' | 替换合理 |
| 34 | reading_jijing_40_test_75_p3 | groups[0].questions[2].analysis | 'o' → 'a'；'t' → 'f'；'' → 't' | 替换合理 |
| 35 | reading_jijing_14_test_23_p3 | groups[1].questions[1].locating_words[3].syn_ary[0].target_sen[1].target_sen | '&#124;' → '.' | 替换合理 |
| 36 | reading_jijing_91_test_49_p3 | groups[2].questions[0].locating_words[2].syn_ary[0].target_sen[0].target_sen | ',' → '.' | 替换合理 |
| 37 | reading_jijing_40_test_75_p3 | groups[0].questions[3].locating_words[0].syn_ary[0].target_sen[0].target_sen | '' → 't'；'o' → 'a' | 替换合理 |
| 38 | reading_jijing_22_test_90_p2 | groups[2].questions[0].locating_words[2].syn_ary[0].target_sen[0].target_sen | ',' → '.' | 替换合理 |
| 39 | reading_jijing_14_test_23_p3 | groups[1].questions[1].central_sentences[0].sentence | '&#124;' → '.' | 替换合理 |
| 40 | reading_jijing_73_test_5_p3 | groups[1].questions[0].central_sentences[0].sentence | '' → "'" | 替换合理 |
| 41 | reading_jijing_78_test_102_p1 | groups[2].questions[2].locating_words[6].syn_ary[0].target_sen[0].target_sen | '.' → '' | 替换合理 |
| 42 | reading_jijing_88_test_98_p2 | groups[0].questions[1].locating_words[1].syn_ary[1].target_sen[0].target_sen | 'y' → 'm' | 替换合理 |
| 43 | reading_jijing_10_test_78_p2 | groups[1].questions[4].locating_words[1].syn_ary[0].target_sen[1].target_sen | 'it' → 'a' | 替换合理 |
| 44 | reading_jijing_50_test_30_p1 | groups[0].questions[1].locating_words[0].syn_ary[0].target_sen[0].target_sen | 'c' → 'n' | 替换合理 |
| 45 | reading_jijing_78_test_102_p1 | groups[0].questions[2].locating_words[3].syn_ary[0].target_sen[0].target_sen | '' → 'as ' | 替换合理 |
| 46 | reading_jijing_10_test_78_p1 | groups[0].questions[1].analysis | 'f' → 'r' | 替换合理 |
| 47 | reading_jijing_9_test_81_p2 | groups[2].questions[1].central_sentences.sentences[1] | 'c' → 'e'；'.' → ',' | 替换合理；同篇残留Pridcaux另见N1 |
| 48 | reading_jijing_40_test_75_p3 | groups[1].questions[3].analysis | 'n' → 'm'；'-' → '' | 替换合理 |
| 49 | reading_jijing_73_test_5_p2 | groups[0].questions[2].locating_words[2].syn_ary[0].target_sen[1].target_sen | '' → 't' | 替换合理 |
| 50 | reading_jijing_65_test_69_p2 | groups[0].questions[3].locating_words[1].syn_ary[0].target_sen[0].target_sen | 'm' → 'in' | 替换合理 |


## 附录E：610条新修订的逐条局部结论

编号为1f03c84修订表fixes数组的1基位置。34–63为第二轮，64–93为第三轮；94–643中第555/557为追加，余548条为第四轮。所有条目均已结合段落上下文阅读。表中“合理”只表示此处find→replace成立，同词未同步及新讲解问题仍见N1–N3。原文改法无需撤回不代表整篇无其他问题。


| 条目 | 轮次 | 来源 | find | replace | 独立结果 |
|---|---|---|---|---|---|
| 34 | 二 | 27_33_p1 B-09 | 'claim mat the image' | 'claim that the image' | 合理 |
| 35 | 二 | 29_63_p1 C-01 | '. If current trends continue' | 'If current trends continue' | 合理 |
| 36 | 二 | 78_102_p1 A-01 | '. Despite gun battles' | 'Despite gun battles' | 合理 |
| 37 | 二 | 78_102_p1 A-01 | 'and Galloping inflation' | 'and galloping inflation' | 合理 |
| 38 | 二 | 78_102_p1 C-01 | '. the prerequisites to prevent' | 'The prerequisites to prevent' | 合理 |
| 39 | 二 | 78_102_p1 D-01 | '. Perhaps the most incisive' | 'Perhaps the most incisive' | 合理 |
| 40 | 二 | 78_102_p1 G-01 | '. To encourage reform' | 'To encourage reform' | 合理 |
| 41 | 二 | 78_102_p1 H-01 | '. These measures, he says' | 'These measures, he says' | 合理 |
| 42 | 二 | 92_58_p2 A-01 | '. As in New Delhi' | 'As in New Delhi' | 合理 |
| 43 | 二 | 92_58_p2 A-01 | 'how water resources and managed' | 'how water resources are managed' | 合理 |
| 44 | 二 | 92_58_p2 B-01 | '. That the problem is well-known' | 'That the problem is well-known' | 合理 |
| 45 | 二 | 92_58_p2 C-01 | '. Scientists expect water scarcity' | 'Scientists expect water scarcity' | 合理 |
| 46 | 二 | 92_58_p2 D-01 | '. Because lack of access' | 'Because lack of access' | 合理 |
| 47 | 二 | 92_58_p2 E-01 | ". The world's water problems" | "The world's water problems" | 合理 |
| 48 | 二 | 92_58_p2 F-01 | '. Much of the Americas' | 'Much of the Americas' | 合理 |
| 49 | 二 | 92_58_p2 H-01 | '. Lots of water, but not always' | 'Lots of water, but not always' | 合理 |
| 50 | 二 | 92_58_p2 I-01 | '. Waters run away' | 'Waters run away' | 合理 |
| 51 | 二 | 73_5_p1 H-02 | "challenge.' Perhaps you could store the summer's heat in water somehow." | "challenge. 'Perhaps you could store the summer's heat in water somehow.'" | 合理 |
| 52 | 二 | 38_22_p3 G-07 | 'commented that"research' | 'commented that "research' | 合理 |
| 53 | 二 | 5_59_p1 A-01 | 'his brother. Will, were' | 'his brother, Will, were' | 合理 |
| 54 | 二 | 65_69_p2 H-03 | 'Free Flight. James Fallows' | 'Free Flight, James Fallows' | 合理 |
| 55 | 二 | 69_40_p2 E-04 | 'brutal months. Saving the energy' | 'brutal months, saving the energy' | 合理 |
| 56 | 二 | 71_1_p2 B-03 | "American ranffian saying. 'Je voudrais" | "American ruffian saying 'Je voudrais" | 合理 |
| 57 | 二 | 72_15_p2 F-02 | 'more friends. And who have' | 'more friends, and who have' | 合理 |
| 58 | 二 | 73_5_p3 D-03 | 'In fact. Hooker knew' | 'In fact, Hooker knew' | 合理 |
| 59 | 二 | 76_43_p3 A-07 | '("Do"vs. "Don' | '("Do" vs. "Don' | 合理 |
| 60 | 二 | 9_81_p2 A-02 | 'environmental management. an educational' | 'environmental management, an educational' | 合理 |
| 61 | 二 | 9_81_p2 A-02 | 'direct anil indirect' | 'direct and indirect' | 合理 |
| 62 | 二 | 9_81_p2 A-02 | '(Ayala. I996)' | '(Ayala, 1996)' | 合理 |
| 63 | 二 | 9_81_p2 B-01 | 'Queensland. Australia.' | 'Queensland, Australia.' | 合理 |
| 64 | 三 | 29_63_p1 B-03 | 'carbon dioxide (CO ) every year' | 'carbon dioxide (CO2) every year' | questions 合理 |
| 65 | 三 | 29_63_p1 B-03 | 'agriculture, 2 say some scientists' | 'agriculture, say some scientists' | questions 合理 |
| 66 | 三 | 29_63_p1 B-05 | 'CO is a greenhouse gas' | 'CO2 is a greenhouse gas' | questions 合理 |
| 67 | 三 | 29_63_p1 B-06 | '2 It has accumulated' | 'It has accumulated' | questions 合理 |
| 68 | 三 | 29_63_p1 C-01 | 'atmospheric CO concentrations to double' | 'atmospheric CO2 concentrations to double' | questions 合理 |
| 69 | 三 | 29_63_p1 C-02 | 'enough 2 to raise global temperatures by around 2 to 5.' | 'enough to raise global temperatures by around 2°C to 5°C.' | questions 合理 |
| 70 | 三 | 29_63_p1 E-01 | 'half of the CO we produce' | 'half of the CO2 we produce' | questions 合理 |
| 71 | 三 | 29_63_p1 E-02 | 'atmospheric CO has doubled since 2001, suggesting 2 that' | 'atmospheric CO2 has doubled since 2001, suggesting that' | questions 合理 |
| 72 | 三 | 29_63_p1 E-02 | 'could now be 2 stretched' | 'could now be stretched' | questions 合理 |
| 73 | 三 | 29_63_p1 E-03 | 'natural CO "sinks"' | 'natural CO2 "sinks"' | questions 合理 |
| 74 | 三 | 29_63_p1 E-03 | 'starting to release 2\nCO . 2' | 'starting to release CO2.' | questions 合理 |
| 75 | 三 | 29_63_p1 G-04 | 'cut CO emissions' | 'cut CO2 emissions' | questions 合理 |
| 76 | 三 | 29_63_p1 G-04 | 'atmospheric CO concentrations--and thus 2 temperatures' | 'atmospheric CO2 concentrations--and thus temperatures' | questions 合理 |
| 77 | 三 | 29_63_p1 G-05 | 'hot our 2 future world' | 'hot our future world' | questions 合理 |
| 78 | 三 | 29_63_p1 None | 'thus  2 temperatures' | 'thus temperatures' | questions 合理 |
| 79 | 三 | 29_63_p1 None | 'atmospheric CO concentrations' | 'atmospheric CO2 concentrations' | questions 合理 |
| 80 | 三 | 29_63_p1 None | 'Peat bogs never release CO . 2' | 'Peat bogs never release CO2.' | questions 合理 |
| 81 | 三 | 29_63_p1 None | "natural CO 'sinks'" | "natural CO2 'sinks'" | questions 合理 |
| 82 | 三 | 29_63_p1 None | 'actually starting to release 2' | 'actually starting to release CO2.' | questions 合理 |
| 83 | 三 | 29_63_p1 None | 'hot our  2 future' | 'hot our future' | questions 合理 |
| 84 | 三 | 29_63_p3 A-02 | 'yuan (\x001.9 trillion)' | 'yuan ($1.9 trillion)' | questions 合理 |
| 85 | 三 | 29_63_p3 A-03 | 'Some\x00265 billion' | 'Some $265 billion' | questions 合理 |
| 86 | 三 | 29_63_p3 F-02 | 'to \x0090 billion in 2005' | 'to $90 billion in 2005' | questions 合理 |
| 87 | 三 | 29_63_p3 F-04 | 'triple to \x00300 billion' | 'triple to $300 billion' | questions 合理 |
| 88 | 三 | 29_63_p3 G-02 | 'another \x00220 billion' | 'another $220 billion' | questions 合理 |
| 89 | 三 | 29_63_p3 None | 'more than\x00300 billion' | 'more than $300 billion' | questions 合理 |
| 90 | 三 | 84_73_p2 C-17 | 'to 18\x00British children' | 'to 18, British children' | questions 合理 |
| 91 | 三 | 75_57_p2 I | '1989\x00and 1993 .' | '1989 and 1993.' | questions 合理 |
| 92 | 三 | 50_30_p2 None | 'rats\x00learning' | "rats' learning" | questions 合理 |
| 93 | 三 | 83_95_p2 D-04 | 'cattle ranching, fagging, oil' | 'cattle ranching, logging, oil' | questions 合理 |
| 94 | 四 | 10_78_p1 C-18 | 'a top of middle' | 'a top or middle' | questions 合理 |
| 95 | 四 | 10_78_p2 A-12 | '"email voice"' | '"email voice".' | at_end 合理 |
| 96 | 四 | 10_78_p2 B-13 | 'the world has' | 'The world has' | 合理 |
| 97 | 四 | 10_78_p2 B-17 | 'ever, liven' | 'ever, even' | 合理 |
| 98 | 四 | 10_78_p2 C-24 | 'her multitasking..' | 'her multitasking.' | questions 合理 |
| 99 | 四 | 10_78_p2 C-26 | 'a wax' | 'a way' | questions 合理 |
| 100 | 四 | 10_78_p2 C-28 | 'if " the' | 'if "the' | questions 合理 |
| 101 | 四 | 10_78_p2 D-30 | 'Davis Meyer' | 'David Meyer' | 合理 |
| 102 | 四 | 10_78_p2 D-34 | 'task look' | 'task took' | questions 合理 |
| 103 | 四 | 10_78_p2 E-41 | 'cheek a' | 'check a' | questions 合理 |
| 104 | 四 | 10_78_p2 E-46 | 'very short time' | 'very short time.' | at_end 合理 |
| 105 | 四 | 10_78_p2 F-49 | 'As it matter' | 'As a matter' | questions 合理 |
| 106 | 四 | 10_78_p3 B-01 | 'drag packaging' | 'drug packaging' | 合理 |
| 107 | 四 | 10_78_p3 B-01 | '(Pits). Many' | '(PILs). Many' | 合理 |
| 108 | 四 | 10_78_p3 H-03 | 'not: fully' | 'not fully' | questions 合理 |
| 109 | 四 | 11_103_p1 A-04 | 'observations of Mars from his own observations of Mars from his own' | 'observations of Mars from his own' | questions 合理 |
| 110 | 四 | 11_103_p1 C-09 | 'up Maritain' | 'up Martian' | questions 合理 |
| 111 | 四 | 11_103_p2 D-06 | '1 You would' | "'You would" | questions 合理 |
| 112 | 四 | 11_103_p2 E-04 | 'all of US' | 'all of us' | questions 合理 |
| 113 | 四 | 11_103_p2 E-04 | "years' says" | "years,' says" | 合理 |
| 114 | 四 | 11_103_p3 B-01 | 'of muthukandiya' | 'of Muthukandiya' | questions 合理 |
| 115 | 四 | 11_103_p3 C-02 | 'harvesting"technology already' | 'harvesting" technology already' | 合理 |
| 116 | 四 | 11_103_p3 E-04 | '–equivalent to' | '– equivalent to' | questions 合理 |
| 117 | 四 | 11_103_p3 H-01 | "it's financial" | 'its financial' | 合理 |
| 118 | 四 | 11_103_p3 I-01 | 'The Muthkandiya' | 'The Muthukandiya' | 合理 |
| 119 | 四 | 13_6_p2 C-14 | 'Angel(1937) are' | 'Angel (1937) are' | questions 合理 |
| 120 | 四 | 13_6_p2 D-16 | 'genre -the musical -' | 'genre - the musical -' | 合理 |
| 121 | 四 | 13_6_p2 D-20 | 'peas ant' | 'peasant' | 合理 |
| 122 | 四 | 13_6_p3 E-03 | 'jars(pithoi) would' | 'jars (pithoi) would' | questions 合理 |
| 123 | 四 | 14_23_p1 G-04 | 'So may be' | 'So maybe' | 合理 |
| 124 | 四 | 14_23_p2 B-03 | 'aventually to' | 'eventually to' | questions 合理 |
| 125 | 四 | 14_23_p2 D-01 | 'one world think' | 'one would think' | 合理 |
| 126 | 四 | 14_23_p2 H-02 | 'Pitting it in s match' | 'pitting it in a match' | questions 合理 |
| 127 | 四 | 14_23_p3 B-04 | 'cruising seed' | 'cruising speed' | 合理 |
| 128 | 四 | 14_23_p3 C-02 | 'of selt-driving' | 'of self-driving' | questions 合理 |
| 129 | 四 | 14_23_p3 D-06 | "'I self-driving" | "'If self-driving" | 合理 |
| 130 | 四 | 14_23_p3 G-01 | 'a redident' | 'a resident' | questions 合理 |
| 131 | 四 | 14_23_p3 G-04 | 'traffic&#124; I' | 'traffic. I' | questions 合理 |
| 132 | 四 | 14_23_p3 H-03 | 'of completely dependent' | 'of being completely dependent' | questions 合理 |
| 133 | 四 | 16_97_p2 E-34 | 'people"retrain" the' | 'people "retrain" the' | 合理 |
| 134 | 四 | 16_97_p3 B-04 | '–the main' | '– the main' | questions 合理 |
| 135 | 四 | 16_97_p3 G-01 | 'problem Like' | 'problem. Like' | questions 合理 |
| 136 | 四 | 16_97_p3 I-04 | 'Duty 2"and' | 'Duty 2" and' | 合理 |
| 137 | 四 | 18_53_p1 E-07 | 'or HI' | 'or H1' | 合理 |
| 138 | 四 | 18_53_p1 G-02 | 'modem commercial' | 'modern commercial' | questions 合理 |
| 139 | 四 | 18_53_p2 F-02 | 'pupils. The whole testing regime' | "pupils. 'The whole testing regime" | 合理 |
| 140 | 四 | 22_90_p1 C-07 | 'meters way' | 'meters away' | questions 合理 |
| 141 | 四 | 22_90_p2 A-01 | 'obese, The' | 'obese. The' | 合理 |
| 142 | 四 | 22_90_p2 B-05 | "reset'children's sleeping" | "reset' children's sleeping" | 合理 |
| 143 | 四 | 22_90_p2 D-10 | 'the bodies metabolism' | "the body's metabolism" | questions 合理 |
| 144 | 四 | 22_90_p2 E-15 | 'the researches published' | 'the researchers published' | 合理 |
| 145 | 四 | 22_90_p3 H-03 | 'in crucial' | 'is crucial' | questions 合理 |
| 146 | 四 | 23_46_p1 A-05 | 'climactic trends;' | 'climatic trends;' | 合理 |
| 147 | 四 | 23_46_p1 E-07 | 'our own activity' | "our own activity.'" | at_end 合理 |
| 148 | 四 | 24_56_p1 A-05 | 'DINA of' | 'DNA of' | questions 合理 |
| 149 | 四 | 24_56_p1 D-01 | 'to oilier' | 'to other' | questions 合理 |
| 150 | 四 | 24_56_p1 E-01 | 'repealed an' | 'repeated an' | questions 合理 |
| 151 | 四 | 24_56_p1 E-02 | "while pigs'brains" | "while pigs' brains" | 合理 |
| 152 | 四 | 24_56_p2 C-02 | 'to 7(from' | 'to 7 (from' | 合理 |
| 153 | 四 | 24_56_p2 C-04 | 'maxi- misers' | 'maximizers' | 合理 |
| 154 | 四 | 24_56_p2 G-02 | '"good enough"philosophy' | '"good enough" philosophy' | 合理 |
| 155 | 四 | 24_56_p2 G-03 | '"good enough"standard' | '"good enough" standard' | 合理 |
| 156 | 四 | 24_56_p2 G-03 | 'the maximizer\'s"best"' | 'the maximizer\'s "best"' | 合理 |
| 157 | 四 | 24_56_p3 D-03 | 'subjects -include' | 'subjects - include' | 合理 |
| 158 | 四 | 24_56_p3 F-03 | 'population often to fifteen' | 'population of ten to fifteen' | questions 合理 |
| 159 | 四 | 24_56_p3 G-02 | 'Phase 11(a)' | 'Phase II(a)' | questions 合理 |
| 160 | 四 | 26_72_p1 A-06 | 'soft-fruited I plants' | 'soft-fruited plants' | questions 合理 |
| 161 | 四 | 26_72_p1 G-10 | 'fun gicide' | 'fungicide' | 合理 |
| 162 | 四 | 26_72_p1 G-12 | 'They cap' | 'They can' | 合理 |
| 163 | 四 | 26_72_p1 I-01 | 'peas ant' | 'peasant' | 合理 |
| 164 | 四 | 26_72_p1 K-02 | 'environ- mental' | 'environmental' | questions 合理 |
| 165 | 四 | 27_33_p1 A-01 | 'there, is believed' | 'there is believed' | 合理 |
| 166 | 四 | 27_33_p1 A-01 | 'Jiving in' | 'living in' | 合理 |
| 167 | 四 | 27_33_p1 A-03 | 'modem day' | 'modern-day' | 合理 |
| 168 | 四 | 27_33_p1 A-04 | 'Ness Is' | 'Ness is' | 合理 |
| 169 | 四 | 27_33_p1 B-04 | 'of tills' | 'of this' | questions 合理 |
| 170 | 四 | 27_33_p1 B-06 | 'claims lie' | 'claims he' | questions 合理 |
| 171 | 四 | 27_33_p1 C-01 | 'could a mirage' | 'could be a mirage' | 合理 |
| 172 | 四 | 27_33_p1 C-03 | 'data, One scientist' | 'data. One scientist' | questions 合理 |
| 173 | 四 | 27_33_p1 C-03 | 'history, It seems' | 'history. It seems' | questions 合理 |
| 174 | 四 | 27_33_p1 C-03 | 'Jive in' | 'live in' | questions 合理 |
| 175 | 四 | 27_33_p1 D-01 | 'year, The phenomenon' | 'year. The phenomenon' | questions 合理 |
| 176 | 四 | 27_33_p1 D-01 | ', Submarines' | '. Submarines' | questions 合理 |
| 177 | 四 | 27_33_p1 D-01 | 'die Loch Ness' | 'the Loch Ness' | questions 合理 |
| 178 | 四 | 27_33_p2 C-06 | 'its own good' | 'its own good.' | at_end 合理 |
| 179 | 四 | 29_63_p2 D-03 | 'renewal, And,' | 'renewal. And,' | 合理 |
| 180 | 四 | 29_63_p2 D-03 | 'mm the clock' | 'turn the clock' | 合理 |
| 181 | 四 | 29_63_p2 E-03 | 'carded the' | 'carried the' | questions 合理 |
| 182 | 四 | 29_63_p3 A-04 | "a result,services'" | "a result, services'" | questions 合理 |
| 183 | 四 | 29_63_p3 C-03 | 'tracking and' | 'trucking and' | 合理 |
| 184 | 四 | 32_20_p1 A-01 | "book Centuries of Childhood'" | "book 'Centuries of Childhood'" | 合理 |
| 185 | 四 | 32_20_p1 F-05 | 'work- Even so' | 'work. Even so' | questions 合理 |
| 186 | 四 | 32_20_p1 F-06 | "'useful child'has" | "'useful child' has" | 合理 |
| 187 | 四 | 32_20_p2 N-04 | 'social responses(adaptive' | 'social responses (adaptive' | questions 合理 |
| 188 | 四 | 32_20_p2 O-07 | 'have intellectual disabilities' | 'have intellectual disabilities.' | at_end 合理 |
| 189 | 四 | 32_20_p3 A-06 | "as'You're fat" | "as 'You're fat" | 合理 |
| 190 | 四 | 32_20_p3 G-04 | 'the stems cells' | 'the stem cells' | 合理 |
| 191 | 四 | 38_22_p3 B-01 | 'first fiared' | 'first flared' | questions 合理 |
| 192 | 四 | 38_22_p3 B-01 | 'International. the' | 'International, the' | 合理 |
| 193 | 四 | 38_22_p3 B-02 | 'Pfefier. a' | 'Pfeffer, a' | 合理 |
| 194 | 四 | 38_22_p3 C-04 | 'competi tive' | 'competitive' | 合理 |
| 195 | 四 | 38_22_p3 C-08 | "ask for,'what purpose" | 'ask for what purpose' | 合理 |
| 196 | 四 | 40_75_p1 A-01 | 'on "Bridge,""Chromatics,"' | 'on "Bridge," "Chromatics,"' | questions 合理 |
| 197 | 四 | 40_75_p1 A-02 | 'authorita-tively about' | 'authoritatively about' | 合理 |
| 198 | 四 | 40_75_p1 A-03 | 'new biog-raphy' | 'new biography' | 合理 |
| 199 | 四 | 40_75_p1 B-06 | 'hypotheses Were' | 'hypotheses were' | 合理 |
| 200 | 四 | 40_75_p1 D-03 | 'Brock-lesby, a' | 'Brocklesby, a' | questions 合理 |
| 201 | 四 | 40_75_p1 E-08 | 'Britan-nica, and' | 'Britannica, and' | questions 合理 |
| 202 | 四 | 40_75_p1 F-05 | "Young's accom-plishments" | "Young's accomplishments" | questions 合理 |
| 203 | 四 | 40_75_p1 G-01 | 'work," Almost' | 'work." Almost' | 合理 |
| 204 | 四 | 40_75_p1 G-04 | "Young's rela-tionships" | "Young's relationships" | 合理 |
| 205 | 四 | 40_75_p2 E-03 | 'influ-ence of' | 'influence of' | 合理 |
| 206 | 四 | 40_75_p2 F-01 | 'and dis-solved' | 'and dissolved' | questions 合理 |
| 207 | 四 | 40_75_p2 F-04 | "or'polynyas'. Recent" | "or 'polynyas'. Recent" | 合理 |
| 208 | 四 | 40_75_p3 A-02 | 'know some-thing' | 'know something' | 合理 |
| 209 | 四 | 40_75_p3 A-03 | 'different. kinds' | 'different kinds' | 合理 |
| 210 | 四 | 40_75_p3 A-04 | 'knowledge medicine' | 'knowledge: medicine' | 合理 |
| 211 | 四 | 40_75_p3 B-04 | 'Iml knowing' | 'but knowing' | 合理 |
| 212 | 四 | 40_75_p3 B-04 | 'a bit. more' | 'a bit more' | 合理 |
| 213 | 四 | 40_75_p3 B-05 | 'in tact' | 'in fact' | questions 合理 |
| 214 | 四 | 40_75_p3 B-06 | 'other limes' | 'other times' | questions 合理 |
| 215 | 四 | 40_75_p3 C-05 | 'You tool worse.' | 'You feel worse.' | questions 合理 |
| 216 | 四 | 40_75_p3 C-06 | "take's your" | 'takes your' | questions 合理 |
| 217 | 四 | 40_75_p3 C-06 | 'lor your' | 'for your' | questions 合理 |
| 218 | 四 | 40_75_p3 D-03 | 'yours of training' | 'years of training' | 合理 |
| 219 | 四 | 40_75_p3 D-04 | 'consider able' | 'considerable' | 合理 |
| 220 | 四 | 40_75_p3 D-08 | 'stains of' | 'status of' | questions 合理 |
| 221 | 四 | 40_75_p3 E-03 | 'diagno-sis is' | 'diagnosis is' | 合理 |
| 222 | 四 | 40_75_p3 E-03 | 'yours of experience' | 'years of experience' | 合理 |
| 223 | 四 | 40_75_p3 F-01 | "of change's" | 'of changes' | questions 合理 |
| 224 | 四 | 40_75_p3 F-01 | 'the subjec-tive' | 'the subjective' | questions 合理 |
| 225 | 四 | 40_75_p3 F-01 | 'of poin' | 'of pain' | questions 合理 |
| 226 | 四 | 40_75_p3 F-02 | 'drown from' | 'drawn from' | questions 合理 |
| 227 | 四 | 40_75_p3 F-03 | 'the post' | 'the past' | questions 合理 |
| 228 | 四 | 40_75_p3 F-04 | 'Refer-ence to' | 'Reference to' | questions 合理 |
| 229 | 四 | 40_75_p3 F-04 | "'stressed end'" | "'stressed out'" | 合理 |
| 230 | 四 | 40_75_p3 F-04 | 'port of' | 'part of' | questions 合理 |
| 231 | 四 | 40_75_p3 F-05 | 'symp-toms of' | 'symptoms of' | 合理 |
| 232 | 四 | 40_75_p3 G-01 | 'on Ihe' | 'on the' | questions 合理 |
| 233 | 四 | 40_75_p3 H-02 | 'he doctor to hove' | 'the doctor to have' | questions 合理 |
| 234 | 四 | 40_75_p3 H-04 | 'employer Unit we' | 'employer that we' | questions 合理 |
| 235 | 四 | 40_75_p3 H-05 | 'on expert' | 'an expert' | questions 合理 |
| 236 | 四 | 40_75_p3 H-05 | 'certificate it we' | 'certificate if we' | questions 合理 |
| 237 | 四 | 40_75_p3 H-05 | 'self-certificaion period.' | 'self-certification period.' | questions 合理 |
| 238 | 四 | 40_75_p3 H-07 | 'permits then' | 'permits them' | questions 合理 |
| 239 | 四 | 40_75_p3 H-07 | 'to pre-scribe' | 'to prescribe' | questions 合理 |
| 240 | 四 | 40_75_p3 H-08 | 'a rauge' | 'a range' | 合理 |
| 241 | 四 | 40_75_p3 I-02 | "may hypothrsie'is" | "may hypothesise 'is" | questions 合理 |
| 242 | 四 | 40_75_p3 I-02 | 'for eevidence' | 'for evidence' | questions 合理 |
| 243 | 四 | 44_29_p1 E-02 | 'hardiest, on' | 'hardiest on' | 合理 |
| 244 | 四 | 44_29_p1 G-07 | 'al location' | 'allocation' | questions 合理 |
| 245 | 四 | 44_29_p1 I-04 | 'need they can fly' | 'need: they can fly' | questions 合理 |
| 246 | 四 | 44_29_p3 B-01 | 'much loo' | 'much too' | questions 合理 |
| 247 | 四 | 44_29_p3 B-05 | 'limes, the' | 'times, the' | questions 合理 |
| 248 | 四 | 44_29_p3 E-02 | 'arc less' | 'are less' | 合理 |
| 249 | 四 | 46_84_p1 A-02 | "(China's rise." | "China's rise." | 合理 |
| 250 | 四 | 46_84_p1 B-01 | 'doing host' | 'doing best' | 合理 |
| 251 | 四 | 46_84_p1 D-06 | 'about. 2' | 'about 2' | 合理 |
| 252 | 四 | 46_84_p1 E-01 | 'ambit ions' | 'ambitious' | questions 合理 |
| 253 | 四 | 46_84_p2 A-02 | 'Univer-sum UK' | 'Universum UK' | questions 合理 |
| 254 | 四 | 46_84_p2 G-01 | '80 businesses,including' | '80 businesses, including' | 合理 |
| 255 | 四 | 46_84_p2 H-03 | 'paid over time' | 'paid overtime' | 合理 |
| 256 | 四 | 46_84_p2 H-03 | 'package, However,' | 'package. However,' | 合理 |
| 257 | 四 | 48_21_p1 B-02 | 'gets. inside' | 'gets inside' | 合理 |
| 258 | 四 | 48_21_p1 G-05 | "the' south" | 'the south' | questions 合理 |
| 259 | 四 | 48_21_p1 H-05 | 'slock of' | 'stock of' | questions 合理 |
| 260 | 四 | 48_21_p2 A-02 | 'and antithera-peutic' | 'and antitherapeutic' | questions 合理 |
| 261 | 四 | 48_21_p2 F-06 | 'regard -to be' | 'regard to be' | 合理 |
| 262 | 四 | 48_21_p3 A-03 | '4oC in' | '4°C in' | questions 合理 |
| 263 | 四 | 48_21_p3 A-03 | '6oC. The' | '6°C. The' | 合理 |
| 264 | 四 | 48_21_p3 C-01 | 'posed be drought' | 'posed by drought' | questions 合理 |
| 265 | 四 | 48_21_p3 F-04 | 'bas al' | 'basal' | questions 合理 |
| 266 | 四 | 48_21_p3 H-01 | 'the serves' | 'that serves' | questions 合理 |
| 267 | 四 | 48_21_p3 I-02 | 'joints efforts' | 'joint efforts' | 合理 |
| 268 | 四 | 50_30_p1 E-02 | "'pine smell" | "'pine' smell" | questions 合理 |
| 269 | 四 | 50_30_p2 D-01 | 'experiences cone' | 'experienced cone' | 合理 |
| 270 | 四 | 50_30_p2 D-04 | 'word out' | 'work out' | questions 合理 |
| 271 | 四 | 50_30_p3 C-04 | "wrong,you're in" | "wrong, you're in" | questions 合理 |
| 272 | 四 | 50_30_p3 D-03 | "rentalmanager's fees," | "rental manager's fees," | questions 合理 |
| 273 | 四 | 53_83_p1 B-04 | 'bank account,"said' | 'bank account," said' | 合理 |
| 274 | 四 | 53_83_p1 B-04 | 'the"next big' | 'the "next big' | 合理 |
| 275 | 四 | 53_83_p1 D-06 | 'phones -something' | 'phones - something' | questions 合理 |
| 276 | 四 | 53_83_p2 C-07 | 'is pul at' | 'is put at' | questions 合理 |
| 277 | 四 | 53_83_p2 C-08 | 'ear ownership' | 'car ownership' | questions 合理 |
| 278 | 四 | 56_64_p1 G-01 | 'Malawi s' | "Malawi's" | questions 合理 |
| 279 | 四 | 56_64_p2 B-02 | 'Seven wars ago.' | 'Seven years ago.' | 合理 |
| 280 | 四 | 56_64_p2 C-06 | 'modem answer' | 'modern answer' | questions 合理 |
| 281 | 四 | 56_64_p2 C-06 | 'I 9th-century' | '19th-century' | questions 合理 |
| 282 | 四 | 56_64_p2 C-09 | 'his approach"metagenomics"' | 'his approach "metagenomics"' | 合理 |
| 283 | 四 | 56_64_p2 E-03 | 'passages." he said.' | "passages,' he said." | 合理 |
| 284 | 四 | 56_64_p2 F-03 | "living thing'-, and Waiter's" | "living things, and Venter's" | 合理 |
| 285 | 四 | 56_64_p2 G-01 | "conn's to" | 'comes to' | 合理 |
| 286 | 四 | 56_64_p2 G-02 | 'used to he thought' | 'used to be thought' | questions 合理 |
| 287 | 四 | 56_64_p2 G-03b | 'viruses phages -' | 'viruses - phages -' | 合理 |
| 288 | 四 | 56_64_p2 H-04 | 'important, gene' | 'important gene' | 合理 |
| 289 | 四 | 56_64_p3 A-02 | "We've had" | "we've had" | 合理 |
| 290 | 四 | 56_64_p3 G-05 | "a cigarette,you're" | "a cigarette, you're" | 合理 |
| 291 | 四 | 56_64_p3 N-02 | 'colour -highlights' | 'colour - highlights' | questions 合理 |
| 292 | 四 | 5_59_p1 C-03 | 'for, instance' | 'for instance' | questions 合理 |
| 293 | 四 | 5_59_p1 C-03 | 'gave US photography' | 'gave us photography' | questions 合理 |
| 294 | 四 | 5_59_p1 G-02 | 'seizing oil the useful' | 'seizing on the useful' | questions 合理 |
| 295 | 四 | 5_59_p1 H-03 | 'frequently pushes by' | 'frequently pushed by' | 合理 |
| 296 | 四 | 5_59_p1 H-03 | "'harness'creativity and" | "'harness' creativity and" | 合理 |
| 297 | 四 | 5_59_p1 I-01 | 'part or the risk-talking' | 'part of the risk-taking' | 合理 |
| 298 | 四 | 5_59_p1 J-01 | 'the unsuccessfull' | 'the unsuccessful' | questions 合理 |
| 299 | 四 | 5_59_p2 C-01 | 'fund on' | 'found on' | questions 合理 |
| 300 | 四 | 5_59_p2 E-03 | 'diers from' | 'differs from' | questions 合理 |
| 301 | 四 | 5_59_p2 E-04 | 'example, coee' | 'example, coffee' | questions 合理 |
| 302 | 四 | 5_59_p2 H-07 | 'coee to' | 'coffee to' | questions 合理 |
| 303 | 四 | 5_59_p2 H-10 | 'system awed' | 'system flawed' | questions 合理 |
| 304 | 四 | 5_59_p2 H-10 | 'scam- and' | 'scam - and' | questions 合理 |
| 305 | 四 | 5_59_p3 A-03 | 'the ease' | 'the case' | questions 合理 |
| 306 | 四 | 5_59_p3 B-01 | 'have frown' | 'have shown' | questions 合理 |
| 307 | 四 | 5_59_p3 D-01 | 'in 19BH' | 'in 1988' | questions 合理 |
| 308 | 四 | 5_59_p3 D-01 | 'cause arid effect' | 'cause and effect' | questions 合理 |
| 309 | 四 | 5_59_p3 G-05 | 'as for as' | 'as far as' | questions 合理 |
| 310 | 四 | 62_44_p1 E-02 | "they' may" | 'they may' | 合理 |
| 311 | 四 | 62_44_p1 E-02 | 'or bandon' | 'or abandon' | questions 合理 |
| 312 | 四 | 62_44_p1 F-03 | 'subjects just 45 –' | 'subjects – just 45 –' | 合理 |
| 313 | 四 | 62_44_p2 D-03 | "chat India's" | "that India's" | 合理 |
| 314 | 四 | 62_44_p2 D-03 | 'Center for\nSustainable' | 'Center for Sustainable' | 合理 |
| 315 | 四 | 62_44_p3 A-03 | '–the planting' | '– the planting' | 合理 |
| 316 | 四 | 62_44_p3 B-06 | 'Pro Merlin' | 'Prof Merlin' | questions 合理 |
| 317 | 四 | 62_44_p3 D-02 | '"elite"shoppers. It' | '"elite" shoppers. It' | 合理 |
| 318 | 四 | 62_44_p3 D-04 | '– away to' | '– a way to' | 合理 |
| 319 | 四 | 62_44_p3 D-04 | 'FRID means' | 'RFID means' | 合理 |
| 320 | 四 | 62_44_p3 E-03 | 'are base on' | 'are based on' | 合理 |
| 321 | 四 | 62_44_p3 E-05 | 'effect (i.e, emotions)' | 'affect (i.e. emotions)' | 合理 |
| 322 | 四 | 65_69_p1 I-03b | "message.' he says" | "message,' he says" | 合理 |
| 323 | 四 | 65_69_p2 B-03 | 'w hat' | 'what' | 合理 |
| 324 | 四 | 65_69_p2 B-04 | 'they w ant a greater' | 'they want a greater' | 合理 |
| 325 | 四 | 65_69_p2 B-04 | 'they w ant greater' | 'they want greater' | 合理 |
| 326 | 四 | 65_69_p2 C-01 | 'and ears' | 'and cars' | 合理 |
| 327 | 四 | 65_69_p2 D-01 | 'raw- materials' | 'raw materials' | questions 合理 |
| 328 | 四 | 65_69_p2 D-01 | 'w ill' | 'will' | questions 合理 |
| 329 | 四 | 65_69_p2 D-03 | 'throw n' | 'thrown' | 合理 |
| 330 | 四 | 65_69_p2 E-05 | 'grow th' | 'growth' | 合理 |
| 331 | 四 | 65_69_p2 F-02 | 'eggs. milk' | 'eggs, milk' | 合理 |
| 332 | 四 | 65_69_p2 G-03 | 'w ill' | 'will' | questions 合理 |
| 333 | 四 | 65_69_p2 I-03 | 'arc never' | 'are never' | questions 合理 |
| 334 | 四 | 65_69_p3 C-01 | 'United Motions' | 'United Nations' | questions 合理 |
| 335 | 四 | 65_69_p3 C-01 | '1967. what' | '1967, what' | questions 合理 |
| 336 | 四 | 65_69_p3 C-01 | "terms'space junk'" | "terms 'space junk'" | 合理 |
| 337 | 四 | 65_69_p3 C-07 | 'ash. those' | 'ash, those' | 合理 |
| 338 | 四 | 65_69_p3 E-01 | 'November 19. 1969. astronauts' | 'November 19, 1969, astronauts' | 合理 |
| 339 | 四 | 65_69_p3 E-01+E-02 | 'probe. Surveyor J. that' | 'probe, Surveyor 3, that' | 合理 |
| 340 | 四 | 65_69_p3 E-02 | 'April 19. 1967.' | 'April 19, 1967.' | 合理 |
| 341 | 四 | 65_69_p3 H-01 | 'probes television' | "probe's television" | questions 合理 |
| 342 | 四 | 65_69_p3 H-01 | 'arm. and' | 'arm, and' | 合理 |
| 343 | 四 | 65_69_p3 H-03 | 'bl Segundo' | 'El Segundo' | questions 合理 |
| 344 | 四 | 65_69_p3 I-03 | 'I or a moment' | 'For a moment' | questions 合理 |
| 345 | 四 | 65_69_p3 J-02 | 'by Rean' | 'by Bean' | 合理 |
| 346 | 四 | 69_40_p2 C-02 | 'While Mountains' | 'White Mountains' | questions 合理 |
| 347 | 四 | 69_40_p2 D-03 | 'Since, the' | 'Since the' | questions 合理 |
| 348 | 四 | 69_40_p2 D-03 | "trees'response to" | "trees' response to" | 合理 |
| 349 | 四 | 69_40_p2 F-01 | 'is no the only' | 'is not the only' | 合理 |
| 350 | 四 | 6_71_p3 F-04 | 'There- are' | 'There are' | 合理 |
| 351 | 四 | 6_71_p3 G-04 | '(patients)explains why' | '(patients) explains why' | 合理 |
| 352 | 四 | 71_1_p1 C-03 | "Gupowder is a'low'" | "Gunpowder is a 'low'" | 合理 |
| 353 | 四 | 71_1_p1 D-04 | 'Undererred, Nobel' | 'Undeterred, Nobel' | 合理 |
| 354 | 四 | 71_1_p1 D-05 | "as'blasting oil'" | "as 'blasting oil'" | questions 合理 |
| 355 | 四 | 71_1_p1 F-01 | 'intro to' | 'nitro to' | questions 合理 |
| 356 | 四 | 71_1_p1 F-01 | 'diatomaccous earth,' | 'diatomaceous earth,' | questions 合理 |
| 357 | 四 | 71_1_p2 B-01 | 'movie watches' | 'movie watchers' | questions 合理 |
| 358 | 四 | 71_1_p2 D-04 | 'give the increasing' | 'given the increasing' | questions 合理 |
| 359 | 四 | 71_1_p2 E-02 | 'the Westren' | 'the Western' | questions 合理 |
| 360 | 四 | 71_1_p3 A-04 | 'into Laurasia(which' | 'into Laurasia (which' | questions 合理 |
| 361 | 四 | 71_1_p3 D-02 | 'convention forces' | 'convection forces' | questions 合理 |
| 362 | 四 | 72_15_p2 E-03 | "mental stages(e.g_ 'you1 re" | "mental states (e.g. 'you're" | 合理 |
| 363 | 四 | 73_5_p1 D-02 | 'building ns size' | 'building of its size' | questions 合理 |
| 364 | 四 | 73_5_p1 F-01 | 'just out' | 'jut out' | questions 合理 |
| 365 | 四 | 73_5_p1 H-01 | 'swings days' | 'swings: days' | questions 合理 |
| 366 | 四 | 73_5_p1 I-02 | '23"C and 25°C.' | '23°C and 25°C,' | questions 合理 |
| 367 | 四 | 73_5_p2 A-03 | 'people In India' | 'people in India' | questions 合理 |
| 368 | 四 | 73_5_p2 C-04 | 'with humans its genes' | 'with humans into its genes' | questions 合理 |
| 369 | 四 | 73_5_p2 D-03 | 'with a an-eaters' | 'with man-eaters' | questions 合理 |
| 370 | 四 | 73_5_p2 E-01 | "a tiger's afraid" | "a tiger's fear" | 合理 |
| 371 | 四 | 73_5_p2 E-07 | 'If he meet a' | 'If he meets a' | questions 合理 |
| 372 | 四 | 73_5_p2 E-07 | 'behind the mind' | 'behind the man' | questions 合理 |
| 373 | 四 | 73_5_p2 F-02 | 'half he size' | 'half the size' | questions 合理 |
| 374 | 四 | 73_5_p3 A-01 | 'Osbeck. a' | 'Osbeck, a' | questions 合理 |
| 375 | 四 | 73_5_p3 F-04 | 'eo-evolve with' | 'co-evolve with' | 合理 |
| 376 | 四 | 73_5_p3 H-02 | 'UK. argues' | 'UK, argues' | questions 合理 |
| 377 | 四 | 73_5_p3 H-02 | "the new' ecosystem" | 'the new ecosystem' | questions 合理 |
| 378 | 四 | 73_5_p3 I-02 | 'titan the' | 'than the' | 合理 |
| 379 | 四 | 73_5_p3 L-02 | "around.' says" | "around,' says" | 合理 |
| 380 | 四 | 73_5_p3 L-06 | 'how- rainforests' | 'how rainforests' | questions 合理 |
| 381 | 四 | 76_43_p1 B-03 | "disability' on" | 'disability on' | 合理 |
| 382 | 四 | 76_43_p1 E-04 | 'Indicates that' | 'indicates that' | questions 合理 |
| 383 | 四 | 76_43_p2 F-04 | 'Goldf inger' | 'Goldfinger' | questions 合理 |
| 384 | 四 | 77_16_p2 C-03 | 'It is. not' | 'It is not' | 合理 |
| 385 | 四 | 77_16_p2 D-04 | 'has to. choose' | 'has to choose' | 合理 |
| 386 | 四 | 78_102_p1 A-03 | 'a cautions' | 'a cautious' | 合理 |
| 387 | 四 | 78_102_p1 B-03 | 'sub -Saharan' | 'sub-Saharan' | questions 合理 |
| 388 | 四 | 78_102_p1 B-03 | 'been third higher' | 'been a third higher' | questions 合理 |
| 389 | 四 | 78_102_p1 C-04 | 'practices.. From' | 'practices. From' | questions 合理 |
| 390 | 四 | 78_102_p1 D-03 | 'such India' | 'such as India' | questions 合理 |
| 391 | 四 | 78_102_p1 E-02 | 'moreover, a' | 'Moreover, a' | 合理 |
| 392 | 四 | 78_102_p1 E-03 | '( them from)' | '(them from)' | 合理 |
| 393 | 四 | 78_102_p1 E-03 | 'ion January' | 'in January' | 合理 |
| 394 | 四 | 79_24_p1 A-04 | 'customary in close businesses' | 'customary to close businesses' | 合理 |
| 395 | 四 | 79_24_p1 B-05 | 'he says sleepiness' | 'He says sleepiness' | questions 合理 |
| 396 | 四 | 79_24_p1 B-06 | '&amp;18 billion' | '$18 billion' | 合理 |
| 397 | 四 | 79_24_p1 D-07 | 'distributor, is' | 'distributor is' | questions 合理 |
| 398 | 四 | 79_24_p1 D-08 | 'offices provides' | 'offices, provides' | questions 合理 |
| 399 | 四 | 79_24_p1 E-05 | 'sleeping, less and working, longer hours' | 'sleeping less and working longer hours' | questions 合理 |
| 400 | 四 | 81_93_p1 B-02 | 'faced -raising' | 'faced - raising' | 合理 |
| 401 | 四 | 81_93_p1 D-05 | 'First -and' | 'First- and' | questions 合理 |
| 402 | 四 | 81_93_p2 A-06 | "ate tugging at the ivy's toots" | "are tugging at the ivy's roots" | questions 合理 |
| 403 | 四 | 81_93_p2 B-02 | 'educa-tion -"massification". in' | 'education - "massification", in' | 合理 |
| 404 | 四 | 81_93_p2 E-06 | 'hinds (as' | 'funds (as' | questions 合理 |
| 405 | 四 | 81_93_p2 F-03 | 'wedded in' | 'wedded to' | 合理 |
| 406 | 四 | 81_93_p2 F-04 | 'Thirty wars' | 'Thirty years' | questions 合理 |
| 407 | 四 | 81_93_p2 F-04 | 'be relics,"says' | 'be relics," says' | questions 合理 |
| 408 | 四 | 81_93_p2 F-08 | 'to contuse' | 'to confuse' | 合理 |
| 409 | 四 | 81_93_p3 H-09 | "or friends'houses" | "or friends' houses" | 合理 |
| 410 | 四 | 82_4_p1 C-01 | 'Amazon, This man' | 'Amazon. This man' | questions 合理 |
| 411 | 四 | 82_4_p2 B-04 | 'there Hows' | 'there flows' | questions 合理 |
| 412 | 四 | 82_4_p2 F-02 | 'atrialed in' | 'trialled in' | 合理 |
| 413 | 四 | 82_4_p2 F-04 | 'as well those' | 'as well as those' | questions 合理 |
| 414 | 四 | 82_4_p2 G-01 | 'Edison first strike' | "Edison's first strike" | 合理 |
| 415 | 四 | 82_4_p2 H-06 | "killer Edison's had hoped" | 'killer Edison had hoped' | 合理 |
| 416 | 四 | 82_4_p3 B-04 | 'salicylates the chemical found in the willow tree became' | 'salicylates, the chemical found in the willow tree, became' | 合理 |
| 417 | 四 | 82_4_p3 E-02 | 'Aspirin is continued' | "Aspirin's continued" | questions 合理 |
| 418 | 四 | 82_4_p3 E-03 | 'the 1070s' | 'the 1970s' | questions 合理 |
| 419 | 四 | 82_4_p3 F-03 | "kill off'certain" | 'kill off certain' | questions 合理 |
| 420 | 四 | 82_4_p3 F-04 | "'wonder drug*" | "'wonder drug'" | 合理 |
| 421 | 四 | 83_95_p1 D-01 | 'began; Pepperberg' | 'began, Pepperberg' | questions 合理 |
| 422 | 四 | 83_95_p3 A-01 | 'history sociologists' | 'history, sociologists' | 合理 |
| 423 | 四 | 83_95_p3 B-02 | 'hunter –gatherer' | 'hunter-gatherer' | questions 合理 |
| 424 | 四 | 84_73_p2 C-14 | 'and\nSwitzerland' | 'and Switzerland' | 合理 |
| 425 | 四 | 84_73_p2 F-40 | "team sports,'says" | "team sports,' says" | 合理 |
| 426 | 四 | 84_73_p2 G-45 | "family's life park" | "family's life: park" | 合理 |
| 427 | 四 | 84_73_p2 G-45 | "to nearbyfriends'" | "to nearby friends'" | 合理 |
| 428 | 四 | 84_73_p3 A-02 | 'concerned From' | 'concerned. From' | questions 合理 |
| 429 | 四 | 84_73_p3 B-03 | 'one given period' | 'one given period.' | at_end 合理 |
| 430 | 四 | 85_12_p1 A-06 | 'useless,"he says.' | 'useless," he says.' | 合理 |
| 431 | 四 | 85_12_p1 C-07 | '"The head,"he' | '"The head," he' | 合理 |
| 432 | 四 | 85_12_p1 D-01 | 'constant "raves"from' | 'constant "raves" from' | 合理 |
| 433 | 四 | 85_12_p1 D-02 | 'travel- ling' | 'travelling' | 合理 |
| 434 | 四 | 85_12_p1 D-06 | 'super- market' | 'supermarket' | questions 合理 |
| 435 | 四 | 85_12_p1 D-06 | 'a palette' | 'a pallet' | questions 合理 |
| 436 | 四 | 85_12_p1 E-02 | 'deck cat the factory' | 'deck at the factory' | questions 合理 |
| 437 | 四 | 85_12_p2 C-04 | 'what ho saw' | 'what he saw' | 合理 |
| 438 | 四 | 85_12_p2 C-06 | 'Then if began' | 'Then it began' | 合理 |
| 439 | 四 | 85_12_p2 C-10 | 'In older to' | 'In order to' | 合理 |
| 440 | 四 | 85_12_p2 D-04 | 'days(force 3-4)' | 'days (force 3-4)' | questions 合理 |
| 441 | 四 | 85_12_p2 D-05 | 'people?walking on' | 'people walking on' | questions 合理 |
| 442 | 四 | 85_12_p2 E-02 | 'troops arc required' | 'troops are required' | questions 合理 |
| 443 | 四 | 85_12_p2 E-06 | 'deck you move' | 'deck: you move' | questions 合理 |
| 444 | 四 | 85_12_p2 E-10 | 'walking they may' | 'walking; they may' | questions 合理 |
| 445 | 四 | 85_12_p3 C-05 | 'calcu lated' | 'calculated' | 合理 |
| 446 | 四 | 85_12_p3 C-05 | 'one- off' | 'one-off' | 合理 |
| 447 | 四 | 88_98_p1 D-04 | 'stacke by' | 'stacked by' | 合理 |
| 448 | 四 | 88_98_p1 H-01 | 'Luapula that crop' | 'Luapula than crop' | questions 合理 |
| 449 | 四 | 88_98_p2 A-02 | 'businesses spend' | 'Businesses spend' | questions 合理 |
| 450 | 四 | 88_98_p2 A-06 | 'study,47% of' | 'study, 47% of' | questions 合理 |
| 451 | 四 | 88_98_p2 E-03 | 'the concept"relative' | 'the concept "relative' | 合理 |
| 452 | 四 | 88_98_p2 E-04 | 'consumers, likelihood' | "consumers' likelihood" | questions 合理 |
| 453 | 四 | 88_98_p2 F-03 | 'before they have' | 'before them have' | questions 合理 |
| 454 | 四 | 91_49_p2 B-03 | 'the crushed' | 'then crushed' | questions 合理 |
| 455 | 四 | 91_49_p2 D-15 | 'timers and' | 'farmers and' | 合理 |
| 456 | 四 | 91_49_p3 A-01 | '20 pars' | '20 years' | questions 合理 |
| 457 | 四 | 91_49_p3 D-05 | 'plaits for' | 'plans for' | 合理 |
| 458 | 四 | 91_49_p3 E-01 | 'Declaration, This document' | 'Declaration. This document' | questions 合理 |
| 459 | 四 | 91_49_p3 F-02 | 'Joss of' | 'loss of' | questions 合理 |
| 460 | 四 | 91_49_p3 F-09 | 'of bow the town' | 'of how the town' | questions 合理 |
| 461 | 四 | 91_49_p3 F-10 | 'molted in' | 'melted in' | 合理 |
| 462 | 四 | 91_49_p3 F-12 | 'wrould be' | 'would be' | questions 合理 |
| 463 | 四 | 92_58_p1 A-06 | 'in dierent' | 'in different' | questions 合理 |
| 464 | 四 | 92_58_p1 B-05 | 'to aeeect' | 'to affect' | questions 合理 |
| 465 | 四 | 92_58_p1 B-05 | '60 dieeerent' | '60 different' | questions 合理 |
| 466 | 四 | 92_58_p2 H-03 | 'is disturbed' | 'is distributed' | 合理 |
| 467 | 四 | 9_81_p2 B-04 | 'from die mainland' | 'from the mainland' | questions 合理 |
| 468 | 四 | 9_81_p2 B-05 | 'ago. there' | 'ago, there' | 合理 |
| 469 | 四 | 9_81_p2 B-08 | 'Eventually. the ocean bloke' | 'Eventually, the ocean broke' | 合理 |
| 470 | 四 | 9_81_p2 B-09 | "world's lew" | "world's few" | 合理 |
| 471 | 四 | 9_81_p2 B-09 | 'naturally -occurring' | 'naturally-occurring' | 合理 |
| 472 | 四 | 9_81_p2 C-01 | 'OF COUKAN' | 'OF COURAN' | 合理 |
| 473 | 四 | 9_81_p2 D-03 | 'resort. transport' | 'resort, transport' | 合理 |
| 474 | 四 | 9_81_p2 D-10 | 'carry. so he careful' | 'carry, so be careful' | 合理 |
| 475 | 四 | 9_81_p2 D-11 | 'tiling is' | 'thing is' | questions 合理 |
| 476 | 四 | 9_81_p2 D-11 | 'some oil the island' | 'some on the island' | questions 合理 |
| 477 | 四 | 9_81_p2 E-01 | 'lias been' | 'has been' | 合理 |
| 478 | 四 | 9_81_p2 E-01 | 'need lo co-exist' | 'need to co-exist' | 合理 |
| 479 | 四 | 9_81_p2 E-01 | 'Island io achieve' | 'Island to achieve' | 合理 |
| 480 | 四 | 9_81_p2 G-11 | 'arc energy' | 'are energy' | 合理 |
| 481 | 四 | 9_81_p2 I-03 | 'contem porary' | 'contemporary' | questions 合理 |
| 482 | 四 | 9_81_p2 I-04 | 'implemen tation' | 'implementation' | questions 合理 |
| 483 | 四 | 9_81_p2 I-04 | 'envi ronmental' | 'environmental' | questions 合理 |
| 484 | 四 | 9_81_p2 I-06 | 'Pridcaux. the' | 'Prideaux, the' | questions 合理 |
| 485 | 四 | 9_81_p2 I-08 | 'com prising' | 'comprising' | questions 合理 |
| 486 | 四 | 9_81_p2 I-08 | 'front nearby' | 'from nearby' | questions 合理 |
| 487 | 四 | 10_78_p2 C-23 | 'species, He found' | 'species. He found' | questions 合理 |
| 488 | 四 | 10_78_p2 E-35 | 'multitasking, Gloria Mark' | 'multitasking. Gloria Mark' | questions 合理 |
| 489 | 四 | 22_90_p2 B-04 | 'hours, Scientists' | 'hours. Scientists' | questions 合理 |
| 490 | 四 | 46_84_p3 M-02 | 'this mouth' | 'this month' | questions 合理 |
| 491 | 四 | 46_84_p3 M-03 | 'come along way' | 'come a long way' | questions 合理 |
| 492 | 四 | 5_59_p3 E-01 | 'rises In temperature' | 'rises in temperature' | questions 合理 |
| 493 | 四 | 71_1_p1 B-04 | 'five degress' | 'five degrees' | questions 合理 |
| 494 | 四 | 71_1_p1 C-04 | 'instrantancous shock' | 'instantaneous shock' | questions 合理 |
| 495 | 四 | 73_5_p3 D-01 | 'Hookers environmental' | "Hooker's environmental" | questions 合理 |
| 496 | 四 | 81_93_p2 D-01 | 'is globalisation..' | 'is globalisation.' | questions 合理 |
| 497 | 四 | 10_78_p2 C-27 | 'patients " heads' | "patients' heads" | 合理 |
| 498 | 四 | 10_78_p3 P-02 | 'according Roger Coleman' | 'according to Roger Coleman' | 合理 |
| 499 | 四 | 11_103_p1 F-07 | "at\nMars'" | "at Mars'" | 合理 |
| 500 | 四 | 11_103_p2 A-01 | 'even that going to be' | 'even that is going to be' | 合理 |
| 501 | 四 | 11_103_p2 C-06+C-07 | 'from\nSpitsbergen. It would stop the ice' | "from Spitsbergen. 'It would stop the ice" | 合理 |
| 502 | 四 | 11_103_p2 C-07 | "northwards' he says" | "northwards,' he says" | 合理 |
| 503 | 四 | 11_103_p2 E-02 | 'allow US to continue' | 'allow us to continue' | questions 合理 |
| 504 | 四 | 11_103_p2 E-07 | 'Dr Dan hunt' | 'Dr Dan Hunt' | 合理 |
| 505 | 四 | 13_6_p3 D-03 | 'form -found' | 'form - found' | questions 合理 |
| 506 | 四 | 14_23_p1 D-01 | "of course don't" | "of course, don't" | 合理 |
| 507 | 四 | 14_23_p2 I-03 | 'a fascinating game' | 'a fascinating game.' | at_end 合理 |
| 508 | 四 | 18_53_p1 D-01 | "named'Board of" | "named 'Board of" | 合理 |
| 509 | 四 | 18_53_p2 B-03 | 'a recent report' | 'a recent report.' | at_end 合理 |
| 510 | 四 | 18_53_p2 C-04 | "was,'less intrusive" | "was 'less intrusive" | 合理 |
| 511 | 四 | 18_53_p2 D-02 | "schools,'their report" | "schools,' their report" | 合理 |
| 512 | 四 | 18_53_p2 D-03 | 'review of assessment' | 'review of assessment.' | at_end 合理 |
| 513 | 四 | 18_53_p2 F-05 | 'Teachers. There are schools that start' | "Teachers. 'There are schools that start" | 合理 |
| 514 | 四 | 18_53_p2 F-06+F-07 | 'ridiculous/ he said. There are other schools' | "ridiculous,' he said. 'There are other schools" | 合理 |
| 515 | 四 | 18_53_p2 G-03 | 'criticism. The idea that children' | "criticism. 'The idea that children" | questions 合理 |
| 516 | 四 | 18_53_p2 G-03 | 'accepts/a spokesman' | "accepts,' a spokesman" | questions 合理 |
| 517 | 四 | 18_53_p2 G-04 | 'said. The reality is that' | "said. 'The reality is that" | questions 合理 |
| 518 | 四 | 22_90_p3 E-03 | "individuals'potential, Once again" | "individuals' potential. Once again" | 合理 |
| 519 | 四 | 22_90_p3 F-06 | 'stages 2 and 3(identifying' | 'stages 2 and 3 (identifying' | questions 合理 |
| 520 | 四 | 22_90_p3 G-01 | 'Tellam Industries agrees' | 'Tellam Industries, agrees' | questions 合理 |
| 521 | 四 | 23_46_p1 D-02 | 'Green Peace is' | 'Greenpeace is' | questions 合理 |
| 522 | 四 | 24_56_p2 F-01 | 'maxi misers' | 'maximizers' | 合理 |
| 523 | 四 | 24_56_p2 I-01 | 'subscrip tions' | 'subscriptions' | 合理 |
| 524 | 四 | 24_56_p3 C-07 | 'preventative Qualities' | 'preventative qualities' | questions 合理 |
| 525 | 四 | 24_56_p3 F-04 | 'volunteers, is exposed' | 'volunteers is exposed' | questions 合理 |
| 526 | 四 | 24_56_p3 G-03 | 'Phase 11(b)' | 'Phase II(b)' | 合理 |
| 527 | 四 | 27_33_p1 E-02 | 'Nessie, In 2007' | 'Nessie. In 2007' | questions 合理 |
| 528 | 四 | 27_33_p2 C-04 | 'and failure."' | "and failure.'" | 合理 |
| 529 | 四 | 27_33_p3 B-03 | 'management, However,' | 'management. However,' | questions 合理 |
| 530 | 四 | 29_63_p3 H-01 | 'attitude,"as Gordon' | 'attitude," as Gordon' | questions 合理 |
| 531 | 四 | 32_20_p1 B-03 | 'work; However,' | 'work. However,' | questions 合理 |
| 532 | 四 | 32_20_p3 E-06 | 'low-insulin- secreting' | 'low-insulin-secreting' | 合理 |
| 533 | 四 | 32_20_p3 E-08 | 'high- insulin-secretors' | 'high-insulin-secretors' | 合理 |
| 534 | 四 | 38_22_p3 A-03 | 'infiuence on' | 'influence on' | 合理 |
| 535 | 四 | 40_75_p1 B-05 | 'and ho believed' | 'and he believed' | questions 合理 |
| 536 | 四 | 40_75_p1 D-01 | 'Bom in 1773' | 'Born in 1773' | questions 合理 |
| 537 | 四 | 40_75_p2 C-02 | 'Current(ACC), that' | 'Current (ACC), that' | questions 合理 |
| 538 | 四 | 40_75_p2 D-02 | 'allow Astronauts' | 'allow astronauts' | 合理 |
| 539 | 四 | 40_75_p2 F-07 | 'hemi-sphere, it' | 'hemisphere, it' | questions 合理 |
| 540 | 四 | 40_75_p3 C-04 | 'or may be you' | 'or maybe you' | questions 合理 |
| 541 | 四 | 44_29_p2 B-01 | 'plant –water lettuce' | 'plant – water lettuce' | questions 合理 |
| 542 | 四 | 46_84_p2 E-03 | 'fraternity, shell saw' | 'fraternity, Shell saw' | 合理 |
| 543 | 四 | 46_84_p2 G-04 | 'Manchester, More are' | 'Manchester. More are' | 合理 |
| 544 | 四 | 46_84_p2 H-02 | 'male Students' | 'male students' | questions 合理 |
| 545 | 四 | 46_84_p3 K-08 | 'not aide to discover' | 'not able to discover' | questions 合理 |
| 546 | 四 | 48_21_p1 C-02 | 'is a head called' | 'is a bead called' | questions 合理 |
| 547 | 四 | 48_21_p1 G-01 | 'shape, Colour,' | 'shape, colour,' | questions 合理 |
| 548 | 四 | 50_30_p1 B-02 | 'to their truck' | 'to their trunk' | questions 合理 |
| 549 | 四 | 50_30_p1 C-01 | 'Pines trees' | 'Pine trees' | 合理 |
| 550 | 四 | 50_30_p1 D-02 | 'introduced in to the' | 'introduced into the' | 合理 |
| 551 | 四 | 50_30_p1 I-04 | 'coring toll' | 'coring tool' | 合理 |
| 552 | 四 | 50_30_p2 A-01 | 'who discover and documented' | 'who discovered and documented' | questions 合理 |
| 553 | 四 | 50_30_p2 A-02 | 'the classical condition.' | 'the classical conditioning.' | 合理 |
| 554 | 四 | 50_30_p2 A-03 | 'stimulus(signal) with' | 'stimulus (signal) with' | 合理 |
| 555 | 追加 | 50_30_p2 F-02 | 'seed catching behavior' | 'seed caching behavior' | questions 合理 |
| 556 | 四 | 50_30_p2 F-02 | "Clark's nutcracker(Nucifraga" | "Clark's nutcracker (Nucifraga" | 合理 |
| 557 | 追加 | 50_30_p2 F-03 | 'specialist, catching' | 'specialist, caching' | questions 合理 |
| 558 | 四 | 53_83_p2 G-01 | 'regularly -to and from' | 'regularly - to and from' | questions 合理 |
| 559 | 四 | 53_83_p3 C-03 | 'stoves -which' | 'stoves - which' | questions 合理 |
| 560 | 四 | 53_83_p3 C-03 | 'cooking -Jhunjhunwala' | 'cooking - Jhunjhunwala' | questions 合理 |
| 561 | 四 | 53_83_p3 D-08 | 'markets -which' | 'markets - which' | questions 合理 |
| 562 | 四 | 56_64_p3 H-04 | 'you eat- the likes' | 'you eat - the likes' | questions 合理 |
| 563 | 四 | 5_59_p1 C-02 | 'gave US cornflakes' | 'gave us cornflakes' | questions 合理 |
| 564 | 四 | 62_44_p1 A-03 | "translates to'unseen'" | "translates to 'unseen'" | 合理 |
| 565 | 四 | 62_44_p2 H-04 | '"catch-up," courses' | '"catch-up" courses' | 合理 |
| 566 | 四 | 62_44_p3 B-08 | 'high—turnover items' | 'high-turnover items' | 合理 |
| 567 | 四 | 62_44_p3 F-01 | 'self – esteem' | 'self-esteem' | questions 合理 |
| 568 | 四 | 65_69_p1 G-01 | "called'chunking', in" | "called 'chunking', in" | questions 合理 |
| 569 | 四 | 65_69_p2 A-01 | 'stablize at' | 'stabilize at' | questions 合理 |
| 570 | 四 | 65_69_p2 C-02 | 'results m decreasing' | 'results in decreasing' | questions 合理 |
| 571 | 四 | 65_69_p2 G-01 | 'In the long run. tissue-cloning' | 'In the long run, tissue-cloning' | 合理 |
| 572 | 四 | 65_69_p2 I-02 | 'in two. and pilot' | 'in two, and pilot' | 合理 |
| 573 | 四 | 65_69_p3 B-03 | 'profit- seeking' | 'profit-seeking' | questions 合理 |
| 574 | 四 | 69_40_p2 A-06 | 'such, environmental' | 'such environmental' | questions 合理 |
| 575 | 四 | 69_40_p2 G-03 | "California's the White Mountains" | "California's White Mountains" | questions 合理 |
| 576 | 四 | 69_40_p2 G-06 | 'Owens Valley, are higher' | 'Owens Valley are higher' | questions 合理 |
| 577 | 四 | 6_71_p1 F-04 | 'ended- it had' | 'ended - it had' | questions 合理 |
| 578 | 四 | 6_71_p3 F-02 | 'universals. you get' | 'universals, you get' | 合理 |
| 579 | 四 | 6_71_p3 F-02 | "outliers.' says" | "outliers,' says" | 合理 |
| 580 | 四 | 71_1_p1 E-01 | "'diatomaccous earth'" | "'diatomaceous earth'" | questions 合理 |
| 581 | 四 | 71_1_p1 E-05 | "name of'dynamite'" | "name of 'dynamite'" | questions 合理 |
| 582 | 四 | 71_1_p2 E-04 | "such as, 'Let's" | "such as 'Let's" | 合理 |
| 583 | 四 | 71_1_p2 F-04 | "intended('old'). I" | "intended ('old'). I" | 合理 |
| 584 | 四 | 71_1_p2 F-05 | "translation of'old'" | "translation of 'old'" | questions 合理 |
| 585 | 四 | 71_1_p2 G-05 | 'language(English) are' | 'language (English) are' | questions 合理 |
| 586 | 四 | 72_15_p2 A-05 | 'of mind(TOM)' | 'of mind (TOM)' | 合理 |
| 587 | 四 | 72_15_p2 H-02 | "use'simulation'. This" | "use 'simulation'. This" | 合理 |
| 588 | 四 | 73_5_p1 D-03 | 'air- conditioning' | 'air-conditioning' | questions 合理 |
| 589 | 四 | 73_5_p1 E-03 | 'forty- eight' | 'forty-eight' | questions 合理 |
| 590 | 四 | 73_5_p2 B-04 | '60.000 in' | '60,000 in' | 合理 |
| 591 | 四 | 73_5_p2 D-01 | '1950s. we have' | '1950s, we have' | 合理 |
| 592 | 四 | 73_5_p2 F-04 | 'This, however appears' | 'This, however, appears' | 合理 |
| 593 | 四 | 73_5_p3 D-02 | 'the islands endemic' | "the island's endemic" | questions 合理 |
| 594 | 四 | 73_5_p3 F-01 | "forest'that has" | "forest' that has" | questions 合理 |
| 595 | 四 | 76_43_p2 A-03 | 'the othic cathedral-builders' | 'the Gothic cathedral-builders' | questions 合理 |
| 596 | 四 | 76_43_p2 A-05 | 'Anglo- Saxons' | 'Anglo-Saxons' | questions 合理 |
| 597 | 四 | 76_43_p2 B-01 | 'the /Early Modern' | 'the Early Modern' | questions 合理 |
| 598 | 四 | 76_43_p2 D-02 | '/But during' | 'But during' | 合理 |
| 599 | 四 | 76_43_p2 G-03 | 'British -were' | 'British - were' | questions 合理 |
| 600 | 四 | 76_43_p2 H-02 | 'high- rise' | 'high-rise' | 合理 |
| 601 | 四 | 76_43_p3 C-05 | 'in\nPsychology' | 'in Psychology' | 合理 |
| 602 | 四 | 77_16_p2 D-06 | "'Attentive'Computing Systems, have" | "'Attentive' Computing Systems have" | 合理 |
| 603 | 四 | 77_16_p2 G-01 | '(Bestcom-ET)digs a' | '(Bestcom-ET) digs a' | questions 合理 |
| 604 | 四 | 78_102_p1 F-02 | '$ 200 million' | '$200 million' | questions 合理 |
| 605 | 四 | 78_102_p1 F-03 | 'right, " he argues' | 'right," he argues' | 合理 |
| 606 | 四 | 78_102_p2 D-04 | 'reassurance a fact' | 'reassurance, a fact' | questions 合理 |
| 607 | 四 | 78_102_p2 D-04 | 'promote Childhood' | 'promote. Childhood' | questions 合理 |
| 608 | 四 | 78_102_p2 D-04 | "McDonald's', like" | "McDonald's, like" | 合理 |
| 609 | 四 | 78_102_p2 G-05 | 'average-sized swimming pools' | 'average-sized swimming pools.' | at_end 合理 |
| 610 | 四 | 78_102_p3 A-04 | 'first place giving' | 'first place, giving' | 合理 |
| 611 | 四 | 78_102_p3 E-04 | 'electricity" to deliver' | 'electricity to deliver' | 合理 |
| 612 | 四 | 78_102_p3 F-02 | 'Department of Defense may' | 'Department of Defense, may' | questions 合理 |
| 613 | 四 | 78_102_p3 H-02 | 'involved- or' | 'involved - or' | 合理 |
| 614 | 四 | 79_24_p1 B-01 | '500 hours -subtracting' | '500 hours - subtracting' | 合理 |
| 615 | 四 | 79_24_p1 E-03 | 'winking out of their bonus' | 'working out of their homes' | questions 合理 |
| 616 | 四 | 81_93_p2 B-04 | 'l975 and' | '1975 and' | 合理 |
| 617 | 四 | 81_93_p2 D-06 | 'or 1 % of' | 'or 1% of' | 合理 |
| 618 | 四 | 81_93_p2 E-02 | 'it. does not' | 'it does not' | 合理 |
| 619 | 四 | 81_93_p2 F-01 | 'if anything can' | 'if anything, can' | 合理 |
| 620 | 四 | 81_93_p3 B-03 | "any'leisure' until" | "any 'leisure' until" | 合理 |
| 621 | 四 | 82_4_p3 H-03 | 'Department of Health.' | 'Department of Health,' | 合理 |
| 622 | 四 | 83_95_p1 G-06 | 'What\'ssame?" she' | 'What\'s same?" she' | 合理 |
| 623 | 四 | 83_95_p1 H-05 | 'clearly!""Don\'t be' | 'clearly!" "Don\'t be' | 合理 |
| 624 | 四 | 84_73_p1 A-07 | 'now –dawning' | 'now dawning' | 合理 |
| 625 | 四 | 84_73_p1 E-04 | 'hard, put to survive' | 'hard put to survive' | questions 合理 |
| 626 | 四 | 84_73_p2 D-27 | '"He added that' | 'He added that' | 合理 |
| 627 | 四 | 84_73_p2 E-31 | 'Jackson, she shouts' | "Jackson,' she shouts" | 合理 |
| 628 | 四 | 85_12_p1 B-06 | 'months ,almost' | 'months, almost' | 合理 |
| 629 | 四 | 85_12_p1 B-07 | "company's, sales" | "company's sales" | 合理 |
| 630 | 四 | 85_12_p1 C-03 | 'friendly One of' | 'friendly. One of' | questions 合理 |
| 631 | 四 | 85_12_p1 D-04 | 'see Woolworths,"Tom' | 'see Woolworths," Tom' | 合理 |
| 632 | 四 | 85_12_p1 D-07 | 'the moon,"says' | 'the moon," says' | 合理 |
| 633 | 四 | 85_12_p3 B-02 | 'peas ant farmers' | 'peasant farmers' | 合理 |
| 634 | 四 | 85_12_p3 D-05 | 'caboclos: bacuri(Platonia' | 'caboclos: bacuri (Platonia' | 合理 |
| 635 | 四 | 85_12_p3 D-05 | 'Endop- leura' | 'Endopleura' | 合理 |
| 636 | 四 | 85_12_p3 I-04 | 'peas ant unions' | 'peasant unions' | questions 合理 |
| 637 | 四 | 85_12_p3 I-04 | 'the cabo\xadclos' | 'the caboclos' | questions 合理 |
| 638 | 四 | 91_49_p2 C-06 | 'in the Americans' | 'in the Americas' | questions 合理 |
| 639 | 四 | 91_49_p3 D-03 | 'Non- Government Organisation(NGOs)' | 'Non-Government Organisation (NGOs)' | 合理 |
| 640 | 四 | 9_81_p1 C-04 | 'peopled way' | "people's way" | questions 合理 |
| 641 | 四 | 9_81_p2 B-09 | 'islands. Conran Cove' | 'islands. Couran Cove' | 合理 |
| 642 | 四 | 9_81_p3 A-01 | 'to the out' | 'to die out' | 合理 |
| 643 | 四 | 81_93_p2 A-02 | 'University of bologna' | 'University of Bologna' | questions 合理 |


## 附录F：逐句人工审核覆盖

下列ID均逐句阅读translation、structure、difficult_points、expressions和拆合上下文；无明确新增问题的合并列出。异常ID在N3逐项给问题与建议，标签覆盖另见N4/G。轮间重复ID分别按当轮结果审核，不把630解释为630个互不重叠的新原句。删除ID对应合并已在正文列出。


### 第二轮：97个变化后句子对象


| passage_id | 已审全部ID | 例外 |
|---|---|---|
| ielts18_test4_p2 | F-03、F-03b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts19_test4_p3 | H-02、H-02b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts20_test2_p3 | I-51、I-51b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts20_test4_p2 | B-11、B-11b、C-16、C-16b、C-16c、D-19、D-19b、D-19c、E-23、E-23b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts4_test1_p3 | I-31、I-31b、I-31c | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts4_test2_p1 | E-27、E-27b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts4_test2_p2 | B-06、B-06b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts4_test2_p3 | A-07、A-07b、A-07c、C-19、C-19b、C-20、C-20b、E-29、E-29b、G-37、G-37b、G-37c、H-38、H-38b、H-43、H-43b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts4_test4_p1 | C-14、C-15、I-45、I-45b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts5_test2_p2 | A-02、A-02b、A-05、A-05b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts5_test4_p2 | J-45、J-45b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts6_test2_p1 | A-01、A-01b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts7_test1_p3 | C-11、C-11b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts7_test2_p1 | I-44、I-44b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts7_test3_p1 | D-03、D-03b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts8_test3_p1 | I-03、I-03b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts8_test3_p3 | A-03、A-03b | N3: A-03b |
| reading_jijing_16_test_97_p2 | G-44、G-44b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_22_test_90_p2 | G-24、G-24b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_26_test_72_p1 | G-11、G-11b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_27_test_33_p1 | B-09 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_29_test_63_p1 | C-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_38_test_22_p3 | G-07、G-07b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_5_test_59_p1 | A-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_65_test_69_p2 | H-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_69_test_40_p2 | E-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_71_test_1_p2 | B-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_72_test_15_p2 | F-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_73_test_5_p1 | H-02、H-02b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_73_test_5_p3 | D-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_76_test_43_p3 | A-07 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_78_test_102_p1 | A-01、C-01、D-01、G-01、H-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_83_test_95_p1 | C-03、C-03b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_92_test_58_p2 | A-01、B-01、C-01、D-01、E-01、F-01、H-01、I-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_9_test_81_p2 | A-02、B-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |

### 第三轮：17个变化后句子对象


| passage_id | 已审全部ID | 例外 |
|---|---|---|
| reading_jijing_29_test_63_p1 | B-03、B-05、B-06、C-01、C-02、E-01、E-02、E-03、G-04、G-05 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_29_test_63_p3 | A-02、A-03、F-02、F-04、G-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_83_test_95_p2 | D-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_84_test_73_p2 | C-17 | 未发现本轮明确新增语言错误；既存/保留项见正文 |

### 第四轮及追加：630个变化后句子对象


| passage_id | 已审全部ID | 例外 |
|---|---|---|
| ielts10_test1_p3 | E-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts14_test1_p1 | N-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts14_test3_p1 | F-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts17_test3_p2 | F-09 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts4_test4_p1 | A-04、B-10 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| ielts6_test4_p1 | A-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_10_test_78_p1 | C-18、J-56 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_10_test_78_p2 | A-12、B-13、B-17、B-19、C-23、C-23b、C-24、C-26、C-27、C-28、D-30、D-32、D-34、E-35、E-35b、E-41、E-46、F-49 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_10_test_78_p3 | B-01、F-01、H-03、P-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_11_test_103_p1 | A-04、C-09、E-06、F-07、H-01、H-05 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_11_test_103_p2 | A-01、B-02、C-06、C-07、D-06、E-02、E-04、E-07 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_11_test_103_p3 | B-01、C-02、E-04、H-01、I-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_13_test_6_p1 | B-03、D-02、G-02、I-02、J-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_13_test_6_p2 | C-14、D-16、D-20、H-40 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_13_test_6_p3 | D-03、E-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_14_test_23_p1 | D-01、G-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_14_test_23_p2 | B-02、B-03、D-01、H-02、I-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_14_test_23_p3 | B-04、C-02、D-06、G-01、G-04、G-04b、H-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_16_test_97_p1 | B-08 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_16_test_97_p2 | B-08、E-34 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_16_test_97_p3 | B-04、C-03、F-01、G-01、G-01b、I-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_18_test_53_p1 | C-02、D-01、E-04、E-07、G-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_18_test_53_p2 | B-03、C-04、D-02、D-03、F-02、F-05、F-06、F-07、G-03、G-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_22_test_90_p1 | A-02、B-03、C-04、C-07、D-04、D-09 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_22_test_90_p2 | A-01、A-01b、B-04、B-04b、B-05、D-10、D-12、E-15、G-20 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_22_test_90_p3 | B-02、E-03、E-03b、F-06、G-01、H-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_23_test_46_p1 | A-05、D-02、E-07 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_24_test_56_p1 | A-05、D-01、D-03、E-01、E-02、E-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_24_test_56_p2 | C-02、C-04、F-01、G-02、G-03、I-01 | N3: G-03 |
| reading_jijing_24_test_56_p3 | C-02、C-07、D-03、E-04、F-03、F-04、G-02、G-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_26_test_72_p1 | A-06、C-01、D-06、E-01、G-10、G-12、I-01、K-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_27_test_33_p1 | A-01、A-03、A-04、B-04、B-06、B-08、C-01、C-03、C-03b、C-03c、D-01、D-01b、D-01c、D-02、E-02、E-02b | N3: D-01b |
| reading_jijing_27_test_33_p2 | A-03、C-04、C-06、E-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_27_test_33_p3 | B-03、B-03b、D-09 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_29_test_63_p1 | G-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_29_test_63_p2 | C-06、D-03、D-03b、E-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_29_test_63_p3 | A-04、C-03、H-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_32_test_20_p1 | A-01、B-03、B-03b、B-04、C-01、F-05、F-05b、F-06、G-01、H-04 | N3: B-03 |
| reading_jijing_32_test_20_p2 | G-01、N-04、O-07 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_32_test_20_p3 | A-06、E-06、E-08、G-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_38_test_22_p1 | B-02、I-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_38_test_22_p3 | A-03、B-01、B-02、C-04、C-08 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_40_test_75_p1 | A-01、A-02、A-03、B-03、B-05、B-06、D-01、D-03、E-08、F-05、G-01、G-01b、G-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_40_test_75_p2 | B-04、C-02、C-04、C-05、D-02、E-03、F-01、F-03、F-04、F-07 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_40_test_75_p3 | A-02、A-03、A-04、B-04、B-05、B-06、C-04、C-05、C-06、D-03、D-04、D-08、E-03、F-01、F-02、F-03、F-04、F-05、G-01、H-02、H-04、H-05、H-07、H-08、I-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_44_test_29_p1 | E-02、G-07、I-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_44_test_29_p2 | B-01、E-03、G-02、G-04、G-05、H-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_44_test_29_p3 | B-01、B-05、E-02、K-01、P-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_46_test_84_p1 | A-02、B-01、D-06、D-09、E-01、E-02 | N3: D-06 |
| reading_jijing_46_test_84_p2 | A-02、C-02、E-03、G-01、G-04、G-04b、H-02、H-03、H-03b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_46_test_84_p3 | K-08、M-02、M-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_48_test_21_p1 | B-02、C-02、F-05、G-01、G-05、H-05 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_48_test_21_p2 | A-02、F-04、F-06 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_48_test_21_p3 | A-03、B-03、C-01、C-04、D-03、F-01、F-04、G-01、G-03、H-01、H-02、I-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_50_test_30_p1 | B-02、C-01、D-02、E-02、I-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_50_test_30_p2 | A-01、A-02、A-03、D-01、D-04、E-01、F-02、F-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_50_test_30_p3 | B-03、C-04、D-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_53_test_83_p1 | B-04、C-01、D-06 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_53_test_83_p2 | C-07、C-08、G-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_53_test_83_p3 | C-03、D-04、D-08 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_56_test_64_p1 | G-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_56_test_64_p2 | B-02、C-01、C-06、C-09、E-03、F-03、G-01、G-02、G-03b、H-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_56_test_64_p3 | A-02、G-05、H-04、N-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_5_test_59_p1 | C-02、C-03、G-02、H-03、I-01、J-01 | N3: I-01 |
| reading_jijing_5_test_59_p2 | C-01、E-03、E-04、H-07、H-10 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_5_test_59_p3 | A-03、B-01、D-01、E-01、F-01、G-05 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_62_test_44_p1 | A-03、B-04、E-02、F-03、F-04、G-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_62_test_44_p2 | D-03、H-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_62_test_44_p3 | A-01、A-03、B-06、B-08、C-05、D-02、D-04、E-03、E-05、F-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_65_test_69_p1 | G-01、I-03b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_65_test_69_p2 | A-01、B-03、B-04、C-01、C-02、D-01、D-03、E-05、F-01、F-02、G-01、G-03、I-02、I-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_65_test_69_p3 | B-03、C-01、C-07、E-01、H-01、H-03、I-03、I-05、J-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_69_test_40_p2 | A-03、A-06、C-02、D-03、F-01、G-01、G-03、G-06 | N3: F-01 |
| reading_jijing_6_test_71_p1 | F-04、H-03、I-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_6_test_71_p3 | F-02、F-04、G-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_71_test_1_p1 | B-04、C-03、C-04、D-04、D-05、E-01、E-05、F-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_71_test_1_p2 | B-01、D-04、E-01、E-02、E-04、F-04、F-05、G-05、H-05 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_71_test_1_p3 | A-04、D-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_72_test_15_p2 | A-05、E-03、H-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_73_test_5_p1 | D-02、D-03、E-03、F-01、H-01、I-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_73_test_5_p2 | A-03、B-04、C-04、D-01、D-03、E-01、E-07、F-02、F-04、F-05 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_73_test_5_p3 | A-01、D-01、D-02、F-01、F-04、H-02、I-02、L-02、L-06 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_76_test_43_p1 | B-01、B-03、E-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_76_test_43_p2 | A-03、A-05、B-01、D-02、F-04、G-03、H-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_76_test_43_p3 | C-05 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_77_test_16_p2 | C-03、D-04、D-06、G-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_78_test_102_p1 | A-03、B-03、C-02、C-04、D-03、E-02、E-03、F-02、F-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_78_test_102_p2 | D-04、D-04b、G-05 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_78_test_102_p3 | A-04、E-04、F-02、H-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_79_test_24_p1 | A-04、B-01、B-05、B-06、D-07、D-08、E-03、E-05 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_81_test_93_p1 | B-02、D-05 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_81_test_93_p2 | A-02、A-06、B-02、B-04、D-01、D-06、E-02、E-06、F-01、F-03、F-04、F-08 | N3: F-01 |
| reading_jijing_81_test_93_p3 | B-03、H-09 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_82_test_4_p1 | C-01、C-01b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_82_test_4_p2 | B-04、F-02、F-04、F-06、G-01、H-06 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_82_test_4_p3 | B-04、E-02、E-03、F-03、F-04、H-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_83_test_95_p1 | D-01、G-06、H-05、H-05b | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_83_test_95_p2 | C-04、D-01、D-03、H-02、H-06 | N3: D-01 |
| reading_jijing_83_test_95_p3 | A-01、B-02 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_84_test_73_p1 | A-07、E-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_84_test_73_p2 | B-09、C-14、D-27、E-31、F-40、G-45 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_84_test_73_p3 | A-02、B-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_85_test_12_p1 | A-06、B-06、B-07、C-03、C-03b、C-07、D-01、D-02、D-04、D-06、D-07、E-02、G-06 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_85_test_12_p2 | C-04、C-06、C-10、D-04、D-05、E-02、E-03、E-06、E-10 | N3: C-10 |
| reading_jijing_85_test_12_p3 | B-02、C-05、D-05、I-04 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_88_test_98_p1 | D-04、H-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_88_test_98_p2 | A-02、A-06、C-03、E-03、E-04、F-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_88_test_98_p3 | F-02、G-10 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_91_test_49_p2 | B-03、C-06、D-15 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_91_test_49_p3 | A-01、D-03、D-05、E-01、E-01b、F-02、F-05、F-09、F-10、F-12 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_92_test_58_p1 | A-06、B-05 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_92_test_58_p2 | F-03、H-03、I-01 | N3: H-03 |
| reading_jijing_92_test_58_p3 | B-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_9_test_81_p1 | C-04、G-03 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_9_test_81_p2 | B-04、B-05、B-08、B-09、C-01、D-03、D-10、D-11、E-01、G-11、I-03、I-04、I-06、I-08 | 未发现本轮明确新增语言错误；既存/保留项见正文 |
| reading_jijing_9_test_81_p3 | A-01 | 未发现本轮明确新增语言错误；既存/保留项见正文 |


## 附录G：72个role的前后映射及真实例子

旧标签全部来自f9aebc7 resolver；旧新函数对同一份最终语料对比。各role最多列2个真实成分实例，单例列全部；run_on_passive_clause最终0例，列第三轮仅有2例。当前71role/403处、38个单例；第三轮72role/407处。新concept/camp变动随标签一并检查。


| role | 旧标签/概念 | 新标签/概念 | 第三轮/当前次数 | 所审实例 | 独立判定 |
|---|---|---|---|---|---|
| accompanying_participle_clause | 状语从句/adverbial_clause | 分词短语/participial_phrase | 3 / 3 | reading_jijing_14_test_23_p2 A-02: eyeing their 16 pieces each as the first move is played<br>reading_jijing_76_test_43_p1 C-03: often experiencing irritability, perpetual tiredness and listlessness | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| adjective_complement_clause | 状语从句/adverbial_clause | 名词性从句/noun_clause | 2 / 2 | reading_jijing_53_test_83_p1 B-03: that growth will be strong in Kenya, and later across Africa<br>reading_jijing_73_test_5_p2 E-10: that it can tackle its prey | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| alternative_question_clause | 状语从句/adverbial_clause | 疑问句/main_clause | 1 / 1 | reading_jijing_40_test_75_p2 B-03: Is this because the world seems a little smaller these days | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| alternative_reason_clause | 状语从句/adverbial_clause | 原因状语从句/adverbial_clause | 1 / 1 | reading_jijing_62_test_44_p3 F-02: either because the celeb epitomizes success or because they seem familiar and so make the product seem "safe" | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| alternative_result_clause | 状语从句/adverbial_clause | 结果状语从句/adverbial_clause | 1 / 1 | reading_jijing_48_test_21_p1 E-05: or the oyster may directly die from such numerous complications as diseases | 应修：见N4；单例全审 |
| bare_infinitive_clause | 状语从句/adverbial_clause | 不定式/infinitive_phrase | 6 / 6 | ielts11_test4_p2 B-01: start with dialogue<br>ielts12_test7_p3 C-02: predict the arrival of our favourite part | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| causal_clause | 状语从句/adverbial_clause | 原因状语从句/adverbial_clause | 7 / 7 | ielts13_test4_p2 A-03: Since soil grows 95% of our food, and sustains human life in other more surprising ways<br>ielts13_test4_p3 A-01: because it is self-evidently good | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| clause | 状语从句/adverbial_clause | 分句/main_clause | 30 / 30 | ielts12_test7_p3 D-07: we are denied the pattern we expect<br>ielts13_test1_p3 B-02: we can break this process down into computer code | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| comma_splice_clause | 状语从句/adverbial_clause | 主句/main_clause | 1 / 1 | reading_jijing_50_test_30_p2 F-03: the Mexican jay will also cache food | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| comma_spliced_clause | 状语从句/adverbial_clause | 主句/main_clause | 1 / 1 | reading_jijing_11_test_103_p2 A-02: the majority are having great difficulty even stemming the rate of increase, let alone reversing | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| complement_clause | 状语从句/adverbial_clause | 名词性从句/noun_clause | 22 / 22 | ielts14_test2_p2 I-04: we changed our outlook<br>ielts17_test1_p1 A-04: that the overground railway stations formed a ring around the City | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| counterfactual_condition_clause | 状语从句/adverbial_clause | 条件状语从句/adverbial_clause | 1 / 1 | reading_jijing_78_test_102_p1 B-03: If these collapses had not occurred | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| elliptical_clause | 状语从句/adverbial_clause | 省略结构/generic_phrase | 36 / 36 | ielts10_test2_p1 D-08: Unlikely<br>ielts10_test3_p3 H-01: successful or not | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| elliptical_comment_clause | 状语从句/adverbial_clause | 省略结构/generic_phrase | 1 / 1 | reading_jijing_44_test_29_p2 E-04: hardly surprising | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| elliptical_comparative_clause | 状语从句/adverbial_clause | 比较状语从句/adverbial_clause | 1 / 1 | ielts13_test3_p3 E-03: As today | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| elliptical_concessive_clause | 状语从句/adverbial_clause | 让步状语从句/adverbial_clause | 3 / 3 | ielts6_test2_p3 B-02: if not advanced<br>ielts6_test2_p3 G-04: while different | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| elliptical_condition_clause | 状语从句/adverbial_clause | 条件状语从句/adverbial_clause | 2 / 2 | reading_jijing_11_test_103_p1 H-05: If not<br>reading_jijing_14_test_23_p1 D-01: but if you do | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| elliptical_conditional_clause | 状语从句/adverbial_clause | 条件状语从句/adverbial_clause | 3 / 3 | ielts11_test1_p1 B-08: If successfully implemented<br>reading_jijing_53_test_83_p3 D-04: If manufactured locally | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| elliptical_contrast_clause | 状语从句/adverbial_clause | 对比状语从句/adverbial_clause | 2 / 2 | reading_jijing_32_test_20_p3 C-03: less so for the gut<br>reading_jijing_78_test_102_p2 A-02: deadly ones, bitter | 应修：见N4 |
| elliptical_disclaimer_clause | 状语从句/adverbial_clause | 省略结构/generic_phrase | 1 / 1 | reading_jijing_53_test_83_p2 E-05: Not that car hire is necessarily the most cost-effective option | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| elliptical_passive_clause | 状语从句/adverbial_clause | 省略结构/generic_phrase | 1 / 1 | reading_jijing_44_test_29_p1 B-04: and my apartment swept and mopped nightly | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| elliptical_time_clause | 状语从句/adverbial_clause | 时间状语从句/adverbial_clause | 2 / 2 | ielts17_test2_p2 D-03: when ripe<br>ielts6_test2_p2 K-36: when asleep | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| exception_condition_clause | 状语从句/adverbial_clause | 条件状语从句/adverbial_clause | 1 / 1 | reading_jijing_78_test_102_p1 E-03: unless you stop (them from) corrupting the normal function of democracy with sufficient checks and balances | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| exclamatory_clause | 状语从句/adverbial_clause | 感叹句/main_clause | 1 / 1 | ielts17_test1_p3 A-02: what a story it is | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| extraposed_infinitive_clause | 状语从句/adverbial_clause | 不定式/infinitive_phrase | 3 / 3 | ielts5_test2_p3 F-23: for mathematicians to keep their discoveries and proofs secret<br>ielts5_test4_p2 D-13: to see why | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| fact_clause | 状语从句/adverbial_clause | 名词性从句/noun_clause | 1 / 1 | ielts5_test4_p2 I-35: that these crystals occur in batches | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| first_clause | 状语从句/adverbial_clause | 分句/main_clause | 4 / 4 | reading_jijing_11_test_103_p1 G-01: have found an 'oasis' of microorganisms two meters below the surface of the Atacama Desert<br>reading_jijing_56_test_64_p1 B-08: Maize, the staple food, is scarce in some areas | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| first_independent_clause | 状语从句/adverbial_clause | 主句/main_clause | 3 / 3 | reading_jijing_76_test_43_p3 B-01: A number of parents were not easy to be aware of the compliance<br>reading_jijing_76_test_43_p3 B-03: this rate was acceptable | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| first_interrogative_clause | 状语从句/adverbial_clause | 疑问句/main_clause | 2 / 2 | reading_jijing_23_test_46_p1 C-04: Does this mean there will be an increase in flooding<br>reading_jijing_23_test_46_p1 C-05: How will our health be affected by climate change | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| first_result_clause | 状语从句/adverbial_clause | 结果状语从句/adverbial_clause | 1 / 1 | reading_jijing_48_test_21_p1 E-05: the pearl may be seriously deformed | 应修：见N4；单例全审 |
| for_to_infinitive_clause | 状语从句/adverbial_clause | 不定式/infinitive_phrase | 1 / 1 | ielts17_test1_p2 E-03: for stadiums to be equipped with public spaces and services | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| fragmented_time_clause | 状语从句/adverbial_clause | 时间状语从句/adverbial_clause | 1 / 1 | reading_jijing_62_test_44_p2 B-05: When cotton production started spreading through Andhra Pradesh state | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| gerund_clause | 状语从句/adverbial_clause | 动名词/gerund_phrase | 9 / 9 | ielts17_test3_p3 G-01: skyscrapers not being built between the two urban centers<br>ielts18_test1_p3 C-05: lowering satellites deep enough into the atmosphere | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| hypothetical_conditional_clause | 状语从句/adverbial_clause | 条件状语从句/adverbial_clause | 1 / 1 | reading_jijing_73_test_5_p2 F-03: If tigers were simply frightened of all humans | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| imperative_clause | 状语从句/adverbial_clause | 祈使句/main_clause | 35 / 37 | ielts11_test4_p3 C-04: run them through the cogs and wheels of the language machine<br>ielts13_test1_p3 C-03: Consider one of the oldest machine artists | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| independent_clause | 状语从句/adverbial_clause | 主句/main_clause | 6 / 6 | ielts17_test2_p3 D-03: they do not actually exist<br>ielts17_test2_p3 G-02: Spencer Silver had a product | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| infinitive_clause | 状语从句/adverbial_clause | 不定式/infinitive_phrase | 41 / 41 | ielts11_test4_p2 A-04: so as to produce the necessary emphases<br>ielts11_test4_p2 F-02: so as to provide an appropriate emotional nuance | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| infinitive_result_clause | 状语从句/adverbial_clause | 不定式/infinitive_phrase | 1 / 1 | ielts18_test3_p3 D-02: only to have to stop and wait every 20 minutes | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| interrogative_clause | 状语从句/adverbial_clause | 疑问句/main_clause | 39 / 39 | ielts10_test4_p2 G-08: are you hoping<br>ielts12_test5_p2 A-05: Why do they do it | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| interrogative_infinitive_clause | 状语从句/adverbial_clause | 不定式/infinitive_phrase | 1 / 1 | ielts5_test2_p3 A-03: how to write science in English | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| inversion_clause | 状语从句/adverbial_clause | 倒装/inversion | 1 / 1 | ielts15_test1_p3 E-01: Here is | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| malformed_condition_clause | 状语从句/adverbial_clause | 条件状语从句/adverbial_clause | 1 / 1 | reading_jijing_11_test_103_p2 F-05: If, over the coming years, the science US about an ever-increased climate sensitivity of the planet and this isn't unrealistic | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| nominal_clause | 状语从句/adverbial_clause | 名词性从句/noun_clause | 18 / 18 | ielts12_test7_p3 C-01: What is rather more significant<br>ielts12_test7_p3 E-04: What Beethoven does instead | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| non_finite_passive_clause | 状语从句/adverbial_clause | 非谓语结构/non_finite_clause | 1 / 1 | ielts12_test7_p3 F-05: to be completed | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| parenthetical_concessive_clause | 状语从句/adverbial_clause | 让步状语从句/adverbial_clause | 1 / 1 | reading_jijing_46_test_84_p3 K-08: though whether the judges were dedicated couch potatoes, and thus biased, we were not able to discover | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| parenthetical_time_clause | 状语从句/adverbial_clause | 时间状语从句/adverbial_clause | 1 / 1 | ielts9_test2_p2 F-06: when Earth is at one point in its orbit | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| participial_clause | 状语从句/adverbial_clause | 分词短语/participial_phrase | 1 / 1 | ielts20_test3_p3 A-01: When asked 'Should robots be used to colonise other planets?' | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| participle_clause | 状语从句/adverbial_clause | 分词短语/participial_phrase | 6 / 6 | ielts17_test2_p2 A-04: allowing genetic material to be added, removed or altered<br>ielts17_test2_p2 B-07: while maintaining or even enhancing the desirable traits of wild strains | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| past_participle_clause | 状语从句/adverbial_clause | 分词短语/participial_phrase | 4 / 4 | reading_jijing_46_test_84_p3 G-07: priced at about £1,250<br>reading_jijing_53_test_83_p3 B-06: Founded in 1997 | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| predicate_with_reason_clause | 状语从句/adverbial_clause | 原因状语从句/adverbial_clause | 1 / 1 | reading_jijing_23_test_46_p1 E-05: reduces carbon emissions because they use less energy to manufacture than products made from completely new materials | 应修：见N4；单例全审 |
| prepositional_clause | 状语从句/adverbial_clause | 介词短语/prepositional_phrase | 1 / 1 | ielts5_test1_p2 I-01: for why so many teacher-subjects were willing to forgo their sense of personal responsibility | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| prepositional_participial_clause | 状语从句/adverbial_clause | 介词短语/prepositional_phrase | 1 / 1 | ielts19_test4_p2 D-02: Despite arising in the last half century | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| present_participial_clause | 状语从句/adverbial_clause | 分词短语/participial_phrase | 4 / 4 | ielts19_test4_p2 A-02: boosting its potential as a life-saving medicine<br>ielts19_test4_p2 B-02: asking for time to weigh up the pros and cons | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| present_participle_clause | 状语从句/adverbial_clause | 分词短语/participial_phrase | 7 / 7 | reading_jijing_81_test_93_p1 C-02: bringing a range of benefits<br>reading_jijing_81_test_93_p1 D-03: getting nine to 9.5 hours of sleep a night | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| question_clause | 状语从句/adverbial_clause | 疑问句/main_clause | 1 / 1 | ielts20_test3_p2 C-05: are the animals? | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| reduced_concessive_clause | 状语从句/adverbial_clause | 让步状语从句/adverbial_clause | 2 / 2 | ielts5_test2_p3 F-24: though international<br>reading_jijing_71_test_1_p2 B-01: although seemingly more accessible to movie watchers | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| reduced_condition_clause | 状语从句/adverbial_clause | 条件状语从句/adverbial_clause | 1 / 1 | reading_jijing_78_test_102_p3 G-03: Properly activated | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| reduced_conditional_clause | 状语从句/adverbial_clause | 条件状语从句/adverbial_clause | 3 / 3 | ielts8_test4_p3 B-10: if mishandled<br>ielts9_test4_p3 B-02: if possible | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| reduced_manner_clause | 状语从句/adverbial_clause | 方式状语从句/adverbial_clause | 1 / 1 | ielts7_test4_p3 C-07: As shown in Table 1 | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| reduced_time_clause | 状语从句/adverbial_clause | 时间状语从句/adverbial_clause | 25 / 25 | ielts6_test2_p3 C-04: when using the one, two, many type of system<br>ielts6_test2_p3 C-05: when dealing with the simpler aspects of human existence | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| reduced_time_condition_clause | 状语从句/adverbial_clause | 时间状语从句/adverbial_clause | 2 / 2 | ielts8_test4_p2 G-03: When handled by experts<br>reading_jijing_32_test_20_p3 G-03: when blocked from expressing itself | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| run_on_clause | 状语从句/adverbial_clause | 主句/main_clause | 5 / 1 | reading_jijing_44_test_29_p1 I-04: they can fly, too | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| run_on_passive_clause | 状语从句/adverbial_clause | 主句/main_clause | 2 / 0 | reading_jijing_27_test_33_p1 D-01: Submarines were sent into die Loch Ness<br>reading_jijing_27_test_33_p1 E-02: In 2007, it was estimated | 所列实例的新标签基本合理；不保证原始跨度本身无误；历史例，当前已消失 |
| second_clause | 状语从句/adverbial_clause | 分句/main_clause | 1 / 1 | reading_jijing_56_test_64_p1 B-08: prices in markets have shot up beyond the means of the hungriest | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| second_independent_clause | 状语从句/adverbial_clause | 主句/main_clause | 3 / 3 | reading_jijing_76_test_43_p3 B-01: some even overlooked their children's noncompliance<br>reading_jijing_76_test_43_p3 B-03: some parents could be patient with the noncompliance | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| second_interrogative_clause | 状语从句/adverbial_clause | 疑问句/main_clause | 1 / 1 | reading_jijing_23_test_46_p1 C-05: how will agricultural practices change | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| standalone_time_clause | 状语从句/adverbial_clause | 时间状语从句/adverbial_clause | 1 / 1 | reading_jijing_76_test_43_p3 C-02: When they are growing up | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| supplementary_participle_clause | 状语从句/adverbial_clause | 分词短语/participial_phrase | 1 / 1 | reading_jijing_71_test_1_p3 B-06: in his death, as in his life, left out in the cold | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| temporal_causal_clause | 状语从句/adverbial_clause | 时间状语从句/adverbial_clause | 1 / 1 | ielts13_test4_p2 D-01: as populations grew and agriculture had to be run on more commercial lines | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| temporal_clause | 状语从句/adverbial_clause | 时间状语从句/adverbial_clause | 25 / 25 | ielts13_test4_p2 B-05: as microorganisms within soil digest dead animals and plants<br>ielts13_test4_p2 C-03: once this has happened | 所列实例的新标签基本合理；不保证原始跨度本身无误 |
| third_interrogative_clause | 状语从句/adverbial_clause | 疑问句/main_clause | 1 / 1 | reading_jijing_23_test_46_p1 C-05: and how will wildlife cope | 所列实例的新标签基本合理；不保证原始跨度本身无误；单例全审 |
| whether_clause | 状语从句/adverbial_clause | 名词性从句/noun_clause | 4 / 4 | ielts4_test1_p3 C-14: whether various lines of motion were apt ways of showing movement<br>ielts4_test1_p3 C-15: whether there were differences in how the blind and the sighted interpreted lines of motion | 所列实例的新标签基本合理；不保证原始跨度本身无误 |


unknown全库从144种329处变为141种323处，无新增种类。用户披露的“34处未改成分”未给相同筛选口径：当前第四轮变化句中有32处unknown，其中24处成分字面与旧版相同；不将34当本轮实测。约85处含混兜底是存量：contrastive_clause需区分主句/省略/从属对比，passive_clause仅表示语态，不能据词名可靠映射为状语从句，建议按真实成分修标注。


## 附录H：源文清单外207条关键词命中

关键词：`原文|源文|疑为|应为|拼写|误写|笔误|OCR|识别|转录|残缺|脱漏|排版|排印|讹|漏字|错字|断词`。先从清单一至七节表格提取passage_id+句ID，再做集合差。108条需进一步分类的源文问题记录（R），99条正常教学信息/合法原文说明（I），不是自动纠错名单。表中保留命中的原难点文字，使另一台电脑不依赖本地缓存也能逐项复核。


| # | 来源 | 分类 | 命中的难点原文 |
|---|---|---|---|
| 1 | ielts10_test2_p2 B-04 | I：不据此认定源文错误 | can be helped to identify 是被动结构，表示儿童可以得到帮助来识别学习方式。 |
| 2 | ielts10_test4_p2 E-01 | I：不据此认定源文错误 | who 引导定语从句修饰 a person，说明所识别的人具有何种特征。 |
| 3 | ielts10_test4_p3 H-06 | I：不据此认定源文错误 | digit loss and gain 被视作一个整体过程，因此原文使用单数谓语 has occurred。 |
| 4 | ielts11_test1_p2 G-01 | I：不据此认定源文错误 | 主语中心概念是 the remaining ... lift，原文因此使用单数谓语 is。 |
| 5 | ielts11_test1_p3 E-04 | I：不据此认定源文错误 | 本句引语尚未结束，结束引号保留在下一句原文中。 |
| 6 | ielts11_test3_p1 D-04 | I：不据此认定源文错误 | the weaving and trading of silk fabric 整体指一项受帝国垄断的产业活动，因此原文使用单数 was。 |
| 7 | ielts11_test4_p1 L-03 | I：不据此认定源文错误 | Things written in pen 是宾语前置，正常语序应为 you can't change things written in pen，此处为强调而提前。 |
| 8 | ielts12_test6_p2 D-04 | I：不据此认定源文错误 | 引号内是宾厄姆原文式的直接引语，he wrote 是后置的报道语。 |
| 9 | ielts12_test6_p3 B-04 | I：不据此认定源文错误 | at least 限定该现象至少出现在词汇识别的早期阶段。 |
| 10 | ielts12_test8_p2 B-02 | I：不据此认定源文错误 | with tasselled ears 是识别猞猁的重要特征。 |
| 11 | ielts13_test3_p2 F-06 | I：不据此认定源文错误 | differences between their native language and other tongues 是 recognize 的宾语，说明识别的对象。 |
| 12 | ielts15_test1_p3 C-02 | I：不据此认定源文错误 | because 从句解释这些 matters 为什么能被所有人识别。 |
| 13 | ielts15_test4_p2 G-03 | I：不据此认定源文错误 | recognising Silbo as a language 使用 recognise ... as ... 结构，表示把 Silbo 当成语言来识别。<br>were not recognising 强调实验过程中他们没有进行这种语言识别。 |
| 14 | ielts15_test4_p2 J-03 | I：不据此认定源文错误 | [Silbo Gomero] 方括号表示原文引语中为了清晰而补入的对象。 |
| 15 | ielts16_test3_p1 G-04 | I：不据此认定源文错误 | a succession of recognisable landmarks 指连续出现、可以识别的地标。 |
| 16 | ielts16_test3_p3 H-03 | I：不据此认定源文错误 | are able to rapidly identify 表示科学家现在能够快速识别。 |
| 17 | ielts17_test4_p2 D-04 | I：不据此认定源文错误 | 这是原文中的片段句，承接上一句 Individual lives，举出具体故事。 |
| 18 | ielts18_test2_p3 E-02 | I：不据此认定源文错误 | But from... 引出与上一句“不容易识别”相反的可能性。 |
| 19 | ielts19_test1_p1 C-06 | I：不据此认定源文错误 | . . . 是原文中的停顿/省略标记，属于直接引语内容。 |
| 20 | ielts19_test1_p2 B-08 | I：不据此认定源文错误 | ocean-going caravels* 指适合远洋航行的卡拉维尔帆船，星号是原文脚注标记。 |
| 21 | ielts19_test2_p2 D-01 | I：不据此认定源文错误 | as 在这里引导原因状语从句，解释两种反应为何影响身体状态。 |
| 22 | ielts19_test4_p1 I-01 | I：不据此认定源文错误 | that may be at risk 修饰 species，说明哪些物种需要被识别。 |
| 23 | ielts20_test3_p3 L-05 | I：不据此认定源文错误 | 方括号中的 threat 是编辑补足词，用来明确原文语义。 |
| 24 | ielts4_test2_p3 G-37c | R：待分类 | is getting 是现在进行时，all sorts of 意为“各种各样的”；原文这句引语没有结束引号。 |
| 25 | ielts4_test2_p3 H-38b | I：不据此认定源文错误 | says Bekoff 是倒装的引述分句；原文的逗号放在了引号外面。 |
| 26 | ielts4_test3_p2 A-14 | I：不据此认定源文错误 | sulphur dioxide 使用英式拼写 sulphur。 |
| 27 | ielts4_test4_p1 B-09 | I：不据此认定源文错误 | with 短语和破折号补充识别运动员的社会条件。 |
| 28 | ielts4_test4_p1 C-12 | I：不据此认定源文错误 | only 强调识别并非全部工作。 |
| 29 | ielts4_test4_p1 E-22 | R：待分类 | even though 后省略了 they take，源文为不完整结构。 |
| 30 | ielts4_test4_p1 I-41 | R：待分类 | that 从句作 learn 的宾语；源文在 John S. 处截断。 |
| 31 | ielts4_test4_p1 I-42 | R：待分类 | 源文是承接上一句引述的姓名和身份片段。 |
| 32 | ielts4_test4_p3 D-16 | I：不据此认定源文错误 | As...put it 引出原文引语。 |
| 33 | ielts5_test1_p1 B-01 | I：不据此认定源文错误 | 书名中的拼写 hard usuall English wordes 保留早期英语形式。 |
| 34 | ielts6_test2_p2 E-14 | I：不据此认定源文错误 | 原文引语跨两句，这一句末尾的引号尚未闭合，仍属同一段话。 |
| 35 | ielts7_test2_p3 C-01 | I：不据此认定源文错误 | Having determined 表示先完成确定需求，再进行后面的识别。 |
| 36 | ielts8_test2_p3 B-01 | I：不据此认定源文错误 | cue 在此指帮助识别关系或触发反应的“线索”。 |
| 37 | ielts8_test2_p3 B-03 | I：不据此认定源文错误 | by scent 表示识别所凭借的方式，而不是识别的对象。 |
| 38 | ielts9_test2_p2 A-01 | I：不据此认定源文错误 | population 是集合名词，原文用 were 强调其中的人。 |
| 39 | ielts9_test2_p2 F-03 | R：待分类 | 原文 today's value of methods in accuracy 表达略显省略或异常，核心意思是该数值接近今天更精确的方法所得结果。 |
| 40 | ielts9_test4_p1 E-04 | R：待分类 | 源文在段落边界处把姓名 André-Louis Debierne 拆开，本段末的 André 与下一段开头 -Louis Debierne 连读。 |
| 41 | ielts9_test4_p1 F-01 | R：待分类 | 源文在段落边界处错误拆分了 André-Louis Debierne，本片段需与上一段末尾 André 合并理解。 |
| 42 | ielts9_test4_p3 F-05 | I：不据此认定源文错误 | five times smaller 是原文表达，强调旧城区面积远小于现代城市。 |
| 43 | reading_jijing_10_test_78_p2 E-35b | R：待分类 | Gloria Mark 是女性，代词应为 her，原文用了 his。 |
| 44 | reading_jijing_10_test_78_p3 C-02 | I：不据此认定源文错误 | are commissioned from 表示设计工作委托给外部机构；distinguish-ability 是源文写法，意为辨识度。 |
| 45 | reading_jijing_10_test_78_p3 F-02 | I：不据此认定源文错误 | attribute blame to 表示把责任归于某个原因；typescript 在此按包装文字排印或字体设计理解。 |
| 46 | reading_jijing_10_test_78_p3 H-06 | R：待分类 | 源文在段落边界处把完整引语拆开，本片段需与下一段开头 are based on strength 连读。 |
| 47 | reading_jijing_10_test_78_p3 I-02 | R：待分类 | prevent a child from access 是源文搭配，常规表达通常是 prevent a child from gaining access。 |
| 48 | reading_jijing_11_test_103_p1 D-01 | R：待分类 | aroused doubts to 搭配不自然，语义应为“引发对上述分析的质疑”。 |
| 49 | reading_jijing_11_test_103_p1 D-05 | R：待分类 | The size and shape 是并列主语，原文却使用单数 is，存在主谓一致问题。 |
| 50 | reading_jijing_11_test_103_p2 F-03 | R：待分类 | As 引导的从句本应依附后面的引语或主句，但原文在此用句号截断。 |
| 51 | reading_jijing_13_test_6_p3 B-07 | I：不据此认定源文错误 | 句首语义上包含两项证据，但源文谓语使用单数 suggests，将整体证据视作一个组合。 |
| 52 | reading_jijing_14_test_23_p2 D-04 | R：待分类 | spacio-visual 是源文非常规拼写，语意为 spatial-visual。 |
| 53 | reading_jijing_14_test_23_p2 G-02 | R：待分类 | that 原意替代 ability，但前面 abilities 为复数，数上不一致，是源文问题。 |
| 54 | reading_jijing_14_test_23_p3 A-04 | I：不据此认定源文错误 | primarily... 限定研发工作的重点领域；原文用单引号标出机构目标。 |
| 55 | reading_jijing_16_test_97_p1 B-06 | I：不据此认定源文错误 | 源文在 University of 与 Arizona 之间有换行，句子内容应按同一句保留并规范为空格。 |
| 56 | reading_jijing_16_test_97_p3 B-03 | R：待分类 | but 后是存在句，源文数据表述存在张力：前半说89%含某种暴力，后半说70%无攻击性内容，可能区分 violent 与 aggressive。 |
| 57 | reading_jijing_16_test_97_p3 E-08 | R：待分类 | 源文在段落边界处拆开了作者身份和书名，本片段需与下一段开头的书名连读。 |
| 58 | reading_jijing_18_test_53_p1 B-01 | R：待分类 | without ... 表示这种衡量不依赖赤道之类的天然基线；baseline 前原文缺冠词或复数标记。 |
| 59 | reading_jijing_18_test_53_p2 E-02 | R：待分类 | structure and content 是并列主语，原文却使用单数 is，存在主谓一致问题。 |
| 60 | reading_jijing_18_test_53_p2 F-09 | R：待分类 | 原文 school 与 not 之间缺少逗号；not just 与前项构成对比但缺少 but。 |
| 61 | reading_jijing_18_test_53_p2 I-02 | R：待分类 | Kevin Brennan 与 The family's minister 同位；原文 family's minister 是非常规表达。 |
| 62 | reading_jijing_22_test_90_p1 B-05 | I：不据此认定源文错误 | 语义上是舞蹈招募其他工蜂，原文用 each aspect 作 recruited 的语法主语，应依原文理解。 |
| 63 | reading_jijing_22_test_90_p1 D-02 | I：不据此认定源文错误 | 原文后半项省略 is a connection to，its 指 food supplies。 |
| 64 | reading_jijing_22_test_90_p2 F-17 | R：待分类 | with 结构补充现代社会的睡眠现状；原文 with 后并列结构不完全平行。 |
| 65 | reading_jijing_22_test_90_p3 F-05 | I：不据此认定源文错误 | This 指前述识别阻碍、引入促进因素的阶段；is followed by 表示下一个流程。 |
| 66 | reading_jijing_22_test_90_p3 G-02 | I：不据此认定源文错误 | two month long 和 in house 均作复合修饰，源文未加连字符。 |
| 67 | reading_jijing_22_test_90_p3 G-06 | R：待分类 | psychometric testing discussions 源文无逗号，可能指心理测评及讨论或心理测评讨论。 |
| 68 | reading_jijing_22_test_90_p3 G-08 | R：待分类 | 源文是缺少限定谓语的句子片段，可理解为 One initiative requires...。<br>to which 与 view 的搭配存在源文语法异常；按语义理解为所有员工将被邀请观看这场表演。 |
| 69 | reading_jijing_23_test_46_p1 C-07 | I：不据此认定源文错误 | while 在引语中引导让步从句，后面原文缺少逗号。 |
| 70 | reading_jijing_24_test_56_p2 A-04 | I：不据此认定源文错误 | 5% lower percentage 是源文不自然的统计表达，按“比例低5%”理解。 |
| 71 | reading_jijing_24_test_56_p3 C-05 | I：不据此认定源文错误 | remain convinced that 表示仍坚信；acid based 是源文无连字符写法，意为以酸为基础。 |
| 72 | reading_jijing_24_test_56_p3 H-02 | R：待分类 | 第二个 which 修饰 adverse reactions；源文在 time frame 后缺少关闭逗号，can be discovered 才是外层从句谓语。 |
| 73 | reading_jijing_26_test_72_p1 B-02 | R：待分类 | top banana 是双关式表达，意为“负责人”；句尾 in 因源文跨段截断而悬空。 |
| 74 | reading_jijing_26_test_72_p1 D-10 | R：待分类 | Rome-based 后缺少中心名词，是源文跨段截断造成的。 |
| 75 | reading_jijing_26_test_72_p1 G-08 | I：不据此认定源文错误 | 整个数量短语被视为一种典型做法，因此原文谓语用单数 is。 |
| 76 | reading_jijing_27_test_33_p1 D-01b | I：不据此认定源文错误 | explode 在此是比喻，指现象迅速升温；in second half of the century 规范写法应为 in the second half of the century。 |
| 77 | reading_jijing_27_test_33_p2 C-05 | I：不据此认定源文错误 | five-percent-better 是源文带连字符的复合比较修饰语。 |
| 78 | reading_jijing_27_test_33_p3 C-01 | R：待分类 | there remains 是存在句；that 后内容在源文中句法不完整，`the focus on who is causing the problem` 后缺少谓语便由 and 接续。 |
| 79 | reading_jijing_27_test_33_p3 C-02 | R：待分类 | who may be at fault 是介词 to 的宾语；or 后 exacerbating 与 who 的连接在源文中略省略。 |
| 80 | reading_jijing_27_test_33_p3 C-03 | I：不据此认定源文错误 | Finger-pointing and blaming 语义为并列主语，但源文使用单数 leads，将其视作一种整体行为。 |
| 81 | reading_jijing_27_test_33_p3 D-02 | R：待分类 | 源文 `almost a reflex action` 前可能缺 as，正常语义是“几乎像反射动作一样”。 |
| 82 | reading_jijing_27_test_33_p3 E-02 | R：待分类 | and 后 a hierarchical structure 在源文中缺少与前面平行的主要谓语，可按“由该结构负责”理解。 |
| 83 | reading_jijing_29_test_63_p1 F-07 | I：不据此认定源文错误 | 现在进行时表示低估风险是当前持续存在的问题；原文 under-estimating 带连字符。 |
| 84 | reading_jijing_29_test_63_p2 B-04 | R：待分类 | make + 宾语 + 形容词构成宾补；environmental friendly 是源文非常规表达。 |
| 85 | reading_jijing_29_test_63_p2 E-08 | R：待分类 | 源文该句开引号但未在句末闭合。 |
| 86 | reading_jijing_29_test_63_p2 H-02 | R：待分类 | could well 表示很可能；源文引语在句末未闭合。 |
| 87 | reading_jijing_29_test_63_p3 E-05 | I：不据此认定源文错误 | It 指 China；the new rich 名词化表示新富阶层，源文用 its new rich。 |
| 88 | reading_jijing_32_test_20_p1 C-03 | I：不据此认定源文错误 | children of 5 or 6 years old 是原文年龄表达，语义为五六岁儿童。 |
| 89 | reading_jijing_32_test_20_p1 E-01 | I：不据此认定源文错误 | working condition 使用单数是源文形式，语义泛指儿童劳动条件。 |
| 90 | reading_jijing_32_test_20_p1 G-03 | R：待分类 | became the core to 是原文搭配，语义为成为这一概念的核心。 |
| 91 | reading_jijing_32_test_20_p2 B-01 | I：不据此认定源文错误 | 编号 1. 属于原文内容，标示第一项定义假设。 |
| 92 | reading_jijing_38_test_22_p1 D-04 | I：不据此认定源文错误 | 12 times less costly than 是原文倍数表达，表示成本显著更低。 |
| 93 | reading_jijing_38_test_22_p3 G-07 | I：不据此认定源文错误 | commented that 后面接的是加了引号的原话：作者转述时直接引用了论文原文。 |
| 94 | reading_jijing_40_test_75_p1 C-02 | I：不据此认定源文错误 | something unrecognisable 指当时尚未识别的世俗体文字。 |
| 95 | reading_jijing_44_test_29_p2 G-01 | I：不据此认定源文错误 | Despite 与 however 同时强化转折，尽管语义略有重复但属原文表达。 |
| 96 | reading_jijing_44_test_29_p3 M-01 | R：待分类 | happens 后紧接连字符开启下一列表项，源文缺少空格和换行。 |
| 97 | reading_jijing_46_test_84_p1 A-01 | I：不据此认定源文错误 | officials 是 being posed 的承受者，原文用被动语态表示官员被人提问。 |
| 98 | reading_jijing_46_test_84_p1 C-04 | R：待分类 | 原句省略了两部分中的系动词，使表达更紧凑；at all areas 是源文搭配。 |
| 99 | reading_jijing_46_test_84_p3 K-09 | I：不据此认定源文错误 | 括号说明 Paleozoic era 在原文中的年代范围。 |
| 100 | reading_jijing_48_test_21_p1 C-04 | R：待分类 | the secreted fluid covering the irritant 是 nacre 的同位解释；分号连接条件从句与主句是源文标点用法。 |
| 101 | reading_jijing_48_test_21_p1 E-02 | R：待分类 | be transplanted an irritant 是源文的双宾式被动表达，含义是“被植入刺激物”。 |
| 102 | reading_jijing_48_test_21_p1 E-06 | R：待分类 | make it through 是习惯表达，表示成功熬过艰难过程；circle 是源文用词。 |
| 103 | reading_jijing_48_test_21_p1 F-01 | R：待分类 | of another different story 是源文表达，语义相当于“属于另一种情况”。 |
| 104 | reading_jijing_48_test_21_p3 D-01 | R：待分类 | agriculture production 是源文用法，语义上指 agricultural production。 |
| 105 | reading_jijing_48_test_21_p3 J-01 | R：待分类 | that 从句中 bring 缺少明确宾语或施事，是源文残缺表达，按大意理解。 |
| 106 | reading_jijing_48_test_21_p3 K-02 | R：待分类 | adaptation to 表示对某种环境变化的适应，源文 adaptation 缺冠词或复数标记。 |
| 107 | reading_jijing_48_test_21_p3 K-04 | I：不据此认定源文错误 | their 指海龟；research 通常不可数，researches 是源文用法。 |
| 108 | reading_jijing_48_test_21_p3 M-01 | I：不据此认定源文错误 | a tip of the iceberg 是源文形式，常见习语为 the tip of the iceberg。 |
| 109 | reading_jijing_48_test_21_p3 M-02 | R：待分类 | that 修饰 a world issue；hangs in an ambiguous future 是源文不自然表达，意指未来仍不确定。 |
| 110 | reading_jijing_53_test_83_p2 G-04 | R：待分类 | 短横线内 for that matter 扩展到任何旅程；with transport 与 by walking 表达方式不完全平行但属原文。 |
| 111 | reading_jijing_53_test_83_p3 A-02 | R：待分类 | when 从句与前一分句仅用逗号连接，属于源文逗号拼接。 |
| 112 | reading_jijing_53_test_83_p3 C-05 | R：待分类 | the village 用单数与上文多个村庄不协调，是源文语法异常。 |
| 113 | reading_jijing_53_test_83_p3 C-06 | R：待分类 | says 与 expressed 时态不一致，是源文表达；its 指 LED lighting。 |
| 114 | reading_jijing_53_test_83_p3 F-03 | R：待分类 | a lack of power plants, transmission 的并列关系不完整，是源文表达问题。 |
| 115 | reading_jijing_53_test_83_p3 F-04 | R：待分类 | require a longer life 搭配不自然，通常应表达 have a longer life，属于源文问题。 |
| 116 | reading_jijing_56_test_64_p2 B-03 | I：不据此认定源文错误 | had identified 使用过去完成时，表示识别工作发生在宣布之前。 |
| 117 | reading_jijing_56_test_64_p2 B-04 | I：不据此认定源文错误 | It 回指文特尔识别人类全部基因这一成果。 |
| 118 | reading_jijing_56_test_64_p3 M-05 | R：待分类 | 两个独立分句仅用逗号连接，是源文逗号拼接。 |
| 119 | reading_jijing_5_test_59_p1 I-03 | I：不据此认定源文错误 | creating 与 designing 说明钱花在什么方面；原文把 bottle and a television campaign 共同置于 designing 后。 |
| 120 | reading_jijing_5_test_59_p2 G-06 | I：不据此认定源文错误 | between 18-37% 是源文的范围写法，语义为 18% 到 37%。 |
| 121 | reading_jijing_62_test_44_p1 B-01 | R：待分类 | 原文用逗号连接两个独立分句，属于逗号拼接；后半句的主语是 this ability。 |
| 122 | reading_jijing_62_test_44_p1 C-04 | I：不据此认定源文错误 | between 12 and 20 是规范的范围表达，与上一句残缺的 between 形成对照。 |
| 123 | reading_jijing_62_test_44_p1 E-01 | R：待分类 | 原文用逗号连接完整主句和残缺结构 some in opposition，语义上相当于“some are in opposition”。 |
| 124 | reading_jijing_62_test_44_p2 B-01 | R：待分类 | 前两个独立分句仅用逗号连接，是源文的逗号拼接现象。 |
| 125 | reading_jijing_62_test_44_p2 B-05 | R：待分类 | 本句由 When 引导，按标准语法应有主句，但源文在此误用了句号。 |
| 126 | reading_jijing_62_test_44_p2 C-08 | R：待分类 | were mixing 后缺少宾语或连接成分，是源文残缺；结合语境可知农民不断混配并喷洒农药。 |
| 127 | reading_jijing_62_test_44_p3 B-01 | R：待分类 | them 指 supermarkets，多个独立分句以逗号连接是源文拼接。 |
| 128 | reading_jijing_62_test_44_p3 H-05 | R：待分类 | products' benefit 数和所有格搭配不自然，是源文表达。 |
| 129 | reading_jijing_62_test_44_p3 I-01 | R：待分类 | author... 是 Richard 的同位语，之后原文缺逗号。<br>it 是形式主语；rather listen 缺 than/to，是源文省略异常。 |
| 130 | reading_jijing_62_test_44_p3 I-04 | R：待分类 | that 修饰 demeanour，但语义上应由 salesperson 执行 takes，源文搭配略生硬。 |
| 131 | reading_jijing_62_test_44_p3 J-05 | R：待分类 | 两个 if 条件结构仅用逗号连接，是源文逗号拼接。 |
| 132 | reading_jijing_65_test_69_p1 C-03 | I：不据此认定源文错误 | when 从句后原文未加逗号，但不影响其状语功能。 |
| 133 | reading_jijing_65_test_69_p1 E-06 | I：不据此认定源文错误 | 原文在本句末没有闭合引号，引语延续至下一句。 |
| 134 | reading_jijing_65_test_69_p1 F-04 | R：待分类 | 原文 between... or... 搭配异常，规范表达通常是 between 5 and 15 seconds；say 是插入语。 |
| 135 | reading_jijing_65_test_69_p3 J-03 | R：待分类 | formational archaeology 前可能缺标点或介词，是源文句法异常；末尾同位语解释其含义。 |
| 136 | reading_jijing_6_test_71_p1 B-01 | I：不据此认定源文错误 | The 1960s 表示一个年代，原文因此使用单数谓语 was。 |
| 137 | reading_jijing_6_test_71_p1 B-03 | I：不据此认定源文错误 | 两个 and 串联三个并列主语，脚注标记属于原文词项的一部分。 |
| 138 | reading_jijing_6_test_71_p2 I-02 | I：不据此认定源文错误 | including... 补充说明 programme of work 的内容；原文 as well as other stakeholders 存在省略，语义上指也与其他利益相关者讨论。 |
| 139 | reading_jijing_71_test_1_p1 E-03 | I：不据此认定源文错误 | a hard-shelled alga 是 diatoms 的同位解释；原文用单数 alga 概括这一生物类别。 |
| 140 | reading_jijing_71_test_1_p2 C-04 | I：不据此认定源文错误 | host culture 指影片来源文化，viewing culture 指观众所在文化；between 修饰 differences。 |
| 141 | reading_jijing_71_test_1_p2 D-01 | R：待分类 | 并列主语 wealth and materialism 后原文使用 was，属于源文数的一致异常。 |
| 142 | reading_jijing_72_test_15_p2 I-01 | I：不据此认定源文错误 | 本段与 H 段内容相近，属于源文本身重复出现的段落。 |
| 143 | reading_jijing_73_test_5_p1 K-01 | R：待分类 | 本句是两个并列现在分词构成的源文残句，没有明示主句主语。 |
| 144 | reading_jijing_73_test_5_p1 K-03 | R：待分类 | 本句以小写 like 开头，是源文独立成句的残片，语义承接植物和动物迁入中庭。 |
| 145 | reading_jijing_73_test_5_p2 A-04 | R：待分类 | 两个独立分句仅用逗号连接，是源文的逗号拼接。 |
| 146 | reading_jijing_73_test_5_p2 E-05 | R：待分类 | they 语义上指泛指的 tigers，但与前面单数 A tiger 存在源文数的不一致。 |
| 147 | reading_jijing_73_test_5_p2 E-11 | R：待分类 | 原文 lions-particularly 前只有一个连字符且缺少闭合破折号，应按插入说明理解。 |
| 148 | reading_jijing_73_test_5_p3 E-03 | R：待分类 | the fact... 与 something quite astonishing 同位，源文两者间省略了冒号或破折号。 |
| 149 | reading_jijing_76_test_43_p1 E-01 | R：待分类 | a number, and often combination of 属于源文略不规范的并列，语义是“多种因素，而且往往是多因素组合”。 |
| 150 | reading_jijing_76_test_43_p2 A-04 | R：待分类 | 原文 that 与 Romano-British 之间缺少冒号或句号，语义上后半句用于纠正前述简单叙事。 |
| 151 | reading_jijing_76_test_43_p3 B-01 | R：待分类 | 逗号直接连接两个独立分句，属于原文的逗号拼接。 |
| 152 | reading_jijing_76_test_43_p3 B-02 | R：待分类 | 原文 several occasion 和 in certain ages 存在数与介词搭配问题，翻译按语意处理。 |
| 153 | reading_jijing_76_test_43_p3 B-03 | R：待分类 | 两个独立分句只用逗号连接，是原文的逗号拼接。 |
| 154 | reading_jijing_76_test_43_p3 C-02 | R：待分类 | When 引导的时间从句本应依附主句，但原文在此用句号截断。 |
| 155 | reading_jijing_76_test_43_p3 C-07 | R：待分类 | 两个独立分句只由逗号连接，是原文的逗号拼接。 |
| 156 | reading_jijing_76_test_43_p3 C-08 | R：待分类 | that 后以动名词 Organizing 开始，却缺少谓语，原文宾语从句在语法上不完整。 |
| 157 | reading_jijing_76_test_43_p3 C-15 | R：待分类 | 从严格语法看，without 短语的逻辑主语会被理解为 they，但语意实际是照护者未替孩子建立预期，原文存在悬垂修饰。 |
| 158 | reading_jijing_76_test_43_p3 D-01 | R：待分类 | that 后只有动名词短语，没有完整谓语，原文宾语从句不完整。 |
| 159 | reading_jijing_76_test_43_p3 D-03 | R：待分类 | 原文 things often refused to occur 结构歧义，按上下文应指“经常遭拒的事情被安排在偏好活动之前”。 |
| 160 | reading_jijing_76_test_43_p3 D-05 | R：待分类 | 原文 you have to do 按上下文逻辑应指 child 必须做，存在人称指代不一致。 |
| 161 | reading_jijing_76_test_43_p3 D-07 | R：待分类 | Instead of the word your request like this 语法残缺，结合上下文应理解为“相反，要这样措辞”。 |
| 162 | reading_jijing_76_test_43_p3 E-01 | R：待分类 | comply with 通常必须带宾语，原文句末缺少介词宾语；翻译按“让孩子服从”处理。 |
| 163 | reading_jijing_77_test_16_p2 D-02 | R：待分类 | must 后接冒号再接动词原形，冒号在此不表示列举，只是排版上的停顿。 |
| 164 | reading_jijing_78_test_102_p1 G-01 | I：不据此认定源文错误 | monitored by... 修饰 auctions；Africa 后的连字符在原文中起破折号的作用。 |
| 165 | reading_jijing_78_test_102_p1 H-02 | R：待分类 | first 在源文中衔接略生硬，应理解为“首先要看到”。 |
| 166 | reading_jijing_78_test_102_p2 A-05 | R：待分类 | 原文复数主语 Taste buds 后使用 offers，存在主谓一致异常。 |
| 167 | reading_jijing_78_test_102_p2 E-03 | I：不据此认定源文错误 | 源文 Christopher 与 Columbus 之间是换行，按规范化空格保留为同一句。 |
| 168 | reading_jijing_78_test_102_p2 E-05 | I：不据此认定源文错误 | 主语中心是不可分割概念 The rise and fall，原文使用单数 is。 |
| 169 | reading_jijing_78_test_102_p3 A-02 | I：不据此认定源文错误 | half of which 是非限制性定语从句，which 指 the nation's electricity；原文用连字符连接。 |
| 170 | reading_jijing_78_test_102_p3 E-03b | R：待分类 | multicore-away 的连字符是原文排版问题，应理解为“转向多核，摆脱……”。 |
| 171 | reading_jijing_81_test_93_p1 C-02 | R：待分类 | that 修饰 benefits；as Shakespeare put it 是插入语，sleave 的异常拼写保留自源文。 |
| 172 | reading_jijing_81_test_93_p1 G-03 | R：待分类 | 源文 soccer - season that practice 语法残缺；破折号后的 too late 说明训练时间导致无法安排晚餐和睡前放松。 |
| 173 | reading_jijing_81_test_93_p3 F-06 | I：不据此认定源文错误 | or to the cinema 承前省略了 to go，完整应为 or to go to the cinema。 |
| 174 | reading_jijing_82_test_4_p3 H-05 | I：不据此认定源文错误 | 句末的双引号在此处闭合，对应 H-04 中未闭合的开引号，是原文标点跨句的情况。 |
| 175 | reading_jijing_83_test_95_p1 B-04 | R：待分类 | that 从句作 know 的宾语；they has 是源文主谓不一致。 |
| 176 | reading_jijing_83_test_95_p1 F-06 | I：不据此认定源文错误 | 现在完成时强调这从来都不是研究目的；引语在源文中跨句延续。 |
| 177 | reading_jijing_83_test_95_p1 H-06 | I：不据此认定源文错误 | 引语在本句末尾未闭合，并延续到下一句，这是源文格式。 |
| 178 | reading_jijing_83_test_95_p2 A-02 | R：待分类 | 从句中 respects 与 are 并列作谓语，但主语 this form of tourism 为单数，are 却用复数形式，属原文主谓不一致的瑕疵。 |
| 179 | reading_jijing_83_test_95_p2 C-05 | I：不据此认定源文错误 | clothing placed 承前省略了 should be，完整应为 clothing should be placed。 |
| 180 | reading_jijing_83_test_95_p2 E-04 | R：待分类 | 主语 They 为复数，但谓语 loves、writes 却用了单数形式，属原文主谓一致错误。 |
| 181 | reading_jijing_83_test_95_p2 F-01 | R：待分类 | 句子实际包含两个独立分句，中间仅用逗号连接（逗号拼接），属原文标点瑕疵。 |
| 182 | reading_jijing_83_test_95_p2 G-01 | R：待分类 | provide 应为 provides，主谓不一致，属原文瑕疵。 |
| 183 | reading_jijing_83_test_95_p2 G-05 | R：待分类 | 本句缺少主要谓语动词，是一个由名词短语构成的片段句，属原文表达不完整。 |
| 184 | reading_jijing_83_test_95_p3 A-03 | I：不据此认定源文错误 | Clan 是原文中的小节标题，在原排版中紧跟上一段末尾、以换行分隔，此处单独处理为一句。 |
| 185 | reading_jijing_83_test_95_p3 C-04 | I：不据此认定源文错误 | Tribe 是原文中的小节标题，紧跟上一段末尾、以换行分隔，此处单独处理为一句。 |
| 186 | reading_jijing_83_test_95_p3 E-06 | I：不据此认定源文错误 | Chiefdom 是原文中的小节标题，紧跟上一段末尾、以换行分隔，此处单独处理为一句。 |
| 187 | reading_jijing_83_test_95_p3 G-05 | I：不据此认定源文错误 | Early State 是原文中的小节标题，紧跟上一段末尾、以换行分隔，此处单独处理为一句。 |
| 188 | reading_jijing_84_test_73_p3 F-04 | I：不据此认定源文错误 | there was 后省略了并列部分的谓语，and 后完整应为 there was an initial [k]...。 |
| 189 | reading_jijing_84_test_73_p3 F-05 | I：不据此认定源文错误 | as if it were tempory 使用虚拟语气，表示“仿佛……一样”，实际发音已接近tempory但拼写未变。 |
| 190 | reading_jijing_85_test_12_p1 B-02 | I：不据此认定源文错误 | OzKleen 是 cleaning products business 的同位语；原文金额未标明货币单位。 |
| 191 | reading_jijing_85_test_12_p1 F-08 | R：待分类 | produced in the liquid 是过去分词短语，修饰 foam；句末 effectively- 的连字符用作破折转引，排版不规范。 |
| 192 | reading_jijing_85_test_12_p1 G-02 | I：不据此认定源文错误 | 本句开引号要到后续引语结束才闭合，因此此处没有右引号是原文连续引语结构。 |
| 193 | reading_jijing_85_test_12_p2 H-04 | R：待分类 | too...that... 是程度结果状语结构，正常应为 too short so that，此处省略了 so，直接用 that 引出结果。 |
| 194 | reading_jijing_88_test_98_p1 F-01 | I：不据此认定源文错误 | and 后的并列部分省略了谓语，完整应为 areas adjacent to vegetables are irrigated with...。 |
| 195 | reading_jijing_88_test_98_p1 H-02 | I：不据此认定源文错误 | than 后省略了 earns，完整应为 than a bean or maize grower earns in a whole season。 |
| 196 | reading_jijing_88_test_98_p2 K-03 | I：不据此认定源文错误 | is not 后面省略了 universal，完整应为 is not universal，即人们对这些倾向的自我意识并不普遍。 |
| 197 | reading_jijing_91_test_49_p1 C-01 | I：不据此认定源文错误 | 句末的引号是原文排版遗留的痕迹，与下一句共同构成一段引语。 |
| 198 | reading_jijing_91_test_49_p3 F-06 | I：不据此认定源文错误 | 全句为倒装结构，正常语序应为 Some personal stories...were also included，表语提前使叙述更连贯地衔接上文。 |
| 199 | reading_jijing_92_test_58_p2 E-03 | R：待分类 | 原文是一个名词性残句，语义承接上一句的最低用水量。 |
| 200 | reading_jijing_92_test_58_p3 E-01 | R：待分类 | instead of 后接动名词 living，与前面所偏好的放松方式形成对比；原文 prefer having to relax 搭配不自然但语义可由上下文确定。 |
| 201 | reading_jijing_92_test_58_p3 F-03 | R：待分类 | during 引出时间背景；原文 first visited 形式不合常规，但语义指女王首次访问澳大利亚。 |
| 202 | reading_jijing_92_test_58_p3 F-07 | R：待分类 | when 引导时间状语从句；原文 crushed 用法不自然，结合语境理解为大量人群涌向海滨。 |
| 203 | reading_jijing_92_test_58_p3 F-09 | R：待分类 | rather than 引出被排除的选择 Manly；原文 satisfied 修饰 destination 不自然，语义为令人满意的目的地。 |
| 204 | reading_jijing_92_test_58_p3 G-04 | R：待分类 | world over 表示“全世界范围内”；原文 the famous 不合常规，但整体语义是“闻名世界”。 |
| 205 | reading_jijing_92_test_58_p3 H-06 | R：待分类 | of having... 说明 human rights 的具体内容；原文 health life 搭配不自然，语义指健康生活。 |
| 206 | reading_jijing_9_test_81_p1 E-03 | R：待分类 | started to modified or decreased 为原文表述，意思上表示开始改变或降低支持。 |
| 207 | reading_jijing_9_test_81_p1 F-02 | R：待分类 | rabbit hibernate 为原文表述，动词未加第三人称单数 -s。 |


## 附录I：确认的34个题目残留字段

路径从对应passage的groups起算，数组下标为0基。修订编号均指最终表，questions状态表示对应源文修订是否同步题目；条目119是Street Angel格式残留，清单未把它算作错答案。对被截短的引用、普通合法词及无法证明为旧错词的命中已剔除。


| # | 条目 / questions | passage_id | JSON路径 | 残留→应有形式 |
|---|---|---|---|---|
| 1 | 138 / True | reading_jijing_18_test_53_p1 | groups[2].collect | modem → modern |
| 2 | 138 / True | reading_jijing_18_test_53_p1 | groups[2].questions[5].locating_words[0].locating_word | modem → modern |
| 3 | 228 / True | reading_jijing_40_test_75_p3 | groups[0].questions[1].locating_words[0].syn_ary[0].synonym | Refer-ence → Reference |
| 4 | 229 / False | reading_jijing_40_test_75_p3 | groups[0].questions[1].locating_words[0].syn_ary[0].target_sen[0].target_sen | end → out |
| 5 | 237 / True | reading_jijing_40_test_75_p3 | groups[0].questions[2].central_sentences[0].sentence | certificaion → certification |
| 6 | 241 / True | reading_jijing_40_test_75_p3 | groups[0].questions[4].analysis | hypothrsie → hypothesise  |
| 7 | 241 / True | reading_jijing_40_test_75_p3 | groups[1].questions[4].analysis | hypothrsie → hypothesise  |
| 8 | 241 / True | reading_jijing_40_test_75_p3 | groups[1].questions[4].locating_words[3].syn_ary[0].synonym | hypothrsie → hypothesise  |
| 9 | 249 / False | reading_jijing_46_test_84_p1 | groups[1].questions[0].central_sentences[0].sentence | (China → China |
| 10 | 249 / False | reading_jijing_46_test_84_p1 | groups[1].questions[0].locating_words[0].syn_ary[0].target_sen[0].target_sen | (China → China |
| 11 | 249 / False | reading_jijing_46_test_84_p1 | groups[1].questions[0].locating_words[1].syn_ary[0].target_sen[0].target_sen | (China → China |
| 12 | 263 / False | reading_jijing_48_test_21_p3 | groups[0].questions[0].analysis | 6oC → 6°C |
| 13 | 263 / False | reading_jijing_48_test_21_p3 | groups[0].questions[0].locating_words[0].syn_ary[2].target_sen[0].target_sen | 6oC → 6°C |
| 14 | 298 / True | reading_jijing_5_test_59_p1 | groups[2].questions[2].analysis | unsuccessfull → unsuccessful |
| 15 | 298 / True | reading_jijing_5_test_59_p1 | groups[2].questions[2].locating_words[0].syn_ary[0].synonym | unsuccessfull → unsuccessful |
| 16 | 302 / True | reading_jijing_5_test_59_p2 | groups[2].questions[2].locating_words[3].syn_ary[1].synonym | coee → coffee |
| 17 | 418 / True | reading_jijing_82_test_4_p3 | groups[1].questions[3].locating_words[0].syn_ary[0].synonym | 1070s → 1970s |
| 18 | 427 / False | reading_jijing_84_test_73_p2 | groups[2].questions[3].analysis | nearbyfriends → nearby friends |
| 19 | 427 / False | reading_jijing_84_test_73_p2 | groups[2].questions[3].central_sentences[0].sentence | nearbyfriends → nearby friends |
| 20 | 427 / False | reading_jijing_84_test_73_p2 | groups[2].questions[3].locating_words[1].syn_ary[0].target_sen[0].target_sen | nearbyfriends → nearby friends |
| 21 | 427 / False | reading_jijing_84_test_73_p2 | groups[2].questions[3].locating_words[2].syn_ary[0].synonym | nearbyfriends → nearby friends |
| 22 | 427 / False | reading_jijing_84_test_73_p2 | groups[2].questions[3].locating_words[2].syn_ary[0].target_sen[0].target_sen | nearbyfriends → nearby friends |
| 23 | 463 / True | reading_jijing_92_test_58_p1 | groups[0].questions[5].central_sentences[0].sentence | dierent → different |
| 24 | 463 / True | reading_jijing_92_test_58_p1 | groups[0].questions[5].locating_words[1].syn_ary[0].target_sen[0].target_sen | dierent → different |
| 25 | 510 / False | reading_jijing_18_test_53_p2 | groups[1].questions[1].locating_words[3].syn_ary[0].target_sen[0].target_sen | was, → was  |
| 26 | 518 / False | reading_jijing_22_test_90_p3 | groups[0].questions[3].locating_words[2].syn_ary[0].target_sen[1].target_sen | potential, →  potential. |
| 27 | 521 / True | reading_jijing_23_test_46_p1 | groups[0].questions[3].locating_words[0].syn_ary[1].synonym | Green Peace → Greenpeace |
| 28 | 521 / True | reading_jijing_23_test_46_p1 | groups[2].questions[2].locating_words[0].syn_ary[0].synonym | Green Peace → Greenpeace |
| 29 | 521 / True | reading_jijing_23_test_46_p1 | groups[2].questions[2].locating_words[0].locating_word | Green Peace → Greenpeace |
| 30 | 540 / True | reading_jijing_40_test_75_p3 | groups[1].questions[0].locating_words[2].syn_ary[1].synonym | may be → maybe |
| 31 | 540 / True | reading_jijing_40_test_75_p3 | groups[1].questions[1].locating_words[2].syn_ary[1].synonym | may be → maybe |
| 32 | 557 / True | reading_jijing_50_test_30_p2 | groups[2].questions[0].locating_words[1].syn_ary[0].synonym | catching → caching |
| 33 | 569 / True | reading_jijing_65_test_69_p2 | groups[0].questions[2].locating_words[0].syn_ary[0].synonym | stablize → stabilize |
| 34 | 119 / True | reading_jijing_13_test_6_p2 | groups[1].questions[1].locating_words[0].syn_ary[1].synonym | Street Angel(1937) → Street Angel (1937) |

同义词字段只是不显示的存量数据，并非无须同步的依据；原文/答案依据一致性与是否渲染是两个检查。第一、二轮63条未启用questions的既披露问题未混入以上第四轮遗漏计数。


## 已披露遗留的独立评估

- 63条旧修订未同步groups属实；不把其所有旧引用再列成新问题。当前第三/四轮窗口覆盖不足另见N2。
- unknown不是本轮新增；两个既有异常成分（76_43_p2 D-02顺序、85_12_p3 B-02 level 5）未被本轮顺手改掉，仍应另行治理。
- ielts18_test3_p3同一句定位词含`\x02`，在groups[2].questions[1].locating_words[1].syn_ary[0/1].target_sen[0].target_sen两个字符串出现；是1种坏句、2个存储字段，不是机经修订表范围，当前页面不读该定位词字段。
- 92_58_p2 H-01小标题连正文仍带heading而被排除出题，未伪称已拆好。
- 既有引语跨从句边界造成不成对标点的情况，不能一律向外补到别的成分；数字引语尾引号是另一具体旧问题，已在结论单列。
- 第五、六节无法确定源文的保留策略可接受，但交付时应同时区分“未擅改原文”和“适合做题”，见A3。

## 复现方法补充（不依赖本机未提交脚本）

所有审计脚本只在仓库外。下面给出核心遍历/抽样定义；本报告列出了完整样本ID和路径，跨电脑可从固定提交直接核对，仓库不额外新增脚本。

```python
# groups差异计数：按相同JSON路径比较字符串，不把生成时间或整个JSON算一次变化。
def strings(x, path=()):
    if isinstance(x, str):
        yield path, x
    elif isinstance(x, dict):
        for k, v in x.items():
            yield from strings(v, path + (k,))
    elif isinstance(x, list):
        for k, v in enumerate(x):
            yield from strings(v, path + (k,))
old, new = dict(strings(old_passage['groups'])), dict(strings(new_passage['groups']))
changes = [(p, old[p], new[p]) for p in old.keys() & new.keys() if old[p] != new[p]]
# 跨全部篇章累计len(changes)；set((before,after))统计完整字符串对。
# sentences按(passage_id,id)匹配，比较时只去sentence_index；删除ID独立计数。
# 抽题：各池先sorted(..., key=lambda i:i['item_id'])，再random.Random(20261027).sample。
```

内存重建实际调用build_reading_test_practice.build_tests(raw, 'jijing')；图片函数仅返回同样本地路径，未请求图片。只比较每篇paragraphs和groups，排除生成时间；171篇均相等。顺序回放从f9原样static起，按修订表逐条apply_passage_fixes，对questions替换前所有find出现检查左右词边界，随后重复应用全表验证幂等。

T5括号边界探针曾以原subject原子span为上界，产生11处假越界；按实现既有完整主语区间`[tag_span.start, predicate_start)`重新核对为0。T2/T3/T4仍以各自原span为界。这一更正防止把已有完整主语提取规则误判成本轮括号补全越界。

## Git / CI / 交接状态

审核正文提交 **9827b8513bb44615d5a79a2574258ee8138317e1** 已推送到 `codex/grammar-item-candidates`，`git ls-remote`核对同SHA。GitHub [CI 40261776632](https://github.com/KB77GG/studytracker/actions/runs/40261776632) 已完成：

- **test：success**；轻量单测与Node拼写队列均成功。
- **lint：failure（advisory）**；Ruff check报存量问题，后续format步骤skipped。其continue-on-error使workflow整体success，不将整体绿色写成lint通过。改动Python文件的本地对照结果见第18项。

本段及两份交接由后续纯文档提交补记，同样不带skip-ci标记；最终提交SHA及其CI结果在最终用户汇报提供，并可用 `git log -1` / `gh run list --branch codex/grammar-item-candidates --workflow ci.yml` 查询。被审核代码、数据和四份交付保持1f03c84。唯一作者改动是本报告、CODEX_HANDOFF与WORKLOG。未推main、未部署、未开PR，未操作生产服务器/生产数据库，未上传/提审/发布小程序。
