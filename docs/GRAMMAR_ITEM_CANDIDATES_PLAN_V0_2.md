# 语法候选题 v0.2 — 增量执行计划（含阅读原文修复）

> 执行方：Codex（用户的 Mac）。交叉审核：Claude（云端会话）。
> 本计划只写**相对 v0.1 的变化**。没提到的部分一律沿用 `docs/GRAMMAR_ITEM_CANDIDATES_PLAN.md`（v0.1），两份冲突时以本计划为准。
> 规则不变：没写的不要做；写了但做不到的，停下来汇报，不要自行变通。

## 0. 为什么有 v0.2

用户看过 Claude 的交叉审核记录（`docs/GRAMMAR_ITEM_CANDIDATES_CROSS_REVIEW.md`）后做了 4 个决定：

1. **even if 归为“让步”**：教师确认，对照表不变。
2. **两句粘连的原句要重新做**：修复原文，把粘连的句子重新拆开、重新标注。不能只在出题时跳过。（第 A 部分）
3. **“times … when …”这类误判要改掉**：when / where / why 从句紧跟名词时，可能是定语从句，不能自动通过。（第 B2 节）
4. **“was born 只高亮 born”这类问题全部修改**：凡是高亮动词的地方，都要标出完整的动词单位。（第 B3 节）

**v0 的抽查表作废，不要交给老师。** 本轮生成 v0.2 抽查表替代它。

## 1. 授权与边界（相对 v0.1 的变化）

- 分支不变：`codex/grammar-item-candidates`。开工先执行
  `git fetch origin claude/word-memorization-system-eval-55v2y5 && git merge --ff-only origin/claude/word-memorization-system-eval-55v2y5`。
  只推这个分支；禁止推 main、部署、开 PR。
- **本轮新增授权（仅限下列范围）：**
  - 修改 `data/reading_study/` 中第 A 节表格列出的 28 句，以及因拆句而需要重排 `sentence_index` 的同文件其他句子（只改 `sentence_index`，其他字段不动）；
  - 通过修订表修改 `static/reading_jijing/` 中这些句子所在段落的原文；
  - 在 `scripts/build_reading_test_practice.py` 的机经构建路径里加入应用修订表的一步。
- **仍然禁止：**
  - 修改 `data/idictation_reading_jijing/raw.json`（这是原始下载数据，保持原样）；
  - 改动表格以外的任何句子或段落，或改动官方剑雅原文（`static/reading_tests/`）；
  - 改动 `api/`、`models.py`、`app.py`、`miniprogram/`；
  - 任何生产服务器操作，包括导入 Reading Study 数据库。
- 线上生效需要另行授权（本轮不做）：合并 main 并部署后，在服务器先备份数据库，再运行 `scripts/import_reading_study.py`。
  这些步骤写进交接文档的“待办”，不执行。

## A. 阅读原文与句子解析修复

### A1. 修复清单（28 句，共 30 处）

问题出在**原文段落本身缺空格**，阅读解析的句子又必须逐字等于原文（`validate_reading_study.py` 要求同段句子用单个空格拼接后与原段落一致）。
所以要先修原文，再修句子。清单由 Claude 从当前数据自动导出：

