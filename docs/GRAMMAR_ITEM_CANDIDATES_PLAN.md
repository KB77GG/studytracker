# 语法候选题生成与抽查清单 — 执行计划（v0.1）

> 执行方：Codex（用户的 Mac）。交叉审核：Claude（云端会话）。
> 本计划是验收标准：没写的不要做；写了但做不到的，停下来在汇报里说明，不要自行变通。

## 修订记录

- **v0.1（2026-10-18）**：Codex 用指定解析器实测后发现，v0 第 11 节“坏例在任何模板都不得自动通过”与第 4、6 节冲突。
  C-04、H-02 的错误只在某一个 span 上，同句其他 span 出的题其实是对的；C-01 是原句残缺，但现有整句过滤拦不住。修订内容：
  1. 第 6 节写明整句过滤与单题失败的边界：**单题失败不传播到同句其他模板**。
  2. 第 6 节新增两条整句过滤：`tagged_fragment`、`clause_attached_to_conjunction`。
  3. 第 11 节改为逐句、逐模板写明预期结果。
  4. 第 7.2、10、13 节相应补充。
  - 两条新规则已由 Claude 在云端用同版本模型（spaCy 3.8.16 + en_core_web_trf 3.8.0 + torch 2.14.1，CPU）对全部 12,657 句实测：
    `tagged_fragment` 命中 36 句，`clause_attached_to_conjunction` 命中 2 句（C-01 和 `ielts13_test2_p2` C-04）。
    云端（Python 3.11）的 6 个例句解析结果与 Codex 在 Mac 上（Python 3.13）的结果一致。
  - 实测中放弃的两种写法：按标注判断“并列分句以 and/but + 从属连词开头”会误伤 36 个正常句；
    按解析器判断“并列分句里没有自己的主句谓语”会命中 105 句，大多是正常句。**不要采用这两种写法。**
- 继续在 `codex/grammar-item-candidates` 上工作：先 `git merge --ff-only origin/claude/word-memorization-system-eval-55v2y5`
  （该分支已包含你的两个提交，应能直接快进），再从第 9 节开始实施。

## 0. 目标

从 `data/reading_study/` 的雅思真题句子标注中，为语法图谱第一阶段的 11 个知识点（G-S01、G-S02、G-C02、G-C03、G-C04、G-C08、G-C10、G-C11、G-N01、G-N04、G-L01）批量生成**候选题**（第 1 步），
用一套独立的语法分析器逐题复核、过滤（第 2 步），最后输出一份给老师的**抽查清单**。

本轮**不入库、不上线、不做界面**。产出只是“候选题池 + 统计报告 + 抽查清单”。

背景：Claude 抽查 30 个复杂句发现，从句边界标注很可靠，但约 1/10 的句子有影响答案的错误，
约 1/4 的谓语标注把宾语也划了进去。所以机器出的题不能直接给学生，必须经过本计划的过滤和老师抽查。

## 1. 开工前必读

1. `CLAUDE.md`（工程硬规则）、`docs/CODEX_HANDOFF.md`、`docs/WORKLOG.md` 最新一节。
2. `docs/GRAMMAR_GRAPH_V0_REVIEW.md` 和 `data/grammar_graph/grammar_graph_v0.json`：知识点 ID 以 JSON 为准。
3. `docs/reading_study_generation_standard.md`：标注格式。`structure[]` 的每个 `text` 都是原句中的连续片段，`level` 1 为主干。
4. `api/reading_study_glossary.py`：`resolve_role()` 把原始 `role` 归一成概念。
   **注意：归一后的 `adverbial_clause` 是兜底桶**，`imperative_clause`、`interrogative_clause`、`nominal_clause`、
   `clause` 等都会掉进去。所以本计划选题目标时一律按**原始 role 白名单**（第 5 节），不按归一概念。

## 2. 授权与边界

- **分支**：从 `origin/claude/word-memorization-system-eval-55v2y5` 切出 `codex/grammar-item-candidates`，所有提交只推到这个分支。
- **用户已授权**：在该分支上 commit 并 push（为了让 Claude 交叉审核）。**禁止**推 `main`、禁止部署、禁止开 PR。
- **只读**：`data/reading_study/*`、`data/grammar_graph/grammar_graph_v0.json`、`api/`、`models.py`、`app.py`、`miniprogram/`。
  如果认为图谱或标注需要改，写进汇报，不要动。
