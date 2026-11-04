# 写作 AI 真实模型小样本验证

- 时间：2026-11-04T14:03:57+00:00
- 模型：deepseek / deepseek-flash · 提示词 iwa-2026-11-04.6 · 评价思考模式 off
- 样本 7 篇 · 模型调用 7 次（上限 14）
- 传输：已收到模型服务响应；鉴权：通过
- 首个内容输出：已返回；内容合格率另见下表。

## 合格率

| 类型 | 首轮纯 JSON | 首轮通过校验 | 最终成功 | p50 / p90 延迟 | 首轮被拒原因 |
|---|---|---|---|---|---|
| 原稿评价 | 100% | 100% | 100% | 11786 / 13219 ms | — |

## 输出预算与思考模式

- 原稿评价：思考模式 off；输出上限 4500；单次输出峰值 2139；思考 token 未报告；截断 0 次、超时 0 次

## 证据与内容

- 评分项 27 个，引文 110 条，能在原文中找到 100%
- 建议因含原文、题目和题图都没有的数字被删去（整份评价合计）：0 条（评分项 0、论证结构 0、提升重点 0）
- 评价中与原文不符、已附更正的计数说法（段落数、某词出现次数）：0 处
- 精修：共 0 句，缺句率 —，改动率 —
- 改写：请求 0 篇，生成 0 篇，通过质量检查 0 篇；**占全部请求 —**（验收口径，生成失败计为未通过），占已生成 —；达到字数下限占全部请求 —；正文通过（字数、未仍离题）占全部请求 —；整篇重写重试 0 次、只修说明 0 次

## 论证结构（Task 2，不单独计分）

- 最终采用的 Task 2 评价 6 篇，有论证结构分析 6 篇，找到可核实立场句 6 篇
- Task 2 评价请求 6 次（含重试），其中 0 次因缺少论证结构或没有可核实的段落被整份拒绝（这些不计入下面的条目统计）
- 段落中心句 26 条（判定：supports ×21；off_position ×5）；论证问题 2 条（irrelevant ×1；unsupported ×1）；可选优化 12 条（不是错误，不计入问题数）
- AI 判断自相矛盾 0 处（已标需人工确认）；“没有支撑”但 AI 自己引用了同段支撑、改列可选优化 1 条；论证部分的建议因含无来源数字被删去 0 条（整份评价的合计见“证据与内容”）
- 条目统计（只看最终采用的评价，立场、每段、每条问题、每条可选优化各计 1 条）：模型给出 46 条 = 采用 46 + 格式不对或无法核实而丢弃 0 + 重复 0 + 超出上限 0；**丢弃率 0%**

## 分数合理性（宽松区间，不是真实分数）

通过 16 / 17（另有 1 项本批未运行，不计入）

- ✓ t2-weak：总分 ≤ 5.5（实际：5.5）
- ✗ t2-weak：论证问题 ≥ 1 条（弱文应被指出问题）（实际：[]）
- ✓ t2-mid：总分 ≥ 5.0（实际：6.5）
- ✓ t2-mid：总分 ≤ 7.0（实际：6.5）
- ✓ t2-good：总分 ≥ 6.0（实际：7.5）
- ✓ t2-good：总分 ≤ 8.0（实际：7.5）
- ✓ t2-strong：总分 ≥ 7.0（实际：7.5）
- ✓ t2-strong：论证问题 ≤ 1 条（强文不应被挑出很多问题）（实际：[]）
- ✓ t2-strong：不应出现 off_position / unclear_position / inconsistent_position / conclusion_inconsistent（问题类型、段落判定或立场一致性）（实际：{'problems': [], 'off_position_paragraphs': [], 'position_consistent': True, 'hits': []}）
- ✓ t2-strong：找到可核实的立场句（实际：I am convinced that investment should be weighted decisively towards public transport, with road construction reserved for cases where no realistic alternative exists.）
- ✓ t2-off-topic：TR ≤ 5.0（离题）（实际：3.0）
- – t2-off-topic：离题样本：通过质量检查的改写必须已按题目重写（实际：本批未运行改写）
- ✓ t2-off-topic：应标出 off_position / irrelevant（问题类型或段落判定偏离）（实际：{'problems': ['irrelevant'], 'off_position_paragraphs': ['introduction', 'body', 'body', 'body', 'conclusion'], 'position_consistent': True, 'hits': ['irrelevant', 'off_position']}）
- ✓ t2-under-length：有字数不足提示（实际：['字数 97 低于 250 词要求，实际考试中Task Response会因此受限。']）
- ✓ t1-no-image：指出文内数据矛盾 ≥ 1 条（已知样本矛盾）（实际：{'issues': ['Country A had the highest level of ownership in both years'], 'claims_checked': 6}）
- ✓ t1-no-image：缺图 TA / 总分不可评（实际：None）
- ✓ 分级样本：总分随水平不降（实际：[('t2-weak', 5.5), ('t2-mid', 6.5), ('t2-good', 7.5), ('t2-strong', 7.5)]）
- ✓ 分级样本：最强与最弱相差 ≥ 1.5（实际：2.0）

## 逐篇结果

| 样本 | 总分 | TR/TA | CC | LR | GRA | 论证问题 | 状态 |
|---|---|---|---|---|---|---|---|
| t2-weak | 5.5 | 6.0 | 5.5 | 5.0 | 5.0 | — | evaluate:ready |
| t2-mid | 6.5 | 6.5 | 6.5 | 6.5 | 6.5 | — | evaluate:ready |
| t2-good | 7.5 | 7.5 | 7.5 | 7.5 | 7.5 | — | evaluate:ready |
| t2-strong | 7.5 | 7.5 | 7.5 | 7.5 | 7.5 | — | evaluate:ready |
| t2-off-topic | 5.0 | 3.0 | 4.0 | 6.0 | 6.5 | irrelevant | evaluate:ready |
| t2-under-length | 5.0 | 5.0 | 5.0 | 5.0 | 5.5 | unsupported | evaluate:ready |
| t1-no-image | — | — | 6.5 | 6.5 | 7.0 | — | evaluate:ready |

总 token（含识图）：输入 13265 · 输出 12838
- 文本：输入 13265 · 输出 12838；缺少用量的调用 0 次
- 识图：输入 0 · 输出 0；缺少用量的调用 0 次
完整费用：未知（不能视为零费用）。

原始调用记录见同目录 `raw_calls.jsonl`（含模型原文，仅保存在本机）。
