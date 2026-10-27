# 语法候选题 v0.2 — 针对 Codex 独立审核的修复记录

- 审核来源：`docs/GRAMMAR_ITEM_CANDIDATES_V0_2_CODEX_REVIEW.md`（审核提交 `8f273e9`，结论“不通过”：1 阻断、4 应修、4 建议）。
- 修复方：Claude（云端会话，分支 `claude/word-memorization-system-eval-55v2y5`，已快进到 `8f273e9` 后修复）。
- 结论：F1–F5 全部修复；S1–S3 采纳；S4 说明不修的原因。复抽时又发现同类问题（T3/T4 从句目标被截短），也一并修了。
- **独立性说明**：本轮仍是同一方修复、同一方检查。建议再让 Codex 或老师按本文“验证”一节复核，再把抽查表交给老师。

## 逐条处理

| 编号 | 处理 | 结果 |
|---|---|---|
| F1 阻断 | T6 目标和 T1 干扰项改用完整依存动词单位（aux / auxpass / neg / prt），不再被原标注边界截断。T1 答案按计划保持不变，仍限定在原标注内；只要完整单位有成分落在原标注外，T1 和 T6 都加 `verb_unit_outside_span`，降为 needs_review。 | Codex 列出的 9 道全部变为 needs_review，并显示完整单位，如 `【could】, argues Angel, 【reduce】`、`【do not】, however, 【handle】`、`【did】 … 【take】`、`【can put】 it all 【down】`；`to cross out`、`to close` 两道 T6 也已显示 to。全库有 578 道题带这一原因（T1 285、T6 293），其中 23 道（T1 10、T6 13）只因这一条从自动通过降级。新增回归测试覆盖插入语加否定（`do not, however, handle`）、倒装（`did … take`）和小品词（`can put it down`）；不定式 to 沿用 v0.2 已有测试 |
| F2 应修 | 新增整句过滤 `suspected_split_word`：两个相邻词只隔一个空格，各自在全库最多出现 2 次，拼起来却是全库出现过的词。这是通用规则，不按句子 ID 列黑名单。 | 命中 6 句，人工逐句确认都是 OCR 断词：`competi tive`、`ambit ions`、`calcu lated`、`contem porary`、`implemen tation`/`envi ronmental`、`com prising`。`gi_v02_c03ab3d84792` 已不再生成。原文没有改，修原文需另行授权 |
| F3 应修 | 16_97_p2 F-36c 的 contrast_clause 延伸到引语末尾，direct_speech 仍作为内层成分。 | T2、T3 自动通过，范围为 `when I could have said to the clients: 'Why don't I give that to you in 48 hours?'`；T4 因 when 不能直接对应“对比”而需人审，符合预期 |
| F4 应修 | 71_1_p2 E-01 的 apposition 只保留片名 `'Lo Scopone Scientifico'`；`translates as 'Scientific Scopone'` 改为 predicate_fragment，难点里说明缺 which。sentence 原文不变。 | 整句由 `tagged_fragment` 排除，该过滤的命中数从 36 变为 37，报告的预期值同步改为 37 |
| F5 应修 | 报告新增 `possible_relative_adverb.targets`（按 passage / 句子 / 目标去重，附题号），`resplit` 新增 `sentences_before` / `sentences_after` / `added`。 | 109 个目标逐条列出；拆句前 12,657 句、拆句后 12,688 句、新增 31 句。新增字段有测试覆盖 |
| S1 建议 | 单引号识别：后面紧跟数字（`'80s`）和词中撇号不再当作引号。`s'` 后接空格和小写词既可能是所有格（`students' books`），也可能是引号术语的结束（`'megacities' and`，全库约 50 处），所以记为“两可”：范围内有未配对的开引号时算结束引号，否则算所有格。第一版把它一律当所有格，重生成后发现 9 道题的引号术语又被切掉右引号（如 `This 'megalopolis`），已改正。 | Codex 的反例 `'The students' books'` 不再只补左侧引号：`s'` 被识别为所有格后，范围内没有不成对的引号，两侧都保持原标注（补引号只修被切开的引号，不额外加外层引号）。与 Codex 审核的版本相比，全库没有任何题的引号范围发生变化。新增复数所有格、人名所有格、年代缩写、词中撇号、引号术语以 s 结尾的测试 |
| S2 建议 | 18_53_p2 E-01c 的 time_clause 改为 adverbial_clause，难点改为“引出话题范围，并不表示时间”。 | 以后引号处理即使变化，这句也不会变成“时间”关系题 |
| S3 建议 | 73_5_p1 H-01b 的 couldn't 解释改为“假设条件下的可行性”，并和对已发生事实的否定推测区分开。 | 翻译不变 |
| S4 建议 | 不修。`scripts/build_reading_test_practice.py` 的 UP017 和格式问题是存量问题。按 UP017 改成 `datetime.UTC` 需要 Python 3.11 以上，而生产环境是 Python 3.10.12（见交接文档），改了会让构建脚本在生产上跑不起来。 | 本轮改动的 5 个 Python 文件 `ruff check` 和 `ruff format --check` 均通过 |

## 同类问题：T3 / T4 从句目标被截短

复抽时发现，T3（判断从句类型）和 T4（判断状语从句关系）的【】有时只框住了从句的一部分，例如漏掉从句内部的定语从句（`… previous conditions` 后面的 `which we still see today`），或漏掉宾语后面的补足成分（`their own ability` 后面的 `to explore and embrace …`）。T2 早就要求目标和句法树的从句范围一致，T3、T4 却没有。

- 处理：T3 的从句类目标和 T4 的目标，现在也必须和句法树的从句范围一致，不一致时加 `boundary_mismatch`，降为 needs_review。短语和非谓语目标不检查，因为它们的边界本来就不严格。（更正：这里原写“严格检查会误降 2,333 道”，无法复现。第一轮复审按本实现把同一检查扩展到短语，新增降级 933 道，另 1 道原已待人审；这些是新增的待复核题，不全是误降。）
- 影响：T3 有 1,638 道题带这一原因，其中 1,382 道只因这一条降级；T4 有 125 道带这一原因，其中 49 道只因这一条降级。
- 1,638 道 T3 的分布：约 40% 是【】漏掉了从句内部的从句或并列部分，约 43% 是在更深处截断（例如漏掉宾语补足成分，或漏掉修饰从句内某个词的定语从句），约 16% 是漏掉了整个状语或介词短语。另有 3 道是【】超出了从句范围，其中一道把独立句 `Consequently, an increasing number of scientists are beginning to explore the alternatives` 标成了结果状语从句，原答案“状语从句”本身就是错的，这次检查把它拦住了。
- 不增加老师工作量：抽查表固定 360 行，降级只改变题目进入哪个池子。

## 修复后统计（auto_pass / needs_review / rejected）

| 模板 | 修复前 | 修复后 |
|---|---|---|
| main_verb_tap | 5935 / 367 / 6386 | 5922 / 377 / 6389 |
| clause_boundary | 4773 / 2400 / 2784 | 4772 / 2397 / 2791 |
| clause_type_classify | 12929 / 1796 / 1430 | 11540 / 3176 / 1437 |
| adverbial_relation | 446 / 589 / 2661 | 396 / 637 / 2668 |
| subject_span | 5374 / 737 / 6577 | 5370 / 737 / 6581 |
| finite_or_not | 12755 / 1553 / 6572 | 12738 / 1561 / 6575 |

全库 317 篇、12,688 句，候选题从 49,654 道变为 49,623 道（断词 6 句和 F4 那一句被整句排除）。整句排除从 1,430 句变为 1,437 句。抽查表仍是 360 行，约 180 分钟。

## 验证

| 检查 | 结果 |
|---|---|
| Codex 点名的题 | F1 的 9 道均为 needs_review，并显示完整单位；F2 的源句被 `suspected_split_word` 排除；F3、F4 见上表 |
| 回归例句 | 计划 B5 和 v0.1 第 11 节的全部例句，结果和修复前一致，全部符合预期（正例 A-04、D-05、G-04、G-04b 仍自动通过；C-06 的 T1 因句中有两个 was 而需人审，修复前也是如此） |
| 复抽 30 题 | 按 Codex 的方法，在新抽查表上用种子 20261019，从每个工作表的 50 道 auto_pass 中各抽 5 道。30 道答案全部正确；第 9 题 `gi_v02_22f334bf1f4e` 的答案正确，但原句有 OCR 错字（见“遗留”） |
| 可复现 | 连续两次生成，7 个文件逐字节一致；`review_batch_v0_2.jsonl` SHA-256 `7d36e93cc62e…`，`review_batch_v0_2.xlsx` `a0c7ebde00ba…`，`generation_report_v0_2.json` `780fb4d5aa5d…` |
| 测试 | 出题器测试 50 项（本轮新增 8 项），只装 Flask 的 CI 列表 133 项运行，1 项按设计跳过；Node 拼写测试通过；`tests.test_reading_study` 22 项通过 |
| 数据 | `validate_reading_study.py` 0 错误；`reading_jijing_text_fixes.py --check` 显示 0 条未应用。临时库先用 main 的完整快照导入，再导入本分支，结果 updated=25 / skipped=292 / failed=0。4 句标注修改都落在原本就要更新的 25 篇里 |
| Ruff | 本轮改动的 5 个 Python 文件 check 和 format 均通过 |

## 第一轮遗留（已在第二轮处理）

第一轮留下三项待用户决定：`claim mat` 错字、14 个段首多余句点、51 个“一条里含多句”的单元。用户 2026-10-19 决定：加修订、修原文并排除、重新拆句，处理结果见下一节。

## 第二轮（2026-10-19，用户决定的三项）

逐句记录：`docs/READING_STUDY_RESPLIT_2026-10_ROUND2.md`（由脚本生成，列出原句、原文修改、修改后的句子和翻译）。

### 原文与阅读解析

| 项目 | 处理 | 结果 |
|---|---|---|
| claim mat | 修订表加 `claim mat the image` → `claim that the image`；B-09 补了 claim 的宾语从句标注，删掉“必须保留 mat”的说明 | 1 句 |
| 段首多余句点 | 原文中段落标号被删后留下了 `. `，修订表加 14 条，删掉句点；`. the prerequisites` 同时改成大写 The。同一批句子里另有 2 处明显错字一并修订：`Galloping` → `galloping`、`resources and managed` → `resources are managed` | 14 句；难点里“句首句点为源文异常”之类的过时说明全部改写 |
| 51 个多句单元 | 逐个判断后分四类处理 | 见下表 |

| 51 个单元的分类 | 数量 | 处理 |
|---|---:|---|
| 确实是多句 | 34 | 拆成 72 句（新增 38 句），重新写翻译、结构、难点和表达。`ielts4_test4_p1` C-14 的末尾 `Yessis believes that U.S.` 是旧拆句在缩写处断开造成的，并到 C-15 句首 |
| 原文把逗号误写成句点 | 9 | 不拆句，修订表改原文（如 `his brother. Will, were` → `his brother, Will, were`、`In fact. Hooker` → `In fact, Hooker`），顺带修正同句的 `ranffian`、`anil`、`I996` 等错字；`challenge.' Perhaps` 改为 `challenge. 'Perhaps` 并补上段末缺的右引号 |
| 规则误报 | 7 | 不改数据，改规则：4 个列表编号（`1. Valid …`）、2 个“引语问句 + 说话人”（`"What's different?" Pepperberg asked.`）、1 个 `Mt. Cook` |
| 一句里嵌着三句引语 | 1 | `reading_jijing_9_test_81_p1` F-02 的三段论作为同位语嵌在句中，拆开会破坏句子，保留并继续排除出题 |

- 修订表从 33 条增加到 63 条（本轮 30 条）。新增测试：每条修订的 find 不得包含在 replace 里，否则重复运行会改两次（本轮曾有一条这样的修订，已合并成一条）。
- 句子数 12,688 → 12,726。97 个句子对象有变化，其余 1,469 个同文件句子除 `sentence_index` 外逐字节不变；`json.dumps(indent=2)` 格式的文件仍保持该格式，其他文件保留原有排版。
- 从 raw 重建全部 171 篇机经，段落文字与修补后的 static 完全一致；static 的改动只涉及段落 text 行。

### 出题器

