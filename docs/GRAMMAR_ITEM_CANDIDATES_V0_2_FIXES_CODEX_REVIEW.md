# 语法候选题 v0.2 审核修复 — Codex 独立复审

审核日期：2026-10-19，Mac / Asia/Shanghai。审核方：Codex，未参与本轮 Claude 修复，没有委派子 agent、调用大模型 API 或修改被审核代码/数据。

## 结论：不通过

**本轮新增记录 1 项阻断、3 项应修、3 项建议。** 阻断 R1 是上一轮 F1 未完全修复：T6 的遗漏已清零，但 T1 的干扰项越出原标注范围时，没有把风险传到题目状态，仍有 3 道 auto_pass，其中两道把解析器误挂的 `not` / `into` 当成动词单位。R2 是单引号修复引入的真实范围回归；R3 是新抽样及全库扫描发现的漏网 OCR 断词；R4 是“短语严格检查多降 2,333 道”无法按当前规则复现，应更正数字或给出另一口径的可复现证据。

测试、临时导入、既定回归例句、跨环境及双次生成复现均通过。它们证明实现可重复，不证明语言内容全部正确。30 道自动通过抽样：**28 道答案和高亮完整；1 道答案正确但原句不适合出题；1 道分类答案正确但高亮缺右括号**。不能把这个样本比例外推为全池错误率，也不能代替教师 360 题盲审。

### 上一轮 F1–F5 / S1–S4 的关闭状态

| 编号 | 独立复审结论 |
|---|---|
| F1 完整动词单位 | **部分解决，不能关闭**。T6 直接子节点遗漏 0；9 道点名题均补齐并降级；6,299 道共同 T1 答案不变；但 T1 干扰项漏传风险，见 R1。578 / 285 / 293 / 23 的原统计本身复现。 |
| F2 OCR 断词 | **原点名案例解决，质量缺口未关闭**。calcu lated 已整句拒绝，规则 6 句均有 OCR 问题；新增扫描找到至少 19 句空格断词/误拆复合词，16 句仍产生 44 道 auto_pass，见 R3。不是要求此启发式达到未知的 100% 召回率，而是交付抽样已有实际坏句。 |
| F3 从句漏直接引语 | **解决**。F-36c 的 contrast_clause 含完整 said 引语宾语；T2/T3 自动通过，T4 仍因关系词与对比标签不一致待复核。 |
| F4 同位语包含有限谓语 | **解决**。片名是 apposition，translates 部分改 predicate_fragment；整句拒绝，tagged_fragment 预期/实际均 37。 |
| F5 报告字段 | **解决**。109 个去重目标逐条与全量候选对应；before/after/added = 12,657 / 12,688 / 31；测试覆盖字段及去重。 |
| S1 单引号 | **未完全解决，并引入回归**。s' 的“两可”分支符合修复说明，但所有数字前的引号都被排除，真实电压引语被截短，见 R2；引语中的所有格仍可破坏配对，见建议 A2。 |
| S2 When it comes to | **解决**。adverbial_clause + 话题范围说明合理，不再误教时间关系。 |
| S3 couldn't 解释 | **解决**。改为假设条件下的可行性，保留原翻译合理。 |
| S4 存量 Ruff / datetime.UTC | **接受兼容性理由，非本轮修复阻断**。UTC 别名需要 Python 3.11+，生产 3.10.12 若执行该脚本会 import 失败。未连接生产核实版本，依据仓库既有交接；格式问题本身不受此兼容性理由解释，可留作存量治理。 |

## 审核现场与范围

- 执行树：`/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker`；分支 `codex/grammar-item-candidates`。先读目录链 AGENTS、CLAUDE、交接最新节、WORKLOG 顶部，并核对实际 Git。
- 执行用户指定的 fetch 和 `git merge --ff-only f9aebc7`，确认审核 HEAD 为 **`f9aebc765b9d78a1bc29a91baa294623ce743e2c`**，范围仅 **`8f273e9..f9aebc7`**。未合并 Claude 后续提交，没有 rebase。
- 开始及完成检查时任务树均干净。随后只新增本报告、更新 `docs/CODEX_HANDOFF.md` 与 `docs/WORKLOG.md`。此前首次审核记录及 Claude 修复记录均保持原样。
- 原项目 `/Users/zhouxin/Desktop/studytracker` 仍为 `main@6ded77d24586327ad94e151e172ae4811b4a2eed`，7 modified / 22 untracked 入口是其他工作，未覆盖、未切分支。
- 临时审计目录 `$AUDIT` = `/tmp/studytracker-grammar-v02-fixes-audit.GgWLmI`（macOS 上解析到 `/private/tmp`）。脚本、日志、输出、解析缓存、预览、SQLite 只在本机，不提交；文中保留方法、题号与结果供异机复现。
- 生成器在 `git archive` 导出的原样代码/输入上运行，使“重新生成”与“不覆盖被审核交付”同时成立。当前版本第一次没有缓存，完整解析 12,688 句；第二次使用首次缓存。8f273e9 也用该版本原样生成器重新生成；基线重跑复用前次审核的同环境缓存，句子文本完全相同，不冒称基线也冷启动。
- `claim mat`、14 个段首句点、51 个多句单元的后续修改不在审核范围，没有审其后续实现或合入其提交。发现的其他原文问题单独记录。
- 没有生产服务器/真实数据库操作，没有推 main、部署、PR、小程序上传/提审/发布。只有临时 SQLite 导入；没有调用大模型 API。

## 15 项检查结果