| # | passage_id | 句子 | 处理 | 粘连处 |
|---:|---|---|---|---|
| 1 | `reading_jijing_10_test_78_p3` | E-04 | 拆句 | `uch as these."Manufact` |
| 2 | `reading_jijing_10_test_78_p3` | P-01 | 拆句 | `tive objects."The popp` |
| 3 | `reading_jijing_14_test_23_p1` | G-02 | 拆句 | `me estimates.'The rock` |
| 4 | `reading_jijing_14_test_23_p3` | H-01 | 拆句 | `e with Susie.'Whilst I` |
| 5 | `reading_jijing_16_test_97_p2` | B-09 | 拆句 | `t of control."Being "t` |
| 6 | `reading_jijing_16_test_97_p2` | F-36 | 拆句；单元内已有空格的句界（如 `ourselves. I'll`）也要拆开 | `ng to happen.I've put` |
| 7 | `reading_jijing_18_test_53_p2` | E-01 | 拆句 | `t on schools.'Uniquely` / `ht,' he said.'When it ` |
| 8 | `reading_jijing_23_test_46_p1` | B-04 | 拆句 | `rior to that.'Some sci` |
| 9 | `reading_jijing_24_test_56_p1` | D-01 | 拆句 | `oilier areas.'Dogs act` |
| 10 | `reading_jijing_38_test_22_p1` | E-03 | 拆句 | `people worse.'Interest` |
| 11 | `reading_jijing_44_test_29_p1` | H-03 | 拆句 | ` that clear).Gregor's` |
| 12 | `reading_jijing_46_test_84_p1` | B-09 | 拆句 | `ture of Asia.Thailand` |
| 13 | `reading_jijing_53_test_83_p2` | B-03 | 拆句 | `of transport."I'm 47 a` |
| 14 | `reading_jijing_56_test_64_p2` | G-03 | 拆句；另改错字 `t his` → `this` | ` be the case.The culp` |
| 15 | `reading_jijing_65_test_69_p1` | I-03 | 拆句 | `portant role.'All musi` |
| 16 | `reading_jijing_71_test_1_p2` | E-01 | 拆句；另补空格 `',translates` → `', translates` | `Card Player'.'Scopone'` |
| 17 | `reading_jijing_71_test_1_p3` | A-01 | 只改错字：`meteorologist,.Alfred` → `meteorologist, Alfred`（一句话，不拆） | `teorologist,.Alfred W` |
| 18 | `reading_jijing_73_test_5_p1` | H-01 | 拆句 | `4°C at night.'You coul` |
| 19 | `reading_jijing_76_test_43_p2` | E-04 | 拆句 | `g techniques.Morris's` |
| 20 | `reading_jijing_78_test_102_p2` | G-01 | 拆句 | `or teaspoons.Today's ` |
| 21 | `reading_jijing_78_test_102_p3` | E-03 | 拆句 | `arating them."When we ` |
| 22 | `reading_jijing_82_test_4_p1` | F-04 | 拆句 | `latex rubber.Ford's f` |
| 23 | `reading_jijing_83_test_95_p1` | G-08 | 只补空格：`?"Pepperberg` → `?" Pepperberg`（一句话，不拆） | `'s different?"Pepperbe` |
| 24 | `reading_jijing_85_test_12_p1` | C-05 | 拆句；另补空格 `that,"he` → `that," he` | `hat,"he says."It offer` / ` money in it."Peter lo` |
| 25 | `reading_jijing_88_test_98_p2` | D-02 | 拆句 | `e they don't.The bias` |
| 26 | `reading_jijing_88_test_98_p2` | G-04 | 拆句 | `oss aversion."For inst` |
| 27 | `reading_jijing_88_test_98_p3` | D-10 | 拆句 | `s into cards.That's w` |
| 28 | `reading_jijing_91_test_49_p1` | F-07 | 拆句 | `nto our fuel."After th` |

**允许的原文改动只有以下几种，且仅限表中位置：**

1. 在每个粘连处补一个空格；
2. 表中写明的 4 处错字或缺空格修正（`t his`、`that,"he`、`',translates`、`meteorologist,.Alfred`）。

其余文字（包括原文本身的语法问题）一律保持原样，保证与原题一致。
发现表外还有同类问题时，记进汇报，不要改。

### A2. 修订表与构建脚本

- 新增 `data/reading_jijing_text_fixes.json`，每处修改一条：

  ```json
  {"passage_id": "...", "paragraph_label": "E", "sentence_id": "E-04", "find": "...", "replace": "...", "reason": "missing_space_between_sentences"}
  ```

  `reason` 取 `missing_space_between_sentences` / `missing_space` / `typo`。
- `find` 在该段落中必须**恰好出现一次**。已经修好的段落（`find` 不在、`replace` 在）视为已应用，跳过不报错。
  其他情况（`find` 不在且 `replace` 也不在，或 `find` 出现多次）一律报错退出。
