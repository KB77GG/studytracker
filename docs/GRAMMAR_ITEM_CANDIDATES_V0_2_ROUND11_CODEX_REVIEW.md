# 语法候选题 v0.2 第十一轮独立复审（Codex）

审核日期：2026-10-27（Asia/Shanghai）。**结论：不通过，以剑桥题为准。X1–X4 点名修复全部关闭；新确认 0 阻断、3 应修（Y1–Y3）、1 建议（Y4）。** 三项应修涉及 35 道不同的剑桥自动通过题、23 个来源句，全部在第十轮已存在，非第十一轮新引入。A8 单独评估，不重复计入问题数量。

固定审查 `525fcb46d71aa636e5c378b8c17d79fc75df27e3..a3fbcbb1ade29c9f39484beaa5eeab761f78afe3`。任务树 `/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker`，分支 `codex/grammar-item-candidates`。起始干净；先读入口、交接最新两节和工作日志，再 fetch/ff 到指定 a3fbcbb。只新增本报告、更新 CODEX_HANDOFF 和 WORKLOG；未修改被审代码、数据、原文、标注和交付文件，未合并 main、部署、开 PR、操作生产或调用大模型 API。

区分四件事：选中的动词身份/局部答案是否成立，显示范围是否完整，题干是否有唯一答案，原句是否适合教学。待复核题不算进自动题正确率；机经单列暂缓。样本及定向检查不能证明其余自动池全部正确。

## 1. X1–X4 关闭情况

| 编号 | 结论 | 独立依据与边界 |
| --- | --- | --- |
| X1 | 点名关闭 | 13 道均 needs_review；独立扫描全量 auto 显示边界，直连字符词内断点 0。真正的连字符动词答案尚未合并，本轮通过降级处理。 |
| X2 | 点名关闭 | back-up/check-out 两道均 needs；纯连字符干扰项去掉剑桥 3、机经 2。不是把词性错误的干扰项修成正确内容。 |
| X3 | 关闭 | J-33 保留 94%；J-40 保留 53% 及闭合破折号。8 道答案、8 个换题号及 4 道共同 ID 升级逐题复核；H-26 的 T2 仍有既有 A8。 |
| X4 | 关闭 | 全部并列连词排除、年龄分支仅 when；替换回旧两函数的全池反事实与当前 50,243 道完全相同。新测试确认 and 被错标 mark 时不再误判。 |

## 2. 十一项检查结果

| 项 | 结果 | 实际证据/命令入口 |
| --- | --- | --- |
| 1 | 通过 | 12 文件、864 增/451 删；保护路径零变化，reading_study 零变化。决策函数不读取三个 ID。命令 A、D。 |
| 2 | 点名验收通过 | 15 道全 needs；额外 41 T1 均应降级，40 道干扰项的词性描述有 Y4 小误差。51 道相关剑桥主句 T6 中 46 道逐字段不变，另 5 道仅因自己的词片段变化；见第4节。命令 C、F。 |
| 3 | 通过，A8 另列 | 两题修复及百分号副作用逐题见第5节。全部剑桥 auto 的 %/‰/°/货币符号截断探针未发现实际遗漏。命令 C、F。 |
| 4 | 通过 | X4 反事实全池 0 变化；9 项新测试含两个 X4 正反例。命令 E。 |
| 5 | 通过 | FIXES 第十轮已写清 W1 的两项接口错误为缺 Reason 常量；与上轮留存负测 traceback 相符。 |
| 6 | 待用户决定，不分级 | 345 题/345 句；248 and、93 but、4 or，77 句同一连词字面出现多次；不建议只写一个连词就批量放行。见第6节。 |
| 7 | 不通过 | seed20261101，120 道全为 auto：118 道本次未见内容问题、1 道 Y1 高亮错、1 道既有 A8；原句均可用。定向检查另确认 Y2/Y3，见第7节。命令 F。 |
| 8 | 统计全部复现 | 50,243；8 对换 ID；共同 ID 剑桥 56 降/3 升、机经 30 降/1 升。auto 40,423，其中剑桥 27,927；字段和三种原因口径见第8节。命令 C。 |
| 9 | 双跑及提交一致；提示哈希有一位笔误 | 4 份两次生成字节相同；JSONL/XLSX 与提交相同，两报告只有 Python 版本一行不同。提示 JSONL SHA 的 …986491f… 实际为 …986490f…；其余提交哈希相符。78 回归、7 过滤不变；7表/6×60/四项下拉/盲审通过。命令 B、C、D。 |
| 10 | 通过 | 专项122；Flask-only190运行/189通过/1按设计跳过；Node、reading22、validator0、--check0、raw171、图谱全等、5个Python Ruff均通过。旧代码负测6断言失败/2接口错误/1控制通过。命令 D、E、G。 |
| 11 | 通过 | 完整main676569c快照2853个tracked文件核对Git blob后，先导317篇，再导a3：updated236/skipped81/failed0。仅本机临时SQLite。命令 H。 |

## 3. 剑桥问题清单

### Y1 — 应修：把关联结构中的 not 误当作动词否定成分，7 道 auto