| 改动 | 原因 | 结果 |
|---|---|---|
| 新增整句过滤 `leading_stray_punctuation` | 用户要求“修原文，并且排除” | 原文修复后命中 0，作为以后数据的防线 |
| `multi_sentence_unit` 修正误报 | 列表编号、引语问句后接说话人、`Mt.`、缩写后接引号（`"Do" vs. "Don't"`） | 命中 51 → 1，报告预期值设为 1 |
| 新增整句过滤 `control_character` | 生成抽查表时发现 6 句含 NUL 字符（原文转码丢失的 `$` 等），Excel 拒收 | 排除 6 句，只报告不设预期 |
| 补回被切掉的括号 | 逐题核对时发现，答案或目标末尾的 `)` 会和引号一样被当作标点切掉，如 `the stepwell of Rani Ki Vav (Queen's Stepwell`。沿用补引号的做法，范围不超出原标注 | 括号不成对的题从 155 道降到 2 道（均为 needs_review）；其中 122 道自动通过题的显示范围补全 |
| 并列分句目标不得带从属连词 | 逐题核对时发现 `and because …`、`and that …` 这类“并列的从句”被当成并列分句出题，答案错误 | 23 道从自动通过降为待人审；`92_58_p2` C-01 的标注同时改为原因状语从句。复审抽查其中 10 道：9 道确实不是并列分句，1 道（ielts5_test2_p2 D-16）是 spaCy 把指示词 that 解析成 mark 造成的保守降级，原答案正确 |
| tagged_fragment 预期 37 → 36 | C-14 的残句 `that U.S.` 已并入 C-15 | 与实际一致 |

### 统计（auto_pass / needs_review / rejected）

| 模板 | 第一轮修复后 | 第二轮后 |
|---|---|---|
| main_verb_tap | 5922 / 377 / 6389 | 5954 / 384 / 6388 |
| clause_boundary | 4772 / 2397 / 2791 | 4790 / 2412 / 2773 |
| clause_type_classify | 11540 / 3176 / 1437 | 11596 / 3200 / 1412 |
| adverbial_relation | 396 / 637 / 2668 | 403 / 637 / 2644 |
| subject_span | 5370 / 737 / 6581 | 5399 / 743 / 6584 |
| finite_or_not | 12738 / 1561 / 6575 | 12802 / 1575 / 6576 |

候选题 49,623 → 49,895；整句排除 1,437 → 1,412。抽查表仍是 360 行。

### 验证

| 检查 | 结果 |
|---|---|
| 新句子出的题 | 97 个变动句子生成的 276 道自动通过题逐题人工核对。发现上面两类问题（括号、并列的从句）后改规则、重新生成；其余答案全部正确 |
| 复抽 30 题 | 新抽查表，种子 20261021，每个工作表 5 道 auto_pass：30 道全部正确 |
| 回归例句 | 78 个模板结果与第一轮修复后完全一致 |
| 可复现 | 连续两次生成，7 个文件逐字节一致；`review_batch_v0_2.jsonl` `c6a5948b4760…`，`review_batch_v0_2.xlsx` `e836d8f7e2e3…`，`generation_report_v0_2.json` `f94e1688dab8…` |
| 测试 | 出题器测试 55 项、原文修订测试 8 项；只装 Flask 的 CI 列表 138 项运行，1 项按设计跳过；Node 通过；`tests.test_reading_study` 22 项通过 |
| 数据 | validator 0 错误；`--check` 0 条未应用；临时库先导入 main 的完整快照，再导入本分支：updated=56 / skipped=261 / failed=0 |
| Ruff | 改动的 Python 文件 check 和 format 均通过 |

### 第二轮遗留（NUL 字符、CO 下标、fagging、阅读页标签四项已在第三轮处理）

- **NUL 字符**：`reading_jijing_29_test_63_p3` 5 句、`reading_jijing_84_test_73_p2` C-17 1 句，原文中 `$` 等字符变成了 NUL（如 `yuan (\x001.9 trillion)`）；同样的问题还出现在 `29_63`、`50_30`、`75_57`、`84_73` 的题目文字和 `ielts18_test3` 的一处 `more\x02knowledgeable`。修原文需要逐处猜回丢失的字符，本轮只在出题时排除。
- **CO 缺下标**：`reading_jijing_29_test_63_p1` 全文 4 处 `CO` 应为 `CO₂`，难点里已有说明。
- **真词 OCR 错字**：`reading_jijing_83_test_95_p2` D-04 的 `fagging` 应为 `logging`，规则查不出来。
- **阅读页标签**：`interrogative_clause`、`elliptical_clause`、`question_clause` 这几个已有角色名会被词汇表兜底成“状语从句”显示，属于 `api/reading_study_glossary.py` 的存量问题；本轮新写的标注没有用这些名字。
- `reading_jijing_92_test_58_p2` H-01 的小标题和正文连在一句里（已按 heading 排除出题）。

## 第三轮（2026-10-19，乱码、CO₂、fagging、阅读页标签）

逐句记录：`docs/READING_STUDY_RESPLIT_2026-10_ROUND3.md`（由脚本生成）。

### 原文

| 项目 | 处理 | 结果 |
|---|---|---|
| 乱码（NUL 字符） | 按上下文补回丢失的字符：`29_63_p3` 的 5 处都是 `$`（`16 trillion yuan ($1.9 trillion)` 可以核对汇率）；`84_73_p2` C-17 是逗号（`From age six to 18, British children`）；`75_57_p2` 段落里的 `1989 and 1993.`；`50_30_p2` 题干里的 `rats' learning` | 全部机经 static 和阅读解析里不再有控制字符。`29_63_p3` F-02、F-04、G-02 的翻译原先猜成“元”，改为“美元” |
| CO₂ | 实际不止 4 处：`29_63_p1` 全文 9 个 `CO` 缺下标，丢失的 9 个 `2` 散落在别处（`agriculture, 2 say`、`atmosphere. 2 It has`、`enough 2 to raise`、`release 2 CO . 2`、`our 2 future` 等）。统一写成语料里通用的 `CO2`，删掉散落的 `2`；`by around 2 to 5` 同时补上丢失的单位，改为 `2°C to 5°C`（原翻译已按“度”理解） | 10 句阅读解析更新；难点里“下标错置，必须保留”的说明全部改写 |
| fagging | 改为 logging | 1 句 |
| 题目数据 | 这些错字在题目数据（题干、答案依据、定位词）里也有复制，学生能看到其中的题干和答案依据，例如题干 `Peat bogs never release CO . 2`。修订表新增可选字段：`questions: true` 时同一修订也改该篇题目数据，`paragraph_label: null` 表示只出现在题目数据里。构建脚本和修补脚本同步支持；补了 3 项测试 | 修订表 63 → 93 条；从 raw 重建 171 篇，段落和题目数据都与 static 完全一致 |

另外 `29_63_p1` E-01 的 `and because …` 原标为 coordinated_cause_clause（会显示成“并列分句”），改为原因状语从句；B-06 的 `exemplification`（词汇表查不到）改为介词短语。

### 阅读页标签

`api/reading_study_glossary.py` 原来把所有不认识的 `*_clause` 一律显示成“状语从句”。现在只在 role 名字能确定含义时改判，以关系词开头的（`time_clause`、`purpose_clause` 等）和其他已有规则全部不变：

| 新标签 | 处数 | role（处数） | 例子 |
|---|---:|---|---|
| 时间状语从句 | 58 | `temporal_clause`（25）、`reduced_time_clause`（25）、`reduced_time_condition_clause`（2）、`elliptical_time_clause`（2）、`temporal_causal_clause`（1）、`standalone_time_clause`（1）… | as microorganisms within soil digest dead animals  |
| 不定式 | 53 | `infinitive_clause`（41）、`bare_infinitive_clause`（6）、`extraposed_infinitive_clause`（3）、`interrogative_infinitive_clause`（1）、`infinitive_result_clause`（1）、`for_to_infinitive_clause`（1） | so as to produce the necessary emphases |
| 名词性从句 | 47 | `complement_clause`（22）、`nominal_clause`（18）、`whether_clause`（4）、`adjective_complement_clause`（2）、`fact_clause`（1） | we changed our outlook |
| 疑问句 | 45 | `interrogative_clause`（39）、`first_interrogative_clause`（2）、`third_interrogative_clause`（1）、`second_interrogative_clause`（1）、`question_clause`（1）、`alternative_question_clause`（1） | are you hoping |
| 省略结构 | 39 | `elliptical_clause`（36）、`elliptical_passive_clause`（1）、`elliptical_disclaimer_clause`（1）、`elliptical_comment_clause`（1） | Unlikely |
| 祈使句 | 35 | `imperative_clause`（35） | run them through the cogs and wheels of the langua |
| 分句 | 35 | `clause`（30）、`first_clause`（4）、`second_clause`（1） | we are denied the pattern we expect |
| 分词短语 | 26 | `present_participle_clause`（7）、`participle_clause`（6）、`present_participial_clause`（4）、`past_participle_clause`（4）、`accompanying_participle_clause`（3）、`supplementary_participle_clause`（1）… | bringing a range of benefits |
| 主句 | 21 | `independent_clause`（6）、`run_on_clause`（5）、`second_independent_clause`（3）、`first_independent_clause`（3）、`run_on_passive_clause`（2）、`comma_spliced_clause`（1）… | they do not actually exist |
| 条件状语从句 | 13 | `reduced_conditional_clause`（3）、`elliptical_conditional_clause`（3）、`elliptical_condition_clause`（2）、`reduced_condition_clause`（1）、`malformed_condition_clause`（1）、`hypothetical_conditional_clause`（1）… | if mishandled |
| 原因状语从句 | 9 | `causal_clause`（7）、`predicate_with_reason_clause`（1）、`alternative_reason_clause`（1） | Since soil grows 95% of our food, and sustains hum |
| 动名词 | 9 | `gerund_clause`（9） | skyscrapers not being built between the two urban  |
| 让步状语从句 | 6 | `elliptical_concessive_clause`（3）、`reduced_concessive_clause`（2）、`parenthetical_concessive_clause`（1） | if not advanced |
| 介词短语 | 2 | `prepositional_participial_clause`（1）、`prepositional_clause`（1） | Despite arising in the last half century |
| 对比状语从句 | 2 | `elliptical_contrast_clause`（2） | less so for the gut |
| 结果状语从句 | 2 | `first_result_clause`（1）、`alternative_result_clause`（1） | the pearl may be seriously deformed |
| 非谓语结构 | 1 | `non_finite_passive_clause`（1） | to be completed |
| 比较状语从句 | 1 | `elliptical_comparative_clause`（1） | As today |
| 倒装 | 1 | `inversion_clause`（1） | Here is |
| 感叹句 | 1 | `exclamatory_clause`（1） | what a story it is |
| 方式状语从句 | 1 | `reduced_manner_clause`（1） | As shown in Table 1 |

共 72 个 role、407 处标注，原来都显示为“状语从句”。

- 名字本身含混的 role 仍显示“状语从句”，需要逐条改标注才能修：`contrastive_clause`（30 处，既有 whilst 从句也有 but 并列句）、`passive_clause`（21）、`supplementary_clause`（8）、`alternative_clause`（7）、`contrasting_clause`（5）等，共约 85 处。
- 新增 `tests/test_reading_study_glossary.py`（7 项，已加入 CI 轻量测试列表），并重新生成 `docs/GRAMMAR_GRAPH_V0_REVIEW.md`（只有各知识点的句数变化）。
- 标签在导入时写进数据库，所以要部署后重新导入才会在阅读页生效。

### 出题器

- `control_character` 预期值改为 0（原文修复后实际为 0）。
- 新的标签会改变概念归类：新增 7 个句子带“第一层出现名词性从句”（level_one_subordinate）这条整句排除原因，其余模板统计变化都在个位数。

### 统计（auto_pass / needs_review / rejected）

| 模板 | 第二轮后 | 第三轮后 |
|---|---|---|
| main_verb_tap | 5954 / 384 / 6388 | 5957 / 383 / 6386 |
| clause_boundary | 4790 / 2412 / 2773 | 4793 / 2409 / 2772 |
| clause_type_classify | 11596 / 3200 / 1412 | 11598 / 3197 / 1411 |
| adverbial_relation | 403 / 637 / 2644 | 404 / 636 / 2643 |
| subject_span | 5399 / 743 / 6584 | 5404 / 742 / 6580 |
| finite_or_not | 12802 / 1575 / 6576 | 12805 / 1573 / 6574 |

### 验证

| 检查 | 结果 |
|---|---|
| 改动句子出的题 | 17 句生成的 52 道自动通过题逐题核对，全部正确 |
| 复抽 30 题 | 新抽查表，种子 20261023：30 道全部正确 |
| 回归例句 | 78 项与第二轮完全一致 |
| 可复现 | 连续两次生成逐字节一致；`review_batch_v0_2.jsonl` `710d32d4ac5a…`，`review_batch_v0_2.xlsx` `07bd14e82681…`，`generation_report_v0_2.json` `f0586841c34d…` |
| 测试 | 只装 Flask 的 CI 列表 148 项运行（新增词汇表 7 项、修订表 3 项），1 项按设计跳过；Node 通过；`tests.test_reading_study` 22 项通过 |
| 数据 | validator 0 错误；`--check` 0 条未应用；从 raw 重建与 static 完全一致（含题目数据）；临时库先导入 main 的完整快照再导入本分支：updated=187 / skipped=130 / failed=0（59 篇数据文件有改动，另外 128 篇是标签变化） |
| Ruff | 改动的 Python 文件通过；构建脚本仍有原有的 UP017 和格式问题（见 S4） |