| # | 结果 | 实际命令或证据 |
|---:|---|---|
| 1 | 通过：17 files，3,851 insertions / 551 deletions；5 个允许的 Python 文件、4 个标注文件各一行替换、4 份交付、4 份文档。 | `git diff --stat 8f273e9..f9aebc7`、`--numstat`、逐文件 diff。 |
| 2 | 通过：所有保护路径差异为空。 | 下节 protected diff。 |
| 3 | 部分通过：T6 漏节点 0；T1 答案共同 6,299 题完全不变；9 题及两例解析误挂均核对；578（T1 285 / T6 293），仅该原因 23（10 / 13）。**另有 3 道 T1 干扰项越界未降级**。 | `probe_all.py`、`final_checks.py`；R1、九题明细。 |
| 4 | 无 ID 黑名单；全库词表在 limit 之前构造；动态 `limit=1` 的 34 句调用都收到完整 18,967 词型计数。6 命中均坏句；至少 19 句漏网，详见 R3。 | `scan_words.py`、`word_confirm.py`、`final_checks.py`；静态原文逐项核对。 |
| 5 | 四个单行 diff 均合理，未改原句/翻译/expressions；F3/F4/S2/S3 成分及教学解释通过；tagged_fragment actual=expected=37。 | `git diff 8f273e9..f9aebc7 -- data/reading_study/`，报告独立过滤统计。 |
| 6 | 通过：109 目标按 passage / sentence / raw tag span 去重，逐条 item_ids 集合一致；12,657 / 12,688 / 31 正确。 | `final_checks.py`；`tests/test_grammar_item_candidates.py:975`。 |
| 7 | **不通过**：数字引语造成一处实际范围变化，改变题号；只按共同 item_id 比较会漏掉。控制其他新规则不变、仅在内存换回旧引号函数，仍精确复现这一处。所有格/嵌套反例见 A2。 | `probe_all.py`、`quote_examples.py`；R2。 |
| 8 | 兼容性理由成立；本轮 5 Python 文件 Ruff 均通过。存量 format 可独立治理。 | Python 官方 datetime 文档、仓库交接；未访问生产。 |
| 9 | T3 1,638 / 仅此 1,382；T4 125 / 仅此 49，均复现。seed20261020 各抽 15：T3 12 明确不完整 / 1 明确误降 / 2 附加语归属两可；T4 14 明确不完整 / 1 两可。同一边界函数扩展至短语仅新增降级 **933**，非 2,333。 | `probe_all.py`、`strict_phrases.py`、下方 30 行明细。 |
| 10 | 通过：Mac 两次四文件字节一致；JSONL/XLSX 与提交版字节一致；两份报告各仅 Python 版本行不同。 | `final_checks.py`、双次完整 SHA-256 表。 |
| 11 | 通过：报告全部 13 条回归记录对象与修复前完全一致；逐句人工对照计划要求通过。 | `assert new_report['regression_cases'] == old_report['regression_cases']`，下方结果表。 |
| 12 | 通过：指定三模块 65 passed；Flask-only 完整 CI 列表 133 ran / 132 passed / 1 skipped，Node 通过；5 文件 Ruff check/format 通过；validator 317 valid / 0 errors，text fixes 0 未应用。 | 完整实际命令见下节；`unit.log`、`ci-tests.log`、`validator.log`。 |
| 13 | 通过：完整 main 快照先导入 created317，再导 f9aebc7 **updated25 / skipped292 / failed0**，317 rows；数据库 URI 明确断言为临时 SQLite。 | `import_snapshot.py`，main 固定 SHA 下文列明，非只换 data。 |
| 14 | seed20261020 每表 auto_pass 抽5，共30；28 完整正确，1 坏句，1 高亮缺括号。 | `sample_auto.py`，逐题表和方法见下文。 |
| 15 | 结构/盲审通过：7 sheets，六题型各60行；360行逐格等于 teacher_row；无 auto_pass/needs_review 字样；H2:H61 四项列表。七表只读渲染，未回写。 | `final_checks.py`、`render.mjs`。展示数据本身仍受 R1/R2/R3/A3 影响。 |

## 新问题清单

### R1 — 阻断：T1 干扰项越界未传播 verb_unit_outside_span

- 位置：`scripts/grammar_items/templates.py:317` 与 `:335`。main_distractors 使用完整单位，main_verb 却只对主句 root 检查 outside_span，没有检查干扰项来源的 raw span。
- 复现：重跑全量候选，对 T1 每个干扰项中心动词取 aux / auxpass / neg / prt 直接子节点，分别对照提供它的原始从句/非谓语标注范围。下列 3 题仍为 auto_pass、无该原因：

| 题号 | 来源 | 越界与语法判断 |
|---|---|---|
| gi_v02_eb01375e183f | ielts9_test3_p2 A-03 | 原 infinitive_complement `[73,107)` 从 close 开始，完整 `to close` 的 to 在 `[70,72)`；单位本身对，但按修复承诺应降级。对应 T6 已降级，T1 却遗漏。 |
| gi_v02_20551c6d1cef | reading_jijing_24_test_56_p3 B-03 | noun_clause `[193,242)` 是 `what would later be identified as vitamin content`；not 在 `[189,192)`，属于前面 `acids ... and not what ...` 的名词性对比，不是否定 identified。解析误挂后干扰项成为 `not / would / be identified`，仍自动通过。 |
| gi_v02_a3288babf979 | reading_jijing_71_test_1_p3 A-04 | relative_clause `[31,69)` 是 `which became North America and Eurasia`；into 在 `[17,21)`，属于主句 `broke up into Laurasia`，误挂成 became 的 prt。干扰项变成 `into / became`，仍自动通过。 |

- 578 的统计只覆盖主句单位及 T6 目标，不能证明所有 T1 干扰项也执行了降级。T1 正确答案范围没变不等于新增干扰项安全。
- 建议改法：收集每个干扰项来源 raw span 的越界风险，合并到 T1 reasons；保留 T1 答案兼容要求，不把“补完整”当成“解析一定对”。添加这三类（不定式 to、名词对比 not、错误 prt）回归测试。本轮仅报告。

### R2 — 应修：数字前单引号被一律当作撇号，真实题目范围退化

