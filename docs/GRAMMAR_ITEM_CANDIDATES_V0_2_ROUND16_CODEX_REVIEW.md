# 语法候选题 v0.2 第十六轮独立复审（Codex）

审核日期：2026-10-28，Asia/Shanghai。**结论：不通过，以剑桥题为准。** 第十六轮 AB1、AB2 的指定修复均关闭；本轮新增 **0 阻断、2 应修（AC1、AC2）、0 单列建议**。AC1 是1道自动通过的关系题把介词短语当作状语从句；AC2 是1句剑桥原文把10⁹排成109，影响6道自动题。两项共7道不同的剑桥auto题，均与第十五轮逐字段相同，属于新发现的存量问题，**不是本轮引入**。机经本轮新确认问题0项，旧暂缓不重复计数。

120题随机样本均取自auto池：119题局部答案/高亮可成立；1题considering的词类/教学口径是已披露待定项，不算新问题。在119题里，1题原句有AC2排印错误，另3题有既有引语主句、宾语隔开的小品词或T2嵌套多解提示。不能把119个局部判断概括为119题全部可直接唯一判分。

## 1. 范围、关闭情况与权限

- 任务工作树：`/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker`；分支`codex/grammar-item-candidates`。
- 开工读目录链AGENTS、CLAUDE、HANDOFF最新两节、WORKLOG顶部，并以实际Git核对。起点`0308aabb235c467d34e0f8ffe2b58759ac25838b`干净；fetch后ff-only到固定`8e04e1712bebc222bb811c7422135a99915a10fd`。未普通merge、rebase、改写历史或合main。
- `git diff --stat 0308aab..8e04e17`：11文件、526插入/405删除。4个Python、4交付、3文档，全部在允许范围。阅读解析、raw、static、修订表、models.py、app.py、api、miniprogram、工作流均零改动。新增判定函数及接入点不读passage_id/sentence_id/item_id；原有题号生成器不等于ID黑名单。
- 所有生成、探针、临时数据库在仓库外`O=/Users/zhouxin/.codex/audits/grammar-v02-round16-20261028`。`O/source`是完整8e04e17快照，`O/baseline`是此前完整e2903b1快照。本轮不覆盖任务树任何被审文件。

| 编号 | 关闭 | 独立结论 |
| --- | --- | --- |
| AB1 | 指定问题关闭 | 点名5 T1+10 T6全部needs，另4 T1因干扰项合理送审；该4句的主句T6仍auto。原答案没修，但已撤出自动池。其余词形、其他挂靠不是穷尽保证。 |
| AB2 | 关闭 | 按来源句+token位置去重，be_participle=7；旧分词+that条件=19，其中13保留、6排除。文档两处已准确更正。历史缓存重复行的计数解释不替代本轮重算。 |

## 2. 八项检查及实际命令

R=上述任务树；G=`$R/.venv-grammar-tools/bin/python`；P=`/Users/zhouxin/Desktop/studytracker/.venv/bin/python`；N=`/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`。除明确写明，正式测试在R，辅助脚本在O，生成在O/source。辅助脚本只写O。

| 项 | 结果 | 实际命令/证据 |
| --- | --- | --- |
| 1 | 通过 | git status --short --branch；git log -5 --oneline；git fetch origin claude/word-memorization-system-eval-55v2y5；git merge --ff-only 8e04e1712bebc222bb811c7422135a99915a10fd；git diff --stat 0308aab..8e04e17；G O/audit_data.py |
| 2 | 指定修复通过 | G O/probe_rules.py；G O/controls.py；G O/final_probes.py。22题逐项、23语料token、26个其他挂靠来源、13真实控制句、230直接条件组合；见§4。 |
| 3 | 通过 | G O/probe_rules.py；全12746个来源句逐token重新计算，19/13/6和7；见§5。 |
| 4 | 发现2项存量问题 | G O/audit_runtime.py按seed20261105抽120；G O/scan_clause_finiteness.py查从句题题干前提；G O/probe_rules.py查to/动名词及数值排印；人工逐题；见§3、6、7。 |
| 5 | 全部复现 | G O/audit_runtime.py比较完整50243题；无ID或其他字段变化；Cam19/Jij2降级；见§8。 |
| 6 | 通过 | G O/generate.py在O/source两次运行G scripts/generate_grammar_candidates.py --seed 20261018；G O/audit_runtime.py核4文件字节、78回归、7过滤、xlsx360行；见§9。 |
| 7 | 通过 | G O/run_checks.py；G O/negative_tests.py；G O/audit_data.py；151专项、219运行/1跳过、22 reading、Node、Ruff、raw171/图谱/validator/textcheck，精确命令见§10。 |
| 8 | 通过 | P O/import_snapshot.py O/main main；P O/import_snapshot.py O/source current。固定676569c完整快照2853个Git blob逐一核对；236updated/81skipped/0failed；见§11。 |

## 3. 剑桥问题清单

### AC1 — 应修：T4缺少目标类别核验，介词短语被称为状语从句

位置：`scripts/grammar_items/templates.py:863`的adverbial_relations（尤其886行只调用predicative_clause）；`data/reading_study/ielts14_test2_p3.json` E-02；题号`gi_v02_cf28b13ef739`。

目标为`until the point where any further increase in order reduces productivity`。整体结构是 **until + 名词短语the point（带where定语从句）**；where从句修饰point。它可以作状语、表达终点，但不能因此把整个目标称为“状语从句”。局部“时间”可理解，**题干预设错误**。同目标T2 `gi_v02_b8929c66e100`和T3 `gi_v02_e4ae9c9ac17d`已因clause_type_mismatch待复核，T4却auto无原因。

复现：生成全池后按此题号读prompt、target、status；解析器为until/prep→point/pobj→reduces/relcl，T4本身的evidence head=until、finite=false。本轮新角度扫所有剑桥auto T2/T3/T4，筛中心无限定性，共9题；人工剔除合法省略和解析误挂后仅此1题成立，见§7。不是把所有finite=false直接判错。

建议：修正该标注的外层类别；同时让T4核验外层目标是否是其题干所称的从句。针对“介词＋名词中心＋其定语从句”设通用送审条件，不按句子/题号列黑名单。应保留`if sustained...`、`although treated...`等合法省略控制，以及`after training stops`这类实际含完整限定从句但解析错挂的控制。不要直接复用一个会误伤全部省略句的粗暴finite判断。