### 第三轮遗留

- 阅读解析的难点里还记着约 88 句“原文有误、按原样保留”的说明，例如 `wax`（way）、`DINA`（DNA）、`tills`（this）、`Jiving`（living）、`chat`（that）、`ear ownership`（car）。其中一部分并不是错误（美式拼写、作者原文的语法），需要逐条判断。
- 前两轮的原文修订没有同步改题目数据，答案依据里仍是修订前的文字（例如粘连的句子）。需要的话可以给这些修订加 `questions: true`。
- `ielts18_test3` 的定位词数据里有一处 `more\x02knowledgeable`，不在页面上显示；它属于剑桥真题数据，不走机经修订表。

## 第四轮（2026-10-19，难点里记录的原文错误）

清单与分类：`docs/READING_STUDY_SOURCE_ERRORS_2026-10.md`（由脚本生成，列出每句的改动或改写后的说明）。

### 用户决定

把难点里记着的“原文有误、按原样保留”逐条列出、分类后再修；修完后再交 Codex 复审。第三轮估计约 88 句，逐条检索后实际多得多：先按关键词找到 449 句，清理时又发现 10 句，放宽检索词后再找到 139 句。

### 原文

| 项目 | 结果 |
|---|---|
| 改原文 | 486 句、553 处：错字和漏字 220、标点 162、空格 138、大小写 22、补句末标点 11。逗号后误接大写新句、句号把一句话断开等，按句子边界拆句 22 个单元（新增 24 句）、合并 5 处（减少 5 句），句子 12,726 → 12,745 |
| 不改原文 | 119 句改写说明：不是错误 20（美式拼写、编者方括号、跨句引语等）、原文分段或句末标点 12、作者原文的语法或用词 70（说明改为“规范写法是……”）、无法确定 17（说明写清大意）。另有 18 句说明已经清楚，不改 |
| 修订表 | 93 → 641 条（本轮 548 条，103 篇）：typo 242、punctuation 170（新原因）、missing_space 136；282 条同时改题目数据（`questions: true`），10 条是段末补句号 |
| 新字段 `at_end` | 段末缺句号无法用现有机制表达（`find` 必然包含在 `replace` 里，重跑会重复追加）。新增可选字段 `at_end: true`：只替换段落末尾的 `find`，段落已经以 `replace` 结尾时跳过，与 `questions` 互斥。`scripts/reading_jijing_text_fixes.py` 加了 3 项测试；修订表测试的原因白名单加入 `punctuation` |
| 题目数据 | 修订窗口自动扩展到段内唯一、至少两个词，并要求在题目数据里只出现在词边界上，避免 `lor → for` 之类误改 `color`。题目数据共 1,065 个字符串改动逐条核对，都是预期的替换（按 JSON 路径比较的前后字符串对共 510 种；原写的“332 种”没有可复现的定义，已更正） |
| static | 42 个机经文件更新；`--check` 0；从 raw 重建 171 篇，段落和题目数据都与 static 完全一致 |
| 追加 | 用户看过清单后决定把 `50_30_p2` F-02、F-03 的 `catching` 改为 `caching`（清单第七节）：修订表再加 2 条，共 643 条，都同时改题目数据（11 个字符串）；阅读解析同步这两句。交付文件只有报告里的语料哈希变化，题目统计和抽查表不变 |

### 阅读解析

- 116 个文件、611 个句子对象更新：句子文字和结构成分随原文同步（成分边界按改动的词平移），过时的“必须保留/按原文保留/源文异常”等说明全部改写；拆句和合并的句子重写完整标注；名字带错误含义的 role `main_clause_with_corruption` 改为 `main_clause`。
- 翻译按改正后的原文更新了 15 句（如 `DINA` → DNA、`19BH` → 1988、`Davis` → 戴维、`Pfefier` → Pfeffer、`科兰湾` → 库兰湾），18_53_p2 补回引语的句子同步调整了引号。
- 未改动的句子对象除 `sentence_index` 外逐字节不变；`json.dumps(indent=2)` 格式的文件仍保持该格式。全库难点里不再有“必须保留、按原文保留、源文异常、已保留、予以保留”之类说法（只剩 71_1_p2 H-05 译文里的“保留原文”策略名，属正常用法）。

### 出题器

逐题核对时发现两处存量问题（v0.2 起就有），都用通用规则修，不针对句子 ID：

- **并列谓语被当成并列分句**：`and usually refer to …`、`and identified it as …` 这类共用主语的并列谓语，原来按 conj 依存判为“并列分句”。现在并列分句的目标必须有自己的主语（nsubj、nsubjpass、csubj、csubjpass、expl），否则加 `clause_type_mismatch`。全库 167 道 auto_pass 因此降为 needs_review，抽查均为并列谓语；保留的并列分句都有自己的主语。
- **for 引出的原因分句**：`for they shared …` 原按 advcl 判为“状语从句”，按教学惯例 for 是并列连词。状语从句目标由 for 引出时加 `clause_type_mismatch`，10 道 auto_pass 降级；`so that` 目的从句不受影响。
- 两条规则各有一项测试，并确认在修改前的代码上失败。
- 报告预期值：`tagged_fragment` 36 → 32（4 个残句并回所属句子）；`suspected_split_word` 由只报告改为预期 0（6 处断词已改原文）。`83_95_p1` H-05 补上两个引语之间的空格后成了两句，已拆开，`multi_sentence_unit` 仍为 1。

### 统计（auto_pass / needs_review / rejected）

| 模板 | 第三轮后 | 第四轮后 |
|---|---|---|
| main_verb_tap | 5957 / 383 / 6386 | 5987 / 384 / 6374 |
| clause_boundary | 4793 / 2409 / 2772 | 4755 / 2497 / 2711 |
| clause_type_classify | 11598 / 3197 / 1411 | 11582 / 3290 / 1350 |
| adverbial_relation | 404 / 636 / 2643 | 411 / 643 / 2584 |
| subject_span | 5404 / 742 / 6580 | 5428 / 747 / 6570 |
| finite_or_not | 12805 / 1573 / 6574 | 12886 / 1578 / 6557 |

候选 49,901 → 50,188 道。

### 验证

| 检查 | 结果 |
|---|---|
| 改动句子出的题 | 第一、二组 140 句的 449 道新 auto_pass、第三组 66 句的 208 道新 auto_pass 逐题核对；发现的 5 道错题全部来自上面两处存量问题，规则修正后已降级，其余全部正确 |
| 复抽 30 题 | 种子 20261025、20261026 各抽 30 道 auto_pass，全部正确 |
| 回归例句 | 78 项状态和原因与第三轮一致；76_43_p2 H-02 因原文 `high- rise` 改为 `high-rise`，偏移量和题号变化 |
| 可复现 | 规则改完后连续两次生成，四份交付文件和全量候选池逐字节一致；`review_batch_v0_2.jsonl` `0c727e740e89…`，`review_batch_v0_2.xlsx` `3fa09b550cfc…`，`generation_report_v0_2.json` `ad5178ea7a54…`（追加 catching 修订后） |
| 测试 | 只装 Flask 的 CI 列表 153 项运行、1 项按设计跳过；Node 通过；`tests.test_reading_study` 22 项通过；出题器、修订表、词汇表、知识图谱测试 85 项通过 |
| 数据 | validator 0 错误；`--check` 0；从 raw 重建与 static 完全一致；临时库先导入 main 的完整快照再导入本分支：updated=227 / skipped=90 / failed=0（133 篇数据文件与 main 不同，另外 94 篇只是标签变化） |
| Ruff | 改动的 Python 文件 check 和 format 通过 |

### 第四轮遗留

- 第一、二轮的 63 条原文修订仍没有 `questions: true`，题目数据里的答案依据还是修订前的文字。
- 名字含混的 role（`contrastive_clause` 等约 85 处）仍显示“状语从句”。
- 清单第五、六节的句子疑有错误但无法确定，保留原文。
- 题目数据里定位词的同义词（`locating_words` 的 `synonym`，多为单个词）有 10 处仍是修订前的写法：`1070s`、`coee`、`stablize`、`Green Peace`、`Refer-ence`、`unsuccessfull`、`hypothrsie…`、`may be you`、`Street Angel(1937)`、`catching`。修订表的替换窗口至少两个词，改不到这些单词；后端和小程序都不读取这个字段，页面不显示。
- 修订和改写由同一方完成并自查，需要独立复审。

## 第五轮（2026-10-26，两份 Codex 复审的问题）

依据：`docs/GRAMMAR_ITEM_CANDIDATES_V0_2_FIXES_CODEX_REVIEW.md`（第一轮修复复审）和 `docs/GRAMMAR_ITEM_CANDIDATES_V0_2_ROUND2_4_CODEX_REVIEW.md`（第二至四轮复审），两份结论都是不通过。原文按第四轮的标准处理（能确定的改原文，其余保留原文、改写说明），清单见 `docs/READING_STUDY_SOURCE_ERRORS_2026-10.md` 第八节。修订表 643 → 686 条：新增 18 条原文修订（13 条同时改题目数据）、1 条摘要修订、24 条只改题目数据的修订，另有 22 条旧修订改为同时修改题目数据。

### 问题与处理

| 复审编号 | 问题 | 处理 |
|---|---|---|
| 第一轮 R1 / 第二至四轮 B1（阻断） | 主句谓语题的干扰项越出来源标注仍自动通过 | `main_distractors` 逐个检查干扰项的完整动词单位是否越出它所在的从句/非谓语标注，越出时主句谓语题加 `verb_unit_outside_span`；动词身份题的主句项只检查自己的单位。全库 3 道降为待人审（含点名的 `gi_v02_eb01375e183f`、`gi_v02_20551c6d1cef`），其他题不变；新测试在修改前失败 |
| 第一轮 R2 | 数字前的单引号一律当撇号，`'15 volts ...'` 的尾引号被截掉 | 只有年代缩写（`'60s`、`'70s`）当撇号；该题恢复完整范围（题号回到 `gi_v02_96287b126ba9`） |
| 第一轮 R3 | OCR 断词漏网 | 复审列的 19 句中 16 句第四轮已改；本轮改剩下的 nas al、cow less / chicken less、may be；全库扫描又改 3 处连字符后多空格（hunter- gatherers 等）和 1 处 ff 连字丢失（dierent） |
| 第一轮 R4 | “严格检查会误降 2,333 道”无法复现 | 第一轮一节已更正为复审核实的 933 道新增降级（不全是误降） |
| 第一轮 A1–A3 | 建议 | A3（目标内括号）第二轮已补回；A1 只涉及说法，第一轮一节保留区分；A2（含所有格的嵌套引语）全库没有实际出现，本轮不改 |
| N1 | 清单外 108 条源文记录未分类；同篇专名不一致 | 全部分类处理：9 条随改原文处理（8 个句子单元，含 2 处合并、1 处拆分），其余 99 条保留原文、改写说明；另把 18 条仍用“源文……”旧说法的信息性说明、5 句夹带说明的译文改成同样口径；9_81_p2 的 Conran Cove、Pridcaux 在同篇所有出现处统一为 Couran Cove、Prideaux |
| N2 | 题目数据仍是修订前写法 | 修订脚本在题目数据里只按整词替换，直撇号同时匹配弯撇号，新增 `exact`（整串替换）和 `summary`（改中文摘要）；22 条旧修订（含第一、二轮的 claim mat 等）改为同时修改题目数据，另加 24 条只改题目数据的修订（2 条整串替换），提交 b7261d5 改了 180 个题目数据字符串（85 种前后字符串对）；整个第五轮（1f03c84..f565da2）共 247 个字段、113 种字符串对（复审核实） |
| N3 | 11 处教学内容错误 | 逐条改正（主语被并进谓语、动名词/名词、被动问句主语、help do 没有宾语、形容词短语、同位语从句、单复数译文、the rest 的指代、过时括注、for 分句按并列分句标注） |
| N4 | 4 个 role 标签与成分不符 | 改数据：两个“结果”分句改为主句和并列分句，两处对比省略改为 `elliptical_clause`，“谓语+原因从句”拆开；带从属连词的 `elliptical_*_clause` 标成对应状语从句是对的，不改规则。另让 15 个原先显示“语法成分”的 `ellip*` role 显示“省略结构” |
| N5 | 拆句基数错误；“332 种”没有定义 | `resplit` 改用固定基线 12,657 句，新增 `removed`、`net_change`，测试覆盖合并；`counting_notes` 同步（含 `suspected_split_word` 预期 0）；第四轮一节的“332 种”更正为可复现的 510 种字符串对 |
| A1 | “降级题都不是并列分句”的全称说法 | 第二轮一节改为抽查 10 道中 9 道确实不是并列分句、1 道是保守降级 |
| A2 | 通用规则的边界 | 题目数据替换改为整词（上一条）；目标内成对破折号在各模板允许的范围内补回（T2/T3/T4 为目标的原标注；T5 沿用完整主语区间，即 subject.start 至 predicate.start）；缩写后真句末（`Inc.`、`p.m.`）全库没有实际误吞，本轮不改规则 |
| A3 | 摘要 CO；残缺句不适合直接出题 | 29_63_p1 摘要改为“二氧化碳”；“残缺句不进自动通过池”需要新的通用规则或审核状态，见遗留 |

