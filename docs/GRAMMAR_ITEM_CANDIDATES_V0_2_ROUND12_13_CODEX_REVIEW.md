# 语法候选题 v0.2 第十二、十三轮独立复审（Codex）

审核日期：2026-10-27，Asia/Shanghai。**结论：不通过，以剑桥题为准。新确认 0 阻断、3 应修（Z1–Z3，6 道不同的剑桥 auto_pass、5 个来源句）、3 建议（Z4–Z6）。** 机经本轮新增确认的问题 0 项；指定影响和历史暂缓项另列，不计剑桥数量。

固定范围 `1558465700752fddc79ef4cfa712989d97dfe175..35e37c5f6157430b8294fb877de46f621daee887`。任务树 `/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker`，分支 `codex/grammar-item-candidates`。本报告没有修改代码、标注、原文、交付文件或题目状态。不能把“已降级”理解成“内容已改对”，也不能把 120 道抽样未见问题推广为全池正确。

## 1. 上次阻塞、范围与关闭情况

按用户顺序先确认任务树仅有 CODEX_HANDOFF、WORKLOG 的修改及未跟踪 ROUND11_12 阻塞记录；恢复两交接、删除该未跟踪记录，再 fetch/ff 到指定 35e37c5，成功。没有普通 merge、rebase 或改写历史。37bd950 中旧 ROUND11 报告逐字节保留；两交接的旧独立复审正文及日志保留，只有滚动“最近更新”行替换为新状态，属于正常更新。

本轮仅提交本报告及两交接。桌面 `/Users/zhouxin/Desktop/studytracker` 的 main 工作树不是任务树；其既有改动未覆盖，仅读取/借用虚拟环境。完整复现快照、脚本、全量候选、日志、临时 SQLite 位于仓库外 `/Users/zhouxin/.codex/audits/grammar-v02-round12-13-20261027`，不随 Git 推送。

| 编号 | 关闭判断 | 独立结论 |
| --- | --- | --- |
| A8 | 本轮范围内关闭 | 原 345 道中的 344 道 auto 均有正确连词定位；77 序号全核；另 1 道嵌套并列已 needs。原 7 道控制为 6 个唯一答案、1 个合理降级。缺连词和深层并列仍有保守边界，见 §4。 |
| Y1 | 点名 not 问题关闭；不是七题全部正确 | 3 个 T1 干扰项和 4 个 T6 的 not 均已纠正；当前 6 auto / 1 needs。lives 那道仍有 Z1；is 的“重复”解释是子串误判（Z4）；否定倒装反例见 Z6。 |
| Y2 | 关闭 | 点名 6 道全 needs，相关完整主句 T6 不继承原因；未在专项扫描中发现 for 分句本身仍被 auto 判从属谓语。 |
| Y3 | 22 道点名关闭；完整性问题尚未完全关闭 | 22 道全 needs；额外 77 道为保守筛选，其中并非每个副词都必须进动词单位。另查到 3 道 live up to 漏网，见 Z1。 |
| Y4 | 关闭 | 第十一轮更正明确 word-spot / hand-raising 是动词用法，mixed-ability 截的是前半 mixed；与上一轮复审一致。 |

## 2. 九项检查逐项结果

| 项 | 结果 | 证据 / 实际命令索引 |
| --- | --- | --- |
| 1 | 通过 | 11 文件、1054 增/445 删；保护路径及阅读解析零改动；6 个新增决策函数不读三个 ID。37bd950 保留旧审核正文。命令 A、D、I。 |
| 2 | 本轮 A8 验收通过，有保守限制 | 77 序号逐题核对；其余随机抽 20 道；158 个缺 cue 全读、全 needs；7 个旧控制单列。不能把 158 全说成原句不存在连词。见 §4；命令 E、I。 |
| 3 | 删除范围验收通过；恢复池另有 Z3 | 剑桥实际删 43 题中的片段；40 题曾恢复，现 38 auto / 2 needs。38 auto 中 37 未见问题，1 的 provided 干扰项有错；2 needs 均 Y3。见 §5。 |
| 4 | 点名修复已核；发现 Z1、Z4–Z6 | Y1/Y2/Y3 共35个旧题逐题映射，现6auto/29needs；Y3额外77按42种表面搭配逐类及逐题列出。T6隔离37无自身触发者全等，25自身触发者降级。见 §6。 |
| 5 | 随机样本未见新错；定向扫描不通过 | seed20261102，六模板各20，120全auto；分别检查答案/高亮/干扰项/题干/原句。新角度“并列与共享助动词”扫描18候选，确认2个非谓语身份错误 Z2；补查 Z1、Z3。见 §7。 |
| 6 | 全部预期复现 | 50243；4换题号；共同ID剑桥104降/38升、机经29降/14升；题干970/干扰61，其他字段不变；auto40341/剑桥27860。见 §8；命令 B、C。 |
| 7 | 双跑、回归、表格通过 | JSONL/XLSX与提交字节一致，两报告只有Python版本行差；双跑4文件全等；78回归/7过滤不变；7表、6×60、四项下拉、盲审。相对a3保留28题号/0同位置。见 §9。 |
| 8 | 运行通过；旧代码负测描述有差异 | 专项137；Flask-only205运行/204通过/1跳过；Node、reading22、validator0、--check0、raw171、图谱一致、4文件Ruff通过。R12负测4失败/0错误/2通过；R13实测5失败/2错误/2通过。见 §10。 |
| 9 | 通过 | main676569c完整快照2853 Git blob核对，先建317篇，再导35e37c5：updated236/skipped81/failed0。只用仓库外临时SQLite。见 §10；命令 H。 |

## 3. 剑桥问题清单

### Z1 — 应修：live up to 的小品词被标成 prep，仍漏出自动题的动词单位（3 道）

位置：`scripts/grammar_items/templates.py:240` 的 `verb_unit()`、`:253` 的 `loose_particle()`。三题都是 `live up to` 表示达到期待/标准；显示只到 lived/lives，up 紧挨动词、tag=RP，但 dep=prep，故既不并入单位也不触发新 advmod 门槛。不是已经披露的“被宾语隔开”的情况。

复现：读取下表三个 ID 的 answer.spans / target.parts；对同句 ParseCache 检查 live 的直接子节点，可见 up 的 `dep=prep, tag=RP`。13_4_p1 两题从 a3 起逐字段未变；5_3_p3 那题因 Y1 换了 ID，去除 not 正确，但不能据此认定高亮已完整。局部主/从句身份成立，完整单位不成立。

