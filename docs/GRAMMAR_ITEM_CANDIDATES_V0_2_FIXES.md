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

- 处理：T3 的从句类目标和 T4 的目标，现在也必须和句法树的从句范围一致，不一致时加 `boundary_mismatch`，降为 needs_review。短语和非谓语目标不检查，因为它们的边界本来就不严格，严格检查会误降 2,333 道。
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
| 并列分句目标不得带从属连词 | 逐题核对时发现 `and because …`、`and that …` 这类“并列的从句”被当成并列分句出题，答案错误 | 23 道从自动通过降为待人审；`92_58_p2` C-01 的标注同时改为原因状语从句 |
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

## 线上状态

未合并 main，未部署，没有操作生产服务器或数据库。上线步骤和以前一样，需要用户另行授权：合并 main 并部署 → 服务器备份数据库 → 运行 `scripts/import_reading_study.py`（第三轮后预期 updated=187；词汇表标签要在部署后的新代码下导入才会生效）。