- 位置：`scripts/grammar_items/templates.py:68`；`ielts5_test1_p2` B-01；旧题 `gi_v02_96287b126ba9` → 新题 **`gi_v02_257090f44957`**，T3，仍 auto_pass。
- 原句讲 Milgram 实验电压开关，目标为 `with labels ranging from '15 volts of electricity (slight shock)' to '450 volts (danger - severe shock)'`。raw span 及旧目标是 `[101,205)`，新目标 `[101,203)`，末尾 `)'` 被截掉。
- 复现：按 passage / sentence / template / raw tag span 匹配两次真实生成候选；再从 8f273e9 以 AST 提取 single_quote_role、balance_single_quotes、close_quotes，仅在临时进程换回这三函数，保持新规则、新数据和同缓存不变重跑，全库仍仅该题恢复。变动是引号逻辑引起，也连带丢失了括号，不能只用“剔除引号后文本相同”作为检测条件。
- 原因：`after.isdigit()` 同时匹配年代缩写 `'80s` 和真正引语 `'15 volts ...'`。前者是省略撇号，后者不是。修复记录 `:17` 声称全库引号范围零变化，与实际不符。
- 建议改法：限定年代省略识别并结合成对引语上下文，加入带数字开头、括号及多个引语的真实回归；跨版本按稳定源标注定位，不能只比较范围派生的 item_id。继续禁止越过原标注边界补内容。

### R3 — 应修：OCR 断词过滤漏过新的交付坏句

- 位置：`scripts/grammar_items/checks.py:106`；抽样题 **`gi_v02_4f3d9fb9f71c`**，主句谓语数据行51 / Excel 行52，`reading_jijing_65_test_69_p2` G-02。该句有 `cow less steaks and chicken less drumsticks`，应按语境写作 cowless/chickenless（或保留合法连字符）。主句答案 should be allowed 正确，原文仍不适合直接出题。
- 复现：按下文种子/顺序抽样；以 `/usr/share/dict/words` 检索相邻词拼接后为词、至少一片段非词的组合，再检查全库标注中的排印提示、逐句独立读语境，并对照同篇 static 原文。没有只依赖 Claude 已列的 6 例。确定的 19 句列表见下节；19/19 的坏字符串都在相应 static JSON 中。
- 规则 `max(freq(a), freq(b)) <= 2 and freq(a+b) >= 1` 极保守：fun 的高频挡住 fun gicide，al 挡住 nas al，peasant 在全库从未正确拼写使 peas ant 无法命中。这是规则召回的结构性限制。19 句中 16 句仍生成共 44 道 auto_pass；这只是本次人工确认的下界，不是完整漏网总数估计。
- 建议改法：另行授权修复已确认的源文本，并给高风险拼写增加可审计词典/词形与上下文复核；不要把“两个片段都极罕见”当唯一来源质量保障，也不要按句 ID 黑名单封堵。扩大规则前仍需评估真实词组误伤，不可无差别拼接。

### R4 — 应修：2,333 道短语降级的证据与当前规则不一致

- 位置：`docs/GRAMMAR_ITEM_CANDIDATES_V0_2_FIXES.md:26`。
- 复现：在临时 Python 进程取得 classify_clauses 的函数源码，仅把 `if kind != "phrase":` 改为 `if True:`，调用同一 collect、f9aebc7 数据与缓存；断言前后 item_id 集合完全相同，再比较 status/reasons。结果新增 boundary_mismatch **934** 道，其中 **933** 道从 auto_pass→needs_review，另1道原已 needs_review。不是2,333。即使改成原始字符边界比较，auto_pass 不匹配数也只是1,047。
- 评价：不检查 T3 短语的决策仍合理——题目只问“不是从句”，句法树可能吞进 for 主语、并列非谓语等，不能直接把整个依存子树当该目标的唯一边界。但 933 也不能全部称作“误降”；需要人工抽样才有真假比例。
- 建议改法：修正文档为可复现的本实现口径；如2,333来自另一实验，补具体算法、基线、分母及脚本，并区分“新增待复核”与“确认误降”。本次没有改该被审核文档。

### A1 — 建议：边界降级适合作保守复核信号，不宜当作错误真值

- 位置：`templates.py:356`；T3 `gi_v02_1b42f742fdcbb`，ielts10_test1_p3 B-02。
- 复现：目标 `what contribution they make` 已是完整名词性从句；spaCy 子树还包含并列的 `and whether, two years after they join, they're still at the company`，因而降级。两从句可分别划，前者没有漏词。
- 30 个边界样本有 26 明确不完整、1 明确误降、3 附加语归属两可。将三类都转人工是可接受的保守策略；报告应保留区别。建议今后对并列从句、括注、结果附加语做单独评估；不能为提高自动率直接取消检查。

### A2 — 建议：含所有格的引语/嵌套引语仍会消耗错误的闭引号

- 位置：`templates.py:79`。给 close_quotes 传入完整 raw bounds，但输入目标末尾被 trim 掉一个闭引号：
  - `who wrote 'the students' books'` → 仍缺最后 `'`；
  - `who called it 'James' book'` → 仍缺最后 `'`；
  - `who quoted 'the students' 'great' books'` → 仍缺最后 `'`；
  - 对照 `who quoted 'the 'great' scientist'` 能补齐，不能以这个成功例说明嵌套情形全对。
- s' 后接小写词且已有未配对开引号时，算法把实际所有格当 close，提前消耗了开引号。四个精确合成字符串在本库出现次数均0；未把此合成风险计为额外真实坏题。真实语料中的数值引语问题另见 R2。
- 建议改法：识别所有格要结合短语结构/左右引语对，不单靠一个 opened/closed 计数器；无法确定时保持有界范围并转人工，补上述测试。

### A3 — 建议：目标内部括号应成对保留

