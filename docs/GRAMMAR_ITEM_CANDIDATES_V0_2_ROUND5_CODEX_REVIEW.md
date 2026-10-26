# 语法候选题 v0.2 第五轮独立复审（Codex）

审核日期：2026-10-26。固定基线 `1f03c84`，固定终点 `f565da265f74faf5d745267c701c9f32e1c4c009`；不包含之后的实现。只审核、只记录，未修改被审代码、数据、交付文件。

## 结论：不通过

**原阻断 R1/B1 已关闭；本轮新增 0 阻断、4 应修（Q1–Q4）、2 建议（A5–A6）。** 代码层面的主要修复、两次生成、数据重建与临时库导入均复现。仍有新改写的教学解释不准确、题目字段遗漏、两处可确定排印错误，以及自查记录的全称结论/新增池状态数字错误。不能把测试通过等同教学内容验收通过。

新增83题实际为 **69 auto_pass / 14 needs_review**，不是自查所称71/12。69道自动题未发现新的核心答案错误；但4道来自列表片段，应与既有A3的整句适用性问题一起处理。14道待复核题内确有错误/不完整范围，不能写“83道答案和高亮全部正确”。抽查表30题局部答案/高亮通过；改动句自动池另30题局部答案正确，部分原句仍有已披露的语病或残缺，详见明细。

### 两份前审的逐项关闭情况

| 编号 | 状态 | 独立依据 |
| --- | --- | --- |
| 第一轮 R1 | 关闭 | 全量T1干扰项直接子节点复查：遗漏0，越界而auto_pass或漏原因0；3道共同题降级。 |
| 第一轮 R2 | 关闭实际回归 | 数字引语gi_v02_96287b126ba9完整恢复；受控反事实全库只有1道范围变化。泛化边界见A5。 |
| 第一轮 R3 | 原19句关闭；全库治理继续 | 19个点名句中的旧坏串均消失；新漏网见Q3，不宣称OCR召回100%。 |
| 第一轮 R4 | 关闭 | 文档更正933新增降级，另1道本已待复核；不再称全是误降。 |
| 第一轮 A1 | 关闭文档问题 | 保守降级不等于答案错误，第一轮记录已区分。 |
| 第一轮 A2 | 未实现，按已披露保留 | 所有格/嵌套引语合成反例仍成立；无本轮真实新坏题，见A5。 |
| 第一轮 A3 | 关闭实际括号问题 | 第二轮的有界括号补回仍在，数字引语括号与引号完整。 |
| 第二至四轮 B1 | 关闭 | 与第一轮R1同一缺陷，不重复计新问题。 |
| 第二至四轮 N1 | 清单流程关闭；内容质量另见Q1 | 108条旧记录独立对照106条难点改写、2个ID并入相邻句，无未处理条；120句124条新说明可逐条定位；同篇Couran/Prideaux统一。 |
| 第二至四轮 N2 | 部分关闭，不能整体关闭 | 原点名同步和替换边界修复有效；另发现6个groups字段仍与正文不一致，Q2。 |
| 第二至四轮 N3 | 原11处改正；新增解释问题未关闭 | 原主语/词性/指代/译文等意见均落实；B-03改role正确但新增for说法过绝对，Q1。 |
| 第二至四轮 N4 | 关闭点名范围 | 4种role对应5个实例已按原意见改；15个ellip角色29处映射符合成分。约85处含混role不在此关闭声明内。 |
| 第二至四轮 N5 | 关闭 | 固定12657基线、94增/7删/净87、counting_notes与历史集合一致；510字符串对更正。 |
| 第二至四轮 A1 | 关闭文档问题 | 第二轮改为9个真实错型、1个保守误降。 |
| 第二至四轮 A2 | 部分关闭，边界保留 | 整词替换与实际58道闭破折号修复通过；缩写真句末未改，新增合成边界见A5。 |
| 第二至四轮 A3 | 摘要关闭；适用性仍待用户决定 | CO摘要已同步；残缺句自动池策略未实现，没有越权新增规则。 |

## 现场、边界与复现材料

- 工作树：`/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker`；分支 `codex/grammar-item-candidates`。从e91d0cc快进至精确f565da2，审核前干净。
- 桌面树：`/Users/zhouxin/Desktop/studytracker`，main/`6ded77d24586327ad94e151e172ae4811b4a2eed`，既有7 modified、22 untracked入口保留，未写入。
- 完整快照和辅助脚本：`/Users/zhouxin/.codex/audits/grammar-v02-round5-20261026`（以下称AUDIT）。source=f565、baseline=1f、main=65f1859。脚本、日志、全量候选、缓存、临时SQLite仅本机可见，未纳入提交。
- 基线候选使用上一轮已独立生成、校验过四交付文件的1f03c84快照：`/Users/zhouxin/.codex/audits/grammar-v02-round2-4-20261026/source`。本轮第一次复用该本地解析缓存，按新文本重新解析有改动句；第二次用本轮缓存。**不是全库冷解析**，本轮要求为两次生成，并未要求清空缓存。
- 未调用大模型API、未操作生产、未部署、未开PR、未合main、未rebase；生成仅写AUDIT副本。只有审核记录和两份交接允许提交。

## 19项检查结果

| 项 | 结果 | 证据/判断 | 实际命令或材料 |
| --- | --- | --- | --- |
| 1 | 通过 | 123文件（含4afeea0带入旧审核文档）。按路径逐项检查均在授权集合；8个Python文件，builder只改apply_passage_fixes调用的一行。 | git diff --stat/--name-only；diff-files.txt |
| 2 | 通过 | 指定raw、static/reading_tests、models.py、app.py、api/miniprogram.py、miniprogram、.github/workflows无差异；IELTS变更限阅读解析。 | 保护路径git diff；structure.json |
| 3 | 通过 | 逐T1干扰项head的aux/auxpass/neg/prt与来源span对比，遗漏0、漏降级0。仅3共同题auto→needs；T6只检查自己单位符合题目局部风险原则。 | audit_runtime.py / distractor-probe.json |
| 4 | 实际修复通过；有边界 | gi_v02_96287b126ba9完整；同语料同parse仅换回旧single_quote_role，1道变化。数字引语、年代缩写、所有格合成例见A5。 | audit_runtime.py；probe_rules.py |
| 5 | 实际修复通过 | 58道范围变化逐题核对，均补回插入语闭破折号；不越调用者允许范围，T5边界区别见A5。单破折号/连字符/标注外不补。数字范围–合成误补见A5。 | dash-changes.json；附录 |
| 6 | 通过，说明失败方式 | 四新测试旧实现3个断言失败、1个TypeError（旧resplit无baseline参数）；新实现四个通过，完整专项93通过。 | probe_rules.py / predecessor-tests.log |
| 7 | 通过，限制已列 | 整词替换保护out sidecar，中文相邻英文名可替换；’可匹配、‘不转换；exact整串，summary整体且必须label。全表幂等、缺项/非法组合报错。未传content时summary延后，实际两个调用方均传入。 | probe_rules.py；audit_static.py |
| 8 | 通过 | --check=0；171篇raw内存重建，content（含summary）及groups均等于static；图片路径函数只计算路径不下载。 | audit_static.py / static-summary.json |
| 9 | 通过改法；遗漏另列 | 643→686：18段落+1摘要+24题目专用，22旧条增加questions。逐项改法合理；19处为18+1，用户旧提交数字17非最终数。 | new-fixes.json；old-fixes-changed.json；附录 |
| 10 | 有问题 | 原19句已修；题目字段另有6处旧错文Q2；源文2句排印Q3。正常词/截短引用未误报。 | audit_static.py；final_checks.py |
| 11 | 通过 | 12745→12744；155变化后对象（含1新ID），删除2；12589对象除index原字节未动；连续index/缩进均无异常；validator0错误，未知role无新增。 | structure.json；validator.log |
| 12 | 有问题 | 全部155变化后对象逐句看过；120句124新说明四类17/11/83/13，均与清单精确一致。原11项/4role/5译文同步；新讲解问题Q1，存量解释A6。 | changed.json；manual-read.txt；dp-doc-coverage.json |
| 13 | 通过实际新增 | 同一最终语料旧/新resolver只有15role29处变化。unknown_span304→274，另1为M-01原second_list_item消失；7个实际开始出题来源共28题，逐题见83题表。 | roles.json；new_unknown_items.json |
| 14 | 通过 | 历史ID集合独立复算12657/12744、增94/删7/净87；7项独立过滤实际=预期，说明匹配。 | resplit-independent.json；generation_report |
| 15 | 机械验证通过；自查数字Q4 | 50230题，auto5989/4764/11591/414/5431/12894；增83删41，3共同题改状态；78回归记录全等；双跑、图谱、93专项、Flask-only161/跳1、Node、reading22通过；Ruff仅builder存量2UP017/format。 | run_checks.py；audit_runtime.py；hashes.json |
| 16 | 通过 | main完整快照65f1859先created317，本轮updated233/skipped84/failed0；独立分区135数据/98标签/84不变。 | import_snapshot.py；import-partition.json |
| 17 | 通过原三处更正 | 933、510字符串对、9/10真实错型+1保守误降均与前审一致；第五轮另有全称/状态数字Q4。 | FIXES.md第1/2/4/5轮 |
| 18 | 完成；区别局部与整句 | seed20261029：六表各5=30、改动句auto另30、全部83新增；明细见附录，未用实现方种子。 | audit_runtime.py；三组逐题表 |
| 19 | 通过结构盲审 | 7表，六题型各60数据行；360行逐格与teacher_row相等，无auto_pass/needs_review；H2:H61四项下拉。只读检查无回写。 | audit_runtime.py / xlsx_rows_match=360 |

## 新问题清单

### Q1 — 应修：改写的教学说明有4处不准确

不是要求改IELTS原文；应修学生看到的解释及清单对应文字。

| 位置 | 问题与复现 | 建议 |
| --- | --- | --- |
| data/reading_study/ielts4_test4_p1.json:23 / E-22 | 把even though supplements定性为正常口语省略they take。它不能由常规省略主语+be得到；从“原文不完整”改成可模仿用法，遮蔽了异常。该句仍因tagged_fragment排除，故不是自动池新漏题。 | 保留原句，明确缺失/不规范；they take只能作为可能理解，不称正常省略。 |
| data/reading_study/reading_jijing_22_test_90_p3.json:49 / G-08 | “to which ... to view介词重复”：第二个to是不定式标记，不是介词。建议去第一to方向正确，但解释错。 | 说明view是及物动词、which作其宾语；保留be invited to view的不定式to。 |
| data/reading_study/reading_jijing_24_test_56_p2.json:13 / A-04 | 原5% lower percentage被断言为低5个百分点；前后文没有给两组比例可据此换算，译文仍是低5%。百分比相对下降与百分点不同。 | 保留原统计措辞的歧义，说明不能据此确定相对下降还是百分点；有原研究数据后再定。 |
| data/reading_study/reading_jijing_32_test_20_p1.json:8 / B-03 | for改并列连词正确；新加“不能放到句首”混淆不能把因果分句前置与不能在句号后起句。 | 改为for补充前述理由，通常跟在被解释内容之后；可在新句句首承接前文。 |