- 在 `build_reading_test_practice.py` 的机经构建路径中，已知 passage_id、写出文件之前应用修订表。
  这样以后从 raw 重建，修复也不会丢。
- 用同一个函数原地修补现有的 `static/reading_jijing/*.json`（可以写一个小脚本 `scripts/apply_reading_jijing_text_fixes.py`）。
  **JSON 的缩进、键顺序、转义方式必须与原文件一致**，`git diff` 只能出现这些段落文字的变化。
- 新增 `tests/test_reading_jijing_text_fixes.py`（纯标准库），加入 CI 轻量测试列表。覆盖四种情况：
  恰好一次 → 替换；已应用 → 跳过；找不到 → 报错；多次出现 → 报错。

### A3. 重新拆句与标注（`data/reading_study/`）

- **拆句规则**：
  - 表中 26 个“拆句”单元，在每个句界处拆开。单元内已有空格的句界也要拆（如 F-36 里的 `ourselves. I'll`）。
  - **例外**：引语和紧跟它的引述部分保持为一句。例如 `'All music has a message.' he says.` 不拆成两句。
  - 2 个“只补空格 / 只改错字”的单元不拆句，只改句子文字和受影响的 `structure[].text`。
- **ID 规则**：拆出的第一句**沿用原 ID**，其后依次为 `<原ID>b`、`<原ID>c`……（例如 `E-04`、`E-04b`）。
  同文件的 `sentence_index` 从 1 起重新连续编号；`paragraph_label` 不变。这样学生已收藏表达里记录的句子 ID 仍然指向原来的位置。
- **重新标注**：对这 28 个单元产生的每一句，按 `docs/reading_study_generation_standard.md` 重新写
  `translation`、`structure`、`difficult_points`、`expressions`。
  - 由你直接撰写，不调用任何大模型 API。
  - `structure` 的 role 在语法上准确的前提下，优先使用 v0.1 第 5 节白名单里的 role。
- **其他句子必须逐字节不变**：除 `sentence_index` 外，任何字段都不能改。用脚本对比修改前后的文件并在汇报里给出结果。
- `scripts/validate_reading_study.py` 对全部 317 个文件必须通过。
- 新增 `docs/READING_STUDY_RESPLIT_2026-10.md`，逐单元列出：原句、新句及其 ID、改了哪些原文字符。
  这份文件供 Claude 和老师核对。

## B. 出题器 v0.2

### B1. 新增两条整句过滤

| 原因码 | 条件（正则按 Python `re` 写） |
|---|---|
| `glued_sentence_boundary` | 原句匹配 `(?<=\S)[.!?]["”’')\]]?(?=[A-Z])`。排除首字母缩写：命中位置前 4 个字符到命中后 1 个字符的片段匹配 `\b(?:[A-Z]\.)+[A-Z]$` 时不算。修复前全库命中 28 句，即 A1 表；**A 部分完成后应为 0**，这条规则作为以后的防线 |
| `multi_sentence_unit` | 原句匹配 `[a-z0-9][.!?]["”’')\]]?\s+["“‘'(]?[A-Z]`。排除常见缩写：命中位置前 6 个字符到命中末尾的片段匹配 `\b(Mr\|Mrs\|Ms\|Dr\|St\|Prof\|Jr\|Sr\|No\|Co\|Inc\|Ltd\|vs\|etc\|U\.S\|U\.K\|e\.g\|i\.e\|a\.m\|p\.m)[.!?]["”’')\]]?\s+[A-Z]$` 时不算。修复前全库命中 51 句（多为引语连着下一句，少数是 `Mt. Cook` 之类误伤）。本轮只在出题时排除，**不修改这些原文**；报告里逐句列出 |

（表中 `\|` 是 Markdown 转义，代码里写 `|`。）

### B2. 关系副词风险 `possible_relative_adverb`