- 位置：`templates.py:98`（只补引号）、`:362`（trim）；题 **`gi_v02_eec00568cf99`**，ielts20_test3_p2 A-01，T3 数据行12 / Excel 行13。
- 复现：raw `[97,160)` 含完整 `at the world-renowned Zoological Society of London (London Zoo)`；目标 `[97,159)` 少最后右括号，显示 `【at ... (London Zoo】)`。答案“不是从句”正确，内部标点范围不完整。属于基线已有展示问题，非此次新回归。
- 建议改法：在不越过 raw span 的前提下保留目标内部的成对括号；与“整个引语本来跨出从句”的12处既有情况不同，此处右括号在原标注内，可以安全补回。

## F2 的六个命中与漏网下界

| 来源 | 命中字符串 | 独立判断 |
|---|---|---|
| reading_jijing_38_test_22_p3 C-04 | competi tive | competitive 被拆开。 |
| reading_jijing_46_test_84_p1 E-01 | ambit ions | OCR 异常成立，但语境 `bright, ... and well-educated Japanese` 需要 ambitious，不是简单拼成 ambitions 就正确；排除合理，修原文时不能机械拼接。 |
| reading_jijing_85_test_12_p3 C-05 | calcu lated | calculated 被拆开，上一轮点名题已不生成。 |
| reading_jijing_9_test_81_p2 I-03 | contem porary | contemporary 被拆开。 |
| reading_jijing_9_test_81_p2 I-04 | implemen tation / envi ronmental | implementation / environmental 被拆开。 |
| reading_jijing_9_test_81_p2 I-08 | com prising | comprising 被拆开；同句另有 `residents front nearby towns`，语境应为 from。整句已排除。 |

下面“漏网”指未命中 suspected_split_word，不一定没有其他拒绝原因。复合词和专名均按实际语境核实；不声称只靠词典能自动判对。19句没有包含用户已排除本次审核的 claim mat、14段首句点或后续51单元拆分成果。

| 来源 | 坏字符串 → 按语境的词 | 该句 auto_pass 数 |
|---|---|---:|
| reading_jijing_13_test_6_p2 D-20 | peas ant → peasant | 2 |
| reading_jijing_26_test_72_p1 G-10 | fun gicide → fungicide | 0 |
| reading_jijing_26_test_72_p1 I-01 | peas ant → peasant | 0 |
| reading_jijing_84_test_73_p3 E-06 | nas al → nasal | 5 |
| reading_jijing_85_test_12_p3 B-02 | peas ant → peasant | 5 |
| reading_jijing_85_test_12_p3 I-04 | peas ant → peasant | 1 |
| reading_jijing_24_test_56_p2 I-01 | subscrip tions → subscriptions | 3 |
| reading_jijing_40_test_75_p3 D-04 | consider able → considerable | 2 |
| reading_jijing_44_test_29_p1 G-07 | al location → allocation | 2 |
| reading_jijing_46_test_84_p2 H-03 | over time → overtime（paid overtime，加班费） | 3 |
| reading_jijing_65_test_69_p2 B-03 | w hat → what | 3 |
| reading_jijing_65_test_69_p2 B-04 | w ant → want（两处） | 1 |
| reading_jijing_65_test_69_p2 D-01 | w ill → will | 5 |
| reading_jijing_65_test_69_p2 D-03 | throw n → thrown | 3 |
| reading_jijing_65_test_69_p2 E-05 | grow th → growth | 2 |
| reading_jijing_65_test_69_p2 G-03 | w ill → will | 1 |
| reading_jijing_65_test_69_p2 G-02 | cow less → cowless / chickenless（或规范连字符） | 5 |
| reading_jijing_76_test_43_p2 F-04 | Goldf inger → Goldfinger（同文建筑师姓名） | 0 |
| reading_jijing_77_test_16_p2 A-01 | may be → maybe（副词，不是谓语may be） | 1 |

扫描同时看到一些**不计入上述19句**的同类原文问题，可另行列修订清单：`reading_jijing_24_test_56_p2` C-04 的 `maxi- misers`；`reading_jijing_26_test_72_p1` K-02 的 `environ- mental`；`reading_jijing_40_test_75_p1` A-02/A-03/E-08/F-05/G-04 的 `authorita-tively / biog-raphy / Britan-nica / accom-plishments / rela-tionships`；`reading_jijing_40_test_75_p3` A-02/E-03/F-05 的 `some-thing / diagno-sis / symp-toms`；`reading_jijing_81_test_93_p2` B-02 的 `educa-tion`；`reading_jijing_85_test_12_p1` D-02/D-06 的 `travel- ling / super- market`。边界抽样另见 `reading_jijing_5_test_59_p2` E-03 的 `diers`（语境应 differs）、`reading_jijing_50_test_30_p2` D-04 的 `word out`（应 work out）。这些是源文本治理建议，没有修改源数据或据此扩展本次范围。

## F1 九道点名题与两例解析误挂

以下全部是新版 T6，均 needs_review 且带 verb_unit_outside_span；高亮按 parts 表示，插入语不算动词单位。

| 旧题号 | 新题号 | 完整单位 |
|---|---|---|
| gi_v02_88bfd8b15d26 | gi_v02_788e3e923f2e | 【could】, argues Angel, 【reduce】 |
| gi_v02_14238a86fcf3 | gi_v02_8f257f380cc3 | 【to cross out】 |
| gi_v02_69129d9bf252 | gi_v02_92d5f476d8a8 | 【are】, as I think you will soon see, 【not】 |
| gi_v02_8aa480f73c33 | gi_v02_9347e1c71174 | 【did】 this event, or events, 【take】 |
| gi_v02_7ff82ab4b444 | gi_v02_a85be189f7a7 | 【can put】 it all 【down】 |
| gi_v02_f38641df8872 | gi_v02_8cd573d803ad | 【to close】 |
| gi_v02_21d87055c7e2 | gi_v02_4d2e5989e120 | 【do not】, however, 【handle】 |
| gi_v02_50d6455ed0ff | gi_v02_742ed01b4a6f | 【do】, however, 【have】 |
| gi_v02_7836de3dae6a | gi_v02_c5686e4a3670 | 【are】 certainly 【not】 |