- **不做**：数据库表或 schema、接口或蓝图、前端界面、小程序、生产服务器上的任何操作、调用任何大模型 API。
- 本工具只在本机离线运行，**不得**装到生产服务器（生产机禁止跑本地重模型）。

## 3. 环境

- 新建独立虚拟环境 `.venv-grammar-tools/`（加进 `.gitignore`），不要装进主 `.venv`。
- 新增 `requirements-grammar-tools.txt`，**精确固定版本**：`spacy==<实际安装的 3.8.x>`、
  `en_core_web_trf`（用官方 3.8.0 wheel 的 URL 固定）、`Flask`（导入 `api.reading_study_glossary` 需要）、`openpyxl`。
- **不得**把 spaCy 或模型加进 `requirements.txt` / `requirements-dev.txt`。
- 解析器只用 `en_core_web_trf`，并强制 CPU（`spacy.require_cpu()`），保证结果可复现。
  装不上 trf 就停下来汇报，**不要换成 sm/lg 或其他模型**。Python 优先用 3.13；3.13 装不上时可用 3.12 建工具环境，并在报告里写明。

## 4. 题型模板（6 个）

总规则：

- **答案来自标注**，解析器只用来复核；只有 T1 和 T6 借解析器把“哪个词”定位准确。
- 标注和解析器一致 → `auto_pass`；生成了但不一致或有歧义 → `needs_review`；被过滤掉 → `rejected`，
  并写原因码（第 6 节）。
- 比较边界时，两端的标点和空白都去掉，比较 token 边界，不比较字符串。
- 所有位置用原句 `sentence` 的字符偏移 `[start, end)` 存储；token 下标只放在 `evidence` 里。
- 下文的 dep 标签是 spaCy 英文模型的标签。注意 spaCy 把系动词当作中心词，例如 `is` 本身就是 ROOT。

### T1 `main_verb_tap` — 点出主句谓语（G-L01；句中没有干扰动词时记为 G-S01）

- **选句**：第 1 层恰好有一个谓语类 span（原始 role 属于 `MAIN_VERB_ROLES`）；第 1 层没有并列类谓语或并列分句
  （`COORDINATED_PREDICATE_ROLES`、`COORDINATE_CLAUSE_ROLES`）。
- **答案**：解析器 ROOT 必须是 VERB/AUX，且落在该标注 span 内。动词单位 = ROOT 加上它在 span 内、dep ∈
  {aux, auxpass, neg, prt} 的子节点。
- **干扰项**：位于第 2 层及以上白名单从句或非谓语 span 内的 VERB/AUX，并记录各自所在 span 的 role。
  记为 G-L01 时至少要有 1 个干扰项。
- **复核**：ROOT 不在标注谓语 span 内 → `needs_review/parser_root_outside_verb_span`；
  ROOT 落在某个从句 span 内 → `needs_review/parser_root_inside_subordinate_span`；
  ROOT 有 conj 子节点且该子节点是动词 → `rejected/coordinated_main_verbs`。
- **判分规则**（写进题目的 `grading` 字段，供以后的界面用）：学生选中的词必须包含 ROOT，且全部属于动词单位。
- 题干：`点出这句话的主句谓语动词。`

### T2 `clause_boundary` — 划出从句（G-C04 定语 / G-C08 名词性 / G-C10 状语 / G-C02 并列分句）

- **选句**：目标 span 的原始 role 属于对应白名单；同一句中同类型白名单 span 只有 1 个
  （否则 `rejected/multiple_targets_same_type`）。
- **答案**：目标 span（去掉两端标点）。并列分句的答案去掉开头的 and / but / or；判分时带不带连词都算对。
- **复核**：在 span 内找唯一一个“头在 span 外”的 token 作为从句中心（去掉标点后不唯一 →
  `needs_review/span_not_constituent`）。它的 dep 必须符合类型：定语 = relcl；名词性 = ccomp / csubj / csubjpass / pcomp；
  状语 = advcl；并列 = conj，且该中心是限定动词。不符合 → `needs_review/clause_type_mismatch`。
  中心的子树范围（left_edge..right_edge，去掉标点；并列分句再去掉开头的连词）必须和答案完全一致，
  否则 → `needs_review/boundary_mismatch`。
