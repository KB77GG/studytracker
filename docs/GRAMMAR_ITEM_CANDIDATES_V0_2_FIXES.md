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

## 遗留（规则查不出来，需要另行决定）

- **真词错字**：`reading_jijing_27_test_33_p1` B-09 的 `claim mat the image` 应为 `claim that`。`mat` 是真实单词，断词规则查不出来。如果同意，可以作为第 34 条加进 `data/reading_jijing_text_fixes.json`，同时改阅读解析的句子；这样上线时会多更新 1 篇。
- **段首多余句点**：3 篇机经（`29_63_p1`、`78_102_p1`、`92_58_p2`）共 14 个段落的第一句以 `. ` 开头，例如 `. To encourage reform …`。这来自原文抽取，学生在阅读页也会看到。可以修原文（14 条修订），也可以加一条整句过滤，需要用户决定。
- 51 个“一条里含多句”的单元仍然只在出题时排除，是否重新拆句待用户决定。

## 线上状态

未合并 main，未部署，没有操作生产服务器或数据库。上线步骤和以前一样，需要用户另行授权：合并 main 并部署 → 服务器备份数据库 → 运行 `scripts/import_reading_study.py`（预期 updated=25）。