- 适用于以白名单状语从句为目标的题：T2（状语从句边界）、T3（标注答案为“状语从句”时）、T4。
- 条件：从句第一个词（小写、去掉逗号）∈ {when, where, why}，且从句前最近的一个非标点 token 的 pos ∈ {NOUN, PROPN, NUM}。
- 命中 → 该题一律 `needs_review`，原因码 `possible_relative_adverb`。即使其他复核都通过也一样。
- Claude 实测：当前数据中 when / where / why 引导的白名单状语从句共 409 个，命中 81 + 38 = 119 个
  （紧挨名词 81 个，中间有逗号 38 个）。报告里给出各模板受影响的题数。
- 不要改成只对 time、century 等时间名词生效：原错例 `times of disenchantment when` 中，紧挨 when 的是 disenchantment，那样会漏掉它。

### B3. 动词高亮必须是完整动词单位

- **定义**：动词单位 = 中心动词，加上它 dep ∈ {aux, auxpass, neg, prt} 的子节点。不定式的 `to`（aux / TO）包括在内。
- **T6**：三类目标都改为高亮动词单位。
  - `target.start/end/text` 覆盖动词单位的第一个到最后一个 token；
  - 新增 `target.parts`，列出每段连续 token 的字符 span；
  - 抽查表的“句子”列对每一段分别加【】。例如 `【has】 also 【identified】`，连续的合并成一段，如 `【was born】`。
- **T1**：答案已是动词单位，不变；`distractors` 也改为动词单位，并带 `parts`。
- 判断的依据仍是中心动词，选项和答案不变。
- 逐一检查其余模板中是否还有“只显示动词单位的一部分”的情况，在汇报里写明检查结果。

### B4. 版本与输出

- `generator_version` 改为 `grammar-items-v0.2`；输出文件改名为 `*_v0_2.*`。
- **删除 v0 的 4 份交付**（git 历史可查），避免有人误用旧抽查表。
- 抽查表规格不变（v0.1 第 8 节），种子仍为 `20261018`。
- 报告新增：
  - 两条新整句规则和 `possible_relative_adverb` 的命中数及逐句列表；
  - A 部分的拆句统计：修复前后的句子总数、新增句子 ID。

### B5. 新增回归例句（报告逐句列出结果）

| 句子 | 预期 |
|---|---|
| `ielts4_test2_p2` G-31 `…sought in times of disenchantment when conventional medicine…` | 以 when 从句为目标的 T2 / T3 / T4 题均为 `needs_review/possible_relative_adverb` |
| `ielts6_test3_p1` C-06 `That was the moment when cinema was born.` | T6 以 born 为中心的题，`target.text` 为 `was born` |
| `reading_jijing_88_test_98_p2` G-04 | 已拆成两句；全库 `glued_sentence_boundary` 命中 0 句 |
| v0.1 第 11 节的全部例句 | 结果与 v0.1 预期一致（C-04、H-02 的动词目标现在显示完整动词单位） |

## C. 测试、验收与汇报

- v0.1 第 10 节的测试继续有效，另外新增：
  - 两条新整句规则：命中和不命中各至少一例，`Mt. Cook` 这类缩写按上表规则处理；
  - `possible_relative_adverb`：命中、不命中（如 `…, he left when it rained` 中 when 前是动词）；
  - 动词单位：连续（was born）、不连续（has also identified）、不定式（to introduce）。
  - A2 的修订表测试。
- 全量生成两次，提交的 4 份 v0.2 文件逐字节一致。
- 汇报：在 v0.1 第 12 节要求之外再加：
  - A 部分的修复前后对比结果（其他句子逐字节不变的证明、validator 结果）；
  - `static/reading_jijing/` 的 diff 统计；
  - B1、B2 的命中数。

## D. Claude 交叉审核会检查

1. diff 范围符合第 1 节授权：raw.json、官方原文和表外句子都没动。
2. 28 个单元逐一核对拆句、ID 和新标注，并抽查翻译和 structure 的质量。
3. 在云端重跑：validator、测试、全量生成，4 份文件逐字节一致（报告中 Python 版本一行除外）。
4. B5 回归例句全部符合预期；再从 v0.2 抽查表的 auto_pass 中人工核对 30 题。
5. 抽查表仍是盲审，T6 的高亮是完整动词单位。