- 题干示例：`划出句中的定语从句（从第一个词划到最后一个词）。`

### T3 `clause_type_classify` — 判断划线部分是什么（G-C03）

- **目标**：白名单定语、名词性、状语从句或并列分句，或者白名单非谓语 span / 介词短语（作为“不是从句”的题）。
- **选项（固定顺序）**：定语从句 / 名词性从句 / 状语从句 / 并列分句 / 不是从句（短语或非谓语）。
- **复核**：按 T2 的方式找中心。标注为从句：中心必须是限定动词，且 dep 符合 T2 的类型表。
  标注为“不是从句”：中心不是限定动词（第 4.1 节），或者 dep = prep。不一致 → `needs_review/clause_type_mismatch`。

### T4 `adverbial_relation` — 状语从句表示什么关系（G-C11）

- **目标**：原始 role 在 `RELATION_BY_ROLE` 表中的状语从句。普通 `adverbial_clause` 没有关系标签 →
  `rejected/no_relation_label`。
- **选项（固定顺序）**：时间 / 原因 / 条件 / 让步 / 对比 / 目的 / 结果。答案取自 `RELATION_BY_ROLE`。
- **复核**：引导词 = 从句中心的 mark 子节点；没有 mark 时取 span 的第一个词（小写；so that、even though、as long as
  等多词引导词按整体匹配）。查 `SUBORDINATOR_RELATIONS`：
  - 引导词无歧义且与标注一致 → `auto_pass`；
  - 无歧义但不一致 → `needs_review/subordinator_mismatch`；
  - 有歧义（while、since、as、so）→ 一律 `needs_review/subordinator_ambiguous`。这些是最有价值的题，必须由老师确认；
  - 不在表里 → `needs_review/subordinator_unknown`。

### T5 `subject_span` — 划出完整主语（G-S02）

- **选句**：符合 T1 选句条件；第 1 层恰好有一个 role = `subject` 的 span，且位于主句谓语之前；
  ROOT 没有 expl 子节点（排除 There be 句）。
- **答案**：从标注主语起点到标注主句谓语起点之间的原文（去掉两端标点），也就是包括修饰它的从句和分词。
- **复核**：ROOT 的 nsubj / nsubjpass / csubj / csubjpass 子节点的子树范围（去掉两端标点）必须与答案完全一致，
  否则 → `needs_review/subject_mismatch`。
- 题干：`划出这句话的完整主语（包括修饰它的成分）。`

### T6 `finite_or_not` — 这个动词是什么身份（G-N01；目标是分词时记为 G-N04）

- **目标词与标注答案**：
  - (a) T1 的 ROOT → 主句谓语；
  - (b) 白名单定语或状语从句的中心动词 → 从句里的谓语；
  - (c) 白名单非谓语 span 的中心动词 → 非谓语。
- **选项（固定顺序）**：主句谓语 / 从句里的谓语 / 非谓语（不定式、分词、动名词）。
- **复核**：(a) 该词是 ROOT；(b) 是限定动词，且是 relcl 或 advcl 从句的中心；(c) 不是限定动词。
  不一致 → `needs_review/finiteness_mismatch`。
- 题干：`句中【】里的动词在句子里是什么身份？`

#### 4.1 “限定动词”的判定（T3、T6 共用）

满足任一条即为限定动词：

- `morph` 中有 `VerbForm=Fin`；
- `tag_` ∈ {VBD, VBZ, VBP, MD}；
- 有 aux / auxpass 子节点，且其 `tag_` ∈ {VBD, VBZ, VBP, MD}。

不定式（带 `to` 子节点、`tag_`=TO）、无限定助动词的 VBG / VBN 都不是限定动词。

## 5. 白名单与对照表（写成代码里的常量，测试要覆盖）

只有原始 role 在白名单里的 span 才能当题目目标；其余 span 只作上下文。

