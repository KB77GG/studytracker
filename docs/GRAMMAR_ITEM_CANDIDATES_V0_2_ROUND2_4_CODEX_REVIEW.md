# 语法候选题 v0.2 第二、三、四轮 — Codex 独立复审记录

日期：2026-10-20（Asia/Shanghai）。审核对象：`f9aebc7..1f03c846c192d939ade43a5902204cb1bea6f9a5`。

## 结论：不通过（验收未完成，等待确认检查口径）

这不是对三轮实现质量作出的“不通过”结论。本轮在检查清单第13项遇到客观无法满足的数量要求，依用户“遇到做不到的检查，停下来如实写明原因，不要变通”停止。**代码/数据问题的阻断和应修数量尚未评定，不能理解为零问题。** 第一轮修复的独立复审已经完成，记录保持在 `GRAMMAR_ITEM_CANDIDATES_V0_2_FIXES_CODEX_REVIEW.md`，本次没有重复审核第一轮。

### 验收阻塞 B0：多数低频 role 无法提供两个独立语料实例

- 要求位置：用户本轮清单第13项，“逐条判断……72个role的新标签是否正确，至少逐个看每个role在语料中的2个例子”。
- 实际证据：以f9aebc7的resolver与1f03c84的resolver处理**同一份1f03c84全语料**，当前有71个role、403处标注的结果发生变化。其中38个role各仅有1处标注，无法从这份语料取得第二例。72/407是第三轮记录的历史数量，当前数量差异尚未逐项追踪，不能凭此断言实现有回归。
- 例如 `exclamatory_clause` 只有 `ielts17_test1_p3 A-02` 的 `what a story it is`；`for_to_infinitive_clause` 只有 `ielts17_test1_p2 E-03`。重复同一例、将同一句旧版本当第二例、另造句子，都不能满足“两个语料例子”，本轮未这样变通。
- 已向用户提出口径确认：**少于2例的role，是否审核全部现有例子并单独列数量限制；其余检查保持不变**。尚未收到该确认，因此后续检查未继续。
- 建议处理：确认上述合理例外，或提供缺少的第二个真实语料实例后继续。这个阻塞是检查要求与语料数量不相容，不是程序bug。

| 当前仅1例的role | 唯一实例 |
|---|---|
| alternative_question_clause | reading_jijing_40_test_75_p2 B-03 |
| alternative_reason_clause | reading_jijing_62_test_44_p3 F-02 |
| alternative_result_clause | reading_jijing_48_test_21_p1 E-05 |
| comma_splice_clause | reading_jijing_50_test_30_p2 F-03 |
| comma_spliced_clause | reading_jijing_11_test_103_p2 A-02 |
| counterfactual_condition_clause | reading_jijing_78_test_102_p1 B-03 |
| elliptical_comment_clause | reading_jijing_44_test_29_p2 E-04 |
| elliptical_comparative_clause | ielts13_test3_p3 E-03 |
| elliptical_disclaimer_clause | reading_jijing_53_test_83_p2 E-05 |
| elliptical_passive_clause | reading_jijing_44_test_29_p1 B-04 |
| exception_condition_clause | reading_jijing_78_test_102_p1 E-03 |
| exclamatory_clause | ielts17_test1_p3 A-02 |
| fact_clause | ielts5_test4_p2 I-35 |
| first_result_clause | reading_jijing_48_test_21_p1 E-05 |
| for_to_infinitive_clause | ielts17_test1_p2 E-03 |
| fragmented_time_clause | reading_jijing_62_test_44_p2 B-05 |
| hypothetical_conditional_clause | reading_jijing_73_test_5_p2 F-03 |
| infinitive_result_clause | ielts18_test3_p3 D-02 |
| interrogative_infinitive_clause | ielts5_test2_p3 A-03 |
| inversion_clause | ielts15_test1_p3 E-01 |
| malformed_condition_clause | reading_jijing_11_test_103_p2 F-05 |
| non_finite_passive_clause | ielts12_test7_p3 F-05 |
| parenthetical_concessive_clause | reading_jijing_46_test_84_p3 K-08 |
| parenthetical_time_clause | ielts9_test2_p2 F-06 |
| participial_clause | ielts20_test3_p3 A-01 |
| predicate_with_reason_clause | reading_jijing_23_test_46_p1 E-05 |
| prepositional_clause | ielts5_test1_p2 I-01 |
| prepositional_participial_clause | ielts19_test4_p2 D-02 |
| question_clause | ielts20_test3_p2 C-05 |
| reduced_condition_clause | reading_jijing_78_test_102_p3 G-03 |
| reduced_manner_clause | ielts7_test4_p3 C-07 |
| run_on_clause | reading_jijing_44_test_29_p1 I-04 |
| second_clause | reading_jijing_56_test_64_p1 B-08 |
| second_interrogative_clause | reading_jijing_23_test_46_p1 C-05 |
| standalone_time_clause | reading_jijing_76_test_43_p3 C-02 |
| supplementary_participle_clause | reading_jijing_71_test_1_p3 B-06 |
| temporal_causal_clause | ielts13_test4_p2 D-01 |
| third_interrogative_clause | reading_jijing_23_test_46_p1 C-05 |

