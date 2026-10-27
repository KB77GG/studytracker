# 语法候选题 v0.2 第十四轮独立复审（Codex）

审核日期：2026-10-27，Asia/Shanghai。**结论：不通过，以剑桥题为准。** 本轮点名的 Z1、Z2 和 Z3 的 provided 干扰项已修复；Z4–Z6 的指定更正和收窄也已复现。新增 **0 阻断、2 应修（AA1、AA2）、1 建议（AA3）**，涉及 **5 道剑桥 auto_pass、3 个来源句**。AA1 中两题明确漏掉 encountered，两题的被动分析尚需复核；AA2 是 given that 的教学类别没有贯通 T1/T6，不能一边排除其动词身份、一边自动判定为非谓语。没有修改被审代码、数据、原标注或交付文件。

这不是声称本轮引入了5道新错题：这些题及其状态在第十三轮已存在。given that 上轮仅作口径建议；本轮新增函数已经明确采用“given + that(mark) 是连词”的标准，却未应用到 T6，因此本次把**未统一口径仍自动通过**列为应修。与用户已披露的 `given the right context`（没有 that）不是同一检查。

随机抽查120题全是当前auto：119题的所给局部答案/高亮未见错误，1题漏词（AA1）；其中另1题有既有A8的非并列从句定位歧义，不宣称119题全部可以唯一判分。原句均可作为阅读材料；不合格的是题目处理，不是原文。待复核题在下文单独统计，不计入自动题通过数。机经本轮记录3项，单列暂缓，不计入上述分级数量。

## 1. 范围、事实源与关闭情况

- 工作树：`/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker`，分支 `codex/grammar-item-candidates`。
- 入口已读目录链 AGENTS、仓库 CLAUDE、CODEX_HANDOFF最新两节、WORKLOG顶部，并用实际Git核对。开始HEAD `8a82138817f128554f9dec6c2c8ed71d4d1dba12`、工作树干净。
- 按授权fetch源分支，ff-only成功到 **`32574773d098ebbf357779dea764c4b8a47e6e37`**；只审 `8a82138..3257477`。未普通merge/rebase/改写历史。
- 范围共11文件，672插入/417删除：4个Python、4份交付文件、3份文档。阅读解析/raw/static/修订表/models/app/api/miniprogram/workflows均零改动。4个新增/改动规则逐个AST检查，不读取 passage_id/sentence_id/item_id；候选ID生成器本来的身份字段不属于规则黑名单。
- 本轮独立生成及辅助文件均在仓库外 `O=/Users/zhouxin/.codex/audits/grammar-v02-round14-20261027`。审计脚本/日志/SQLite/快照仅本机，报告与两交接提交到任务分支。

| 编号 | 是否关闭 | 独立结论 |
|---|---|---|
| Z1 | 点名3题关闭 | live up to三题全部needs；本轮无额外剑桥误降。非相邻RP边界仍未扩大，机经出现一组保守误降，见J1。 |
| Z2 | 点名问题关闭 | roasted、updated需复核，designed有两种合理分析，保守送审可接受。原18例其余15题逐字段不变。VBG等范围仍有限，见控制例。 |
| Z3 | 点名T1关闭；同类T6尚未关闭 | B-03忽略provided后主答案/余下干扰项正确；given that T6仍auto，见AA2。不能把点名修复扩大说成所有词汇化连词已统一。 |
| Z4 | 文档更正关闭 | 旧负测实为5断言失败/2接口错误/2通过；is整词一次、fish内子串一次。ambiguous实现未改，保守误降保留。 |
| Z5 | 关闭 | 文档正确改为保守送审，未断言77题原答案全错；by达到十次但多是介词的排除理由写入注释。 |
| Z6 | 指定反例关闭 | Did not the team win?保留not；全库排除集合仍15处，9/3/3分组一致。or not do的潜在反例见机经J2，不混称15次排除全部语义正确。 |

## 2. 十项检查与实际命令

以下简称R为上述工作树，G为`$R/.venv-grammar-tools/bin/python`，P为`/Users/zhouxin/Desktop/studytracker/.venv/bin/python`，N为`/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`。只借用桌面venv，不在桌面工作树改文件。

| 项 | 结果 | 实际执行/证据 |
|---|---|---|
| 1 | 通过 | `git status --short --branch`、`git log -5 --oneline`；`git fetch origin claude/word-memorization-system-eval-55v2y5`；`git merge --ff-only 32574773d098ebbf357779dea764c4b8a47e6e37`；`git diff --stat 8a82138..3257477`；`G O/audit_data.py`检查白名单、AST、数据不变。 |
| 2 | 指定范围通过 | `G O/probe_rules.py`全库RP扫描及前后池比对；3道live up to全部needs，见§4。 |
| 3 | 指定范围通过 | `G O/probe_followup.py`重读原18例、扩大到其他词形共享首项助动词；`G O/controls.py`实际本地解析反例，见§5。 |
| 4 | 点名通过、存在AA2/AA3 | 全库词表定位249处，19处匹配“词+that(mark)”；逐一辨别引导表达与真动词，见§6。 |
| 5 | 通过（有限范围） | 原/新correlative_not逐token比较；15处集合完全相同；旧负测证据和第十三轮三处文字更正复核，见§7。 |
| 6 | 未通过内容质量 | `G O/audit_runtime.py`按seed20261103生成120题清单；逐题人工判断；新增“be被误作中心、被动分词遗漏”扫描，62题逐题辨别，见§8–9。 |
| 7 | 数值全部复现 | 前后50243候选字典按item_id比较：零增删；8个降级、3个distractors变化，其余字段全等，见§10。 |
| 8 | 通过 | `G O/generate.py`在完整325快照中连续两次执行`G scripts/generate_grammar_candidates.py --seed 20261018`；`G O/audit_runtime.py`逐字节比较、核78回归/7过滤、解析xlsx全部单元格/下拉/盲审，见§11。 |
| 9 | 通过 | `G O/run_checks.py`运行本节所列全部测试；`G O/negative_tests.py`旧35代码运行7项新测试；`G O/audit_data.py`raw171与图谱，见§12。 |
| 10 | 通过 | `P O/import_snapshot.py O/main main`然后`P O/import_snapshot.py O/source current`：完整676569c先建317，再更新236/跳过81/失败0，见§13。 |

辅助脚本首轮执行曾因候选字段名误用parser_evidence（实际为evidence）、旧扫描记录外层有item键而报KeyError；只修正仓库外审计脚本后重跑成功，没有变更被审实现，也未把这两次探针错误算作产品测试失败。完整命令参数和生成根路径见下文；云端复核可直接用相同commit运行正式CLI，再按报告中的题号定位。

## 3. 剑桥问题清单

### AA1 — 应修：解析器把be提升为中心，遗漏被动分词的T1/T6仍自动通过

位置：`scripts/grammar_items/templates.py:598`、`:939`、`verb_unit():245`；来源 `data/reading_study/ielts14_test3_p2.json:928`、`ielts14_test2_p2.json:1418`。

| 来源 | 题号 | 当前答案/高亮 | 独立判断 |
|---|---|---|---|
| 14_3_p2 F-06 | gi_v02_7009c768706e（T1）、gi_v02_d765c317f6a7（T6） | are | `are infrequently encountered`是“很少被发现/接触”的被动谓语；至少应显示are / encountered。解析器给are=ROOT、encountered=VERB/VBN/dep，后者被漏掉。T6身份选项“主句谓语”可以成立，但高亮不符合完整动词单位要求；T1只认are并不能接受完整的词汇谓语。2题不应auto。 |
| 14_2_p2 H-02 | gi_v02_56671bb1833d（T1）、gi_v02_108f07638465（T6） | is | 原文`is naturally ventilated, passively cooled and naturally lit`；原标注及难点明确按三个并列被动描述。只显示is没有检验被动单位/并列谓语。也存在建筑属性的形容词式分析，所以不武断断言唯一改答；2题应复核口径，不能仅凭is为ROOT就自动通过。 |

复现：生成全池，按以上4题号读取answer/target，缓存查看be与VBN的依存；与原句/原结构对照。第十三轮同4题内容/状态相同，非本轮引入。随机120题包含F-06的T6。

建议：新增通用的“be后有未进入单位的动词性分词/被动分析冲突”复核信号，同时检查T1和T6；在T1答案冻结的约束下先降级，不擅自重写答案。区分`is used to`、`is terrified`、`family-owned`、表语that/what从句等合法系表结构，不能把本次62个预筛结果全部当错误。若将来要改答案，应让词汇谓语中心与被动助动词正确组合，并专测混合并列与多谓语。