另外 `ielts16_test3_p1` G-04 的 `gi_v02_009ef4990a5a` 显示 sailed by，by 实际引出 noting；`ielts8_test3_p1` C-05 的 `gi_v02_e557ada3f3c8` 显示 to using，to 实际属于前面的 want it to。两题已转 needs_review，作为保留解析器证据、等待老师修正的候选可接受，不能把它们称为英语语法正确的完整单位或提升为自动通过。

## 第9项：30道仅因 boundary_mismatch 降级的逐题审核

方法：读取完整生成池，分别过滤 T3/T4 且 `reasons == ['boundary_mismatch']`；各池按 item_id 排序；新建一次 `random.Random(20261020)`，先抽T3的15道，再用同一 RNG 抽T4的15道。没有用Claude种子、没有在看到结果后重抽。判断根据完整英语句子及目标上下文，依存树仅用于解释降级原因。

“不完整”指原目标遗漏从句内部的修饰语、补语、并列成分等；“两可”指省略部分可能作为句外附加语，保守复核可以接受。T3 12/1/2，T4 14/0/1（不完整/误降/两可）。

| # | 题目编号 | 模板 / 来源 | 判定及理由 |
|---:|---|---|---|
| 1 | gi_v02_aae9e443732b | T3 · ielts9_test1_p2 D-24 | 不完整：漏 to conduct thorough search… 的补足内容 |
| 2 | gi_v02_f7dca9ed5c6d | T3 · reading_jijing_73_test_5_p3 I-02 | 不完整：as research reveals 漏其 that 宾语从句 |
| 3 | gi_v02_7670d06fb8e1 | T3 · ielts11_test2_p2 E-01 | 不完整：漏修饰 activity 的 that helped… |
| 4 | gi_v02_50cf0a485285 | T3 · reading_jijing_91_test_49_p1 B-03 | 不完整：漏 and thus requires… 并列谓语部分 |
| 5 | gi_v02_b5cb595285a5 | T3 · ielts19_test2_p2 A-03 | 不完整：漏 on social media following her withdrawal… |
| 6 | gi_v02_16d35661494c | T3 · ielts9_test1_p1 G-01 | 两可：thus making… 可作结果附加语，不能只凭子树断言 that 从句截短 |
| 7 | gi_v02_f77fd5a83e35 | T3 · ielts18_test3_p1 F-01 | 不完整：reports 漏 that… 引出的宾语内容 |
| 8 | gi_v02_ba9d2167c7b0 | T3 · ielts7_test4_p3 C-04 | 两可：漏括注 unpredictable noise；核心从句已完整 |
| 9 | gi_v02_1f2f13a7fd60 | T3 · ielts10_test1_p3 B-02 | 误降：what contribution they make 完整；子树额外包含并列 whether 从句 |
| 10 | gi_v02_375aa8fddf0f | T3 · reading_jijing_71_test_1_p1 H-04 | 不完整：漏 armament manufacture 后 the indirect cause… 的同位说明 |
| 11 | gi_v02_0c28f829f306 | T3 · reading_jijing_24_test_56_p2 C-04 | 不完整：漏 and those…as… 并列对比部分 |
| 12 | gi_v02_78ca26182b09 | T3 · ielts11_test3_p2 A-06 | 不完整：漏修饰 challenges 的 that would… |
| 13 | gi_v02_bf8d04c24a11 | T3 · ielts15_test4_p2 F-03 | 不完整：漏 including those… 对 regions 的补充说明 |
| 14 | gi_v02_4d3b424cb6dd | T3 · reading_jijing_73_test_5_p3 B-03 | 不完整：漏修饰 rainfall 的 that was turning… |
| 15 | gi_v02_177d430a907c | T3 · reading_jijing_73_test_5_p2 C-06 | 不完整：漏 and … more intriguing 的并列表语 |
| 16 | gi_v02_4b8d459f58f8 | T4 · reading_jijing_32_test_20_p2 H-02 | 不完整：漏修饰 activities 的 that… |
| 17 | gi_v02_77bd71a8813d | T4 · reading_jijing_48_test_21_p1 A-02 | 不完整：remind themselves 漏 how wealthy… 的内容 |
| 18 | gi_v02_1b42f742fd95 | T4 · ielts8_test4_p3 B-10 | 不完整：漏 if mishandled，限定不易打碎的条件 |
| 19 | gi_v02_96a08199f3b9 | T4 · ielts7_test2_p1 H-35 | 不完整：漏 with successive floors… 对taper的具体说明 |
| 20 | gi_v02_43d70558700c | T4 · reading_jijing_83_test_95_p1 G-01 | 不完整：漏 sounds 后 of some English words |
| 21 | gi_v02_a53d315eca98 | T4 · reading_jijing_13_test_6_p1 E-04 | 不完整：satisfied 漏 that… 内容从句 |
| 22 | gi_v02_b2e130df93e4 | T4 · ielts9_test1_p2 B-13 | 不完整：漏 in case… 修饰保持开放心态的目的/预防情形 |
| 23 | gi_v02_8abca53ba745 | T4 · reading_jijing_5_test_59_p2 E-03 | 不完整：漏 goods 后 which… 定语从句；另见原文 diers |
| 24 | gi_v02_41102fad2ef1 | T4 · reading_jijing_40_test_75_p2 B-02 | 不完整：漏 and spend time there… 并列部分 |
| 25 | gi_v02_27eb82d0bfd8 | T4 · reading_jijing_83_test_95_p1 B-01 | 不完整：漏 Alex 后 who died… 修饰语 |
| 26 | gi_v02_12c4fdbfdcbb | T4 · ielts7_test3_p1 F-01 | 不完整：漏破折号后 forcing house of intelligence 的同位说明 |
| 27 | gi_v02_0b75cf1110ef | T4 · reading_jijing_46_test_84_p2 H-02 | 不完整：漏 work 后 such as… 举例 |
| 28 | gi_v02_29fde941bf55 | T4 · reading_jijing_50_test_30_p2 D-04 | 不完整：漏 cones 后 from which…；另见原文 word out |
| 29 | gi_v02_20a9e4df5e92 | T4 · reading_jijing_32_test_20_p2 F-03 | 不完整：漏 i.e. setting… 对 label 的补充说明 |
| 30 | gi_v02_4f479ebce168 | T4 · ielts7_test2_p1 G-34 | 两可：transmitting energy… 可作碰撞结果或主句附加语；保守复核合理 |

