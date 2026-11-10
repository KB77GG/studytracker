# 写作 AI 真实模型小样本验证

- 时间：2026-11-09T15:16:18+00:00
- 模型：deepseek / deepseek-flash · 提示词 iwa-2026-11-10.12 · 评价思考模式 high
- 样本 7 篇 · 模型调用 9 次（上限 14）
- 传输：已收到模型服务响应；鉴权：通过
- 首个内容输出：已返回；内容合格率另见下表。

## 合格率

| 类型 | 首轮纯 JSON | 首轮通过校验 | 最终成功 | p50 / p90 延迟 | 首轮被拒原因 |
|---|---|---|---|---|---|
| 原稿评价 | 86% | 71% | 86% | 40654 / 84835 ms | 缺少总评 ×1；JSON 括号或结构错误 ×1 |
- 原稿评价 · t2-strong 第 1 次：JSON 结构错误：最外层对象在 grammar_note 之后就结束了（多了一个 } 或 ]），后面的 argument、overall_comment、priorities 落在了 JSON 之外；paragraphs 出现在最外层，但它属于 argument：argument 提前结束了（多了一个 }）；problems 出现在最外层，但它属于 argument：argument 提前结束了（多了一个 }）
- 原稿评价 · t2-strong 第 2 次：JSON 结构错误：最外层对象在 overall_comment 之后就结束了（多了一个 } 或 ]），后面的 priorities 落在了 JSON 之外

## 输出预算与思考模式

- 原稿评价：思考模式 high；输出上限 32000；单次输出峰值 13506；思考 token 合计 39165，单次最多 11293；截断 0 次、超时 0 次

## 证据与内容

- 评分项 23 个，引文 81 条，能在原文中找到 100%
- 建议因含原文、题目和题图都没有的数字被删去（整份评价合计）：1 条（评分项 0、论证结构 0、提升重点 1）
- 评价中与原文不符、已附更正的计数说法（段落数、某词出现次数）：0 处
- 精修：共 0 句，缺句率 —，改动率 —
- 改写：请求 0 篇，生成 0 篇，通过质量检查 0 篇；**占全部请求 —**（验收口径，生成失败计为未通过），占已生成 —；达到字数下限占全部请求 —；正文通过（字数、未仍离题）占全部请求 —；整篇重写重试 0 次、只修说明 0 次

## 论证结构（Task 2，不单独计分）

- 最终采用的 Task 2 评价 5 篇，有论证结构分析 5 篇，找到可核实立场句 5 篇
- Task 2 评价请求 8 次（含重试），其中 0 次因缺少论证结构或没有可核实的段落被整份拒绝（这些不计入下面的条目统计）
- 段落中心句 21 条（判定：supports ×16；off_position ×5）；论证问题 3 条（overgeneralized ×1；irrelevant ×1；off_position ×1）；可选优化 15 条（不是错误，不计入问题数）
- AI 判断自相矛盾 0 处（已标需人工确认）；“没有支撑”但 AI 自己引用了同段支撑、改列可选优化 0 条；论证部分的建议因含无来源数字被删去 0 条（整份评价的合计见“证据与内容”）
- 条目统计（只看最终采用的评价，立场、每段、每条问题、每条可选优化各计 1 条）：模型给出 44 条 = 采用 44 + 格式不对或无法核实而丢弃 0 + 重复 0 + 超出上限 0；**丢弃率 0%**

## 分数合理性（宽松区间，不是真实分数）

通过 11 / 12（另有 1 项本批未运行，不计入）

- ✓ t2-weak：总分 ≤ 5.5（实际：5.5）
- ✓ t2-weak：论证问题 ≥ 1 条（弱文应被指出问题）（实际：['overgeneralized']）
- ✓ t2-mid：总分 ≥ 5.0（实际：7.0）
- ✓ t2-mid：总分 ≤ 7.0（实际：7.0）
- ✓ t2-good：总分 ≥ 6.0（实际：8.0）
- ✓ t2-good：总分 ≤ 8.0（实际：8.0）
- ✗ t2-strong：评价已生成（实际：评价失败，无法检查）
- ✓ t2-off-topic：TR ≤ 5.0（离题）（实际：3.0）
- – t2-off-topic：离题样本：通过质量检查的改写必须已按题目重写（实际：本批未运行改写）
- ✓ t2-off-topic：应标出 off_position / irrelevant（问题类型或段落判定偏离）（实际：{'problems': ['irrelevant', 'off_position'], 'off_position_paragraphs': ['introduction', 'body', 'body', 'body', 'conclusion'], 'position_consistent': True, 'hits': ['irrelevant', 'off_position']}）
- ✓ t2-under-length：有字数不足提示（实际：['字数 97 低于 250 词要求，实际考试中Task Response会因此受限。']）
- ✓ t1-no-image：指出文内数据矛盾 ≥ 1 条（已知样本矛盾）（实际：{'issues': ['Country A had the highest level of ownership in both years'], 'claims_checked': 8}）
- ✓ t1-no-image：缺图 TA / 总分不可评（实际：None）

## 逐篇结果

| 样本 | 总分 | TR/TA | CC | LR | GRA | 论证问题 | 状态 |
|---|---|---|---|---|---|---|---|
| t2-weak | 5.5 | 6.0 | 6.0 | 5.0 | 5.0 | overgeneralized | evaluate:ready |
| t2-mid | 7.0 | 7.0 | 7.0 | 7.0 | 7.5 | — | evaluate:ready |
| t2-good | 8.0 | 8.0 | 8.0 | 8.0 | 8.0 | — | evaluate:ready |
| t2-strong | — | — | — | — | — | — | evaluate:failed |
| t2-off-topic | 6.5 | 3.0 | 7.0 | 7.5 | 7.5 | irrelevant, off_position | evaluate:ready |
| t2-under-length | 5.5 | 5.0 | 5.0 | 5.5 | 6.0 | — | evaluate:ready |
| t1-no-image | — | — | 7.0 | 7.0 | 7.5 | — | evaluate:ready |

总 token（含识图）：输入 29322 · 输出 56708
- 文本：输入 29322 · 输出 56708；缺少用量的调用 0 次
- 识图：输入 0 · 输出 0；缺少用量的调用 0 次
完整费用：未知（不能视为零费用）。

原始调用记录见同目录 `raw_calls.jsonl`（含模型原文，仅保存在本机）。