### 统计（auto_pass / needs_review / rejected）

| 模板 | 第四轮后 | 第五轮后 |
|---|---|---|
| main_verb_tap | 5987 / 384 / 6374 | 5989 / 387 / 6368 |
| clause_boundary | 4755 / 2497 / 2711 | 4764 / 2497 / 2695 |
| clause_type_classify | 11582 / 3290 / 1350 | 11591 / 3291 / 1334 |
| adverbial_relation | 411 / 643 / 2584 | 414 / 643 / 2568 |
| subject_span | 5428 / 747 / 6570 | 5431 / 749 / 6564 |
| finite_or_not | 12886 / 1578 / 6557 | 12894 / 1580 / 6550 |

句子 12,745 → 12,744（合并 2、拆分 1）；候选 50,188 → 50,230。增加的题主要来自 7 句因“省略结构”标签不再整句排除（`unknown_span` 304 → 274）。报告预期 `tagged_fragment` 32 → 30（两个残句并回）。

### 验证

| 检查 | 结果 |
|---|---|
| 新增题 | 新增 83 道：69 道 auto_pass、14 道 needs_review（更正：原写“71 道 auto_pass，全部正确”，计数时把统计行算了进去，“全部正确”也只适用于自动通过题）。69 道自动通过题逐题核对未发现答案错误，其中 4 道来自 44_29_p3 M-01 列表片段，整句适用性见遗留；14 道待复核题里有范围不完整的（如 81_93_p2 F-01 的主语带上了插入语、5_59_p1 I-01 的同位语从句只到 realise），降级起了作用。共有题目里只有上述 3 道主句谓语题改变状态 |
| 抽查 | 种子 20261028 从抽查表每个题型抽 5 道 auto_pass，共 30 道，全部正确 |
| 回归例句 | 报告里的 13 句 × 6 模板回归记录与第四轮完全一致 |
| 可复现 | 规则改完后连续两次生成，四份交付文件和全量候选池逐字节一致：`review_batch_v0_2.jsonl` `4098cdd88d26…`，`review_batch_v0_2.xlsx` `72cab3ba0c50…`，`generation_report_v0_2.json` `bf148c672b49…`；7 项整句过滤预期全部吻合 |
| 测试 | 只装 Flask 的 CI 列表 161 项运行、1 项按设计跳过；Node 通过；`tests.test_reading_study` 22 项通过；出题器、修订表、词汇表、知识图谱测试 93 项通过；每项新测试都确认在修改前的代码上失败 |
| 数据 | validator 0 错误；`--check` 0；从 raw 重建 171 篇（段落、摘要、题目数据）与 static 完全一致；无法识别的 role 没有新增；临时库先导入 `origin/main`（65f1859）完整快照再导入本分支：updated=233 / skipped=84 / failed=0（135 篇数据文件与 main 不同，另外 98 篇只是标签变化） |
| Ruff | 改动的 Python 文件 check 和 format 通过（`build_reading_test_practice.py` 的 UP017 与格式问题是存量） |

### 第五轮遗留

- 复审 A3：保留原文的残缺句（如 vein/spine、vibration fell）局部答案正确，但整句不适合直接给学生；要排除需要新的通用规则或审核状态，等用户决定。
- IELTS 原文（static/reading_tests）里的同类排印问题不在机经修订表范围内，本轮没有改（如 `ielts13_test3_p3` C-04 的 `well- argued`、`ielts9_test4_p1` 跨段拆开的人名），说明已如实写明。
- 名字含混的 role（`contrastive_clause` 等约 85 处）仍显示“状语从句”；按句子截短的题目引用（如 `Saving the energy…`）保留截取时的大小写。
- ielts18_test3 定位词数据里的 `\x02`、76_43_p2 D-02 嵌套成分顺序、85_12_p3 B-02 的 level 5 仍是存量问题。
- 修订和自查仍由同一方完成，需要独立复审。

## 第六轮（2026-10-26，第五轮复审 Q1–Q4、A5–A6）

依据：`docs/GRAMMAR_ITEM_CANDIDATES_V0_2_ROUND5_CODEX_REVIEW.md`（结论不通过；原阻断 R1/B1 已关闭，新增 4 项应修、2 项建议）。原文清单见 `docs/READING_STUDY_SOURCE_ERRORS_2026-10.md` 第九节。

| 复审编号 | 问题 | 处理 |
|---|---|---|
| Q1 | 4 条改写的说明不准确 | ielts4_test4_p1 E-22 改为“不完整、不宜模仿”；22_90_p3 G-08 说明 view 是及物动词、be invited to view 的 to 是不定式标记；24_56_p2 A-04 不再断定“低 5 个百分点”；32_20_p1 B-03 改正 for 分句位置的说法。清单第八节同步，E-22、A-04 归入“无法确定” |
| Q2 | 9_81_p2 题目数据仍有 docs not、capac ity | 这两处是题目引用抄错（正文本来就对），按修订找遗留的方法查不到。新增“题目引用与改后正文逐词比对”（中心句、定位句、解析里引号括起来的英文），又找到 9_81_p3 的 newand、becoming modem；4 处都用只改题目数据的整词修订同步。比对现在只剩 84_73_p1 一条：中心句引用了正文里没有的一段文字，属于数据源本身的问题 |
| Q3 | 5_59_p1 两处排印错误 | Post- It Notes → Post-it Notes（题目里的 Post-It 一并统一）、Peroy Spender → Percy Spencer（译名改为珀西·斯宾塞）。另按“行尾断字留下的连字符”扫描全部机经正文（只用独立出现的词频判断），改 crea-tures、cam-paign、impos-sible、prom-ising、terres-trial、gaso-line、In-stead、Oeco-phylla 和 Yu- kichi；鹦鹉 Alex 的 "Co-lor." 表示分音节发音，保留 |
| Q4 | 新增题“71 道、全部正确”不成立 | 第五轮验证一节更正为 69 道自动通过、14 道待复核，并说明“全部正确”只指自动通过题；“180 个字符串”注明是提交 b7261d5 的数字，整轮为 247 个字段 |
| A5 | 启发式边界 | 数字区间号（5–10）不再算作成对破折号，新增测试；第五轮 A2 一行改正范围说法（T5 沿用完整主语区间）。年代撇号与 '90s 开头的引语、含所有格的嵌套引语、‘ 弯引号、缩写后真句末仍按已披露的边界保留，全库没有实际受害题 |
| A6 | 整句适用性；存量说明 | 83_95_p2 F-01 的 targeting 说明改为动名词复合结构（role 改 gerund_phrase）；残缺句、列表片段是否进自动通过池仍待用户决定 |

修订表 686 → 702 条：11 条原文修订（9 条同时改题目数据）、5 条只改题目数据。阅读解析 6 个文件、7 个句子对象更新，句子数不变（12,744）。

### 验证

| 检查 | 结果 |
|---|---|
| 题目 | 候选 50,230，各模板状态数与第五轮相同；只有 5_59_p1 C-06、83_95_p2 F-01 的 11 道题换了题号（7 道自动通过、4 道待复核）。7 道自动通过题逐题核对答案和高亮正确；4 道待复核题中 2 道的 when 从句、宾语从句范围不完整或有歧义，降级起了作用 |
| 可复现 | 连续两次生成逐字节一致；抽查表 `review_batch_v0_2.jsonl` `4098cdd88d26…`、`review_batch_v0_2.xlsx` `72cab3ba0c50…` 与第五轮相同，`generation_report_v0_2.json` `7ea3af10b1c5…`；回归记录不变，7 项整句过滤预期吻合 |
| 测试 | 只装 Flask 的 CI 列表 161 项运行、1 项按设计跳过；Node 通过；出题器、修订表、词汇表、知识图谱测试 93 项通过；新测试在修改前失败 |
| 数据 | validator 0 错误；`--check` 0；从 raw 重建 171 篇一致；无法识别的 role 没有新增；临时库先导入 `origin/main` 65f1859 完整快照再导入本分支：updated=233 / skipped=84 / failed=0（main 之后的 80f215b 不涉及阅读解析和导入） |

### 第六轮遗留

- 残缺句、列表片段（如 44_29_p3 M-01）出的题局部答案正确，但整句不适合直接给学生；是否排除出自动通过池，待用户决定（复审 A3 / A6）。
- 84_73_p1 中心句引用了正文里没有的一段文字（数据源问题）；IELTS 原文的同类排印问题不在修订表范围。
- 第五轮遗留的其余各项（含混 role、截短引用的大小写、ielts18_test3 的 `\x02` 等）不变。

## 第七轮（2026-10-26，用户决定：原句有缺陷的句子和列表项不进自动通过池）

依据：第二至四轮复审 A3、第五轮复审 A6 都指出，残缺句、明显语病句和列表片段出的题局部答案正确，但整句不适合直接给学生。用户决定把它们排除出自动通过池。做法是给这些句子出的题全部降为待人审（不拒绝整句，老师审核时仍可保留），规则是通用的，没有按句子 ID 列名单。原文清单见 `docs/READING_STUDY_SOURCE_ERRORS_2026-10.md` 第十节。

### 怎么识别

| 原因码 | 规则 | 数据 |
|---|---|---|
| `source_quality` | 阅读解析里只要有一条难点以“原句问题：”开头，就表示原句本身有缺陷（语病、残缺、截断、脱漏、乱码、明显排印错误），该句所有题加这一原因 | 85 篇 251 句、255 条说明加了前缀（提交 b60cf61）。来源：第四至六轮已分类为“作者原文的语法或用词问题”“分段截断片段”“无法确定”的说明，加上对其余说明的人工扫描。5 条当前说明已不再指出缺陷（13_6_p1 D-02、32_20_p1 G-01 / H-04、44_29_p2 E-03、78_102_p1 C-02），不加。讲缺陷的子句不在开头的，移到前缀后面（54 条），另有 8 条改写了语序；只改 difficult_points |
| `list_item` | 句子以列表符号（- – — • *）或编号（1. / 2) / (3)）开头 | 全库 27 句：44_29_p3 的 5 条“- 动词短语”、ielts4_test3_p1 的 9 条 •、32_20_p2 的 8 条编号、5 条 * 脚注释义 |

两条都在 `scripts/grammar_items/checks.py` 的 `review_reasons()`，由 `collect()` 读阅读解析传给 `generate_templates()`，在 `Context.emit` 里加到每道题的原因上。不改变出不出题、题号和答案，只改状态。报告新增 `sentence_review` 一节，`only_reason` 是只因这两条才没有自动通过的题数。

### 统计（auto_pass / needs_review / rejected）

| 题型 | 第六轮 | 第七轮 | 降级 |
|---|---|---|---:|
| 主句谓语 main_verb_tap | 5989 | 5922 | 67 |
| 从句边界 clause_boundary | 4764 | 4700 | 64 |
| 从句类型 clause_type_classify | 11591 | 11455 | 136 |
| 状语关系 adverbial_relation | 414 | 404 | 10 |
| 主语范围 subject_span | 5431 | 5371 | 60 |
| 动词身份 finite_or_not | 12894 | 12742 | 152 |
| 合计 auto_pass | 41,083 | 40,594 | 489 |

- 候选总数 50,230 和全部题号不变；除 status / reasons 外其他字段逐题相同；唯一的状态变化是 489 道 auto_pass → needs_review（机经 446、IELTS 43，来自 142 句）。
- `source_quality`：150 句出了题，共 631 道带此原因，其中 441 道只因此降级；另外 62 句被整句过滤拒绝、39 句没有适用目标。
- `list_item`：14 句出了题，共 52 道带此原因，其中 48 道只因此降级；另外 10 句被整句过滤拒绝，3 句（32_20_p2 C-01、44_29_p3 L-01 / M-01b）没有适用的题型。两类没有重叠。
- 第五轮复审 C2 / C3 点名“原句语病或残缺、列表片段”的 16 道自动通过题，以及第二至四轮、第一轮复审点名的同类题，现在全部是 needs_review 或已不存在。
- 抽查表用同一种子，但自动通过池变小，分层抽样结果随之变化：333 道是新题、27 道保留，但按工作表和行号比较，360 行全部换了题，不能按旧行号续审（第七轮原写“333 行换了题”，复审 A7 更正）。抽查表里的自动通过题都不带这两个原因。

### 验证