短语免检的独立验证：精确实验采用现有 boundary_reasons，得到934新增原因、933新增降级。另从这933题中查看8个实例，看到 `to attack this coastal city's elm population` 的子树额外含 for 引导主语、`making such initiatives sustainable` 的子树额外含并列 expanding，均说明依存子树未必等于本题短语目标。这里只作边界语义诊断，不据8例估计全体误降率。

## 第14项：30道自动通过题抽查

方法：读取提交版 `review_batch_v0_2.jsonl`；按原文件顺序保留各模板 pool_status=auto_pass 的50行；新建另一个 `random.Random(20261020)`，按 T1→T6 顺序各 `sample(pool,5)`。表中行号是 Excel 行号（review_row + 1，含表头）。这与边界样本使用独立 RNG，互不影响。

| # | 题目编号 | 工作表 | Excel行 | 判定 |
|---:|---|---|---:|---|
| 1 | gi_v02_2bf367809dac | 主句谓语 | 61 | 正确：was |
| 2 | gi_v02_c6a67235e33c | 主句谓语 | 38 | 正确：completed |
| 3 | gi_v02_47809a4c0612 | 主句谓语 | 59 | 正确：may seem |
| 4 | gi_v02_4f3d9fb9f71c | 主句谓语 | 52 | 句子不适合出题：should be allowed 答案对；cow less / chicken less 原文断词，R3 |
| 5 | gi_v02_7cd55e89e208 | 主句谓语 | 29 | 正确：is |
| 6 | gi_v02_e1e760f943b6 | 从句边界 | 18 | 正确：that…brains 全部 |
| 7 | gi_v02_9be6813e550c | 从句边界 | 37 | 正确：how wonderful they are |
| 8 | gi_v02_ce2766b4c054 | 从句边界 | 5 | 正确：while…steep mountains 全部 |
| 9 | gi_v02_f9c28e0f628a | 从句边界 | 51 | 正确：because…repayments 全部 |
| 10 | gi_v02_e058de9598d2 | 从句边界 | 38 | 正确：where…1530s 全部 |
| 11 | gi_v02_1c1b253bf45c | 从句类型 | 8 | 正确：If… 状语从句 |
| 12 | gi_v02_eec00568cf99 | 从句类型 | 13 | 答案正确但高亮标点不完整：介词短语，缺右括号，A3 |
| 13 | gi_v02_5ca9a368e5e5 | 从句类型 | 4 | 正确：关系从句 it wasn’t supposed to go |
| 14 | gi_v02_e6e23fd687aa | 从句类型 | 27 | 正确：that…prices 定语从句 |
| 15 | gi_v02_f52228a19d63 | 从句类型 | 42 | 正确：built…Billings 为非谓语 |
| 16 | gi_v02_b668249ed6c6 | 状语关系 | 16 | 正确：even if 让步（按教师约定） |
| 17 | gi_v02_ba6976615910 | 状语关系 | 6 | 正确：although 让步 |
| 18 | gi_v02_a0c4882fb41a | 状语关系 | 18 | 正确：though rare 省略让步 |
| 19 | gi_v02_d0769e56d9a4 | 状语关系 | 33 | 正确：because 原因 |
| 20 | gi_v02_6a5c8b29a7d8 | 状语关系 | 7 | 正确：though 让步 |
| 21 | gi_v02_769a562ff8bc | 完整主语 | 43 | 正确：Silbo |
| 22 | gi_v02_335cadc930ac | 完整主语 | 18 | 正确：International commerce |
| 23 | gi_v02_304ee99e284e | 完整主语 | 51 | 正确：Analysis |
| 24 | gi_v02_1dbcd4174d83 | 完整主语 | 53 | 正确：It |
| 25 | gi_v02_d469d79f1bbe | 完整主语 | 41 | 正确：The type II |
| 26 | gi_v02_1d2386b88dd5 | 动词身份 | 19 | 正确：called 非谓语 |
| 27 | gi_v02_2c0831ffd88c | 动词身份 | 14 | 正确：were 主句谓语 |
| 28 | gi_v02_40ebf6a9d933 | 动词身份 | 5 | 正确：joined 主句谓语 |
| 29 | gi_v02_d053f395f0a3 | 动词身份 | 4 | 正确：to convince 非谓语 |
| 30 | gi_v02_4a920bc2c9c4 | 动词身份 | 15 | 正确：analyzed 从句谓语 |

## 既定回归逐项核对

两版实际生成报告的 regression_cases 全对象（含题号、答案、范围、状态、原因、拒绝记录）完全相等；再人工对照两版计划逐例核对：

