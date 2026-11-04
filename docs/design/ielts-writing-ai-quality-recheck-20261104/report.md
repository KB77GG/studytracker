# 写作 AI 真实模型小样本验证

- 时间：2026-11-04T04:23:16+00:00
- 模型：deepseek / deepseek-flash · 提示词 iwa-2026-11-04.2
- 样本 7 篇 · 模型调用 24 次（上限 42）
- 传输：已收到模型服务响应；鉴权：通过
- 首个内容输出：已返回；内容合格率另见下表。

## 合格率

| 类型 | 首轮纯 JSON | 首轮通过校验 | 最终成功 | p50 / p90 延迟 | 首轮被拒原因 |
|---|---|---|---|---|---|
| 原稿评价 | 100% | 100% | 100% | 9133 / 10476 ms | — |
| 逐句精修 | 100% | 100% | 100% | 3090 / 7505 ms | — |
| 整篇改写 | 100% | 57% | 100% | 5617 / 6954 ms | 质量检查：band_claim ×1；质量检查：below_min；claim_absent；deletion_mismatch ×1；质量检查：deletion_mismatch ×1 |

## 证据与内容

- 评分项 27 个，引文 112 条，能在原文中找到 100%
- 精修：共 87 句，缺句率 0%，改动率 39%
- 改写：请求 7 篇，生成 7 篇，通过质量检查 5 篇；**占全部请求 71%**（验收口径，生成失败计为未通过），占已生成 71%；达到字数下限占全部请求 100%（未通过项：no_changes ×1；noop_change ×1）

## 分数合理性（宽松区间，不是真实分数）

通过 11 / 11

- ✓ t2-weak：总分 ≤ 5.5（实际：5.0）
- ✓ t2-mid：总分 ≥ 5.0（实际：6.5）
- ✓ t2-mid：总分 ≤ 7.0（实际：6.5）
- ✓ t2-good：总分 ≥ 6.0（实际：7.0）
- ✓ t2-good：总分 ≤ 8.0（实际：7.0）
- ✓ t2-strong：总分 ≥ 7.0（实际：7.5）
- ✓ t2-off-topic：TR ≤ 5.0（离题）（实际：4.0）
- ✓ t2-under-length：有字数不足提示（实际：['字数 97 低于 250 词要求，实际考试中Task Response会因此受限。']）
- ✓ t1-no-image：缺图 TA / 总分不可评（实际：None）
- ✓ 分级样本：总分随水平不降（实际：[('t2-weak', 5.0), ('t2-mid', 6.5), ('t2-good', 7.0), ('t2-strong', 7.5)]）
- ✓ 分级样本：最强与最弱相差 ≥ 1.5（实际：2.5）

## 逐篇结果

| 样本 | 总分 | TR/TA | CC | LR | GRA | 状态 |
|---|---|---|---|---|---|---|
| t2-weak | 5.0 | 5.5 | 5.0 | 5.0 | 5.0 | evaluate:ready refine:ready rewrite:ready |
| t2-mid | 6.5 | 6.5 | 6.5 | 6.5 | 6.5 | evaluate:ready refine:ready rewrite:ready |
| t2-good | 7.0 | 7.0 | 7.0 | 7.0 | 7.0 | evaluate:ready refine:ready rewrite:ready |
| t2-strong | 7.5 | 7.0 | 7.5 | 7.5 | 7.5 | evaluate:ready refine:ready rewrite:ready |
| t2-off-topic | 6.0 | 4.0 | 6.0 | 6.5 | 6.5 | evaluate:ready refine:ready rewrite:ready |
| t2-under-length | 5.0 | 4.0 | 5.0 | 5.0 | 5.0 | evaluate:ready refine:ready rewrite:ready |
| t1-no-image | — | — | 7.0 | 7.0 | 7.0 | evaluate:ready refine:ready rewrite:ready |

总 token（含识图）：输入 20533 · 输出 25251
- 文本：输入 20533 · 输出 25251；缺少用量的调用 0 次
- 识图：输入 0 · 输出 0；缺少用量的调用 0 次
按输入的单价估算费用：0.036461

原始调用记录见同目录 `raw_calls.jsonl`（全部为内置合成样本，本次随功能分支共享；不含学生数据或密钥）。