复现：读取上述difficult_points并与1f03c84差分；前两处及A-04均为本轮替换后的句子，B-03为本轮新增断言。关于for，词典明确记录可在句号后以大写For开始新句：[American Heritage用法说明](https://www.ahdictionary.com/word/search.html?q=FOR)。其余判断来自成分分析；没有把“存在无动词从句”误说成“even though后永远不能省略”。

### Q2 — 应修：9_81_p2仍有6个题目字段未同步

正文I-09已是`carrying capacity ... does not seem`，I-11已是`carrying capacity`；下列字段仍有`docs not`或`capac ity`。不是合法截短、大小写差异或普通单词误报。至少analysis和central_sentences由阅读刷题页渲染，不能以synonym不读取为由略过。

| 位置（reading_jijing_9_test_81.json内p2，0基下标） | 残留 |
| --- | --- |
| groups[0].questions[4].analysis | docs not |
| groups[0].questions[4].locating_words[0].syn_ary[0].target_sen[0].target_sen | capac ity, docs not |
| groups[2].questions[0].central_sentences[0].sentence | capac ity |
| groups[2].questions[0].locating_words[0].syn_ary[1].target_sen[3].target_sen | capac ity |
| groups[2].questions[2].central_sentences[0].sentence | capac ity |
| groups[2].questions[2].locating_words[0].syn_ary[1].target_sen[3].target_sen | capac ity |

复现：`rg -n 'docs not|capac ity' static/reading_jijing/reading_jijing_9_test_81.json`，包括line2460/2483及后续central_sentences。建议用题目专用、带上下文的整词修订，把docs→does、capac ity→capacity同步；不要仅扩大原段落窗口后假设所有引用都已覆盖。Q2是在既有N2点名修复之外的新漏网证据，不表示整词替换本身越界。

### Q3 — 应修：同篇仍有两处可确定排印错误

- `reading_jijing_5_test_59_p1 C-06`，data文件line218/224、static文件line53：`Post- It Notes`连字符后多空格；正文、structure及5个groups字段同样存在。应规范为Post-it Notes并同步标注/题目。依据：[品牌自身历史页](https://www.post-it.com/3M/en_US/post-it/contact-us/about-us/)。
- 同篇`C-04`，data文件line189/193/199：Raytheon微波炉发明者被写为`Peroy Spender`，应为`Percy Spencer`，译名/同位语说明也须同步；不是另一个同名人。依据：[美国发明家名人堂的本人档案](https://www.invent.org/inductees/percy-l-spencer)。

复现：`rg -n 'Post- It|Peroy Spender' data/reading_study/reading_jijing_5_test_59_p1.json static/reading_jijing/reading_jijing_5_test_59.json`。前者来自独立连字符空格扫描，后者是在读该段上下文时发现并另找权威依据。原第一轮19句已全修，故不把这两句说成原19句修复失败。

### Q4 — 应修：新增题自查的数字与“全部正确”不可复现

位置`docs/GRAMMAR_ITEM_CANDIDATES_V0_2_FIXES.md:317`（两份交接也转述了全对）。按1f03c84全量候选item_id集合差得到83题，其中**69自动、14待复核**。例如：

- `gi_v02_5a2d9f10df5a`（81_93_p2 F-01，T5，needs_review）答案`What, if anything`把插入语并入完整主语；主语应为What。
- `gi_v02_46ae5aa33437`（5_59_p1 I-01，T3，needs_review）名词性从句类型对，但目标停在realise，漏后面that宾语从句。
- `gi_v02_b33f4b6b17fc`（16_97_p1 E-01，T2，needs_review）范围未包含从句内补充说明；不能当完整边界通过。

降级正确发挥作用，不要求这些待复核题必须自动修好；应把“全部正确”改成按状态和实际判定的结果。附录列完83题。

另澄清计数口径：180个groups字符串变化可在`b7261d5^..b7261d5`复现（85种完整字符串对）；整个第五轮`1f03c84..f565da2`是247字段、113种完整字符串对。180不是整轮总量，文档应注明提交范围。

### A5 — 建议：引号、破折号与题目替换的启发式边界

`templates.py:67–148`的合成反例：`'06`、`'1999`被视为开引号；`He called it '90s music'`的真实开引号被视为年代撇号，不能补闭引号；`'Our students' work is ready.'`中的所有格仍可提前消耗开引号。普通数字嵌套引语`"They called it '15 volts'."`可正确补全。全库数字前单引号只有5个句子（4年代场景、1电压标签句），未发现新的实际受害题。

`The 5–10 range – a useful convention – matters.`中，把`The 5–10 range`作为截取目标且原span容许后续插入语时，数字范围的en dash被当作第一个破折号，误补后面的开破折号为`The 5–10 range –`。建议识别数字区间/同类配对并补反例测试。真实58道变更均不是此形状，不能据合成例声称已产生真实错题。另需纠正文案中的范围表述：T2/T3/T4以目标raw span限界；T5沿用原有完整主语策略，以subject.start至predicate.start限界。58道中53道T5答案超出单个subject标签的end，补破折号之前这53道也已超出，都是既有完整主语扩展；本轮没有新引入跨词扩展。58道均未超调用函数的low/high。不能笼统声称所有模板都被单个raw tag限定，但按完整主语出题目标，这种既有边界合理。

`reading_jijing_text_fixes.py`的WORD_CHAR有意只识别拉丁字母/数字边界；`Pridcauxson`不改，`根据Pridcaux的模型`可改。`China‘s rise`的左弯撇号不覆盖，`China’s rise`覆盖；当前已修的题目没有依此发现新漏项。summary若不传content会静默延后，应继续保证调用方始终传content；当前builder和patch入口均满足。缩写Inc./p.m.真句末问题仍是此前已披露、未改的边界。

### A6 — 建议：整句适用性仍未解决，存量解释也应保留复核标记

第二至四轮A3未实现是用户已知取舍，本轮不重复记应修。新增83中44_29_p3 M-01列表片段的4道自动题，以及改动句30抽查中的残缺/明显语病原句，均只证明局部答案对；不适合直接作为无说明的学生标准语法材料。

另，83_95_p2 F-01本轮只改第一条难点，但保留的第三条仍把`the local government targeting the right markets`断言为以government为中心、targeting仅作修饰。按该句意，prerequisite应是政府准确定位市场这一行动，至少应讨论动名词结构以government作其主语的分析；不宜排除它。这一句该说明在1f03c84已存在，本轮没有引入，记录为存量建议，未混入Q1新增数。

## 方法、命令与环境

辅助脚本均为本次独立编写、只写AUDIT；没有调用Claude未入库的生成清单脚本。下列路径变量只是说明实际绝对路径的简写。

```sh
ROOT=/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker
AUDIT=/Users/zhouxin/.codex/audits/grammar-v02-round5-20261026
G="$ROOT/.venv-grammar-tools/bin/python"
P=/Users/zhouxin/Desktop/studytracker/.venv/bin/python
cd "$ROOT"
git status --short --branch
git log -5 --oneline
git fetch origin claude/word-memorization-system-eval-55v2y5
git merge --ff-only f565da265f74faf5d745267c701c9f32e1c4c009
git fetch origin main
git diff --stat 1f03c84..f565da2
git diff --name-only 1f03c84..f565da2
git diff 1f03c84..f565da2 -- data/idictation_reading_jijing/raw.json static/reading_tests models.py app.py api/miniprogram.py miniprogram .github/workflows
git diff 1f03c84..f565da2 -- scripts/build_reading_test_practice.py
# 分别用git archive将f565da2 / 1f03c84 / 65f1859完整解压到AUDIT下source/baseline/main。
"$G" "$AUDIT/audit_static.py"
"$G" "$AUDIT/audit_runtime.py"
"$G" "$AUDIT/probe_rules.py"
"$G" "$AUDIT/final_checks.py"
"$G" "$AUDIT/run_checks.py"
"$G" -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary tests.test_grammar_graph_draft -v
"$G" scripts/validate_reading_study.py
"$G" scripts/reading_jijing_text_fixes.py --check
"$P" -m unittest tests.test_reading_study -v
"$G" -m venv "$AUDIT/flask-only"
"$AUDIT/flask-only/bin/python" -m pip install --cert /etc/ssl/cert.pem Flask
"$AUDIT/flask-only/bin/python" -m unittest tests.test_miniprogram_guest_access tests.test_miniprogram_dictation_grouping tests.test_inventory_toefl_materials tests.test_organize_toefl_materials tests.test_extract_toefl_answer_keys tests.test_map_toefl_answers_to_practice_docs tests.test_import_toefl_official_reading tests.test_reading_vocab_grading tests.test_stats_utils tests.test_grammar_graph_draft tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary -v
/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tests/test_dictation_spell_queue.js
"$P" -m ruff check api/reading_study_glossary.py scripts/build_reading_test_practice.py scripts/grammar_items/reporting.py scripts/grammar_items/templates.py scripts/reading_jijing_text_fixes.py tests/test_grammar_item_candidates.py tests/test_reading_jijing_text_fixes.py tests/test_reading_study_glossary.py
# 同一8文件列表：ruff format --check；只builder已有2个UP017和format失败，其他7文件通过。
"$P" "$AUDIT/import_snapshot.py" "$AUDIT/main"
"$P" "$AUDIT/import_snapshot.py" "$AUDIT/source"
cd "$AUDIT/source"
"$G" scripts/generate_grammar_candidates.py --seed 20261018
# 四交付文件保存到AUDIT/run1，再执行相同命令第二次：
"$G" scripts/generate_grammar_candidates.py --seed 20261018
"$G" scripts/render_grammar_graph_review.py
cmp docs/GRAMMAR_GRAPH_V0_REVIEW.md "$ROOT/docs/GRAMMAR_GRAPH_V0_REVIEW.md"
```

图谱首次用`--stdout`比较时仅多print的末尾换行，因此另在快照中运行正常写文件入口再cmp，逐字节相同。辅助脚本开发中修正了对目录index.json的读取和清单章节选择；修正仅发生于AUDIT，最终完整检查成功，没有跳过失败项。

静态方法：递归按JSON路径对比groups；剥离sentence_index后同时对比对象和原始对象文本；对全686修订做幂等重放；raw builder只替换图片本地路径函数为同规则的纯计算。运行方法：从候选与对应ParseCache提取干扰项中心词和直接孩子，对照locate_spans来源；反事实只替换一个待审函数、其余语料/parse/规则不变，避免只按共同item_id漏掉范围变化。全文漏网搜索结合修订旧词、原19句词表、低频相邻词拼接、ff/fi/fl插入候选、连字符空格和人工上下文；这些是下界扫描，不声称证明全库无其他OCR。

main取到`65f1859683c94ef41c938319515702e12709e96c`，与Claude一致。SQLite明确绑定AUDIT/main-to-current.sqlite，先用main的代码/static/data，再用f565的完整快照。独立比较数据文件与归一化payload，得到135+98+84。标签由import的normalize_payload写入数据库，部署新词汇表后仍需重新导入才更新；本轮未部署或导入生产。

环境：macOS、CPU、Python3.13.3、spaCy3.8.16、en_core_web_trf3.8.0、torch2.14.1、openpyxl3.1.5；种子20261018。reading_study指纹`bfd88826712ac620d44f1afa8f02e63e07aa171853e84c4497d576d0d0392db1`。两份报告与提交版只有Python版本3.11.15→3.13.3一行变化；JSONL/XLSX逐字节相同。

| 文件 | 第一次SHA-256 | 第二次SHA-256 | 提交版SHA-256 |
| --- | --- | --- | --- |
| generation_report_v0_2.md | 9eed2f7bb25c9efede5d791b1353ca39a0311e8fb7ee7e4c256fdf2f710ee49e | 9eed2f7bb25c9efede5d791b1353ca39a0311e8fb7ee7e4c256fdf2f710ee49e | 0eebaaee1317974271aca2acce38e9072cc3152c7ad4dfefa04006b966f22c6c |
| generation_report_v0_2.json | 022b669ba277c88c32b89ba1f4a5dc5a6d5f19f4c0e5cd1486aa59a21d446eef | 022b669ba277c88c32b89ba1f4a5dc5a6d5f19f4c0e5cd1486aa59a21d446eef | bf148c672b492cc6348fe4c3afab2c9491df386b353f8d39dcee5ee1dba0dc33 |
| review_batch_v0_2.xlsx | 72cab3ba0c50dff1005281e471cba1295b5c907c334de3fe321ad781a505ce71 | 72cab3ba0c50dff1005281e471cba1295b5c907c334de3fe321ad781a505ce71 | 72cab3ba0c50dff1005281e471cba1295b5c907c334de3fe321ad781a505ce71 |
| review_batch_v0_2.jsonl | 4098cdd88d262835d5e9b8f15606c110cbf6ba47fab263e09882564d71890283 | 4098cdd88d262835d5e9b8f15606c110cbf6ba47fab263e09882564d71890283 | 4098cdd88d262835d5e9b8f15606c110cbf6ba47fab263e09882564d71890283 |

### 独立过滤与回归

| 过滤 | expected | actual |
| --- | --- | --- |
| tagged_fragment | 30 | 30 |
| clause_attached_to_conjunction | 2 | 2 |
| glued_sentence_boundary | 0 | 0 |
| multi_sentence_unit | 1 | 1 |
| suspected_split_word | 0 | 0 |
| leading_stray_punctuation | 0 | 0 |
| control_character | 0 | 0 |

13句×6模板的完整regression_cases对象与1f03c84相等（不仅状态/原因，包括目标与题号）。具体句子见下表；对应每句6模板均逐项比较。

| 回归句 | 逐模板实际结果（T1→T6） | 对比 |
| --- | --- | --- |
| ielts7_test3_p1 K-03 | T1: {} ['too_short', 'unbalanced_quotes_or_brackets']; T2: {} ['too_short', 'unbalanced_quotes_or_brackets']; T3: {} ['too_short', 'unbalanced_quotes_or_brackets']; T4: {} ['too_short', 'unbalanced_quotes_or_brackets']; T5: {} ['too_short', 'unbalanced_quotes_or_brackets']; T6: {} ['too_short', 'unbalanced_quotes_or_brackets'] | 与基线完全一致 |
| ielts8_test4_p1 C-04 | T1: {} ['no_main_verb_tag']; T2: 不适用; T3: {'auto_pass': 1} []; T4: 不适用; T5: {} ['no_main_verb_tag']; T6: {'auto_pass': 1} ['no_main_verb_tag'] | 与基线完全一致 |
| reading_jijing_76_test_43_p2 H-02 | T1: {'auto_pass': 1} []; T2: 不适用; T3: 不适用; T4: 不适用; T5: {'needs_review': 1} ['subject_mismatch']; T6: {'auto_pass': 1} [] | 与基线完全一致 |
| reading_jijing_73_test_5_p2 F-05 | T1: {} ['tagged_fragment', 'unknown_span']; T2: {} ['tagged_fragment', 'unknown_span']; T3: {} ['tagged_fragment', 'unknown_span']; T4: {} ['tagged_fragment', 'unknown_span']; T5: {} ['tagged_fragment', 'unknown_span']; T6: {} ['tagged_fragment', 'unknown_span'] | 与基线完全一致 |
| reading_jijing_56_test_64_p2 C-01 | T1: {} ['clause_attached_to_conjunction']; T2: {} ['clause_attached_to_conjunction']; T3: {} ['clause_attached_to_conjunction']; T4: {} ['clause_attached_to_conjunction']; T5: {} ['clause_attached_to_conjunction']; T6: {} ['clause_attached_to_conjunction'] | 与基线完全一致 |
| ielts13_test2_p2 C-04 | T1: {} ['clause_attached_to_conjunction']; T2: {} ['clause_attached_to_conjunction']; T3: {} ['clause_attached_to_conjunction']; T4: {} ['clause_attached_to_conjunction']; T5: {} ['clause_attached_to_conjunction']; T6: {} ['clause_attached_to_conjunction'] | 与基线完全一致 |
| reading_jijing_91_test_49_p3 D-02 | T1: {'auto_pass': 1} []; T2: 不适用; T3: {'auto_pass': 2, 'needs_review': 1} ['span_not_constituent']; T4: 不适用; T5: {'auto_pass': 1} []; T6: {'auto_pass': 3} [] | 与基线完全一致 |
| ielts11_test3_p2 A-04 | T1: {'auto_pass': 1} []; T2: {'auto_pass': 1} []; T3: {'auto_pass': 1} []; T4: 不适用; T5: {'auto_pass': 1} []; T6: {'auto_pass': 2} [] | 与基线完全一致 |
| ielts15_test2_p3 D-05 | T1: {'auto_pass': 1} []; T2: {'auto_pass': 1} []; T3: {'auto_pass': 2} []; T4: 不适用; T5: {'auto_pass': 1} []; T6: {'auto_pass': 1} [] | 与基线完全一致 |
| ielts4_test2_p2 G-31 | T1: {} ['no_main_verb_tag']; T2: {'needs_review': 1} ['possible_relative_adverb']; T3: {'needs_review': 1} ['possible_relative_adverb']; T4: {'needs_review': 1} ['possible_relative_adverb']; T5: {} ['no_main_verb_tag', 'split_subject']; T6: {'auto_pass': 1} ['no_main_verb_tag'] | 与基线完全一致 |
| ielts6_test3_p1 C-06 | T1: {'needs_review': 1} ['ambiguous_span_location']; T2: {'auto_pass': 1} []; T3: {'auto_pass': 1} []; T4: 不适用; T5: {'needs_review': 1} ['ambiguous_span_location']; T6: {'needs_review': 1, 'auto_pass': 1} ['ambiguous_span_location'] | 与基线完全一致 |
| reading_jijing_88_test_98_p2 G-04 | T1: {'auto_pass': 1} []; T2: {'auto_pass': 1} []; T3: {'auto_pass': 1} []; T4: 不适用; T5: {'auto_pass': 1} []; T6: {'auto_pass': 2} [] | 与基线完全一致 |
| reading_jijing_88_test_98_p2 G-04b | T1: {'auto_pass': 1} []; T2: {'auto_pass': 2} []; T3: {'auto_pass': 2} []; T4: 不适用; T5: {'auto_pass': 1} []; T6: {'auto_pass': 2} [] | 与基线完全一致 |

## 附录A：新增43条及旧22条修订逐条审核

编号是f565修订表fixes数组1基位置；“合理”针对本条改法，不等于不存在同篇漏项。18段落、1摘要均结合原段落和译文检查；24题目专用结合groups实际前后字符串检查。247个变化字段按完整字符串对归并113组，再读差异上下文，未见替换越界。

| 条目 | 来源/句子 | find → replace | 范围 | 判定 |
| --- | --- | --- | --- | --- |
| 84 | reading_jijing_29_test_63_p1  | 大气中的CO浓度 → 大气中的二氧化碳浓度 | summary | 改法合理 |
| 123 | reading_jijing_13_test_6_p2  | Street Angel(1937) → Street Angel (1937) | questions only | 改法合理 |
| 154 | reading_jijing_24_test_56_p1  | DINA → DNA | questions only | 改法合理 |
| 168 | reading_jijing_26_test_72_p1 A-05 | hunter- gatherers → hunter-gatherers | paragraph + questions | 改法合理 |
| 253 | reading_jijing_44_test_29_p3 M-01 | happens- is outgoing → happens - is outgoing | paragraph + questions | 改法合理 |
| 258 | reading_jijing_46_test_84_p1  | (China’s rise → China’s rise | questions only | 改法合理 |
| 274 | reading_jijing_48_test_21_p3  | 6oC → 6°C | questions only | 改法合理 |
| 312 | reading_jijing_5_test_59_p2  | fair-trade coee → fair-trade coffee | questions only | 改法合理 |
| 438 | reading_jijing_84_test_73_p3 E-06 | nas al → nasal | paragraph + questions | 改法合理 |
| 475 | reading_jijing_92_test_58_p1 B-01 | causes dierent senses → causes different senses | paragraph + questions | 改法合理 |
| 476 | reading_jijing_92_test_58_p1 B-01 | syn("with") → syn ("with") | paragraph + questions | 改法合理 |
| 516 | reading_jijing_11_test_103_p2 E-06 | non-fossil- fuel → non-fossil-fuel | paragraph | 改法合理 |
| 520 | reading_jijing_14_test_23_p2 D-04 | spacio-visual → spatio-visual | paragraph + questions | 改法合理 |
| 522 | reading_jijing_18_test_53_p1  | modem version → modern version | questions only | 改法合理 |
| 532 | reading_jijing_18_test_53_p2 I-02 | The family's minister → The families minister | paragraph + questions | 改法合理 |
| 537 | reading_jijing_23_test_46_p1  | Green Peace → Greenpeace | questions only | 改法合理 |
| 548 | reading_jijing_32_test_20_p1  | book Centuries of Childhood’ → book ‘Centuries of Childhood’ | questions only | 改法合理 |
| 554 | reading_jijing_40_test_75_p1  | Brock-lesby → Brocklesby | questions only | 改法合理 |
| 559 | reading_jijing_40_test_75_p3  | stressed end' → stressed out' | questions only | 改法合理 |
| 560 | reading_jijing_40_test_75_p3  | self-certificaion → self-certification | questions only | 改法合理 |
| 561 | reading_jijing_40_test_75_p3  | hypothrsie → hypothesise | questions only | 改法合理 |
| 562 | reading_jijing_40_test_75_p3  | hypothesise'is → hypothesise 'is | questions only | 改法合理 |
| 563 | reading_jijing_40_test_75_p3  | Refer-ence → Reference | questions only | 改法合理 |
| 564 | reading_jijing_40_test_75_p3  | may be you should → maybe you should | questions only | 改法合理 |
| 582 | reading_jijing_50_test_30_p2  | catching → caching | questions exact | 改法合理 |
| 587 | reading_jijing_53_test_83_p3 F-03 | transmission, and distribution → transmission and distribution | paragraph | 改法合理 |
| 590 | reading_jijing_5_test_59_p1  | risk-talking → risk-taking | questions only | 改法合理 |
| 591 | reading_jijing_5_test_59_p1  | unsuccessfull → unsuccessful | questions only | 改法合理 |
| 596 | reading_jijing_62_test_44_p3 I-01 | Salesperson says → Salesperson, says | paragraph + questions | 改法合理 |
| 597 | reading_jijing_62_test_44_p3 I-01 | speak rather listen → speak rather than listen | paragraph + questions | 改法合理 |
| 603 | reading_jijing_65_test_69_p2 G-02 | cow less steaks and chicken less drumsticks → cowless steaks and chickenless drumsticks | paragraph + questions | 改法合理 |
| 604 | reading_jijing_65_test_69_p2  | stablize → stabilize | questions only | 改法合理 |
| 606 | reading_jijing_65_test_69_p3 B-05 | tyre- marks → tyre-marks | paragraph | 改法合理 |
| 619 | reading_jijing_71_test_1_p2  | ranffian saying. ‘Je → ruffian saying ‘Je | questions only | 改法合理 |
| 624 | reading_jijing_73_test_5_p1 K-02+K-03 | into it. like that → into it, like that | paragraph + questions | 改法合理 |
| 625 | reading_jijing_73_test_5_p1  | 23"C → 23°C | questions only | 改法合理 |
| 640 | reading_jijing_77_test_16_p2 A-01 | and may be even → and maybe even | paragraph | 改法合理 |
| 651 | reading_jijing_78_test_102_p3 E-03b | multicore-away → multicore—away | paragraph + questions | 改法合理 |
| 660 | reading_jijing_82_test_4_p3  | 1070s → 1970s | questions exact | 改法合理 |
| 681 | reading_jijing_9_test_81_p2 B-01 | Conran Cove → Couran Cove | paragraph | 改法合理 |
| 682 | reading_jijing_9_test_81_p2 I-05 | Pridcaux → Prideaux | paragraph + questions | 改法合理 |
| 683 | reading_jijing_9_test_81_p2  | ocean bloke → ocean broke | questions only | 改法合理 |
| 686 | reading_jijing_81_test_93_p2  | educa-tion → education | questions only | 改法合理 |

| 旧条目现编号 | 来源 | 增加questions的改法 | 判定 |
| --- | --- | --- | --- |
| 19 | reading_jijing_71_test_1_p2 | Scientifico',translates → Scientifico', translates | 同步合理 |
| 32 | reading_jijing_88_test_98_p3 | cards.That's → cards. That's | 同步合理 |
| 34 | reading_jijing_27_test_33_p1 | claim mat the image → claim that the image | 同步合理 |
| 52 | reading_jijing_38_test_22_p3 | commented that"research → commented that "research | 同步合理 |
| 114 | reading_jijing_11_test_103_p2 | years' says → years,' says | 同步合理 |
| 118 | reading_jijing_11_test_103_p3 | it's financial → its financial | 同步合理 |
| 144 | reading_jijing_22_test_90_p2 | reset'children's sleeping → reset' children's sleeping | 同步合理 |
| 153 | reading_jijing_24_test_56_p1 | while pigs'brains → while pigs' brains | 同步合理 |
| 297 | reading_jijing_56_test_64_p3 | a cigarette,you're → a cigarette, you're | 同步合理 |
| 318 | reading_jijing_62_test_44_p1 | they' may → they may | 同步合理 |
| 356 | reading_jijing_69_test_40_p2 | trees'response to → trees' response to | 同步合理 |
| 378 | reading_jijing_73_test_5_p2 | a tiger's afraid → a tiger's fear | 同步合理 |
| 389 | reading_jijing_76_test_43_p1 | disability' on → disability on | 同步合理 |
| 423 | reading_jijing_82_test_4_p2 | killer Edison's had hoped → killer Edison had hoped | 同步合理 |
| 434 | reading_jijing_84_test_73_p2 | family's life park → family's life: park | 同步合理 |
| 435 | reading_jijing_84_test_73_p2 | to nearbyfriends' → to nearby friends' | 同步合理 |
| 518 | reading_jijing_14_test_23_p1 | of course don't → of course, don't | 同步合理 |
| 524 | reading_jijing_18_test_53_p2 | was,'less intrusive → was 'less intrusive | 同步合理 |
| 525 | reading_jijing_18_test_53_p2 | schools,'their report → schools,' their report | 同步合理 |
| 533 | reading_jijing_22_test_90_p3 | individuals'potential, Once again → individuals' potential. Once again | 同步合理 |
| 580 | reading_jijing_50_test_30_p2 | Clark's nutcracker(Nucifraga → Clark's nutcracker (Nucifraga | 同步合理 |
| 645 | reading_jijing_78_test_102_p2 | McDonald's', like → McDonald's, like | 同步合理 |

重点判断：families minister是政府职务语境，不是某家人的牧师；spatio-visual拼写、transmission and distribution losses共同修饰losses、multicore—away插入说明、into it, like that句内补充、Salesperson书名后的逗号、rather than listen、cowless/chickenless、tyre-marks与hunter-gatherers均符合上下文。CO摘要同步。两个exact分别限定单字段catching与1070s，避免改其他正常词内文本。I-41/I-42合并后人名及谓语属于同句；K-02/K-03合并恢复like that修饰；M-01/M-01b分开两条列表仍是片段，见A6。

## 附录B：阅读解析逐句覆盖

155个变化后对象均逐句阅读sentence、translation、structure、difficult_points、expressions；下面合并列出未发现明确新增问题的ID，异常单列Q1/A6。删除I-42、K-03已对照合并后整句，M-01b新增也覆盖。120句124条新说明都在此覆盖内，清单逐条文本匹配0差异；分类行数17/11/83/13。5句改译（10_78_p3 F-01；24_56_p3 C-02；26_72_p1 B-02、D-10；76_43_p3 D-07）为对原残缺文本的合理大意，无额外虚构确定事实；残缺性在难点保留。

| passage_id | 全部审核ID | 结论 |
| --- | --- | --- |
| ielts4_test2_p3 | G-37c | 未发现明确新增错误；不作整句出题适用性背书 |
| ielts4_test4_p1 | E-22、I-41 | Q1: E-22 |
| ielts8_test3_p3 | A-03b | 未发现明确新增错误；不作整句出题适用性背书 |
| ielts9_test2_p2 | F-03 | 未发现明确新增错误；不作整句出题适用性背书 |
| ielts9_test4_p1 | E-04、F-01 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_10_test_78_p2 | E-35b | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_10_test_78_p3 | C-02、F-01、H-06、I-02 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_11_test_103_p1 | D-01、D-05、E-07 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_11_test_103_p2 | B-05、E-06、F-01、F-03 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_13_test_6_p3 | B-07 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_14_test_23_p2 | D-04、G-02 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_16_test_97_p1 | B-06 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_16_test_97_p3 | B-03、E-08 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_18_test_53_p1 | B-01 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_18_test_53_p2 | E-02、F-09、I-02 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_22_test_90_p2 | F-17 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_22_test_90_p3 | G-02、G-06、G-08 | Q1: G-08 |
| reading_jijing_23_test_46_p1 | E-05 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_24_test_56_p2 | A-04、G-03 | Q1: A-04 |
| reading_jijing_24_test_56_p3 | C-02、C-05、H-02 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_26_test_72_p1 | A-05、B-02、D-10 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_27_test_33_p1 | D-01b | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_27_test_33_p2 | C-05 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_27_test_33_p3 | C-01、C-02、C-03、D-02、E-02 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_29_test_63_p2 | B-04、E-08、H-02 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_29_test_63_p3 | E-05 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_32_test_20_p1 | B-03、E-01、G-03 | Q1: B-03 |
| reading_jijing_32_test_20_p3 | C-03 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_44_test_29_p3 | M-01、M-01b | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_46_test_84_p1 | C-04、D-06 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_48_test_21_p1 | C-04、E-02、E-05、E-06、F-01 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_48_test_21_p3 | D-01、J-01、K-02、K-04、M-01、M-02 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_53_test_83_p2 | G-04 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_53_test_83_p3 | A-02、C-05、C-06、F-03、F-04 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_56_test_64_p2 | F-01 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_56_test_64_p3 | M-05 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_5_test_59_p1 | I-01 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_5_test_59_p2 | G-06 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_62_test_44_p1 | B-01、E-01 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_62_test_44_p2 | B-01、B-05、C-08 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_62_test_44_p3 | B-01、H-05、I-01、I-04、J-05 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_65_test_69_p1 | F-04 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_65_test_69_p2 | G-02 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_65_test_69_p3 | B-05、J-03 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_69_test_40_p2 | F-01 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_71_test_1_p2 | D-01 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_72_test_15_p2 | I-01 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_73_test_5_p1 | K-01、K-02 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_73_test_5_p2 | A-04、E-05、E-11 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_73_test_5_p3 | E-03 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_76_test_43_p1 | E-01 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_76_test_43_p2 | A-04 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_76_test_43_p3 | B-01、B-02、B-03、C-02、C-07、C-08、C-15、D-01、D-03、D-05、D-07、E-01 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_77_test_16_p2 | A-01、D-02 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_78_test_102_p1 | H-02 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_78_test_102_p2 | A-02、A-05、E-03 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_78_test_102_p3 | E-03b | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_81_test_93_p1 | C-02、G-03 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_81_test_93_p2 | F-01 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_83_test_95_p1 | B-04、F-06、H-06 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_83_test_95_p2 | A-02、D-01、E-04、F-01、G-01、G-05 | A6: F-01原有解释 |
| reading_jijing_84_test_73_p3 | E-06 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_85_test_12_p1 | F-08 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_85_test_12_p2 | C-10、H-04 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_92_test_58_p1 | B-01 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_92_test_58_p2 | E-03、H-03 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_92_test_58_p3 | E-01、F-03、F-07、F-09、G-04、H-06 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_9_test_81_p1 | E-03、F-02 | 未发现明确新增错误；不作整句出题适用性背书 |
| reading_jijing_9_test_81_p2 | B-01、I-05 | 未发现明确新增错误；不作整句出题适用性背书 |

### 15个ellip角色与实际新出题

| role | 处数 | 旧 → 新 | 真实来源 |
| --- | --- | --- | --- |
| elliptical_answer | 2 | 语法成分 → 省略结构 | ielts13_test1_p2 D-07；reading_jijing_46_test_84_p1 B-02 |
| elliptical_question | 9 | 语法成分 → 省略结构 | ielts15_test3_p3 A-04；ielts18_test2_p2 A-02；ielts20_test1_p2 C-08；ielts5_test1_p3 I-35；ielts6_test4_p1 E-21；reading_jijing_26_test_72_p1 H-01；reading_jijing_53_test_83_p2 B-01；reading_jijing_5_test_59_p3 G-02；reading_jijing_76_test_43_p2 H-05 |
| ellipsis | 1 | 语法成分 → 省略结构 | ielts20_test2_p1 B-02 |
| elliptical_contrast | 5 | 语法成分 → 省略结构 | reading_jijing_16_test_97_p1 E-01；reading_jijing_50_test_30_p1 A-02；reading_jijing_62_test_44_p3 G-01；reading_jijing_62_test_44_p3 I-05；reading_jijing_6_test_71_p3 F-04 |
| elliptical_negation | 1 | 语法成分 → 省略结构 | reading_jijing_26_test_72_p1 H-04 |
| elliptical_escalation | 1 | 语法成分 → 省略结构 | reading_jijing_38_test_22_p1 H-06 |
| elliptical_supplement | 1 | 语法成分 → 省略结构 | reading_jijing_46_test_84_p2 G-05 |
| elliptical_addition | 1 | 语法成分 → 省略结构 | reading_jijing_53_test_83_p3 C-07 |
| elliptical_explanation | 1 | 语法成分 → 省略结构 | reading_jijing_56_test_64_p2 H-05 |
| elliptical_question_option | 1 | 语法成分 → 省略结构 | reading_jijing_5_test_59_p3 G-03 |
| elliptical_question_topic | 1 | 语法成分 → 省略结构 | reading_jijing_5_test_59_p3 G-04 |
| elliptical_response | 2 | 语法成分 → 省略结构 | reading_jijing_73_test_5_p2 C-03；reading_jijing_73_test_5_p2 C-05 |
| main_clause_with_ellipsis | 1 | 语法成分 → 省略结构 | reading_jijing_78_test_102_p1 F-04 |
| elliptical_range | 1 | 语法成分 → 省略结构 | reading_jijing_81_test_93_p2 B-05 |
| elliptical_quotation | 1 | 语法成分 → 省略结构 | reading_jijing_85_test_12_p1 C-07 |

| 实际开始出题句 | 题数 | 全部题号（判定见83题表） |
| --- | --- | --- |
| ielts15_test3_p3 A-04 | 5 | gi_v02_def9b6b4c193、gi_v02_2fc0d0adf2b5、gi_v02_fd3845e8e24f、gi_v02_1d1223d9818c、gi_v02_d4bc3da831e7 |
| ielts20_test2_p1 B-02 | 3 | gi_v02_9d30711afa2d、gi_v02_ac44a7c144c8、gi_v02_585942db8226 |
| reading_jijing_16_test_97_p1 E-01 | 5 | gi_v02_84a87a984bc5、gi_v02_b33f4b6b17fc、gi_v02_d29f45361cc8、gi_v02_622d63e3130f、gi_v02_76bd7aa23bff |
| reading_jijing_38_test_22_p1 H-06 | 4 | gi_v02_c7795326ba56、gi_v02_ece54dc3c4ac、gi_v02_95025b986926、gi_v02_6b596b6b0a4a |
| reading_jijing_46_test_84_p2 G-05 | 4 | gi_v02_c28518bc1c63、gi_v02_4c740d83327c、gi_v02_53de8d8dbb3c、gi_v02_c9400354f43b |
| reading_jijing_53_test_83_p2 B-01 | 4 | gi_v02_06f70977d932、gi_v02_6d600583b1a8、gi_v02_4b0291e7e23c、gi_v02_450893d4f560 |
| reading_jijing_56_test_64_p2 H-05 | 3 | gi_v02_0786eb6b529e、gi_v02_20784cae194c、gi_v02_748165fdcb44 |

29个句子不再含unknown角色，其中22仍因其他原因排除，实际7句28题；不能把29误写成新增出题来源数。28题中的待复核边界仍保留待复核，不把角色名字识别成功当作标注正确保证。

## 附录C：三组逐题人工审核

方法：Python random.Random(20261029)。抽查表按T1→T6顺序，每模板先按item_id排序，再以同一RNG连续sample5；xlsx实际行号=review_row+1。改动句池为155个变化后句子ID对应的全部auto_pass，按item_id排序，用重新初始化的同种子RNG sample30。新增池为当前与1f候选item_id集合差，按item_id排序全审83，无随机抽样。三组可能自然重叠，不人为替换样本。

### C1 抽查表30题

| # | 题目编号 | 工作表/模板 | xlsx行 | 池状态 | 来源 | 核对的答案/高亮 | 判定 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_9d4fea0572c7 | 主句谓语 | 53 | auto_pass | ielts6_test2_p3 B-04 | However, when early humans first began to reflect on the nature of things around them, they 【discovered】 that they needed an idea of number simply to keep their thoughts in order. | 答案与高亮正确 |
| 2 | gi_v02_8571454fe84c | 主句谓语 | 11 | auto_pass | reading_jijing_85_test_12_p1 B-02 | In 1995, Tom Quinn and John Heron 【bought】 a struggling cleaning products business, OzKleen, for 250,000. | 答案与高亮正确 |
| 3 | gi_v02_54f57f0c7857 | 主句谓语 | 50 | auto_pass | ielts5_test2_p1 D-13 | While Baekeland had been busily amassing dollars, some advances 【had been made】 in the development of plastics. | 答案与高亮正确 |
| 4 | gi_v02_c2edc297a883 | 主句谓语 | 3 | auto_pass | ielts19_test1_p2 A-02 | Yet from the first to the third millennium BCE, thousands of years before these swashbucklers began spreading fear across the Caribbean, pirates 【prowled】 the Mediterranean, raiding merchant ships and threatening vital trade routes. | 答案与高亮正确 |
| 5 | gi_v02_70a2765bace2 | 主句谓语 | 36 | auto_pass | ielts14_test4_p3 J-02 | Many studies 【have looked】 at how plastic affects an individual animal, or that animal's tissues or cells, rather than whole populations. | 答案与高亮正确 |
| 6 | gi_v02_7db1c1d381c0 | 从句边界 | 27 | auto_pass | ielts10_test2_p1 C-04 | The theory sounds eccentric but once he starts to explain the detective work 【that went into his deduction】, the skepticism gives way to wary admiration. | 答案与高亮正确 |
| 7 | gi_v02_4b2d4361230f | 从句边界 | 10 | auto_pass | reading_jijing_38_test_22_p3 D-01 | 【If a school chose to specialise in professional outputs rather than academic outputs】, it could use such a large sum of money and redirect it into more fruitful programs. | 答案与高亮正确 |
| 8 | gi_v02_3213fdcb6d40 | 从句边界 | 60 | auto_pass | ielts8_test3_p3 D-21 | Every organism has a life span 【which is highly characteristic】. | 答案与高亮正确 |
| 9 | gi_v02_f7ef5e533cb7 | 从句边界 | 30 | auto_pass | ielts14_test4_p2 A-06 | A lot of very nasty things happen to truly 'wild' animals 【that simply don't happen in good zoos】, and to view a life that is 'free' as one that is automatically 'good' is, I think, an error. | 答案与高亮正确 |
| 10 | gi_v02_dcb9a9a0e999 | 从句边界 | 59 | auto_pass | reading_jijing_65_test_69_p1 I-02 | 【Before the written word could be used to record history】, people memorised it in songs, says Leon James, a psychologist at the University of Hawaii. | 答案与高亮正确 |
| 11 | gi_v02_b8b311f3f9c0 | 从句类型 | 37 | auto_pass | reading_jijing_40_test_75_p1 F-07 | We catch glimpses of a playful Young, 【doodling Greek and Latin phrases in his notes on medical lectures】 and translating the verses that a young lady had written on the walls of a summerhouse into Greek elegiacs. ⇒ 不是从句（短语或非谓语） | 答案与高亮正确 |
| 12 | gi_v02_ef0b1f2810bf | 从句类型 | 19 | auto_pass | reading_jijing_88_test_98_p2 G-04 | Fourth, and most important, losses have a far greater impact on people than similarly sized gains, a phenomenon 【that Kahneman and Tversky called "loss aversion."】 ⇒ 定语从句 | 答案与高亮正确 |
| 13 | gi_v02_affb09e4603a | 从句类型 | 38 | auto_pass | reading_jijing_32_test_20_p3 G-03 | In his latest studies, Dhurandhar has isolated a gene 【that, when blocked from expressing itself, seems to turn off the virus’s fattening power】. ⇒ 定语从句 | 答案与高亮正确 |
| 14 | gi_v02_2ea6658f514d | 从句类型 | 36 | auto_pass | ielts4_test2_p1 C-11 | Isolation breeds linguistic diversity: as a result, the world is peppered with languages 【spoken by only a few people】. ⇒ 不是从句（短语或非谓语） | 答案与高亮正确 |
| 15 | gi_v02_7bd12fc027b9 | 从句类型 | 21 | auto_pass | ielts10_test2_p3 H-03 | In the case of a major collection, there are probably more works on display 【than we could realistically view in weeks or even months】. ⇒ 状语从句 | 答案与高亮正确 |
| 16 | gi_v02_e14a71c4a87c | 状语关系 | 34 | auto_pass | reading_jijing_56_test_64_p3 H-07 | 【If you have to cook】, steaming will retain at least some of the vitamins and minerals. ⇒ 条件 | 答案与高亮正确 |
| 17 | gi_v02_86d4f0bf9aa6 | 状语关系 | 37 | auto_pass | reading_jijing_14_test_23_p3 D-06 | As a consortium of researchers put it, '【If self-driving cars cut the roughly 40,000 annual US traffic fatalities in half】, the car makers might get not 20,000 thank-you notes, but 20,000 lawsuits.' ⇒ 条件 | 答案与高亮正确 |
| 18 | gi_v02_3bdf276a4cd0 | 状语关系 | 29 | auto_pass | reading_jijing_24_test_56_p2 C-06 | 【When satisficers find an item that meets their standards】, they stop looking. ⇒ 时间 | 答案与高亮正确 |
| 19 | gi_v02_ae2733bdc2bb | 状语关系 | 39 | auto_pass | ielts19_test1_p3 C-01 | The main worry regarding misinformation is its potential to unduly influence attitudes and behavior, leading people to think and act differently than they would 【if they were correctly informed】, as suggested by the research teams of Stephan Lewandowsky of the University of Bristol and Elizabeth Marsh of Duke University, among others. ⇒ 条件 | 答案与高亮正确 |
| 20 | gi_v02_d6e38f82c567 | 状语关系 | 25 | auto_pass | reading_jijing_27_test_33_p3 D-06 | 【If you feel that someone involved is being unfair or unreasonable】, then a solution could over-compensate for this, which of course would not be effective in the long run. ⇒ 条件 | 答案与高亮正确 |
| 21 | gi_v02_59baa4b26f5d | 完整主语 | 21 | auto_pass | ielts4_test1_p1 H-02 | Here, 【children】 are confusing rainforest destruction with damage to the forests of Western Europe by these factors. | 答案与高亮正确 |
| 22 | gi_v02_adcec73212c2 | 完整主语 | 23 | auto_pass | ielts7_test2_p3 C-10 | 【The use of bicycles】 was constrained by their high cost and the lack of available spare parts. | 答案与高亮正确 |
| 23 | gi_v02_2b447192291f | 完整主语 | 46 | auto_pass | ielts5_test1_p1 E-02 | 【Johnson himself】 was stationed on a rickety chair at an 'old crazy deal table' surrounded by a chaos of borrowed books. | 答案与高亮正确 |
| 24 | gi_v02_66d7d218a5f7 | 完整主语 | 57 | auto_pass | ielts5_test4_p1 B-23 | 【Much attention】 has focused on erosion along major trails, but perhaps more important are the deforestation and impacts on water supplies arising from the need to provide tourists with cooked food and hot showers. | 答案与高亮正确 |
| 25 | gi_v02_835c273e4647 | 完整主语 | 16 | auto_pass | reading_jijing_6_test_71_p2 C-02 | 【Development at that time】 was geared to providing homes for the railway and depot workers, with limited investment in shopping and other services for the local population. | 答案与高亮正确 |
| 26 | gi_v02_c38dfb3e85b7 | 动词身份 | 60 | auto_pass | ielts9_test4_p2 F-03 | He called the self-as-object the 'looking-glass self', since people 【come】 to see themselves as they are reflected in others. ⇒ 从句里的谓语 | 答案与高亮正确 |
| 27 | gi_v02_185e282a4ee1 | 动词身份 | 31 | auto_pass | reading_jijing_56_test_64_p1 F-05 | Along the canal, women with babies on their backs labour on what look like portable stairmasters, 【pumping】 water into their fields: the maize is flourishing. ⇒ 非谓语（不定式、分词、动名词） | 答案与高亮正确 |
| 28 | gi_v02_fc39fcaee8dd | 动词身份 | 26 | auto_pass | reading_jijing_88_test_98_p1 A-04 | In these areas registered ownership patterns 【are becoming】 prevalent. ⇒ 主句谓语 | 答案与高亮正确 |
| 29 | gi_v02_44bfa87e4149 | 动词身份 | 40 | auto_pass | ielts20_test1_p1 C-04 | They are entirely vegetarian, with their diet 【including】 the leaves, roots and bark of trees as well as bulbs, and fern fronds. ⇒ 非谓语（不定式、分词、动名词） | 答案与高亮正确 |
| 30 | gi_v02_1848ef598fc4 | 动词身份 | 8 | auto_pass | reading_jijing_40_test_75_p2 D-05 | By receiving more accurate predictions, graziers in northern Queensland are able to avoid overstocking in years when rainfall 【will be】 poor. ⇒ 从句里的谓语 | 答案与高亮正确 |

### C2 全部83新增题

| # | 题目编号 | 工作表/模板 | xlsx行 | 池状态 | 来源 | 核对的答案/高亮 | 判定 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_00354f42ef33 | 动词身份 | — | auto_pass | reading_jijing_84_test_73_p3 E-06 | So the place of articulation of the nasal consonant has been changed 【to conform】 with that of the following plosive. ⇒ 非谓语（不定式、分词、动名词） | 答案与高亮正确 |
| 2 | gi_v02_06f70977d932 | 从句边界 | — | auto_pass | reading_jijing_53_test_83_p2 B-01 | Why wait 【until you are forced off the road by costly charges】? | 答案与高亮正确 |
| 3 | gi_v02_0786eb6b529e | 主句谓语 | — | auto_pass | reading_jijing_56_test_64_p2 H-05 | Blue and green variants 【are found】 in different environments - blue light preferred in the open ocean such as the indigo Sargasso Sea and green light along coasts. | 答案与高亮正确 |
| 4 | gi_v02_11c9d8a7ef4f | 动词身份 | — | auto_pass | reading_jijing_65_test_69_p3 B-05 | The mission, which would leave vehicle tyre-marks all over some of the most famous sites on the Moon, 【was promoted】 as a form of theme-park entertainment. ⇒ 主句谓语 | 答案与高亮正确 |
| 5 | gi_v02_181ad36dd399 | 从句类型 | — | auto_pass | reading_jijing_92_test_58_p1 B-01 | Synaesthesia, loosely translated as "senses coming together" from the Greek words syn ("with") and aesthesis ("sensation"), is an interesting neurological phenomenon 【that causes different senses to be combined】. ⇒ 定语从句 | 答案与高亮正确 |
| 6 | gi_v02_1909e7684996 | 从句类型 | — | auto_pass | ielts19_test4_p3 C-02 | And 【because survival depended on access to resources—such as rivers, forests and animals—】there was bound to be conflict between rival groups, which led to the development of traits such as racism and warfare. ⇒ 状语从句 | 答案与高亮正确 |
| 7 | gi_v02_1d1223d9818c | 完整主语 | — | auto_pass | ielts15_test3_p3 A-04 | 【You】 may think you know the story – but which version? | 答案与高亮正确 |
| 8 | gi_v02_1f4d7dba2457 | 动词身份 | — | auto_pass | reading_jijing_73_test_5_p1 K-02 | Pearce said he hoped plants would grow wild in the atrium and pigeons and bats would move into it, like that termite fungus, further 【extending】 the whole 'organic machine' metaphor. ⇒ 非谓语（不定式、分词、动名词） | 答案与高亮正确 |
| 9 | gi_v02_20784cae194c | 完整主语 | — | auto_pass | reading_jijing_56_test_64_p2 H-05 | 【Blue and green variants】 are found in different environments - blue light preferred in the open ocean such as the indigo Sargasso Sea and green light along coasts. | 答案与高亮正确 |
| 10 | gi_v02_20a95fe378ea | 从句类型 | — | auto_pass | reading_jijing_73_test_5_p1 K-02 | Pearce said he hoped plants would grow wild in the atrium and pigeons and bats would move into it, like that termite fungus, 【further extending the whole 'organic machine' metaphor】. ⇒ 不是从句（短语或非谓语） | 答案与高亮正确 |
| 11 | gi_v02_218f0ac0268d | 动词身份 | — | auto_pass | reading_jijing_65_test_69_p2 G-02 | Once their DNA has been extracted to create cowless steaks and chickenless drumsticks, domesticated species of livestock, 【bred】 for millennia to be stupid or to have grotesquely enhanced traits, should be allowed to become extinct, except for a few specimens in zoos. ⇒ 非谓语（不定式、分词、动名词） | 答案与高亮正确 |
| 12 | gi_v02_23dfff55bb56 | 主句谓语 | — | auto_pass | reading_jijing_65_test_69_p2 G-02 | Once their DNA has been extracted to create cowless steaks and chickenless drumsticks, domesticated species of livestock, bred for millennia to be stupid or to have grotesquely enhanced traits, 【should be allowed】 to become extinct, except for a few specimens in zoos. | 答案与高亮正确 |
| 13 | gi_v02_24717cc61a43 | 动词身份 | — | auto_pass | reading_jijing_65_test_69_p3 B-05 | The mission, which 【would leave】 vehicle tyre-marks all over some of the most famous sites on the Moon, was promoted as a form of theme-park entertainment. ⇒ 从句里的谓语 | 答案与高亮正确 |
| 14 | gi_v02_28c883d198b2 | 从句类型 | — | auto_pass | reading_jijing_48_test_21_p1 E-05 | As a result, the pearl may be seriously deformed, or 【the oyster may directly die from such numerous complications as diseases】. ⇒ 并列分句 | 答案与高亮正确 |
| 15 | gi_v02_2fb55859d134 | 动词身份 | — | auto_pass | ielts8_test3_p3 A-03b | However, in this statement we 【think】 of artificially produced, technical objects, products which are subjected to natural wear and tear during use. ⇒ 主句谓语 | 答案与高亮正确 |
| 16 | gi_v02_2fc0d0adf2b5 | 从句边界 | — | auto_pass | ielts15_test3_p3 A-04 | You may think 【you know the story】 – but which version? | 答案与高亮正确 |
| 17 | gi_v02_392b616b2dff | 动词身份 | — | needs_review | reading_jijing_92_test_58_p1 B-01 | Synaesthesia, loosely translated as "senses coming together" from the Greek words syn ("with") and aesthesis ("sensation"), 【is】 an interesting neurological phenomenon that causes different senses to be combined. ⇒ 主句谓语 | 答案与高亮正确；保守needs_review可接受 |
| 18 | gi_v02_3a9a7231694f | 从句类型 | — | auto_pass | reading_jijing_84_test_73_p3 E-06 | So the place of articulation of the nasal consonant has been changed 【to conform with that of the following plosive】. ⇒ 不是从句（短语或非谓语） | 答案与高亮正确 |
| 19 | gi_v02_3dbf6b37484e | 从句类型 | — | auto_pass | ielts4_test4_p1 I-41 | "Once you study athletics, you learn 【that it's a vexingly complex issue】," says John S. Raglin, a sports psychologist at Indiana University. ⇒ 名词性从句 | 答案与高亮正确 |
| 20 | gi_v02_3eaae5a132ef | 从句边界 | — | auto_pass | reading_jijing_65_test_69_p3 B-05 | The mission, 【which would leave vehicle tyre-marks all over some of the most famous sites on the Moon】, was promoted as a form of theme-park entertainment. | 答案与高亮正确 |
| 21 | gi_v02_450893d4f560 | 动词身份 | — | auto_pass | reading_jijing_53_test_83_p2 B-01 | Why wait until you 【are forced】 off the road by costly charges? ⇒ 从句里的谓语 | 答案与高亮正确 |
| 22 | gi_v02_46ae5aa33437 | 从句类型 | — | needs_review | reading_jijing_5_test_59_p1 I-01 | There are tentative signs 【that more companies are starting to realise】 that failure can lead to commercial gain, and that this is part of the risk-taking that underpins innovation. ⇒ 名词性从句 | 类型正确；目标在realise处截短，漏后续that补语，needs_review合理 |
| 23 | gi_v02_483bc5372da7 | 从句边界 | — | auto_pass | reading_jijing_23_test_46_p1 E-05 | In addition, using products that are made from recycled paper, glass, metal and plastic reduces carbon emissions 【because they use less energy to manufacture than products made from completely new materials】. | 答案与高亮正确 |
| 24 | gi_v02_4b0291e7e23c | 状语关系 | — | auto_pass | reading_jijing_53_test_83_p2 B-01 | Why wait 【until you are forced off the road by costly charges】? ⇒ 时间 | 答案与高亮正确 |
| 25 | gi_v02_4b9f335f7614 | 从句类型 | — | needs_review | reading_jijing_77_test_16_p2 A-01 | 'Your battery is now fully charged,' announced the laptop to its owner Donald A. Norman 【in a synthetic voice, with great enthusiasm and maybe even a hint of pride】. ⇒ 不是从句（短语或非谓语） | 答案与高亮正确；保守needs_review可接受 |
| 26 | gi_v02_4c740d83327c | 从句类型 | — | needs_review | reading_jijing_46_test_84_p2 G-05 | Of the first set of recruits to complete the programme, half have gone on to work for "some amazing companies", 【while the other half have chosen to stay on in their schools for a further year】 - 20% in leadership roles. ⇒ 状语从句 | 状语类型正确；附加20%说明在目标外，保留needs_review |
| 27 | gi_v02_53de8d8dbb3c | 状语关系 | — | needs_review | reading_jijing_46_test_84_p2 G-05 | Of the first set of recruits to complete the programme, half have gone on to work for "some amazing companies", 【while the other half have chosen to stay on in their schools for a further year】 - 20% in leadership roles. ⇒ 对比 | 对比关系正确；附加说明边界待复核 |
| 28 | gi_v02_585942db8226 | 动词身份 | — | auto_pass | ielts20_test2_p1 B-02 | This short neck 【allows】 a manatee to move its head up and down, but not side to side. ⇒ 主句谓语 | 答案与高亮正确 |
| 29 | gi_v02_5a2d9f10df5a | 完整主语 | — | needs_review | reading_jijing_81_test_93_p2 F-01 | 【What, if anything】, can be done? | 答案错：if anything是插入语，主语应What；已needs_review |
| 30 | gi_v02_5d5acf93d24b | 从句边界 | — | auto_pass | reading_jijing_5_test_59_p1 I-01 | There are tentative signs that more companies are starting to realise that failure can lead to commercial gain, and that this is part of the risk-taking 【that underpins innovation】. | 答案与高亮正确 |
| 31 | gi_v02_5ff683ee908d | 主句谓语 | — | auto_pass | ielts8_test3_p3 A-03b | However, in this statement we 【think】 of artificially produced, technical objects, products which are subjected to natural wear and tear during use. | 答案与高亮正确 |
| 32 | gi_v02_618aee26fe22 | 动词身份 | — | auto_pass | reading_jijing_26_test_72_p1 A-05 | But now and then, hunter-gatherers must have discovered rare mutant plants that 【produced】 seedless, edible fruits. ⇒ 从句里的谓语 | 答案与高亮正确 |
| 33 | gi_v02_622d63e3130f | 从句类型 | — | auto_pass | reading_jijing_16_test_97_p1 E-01 | MacPhee agrees that humans most likely brought about these extinctions (as well as others around the world 【that coincided with human arrival】), but not directly. ⇒ 定语从句 | 答案与高亮正确 |
| 34 | gi_v02_6a4c73660fc6 | 状语关系 | — | auto_pass | reading_jijing_44_test_29_p3 M-01 | - is calm, and is not excitable 【when something unexpected happens】 ⇒ 时间 | 局部答案与高亮正确；列表片段需上下文（A6） |
| 35 | gi_v02_6aa82bd827d5 | 动词身份 | — | auto_pass | reading_jijing_23_test_46_p1 E-05 | In addition, using products that are made from recycled paper, glass, metal and plastic 【reduces】 carbon emissions because they use less energy to manufacture than products made from completely new materials. ⇒ 主句谓语 | 答案与高亮正确 |
| 36 | gi_v02_6b596b6b0a4a | 动词身份 | — | auto_pass | reading_jijing_38_test_22_p1 H-06 | 【Viewing】 the offender and their crime in isolation and disregarding all other social and environmental factors is therefore mistaken, if not downright morally reprehensible. ⇒ 非谓语（不定式、分词、动名词） | 答案与高亮正确 |
| 37 | gi_v02_6d600583b1a8 | 从句类型 | — | auto_pass | reading_jijing_53_test_83_p2 B-01 | Why wait 【until you are forced off the road by costly charges】? ⇒ 状语从句 | 答案与高亮正确 |
| 38 | gi_v02_70e5cf5c2885 | 完整主语 | — | needs_review | ielts8_test3_p3 A-03b | However, in this statement 【we】 think of artificially produced, technical objects, products which are subjected to natural wear and tear during use. | 答案与高亮正确；保守needs_review可接受 |
| 39 | gi_v02_71858a50cf66 | 从句类型 | — | auto_pass | reading_jijing_65_test_69_p2 G-02 | Once their DNA has been extracted to create cowless steaks and chickenless drumsticks, domesticated species of livestock, 【bred for millennia to be stupid or to have grotesquely enhanced traits】, should be allowed to become extinct, except for a few specimens in zoos. ⇒ 不是从句（短语或非谓语） | 答案与高亮正确 |
| 40 | gi_v02_73acebae1b1e | 主句谓语 | — | auto_pass | reading_jijing_92_test_58_p1 B-01 | Synaesthesia, loosely translated as "senses coming together" from the Greek words syn ("with") and aesthesis ("sensation"), 【is】 an interesting neurological phenomenon that causes different senses to be combined. | 答案与高亮正确 |
| 41 | gi_v02_748165fdcb44 | 动词身份 | — | auto_pass | reading_jijing_56_test_64_p2 H-05 | Blue and green variants 【are found】 in different environments - blue light preferred in the open ocean such as the indigo Sargasso Sea and green light along coasts. ⇒ 主句谓语 | 答案与高亮正确 |
| 42 | gi_v02_7653d19f4747 | 动词身份 | — | auto_pass | reading_jijing_84_test_73_p3 E-06 | So the place of articulation of the nasal consonant 【has been changed】 to conform with that of the following plosive. ⇒ 主句谓语 | 答案与高亮正确 |
| 43 | gi_v02_76bd7aa23bff | 动词身份 | — | auto_pass | reading_jijing_16_test_97_p1 E-01 | MacPhee agrees that humans most likely brought about these extinctions (as well as others around the world that 【coincided】 with human arrival), but not directly. ⇒ 从句里的谓语 | 答案与高亮正确 |
| 44 | gi_v02_7e2f475c21e7 | 从句边界 | — | auto_pass | reading_jijing_48_test_21_p1 E-05 | As a result, the pearl may be seriously deformed, or 【the oyster may directly die from such numerous complications as diseases】. | 答案与高亮正确 |
| 45 | gi_v02_7e6c0dc53eae | 从句类型 | — | auto_pass | reading_jijing_26_test_72_p1 A-05 | But now and then, hunter-gatherers must have discovered rare mutant plants 【that produced seedless, edible fruits】. ⇒ 定语从句 | 答案与高亮正确 |
| 46 | gi_v02_7ff80f5cee98 | 从句边界 | — | auto_pass | reading_jijing_62_test_44_p3 I-01 | Richard Hession, author of Be a Great Salesperson, says it is human nature to prefer to speak rather than listen, and 【good salespeople pander to this】. | 答案与高亮正确 |
| 47 | gi_v02_84a87a984bc5 | 从句边界 | — | auto_pass | reading_jijing_16_test_97_p1 E-01 | MacPhee agrees that humans most likely brought about these extinctions (as well as others around the world 【that coincided with human arrival】), but not directly. | 答案与高亮正确 |
| 48 | gi_v02_89606374fb7c | 从句边界 | — | auto_pass | reading_jijing_92_test_58_p1 B-01 | Synaesthesia, loosely translated as "senses coming together" from the Greek words syn ("with") and aesthesis ("sensation"), is an interesting neurological phenomenon 【that causes different senses to be combined】. | 答案与高亮正确 |
| 49 | gi_v02_8aeae0a58c91 | 从句类型 | — | auto_pass | reading_jijing_65_test_69_p3 B-05 | The mission, 【which would leave vehicle tyre-marks all over some of the most famous sites on the Moon】, was promoted as a form of theme-park entertainment. ⇒ 定语从句 | 答案与高亮正确 |
| 50 | gi_v02_8c588cd1fa99 | 状语关系 | — | auto_pass | reading_jijing_23_test_46_p1 E-05 | In addition, using products that are made from recycled paper, glass, metal and plastic reduces carbon emissions 【because they use less energy to manufacture than products made from completely new materials】. ⇒ 原因 | 答案与高亮正确 |
| 51 | gi_v02_92600be34fb8 | 完整主语 | — | auto_pass | reading_jijing_65_test_69_p2 G-02 | Once their DNA has been extracted to create cowless steaks and chickenless drumsticks, 【domesticated species of livestock, bred for millennia to be stupid or to have grotesquely enhanced traits】, should be allowed to become extinct, except for a few specimens in zoos. | 答案与高亮正确 |
| 52 | gi_v02_93f037acdfeb | 从句类型 | — | needs_review | reading_jijing_32_test_20_p1 B-03 | After scrutinising medieval pictures and diaries, he concluded that there was no distinction between children and adults 【for they shared similar leisure activities and work】. ⇒ 并列分句 | 答案与高亮正确；保守needs_review可接受 |
| 53 | gi_v02_95025b986926 | 动词身份 | — | needs_review | reading_jijing_38_test_22_p1 H-06 | Viewing the offender and their crime in isolation and disregarding all other social and environmental factors 【is】 therefore mistaken, if not downright morally reprehensible. ⇒ 主句谓语 | 答案与高亮正确；保守needs_review可接受 |
| 54 | gi_v02_96121bcd2abc | 动词身份 | — | needs_review | reading_jijing_23_test_46_p1 E-05 | In addition, using products that are made from recycled paper, glass, metal and plastic reduces carbon emissions because they 【use】 less energy to manufacture than products made from completely new materials. ⇒ 从句里的谓语 | 答案与高亮正确；保守needs_review可接受 |
| 55 | gi_v02_96287b126ba9 | 从句类型 | — | auto_pass | ielts5_test1_p2 B-01 | Milgram's experimental set-up involved placing the teacher-subject before a panel of thirty switches 【with labels ranging from '15 volts of electricity (slight shock)' to '450 volts (danger - severe shock)'】 in steps of 15 volts each. ⇒ 不是从句（短语或非谓语） | 答案与高亮正确 |
| 56 | gi_v02_9640952845c3 | 主句谓语 | — | auto_pass | reading_jijing_65_test_69_p3 B-05 | The mission, which would leave vehicle tyre-marks all over some of the most famous sites on the Moon, 【was promoted】 as a form of theme-park entertainment. | 答案与高亮正确 |
| 57 | gi_v02_96670a2318b3 | 从句边界 | — | auto_pass | ielts4_test4_p1 I-41 | "Once you study athletics, you learn 【that it's a vexingly complex issue】," says John S. Raglin, a sports psychologist at Indiana University. | 答案与高亮正确 |
| 58 | gi_v02_9c1757e5e5f1 | 从句边界 | — | auto_pass | reading_jijing_62_test_44_p3 I-01 | Richard Hession, author of Be a Great Salesperson, says 【it is human nature to prefer to speak rather than listen】, and good salespeople pander to this. | 答案与高亮正确 |
| 59 | gi_v02_9d30711afa2d | 主句谓语 | — | auto_pass | ielts20_test2_p1 B-02 | This short neck 【allows】 a manatee to move its head up and down, but not side to side. | 答案与高亮正确 |
| 60 | gi_v02_ac44a7c144c8 | 完整主语 | — | auto_pass | ielts20_test2_p1 B-02 | 【This short neck】 allows a manatee to move its head up and down, but not side to side. | 答案与高亮正确 |
| 61 | gi_v02_b145ca39ef17 | 主句谓语 | — | auto_pass | reading_jijing_84_test_73_p3 E-06 | So the place of articulation of the nasal consonant 【has been changed】 to conform with that of the following plosive. | 答案与高亮正确 |
| 62 | gi_v02_b33f4b6b17fc | 从句边界 | — | needs_review | reading_jijing_16_test_97_p1 E-01 | MacPhee agrees 【that humans most likely brought about these extinctions】 (as well as others around the world that coincided with human arrival), but not directly. | 边界不完整：漏从句附加说明，已needs_review |
| 63 | gi_v02_b82799440ca0 | 动词身份 | — | auto_pass | reading_jijing_65_test_69_p2 G-02 | Once their DNA has been extracted to create cowless steaks and chickenless drumsticks, domesticated species of livestock, bred for millennia to be stupid or to have grotesquely enhanced traits, 【should be allowed】 to become extinct, except for a few specimens in zoos. ⇒ 主句谓语 | 答案与高亮正确 |
| 64 | gi_v02_ba1fb8fd65c9 | 从句类型 | — | auto_pass | reading_jijing_23_test_46_p1 E-05 | In addition, using products that are made from recycled paper, glass, metal and plastic reduces carbon emissions 【because they use less energy to manufacture than products made from completely new materials】. ⇒ 状语从句 | 答案与高亮正确 |
| 65 | gi_v02_be7116c2c28d | 从句类型 | — | auto_pass | reading_jijing_62_test_44_p3 I-01 | Richard Hession, author of Be a Great Salesperson, says it is human nature to prefer to speak rather than listen, and 【good salespeople pander to this】. ⇒ 并列分句 | 答案与高亮正确 |
| 66 | gi_v02_c28518bc1c63 | 从句边界 | — | needs_review | reading_jijing_46_test_84_p2 G-05 | Of the first set of recruits to complete the programme, half have gone on to work for "some amazing companies", 【while the other half have chosen to stay on in their schools for a further year】 - 20% in leadership roles. | while核心边界可辨，但附加20%说明遗漏，保留needs_review |
| 67 | gi_v02_c41e941b991e | 从句边界 | — | needs_review | reading_jijing_32_test_20_p1 B-03 | After scrutinising medieval pictures and diaries, he concluded that there was no distinction between children and adults 【for they shared similar leisure activities and work】. | 答案与高亮正确；保守needs_review可接受 |
| 68 | gi_v02_c7795326ba56 | 主句谓语 | — | auto_pass | reading_jijing_38_test_22_p1 H-06 | Viewing the offender and their crime in isolation and disregarding all other social and environmental factors 【is】 therefore mistaken, if not downright morally reprehensible. | 答案与高亮正确 |
| 69 | gi_v02_c9400354f43b | 动词身份 | — | auto_pass | reading_jijing_46_test_84_p2 G-05 | Of the first set of recruits to complete the programme, half have gone on to work for "some amazing companies", while the other half 【have chosen】 to stay on in their schools for a further year - 20% in leadership roles. ⇒ 从句里的谓语 | 答案与高亮正确 |
| 70 | gi_v02_cbaf8676b1f0 | 从句边界 | — | auto_pass | reading_jijing_26_test_72_p1 A-05 | But now and then, hunter-gatherers must have discovered rare mutant plants 【that produced seedless, edible fruits】. | 答案与高亮正确 |
| 71 | gi_v02_d29f45361cc8 | 从句类型 | — | needs_review | reading_jijing_16_test_97_p1 E-01 | MacPhee agrees 【that humans most likely brought about these extinctions】 (as well as others around the world that coincided with human arrival), but not directly. ⇒ 名词性从句 | 类型正确；范围漏从句附加说明，已needs_review |
| 72 | gi_v02_d4bc3da831e7 | 动词身份 | — | auto_pass | ielts15_test3_p3 A-04 | You 【may think】 you know the story – but which version? ⇒ 主句谓语 | 答案与高亮正确 |
| 73 | gi_v02_d4d6289c3594 | 主句谓语 | — | auto_pass | reading_jijing_23_test_46_p1 E-05 | In addition, using products that are made from recycled paper, glass, metal and plastic 【reduces】 carbon emissions because they use less energy to manufacture than products made from completely new materials. | 答案与高亮正确 |
| 74 | gi_v02_d8286575387b | 从句类型 | — | auto_pass | reading_jijing_44_test_29_p3 M-01 | - is calm, and is not excitable 【when something unexpected happens】 ⇒ 状语从句 | 局部答案与高亮正确；列表片段需上下文（A6） |
| 75 | gi_v02_def9b6b4c193 | 主句谓语 | — | auto_pass | ielts15_test3_p3 A-04 | You 【may think】 you know the story – but which version? | 答案与高亮正确 |
| 76 | gi_v02_df815e1bc263 | 状语关系 | — | auto_pass | ielts19_test4_p3 C-02 | And 【because survival depended on access to resources—such as rivers, forests and animals—】there was bound to be conflict between rival groups, which led to the development of traits such as racism and warfare. ⇒ 原因 | 答案与高亮正确 |
| 77 | gi_v02_e8e5e87288f8 | 从句边界 | — | auto_pass | reading_jijing_44_test_29_p3 M-01 | - is calm, and is not excitable 【when something unexpected happens】 | 局部答案与高亮正确；列表片段需上下文（A6） |
| 78 | gi_v02_e96006c1e246 | 从句类型 | — | auto_pass | reading_jijing_62_test_44_p3 I-01 | Richard Hession, author of Be a Great Salesperson, says 【it is human nature to prefer to speak rather than listen】, and good salespeople pander to this. ⇒ 名词性从句 | 答案与高亮正确 |
| 79 | gi_v02_ece54dc3c4ac | 从句类型 | — | auto_pass | reading_jijing_38_test_22_p1 H-06 | 【Viewing the offender and their crime in isolation and disregarding all other social and environmental factors】 is therefore mistaken, if not downright morally reprehensible. ⇒ 不是从句（短语或非谓语） | 答案与高亮正确 |
| 80 | gi_v02_ef9ae2b4c263 | 动词身份 | — | auto_pass | reading_jijing_92_test_58_p1 B-01 | Synaesthesia, loosely translated as "senses coming together" from the Greek words syn ("with") and aesthesis ("sensation"), is an interesting neurological phenomenon that 【causes】 different senses to be combined. ⇒ 从句里的谓语 | 答案与高亮正确 |
| 81 | gi_v02_f41d9eeaef05 | 完整主语 | — | auto_pass | reading_jijing_84_test_73_p3 E-06 | So 【the place of articulation of the nasal consonant】 has been changed to conform with that of the following plosive. | 答案与高亮正确 |
| 82 | gi_v02_fd3845e8e24f | 从句类型 | — | auto_pass | ielts15_test3_p3 A-04 | You may think 【you know the story】 – but which version? ⇒ 名词性从句 | 答案与高亮正确 |
| 83 | gi_v02_ff13a9dd5d98 | 动词身份 | — | auto_pass | reading_jijing_44_test_29_p3 M-01 | - is calm, and is not excitable when something unexpected 【happens】 ⇒ 从句里的谓语 | 局部答案与高亮正确；列表片段需上下文（A6） |

### C3 改动句自动池30题

| # | 题目编号 | 工作表/模板 | xlsx行 | 池状态 | 来源 | 核对的答案/高亮 | 判定 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | gi_v02_dfe014738eb2 | 从句类型 | — | auto_pass | reading_jijing_16_test_97_p1 B-06 | The overkill model emerged in the 1960s, 【when it was put forth by Paul S. Martin of the University of Arizona】. ⇒ 定语从句 | 答案与高亮正确 |
| 2 | gi_v02_b5c7b787ec3e | 动词身份 | — | auto_pass | reading_jijing_32_test_20_p1 E-01 | The concerns of reformers gradually 【had】 some impact upon the working condition of children. ⇒ 主句谓语 | 答案与高亮正确 |
| 3 | gi_v02_5e42a802ee36 | 从句边界 | — | auto_pass | reading_jijing_92_test_58_p3 F-07 | However, the shortage of houses occurs 【when lots of people crushed to the seaside】. | 局部答案/高亮正确；原句语病或残缺，不宜直接交学生（既有A3/A6） |
| 4 | gi_v02_8c588cd1fa99 | 状语关系 | — | auto_pass | reading_jijing_23_test_46_p1 E-05 | In addition, using products that are made from recycled paper, glass, metal and plastic reduces carbon emissions 【because they use less energy to manufacture than products made from completely new materials】. ⇒ 原因 | 答案与高亮正确 |
| 5 | gi_v02_bca65eff43ff | 动词身份 | — | auto_pass | reading_jijing_76_test_43_p3 C-08 | His collaborator Wallace Friesen believed that Organizing a child's daily activities so that they 【occur】 in the same order each day as much as possible. ⇒ 从句里的谓语 | 局部答案/高亮正确；原句语病或残缺，不宜直接交学生（既有A3/A6） |
| 6 | gi_v02_71858a50cf66 | 从句类型 | — | auto_pass | reading_jijing_65_test_69_p2 G-02 | Once their DNA has been extracted to create cowless steaks and chickenless drumsticks, domesticated species of livestock, 【bred for millennia to be stupid or to have grotesquely enhanced traits】, should be allowed to become extinct, except for a few specimens in zoos. ⇒ 不是从句（短语或非谓语） | 答案与高亮正确 |
| 7 | gi_v02_479270c059b8 | 主句谓语 | — | auto_pass | reading_jijing_92_test_58_p3 F-03 | A Royal Surf Carnival 【was held】 at Bondi Beach for Queen Elizabeth II during her first visited in Australia in 1954. | 局部答案/高亮正确；原句语病或残缺，不宜直接交学生（既有A3/A6） |
| 8 | gi_v02_bb1d4b40519c | 从句类型 | — | auto_pass | reading_jijing_83_test_95_p2 F-01 | 【In Indonesia】, ecotourism started to become an important concept from 1995, in order to strengthen the domestic travelling movement, the local government targeting the right markets is a prerequisite for successful ecotourism. ⇒ 不是从句（短语或非谓语） | 局部答案/高亮正确；原句标点异常须提示（A6） |
| 9 | gi_v02_aec697672490 | 动词身份 | — | auto_pass | reading_jijing_48_test_21_p3 M-02 | So far, global warming 【has been】 a world issue that still hangs in an ambiguous future. ⇒ 主句谓语 | 答案与高亮正确 |
| 10 | gi_v02_24717cc61a43 | 动词身份 | — | auto_pass | reading_jijing_65_test_69_p3 B-05 | The mission, which 【would leave】 vehicle tyre-marks all over some of the most famous sites on the Moon, was promoted as a form of theme-park entertainment. ⇒ 从句里的谓语 | 答案与高亮正确 |
| 11 | gi_v02_6c062182d7c5 | 从句类型 | — | auto_pass | reading_jijing_27_test_33_p3 C-03 | Finger-pointing and blaming leads to an uncomfortable work environment 【where problems grow, and ultimately have a detrimental effect on the productivity of the workplace】. ⇒ 定语从句 | 答案与高亮正确 |
| 12 | gi_v02_69ca7b26dec7 | 动词身份 | — | auto_pass | reading_jijing_9_test_81_p1 E-03 | And after they were given some evidence 【opposing】 the position, the Korean started to modified or decreased their support. ⇒ 非谓语（不定式、分词、动名词） | 局部答案/高亮正确；原句语病或残缺，不宜直接交学生（既有A3/A6） |
| 13 | gi_v02_36b92c7d8c13 | 从句类型 | — | auto_pass | reading_jijing_83_test_95_p2 F-01 | In Indonesia, ecotourism started to become an important concept 【from 1995】, in order to strengthen the domestic travelling movement, the local government targeting the right markets is a prerequisite for successful ecotourism. ⇒ 不是从句（短语或非谓语） | 局部答案/高亮正确；原句标点异常须提示（A6） |
| 14 | gi_v02_addbc54f45ab | 从句类型 | — | auto_pass | reading_jijing_9_test_81_p2 B-01 | Couran Cove Island Resort is a large integrated ecotourism-based resort 【located south of Brisbane on the Gold Coast, Queensland, Australia】. ⇒ 不是从句（短语或非谓语） | 答案与高亮正确 |
| 15 | gi_v02_5ff683ee908d | 主句谓语 | — | auto_pass | ielts8_test3_p3 A-03b | However, in this statement we 【think】 of artificially produced, technical objects, products which are subjected to natural wear and tear during use. | 答案与高亮正确 |
| 16 | gi_v02_d097102da6b5 | 完整主语 | — | auto_pass | reading_jijing_22_test_90_p3 G-06 | Previously 【the organisation】 has taken a more formalised approach to staff development training relying on methods such as psychometric testing discussions, motivational conferences and formal appraisals. | 答案与高亮正确 |
| 17 | gi_v02_322c3f33b8f9 | 动词身份 | — | auto_pass | reading_jijing_73_test_5_p2 E-11 | This is especially true of a solitary hunter such as the tiger and may explain why lions-particularly young lionesses who 【tend】 to encourage one another to take risks are more dangerous than tigers. ⇒ 从句里的谓语 | 局部答案/高亮正确；原句标点异常须提示（A6） |
| 18 | gi_v02_6888615848f8 | 从句类型 | — | auto_pass | reading_jijing_76_test_43_p1 E-01 | Clinical depression was originally solely attributed to chemical imbalance in the brain, and 【while anti-depressant drugs which work to optimise levels of 'feel good' chemicals – serotonin and norepinephrine – are still commonly prescribed today】, experts now believe that onset of depression may be caused by a number, and often combination of, physiological and socio-psychological factors. ⇒ 状语从句 | 答案与高亮正确 |
| 19 | gi_v02_95efeb86b429 | 主句谓语 | — | auto_pass | reading_jijing_83_test_95_p2 G-01 | On the other hand, ecotourism 【provide】 as many services as traditional tourism. | 局部答案/高亮正确；原句语病或残缺，不宜直接交学生（既有A3/A6） |
| 20 | gi_v02_f4b19b1e5a78 | 主句谓语 | — | auto_pass | reading_jijing_53_test_83_p3 F-03 | Constant energy shortages and blackouts 【are】 a common problem due to a lack of power plants, transmission and distribution losses caused by old technology and illegal stealing of electricity from the grid. | 答案与高亮正确 |
| 21 | gi_v02_29575bea268c | 动词身份 | — | auto_pass | reading_jijing_9_test_81_p2 B-01 | Couran Cove Island Resort is a large integrated ecotourism-based resort 【located】 south of Brisbane on the Gold Coast, Queensland, Australia. ⇒ 非谓语（不定式、分词、动名词） | 答案与高亮正确 |
| 22 | gi_v02_649b037df6a2 | 动词身份 | — | auto_pass | reading_jijing_22_test_90_p3 G-06 | Previously the organisation has taken a more formalised approach to staff development training 【relying】 on methods such as psychometric testing discussions, motivational conferences and formal appraisals. ⇒ 非谓语（不定式、分词、动名词） | 答案与高亮正确 |
| 23 | gi_v02_23dfff55bb56 | 主句谓语 | — | auto_pass | reading_jijing_65_test_69_p2 G-02 | Once their DNA has been extracted to create cowless steaks and chickenless drumsticks, domesticated species of livestock, bred for millennia to be stupid or to have grotesquely enhanced traits, 【should be allowed】 to become extinct, except for a few specimens in zoos. | 答案与高亮正确 |
| 24 | gi_v02_807ed9857141 | 完整主语 | — | auto_pass | reading_jijing_27_test_33_p3 C-01 | 【Garen Filke, Managing Director of a large paper supply company】, has put Hewings' steps to the test, and although he referred to the results as 'potentially encouraging', there remains the feeling that the focus on who is causing the problem, and this in itself is the main reason for any implemented solution to falter if not fail. | 局部答案/高亮正确；原句语病或残缺，不宜直接交学生（既有A3/A6） |
| 25 | gi_v02_6f4d11e52339 | 完整主语 | — | auto_pass | reading_jijing_10_test_78_p3 F-01 | 【Incidents where vein has been injected intrathecally instead of spine】 are a classic example of how poor design can contribute to harm. | 局部答案/高亮正确；原句语病或残缺，不宜直接交学生（既有A3/A6） |
| 26 | gi_v02_4b84a4452a2f | 从句类型 | — | auto_pass | reading_jijing_73_test_5_p2 A-04 | Tigers can and do kill almost everything 【they meet in the jungle】, they will kill even attack elephants and rhino. ⇒ 定语从句 | 局部答案/高亮正确；原句语病或残缺，不宜直接交学生（既有A3/A6） |
| 27 | gi_v02_b568f5077d22 | 从句边界 | — | auto_pass | reading_jijing_27_test_33_p3 C-02 | With over 30 years of management experience, Filke holds 【that looking at the problem as an organic entity in itself, without reference to who may be at fault, or at least exacerbating the issue, is the only way to find a lasting solution】. | 答案与高亮正确 |
| 28 | gi_v02_a12b390f385a | 动词身份 | — | auto_pass | reading_jijing_48_test_21_p1 F-01 | Imitation pearls 【are】 of another different story. ⇒ 主句谓语 | 答案与高亮正确 |
| 29 | gi_v02_4e3b204118be | 主句谓语 | — | auto_pass | reading_jijing_53_test_83_p2 G-04 | Other people 【may be】 able to replace part or all of their journey to work - or any journeys, for that matter - with low-cost transport such as a bicycle, or even by just walking. | 答案与高亮正确 |
| 30 | gi_v02_4ba817b7adb2 | 动词身份 | — | auto_pass | reading_jijing_27_test_33_p3 D-02 | Wicks has built the filters into a ladder through which all decisions 【have】 the potential to be coloured, the first step being programming – from the day we are born, there is an amount of conditioning that means we accept or reject certain points of view almost a reflex action. ⇒ 从句里的谓语 | 局部答案/高亮正确；原句语病或残缺，不宜直接交学生（既有A3/A6） |

## 附录D：破折号补全全库58题

同语料/parse只换回c4bb253前close_quotes函数作对照。所有58道均人工看过前后范围与原句，闭破折号补回合理；下面列当前题号和补后范围。T5题号可能不变但answer范围改变，故不能只查新增ID。

| 题号 | 来源 | 模板 | 补后范围 | 判定 |
| --- | --- | --- | --- | --- |
| gi_v02_46a92ce02130 | ielts8_test2_p1 F-02 | subject_span | Several processes - melting, refining, homogenising - | 补全合理；未超调用边界 |
| gi_v02_52bd3f659210 | ielts10_test1_p2 D-01 | subject_span | a new imperative – sustainable development – | 补全合理；未超调用边界 |
| gi_v02_706cc3d1ee76 | ielts15_test4_p2 B-01 | subject_span | This 'language', known as 'Silbo' or 'Silbo Gomero' – from the Spanish word for 'whistle' – | 补全合理；未超调用边界 |
| gi_v02_3ec00c3e1ce8 | ielts15_test4_p2 D-02 | subject_span | A whistler – or silbador – | 补全合理；未超调用边界 |
| gi_v02_b6dd08bed1d4 | ielts5_test4_p2 J-45b | subject_span | the alternative - re-cladding the entire building - | 补全合理；未超调用边界 |
| gi_v02_c02b3980856e | reading_jijing_13_test_6_p2 C-13 | subject_span | China's best directors - Bu Wancang and Yuan Muzhi - | 补全合理；未超调用边界 |
| gi_v02_29caef68e341 | ielts12_test5_p2 F-01 | subject_span | another potential reason for it - or, perhaps, a result of collecting - | 补全合理；未超调用边界 |
| gi_v02_09e5cafefbc6 | ielts11_test4_p3 C-03 | subject_span | these configurations of mouth – p, f, b, v, t, d, k, g, sh, a, e and so on – | 补全合理；未超调用边界 |
| gi_v02_d11351d53007 | ielts20_test3_p2 A-02 | subject_span | Samples of the planet's most spectacular corals – vivid green branching coral, yellow scroll, blue ridge and many more species – | 补全合理；未超调用边界 |
| gi_v02_9a4b05232797 | ielts19_test3_p2 D-02 | subject_span | Peatlands - wetlands with a waterlogged organic soil layer - | 补全合理；未超调用边界 |
| gi_v02_9df4fa69fa2d | reading_jijing_83_test_95_p1 D-03 | subject_span | this one – as small as it was – | 补全合理；未超调用边界 |
| gi_v02_81f7ea5caafe | reading_jijing_83_test_95_p1 G-12 | subject_span | the words – and what can only be called the thoughts – | 补全合理；未超调用边界 |
| gi_v02_db38df4214e0 | reading_jijing_78_test_102_p2 E-05 | subject_span | The rise and fall of corporate empires – soft-drink companies, snack-food companies, and fast-food chains – | 补全合理；未超调用边界 |
| gi_v02_ed4743fde6b9 | reading_jijing_29_test_63_p3 A-03 | subject_span | Some $265 billion of the increase - 93% of it - | 补全合理；未超调用边界 |
| gi_v02_1489672a6bd6 | reading_jijing_16_test_97_p1 B-02 | subject_span | these large-bodied mammals and others – about 70 species in all – | 补全合理；未超调用边界 |
| gi_v02_272ee85356fd | reading_jijing_16_test_97_p1 F-07 | subject_span | the final major fluctuation – the so-called Younger Dryas event – | 补全合理；未超调用边界 |
| gi_v02_fa439f1d87c3 | reading_jijing_40_test_75_p2 C-05 | subject_span | The icy blast that howls over the ice cap and out to sea—the so-called katabatic wind— | 补全合理；未超调用边界 |
| gi_v02_9305c0cd5919 | reading_jijing_40_test_75_p2 E-05 | subject_span | Antarctic krill—the small shrimp-like crustaceans that are the staple diet for baleen whales, penguins, some seals, flighted sea birds and many fish— | 补全合理；未超调用边界 |
| gi_v02_1e0a68724414 | ielts6_test3_p1 E-04 | subject_span | the lives recorded—at least in film fiction— | 补全合理；未超调用边界 |
| gi_v02_c7570d59c8f3 | ielts6_test3_p1 E-06 | subject_span | American imagery—the cars, the cities, the cowboys— | 补全合理；未超调用边界 |
| gi_v02_52d4842ef66c | ielts17_test3_p2 C-03 | subject_span | Endangered species – most famously the Sumatran orangutan, but also rhinos, elephants, tigers, and numerous other fauna – | 补全合理；未超调用边界 |
| gi_v02_2f38b1560388 | ielts17_test3_p2 F-03 | subject_span | That immensely high yield – which is predominantly what makes it so profitable – | 补全合理；未超调用边界 |
| gi_v02_b0d9dcf708ff | ielts13_test3_p2 A-01 | subject_span | The typical way of talking to a baby—high-pitched, exaggerated and repetitious— | 补全合理；未超调用边界 |
| gi_v02_03fa404f66ca | ielts13_test3_p2 F-01 | subject_span | a total of 57 babies from two slightly different age groups—seven months and eleven and a half months— | 补全合理；未超调用边界 |
| gi_v02_1d674c75bad9 | ielts13_test3_p3 A-03 | subject_span | their lack of self-imagery - at a time when the Egyptians were carving and painting representations of themselves all over their temples - | 补全合理；未超调用边界 |
| gi_v02_7a727ebdd3d1 | ielts18_test4_p3 B-03 | subject_span | Wegener's idea – that the continents move – | 补全合理；未超调用边界 |
| gi_v02_c516b42bddd1 | ielts4_test3_p2 A-03 | subject_span | the classic eruption - cone-shaped mountain, big bang, mushroom cloud and surges of molten lava - | 补全合理；未超调用边界 |
| gi_v02_2a33047fcd6c | ielts4_test3_p2 C-04 | subject_span | vast bubbles of magma - molten rock from the mantle - | 补全合理；未超调用边界 |
| gi_v02_65f5ac4466e5 | reading_jijing_84_test_73_p1 A-08 | subject_span | Rivers – and the ecosystems they support – | 补全合理；未超调用边界 |
| gi_v02_8f3e09cddf40 | reading_jijing_88_test_98_p2 A-05 | subject_span | Most innovative products – those that create new product categories or revolutionize old ones – | 补全合理；未超调用边界 |
| gi_v02_e4b2747f8dbb | ielts11_test3_p2 D-01 | subject_span | daily vertical movements by zooplankton in the ocean—upward by night to seek food, downward by day to escape predators— | 补全合理；未超调用边界 |
| gi_v02_68829f50d56a | ielts6_test2_p2 B-06 | subject_span | Other diseases of old age—dementia, stroke, arteriosclerosis and emphysema— | 补全合理；未超调用边界 |
| gi_v02_e83aef685100 | ielts19_test4_p3 C-02 | clause_boundary | because survival depended on access to resources—such as rivers, forests and animals— | 补全合理；未超调用边界 |
| gi_v02_1909e7684996 | ielts19_test4_p3 C-02 | clause_type_classify | because survival depended on access to resources—such as rivers, forests and animals— | 补全合理；未超调用边界 |
| gi_v02_df815e1bc263 | ielts19_test4_p3 C-02 | adverbial_relation | because survival depended on access to resources—such as rivers, forests and animals— | 补全合理；未超调用边界 |
| gi_v02_23f62fa96094 | ielts6_test3_p3 D-17 | subject_span | caloric-restriction projects underway in two species more closely related to humans - rhesus and squirrel monkeys - | 补全合理；未超调用边界 |
| gi_v02_e3d3de503d33 | ielts7_test2_p1 B-08 | subject_span | the thirty-six-storey Kasumigaseki building in central Tokyo - Japan's first skyscraper - | 补全合理；未超调用边界 |
| gi_v02_1c7eda318b26 | ielts10_test2_p1 C-03 | subject_span | The antiseptic properties of tannin, the active ingredient in tea, and of hops in beer – plus the fact that both are made with boiled water – | 补全合理；未超调用边界 |
| gi_v02_6ace4263f04d | reading_jijing_24_test_56_p3 D-03 | subject_span | Stages which need to be fulfilled prior to clinical trial – where the treatment is actually tested on human subjects - | 补全合理；未超调用边界 |
| gi_v02_4ac41bc37a08 | ielts11_test2_p2 A-03 | subject_span | All the energy and resources that went into the moai - some of which are ten metres tall and weigh over 7,000 kilos - | 补全合理；未超调用边界 |
| gi_v02_359aa6585700 | ielts11_test2_p2 A-09 | subject_span | Modern science – linguistic, archaeological and genetic evidence - | 补全合理；未超调用边界 |
| gi_v02_2238db5890aa | ielts12_test8_p2 A-04 | subject_span | the lynx - a large spotted cat with tasselled ears - | 补全合理；未超调用边界 |
| gi_v02_d8692820c131 | ielts14_test4_p3 L-03 | subject_span | the name of the 'Great Pacific Garbage Patch'—a collection of marine debris in the northern Pacific Ocean— | 补全合理；未超调用边界 |
| gi_v02_f733223cb8ba | ielts18_test2_p3 H-03 | subject_span | the subdivision of the city by function – with services and infrastructures located in the lower levels and wide and well-ventilated boulevards and walkways above for residents – | 补全合理；未超调用边界 |
| gi_v02_b46f95cc9894 | reading_jijing_53_test_83_p2 D-01 | subject_span | Depreciation - the fact that your vehicle loses a large chunk of its resale value each year - | 补全合理；未超调用边界 |
| gi_v02_0ac1b1ca68b4 | reading_jijing_76_test_43_p2 A-04 | subject_span | Romano-British culture – and that included architecture along with language, religion, political organization and the arts – | 补全合理；未超调用边界 |
| gi_v02_f701df0523be | reading_jijing_76_test_43_p2 G-03 | subject_span | The use of prefabricated elements, metal frames, concrete cladding and the absence of decoration – all of which had been embraced by Modernists abroad and viewed with suspicion by the British - | 补全合理；未超调用边界 |
| gi_v02_abf2bfb581ca | ielts11_test1_p3 C-01 | subject_span | The majority of geo-engineering projects so far carried out - which include planting forests in deserts and depositing iron in the ocean to stimulate the growth of algae - | 补全合理；未超调用边界 |
| gi_v02_39d991e3eabf | ielts16_test1_p3 A-02 | subject_span | Automation – or 'embodied artificial intelligence' (AI) – | 补全合理；未超调用边界 |
| gi_v02_b881e1be37a5 | ielts16_test1_p3 F-01 | subject_span | The algorithm – usually built by external designers – | 补全合理；未超调用边界 |
| gi_v02_5591b1466397 | ielts16_test1_p3 F-03 | subject_span | Alternative explorations – where experimentation and human instinct lead to progress and new ideas – | 补全合理；未超调用边界 |
| gi_v02_a1bd7ba7d085 | ielts15_test1_p2 B-06 | subject_span | those who are challenged by existing mobility models – such as older or disabled travellers – | 补全合理；未超调用边界 |
| gi_v02_98c3b84840ee | ielts12_test5_p1 A-01 | subject_span | Cork - the thick bark of the cork oak tree (Quercus suber) - | 补全合理；未超调用边界 |
| gi_v02_a6ccdb342a1e | ielts12_test5_p1 F-03 | subject_span | The tiniest concentrations - as little as three or four parts to a trillion - | 补全合理；未超调用边界 |
| gi_v02_dcfe0e5c59f7 | reading_jijing_44_test_29_p2 B-01 | subject_span | another aquatic floating plant – water lettuce – | 补全合理；未超调用边界 |
| gi_v02_172c121a64fc | ielts11_test4_p1 A-03 | subject_span | Any differences between them - one twin having younger looking skin, for example - | 补全合理；未超调用边界 |
| gi_v02_142b10d88802 | ielts11_test4_p1 C-01 | subject_span | These two lines of research - studying the differences between identical twins to pinpoint the influence of environment, and comparing identical twins with fraternal ones to measure the role of inheritance - | 补全合理；未超调用边界 |
| gi_v02_6388aabec4a8 | ielts10_test1_p1 A-02 | subject_span | the significance of this invention – the stepwell – | 补全合理；未超调用边界 |

## 与要求的差异及未验证范围

19项均完成，没有因无法执行而跳项。实际结果与预期不一致：T5既有允许范围是subject起点至谓语起点，不能确认“全模板不超单个原标签”的字面说法；83新增状态是69/14；“全部正确”不成立；题目残留和新的排印/解释问题见Q1–Q4。旧提交17条/23条与最终18/24的差异已按用户说明核对，不单独算实现缺陷。180字段只指b726提交；整轮247。

第一次生成复用上轮本机验证缓存，并重新解析变化文本；已明确记录，未声称冷解析。两份报告的Python版本差异是用户预期差异。验证器覆盖317/387、70未生成是存量覆盖情况，不把0错误误报为387篇全有解析。XLSX做结构及360行内容只读核对，未进行Excel原生交互点击；本项要求的sheet/盲审/下拉定义已验证。

未进行老师360题全盲审，也没有上线授权。只允许三份文档写入，因此辅助证据和快照仅本机可见；跨机器可据报告中的算法、基线、命令和逐题/逐条位置重建。

## 提交与GitHub CI

报告正文完成后将仅提交三份获准文档，推送codex/grammar-item-candidates；不带skip-ci标记。最终SHA及远端CI结果在提交后补记到本节/交接，并在用户最终回复明确区分test与lint。