| 检查 | 结果 |
|---|---|
| 可复现 | 连续两次生成逐字节一致：`generation_report_v0_2.json` `e62e5c0e19c9…`、`generation_report_v0_2.md` `d0aee87a35ae…`、`review_batch_v0_2.jsonl` `329cd9d5fd2a…`、`review_batch_v0_2.xlsx` `360a8110ac40…`；回归记录不变，7 项整句过滤预期吻合；知识图谱审阅文档重新渲染后不变 |
| 测试 | 新增 4 项（判断规则、模板降级、`collect` 从阅读解析读取、报告计数），修改前全部不能通过（复审核实：在旧代码上是 1 项断言失败、3 项接口不存在或参数不符的错误，不是 4 项业务断言失败）；只保留 checks.py 的改动、不接入出题流程时，模板降级和 `collect` 两项仍不能通过；出题器、修订表、词汇表、知识图谱测试 97 项通过；只装 Flask 的 CI 列表 165 项运行、1 项按设计跳过；Node 通过；`tests.test_reading_study` 22 项通过 |
| 数据 | validator 0 错误；只有 difficult_points 变化（逐字段比对）；重复应用前缀脚本不再产生改动；修订表 `--check` 0；从 raw 重建 171 篇一致；临时库先导入 main 快照（65f1859，与现在的 `origin/main` 676569c 在阅读解析、导入脚本和 models.py 上相同）再导入本分支：updated=233 / skipped=84 / failed=0，85 篇解析带上了前缀 |
| 改动文件 Ruff | check 与 format --check 通过 |

### 第七轮遗留

- 判断依据是阅读解析里的说明。没写说明的缺陷句仍可能自动通过；对其余说明扫描时，内容上讲“错误”的词义、合法省略、跨句引语、IELTS 原文的修辞片段（如 ielts11_test4_p3 F-07、ielts17_test4_p2 D-04）、标题和小节名都没有加前缀。
- 自动通过池里还有 8 句（28 道）句末没有句号：以冒号结尾的引导句、脚注编号、原排版的标题式句子（如 ielts20_test1_p1 A-01、ielts7_test3_p2 B-05），不算原句缺陷，未处理。
- 第六轮遗留的其余各项（84_73_p1 中心句引用、含混 role、截短引用的大小写、ielts18_test3 的 `\x02` 等）不变。

## 第八轮（2026-10-26，第六、七轮复审 U1–U6、A7–A8）

依据：`docs/GRAMMAR_ITEM_CANDIDATES_V0_2_ROUND6_7_CODEX_REVIEW.md`（结论不通过；0 阻断、6 应修、2 建议）。原文清单见 `docs/READING_STUDY_SOURCE_ERRORS_2026-10.md` 第十一节。

| 复审编号 | 问题 | 处理 |
|---|---|---|
| U1 | 已写明缺陷的说明漏加前缀 | 9 条补前缀（11_103_p1 D-04、11_103_p2 F-04 / F-05、18_53_p1 D-01、44_29_p2 E-03、46_84_p1 E-01、65_69_p2 D-04、71_1_p2 H-05、76_43_p3 C-06），其中 5 条改写成先讲缺陷；44_29_p2 E-03 改为“分号后应是能独立成句的分句，experts warning that... 却没有限定谓语”。复审点名的另两句能确定原文错误，直接改原文、不加前缀：91_49_p1 下一段引语的开引号错放在 C-01 句末（`processing." There's` → `processing. "There's`），23_46_p1 B-04b 的引语缺闭合引号（题目数据里有，段末补 `'`）。85_12_p1 B-02 的金额没有币种，无法确定是否丢了 $，不改不标 |
| U2 | 合法表达或风格建议被标成缺陷 | 逐条复核后，13 条同意复审（the providing of、is plausible / was unavoidable、would indicate / was obtained、school 后的逗号、average 与 on average、表语 acid based、researches、says / expressed、some in opposition、need to / for、products' benefit、could not / insert、up to almost）：去掉前缀，讲解改为合法用法或可选的措辞建议。27_33_p2 A-03 的问题确实存在，但旧理由（triple 作动词）不对，改为 is able to more than triple 语义不符（应为 has more than three times），保留前缀。另 5 条（48_21_p3 K-02、50_30_p3 B-03、53_83_p1 C-01、62_44_p3 C-05、65_69_p2 E-05）保留前缀，改为不断言唯一写法 |
| U3 | 字母编号列表漏识别 | `checks.py` 新增 `LETTER_LABEL` 和 `list_letters()`：句首单个大写字母加句点或右括号，且同篇还有相邻字母的同类编号，才算列表项；后面紧跟另一个首字母缩写的（A. K. Lakhina）不算，孤立的（K. Anders Ericsson）也不算。`LIST_ITEM` 另补 a)、(iv)、100.、·、− 等写法，去掉 —（可能是对话破折号）。全库新命中只有 32_20_p2 G-01（没有题）和 I-01（2 道降级） |
| U4 | 32_20_p3 题目引用的句子不在正文 | 原因是原始数据把文章开头两句（盲人摸象的比喻）放进了 `sub_title`，构建时丢掉。全库 17 篇有 `sub_title`，只有这一篇被题目数据引用；其余 16 篇是副标题或导语，题目没有引用，未改。修订表新增 `at_start`（与 `at_end` 对称），把这两句补回 A 段开头；阅读解析为它们新写解析（A-01、A-01b），原 A-01 改为 A-01c。题目答案的段落字母按现在显示的标号，不受影响；`summary` 和定位句的 `target_para` 按原始数据的编号（把这两句算作 A 段），比显示的标号多一位，这两个字段网页和小程序的阅读页都不显示，未改。第 27 题的解析本身就引用了这两句，属数据源问题 |
| U5 | 19 处排印残留 | 全部按复审改法加入修订表（14 处同时改题目数据），这些篇目暂无阅读解析。另用同样方法复扫全库，其余命中是合法的连字符写法（multi-tasking、co-exist 等）、悬挂连字符（first- or second-）和当破折号用的连字符，未改 |
| U6 | 数字区间规则使 1 道 T5 丢了闭合破折号 | `DASH` 改为只有两侧都是数字才算区间（5–10、5 - 10），一侧是数字的仍算插入语破折号；29_63_p3 A-03 的主语题恢复为 `Some $265 billion of the increase - 93% of it -`。全库只有这 1 道题的答案变化 |
| A7 | 抽查表换行数口径 | 第七轮统计一节已更正（333 道新题、27 道保留，按行号 360 行全部换题） |
| A8 | E-22 措辞；T2 多解 | E-22 改为“even though 后面一般接分句；这里也不能按常规省略补出”。T2 多解未改：按解析器粗估，自动通过的 T2 里约 440 道句中还有同类依存标签，但大多是解析器把非谓语结构也标成从句造成的误报，要做准需要另设计规则；盲审时老师可以标“题目有歧义” |

修订表 702 → 725 条（23 条：19 处排印、2 处引号、题目数据里的弯引号版本 1 条、段首恢复 1 条）。阅读解析 25 个文件：说明前缀补 9 条、去 13 条，共改写 25 条说明；前缀说明现为 251 条；新增 2 句（12,744 → 12,746）。

### 统计（auto_pass / needs_review / rejected）

| 题型 | 第七轮 | 第八轮 |
|---|---|---|
| 主句谓语 main_verb_tap | 5922 / 454 / 6368 | 5926 / 452 / 6368 |
| 从句边界 clause_boundary | 4700 / 2561 / 2695 | 4705 / 2559 / 2692 |
| 从句类型 clause_type_classify | 11455 / 3427 / 1334 | 11465 / 3422 / 1331 |
| 状语关系 adverbial_relation | 404 / 653 / 2568 | 404 / 653 / 2565 |
| 主语范围 subject_span | 5371 / 809 / 6564 | 5377 / 806 / 6563 |
| 动词身份 finite_or_not | 12742 / 1732 / 6550 | 12749 / 1730 / 6550 |

- 候选 50,230 → 50,248：新增 21 道（91_49_p1 C-01 6 道、23_46_p1 B-04b 4 道，这两句修好引号后不再被整句过滤；32_20_p3 A-01 / A-01b / A-01c 11 道），去掉 3 道（原 32_20_p3 A-01 的旧题号）。新增题 14 道自动通过、7 道待复核。
- 状态变化：34 道 needs_review → auto_pass（U2 去掉前缀的 7 句）；13 道 auto_pass → needs_review（U1 的 4 句 11 道、U3 的 2 道）。题目内容只有 U6 那 1 道变化。
- 34 道恢复题和 14 道新增自动题逐题核对，局部答案、高亮和干扰项都正确，整句适合给学生（24_56_p3 C-05 的主句谓语题有一个干扰项也是 was，是从句里的 was，按位置点选，不算重复）。
- `sentence_review`：source_quality 149 句出了题、只因此降级 418 道；list_item 15 句出了题、只因此降级 50 道。
- 抽查表随自动通过池变化重抽，360 行中只有 56 道题仍在表里，按行号比较几乎全部换题；老师盲审尚未开始。

### 验证

| 检查 | 结果 |
|---|---|
| 可复现 | 连续两次生成逐字节一致：`generation_report_v0_2.json` `64c628fe0dc6…`、`generation_report_v0_2.md` `d840e8303e1e…`、`review_batch_v0_2.jsonl` `ba6bbe12e9f7…`、`review_batch_v0_2.xlsx` `4d18539cfee9…`；回归记录不变，7 项整句过滤预期吻合；知识图谱审阅文档只有句数变化 |
| 测试 | 新增 4 项（字母编号 1 项、at_start 3 项），并在原有列表测试里加了 a)、(iv)、100.、·、− 和对话破折号的用例，在破折号测试里加了真实句和 `2010–a` 两个用例。在旧代码上：破折号用例断言失败；列表用例导入 `list_letters` 失败，另用旧 `review_reasons` 逐句核对，新增写法都返回空、`— We agreed` 反而被判为列表；at_start 3 项断言失败。出题器、修订表、词汇表、知识图谱测试 101 项通过；只装 Flask 的 CI 列表 169 项运行、1 项按设计跳过；Node 通过；`tests.test_reading_study` 22 项通过 |
| 数据 | validator 0 错误；`--check` 0；从 raw 重建 171 篇一致；改动的三篇阅读解析逐段拼起来与 static 正文完全一致；无法识别的 role 没有新增；临时库先导入 main 快照（65f1859，与现在的 `origin/main` 676569c 在阅读解析、导入脚本和 models.py 上相同）再导入本分支：updated=233 / skipped=84 / failed=0 |
| 改动文件 Ruff | check 与 format --check 通过 |

### 第八轮遗留

- 判断仍依赖说明；复审按句子抽 50 句未见残留，但这不证明全池没有。
- 32_20_p3 的 `summary`、`target_para` 仍是数据源原样，网页和小程序阅读页都不显示；第 27 题的解析和中心句也是数据源原样，**会在网页复盘卡显示**（解析用 A 段的盲人摸象支撑答案 E，内容不对；第八轮复审 V3 更正：原写“不显示”有误）。84_73_p1 中心句引用缺失照旧。
- T2 多解（A8）未处理，理由见上表。
- 第六轮遗留的其余各项（含混 role、截短引用的大小写、ielts18_test3 的 `\x02` 等）不变。

## 第九轮（2026-10-27，第八轮复审 V1–V5；用户决定先保证剑桥雅思的题）

依据：`docs/GRAMMAR_ITEM_CANDIDATES_V0_2_ROUND8_CODEX_REVIEW.md`（结论不通过；0 阻断、3 应修、2 建议）。用户说明：最重要的是剑桥雅思配套的题没有问题，机经可以晚点处理。本轮只处理剑桥原文相关的问题和通用规则，机经的问题记录在下面，暂不改。

| 复审编号 | 问题 | 处理 |
|---|---|---|
| V1（剑桥） | 表语位置的 because 从句当状语从句自动通过（16_3_p2 H-04，3 道） | 出题器新增 `predicative_clause()`：advcl 挂在没有其他补足成分的 be 上、且紧跟在 be 后面（中间只允许 usually、only、probably 这类副词），就是表语从句，从句边界、从句类型、状语关系三种题加 `clause_type_mismatch` 降为待复核；前置的 if / when 从句（"If we are kind, it's usually because ..."）仍是状语从句。第一版只看“挂在光杆 be 上”，误伤了 10 句前置状语从句，已收紧。同类剑桥句的标注统一为表语从句：11_1_p2 E-04、11_4_p2 B-05、16_3_p2 H-04、19_4_p1 I-03、4_3_p2 D-02、17_1_p3 D-02（与同库 9_4_p2 C-06、16_4_p1 E-04 等一致，难点同步）。H-04 的 3 道和同类 B-05、I-03 的 4 道不再自动通过 |
| V2（机经） | pre-modem、Fischer-Price、Dr Witthof 三处排印 | 暂缓（用户决定）。92_58_p1 E-02 有 8 道自动通过题显示的原句含 Fischer-Price / Witthof |
| V3（机经） | 第八轮把第 27 题解析写成“不显示” | 第八轮遗留一节已更正：summary、target_para 不显示；第 27 题解析和中心句在网页复盘卡显示。数据本身暂缓 |
| V4 | 列表启发式的合成边界（IV.、•Item、相邻姓名缩写等） | 暂缓；当前语料没有对应的自动通过题 |
| V5 | at_start 与 at_end 可同时开启 | 暂缓；修订表没有双开条目，只用于机经修订 |