语法依据：until可以是介词或连词，是否带名词短语或从句需分别分析。[Cambridge English Grammar Today: Until](https://dictionary.cambridge.org/grammar/british-grammar/until)。这里的具体结构判断来自本句，而非仅凭词典词性。

### AC2 — 应修：原版10⁹丢失上标成为109，六道题仍自动通过

位置：`static/reading_tests/ielts11_test1_reading.json:43` A段；`data/reading_study/ielts11_test1_p1.json:120` A-03（句子、subject文本及155行难点也写109）。原版明确为 **10⁹ hectares**，库内成了 **109 hectares**；中文译文的“十亿公顷”正确。该句又括注面积比巴西大约20%，不能让学生按109理解。

证据：直接读取并渲染[剑桥出版社官方样章第18页（PDF第9页）](https://assets.cambridge.org/97813165/03850/excerpt/9781316503850_excerpt.pdf#page=9)，视觉确认9是上标；PDF文本提取本身也会把它扁平化成109，所以没有只信提取文本。PDF技能用于这一步版式核验；没有改任何原文。

复现：全池筛passage_id=ielts11_test1_p1、sentence_id=A-03；共12道候选，6auto+6needs。抽样第82题T5语法范围本身正确，但原句不宜直接给学生。6道auto如下；其余6已needs不计新增auto受影响数。

| 题号 | 模板 | 状态 | 局部答案与原句 |
| --- | --- | --- | --- |
| gi_v02_e9c210fd1e2b | T1 | auto_pass | will / be / needed；局部可成立，原句数值排印错误 |
| gi_v02_b0d13b157ddc | T3 | auto_pass | 状语从句；局部可成立，原句数值排印错误 |
| gi_v02_3de81a78963f | T4 | auto_pass | 条件；局部可成立，原句数值排印错误 |
| gi_v02_f00864c296fb | T5 | auto_pass | An estimated 109 hectares of new land (about 20% larger than Brazil)；局部可成立，原句数值排印错误 |
| gi_v02_6b030d70d081 | T6 | auto_pass | 主句谓语；局部可成立，原句数值排印错误 |
| gi_v02_d4ea719b03d3 | T6 | auto_pass | 从句里的谓语；局部可成立，原句数值排印错误 |

建议：单独授权后依据原版恢复10⁹或稳定的10^9/1,000,000,000显示，并同步正文、阅读解析成分/难点及相关题目引用。若暂不修剑桥原文，应通过现有通用source_quality审核状态撤出自动池；不要按ID在出题器打补丁。本轮只记录，未修改static或标注。

### 机经（暂缓）

本轮新确认问题0项；不重复罗列用户已暂缓项目。AB1涉及的2道新降、1道原有needs加原因属于本轮修复核验，见下一节，不算新的机经问题。

## 4. AB1逐题复核、隔离与控制

按候选status计：剑桥19道auto→needs（9T1/10T6）；机经2道auto→needs、1道needs→needs。全量22道带新原因，不把机经本来needs的那1道算新增降级。T1的5个主答案仍以分词作required_root；修复选择送审，不是已经改正判分。T6身份选项往往可成立，仅高亮/教学口径须统一。

| 题号 | 来源 | 模板 | 状态 | 答案 | 判读 |
| --- | --- | --- | --- | --- | --- |
| gi_v02_a35eb87063b9 | ielts11_test2_p1 B-05 | T6 | auto_pass→needs_review | 主句谓语 | 身份选项可成立；高亮含系动词及表语，送审合理 |
| gi_v02_dab43c9473dd | ielts11_test2_p1 B-05 | T1 | auto_pass→needs_review | became / covered | 评分中心仍为表语分词，送审合理 |
| gi_v02_81f2be3eccd1 | ielts11_test4_p1 D-03 | T1 | auto_pass→needs_review | visited | 主答案正确；干扰项含同类系表单位，送审合理 |
| gi_v02_92579fb7cf29 | ielts12_test8_p1 E-04 | T6 | auto_pass→needs_review | 从句里的谓语 | 身份选项可成立；高亮含系动词及表语，送审合理 |
| gi_v02_6ebbace57044 | ielts16_test1_p2 A-02 | T6 | auto_pass→needs_review | 主句谓语 | 身份选项可成立；高亮含系动词及表语，送审合理 |
| gi_v02_f5435b795551 | ielts16_test1_p2 A-02 | T1 | auto_pass→needs_review | have / become / linked | 评分中心仍为表语分词，送审合理 |
| gi_v02_c9f0705a51ac | ielts17_test1_p2 C-04 | T6 | auto_pass→needs_review | 主句谓语 | 身份选项可成立；高亮含系动词及表语，送审合理 |
| gi_v02_909373502a94 | ielts17_test1_p2 C-04 | T1 | auto_pass→needs_review | remain / embedded | 评分中心仍为表语分词，送审合理 |
| gi_v02_8d9d51eb274c | ielts18_test1_p2 F-01 | T6 | auto_pass→needs_review | 从句里的谓语 | 身份选项可成立；高亮含系动词及表语，送审合理 |
| gi_v02_dfe8bb019ea0 | ielts18_test1_p2 F-01 | T1 | auto_pass→needs_review | involves | 主答案正确；干扰项含同类系表单位，送审合理 |
| gi_v02_7284cbb08492 | ielts19_test2_p1 H-04 | T6 | auto_pass→needs_review | 从句里的谓语 | 身份选项可成立；高亮含系动词及表语，送审合理 |
| gi_v02_4fa9666eaddb | ielts19_test2_p1 H-04 | T1 | auto_pass→needs_review | were | 主答案正确；干扰项含同类系表单位，送审合理 |
| gi_v02_3b5789a23e3d | ielts5_test4_p1 B-18 | T6 | auto_pass→needs_review | 从句里的谓语 | 身份选项可成立；高亮含系动词及表语，送审合理 |
| gi_v02_9e88d6bc48fd | ielts8_test1_p1 C-05 | T6 | auto_pass→needs_review | 主句谓语 | 身份选项可成立；高亮含系动词及表语，送审合理 |
| gi_v02_9ab665ea6ed4 | ielts8_test1_p1 C-05 | T1 | auto_pass→needs_review | became / known | 评分中心仍为表语分词，送审合理 |
| gi_v02_637171dc92ff | ielts8_test1_p1 G-05 | T6 | auto_pass→needs_review | 从句里的谓语 | 身份选项可成立；高亮含系动词及表语，送审合理 |
| gi_v02_ef2cab00a4b6 | ielts9_test1_p1 B-01 | T6 | auto_pass→needs_review | 主句谓语 | 身份选项可成立；高亮含系动词及表语，送审合理 |
| gi_v02_6455e9eca58a | ielts9_test1_p1 B-01 | T1 | auto_pass→needs_review | became / immersed | 评分中心仍为表语分词，送审合理 |
| gi_v02_1d9ca106b1c8 | ielts9_test2_p3 G-09 | T1 | auto_pass→needs_review | shows | 主答案正确；干扰项含同类系表单位，送审合理 |
| gi_v02_e8e4a5ac2406 | reading_jijing_88_test_98_p3 F-02 | T6 | needs_review→needs_review | 从句里的谓语 | 身份选项可成立；高亮含系动词及表语，送审合理；既有source_quality不变 |
| gi_v02_cfead8704806 | reading_jijing_92_test_58_p3 D-01 | T6 | auto_pass→needs_review | 主句谓语 | 身份选项可成立；高亮含系动词及表语，送审合理 |
| gi_v02_aafce783270e | reading_jijing_92_test_58_p3 D-01 | T1 | auto_pass→needs_review | became / associated | 评分中心仍为表语分词，送审合理 |

### T6不继承干扰项原因

以下4道T1因干扰项降级，但同句主句T6逐字段保持auto；不是整句连坐。其余主句T6确有同类单位才自行命中新规则。

| T1 | 主句T6 | 高亮 | 前→后 |
| --- | --- | --- | --- |
| gi_v02_81f2be3eccd1 | gi_v02_c48430aee937 | visited | auto_pass→auto_pass |
| gi_v02_dfe8bb019ea0 | gi_v02_a60c9068c4f6 | involves | auto_pass→auto_pass |
| gi_v02_4fa9666eaddb | gi_v02_31291b5dff9d | were | auto_pass→auto_pass |
| gi_v02_1d9ca106b1c8 | gi_v02_23af82020407 | shows | auto_pass→auto_pass |

### 条件合理性及边界

aux/auxpass的依存并不能把become/remain变成英语助动词；用它作为“解析可能有误”的信号送审合理。词形表覆盖本语料实测23个来源token位置，扩展检查grown/feeling/looking以及sound/smell/taste/prove/go/fall/keep等词形后，未发现表外aux/auxpass实际命中。按源句而非缓存行计算。

对其他依存再查：26个来源的词形挂到VBN/VBG/JJ父节点且父节点有auto T1/T6。逐一读句后均不是本轮那种“系动词被并入表语单位”：多为shown→become/meaning→becomes等补语，或allowing→turn、beginning→appear等不定式；另growing Norwegian towns的解析有误，但本探针命中的主句动词单位仍是would have created。该扫描不是证明全部系表分析无误。

表没有grown、feeling、looking等全部词形，也不处理cop等其他依存。人工让grown处于auxpass可构造未命中；真实语料未发现受害题，列边界，不另算应修。未来扩大语料可改为有明确词元依据的词形集合，仍需控制正常助动词和真动词用法。

13句用本地spaCy现解析；230个直接token条件组合核对词形×依存。have become里的have、was built、get被动均不命中。47个规则语料来源加2个新问题来源，合计49个不同句子现解析逐字段与缓存一致。

| 控制句 | 实测单位及新原因 | 判断 |
| --- | --- | --- |
| He became immersed in chemistry. | became/auxpass→送审；immersed/ROOT→送审 | 前2句正确命中；其余正常助动词/系动词中心不误伤 |
| The ruins remain embedded in the shops. | remain/aux→送审；embedded/ROOT→送审 | 前2句正确命中；其余正常助动词/系动词中心不误伤 |
| They have become friends. | have/aux→不命中；become/ROOT→不命中 | 未新增原因，符合预期 |
| The bridge was built in 1900. | was/auxpass→不命中；built/ROOT→不命中 | 未新增原因，符合预期 |
| He got injured. | got/auxpass→不命中；injured/ROOT→不命中 | 未新增原因，符合预期 |
| He gets paid weekly. | gets/auxpass→不命中；paid/ROOT→不命中 | 未新增原因，符合预期 |
| They remained calm. | remained/ROOT→不命中 | 未新增原因，符合预期 |
| The door seems closed. | seems/ROOT→不命中；closed/oprd→不命中 | 未新增原因，符合预期 |
| The building appears abandoned. | appears/ROOT→不命中；abandoned/oprd→不命中 | 未新增原因，符合预期 |
| The leaves turned red. | turned/ROOT→不命中 | 未新增原因，符合预期 |
| The task has grown complicated. | has/aux→不命中；grown/ROOT→不命中 | 未新增原因，符合预期 |
| He is feeling tired. | is/aux→不命中；feeling/ROOT→不命中 | 未新增原因，符合预期 |
| The cloth looks faded. | looks/ROOT→不命中 | 未新增原因，符合预期 |

| 其他挂靠来源 | 词及依存→父节点 | AB1判断 |
| --- | --- | --- |
| ielts10_test4_p2 A-02 | looking/xcomp→begun | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts11_test1_p1 A-03 | grow/advcl→needed | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts11_test1_p2 F-04 | turn/ccomp→allowing | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts11_test1_p2 F-08 | remain/ccomp→ensuring | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts12_test6_p3 A-03 | look/ccomp→allowed | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts13_test1_p2 C-05 | feel/xcomp→made | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts13_test2_p2 B-07 | become/ccomp→shown | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts13_test4_p2 C-06 | becomes/ccomp→meaning | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts14_test4_p1 E-02 | seem/ccomp→showing | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts15_test1_p1 E-06 | growing/xcomp→caught | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts16_test3_p2 G-04 | growing/csubj→created | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts16_test3_p3 E-03 | grow/ccomp→enabling | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts18_test4_p1 E-01 | grows/advcl→developed | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts19_test1_p1 D-02 | look/advcl→becoming | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts19_test3_p3 C-04 | appear/xcomp→started | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts20_test2_p2 F-41 | feeling/conj→Forgiving | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts20_test2_p3 A-03 | looked/ccomp→mounted | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts20_test2_p3 E-23 | seems/ccomp→complained | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts4_test1_p2 F-01 | appear/advcl→compensated | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts5_test4_p1 B-16 | turned/ccomp→been | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts6_test1_p2 F-03 | become/advcl→exported | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts6_test1_p3 E-29 | appear/xcomp→beginning | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts7_test1_p1 D-03 | feels/ccomp→reported | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts7_test4_p1 A-06 | looked/ccomp→holding | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts8_test1_p1 G-03 | turn/ccomp→allowing | 未见系动词作为助动词并入父单位；不应因词形一律降级 |
| ielts9_test4_p1 H-02 | becoming/advcl→appointed | 未见系动词作为助动词并入父单位；不应因词形一律降级 |

## 5. AB2计数与逐位置复核

全库12746个来源句、12740种不同字符串。每个来源的每个token只计一次；同一字符串若确实属于不同来源仍分别计。be_participle=7；旧条件（词表+紧邻that/mark）=19，新规则保留13、排除6。文档现在与实测一致。

be表只复核计数，未把7个信号称为7个真被动；其中部分是保守误挂且没有适用候选。当前与上一轮函数/语料均不变。

| 来源 | be token | 判读 |
| --- | --- | --- |
| ielts14_test2_p2 H-02 | is #12 | is＋ventilated/cooled/lit串列，已送审 |
| ielts14_test3_p2 F-06 | are #3 | are＋encountered/dep，已送审 |
| ielts20_test2_p3 H-46 | are #4 | delineated是补充描写，解析挂靠信号不能直接等同漏被动 |
| ielts4_test4_p3 C-10 | are #18 | poverty-stricken/deprived系表/被动两可，原needs |
| ielts7_test1_p3 F-30 | be #10 | accomplished补充描写，非一律漏被动 |
| reading_jijing_13_test_6_p2 B-08 | were #2 | forgiven误挂前方be，不等于单位遗漏 |
| reading_jijing_29_test_63_p3 C-03 | are #5 | state-controlled/measured串列信号 |

| 来源 | 分词 | 现规则 | 判读 |
| --- | --- | --- | --- |
| ielts10_test2_p2 D-07 | Given #0 | 保留 | 连词用法成立 |
| ielts15_test4_p3 B-03 | provided #32 | 保留 | 连词用法成立 |
| ielts18_test2_p2 F-04 | given #6 | 保留 | 连词用法成立 |
| ielts18_test2_p3 C-03 | given #1 | 保留 | 连词用法成立 |
| ielts18_test4_p3 B-01 | supposing #27 | 排除 | 真动词/分词补语，不应按词形剔除 |
| ielts7_test1_p1 A-05 | Given #0 | 保留 | 连词用法成立 |
| ielts7_test1_p1 A-05 | given #13 | 保留 | 连词用法成立 |
| reading_jijing_10_test_78_p2 C-24 | Given #0 | 保留 | 连词用法成立 |
| reading_jijing_13_test_6_p2 B-08 | assuming #16 | 排除 | 真动词/分词补语，不应按词形剔除 |
| reading_jijing_18_test_53_p2 G-05 | Seeing #0 | 排除 | Seeing that作主语，按动名词/确保义分析合理 |
| reading_jijing_44_test_29_p2 E-04 | given #23 | 保留 | 连词用法成立 |
| reading_jijing_53_test_83_p2 E-04 | assuming #3 | 保留 | 连词用法成立 |
| reading_jijing_62_test_44_p3 I-04 | granted #14 | 排除 | 真动词/分词补语，不应按词形剔除 |
| reading_jijing_62_test_44_p3 K-05 | granted #7 | 排除 | 真动词/分词补语，不应按词形剔除 |
| reading_jijing_69_test_40_p2 B-04 | Considering #0 | 保留 | 连词用法成立 |
| reading_jijing_77_test_16_p2 F-01 | assuming #17 | 排除 | 真动词/分词补语，不应按词形剔除 |
| reading_jijing_83_test_95_p1 D-06 | Given #0 | 保留 | 连词用法成立 |
| reading_jijing_88_test_98_p1 J-03 | provided #11 | 保留 | 连词用法成立 |
| reading_jijing_9_test_81_p2 I-10 | Given #0 | 保留 | 连词用法成立 |

## 6. 120道剑桥auto抽样逐题表

方法：仅source_kind=reading_test且passage_id以ielts开头、status=auto_pass。按T1–T6顺序，每模板先按item_id排序，使用同一个`random.Random(20261105)`连续sample20；合计120，不含needs。不是从360行交付表抽样。报告每行给出题号，完整高亮可由全池或teacher_row复现。

“局部可成立”指所给局部语法答案/高亮；“可”指本次未发现妨碍教学的问题，不是对全库或科学事实的认证。第13/15/40/116为已披露边界，本次不重复计新问题；第82为AC2。局部119可成立、1既有口径待定；教学上115题未见本轮问题、1句原文需修、4题仍有既有教学/题干提醒。

### T1（20道，均auto_pass）

| # | 题号 | 来源 | 答案/目标 | 局部/题干/干扰项 | 整句与教学 |
| --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_20a3b0d8a40b | ielts16_test1_p3 H-02 | is | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 2 | gi_v02_d5b410aaab4c | ielts6_test1_p2 H-04 | started | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 3 | gi_v02_b5832e4b11aa | ielts8_test4_p2 J-05 | are / infested | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 4 | gi_v02_d19143d805b3 | ielts20_test3_p1 B-02 | had | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 5 | gi_v02_262f01689167 | ielts5_test2_p2 J-43 | explains | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 6 | gi_v02_e1d9e3c8a1bc | ielts10_test2_p3 F-01 | is / related | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 7 | gi_v02_9fd73846a9bc | ielts6_test2_p2 F-18 | live | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 8 | gi_v02_188e4296b6fc | ielts4_test1_p3 D-16 | created | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 9 | gi_v02_6a6b0fab16e7 | ielts6_test2_p2 K-36 | found | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 10 | gi_v02_a2570bf97325 | ielts15_test3_p3 C-01 | compare | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 11 | gi_v02_a70b2462b5f1 | ielts12_test8_p1 F-04 | can / imagine | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 12 | gi_v02_2b8a2391a393 | ielts15_test1_p3 E-04 | said | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 13 | gi_v02_6df3e5d71870 | ielts5_test1_p1 G-03 | will / be | will be在引语内是谓语；外层wrote也存在；既有W2引语主句口径；不能称唯一 | 原句可读；题目需明确主句层级 |
| 14 | gi_v02_e7fdb778e39f | ielts18_test4_p3 B-01 | was | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 15 | gi_v02_4df3214e4059 | ielts18_test4_p3 G-01 | left | left是主谓中心；behind被宾语隔开；既有小品词隔开未覆盖；单位完整性提示 | 原句可；动词单位口径待统一 |
| 16 | gi_v02_2bc0e49ed728 | ielts4_test1_p3 J-41 | concluded | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 17 | gi_v02_fd20cd898644 | ielts13_test2_p3 A-03 | is | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 18 | gi_v02_af734ca2b16b | ielts19_test3_p1 B-05 | travelled | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 19 | gi_v02_c876ca7042d5 | ielts15_test4_p3 B-01 | is | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 20 | gi_v02_c7e321ce2773 | ielts17_test2_p2 D-02 | looks | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |

### T2（20道，均auto_pass）

| # | 题号 | 来源 | 答案/目标 | 局部/题干/干扰项 | 整句与教学 |
| --- | --- | --- | --- | --- | --- |
| 21 | gi_v02_fae6e08ca96a | ielts16_test1_p3 I-01 | that the future of work will involve major transitions across the whole life course for everyone | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 22 | gi_v02_95805e56ef4e | ielts4_test1_p3 F-25 | as a group they generally came up with the same meaning at least as frequently as did sighted subjects | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 23 | gi_v02_c771995284e2 | ielts12_test7_p3 C-02 | that the purpose of this activity is to help us predict the arrival of our favourite part | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 24 | gi_v02_66a1e2394202 | ielts8_test2_p3 A-04 | that many of their olfactory likes and dislikes were based on emotional associations | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 25 | gi_v02_3d962c40c773 | ielts16_test3_p2 A-02 | As the ice has vanished | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 26 | gi_v02_38b4a0d1e7f6 | ielts12_test6_p2 C-04 | Bingham also seems to have been less than keen on the prospect of climbing the hill | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 27 | gi_v02_0708293fed9a | ielts15_test3_p3 D-03 | Once his phylogenetic analysis had established that they were indeed related | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 28 | gi_v02_6558f9d51457 | ielts5_test1_p3 D-14 | it will also create an impression that many more potential problems exist than is the case | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 29 | gi_v02_58b7848eec1a | ielts11_test4_p3 D-01 | that one doesn't have to be a genius to set its wheels in motion | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 30 | gi_v02_6e403f47646a | ielts8_test1_p3 H-37 | who are particularly successful in autoganzfeld trials | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 31 | gi_v02_0fc468cf93cc | ielts12_test6_p3 G-05 | that for very young children, as well as for older people, navigating a multilingual environment imparts advantages that transfer far beyond language | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 32 | gi_v02_9f1e80ebbb96 | ielts19_test3_p3 H-02 | If the technology matures into seamless, ubiquitous artificial speech translation | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 33 | gi_v02_14fe1215cae1 | ielts20_test3_p1 K-02 | that represents a third of the total food service sales | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 34 | gi_v02_9c10aa504ff1 | ielts14_test1_p1 G-02 | what the long-term impact of play is | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 35 | gi_v02_b8c1081ffea1 | ielts11_test3_p2 E-02 | that distinguish migration from other forms of movement | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 36 | gi_v02_3e3abd1c6003 | ielts5_test3_p1 E-01 | who had been involved in the 'Missouri' programme | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 37 | gi_v02_9d38eae04fac | ielts19_test4_p1 C-05 | a new study is seeking to answer these questions | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 38 | gi_v02_373b3c7786fb | ielts13_test2_p2 A-05 | which is sometimes referred to as the 'love hormone' | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 39 | gi_v02_b78d8facc011 | ielts11_test1_p2 E-05 | when a boat enters a gondola | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 40 | gi_v02_7cfacd5ec03f | ielts20_test3_p3 A-01 | he believed the solar system would be mapped by robotic craft by the end of the century | he believed...完整；内部the solar system would...也为名词性从句；既有A8嵌套名词性从句多解 | 原句可；题目不宜唯一判分 |

### T3（20道，均auto_pass）

| # | 题号 | 来源 | 答案/目标 | 局部/题干/干扰项 | 整句与教学 |
| --- | --- | --- | --- | --- | --- |
| 41 | gi_v02_39af3fd5a6a1 | ielts12_test7_p2 H-02 | If we can understand how geography affects our health no matter where in the world we are located → 状语从句 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 42 | gi_v02_fbfcc5ab2613 | ielts20_test1_p2 D-05 | such as storage crates and flooring → 不是从句（短语或非谓语） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 43 | gi_v02_87ca19185890 | ielts7_test1_p3 E-22 | Through meeting with the staff and satisfied students → 不是从句（短语或非谓语） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 44 | gi_v02_d9fd7f235469 | ielts17_test2_p2 A-09 | from just 15 crops → 不是从句（短语或非谓语） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 45 | gi_v02_18aa840992b6 | ielts5_test3_p2 B-04 | replacing what had been washed away by the sea → 不是从句（短语或非谓语） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 46 | gi_v02_ed1255234a62 | ielts14_test2_p2 F-05 | While miasma theory has been long since disproved → 状语从句 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 47 | gi_v02_1ce32677ca17 | ielts18_test1_p2 D-03 | Removing invasive plants → 不是从句（短语或非谓语） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 48 | gi_v02_eebfe680dde0 | ielts15_test2_p1 B-03 | that urban design has suffered from a separation between mind and body since the introduction of the architectural blueprint → 名词性从句 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 49 | gi_v02_e2ed6ab1c546 | ielts13_test2_p2 D-02 | who had received a dose of oxytocin → 定语从句 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 50 | gi_v02_dc5f9707e5fc | ielts13_test2_p3 F-01 | in ways that allow consumers to oppose—or at least temporarily escape from—the aspects of trends they view as undesirable → 不是从句（短语或非谓语） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 51 | gi_v02_afd5dd179d7f | ielts18_test2_p3 G-03 | to create artificial canals throughout the city → 不是从句（短语或非谓语） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 52 | gi_v02_41e59a7132f8 | ielts11_test1_p2 A-02 | to restore navigability across Scotland → 不是从句（短语或非谓语） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 53 | gi_v02_74c0c91de855 | ielts20_test2_p3 C-14 | When the robo-umpires came → 状语从句 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 54 | gi_v02_38e1f2c3a77b | ielts12_test7_p2 A-01 | While many diseases that affect humans have been eradicated due to improvements in vaccinations and the availability of healthcare → 状语从句 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 55 | gi_v02_7c92346d6672 | ielts16_test3_p2 H-02 | with almost no artefacts from about 3,800 to 2,200 BCE → 不是从句（短语或非谓语） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 56 | gi_v02_100fad52d5fb | ielts11_test1_p2 F-08 | connected by two smaller cogs → 不是从句（短语或非谓语） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 57 | gi_v02_1d575d2935e9 | ielts11_test4_p3 A-03 | since everything we have ever achieved depends on language and originates from it → 状语从句 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 58 | gi_v02_666615d0722f | ielts13_test1_p1 D-05 | where anyone could submit a blog of their New Zealand travels for possible inclusion on the website → 定语从句 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 59 | gi_v02_ff2a7ae5c411 | ielts4_test1_p1 C-01 | Despite the extensive coverage in the popular media of the destruction of rainforests → 不是从句（短语或非谓语） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 60 | gi_v02_24a65fa18623 | ielts12_test5_p2 D-01 | to find something special, or a particular example of the collected item → 不是从句（短语或非谓语） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |

### T4（20道，均auto_pass）

| # | 题号 | 来源 | 答案/目标 | 局部/题干/干扰项 | 整句与教学 |
| --- | --- | --- | --- | --- | --- |
| 61 | gi_v02_8b11cffee970 | ielts4_test2_p3 C-19 | after training stops → 时间 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 62 | gi_v02_66d529b93d1c | ielts7_test3_p1 B-06 | whereas in humans the opposite is true → 对比 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 63 | gi_v02_85798ad7a59e | ielts13_test4_p3 D-02 | If happiness is to be regarded as a science → 条件 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 64 | gi_v02_0e44d851d08f | ielts18_test3_p2 C-05 | Though the Doble boys' third prototype, nicknamed the Model B, still lacked the convenience of an internal combustion engine → 让步 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 65 | gi_v02_315ddcb542db | ielts5_test2_p1 G-30 | although treated with disdain in its early years → 让步 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 66 | gi_v02_a2dcc2e087a5 | ielts8_test3_p1 F-02 | before the electric field becomes strong enough to break down the air in an uncontrollable surge → 时间 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 67 | gi_v02_be1bd61fe1e2 | ielts6_test3_p2 B-07 | If participation and the culture are incongruous → 条件 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 68 | gi_v02_ed10def280ce | ielts13_test4_p2 C-03 | once this has happened → 时间 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 69 | gi_v02_58515a0cc06b | ielts4_test2_p1 E-29 | When an unwritten and unrecorded language disappears → 时间 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 70 | gi_v02_bc6f24842d21 | ielts14_test4_p3 K-04 | if ecologists can understand how the slow-moving effect of ocean trash is damaging ecosystems → 条件 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 71 | gi_v02_e8a0a1d51e7c | ielts18_test3_p2 F-05 | even though it was so heavy → 让步 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 72 | gi_v02_5dd1972e5262 | ielts18_test1_p3 B-04 | so that satellite operators know how much to worry about what's coming their way → 目的 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 73 | gi_v02_7181189f4554 | ielts19_test4_p3 A-04 | If we are good → 条件 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 74 | gi_v02_d2cd51e8143d | ielts14_test2_p2 H-04 | if climate modelling predictions and energy price rises come to pass as expected → 条件 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 75 | gi_v02_e9f70015c6df | ielts14_test2_p3 H-01 | if overused → 条件 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 76 | gi_v02_596d4f08542a | ielts16_test1_p1 D-05 | If the mechanism of bone remodelling in polar bears can be understood → 条件 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 77 | gi_v02_5d08c14a73b7 | ielts7_test4_p2 D-05 | until, during the 1990s, annual harvests were well in excess of 100 million, and on several occasions over 200 million fish → 时间 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 78 | gi_v02_deb14d7127fe | ielts19_test4_p3 A-03 | If we are kind to one another → 条件 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 79 | gi_v02_fe34bf66e454 | ielts5_test4_p2 H-29 | if they are within the central, tensile region of the pane → 条件 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 80 | gi_v02_1a5108714938 | ielts6_test2_p2 G-23 | If the trends apparent in the United States 14 years ago had continued → 条件 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |

### T5（20道，均auto_pass）

| # | 题号 | 来源 | 答案/目标 | 局部/题干/干扰项 | 整句与教学 |
| --- | --- | --- | --- | --- | --- |
| 81 | gi_v02_b8af6e3ba219 | ielts9_test2_p2 E-01 | the measurements | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 82 | gi_v02_f00864c296fb | ielts11_test1_p1 A-03 | An estimated 109 hectares of new land (about 20% larger than Brazil) | 完整主语边界正确（含括注）；语法题干成立；AC2数字原文错误 | 不可原样给学生：10⁹误作109 |
| 83 | gi_v02_b3ee981a6aeb | ielts17_test4_p3 D-02 | displays of the feat | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 84 | gi_v02_aec04f51df69 | ielts8_test2_p2 F-01 | Global temperatures | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 85 | gi_v02_cc3789806199 | ielts15_test1_p1 E-09 | One of the Banda Islands, a sliver of land called Run, only 3 km long by less than 1 km wide | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 86 | gi_v02_3a51ba8c1847 | ielts6_test2_p3 B-05 | the need for a sophisticated number system | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 87 | gi_v02_148d321b2000 | ielts20_test3_p1 J-06 | Swanson | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 88 | gi_v02_1a09085a1929 | ielts5_test4_p2 H-29 | the stresses this unleashes | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 89 | gi_v02_7bb48e728c63 | ielts18_test3_p2 G-04 | fewer than fifty of the amazing Model E steam cars | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 90 | gi_v02_0caa9471b641 | ielts7_test2_p3 B-07 | The socio-economic survey of more than 400 households in the district | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 91 | gi_v02_46a09bf9989d | ielts17_test1_p1 C-05 | Pearson and his partners | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 92 | gi_v02_2a414b10040b | ielts17_test3_p3 F-01 | Chapter five | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 93 | gi_v02_142b10d88802 | ielts11_test4_p1 C-01 | These two lines of research - studying the differences between identical twins to pinpoint the influence of environment, and comparing identical twins with fraternal ones to measure the role of inheritance - | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 94 | gi_v02_a8b45ff4f52f | ielts18_test4_p1 D-05 | The term 'natural capital' | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 95 | gi_v02_4ae6394256fc | ielts12_test7_p1 A-03 | Only the thick vegetation at the skirt of the often cloud-covered peak of Sierra Negra | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 96 | gi_v02_85c1dda87a3d | ielts16_test4_p2 D-04 | the result | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 97 | gi_v02_5d9ce176aa85 | ielts18_test2_p1 C-02 | These stones | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 98 | gi_v02_253a3c2e9768 | ielts9_test1_p3 D-27 | The next step | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 99 | gi_v02_7b74eaa5663c | ielts8_test2_p2 E-09 | A gradual agricultural revolution in northern Europe | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 100 | gi_v02_54fac9748148 | ielts20_test4_p1 G-20 | O’Keeffe | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |

### T6（20道，均auto_pass）

| # | 题号 | 来源 | 答案/目标 | 局部/题干/干扰项 | 整句与教学 |
| --- | --- | --- | --- | --- | --- |
| 101 | gi_v02_17806d487e50 | ielts11_test4_p1 F-02 | serves → 从句里的谓语 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 102 | gi_v02_25eedc500d54 | ielts15_test3_p1 I-05 | felt → 从句里的谓语 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 103 | gi_v02_45a278edd3f1 | ielts17_test3_p2 F-06 | sequester → 从句里的谓语 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 104 | gi_v02_a6c21eff9dcd | ielts10_test4_p2 A-09 | will help → 主句谓语 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 105 | gi_v02_052a831689ae | ielts4_test1_p2 C-03 | restricts → 主句谓语 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 106 | gi_v02_16e5b057ff60 | ielts16_test2_p3 F-01 | require → 从句里的谓语 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 107 | gi_v02_bdd72fecd3ad | ielts12_test6_p3 B-07 | heard → 从句里的谓语 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 108 | gi_v02_08f7467b233c | ielts12_test5_p1 C-03 | putting down → 非谓语（不定式、分词、动名词） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 109 | gi_v02_b450be2e1ebb | ielts11_test4_p2 A-01 | might think → 从句里的谓语 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 110 | gi_v02_ede18594dcb9 | ielts16_test2_p3 H-03 | were → 主句谓语 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 111 | gi_v02_d23da7cc2ba7 | ielts6_test2_p3 F-02 | contains → 主句谓语 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 112 | gi_v02_b39774d47196 | ielts16_test2_p3 C-01 | to reason → 非谓语（不定式、分词、动名词） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 113 | gi_v02_396f47dde94b | ielts15_test3_p1 I-05 | enabled → 主句谓语 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 114 | gi_v02_793493ff740a | ielts17_test3_p3 H-03 | learning → 非谓语（不定式、分词、动名词） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 115 | gi_v02_f1b293fdf799 | ielts11_test3_p1 E-05 | was restored → 主句谓语 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 116 | gi_v02_c4a169b1809d | ielts4_test1_p1 I-03 | considering → 非谓语（不定式、分词、动名词） | considering介词化/分词教学口径待定；已披露介词化分词，非本轮新问题 | 原句可；词类题须先定口径 |
| 117 | gi_v02_254c45fd1c25 | ielts12_test5_p3 C-07 | has been marketed → 从句里的谓语 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 118 | gi_v02_05afa4245841 | ielts14_test4_p2 A-04 | do not suffer → 主句谓语 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 119 | gi_v02_3ffc0399a676 | ielts15_test3_p3 I-05 | known → 非谓语（不定式、分词、动名词） | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |
| 120 | gi_v02_81213c6a7c95 | ielts18_test3_p3 C-02 | requires → 主句谓语 | 局部答案、高亮成立；干扰项未见错误；题干前提成立 | 可 |

## 7. 新角度定向扫描及判读

与前几轮的动词单位、并列/系表、非典型主语扫描不同，本轮首先从**题干宣称的“从句”与外层短语结构是否一致**入手：遍历全部27830道剑桥auto，取T2/T3/T4中不是“短语或非谓语”答案的目标，筛中心finite=false。T2/T3无命中，T4有9题。不能因为中心无限定性就把9题全部判错：合法省略和错误挂靠须人工区分。完整命中表如下。

| 题号 | 来源 | 目标 | 状态 | 独立判断 |
| --- | --- | --- | --- | --- |
| gi_v02_cf28b13ef739 | ielts14_test2_p3 E-02 | until the point where any further increase in order reduces productivity | auto_pass | AC1：until＋the point名词短语；外层不是从句，题干错 |
| gi_v02_3cfba0eafd9a | ielts14_test2_p3 F-01 | when innovating | auto_pass | when innovating可按省略状语从句分析；不算错误 |
| gi_v02_e9f70015c6df | ielts14_test2_p3 H-01 | if overused | auto_pass | if overused合法省略；不算错误 |
| gi_v02_bda011edf0d9 | ielts14_test4_p3 K-02 | until after they've happened | auto_pass | until after后有they have happened完整时间从句；关系可成立，不凭prep标签判错 |
| gi_v02_8b11cffee970 | ielts4_test2_p3 C-19 | after training stops | auto_pass | training stops实际有主谓；解析器把after当头不改变时间从句性质 |
| gi_v02_0628b13312c2 | ielts4_test4_p1 F-27 | as long as our training continues to improve | auto_pass | as long as后有our training continues完整从句；中心误取as，不算错 |
| gi_v02_315ddcb542db | ielts5_test2_p1 G-30 | although treated with disdain in its early years | auto_pass | although treated可还原it was treated，让步正确 |
| gi_v02_839c85588857 | ielts7_test4_p1 C-03 | if sustained over a long time | auto_pass | if sustained可还原it is sustained，条件正确 |
| gi_v02_57876a908e1c | ielts9_test1_p2 E-33 | if faced with a superior and much older civilization | auto_pass | if faced可还原the human race were faced，条件正确 |

另查to的介词/不定式身份：全剑桥auto T6中，显示中心为VBG且紧邻前词to，共3题。均为介词to后动名词，按项目的“非谓语（含动名词）”分类成立。没有把to一律加入动词单位，也未发现新错误。

| 题号 | 来源 | 目标 | 判断 |
| --- | --- | --- | --- |
| gi_v02_a370edb7d187 | ielts19_test4_p1 G-02 | emerging | 非谓语/动名词成立，to是外层介词 |
| gi_v02_bd72c5cf374b | ielts10_test2_p3 J-02 | seeking out | 非谓语/动名词成立，to是外层介词 |
| gi_v02_dd13bf003f99 | ielts18_test1_p3 E-01 | managing | 非谓语/动名词成立，to是外层介词 |

由抽样AC2再做数值排印扩查：按来源句去重，筛`10[2-9]`、m2/m3等单位、化学式CO/SO（区分大小写）及数字+hectares/degrees/°/billion/trillion。31句命中，1句官方原版确认上标丢失。另30句未发现同型上标吞并的证据；这不是对每项科学数据的事实核查，不在本轮据常识擅改科学数值。以下列出全命中，方便重做，均有auto候选。

| 来源 | 检查结论 |
| --- | --- |
| ielts10_test1_p1 H-03 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts10_test1_p2 E-02 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts10_test3_p1 C-05 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts10_test3_p1 C-07 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts11_test1_p1 A-03 | AC2，官方原版10⁹→库内109 |
| ielts11_test1_p3 B-05 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts11_test1_p3 D-03 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts11_test2_p1 B-01 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts12_test5_p1 B-02 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts15_test4_p3 D-01 | m3为纯文本立方米惯用写法，未改变数值 |
| ielts17_test1_p2 A-03 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts18_test3_p1 A-03 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts19_test4_p1 C-02 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts20_test2_p1 F-05 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts20_test2_p1 H-03 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts20_test3_p1 J-08 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts20_test3_p1 K-01 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts20_test3_p1 K-02 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts20_test4_p2 F-31 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts4_test2_p2 B-09 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts4_test3_p2 C-02 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts5_test1_p3 G-30 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts5_test1_p3 I-37 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts5_test1_p3 J-38 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts5_test4_p2 E-16 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts6_test2_p2 G-24 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts6_test4_p2 E-12 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts8_test2_p1 A-02 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts8_test2_p1 D-04 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts8_test4_p2 J-05 | 未见同型上标吞并证据；不是数据事实认证 |
| ielts9_test3_p2 C-14 | 未见同型上标吞并证据；不是数据事实认证 |

## 8. 全量差异与报告

与完整e2903b1生成池比较：50243候选、题号集合相同；除status/reasons外每字段逐题相同，无新增/删除。剑桥19auto→needs（9T1/10T6）、机经2（1T1/1T6），无needs→auto；另1机经本来needs仅加原因。新原因全量Cam19/Jij3。新问题AC1/AC2对应的全部候选也与e290逐字段相同。

| 模板 | auto_pass | needs_review |
| --- | --- | --- |
| T1 main_verb_tap | 5822 | 557 |
| T2 clause_boundary | 4678 | 2584 |
| T3 clause_type_classify | 11401 | 3486 |
| T4 adverbial_relation | 399 | 657 |
| T5 subject_span | 5365 | 819 |
| T6 finite_or_not | 12641 | 1834 |

auto合计40306=剑桥27830+机经12476。report计数说明与实现一致。回归13句×6模板共78条逐字段相同；7项整句过滤的actual/expected/来源列表与e290相同：30/2/0/1/0/0/0（tagged_fragment、clause_attached_to_conjunction、glued_sentence_boundary、multi_sentence_unit、suspected_split_word、leading_stray_punctuation、control_character）。

## 9. 生成环境、双跑SHA及表格

Mac arm64，macOS 27.0.1；Python3.13.3、spaCy3.8.16、en_core_web_trf3.8.0、torch2.14.1 CPU、openpyxl3.1.5；seed20261018。G来自本机隔离的.venv-grammar-tools。本轮复用同环境解析缓存，另49句现解析核缓存；没有声称全库重新解析。用户要求的是两次完整生成，本轮均已执行；生成目录是仓库外完整被审快照，以保护交付文件。

reading_study SHA-256：`55b808e1a69cfb7fc06670a6ac3bb36d2861923f229183875ed309ea3a747f37`；grammar_graph：`c7b35ddb68db7601ccd01e38a210ad3dd772ff507302190f68a351e408b85a29`。

| 文件 | 第一次SHA-256 | 第二次SHA-256 | 与提交版 |
| --- | --- | --- | --- |
| generation_report_v0_2.json | f04b9e607295586a16a2ecd7aaabea5c8c079d177a9301a5d02ebc11c52e4b5c | f04b9e607295586a16a2ecd7aaabea5c8c079d177a9301a5d02ebc11c52e4b5c | 仅Python版本行3.13.3 / 3.11.15不同 |
| generation_report_v0_2.md | c065ab137d67841100c4ecf4ed2a20923b76ba90b73c66cd1f819d30fb5783c3 | c065ab137d67841100c4ecf4ed2a20923b76ba90b73c66cd1f819d30fb5783c3 | 仅Python版本行3.13.3 / 3.11.15不同 |
| review_batch_v0_2.jsonl | 7e045267aa0eabe541b54513b5fc3a3c87484e63f0a87b9c90957648745d2c6c | 7e045267aa0eabe541b54513b5fc3a3c87484e63f0a87b9c90957648745d2c6c | 字节一致 |
| review_batch_v0_2.xlsx | 2fa84b63a738306617b9695eea38fcb7427e600198b35c1afaef4e033e99d769 | 2fa84b63a738306617b9695eea38fcb7427e600198b35c1afaef4e033e99d769 | 字节一致 |

提交版四个SHA均与用户提供值一致。两份报告用逐行比较确认仅一行Python版本不同；不是删除任意environment字段后笼统比较。

xlsx：7表（说明+6题型），每题型60数据行；判定列H2:H61仅四项下拉“正确 / 答案错 / 题目有歧义 / 句子不适合出题”。所有360行逐格与teacher_row渲染一致，老师可见内容无auto_pass/needs_review或内部原因。剑桥233=196auto+37needs，机经127=104auto+23needs。相对e290仅27个题号保留，(工作表,行号)保留0行。老师若已有旧表判定，应按题号核对迁移，不能按行号照搬；本轮没有写老师判定，盲审范围仍待用户决定。

## 10. 测试、负测、raw重建与图谱

实际执行（G/P/N/R/O定义见§2）：

```sh
# 在R
$G -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary tests.test_grammar_graph_draft -v
$P -m unittest tests.test_reading_study -v
$G scripts/validate_reading_study.py
$G scripts/reading_jijing_text_fixes.py --check
$N tests/test_dictation_spell_queue.js
$P -m ruff check --config 'extend-exclude=[]' scripts/grammar_items/checks.py scripts/grammar_items/reporting.py scripts/grammar_items/templates.py tests/test_grammar_item_candidates.py
$P -m ruff format --check --config 'extend-exclude=[]' scripts/grammar_items/checks.py scripts/grammar_items/reporting.py scripts/grammar_items/templates.py tests/test_grammar_item_candidates.py
# O里创建全新Flask-only环境
$G -m venv "$O/flask-only"
$O/flask-only/bin/python -m pip install --cert /etc/ssl/cert.pem Flask
$O/flask-only/bin/python -m pip list
```

ci.yml原列表（没有挑选或缩减），在R实际执行：

```sh
$O/flask-only/bin/python -m unittest tests.test_miniprogram_guest_access tests.test_miniprogram_dictation_grouping tests.test_inventory_toefl_materials tests.test_organize_toefl_materials tests.test_extract_toefl_answer_keys tests.test_map_toefl_answers_to_practice_docs tests.test_import_toefl_official_reading tests.test_reading_vocab_grading tests.test_stats_utils tests.test_grammar_graph_draft tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary -v
```

结果：151专项通过；Flask-only **219运行=218通过+1按设计跳过**；Node exit0；reading22通过；validator0（317/387就绪、70缺失为存量）；textfix --check0。Flask-only只有Flask3.1.3及其传递依赖和pip，无spaCy/torch/SQLAlchemy。4改动Python的Ruff check、format --check通过。

新测试在旧e290代码下逐项跑：加载旧checks/templates，测试本体用当前版本；不改仓库文件。1项断言失败、1项接口错误，与Claude所报一致：

| 测试 | 旧代码结果 | 证据 |
| --- | --- | --- |
| LinkingAuxiliaryTests.test_linking_verb_parsed_as_auxiliary_goes_to_review | 断言失败 | 旧代码仍auto，与needs断言冲突 |
| LinkingAuxiliaryTests.test_real_passive_auxiliary_unaffected | 接口错误 | 缺Reason.LINKING_VERB_AS_AUXILIARY，不是语义断言失败 |

补充实际命令：`G O/audit_data.py`调用build_reading_test_practice.build_tests(raw,'jijing')在内存重建；只把localize_image替换为相同本地路径计算，**无下载图片**，所有171篇content整体（含summary）及groups与static逐结构全等。随后在O/source运行`G scripts/render_grammar_graph_review.py`，输出与任务树提交版字节一致。未知role无新增。`G O/audit_runtime.py`、`G O/probe_rules.py`、`G O/controls.py`、`G O/scan_clause_finiteness.py`、`G O/final_probes.py`均执行，明细保存在O。

官方样章验证命令在O执行：

```sh
curl --fail --silent --show-error -o tmp/pdfs/cambridge11-excerpt.pdf https://assets.cambridge.org/97813165/03850/excerpt/9781316503850_excerpt.pdf
pdftoppm -f 9 -l 9 -scale-to 1600 -singlefile -png tmp/pdfs/cambridge11-excerpt.pdf tmp/pdfs/page18
```

实际视觉查看page18.png确认10⁹；报告只引用必要短片段，不把整页复制进仓库。新问题扫描不是单靠生成器与自身结果相互印证。

## 11. 模拟导入、Git与CI

使用固定`676569c`完整快照（代码/static/data齐全，2853个tracked Git blob逐一校验），本机独立SQLite `O/main-to-current.sqlite`；仅创建ReadingPassageAnalysis表，显式绑定此SQLite URI，没有读取生产连接：先导main **created317/failed0**，再导8e04 **updated236/skipped81/failed0/created0**，最终317行。与Claude结果一致。本轮没改阅读解析，数量相同合理。

共享origin/main实为`ee94abb30d56b3c9623c519f75c1ffa9679c65b5`，不是提示中的旧引用；本轮仍按明确指定的676569c导入，不合main、不偷换基线。

被审8e04的[CI40605965839](https://github.com/KB77GG/studytracker/actions/runs/40605965839)已完成：test成功；lint为存量advisory失败。此报告正文和两份交接提交推送后，再核它们自己的精确head CI并补记。不能把被审分支CI当成本审核提交CI。

## 12. 交接审计、限制与下一步

- 本轮仅新增ROUND16报告、更新CODEX_HANDOFF/WORKLOG，准备普通commit/push `codex/grammar-item-candidates`；没有修改任何被审文件。最后SHA与精确CI见最终回复/CI补记。
- 桌面`/Users/zhouxin/Desktop/studytracker`仍main@6ded77d24586327ad94e151e172ae4811b4a2eed、behind87，既有7modified/22untracked入口未动，仅借其venv；完整路径清单以该树git status为准。任务树与桌面成果不能混同。
- O内快照、全池、缓存、脚本、日志、SQLite、PDF页只本机可见；三份正式文档commit并push后才可跨电脑获取。没有生产服务器/数据库、部署、main推送、PR、小程序上传/提审/发布、LLM API操作。
- 所有8项必检均已完成，没有无法完成而绕过的项目。执行位置在仓库外完整快照，复用缓存并补49句现解析；使用固定main676而不追随共享origin/main移动，均如实列出。
- 发现问题只记录不修。下一位先读AC1/AC2：按后续授权统一T4类别门槛并保留合法省略控制；依据官方原版修上标或用通用source_quality送审，不用ID黑名单。AB1/AB2无需重做；老师盲审范围、系表等教学口径及上线仍待用户决定。