| 常量 | 原始 role |
|---|---|
| `MAIN_VERB_ROLES` | verb_phrase, predicate, verb, main_predicate, passive_predicate, passive_verb_phrase, passive_verb, linking_verb, linking_predicate |
| `COORDINATED_PREDICATE_ROLES` | coordinated_predicate, coordinate_predicate, coordinated_verb_phrase, compound_predicate, coordinate_verb, first_predicate, coordinate_passive_predicate, coordinated_passive_predicate |
| `RELATIVE_CLAUSE_ROLES` | relative_clause, nonrestrictive_relative_clause, non_restrictive_relative_clause |
| `NOUN_CLAUSE_ROLES` | noun_clause, object_clause, subject_clause, appositive_clause, content_clause, predicative_clause, that_clause, subject_complement_clause, embedded_question |
| `ADVERBIAL_CLAUSE_ROLES` | adverbial_clause 加上 `RELATION_BY_ROLE` 的全部 key |
| `COORDINATE_CLAUSE_ROLES` | coordinated_clause, coordinate_clause, coordinated_main_clause |
| `NON_FINITE_ROLES` | participial_phrase, past_participle_modifier, past_participial_phrase, present_participle_modifier, present_participle_adverbial, present_participial_phrase, present_participle_result, participial_modifier, past_participle_phrase, past_participle_postmodifier, infinitive_phrase, infinitive_complement, purpose_infinitive, infinitive_modifier, infinitive_purpose, infinitive_postmodifier, gerund_phrase, gerund_subject, gerund_object, gerund_complement, non_finite_clause |
| T3 用的介词短语 | role 归一后为 `prepositional_phrase` 的 span |

明确排除（不能当目标）：fused / reduced / cleft / coordinated_* 类定语从句、`correlative_main_clause`、
explanatory / interrogative / infinitive / elliptical / imperative / passive / complement / nominal 类 clause、
裸 `clause`、所有 `reduced_*`、`time_condition_clause`。

`RELATION_BY_ROLE`：

| 关系 | 原始 role |
|---|---|
| 条件 | conditional_clause, condition_clause |
| 时间 | time_clause, temporal_clause |
| 目的 | purpose_clause |
| 让步 | concessive_clause, concession_clause |
| 结果 | result_clause |
| 对比 | contrast_clause, contrastive_clause |
| 原因 | reason_clause, cause_clause |

`SUBORDINATOR_RELATIONS`（无歧义）：

| 关系 | 引导词 |
|---|---|
| 让步 | although, though, even though, even if |
| 对比 | whereas |
| 原因 | because |
| 条件 | if, unless, provided, providing, as long as |
| 目的 | so that, in order that |
| 时间 | until, till, before, after, once, whenever, as soon as, when |

有歧义：while、since、as、so。

## 6. 过滤与原因码

**整句过滤**（命中任一条，整句不出任何题，状态为 `rejected`）：

| 原因码 | 条件 |
|---|---|
| `heading` | 任一 span 归一为 heading |
| `too_short` / `too_long` | 去掉标点后少于 6 个词或多于 60 个词 |
| `unknown_span` | 任一 span 归一为 unknown |
| `span_not_found` | 任一 span 的 text 不是原句子串 |
| `level_one_subordinate` | 第 1 层出现定语从句或名词性从句（已知异常） |
| `fragment` | 解析器 ROOT 不是 VERB/AUX |
| `unbalanced_quotes_or_brackets` | 引号或括号不成对 |
| `tagged_fragment` | 任一 span 的**原始** role 含子串 `fragment`（标注者自己标了残句，全库 36 句） |
| `clause_attached_to_conjunction` | 解析器中存在 dep ∈ {advcl, conj, ccomp, relcl, csubj, csubjpass, acl} 的 token，而它的 head 的 dep = `cc`。含义是解析器找不到这个从句依附的主句，原句残缺或是省略结构。全库命中 2 句 |
| `parse_failure` | 解析异常 |

**整句过滤和单题失败的边界（v0.1 新增，必须遵守）：**

- 整句过滤只处理“整句都不能用”的情况：上表各项。
- 一句命中多条整句规则时，`rejections_v0.jsonl` 记录命中的**全部**原因码。
- 某个 span 标错（例如主语边界错），只让**以该 span 为目标或答案依赖该 span 的题**失败，
  对应模板记 `needs_review` 或 `rejected`。**不传播**到同句的其他模板，同句其他 span 出的题照常复核。