### AA2 — 应修：given that已按连词过滤T1，T6却仍自动判为非谓语

位置：`templates.py:261`、`:531`、`:934`；`ielts18_test2_p3 C-03`，`gi_v02_31a694497b01`，当前auto，目标`given`，答案“非谓语（不定式、分词、动名词）”。

复现：本句`conjunction_participle(view, given)`返回True，仍生成auto的T6；provided that的对应T6则因finiteness_mismatch在needs。新规则只接入main_distractors，没约束T6。这不是指所有given均非动词，也不是已披露的given + 名词短语问题。上轮保留了历史分词来源的解释争议；本轮既选择连词口径，应对相同结构贯通，至少在未统一前送审。Oxford将这个固定引导表达列为连词，支持“不能无条件自动判为动词”的复核要求：[Oxford given that](https://www.oxfordlearnersdictionaries.com/definition/english/given-that)。

建议：在T6检查同类固定引导表达，作为词类/题干前提不确定送审，或统一标注与出题白名单；不要硬把所有given/assuming当连词。保留真正被动given、assuming/seeing带宾语从句的动词用法控制例。本项只计1道剑桥auto；另外7道同模式T6本来已needs，不算新增错题。

### AA3 — 建议：分词+that(mark)不足以判断连词，当前宽词表会命中真动词

位置：`templates.py:261`。实际反例`He granted that the plan might fail.`的granted、`I am assuming that he will come.`的assuming都返回True；它们仍是“承认/正在假定”的动词。真实语料`ielts18_test4_p3 B-01`的`rather than supposing that ...`也返回True，supposing是与supposed对照的假定行为，不是条件连词。

目前前后池仅3项干扰项改变，均为真正引导表达，没有确认因这条宽判新增的剑桥错题；删去一个合法可选干扰项也不必然破坏主答案，故分级建议。建议先看谓语/非谓语在句中的作用、自己的助动词/主语/介词支配，再决定是否是固定连词；补上述正反例，不能把that的mark身份当作前词词性的充分条件。

## 4. Z1：RP漏入单位的逐题复核

条件与目标一致：只检查显示单位里的VERB/AUX，其直接子节点必须紧挨、尚未进入单位、依存非prt；advmod词表或RP触发。它是解析风险信号，不是“RP一定应并入”的语义断言。全库查得26个RP且非prt挂动词的token；能落到现有T1/T6显示内容的来源如下。剑桥新增只有指定3题，其余现状保留。

| 来源 | 词对 | child依存 | 相邻 | 题号/当前状态 | 判定 |
|---|---|---|---|---|---|
| ielts10_test4_p2 G-06 | hold back | advmod | 否 | gi_v02_73e53f470ca2 auto_pass | hold joy back被宾语隔开；已披露边界，auto不变，不算本轮新增 |
| ielts13_test4_p1 E-04 | lived up | prep | 是 | gi_v02_e7f5ca02117f needs_review; gi_v02_9bf2469ce8c1 needs_review | 相邻非prt/RP；现已needs，需确认完整单位 |
| ielts16_test2_p3 H-02 | wrote down | advmod | 是 | gi_v02_095923e43569 needs_review; gi_v02_05e6a3ca1a02 needs_review | 相邻非prt/RP；现已needs，需确认完整单位 |
| ielts4_test1_p3 E-21 | had on | ccomp | 否 | gi_v02_d60aedeca103 auto_pass | had its brakes on：宾语补足位置，不紧挨；不应仅凭RP扩大单位 |
| ielts5_test3_p3 E-35 | lives up | prep | 是 | gi_v02_100095519c58 needs_review | 相邻非prt/RP；现已needs，需确认完整单位 |
| ielts5_test4_p2 J-42 | went up | advmod | 是 | gi_v02_b3f97a4a3760 needs_review; gi_v02_5b0ae189651e needs_review | 相邻非prt/RP；现已needs，需确认完整单位 |
| ielts9_test3_p3 A-07 | sent out | advmod | 是 | gi_v02_057e273a9e42 needs_review; gi_v02_6976a217d6d3 needs_review | 相邻非prt/RP；现已needs，需确认完整单位 |
| reading_jijing_40_test_75_p3 G-03 | draw in | prep | 是 | gi_v02_36ad7ce3631a needs_review; gi_v02_8c1ace89792f needs_review | in deciding是介词结构，不是draw in；保守误降，机经J1 |
| reading_jijing_84_test_73_p2 F-36 | gets up | ccomp | 否 | gi_v02_bb4ff9662907 auto_pass; gi_v02_f0871c08819d auto_pass | 非相邻；未扩大规则，机经暂缓范围 |
| reading_jijing_92_test_58_p3 E-05 | sweeping out | prep | 否 | gi_v02_58d1b29f0f06 auto_pass | 非相邻；未扩大规则，机经暂缓范围 |

三道点名题均只有particle_outside_unit原因。lived/lives的主句/从句身份可成立，缺up所以高亮需复核；不能将needs标为答案已经修正。实际控制句`go on a hike`、`carried the bags on their backs`均不触发，正常介词受保护。`held their joy back`不触发是明确边界，非已覆盖。

## 5. Z2：18个旧候选及范围探针

`shared_auxiliary`在non_finite分支调用：VBN、conj、无自有aux/auxpass，沿conj到首项，该首项有非to助动词才送审。这个条件适合作保守风险筛选，不证明每个命中都是省略助动词。designed的后置分词说明与共享are均可理解，因此新增needs合理；roasted/updated原答案确实忽略了can be/must be的共享或省略。

| 题号 | 来源 | 高亮 | 前→后 | 判定 |
|---|---|---|---|---|
| gi_v02_180f5b7bfbf3 | ielts10_test4_p3 I-04 | reversing | auto_pass → auto_pass | 结果/补充说明的-ing分词，非谓语答案成立；逐字段未变 |
| gi_v02_bb437aa4b900 | ielts11_test1_p1 E-02 | reducing | auto_pass → auto_pass | 结果/补充说明的-ing分词，非谓语答案成立；逐字段未变 |
| gi_v02_173f4b836393 | ielts12_test6_p2 B-02 | cutting | auto_pass → auto_pass | 结果/补充说明的-ing分词，非谓语答案成立；逐字段未变 |
| gi_v02_c5f8bfba90e2 | ielts12_test6_p3 A-03 | identifying | auto_pass → auto_pass | 结果/补充说明的-ing分词，非谓语答案成立；逐字段未变 |
| gi_v02_1ad93e498bd5 | ielts12_test8_p1 C-03 | adding | auto_pass → auto_pass | 结果/补充说明的-ing分词，非谓语答案成立；逐字段未变 |
| gi_v02_e308d4a8777f | ielts13_test2_p3 D-05 | infusing | auto_pass → auto_pass | 结果/补充说明的-ing分词，非谓语答案成立；逐字段未变 |
| gi_v02_526d2a4edcd0 | ielts14_test4_p1 E-02 | showing | auto_pass → auto_pass | 结果/补充说明的-ing分词，非谓语答案成立；逐字段未变 |
| gi_v02_86b996fd1f46 | ielts15_test4_p1 F-05 | roasted | auto_pass → needs_review | 省略can be；不应自动判非谓语，needs成立 |
| gi_v02_5bb62dffbbf7 | ielts15_test4_p3 G-03 | to reward | auto_pass → auto_pass | to reward与前文不定式并列，非谓语；逐字段未变 |
| gi_v02_5f825d2822fa | ielts16_test1_p1 C-03 | depending | auto_pass → auto_pass | 结果/补充说明的-ing分词，非谓语答案成立；逐字段未变 |
| gi_v02_cffbc50169cf | ielts17_test1_p2 D-03 | designed | auto_pass → needs_review | 共享are或后置分词说明两可；保守needs成立 |
| gi_v02_42b61e4eac46 | ielts17_test1_p3 A-03 | accepting | auto_pass → auto_pass | 结果/补充说明的-ing分词，非谓语答案成立；逐字段未变 |
| gi_v02_dfd8b52356bb | ielts17_test4_p1 C-01 | making | auto_pass → auto_pass | 结果/补充说明的-ing分词，非谓语答案成立；逐字段未变 |
| gi_v02_330fff562bff | ielts17_test4_p3 E-07 | updated | auto_pass → needs_review | 共享must be；不应自动判非谓语，needs成立 |
| gi_v02_b6a8303441af | ielts19_test2_p1 E-03 | enabling | auto_pass → auto_pass | 结果/补充说明的-ing分词，非谓语答案成立；逐字段未变 |
| gi_v02_7ebb46e41faa | ielts4_test1_p1 B-02 | making | auto_pass → auto_pass | 结果/补充说明的-ing分词，非谓语答案成立；逐字段未变 |
| gi_v02_63d9298d36e1 | ielts8_test1_p1 G-03 | allowing | auto_pass → auto_pass | 结果/补充说明的-ing分词，非谓语答案成立；逐字段未变 |
| gi_v02_32dd0bb613c1 | ielts8_test3_p2 A-04 | derived | auto_pass → auto_pass | 修饰attributes的过去分词，非谓语；逐字段未变 |

其中15道auto维持原内容（13个-ing、to reward、derived），3道needs单列，未把后者算“全部正确”。更宽扫描所有剑桥T6非谓语的conj首项助动词，10题命中；除了上述3题，还有reducing/cutting/infusing/depending/making和to reward/to make，逐题均为结果分词或不定式，本轮未误降。没有在该筛选集合发现新的VBG共享助动词漏网。

反例仍有：实际解析`He is singing and dancing.`的dancing为VBG/conj，函数False；`The seeds can be dried and roasted.`的roasted为True；`thereby avoiding`与`to look and listen`不命中。因此只能关闭点名VBN缺口，不能宣称全部词形的省略都解决。

## 6. Z3：干扰项、词汇化引导表达和反例

| 题号 | 来源 | 当前状态 | 主答案 | 原干扰项 | 现干扰项 | 判定 |
|---|---|---|---|---|---|---|
| gi_v02_328b5d2797b9 | reading_jijing_88_test_98_p1 J-03 | auto_pass | could; be; alleviated | was; provided; lived; could find; bartering; dried | was; lived; could find; bartering; dried | 删除provided/Considering合理；剩余项依照原句判读 |
| gi_v02_aa9399af40a2 | reading_jijing_69_test_40_p2 B-04 | auto_pass | have; become | Considering; are obtained | are obtained | 删除provided/Considering合理；剩余项依照原句判读 |
| gi_v02_b16884621b7b | ielts15_test4_p3 B-03 | auto_pass | ignores | are not; provided; do | are not; do | 删除provided/Considering合理；剩余项依照原句判读 |

B-03主答案ignores；are not是that内容从句里的谓语，do是条件从句里的谓语，都是合适干扰项。provided by / was provided / provided an ...在实际解析和新测试中均保留为动词。

以下19处是全库249个词表token中的**形态规则命中**，不是19个确认连词。匹配之后没有候选的行也列出，以免把“未进入题目”当作规则精准。

| 序 | 来源 | 词 | 当前题 | 判定 |
|---|---|---|---|---|
| 1 | ielts10_test2_p2 D-07 | Given | gi_v02_d7b85db07823 needs_review | 固定条件/原因/假设引导表达，可按连词口径处理 |
| 2 | ielts15_test4_p3 B-03 | provided | gi_v02_1892e239a5c5 needs_review | 固定条件/原因/假设引导表达，可按连词口径处理 |
| 3 | ielts18_test2_p2 F-04 | given | 当前无该词的T6/干扰项 | 固定条件/原因/假设引导表达，可按连词口径处理 |
| 4 | ielts18_test2_p3 C-03 | given | gi_v02_31a694497b01 auto_pass | 固定条件/原因/假设引导表达，可按连词口径处理；T6仍auto，AA2 |
| 5 | ielts18_test4_p3 B-01 | supposing | 当前无该词的T6/干扰项 | rather than支配supposing，真动词性分词；规则过宽（AA3） |
| 6 | ielts7_test1_p1 A-05 | Given | gi_v02_268ca701fe44 needs_review | 固定条件/原因/假设引导表达，可按连词口径处理 |
| 7 | ielts7_test1_p1 A-05 | given | 当前无该词的T6/干扰项 | 固定条件/原因/假设引导表达，可按连词口径处理 |
| 8 | reading_jijing_10_test_78_p2 C-24 | Given | gi_v02_acd827aad052 needs_review | 固定条件/原因/假设引导表达，可按连词口径处理 |
| 9 | reading_jijing_13_test_6_p2 B-08 | assuming | 当前无该词的T6/干扰项 | for assuming的动名词行为，非连词 |
| 10 | reading_jijing_18_test_53_p2 G-05 | Seeing | 当前无该词的T6/干扰项 | Seeing that...作主语，意为确保；非原因连词 |
| 11 | reading_jijing_44_test_29_p2 E-04 | given | gi_v02_293b0aaff89a needs_review | 固定条件/原因/假设引导表达，可按连词口径处理 |
| 12 | reading_jijing_53_test_83_p2 E-04 | assuming | 当前无该词的T6/干扰项 | 固定条件/原因/假设引导表达，可按连词口径处理 |
| 13 | reading_jijing_62_test_44_p3 I-04 | granted | 当前无该词的T6/干扰项 | take it for granted固定动词结构，非连词 |
| 14 | reading_jijing_62_test_44_p3 K-05 | granted | 当前无该词的T6/干扰项 | take it for granted固定动词结构，非连词 |
| 15 | reading_jijing_69_test_40_p2 B-04 | Considering | gi_v02_2a9cd011998d needs_review | 固定条件/原因/假设引导表达，可按连词口径处理 |
| 16 | reading_jijing_77_test_16_p2 F-01 | assuming | 当前无该词的T6/干扰项 | by assuming支配，真动词性分词；非连词 |
| 17 | reading_jijing_83_test_95_p1 D-06 | Given | 当前无该词的T6/干扰项 | 固定条件/原因/假设引导表达，可按连词口径处理 |
| 18 | reading_jijing_88_test_98_p1 J-03 | provided | gi_v02_1495cbe1f52c needs_review | 固定条件/原因/假设引导表达，可按连词口径处理 |
| 19 | reading_jijing_9_test_81_p2 I-10 | Given | gi_v02_4490077dd6af auto_pass | 固定条件/原因/假设引导表达，可按连词口径处理；T6仍auto，机经J3 |

只有9道现有T6直接指向上述词：剑桥3needs/1auto、机经4needs/1auto。7道needs不能算修正后正确；其中provided仍被机器答“从句谓语”，但被finiteness_mismatch隔离。带that的given auto是AA2/J3。其他不带that的given + NP用法沿用已披露的教学口径问题，不新计。

`provided they comply`实际解析函数False，确是可能漏掉的条件连词；全库provided/providing上下文检索未发现这样的现有剑桥自动题。`seeing that`实际控制句命中，语料中Seeing作主语那例反而说明不能只看词形。没有发现未带that的provided需要立即新增的剑桥点名题。

## 7. Z4–Z6：更正及15处not

第十三轮负测行已经更正为5断言失败/2接口错误/2通过，Y3控制例和A8单分句控制例均缺新Reason常量；is/fish解释已准确；Y3额外77题改为保守送审，明确was over的补足不等于谓语不完整。by未收的代码注释与解释一致。

原/新函数遍历全部句子所有token，排除集合完全相同：or后9处（whether or not 8、or not do 1）、mark前3处、wh前3处。以下是逐项语义判读，不把数量相等替代质量检查。

| 来源 | 位置类别 | 原挂靠动词 | 判定 |
|---|---|---|---|
| ielts11_test1_p2 E-03 | or | carrying | not作用于选择/引导结构，不作为该词汇谓语的内部否定 |
| ielts11_test2_p1 E-05 | or | salvage | not作用于选择/引导结构，不作为该词汇谓语的内部否定 |
| ielts11_test2_p2 A-09 | wh | moved | not作用于选择/引导结构，不作为该词汇谓语的内部否定 |
| ielts11_test4_p3 B-01 | mark | came | not作用于选择/引导结构，不作为该词汇谓语的内部否定 |
| ielts12_test6_p2 D-02 | mark | sees | not作用于选择/引导结构，不作为该词汇谓语的内部否定 |
| ielts14_test2_p3 H-04 | or | work | not作用于选择/引导结构，不作为该词汇谓语的内部否定 |
| ielts5_test1_p2 A-02 | or | have | not作用于选择/引导结构，不作为该词汇谓语的内部否定 |
| ielts5_test3_p3 E-35 | or | lives | not作用于选择/引导结构，不作为该词汇谓语的内部否定 |
| ielts7_test1_p1 C-08 | or | is | not作用于选择/引导结构，不作为该词汇谓语的内部否定 |
| reading_jijing_10_test_78_p1 I-51 | or | was | not作用于选择/引导结构，不作为该词汇谓语的内部否定 |
| reading_jijing_10_test_78_p3 E-05 | wh | supposed | not作用于选择/引导结构，不作为该词汇谓语的内部否定 |
| reading_jijing_24_test_56_p2 B-02 | or | be | not作用于选择/引导结构，不作为该词汇谓语的内部否定 |
| reading_jijing_24_test_56_p3 B-03 | wh | identified | not作用于选择/引导结构，不作为该词汇谓语的内部否定 |
| reading_jijing_27_test_33_p3 D-09 | or | do | not do是真否定，误排除；本句未生成do相关题且全句source_quality，机经J2 |
| reading_jijing_53_test_83_p2 E-05 | mark | is | not作用于选择/引导结构，不作为该词汇谓语的内部否定 |

`Did not the team win?`现在单位Did/not/win；did not come、decided not to go均保留not。这个收窄关闭Z6点名的否定倒装反例。实际控制句`He chose to do it or not do it.`仍会丢后一个do的not，说明“紧跟or就排除”有独立边界；现有同形机经没有因此自动出错题，见J2。

## 8. 随机120题明细（全部当前auto）

抽样方法：从本机重新生成的50243题中，仅留`source_kind == reading_test`、`passage_id.startswith('ielts')`、`status == auto_pass`。每个模板按item_id升序，使用同一个`random.Random(20261103)`，按T1–T6顺序各sample20。没有换种子、没有挑掉命中题。

```python
rng = random.Random(20261103)
sample = [i for template in TEMPLATES
          for i in rng.sample(sorted(
              [i for i in pool if i['template'] == template
               and i['status'] == 'auto_pass'
               and i['source']['source_kind'] == 'reading_test'
               and i['source']['passage_id'].startswith('ielts')],
              key=lambda i: i['item_id']), 20)]
```

T1检查全部已给干扰项（不要求穷举句中每一个动词）；T2检查连词序号/目标边界/类别与唯一性；T3/T4检查题干类别前提；T5检查修饰语与同位语；T6检查身份及完整高亮。原句是否适合和题目是否能直接使用分别判断。

### T1（20道auto）

| 序 | 题号 | 来源 | 答案/高亮 | 人工判定 | 原句/使用 |
|---|---|---|---|---|---|
| 1 | gi_v02_165fe5bf9692 | ielts19_test3_p3 C-02 | featured | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：published; placed; enabled; to understand | 适合阅读；题目本次未见问题 |
| 2 | gi_v02_2477f1ad2d8d | ielts13_test1_p1 E-04 | grew | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：compared | 适合阅读；题目本次未见问题 |
| 3 | gi_v02_292a375f18a2 | ielts12_test7_p3 F-03 | arises | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：invokes; ignores | 适合阅读；题目本次未见问题 |
| 4 | gi_v02_297a31ebfd03 | ielts13_test2_p2 E-06 | could; help | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：to reduce | 适合阅读；题目本次未见问题 |
| 5 | gi_v02_332bc5582ae3 | ielts7_test3_p2 F-02 | is | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：无 | 适合阅读；题目本次未见问题 |
| 6 | gi_v02_a2b34d1a882d | ielts7_test4_p2 F-02 | certifies | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：was founded; meet; recognises | 适合阅读；题目本次未见问题 |
| 7 | gi_v02_a1ed3bc80c12 | ielts12_test6_p1 F-01 | argued | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：can help; mitigate; allow | 适合阅读；题目本次未见问题 |
| 8 | gi_v02_d9887c973976 | ielts13_test1_p1 G-05 | apply | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：based | 适合阅读；题目本次未见问题 |
| 9 | gi_v02_2212a6ded3a2 | ielts16_test1_p1 E-03 | seem | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：无 | 适合阅读；题目本次未见问题 |
| 10 | gi_v02_0e43ce75d094 | ielts12_test8_p2 F-01 | is | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：articulate; are; are | 适合阅读；题目本次未见问题 |
| 11 | gi_v02_8b4e84ae2ec7 | ielts4_test2_p3 C-19 | points; out | points out完整；so后内容可理解在that报告内容内，本题主答案成立；干扰项：increased; disappear; resulting | 适合阅读；题目本次未见问题 |
| 12 | gi_v02_42a60c5a5861 | ielts6_test4_p1 E-17 | stops | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：无 | 适合阅读；题目本次未见问题 |
| 13 | gi_v02_8ba511d10a43 | ielts8_test4_p3 C-01 | can; be; used | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：to attract; concentrate | 适合阅读；题目本次未见问题 |
| 14 | gi_v02_c5a03334c075 | ielts6_test2_p3 F-02 | contains | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：无 | 适合阅读；题目本次未见问题 |
| 15 | gi_v02_b49587329c16 | ielts18_test1_p2 D-01 | is; called | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：无 | 适合阅读；题目本次未见问题 |
| 16 | gi_v02_bb81dbbb6013 | ielts10_test2_p1 E-04 | revealed | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：was | 适合阅读；题目本次未见问题 |
| 17 | gi_v02_86321d92e084 | ielts8_test4_p3 D-06 | works | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：无 | 适合阅读；题目本次未见问题 |
| 18 | gi_v02_1ce82896782b | ielts7_test3_p3 A-02 | has; led | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：threaten | 适合阅读；题目本次未见问题 |
| 19 | gi_v02_2e01e2cbe11b | ielts17_test3_p1 E-01 | is; attributed | is / attributed完整；**为脚注标记，不是缺句；干扰项：began; continued | 适合阅读；题目本次未见问题 |
| 20 | gi_v02_76f51d530a5e | ielts20_test1_p3 A-01 | occur | 局部答案、高亮、已给干扰项及题干前提未见问题；干扰项：无 | 适合阅读；题目本次未见问题 |

### T2（20道auto）

| 序 | 题号 | 来源 | 答案/高亮 | 人工判定 | 原句/使用 |
|---|---|---|---|---|---|
| 21 | gi_v02_faf681433fe6 | ielts15_test1_p3 A-02 | what makes us human | what名词性从句边界成立，破折号后独立说明不在目标内 | 适合阅读；题目本次未见问题 |
| 22 | gi_v02_3fc055971c4d | ielts14_test4_p2 E-03 | real changes can be effected on wild populations | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 23 | gi_v02_69d13a5e084d | ielts7_test4_p3 F-01 | only transient effects were studied | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 24 | gi_v02_d40e57a8f311 | ielts17_test1_p1 A-08 | few succeeded | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 25 | gi_v02_a4352b5adaee | ielts20_test4_p3 D-18 | large numbers have been killed by farmers | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 26 | gi_v02_3bcac8e7be5c | ielts16_test1_p1 D-02 | before they started to build their dens | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 27 | gi_v02_66a1e2394202 | ielts8_test2_p3 A-04 | that many of their olfactory likes and dislikes were based on emotional associations | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 28 | gi_v02_68c3f594122f | ielts11_test4_p1 J-04 | that other things about them are different | 形式it后的that主语从句边界成立 | 适合阅读；题目本次未见问题 |
| 29 | gi_v02_953295bec7b6 | ielts7_test4_p1 B-04 | that had sparked Clemmons's interest | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 30 | gi_v02_f5efc0be2ffd | ielts5_test1_p3 J-39 | that the planet would have experienced in 2094 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 31 | gi_v02_6f3ce09da3cb | ielts14_test3_p3 F-04 | When children play | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 32 | gi_v02_947fac925d0f | ielts18_test3_p3 G-01 | that streaming results in better outcomes for students | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 33 | gi_v02_448133d16b54 | ielts5_test4_p3 G-36 | that prevent them from occupying other habitats | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 34 | gi_v02_5156c4d243fb | ielts11_test4_p1 J-04 | when you get to know them | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 35 | gi_v02_ad79b1304965 | ielts18_test4_p3 B-04 | Charles Darwin proposed in the 1850s about biological evolution | 所给省略关系词从句完整；in the same way that另有同类分析，未定位的题干有既有A8歧义，不批准唯一判分 | 适合阅读；题目需复核 |
| 36 | gi_v02_2652e55c28e8 | ielts6_test1_p3 F-33 | their wealth of traditional knowledge is vital to the task | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 37 | gi_v02_081f3436c73c | ielts20_test1_p1 J-02 | the total population had grown to 62 birds | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 38 | gi_v02_16db4d57b175 | ielts11_test3_p2 B-04 | we humans find admirable | we humans find admirable定语从句完整，冒号后的同位说明不应划入 | 适合阅读；题目本次未见问题 |
| 39 | gi_v02_662969a110e3 | ielts10_test4_p3 A-03 | as more and more examples come to light and modern genetics enters the scene | as统一统领两个并列主谓，目标整体成立 | 适合阅读；题目本次未见问题 |
| 40 | gi_v02_48e60f6d74b7 | ielts11_test2_p1 E-06 | when all the necessary information was available | when回指January 1982，定语从句分析成立 | 适合阅读；题目本次未见问题 |

### T3（20道auto）

| 序 | 题号 | 来源 | 答案/高亮 | 人工判定 | 原句/使用 |
|---|---|---|---|---|---|
| 41 | gi_v02_f36ae9d78009 | ielts11_test3_p3 A-06 | in the reasoning → 不是从句（短语或非谓语） | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 42 | gi_v02_73036ed6a5ee | ielts18_test1_p2 B-06 | wood energy markets help promote this → 并列分句 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 43 | gi_v02_3ad6cbcbf1d1 | ielts7_test4_p1 B-04 | that had sparked Clemmons's interest → 定语从句 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 44 | gi_v02_c9e6140b0263 | ielts19_test1_p1 F-03 | including the court surface, climatic conditions, and game styles → 不是从句（短语或非谓语） | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 45 | gi_v02_b8c759276973 | ielts11_test1_p2 D-02 | to ensure a perfect final fit → 不是从句（短语或非谓语） | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 46 | gi_v02_1593a605c2f7 | ielts11_test1_p3 D-06 | thus enabling radiation to be reflected by the snow → 不是从句（短语或非谓语） | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 47 | gi_v02_2baebe061085 | ielts11_test2_p2 B-06 | When the islanders cleared the forests for firewood and farming → 状语从句 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 48 | gi_v02_f4dfdcb86a8d | ielts16_test3_p1 D-05 | that contrary to popular perception, rowers were not slaves but mostly Roman citizens enrolled in the military → 名词性从句 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 49 | gi_v02_42ae736b8dd3 | ielts16_test4_p3 C-05 | for most people to comprehend → 不是从句（短语或非谓语） | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 50 | gi_v02_63889ae17166 | ielts7_test4_p3 C-02 | to 'tune out' chronic background noise → 不是从句（短语或非谓语） | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 51 | gi_v02_8f7bc0738b3a | ielts7_test4_p1 F-02 | Harnessing the wind → 不是从句（短语或非谓语） | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 52 | gi_v02_84c9b473f487 | ielts18_test1_p2 C-03 | to heat and power their facilities → 不是从句（短语或非谓语） | 并列主句中to heat and power为不定式，题干类别成立 | 适合阅读；题目本次未见问题 |
| 53 | gi_v02_188e0c9c3031 | ielts4_test4_p2 E-18 | which sets out to compare cultures using ethnographic evidence to derive general principles about human society → 定语从句 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 54 | gi_v02_38da3a739047 | ielts13_test1_p3 D-08 | it has a certain level of imagination → 名词性从句 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 55 | gi_v02_ac1dbdd6bc48 | ielts20_test1_p3 J-03 | which evolution has equipped us with to help us avoid famished predators → 定语从句 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 56 | gi_v02_6a8ee8e74eb9 | ielts4_test3_p1 E-01 | to the need to direct such opportunities to young people → 不是从句（短语或非谓语） | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 57 | gi_v02_dbc885c90e47 | ielts18_test3_p3 G-05 | in the higher sets → 不是从句（短语或非谓语） | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 58 | gi_v02_75887c7ff4f6 | ielts12_test8_p1 C-01 | with the invention of lead crystal glass by the English glass manufacturer George Ravenscroft (1632-1683) → 不是从句（短语或非谓语） | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 59 | gi_v02_f1795e0796db | ielts16_test3_p2 A-02 | As the ice has vanished → 状语从句 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 60 | gi_v02_08a076b8fd99 | ielts9_test2_p1 E-05 | in comprehending verbal information and speech processing → 不是从句（短语或非谓语） | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |

### T4（20道auto）

| 序 | 题号 | 来源 | 答案/高亮 | 人工判定 | 原句/使用 |
|---|---|---|---|---|---|
| 61 | gi_v02_df815e1bc263 | ielts19_test4_p3 C-02 | because survival depended on access to resources—such as rivers, forests and animals— → 原因 | 插入举例的闭合破折号完整，because表原因 | 适合阅读；题目本次未见问题 |
| 62 | gi_v02_ca22cccef988 | ielts18_test3_p2 C-04 | Though it did not run well → 让步 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 63 | gi_v02_b74effb3a4a4 | ielts5_test4_p2 D-15 | because large panels can be bolted together to make transparent walls → 原因 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 64 | gi_v02_3428c100ada3 | ielts9_test1_p3 C-16 | especially if only fragments are found → 条件 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 65 | gi_v02_0e44d851d08f | ielts18_test3_p2 C-05 | Though the Doble boys' third prototype, nicknamed the Model B, still lacked the convenience of an internal combustion engine → 让步 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 66 | gi_v02_27c2a7a7d519 | ielts9_test4_p3 A-02 | Although it is now evident that artefacts are as easily altered as chronicles → 让步 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 67 | gi_v02_ba6976615910 | ielts5_test2_p3 H-31 | Although a proposal in 1664 to establish a committee for improving the English language came to little → 让步 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 68 | gi_v02_23908fd7c6e7 | ielts13_test4_p2 C-01 | If the soil loses its ability to perform these functions → 条件 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 69 | gi_v02_f09cafd26908 | ielts5_test1_p3 F-21 | if people applied the same degree of scepticism to environmental lobbying as they do to lobby groups in other fields → 条件 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 70 | gi_v02_8e553e9d5a7b | ielts8_test4_p3 B-08 | if the ants are known not to sting → 条件 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 71 | gi_v02_ec4a9719b5db | ielts20_test2_p2 C-15 | if we don't finish that report or complete those home repairs → 条件 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 72 | gi_v02_bda011edf0d9 | ielts14_test4_p3 K-02 | until after they've happened → 时间 | until after引导时间界限，目标完整 | 适合阅读；题目本次未见问题 |
| 73 | gi_v02_22c11d651099 | ielts15_test2_p1 F-01 | If their designers had had the tools to think with their bodies – like dancers – and imagine how these barriers would feel → 条件 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 74 | gi_v02_cf4b08935df5 | ielts6_test3_p2 A-02 | if the job is running a small business or an autonomous unit within a larger business → 条件 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 75 | gi_v02_79c59d79307b | ielts6_test2_p3 B-04 | when early humans first began to reflect on the nature of things around them → 时间 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 76 | gi_v02_253f3c0d8c9b | ielts9_test4_p2 G-04 | if the children knew what they usually looked like → 条件 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 77 | gi_v02_3aebabe5bdd3 | ielts17_test4_p2 B-05 | even though there is plenty of evidence that growth increases education → 让步 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 78 | gi_v02_e2080683cbad | ielts19_test1_p2 G-06 | until the entire Mediterranean was free of pirates → 时间 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 79 | gi_v02_71ca70f2575d | ielts4_test4_p3 A-01 | so that they are distributed in both the most just and most efficient way → 目的 | so that为目的，非for并列义 | 适合阅读；题目本次未见问题 |
| 80 | gi_v02_159b6d3612b5 | ielts5_test3_p3 D-27 | If it works → 条件 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |

### T5（20道auto）

| 序 | 题号 | 来源 | 答案/高亮 | 人工判定 | 原句/使用 |
|---|---|---|---|---|---|
| 81 | gi_v02_ed52e37cb68e | ielts16_test4_p3 C-05 | AI's decision-making process | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 82 | gi_v02_1042c94dc044 | ielts6_test2_p2 G-23 | researchers | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 83 | gi_v02_3ea56ef0e419 | ielts15_test2_p3 E-03 | Oveis and colleagues | 报告分句主语Oveis and colleagues完整；引语是被报告内容 | 适合阅读；题目本次未见问题 |
| 84 | gi_v02_32e353d472f2 | ielts20_test2_p3 H-43 | baseball | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 85 | gi_v02_9341350334b9 | ielts16_test4_p3 B-05 | physicians | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 86 | gi_v02_7a35d8ba4c8c | ielts5_test1_p3 E-16 | They | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 87 | gi_v02_0f21b8919cc7 | ielts9_test2_p1 E-05 | Autistic spectrum disorders | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 88 | gi_v02_673e3715152f | ielts7_test4_p1 B-01 | Clemmons | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 89 | gi_v02_48e5b150cbd3 | ielts8_test1_p3 B-06 | Reports of telepathic experiences had by people during meditation | had by people...后置修饰已包含 | 适合阅读；题目本次未见问题 |
| 90 | gi_v02_e0b178ec35ff | ielts9_test2_p3 G-08 | The perception of someone's enthusiasm, or reputation | or reputation并列补充已包含；不需把末尾逗号当主语词汇 | 适合阅读；题目本次未见问题 |
| 91 | gi_v02_fca0b273aeb7 | ielts17_test2_p1 C-03 | Some scrolls | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 92 | gi_v02_ab0beb27aebd | ielts10_test1_p1 D-01 | Some wells | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 93 | gi_v02_fd4e111fa584 | ielts19_test4_p2 D-01 | environmental and legal groups | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 94 | gi_v02_4143cd444b32 | ielts10_test4_p1 G-01 | many experts | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 95 | gi_v02_b741356e3721 | ielts19_test4_p3 C-01 | Prehistory | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 96 | gi_v02_cc676f6a4182 | ielts9_test3_p2 C-09 | The first station | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 97 | gi_v02_d40913455978 | ielts5_test2_p3 J-38 | much of this momentum | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 98 | gi_v02_5d6aa2f2ea3d | ielts18_test3_p1 G-03 | Iron-ore slag, a byproduct of the iron-ore smelting process | a byproduct...同位语已包含，末尾逗号可裁 | 适合阅读；题目本次未见问题 |
| 99 | gi_v02_a3e6dff11c17 | ielts11_test4_p2 A-03 | The entire soundtrack | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 100 | gi_v02_f841e48db1c0 | ielts15_test1_p3 D-04 | We | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |

### T6（20道auto）

| 序 | 题号 | 来源 | 答案/高亮 | 人工判定 | 原句/使用 |
|---|---|---|---|---|---|
| 101 | gi_v02_d765c317f6a7 | ielts14_test3_p2 F-06 | are → 主句谓语 | AA1：只高亮are，遗漏encountered；身份选项可成立但完整单位不合格 | 适合阅读；题目需复核 |
| 102 | gi_v02_ee7aef9f24f1 | ielts16_test4_p3 D-06 | reject → 从句里的谓语 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 103 | gi_v02_ab6a52910527 | ielts9_test4_p1 I-01 | devoted → 主句谓语 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 104 | gi_v02_c80909f90525 | ielts8_test1_p2 F-05 | possess → 从句里的谓语 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 105 | gi_v02_7935de954b26 | ielts19_test3_p1 B-01 | connected → 从句里的谓语 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 106 | gi_v02_e72d8a318c82 | ielts18_test1_p3 D-04 | knew → 从句里的谓语 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 107 | gi_v02_23b5e7b92a0b | ielts12_test6_p2 G-03 | has gained → 从句里的谓语 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 108 | gi_v02_2ef5ecee41be | ielts17_test4_p3 B-03 | have → 主句谓语 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 109 | gi_v02_3cb4e32f9714 | ielts11_test3_p2 C-01 | depending → 非谓语（不定式、分词、动名词） | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 110 | gi_v02_93068bc6197e | ielts20_test2_p1 F-02 | moves → 主句谓语 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 111 | gi_v02_be9d4c84c0ad | ielts20_test1_p3 J-03 | has equipped → 从句里的谓语 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 112 | gi_v02_1dc8783845ff | ielts14_test1_p2 B-04 | was → 主句谓语 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 113 | gi_v02_9d729dccc04d | ielts14_test1_p1 L-01 | do facilitate → 从句里的谓语 | do facilitate强调助动词完整 | 适合阅读；题目本次未见问题 |
| 114 | gi_v02_b0bde4b3cbd7 | ielts6_test1_p1 D-08 | measuring → 非谓语（不定式、分词、动名词） | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 115 | gi_v02_b2e15dbd4aec | ielts5_test3_p2 A-01 | is being eroded → 主句谓语 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 116 | gi_v02_8a4437086f69 | ielts16_test3_p2 A-01 | are shrinking → 主句谓语 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 117 | gi_v02_a18ae61b5a5f | ielts13_test4_p2 B-02 | has grown → 主句谓语 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 118 | gi_v02_ee25dc2b796a | ielts9_test4_p1 D-02 | decided → 主句谓语 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 119 | gi_v02_3b60f2495986 | ielts20_test4_p2 F-31 | Using → 非谓语（不定式、分词、动名词） | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |
| 120 | gi_v02_867d6b2b5850 | ielts15_test3_p2 G-02 | has raised → 主句谓语 | 局部答案、高亮、已给干扰项及题干前提未见问题 | 适合阅读；题目本次未见问题 |


计数：120 auto、0 needs。所给局部答案/高亮119可成立、1不完整；题干另有1条沿用A8的非并列同类从句歧义。T1/T3/T4/T5各20未见新增错，T2为19无新增疑点+1既有歧义，T6为19未见错+1AA1。此为一次抽样和定向复核结果，不是全池无错率证明。

## 9. 新角度定向扫描：be中心与动词性分词遗漏

与此前并列共享助动词、连字符、not作用域、小品词不同，本次检查**解析器已把be选为当前动词中心，却把后面的VBN/VBG挂成其他补足依存**。对全部27,854道剑桥auto过滤T1/T6，取其evidence中心；中心为be词形、直接子节点是VBN/VBG、dep属dep/acomp/attr/oprd/xcomp/ccomp、且未在显示单位时列入。命中62题（并非62错），逐题如下。

| 序 | 题号 | 模板/来源 | 当前显示 | 人工判断 |
|---|---|---|---|---|
| 1 | gi_v02_bcd775abe58e | T1 ielts10_test2_p1 C-01 | are | be to be found的准情态/表语分析需保持教学口径；未认定新增错 |
| 2 | gi_v02_cf6e17e6e664 | T6 ielts10_test2_p1 C-01 | are | 同前，be to结构；本次不算确定错误 |
| 3 | gi_v02_f3dff1c1c598 | T1 ielts11_test4_p3 F-08 | is | so fine-tuned可形容词化，系表分析成立 |
| 4 | gi_v02_143a8709b9aa | T6 ielts11_test4_p3 F-08 | is | 同前 |
| 5 | gi_v02_177554194a2c | T1 ielts12_test5_p1 D-01 | are | family-owned复合形容词，系表分析成立 |
| 6 | gi_v02_cdcfe7550cab | T6 ielts12_test5_p1 D-01 | are | 同前 |
| 7 | gi_v02_b2151afb2691 | T6 ielts13_test3_p3 F-02 | is | possible + that内容从句，非遗漏被动中心 |
| 8 | gi_v02_8989e1540660 | T1 ielts13_test4_p2 A-02 | could; be | gone可形容词作表语，非必需并入单位 |
| 9 | gi_v02_250b42222768 | T6 ielts13_test4_p2 A-02 | could be | 同前 |
| 10 | gi_v02_d5255c499f80 | T1 ielts13_test4_p3 E-04 | was | was后表语that从句，合法 |
| 11 | gi_v02_ed7cdb578952 | T6 ielts13_test4_p3 E-04 | was | 同前 |
| 12 | gi_v02_1a55d8c99a6a | T6 ielts14_test1_p2 G-07 | were | prepared=ready形容词，合法；原引语跨句 |
| 13 | gi_v02_56671bb1833d | T1 ielts14_test2_p2 H-02 | is | AA1：并列被动描述只剩is，至少送审被动/系表分析 |
| 14 | gi_v02_108f07638465 | T6 ielts14_test2_p2 H-02 | is | AA1：同前，不能自动认证完整单位 |
| 15 | gi_v02_4209b5730257 | T1 ielts14_test3_p2 D-04 | is | is yet to be realised准情态/表语边界，未认定新增错 |
| 16 | gi_v02_7009c768706e | T1 ielts14_test3_p2 F-06 | are | AA1：are infrequently encountered漏encountered |
| 17 | gi_v02_d765c317f6a7 | T6 ielts14_test3_p2 F-06 | are | AA1：同前，完整高亮失败 |
| 18 | gi_v02_a9ff44478b8c | T1 ielts14_test3_p3 F-05 | is | freely chosen/spontaneous/voluntary可并列形容词性质描述 |
| 19 | gi_v02_1a9c9ac96f72 | T6 ielts14_test3_p3 F-05 | is | 同前 |
| 20 | gi_v02_cd9fcca3be29 | T1 ielts14_test3_p3 J-04 | must; be | child-centered形容词表语 |
| 21 | gi_v02_1fc6edcc2e7b | T6 ielts14_test3_p3 J-04 | must / be | 同前 |
| 22 | gi_v02_8c74d19c6866 | T1 ielts15_test1_p2 A-01 | is | used to=accustomed to，形容词而非被动动作 |
| 23 | gi_v02_9074f3b4f34c | T6 ielts15_test1_p2 A-01 | is | 同前 |
| 24 | gi_v02_c11de5a0051b | T6 ielts15_test1_p3 B-01 | are | well travelled形容词性质描述 |
| 25 | gi_v02_758ab285e78d | T1 ielts16_test3_p3 H-04 | is | well-positioned形容词性质描述 |
| 26 | gi_v02_cbb991ffd153 | T1 ielts16_test4_p2 D-04 | is | is后表语that从句 |
| 27 | gi_v02_bd687830ddc1 | T1 ielts17_test3_p3 H-03 | would; be | well-suited形容词表语 |
| 28 | gi_v02_e79719a01c31 | T6 ielts17_test3_p3 H-03 | would be | 同前 |
| 29 | gi_v02_e7fdb778e39f | T1 ielts18_test4_p3 B-01 | was | was后表语that从句 |
| 30 | gi_v02_13775783b706 | T6 ielts18_test4_p3 B-01 | was | 同前 |
| 31 | gi_v02_38a83a89574a | T6 ielts19_test1_p2 E-02 | was | land-based形容词表语 |
| 32 | gi_v02_c6e90d87a4ab | T6 ielts20_test2_p3 F-29 | are | terrified情绪形容词可成立 |
| 33 | gi_v02_e79a38c7bde2 | T1 ielts20_test3_p2 D-08 | is | is后what名词性表语 |
| 34 | gi_v02_2184cfc53946 | T6 ielts20_test3_p2 D-08 | is | 同前 |
| 35 | gi_v02_e6bf68e3a802 | T1 ielts20_test3_p3 A-02 | would; be | mining asteroids作“下一步”的表语，不是进行时 |
| 36 | gi_v02_0de202d8ee51 | T6 ielts20_test3_p3 A-02 | would be | 同前 |
| 37 | gi_v02_1effe59cfca4 | T1 ielts5_test3_p3 F-36 | is | is后表语that从句 |
| 38 | gi_v02_565cd0bbc38e | T6 ielts5_test3_p3 F-36 | is | 同前 |
| 39 | gi_v02_c750b58ca82f | T1 ielts5_test4_p1 B-16 | has; been | has been后表语that从句 |
| 40 | gi_v02_cee372a53302 | T6 ielts5_test4_p1 B-16 | has been | 同前 |
| 41 | gi_v02_a8b7f96832ba | T1 ielts6_test2_p3 A-02 | are | bound up with表示密切关联，可形容词补足 |
| 42 | gi_v02_e62c4336b2a2 | T6 ielts6_test2_p3 A-02 | are | 同前 |
| 43 | gi_v02_9a63c48bd5f6 | T6 ielts7_test2_p3 A-01 | were | were to be tackled准情态/表语口径，未认定新增错 |
| 44 | gi_v02_94cfb42a7c6a | T1 ielts7_test2_p3 A-05 | was | was后表语that从句 |
| 45 | gi_v02_6a50c8f657ba | T6 ielts7_test2_p3 A-05 | was | 同前 |
| 46 | gi_v02_154dae0e91c6 | T1 ielts7_test2_p3 D-01 | was | clear + that补足，非当前被动 |
| 47 | gi_v02_30b21be9eed1 | T6 ielts7_test2_p3 D-01 | was | 同前 |
| 48 | gi_v02_f974fca7ac75 | T1 ielts7_test4_p1 B-02 | was | fascinated可情绪形容词；不强制认定被动 |
| 49 | gi_v02_c5b32e0cdcca | T6 ielts7_test4_p1 B-02 | was | 同前 |
| 50 | gi_v02_0f5782c6b167 | T6 ielts7_test4_p3 F-07 | to be | long lasting作不定式to be的表语 |
| 51 | gi_v02_e72f802b71b6 | T1 ielts8_test1_p3 D-15 | was | was后表语that从句 |
| 52 | gi_v02_ceb6b2ca7f32 | T6 ielts8_test1_p3 D-15 | was | 同前 |
| 53 | gi_v02_415439abcc14 | T6 ielts8_test2_p3 F-03 | may be | may be acceptable合法；扫描因其他分句的挂靠而扩大 |
| 54 | gi_v02_9a27b9cf8463 | T1 ielts8_test4_p1 E-01 | is | remarkable + that补足，非当前被动 |
| 55 | gi_v02_a65e794e2cac | T6 ielts8_test4_p1 E-01 | is | 同前 |
| 56 | gi_v02_be5eb9447e95 | T1 ielts8_test4_p3 E-07 | is | is后表语that从句 |
| 57 | gi_v02_6c3665010501 | T6 ielts8_test4_p3 E-07 | is | 同前 |
| 58 | gi_v02_153f0216521d | T1 ielts9_test2_p1 I-05 | is | imperative + that补足，非当前被动 |
| 59 | gi_v02_58de76fa86c8 | T6 ielts9_test2_p1 I-05 | is | 同前 |
| 60 | gi_v02_f7af16f89470 | T1 ielts9_test4_p1 K-01 | was | to have understood名词性不定式作表语 |
| 61 | gi_v02_b2fb27bb730e | T6 ielts9_test4_p1 K-01 | was | 同前 |
| 62 | gi_v02_2397523a1605 | T6 ielts9_test4_p3 A-02 | is | evident + that补足，非当前被动 |

62道均为auto；4题列AA1，其余58题未认定需按本规则强制降级（其中be to等分析边界写明，未宣称都只有一种语法分析）。四题所在两句都属于可阅读的正常原文，问题在出题复核。

另尝试了缩约助动词与所有格筛选，得到178个题目命中；它只作探索线索，未逐题穷尽验收，未据此作“178全正确”或“178有问题”的结论。本节要求的全池定向扫描采用上面完成逐题判断的62题口径。

## 10. 前后池比较与计数

| 口径 | 独立结果 |
|---|---|
| 候选/ID | 50,243 → 50,243；增加0/删除0 |
| Cam auto→needs | 6（T1 1，T6 5） |
| Jijing auto→needs | 2（同句T1/T6） |
| needs→auto | 0 |
| status/reasons之外 | 仅distractors 3题：Cam1/Jijing2；其余字段0变化 |
| auto各模板 | 5834 / 4678 / 11401 / 399 / 5365 / 12656 |
| auto合计 | 40,333；Cam27,854；Jijing12,479 |
| 全量particle_outside_unit | Cam107 / Jijing39；不是本轮新增数量 |
| 全量shared_auxiliary | Cam3 / Jijing0 |

本轮8道降级逐题已核（剑桥6道见Z1/Z2、机经2道见J1）；不是把本来已needs的题当作新增。Z6前后排除token一致，未使任何题变化。

## 11. 双跑、环境、报告和盲审表

环境：Mac27.0.1 arm64，Python3.13.3、spaCy3.8.16、en_core_web_trf3.8.0、torch2.14.1 CPU、openpyxl3.1.5，生成种子20261018。使用指定`.venv-grammar-tools`。语料SHA-256 `55b808e1a69cfb7fc06670a6ac3bb36d2861923f229183875ed309ea3a747f37`，图谱 `c7b35ddb68db7601ccd01e38a210ad3dd772ff507302190f68a351e408b85a29`。

为了不覆写被审交付文件，`git archive 32574773d098ebbf357779dea764c4b8a47e6e37`完整解包到O/source，再在该根运行正式CLI两次；没有改写被审脚本。两次均复用前审在同一Mac、同版本解析器上产生的完整缓存；阅读解析逐字节未变。**本轮是两次完整出题，不是清空缓存后的全量重新解析**，用户本轮未要求清空缓存。额外控制句确实由本地模型新解析。

| 文件 | 第一次SHA-256 | 第二次SHA-256 | 与提交版 |
|---|---|---|---|
| generation_report_v0_2.json | 9cf7a41431605716b5761a2601832763d83141f6c0f5f9d9cf3a7944ed3d97ee | 9cf7a41431605716b5761a2601832763d83141f6c0f5f9d9cf3a7944ed3d97ee | 仅Python版本一行不同；提交版 74c949ee7e761f97d85d4d4dfb5d90adf9f9b31278de601285c853a10c92f5d3 |
| generation_report_v0_2.md | aeea3d4228cfb7156a39206344572b81878fcb957a886d8a10ef9f6cc752541b | aeea3d4228cfb7156a39206344572b81878fcb957a886d8a10ef9f6cc752541b | 仅Python版本一行不同；提交版 df38a427bacfe45a47b66d822b274aae5ca5f9c71df785dc5b0c9f7bf9cf6ca7 |
| review_batch_v0_2.jsonl | 57540dcfebb95e7daf0127a63cf528b81d15a0e6a17df57785a029e55d09cf9d | 57540dcfebb95e7daf0127a63cf528b81d15a0e6a17df57785a029e55d09cf9d | 字节一致 |
| review_batch_v0_2.xlsx | 6aef0550a2f82bef8a0bd0bb6fc40ebb4bc53d6f199ca5717e8561bfbc759ffb | 6aef0550a2f82bef8a0bd0bb6fc40ebb4bc53d6f199ca5717e8561bfbc759ffb | 字节一致 |

两报告逐行比对只有Python3.13.3 / 云端3.11.15一行；JSONL/XLSX提交SHA与提示一致。两次彼此四文件逐字节相同。13×6回归对象逐字段与第十三轮一致。7项整句过滤对象（含句子列表）与第十三轮完全相同：

| 过滤 | 预期 | 实际 |
|---|---|---|
| tagged_fragment | 30 | 30 |
| clause_attached_to_conjunction | 2 | 2 |
| glued_sentence_boundary | 0 | 0 |
| multi_sentence_unit | 1 | 1 |
| suspected_split_word | 0 | 0 |
| leading_stray_punctuation | 0 | 0 |
| control_character | 0 | 0 |

XLSX用ZIP/XML读7张表，6类各60条数据+表头；H2:H61判定下拉四项“正确/答案错/题目有歧义/句子不适合出题”。每个可见单元格与teacher_row输出逐格比较，未出现auto_pass/needs_review或内部原因。说明表也无泄露。剑桥230行（196auto/34needs），机经130行（104auto/26needs）。相对35e37c5，按题号保留**21**，按(模板/工作表,review_row)同题保留**1**。老师结果迁移应按题号，不能按旧行号套用；未决定老师盲审范围。

## 12. 测试、数据与旧代码负测

实际运行命令（在R执行，变量定义见§2；未省略为“测试都通过”）：

```sh
$G -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary tests.test_grammar_graph_draft -v
$G scripts/validate_reading_study.py
$G scripts/reading_jijing_text_fixes.py --check
$P -m unittest tests.test_reading_study -v
$N tests/test_dictation_spell_queue.js
$P -m ruff check --config 'extend-exclude=[]' scripts/grammar_items/checks.py scripts/grammar_items/reporting.py scripts/grammar_items/templates.py tests/test_grammar_item_candidates.py
$P -m ruff format --check --config 'extend-exclude=[]' scripts/grammar_items/checks.py scripts/grammar_items/reporting.py scripts/grammar_items/templates.py tests/test_grammar_item_candidates.py
$G -m venv "$O/flask-only"
$O/flask-only/bin/python -m pip install --cert /etc/ssl/cert.pem Flask
```

全新Flask-only环境按ci.yml抽取的完整模块列表运行，实际命令：

```sh
$O/flask-only/bin/python -m unittest tests.test_miniprogram_guest_access tests.test_miniprogram_dictation_grouping tests.test_inventory_toefl_materials tests.test_organize_toefl_materials tests.test_extract_toefl_answer_keys tests.test_map_toefl_answers_to_practice_docs tests.test_import_toefl_official_reading tests.test_reading_vocab_grading tests.test_stats_utils tests.test_grammar_graph_draft tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary -v
```

结果：专项144全部通过；轻量212项运行=211通过+1按设计跳过（非“212通过再加1跳过”）；reading_study22通过；Node退出0；4Python Ruff check/format均通过。Flask-only只有Flask3.1.3及其传递依赖、pip，没有读取重型模型环境。validator零错误，覆盖317/387、70篇未就绪是既有覆盖状态；`--check`输出`0 fix(es) not yet applied`。

`G O/audit_data.py`导入build_reading_test_practice，替换localize_image为纯路径生成（只禁止下载图片，仍使用实际构建逻辑），raw重建171篇的content整体（含summary）和groups全等；图谱脚本在O/source执行`G scripts/render_grammar_graph_review.py`，输出与提交版逐字节一致。

旧代码负测：将当前7个新test方法保留，在独立Python进程中载入35e37c5的templates/checks（其余未变），不更改仓库；`G O/negative_tests.py`。结果与Claude这次描述一致：

| 测试 | 旧代码结果 | 具体原因 |
|---|---|---|
| ConjunctionParticipleTests.test_provided_as_a_verb_stays | 控制通过 | 正常介词或provided by控制仍成立 |
| ConjunctionParticipleTests.test_provided_that_is_no_distractor | 断言失败 | 原断言得到缺词/错误状态 |
| CorrelativeNotTests.test_negative_question_keeps_its_not | 断言失败 | 原断言得到缺词/错误状态 |
| LooseParticleTests.test_preposition_after_a_verb_unaffected | 控制通过 | 正常介词或provided by控制仍成立 |
| LooseParticleTests.test_rp_particle_attached_as_prep_goes_to_review | 断言失败 | 原断言得到缺词/错误状态 |
| SharedAuxiliaryTests.test_participle_sharing_auxiliaries_goes_to_review | 断言失败 | 原断言得到缺词/错误状态 |
| SharedAuxiliaryTests.test_result_participle_unaffected | 接口错误 | Reason.SHARED_AUXILIARY不存在（AttributeError） |

汇总4断言失败、1接口错误、2控制通过，当前7项均已包含在144项通过中。没有把缺接口误写成业务断言失败。

## 13. 临时SQLite导入

先逐个校验固定main676569c完整快照的2853个Git blob（代码/static/data全套），再运行其自己的导入脚本创建317篇；随后用3257477完整快照自己的导入脚本更新同一`O/main-to-current.sqlite`。两次只创建/访问本机ReadingPassageAnalysis表；连接URI明示为审计目录下SQLite，未读取生产连接。

实测：main created317/failed0；当前created0、**updated236/skipped81/failed0**，总数317。与提示一致；不是沿用过去的预期。本轮未改阅读解析。共享远端跟踪origin/main现为`ee94abb30d56b3c9623c519f75c1ffa9679c65b5`，已比提示中的676569c更新；依照本次明确指定仍固定676569c，没有合并main，也没有改用新基线。

## 14. 机经（暂缓）

本轮新增/补充记录3项，不计入剑桥分级；用户已决定暂缓的V2、第27题等不重复列。

| 编号 | 位置 | 问题/状态 | 复现与建议 |
|---|---|---|---|
| J1 | reading_jijing_40_test_75_p3 G-03；gi_v02_36ad7ce3631a T1、gi_v02_8c1ace89792f T6 | 本轮2题auto→needs是保守误降。`upon which we might also draw in deciding ...`的in支配deciding，不属于draw in；谓语might draw本来完整。 | 缓存in=RP/prep且紧挨draw；新规则命中。将来结合in的动名词宾语与upon which区分，不要据needs宣称原答案错；目前不危害自动池。 |
| J2 | reading_jijing_27_test_33_p3 D-09；templates.py:229 | or not do是真否定，correlative_not仍排掉not。原句已source_quality，现无do对应T1/T6，所以无实际自动题受害。 | `He chose to do it or not do it.`实际解析第二do单位仅do；将来区分whether or not的选择标记与否定第二谓语。不是把15处都认作正确排除。 |
| J3 | reading_jijing_9_test_81_p2 I-10；gi_v02_4490077dd6af T6 | 与AA2同类：given that函数True，仍auto答非谓语。 | 与剑桥一起统一口径，至少送审；不重复计入剑桥数量。 |

## 15. 提交、CI、限制与交接

- 本次只写ROUND14审核记录、CODEX_HANDOFF、WORKLOG。被审代码/数据/4份交付文件未改；没有生产连接、部署、main推送、PR或大模型API调用。
- 桌面工作树`/Users/zhouxin/Desktop/studytracker`不是本次任务树；其既有修改/未跟踪文件未碰。任务树开始干净，结束只应有授权3文档；审计辅助材料仅本机目录。
- 基线3257477的[CI40523350786](https://github.com/KB77GG/studytracker/actions/runs/40523350786)整体success；test成功，lint advisory失败、format跳过。本次报告提交后另核精确head，不以基线代替本次CI。
- 与提示不一致处：无未执行的必检项。生成在仓库外完整快照执行以保护被审文件；沿用已验证解析缓存，已说明；main远端前进，导入按指定固定基线。未知全池错误率、词类口径边界、非并列T2的既有A8多解均未被本次120抽样消除。
- 下一位先读本报告，按用户下一步授权处理AA1/AA2并补正常系表、真动词provided/assuming等控制；不要按题号加黑名单。老师盲审范围和上线仍待用户决定，本轮未替老师提交任何判定。
