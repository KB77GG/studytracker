# 语法候选题 v0.2 第十五轮独立复审（Codex）

审核日期：2026-10-28，Asia/Shanghai。**结论：不通过，以剑桥题为准。** AA1–AA3 的指定修复均关闭；这不代表整个自动池已达到直接给学生的条件。新增 **0 阻断、1 应修（AB1）、1 建议（AB2）**。AB1 是 **5 道剑桥 auto_pass T1 的系动词/表语评分中心问题**；同一筛选另有10道T6，身份选项可成立，但高亮把系动词和表语混成“动词单位”，列为同组教学口径复核，不把10道全部断言为身份答案错。上述15题均与第十四轮逐字段相同，属于新发现的存量问题，并非本轮引入。

120题随机样本全部为auto：119题所给局部答案/高亮可成立，1题有AB1判分问题；在119题中另有2题保留既有A8提醒（1题明确有两个when目标，1题存在嵌套as从句的层级歧义）。不把局部答案可成立说成题目均能唯一判分。原句均可作为阅读材料；第107题插入说明的逗号可斟酌，不据此认定整句不能教学。机经本轮新确认问题 **0项**；按要求不重复登记已暂缓项目。

## 1. 范围与关闭情况

- 任务工作树：`/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker`，分支`codex/grammar-item-candidates`。
- 开工已读目录链AGENTS、CLAUDE、HANDOFF最新两节、WORKLOG顶部，并核实际Git。开始`c6bfb1a20c412e46624f31fe49081e5a8242d9d3`、工作树干净；按授权fetch后ff-only到 **`e2903b18eb448640390ceec9c7d3a4dde787f380`**。未普通merge/rebase/改写历史，未合main。
- `git diff --stat c6bfb1a..e2903b1`实测11文件、612插入/396删除：4个Python、4份交付文件、3份文档。禁止路径全部零改动；新增/修改规则逐个AST及代码检查不读passage_id/sentence_id/item_id。既有item_id生成器读取身份字段不等于规则黑名单。
- 本轮所有运行输出位于仓库外`O=/Users/zhouxin/.codex/audits/grammar-v02-round15-20261028`，完整被审快照在`O/source`。未覆盖任务树被审文件。

| 编号 | 关闭情况 | 独立结论 |
| --- | --- | --- |
| AA1 | 指定修复关闭 | 4道点名题均needs；旧62题中其余58逐字段不变。实际7个语料token位置命中，不是8；只有5道候选带原因，其中4道新降、1道本来needs。两类挂法只能作为保守复核信号，不能等同被动判定器。 |
| AA2 | 关闭 | given that的9道T6均needs；剑桥1/Jijing1新降，剑桥3/Jijing4本来needs。原答案未修，已阻止自动发布。 |
| AA3 | 指定反例与收窄关闭 | He granted / I am assuming / rather than supposing保留动词分析；第二个given仍可沿conj回溯。实际旧规则19处=13保留+6排除，文档20/7待更正（AB2）。Seeing that作本句主语按动名词处理合理。 |

## 2. 九项检查与实际运行

以下R指任务工作树；G=`$R/.venv-grammar-tools/bin/python`；P=`/Users/zhouxin/Desktop/studytracker/.venv/bin/python`；N=`/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`。O为上一节仓库外目录。除明确写明，命令在R执行；辅助脚本在O执行，正式生成命令在O/source执行。

| 项 | 结果 | 实际命令/证据 |
| --- | --- | --- |
| 1 | 通过 | git status --short --branch；git log -5 --oneline；git fetch origin claude/word-memorization-system-eval-55v2y5；git merge --ff-only e2903b18eb448640390ceec9c7d3a4dde787f380；git diff --stat c6bfb1a..e2903b1；G O/audit_data.py |
| 2 | 点名通过；计数需更正 | G O/probe_rules.py、G O/probe_followup.py、G O/final_checks.py；重查62题、全量be/VBN挂靠、T6隔离；见§4。 |
| 3 | 通过 | 从全池筛lexical_conjunction并逐题判断9题，见§5。 |
| 4 | 规则通过；计数需更正 | 旧/新conjunction_participle对全部12746个来源句逐token比较；G O/controls.py实际本地spaCy控制与24个真实来源重新解析，见§6。 |
| 5 | 内容质量不通过 | G O/audit_runtime.py按seed20261104抽120题，人工逐题审；另做非典型主语全池扫描29题及系动词评分中心扫描15题，见§7–8。 |
| 6 | 全部复现 | G O/audit_runtime.py与G O/final_checks.py：50243集合/字段比较、剑桥5/机经1降级、auto40327/剑桥27849，见§9。 |
| 7 | 通过 | G O/generate.py在完整e290快照执行两次G scripts/generate_grammar_candidates.py --seed 20261018；G O/audit_runtime.py核字节、78回归、7过滤及所有xlsx行，见§10。 |
| 8 | 通过 | G O/run_checks.py；G O/negative_tests.py；G O/audit_data.py，精确测试列表/结果见§11。 |
| 9 | 通过 | P O/import_snapshot.py O/main main，再P O/import_snapshot.py O/source current；完整main676569c快照2853个Git blob逐一核对，实测236/81/0，见§12。 |

辅助脚本都是本轮在仓库外创建、执行的检查，不写被审数据。一次新鲜解析与缓存的Python对象比较最初显示24处不等，原因仅是缓存morph_verbform为list、适配器为tuple；改用JSON规范化逐字段比较重跑，24处全部一致。这是审计探针比较类型问题，不是解析器差异，也没有更换模型或绕开失败的被审测试。两次读文件曾在O漏写source前缀而找不到文件，改为明确路径后读取；不计入产品检查失败。

## 3. 剑桥问题清单

### AB1 — 应修：系动词被当作助动词，T1强制选中表语而不接受系动词

位置：`scripts/grammar_items/templates.py:246`（verb_unit）及`:623`/`:644`（main_verb及required_root）。本次未改动这些评分规则；风险从第十四轮延续。具体来源与题号见下表。

例：`ielts9_test1_p1 B-01`原句“Perkin became immersed in the study of chemistry”。`gi_v02_6455e9eca58a`的答案显示`became immersed`，但grading.required_root是`immersed`，按contains_root_subset_of_verb_unit规则，**只选became会失败，只选immersed会通过**。`ielts17_test1_p2 C-04`的remain embedded同样强制embedded而不接受remain。错误不只是显示多了一个词，而是把解析器误给的aux/auxpass关系直接当作教学判分中心。