- 不得为了让坏例达标而增加按句子 ID 的黑名单，也不得增加本表以外的整句规则。如果发现还需要别的整句规则，停下来汇报。

**定位 span**：按 `structure` 顺序，取不早于上一个 span 起点的第一次出现。
如果题目目标文本在句中出现不止一次 → 该题 `needs_review/ambiguous_span_location`。

**模板级原因码**：上一节已列出的，加上 `no_main_verb_tag`、`multiple_main_verbs`、`coordinated_main_clauses`、
`split_subject`、`existential`、`subject_after_verb`、`relation_label_out_of_scope`、`no_distractor`。
每个原因码在代码里集中定义一次，报告里按原因码统计。

## 7. 输出

| 文件 | 内容 | 提交到 git |
|---|---|---|
| `output/grammar_items/candidates_v0.jsonl` | 全部 auto_pass + needs_review 题 | 否（output/ 已忽略） |
| `output/grammar_items/rejections_v0.jsonl` | 被过滤的（句子、模板、原因码） | 否 |
| `output/grammar_items/parse_cache_v0.jsonl` | 可选的解析缓存，key = 句子 SHA-1 + 模型版本 | 否 |
| `data/grammar_items/generation_report_v0.json` / `.md` | 统计报告（第 7.2 节） | 是 |
| `data/grammar_items/review_batch_v0.xlsx` | 给老师的抽查清单（第 8 节） | 是 |
| `data/grammar_items/review_batch_v0.jsonl` | 抽查清单的机器可读版 | 是 |

### 7.1 单题格式（JSONL 每行一题，字段顺序固定）

```json
{
  "item_id": "gi_v0_<sha1(passage_id|sentence_id|template|target_start:target_end|variant)[:12]>",
  "generator_version": "grammar-items-v0",
  "template": "clause_boundary",
  "node_id": "G-C04",
  "source": {"source_kind": "reading_test", "test_id": "...", "passage_id": "...", "sentence_id": "A-04", "sentence": "原句"},
  "prompt_zh": "划出句中的定语从句（从第一个词划到最后一个词）。",
  "target": {"start": 0, "end": 0, "text": "..."},
  "options": null,
  "answer": {"kind": "span", "spans": [{"start": 0, "end": 0, "text": "..."}], "option": null},
  "grading": {"mode": "exact_span_ignore_punct", "allow_leading_conjunction": false},
  "distractors": [],
  "difficulty": "medium",
  "status": "auto_pass",
  "reasons": [],
  "evidence": {"tag_role": "relative_clause", "tag_level": 2, "parser": {"head": "apply", "dep": "relcl", "subtree": [0, 0]}}
}
```

- `target`：分类题中被划线的部分；点选题和划边界题为 null。`options` 只有分类题有。
- `answer.kind` ∈ {tokens, span, option}。T1 用 tokens，即多个字符 span；T2、T5 用 span；T3、T4、T6 用 option。
- `difficulty`：去掉标点后不超过 20 词且最大 level ≤ 2 → easy；超过 35 词或最大 level ≥ 3 → hard；其余 medium。
- `item_id` 必须稳定：同样的输入重跑，ID 不变且全局唯一。

### 7.2 统计报告必须包含

1. 每个模板 × 状态的题数，以及每个知识点的题数。
2. 各原因码数量，从高到低排列。
3. 按 source_kind（reading_test / reading_jijing）和 difficulty 的分布。
4. 环境：spaCy 版本、模型名与版本、Python 版本、随机种子、`data/reading_study` 全部文件内容的合并 SHA-256、图谱 JSON 的 SHA-256。
5. 第 11 节“已知坏例 / 正例”每句在每个模板下的处理结果。
6. 抽查清单的行数，以及按每行 30 秒估算的老师工作量。
7. `tagged_fragment` 和 `clause_attached_to_conjunction` 在全部 12,657 句上**各自独立统计**的命中句数（不受过滤顺序影响），并**逐句列出**命中的 passage_id、sentence_id 和原句。
   预期分别为 36 和 2；不一致时写出差异的句子。
8. **不得**包含时间戳或运行耗时，保证重跑结果逐字节一致。

## 8. 老师抽查清单（`review_batch_v0.xlsx`）