| 来源 | 核对结果 |
|---|---|
| ielts7_test3_p1 K-03 | 整句 too_short + unbalanced_quotes_or_brackets，无自动通过。 |
| ielts8_test4_p1 C-04 | he felt… 不成为从句题；T1/T5/T6主句候选因 no_main_verb_tag 拒绝；to introduce… 的T3及T6非谓语题自动通过，符合单题隔离。 |
| reading_jijing_76_test_43_p2 H-02 | T5 subject_mismatch 待复核；had lost out 的T1/T6自动通过。 |
| reading_jijing_73_test_5_p2 F-05 | tagged_fragment + unknown_span 整句拒绝。 |
| reading_jijing_56_test_64_p2 C-01 | clause_attached_to_conjunction 整句拒绝。 |
| ielts13_test2_p2 C-04 | 同上，是计划明确接受的保守拒绝。 |
| reading_jijing_91_test_49_p3 D-02 | occurred 主句题、attended / representing 非谓语题自动通过；无需强求该句所有其他目标也自动通过。 |
| ielts11_test3_p2 A-04 | that apply…all migrations 定语从句边界自动通过；主句 has identified / 主语也正常。 |
| ielts15_test2_p3 D-05 | that…low-status individuals 的完整名词性从句边界自动通过。 |
| ielts4_test2_p2 G-31 | T2/T3/T4 均因 possible_relative_adverb 待复核。 |
| ielts6_test3_p1 C-06 | T6完整【was born】自动通过；T1因两个was的定位歧义仍待复核，与基线相同。 |
| reading_jijing_88_test_98_p2 G-04 | 第一句及引语范围完整，相关T2/T3自动通过。 |
| reading_jijing_88_test_98_p2 G-04b | 新句独立且完整，that…和in which…两个目标自动通过；glued_sentence_boundary全库仍0。 |

## 重新生成的环境与 SHA-256

Mac本地：Python **3.13.3**；spaCy **3.8.16**；`en_core_web_trf` **3.8.0**；torch **2.14.1**（CPU）；openpyxl **3.1.5**；生成种子 **20261018**（抽样种子另为20261020）；`pip check` 无冲突。使用任务树 `.venv-grammar-tools`，没有往生产运行环境安装分析依赖。

语料317篇 / 12,688句；49,623候选；1,437整句拒绝。完整T1–T6 auto_pass / needs_review 分别5922/377、4772/2397、11540/3176、396/637、5370/737、12738/1561，与提交报告一致。

| 文件 | 第一次（冷缓存）SHA-256 | 第二次SHA-256 |
|---|---|---|
| generation_report_v0_2.json | `62052f21b8284823597e85a25a1edbdd8aae8d6086cbea5be151b1f45dd918ca` | `62052f21b8284823597e85a25a1edbdd8aae8d6086cbea5be151b1f45dd918ca` |
| generation_report_v0_2.md | `68607f3ad5f81e8b5a5a844bb2cf98080cf57ede85bc439dfbb309a96c8a858a` | `68607f3ad5f81e8b5a5a844bb2cf98080cf57ede85bc439dfbb309a96c8a858a` |
| review_batch_v0_2.jsonl | `7d36e93cc62e278a331e6869df177548cf21284b1c78948e9a84e0e1b4e58636` | `7d36e93cc62e278a331e6869df177548cf21284b1c78948e9a84e0e1b4e58636` |
| review_batch_v0_2.xlsx | `a0c7ebde00ba736080256294d01f32b1bd4d1adf5fd7ad2e656e68a29531f05a` | `a0c7ebde00ba736080256294d01f32b1bd4d1adf5fd7ad2e656e68a29531f05a` |

JSONL/XLSX与提交版字节相同。报告JSON唯一差异第16行，Markdown唯一差异第36行：`python: 3.11.15` → `3.13.3`，未标准化或忽略任何其他差异。提交版两报告SHA分别 `780fb4d5aa5d251b509204b7a9bee3d73f1bd21a23558c6ee1d1384a0eb79670`、`040f9e27481da84c80cbbe8811fe930491f9e0f5a9209a274580b51e9f5b0cd9`。

## 实际运行命令与复现说明

命令工作目录为任务树。辅助脚本仅在 `$AUDIT`；下述反事实实验只改临时进程内的函数对象，没有写入任何被审核 Python 文件。

```sh
git fetch origin claude/word-memorization-system-eval-55v2y5
git merge --ff-only f9aebc7
git status --short --branch
git log -5 --oneline
git rev-parse HEAD
git diff --stat 8f273e9..f9aebc7
git diff --numstat 8f273e9..f9aebc7
git diff 8f273e9..f9aebc7 -- data/idictation_reading_jijing/raw.json static/ api/ models.py app.py miniprogram/ .github/
git diff 8f273e9..f9aebc7 -- data/reading_study/

AUDIT=/tmp/studytracker-grammar-v02-fixes-audit.GgWLmI
.venv-grammar-tools/bin/python -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_grammar_graph_draft -v
.venv-grammar-tools/bin/python scripts/validate_reading_study.py
.venv-grammar-tools/bin/python scripts/reading_jijing_text_fixes.py --check
.venv-grammar-tools/bin/python -m pip check
.venv-grammar-tools/bin/python -m venv "$AUDIT/flask-only"
"$AUDIT/flask-only/bin/python" -m pip install --cert /etc/ssl/cert.pem Flask==3.1.3
"$AUDIT/flask-only/bin/python" -m unittest tests.test_miniprogram_guest_access tests.test_miniprogram_dictation_grouping tests.test_inventory_toefl_materials tests.test_organize_toefl_materials tests.test_extract_toefl_answer_keys tests.test_map_toefl_answers_to_practice_docs tests.test_import_toefl_official_reading tests.test_reading_vocab_grading tests.test_stats_utils tests.test_grammar_graph_draft tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes -v
/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tests/test_dictation_spell_queue.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check --config 'extend-exclude=[]' scripts/generate_grammar_candidates.py scripts/grammar_items/checks.py scripts/grammar_items/templates.py scripts/grammar_items/reporting.py tests/test_grammar_item_candidates.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff format --check --config 'extend-exclude=[]' scripts/generate_grammar_candidates.py scripts/grammar_items/checks.py scripts/grammar_items/templates.py scripts/grammar_items/reporting.py tests/test_grammar_item_candidates.py

git archive f9aebc7 scripts/grammar_items scripts/generate_grammar_candidates.py api/__init__.py api/reading_study_glossary.py data/reading_study data/grammar_graph | tar -x -C "$AUDIT/source"
PYTHONDONTWRITEBYTECODE=1 .venv-grammar-tools/bin/python "$AUDIT/source/scripts/generate_grammar_candidates.py" --seed 20261018
# 首次四份交付复制到 $AUDIT/first-files 后，再执行同一命令
PYTHONDONTWRITEBYTECODE=1 .venv-grammar-tools/bin/python "$AUDIT/source/scripts/generate_grammar_candidates.py" --seed 20261018
git archive 8f273e9 scripts/grammar_items scripts/generate_grammar_candidates.py api/__init__.py api/reading_study_glossary.py data/reading_study data/grammar_graph | tar -x -C "$AUDIT/before"
PYTHONDONTWRITEBYTECODE=1 .venv-grammar-tools/bin/python "$AUDIT/before/scripts/generate_grammar_candidates.py" --seed 20261018
.venv-grammar-tools/bin/python "$AUDIT/probe_all.py"
.venv-grammar-tools/bin/python "$AUDIT/strict_phrases.py"
.venv-grammar-tools/bin/python "$AUDIT/scan_words.py"
.venv-grammar-tools/bin/python "$AUDIT/word_confirm.py"
.venv-grammar-tools/bin/python "$AUDIT/quote_examples.py"
.venv-grammar-tools/bin/python "$AUDIT/sample_auto.py"
.venv-grammar-tools/bin/python "$AUDIT/final_checks.py"
/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node "$AUDIT/render.mjs"

git fetch origin main
git archive cc6323e0cfa85342a34711480eac9def9c3fefaf | tar -x -C "$AUDIT/main"
/Users/zhouxin/Desktop/studytracker/.venv/bin/python "$AUDIT/import_snapshot.py" "$AUDIT/main"
/Users/zhouxin/Desktop/studytracker/.venv/bin/python "$AUDIT/import_snapshot.py" /Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker
git diff --check
```

