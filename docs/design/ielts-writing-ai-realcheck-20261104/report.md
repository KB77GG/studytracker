# 写作 AI 真实模型小样本验证

- 时间：2026-11-04T00:57:54+00:00
- 模型：deepseek / deepseek-flash · 提示词 iwa-2026-11-03.1
- 样本 7 篇 · 模型调用 21 次（上限 42）
- 传输：已收到模型服务响应；鉴权：通过
- 首个内容输出：已返回；内容合格率另见下表。

## 合格率

| 类型 | 首轮纯 JSON | 首轮通过校验 | 最终成功 | p50 / p90 延迟 | 首轮被拒原因 |
|---|---|---|---|---|---|
| 原稿评价 | 100% | 100% | 100% | 8777 / 10384 ms | — |
| 逐句精修 | 100% | 100% | 100% | 3022 / 8403 ms | — |
| 整篇改写 | 100% | 100% | 100% | 4498 / 5647 ms | — |

## 证据与内容

- 评分项 27 个，引文 117 条，能在原文中找到 100%
- 精修：共 87 句，缺句率 0%，改动率 34%
- 改写：7 篇，达到字数下限 71%

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
| t2-weak | 5.0 | 5.5 | 5.0 | 5.0 | 4.5 | evaluate:ready refine:ready rewrite:ready |
| t2-mid | 6.5 | 6.5 | 6.5 | 6.5 | 6.5 | evaluate:ready refine:ready rewrite:ready |
| t2-good | 7.0 | 7.0 | 7.0 | 7.0 | 7.0 | evaluate:ready refine:ready rewrite:ready |
| t2-strong | 7.5 | 7.0 | 7.5 | 7.5 | 7.5 | evaluate:ready refine:ready rewrite:ready |
| t2-off-topic | 6.0 | 4.0 | 6.0 | 6.5 | 6.5 | evaluate:ready refine:ready rewrite:ready |
| t2-under-length | 5.0 | 4.0 | 5.0 | 5.0 | 5.0 | evaluate:ready refine:ready rewrite:ready |
| t1-no-image | — | — | 6.5 | 6.5 | 6.5 | evaluate:ready refine:ready rewrite:ready |

总 token（含识图）：输入 15899 · 输出 19471
- 文本：输入 15899 · 输出 19471；缺少用量的调用 0 次
- 识图：输入 0 · 输出 0；缺少用量的调用 0 次
按输入的单价估算费用：0.028135

原始调用记录见同目录 `raw_calls.jsonl`（全部为内置合成样本，本次随功能分支共享；不含学生数据或密钥）。