## Git、授权范围及执行状态

- 执行工作树：`/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker`，分支 `codex/grammar-item-candidates`。开工前已读取目录链AGENTS、CLAUDE、交接和WORKLOG，并核对Git；原HEAD为第一轮复审最后提交 `eca7404592a5c76329e4a4594befb1a042e8d952`，工作区干净。
- 按用户指定fetch后合并 **1f03c846c192d939ade43a5902204cb1bea6f9a5**。仅CODEX_HANDOFF和WORKLOG发生冲突，两边记录保留；没有rebase，没有合并main。
- 合并提交 **1cdc4e5eeac7eef3c9562282306679abd6510af1**。该合并相对于1f03c84只多出第一轮审核记录及两份交接差异；被审核代码/数据与1f03c84一致。
- 原桌面项目 `/Users/zhouxin/Desktop/studytracker` 未写入；既有main工作和脏文件未覆盖。
- 本轮只新增本记录并更新两份交接。没有修复被审核代码/数据，没有推main、部署、PR、生产服务器/数据库操作或大模型API调用。
- 临时目录：`/tmp/studytracker-grammar-round2-4-audit.H4JlOk`。原样提交副本、测试日志、角色计数JSON及未完成的解析缓存只在本机。

## 21项进度，不能视为完成的审核表

| # | 实际结果与未完成部分 |
|---:|---|
| 1 | 已运行stat：197 files、12,420 insertions /4,729 deletions；已读主要Python/CI diff。尚未完成逐文件授权范围核对。 |
| 2 | 指定保护路径diff为空；api只改reading_study_glossary.py。IELTS各轮字段变化尚未逐项核对。 |
| 3 | 已读ROUND2/ROUND3部分逐句说明，未完成全部60条独立上下文核查，不能照抄自查为通过。 |
| 4 | 未完成548条及追加2条逐条审核。 |
| 5 | 未进行独立漏网检索和过时说明清点。 |
| 6 | `--check`输出0，exit0；find/replace及at_end全表不变量尚未独立遍历。 |
| 7 | 已读修补脚本及构建脚本diff；反例、全库词边界和独立幂等验证未完成。 |
| 8 | 未完成groups逐字符串比较、50处抽查和未带questions条目漏网检查。 |
| 9 | 未重建171篇，也未完成控制字符/CO全量检查。 |
| 10 | validator运行exit0，当前317文件全部OK；输出Coverage 317/387 ready、70 missing。句数、对象字节、格式、ID等独立结构核对未完成。 |
| 11 | 未完成全部指定句子的translation/structure/difficult_points/expressions逐句审核。 |
| 12 | 未完成分类合理性审核。 |
| 13 | 已对当前全库role比较旧新resolver，发现B0；未完成逐role语义审核、未知role和Python3.10兼容验证。 |
| 14 | 尚未独立核对导入时标签持久化流程。 |
| 15 | 已读checks.py修改；反例及全库漏网检查未完成。 |
| 16 | 已读templates.py修改；数量反事实验证、各组抽样、新测试在旧代码上的失败验证未完成。 |
| 17 | 尚未从独立完整生成核对报告预期值。 |
| 18 | 四个指定模块85项测试通过。首次冷缓存生成已启动，遇B0后暂停并结束（exit130）；最后进度为125篇/4875句。未产生完成版交付，未双跑、未计算交付SHA；Flask-only、Node、reading_study22项、Ruff、图谱重生成均未执行。 |
| 19 | 未执行main完整快照→当前版本的临时SQLite模拟导入。 |
| 20 | 未开始五组题目抽样，不提供空缺的明细冒充完成。 |
| 21 | 本轮尚未检查xlsx；不得沿用上一轮的表格检查结论。 |

