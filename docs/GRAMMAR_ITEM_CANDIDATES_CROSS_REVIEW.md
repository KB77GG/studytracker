# 语法候选题 v0.1 — Claude 交叉审核记录

- 审核对象：`codex/grammar-item-candidates@db7c2de`（实现提交 `2cc9e12`）。
- 依据：`docs/GRAMMAR_ITEM_CANDIDATES_PLAN.md` 第 13 节。
- **更新（2026-10-18）**：用户看过本记录后决定先修复再交老师。v0 抽查表作废，改用 `docs/GRAMMAR_ITEM_CANDIDATES_PLAN_V0_2.md` 生成的 v0.2 抽查表；even if 归为“让步”已获教师确认。
- 原结论：**通过，抽查清单可以交给老师。** 发现的 1 个答案错误和 2 个质量问题正是老师抽查要捕捉的那类问题，不阻断本轮；
  建议等老师反馈回来后，与老师的发现合并成一次 v0.2 修订（见文末）。

## 逐项结果

| # | 检查项（计划第 13 节） | 结果 |
|---|---|---|
| 1 | diff 范围 | 通过。只涉及第 7、9、10 节列出的文件（另有同包内的 `reporting.py`）、ci.yml 一行和交接文档；未改原始标注、图谱、`api/`、`models.py`、`app.py`、`miniprogram/` 或运行时依赖 |
| 2 | 白名单与对照表 | 通过。用脚本把代码常量与计划第 5 节逐表比对，`MAIN_VERB_ROLES` 等 6 个白名单、`RELATION_BY_ROLE`、`ADVERBIAL_CLAUSE_ROLES`、`SUBORDINATOR_RELATIONS` 和歧义引导词全部一致；两条新整句规则的实现与第 6 节定义一致 |
| 3 | 测试 | 通过。云端（Python 3.11）新测试加图谱测试共 39 项全部通过；目标文件 Ruff 通过；GitHub CI [39103643168](https://github.com/KB77GG/studytracker/actions/runs/39103643168) 的 test job 为 success（lint job 失败是仓库既有的存量问题，属于提示性检查） |
| 4 | 云端重跑 | 通过。不使用缓存、在云端从零重新解析全库：`review_batch_v0.jsonl` 和 `review_batch_v0.xlsx` 的 SHA-256 与 Codex 提交的**逐字节一致**；两份报告只有记录 Python 版本的那一行不同（3.11.15 对比 3.13.3），其余逐字节一致；候选题同为 49,564 道，各模板计数完全一致 |
| 5 | 人工抽查 30 题、坏例和正例 | 30 题中 29 题正确（明细见下表）。第 11 节的 6 个坏例和 3 个正例全部符合预期；两条新规则分别命中 36 句和 2 句，与预期一致 |
| 6 | 抽查清单 | 通过。7 个工作表；6 个题型表各 60 行、10 列；“老师判定”列有四项下拉框；表头冻结；没有隐藏行、隐藏列或状态信息（auto_pass / needs_review 只出现在 JSONL 的 `pool_status` 里） |

## 人工抽查明细

抽样方法：从 `review_batch_v0.jsonl` 中 `pool_status = auto_pass` 的题里，每个模板随机抽 5 题，随机种子为 424242。
表中“行”是该题在对应工作表中的序号。

| # | 模板 | 题目编号 | 行 | 判定 |
|---|---|---|---:|---|
| 1 | adverbial_relation | gi_v0_b668249ed6c6 | 39 | 正确（even if → 让步，请老师确认是否认同这个归类） |
| 2 | adverbial_relation | gi_v0_4c972ce0bfc7 | 20 | 正确 |
| 3 | adverbial_relation | gi_v0_079246b7c2a3 | 27 | 正确 |
| 4 | adverbial_relation | gi_v0_78edb489fe98 | 54 | **答案错**：`sought in times of disenchantment when conventional medicine…` 中，when 从句修饰 times，实为关系副词引导的定语从句，题目前提不成立 |
| 5 | adverbial_relation | gi_v0_ed633e95fa2b | 40 | 正确 |
| 6 | clause_boundary | gi_v0_bf3ac7234d6c | 26 | 正确 |
| 7 | clause_boundary | gi_v0_5da65673be3f | 4 | 正确 |
| 8 | clause_boundary | gi_v0_828954cb9539 | 30 | 正确 |
| 9 | clause_boundary | gi_v0_8503e3754299 | 18 | 正确 |
| 10 | clause_boundary | gi_v0_e56468b99087 | 12 | 正确（省略关系词的定语从句 `we encountered in the womb`） |
| 11 | clause_type_classify | gi_v0_3afd54baa862 | 41 | 正确 |
| 12 | clause_type_classify | gi_v0_550fc3850aa2 | 52 | 正确 |
| 13 | clause_type_classify | gi_v0_ad568e381d6a | 30 | 正确 |
| 14 | clause_type_classify | gi_v0_43dfdddcacd8 | 28 | 正确 |
| 15 | clause_type_classify | gi_v0_7109415f803c | 31 | 正确 |
| 16 | finite_or_not | gi_v0_f49186782445 | 42 | 正确 |
| 17 | finite_or_not | gi_v0_a36761f881be | 37 | 正确，但**展示有问题**：从句谓语是 `was born`，题目只标出 `born`，学生容易误判为分词（非谓语） |
| 18 | finite_or_not | gi_v0_d86f86c832e8 | 16 | 正确 |
| 19 | finite_or_not | gi_v0_e81311386323 | 13 | 正确 |
| 20 | finite_or_not | gi_v0_6f5ac096a75b | 38 | 正确，但**原句有问题**：两个句子粘连（`…"loss aversion."For instance…`），属于分句错误 |
| 21 | main_verb_tap | gi_v0_eb1d7f02e003 | 57 | 正确 |
| 22 | main_verb_tap | gi_v0_86fa0423e3d4 | 52 | 正确 |
| 23 | main_verb_tap | gi_v0_4f9a38b8488f | 27 | 正确 |
| 24 | main_verb_tap | gi_v0_bfa726fc479f | 36 | 正确 |
| 25 | main_verb_tap | gi_v0_7fd67ea5dd54 | 1 | 正确 |
| 26 | subject_span | gi_v0_d39c4ea6e6fb | 12 | 正确 |
| 27 | subject_span | gi_v0_971809de8b05 | 13 | 正确 |
| 28 | subject_span | gi_v0_468a89e14224 | 47 | 正确 |
| 29 | subject_span | gi_v0_f65387f83520 | 53 | 正确 |
| 30 | subject_span | gi_v0_85272cdd16e7 | 2 | 正确 |

## 建议的 v0.2 修订

等老师反馈后与老师的发现合并成一次修订，本轮不做：

1. **新增整句过滤 `glued_sentence_boundary`。** 原句中出现“小写字母 + 句末标点 + 可选引号 + 大写字母开头的单词”且中间没有空格，说明是两句粘连。
   正则示例：`[a-z][.!?]["”’']?[A-Z][a-z]`。全库命中 23 句，全部来自机经（reading_jijing）。
2. **finite_or_not 的目标改为高亮整个动词单位。** 判断的仍是中心动词，但对限定动词要连同助动词一起标出（如 `was born`），避免看起来像分词。
3. **状语从句的关系副词风险。** 引导词是 when / where，且从句紧跟在名词后面（如 times when、place where）时，标为 `needs_review/possible_relative_adverb`。
   具体条件和命中数要先在全库实测，再写进计划。
4. **请老师确认 even if 归为“让步”**（目前按计划的对照表处理）。

## 云端复现环境

spaCy 3.8.16、en_core_web_trf 3.8.0、torch 2.14.1（CPU）、Python 3.11.15、openpyxl 3.1.5、Flask 3.1.3。
该环境只存在于本次云端会话的容器里，不长期保留；复现命令与 Codex 交接中的相同。