main 快照固定为本次 fetch 得到的 `cc6323e0cfa85342a34711480eac9def9c3fefaf`，完整导出代码/static/data。两个独立 Python 进程分别从各自 root 导入真实 importer，断言模块路径；最小 Flask app 显式传入 `sqlite:////tmp/studytracker-grammar-v02-fixes-audit.GgWLmI/main-to-fix.sqlite`，断言实际engine URL，只建临时表。main首导created317，再导当前updated25/skipped292/failed0/created0/ignored0。没有只替换main的data而复用修复后的static。

Flask-only仅装Flask及传递依赖；缺openpyxl的写表测试按设计跳过，在完整语法环境已运行通过。Ruff显式清空extend-exclude以免scripts默认被忽略。测试结果为65 passed；轻量133 ran/1 skipped，不将skip误计为通过。

引号对照按源标注键匹配，避免新范围改变题号后被漏掉。原样新旧生成共有39个目标范围差异：38个T6动词单位、1个数字引语。然后控制其他新逻辑不变，独立证明这1个来自引号函数。辅助脚本曾仅比较“去引号后文本”而未捕获连带括号变化，后改为比较全部start/end/text并做上述控制实验；报告使用完整复跑结果。

短语反事实的关键步骤可在新审计进程复现：`inspect.getsource(templates.classify_clauses)`，仅替换一处 `if kind != "phrase":`，`exec` 到该模块全局字典的副本；将产生的函数绑定到该进程的templates.classify_clauses后调用collect。断言item_id集合不变，再计数 `old.status == 'auto_pass' and new.status == 'needs_review'`，结果933。没有把语义未知的边界差异一概当错。

关于S4：[Python官方文档](https://docs.python.org/3/library/datetime.html#datetime.UTC) 明确 `datetime.UTC` 在3.11加入。因此拒绝机械替换为这个别名有依据；不能据此免除所有未来格式治理。本轮生产版本只引用已有记录，没有越权访问生产。

## 与用户要求的差异、未验证项及交接

- 15项要求均完成；没有因环境障碍跳过检查，也没有替换用户指定的审核终点。实际结果未满足预期之处已列R1–R4及样本表，未将测试成功写成质量通过。
- 生成在该提交原样临时导出目录运行，避免覆盖被审核文件；4交付均做原字节比较。基线8f的重跑使用已有同环境缓存，当前f9aebc7首次为真正冷启动。
- 仅审核和报告，没有修复R1–R4。教师360题尚未完成；Claude在f9aebc7之后的改动未审、未合入。不得把本报告当成入库/生产发布批准。
- 本轮交接更新于CODEX_HANDOFF、WORKLOG最新节；最终提交与推送、CI结果在下方记录。临时脚本/缓存/SQLite/预览只在本机；审核记录随任务分支推送后可跨电脑获取。

## 提交与 GitHub CI

- 审核正文提交 **`0eedc0b7827f331ad4eacb81e4d89fdd569ae8d8` 已 commit/push** 至 `origin/codex/grammar-item-candidates`，`git ls-remote` 确认远端相同。该提交只含三份获准文档，没有skip标记。
- [GitHub CI 39208956728](https://github.com/KB77GG/studytracker/actions/runs/39208956728)：headSha等于上述提交，completed / **success**；test job **success**，133 ran /132 passed /1 skipped，Node spelling queue **success**。
- lint job **failure**，Ruff check报仓库存量问题，format step **skipped**。从日志提取错误路径，与本次被审核的改动文件集合交集为空；CI配置将lint设为continue-on-error。不能把整体success写成全部检查通过。本轮5个Python文件的显式Ruff check/format均通过。
- 核实命令：`gh run view 39208956728 --json status,conclusion,headSha,jobs,url`、`gh run view 39208956728 --log`；完整日志存本机 `$AUDIT/github-ci-first.log`。
- 本节及交接由后续纯文档提交补记，另校正正文两处Excel行号（题号及抽样表未变）。该后续提交也不带skip标记，最终回复前核对其远端HEAD和CI。被审核代码/数据始终保持f9aebc7；最后HEAD以 `git rev-parse HEAD` 和 `git ls-remote origin refs/heads/codex/grammar-item-candidates` 为准。