建议：用词组证据或 RP 等交叉信号把有歧义的动词单位送审，不要将所有 prep 一律并入。覆盖 live up to，保留 go on a hike、had its brakes on 等正常介词/宾补控制。T1 答案冻结时先降级；是否扩大单位另按授权处理。[Cambridge 将 live up to 收为短语动词](https://dictionary.cambridge.org/dictionary/english/live-up-to)，支持本次上下文判断。

| 题号 | 题型 / 来源 | 状态 | 答案或目标 | 独立判定 |
| --- | --- | --- | --- | --- |
| gi_v02_e7f5ca02117f | T1 / ielts13_test4_p1 E-04 | auto_pass | never / lived | 主/从句身份成立；缺 up（词组 live up to），完整高亮不成立；原句可用 |
| gi_v02_9bf2469ce8c1 | T6 / ielts13_test4_p1 E-04 | auto_pass | never lived | 主/从句身份成立；缺 up（词组 live up to），完整高亮不成立；原句可用 |
| gi_v02_100095519c58 | T6 / ielts5_test3_p3 E-35 | auto_pass | lives | 主/从句身份成立；缺 up（词组 live up to），完整高亮不成立；原句可用 |

### Z2 — 应修：共享或省略助动词的并列谓语被自动判为非谓语（2 道）

位置：`scripts/grammar_items/parse_view.py:56` 的 `finite()` 仅看自身和直接 aux；`templates.py:885–900` 据此给“非谓语”。此文件本轮未改，但错误仍在被交付的自动池中。

- 15_4_p1 F-05：`The pods can be ground ... and the seeds roasted ...`，后项是 `the seeds [can be] roasted`；本库难点本来就解释省略 can be。不是把 roasted 单独当非谓语修饰 seeds。
- 17_4_p3 E-07：`they must be recalled ..., updated ..., and ... stored ...`，updated 与 recalled/stored 共享 must be，是并列谓语的一部分。当前“非谓语”身份错误。

复现：下表两题均 auto、answer.option 为非谓语；缓存两中心词均 conj/VBN，自身没有助动词、前项有 can be / must be。用 §7 的全池探针共筛出18题，人工排除16个结果状语/定语等，不把所有 conj/VBN 一律判谓语。[Cambridge 对并列结构省略的说明](https://dictionary.cambridge.org/grammar/british-grammar/ellipsis)和[British Council 对共享主语、be 的说明](https://learnenglish.britishcouncil.org/free-resources/grammar/c1/ellipsis)支持省略不等于语法身份自动变成非谓语；具体两句为本次语境判断。

建议：有限性复核加入并列助动词共享/省略证据，并与非谓语状语区分；不能可靠解析时降级，不凭自身没有 aux 自动批准。测试包含两条真实来源和 thereby cutting、逗号后结果分词、后置定语等反例。不要擅自给原句添加不存在的词，也不要按句子 ID 排除。

| 题号 | 题型 / 来源 | 状态 | 答案或目标 | 独立判定 |
| --- | --- | --- | --- | --- |
| gi_v02_86b996fd1f46 | T6 / ielts15_test4_p1 F-05 | auto_pass | roasted | 答案“非谓语”错误；共享/省略助动词的并列谓语；原句可用 |
| gi_v02_330fff562bff | T6 / ielts17_test4_p3 E-07 | auto_pass | updated | 答案“非谓语”错误；共享/省略助动词的并列谓语；原句可用 |

### Z3 — 应修：恢复的 T1 还把 provided that 的连词列作动词干扰项（1 道）

位置：`templates.py:475–504` 的 `main_distractors()`；`ielts15_test4_p3` B-03、下表 ID。第十二轮正确删除 profit-making 中的 making 后，这题从 needs 恢复 auto；剩余 provided 却是条件连词 provided that 的一部分，不是动词。主答案 ignores 正确，不足以使整道动词辨别题合格。

复现：distractors 为 `are not / provided / do`；原句尾部为 `provided that they do so by legal means`。计划 v0.1 T1 指定干扰来自从句/非谓语内的动词，不能仅凭解析器的 VERB 标签认定词性。[Cambridge 的从属连词说明明确包括 provided that](https://dictionary.cambridge.org/grammar/british-grammar/subordinating-conjunctions)。

建议：按上下文识别词汇化连词，删掉无动词身份的干扰项或送审；保留真正 `provided information`、`was provided` 的动词用法，不做 provided 字面黑名单。补测条件连词与普通动词的对照。

| 题号 | 题型 / 来源 | 状态 | 答案或目标 | 独立判定 |
| --- | --- | --- | --- | --- |
| gi_v02_b16884621b7b | T1 / ielts15_test4_p3 B-03 | auto_pass | ignores | 主答案 ignores 对；provided 是连词片段，干扰项类型错误；原句可用 |

### Z4 — 建议：更正负测口径及 is 重复的解释

位置：`docs/GRAMMAR_ITEM_CANDIDATES_V0_2_FIXES.md` 第十三轮“验证”和 Y1 表；对应交接摘要。

1. 旧 891b9d2 上运行9项新测试，实际是5项断言失败、**2项接口错误、2项通过**。除了 LooseParticle 控制缺 `PARTICLE_OUTSIDE_UNIT`，NestedCoordination 的单分句控制还缺 `NESTED_COORDINATION`，不能称该项已在旧代码通过。§10逐项列出 traceback 类型，复现命令 F。
2. 7_1_p1 C-08 只有一个整词 is（字符40处），第二个子串在 fish 内（145处）。`templates.py:358–362` 的 `str.find` 把子串也算重复，导致 `gi_v02_aaac16edcfbf` needs。建议记录为“子串匹配导致的保守误降”，不要说句中有多个 is 动词；后续采用 token/整词位置并测试 is/fish、is/possible 等。此项现为 needs，不影响自动池安全，故不列应修。

### Z5 — 建议：Y3 的额外命中不能一概解释为“只显示动词确实不完整”

位置：FIXES 第十三轮“额外命中”；规则 `templates.py:253`。例如 `The Dutch nutmeg monopoly was over.` 的 over 是系表补足，主句谓语动词 was 本身可以成立；普通方向副词也不自动属于短语动词粒子。§6逐对区分，而不是声称77题原答案全部错误。

复现：`The monopoly was over.`、`He was down with a cold.` 的单位分别 was，loose_particle 均送审；语料同类条目见77题表。保守 needs 可以接受，但建议把解释改成“解析无法区分粒子/副词/补语，送审”，以后以明确词组证据收窄。语料 prt ≥10 次的字面词还有 by=10，当前11词表未包含它；可谨慎排除 by，但不要将这份选择表称为穷尽清单。

### Z6 — 建议：correlative_not 的“在主语之前”会误删否定倒装的 not

位置：`templates.py:224–237`。独立构造并用同一解析器运行 `Did not the team win?`，unit 变成 Did / win，not 被误排除；它确实否定 win。正常 `He did not come.`、`He decided not to go.` 控制保留 not。

语料扫描剑桥全部句子的 neg/not，共9个实际被排除的来源均可由 whether-or-not、not because、not how、not that 解释，本次未发现真实题受此反例影响。故仅建议：把“主语在后”与真实关联结构、倒装分开，补否定问句控制，不能仅凭相对词序排除 not。复现命令 I。

### 机经（暂缓）

本轮新增确认0项，不对机经全池作质量担保。指定 `reading_jijing_24_test_56_p3` B-03 的 T1 `gi_v02_20551c6d1cef` 恢复 auto 合理：were attributed 是主谓，not 作用于 what 从句对比项，干扰单位 would / be identified 不应带 not；同句其余needs仍保留。

Y3在机经的37个带原因、29道共同ID降级，以及坐标缺失98/嵌套2均只作为影响统计。嵌套规则会把目标内部更深层的并列也算进去（如10_78_p1 K-64的两个 what 宾语分句），这是保守范围，现仍needs，不作为新增机经问题重复登记。V2、第27题、V4/V5等用户决定暂缓项不重列。

## 4. A8 逐题检查

`coordinate_prompt()` 先找答案起点前最近的英文词；若属于 and/but/or/nor/yet，再在整句用整词、不区分大小写计数。因此句首 And 也计入。独立探针先按单词切分整句，用位置回算序号，再逐条与题干比较；345条均一致，无序号落在单词内部。77道带序号均仍auto；其余268道中的原嵌套1道已needs，随机复核20个无序号目标均未见问题。

158条 `coordinate_cue_missing` 全部是已待复核题，不是新增158道 auto 降级。逐条阅读可分：无显式合格连词、目标含连词本身、for/so不在词表、连词与起点间有主语/状语/插入语或边界问题。特别是3条nor、2条yet已在答案内部；并非原句无连词。只按当前“后面的”题干且冻结答案，继续needs合理；若将来支持含连词答案，应改成“由…引出的”等并复核范围。不能盲目删除答案中的nor/yet（含否定倒装）。

`nested_coordination()` 把目标内有自己主语的有限 conj 送审，9_3_p2 A-01成立。它不限制嵌套层级，`but I knew that wages fell and jobs went` 也可能被保守命中，尽管外层目标可以唯一；不应说所有命中都是真多解。独立在344个当前auto答案里用表面“and/but/or/nor/yet + 主语起始词”查漏，命中4条，实际都是名词并列或定语/强调句内成分，未发现新漏网（见下表）。

### 4.1 原7道多解例句

| 题号 | 题型 / 来源 | 状态 | 答案或目标 | 独立判定 |
| --- | --- | --- | --- | --- |
| gi_v02_2ad35c049cf2 | T2 / ielts11_test2_p2 D-01 | auto_pass | they believe the islanders themselves weren't to blame | 新题干定位唯一；答案/高亮完整；原句可用 |
| gi_v02_e352db294821 | T2 / ielts13_test4_p3 B-05 | auto_pass | thinkers throughout the ages may have struggled to reconcile the pursuit of happiness with… | 新题干定位唯一；答案/高亮完整；原句可用 |
| gi_v02_40b28d51f5de | T2 / ielts15_test1_p3 D-03 | auto_pass | that's not including bacteria | 新题干定位唯一；答案/高亮完整；原句可用 |
| gi_v02_575951b8f98e | T2 / ielts17_test4_p2 B-03 | auto_pass | it was the first country to industrialise | 新题干定位唯一；答案/高亮完整；原句可用 |
| gi_v02_35c7914eb701 | T2 / ielts17_test4_p2 B-04 | auto_pass | they industrialised late | 新题干定位唯一；答案/高亮完整；原句可用 |
| gi_v02_8d12000ccc0a | T2 / ielts6_test4_p1 E-23 | auto_pass | it doesn't make me prescribe their medicine | 新题干定位唯一；答案/高亮完整；原句可用 |
| gi_v02_6cda2311a1da | T2 / ielts9_test3_p2 A-01 | needs_review | unlike wind, the tides are predictable and the power input is constant | 目标仍包含两个并列分句；needs正确，不算自动正确题 |

### 4.2 全部77道序号题（当前均auto，逐题连词指向、局部答案及原句未见问题）

| 题号 | 来源 | 连词 / 序号 / 全句次数 | 独立核对 |
| --- | --- | --- | --- |
| gi_v02_005cc06e85f1 | ielts16_test3_p1 A-01 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_00f22ea9fdd9 | ielts12_test5_p2 J-03 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_011375b035b3 | ielts11_test4_p2 C-04 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_0294c71616c4 | ielts6_test2_p2 A-02 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_0b9764d87eff | ielts5_test1_p3 C-11 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_0f279c9eaf5a | ielts11_test3_p1 B-05 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_1053ae38ab22 | ielts7_test1_p1 E-04 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_14fe1215cae1 | ielts20_test3_p1 K-02 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_16448833f93a | ielts5_test3_p3 G-42 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_17ab20f71721 | ielts15_test1_p1 G-01 | and / 2 / 3 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_1b1783d06ff3 | ielts11_test3_p1 B-01 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_1ca8fd648fb8 | ielts11_test3_p1 D-04 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_1d9f365ece42 | ielts6_test1_p2 G-04 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_1f1e517aa4da | ielts14_test2_p1 D-03 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_2043b6dfbbed | ielts7_test4_p3 C-05 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_248799464af5 | ielts12_test8_p1 C-03 | and / 4 / 4 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_28dc3a20eae4 | ielts20_test3_p2 A-05 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_2cafd36a7a6a | ielts18_test3_p3 A-05 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_2ff29d9d5ea2 | ielts8_test3_p2 E-02 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_35c7914eb701 | ielts17_test4_p2 B-04 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_375ce7575820 | ielts18_test4_p1 A-06 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_38b4a0d1e7f6 | ielts12_test6_p2 C-04 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_3af5da7b9836 | ielts17_test1_p1 H-09 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_3e4792dd1297 | ielts13_test1_p1 A-06 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_40b28d51f5de | ielts15_test1_p3 D-03 | and / 3 / 3 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_41005c2bc579 | ielts18_test3_p3 A-02 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_437159be961a | ielts17_test4_p1 A-06 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_449dfdb3b860 | ielts14_test4_p2 B-08 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_556b2510f4ce | ielts18_test3_p1 E-07 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_5757dba9cd11 | ielts13_test2_p3 C-03 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_575951b8f98e | ielts17_test4_p2 B-03 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_5c8f7ef7d842 | ielts12_test8_p1 B-06 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_5fb78ddc51b7 | ielts4_test3_p2 C-03 | and / 1 / 3 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_6119086a0018 | ielts10_test2_p1 E-09 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_61e67e82a7c7 | ielts16_test1_p2 F-02 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_66105ccdafdc | ielts4_test2_p1 F-34 | and / 2 / 3 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_67ae0961d270 | ielts20_test1_p2 D-05 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_68937156c274 | ielts17_test1_p2 A-03 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_6c429812b80e | ielts8_test4_p1 C-01 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_6ee7bba63953 | ielts15_test3_p3 I-05 | and / 2 / 3 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_703930cdf055 | ielts12_test8_p3 D-03 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_729c29c8039a | ielts13_test2_p2 A-08 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_73fe727b4971 | ielts17_test1_p3 E-03 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_768dd138f9b6 | ielts15_test2_p2 F-05 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_7c19fd82de59 | ielts8_test3_p2 B-01 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_843c0fa4d33e | ielts20_test3_p2 D-05 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_8ccdd923167e | ielts13_test3_p3 B-03 | and / 2 / 3 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_8d4990efb031 | ielts16_test2_p3 J-02 | and / 1 / 3 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_9193681d2c7d | ielts16_test2_p2 C-01 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_947cf42da794 | ielts19_test2_p3 G-04 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_98bb00dad4cf | ielts4_test1_p2 C-02 | and / 5 / 6 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_9e0cc443e1d7 | ielts18_test3_p3 J-02 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_9fff86e4bbab | ielts19_test2_p1 D-03 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_a0229a3f7156 | ielts19_test2_p1 I-02 | and / 2 / 3 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_a08bcc49fe72 | ielts15_test3_p1 I-03 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_a1edd5a2725d | ielts14_test4_p2 A-02 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_a85dde4a49cd | ielts4_test2_p2 F-29 | and / 3 / 3 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_aef121386858 | ielts19_test2_p1 C-02 | and / 1 / 3 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_b13edf39d2be | ielts12_test5_p3 E-06 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_b2af0ef1f6ba | ielts5_test3_p3 C-21 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_b5b9e54fcde9 | ielts14_test4_p2 B-02 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_b64c32b26c13 | ielts7_test4_p3 C-03 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_ba6033280118 | ielts12_test6_p1 C-01 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_bbc7b3029601 | ielts20_test2_p1 A-03 | and / 3 / 3 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_c126dd8d3bc8 | ielts13_test1_p2 D-12 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_c2cb10d1dede | ielts5_test2_p2 J-40 | but / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_cab98997fa43 | ielts12_test5_p2 F-03 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_d3572eb50a84 | ielts12_test8_p1 B-05 | and / 2 / 3 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_d3f5311a9963 | ielts6_test3_p2 A-05 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_def15c88656b | ielts5_test4_p2 F-21 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_ea10e569a501 | ielts9_test4_p1 F-02 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_ea7a7d8d49e3 | ielts13_test4_p1 A-01 | and / 1 / 3 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_ebef2a926cc8 | ielts20_test4_p3 E-26 | and / 1 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_ede97ea87018 | ielts9_test1_p1 I-06 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_f2b4a4104c44 | ielts20_test4_p3 C-13 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_f649a0039f30 | ielts4_test1_p2 B-02 | and / 2 / 4 | 序号指向答案前连词；不计单词内部；唯一目标成立 |
| gi_v02_fa0ec52fa9cc | ielts19_test3_p1 D-02 | and / 2 / 2 | 序号指向答案前连词；不计单词内部；唯一目标成立 |

### 4.3 无序号抽查20道（seed20261102，按题号排序后 Random.sample）

| 题号 | 题型 / 来源 | 状态 | 答案或目标 | 独立判定 |
| --- | --- | --- | --- | --- |
| gi_v02_21a2b38dfd6f | T2 / ielts7_test4_p3 D-01 | auto_pass | it takes a while for this fatigue to take its toll on performance | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_b3017ad19870 | T2 / ielts14_test2_p1 B-04 | auto_pass | they settled in Montreal | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_4fd7efbd12b8 | T2 / ielts13_test3_p1 A-03 | auto_pass | among the mid-14th-century travel writings of Sir John Mandeville there is mention of 'gre… | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_4033df204f23 | T2 / ielts14_test1_p2 D-04 | auto_pass | this time he succeeded in arousing the interest of the Dutch Ministry of Transport | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_cc6a54ffebec | T2 / ielts15_test1_p3 E-04 | auto_pass | an explorer changes the world | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_164e5ffdfce6 | T2 / ielts6_test1_p3 D-27 | auto_pass | for many people state benefits are their only income | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_60bb5cc29ad1 | T2 / ielts15_test1_p2 G-03 | auto_pass | the need to be flexible in response to this will be vital for those involved in manufactur… | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_c384f5e77281 | T2 / ielts14_test3_p2 F-03 | auto_pass | the glands inside them that secrete potentially useful compounds are smaller still | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_fba46b5d95c5 | T2 / ielts7_test4_p2 E-05 | auto_pass | on any given day, one or more field biologists in a particular area can put a halt to fish… | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_e68844fd37bf | T2 / ielts5_test4_p3 B-06 | auto_pass | the amount of experimental evidence for this phenomenon is considerable | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_5e6efc7ad47e | T2 / ielts5_test3_p2 A-02 | auto_pass | this is no longer happening | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_5cdd0a3ae05b | T2 / ielts6_test4_p2 J-28 | auto_pass | many literacy campaigns in other countries have been much less successful | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_c551e0084b5d | T2 / ielts8_test3_p3 D-22 | auto_pass | within one species the parameter is relatively constant | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_dde8a71da2ed | T2 / ielts9_test4_p2 B-02 | auto_pass | he gave it various elements | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_9bea38329f86 | T2 / ielts10_test1_p3 A-01 | auto_pass | companies put substantial resources into inspiring employees to develop new ideas | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_60a9dc3c5de8 | T2 / ielts4_test1_p2 B-04 | auto_pass | captive animals often object strongly to being touched there | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_f53e9c97e45e | T2 / ielts14_test2_p2 C-03 | auto_pass | the rest of the world is catching up at a frightening rate | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_1c138cfaedb7 | T2 / ielts13_test4_p2 C-05 | auto_pass | then when the plants die and decay these nutrients are returned directly to the soil | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_2d532c15dcee | T2 / ielts20_test1_p3 E-02 | auto_pass | when they were under stress, a different pattern emerged | 连词唯一；目标前提、范围成立；原句可用 |
| gi_v02_37aa937e5f7e | T2 / ielts18_test1_p2 B-06 | auto_pass | wood energy markets help promote this | 连词唯一；目标前提、范围成立；原句可用 |

### 4.4 全部158道缺cue题（全部needs；不等于158个原文错误）

| 序 | 题号 | 来源 | 起点前词 | 目标起始 | 独立判断 |
| --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_9f0b338c1cbf | ielts10_test1_p1 B-04 | community | others were positioned beside ponds | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 2 | gi_v02_26d5f75cae2c | ielts10_test1_p1 C-02 | low | several levels would have to be negotiated | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 3 | gi_v02_82861e7e1b86 | ielts10_test1_p1 E-02 | spells | southern Rajasthan suffered an eight-year drought between 1996… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 4 | gi_v02_9eab14328d4e | ielts10_test1_p1 J-01 | wells | aesthetically it's perhaps one of the most dramatic | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 5 | gi_v02_895d4a3978c7 | ielts10_test1_p2 H-02 | infrastructure | nor does it guarantee better regional cohesion | 连词在答案内；可另设计“引出的”题干；当前后面题干不可直接套用 |
| 6 | gi_v02_6b6a8b979b80 | ielts10_test2_p1 C-04 | deduction | the skepticism gives way to wary admiration | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 7 | gi_v02_59c7cf0879a3 | ielts10_test2_p2 A-07 | thinking | nor predict creativity | 连词在答案内；可另设计“引出的”题干；当前后面题干不可直接套用 |
| 8 | gi_v02_e8023b35f8c3 | ielts10_test2_p2 B-05 | metacognition | so children should be helped to be aware of their feelings aro… | 目标以for/so开头，不在当前cue词表；仍须核并列/从属及边界 |
| 9 | gi_v02_672b3cd2fb4c | ielts10_test2_p2 C-05 | case | adjustments have to be made in methods of learning and teachin… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 10 | gi_v02_ecbdbbc64457 | ielts10_test3_p1 E-02 | countries | it ranks second or third | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 11 | gi_v02_792dc8961f28 | ielts10_test3_p2 C-01 | known | it is created by anthocyanins | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 12 | gi_v02_a42b8e39b624 | ielts10_test3_p3 K-01 | Pacific | then called it quits | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 13 | gi_v02_5cd702fb712a | ielts10_test4_p2 H-07 | down | then looked for a way to mitigate the danger | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 14 | gi_v02_4de0901bdfcb | ielts10_test4_p3 A-04 | 句首 | Not only are evolutionary throwbacks possible | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 15 | gi_v02_d62aa3595b78 | ielts10_test4_p3 G-02 | state | then metamorphose into the adult form | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 16 | gi_v02_f96fcf9d20e6 | ielts10_test4_p3 H-06 | more | digit loss and gain has occurred on more than one occasion | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 17 | gi_v02_7fed3790e876 | ielts11_test1_p2 D-04 | robust | the steel sections were bolted rather than welded together | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 18 | gi_v02_b0babf364473 | ielts11_test1_p2 E-06 | mass | it rotates through 180° in five and a half minutes | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 19 | gi_v02_09c6f737187a | ielts11_test2_p1 D-04 | unsatisfactory | so McKee entered into collaboration with Harold E. Edgerton | 目标以for/so开头，不在当前cue词表；仍须核并列/从属及边界 |
| 20 | gi_v02_1fd2a44ee8dc | ielts11_test2_p3 D-04 | meaning | the more rewarding is the moment of recognition | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 21 | gi_v02_6d1723e9e1d8 | ielts11_test3_p2 B-07 | journey | its undivided intent is arrival | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 22 | gi_v02_f2b5956e07aa | ielts11_test4_p2 B-04 | Spade | film personality and life personality seem to merge | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 23 | gi_v02_00d8de07eb38 | ielts11_test4_p2 D-03 | conversation | there is no time for audience reflection | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 24 | gi_v02_a85862b93fe7 | ielts11_test4_p2 E-05 | volume | this helps to engage the audience in a moment of suspense | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 25 | gi_v02_3c154c9f4b49 | ielts11_test4_p2 F-04 | argument | at the same time the noise of the siren adds to the realism of… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 26 | gi_v02_2e083f05983b | ielts11_test4_p3 B-04 | praise | for the homage to language's unique accomplishment conceals a … | 目标以for/so开头，不在当前cue词表；仍须核并列/从属及边界 |
| 27 | gi_v02_1c81841fe374 | ielts11_test4_p3 C-04 | machine | let it arrange them in some very special orders | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 28 | gi_v02_28fa08d0bcbc | ielts12_test5_p1 E-02 | invented | so the job is done by teams of highly skilled workers | 目标以for/so开头，不在当前cue词表；仍须核并列/从属及边界 |
| 29 | gi_v02_1edc92458f7b | ielts12_test5_p1 E-03 | axes | then lever it away in pieces as large as they can manage | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 30 | gi_v02_12bded0452bd | ielts12_test5_p2 B-01 | money | this could be called an instrumental reason for collecting | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 31 | gi_v02_a01a3e263079 | ielts12_test5_p2 B-03 | too | buying cheap and selling dear can give the collector a sense o… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 32 | gi_v02_b81e747ccb9c | ielts12_test5_p2 I-01 | though | so what we might call a psychological reason for collecting is… | 目标以for/so开头，不在当前cue词表；仍须核并列/从属及边界 |
| 33 | gi_v02_a53cbfad3fee | ielts12_test5_p3 A-05 | not | we have it on the books | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 34 | gi_v02_d0e0f6e726c6 | ielts12_test5_p3 B-03 | science | they are highly welcome as part of the increasing professional… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 35 | gi_v02_90751cb59b96 | ielts12_test5_p3 C-07 | marketed | obviously it need not be done in a principled (=ethical) fashi… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 36 | gi_v02_9d15bd08555a | ielts12_test5_p3 E-08 | end | hence both deserve scrutiny | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 37 | gi_v02_a0d187e4e9d8 | ielts12_test6_p2 D-04 | dream | the sight held me spellbound | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 38 | gi_v02_eac01e637d9a | ielts12_test6_p2 E-03 | buildings | then descended and rejoined his companions | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 39 | gi_v02_6bc31c745a36 | ielts12_test6_p2 E-04 | site | nor did he realise what use he could make of the discovery | 连词在答案内；可另设计“引出的”题干；当前后面题干不可直接套用 |
| 40 | gi_v02_1b496279163c | ielts12_test6_p3 B-05 | language | auditory input activates corresponding words | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 41 | gi_v02_927df192d2e2 | ielts12_test6_p3 C-09 | triangle | they do so more quickly than monolingual people | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 42 | gi_v02_045109465f86 | ielts12_test6_p3 G-04 | learned | only the bilingual babies were able to successfully learn the … | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 43 | gi_v02_602d19bbe476 | ielts12_test7_p1 F-02 | cargo | so a custom crate was designed | 目标以for/so开头，不在当前cue词表；仍须核并列/从属及边界 |
| 44 | gi_v02_bde9d063fb8f | ielts12_test7_p3 D-06 | why | composers often introduce a key note in the beginning of a son… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 45 | gi_v02_9673151edd11 | ielts13_test2_p2 F-04 | amygdala | so it's going to have many effects on just about everything | 目标以for/so开头，不在当前cue词表；仍须核并列/从属及边界 |
| 46 | gi_v02_c936451b79c5 | ielts13_test4_p1 C-04 | water | so this was a rather strange choice of name for a ship | 目标以for/so开头，不在当前cue词表；仍须核并列/从属及边界 |
| 47 | gi_v02_a236c0424e37 | ielts13_test4_p1 E-01 | prestige | so Cutty Sark was designed to make the journey more quickly th… | 目标以for/so开头，不在当前cue词表；仍须核并列/从属及边界 |
| 48 | gi_v02_9b59430fc90a | ielts13_test4_p1 G-01 | instead | she took on the much less prestigious work of carrying any car… | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 49 | gi_v02_5de91fb1180d | ielts13_test4_p2 B-05 | plants | they lock in their carbon content | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 50 | gi_v02_d5cb60990603 | ielts14_test1_p2 B-03 | city | they removed them | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 51 | gi_v02_dfaf79553539 | ielts14_test1_p2 D-09 | card | the plan started with 250 bikes, distributed over five station… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 52 | gi_v02_aca740d7d6c9 | ielts14_test2_p1 E-03 | landscape | he usually composed his scenes around such human pursuits as f… | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 53 | gi_v02_d2ff5642d66c | ielts14_test2_p1 E-06 | market | Henderson had stock photographs on display at his studio for m… | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 54 | gi_v02_5523457f7c3a | ielts14_test2_p3 D-02 | work | it's the basic assumptions we hold in approaching how we work | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 55 | gi_v02_4a2ff999e21b | ielts14_test3_p1 A-01 | way | no one does | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 56 | gi_v02_06c940976997 | ielts14_test3_p2 A-02 | new | we have been doing it for tens of thousands of years | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 57 | gi_v02_636dfc886f41 | ielts14_test3_p3 G-02 | playfulness | however, other researchers have suggested | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 58 | gi_v02_d0329f20304c | ielts14_test3_p3 H-03 | learning | rather, they can provide optimal contexts for learning | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 59 | gi_v02_cdd98a4ef0d1 | ielts15_test1_p2 G-01 | research | these can most probably be conquered within the next 10 years | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 60 | gi_v02_ae24d9de2c4d | ielts15_test1_p3 A-02 | human | indeed, this has played an important part in our success as a … | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 61 | gi_v02_e91c80709486 | ielts15_test1_p3 G-09 | lies | exploration of it is now down to the details | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 62 | gi_v02_070f485c3c4b | ielts16_test1_p2 D-04 | corner | the entire wall was then ringed by a trench 750 meters long an… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 63 | gi_v02_18010363dbf5 | ielts16_test2_p2 C-07 | food | we are continually swapping microbes with other humans, pets a… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 64 | gi_v02_bb1fe0a5d63a | ielts16_test2_p2 F-03 | bacteria | yet at the same time we are sold yoghurts and drinks | 连词在答案内；可另设计“引出的”题干；当前后面题干不可直接套用 |
| 65 | gi_v02_4040ee0b40d8 | ielts16_test2_p3 A-02 | all | in fact, the latest studies suggest | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 66 | gi_v02_3cf496ae7083 | ielts16_test2_p3 E-02 | viewpoint | we reason more broadly and focus more on interpersonal and mor… | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 67 | gi_v02_4210cabf9f41 | ielts16_test4_p2 A-03 | smartphones | older kids don't read at all | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 68 | gi_v02_16247344be12 | ielts16_test4_p2 D-01 | language | it needs an environment to develop | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 69 | gi_v02_350cbfa13d87 | ielts17_test1_p1 F-01 | authorised | these were built over the next five years | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 70 | gi_v02_b81dd5f65600 | ielts17_test3_p2 F-09 | Malaysia | it's been allowed to get out of hand | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 71 | gi_v02_ac9e93766634 | ielts17_test3_p3 A-04 | to | the second deals primarily with the 20th century and is a comp… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 72 | gi_v02_2d08fc04cb7d | ielts17_test3_p3 H-05 | boom | cheap credit was not, he argues, the primary cause | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 73 | gi_v02_7de379d90a71 | ielts17_test4_p2 C-03 | activities | ownership of books and education-related objects like pens and… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 74 | gi_v02_c187a35b5e64 | ielts17_test4_p2 E-01 | Ogilvie | it is time 'to ask the big questions' | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 75 | gi_v02_165f38a2f6aa | ielts18_test1_p1 A-04 | lettuces | near those are aromatic herbs | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 76 | gi_v02_9db550bf9ff8 | ielts18_test1_p2 A-04 | bowls | it brings an opportunity for a unique and beautiful piece of a… | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 77 | gi_v02_8755746b4c41 | ielts18_test1_p2 D-04 | wildlife | they have a better chance to regenerate in a less crowded envi… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 78 | gi_v02_665286b2f619 | ielts18_test2_p1 D-02 | alternatively | they may have towed each stone with a fleet of vessels | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 79 | gi_v02_1342688aa1cf | ielts18_test2_p1 F-02 | ring | some were assembled into the iconic three-piece structures cal… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 80 | gi_v02_ac8a047e8c71 | ielts18_test3_p3 E-03 | collective | mediocrity prevails | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 81 | gi_v02_0d4f69bb426d | ielts18_test3_p3 G-06 | that | the smart stay smart and the dumb get dumber | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 82 | gi_v02_2b2ae48eccc7 | ielts18_test4_p1 C-02 | forward | only recently, San Francisco, USA, created a policy | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 83 | gi_v02_6b68754d7a44 | ielts18_test4_p1 D-02 | cases | volunteers may be needed to help out | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 84 | gi_v02_04876410a429 | ielts18_test4_p2 B-04 | are | smart is something | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 85 | gi_v02_5e49372ad21a | ielts19_test1_p3 E-04 | falsehood | Spinoza argued that people accept all encountered information … | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 86 | gi_v02_add41abb7ba3 | ielts19_test2_p2 E-06 | responses | can increase risk of heart disease and depression | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 87 | gi_v02_41a08e520531 | ielts19_test3_p2 D-03 | WI | this practice causes six per cent of all global carbon emissio… | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 88 | gi_v02_c2c5ad28303b | ielts19_test3_p2 E-06 | water | so this is one of the most alarming consequences of peatland c… | 目标以for/so开头，不在当前cue词表；仍须核并列/从属及边界 |
| 89 | gi_v02_7d7151c64eea | ielts19_test3_p2 E-07 | year | so within half a century, very large landscapes on Sumatra and… | 目标以for/so开头，不在当前cue词表；仍须核并列/从属及边界 |
| 90 | gi_v02_6256648996aa | ielts19_test3_p3 G-01 | noise | they will also need to be socially aware | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 91 | gi_v02_5ef50026f40e | ielts19_test4_p1 B-04 | phenology | so when an animal or plant starts to do something earlier in t… | 目标以for/so开头，不在当前cue词表；仍须核并列/从属及边界 |
| 92 | gi_v02_63e32158f73f | ielts20_test1_p3 B-01 | stress | so we visited some local fire stations | 目标以for/so开头，不在当前cue词表；仍须核并列/从属及边界 |
| 93 | gi_v02_ccb6272250f7 | ielts20_test1_p3 B-03 | relaxed | they’ll spend their time | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 94 | gi_v02_e3f2ec8be2eb | ielts20_test1_p3 B-04 | to | they’ll enter burning homes | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 95 | gi_v02_30598799500d | ielts20_test1_p3 K-05 | globe | stocks are sold | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 96 | gi_v02_490baad50dbf | ielts20_test2_p1 B-01 | neck | most others, including humans and giraffes, have seven | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 97 | gi_v02_34dbb8faa66f | ielts20_test2_p1 E-01 | mammals | they need to come up to the surface | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 98 | gi_v02_29bc0b964c96 | ielts20_test3_p1 J-01 | mealtimes | so the moment was right for the arrival of the ‘TV Dinner’ | 目标以for/so开头，不在当前cue词表；仍须核并列/从属及边界 |
| 99 | gi_v02_a7a9689dcf78 | ielts20_test3_p1 J-03 | budget | it launched the first ‘TV Dinner’ | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 100 | gi_v02_b263d9d83fd9 | ielts20_test3_p3 I-01 | persist | none have in fact risen up and challenged human supremacy | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 101 | gi_v02_edcaadcccbd7 | ielts20_test3_p3 I-03 | robots | many people welcome machine intelligence | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 102 | gi_v02_91b2ea906310 | ielts20_test4_p2 B-06 | USA | seawater isn’t just breaching the island city’s walls, it’s se… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 103 | gi_v02_173487fcac82 | ielts4_test1_p1 H-01 | destruction | a similar proportion said that pollution is destroying rainfor… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 104 | gi_v02_dac537cdca9e | ielts4_test2_p2 F-27 | complaints | 12% suffer from digestive problems | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 105 | gi_v02_4038ed7ae5d8 | ielts4_test3_p2 A-07 | continents | they are also thought | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 106 | gi_v02_d700ebcdb493 | ielts4_test3_p2 D-03 | crater | later the lava cools slowly into a huge, hard, stable plug | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 107 | gi_v02_697f0e600879 | ielts4_test3_p3 C-12 | cases | decisions have to be made about the best investigative techniq… | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 108 | gi_v02_532bbeb8729e | ielts4_test3_p3 G-35 | text | others are extremely selective | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 109 | gi_v02_9c0dc69c4c51 | ielts4_test3_p3 G-36 | data | it can take up to several hours to provide an accurate transcr… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 110 | gi_v02_d1f8ab2c3d11 | ielts5_test1_p1 B-02 | words | one function of the dictionary was to enable its student to co… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 111 | gi_v02_b9ca8f64d836 | ielts5_test1_p1 F-01 | hand | Johnson wrote the definitions of over 40,000 words | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 112 | gi_v02_06fe31053cc8 | ielts5_test3_p3 B-10 | 句首 | The field was launched, and the term 'artificial intelligence'… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 113 | gi_v02_bf6f6ea76961 | ielts5_test3_p3 B-13 | ways | AI unified the field in name only | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 114 | gi_v02_3d6e5fb6e1be | ielts5_test4_p1 B-18 | food | this has led to increasing dependence on bought food and store… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 115 | gi_v02_5ba5a7267a3e | ielts5_test4_p2 D-15 | floors | is almost as easy | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 116 | gi_v02_7de0191dc0b7 | ielts6_test1_p2 B-08 | spring | trade may lose its advantages | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 117 | gi_v02_97e5894be870 | ielts6_test1_p3 C-17 | limits | sometimes the colonists were successful, sometimes they failed… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 118 | gi_v02_aa253cc85963 | ielts6_test2_p3 B-03 | numbers | instead their considerations would have been more of the kind … | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 119 | gi_v02_2db45405c04b | ielts6_test2_p3 E-02 | birds | however, it is not an elementary step to associate the number … | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 120 | gi_v02_daccafd4b9e9 | ielts6_test3_p1 C-08 | still | only reality moved | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 121 | gi_v02_89c1037039bb | ielts6_test3_p1 D-02 | familiar | the magic was accepted | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 122 | gi_v02_840a0970fe7d | ielts6_test3_p1 E-03 | like | they knew how other people worked and lived | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 123 | gi_v02_b6b626667994 | ielts6_test3_p1 I-04 | stories | early producers doubted the ability of audiences to concentrat… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 124 | gi_v02_272b6653d045 | ielts6_test3_p2 F-08 | highly | whereas clerical workers rated advancement in the lower third … | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 125 | gi_v02_c81abd38c264 | ielts6_test3_p2 F-09 | inequity | so an ideal should probably weigh different inputs and outcome… | 目标以for/so开头，不在当前cue词表；仍须核并列/从属及边界 |
| 126 | gi_v02_09b2220b9d8f | ielts6_test3_p3 G-28 | restriction | the trick is finding the right one | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 127 | gi_v02_afccc99d3d3b | ielts6_test4_p1 F-28 | patterns | the conclusion was that the availability of samples led them t… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 128 | gi_v02_b7f6f0e3c561 | ielts7_test1_p2 C-02 | water | some two and a half billion do not have adequate sanitation se… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 129 | gi_v02_909351fbd543 | ielts7_test1_p2 G-05 | output | by 1989 this had dropped to 3.5 million gallons | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 130 | gi_v02_8276fdbf80d2 | ielts7_test1_p3 D-15 | part | the music is classical (Mozart, Beethoven, Brahms) and the tea… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 131 | gi_v02_aebec6a611c9 | ielts7_test1_p3 D-20 | passive | they listen to the music but make no attempt to learn the mate… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 132 | gi_v02_49a3dc27e6b3 | ielts7_test2_p2 F-02 | seen | it may be more feasible | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 133 | gi_v02_8644dfcbcd40 | ielts7_test2_p3 D-14 | breeding | donkeys should become more affordable | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 134 | gi_v02_be52863170f9 | ielts7_test3_p2 F-01 | population | they involve the study of teeth and of languages | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 135 | gi_v02_a05ed79f516d | ielts7_test4_p1 F-07 | BC | the Chinese were using them to deliver messages and dump flami… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 136 | gi_v02_c1c8ea6e1699 | ielts8_test1_p1 C-06 | 句首 | Summer hours were long, winter ones short | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 137 | gi_v02_8b2d87bc9ec7 | ielts8_test1_p1 H-03 | equipment | they do so as well for mobile phones, instant stock-trading sy… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 138 | gi_v02_2ef46ae16454 | ielts8_test1_p2 B-02 | flags | while beacons and flashing lights were placed along cross-coun… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 139 | gi_v02_fc5805e514af | ielts8_test1_p2 B-03 | s | radio communication was coming into use for ATC | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 140 | gi_v02_042f2ed230a2 | ielts8_test1_p2 E-07 | m | while the pilot who does want the protection afforded by ATC c… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 141 | gi_v02_57cd1cb843de | ielts8_test1_p2 G-02 | while | controlled airspace below 5,490m above sea level and not in th… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 142 | gi_v02_53d9564a4678 | ielts8_test1_p3 F-27 | people | the group is just not big enough | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 143 | gi_v02_302c0a35574c | ielts8_test2_p1 C-03 | in | he had the idea of using a bed of molten metal to form the fla… | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 144 | gi_v02_152c763a9d96 | ielts8_test2_p1 E-01 | by | he had convinced his company to build a full-scale plant | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 145 | gi_v02_6c07d8087461 | ielts8_test2_p1 H-01 | stage | computers translate customer requirements into patterns of cut… | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 146 | gi_v02_e0407f85fcf5 | ielts8_test2_p2 A-02 | unchanging | yet humanity has been at the mercy of climate change for its e… | 连词在答案内；可另设计“引出的”题干；当前后面题干不可直接套用 |
| 147 | gi_v02_bafcfc344205 | ielts8_test2_p3 B-05 | considered | smells register | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 148 | gi_v02_5aa71827bec6 | ielts8_test3_p1 A-03 | open | a lone golfer may be a lightning bolt's most inviting target | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 149 | gi_v02_59101469193b | ielts8_test3_p2 B-04 | many | 'intellectual' is a term of denigration | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 150 | gi_v02_8daef13e78fe | ielts8_test3_p2 C-05 | today | home tutoring was common in the families of the nobility and w… | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 151 | gi_v02_5ed4bd1711f2 | ielts8_test3_p2 F-02 | educated | we can learn from the achievements of those more gifted than o… | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 152 | gi_v02_90448efe5809 | ielts8_test4_p1 D-02 | then | the teachers comment, correct or elaborate as necessary | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 153 | gi_v02_6e432439cf3e | ielts9_test1_p1 C-02 | years | he became Hofmann's youngest assistant | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 154 | gi_v02_d2977ae35436 | ielts9_test1_p3 B-12 | water | they breathe air | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |
| 155 | gi_v02_809ec7d96794 | ielts9_test2_p2 C-04 | Sun | the scale of the Solar System would fall into place | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 156 | gi_v02_6d64347e76fb | ielts9_test3_p1 C-04 | correctly | deviations from it are said to be 'incorrect' | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 157 | gi_v02_009f5bacd933 | ielts9_test3_p1 D-04 | accurately | others are 'proscribed' | 答案起点前无紧邻白名单连词；标点连接、前项或标注类别/范围问题，保守needs |
| 158 | gi_v02_093cb002b0ce | ielts9_test4_p3 D-02 | fulfil | they are also operating in a very competitive environment | 上文可见连词，但与起点隔了状语/插入语/主语；需先核范围，保守needs |

### 4.5 嵌套查漏的4条表面命中（均auto）

| 题号 | 题型 / 来源 | 状态 | 答案或目标 | 独立判定 |
| --- | --- | --- | --- | --- |
| gi_v02_6aa39bfe587c | T2 / ielts11_test2_p2 C-04 | auto_pass | that required both a lot of wood and a lot of people | 目标内只是名词并列等，不是第二个同层独立分句；题干成立 |
| gi_v02_d3572eb50a84 | T2 / ielts12_test8_p1 B-05 | auto_pass | it was not until their empire collapsed in 476 AD that glass-making knowledge became wides… | 目标内只是名词并列等，不是第二个同层独立分句；题干成立 |
| gi_v02_68937156c274 | T2 / ielts17_test1_p2 A-03 | auto_pass | stadiums finished for major events such as the Olympic Games or the FIFA World Cup have no… | 目标内只是名词并列等，不是第二个同层独立分句；题干成立 |
| gi_v02_6c429812b80e | T2 / ielts8_test4_p1 C-01 | auto_pass | the remarkably quiet classes take their own notes of the points made and the examples demo… | 目标内只是名词并列等，不是第二个同层独立分句；题干成立 |

## 5. 复合修饰语删除与40道恢复题

逐读43道删除项及原上下文：water-borne、profit-making、mixed-ability、check-out等中的片段不再作T1动词干扰项，方向符合用户决定。依存词性只是证据，不保证其它干扰项正确；Z3即反例。原word-spot、hand-raising、to re-establish、to be road-tested的相关T1仍needs，没有误删这些真实动词片段；完整主句自身T6可以照常auto。

第十二轮恢复40道，到当前为38auto、2needs；**38auto中37题本次未见问题、1题Z3；2needs均还有粒子问题，不能算进“全部正确”。** 原句均可用于教学，问题在生成题。局部答案及剩余干扰项逐题如下。

| 题号 | 来源 | 当前状态 | 主答案 | 剩余干扰项 | 独立判断 |
| --- | --- | --- | --- | --- | --- |
| gi_v02_1195f2b74ef7 | ielts10_test4_p3 D-04 | auto_pass | argued | must be | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_1213768264f6 | ielts14_test2_p2 I-02 | auto_pass | have / worked | built; assisted; can be switched off | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_14a707bfbdde | ielts12_test6_p1 I-03 | auto_pass | wrote | invest; guarantee; is | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_3a9a831b1649 | ielts13_test1_p2 F-01 | auto_pass | speculates | might / be | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_3b2a3067a435 | ielts14_test4_p2 B-06 | auto_pass | exist | have been boosted | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_47f24247866b | ielts20_test2_p3 A-02 | auto_pass | had | connected; modified | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_47f9d492f5b3 | ielts5_test1_p2 F-01 | auto_pass | might / be | must be; was activated | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_4945b9c8244c | ielts14_test2_p1 G-05 | auto_pass | led | to record; connecting | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_4eab3bab30f1 | ielts7_test1_p1 A-05 | auto_pass | has / favoured | make | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_5282519b7fa1 | ielts14_test4_p3 K-04 | auto_pass | might / be | can understand; is damaging | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_5358c771bef2 | ielts11_test2_p2 D-03 | auto_pass | indicate | went; to protect | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_57507ce7bbad | ielts10_test2_p2 F-03 | auto_pass | can / limit | is; motivates | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_62e56f5f661a | ielts5_test3_p2 B-04 | auto_pass | brought / in | replacing; had been washed away; dispensing | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_67a4a168425a | ielts16_test4_p2 F-04 | auto_pass | indicated | read; were | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_6878167af80a | ielts11_test1_p3 B-05 | auto_pass | would / employ | to form | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_6b3e67116a8e | ielts6_test2_p2 F-16 | auto_pass | is | uncovered; are; to live | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_6fb98ed46203 | ielts10_test3_p3 J-03 | auto_pass | points / out | obtained; indicate | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_70c2a6526058 | ielts13_test2_p1 E-02 | auto_pass | began | to boost; satisfy | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_718d24550f2b | ielts16_test4_p2 B-04 | auto_pass | cautions | surfacing; may be; move | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_71cde94f9214 | ielts16_test4_p3 B-08 | auto_pass | would / n't / be | was; were; to be / understood | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_7308fd06bb64 | ielts15_test1_p2 A-07 | auto_pass | has / gathered | announced; had been trialling | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_8a55ab7a41de | ielts18_test1_p2 D-02 | auto_pass | is / cut / down | to allow; remain | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_8ea937652bf7 | ielts14_test1_p1 N-01 | auto_pass | has / involved | developing | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_96294008ca3c | ielts6_test2_p2 I-30 | auto_pass | found | exercise; have raised; coursing | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_97252727a6b7 | ielts14_test1_p2 F-02 | auto_pass | got | wanted; to set up | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_978ce796e05c | ielts8_test1_p3 B-05 | auto_pass | do / concur | has come; means | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_9a27b9cf8463 | ielts8_test4_p1 E-01 | auto_pass | is | could be kept | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_a4cd7d2fad47 | ielts11_test1_p1 C-04 | auto_pass | means | have; subject; can do; hope | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_accf19fe1002 | ielts18_test3_p2 G-05 | auto_pass | remained | were | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_b16884621b7b | ielts15_test4_p3 B-03 | auto_pass | ignores | are not; provided; do | 主答案对；provided连词误作干扰项（Z3）；原句可用 |
| gi_v02_b983993a8787 | ielts9_test3_p3 E-28 | auto_pass | have / become | uses; ensures; can read | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_bb81dbbb6013 | ielts10_test2_p1 E-04 | auto_pass | revealed | was | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_c19cc9a4e423 | ielts14_test3_p2 I-02 | auto_pass | is | 'd love; to help; develop | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_c62d5283de92 | ielts5_test3_p3 A-09 | needs_review | suggests | are starting; to use; has moved; being seen | 答案suggests对；has moved缺on，Y3降级合理；原句可用 |
| gi_v02_c75314581269 | ielts19_test1_p1 E-01 | needs_review | date | started; playing | 答案date缺back，Y3降级合理；原句可用 |
| gi_v02_cbb991ffd153 | ielts16_test4_p2 D-04 | auto_pass | is | writes; will be allocated | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_cd728f0f7dd3 | ielts13_test3_p1 D-05 | auto_pass | acquired | introduced | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_db5acf9f87cd | ielts18_test1_p1 F-01 | auto_pass | sells | grown; are | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_ee6c86ecc12c | ielts16_test2_p1 E-02 | auto_pass | is | consists | 主答案/剩余干扰项成立，片段已删除；原句可用 |
| gi_v02_faabf8c134fd | ielts15_test3_p2 C-05 | auto_pass | flows | heated; is converted | 主答案/剩余干扰项成立，片段已删除；原句可用 |

### 5.1 另3道删除了片段但仍待复核

| 题号 | 题型 / 来源 | 状态 | 答案或目标 | 独立判定 |
| --- | --- | --- | --- | --- |
| gi_v02_1418d31c7f8d | T1 / ielts11_test1_p3 D-07 | needs_review | say | 删除复合修饰语片段成立；原有定位/解析根问题仍需复核 |
| gi_v02_faf124494ea4 | T1 / ielts13_test4_p3 C-02 | needs_review | is | 删除复合修饰语片段成立；原有定位/解析根问题仍需复核 |
| gi_v02_aeea93ff598c | T1 / ielts7_test4_p2 E-01 | needs_review | is | 删除复合修饰语片段成立；原有定位/解析根问题仍需复核 |

真实动词控制：word-spot 的 T1 `gi_v02_0cc036914ffd`、hand-raising 的 T1 `gi_v02_a2c3b8ddd827`、to re-establish 的 T1 `gi_v02_39a5639ec9f7`、to be road-tested 的 T1 `gi_v02_9102debcb432` 均仍带 hyphenated_word_split、needs。`gi_v02_83675968fdcd` 的 use 和 `gi_v02_217cb84336c9` 的 involved 主句T6仍auto，身份正确，未被T1片段干扰连带降级。

## 6. Y1–Y3、A8嵌套的点名与额外影响

### 6.1 原35题逐一对应

旧题号来自上一轮报告，current即35e37c5全池；Y1换4个T6题号，其余题号不变。当前6auto/29needs；6auto里5个局部答案和完整单位未见问题，lives仍缺up（Z1）。29needs没有算进自动题正确数。

| 原问题 | 旧题号 | 当前题号 | 来源 | 当前状态 | 独立复核 |
| --- | --- | --- | --- | --- | --- |
| Y1 | gi_v02_6ce16124dbb2 | gi_v02_6ce16124dbb2 | T1 ielts11_test1_p2 E-03 | auto_pass | not作用域已改对；单位/身份正确 |
| Y1 | gi_v02_a61a5b99135c | gi_v02_ebed8d7d131d | T6 ielts11_test1_p2 E-03 | auto_pass | not作用域已改对；单位/身份正确 |
| Y1 | gi_v02_3002b418088f | gi_v02_3002b418088f | T1 ielts11_test2_p1 E-05 | auto_pass | not作用域已改对；单位/身份正确 |
| Y1 | gi_v02_ccbce5a7be7b | gi_v02_ccbce5a7be7b | T1 ielts14_test2_p3 H-04 | auto_pass | not作用域已改对；单位/身份正确 |
| Y1 | gi_v02_35474f09ec89 | gi_v02_100095519c58 | T6 ielts5_test3_p3 E-35 | auto_pass | not已改对；lives仍缺up，见Z1 |
| Y1 | gi_v02_044d1a9f8a14 | gi_v02_aaac16edcfbf | T6 ielts7_test1_p1 C-08 | needs_review | is身份对；fish中的is子串导致保守needs，见Z4 |
| Y1 | gi_v02_fe9aead717a1 | gi_v02_c9b4d4f8139c | T6 ielts11_test4_p3 B-01 | auto_pass | not作用域已改对；单位/身份正确 |
| Y2 | gi_v02_f7cd971488b0 | gi_v02_f7cd971488b0 | T6 ielts10_test3_p3 C-04 | needs_review | for并列身份需复核；不再自动批准原答案/唯一主句前提 |
| Y2 | gi_v02_f32918997270 | gi_v02_f32918997270 | T6 ielts10_test3_p3 E-03 | needs_review | for并列身份需复核；不再自动批准原答案/唯一主句前提 |
| Y2 | gi_v02_d4fdc39f0b39 | gi_v02_d4fdc39f0b39 | T1 ielts8_test2_p2 D-04 | needs_review | for并列身份需复核；不再自动批准原答案/唯一主句前提 |
| Y2 | gi_v02_759fc82d90f1 | gi_v02_759fc82d90f1 | T5 ielts8_test2_p2 D-04 | needs_review | for并列身份需复核；不再自动批准原答案/唯一主句前提 |
| Y2 | gi_v02_967f99c9b5a8 | gi_v02_967f99c9b5a8 | T6 ielts8_test2_p2 D-04 | needs_review | for并列身份需复核；不再自动批准原答案/唯一主句前提 |
| Y2 | gi_v02_9350e99ac9fb | gi_v02_9350e99ac9fb | T6 ielts9_test1_p3 B-13 | needs_review | for并列身份需复核；不再自动批准原答案/唯一主句前提 |
| Y3 | gi_v02_051024162296 | gi_v02_051024162296 | T1 ielts11_test4_p1 D-01 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_1090ec7f7d3f | gi_v02_1090ec7f7d3f | T6 ielts11_test4_p1 D-01 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_de552d2832c0 | gi_v02_de552d2832c0 | T6 ielts12_test8_p1 A-03 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_1d976c3e5337 | gi_v02_1d976c3e5337 | T1 ielts13_test3_p2 C-06 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_44fd8b8dd379 | gi_v02_44fd8b8dd379 | T6 ielts13_test3_p2 C-06 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_9eedd4ac446f | gi_v02_9eedd4ac446f | T1 ielts14_test1_p2 A-01 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_dd42053a2258 | gi_v02_dd42053a2258 | T6 ielts14_test1_p2 A-01 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_013b8acb1018 | gi_v02_013b8acb1018 | T1 ielts16_test2_p1 F-02 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_4f548033a581 | gi_v02_4f548033a581 | T6 ielts16_test2_p1 F-02 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_095923e43569 | gi_v02_095923e43569 | T1 ielts16_test2_p3 H-02 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_05e6a3ca1a02 | gi_v02_05e6a3ca1a02 | T6 ielts16_test2_p3 H-02 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_9c0d7a8a7775 | gi_v02_9c0d7a8a7775 | T1 ielts18_test2_p1 B-03 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_1d8e8000c3a4 | gi_v02_1d8e8000c3a4 | T6 ielts18_test2_p1 B-03 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_9066f53b827a | gi_v02_9066f53b827a | T6 ielts19_test1_p1 E-01 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_9c0dbbe8f595 | gi_v02_9c0dbbe8f595 | T1 ielts19_test2_p1 B-01 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_570f21f9d7b1 | gi_v02_570f21f9d7b1 | T6 ielts19_test2_p1 B-01 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_1a955eea23ab | gi_v02_1a955eea23ab | T1 ielts19_test3_p1 D-01 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_c6d551018269 | gi_v02_c6d551018269 | T6 ielts19_test3_p1 D-01 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_e00c7ec83156 | gi_v02_e00c7ec83156 | T1 ielts6_test1_p3 G-41 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_1b9a92c72a9e | gi_v02_1b9a92c72a9e | T6 ielts7_test3_p1 H-02 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_8756902f6024 | gi_v02_8756902f6024 | T1 ielts9_test4_p3 A-06 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |
| Y3 | gi_v02_a3735a0425ca | gi_v02_a3735a0425ca | T6 ielts9_test4_p3 A-06 | needs_review | date back / wrote down单位缺粒子，needs合理；不是内容已修正 |

### 6.2 Y1控制与整库排除检查

普通did not和decided not to go保留not；否定倒装反例见Z6。剑桥全句解析扫描到9个neg/not被排除的来源，均在下表，实际语境没有误删普通谓语否定。机经指定B-03恢复成立（§3）。这不证明任意未来否定结构都安全。

| 来源 | 被挂动词 | 语境判定 |
| --- | --- | --- |
| ielts11_test1_p2 E-03 | carrying | whether-or-not关联结构 |
| ielts11_test2_p1 E-05 | salvage | whether-or-not关联结构 |
| ielts11_test2_p2 A-09 | moved | not作用于引导结构/整段对比，不是否定该动词 |
| ielts11_test4_p3 B-01 | came | not作用于引导结构/整段对比，不是否定该动词 |
| ielts12_test6_p2 D-02 | sees | not作用于引导结构/整段对比，不是否定该动词 |
| ielts14_test2_p3 H-04 | work | whether-or-not关联结构 |
| ielts5_test1_p2 A-02 | have | whether-or-not关联结构 |
| ielts5_test3_p3 E-35 | lives | not作用于引导结构/整段对比，不是否定该动词 |
| ielts7_test1_p1 C-08 | is | whether-or-not关联结构 |

### 6.3 Y2控制及T6隔离

for_clause要求for为mark、有限动词且带自己主语；与type_matches的“for不能自动算状语从句”教学口径一致，非有限for-to不受影响。真实for并列目标6题已降；额外扫描有限for分句所在的auto T1/T5/T6只剩下表4个目标，分别是非谓语、内部时间/定语从句、真正主句，均不应连坐。D-04主句was not的T6与a3逐字段一致。

| 题号 | 题型 / 来源 | 状态 | 答案或目标 | 独立判定 |
| --- | --- | --- | --- | --- |
| gi_v02_c3e803717788 | T6 / ielts10_test3_p3 C-04 | auto_pass | digging up | 目标自身身份正确，与a3逐字段相同；不因同句for分句连带降级 |
| gi_v02_e18def389135 | T6 / ielts10_test3_p3 E-03 | auto_pass | reach | 目标自身身份正确，与a3逐字段相同；不因同句for分句连带降级 |
| gi_v02_2a3eda660059 | T6 / ielts6_test3_p1 B-02 | auto_pass | has made | 目标自身身份正确，与a3逐字段相同；不因同句for分句连带降级 |
| gi_v02_108d6df37ad5 | T6 / ielts8_test2_p2 D-04 | auto_pass | was not | 目标自身身份正确，与a3逐字段相同；不因同句for分句连带降级 |

### 6.4 Y3额外77题，42种表面搭配

按“891b9d2 auto → 当前needs，带particle_outside_unit，扣除原22题”选取，确为77题。显示单位中的任何动词（答案/目标/干扰项）触发皆算一题，不能把同题的多处触发重复计题。

分类判断：明确习语/短语动词遗漏送审有根据；一般移动/方向副词需要语境判别；be+副词/补语不是当然漏了谓语。下表每题均needs，原句通常可用，不能计入auto正确率。带粒子原因的T1对应62个主句T6：37个仅干扰项有问题者逐字段不变；25个自己的单位也触发者才变化。

| 题号 | 来源 / 模板 | 触发搭配 | 当前状态 | 独立判断 |
| --- | --- | --- | --- | --- |
| gi_v02_03132a5547df | ielts9_test1_p3 A-02 T1 | moved out | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_057e273a9e42 | ielts9_test3_p3 A-07 T1 | sent out | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_093b125b36f8 | ielts10_test1_p3 I-02 T6 | opt out | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_0c5f67f30e20 | ielts10_test3_p3 G-05 T1 | carried out | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_0c9f65aca03b | ielts6_test1_p1 C-01 T6 | comes down | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_10a33adcc580 | ielts17_test4_p3 D-02 T1 | go back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_13dcc4c7807d | ielts16_test2_p1 C-05 T6 | stretch back | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_1615986ad39d | ielts9_test1_p3 A-01 T6 | go back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_16986b612a87 | ielts7_test1_p3 C-11 T6 | shifted away | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_224f20cc545b | ielts12_test5_p1 B-05 T1 | spring back | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_22e3be17dbbb | ielts7_test1_p1 D-06 T6 | goes in | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_232999f9de7d | ielts18_test1_p2 F-04 T6 | comes in | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_2e7e03cd542a | ielts18_test1_p2 G-03 T1 | cycle back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_309212a1b586 | ielts15_test2_p2 B-01 T1 | bring back | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_31b4351a3afb | ielts9_test1_p3 E-32 T6 | went back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_32a2c8146cb9 | ielts13_test3_p1 B-06 T6 | stripped away | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_384e042cf87d | ielts6_test1_p1 D-09 T1 | be down | needs_review | 系表补足；动词本身可成立，保守送审可接受，不能断言单位错误（Z5） |
| gi_v02_397ebcae7ec0 | ielts16_test2_p1 C-05 T1 | stretch back | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_3afe5e16e0ce | ielts10_test1_p3 I-02 T1 | opt out | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_3c8464e0e11e | ielts17_test1_p2 B-03 T6 | converted back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_48cc446b7a93 | ielts17_test1_p2 B-03 T1 | converted back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_4b8507d120a7 | ielts8_test3_p1 A-03 T6 | roll in | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_4eadc2ff444b | ielts19_test3_p1 G-01 T1 | brought over | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_518a8e56925c | ielts12_test7_p1 G-01 T6 | spread out | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_59e5a122dbba | ielts6_test1_p3 G-40 T6 | go back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_5b0ae189651e | ielts5_test4_p2 J-42 T6 | went up | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_5e80a262136d | ielts6_test1_p1 D-09 T6 | be down | needs_review | 系表补足；动词本身可成立，保守送审可接受，不能断言单位错误（Z5） |
| gi_v02_625486c6a7c9 | ielts7_test2_p1 G-34 T6 | running up | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_6396485b7de7 | ielts9_test1_p3 A-02 T6 | moved out | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_6976a217d6d3 | ielts9_test3_p3 A-07 T6 | sent out | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_6bdf3d85b580 | ielts17_test4_p3 D-02 T6 | go back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_6d4acace142c | ielts20_test2_p3 E-20 T1 | yells back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_6e5b7a314983 | ielts8_test1_p1 H-03 T6 | beamed down | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_70da82ebcaae | ielts20_test2_p2 F-45 T1 | get back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_71aba66067a6 | ielts12_test7_p3 C-03 T1 | are up | needs_review | 系表补足；动词本身可成立，保守送审可接受，不能断言单位错误（Z5） |
| gi_v02_72894232155a | ielts10_test4_p2 G-04 T6 | got back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_75f2f2d2fa01 | ielts7_test2_p1 G-34 T1 | running up | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_7ae1e175826d | ielts19_test3_p1 G-01 T6 | brought over | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_7b09561bbe45 | ielts18_test1_p2 F-04 T1 | comes in; spread out | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_7bc5d472e548 | ielts18_test3_p3 K-06 T6 | report back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_7c50a00976e3 | ielts11_test3_p2 B-02 T6 | flies on | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_81c933164f0b | ielts10_test3_p3 G-05 T6 | carried out | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_85535e4997b7 | ielts11_test3_p2 B-02 T1 | flies on | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_85c3c7a8ebe2 | ielts15_test3_p1 F-01 T6 | moved away | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_8e46a959ca9d | ielts20_test2_p2 F-45 T6 | get back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_8f851707ff3d | ielts15_test1_p1 F-06 T6 | was over | needs_review | 系表补足；动词本身可成立，保守送审可接受，不能断言单位错误（Z5） |
| gi_v02_9841dbcc0a2d | ielts11_test2_p3 H-03 T1 | be down | needs_review | 系表补足；动词本身可成立，保守送审可接受，不能断言单位错误（Z5） |
| gi_v02_98b59b24d0e2 | ielts9_test1_p1 I-07 T1 | went back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_9c656cd6bbb5 | ielts11_test1_p2 B-02 T1 | stepped down | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_9e21e9e14b9f | ielts19_test3_p2 E-04 T6 | drained away | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_a84a0755f323 | ielts10_test3_p3 C-03 T1 | peering down | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_a9bf0f603b3b | ielts7_test1_p1 D-06 T1 | goes in | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_aafe7a36d122 | ielts9_test1_p3 E-37 T6 | went back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_ac9447ba481c | ielts20_test2_p3 E-20 T6 | yells back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_add113d901de | ielts15_test3_p1 F-01 T1 | moved away | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_af6ea5715443 | ielts6_test1_p1 C-01 T1 | comes down | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_afb4be4aa86e | ielts13_test1_p2 A-05 T1 | stay away | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_b3f97a4a3760 | ielts5_test4_p2 J-42 T1 | went up | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_b7ec2f51b5ee | ielts11_test1_p2 B-02 T6 | stepped down | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_b95a87e0494c | ielts5_test1_p3 H-33 T1 | throws away | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_bc046121ec52 | ielts11_test2_p3 H-03 T6 | be down | needs_review | 系表补足；动词本身可成立，保守送审可接受，不能断言单位错误（Z5） |
| gi_v02_c23d4525b142 | ielts12_test7_p1 G-01 T1 | spread out | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_c59559434f6b | ielts9_test1_p3 E-32 T1 | went back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_c62d5283de92 | ielts5_test3_p3 A-09 T1 | moved on | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_c75314581269 | ielts19_test1_p1 E-01 T1 | date back | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_c965b046a0f9 | ielts5_test1_p3 H-33 T6 | throws away | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_d376b043c84e | ielts15_test1_p1 F-06 T1 | was over | needs_review | 系表补足；动词本身可成立，保守送审可接受，不能断言单位错误（Z5） |
| gi_v02_d3bd85fd1512 | ielts17_test3_p3 G-04 T6 | dig down | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_d696ab498d55 | ielts7_test1_p2 E-02 T6 | shifting back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_debfd1560fe2 | ielts10_test4_p3 E-05 T6 | switched back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_e4aa893f837e | ielts18_test1_p2 G-03 T6 | cycle back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_ea784a786fe6 | ielts7_test1_p2 E-02 T1 | shifting back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_eab48f8cb495 | ielts9_test1_p3 F-39 T6 | stretching back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_f5eb226a91ec | ielts13_test3_p1 B-06 T1 | stripped away | needs_review | 短语动词/惯用搭配有粒子遗漏风险，送审合理；内容仍未扩展 |
| gi_v02_fa6be1bf43ec | ielts17_test3_p3 G-04 T1 | dig down | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_fca3160e2e90 | ielts9_test1_p1 I-07 T6 | went back | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |
| gi_v02_fdfe1ed6bc65 | ielts7_test1_p3 C-11 T1 | shifted away | needs_review | 移动/方向或恢复状态副词，需语境定粒子；保守送审可接受，非一律漏词（Z5） |

控制实测：go on a hike、carried on the backs 的on均为介词，不触发；quickly/also不触发；普通looked down the hill也未触发。反过来，was over、was down with触发，正是Z5的保守范围。小品词已标prt并进入单位时不重复降级。实际`wrote it down`若parser标prt仍可完整显示；“被宾语隔开不覆盖”只指新advmod门槛，不意味着所有这类句子都漏。

### 6.5 A8全部剑桥nested命中（3题，均needs）

| 题号 | 题型 / 来源 | 状态 | 答案或目标 | 独立判定 |
| --- | --- | --- | --- | --- |
| gi_v02_0d4f69bb426d | T2 / ielts18_test3_p3 G-06 | needs_review | the smart stay smart and the dumb get dumber | 目标合了两个有各自主语的分句；needs合理；其中仅9_3_p2 A-01为本轮新降 |
| gi_v02_8276fdbf80d2 | T2 / ielts7_test1_p3 D-15 | needs_review | the music is classical (Mozart, Beethoven, Brahms) and the teacher reads the text slowly a… | 目标合了两个有各自主语的分句；needs合理；其中仅9_3_p2 A-01为本轮新降 |
| gi_v02_6cda2311a1da | T2 / ielts9_test3_p2 A-01 | needs_review | unlike wind, the tides are predictable and the power input is constant | 目标合了两个有各自主语的分句；needs合理；其中仅9_3_p2 A-01为本轮新降 |

## 7. 剑桥随机抽查与不同角度的定向扫描

### 7.1 seed20261102，120道auto逐题表

方法：读取完整50243候选，以source_kind=reading_test且passage_id以ielts开头、status=auto_pass过滤；按T1–T6固定顺序，各池按item_id排序，使用一个`random.Random(20261102)`连续sample20。不是从360行表里抽，也未混入needs。逐题看teacher_row渲染的题干/高亮/答案/干扰项和原句。**120道均未确认新的答案、范围或题干前提错误；原句均可用于本题。** 上下文指代、原有排版差异不据此擅自改原文。

该样本与Z1–Z3六题没有交集；定向检出的问题不能伪装成随机错误率。各行“通过”只指本次所列五项人工复核，不是将auto状态当作判定。

| 序 | 题号 | 题型 / 来源 | 状态 | 答案 / 目标 | 五项人工复核 |
| --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_959bc0448b1c | T1 / ielts9_test2_p3 D-04 | auto_pass | have / found | 局部答案/范围/干扰项/题干成立；原句可用 |
| 2 | gi_v02_10ae16f31eb0 | T1 / ielts4_test1_p3 J-38 | auto_pass | scored | 局部答案/范围/干扰项/题干成立；原句可用 |
| 3 | gi_v02_620fc402aec7 | T1 / ielts9_test3_p2 D-16 | auto_pass | needs | 局部答案/范围/干扰项/题干成立；原句可用 |
| 4 | gi_v02_a5805d774fe9 | T1 / ielts14_test1_p3 I-04 | auto_pass | does / not / result | 局部答案/范围/干扰项/题干成立；原句可用 |
| 5 | gi_v02_a8cb6a815ba8 | T1 / ielts14_test2_p3 A-02 | auto_pass | helps | helps主谓及干扰项成立；it需承接上文，插入语标点不据此判原句缺陷 |
| 6 | gi_v02_282abc40cc41 | T1 / ielts18_test1_p1 C-01 | auto_pass | is | 局部答案/范围/干扰项/题干成立；原句可用 |
| 7 | gi_v02_1ec1af9f6b7f | T1 / ielts16_test1_p3 I-02 | auto_pass | envisages | 局部答案/范围/干扰项/题干成立；原句可用 |
| 8 | gi_v02_6af3afc2f8ff | T1 / ielts15_test4_p2 H-01 | auto_pass | says | 局部答案/范围/干扰项/题干成立；原句可用 |
| 9 | gi_v02_0b7f3497e234 | T1 / ielts5_test2_p2 E-19 | auto_pass | is | 局部答案/范围/干扰项/题干成立；原句可用 |
| 10 | gi_v02_cab3ca915a8d | T1 / ielts7_test1_p3 F-32 | auto_pass | is | 局部答案/范围/干扰项/题干成立；原句可用 |
| 11 | gi_v02_dfeab8cddae4 | T1 / ielts8_test3_p1 C-04 | auto_pass | is / looking | 局部答案/范围/干扰项/题干成立；原句可用 |
| 12 | gi_v02_ab43d7edaa23 | T1 / ielts13_test4_p2 F-06 | auto_pass | are / working | 局部答案/范围/干扰项/题干成立；原句可用 |
| 13 | gi_v02_3564934916e4 | T1 / ielts16_test1_p3 L-01 | auto_pass | answers | 局部答案/范围/干扰项/题干成立；原句可用 |
| 14 | gi_v02_cc82036e35a4 | T1 / ielts11_test1_p1 G-01 | auto_pass | is | 局部答案/范围/干扰项/题干成立；原句可用 |
| 15 | gi_v02_fa8452e3d442 | T1 / ielts11_test3_p1 D-06 | auto_pass | spread | 局部答案/范围/干扰项/题干成立；原句可用 |
| 16 | gi_v02_6878167af80a | T1 / ielts11_test1_p3 B-05 | auto_pass | would / employ | 局部答案/范围/干扰项/题干成立；原句可用 |
| 17 | gi_v02_87edf512ab12 | T1 / ielts11_test3_p1 B-04 | auto_pass | was | was作系动词、prized表状态读法成立；so…that结构与题干相符 |
| 18 | gi_v02_a2570bf97325 | T1 / ielts15_test3_p3 C-01 | auto_pass | compare | 局部答案/范围/干扰项/题干成立；原句可用 |
| 19 | gi_v02_7ac03992ff97 | T1 / ielts17_test2_p1 G-02 | auto_pass | spent | 局部答案/范围/干扰项/题干成立；原句可用 |
| 20 | gi_v02_3266c305657f | T1 / ielts13_test2_p3 G-02 | auto_pass | will / allow | 局部答案/范围/干扰项/题干成立；原句可用 |
| 21 | gi_v02_c53350fcf001 | T2 / ielts14_test3_p2 G-01 | auto_pass | in which we use our knowledge of ecology as a guide to target our efforts | 局部答案/范围/干扰项/题干成立；原句可用 |
| 22 | gi_v02_3e4792dd1297 | T2 / ielts13_test1_p1 A-06 | auto_pass | it made New Zealand one of the strongest national brands in the world | 局部答案/范围/干扰项/题干成立；原句可用 |
| 23 | gi_v02_e90f8698a700 | T2 / ielts20_test4_p1 G-23 | auto_pass | until she moved permanently to New Mexico in 1949 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 24 | gi_v02_b7501343675c | T2 / ielts20_test1_p2 B-03 | auto_pass | that spread the deadly fungus | 局部答案/范围/干扰项/题干成立；原句可用 |
| 25 | gi_v02_878589e4196c | T2 / ielts15_test2_p1 G-02 | auto_pass | that would not be possible using purely abstract thought | 局部答案/范围/干扰项/题干成立；原句可用 |
| 26 | gi_v02_b8de951bf7fc | T2 / ielts16_test4_p2 F-01 | auto_pass | that digital screen use may be causing a variety of troubling downstream effects on reading comprehension… | 局部答案/范围/干扰项/题干成立；原句可用 |
| 27 | gi_v02_90c82723a174 | T2 / ielts5_test2_p1 G-33 | auto_pass | that they were now, at last, no longer restricted to the wood tones and drab browns of the pre-plastic er… | 局部答案/范围/干扰项/题干成立；原句可用 |
| 28 | gi_v02_c324b643ee50 | T2 / ielts10_test1_p3 D-01 | auto_pass | under that pressure we, as a species, behave differently | 局部答案/范围/干扰项/题干成立；原句可用 |
| 29 | gi_v02_6981f6766c1c | T2 / ielts18_test3_p2 C-04 | auto_pass | Though it did not run well | 局部答案/范围/干扰项/题干成立；原句可用 |
| 30 | gi_v02_42feb7355967 | T2 / ielts9_test4_p3 E-05 | auto_pass | who make these interpretations | 局部答案/范围/干扰项/题干成立；原句可用 |
| 31 | gi_v02_b305a481b933 | T2 / ielts12_test7_p3 D-05 | auto_pass | what's going to happen next | 局部答案/范围/干扰项/题干成立；原句可用 |
| 32 | gi_v02_de712eb91358 | T2 / ielts12_test6_p2 F-07 | auto_pass | that Vilcabamba actually lies 65 kilometres away in the depths of the jungle | 局部答案/范围/干扰项/题干成立；原句可用 |
| 33 | gi_v02_a4352b5adaee | T2 / ielts20_test4_p3 D-18 | auto_pass | large numbers have been killed by farmers | 局部答案/范围/干扰项/题干成立；原句可用 |
| 34 | gi_v02_11749ebb7c02 | T2 / ielts9_test3_p3 F-33 | auto_pass | that cram maximum information into the minimum space | 局部答案/范围/干扰项/题干成立；原句可用 |
| 35 | gi_v02_d01b1f9a5d26 | T2 / ielts20_test3_p1 J-04 | auto_pass | that was used by airlines | 局部答案/范围/干扰项/题干成立；原句可用 |
| 36 | gi_v02_1a793f6557a6 | T2 / ielts19_test1_p1 J-02 | auto_pass | some will have the handle of one racket moulded onto the frame of a different racket | 局部答案/范围/干扰项/题干成立；原句可用 |
| 37 | gi_v02_2094b58e04fa | T2 / ielts8_test2_p1 D-01 | auto_pass | which guaranteed that the surface of the molten metal was perfectly flat and horizontal | 局部答案/范围/干扰项/题干成立；原句可用 |
| 38 | gi_v02_d2a36511db35 | T2 / ielts9_test4_p2 D-02 | auto_pass | that it is in such day-to-day relationships and interactions that the child's understanding of his- or he… | 局部答案/范围/干扰项/题干成立；原句可用 |
| 39 | gi_v02_16d338f9bdef | T2 / ielts10_test1_p1 E-01 | auto_pass | as groundwater has been diverted for industrial use and the wells no longer reach the water table | 局部答案/范围/干扰项/题干成立；原句可用 |
| 40 | gi_v02_ac96b5e40590 | T2 / ielts18_test4_p2 I-01 | auto_pass | that its proponents claim it to be | 局部答案/范围/干扰项/题干成立；原句可用 |
| 41 | gi_v02_02128770792c | T3 / ielts6_test2_p1 C-13 | auto_pass | as the city has become larger and wealthier → 状语从句 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 42 | gi_v02_09d586e94252 | T3 / ielts12_test8_p3 A-03 | auto_pass | which resulted in a deeper and more prolonged period of economic downturn than anyone expected → 定语从句 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 43 | gi_v02_e6eaa540145d | T3 / ielts14_test1_p3 A-01 | auto_pass | in the success of hotels → 不是从句（短语或非谓语） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 44 | gi_v02_b6197ad33aea | T3 / ielts12_test6_p1 I-02 | auto_pass | farmers can gain greater control over prices and minimise price volatility by selling directly to consume… | 局部答案/范围/干扰项/题干成立；原句可用 |
| 45 | gi_v02_243ce480dfe8 | T3 / ielts4_test3_p3 E-23 | auto_pass | on the non-verbal behavior of the participants, and about the context in general → 不是从句（短语或非谓语） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 46 | gi_v02_d8f2727655ab | T3 / ielts17_test1_p1 F-03 | auto_pass | in which steam could be condensed → 定语从句 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 47 | gi_v02_3e18289e52f5 | T3 / ielts13_test3_p3 D-04 | auto_pass | Over the course of several seasons of fieldwork → 不是从句（短语或非谓语） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 48 | gi_v02_714998a48fa4 | T3 / ielts11_test1_p1 F-01 | auto_pass | that has been developed → 定语从句 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 49 | gi_v02_fe7dc4555b2b | T3 / ielts6_test4_p1 E-24 | auto_pass | I'm not influenced by what they give me → 名词性从句 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 50 | gi_v02_334951777d8b | T3 / ielts16_test3_p1 A-03 | auto_pass | that they conquered → 定语从句 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 51 | gi_v02_94db3ad4179f | T3 / ielts6_test1_p1 B-01 | auto_pass | Inside the academies → 不是从句（短语或非谓语） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 52 | gi_v02_dc526a73066c | T3 / ielts16_test4_p1 B-04 | auto_pass | placed across the top of each shaft → 不是从句（短语或非谓语） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 53 | gi_v02_4082d6510600 | T3 / ielts14_test2_p3 G-08 | auto_pass | which glue people together → 定语从句 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 54 | gi_v02_9109d4b4c643 | T3 / ielts7_test4_p2 G-01 | auto_pass | leading up to MSC's final decision → 不是从句（短语或非谓语） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 55 | gi_v02_5176e3738ab5 | T3 / ielts5_test3_p3 E-33 | auto_pass | ever discovered → 不是从句（短语或非谓语） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 56 | gi_v02_89a2a1274e4b | T3 / ielts11_test2_p3 B-04 | auto_pass | to make simple perceptual decisions → 不是从句（短语或非谓语） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 57 | gi_v02_a38fc9fc88a8 | T3 / ielts12_test8_p3 B-02 | auto_pass | At the simplest and most practical level → 不是从句（短语或非谓语） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 58 | gi_v02_3e167c994d1a | T3 / ielts19_test3_p2 D-01 | auto_pass | such as palm oil and pulpwood → 不是从句（短语或非谓语） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 59 | gi_v02_f180518c5277 | T3 / ielts15_test3_p1 H-01 | auto_pass | during the Second World War → 不是从句（短语或非谓语） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 60 | gi_v02_0bda93cf7007 | T3 / ielts7_test2_p1 B-06 | auto_pass | about why these tall, slender buildings are so stable → 不是从句（短语或非谓语） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 61 | gi_v02_b69b1a401528 | T4 / ielts9_test1_p2 E-30 | auto_pass | if we detect a signal from an alien civilization → 条件 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 62 | gi_v02_32022784c57d | T4 / ielts6_test4_p2 F-14 | auto_pass | after the National Literacy Crusade had ended → 时间 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 63 | gi_v02_e8a0a1d51e7c | T4 / ielts18_test3_p2 F-05 | auto_pass | even though it was so heavy → 让步 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 64 | gi_v02_f4786fc2897f | T4 / ielts5_test4_p2 H-30 | auto_pass | before failure occurs → 时间 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 65 | gi_v02_79c59d79307b | T4 / ielts6_test2_p3 B-04 | auto_pass | when early humans first began to reflect on the nature of things around them → 时间 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 66 | gi_v02_74e62eeb6224 | T4 / ielts18_test3_p1 A-05 | auto_pass | If concrete is the only answer to the construction of new cities → 条件 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 67 | gi_v02_bdc38966997f | T4 / ielts7_test1_p1 D-09 | auto_pass | before weapons designers adapted it for the detection of submarines → 时间 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 68 | gi_v02_9ed4233cb9e3 | T4 / ielts6_test3_p2 B-06 | auto_pass | If participation is inconsistent with the culture → 条件 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 69 | gi_v02_28b9c5156164 | T4 / ielts16_test1_p2 D-06 | auto_pass | If someone wished to enter → 条件 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 70 | gi_v02_8e553e9d5a7b | T4 / ielts8_test4_p3 B-08 | auto_pass | if the ants are known not to sting → 条件 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 71 | gi_v02_1b52f7fdd1d5 | T4 / ielts7_test2_p1 A-05 | auto_pass | though it levelled a number of buildings in the neighbourhood → 让步 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 72 | gi_v02_4e4f880efc8f | T4 / ielts7_test4_p3 C-02 | auto_pass | even if it is quite loud → 让步 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 73 | gi_v02_a13982d8ea6e | T4 / ielts9_test1_p1 J-01 | auto_pass | Although Perkin's fame was achieved and fortune assured by his first discovery → 让步 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 74 | gi_v02_98c0a799dbf1 | T4 / ielts6_test3_p2 A-03 | auto_pass | if the job to be filled is a managerial post in a large bureaucratic organisation → 条件 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 75 | gi_v02_5dd1972e5262 | T4 / ielts18_test1_p3 B-04 | auto_pass | so that satellite operators know how much to worry about what's coming their way → 目的 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 76 | gi_v02_5cb5e07fd58b | T4 / ielts7_test2_p1 D-15 | auto_pass | because the Japanese pagoda did not have any practical use but became more of an art object → 原因 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 77 | gi_v02_02ca1e94b721 | T4 / ielts18_test1_p2 G-03 | auto_pass | so that their nutrients cycle back into the soil → 目的 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 78 | gi_v02_5d08c14a73b7 | T4 / ielts7_test4_p2 D-05 | auto_pass | until, during the 1990s, annual harvests were well in excess of 100 million, and on several occasions ove… | 局部答案/范围/干扰项/题干成立；原句可用 |
| 79 | gi_v02_6a5c8b29a7d8 | T4 / ielts9_test2_p2 C-08 | auto_pass | though he didn't survive to see either → 让步 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 80 | gi_v02_1cb7a8ad8f61 | T4 / ielts9_test4_p2 G-05 | auto_pass | unless other cues such as movement are present → 条件 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 81 | gi_v02_2f25b6fcc06a | T5 / ielts16_test2_p2 C-06 | auto_pass | we | 局部答案/范围/干扰项/题干成立；原句可用 |
| 82 | gi_v02_4c8cf11febda | T5 / ielts17_test3_p2 B-01 | auto_pass | Many farmers | 局部答案/范围/干扰项/题干成立；原句可用 |
| 83 | gi_v02_cf0284546665 | T5 / ielts6_test1_p3 E-29 | auto_pass | Obesity, heart disease and diabetes | 局部答案/范围/干扰项/题干成立；原句可用 |
| 84 | gi_v02_ebeb96100a0c | T5 / ielts18_test2_p3 G-02 | auto_pass | the true originality of Leonardo's vision | 局部答案/范围/干扰项/题干成立；原句可用 |
| 85 | gi_v02_2ad8d901175b | T5 / ielts10_test4_p1 B-02 | auto_pass | Some recent wildfires | 局部答案/范围/干扰项/题干成立；原句可用 |
| 86 | gi_v02_dc8b80d16edb | T5 / ielts16_test3_p1 G-02 | auto_pass | Navigation in ancient Rome | 局部答案/范围/干扰项/题干成立；原句可用 |
| 87 | gi_v02_4b2792febd16 | T5 / ielts16_test1_p2 F-01 | auto_pass | all of the precautions and intricate design of the underground network | 局部答案/范围/干扰项/题干成立；原句可用 |
| 88 | gi_v02_83b6f82994bb | T5 / ielts13_test4_p3 B-01 | auto_pass | It | 局部答案/范围/干扰项/题干成立；原句可用 |
| 89 | gi_v02_8e99f24e3314 | T5 / ielts12_test5_p1 B-04 | auto_pass | The cells | 局部答案/范围/干扰项/题干成立；原句可用 |
| 90 | gi_v02_8fa63e68e805 | T5 / ielts13_test4_p2 G-06 | auto_pass | that | 局部答案/范围/干扰项/题干成立；原句可用 |
| 91 | gi_v02_8e897ebbc2fa | T5 / ielts16_test3_p3 H-04 | auto_pass | Cambridge | 局部答案/范围/干扰项/题干成立；原句可用 |
| 92 | gi_v02_122c085e5bc3 | T5 / ielts20_test4_p1 B-06 | auto_pass | She | 局部答案/范围/干扰项/题干成立；原句可用 |
| 93 | gi_v02_1ae510057272 | T5 / ielts14_test3_p1 H-03 | auto_pass | Low achievers | 局部答案/范围/干扰项/题干成立；原句可用 |
| 94 | gi_v02_1eac84ca35ed | T5 / ielts8_test4_p1 A-01 | auto_pass | Japan | 局部答案/范围/干扰项/题干成立；原句可用 |
| 95 | gi_v02_b02a7b789685 | T5 / ielts4_test3_p2 D-06 | auto_pass | It | 局部答案/范围/干扰项/题干成立；原句可用 |
| 96 | gi_v02_28c9db4d363f | T5 / ielts13_test4_p2 G-04 | auto_pass | Chasek and her colleagues | 局部答案/范围/干扰项/题干成立；原句可用 |
| 97 | gi_v02_f0fbdc970ae3 | T5 / ielts13_test3_p2 D-01 | auto_pass | Scientists from the University of Washington and the University of Connecticut | 局部答案/范围/干扰项/题干成立；原句可用 |
| 98 | gi_v02_411c027255c7 | T5 / ielts4_test2_p1 A-02 | auto_pass | Most of its speakers | 局部答案/范围/干扰项/题干成立；原句可用 |
| 99 | gi_v02_3517c180b7ca | T5 / ielts10_test4_p3 E-03 | auto_pass | Rudolf Raff and colleagues at Indiana University in the USA | 局部答案/范围/干扰项/题干成立；原句可用 |
| 100 | gi_v02_32dd0acad5b8 | T5 / ielts4_test3_p1 M-13 | auto_pass | the rates | 完整主语正确；原有句末排版不构成本题答案错误 |
| 101 | gi_v02_a29565ea76f9 | T6 / ielts19_test3_p3 E-01 | auto_pass | need → 主句谓语 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 102 | gi_v02_5d04a042ba27 | T6 / ielts5_test3_p3 F-37 | auto_pass | exacerbated → 非谓语（不定式、分词、动名词） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 103 | gi_v02_4effb00fe71c | T6 / ielts4_test2_p2 E-21 | auto_pass | offered → 主句谓语 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 104 | gi_v02_d4bb7a41f5d8 | T6 / ielts7_test3_p3 D-39 | auto_pass | called → 非谓语（不定式、分词、动名词） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 105 | gi_v02_b959e55dab31 | T6 / ielts18_test4_p3 H-01 | auto_pass | am → 主句谓语 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 106 | gi_v02_175508dcf1fb | T6 / ielts17_test3_p2 G-01 | auto_pass | is / regulated → 主句谓语 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 107 | gi_v02_b50cc8e4138f | T6 / ielts17_test3_p2 C-02 | auto_pass | to establish → 非谓语（不定式、分词、动名词） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 108 | gi_v02_a16f7286493f | T6 / ielts11_test2_p2 C-05 | auto_pass | To feed → 非谓语（不定式、分词、动名词） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 109 | gi_v02_40ebf6a9d933 | T6 / ielts9_test4_p1 E-02 | auto_pass | joined → 主句谓语 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 110 | gi_v02_8ff01183b287 | T6 / ielts9_test2_p3 C-09 | auto_pass | is not → 主句谓语 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 111 | gi_v02_c7f453060652 | T6 / ielts10_test2_p3 C-03 | auto_pass | allow → 从句里的谓语 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 112 | gi_v02_ff6103690d95 | T6 / ielts11_test2_p3 C-03 | auto_pass | were / seeing → 从句里的谓语 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 113 | gi_v02_8bae22b288cb | T6 / ielts18_test2_p1 D-03 | auto_pass | have → 主句谓语 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 114 | gi_v02_e28e4c7e6eb1 | T6 / ielts10_test3_p3 B-01 | auto_pass | used → 从句里的谓语 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 115 | gi_v02_d0790cffa376 | T6 / ielts10_test2_p3 H-01 | auto_pass | were not / created → 从句里的谓语 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 116 | gi_v02_a9dc751b51b6 | T6 / ielts7_test4_p1 F-05 | auto_pass | looks → 主句谓语 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 117 | gi_v02_d02dfff8b660 | T6 / ielts10_test2_p1 D-14 | auto_pass | left → 非谓语（不定式、分词、动名词） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 118 | gi_v02_e988295d03fe | T6 / ielts6_test1_p1 E-01 | auto_pass | is → 主句谓语 | 局部答案/范围/干扰项/题干成立；原句可用 |
| 119 | gi_v02_d352d9b8c29f | T6 / ielts10_test1_p3 D-03 | auto_pass | to be lost → 非谓语（不定式、分词、动名词） | 局部答案/范围/干扰项/题干成立；原句可用 |
| 120 | gi_v02_dd2fc95b8134 | T6 / ielts9_test3_p2 F-24 | auto_pass | is → 主句谓语 | 局部答案/范围/干扰项/题干成立；原句可用 |

### 7.2 新角度：并列助动词共享/省略

对全部剑桥auto T6，选机器判非谓语、中心dep=conj，沿conj链向前找到有限中心/aux的题；共18个。不是复用X1–X3的字符边界、粒子规则，也不是只看本轮改动句。逐题读语境，确认Z2两题；其余16个是结果分词、定语等正常非谓语，说明不能用这个粗筛直接批量改答案。

| 题号 | 题型 / 来源 | 状态 | 答案或目标 | 独立判定 |
| --- | --- | --- | --- | --- |
| gi_v02_180f5b7bfbf3 | T6 / ielts10_test4_p3 I-04 | auto_pass | reversing | 结果/伴随等非谓语分词成立；不能因conj标签自动改判谓语 |
| gi_v02_bb437aa4b900 | T6 / ielts11_test1_p1 E-02 | auto_pass | reducing | 结果/伴随等非谓语分词成立；不能因conj标签自动改判谓语 |
| gi_v02_173f4b836393 | T6 / ielts12_test6_p2 B-02 | auto_pass | cutting | 结果/伴随等非谓语分词成立；不能因conj标签自动改判谓语 |
| gi_v02_c5f8bfba90e2 | T6 / ielts12_test6_p3 A-03 | auto_pass | identifying | 结果/伴随等非谓语分词成立；不能因conj标签自动改判谓语 |
| gi_v02_1ad93e498bd5 | T6 / ielts12_test8_p1 C-03 | auto_pass | adding | 结果/伴随等非谓语分词成立；不能因conj标签自动改判谓语 |
| gi_v02_e308d4a8777f | T6 / ielts13_test2_p3 D-05 | auto_pass | infusing | 结果/伴随等非谓语分词成立；不能因conj标签自动改判谓语 |
| gi_v02_526d2a4edcd0 | T6 / ielts14_test4_p1 E-02 | auto_pass | showing | 结果/伴随等非谓语分词成立；不能因conj标签自动改判谓语 |
| gi_v02_86b996fd1f46 | T6 / ielts15_test4_p1 F-05 | auto_pass | roasted | 共享/省略can be或must be，非谓语答案错误（Z2） |
| gi_v02_5bb62dffbbf7 | T6 / ielts15_test4_p3 G-03 | auto_pass | to reward | to reward是不定式，与expect后的并列补足相容 |
| gi_v02_5f825d2822fa | T6 / ielts16_test1_p1 C-03 | auto_pass | depending | 结果/伴随等非谓语分词成立；不能因conj标签自动改判谓语 |
| gi_v02_cffbc50169cf | T6 / ielts17_test1_p2 D-03 | auto_pass | designed | designed可作后置补充描述；本次不据conj强判共享are，保留非谓语读法 |
| gi_v02_42b61e4eac46 | T6 / ielts17_test1_p3 A-03 | auto_pass | accepting | 结果/伴随等非谓语分词成立；不能因conj标签自动改判谓语 |
| gi_v02_dfd8b52356bb | T6 / ielts17_test4_p1 C-01 | auto_pass | making | 结果/伴随等非谓语分词成立；不能因conj标签自动改判谓语 |
| gi_v02_330fff562bff | T6 / ielts17_test4_p3 E-07 | auto_pass | updated | 共享/省略can be或must be，非谓语答案错误（Z2） |
| gi_v02_b6a8303441af | T6 / ielts19_test2_p1 E-03 | auto_pass | enabling | 结果/伴随等非谓语分词成立；不能因conj标签自动改判谓语 |
| gi_v02_7ebb46e41faa | T6 / ielts4_test1_p1 B-02 | auto_pass | making | 结果/伴随等非谓语分词成立；不能因conj标签自动改判谓语 |
| gi_v02_63d9298d36e1 | T6 / ielts8_test1_p1 G-03 | auto_pass | allowing | 结果/伴随等非谓语分词成立；不能因conj标签自动改判谓语 |
| gi_v02_32dd0bb613c1 | T6 / ielts8_test3_p2 A-04 | auto_pass | derived | derived修饰attributes，后置分词定语正确 |

### 7.3 额外核对范围及边界

RP交叉信号筛全量auto T1/T6显示动词：其直接子节点tag=RP却dep不是prt且未显示，共5题。3个live up to为Z1；另`gi_v02_73e53f470ca2` hold joy back属于已披露的被宾语隔开范围，不能用“紧挨”规则要求覆盖；`gi_v02_d60aedeca103` had its brakes on中on可作宾补，不将所有RP自动并入had。

恢复40题时检查provided that，确认Z3；补看`gi_v02_31a694497b01`的given that，它有固定引导表达与分词来源的分析差异，建议统一教学口径，本次不把这处争议当成已证实新错误，也不把广泛词表预筛188个动词/介词同形命中算成188个错误。上述定向筛选均是召回线索，人工结论与机器命中数分开。

## 8. 全池与状态统计（基准a3fbcbb）

| 指标 | 独立实测 |
| --- | --- |
| 总候选 / 换题号 | 50243；移除4、新增4，均Y1剑桥T6 |
| 共同ID auto→needs | 剑桥104：T1 46、T2 1、T5 1、T6 56；机经29 |
| 共同ID needs→auto | 剑桥38 T1；机经14 |
| 非状态字段变化 | prompt_zh 970（剑桥631）；distractors 61（剑桥46）；其余共同ID字段0变化 |
| auto总数 / 剑桥 / 机经 | 40341 / 27860 / 12481 |
| particle_outside_unit 全量 | 剑桥104 / 机经37 |
| nested_coordination 全量 | 剑桥3 / 机经2 |
| coordinate_cue_missing 全量 | 剑桥158 / 机经98 |

| 模板 | auto_pass | needs_review | rejected（未出题诊断，不与候选相加） |
| --- | --- | --- | --- |
| T1 main_verb_tap | 5836 | 543 | 6367 |
| T2 clause_boundary | 4678 | 2584 | 2694 |
| T3 clause_type_classify | 11401 | 3486 | 1331 |
| T4 adverbial_relation | 399 | 657 | 2561 |
| T5 subject_span | 5365 | 819 | 6562 |
| T6 finite_or_not | 12662 | 1813 | 6549 |

统计按题号去重。第十二轮中间池独立用891b9d2模块和不变的数据/缓存重生，复现40个剑桥T1恢复；第十三轮又降其中2个，因此与a3比较只升38。共同ID数量不包括4对换题号；不能把新增的3auto、1needs混进共同题号升降。

## 9. 双跑环境、SHA-256及xlsx

| 项 | 本机实测 |
| --- | --- |
| spacy | 3.8.16 |
| model_name | en_core_web_trf |
| model_version | 3.8.0 |
| device | CPU |
| python | 3.13.3 |
| torch | 2.14.1 |
| openpyxl | 3.1.5 |
| seed | 20261018 |
| reading_study_sha256 | 55b808e1a69cfb7fc06670a6ac3bb36d2861923f229183875ed309ea3a747f37 |
| grammar_graph_sha256 | c7b35ddb68db7601ccd01e38a210ad3dd772ff507302190f68a351e408b85a29 |

运行于Mac arm64、Python3.13.3，torch只用CPU；独立完整35e37c5快照内使用指定`.venv-grammar-tools`生成两次、seed20261018。复用此前独立验证且环境完全相同的全库解析缓存；本轮reading_study字节未改。每次都完整重新收集候选、复核、抽表、写4份文件；没有复制提交交付文件冒充运行结果，也没有在任务树覆写它们。本轮要求两次生成，未要求重新做一次无缓存模型推理；此缓存使用在此明确披露。

| 文件 | 第一次SHA-256 | 第二次SHA-256 | 对提交 |
| --- | --- | --- | --- |
| generation_report_v0_2.json | 3f96449c72dba5cd526f8fa5693ad790c258f470635a73c6af8e9f1a0a34c200 | 3f96449c72dba5cd526f8fa5693ad790c258f470635a73c6af8e9f1a0a34c200 | 仅Python版本一行不同 |
| generation_report_v0_2.md | 4e660f38662b7ff5574a19f006583eab8792b3a91d70a6d4afd64b5832a7afab | 4e660f38662b7ff5574a19f006583eab8792b3a91d70a6d4afd64b5832a7afab | 仅Python版本一行不同 |
| review_batch_v0_2.jsonl | 4853a1a58089c79eb6ce097f13320c5b76f87529372caabb2a5359fc95049f7e | 4853a1a58089c79eb6ce097f13320c5b76f87529372caabb2a5359fc95049f7e | 字节一致 |
| review_batch_v0_2.xlsx | 9aff2bae36cee5b447101eb57746526c74b219ddb9592f7aba767ac127d0d6de | 9aff2bae36cee5b447101eb57746526c74b219ddb9592f7aba767ac127d0d6de | 字节一致 |

提交报告JSON为`0b738bbe23eaef668a130ea31a790571abd4fdb99afe6c1dfb078cb1ae25eccb`、MD为`c0464918f5d4fcd05bf31f07851d692d43eb830c85c57eac9893b8c805da4a35`；本机版本3.13.3对提交3.11.15，分别只差一行；JSONL/XLSX均吻合提示哈希。

78个回归（13句×6）逐对象相同。7项整句过滤：tagged_fragment30、clause_attached_to_conjunction2、glued_sentence_boundary0、multi_sentence_unit1、suspected_split_word0、leading_stray_punctuation0、control_character0，预期全部吻合。

xlsx检查7个工作表、6种题型各60个数据行；H2:H61的判定下拉为“正确 / 答案错 / 题目有歧义 / 句子不适合出题”。教师可见单元格没有auto_pass/needs_review/内部原因。将360行逐行与teacher_row生成值比较全部一致；动词parts高亮仍完整合并为既定格式。剑桥224行=196auto+28needs，机经136行=104auto+32needs。

**相对a3fbcbb保留28个题号，按(工作表,行号)同位置0行。** 文档“10题号/1同位置”比较的是第十二轮，不是本次要求的a3，不能混用。重抽后的老师判定若需要迁移应按题号匹配；本次未操作老师文件或决定盲审范围。

## 10. 测试、数据、模拟导入与实际命令

| 检查 | 实际结果 |
| --- | --- |
| 4个专项模块 | 137运行、137通过 |
| 全新Flask-only的ci.yml13模块 | 205运行、204通过、1按设计skip（无重依赖） |
| Node旧拼写队列 | exit0 |
| tests.test_reading_study | 22运行、22通过 |
| validate_reading_study.py / text_fixes --check | 均0错误 |
| raw内存重建 | 171篇content（含summary）及groups逐对象一致，不下载图片 |
| 图谱review渲染 | 与提交GRAMMAR_GRAPH_V0_REVIEW.md逐字节相同 |
| 4个变更Python Ruff | check与format --check均exit0 |
| 临时SQLite | 完整676569c先created317；当前updated236/skipped81/failed0，最终317行 |

### 10.1 新测试在修改前的结果

分别以a3fbcbb、891b9d2为基准，在隔离子进程加载旧checks/templates，用当前新增测试的具体方法运行；没有修改仓库文件。接口错误不能算断言证明。第十二轮4失败/2控制通过与自查一致；第十三轮实际5失败/2接口错误/2控制通过，Z4已说明。

| 轮次 / 旧基准 | 测试 | 结果 |
| --- | --- | --- |
| round12 / a3fbcbb | CoordinatePromptTests.test_clause_without_a_conjunction_goes_to_review | 断言失败 |
| round12 / a3fbcbb | CoordinatePromptTests.test_other_clause_prompts_unchanged | 控制通过 |
| round12 / a3fbcbb | CoordinatePromptTests.test_prompt_names_the_conjunction | 断言失败 |
| round12 / a3fbcbb | CoordinatePromptTests.test_repeated_conjunction_gets_its_position | 断言失败 |
| round12 / a3fbcbb | HyphenatedWordTests.test_compound_adjective_is_no_distractor | 断言失败 |
| round12 / a3fbcbb | HyphenatedWordTests.test_hyphenated_verb_in_coordination_stays_a_split_word | 控制通过 |
| round13 / 891b9d2 | CorrelativeNotTests.test_not_before_because | 断言失败 |
| round13 / 891b9d2 | CorrelativeNotTests.test_ordinary_negation_stays | 控制通过 |
| round13 / 891b9d2 | CorrelativeNotTests.test_whether_or_not | 断言失败 |
| round13 / 891b9d2 | ForClauseTests.test_because_clause_unaffected | 控制通过 |
| round13 / 891b9d2 | ForClauseTests.test_for_clause_is_no_subordinate_predicate | 断言失败 |
| round13 / 891b9d2 | LooseParticleTests.test_particle_in_the_unit_and_plain_adverbs_unaffected | 接口错误 |
| round13 / 891b9d2 | LooseParticleTests.test_particle_parsed_as_adverb_goes_to_review | 断言失败 |
| round13 / 891b9d2 | NestedCoordinationTests.test_single_clause_target_unaffected | 接口错误 |
| round13 / 891b9d2 | NestedCoordinationTests.test_target_joining_two_clauses_goes_to_review | 断言失败 |

### 10.2 实际命令与探针入口

下列绝对路径均为本机真实运行位置；临时脚本/日志不在仓库中。另一台电脑可从固定Git提交建立同样快照，按所列方法复现。生产连接从未使用；SQLite连接被断言为本机审计目录。

```sh
# A. 用户授权的清理、快进与范围核验（任务树）
cd /Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker
git status --short --branch
git log -5 --oneline
git restore docs/CODEX_HANDOFF.md docs/WORKLOG.md
# 仅删除已核对为未跟踪、过时的 ROUND11_12_CODEX_REVIEW.md
git fetch origin claude/word-memorization-system-eval-55v2y5
git merge --ff-only 35e37c5f6157430b8294fb877de46f621daee887
git diff --stat 1558465..35e37c5
git diff --name-only 1558465..35e37c5
```

以下为脚本实际执行的核心命令；G指任务树`.venv-grammar-tools/bin/python`，P指`/Users/zhouxin/Desktop/studytracker/.venv/bin/python`，O指仓库外审计目录，F指`O/flask-only/bin/python`。

```sh
# B. 两次完整生成；cwd是O/source，不是任务树
G scripts/generate_grammar_candidates.py --seed 20261018
G scripts/generate_grammar_candidates.py --seed 20261018
# 实际驱动及所有日志
G O/generate.py
# C. 池、SHA、回归、xlsx及种子抽样
G O/audit_runtime.py
# D. 范围、171篇内存重建、图谱、main完整快照Git blob验证
G O/audit_data.py
# D内部，在O/source运行
G scripts/render_grammar_graph_review.py
# E. 第十二轮中间池、题号集及逐题抽取（仓库外隔离加载891b9d2模块）
G O/round12_pool.py
G O/extract_checks.py
# F. 新测试逐个跑旧代码，保留完整traceback
G O/negative_tests.py
# G. 正向测试（cwd任务树）
G -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary tests.test_grammar_graph_draft -v
P -m unittest tests.test_reading_study -v
G scripts/validate_reading_study.py
G scripts/reading_jijing_text_fixes.py --check
/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tests/test_dictation_spell_queue.js
P -m ruff check --config 'extend-exclude=[]' scripts/grammar_items/checks.py scripts/grammar_items/reporting.py scripts/grammar_items/templates.py tests/test_grammar_item_candidates.py
P -m ruff format --check --config 'extend-exclude=[]' scripts/grammar_items/checks.py scripts/grammar_items/reporting.py scripts/grammar_items/templates.py tests/test_grammar_item_candidates.py
G -m venv O/flask-only
F -m pip install --cert /etc/ssl/cert.pem Flask
F -m pip list
F -m unittest tests.test_miniprogram_guest_access tests.test_miniprogram_dictation_grouping tests.test_inventory_toefl_materials tests.test_organize_toefl_materials tests.test_extract_toefl_answer_keys tests.test_map_toefl_answers_to_practice_docs tests.test_import_toefl_official_reading tests.test_reading_vocab_grading tests.test_stats_utils tests.test_grammar_graph_draft tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary -v
# H. 两个完整快照，各自代码/static/data独立import，连接同一个临时SQLite
P O/import_snapshot.py O/main main
P O/import_snapshot.py O/source round13
# I. 补充代码控制、范围定位及全池探针
G O/final_probes.py
G O/controls.py
G O/coord_scan.py
```

`G/P/O/F`是报告路径缩写，不是声称shell可以直接将G当变量执行。`audit_data.py`的build测试只将图片定位钩子替换为同样的相对路径计算，未下载图片；正文/题目修订走原build函数。生成及图谱在完整快照写入，任务树内被审文件保持字节不变。

Y1全库检查另运行标准库/ParseCache脚本：逐个ielts JSON句子，遍历neg/not，对correlative_not结果保存9来源。Z2探针为§7.2描述的全池谓语协调筛选。Z1复现用tag=RP与dep=prt交叉检查显示范围；新问题表给出全部6题ID和准确语境，跨电脑无需依赖本机脚本即可定位。

### 10.3 环境与执行差异

- 没有缺失或无法完成的必查项；全部9项已执行。按只审不改要求，生成写到仓库外完整快照，任务树被审文件未覆盖；复用相同环境缓存的情况已披露。
- `origin/main`本机共享引用在本次期间已见`ee94abb30d56b3c9623c519f75c1ffa9679c65b5`，不同于提示中的676569c。按用户明确要求固定**676569c完整快照**模拟导入，没有合并或切到新main，因此236/81/0可直接与指定基线比较。
- 辅助脚本final_probes.py最初一次写到了任务树根目录，尚未执行即发现路径错误，立即移动到仓库外审计目录；未修改任何被审文件、未留在Git差异或提交中。此短暂新建文件超出所列三文档写入路径，在此如实披露。
- 统计差异为R13负测5/2/2（不是5/1/3）；is子串误重复；相对a3抽查表为28/0。它们没有被换口径掩盖。

## 11. GitHub CI、交接与下一步

被审35e37c5的[CI 40511565346](https://github.com/KB77GG/studytracker/actions/runs/40511565346)已核：test成功，lint advisory失败、format因前一步失败跳过，整体success。审核文档提交后另核精确head的CI，并分别记录test与lint；不能拿基线CI冒充审核提交CI。

下一步：实现方处理Z1–Z3并回归全部6题、共享助动词与词汇化连词的正常控制；更正Z4记录，按Z5/Z6收窄或清楚解释启发式边界。A8本次限定范围验收通过；老师盲审范围及后续上线仍待用户决定。本轮未推main、未开PR、未部署后端、未上传/提审/发布小程序、未操作生产数据库或服务器、未调用大模型API。

### 11.1 审核正文提交后的CI实测

审核正文与交接已commit/push `0c5ede3e4029ed0b08ae9eaddb36a0bbf020879a`，仅3份授权文档。[CI 40517825017](https://github.com/KB77GG/studytracker/actions/runs/40517825017)的head与此SHA一致、运行completed/success：测试日志205项运行、1项跳过，Node步骤success；lint advisory失败，**112条Python诊断与被审35e37c5的CI逐条相同**，format因前一步失败跳过。不是新增lint回归。

实际核对命令：`gh run view 40517825017 --json status,conclusion,headSha,jobs`、`gh run view 40517825017 --log`，与基线40511565346同样命令对照；比较去掉时间戳后的路径、行列、规则码和消息。此CI补记作为第二个普通文档提交推同一分支、无skip-ci；末次精确SHA与CI结果在最终回复报告，Git历史和Actions均可独立取得。任务树仅本轮三文档有变化，未部署。