- **工作表**：第一个是“说明”，之后每个模板一个表，共 7 个。
- **每个模板 60 行**：auto_pass 50 行 + needs_review 10 行，随机打乱。
  种子固定为 `20261018`；auto_pass 不足 50 时全取，并在报告里写明。
- **盲审**：老师看不到每行是 auto_pass 还是 needs_review。这个信息只写在 `review_batch_v0.jsonl` 的 `pool_status` 里。
- **抽样**：auto_pass 按 (source_kind, difficulty) 分层，按各层题数比例分配名额（最大余数法），层内随机。
  同一张表里同一句最多 1 行，同一篇文章最多 2 行。
- **列**：序号 | 题目编号 | 知识点（ID + 中文名）| 题干 | 句子 | 选项 | 机器答案 | 老师判定 | 正确答案应为（选填）| 备注。
  - 分类题：在“句子”列用【】标出被划线的部分，“机器答案”列写选项文字。
  - 点选题和划边界题：“句子”列放原句，“机器答案”列放同一句并用【】标出答案。
- **“老师判定”列用下拉框**：正确 / 答案错 / 题目有歧义 / 句子不适合出题。表头冻结，自动换行，列宽可读。
- **“说明”表要写清**：
  - 四种判定的含义：
    - 正确：题目清楚，机器答案对；
    - 答案错：机器答案不对，请在“正确答案应为”里写出正确答案；
    - 题目有歧义：不止一个合理答案，或者题干说不清；
    - 句子不适合出题：原句残缺、太偏，或者和这个知识点无关。
  - 预计用时。
  - 填完交回给谁。
- **以后的通过标准**（本轮只写进“说明”，不实现）：某模板 auto_pass 的 50 行中，“答案错”加“题目有歧义”不超过 1 行，
  该模板才可以入库；否则调整规则、重新生成、重新抽样。

## 9. 代码组织与工程规则

- 建议结构：
  - `scripts/grammar_items/` 包：
    - `spans.py`：定位 span、白名单；
    - `parse_view.py`：与解析器无关的 token 视图，**只有这里 import spaCy**；
    - `checks.py`：过滤规则、原因码；
    - `templates.py`：6 个模板；
    - `review_batch.py`：抽样、xlsx。
  - CLI 入口：`scripts/generate_grammar_candidates.py`。
- 除 `parse_view.py` 的适配函数外，所有逻辑只依赖 token 视图（字段：i, text, start, end, pos, tag, dep, head, morph_verbform,
  is_punct），这样测试可以手造 token，**不需要 spaCy**。
- 概念归一只用 `api.reading_study_glossary.resolve_role`，不要重写。
  不要新增 `_normalize_*`：边界比较基于 token 下标，不做字符串清洗。
- 单个函数尽量少于 60 行；常量表集中定义；遍历文件时先排序；输出 JSON 用 `ensure_ascii=False`，结尾带换行。
- CLI 示例：

  ```
  .venv-grammar-tools/bin/python scripts/generate_grammar_candidates.py --seed 20261018
  ```

  一条命令完成生成、统计和抽查清单。还要有 `--limit N`，只跑前 N 篇，用于调试。

## 10. 测试

- 新增 `tests/test_grammar_item_candidates.py`，加入 `.github/workflows/ci.yml` 的轻量测试列表。
  CI 里只有 Flask，所以测试不能 import spaCy；xlsx 写出的测试在没有 openpyxl 时 `skipUnless` 跳过，
  但抽样和行内容的构造逻辑必须能在 CI 中测到。
- 必须覆盖：
  1. span 定位：文本重复出现时取正确位置；找不到时 → `span_not_found`。
  2. 白名单：`imperative_clause`、`correlative_main_clause`、裸 `clause` 不能当目标。
  3. T1：ROOT 在谓语 span 内 → auto_pass，动词单位正确；ROOT 在定语从句内 → needs_review；并列谓语 → rejected。
  4. T2：子树一致 → auto_pass；边界不一致 → `boundary_mismatch`；并列分句的开头连词被忽略。
  5. T4：although + concessive → auto_pass；while → `subordinator_ambiguous`；because + time_clause → `subordinator_mismatch`。
  6. T5：仿照第 11 节坏例 3（主语前多了介词短语）→ `subject_mismatch`。
  7. `item_id` 重跑稳定且全局唯一。
  8. 抽样：同一种子结果一致；每表每句最多 1 行、每篇最多 2 行；老师看到的行里没有 status 字段。
  9. 新整句规则：role 含 `fragment` → `tagged_fragment`；从句中心挂在 cc 上 → `clause_attached_to_conjunction`；
     正常的“并列分句里带状语从句”（如 `…, and when it does break it shatters…`）不命中。
  10. 不传播：同一句里 T5 因 `subject_mismatch` 失败时，T1 仍可 auto_pass。