位置：`scripts/grammar_items/templates.py:195` 的 `verb_unit()`、`:410` 的干扰项构造及 `:768` 的 T6。直接收下解析器标为 `neg` 的子节点，不能辨别否定的作用域。`whether or not` 表示两个相反的可能性；这里的 not 不是把后面的动词改成否定谓语。`not just because it came first` 否定的是原因的唯一性，也不是“没有先出现”。本库 11_4_p3 B-01 的难点已经明确说明这一点。[Cambridge 对 whether…or not 的解释](https://dictionary.cambridge.org/grammar/british-grammar/whether?q=Whether)支持两种可能性的分析。

复现：按下表 ID 读取 `target.parts` 或 `distractors[*].parts` 并用 `teacher_row()` 渲染。例如 `whether or 【not】 they 【are carrying】`、`【not】 just because it 【came】 first`；七题均 auto，且与 8a0660b 对应题逐字段相同。

建议：加通用的关联结构/否定作用域复核，区分 whether-or-not、not 修饰 because 等引导结构，与 `did not come` 的普通谓语否定。无法可靠归属时只降级涉及该单位的题；T1 干扰项问题不要连带降完整主句 T6。不要全删 not，也不要只按 neg 依存标签决定。新增实际例和正常否定、not necessarily、whether…or not 后置等控制例。

| 题号 | 题型 | 来源 | 状态 | 独立判定 |
| --- | --- | --- | --- | --- |
| gi_v02_6ce16124dbb2 | T1 | ielts11_test1_p2 E-03 | auto_pass | 主答案 weigh 对；干扰项应是 are carrying，混入 not |
| gi_v02_a61a5b99135c | T6 | ielts11_test1_p2 E-03 | auto_pass | 从句谓语身份对；高亮应 are carrying，混入 not |
| gi_v02_3002b418088f | T1 | ielts11_test2_p1 E-05 | auto_pass | 主答案 was not 对；干扰项 not to salvage 把 or not 的省略否定混入 |
| gi_v02_ccbce5a7be7b | T1 | ielts14_test2_p3 H-04 | auto_pass | 主答案 shows 对；干扰项 not…work 混入 whether or not |
| gi_v02_35474f09ec89 | T6 | ielts5_test3_p3 E-35 | auto_pass | 从句谓语身份对；not…lives 混入 whether or not |
| gi_v02_044d1a9f8a14 | T6 | ielts7_test1_p1 C-08 | auto_pass | 从句谓语身份对；not…is 混入 whether or not |
| gi_v02_fe9aead717a1 | T6 | ielts11_test4_p3 B-01 | auto_pass | came 的身份对；not 修饰 because 原因，不能显示成 not…came |

### Y2 — 应修：for 分句的并列身份未传到 T1/T5/T6，6 道 auto

位置：`templates.py:520` 已明确把 because 意义的 for 当并列；但 `finite_targets():741` / `finite_or_not():768` 仍仅凭原 role、有限性和 advcl/relcl 给“从句里的谓语”。`main_verb():472` / 主语题只靠标注和 `independent_clauses()` 的冒号分号检查，在 D-04 留下唯一主句/主语题。

项目已采用 for 为并列连词的教学口径；这也符合 [UW–Madison 的 coordinating conjunctions 说明](https://writing.wisc.edu/handbook/grammarandstyle/coordconj/)。同一来源 T2/T3 因 `clause_type_mismatch` 待复核，不能在 T6 又把该 for 分句断言为从属从句。引语夹 says 的 C-04 至少也须复核引语层级，不能凭 advcl 直接批准该答案。D-04 两个独立分句各有谓语，T1/T5 的唯一性不成立。

复现：下表六题与其同句的 T2/T3 对照。四个来源的 for 都接有限、有自己主语的分句，分别为 it identifies / they turn / there were / turtles lay；不是 for + 名词或 for + to-infinitive。

建议：让各题型共享经语法复核后的并列/从属证据；对 for 的此用法降相关 T6，对全句唯一性受影响的 T1/T5 降级。不要把任何 T3 待审原因一律复制给 T6：本轮另 50 道类型/依存不符的 T6，动词仍确属从句（relative 与 adverbial 的分歧不改变这个答案）。T6 主句谓语身份本身正确的仍可保留。

| 题号 | 题型 | 来源 | 状态 | 独立判定 |
| --- | --- | --- | --- | --- |
| gi_v02_f7cd971488b0 | T6 | ielts10_test3_p3 C-04 | auto_pass | for it identifies 为引语内并列解释，至少须复核，不能自动断言从属谓语 |
| gi_v02_f32918997270 | T6 | ielts10_test3_p3 E-03 | auto_pass | for they turn…为并列解释，不是状语从属谓语 |
| gi_v02_d4fdc39f0b39 | T1 | ielts8_test2_p2 D-04 | auto_pass | was not 局部对；were 所在的第二独立分句使唯一主句谓语前提不成立 |
| gi_v02_759fc82d90f1 | T5 | ielts8_test2_p2 D-04 | auto_pass | It 是第一分句主语；全句另有存在分句，不宜问唯一完整主语 |
| gi_v02_967f99c9b5a8 | T6 | ielts8_test2_p2 D-04 | auto_pass | were 在 for 引出的独立分句，不是从属从句谓语 |
| gi_v02_9350e99ac9fb | T6 | ielts9_test1_p3 B-13 | auto_pass | for turtles lay…为并列解释，不是状语从属谓语 |

### Y3 — 应修：真实短语动词的粒子被标 advmod 后漏出单位，22 道 auto

位置：`templates.py:195`。本轮修复了词内连字符边界，但单位仍只收 aux/auxpass/neg/prt；`wrote down` 的 down 和 `date(s/d/ing) back` 的 back 在这些解析里均为 advmod，导致高亮/答案/干扰项只剩 wrote、date(s/d/ing)。这是单位完整性问题；有限性和主/从句身份多数仍答对，不能据此称高亮完整。

[Cambridge write down](https://dictionary.cambridge.org/dictionary/english/write-down)和[Cambridge date back](https://dictionary.cambridge.org/dictionary/english/date-back?topic=starting-from-a-particular-time)均按 phrasal verb 收录此义。本项目要求带 particle 的完整动词单位，不能把解析器没有标 prt 当成“不需要粒子”的证据。这里只确认这些上下文中的词组，不主张所有动词后介词/方向副词都并入单位。

复现：下表 22 道中，读取显示 parts；对同句缓存取该动词直接子节点，down/back 存在但 dep=advmod。建议用可审计的词组证据加复核门槛，或不能确定时降级；不应把所有 advmod 一概并入。T1 答案冻结期间先降级，不擅自扩答案。控制需覆盖 `go on a hike`、`carried on the backs`、`take the edge off` 和普通地点/方向短语。

| 题号 | 题型 | 来源 | 状态 | 缺漏 |
| --- | --- | --- | --- | --- |
| gi_v02_051024162296 | T1 | ielts11_test4_p1 D-01 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_1090ec7f7d3f | T6 | ielts11_test4_p1 D-01 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_de552d2832c0 | T6 | ielts12_test8_p1 A-03 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_1d976c3e5337 | T1 | ielts13_test3_p2 C-06 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_44fd8b8dd379 | T6 | ielts13_test3_p2 C-06 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_9eedd4ac446f | T1 | ielts14_test1_p2 A-01 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_dd42053a2258 | T6 | ielts14_test1_p2 A-01 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_013b8acb1018 | T1 | ielts16_test2_p1 F-02 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_4f548033a581 | T6 | ielts16_test2_p1 F-02 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_095923e43569 | T1 | ielts16_test2_p3 H-02 | auto_pass | wrote 的 down（T1 为干扰项） |
| gi_v02_05e6a3ca1a02 | T6 | ielts16_test2_p3 H-02 | auto_pass | wrote 的 down（T1 为干扰项） |
| gi_v02_9c0d7a8a7775 | T1 | ielts18_test2_p1 B-03 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_1d8e8000c3a4 | T6 | ielts18_test2_p1 B-03 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_9066f53b827a | T6 | ielts19_test1_p1 E-01 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_9c0dbbe8f595 | T1 | ielts19_test2_p1 B-01 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_570f21f9d7b1 | T6 | ielts19_test2_p1 B-01 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_1a955eea23ab | T1 | ielts19_test3_p1 D-01 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_c6d551018269 | T6 | ielts19_test3_p1 D-01 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_e00c7ec83156 | T1 | ielts6_test1_p3 G-41 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_1b9a92c72a9e | T6 | ielts7_test3_p1 H-02 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_8756902f6024 | T1 | ielts9_test4_p3 A-06 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |
| gi_v02_a3735a0425ca | T6 | ielts9_test4_p3 A-06 | auto_pass | date(s/d/ing) 的 back（按当前目标/答案/干扰项） |

### Y4 — 建议：额外 40 道干扰项不全是“复合形容词的后半截”

位置：`docs/GRAMMAR_ITEM_CANDIDATES_V0_2_FIXES.md:674`、`:752`，交接本轮摘要同说法。40 道中，16_4_p2 G-02 的 `word-spot` 是有限并列动词；20_1_p1 I-05 的 `hand-raising` 是非谓语动词结构；8_4_p1 E-01 的 `mixed-ability` 截出的是前半 mixed。数目及降级判断正确，说明把不同词性和前/后片段统称为复合形容词后半截不准确。

复现见第4.2节；建议改成“40 道连字符词的片段干扰项（其中38道含复合修饰语，2道为动词/非谓语词组）”。这是记录建议，不算应修或新的算法误伤。

### 机经（暂缓）

本轮**新增确认的机经问题 0 项**，不是对机经全池的正确性担保。复核指定 78_102_p3 A-02、92_58_p1 F-03 共4道降级：electricity-half、people-using 实际把短横线当无空格破折号，按字面词内连字符规则属于已披露的保守误降；目标本身可成立。优先规范原文标点再重生，比给 ID 例外合适。百分号相关机经题逐题见第5节，既有待复核边界/关系问题继续保留。V2、第27题、V4/V5及历史暂缓项不重新登记或计数。

## 4. 第2项逐题复核：X1/X2

`split_word()` 检查每个输入 span 及其一层 parts 的两端 e；e 或 e−1 是两边紧邻字母/数字的 ASCII `-` 即降级。覆盖 answer.spans、target、distractors，并在 emit 统一应用于六种题型。它识别的是显示片段风险，不判断整词词性。完整 `back-up`、`5-10` 不触发；只选 `back`、`up`、`5` 触发合理；两侧有空格的插入破折号不触发。`main_distractors` 拒绝不含字母数字的中心 token。

独立探针直接在原句枚举词内连字符位置，再检查全量 auto 的所有可见范围与 parts，命中0；没有复用 split_word 作探针。数字范围以完整范围作控制，不把“只选5”的残缺范围当作必须保护的例子。

### 4.1 原点名17道

15道 needs 的错误内容仍在，仅状态降级；2道百分号主语已修正且仍auto。表中不得解读为17道题的内容全修好。

| 原编号 | 题号 | 题型 | 来源 | 当前状态 | 复核 |
| --- | --- | --- | --- | --- | --- |
| X1 | gi_v02_39a5639ec9f7 | T1 | ielts12_test8_p2 G-02 | needs_review | 带 hyphenated_word_split；仍是片段，降级合理 |
| X1 | gi_v02_2612039eb0fc | T1 | ielts16_test1_p3 M-03 | needs_review | 带 hyphenated_word_split；仍是片段，降级合理 |
| X1 | gi_v02_9d25c9be58aa | T1 | ielts7_test3_p3 A-04 | needs_review | 带 hyphenated_word_split；仍是片段，降级合理 |
| X1 | gi_v02_4f9aff5be0d3 | T1 | ielts10_test1_p3 D-02 | needs_review | 带 hyphenated_word_split；仍是片段，降级合理 |
| X1 | gi_v02_ada51e0516f7 | T6 | ielts10_test1_p3 D-02 | needs_review | 带 hyphenated_word_split；仍是片段，降级合理 |
| X1 | gi_v02_d3ad4b5fc6b8 | T1 | ielts15_test2_p2 D-06 | needs_review | 带 hyphenated_word_split；仍是片段，降级合理 |
| X1 | gi_v02_facbcdde7ef5 | T6 | ielts15_test2_p2 D-06 | needs_review | 带 hyphenated_word_split；仍是片段，降级合理 |
| X1 | gi_v02_411c43f579e8 | T1 | ielts4_test3_p3 D-13 | needs_review | 带 hyphenated_word_split；仍是片段，降级合理 |
| X1 | gi_v02_7bd50392fc2c | T6 | ielts4_test3_p3 D-13 | needs_review | 带 hyphenated_word_split；仍是片段，降级合理 |
| X1 | gi_v02_177f2e3cb51e | T1 | ielts7_test4_p2 E-04 | needs_review | 带 hyphenated_word_split；仍是片段，降级合理 |
| X1 | gi_v02_96c3342be4bf | T6 | ielts7_test4_p2 E-04 | needs_review | 带 hyphenated_word_split；仍是片段，降级合理 |
| X1 | gi_v02_9102debcb432 | T1 | ielts18_test3_p2 F-02 | needs_review | 带 hyphenated_word_split；仍是片段，降级合理 |
| X1 | gi_v02_f0cf657b23e2 | T6 | ielts18_test3_p2 F-02 | needs_review | 带 hyphenated_word_split；仍是片段，降级合理 |
| X2 | gi_v02_1213768264f6 | T1 | ielts14_test2_p2 I-02 | needs_review | 带 hyphenated_word_split；仍是片段，降级合理 |
| X2 | gi_v02_b983993a8787 | T1 | ielts9_test3_p3 E-28 | needs_review | 带 hyphenated_word_split；仍是片段，降级合理 |
| X3 | gi_v02_50bd636fe569 | T5 | ielts4_test1_p3 J-33 | auto_pass | 答案改为 A full 94%，正确 |
| X3 | gi_v02_45648a820455 | T5 | ielts4_test1_p3 J-40 | auto_pass | 答案改为 only a small majority of sighted subjects – 53% –，正确 |

### 4.2 额外41道剑桥T1

41道全部是auto→needs：re-entered一题答案错，其余40道主句局部答案可成立、干扰项是连字符词片段。按冻结内容的最小改法降级可接受。**这与上轮“合法分词定语”不矛盾**：分词可作为非主句干扰项，前提是显示完整词；单独的 borne、called 等丢了同一复合词的前半部分。word-spot/hand-raising 的漏字更是直接动词单位缺损。表中“降级合理”不代表干扰项已改正。

| 题号 | 来源 | 有问题的词/位置 | 当前状态 | 判定 |
| --- | --- | --- | --- | --- |
| gi_v02_0cc036914ffd | ielts16_test4_p2 G-02 | 干扰项: word-spot | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_1195f2b74ef7 | ielts10_test4_p3 D-04 | 干扰项: land-living | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_14a707bfbdde | ielts12_test6_p1 I-03 | 干扰项: community-supported; 干扰项: risk-sharing | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_3a9a831b1649 | ielts13_test1_p2 F-01 | 干扰项: over-connected | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_3b2a3067a435 | ielts14_test4_p2 B-06 | 干扰项: captive-bred | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_47f24247866b | ielts20_test2_p3 A-02 | 干扰项: missile-tracking | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_47f9d492f5b3 | ielts5_test1_p2 F-01 | 干扰项: built-in | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_4945b9c8244c | ielts14_test2_p1 G-05 | 干扰项: almost-completed | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_4eab3bab30f1 | ielts7_test1_p1 A-05 | 干扰项: night-hunting | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_5282519b7fa1 | ielts14_test4_p3 K-04 | 干扰项: slow-moving | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_5358c771bef2 | ielts11_test2_p2 D-03 | 干扰项: wind-lashed | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_57507ce7bbad | ielts10_test2_p2 F-03 | 干扰项: problem-solving | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_62e56f5f661a | ielts5_test3_p2 B-04 | 干扰项: food-growing | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_67a4a168425a | ielts16_test4_p2 F-04 | 干扰项: screen-reading | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_6878167af80a | ielts11_test1_p3 B-05 | 干扰项: sunlight-refracting | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_6b3e67116a8e | ielts6_test2_p2 F-16 | 干扰项: better-educated | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_6fb98ed46203 | ielts10_test3_p3 J-03 | 干扰项: slow-growing | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_70c2a6526058 | ielts13_test2_p1 E-02 | 干扰项: ever-increasing | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_718d24550f2b | ielts16_test4_p2 B-04 | 干扰项: digital-based | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_71cde94f9214 | ielts16_test4_p3 B-08 | 干扰项: machine-learning | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_7308fd06bb64 | ielts15_test1_p2 A-07 | 干扰项: self-driving | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_7a849af41dba | ielts5_test3_p3 A-03 | 答案: re-entered | needs_review | 降级合理；re 不是完整 re-entered |
| gi_v02_8a55ab7a41de | ielts18_test1_p2 D-02 | 干扰项: highest-valued | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_8ea937652bf7 | ielts14_test1_p1 N-01 | 干扰项: play-based | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_96294008ca3c | ielts6_test2_p2 I-30 | 干扰项: brain-derived | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_97252727a6b7 | ielts14_test1_p2 F-02 | 干扰项: bike-sharing | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_978ce796e05c | ielts8_test1_p3 B-05 | 干扰项: so-called | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_9a27b9cf8463 | ielts8_test4_p1 E-01 | 干扰项: mixed-ability | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_a2c3b8ddd827 | ielts20_test1_p1 I-05 | 干扰项: hand-raising | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_a4cd7d2fad47 | ielts11_test1_p1 C-04 | 干扰项: food-bearing | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_accf19fe1002 | ielts18_test3_p2 G-05 | 干扰项: steam-powered | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_b16884621b7b | ielts15_test4_p3 B-03 | 干扰项: profit-making | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_bb81dbbb6013 | ielts10_test2_p1 E-04 | 干扰项: water-borne | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_c19cc9a4e423 | ielts14_test3_p2 I-02 | 干扰项: insect-derived | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_c62d5283de92 | ielts5_test3_p3 A-09 | 干扰项: under-achieving | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_c75314581269 | ielts19_test1_p1 E-01 | 干扰项: so-called | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_cbb991ffd153 | ielts16_test4_p2 D-04 | 干扰项: time-demanding | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_cd728f0f7dd3 | ielts13_test3_p1 D-05 | 干扰项: nitroglycerine-based | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_db5acf9f87cd | ielts18_test1_p1 F-01 | 干扰项: soil-based | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_ee6c86ecc12c | ielts16_test2_p1 E-02 | 干扰项: well-preserved | needs_review | 降级合理；词片段不宜作完整动词干扰项 |
| gi_v02_faabf8c134fd | ielts15_test3_p2 C-05 | 干扰项: solar-powered | needs_review | 降级合理；词片段不宜作完整动词干扰项 |

### 4.3 原已needs的7道与T6隔离

| 题号 | 题型 | 来源 | 变化 | 判定 |
| --- | --- | --- | --- | --- |
| gi_v02_1418d31c7f8d | T1 | ielts11_test1_p3 D-07 | needs→needs；只增加 hyphen 原因 | 词片段风险真实，其他原因仍保留 |
| gi_v02_37fc3dc6668f | T6 | ielts5_test3_p3 A-03 | needs→needs；只增加 hyphen 原因 | 词片段风险真实，其他原因仍保留 |
| gi_v02_65b2f440a04a | T6 | ielts4_test1_p1 B-05 | needs→needs；只增加 hyphen 原因 | 词片段风险真实，其他原因仍保留 |
| gi_v02_83b45ed0a897 | T6 | ielts7_test3_p3 A-04 | needs→needs；只增加 hyphen 原因 | 词片段风险真实，其他原因仍保留 |
| gi_v02_aeea93ff598c | T1 | ielts7_test4_p2 E-01 | needs→needs；只增加 hyphen 原因 | 词片段风险真实，其他原因仍保留 |
| gi_v02_dfa1dc9d1019 | T6 | ielts16_test1_p3 M-03 | needs→needs；只增加 hyphen 原因 | 词片段风险真实，其他原因仍保留 |
| gi_v02_faf124494ea4 | T1 | ielts13_test4_p3 C-02 | needs→needs；只增加 hyphen 原因 | 词片段风险真实，其他原因仍保留 |

与被降级T1同句的“主句身份T6”共有71道（剑桥51、机经20）。65道逐字段不变；剩余6道自己的单位也切词：5道auto→needs，1道原needs增加原因。剑桥51道中42道auto保持auto、5道needs保持needs、4道auto→needs；其中原needs的re-entered增加原因，故46道逐字段不变。另1道剑桥T6新增降级是 road-tested 的非谓语目标，不是主句目标。全量复查没有仅因T1干扰项切词而连带降级的完整主句T6。

纯 `-` 干扰项实际移除的5道：

| 题号 | 来源 | 当前状态 | 判定 |
| --- | --- | --- | --- |
| gi_v02_2612039eb0fc | ielts16_test1_p3 M-03 | needs_review | 单独 - 已无；其余 re/pre/co 等片段仍带原因 |
| gi_v02_39a5639ec9f7 | ielts12_test8_p2 G-02 | needs_review | 单独 - 已无；其余 re/pre/co 等片段仍带原因 |
| gi_v02_80ee83d60a0c | reading_jijing_9_test_81_p2 E-01 | needs_review | 单独 - 已无；其余 re/pre/co 等片段仍带原因 |
| gi_v02_9d25c9be58aa | ielts7_test3_p3 A-04 | needs_review | 单独 - 已无；其余 re/pre/co 等片段仍带原因 |
| gi_v02_a59f135c656e | reading_jijing_85_test_12_p3 I-03 | needs_review | 单独 - 已无；其余 re/pre/co 等片段仍带原因 |

## 5. 第3项逐题复核：百分号

`unit_symbol()` 的实际条件是上一 token 含数字字符、当前尾 token 为 `%`，并不要求上一 token 的 POS=NUM 或两个 token 的字符位置无空格。这能接受 `94 %` 这种有间距的排版；字母数字混合代码加%是理论宽松边界，本库未发现受害题，不把它计为新问题。没有把 `%` 一概视作应保留标点：单独%和普通句末逗号控制仍裁掉。

全剑桥auto中含百分号、角度/温度或货币符号的107个来源句参加边缘扫描，未发现显示范围止于 `% / ‰ / ‱ / ° / ℃ / ℉` 之前，或在金额数字前切掉紧贴的 `$ / £ / € / ¥`。这不等于已穷尽所有科学单位的语义审核。

### 5.1 八对换题号（四剑桥、四机经）

| 旧题号 → 新题号 | 题型/来源 | 状态 | 独立判断 |
| --- | --- | --- | --- |
| gi_v02_2a9125f495cd → gi_v02_1e34da606878 | T3 reading_jijing_88_test_98_p2 A-03 | needs_review → needs_review | 名词性内容判断可成立；depending…边界仍待审 |
| gi_v02_316b5281dce9 → gi_v02_59539b0625fa | T4 reading_jijing_44_test_29_p2 H-01 | needs_review → needs_review | while 关系/边界有歧义，继续待审，不计作正确自动题 |
| gi_v02_775335b45bdb → gi_v02_6965a9feeda3 | T3 ielts10_test1_p2 C-04 | needs_review → auto_pass | while 对比状语从句，43.5%完整；升级合理 |
| gi_v02_70503ed4a385 → gi_v02_ba15890eff44 | T3 ielts13_test1_p1 F-03 | needs_review → auto_pass | while 对比状语从句，26%完整；升级合理 |
| gi_v02_25fd1bc6089d → gi_v02_c575a8bdb20f | T3 reading_jijing_29_test_63_p1 G-04 | needs_review → needs_review | 名词性内容判断可成立；simply to stabilise…被留在范围外，继续待审 |
| gi_v02_fc4d15a329da → gi_v02_dd0e50825edb | T3 reading_jijing_44_test_29_p2 H-01 | needs_review → needs_review | 状语从句；far below…附加范围未含，继续待审 |
| gi_v02_1f8dbf48c548 → gi_v02_e5403312ee6e | T3 ielts20_test2_p1 J-02 | needs_review → auto_pass | of 20% 为介词短语，完整；升级合理 |
| gi_v02_a0822bef80d2 → gi_v02_e5910dd98797 | T3 ielts6_test2_p2 H-26 | needs_review → auto_pass | 明确标出的后项为并列分句，50%完整；T3无A8定位问题 |

### 5.2 共同题号的八道答案变化与四道状态恢复

| 题号 | 题型/来源 | 状态 | 答案/目标 | 独立判断 |
| --- | --- | --- | --- | --- |
| gi_v02_28e61338d892 | T2 reading_jijing_29_test_63_p1 G-04 | needs_review → needs_review | that we will need to cut CO2 emissions by 70% to 80% | 80%已补回；名词性从句范围仍缺后续目的结构，needs合理 |
| gi_v02_38a576ceaaa4 | T5 reading_jijing_92_test_58_p2 H-07 | auto_pass → auto_pass | Only 1.5% | Only 1.5%完整，自动保持合理 |
| gi_v02_3c17aab2ec0b | T2 reading_jijing_44_test_29_p2 H-01 | needs_review → needs_review | While the infestation of water hyacinth in Lake Victoria at the time of writing stands at 0.5% | 0.5%已补回；far below…是否纳入仍须复核 |
| gi_v02_45648a820455 | T5 ielts4_test1_p3 J-40 | auto_pass → auto_pass | only a small majority of sighted subjects – 53% – | 53%及闭合–均补回；主语包含同位说明，正确 |
| gi_v02_50bd636fe569 | T5 ielts4_test1_p3 J-33 | auto_pass → auto_pass | A full 94% | A full 94%完整，正确 |
| gi_v02_bd6ff57c677d | T5 ielts4_test1_p3 J-35 | needs_review → needs_review | And only 51% | 51%补回；And仍混入主语，已有subject_mismatch，不可称内容正确 |
| gi_v02_bdf09c21ab1d | T2 reading_jijing_88_test_98_p2 A-03 | needs_review → needs_review | that new products fail at the stunning rate of between 40% and 90% | 90%补回；depending…附加范围仍待审 |
| gi_v02_df825aebfddd | T2 ielts6_test2_p2 H-26 | needs_review → auto_pass | the use of bath seats has grown by more than 50% | 给定后项及50%完整；但题干仍有A8多解，不批准直接给学生 |
| gi_v02_a75f2590b709 | T6 ielts13_test1_p1 F-03 | needs_review → auto_pass | account | account 为while从句谓语，高亮完整 |
| gi_v02_e52a3c4ab1ed | T6 reading_jijing_44_test_29_p2 H-01 | needs_review → auto_pass | stands | stands 为while从句谓语，高亮完整 |
| gi_v02_e87698c38bae | T6 ielts10_test1_p2 C-04 | needs_review → auto_pass | decreased | decreased 为while从句谓语，高亮完整 |

两表去重共19道：当前11auto（剑桥9、机经2），8needs（剑桥1、机经7）。11auto中10道本次未见内容问题；H-26 T2局部正确、既有A8仍未解决。8needs仅确认百分号修复及保留复核状态，未算入正确自动题。X3本身没有引入新的错误范围。

## 6. A8评估与建议（待用户决定，不计分级）

重跑得到剑桥auto T2并列分句 **345题/345句**；按答案前最近可见连词统计，and248、but93、or4。这个统计用于评估定位难度，不是声称“最近的连词”已经全部语义验收。77句的该连词字面出现不止一次，既可能是词/短语并列，也可能是另一个分句。解析器粗筛还有7题出现多个“conj+有限谓语+自己的主语”，逐题见下表；不能把7当作全部真实多解数。

345道统一题干只说“句中的并列分句”，但只接受一个标注范围，存在未说明选择哪一并列项的教学/判分风险。这里不把“原句至少含两个并列项”偷换成“所有句子都是两个独立主句”；从属内容内部的并列也存在同样定位问题。

- **只写连词**：能改善一个明确连词、一个完整后项的句子；遇到77句中的重复字面、不同层次并列、连词连接短语或嵌套that范围，仍不能唯一定位。不能简单字符串搜索第一个and。
- **全部降为待复核**：最小且可逆，保护学生，代价是暂时少345道剑桥auto；仍需人审题干，needs不是答案修正。建议在用户未批准新题干设计前选择这一步。
- **推荐长期方案**：在原句里标记具体的连词位置（如编号①的and），题干“划出标记①所连接的后一个完整分句”；用源文本字符偏移确定该次出现，并验证它确实连接完整分句、目标始终从该后项开始。同一词出现多次也能定位。无可靠连接点或存在嵌套范围歧义的继续needs。
- **多答案模式**：如果要考“找出任意并列分句”，则必须维护经审核的多个合法范围，判分接受任一；不能把解析器子树的所有候选直接当答案。工作量比明确定位更大。

这是评估建议，本轮没有替用户选择并实施规则，也没有把A8计入新应修。

| 题号 | 来源 | 当前状态 | 人工判断 |
| --- | --- | --- | --- |
| gi_v02_2ad35c049cf2 | ielts11_test2_p2 D-01 | auto_pass | 主句but与that内容内and并存，需按具体层次定位 |
| gi_v02_e352db294821 | ielts13_test4_p3 B-05 | auto_pass | and后thinkers和but后all this均是完整后项 |
| gi_v02_40b28d51f5de | ielts15_test1_p3 D-03 | auto_pass | 多个and，另有one and a half及从属作用域，裸and提示不足 |
| gi_v02_575951b8f98e | ielts17_test4_p2 B-03 | auto_pass | yet和and均接有自己主语的分句 |
| gi_v02_35c7914eb701 | ielts17_test4_p2 B-04 | auto_pass | but和and均接有自己主语的分句 |
| gi_v02_8d12000ccc0a | ielts6_test4_p1 E-23 | auto_pass | 引语内and与but，裸“并列分句”不唯一 |
| gi_v02_6cda2311a1da | ielts9_test3_p2 A-01 | auto_pass | but后的目标还包含一个and并列，须明确要整体还是后项 |

## 7. 第7项：120题及定向扫描

抽样：将当前全量候选筛为 source_kind=reading_test、passage_id以ielts开头、status=auto_pass；按T1–T6顺序，每组先按item_id排序，再使用同一个 `random.Random(20261101)` 连续 `sample(pool,20)`，不重置种子。120道全为auto；逐题看原句、teacher_row显示、答案、T1干扰项和题干前提。

**结果：118道本次未见问题；第107道T6是Y1（动词身份对但混入not），第39道T2是既有A8（给定答案对但题干不唯一）。120句原句均适合语法教学。** 不把这表与定向命中混作同一个随机分母。

| 序号 | 题号 | 题型/来源 | 局部答案 | 显示/题干与判定 | 原句 |
| --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_c44a06bbcf09 | T1 ielts8_test2_p3 F-04 | 成立 | is；interacting 为非谓语，主句唯一 | 是 |
| 2 | gi_v02_167291b9d966 | T1 ielts5_test1_p1 G-02 | 成立 | was…recognised，被动单位完整 | 是 |
| 3 | gi_v02_1cea9b4e87d9 | T1 ielts13_test4_p1 G-02 | 成立 | led；stole 在定语从句内 | 是 |
| 4 | gi_v02_657214e0df45 | T1 ielts11_test3_p1 B-06 | 成立 | was…used，被动单位完整 | 是 |
| 5 | gi_v02_0f07b5aae9e3 | T1 ielts11_test3_p1 C-04 | 成立 | was shipped | 是 |
| 6 | gi_v02_b93fdb944c8b | T1 ielts19_test1_p3 E-02 | 成立 | has garnered；嵌套 how/when 不改变主句 | 是 |
| 7 | gi_v02_0b07c3e6fa1f | T1 ielts8_test4_p3 B-02 | 成立 | include；to attract 为非谓语 | 是 |
| 8 | gi_v02_0c9dc48b7281 | T1 ielts5_test2_p2 H-34 | 成立 | sprang；后置同位语不属谓语 | 是 |
| 9 | gi_v02_ab5c28f17ed7 | T1 ielts11_test2_p2 B-02 | 成立 | found；preserved/proved/had been covered 均非主句谓语 | 是 |
| 10 | gi_v02_3918665fa746 | T1 ielts5_test1_p2 E-04 | 成立 | 疑问倒装 can…account，主语 we 不高亮 | 是 |
| 11 | gi_v02_476cbb5ddf4b | T1 ielts5_test3_p2 B-03 | 成立 | continued；covering 为结果分词结构 | 是 |
| 12 | gi_v02_5520d7997ea8 | T1 ielts7_test1_p3 G-35 | 成立 | may be seen | 是 |
| 13 | gi_v02_1f2064fb1524 | T1 ielts9_test4_p2 F-01 | 成立 | suggested；并列的是主语 | 是 |
| 14 | gi_v02_23c50fa56b2b | T1 ielts9_test2_p1 C-01 | 成立 | are…failing；generated 为分词定语 | 是 |
| 15 | gi_v02_74e2092bd667 | T1 ielts6_test4_p2 E-11 | 成立 | was | 是 |
| 16 | gi_v02_9408cbad5499 | T1 ielts19_test2_p3 H-04 | 成立 | found；looked/being studied/were succeeding 非主句谓语 | 是 |
| 17 | gi_v02_de5bd2d68b54 | T1 ielts17_test3_p3 H-01 | 成立 | focus；并列的是主语 | 是 |
| 18 | gi_v02_e00c584f0096 | T1 ielts17_test2_p2 C-03 | 成立 | managed；reduced/thought/to have 非主句谓语 | 是 |
| 19 | gi_v02_df59d564c9f9 | T1 ielts16_test1_p1 E-06 | 成立 | used；hung 为分词 | 是 |
| 20 | gi_v02_80cb4b944177 | T1 ielts12_test5_p3 E-09 | 成立 | need；to achieve 非谓语，is 在 what 从句中 | 是 |
| 21 | gi_v02_1c52371a358d | T2 ielts7_test4_p2 I-03 | 成立 | that 宾语从句完整 | 是 |
| 22 | gi_v02_2e5fe39dd88f | T2 ielts6_test4_p3 D-08 | 成立 | that 内保留插入状语 over a two-year period | 是 |
| 23 | gi_v02_ce02c2098093 | T2 ielts12_test7_p3 D-04 | 成立 | that 宾语从句完整 | 是 |
| 24 | gi_v02_0085b2a9ee6f | T2 ielts18_test2_p1 C-01 | 成立 | 43 of which 整体为非限制性定语从句 | 是 |
| 25 | gi_v02_7444f9199971 | T2 ielts7_test3_p3 A-11 | 成立 | that 宾语从句完整 | 是 |
| 26 | gi_v02_06f143584879 | T2 ielts9_test3_p3 D-20 | 成立 | which 定语从句完整 | 是 |
| 27 | gi_v02_a14cd6b9ac27 | T2 ielts16_test4_p1 E-02 | 成立 | time 后省略关系词的定语从句 | 是 |
| 28 | gi_v02_80aa6bfa8848 | T2 ielts16_test4_p3 F-02 | 成立 | that 内容含前置 when 和并列表语，完整 | 是 |
| 29 | gi_v02_20fea0820f3b | T2 ielts9_test2_p3 B-04 | 成立 | way 后省略关系词；realization 后 that 为内容从句，未混淆 | 是 |
| 30 | gi_v02_a2d81cae57a8 | T2 ielts20_test1_p2 C-05 | 成立 | why 宾语从句含 when 从句 | 是 |
| 31 | gi_v02_021d3888cacf | T2 ielts8_test1_p1 G-02 | 成立 | which 定语从句包含 shaped 分词后置修饰 | 是 |
| 32 | gi_v02_3e8cf2dcfaeb | T2 ielts6_test3_p1 H-02 | 成立 | how 为形式主语 it 对应内容 | 是 |
| 33 | gi_v02_e2611401de2c | T2 ielts7_test1_p3 B-03 | 成立 | which 指代 processing，括号不属于内部定语从句 | 是 |
| 34 | gi_v02_23707ee1b8d0 | T2 ielts13_test1_p2 B-05 | 成立 | what 表语从句；冒号后为独立解释，范围止于 boredom 合理 | 是 |
| 35 | gi_v02_cef2a6549552 | T2 ielts4_test2_p2 E-26 | 成立 | that 宾语从句完整 | 是 |
| 36 | gi_v02_6c14a2c7e5b7 | T2 ielts10_test4_p2 D-03 | 成立 | that 内容完整；making 可作高层结果补充 | 是 |
| 37 | gi_v02_526b66c17cde | T2 ielts19_test1_p3 F-04 | 成立 | through which 定语从句完整 | 是 |
| 38 | gi_v02_3d172027a6ca | T2 ielts14_test2_p1 B-03 | 成立 | Although 让步从句 | 是 |
| 39 | gi_v02_6558f9d51457 | T2 ielts5_test1_p3 D-14 | 成立 | 给定 but 后分句正确；题干未定位唯一分句，既有 A8 | 是 |
| 40 | gi_v02_69f873ee255e | T2 ielts18_test4_p3 C-03 | 成立 | When 时间从句 | 是 |
| 41 | gi_v02_0f9f86350bb8 | T3 ielts5_test1_p1 B-01 | 成立 | compiled 分词修饰 book，非限定 | 是 |
| 42 | gi_v02_507ff7f99f43 | T3 ielts12_test6_p3 B-08 | 成立 | what 从句在 because 内作主语 | 是 |
| 43 | gi_v02_79b32ac8b0e3 | T3 ielts16_test1_p3 B-01 | 成立 | that 修饰 jobs | 是 |
| 44 | gi_v02_d0a1d38e95cf | T3 ielts20_test2_p2 F-43 | 成立 | to procrastinate 不定式后置修饰 | 是 |
| 45 | gi_v02_96e57b06c99b | T3 ielts12_test6_p2 C-04 | 成立 | to have been…为不定式补语 | 是 |
| 46 | gi_v02_ad25dd14e250 | T3 ielts19_test4_p3 F-02 | 成立 | if 条件从句 | 是 |
| 47 | gi_v02_7e7ffd0258b2 | T3 ielts7_test2_p2 A-02 | 成立 | bringing it down 动名词结构 | 是 |
| 48 | gi_v02_e83e13979feb | T3 ielts11_test3_p2 F-07 | 成立 | where 非限制性定语从句，先行词 shoulders of land | 是 |
| 49 | gi_v02_ce3745c892fd | T3 ielts16_test3_p1 E-04 | 成立 | controlled 分词修饰 rudders | 是 |
| 50 | gi_v02_195e7b7c9193 | T3 ielts10_test4_p3 G-02 | 成立 | Like 介词短语 | 是 |
| 51 | gi_v02_1fe0db2a9b1e | T3 ielts16_test3_p3 B-01 | 成立 | at which 修饰 pace | 是 |
| 52 | gi_v02_e293926a54f5 | T3 ielts13_test3_p1 B-07 | 成立 | among 介词短语 | 是 |
| 53 | gi_v02_e0ccb80a9faf | T3 ielts14_test3_p3 J-03 | 成立 | joining/raising/commenting/encouraging 并列非谓语 | 是 |
| 54 | gi_v02_5258548f6eb1 | T3 ielts15_test4_p1 F-01 | 成立 | that 修饰 tree | 是 |
| 55 | gi_v02_a9d2056f3864 | T3 ielts19_test4_p1 E-01 | 成立 | that 为 discovered 的内容 | 是 |
| 56 | gi_v02_f5f8d0f3f1d9 | T3 ielts4_test3_p1 O-01 | 成立 | of access to credit 介词短语 | 是 |
| 57 | gi_v02_5e124148edc0 | T3 ielts4_test1_p2 D-05 | 成立 | that 为 suggests 的内容 | 是 |
| 58 | gi_v02_fb73665d59aa | T3 ielts11_test3_p3 F-01 | 成立 | As I wrote 为状语从句；未强定关系类型 | 是 |
| 59 | gi_v02_e785497def67 | T3 ielts17_test4_p1 L-02 | 成立 | to quantify 为目的不定式 | 是 |
| 60 | gi_v02_382839170d30 | T3 ielts10_test4_p1 I-04 | 成立 | among 介词短语 | 是 |
| 61 | gi_v02_82a8fb68342b | T4 ielts9_test1_p2 B-14 | 成立 | if 条件，嵌于 since 中 | 是 |
| 62 | gi_v02_2a92467d0907 | T4 ielts5_test4_p3 C-15 | 成立 | because 原因 | 是 |
| 63 | gi_v02_e5a85a7c964c | T4 ielts8_test4_p3 E-05 | 成立 | although 让步，括号内结构完整 | 是 |
| 64 | gi_v02_c18daabb7c74 | T4 ielts7_test1_p1 B-05 | 成立 | although 让步，嵌于 because 中 | 是 |
| 65 | gi_v02_b5b436c9ae87 | T4 ielts5_test4_p2 F-20 | 成立 | when 时间 | 是 |
| 66 | gi_v02_b69b1a401528 | T4 ielts9_test1_p2 E-30 | 成立 | if 条件 | 是 |
| 67 | gi_v02_c8fb718b0fec | T4 ielts14_test4_p2 F-02 | 成立 | so that 表目的 | 是 |
| 68 | gi_v02_db89688be8b2 | T4 ielts4_test2_p1 C-16 | 成立 | if 条件 | 是 |
| 69 | gi_v02_fe308ec5ab28 | T4 ielts12_test8_p2 A-06 | 成立 | if 条件，this 指前文仍可作语法题 | 是 |
| 70 | gi_v02_f29eb2a6a26e | T4 ielts18_test1_p3 B-02 | 成立 | so that 表目的 | 是 |
| 71 | gi_v02_02ed523591e6 | T4 ielts13_test4_p2 E-04 | 成立 | when 时间 | 是 |
| 72 | gi_v02_ec4a9719b5db | T4 ielts20_test2_p2 C-15 | 成立 | if 条件，否定/并列谓语范围完整 | 是 |
| 73 | gi_v02_241a8109b046 | T4 ielts7_test4_p3 B-01 | 成立 | if 条件 | 是 |
| 74 | gi_v02_ea3427ca28a7 | T4 ielts5_test4_p3 B-10 | 成立 | after 时间 | 是 |
| 75 | gi_v02_2f7ea967f5a4 | T4 ielts15_test2_p2 C-01 | 成立 | if 条件，主句为疑问句不妨碍本题 | 是 |
| 76 | gi_v02_bf18d8697612 | T4 ielts20_test4_p3 E-26 | 成立 | if 条件，外层引号不属于目标 | 是 |
| 77 | gi_v02_ca22cccef988 | T4 ielts18_test3_p2 C-04 | 成立 | though 让步 | 是 |
| 78 | gi_v02_ae2733bdc2bb | T4 ielts19_test1_p3 C-01 | 成立 | if 为反事实条件 | 是 |
| 79 | gi_v02_45ff223cfc7b | T4 ielts20_test2_p3 B-07 | 成立 | even if 让步条件，选让步合理 | 是 |
| 80 | gi_v02_b50f59f27c4a | T4 ielts8_test3_p2 F-01 | 成立 | if 条件 | 是 |
| 81 | gi_v02_8535aaf9dd5f | T5 ielts6_test3_p1 D-01 | 成立 | Early cinema audiences 完整 | 是 |
| 82 | gi_v02_3355add8774c | T5 ielts15_test4_p3 G-01 | 成立 | the conclusion 连同 that 同位内容完整 | 是 |
| 83 | gi_v02_3e5b6098e60b | T5 ielts11_test1_p2 F-08 | 成立 | Two eight-metre-wide cogs 完整；connected 修饰后面的齿轮结构 | 是 |
| 84 | gi_v02_e0dd9e66c6d5 | T5 ielts6_test2_p3 C-03 | 成立 | the number and words 并列主语完整 | 是 |
| 85 | gi_v02_971d02a3d03f | T5 ielts6_test3_p1 H-03 | 成立 | All 连同 that mattered at first 完整 | 是 |
| 86 | gi_v02_0aad43175600 | T5 ielts17_test2_p3 I-03 | 成立 | the Law of Effect 完整；句首类比状语不属主语 | 是 |
| 87 | gi_v02_2fe4fcc34f53 | T5 ielts12_test6_p2 F-04 | 成立 | This term；Vilcabamba 的同位语在表语内 | 是 |
| 88 | gi_v02_bc0942f85936 | T5 ielts14_test2_p1 C-02 | 成立 | He | 是 |
| 89 | gi_v02_fb856875b6a2 | T5 ielts13_test2_p1 F-02 | 成立 | production of cinnamon | 是 |
| 90 | gi_v02_54292c47b5e7 | T5 ielts13_test2_p3 C-02 | 成立 | A case in point；倒置意义不改变本句表层主语 | 是 |
| 91 | gi_v02_71ae1f4ae753 | T5 ielts18_test3_p2 G-02 | 成立 | it；Priced 分词为句首状语 | 是 |
| 92 | gi_v02_96ab5e04206a | T5 ielts17_test4_p2 D-01 | 成立 | Ogilvie and her team 并列主语完整 | 是 |
| 93 | gi_v02_cdeb0ad9d4d1 | T5 ielts5_test4_p1 C-41 | 成立 | A growing number of communities | 是 |
| 94 | gi_v02_77de876b09d5 | T5 ielts19_test1_p2 A-02 | 成立 | pirates；句首时间状语不属主语 | 是 |
| 95 | gi_v02_c8f752058b7f | T5 ielts12_test7_p1 E-03 | 成立 | The aim | 是 |
| 96 | gi_v02_df380d5f2f43 | T5 ielts18_test3_p1 E-03 | 成立 | 两个并列动名词结构均包含 | 是 |
| 97 | gi_v02_babc11ffa7ca | T5 ielts18_test4_p3 C-04 | 成立 | he | 是 |
| 98 | gi_v02_62ceb90440b5 | T5 ielts17_test4_p2 C-05 | 成立 | Previous studies | 是 |
| 99 | gi_v02_10e2a996bd38 | T5 ielts5_test3_p1 D-08 | 成立 | Medical problems | 是 |
| 100 | gi_v02_23b6cf710eca | T5 ielts15_test3_p2 C-05 | 成立 | The warm water | 是 |
| 101 | gi_v02_5aad9998f7f0 | T6 ielts16_test3_p3 E-09 | 成立 | rises 为 Just as 从句谓语 | 是 |
| 102 | gi_v02_7b1fc8b32a2d | T6 ielts15_test2_p2 F-02 | 成立 | think 为 when 从句谓语 | 是 |
| 103 | gi_v02_9319319ed21a | T6 ielts5_test2_p1 G-32 | 成立 | Being 为分词 | 是 |
| 104 | gi_v02_9c79d7f2017a | T6 ielts12_test6_p2 F-01 | 成立 | occurred 为主句谓语，that 内容后置 | 是 |
| 105 | gi_v02_070008510acc | T6 ielts18_test1_p2 D-03 | 成立 | might be 为主句谓语 | 是 |
| 106 | gi_v02_914e1101b74b | T6 ielts13_test2_p1 A-01 | 成立 | produced 为分词定语 | 是 |
| 107 | gi_v02_a61a5b99135c | T6 ielts11_test1_p2 E-03 | 主要动词身份成立 | carrying 的身份正确，但 whether or not 的 not 被混入单位（Y1） | 是 |
| 108 | gi_v02_a6c51de4c056 | T6 ielts14_test1_p3 K-02 | 成立 | conducted 主句谓语 | 是 |
| 109 | gi_v02_e0888d3c6138 | T6 ielts12_test7_p1 B-03 | 成立 | to act 目的不定式 | 是 |
| 110 | gi_v02_cf6e17e6e664 | T6 ielts10_test2_p1 C-01 | 成立 | are 为主句有限动词；to be found 另作不定式补语，本题身份成立 | 是 |
| 111 | gi_v02_5307bad78422 | T6 ielts9_test1_p3 E-34 | 成立 | draw out 单位完整 | 是 |
| 112 | gi_v02_117d01ea8fcb | T6 ielts12_test5_p1 F-02 | 成立 | is caused 被动单位完整 | 是 |
| 113 | gi_v02_b97cfb3596b9 | T6 ielts5_test1_p1 D-06 | 成立 | set up 在 in which 定语从句内 | 是 |
| 114 | gi_v02_ad5fe0946234 | T6 ielts8_test1_p3 E-21 | 成立 | switched 主句谓语；to 引导介词短语 | 是 |
| 115 | gi_v02_6156540e903c | T6 ielts9_test3_p3 D-21 | 成立 | generalises 主句谓语 | 是 |
| 116 | gi_v02_d09d674e150a | T6 ielts12_test7_p2 C-03 | 成立 | being driven 非谓语被动 | 是 |
| 117 | gi_v02_3d8fe6469337 | T6 ielts16_test2_p2 H-02 | 成立 | indicating 分词修饰 studies | 是 |
| 118 | gi_v02_d3efefdcb02c | T6 ielts11_test2_p2 A-03 | 成立 | came 主句谓语 | 是 |
| 119 | gi_v02_399ef5b1fa85 | T6 ielts19_test3_p1 C-06 | 成立 | allowing 非谓语结果结构 | 是 |
| 120 | gi_v02_f2f3a43eddd6 | T6 ielts12_test5_p3 F-10 | 成立 | gives 主句谓语 | 是 |

### 定向扫描方法、命中与排除

本轮新角度是**词语的语法作用域与跨题型语义一致性**，不是再数解析器直接子节点是否齐全：

1. 在27,927道剑桥auto中扫描T1/T6的可见parts是否包含whether-or-not、not just because等关联结构里的not，并扩展普通not just/not necessarily/名词补足等控制。命中49题，逐题读上下文确认7题Y1；其余42是普通谓语否定或相关正常用法，不降级。这里先定位关联结构再比较显示范围，不把所有neg当错。
2. 对所有剑桥auto T3名词性/定语目标，从that是否作句法成分、是否有先行词、是否只是在内部含what等角度筛疑点。定语that作mark为0；名词性that作论元命中1题；非名词挂靠/内部what命中18题。19个目标逐一看后都没有确认新的类别错误：H-04的that是say后内容里的指示代词，不是关系词；18个定语目标多为整句指代、名词化best/much、外置定语或内部嵌套what。不能机械地按词性/依存挂靠批量降级。
3. 对所有剑桥auto T6从属目标反查相同head的type_matches，命中54道。人工确认4个for目标是Y2；其余50道在主/从句/非谓语这一粒度上仍是从句谓语。由4句回查T1/T5另确认2道唯一性错误，合计6道。50个类别仍成立的控制中，H-02的wrote存在另一个完整单位问题，计Y3，不混称所有字段正确。
4. 从H-02的wrote down出发，用16组常见短语动词的词形+粒子作表面触发（write down、date back、point out、carry out/on、find out、set up、take off、go on、turn out、put off、make up、give up、break down、work out、end up），找粒子在直接子节点但未显示的auto。命中34题；22题上下文确为date back/write down（均advmod，Y3）；另外12题是方向/介词短语、take the edge off或不同动词的同形词触发，未判错。未扩展成“所有advmod要高亮”。

上述35道确认问题在8a0660b中逐字段相同；这不是新规则引入35个回归。下面列出其余定向控制的逐目标结论，保留阴性证据，避免只列错误例。

| 题号 | 来源 | 目标 | 人工结论 |
| --- | --- | --- | --- |
| gi_v02_ba7e3ccad450 | ielts16_test3_p2 H-04 | that could be because many of those artefacts have already disintegrated or are still frozen in the ice | 名词性内容成立；that在内层作指示主语 |
| gi_v02_3013f3944182 | ielts10_test2_p2 B-04 | which will include strategies of planning, monitoring, evaluation, and choice of what to learn | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_8ee128faf7db | ielts11_test1_p3 A-02 | we can do | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_81e28cf74b8d | ielts11_test3_p1 B-08 | who is estimated to have died around 168 AD | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_89e8f04bd764 | ielts11_test4_p2 E-01 | which are synchronized or matched with what is viewed | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_595752e78970 | ielts12_test8_p2 F-01 | in which campaigners articulate what they are for rather than only what they are against | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_fefb10d21f97 | ielts13_test1_p2 B-02 | which measures how positive or negative the feeling is | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_ab66207b236b | ielts13_test1_p2 D-13 | where we don't know what to do any more, and no longer care | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_5f124000ac6e | ielts13_test2_p3 H-01 | that affect how people perceive the world around them and shape what they expect from products and services | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_addb17db3207 | ielts13_test3_p2 E-07 | which approximates sound making | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_099667c1f851 | ielts13_test4_p3 A-06 | that not only identifies what makes people happy but also allows their happiness to be measured | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_6febf15db9f9 | ielts13_test4_p3 E-02 | that is interesting | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_ccf378ae3f89 | ielts15_test3_p2 D-03 | that is able to help these people | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_6ddfeb6f8e93 | ielts17_test3_p2 F-03 | which is predominantly what makes it so profitable | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_80f2803f5a91 | ielts17_test4_p3 F-09 | that make up what is called the frontoparietal control network | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_0cd613fa6d77 | ielts20_test1_p3 G-01 | that causes us to take in warnings and focus on what might go wrong | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_686b72dcdc8f | ielts4_test4_p1 C-17 | that duplicates what they are doing in their running events | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_ec049ec70dd4 | ielts7_test1_p2 E-03 | which is increasingly considered the option of last, not first, resort | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |
| gi_v02_3a5745ff3758 | ielts9_test3_p3 C-17 | which can be captured in the binary unit, or 'bit', of the form 1 or 0 | 定语从句成立；内部嵌套词/整句指代/外置位置不构成类别错误 |

## 8. 全池差分与统计

基线是前轮在Mac独立生成的8a0660b完整快照候选；525fcb4只比它多复审文档。当前为固定a3fbcbb快照生成。按共同item_id逐字段比较，换ID的8题另用未变的source/template/tag_role/tag_span一对一配对，不把换ID当共同题号升级。

| 口径 | 剑桥 | 机经 |
| --- | --- | --- |
| 旧题数/新题数（全库） | 50,243 → 50,243 | 全库同口径 |
| 换ID | 4对：旧needs→新auto | 4对：旧needs→新needs |
| 共同ID auto→needs | 56（T1 51、T6 5） | 30 |
| 共同ID needs→auto | 3 | 1 |
| hyphen原因全量 | 63 | 45 |
| 只因hyphen待审 | 56 | 30 |
| 原needs仅新增hyphen原因 | 7 | 15 |
| 当前auto | 27,927 | 12,496 |

| 题型 | auto_pass | needs_review |
| --- | --- | --- |
| T1 | 5841 | 538 |
| T2 | 4679 | 2583 |
| T3 | 11401 | 3486 |
| T4 | 399 | 657 |
| T5 | 5366 | 818 |
| T6 | 12737 | 1738 |

当前auto合计40,423。共同题号非状态字段实际变化：answer8、distractors5、evidence29，其中21道仅evidence变化；其他字段0。换ID8对已另列，不混进这组“共同题号”计数。三种hyphen口径分别代表“受影响总量”“唯一原因”“原待审新增原因”，没有把7/15原待审算作新增降级。

回归13×6=78个记录对象与8a0660b完全相同；7项整句过滤的预期/实际逐项如下。

| 过滤 | 预期 | 实际 | 是否相符 |
| --- | --- | --- | --- |
| tagged_fragment | 30 | 30 | True |
| clause_attached_to_conjunction | 2 | 2 | True |
| glued_sentence_boundary | 0 | 0 | True |
| multi_sentence_unit | 1 | 1 | True |
| suspected_split_word | 0 | 0 | True |
| leading_stray_punctuation | 0 | 0 | True |
| control_character | 0 | 0 | True |

## 9. 重新生成、表格与SHA-256

环境：Mac Darwin arm64、macOS27.0.1；Python3.13.3、spaCy3.8.16、en_core_web_trf3.8.0、torch2.14.1 CPU、openpyxl3.1.5，seed20261018。reading_study输入SHA `55b808e1a69cfb7fc06670a6ac3bb36d2861923f229183875ed309ea3a747f37`；grammar_graph输入SHA `c7b35ddb68db7601ccd01e38a210ad3dd772ff507302190f68a351e408b85a29`。

在仓库外完整a3快照用任务树`.venv-grammar-tools`运行两次完整生成。复用上一轮已验证、相同原句/模型/适配器环境的解析缓存；本轮未改reading_study，不是重新训练或调用模型API。两次都重新构造全量候选、报告和抽查表。比较前统一序列化运行时tuple/list，避免把内存类型与JSON表示误算为反事实差异。

| 文件 | 第一次SHA-256 | 第二次SHA-256 |
| --- | --- | --- |
| generation_report_v0_2.json | c84fcae60df8aa01b1aa25cb512092923e61001babcfcd846466f19d36fe52a2 | c84fcae60df8aa01b1aa25cb512092923e61001babcfcd846466f19d36fe52a2 |
| generation_report_v0_2.md | 9eb5bca1469b49870784078c9dc6290996d7103c1742cb7450fb42e586000926 | 9eb5bca1469b49870784078c9dc6290996d7103c1742cb7450fb42e586000926 |
| review_batch_v0_2.jsonl | f8b14a0de986490f8ad2672b043b1f7981117903e9d51183b2e2ff1a9cd6e547 | f8b14a0de986490f8ad2672b043b1f7981117903e9d51183b2e2ff1a9cd6e547 |
| review_batch_v0_2.xlsx | 68bac14def853460fedabeee911199a0017af56fd2e2ed37e77c5bbb3ad3b9a0 | 68bac14def853460fedabeee911199a0017af56fd2e2ed37e77c5bbb3ad3b9a0 |

| 文件 | 提交版SHA-256 | 与Mac比较 |
| --- | --- | --- |
| generation_report_v0_2.json | d9c280216849ad9a43bd33f136553105f31eec243f56cdb1c5ed267b3756f800 | 仅Python版本行：提交3.11.15 / Mac3.13.3 |
| generation_report_v0_2.md | a404f8afc867fd24c384764b1f4c499e95a4b0b3866470a69f9778fd58a4c06d | 仅Python版本行：提交3.11.15 / Mac3.13.3 |
| review_batch_v0_2.jsonl | f8b14a0de986490f8ad2672b043b1f7981117903e9d51183b2e2ff1a9cd6e547 | 逐字节相同 |
| review_batch_v0_2.xlsx | 68bac14def853460fedabeee911199a0017af56fd2e2ed37e77c5bbb3ad3b9a0 | 逐字节相同 |

**与提示的差异**：提示JSONL SHA写 `f8b14a0de986491f8ad2672b043b1f7981117903e9d51183b2e2ff1a9cd6e547`；Git提交字节和两次本机生成都是 `f8b14a0de986490f8ad2672b043b1f7981117903e9d51183b2e2ff1a9cd6e547`。区别为这一位1/0；不是本机改写了交付文件。其余三个提示SHA与提交相同。

XLSX用原生ZIP/XML只读检查，并把每个可见单元格与JSONL经teacher_row生成的老师行比较：7表（说明+6题型）、每题型60行、H2:H61四项下拉“正确 / 答案错 / 题目有歧义 / 句子不适合出题”、所有可见行无auto_pass/needs_review/原因标签。动词parts高亮逐行一致；盲审不代表题目内容已经正确。

抽查表360题：剑桥237=196auto+41needs，机经123=104auto+19needs。与上一轮按题号集合仅13题保留；按(工作表, review_row)比较0行同题。老师旧判定只能按题号迁移，不能按Excel行号套用；120题独立抽样来自全池，不是这360行的子抽样。

## 10. 测试、数据与负测

| 检查 | 实际结果 |
| --- | --- |
| 四个专项模块 | 122运行、122通过 |
| 新建Flask-only环境按ci.yml完整13模块 | 190运行、189通过、1按设计跳过；只安装Flask及其传递依赖 |
| Node拼写队列 | exit0 |
| tests.test_reading_study | 22运行、22通过 |
| validate_reading_study.py | exit0、0错误，覆盖317/387、70缺失为存量 |
| reading_jijing_text_fixes.py --check | 0 fix(es) not yet applied |
| raw内存重建 | 171篇，content整体（含summary）和groups与static全等；图片只计算原有本地路径，不联网下载 |
| render_grammar_graph_review.py | 仓库外生成与提交版逐字节相同 |
| 改动Python Ruff check/format | 5文件均通过，ruff0.15.21；显式extend-exclude=[]确保没有被仓库排除规则漏检 |
| SQLite模拟导入 | main先created317；a3再updated236/skipped81/failed0，最终317行 |

完整main快照按676569c的2853个Git blob逐个核验，包含代码/static/data，不是只拿main解析文件配新static。导入使用`make_app(database_uri=...)`明确绑定仓库外SQLite，只建所需分析表、核对engine URI；未读取/写入生产数据库。当前分支reading_study未变，实测236/81与前轮相同。

9个新测试在旧525fcb4代码上运行，测试体用当前版本，三个依赖模块parse_view/checks/templates全部换旧版，逐进程隔离：

| 测试 | 旧代码结果 | 含义 |
| --- | --- | --- |
| CoordinateOverlapTests.test_and_parsed_as_mark_is_no_subordinator | 断言失败 | 新行为正例失败 |
| AgeExpressionTests.test_only_when_is_checked_against_an_age | 断言失败 | 新行为正例失败 |
| HyphenatedWordTests.test_span_edges_inside_a_hyphenated_word | 接口错误 | 缺split_word |
| HyphenatedWordTests.test_hyphenated_main_verb_goes_to_review | 断言失败 | 新行为正例失败 |
| HyphenatedWordTests.test_hyphen_tagged_verb_is_no_distractor | 断言失败 | 新行为正例失败 |
| HyphenatedWordTests.test_compound_adjective_in_a_subject_is_whole | 接口错误 | 缺Reason.HYPHENATED_WORD_SPLIT；不能称业务断言失败 |
| PercentSubjectTests.test_percent_stays_in_the_subject | 断言失败 | 新行为正例失败 |
| PercentSubjectTests.test_percent_and_closing_dash_in_an_inserted_phrase | 断言失败 | 新行为正例失败 |
| PercentSubjectTests.test_trailing_punctuation_is_still_trimmed | 通过 | 普通标点控制原已成立 |

合计6断言失败、2接口错误、1控制通过。当前9项都通过。第十轮FIXES已更正W1两项为缺Reason常量，与上轮证据一致；W2模块导入失败是另一项，不能混称。

## 11. 实际执行命令与复现入口

以下变量只为缩短命令；没有向生产运行任何命令。辅助脚本、完整候选池、缓存、日志、快照和SQLite仅本机保存在O，不随Git共享；跨电脑以本报告的逐题ID、抽样算法、探针说明和已推送文档为依据。仓库允许写入的只有三份审核/交接文档。

```sh
R=/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker
O=/Users/zhouxin/.codex/audits/grammar-v02-round11-20261027
G=$R/.venv-grammar-tools/bin/python
P=/Users/zhouxin/Desktop/studytracker/.venv/bin/python
N=/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
```

A：入口和固定版本（在R；读取链上AGENTS及CLAUDE、HANDOFF最新两节、WORKLOG顶部后）：

```sh
git status --short --branch
git log -5 --oneline
git fetch origin claude/word-memorization-system-eval-55v2y5
git merge --ff-only a3fbcbb1ade29c9f39484beaa5eeab761f78afe3
git rev-parse HEAD
git diff --stat 525fcb4..a3fbcbb
git diff --name-only 525fcb4..a3fbcbb
git diff 525fcb4..a3fbcbb -- scripts/grammar_items/templates.py scripts/grammar_items/checks.py scripts/grammar_items/parse_view.py scripts/grammar_items/reporting.py tests/test_grammar_item_candidates.py
```

B：用Python subprocess取得`git archive a3fbcbb`并由tarfile解到O/source，复用前轮相同环境的parse_cache；`generate.py`顺序执行下列命令两次，各次将四份交付复制到O/first、O/second。工作目录O/source，未覆盖R：

```sh
$G scripts/generate_grammar_candidates.py --seed 20261018
$G scripts/generate_grammar_candidates.py --seed 20261018
```

C：在O运行`$G audit_runtime.py > audit-runtime.log`。按item_id比较基线/当前池、另配对换ID；计算每份SHA、双跑和提交字节；XML比对全部360老师行、下拉与盲审；依第7节算法抽120并用teacher_row显示；结果`runtime-summary.json`、`field-changes.json`、`id-pairs.json`、`hashes.json`、`sample120*`。

D：在O运行`$G audit_data.py > audit-data.log`。diff白名单、AST决策函数ID访问、未知role、7过滤；import构建器并替换localize_image为纯路径计算，build_tests(raw,'jijing')逐篇比较content/groups；完整main Git blob哈希；O/source运行图谱生成与提交字节比较。

E：在O运行`$G negative_tests.py > negative-summary.log`和`$G counterfactual.py`。负测逐个子进程载入旧525版本的三个模块，执行当前9测试；反事实只把coordinate_function_overlap、relative_adverb_risk换回d53f8ba前版本，其余维持当前，用完整缓存collect，JSON规范化后比较50,243题，0差异。

F：在O运行以下独立扫描和人工判定保存；所有输入来自当前全池及同句缓存，未调用大模型API：

```sh
$G scan_new.py
$G scan_consistency.py
$G scan_particles.py
$G judgments.py
```

第7节给出触发条件和人工排除规则，问题ID及120判断均在本报告。`scan_new.py`另统计A8重复连词、语义单位边缘；`scan_consistency.py`反查T6分类并关联T1/T5；`scan_particles.py`对16组明确词形+粒子逐题回读，不把词表触发当结论。

G：`$G run_checks.py`逐条执行（cwd=R；日志在O），实际展开主要命令如下：

```sh
$G -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary tests.test_grammar_graph_draft -v
$P -m unittest tests.test_reading_study -v
$G scripts/validate_reading_study.py
$G scripts/reading_jijing_text_fixes.py --check
$N tests/test_dictation_spell_queue.js
$P -m ruff check --config 'extend-exclude=[]' scripts/grammar_items/checks.py scripts/grammar_items/parse_view.py scripts/grammar_items/reporting.py scripts/grammar_items/templates.py tests/test_grammar_item_candidates.py
$P -m ruff format --check --config 'extend-exclude=[]' scripts/grammar_items/checks.py scripts/grammar_items/parse_view.py scripts/grammar_items/reporting.py scripts/grammar_items/templates.py tests/test_grammar_item_candidates.py
$G -m venv "$O/flask-only"
$O/flask-only/bin/python -m pip install --cert /etc/ssl/cert.pem Flask
$O/flask-only/bin/python -m unittest tests.test_miniprogram_guest_access tests.test_miniprogram_dictation_grouping tests.test_inventory_toefl_materials tests.test_organize_toefl_materials tests.test_extract_toefl_answer_keys tests.test_map_toefl_answers_to_practice_docs tests.test_import_toefl_official_reading tests.test_reading_vocab_grading tests.test_stats_utils tests.test_grammar_graph_draft tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary -v
$O/flask-only/bin/python -m pip list
```

H：cwd=O，新建SQLite路径`O/main-to-current.sqlite`；两次分别只import对应完整快照的代码/原文/数据：

```sh
$P import_snapshot.py main main > import-main.log
$P import_snapshot.py source round11 > import-round11.log
```

## 12. 交接、CI与限制

执行和待提交文档位于任务树R；桌面`/Users/zhouxin/Desktop/studytracker`仍main@6ded77d、behind85，原有7modified/22untracked入口原样保留，本轮没有写入它。仅借用其venv运行reading测试、临时SQLite和Ruff。任务树开工无未提交/未跟踪文件；本轮只新增ROUND11_CODEX_REVIEW，更新HANDOFF/WORKLOG，辅助产物全部在O。

实现验收可复现，不等于全池语义验收通过。下一步：实现方处理Y1–Y3并回归上述35题与正常控制；更正Y4描述；用户另行决定A8（建议先降345题，后用具体连词位置限定题干）。未修被审文件，未推main、开PR、部署后端、小程序上传/提审/发布、修改数据库或外部业务服务。

与提示要求的执行差异：只有提示中的JSONL SHA一位不符，已以Git字节和两次生成独立核实；生成在仓库外的相同提交完整快照以遵守只读边界，缓存复用已披露。其余指定检查均完成，没有跳过或用自查数字替代实测。

CI将在本报告及交接提交/推送后核实，test和lint分开记录；这里的本机通过不能冒充GitHub CI通过。