### 剑桥题自查

按用户的优先级，从剑桥自动通过题里另抽 60 道（种子 20261027，每种题型 10 道）逐题核对：局部答案、高亮和干扰项都正确，原句都适合给学生。其中 1 道值得商量：5_1_p1 A-01 “For the century before Johnson's Dictionary was published in 1755, ...” 的 before 从句修饰名词 century，答“状语从句”有争议。据此新增 `noun_attached_clause`：状语从句目标的 advcl 被解析器挂在名词、专名、数词或代词上时，三种从句题降为待复核。全库 40 道因此降级（剑桥 22：如 the decades since ...、'green deserts', as Ellwood describes them、the time before records began；机经 18），题目内容不变。粗筛“紧跟名词的 before / after / since / until”命中 74 道剑桥题，但几乎都是正常状语从句（前面的名词只是上一个短语的结尾），所以改用解析器的挂靠关系判断。

### 统计（auto_pass / needs_review / rejected）

| 题型 | 第八轮 | 第九轮 |
|---|---|---|
| 主句谓语 main_verb_tap | 5926 / 452 / 6368 | 5925 / 454 / 6367 |
| 从句边界 clause_boundary | 4705 / 2559 / 2692 | 4683 / 2579 / 2694 |
| 从句类型 clause_type_classify | 11465 / 3422 / 1331 | 11444 / 3443 / 1331 |
| 状语关系 adverbial_relation | 404 / 653 / 2565 | 399 / 657 / 2561 |
| 主语范围 subject_span | 5377 / 806 / 6563 | 5376 / 808 / 6562 |
| 动词身份 finite_or_not | 12749 / 1730 / 6550 | 12745 / 1730 / 6549 |

- 候选 50,248 → 50,243：改标的 5 句去掉 22 道、新增 17 道（新增的表语从句题都是待复核。这几句也少了几道原本正确的自动题：表语从句里的谓语动词不出动词身份题，少 4 道；16_3_p2 H-04 句中有两个名词性从句，名词性从句边界题不再出；4_3_p2 D-02 的 is 出现两次，主句谓语题转为待复核）。其余题目内容不变，只有状态变化：V1 规则 7 道、`noun_attached_clause` 40 道从 auto_pass 改为 needs_review。（第九轮复审 W6 更正：7 + 40 是固定旧标注、只换规则时的反事实计数，不是最终池的差分。按题号对比第八、九轮最终候选池，共同题号只有 41 道 auto_pass → needs_review：40 道 `noun_attached_clause`，1 道 T5 `ambiguous_span_location`。V1 那 7 道的旧题号已随改标被替换，不算共同题号。另有 16_3_p2 H-04 的 1 道 T1，干扰项 roles 元数据由 reason_clause 改为 predicative_clause，可见内容不变；reasons 有变化的共同题号是 61 道，不只 41 道。）
- auto_pass 合计 40,572，其中剑桥 28,029（第八轮 28,065）。
- 抽查表随池子变化重抽，与第八轮相比只有 39 道题仍在表里。现在 360 行里剑桥 233 行（自动 196、待复核 37），机经 127 行。

### 验证

| 检查 | 结果 |
|---|---|
| 可复现 | 连续两次生成逐字节一致：`generation_report_v0_2.json` `afbedc9fdff9…`、`generation_report_v0_2.md` `cc9bbe1008fa…`、`review_batch_v0_2.jsonl` `2120789b34b5…`、`review_batch_v0_2.xlsx` `5c9ae0ea5bd3…`；回归记录不变，7 项整句过滤预期吻合 |
| 测试 | 新增 5 项（真实句式及副词插在中间、be 有补足成分、其他动词、前置从句、挂在名词上的从句），涉及新规则的用例在修改前断言失败；出题器、修订表、词汇表、知识图谱测试 106 项通过；只装 Flask 的 CI 列表 174 项运行、1 项按设计跳过；Node 通过；`tests.test_reading_study` 22 项通过 |
| 数据 | validator 0 错误；无法识别的 role 没有新增；`--check` 0；从 raw 重建 171 篇一致；临时库先导入 main 快照（65f1859，与 `origin/main` 676569c 在阅读解析、导入脚本和 models.py 上相同）再导入本分支：updated=236 / skipped=81 / failed=0（第八轮是 233 / 84，本轮又有 3 篇剑桥解析与 main 不同） |
| 改动文件 Ruff | check 与 format --check 通过 |

### 第九轮遗留

- 机经：V2 三处排印、第 27 题错误解析（网页可见）、第八轮以前记录的机经遗留，等用户安排时再处理。
- T2 多解（A8）、列表启发式边界（V4）、at_start / at_end 互斥校验（V5）未改。
- 剑桥题的判断仍依赖原标注和解析器；本轮自查 60 道 + 复审历次抽查都未见错误答案，但这不证明全池没有。（第九轮复审另找到 W1–W4 四类剑桥自动题的问题，见第十轮。）

## 第十轮（2026-10-27，第九轮复审 W1–W6，按复审附录“修订方案 v0.1”实施）

依据：`docs/GRAMMAR_ITEM_CANDIDATES_V0_2_ROUND9_CODEX_REVIEW.md`（结论不通过；0 阻断、4 应修 W1–W4、2 建议 W5–W6，全部是剑桥自动通过题）及其附录的修订方案。按方案的“最小版”实施：只给有风险的题加复核原因、降为待复核，题号、题干、选项、答案、范围、干扰项都不改；另改三句难点说明。规则只看解析结构和标点，不读 passage_id、sentence_id 或 item_id。

| 复审编号 | 问题 | 处理 |
|---|---|---|
| W1 | 并列的从句题把“并列分句”当唯一答案，但目标同时在从属从句里（12_5_p1 C-04 `and why ...` 作宾语、D-07 `or when ...` 修饰 day、6_3_p2 A-05 共享 when 的状语等） | `coordinate_function_overlap()`，只接在从句类型题（T3）的 coordinate 分支，不改 `type_matches()`，从句边界题（T2）不受影响。沿 conj 链找到并列首项：首项不是全句的根，并且自己带从属引导词（as / because / that / if / so that 等 mark，不含 and / or）或以 wh 词开头，就加原因、降为待复核。只看首项自己的引导词，不看“有没有从属祖先”，所以引语里的正常并列（引语是 says 的 ccomp，首项没有引导词）不会命中 |
| W2 | 冒号或分号两边各有一个完整分句，主句谓语题、主语题却只有一个答案（17_1_p2 E-06 等 10 句） | `independent_clauses()`：全句根的 ccomp / parataxis / conj 子句是限定的、有自己的主语、与根之间隔着 `;` 或 `:`、不以 wh 词或从属引导词开头、边界两侧没有引号，就给 T1、T5 加 `multiple_independent_clauses`。E-06 那种被解析成 ccomp 的前半句也能识别（正常宾语从句和谓语之间没有冒号分号）。T6 隔离：`finite_targets()` 复制主句题原因时去掉这个原因，T6 照常按自己的动词判断。没有接进 `main_selection()`，不会让 T1 被拒、连带丢掉 T6 |
| W3 | 15_1_p3 F-04、7_3_p1 B-07 分号后是独立主格（being / being learned 不是限定谓语），说明没写成原句问题 | 两句第一条难点改写并加“原句问题：”，整句按原有规则待复核。采用复审草稿的两种改法（分号改逗号保留独立主格；或保留分号，being → was、being learned → are learned）；措辞改为“分号一般连接两个独立分句……标点不够规范”，不说独立主格本身不合法 |
| W4 | 15_2_p3 A-01 `as early as six weeks old, when babies begin to laugh ...` 的 when 从句也可以分析成回指年龄的非限制性定语从句，从句边界题和类型题却按“状语从句”自动通过 | `age_expression()`：when 从句前紧挨着逗号，逗号前三个词是“数词 + day / week / month / year(s) + old”，就按 `possible_relative_adverb` 处理（与原来的名词前 when 共用入口，T2 / T3 / T4 都适用）。没有逗号的 `He was ten years old when he moved` 不算。A-01 第三条难点改为两种分析都说得通、不加前缀；复审草稿最后一句“若题目要求单选……需要先明确分析口径”是写给出题人的，学生在阅读页会看到，所以没有放进去 |
| W5（建议） | `noun_attached_clause` 是保守筛选，22 道剑桥降级题里 9 道是正常状语从句 | 不改，接受保守误降（只降为待复核，不删题不改答案）；老师应按整句判断，原因码不等于错误判定 |
| W6（建议） | 第九轮把规则反事实计数和最终池差分混写 | 第九轮一节已更正；本轮按三种口径分别统计（见下） |

验收时又发现一处 W2 的漏洞并修正（5bf45ac）。原来只看被挂子句开头有没有引号，但解析器有时把冒号后引号里的句子当根，把说话人那半句挂成它的 ccomp，比如 17_1_p3 B-04 `Charles commenced his story: 'After ..., I began ...'`。复审方案把直接引语列为不应加原因的控制例，所以现在分隔符后紧跟引号也跳过。这只会减少命中：剑桥 8 道、机经 1 道去掉了这个原因，都还因其他原因待复核，状态不变。代价是 16_1_p3 I-01 `... for everyone: '...,' says Low.` 确实有两个主句，也不再带这个原因（它本来就待复核）。

### 42 道回归题

复审给的回归集是 42 个题号、30 句，修复前全部 auto_pass、没有复核原因。修复后全部 needs_review，各自只多了一个原因，局部答案不变（保留原标注答案，留给老师判断）。