become/remain是系动词，后接的状态描述是补语；Cambridge的语法说明明确把它们列在main/linking verbs中：[Verbs: types / Linking verbs](https://dictionary.cambridge.org/grammar/british-grammar/linking-verbs)，[Subject complements](https://dictionary.cambridge.org/grammar/british-grammar/subject-complements)。这里不把所有VBN都一概当形容词；即便covered/linked支持被动状态的分析，也不能无提示地拒绝合理的系表分析。`became known`、`remain embedded`、`became immersed`尤其清楚。计划T1是“点主句谓语动词”，不是“选整个系表谓语”；计划还明确系动词可作中心。实际评分中心与题干不一致，至少应needs_review。

| 题号 | 来源/模板 | 当前显示 | 评分/判断 |
| --- | --- | --- | --- |
| gi_v02_dab43c9473dd | ielts11_test2_p1 B-05 T1 | became / covered | required_root=covered；系动词分析会被错误拒绝，送审 |
| gi_v02_a35eb87063b9 | ielts11_test2_p1 B-05 T6 | became covered → 主句谓语 | 身份选项可成立；高亮含系动词及表语，教学口径需统一，不断言身份选项错 |
| gi_v02_92579fb7cf29 | ielts12_test8_p1 E-04 T6 | became cut off → 从句里的谓语 | 身份选项可成立；高亮含系动词及表语，教学口径需统一，不断言身份选项错 |
| gi_v02_f5435b795551 | ielts16_test1_p2 A-02 T1 | have / become / linked | required_root=linked；系动词分析会被错误拒绝，送审 |
| gi_v02_6ebbace57044 | ielts16_test1_p2 A-02 T6 | have become linked → 主句谓语 | 身份选项可成立；高亮含系动词及表语，教学口径需统一，不断言身份选项错 |
| gi_v02_909373502a94 | ielts17_test1_p2 C-04 T1 | remain / embedded | required_root=embedded；系动词分析会被错误拒绝，送审 |
| gi_v02_c9f0705a51ac | ielts17_test1_p2 C-04 T6 | remain embedded → 主句谓语 | 身份选项可成立；高亮含系动词及表语，教学口径需统一，不断言身份选项错 |
| gi_v02_8d9d51eb274c | ielts18_test1_p2 F-01 T6 | have become established → 从句里的谓语 | 身份选项可成立；高亮含系动词及表语，教学口径需统一，不断言身份选项错 |
| gi_v02_7284cbb08492 | ielts19_test2_p1 H-04 T6 | became known → 从句里的谓语 | 身份选项可成立；高亮含系动词及表语，教学口径需统一，不断言身份选项错 |
| gi_v02_3b5789a23e3d | ielts5_test4_p1 B-18 T6 | become involved → 从句里的谓语 | 身份选项可成立；高亮含系动词及表语，教学口径需统一，不断言身份选项错 |
| gi_v02_9ab665ea6ed4 | ielts8_test1_p1 C-05 T1 | became / known | required_root=known；系动词分析会被错误拒绝，送审 |
| gi_v02_9e88d6bc48fd | ielts8_test1_p1 C-05 T6 | became known → 主句谓语 | 身份选项可成立；高亮含系动词及表语，教学口径需统一，不断言身份选项错 |
| gi_v02_637171dc92ff | ielts8_test1_p1 G-05 T6 | became known → 从句里的谓语 | 身份选项可成立；高亮含系动词及表语，教学口径需统一，不断言身份选项错 |
| gi_v02_6455e9eca58a | ielts9_test1_p1 B-01 T1 | became / immersed | required_root=immersed；系动词分析会被错误拒绝，送审 |
| gi_v02_ef2cab00a4b6 | ielts9_test1_p1 B-01 T6 | became immersed → 主句谓语 | 身份选项可成立；高亮含系动词及表语，教学口径需统一，不断言身份选项错 |

计数：15个不同auto、10个来源句，**5 T1为本项应修对象，10 T6为关联范围复核**。所有15题与3257477相同。T1五题必须根的依次为covered、linked、embedded、known、immersed。将“当前选项可成立”和“能自动认证动词单位正确”分开。

复现：全池按题号读grading；或筛Cambridge auto T1/T6的显示单位，找到被解析为aux/auxpass的become/remain等词形，再回看其中心和原句。报告§8给出具体筛选算法。无需修改任何数据，即可按既有grading声明推演上面的选词结果；本轮没有接触学生判分服务。

建议：用通用的词汇系动词/助动词冲突检查先把相关T1送审，勿用题号黑名单。将来修正中心时保留have become等真实时态助动词，并测试became known、remain embedded、became immersed和真正的was built/get-passive。T6应先明确题干是判断整个谓语结构还是一个动词单位，再统一高亮；不要把身份选项当前可成立的10题全称“答案错误”。本轮只报告，不实施。

### AB2 — 建议：第十五轮说明的两处全库命中数不可复现

位置：`docs/GRAMMAR_ITEM_CANDIDATES_V0_2_FIXES.md:931`、`:933`。实测当前317篇、12746句逐token：be_participle命中**7处**，不是8；原conjunction_participle命中**19处**，新规则保留13、排除**6**，不是20/7。这里“处”定义为passage_id + sentence_id + token位置，不是题数或标注嵌套次数。真实句重新解析24个不同文本与缓存逐字段一致；未找到可补出的第8/20处。

复现：本报告§4、§6列出全部位置；用325版旧函数和e290版新函数对相同来源句遍历。建议更正文档，或提供不同口径的具体额外位置；不推断Claude计数错误的原因。候选降级数、全池统计、交付哈希没有因此变化。

## 4. AA1逐题与全库命中

实现覆盖T1答案、T1干扰项和T6自己的完整单位；在T1_ONLY_REASONS中排除传播，T6随后按自己的unit重算。全库每道T6逐一核验：是否含participle_after_be与自身函数结果完全一致。没有把主句干扰项的问题连坐到其他T6。

| 题号 | 来源/模板 | 前→后 | 局部内容与降级判断 |
| --- | --- | --- | --- |
| gi_v02_56671bb1833d | ielts14_test2_p2 H-02 T1 | auto_pass → needs_review | 原答案仍只含is；三个并列被动/系表口径需复核，降级合理 |
| gi_v02_108f07638465 | ielts14_test2_p2 H-02 T6 | auto_pass → needs_review | 原答案仍只含is；三个并列被动/系表口径需复核，降级合理 |
| gi_v02_7009c768706e | ielts14_test3_p2 F-06 T1 | auto_pass → needs_review | 原答案仍只含are；encountered漏出，隔离正确 |
| gi_v02_d765c317f6a7 | ielts14_test3_p2 F-06 T6 | auto_pass → needs_review | 原答案仍只含are；encountered漏出，隔离正确 |
| gi_v02_4031959870fe | ielts4_test4_p3 C-10 T6 | needs_review → needs_review | are poverty-stricken / deprived可作状态表语；保守加原因可接受，本来needs，不能算新增修正正确 |

同句另3道T6（Containing、including、can leave）逐字段不变；此处仅核实隔离，不把含including的词汇化介词/分词教学边界当作已解决。
| T6题号 | 显示中心 | 自身有AA1风险 | 结果 |
| --- | --- | --- | --- |
| gi_v02_108f07638465 | is | True | auto_pass → needs_review；按自身风险降级 |
| gi_v02_44a90fa2de05 | Containing | False | auto_pass → auto_pass；未变化 |
| gi_v02_82d07c56542b | including | False | auto_pass → auto_pass；未变化 |
| gi_v02_d765c317f6a7 | are | True | auto_pass → needs_review；按自身风险降级 |
| gi_v02_76ab3c803ec8 | leave | False | auto_pass → auto_pass；未变化 |

| 来源 | be位置 | 独立判断 |
| --- | --- | --- |
| ielts14_test2_p2 H-02 | 12 is | 并列VBN作acomp；2道新降，需被动/系表复核 |
| ielts14_test3_p2 F-06 | 3 are | encountered为dep；2道新降，明确漏出被动单位 |
| ielts20_test2_p3 H-46 | 4 are | are precise已有形容词补语，delineated是补充描述；若当被动错误会误伤；当前无带此原因题 |
| ielts4_test4_p3 C-10 | 18 are | poverty-stricken / deprived状态描述；1道原needs新增原因，保守复核 |
| ielts7_test1_p3 F-30 | 10 be | be automatic and effortless已有完整系表，accomplished补充说明；启发式保守命中，当前无该原因候选 |
| reading_jijing_13_test_6_p2 B-08 | 2 were | 倒装were heady与can be forgiven是不同分句；解析器dep误挂，非be单位遗漏；无该原因候选，机经 |
| reading_jijing_29_test_63_p3 C-03 | 5 are | state-controlled / measured属性并列，被动或系表需复核；无该原因候选，机经 |

因此规则作为“需看一眼”的保守信号可接受，不能称7处全是确凿被动漏词。若以后这些来源新增适用题，可能保守降级；本轮无新增误降的剑桥auto。扩大VBN直接子节点检查还查看了advcl、ccomp、xcomp、conj等挂法，常见的是其他从句、补充状语、表语that内容和已披露be to结构；未另确认必须按AA1降级的auto。被动和分词形容词本就有分析边界，未据此声称覆盖全部漏网。

原62题中4题上表，其余58题逐字段不变（不是仅比较状态）。以下逐题列出现值；“不变”是比较结论，沿用上轮已记录的可接受或需统一口径说明，不把58题重新宣称为语法绝无争议。

| 题号 | 来源/模板 | 现值 | 结果 |
| --- | --- | --- | --- |
| gi_v02_bcd775abe58e | ielts10_test2_p1 C-01 T1 | are | auto → auto；全部字段不变 |
| gi_v02_cf6e17e6e664 | ielts10_test2_p1 C-01 T6 | are → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_f3dff1c1c598 | ielts11_test4_p3 F-08 T1 | is | auto → auto；全部字段不变 |
| gi_v02_143a8709b9aa | ielts11_test4_p3 F-08 T6 | is → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_177554194a2c | ielts12_test5_p1 D-01 T1 | are | auto → auto；全部字段不变 |
| gi_v02_cdcfe7550cab | ielts12_test5_p1 D-01 T6 | are → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_b2151afb2691 | ielts13_test3_p3 F-02 T6 | is → 从句里的谓语 | auto → auto；全部字段不变 |
| gi_v02_8989e1540660 | ielts13_test4_p2 A-02 T1 | could / be | auto → auto；全部字段不变 |
| gi_v02_250b42222768 | ielts13_test4_p2 A-02 T6 | could be → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_d5255c499f80 | ielts13_test4_p3 E-04 T1 | was | auto → auto；全部字段不变 |
| gi_v02_ed7cdb578952 | ielts13_test4_p3 E-04 T6 | was → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_1a55d8c99a6a | ielts14_test1_p2 G-07 T6 | were → 从句里的谓语 | auto → auto；全部字段不变 |
| gi_v02_4209b5730257 | ielts14_test3_p2 D-04 T1 | is | auto → auto；全部字段不变 |
| gi_v02_a9ff44478b8c | ielts14_test3_p3 F-05 T1 | is | auto → auto；全部字段不变 |
| gi_v02_1a9c9ac96f72 | ielts14_test3_p3 F-05 T6 | is → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_cd9fcca3be29 | ielts14_test3_p3 J-04 T1 | must / be | auto → auto；全部字段不变 |
| gi_v02_1fc6edcc2e7b | ielts14_test3_p3 J-04 T6 | must also be → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_8c74d19c6866 | ielts15_test1_p2 A-01 T1 | is | auto → auto；全部字段不变 |
| gi_v02_9074f3b4f34c | ielts15_test1_p2 A-01 T6 | is → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_c11de5a0051b | ielts15_test1_p3 B-01 T6 | are → 从句里的谓语 | auto → auto；全部字段不变 |
| gi_v02_758ab285e78d | ielts16_test3_p3 H-04 T1 | is | auto → auto；全部字段不变 |
| gi_v02_cbb991ffd153 | ielts16_test4_p2 D-04 T1 | is | auto → auto；全部字段不变 |
| gi_v02_bd687830ddc1 | ielts17_test3_p3 H-03 T1 | would / be | auto → auto；全部字段不变 |
| gi_v02_e79719a01c31 | ielts17_test3_p3 H-03 T6 | would be → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_e7fdb778e39f | ielts18_test4_p3 B-01 T1 | was | auto → auto；全部字段不变 |
| gi_v02_13775783b706 | ielts18_test4_p3 B-01 T6 | was → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_38a83a89574a | ielts19_test1_p2 E-02 T6 | was → 从句里的谓语 | auto → auto；全部字段不变 |
| gi_v02_c6e90d87a4ab | ielts20_test2_p3 F-29 T6 | are → 从句里的谓语 | auto → auto；全部字段不变 |
| gi_v02_e79a38c7bde2 | ielts20_test3_p2 D-08 T1 | is | auto → auto；全部字段不变 |
| gi_v02_2184cfc53946 | ielts20_test3_p2 D-08 T6 | is → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_e6bf68e3a802 | ielts20_test3_p3 A-02 T1 | would / be | auto → auto；全部字段不变 |
| gi_v02_0de202d8ee51 | ielts20_test3_p3 A-02 T6 | would be → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_1effe59cfca4 | ielts5_test3_p3 F-36 T1 | is | auto → auto；全部字段不变 |
| gi_v02_565cd0bbc38e | ielts5_test3_p3 F-36 T6 | is → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_c750b58ca82f | ielts5_test4_p1 B-16 T1 | has / been | auto → auto；全部字段不变 |
| gi_v02_cee372a53302 | ielts5_test4_p1 B-16 T6 | has been → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_a8b7f96832ba | ielts6_test2_p3 A-02 T1 | are | auto → auto；全部字段不变 |
| gi_v02_e62c4336b2a2 | ielts6_test2_p3 A-02 T6 | are → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_9a63c48bd5f6 | ielts7_test2_p3 A-01 T6 | were → 从句里的谓语 | auto → auto；全部字段不变 |
| gi_v02_94cfb42a7c6a | ielts7_test2_p3 A-05 T1 | was | auto → auto；全部字段不变 |
| gi_v02_6a50c8f657ba | ielts7_test2_p3 A-05 T6 | was → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_154dae0e91c6 | ielts7_test2_p3 D-01 T1 | was | auto → auto；全部字段不变 |
| gi_v02_30b21be9eed1 | ielts7_test2_p3 D-01 T6 | was → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_f974fca7ac75 | ielts7_test4_p1 B-02 T1 | was | auto → auto；全部字段不变 |
| gi_v02_c5b32e0cdcca | ielts7_test4_p1 B-02 T6 | was → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_0f5782c6b167 | ielts7_test4_p3 F-07 T6 | to be → 非谓语（不定式、分词、动名词） | auto → auto；全部字段不变 |
| gi_v02_e72f802b71b6 | ielts8_test1_p3 D-15 T1 | was | auto → auto；全部字段不变 |
| gi_v02_ceb6b2ca7f32 | ielts8_test1_p3 D-15 T6 | was → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_415439abcc14 | ielts8_test2_p3 F-03 T6 | may be → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_9a27b9cf8463 | ielts8_test4_p1 E-01 T1 | is | auto → auto；全部字段不变 |
| gi_v02_a65e794e2cac | ielts8_test4_p1 E-01 T6 | is → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_be5eb9447e95 | ielts8_test4_p3 E-07 T1 | is | auto → auto；全部字段不变 |
| gi_v02_6c3665010501 | ielts8_test4_p3 E-07 T6 | is → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_153f0216521d | ielts9_test2_p1 I-05 T1 | is | auto → auto；全部字段不变 |
| gi_v02_58de76fa86c8 | ielts9_test2_p1 I-05 T6 | is → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_f7af16f89470 | ielts9_test4_p1 K-01 T1 | was | auto → auto；全部字段不变 |
| gi_v02_b2fb27bb730e | ielts9_test4_p1 K-01 T6 | was → 主句谓语 | auto → auto；全部字段不变 |
| gi_v02_2397523a1605 | ielts9_test4_p3 A-02 T6 | is → 从句里的谓语 | auto → auto；全部字段不变 |

## 5. AA2的9道T6

全部当前needs，**0道auto**。两道由auto降级、7道本来needs。连词given/provided/considering不能在本轮已选的教学口径下自动判成“从句动词/非谓语动词”；新增原因正确，但没有改正既有机器答案，老师仍需审。

| 题号 | 来源 | 显示/答案 | 前→后 | 判断 |
| --- | --- | --- | --- | --- |
| gi_v02_d7b85db07823 | ielts10_test2_p2 D-07 | Given → 从句里的谓语 | needs_review → needs_review | 固定引导表达；降级/维持needs合理；原句可读，机器选项未经修正 |
| gi_v02_1892e239a5c5 | ielts15_test4_p3 B-03 | provided → 从句里的谓语 | needs_review → needs_review | 固定引导表达；降级/维持needs合理；原句可读，机器选项未经修正 |
| gi_v02_31a694497b01 | ielts18_test2_p3 C-03 | given → 非谓语（不定式、分词、动名词） | auto_pass → needs_review | 固定引导表达；降级/维持needs合理；原句可读，机器选项未经修正 |
| gi_v02_268ca701fe44 | ielts7_test1_p1 A-05 | Given → 从句里的谓语 | needs_review → needs_review | 固定引导表达；降级/维持needs合理；原句可读，机器选项未经修正 |
| gi_v02_acd827aad052 | reading_jijing_10_test_78_p2 C-24 | Given → 从句里的谓语 | needs_review → needs_review | 固定引导表达；降级/维持needs合理；原句可读，机器选项未经修正 |
| gi_v02_293b0aaff89a | reading_jijing_44_test_29_p2 E-04 | given → 从句里的谓语 | needs_review → needs_review | 固定引导表达；降级/维持needs合理；原句可读，机器选项未经修正 |
| gi_v02_2a9cd011998d | reading_jijing_69_test_40_p2 B-04 | Considering → 从句里的谓语 | needs_review → needs_review | 固定引导表达；降级/维持needs合理；原句可读，机器选项未经修正 |
| gi_v02_1495cbe1f52c | reading_jijing_88_test_98_p1 J-03 | provided → 从句里的谓语 | needs_review → needs_review | 固定引导表达；降级/维持needs合理；原句可读，机器选项未经修正 |
| gi_v02_4490077dd6af | reading_jijing_9_test_81_p2 I-10 | Given → 非谓语（不定式、分词、动名词） | auto_pass → needs_review | 固定引导表达；降级/维持needs合理；原句可读，机器选项未经修正 |

## 6. AA3全库与反例

prep/advcl/mark、无自己的主语/aux/auxpass，或沿conj回到满足条件的首项，能排除本次三个真动词反例；第二个given的并列仍保留。条件是启发式，不是“所有这类分词都是连词”的定义。词序与that(mark)要求使that-less provided、介词given + NP等仍在已披露边界内。

旧函数19个命中均在下表（13保留/6排除），没有使用陈旧缓存条目凑20。短语takes it for granted中的granted即使不是普通限定动词，也不是given that式连词，排除正确。

| 序 | 来源/词位置 | 词/依存 | 新判断 | 逐项判断 |
| --- | --- | --- | --- | --- |
| 1 | ielts10_test2_p2 D-07 #0 | Given / prep | 保留 | 条件/原因/依据引导表达；按本轮连词口径保留合理 |
| 2 | ielts15_test4_p3 B-03 #32 | provided / prep | 保留 | 条件/原因/依据引导表达；按本轮连词口径保留合理 |
| 3 | ielts18_test2_p2 F-04 #6 | given / prep | 保留 | 条件/原因/依据引导表达；按本轮连词口径保留合理 |
| 4 | ielts18_test2_p3 C-03 #1 | given / prep | 保留 | 条件/原因/依据引导表达；按本轮连词口径保留合理 |
| 5 | ielts18_test4_p3 B-01 #27 | supposing / pcomp | 排除 | rather than支配supposing，假定行为；排除正确 |
| 6 | ielts7_test1_p1 A-05 #0 | Given / prep | 保留 | 条件/原因/依据引导表达；按本轮连词口径保留合理 |
| 7 | ielts7_test1_p1 A-05 #13 | given / conj | 保留 | 条件/原因/依据引导表达；按本轮连词口径保留合理，第二个given沿conj回溯 |
| 8 | reading_jijing_10_test_78_p2 C-24 #0 | Given / prep | 保留 | 条件/原因/依据引导表达；按本轮连词口径保留合理 |
| 9 | reading_jijing_13_test_6_p2 B-08 #16 | assuming / pcomp | 排除 | for assuming that的动名词；排除正确 |
| 10 | reading_jijing_18_test_53_p2 G-05 #0 | Seeing / csubj | 排除 | Seeing ... is the highest priority；Seeing=确保/使得，整个动名词结构作主语，非原因连词；排除正确 |
| 11 | reading_jijing_44_test_29_p2 E-04 #23 | given / prep | 保留 | 条件/原因/依据引导表达；按本轮连词口径保留合理 |
| 12 | reading_jijing_53_test_83_p2 E-04 #3 | assuming / advcl | 保留 | 条件/原因/依据引导表达；按本轮连词口径保留合理 |
| 13 | reading_jijing_62_test_44_p3 I-04 #14 | granted / amod | 排除 | takes it for granted固定补语；排除正确 |
| 14 | reading_jijing_62_test_44_p3 K-05 #7 | granted / ccomp | 排除 | takes it for granted固定补语；排除正确 |
| 15 | reading_jijing_69_test_40_p2 B-04 #0 | Considering / advcl | 保留 | 条件/原因/依据引导表达；按本轮连词口径保留合理 |
| 16 | reading_jijing_77_test_16_p2 F-01 #17 | assuming / pcomp | 排除 | by assuming that的方法动名词；排除正确 |
| 17 | reading_jijing_83_test_95_p1 D-06 #0 | Given / prep | 保留 | 条件/原因/依据引导表达；按本轮连词口径保留合理 |
| 18 | reading_jijing_88_test_98_p1 J-03 #11 | provided / prep | 保留 | 条件/原因/依据引导表达；按本轮连词口径保留合理 |
| 19 | reading_jijing_9_test_81_p2 I-10 #0 | Given / prep | 保留 | 条件/原因/依据引导表达；按本轮连词口径保留合理 |

实际本地模型控制（不是仅手工mock）：
| 句子 | 关键结果 | 判断 |
| --- | --- | --- |
| He granted that the plan might fail. | granted:True→False | 真动词/主语/被动保留；条件given/provided保留连词 |
| I am assuming that he will come. | assuming:True→False | 真动词/主语/被动保留；条件given/provided保留连词 |
| Rather than supposing that they stayed, we checked the evidence. | supposing:True→False | 真动词/主语/被动保留；条件given/provided保留连词 |
| Given that it is late, and given that the roads are icy, we should go. | Given:True→True；given:True→True | 真动词/主语/被动保留；条件given/provided保留连词 |
| The plan works provided that they comply. | provided:True→True | 真动词/主语/被动保留；条件given/provided保留连词 |
| Seeing that the children leave school up to the right standard is our priority. | Seeing:True→False | 真动词/主语/被动保留；条件given/provided保留连词 |
| The money was provided by banks. | provided:False→False | 真动词/主语/被动保留；条件given/provided保留连词 |
| She provided an explanation. | provided:False→False | 真动词/主语/被动保留；条件given/provided保留连词 |

同一控制组还含正常is being treated、is closed、is securely fastened：分词已在单位中，不触发AA1；family-owned、terrified、freely chosen/spontaneous不新增风险。短句“Insects are infrequently encountered”被模型正确解析为are+encountered，因此不触发；真实完整F-06仍解析成dep并触发。不能用简化短句的解析替代原句证据。24个真实来源的重新解析与缓存经JSON规范化逐字段全等。

## 7. seed 20261104：剑桥auto 120题逐题审核

方法：使用本轮重新生成的全量池，筛source_kind=reading_test且passage_id以ielts开头、status=auto_pass；按T1–T6固定顺序，各模板先按item_id排序，以**同一个random.Random(20261104)**连续sample20，合计120。不是从360行老师表抽，不混入needs。展示使用正式teacher_row，核原句、目标/答案各parts、干扰项、grading和题干。

### T1（20道，全部auto）

| 序 | 题号 | 来源 | 答案/目标 | 判定 | 原句/题目适用性 |
| --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_c5fc77fc1a2a | ielts20_test3_p1 C-02 | used | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 2 | gi_v02_a62878c7526e | ielts16_test2_p1 I-03 | are | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 3 | gi_v02_36f5b0731e43 | ielts15_test3_p3 F-01 | found | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 4 | gi_v02_53d5dc08031d | ielts15_test3_p1 G-04 | show | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 5 | gi_v02_602ed651f958 | ielts15_test1_p2 D-06 | may / mean | may mean为主句；will not / decrease是不连续完整从句单位 | 原句可读；本次未见阻止使用的问题 |
| 6 | gi_v02_8385f320a553 | ielts8_test2_p3 D-06 | has | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 7 | gi_v02_9bdf2da506b8 | ielts20_test2_p2 C-21 | tend | tend为主句中心；to be left补足不并入其单位 | 原句可读；本次未见阻止使用的问题 |
| 8 | gi_v02_0539083e6f8e | ielts10_test2_p1 F-02 | had | Water-borne已不作动词干扰；had正确 | 原句可读；本次未见阻止使用的问题 |
| 9 | gi_v02_3b9d152184c6 | ielts14_test3_p3 G-01 | can / range | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 10 | gi_v02_6455e9eca58a | ielts9_test1_p1 B-01 | became / immersed | AB1：became immersed的required_root=immersed，合理系动词became答案被拒；题目不可auto | 原句可读；题目需复核 |
| 11 | gi_v02_01a7b3023c8a | ielts8_test4_p1 B-01 | cover | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 12 | gi_v02_ab43d7edaa23 | ielts13_test4_p2 F-06 | are / working | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 13 | gi_v02_e6375dc3960c | ielts4_test1_p1 F-01 | said | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 14 | gi_v02_8f548840cfce | ielts7_test3_p2 A-03 | is / being / obtained | is / being obtained跨now保持单位；正确 | 原句可读；本次未见阻止使用的问题 |
| 15 | gi_v02_9a96a8af6544 | ielts7_test2_p1 H-39 | would / not / be / permitted | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 16 | gi_v02_d9858b63987c | ielts7_test2_p1 D-17 | prevents | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 17 | gi_v02_faea699b6f1d | ielts13_test2_p3 D-03 | can / accumulate | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 18 | gi_v02_a2b34d1a882d | ielts7_test4_p2 F-02 | certifies | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 19 | gi_v02_b927113a18f1 | ielts12_test6_p1 E-01 | held / up | held up含小品词；to address/reduce是不定式并列，干扰合理 | 原句可读；本次未见阻止使用的问题 |
| 20 | gi_v02_126c6da1f2c1 | ielts11_test3_p2 G-03 | can / control | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |

### T2（20道，全部auto）

| 序 | 题号 | 来源 | 答案/目标 | 判定 | 原句/题目适用性 |
| --- | --- | --- | --- | --- | --- |
| 21 | gi_v02_96193e254b1a | ielts6_test2_p2 F-18 | who continued their education | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 22 | gi_v02_7c79170e31d1 | ielts16_test4_p1 A-04 | which also provided ventilation during the work | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 23 | gi_v02_07e1eba02ad3 | ielts8_test2_p1 B-01 | glassmakers across the world were looking for a method of making it continuously | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 24 | gi_v02_92967174e508 | ielts19_test1_p3 E-03 | how the 17th-century philosophers René Descartes and Baruch Spinoza described human information engagement | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 25 | gi_v02_e25b862c0583 | ielts20_test1_p3 E-02 | when the firefighters were relaxed | 局部when边界正确；另一个when they were under stress也符合题干，既有A8非并列多解，不能唯一判分 | 原句可读；题目需复核 |
| 26 | gi_v02_360b8ce6d37c | ielts13_test1_p2 E-07 | those who bore easily face poorer prospects in education, their career and even life in general | 省that名词性从句包含those who...；其中who从句不改变整体类别 | 原句可读；本次未见阻止使用的问题 |
| 27 | gi_v02_b358f14b6b99 | ielts11_test1_p2 B-04 | which would not only be a fitting commemoration of the Millennium, but also a lasting symbol of the economic regeneration of the region | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 28 | gi_v02_9a3d4e2b5686 | ielts19_test3_p3 A-03 | even if you're speaking the same language, as we are | even if目标整体可成立；内部as we are另可分析从句，T2层级未限定，沿用A8歧义提醒 | 原句可读；题目需复核 |
| 29 | gi_v02_e99bd48db52c | ielts6_test2_p3 G-06 | that happen to be the names of the numbers | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 30 | gi_v02_50662395ac92 | ielts11_test3_p2 A-01 | however it is defined | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 31 | gi_v02_25ca2bb75c3d | ielts11_test1_p1 G-02 | it would have on the environment | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 32 | gi_v02_5e3220e0be17 | ielts11_test4_p3 B-03 | no one since has celebrated more eloquently the magnitude of its achievement | and所指唯一，后项是主层并列分句 | 原句可读；本次未见阻止使用的问题 |
| 33 | gi_v02_e461efa6dd68 | ielts12_test7_p1 A-01 | that separate the interior of the Galápagos island of Isabela from the Pacific Ocean | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 34 | gi_v02_5f8ba6bce199 | ielts10_test1_p3 B-01 | that innovation starts with recruitment | that innovation starts...为表语内容；与reason后关系从句区分 | 原句可读；本次未见阻止使用的问题 |
| 35 | gi_v02_475e4fbe984e | ielts14_test4_p1 A-02 | that it doesn't seem to show any signs of aging | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 36 | gi_v02_24716b36770e | ielts9_test4_p2 G-03 | who were playing in front of a mirror | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 37 | gi_v02_fec22fae8e61 | ielts10_test3_p2 H-05 | the more north you travel in the northern hemisphere | the more...为比例/比较状语结构；目标完整 | 原句可读；本次未见阻止使用的问题 |
| 38 | gi_v02_e22983137acb | ielts4_test1_p2 D-04 | it watches and tracks airborne flying fish | the way后的省关系词从句；边界可成立 | 原句可读；本次未见阻止使用的问题 |
| 39 | gi_v02_6883edc798ca | ielts17_test1_p2 A-05 | that stadiums can drive urban development and adapt to the culture of every age | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 40 | gi_v02_b46694839f1b | ielts16_test4_p2 D-01 | that the reading circuit is not given to human beings through a genetic blueprint like vision or language | 只划that内容从句，分号后独立句未混入；题目可判 | 原句可读；本次未见阻止使用的问题 |

### T3（20道，全部auto）

| 序 | 题号 | 来源 | 答案/目标 | 判定 | 原句/题目适用性 |
| --- | --- | --- | --- | --- | --- |
| 41 | gi_v02_ff2a7ae5c411 | ielts4_test1_p1 C-01 | Despite the extensive coverage in the popular media of the destruction of rainforests → 不是从句（短语或非谓语） | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 42 | gi_v02_fc1a3bf40dde | ielts15_test2_p2 D-03 | When it comes to breeding → 状语从句 | when it comes to...含完整主谓；状语类别可成立 | 原句可读；本次未见阻止使用的问题 |
| 43 | gi_v02_f974587370ba | ielts13_test2_p3 C-07 | to avert an across-the-board price cut → 不是从句（短语或非谓语） | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 44 | gi_v02_c40c533be490 | ielts19_test2_p1 F-03 | In the 1830s and 1840s → 不是从句（短语或非谓语） | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 45 | gi_v02_e4d5675da5bb | ielts4_test3_p1 O-03 | in association with other types of support → 不是从句（短语或非谓语） | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 46 | gi_v02_9ec8d879724c | ielts15_test1_p3 C-02 | because they are common to humanity → 状语从句 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 47 | gi_v02_5c738716dd17 | ielts5_test2_p3 H-31 | Although a proposal in 1664 to establish a committee for improving the English language came to little → 状语从句 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 48 | gi_v02_d236a381b98a | ielts18_test1_p3 B-01 | of attacking the problem → 不是从句（短语或非谓语） | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 49 | gi_v02_6ac69c7bc5d2 | ielts20_test4_p2 E-27 | comparing a barren plot of land to the ‘beautiful, lush green vegetable garden’ sitting beside it → 不是从句（短语或非谓语） | comparing...含其后修饰短语，属非谓语目标 | 原句可读；本次未见阻止使用的问题 |
| 50 | gi_v02_4ed1c719037a | ielts10_test3_p1 E-05 | because of problems of definition → 不是从句（短语或非谓语） | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 51 | gi_v02_6fc0314d63ed | ielts11_test2_p3 B-04 | if they see others doing the same → 状语从句 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 52 | gi_v02_133eef10df1f | ielts6_test2_p3 A-03 | that comes naturally to a person → 定语从句 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 53 | gi_v02_a00bd565e4c5 | ielts9_test1_p1 I-06 | the public clamoured for more → 并列分句 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 54 | gi_v02_f8e878180a19 | ielts11_test1_p2 D-05 | each bolt was hand-tightened → 并列分句 | 每个bolt自有主语；hand-tightened整词完整 | 原句可读；本次未见阻止使用的问题 |
| 55 | gi_v02_05faa3d7f559 | ielts4_test3_p1 H-02 | as a place to find adventurous play and money → 不是从句（短语或非谓语） | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 56 | gi_v02_b1bce7254f9e | ielts13_test3_p3 F-02 | While it is possible that these local-scale processes were linked → 状语从句 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 57 | gi_v02_f9966da85c80 | ielts17_test2_p3 I-03 | without any end objective in sight → 不是从句（短语或非谓语） | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 58 | gi_v02_c16a8fb4b4a4 | ielts19_test3_p3 B-03 | that lecturers speak clearly, don't have to compete with background chatter, and say much the same thing each year → 名词性从句 | it为形式主语，that...为名词性从句，三个谓语并列在内部 | 原句可读；本次未见阻止使用的问题 |
| 59 | gi_v02_dcdc0e88ec46 | ielts15_test3_p2 E-02 | after field tests are carried out → 状语从句 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 60 | gi_v02_62509978a7d0 | ielts8_test4_p2 I-01 | known to exert devious influence on agriculture and human health in both India and Australia → 不是从句（短语或非谓语） | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |

### T4（20道，全部auto）

| 序 | 题号 | 来源 | 答案/目标 | 判定 | 原句/题目适用性 |
| --- | --- | --- | --- | --- | --- |
| 61 | gi_v02_57876a908e1c | ielts9_test1_p2 E-33 | if faced with a superior and much older civilization → 条件 | if faced省主语和be，按省略条件从句口径成立 | 原句可读；本次未见阻止使用的问题 |
| 62 | gi_v02_e2aa7729c6b0 | ielts8_test3_p1 F-02 | If a laser could generate a line of ionisation in the air all the way up to a storm cloud → 条件 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 63 | gi_v02_bd90f60ed66a | ielts5_test4_p2 J-40 | before experts were finally called in → 时间 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 64 | gi_v02_0628b13312c2 | ielts4_test4_p1 F-27 | as long as our training continues to improve → 条件 | as long as为条件；引语末标点不扩大从句范围 | 原句可读；本次未见阻止使用的问题 |
| 65 | gi_v02_bda011edf0d9 | ielts14_test4_p3 K-02 | until after they've happened → 时间 | until after...仍表示时间关系；不是原因/条件 | 原句可读；本次未见阻止使用的问题 |
| 66 | gi_v02_a842071cfde4 | ielts9_test2_p1 H-03 | so that all children, youth learners and adult learners will have equal opportunities to learn and develop within their already existing local school → 目的 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 67 | gi_v02_be1bd61fe1e2 | ielts6_test3_p2 B-07 | If participation and the culture are incongruous → 条件 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 68 | gi_v02_4c972ce0bfc7 | ielts4_test2_p1 F-31 | If a person shifts from Navajo to English → 条件 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 69 | gi_v02_c18daabb7c74 | ielts7_test1_p1 B-05 | although there is light → 让步 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 70 | gi_v02_6f9122901fa9 | ielts11_test1_p1 E-05 | unless cheap, renewable energy is available → 条件 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 71 | gi_v02_e3a86a2e4e22 | ielts6_test4_p3 C-04 | when it occurs → 时间 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 72 | gi_v02_9ed4233cb9e3 | ielts6_test3_p2 B-06 | If participation is inconsistent with the culture → 条件 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 73 | gi_v02_dcb2ae6ed686 | ielts5_test4_p2 I-36 | if you experience one nickel sulphide failure in your building → 条件 | 所标if确为条件；另一个even if未混入该目标 | 原句可读；本次未见阻止使用的问题 |
| 74 | gi_v02_0e44d851d08f | ielts18_test3_p2 C-05 | Though the Doble boys' third prototype, nicknamed the Model B, still lacked the convenience of an internal combustion engine → 让步 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 75 | gi_v02_22c11d651099 | ielts15_test2_p1 F-01 | If their designers had had the tools to think with their bodies – like dancers – and imagine how these barriers would feel → 条件 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 76 | gi_v02_ba6976615910 | ielts5_test2_p3 H-31 | Although a proposal in 1664 to establish a committee for improving the English language came to little → 让步 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 77 | gi_v02_23908fd7c6e7 | ielts13_test4_p2 C-01 | If the soil loses its ability to perform these functions → 条件 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 78 | gi_v02_74e62eeb6224 | ielts18_test3_p1 A-05 | If concrete is the only answer to the construction of new cities → 条件 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 79 | gi_v02_28b9c5156164 | ielts16_test1_p2 D-06 | If someone wished to enter → 条件 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 80 | gi_v02_fe308ec5ab28 | ielts12_test8_p2 A-06 | If this is so → 条件 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |

### T5（20道，全部auto）

| 序 | 题号 | 来源 | 答案/目标 | 判定 | 原句/题目适用性 |
| --- | --- | --- | --- | --- | --- |
| 81 | gi_v02_9a2fbc7a68d8 | ielts12_test8_p1 D-03 | Joseph Paxton's Crystal Palace at London's Great Exhibition of 1851 | 主语包含Paxton所有格和at...后置修饰；完整 | 原句可读；本次未见阻止使用的问题 |
| 82 | gi_v02_01e02c1d22ba | ielts8_test3_p1 A-02 | Their electrical fury | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 83 | gi_v02_f4a4b3205850 | ielts11_test2_p2 E-04 | Recent experiments | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 84 | gi_v02_df2637806a4e | ielts12_test6_p1 B-01 | Farmers everywhere | everywhere可作后置修饰，完整主语可成立 | 原句可读；本次未见阻止使用的问题 |
| 85 | gi_v02_4b89f9052b56 | ielts17_test3_p3 F-02 | the introduction of iron and steel skeletal frames | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 86 | gi_v02_b161dfec53d9 | ielts19_test3_p1 E-01 | the climate | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 87 | gi_v02_6b9738442ffc | ielts13_test4_p1 E-08 | Cutty Sark | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 88 | gi_v02_12403cf7f89a | ielts8_test2_p3 F-04 | our sense of smell | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 89 | gi_v02_2fce6d9cf0b4 | ielts13_test4_p3 D-06 | Bentham | Davies writes是插入归属语；所述主层Bentham为主语 | 原句可读；本次未见阻止使用的问题 |
| 90 | gi_v02_16c5ea3f5034 | ielts7_test4_p1 B-05 | The object in the sky | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 91 | gi_v02_f1d7e830edcc | ielts13_test2_p1 A-04 | the spice | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 92 | gi_v02_ca9ecb29f7b2 | ielts4_test2_p1 C-17 | The critically endangered languages | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 93 | gi_v02_6a8abdcefa66 | ielts15_test3_p2 C-06 | it | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 94 | gi_v02_5aab95387e5a | ielts16_test4_p3 A-02 | Police forces | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 95 | gi_v02_b5cd5d7ab5e4 | ielts11_test2_p1 F-08 | This | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 96 | gi_v02_76facbfed13b | ielts20_test3_p3 G-01 | This | 引语问句是question的同位内容；外层主语This明确 | 原句可读；本次未见阻止使用的问题 |
| 97 | gi_v02_468d44ba33bf | ielts13_test2_p3 G-03 | your innovations | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 98 | gi_v02_db09355ac7cf | ielts16_test4_p1 E-01 | Roman tunnel projects | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 99 | gi_v02_8021df45aaef | ielts4_test3_p1 I-02 | Some | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 100 | gi_v02_40784676ab23 | ielts20_test2_p3 C-14 | the arguments | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |

### T6（20道，全部auto）

| 序 | 题号 | 来源 | 答案/目标 | 判定 | 原句/题目适用性 |
| --- | --- | --- | --- | --- | --- |
| 101 | gi_v02_526cbaa11e79 | ielts7_test2_p1 D-18 | is found → 从句里的谓语 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 102 | gi_v02_324fef3d4164 | ielts14_test1_p1 N-03 | wrote → 主句谓语 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 103 | gi_v02_8ef902d31940 | ielts6_test3_p3 C-13 | means → 从句里的谓语 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 104 | gi_v02_6e5fe0e50540 | ielts20_test1_p1 I-04 | were removed → 从句里的谓语 | were removed处在until从句中；单位完整 | 原句可读；本次未见阻止使用的问题 |
| 105 | gi_v02_b9015b1278c1 | ielts9_test2_p3 G-01 | must sell → 主句谓语 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 106 | gi_v02_2c9e9b093a8d | ielts8_test2_p3 C-02 | is held → 从句里的谓语 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 107 | gi_v02_ffba011362dd | ielts7_test3_p3 A-10 | bordering → 非谓语（不定式、分词、动名词） | bordering后置分词，非谓语正确；原句插入such as说明的闭合逗号可斟酌，仍可读 | 原句可读；本次未见阻止使用的问题 |
| 108 | gi_v02_3dd84b0c9074 | ielts11_test3_p3 E-02 | illustrate → 从句里的谓语 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 109 | gi_v02_bb7cc4f611b1 | ielts19_test3_p2 E-03 | to allow → 非谓语（不定式、分词、动名词） | to allow为非谓语；for为介词不按小品词并入 | 原句可读；本次未见阻止使用的问题 |
| 110 | gi_v02_2e3bdfa37ee4 | ielts13_test2_p1 C-04 | associated → 非谓语（不定式、分词、动名词） | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 111 | gi_v02_7caefd78b630 | ielts12_test6_p1 E-01 | to address → 非谓语（不定式、分词、动名词） | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 112 | gi_v02_35073da97a78 | ielts7_test3_p1 D-03b | to control → 非谓语（不定式、分词、动名词） | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 113 | gi_v02_c4e8da169f70 | ielts19_test3_p1 I-01 | owned → 从句里的谓语 | owned为who从句谓语；不受前面的其他从句影响 | 原句可读；本次未见阻止使用的问题 |
| 114 | gi_v02_647a06086b2d | ielts6_test3_p3 B-05 | could stick → 主句谓语 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 115 | gi_v02_98c60996b700 | ielts11_test2_p2 D-03 | to protect → 非谓语（不定式、分词、动名词） | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 116 | gi_v02_7504e85f071d | ielts13_test4_p1 I-03 | carried → 主句谓语 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 117 | gi_v02_9496c36d673b | ielts16_test1_p3 G-01 | observed → 主句谓语 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 118 | gi_v02_66224cac0870 | ielts4_test3_p3 F-28 | can be covered → 主句谓语 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 119 | gi_v02_9a33a2de40d5 | ielts4_test1_p1 H-03 | provided → 从句里的谓语 | 局部答案、高亮、所给干扰项及题干前提本次未见问题 | 原句可读；本次未见阻止使用的问题 |
| 120 | gi_v02_e13527c5d154 | ielts16_test4_p1 D-04 | were also built → 主句谓语 | were / built跨also完整高亮 | 原句可读；本次未见阻止使用的问题 |

计数：T1为19局部/判分未见问题+1 AB1；T2的20局部目标均可成立，但1明确多解、1嵌套层级风险属于既有A8；T3/T4/T5/T6各20未见新增问题。不能把needs题混进“全部正确”，也不把一次样本当作全池无错率证明。

## 8. 与以往不同角度的全池扫描

### 8.1 非典型主语：从句/动名词主语、倒装、形式主语与前置表语

扫描全部27849剑桥auto，针对T5检查：root有expl子节点、答案在root之后、root有csubj/csubjpass子节点、或attr/acomp在root之前。前两种在现有subject_boundary已拒绝，因此当前命中**29道**，主要为动名词主语。逐题结果如下，29道均auto；未把解析器给growing towns和书名Building...的csubj标签当作语义事实。此角度不同于前轮be分词、小品词、连字符、否定、共享助动词扫描。

| 序 | 题号 | 来源 | 完整主语 | 判断 |
| --- | --- | --- | --- | --- |
| 1 | gi_v02_2a26511d5f00 | ielts10_test1_p3 E-01 | Managing innovation | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 2 | gi_v02_a0c970880112 | ielts10_test3_p3 H-02 | overshooting their home ports, getting lost and sailing off into eternity | 三个动名词并列整体为主语；完整 |
| 3 | gi_v02_8c34af6eded8 | ielts10_test4_p1 E-02 | Doing that in many of the forests of the western US | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 4 | gi_v02_c5b9d25d8ff8 | ielts11_test1_p1 F-02 | Moving the trays | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 5 | gi_v02_c3b3bce183c2 | ielts12_test5_p2 A-03 | Amassing hundreds or even thousands of postcards, chocolate wrappers or whatever | Amassing...主语完整；末逗号是长主语停顿，不新增原句缺陷判定 |
| 6 | gi_v02_fa88409fcedf | ielts13_test1_p2 A-02 | defining boredom so that it can be studied in the lab | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 7 | gi_v02_5a5591db87d3 | ielts13_test1_p2 D-13 | repeatedly failing to engage attention | says Eastwood插入语不进入主语；正确 |
| 8 | gi_v02_da7bb863e856 | ielts13_test1_p3 G-07 | finding those greater depths in computer art | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 9 | gi_v02_e1d5e93eb38f | ielts13_test2_p2 C-03 | administering oxytocin | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 10 | gi_v02_f9cdff9950f6 | ielts14_test1_p3 I-04 | just fulfilling these needs | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 11 | gi_v02_adebd5b9523b | ielts14_test3_p1 E-01 | understanding implicit theories of intelligence | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 12 | gi_v02_db77f01e0488 | ielts14_test4_p3 L-01 | Asking the right questions | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 13 | gi_v02_ea7c519a6987 | ielts14_test4_p3 M-03 | Interrogating the existing scientific literature | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 14 | gi_v02_beef93edb1fb | ielts15_test4_p1 C-04 | Cutting down native woodland | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 15 | gi_v02_a8db19b623a3 | ielts16_test2_p3 E-03 | Looking at problems from this more expansive viewpoint | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 16 | gi_v02_ece11f1a490c | ielts16_test2_p3 J-03 | knowing how wisely a person behaves in a given situation | knowing...含how宾语从句；整体完整 |
| 17 | gi_v02_c60c52575de5 | ielts16_test3_p2 G-04 | growing Norwegian towns, along with export markets | 实际是growing修饰towns的名词主语，非动名词；答案仍完整，along with补充修饰未漏 |
| 18 | gi_v02_ac32929d971d | ielts16_test4_p3 D-07 | refusing to accept the advantages offered by AI | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 19 | gi_v02_8655c378838f | ielts16_test4_p3 E-02 | Simply having previous experience with AI | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 20 | gi_v02_476924b69fd8 | ielts17_test3_p3 A-03 | Building the Skyline | Building the Skyline是书名，虽模型标csubj，完整题目答案仍正确 |
| 21 | gi_v02_df380d5f2f43 | ielts18_test3_p1 E-03 | treating wood and combining it with other materials | 两个动名词并列整体完整 |
| 22 | gi_v02_2f7a93a097b5 | ielts18_test3_p1 F-03 | using timber in a building | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 23 | gi_v02_a44a59a30fd8 | ielts18_test4_p1 C-05 | Being able to keep enough water at roof height and distribute it right across the rooftop | Being able...内部共享to的并列补足完整 |
| 24 | gi_v02_d6cc592471d8 | ielts18_test4_p1 C-07 | Having a stronger roof | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 25 | gi_v02_d8e09ded47f3 | ielts19_test3_p2 C-05 | Implementing climate change projects | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 26 | gi_v02_c8d3f341a0f6 | ielts20_test3_p2 F-05 | Saving our coral reefs | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 27 | gi_v02_e8ef333e90aa | ielts6_test1_p1 E-01 | Using data | 动名词主语及宾语/修饰/补足完整，未见问题 |
| 28 | gi_v02_ca7e5db090c4 | ielts7_test1_p3 A-01 | Educating Psyche by Bernie Neville | Educating Psyche是书名，by Bernie Neville为后置说明；整体可成立 |
| 29 | gi_v02_5208b1a7ffa8 | ielts7_test4_p1 B-07 | investigating the possibility of using kites as heavy lifters | 动名词主语及宾语/修饰/补足完整，未见问题 |

### 8.2 随机题触发的系动词评分中心扫描

对全Cambridge auto T1/T6的答案/target.parts取token，查dep属于aux/auxpass但词形来自become/remain/seem/appear/feel/look/stay/grow/turn及常见变形的词。命中15题，全部是become/remain，逐题见AB1表。排除了普通be/have/do/modal、get-passive等，避免把真正助动词一概误伤。此表是15个命中、不是15个确定错误：明确应修T1五道，T6十道只确认显示范围与系表口径需统一。

扫描还看到词汇化介词/分词的既有教学口径边界（例如according to），本轮没有把“不是主句谓语的干扰项”一概升级为新的判分错误；与已披露given + NP口径一起留待统一。没有修改任何原标注。

## 9. 候选池差异与报告

比较本轮全池与完整3257477快照的全池，按item_id逐字段比较，结论如下。候选包含auto和needs；rejected是尝试记录，不混进50243题。

| 指标 | 实测 |
| --- | --- |
| 候选/ID集合 | 50243 → 50243；新增0、删除0 |
| 共同题其他字段 | 除status/reasons之外0处变化 |
| auto→needs | 剑桥5（T1 2/T6 3），机经1（T6） |
| needs→auto | 0 |
| auto合计 | 40327；剑桥27849，机经12478 |
| 新原因全量 | participle_after_be：剑桥5/机经0；lexical_conjunction：剑桥4/机经5 |
| 回归/过滤 | 13×6回归完全相同；7项整句过滤expected=actual |

| 模板 | auto | needs | rejected尝试 |
| --- | --- | --- | --- |
| main_verb_tap | 5832 | 547 | 6367 |
| clause_boundary | 4678 | 2584 | 2694 |
| clause_type_classify | 11401 | 3486 | 1331 |
| adverbial_relation | 399 | 657 | 2561 |
| subject_span | 5365 | 819 | 6562 |
| finite_or_not | 12652 | 1823 | 6549 |

| 降级题 | 来源/模板 | 原因 | 独立判断 |
| --- | --- | --- | --- |
| gi_v02_108f07638465 | ielts14_test2_p2 H-02 T6 | participle_after_be | 按AA1/AA2送审合理，内容未被改正 |
| gi_v02_31a694497b01 | ielts18_test2_p3 C-03 T6 | lexical_conjunction | 按AA1/AA2送审合理，内容未被改正 |
| gi_v02_4490077dd6af | reading_jijing_9_test_81_p2 I-10 T6 | lexical_conjunction | 按AA1/AA2送审合理，内容未被改正 |
| gi_v02_56671bb1833d | ielts14_test2_p2 H-02 T1 | participle_after_be | 按AA1/AA2送审合理，内容未被改正 |
| gi_v02_7009c768706e | ielts14_test3_p2 F-06 T1 | participle_after_be | 按AA1/AA2送审合理，内容未被改正 |
| gi_v02_d765c317f6a7 | ielts14_test3_p2 F-06 T6 | participle_after_be | 按AA1/AA2送审合理，内容未被改正 |

| 整句过滤 | expected | actual |
| --- | --- | --- |
| tagged_fragment | 30 | 30 |
| clause_attached_to_conjunction | 2 | 2 |
| glued_sentence_boundary | 0 | 0 |
| multi_sentence_unit | 1 | 1 |
| suspected_split_word | 0 | 0 |
| leading_stray_punctuation | 0 | 0 |
| control_character | 0 | 0 |

counting_notes与代码的限定一致：它写的是“像引导词那样挂且无主语/助动词”和两种be挂法，未声称解决全部被动或词汇化用法。文档命中数量的两处差异独立列AB2。

## 10. 双次生成、环境、SHA与xlsx

- macOS 27.0.1（26A434），arm64；Python3.13.3、spaCy3.8.16、en_core_web_trf3.8.0、torch2.14.1 CPU、openpyxl3.1.5；seed20261018。
- 阅读数据SHA：`55b808e1a69cfb7fc06670a6ac3bb36d2861923f229183875ed309ea3a747f37`；图谱SHA：`c7b35ddb68db7601ccd01e38a210ad3dd772ff507302190f68a351e408b85a29`。
- 在仓库外完整e290快照运行指定G，沿用同版本/同环境、原句字节未变的本机解析缓存；**不是重新全库解析**。另取AA1/AA3全部匹配来源24个不同文本现用模型重新解析，逐字段相同。
- 两次执行：`G scripts/generate_grammar_candidates.py --seed 20261018`（cwd=`O/source`），分别保留`O/first`与`O/second`。四文件两次逐字节相同；JSONL/XLSX与提交版相同；两报告仅Python版本一行3.13.3对3.11.15不同，无其他行差。

| 文件 | 第1次SHA-256 | 第2次SHA-256 | 提交版SHA-256 |
| --- | --- | --- | --- |
| generation_report_v0_2.json | b20452ced5c470eb820c0862737d75756c5528b771e2a2f1b03dbc1197e07737 | b20452ced5c470eb820c0862737d75756c5528b771e2a2f1b03dbc1197e07737 | f775880b9a79e59afaa91621493c14adc2b24935aba7a690305e147b67dbbcbe |
| generation_report_v0_2.md | 9d2cf9de57efe39929afd1d4bf83a0890d1df4320ab5a030605bf6f37cd1e412 | 9d2cf9de57efe39929afd1d4bf83a0890d1df4320ab5a030605bf6f37cd1e412 | 06b22698c6823b7d2ffce469d2d7eac5979bfd548fcab7b50ea2fa04b0bfcba6 |
| review_batch_v0_2.jsonl | bfd4b24f41e5c5bb16f6cc690af6ec31b9d8907a08edeec4ef9f07f70c03866d | bfd4b24f41e5c5bb16f6cc690af6ec31b9d8907a08edeec4ef9f07f70c03866d | bfd4b24f41e5c5bb16f6cc690af6ec31b9d8907a08edeec4ef9f07f70c03866d |
| review_batch_v0_2.xlsx | 02e84d26c9cf40dc07407ee0357b650d7fed77716371b475becde65fbf2190a2 | 02e84d26c9cf40dc07407ee0357b650d7fed77716371b475becde65fbf2190a2 | 02e84d26c9cf40dc07407ee0357b650d7fed77716371b475becde65fbf2190a2 |

xlsx直接解包核所有单元格、共享字符串和验证定义，并与teacher_row逐行对照：7工作表，六题型每表60数据行；H2:H61均为“正确/答案错/题目有歧义/句子不适合出题”四项下拉。老师可见行无auto_pass、needs_review、原因码，盲审保持。没有填老师判定，也没有重新决定盲审范围。

抽查表来源：剑桥227=196auto+31needs；机经133=104auto+29needs。与3257477相比，**保留26个题号、2个相同(模板/工作表,行号)位置**。不能按旧行号迁移老师答案，应按题号核对。这里只验证格式和内容投影，并非把360题全部做了语法人工复审。

## 11. 测试、负测与数据检查

实际专项命令（cwd=R）：

```sh
.venv-grammar-tools/bin/python -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary tests.test_grammar_graph_draft -v
.venv-grammar-tools/bin/python scripts/validate_reading_study.py
.venv-grammar-tools/bin/python scripts/reading_jijing_text_fixes.py --check
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_reading_study -v
/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tests/test_dictation_spell_queue.js
```

专项149通过；reading22通过；Node exit0；validator0错误（317/387已就绪，70缺失为既有覆盖状态）；--check输出0。

全新O/flask-only：用G创建venv，`O/flask-only/bin/python -m pip install --cert /etc/ssl/cert.pem Flask`，只安装Flask及其必需依赖，未安装spaCy/SQLAlchemy等。按当前ci.yml完整列表运行：

```sh
O/flask-only/bin/python -m unittest   tests.test_miniprogram_guest_access   tests.test_miniprogram_dictation_grouping   tests.test_inventory_toefl_materials   tests.test_organize_toefl_materials   tests.test_extract_toefl_answer_keys   tests.test_map_toefl_answers_to_practice_docs   tests.test_import_toefl_official_reading   tests.test_reading_vocab_grading   tests.test_stats_utils   tests.test_grammar_graph_draft   tests.test_grammar_item_candidates   tests.test_reading_jijing_text_fixes   tests.test_reading_study_glossary -v
```

实测217运行=216通过+1按设计跳过；不是217全部执行成功。Node检查另行通过。

```sh
P -m ruff check --config 'extend-exclude=[]' scripts/grammar_items/templates.py scripts/grammar_items/checks.py scripts/grammar_items/reporting.py tests/test_grammar_item_candidates.py
P -m ruff format --check --config 'extend-exclude=[]' scripts/grammar_items/templates.py scripts/grammar_items/checks.py scripts/grammar_items/reporting.py tests/test_grammar_item_candidates.py
```

Ruff0.15.21，四个改动Python check/format均通过；未自动修复/格式化文件。

新测试负测：将325版checks/templates装入隔离进程，运行本轮新增的5个test方法，未改被审文件；实际命令`G O/negative_tests.py`。确认3断言失败、2接口错误，与Claude记录一致。

| 测试 | 旧码结果 | 说明 |
| --- | --- | --- |
| BeParticipleTests.test_adjectival_participles_unaffected | 接口错误 | 缺Reason.PARTICIPLE_AFTER_BE；不是语义断言失败 |
| BeParticipleTests.test_participle_hung_as_dep_goes_to_review | 断言失败 | 未产生应有needs或真动词被误判 |
| BeParticipleTests.test_participle_series_goes_to_review | 接口错误 | 缺Reason.PARTICIPLE_AFTER_BE；不是语义断言失败 |
| ConjunctionParticipleTests.test_given_that_is_not_classified_as_a_verb | 断言失败 | 未产生应有needs或真动词被误判 |
| ConjunctionParticipleTests.test_verbs_before_that_stay_verbs | 断言失败 | 未产生应有needs或真动词被误判 |

数据检查：`G O/audit_data.py`导入现有build_reading_test_practice，替换localize_image为纯路径计算，不下载图片；从raw在内存重建171篇，逐篇content整体（含summary）和groups与static一致。未只比paragraphs，也未写回static。`G scripts/render_grammar_graph_review.py`在O/source生成的图谱文档与提交版逐字节相同。

## 12. 完整main快照到本轮的临时SQLite导入

固定用户指定676569c。对完整快照中2853个tracked blob按Git对象哈希逐一校验；代码、static、data、models和导入脚本都来自main，不拼接当前static。未改阅读解析的说法也由本次diff核实。

```sh
P O/import_snapshot.py O/main main
P O/import_snapshot.py O/source current
```

先main created317/updated0/skipped0/failed0；再e290 created0/**updated236/skipped81/failed0**，总317。连接URI固定为`sqlite:///.../grammar-v02-round15-20261028/main-to-current.sqlite`，没有读取生产连接、服务器或远程数据库。

本机共享origin/main跟踪引用实际为`ee94abb30d56b3c9623c519f75c1ffa9679c65b5`，已超出提示中的676569c；仍按明确要求用676569c固定基线，没有擅自改用最新main，也没有合并main。

## 13. 机经（暂缓）

本轮新确认问题0项。用户要求核的9_81_p2 I-10 given已经降级，见§5；其余4道同类原needs维持needs。AA1两处机经raw匹配只列出语法判断，不把无适用题的启发式命中虚报成新增受害题。已暂缓机经项目、主语Seeing的既有教学口径不重复计数；未据此扩大修复范围。

## 14. 限制、交接、提交与CI

- 本轮只写本报告、CODEX_HANDOFF、WORKLOG，未改被审代码/数据/原标注/交付文件；没有大模型API调用、生产服务器/数据库操作、main推送、PR、后端部署、小程序上传/提审/发布。
- 检查均可执行并完成。与提示预期不同的是AB2计数（7而非8；19=13+6而非20=13+7），不是未做检查；两报告的Python版本行差为预期。未声称复审能证明整个池子无错误。
- 任务树入口干净；本轮提交前仅3文档变更。仓库外O下有完整快照、检查脚本、全池/缓存、日志、SQLite，仅本机可见，不随Git推送；报告提供算法、题号、命令和哈希供跨机器重做。
- 桌面工作树`/Users/zhouxin/Desktop/studytracker`仍main@6ded77d24586327ad94e151e172ae4811b4a2eed、behind87，已有7modified/22untracked入口未改；只借其venv。详细路径保留于该树git status和此前交接，不能把任务分支成果当作桌面main已有。
- 基线e290的[CI40544066693](https://github.com/KB77GG/studytracker/actions/runs/40544066693)已核：test成功，lint advisory失败/format跳过；本次审核提交的精确head CI将在推送后补记，不能沿用基线CI冒充。
- 下一位按用户授权先处理AB1的5道T1评分中心并保留正常助动词控制，统一10道T6的显示口径；按AB2更正文档计数。老师盲审范围和上线仍待用户决定。本轮没有实施这些建议。