- 本机还要跑完整生成一次，并**再跑第二次**，确认提交的 4 个文件逐字节一致（汇报里写出两次的 SHA-256）。

## 11. 已知坏例与正例（报告第 5 项必须逐句列出结果）

坏例：v0.1 起按句、按模板写预期。表中“允许”的题，Claude 已人工确认答案正确。

| 句子 | 错在哪里 | 预期 |
|---|---|---|
| `ielts7_test3_p1` K-03 `Be careful of little lives.'` | 祈使句被标成从句 | 整句 `rejected`（`too_short` 或 `unbalanced_quotes_or_brackets`） |
| `ielts8_test4_p1` C-04 `(One teacher was particularly keen …: he felt this would make …)` | 冒号后的独立句被标成 `explanatory_clause` | ① 不得有以 `he felt…` 为目标的题（不在白名单）。② T1、T5、T6(a) 无题（`no_main_verb_tag`）。③ **允许并预期 auto_pass**：T3 `to introduce colour and pictures into maths textbooks` → 不是从句；T6(c) `introduce` → 非谓语 |
| `reading_jijing_76_test_43_p2` H-02 | 主语标成了 `By the late 1980s the Modern Movement` | ① T5 必须是 `needs_review/subject_mismatch`。② **允许并预期 auto_pass**：T1（G-S01，答案 had / lost / out）、T6(a) `lost` → 主句谓语 |
| `reading_jijing_73_test_5_p2` F-05 | 原句是残句 | 整句 `rejected`（`unknown_span` 或 `tagged_fragment`） |
| `reading_jijing_56_test_64_p2` C-01 | 原句残缺 | 整句 `rejected`（`clause_attached_to_conjunction`） |
| `ielts13_test2_p2` C-04 | 省略结构 `but only if…` | 整句 `rejected`（`clause_attached_to_conjunction`，保守拒绝） |

正例（预期 auto_pass；如果不是，报告里要写解析器给出的理由）：

1. `reading_jijing_91_test_49_p3` D-02：T1 答案为 occurred，干扰项为 attended / representing。
2. `ielts11_test3_p2` A-04：T2 定语从句 `that apply, in varying degrees and combinations, to all migrations`。
3. `ielts15_test2_p3` D-05：T2 名词性从句 `that, as expected, high-status individuals … low-status individuals`。

## 12. 交付与汇报

1. 提交可以分几次，每次一件事，提交信息用中文。完成后推到 `codex/grammar-item-candidates`。
2. 按 CLAUDE.md 更新 `docs/CODEX_HANDOFF.md`（当前事实）和 `docs/WORKLOG.md`（顶部一条）。
3. 最终汇报（发给用户，由用户转给 Claude）必须包括：
   - 分支名和最后一个提交的 SHA；
   - 执行的命令及结果：测试数量、Ruff、两次生成的 SHA-256；
   - 每个模板的 auto_pass / needs_review / rejected 数量；
   - 坏例、正例的结果；
   - 与本计划不一致的地方及原因。

## 13. Claude 交叉审核时会检查的内容

1. diff 只涉及第 7、9、10 节列出的文件，加上 `.gitignore`、`requirements-grammar-tools.txt`、ci.yml 中的一行和交接文档。
2. 白名单、对照表与第 5 节逐项一致。
3. CI 轻量测试通过；第 10 节的 10 类用例都在。
4. 在云端用同版本环境重跑生成，提交的 4 个文件逐字节一致，item_id 和统计数一致（云端已装好 trf）。
5. 从抽查清单的 auto_pass 中随机再抽 30 题人工核对，并确认第 11 节每句的结果符合表中预期。
6. xlsx 是盲审（老师看到的行里没有状态信息）、有下拉框、行数符合第 8 节。