| 组 | 题号 | 题型 | 句子 | 修复后原因 | 局部答案 | 题干判断 |
|---|---|---|---|---|---|---|
| W1 | gi_v02_8d37d96a8c41 | T3 | 10_1_p1 E-01 | coordinate_function_overlap | 并列分句 | 在共享 as 的原因状语从句里 |
| W1 | gi_v02_ac9f8535a872 | T3 | 10_4_p3 A-03 | coordinate_function_overlap | 并列分句 | 在共享 as 的状语从句里 |
| W1 | gi_v02_db4a94e67ec4 | T3 | 11_2_p2 B-07 | coordinate_function_overlap | 并列分句 | 在共享 As 的状语从句里 |
| W1 | gi_v02_5098e4ecac73 | T3 | 11_3_p3 G-07 | coordinate_function_overlap | 并列分句 | 在 watching as ... 的状语从句里 |
| W1 | gi_v02_0bd648f0066e | T3 | 12_5_p1 C-04 | coordinate_function_overlap | 并列分句 | and why ... 作 explains 的宾语，名词性从句 |
| W1 | gi_v02_cced38be072a | T3 | 12_5_p1 D-07 | coordinate_function_overlap | 并列分句 | or when ... 修饰 a day，定语从句 |
| W1 | gi_v02_1a3f8293a80a | T3 | 13_4_p2 D-01 | coordinate_function_overlap | 并列分句 | 在共享 as 的状语从句里 |
| W1 | gi_v02_4c275b496ac1 | T3 | 14_1_p3 K-03 | coordinate_function_overlap | 并列分句 | 在 It was found that ... 的主语从句里 |
| W1 | gi_v02_d01f41961eff | T3 | 16_1_p2 E-05 | coordinate_function_overlap | 并列分句 | or what ... 作 on 的宾语，名词性从句 |
| W1 | gi_v02_60cb6a4601fa | T3 | 16_2_p3 J-02 | coordinate_function_overlap | 并列分句 | and how ... 是 It is remarkable 的真正主语 |
| W1 | gi_v02_48bddfc51ad7 | T3 | 18_1_p2 F-04 | coordinate_function_overlap | 并列分句 | 在共享 so that 的状语从句里 |
| W1 | gi_v02_d661a884e51f | T3 | 20_1_p1 I-04 | coordinate_function_overlap | 并列分句 | 在共享 until 的状语从句里 |
| W1 | gi_v02_077495b556b8 | T3 | 6_2_p2 A-02 | coordinate_function_overlap | 并列分句 | 在 reveal that ... 的宾语从句里 |
| W1 | gi_v02_23f3ec6f71a5 | T3 | 6_3_p2 A-05 | coordinate_function_overlap | 并列分句 | and where ... 与 when ... 并列作状语 |
| W1 | gi_v02_4919084edc4c | T3 | 7_2_p3 D-07 | coordinate_function_overlap | 并列分句 | 在共享 because 的状语从句里 |
| W1 | gi_v02_7f0cf16fab32 | T3 | 8_2_p2 F-05 | coordinate_function_overlap | 并列分句 | 在共享 as 的状语从句里 |
| W1 | gi_v02_8e07cbab650d | T3 | 8_3_p2 E-02 | coordinate_function_overlap | 并列分句 | 在 the fact that ... 的同位语从句里 |
| W2 | gi_v02_5690b731fad2 | T1 | 17_1_p2 E-06 | multiple_independent_clauses | have / become | 冒号前 There have been ... 也是完整分句，主句谓语不唯一 |
| W2 | gi_v02_3d42601b8d9c | T5 | 17_1_p2 E-06 | multiple_independent_clauses | the mixed-use facilities at Wembley and Old Trafford | 同上，完整主语不唯一 |
| W2 | gi_v02_fa5a06f81026 | T1 | 12_8_p2 E-02 | multiple_independent_clauses | could / not / be | 分号前 This policy would also greatly boost ... 是另一主句 |
| W2 | gi_v02_ec4d82f4d263 | T5 | 12_8_p2 E-02 | multiple_independent_clauses | the fishing industry's insistence ... | 同上 |
| W2 | gi_v02_88f13fac6658 | T1 | 13_4_p2 B-06 | multiple_independent_clauses | costs | 冒号前 Soils also store water 是另一主句 |
| W2 | gi_v02_e76742369569 | T5 | 13_4_p2 B-06 | multiple_independent_clauses | damage to buildings, roads and bridges ... | 同上 |
| W2 | gi_v02_d5e448590295 | T1 | 14_3_p3 F-04 | multiple_independent_clauses | are | 冒号前 Play is process oriented 是另一主句 |
| W2 | gi_v02_5be941a91aed | T5 | 14_3_p3 F-04 | multiple_independent_clauses | the means | 同上 |
| W2 | gi_v02_2e69d0c43c2e | T1 | 14_3_p3 F-07 | multiple_independent_clauses | must / be | 冒号前 Play is actively engaged 是另一主句 |
| W2 | gi_v02_cf9221c3ec44 | T5 | 14_3_p3 F-07 | multiple_independent_clauses | Players | 同上 |
| W2 | gi_v02_45903e2a439d | T1 | 20_2_p3 A-03 | multiple_independent_clauses | was / mounted | 分号前 The contraption looked like ... 是另一主句 |
| W2 | gi_v02_039e5b6e4241 | T1 | 4_3_p2 C-04 | multiple_independent_clauses | inch | 冒号前 Sometimes it is slow 是另一主句 |
| W2 | gi_v02_2a33047fcd6c | T5 | 4_3_p2 C-04 | multiple_independent_clauses | vast bubbles of magma - molten rock from the mantle - | 同上 |
| W2 | gi_v02_99249b0927cf | T1 | 5_4_p1 A-03 | multiple_independent_clauses | requires | 冒号前 The attraction of these areas is obvious 是另一主句 |
| W2 | gi_v02_fc21ccd2630c | T1 | 6_4_p3 E-08 | multiple_independent_clauses | should / be | 分号前 curriculum work alone may only have ... 是另一主句 |
| W2 | gi_v02_4445ed6322d4 | T1 | 8_2_p3 F-03 | multiple_independent_clauses | may / be | 冒号前 Odours are invested with cultural values 是另一主句 |
| W2 | gi_v02_bdd363f085d7 | T5 | 8_2_p3 F-03 | multiple_independent_clauses | smells that are considered to be offensive in some cultures | 同上 |
| W3 | gi_v02_7b702aabb705 | T2 | 15_1_p3 F-04 | source_quality | who simply enjoy travel or discovering new things | 局部答案成立；原句分号后是独立主格，整句待复核 |
| W3 | gi_v02_9ab094841299 | T3 | 15_1_p3 F-04 | source_quality | 定语从句 | 同上 |
| W3 | gi_v02_237c28eb99a6 | T6 | 15_1_p3 F-04 | source_quality | 从句里的谓语（enjoy） | 同上 |
| W3 | gi_v02_604e3328ad97 | T2 | 7_3_p1 B-07 | source_quality | as the child grows up | 同上 |
| W3 | gi_v02_c88af5a29c0e | T3 | 7_3_p1 B-07 | source_quality | 状语从句 | 同上 |
| W3 | gi_v02_10587d4ba8fd | T6 | 7_3_p1 B-07 | source_quality | 从句里的谓语（grows up） | 同上 |
| W4 | gi_v02_7e2180fd8faf | T2 | 15_2_p3 A-01 | possible_relative_adverb | when babies begin to laugh and smile in response to stimuli | 边界成立，但题干预设它是状语从句 |
| W4 | gi_v02_7b4122b362c5 | T3 | 15_2_p3 A-01 | possible_relative_adverb | 状语从句 | 也可分析为回指 six weeks old 的定语从句，单选不安全 |

### 新命中与复查

- **W1**：剑桥另有 10 道 auto 降级。它们都在复审列出的 27 个“未确认类别错误”的并列目标里：
  - 8 道的第二个并列项可以理解为仍在前面的从属从句里，例如 6_4_p2 J-27 `warns that ... and similar campaigns ... might not work`、7_4_p1 A-07 `wondered if ... and the men were using it`，所以互斥单选不安全，降级有道理。这 8 道是 10_1_p3 D-01、10_3_p3 F-01、15_1_p2 B-02、15_1_p3 D-03、18_3_p1 E-07、5_3_p3 G-44、6_4_p2 J-27、7_4_p1 A-07。
  - 2 道是误伤：
    - 4_1_p3 E-20 第三项 `and the bent spokes were taken as a sign ...`：中间一项带 they thought，三项都是独立分句。
    - 5_1_p3 C-11 `and four factors seem to cause ...`：这是作者自己的判断，不属于 polls suggest 的内容。
  - 解析器把这两句挂进了 that 从句，规则分不开，只能保守降级。
  - 其余 17 个目标不受影响，仍自动通过，都是正常的主句并列。
  - 44 个目标上的 35 道 T2 都没有加这个原因，状态不变；全库没有 T3 以外的题带这个原因。
  - 另有 27 道剑桥题本来就待复核，这次加了这个原因，逐题看过，基本都是共享引导词的 that / whether / when / which 从句并列。4_1_p3 E-20 的另一道同样属于上面的误伤。
- **W2**：
  - 复审逐条看过的 109 句剑桥 auto T1 含冒号或分号，修复后只有回归集那 10 句降级，其余 99 句仍自动通过。同句的 T5 有 7 道降级，都在回归集里。T6 一道都没有带这个原因。
  - 回归集外，剑桥只多降 1 道：12_6_p1 A-01 的 T5，即 `Two things distinguish ...: first, every single person needs food ...; and second, it is hugely dependent on nature.`。它和 E-06 是同一结构，降级成立。
  - 另有 54 道剑桥题本来就待复核，这次加了这个原因，都是冒号或分号两侧各有完整分句。
- **W3**：两句全部 8 道题都带 `source_quality`，其中 6 道原 auto、2 道原本已待复核，没有残留 auto。
- **W4**：
  - 全库只命中 A-01 这一个目标的 2 道题；同句其余 5 道 auto（T1 start、T3 in response to stimuli、T5 Humans、T6 start / begin）不变。
  - 复审 ADJ 挂靠扫描里另外 3 个正常目标都没有加原因，仍自动通过：10_3_p3 F-04 `as landing on the moon is for us today`、11_4_p1 B-02 `than fraternal twins are`、20_1_p2 A-05 `if you hadn't seen ...`。
- **机经（暂缓，只列影响）**：
  - W1 降级 13 道 T3，例如 77_16_p2 C-01、91_49_p3 F-07、65_69_p2 B-04 的 `that ... , they want ... and they want ...`。
  - W2 降级 5 道（40_75_p1 A-04 的 T1 / T5、6_71_p1 I-03 的 T1、91_49_p1 H-02 的 T1 / T5），都是冒号或分号两侧各有完整分句。
  - 另有 48 道机经题本来就待复核，这次加了原因。

### 统计（auto_pass / needs_review / rejected）

| 题型 | 第九轮 | 第十轮 |
|---|---|---|
| 主句谓语 main_verb_tap | 5925 / 454 / 6367 | 5912 / 467 / 6367 |
| 从句边界 clause_boundary | 4683 / 2579 / 2694 | 4680 / 2582 / 2694 |
| 从句类型 clause_type_classify | 11444 / 3443 / 1331 | 11401 / 3486 / 1331 |
| 状语关系 adverbial_relation | 399 / 657 / 2561 | 399 / 657 / 2561 |
| 主语范围 subject_span | 5376 / 808 / 6562 | 5366 / 818 / 6562 |
| 动词身份 finite_or_not | 12745 / 1730 / 6549 | 12743 / 1732 / 6549 |

候选仍是 50,243 道，题号集合不变；除 status 和 reasons 外，所有字段与第九轮逐题相同（0 道有其他变化）。三种口径（剑桥 / 机经）：

| 原因 | 全量带此原因 | 只因此原因待复核 | 共同题号实际 auto → needs |
|---|---|---|---|
| coordinate_function_overlap（新） | 54 / 28 | 27 / 13 | 27 / 13 |
| multiple_independent_clauses（新） | 72 / 38 | 18 / 5 | 18 / 5 |
| possible_relative_adverb | 144 / 92（第九轮 142 / 92） | 97 / 46（95 / 46） | 2 / 0 |
| source_quality | 17 / 607（9 / 607） | 15 / 407（9 / 409） | 6 / 0 |

- 实际状态变化共 71 道，全部是 auto_pass → needs_review（剑桥 53、机经 18），每道只多一个原因；没有题从待复核变回自动，也没有题少了原因。auto_pass 40,572 → 40,501，其中剑桥 28,029 → 27,976。
- 本来就待复核、这次只是多了原因的有 131 道（剑桥 83、机经 48），不算新增降级。机经“只因 source_quality”从 409 变 407，是因为其中 2 道多了别的原因，不是原因被去掉。
- 抽查表随池子变化重抽：360 行里只有 13 个题号仍在表里，按 (工作表, 行号) 对比没有一行还是同一道题；老师的结果须按题号迁移。现在剑桥 231 行（自动 196、待复核 35），机经 129 行。六张表各 60 行，判定列下拉仍是四项，表里不出现状态和原因（盲审）。

### 验证

| 检查 | 结果 |
|---|---|
| 可复现 | 连续两次生成逐字节一致：`generation_report_v0_2.json` `274d989b44eb…`、`generation_report_v0_2.md` `c1076ca682cb…`、`review_batch_v0_2.jsonl` `e3a503b8742d…`、`review_batch_v0_2.xlsx` `386ea7e0564e…`；13 组 × 6 的回归记录不变，7 项整句过滤不变；`GRAMMAR_GRAPH_V0_REVIEW.md` 重新渲染无变化 |
| 测试 | 新增 7 项（W1 3、W2 2、W4 2），另在 W2 的控制例里补了引语作根的一例。修改前：W1 是 1 项断言失败 + 2 项接口错误（Reason 常量不存在；第十轮复审更正，原写“函数不存在”不准确），W2 整个测试模块导入失败（函数不存在），W4 是 1 项断言失败，引语控制例是 1 项断言失败。出题器、修订表、词汇表、知识图谱测试 113 项通过；只装 Flask 的 CI 列表 181 项运行、1 项按设计跳过；Node 通过；`tests.test_reading_study` 22 项通过 |
| 数据 | 三句只改了指定的那一条 difficult_points，其他字段逐字节不变；validator 0 错误；`--check` 0；从 raw 重建 171 篇一致。临时库先导入 main 快照（65f1859，与 `origin/main` 676569c 在阅读解析、导入脚本和 models.py 上相同），再导入本分支，实测 updated=236 / skipped=81 / failed=0。与第九轮相同，原因是另两篇（15_1_p3、15_2_p3）在第九轮已经因为词汇表标签不同算作 updated |
| 改动文件 Ruff | check 与 format --check 通过 |

### 第十轮遗留

- W1：that 从句后接不带 that 的并列分句时，解析结构分不清第二项是否仍在从句里，现在一律降级，已知误伤 2 句。role 字段只能表示一种身份，并列兼从属的目标没有改标；要彻底解决，需要把类型题改成两个维度，题干、选项和标注规范要一起改。
- W2：只降级，不改题干，也不出多答案。引号边界的规则会漏掉 16_1_p3 I-01 这类“引语 + says X”的两个主句。
- W4：只覆盖“数词 + 时间单位 + old + 逗号 + when”。`at the age of ...` 等其他写法没有覆盖。
- W5 的保守误降、T2 多解（A8）、V4 / V5 未改。机经暂缓的各项不变：V2 排印、第 27 题解析等。
- 修订和自查仍由同一方完成。

## 第十一轮（2026-10-27，第十轮复审 X1–X4）