## 实际运行命令及证据

工作目录为上述任务树；临时路径简称 `$AUDIT`。主要执行命令：

```sh
git status --short --branch
git log -5 --oneline
git fetch origin claude/word-memorization-system-eval-55v2y5
git merge --no-edit 1f03c846c192d939ade43a5902204cb1bea6f9a5
# 仅手工合并两份交接，保留双方内容；随后提交合并
git add docs/CODEX_HANDOFF.md docs/WORKLOG.md
git commit -m "merge: integrate grammar rounds two through four for independent review"
git diff --name-only 1f03c84..HEAD
git diff --shortstat f9aebc7..1f03c84
git diff f9aebc7..1f03c84 -- data/idictation_reading_jijing/raw.json static/reading_tests/ models.py app.py miniprogram/ .github/workflows/deploy.yml
git diff --name-only f9aebc7..1f03c84 -- api/

AUDIT=/tmp/studytracker-grammar-round2-4-audit.H4JlOk
git archive 1f03c84 | tar -x -C "$AUDIT/source"
PYTHONDONTWRITEBYTECODE=1 .venv-grammar-tools/bin/python "$AUDIT/source/scripts/generate_grammar_candidates.py" --seed 20261018
# 上述首次生成因B0主动结束，exit130，不是生成器异常，也不是已完成验证
.venv-grammar-tools/bin/python -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary tests.test_grammar_graph_draft -v
.venv-grammar-tools/bin/python scripts/validate_reading_study.py
.venv-grammar-tools/bin/python scripts/reading_jijing_text_fixes.py --check
```

角色数量的只读独立复现代码（f9aebc7与当前函数作用于同一当前语料；不修改模块）：

```python
import collections, json, subprocess
from pathlib import Path
from api.reading_study_glossary import resolve_role

old = {}
exec(subprocess.check_output(
    ['git', 'show', 'f9aebc7:api/reading_study_glossary.py'], text=True
), old)
roles = collections.defaultdict(list)
for path in sorted(Path('data/reading_study').glob('*.json')):
    for sentence in json.loads(path.read_text())['sentences']:
        for span in sentence['structure']:
            role = span.get('role', '')
            if old['resolve_role'](role) != resolve_role(role):
                roles[role].append((path.stem, sentence['id'], span.get('text')))
print(len(roles), sum(map(len, roles.values())))  # 71, 403
print(sum(len(examples) < 2 for examples in roles.values()))  # 38
```

日志：`unit.log`（85 ran，OK）、`validator.log`（exit0）、`textcheck.log`（0未应用）、`roles-changed.json`（全部71个role的来源）、`generate-first.log`（未完成生成）。当前工具环境沿用任务树 `.venv-grammar-tools`；本轮未重新核对全部依赖版本，**没有双次交付SHA可报告**。

## 提交、CI及继续条件

待本记录和交接提交推送后补记CI。只推 `codex/grammar-item-candidates`，不带skip标记。CI测试成功也不能补足上述未完成的语言内容审核。

下一步须先由用户确认B0的例数口径。若确认“不足2例审核所有现有例子”，就在1f03c84不变的代码/数据上继续其余检查，将本临时阻塞记录更新为完整审核；不能自行假定用户同意。首次生成可重新冷启动，或明确记录复用已生成解析缓存，不能把中断这次记作一次完整生成。