依据：`docs/GRAMMAR_ITEM_CANDIDATES_V0_2_ROUND10_CODEX_REVIEW.md`。复审结论是不通过，以剑桥题为准：W1–W4 点名问题和 W6 关闭，W5、A8 保留。新增 0 阻断、3 应修（X1–X3，17 道剑桥自动题，第九轮已存在）、1 建议（X4）。规则仍只看原文字符和解析结构，不读题号或句号。

| 复审编号 | 问题 | 处理 |
|---|---|---|
| X1 | 连字符动词被分词拆开，13 道剑桥自动题的答案、高亮或干扰项只有半个词：`could / re`、`【is not pre】-set`、干扰项 `to re` / `-` / `establish`、`to be road-【tested】` | 新增 `hyphenated_word_split`：答案、目标、干扰项（含各段 parts）任一起止点紧挨词内连字符（两侧都是字母或数字、没有空格），就降为待复核。T6 按自己的高亮判断，不继承 T1 的这个原因。被解析器标成 VERB 的纯标点不再当干扰项（剑桥 3 道、机经 2 道去掉了单独的 `-`）。没有把连字符词合并成一个动词单位：复审说明 T1 答案规则冻结时先降级，改答案规则需另行批准 |
| X2 | back-up、check-out 是名词性定语，被做成动词干扰项 back / up、check / out | 同一规则命中（干扰项的起止点在 back-up、check-out 内部），降为待复核；没有按 amod 一刀切 |
| X3 | `%` 被当作标点裁掉，完整主语成了 `A full 94`、`... – 53` | `trim_tokens()` 保留紧跟数字的 `%`。J-40 因此也补回了闭合破折号。两道答案改为 `A full 94%`、`only a small majority of sighted subjects – 53% –`，仍自动通过 |
| X4 | 并列首项的 and / or 被标成 mark 时会误判为从属；年龄规则对 where / why 也生效，与说明不一致 | 排除全部并列连词（and / but / or / nor / for / so / yet）；年龄规则只看 when。全库候选池无变化，与复审结论一致 |
| 第十轮更正 | W1 负测的 2 项接口错误是 Reason 常量不存在，不是函数不存在 | 已改第十轮一节 |

四项分开提交（65a77e8 X1/X2、0a1f9c5 X3、d53f8ba X4），每步各生成一次，用来归因；最后统一重新生成。

### 17 道回归题

| 题号 | 题型 | 句子 | 修复前 | 修复后 | 说明 |
|---|---|---|---|---|---|
| gi_v02_39a5639ec9f7 | T1 | 12_8_p2 G-02 | auto | needs（hyphenated_word_split） | 主答案 is 正确；干扰项 to re / establish 是半个词，单独的 `-` 已去掉 |
| gi_v02_2612039eb0fc | T1 | 16_1_p3 M-03 | auto | needs | 主答案 are 正确；干扰项 to pre / empt，`-` 已去掉 |
| gi_v02_9d25c9be58aa | T1 | 7_3_p3 A-04 | auto | needs | 主答案 has / been 正确；干扰项 to co / ordinate，`-` 已去掉 |
| gi_v02_4f9aff5be0d3 | T1 | 10_1_p3 D-02 | auto | needs | 答案 are / wired 缺 hard- |
| gi_v02_ada51e0516f7 | T6 | 10_1_p3 D-02 | auto | needs | 高亮【are】hard-【wired】 |
| gi_v02_d3ad4b5fc6b8 | T1 | 15_2_p2 D-06 | auto | needs | 答案 could / re 缺 -establish |
| gi_v02_facbcdde7ef5 | T6 | 15_2_p2 D-06 | auto | needs | 高亮【could】…【re】-establish |
| gi_v02_411c43f579e8 | T1 | 4_3_p3 D-13 | auto | needs | 答案 record 缺 tape- |
| gi_v02_7bd50392fc2c | T6 | 4_3_p3 D-13 | auto | needs | 高亮 tape-【record】 |
| gi_v02_177f2e3cb51e | T1 | 7_4_p2 E-04 | auto | needs | 答案 is / not / pre 缺 -set |
| gi_v02_96c3342be4bf | T6 | 7_4_p2 E-04 | auto | needs | 高亮【is not pre】-set |
| gi_v02_9102debcb432 | T1 | 18_3_p2 F-02 | auto | needs | 主答案 shipped 正确；干扰项 to be / tested 缺 road- |
| gi_v02_f0cf657b23e2 | T6 | 18_3_p2 F-02 | auto | needs | 高亮【to be】road-【tested】 |
| gi_v02_1213768264f6 | T1 | 14_2_p2 I-02 | auto | needs | 主答案 have / worked 正确；干扰项 back / up 是名词定语 back-up 的一部分 |
| gi_v02_b983993a8787 | T1 | 9_3_p3 E-28 | auto | needs | 主答案 have / become 正确；干扰项 check / out 是 check-out lasers 的一部分 |
| gi_v02_50bd636fe569 | T5 | 4_1_p3 J-33 | auto（A full 94） | auto（A full 94%） | 答案改正 |
| gi_v02_45648a820455 | T5 | 4_1_p3 J-40 | auto（… – 53） | auto（… – 53% –） | 答案改正，闭合破折号补回 |

### 新命中、副作用与复查

**连字符规则在剑桥的额外命中：41 道 auto 降级，都是 T1。**
- 1 道是复审没列出的同类答案错误：5_3_p3 A-03 的 T1 答案是 `re`（原文 re-entered），降级成立。它的 T6 本来就待复核。
- 40 道的主句答案正确，但干扰项是复合形容词的后半截，比如 water-borne 的 borne、problem-solving 的 solving、self-driving 的 driving、so-called 的 called、solar-powered 的 powered。高亮的是半个词，和 X1 的 road-tested 同理，降级成立。
  - 另一种处理是从干扰项里去掉这些片段、题目保留自动通过，但那会改动干扰项内容，本轮按复审的最小改法只降级。
- 另有 7 道剑桥题本来就待复核，这次多了这个原因（T6 的 to pre、to re、to co、re，以及 ice-forming、well-defined、Abundance-Based 三个干扰项片段）。

**百分号修正的副作用（剑桥），逐题看过：**
- 4 道 T3 的目标现在包含 `%`，因此换了题号。旧题号是待复核（解析树带 `%`、标注范围裁掉 `%`，对不上）；新题号自动通过，答案都正确：
  - 10_1_p2 C-04 `while during the same period rail haulage decreased by 43.5%`：状语从句
  - 13_1_p1 F-03 `while transport and accommodation account for the remaining 26%`：状语从句
  - 20_2_p1 J-02 `of 20%`：不是从句
  - 6_2_p2 H-26 `the use of bath seats has grown by more than 50%`：并列分句
- 3 道从待复核变为自动通过：
  - 10_1_p2 C-04 T6 decreased、13_1_p1 F-03 T6 account：都是从句里的谓语，正确。
  - 6_2_p2 H-26 T2：答案补上了 `%`，边界正确。但这句前半 `the use of raised toilet seats has more than doubled ...` 也是并列分句，题干“划出句中的并列分句”却只接受后一句，属于既有的 A8 多解问题（见遗留）。
- 答案变化另有 J-35 `And only 51%`（本来就待复核）。另有 19 道剑桥题只是解析证据里的子树范围多了 `%`，其他字段不变。

**复审的扫描口径在新池上重跑（剑桥 auto）：**
- 起止点在连字符词内部：0
- 干扰项不含字母：0
- 范围紧挨在 `%` / `°` 前结束：0

**机经（暂缓，只列影响）：**
- auto → needs 30 道（T1 20、T3 4、T6 4、T2 2）。其中几处是原文把破折号写成不带空格的连字符，比如 78_102_p3 A-02 `electricity-half of which ...`、92_58_p1 F-03 `people-using ...`，属于机经原文排印问题，降级是对的。
- needs → auto 1 道：44_29_p2 H-01 的 T6 stands，是从句里的谓语，正确。
- 答案变化 4 道：92_58_p2 H-07 `Only 1.5%` 自动通过，正确；另 3 道本来就待复核。
- 换题号 4 道，新旧题号都是待复核。

### 统计（auto_pass / needs_review / rejected）

| 题型 | 第十轮 | 第十一轮 |
|---|---|---|
| 主句谓语 main_verb_tap | 5912 / 467 / 6367 | 5841 / 538 / 6367 |
| 从句边界 clause_boundary | 4680 / 2582 / 2694 | 4679 / 2583 / 2694 |
| 从句类型 clause_type_classify | 11401 / 3486 / 1331 | 11401 / 3486 / 1331 |
| 状语关系 adverbial_relation | 399 / 657 / 2561 | 399 / 657 / 2561 |
| 主语范围 subject_span | 5366 / 818 / 6562 | 5366 / 818 / 6562 |
| 动词身份 finite_or_not | 12743 / 1732 / 6549 | 12737 / 1738 / 6549 |

**候选与状态：**
- 候选仍是 50,243 道，换了 8 个题号：剑桥 4 道待复核换成 4 道自动通过的新题号，机经 4 道待复核换成 4 道待复核的新题号。
- 共同题号的状态变化：
  - auto → needs：剑桥 56（T1 51、T6 5），机经 30；
  - needs → auto：剑桥 3，机经 1。

**`hyphenated_word_split` 三种口径（剑桥 / 机经）：**

| 口径 | 剑桥 | 机经 |
|---|---|---|
| 全量带此原因 | 63 | 45 |
| 只因此原因待复核 | 56 | 30 |
| 共同题号实际 auto → needs | 56 | 30 |
| 本来就待复核、只多了原因（不算新增降级） | 7 | 15 |

**除 status / reasons 外的字段变化：**
- 答案 8 道（剑桥 4、机经 4）
- 干扰项 5 道（去掉单独的 `-`）
- 解析证据 29 道（其中 21 道只有这一处变化）

**auto_pass：** 40,501 → 40,423，其中剑桥 27,976 → 27,927（−56 + 3 + 4）。

**抽查表：** 随池子变化重抽，只有 13 个题号仍在表里，按 (工作表, 行号) 对比没有一行还是同一道题。现在剑桥 237 行（自动 196、待复核 41），机经 123 行。六张表各 60 行，判定列下拉仍是四项，表里不出现状态和原因（盲审）。

### 验证

| 检查 | 结果 |
|---|---|
| 可复现 | 连续两次生成逐字节一致：`generation_report_v0_2.json` `d9c280216849…`、`generation_report_v0_2.md` `a404f8afc867…`、`review_batch_v0_2.jsonl` `f8b14a0de986…`、`review_batch_v0_2.xlsx` `68bac14def85…`；13 组 × 6 的回归记录不变，7 项整句过滤不变；`GRAMMAR_GRAPH_V0_REVIEW.md` 重新渲染无变化 |
| 测试 | 新增 9 项：连字符 4、百分号 3、X4 2。修改前的结果：<br>· 6 项断言失败；<br>· 2 项接口错误：一项缺 `split_word` 函数，一项缺 `HYPHENATED_WORD_SPLIT` 常量，后者是“复合形容词作为整体不受影响”的控制例，其余断言在旧代码上能通过；<br>· 1 项控制例通过：普通句末标点照旧裁掉。<br>出题器、修订表、词汇表、知识图谱测试 122 项通过；只装 Flask 的 CI 列表 190 项运行、1 项按设计跳过；Node 通过；`tests.test_reading_study` 22 项通过 |
| 数据 | 本轮没有改阅读解析；validator 0 错误；`--check` 0；从 raw 重建 171 篇一致；临时库先导入 main 快照再导入本分支：updated=236 / skipped=81 / failed=0 |
| 改动文件 Ruff | check 与 format --check 通过 |

### 第十一轮遗留

- **A8（T2 并列分句多解）仍未处理，需要决定改法。** 剑桥现有 345 道自动通过的“划出句中的并列分句”题：句中至少有两个并列分句，题干却没说划哪一个，只接受标注的那一个。本轮 X3 修正后，6_2_p2 H-26 又多了一道这样的自动题。可选改法：
  1. 题干写明连词，例如“划出 and 后面的并列分句”，答案不变；
  2. 全部降为待复核。

  第一种改动题干，需要用户同意。
- **连字符词：**
  - 40 道复合形容词片段干扰项是按最小改法降级的，也可以改成去掉这些干扰项、保留自动通过。
  - 真正的连字符动词（re-establish、hard-wired、tape-record）也可以合并成一个完整的动词单位，改正 T1 答案。

  两者都会改动题目内容，需要另行同意。
- W5 的保守误降、V4 / V5 未改；机经暂缓的各项不变。
- 修订和自查仍由同一方完成。

## 线上状态

未合并 main，未部署，没有操作生产服务器或数据库。上线步骤和以前一样，需要用户另行授权：合并 main 并部署 → 服务器备份数据库 → 运行 `scripts/import_reading_study.py`（第十一轮后，以 `origin/main` 65f1859 / 676569c 为基准实测 updated=236；词汇表标签要在部署后的新代码下导入才会生效）。
