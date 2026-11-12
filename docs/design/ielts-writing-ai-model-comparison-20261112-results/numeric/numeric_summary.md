# 真实比较：脱敏数字审计

状态：批次数字核对完成；判断质量仍需独立盲评。

| 组 | 模型 | 请求 | 重试 | 成功评价 | 最终失败 | 首轮 JSON | 首轮校验 |
|---|---|---:|---:|---:|---:|---:|---:|
| dev | flash | 18 | 4 | 13 | 1 | 10 | 10 |
| dev | pro | 14 | 0 | 14 | 0 | 14 | 14 |
| teacher | flash | 2 | 0 | 2 | 0 | 2 | 2 |
| teacher | pro | 2 | 0 | 2 | 0 | 2 | 2 |
| rated_t2 | flash | 11 | 3 | 7 | 1 | 5 | 5 |
| rated_t2 | pro | 8 | 0 | 8 | 0 | 8 | 8 |
| ordering | flash | 13 | 3 | 10 | 0 | 7 | 7 |
| ordering | pro | 10 | 0 | 10 | 0 | 10 | 10 |
| lowband | flash | 12 | 0 | 12 | 0 | 12 | 12 |
| lowband | pro | 12 | 0 | 12 | 0 | 12 | 12 |

完整延迟、token、费用区间、重复波动、共同评分子集、排序与账本核对见同目录 numeric_summary.json。


- flash：请求 56；已知用量估算 3.20242008–3.20242008 元；全部请求费用上界 3.20242008。非服务商账单。
- pro：请求 46；已知用量估算 12.4468866–12.6137826 元；全部请求费用上界 12.6137826。非服务商账单。

## 口径与限制

- Counts include all reserved requests, including retries and unknown outcomes; reservations are not proof the provider received a request.
- JSON/validation denominators are first attempts. Final failure rates use attempted evaluations; completion checks require all planned evaluations.
- Report p50/p90 covers successful transport calls, including retries; ledger wall times cover every completed request and have one-second timestamp resolution.
- Peak is Monday-Friday Beijing 09:00-12:00 and 14:00-18:00; other times are half price. No statutory-holiday calendar is inferred.
- Requests spanning a price boundary are separately counted and bounded at half/full price. Unknown usage makes total upper cost null, never zero.
- Missing cache usage is bounded using all-hit/all-miss input pricing. Reasoning tokens are included in completion tokens, never added twice.
- Private summary.json uses fixed peak rates: a conservative usage estimate, not the provider bill; unknown usage remains unpriced.
- Repeated scores are dependent measurements, not additional independent essays. Issue overlap is unavailable from the permitted numeric reports.
- Teacher and dual-rater groups are score references; ordering and synthetic lowband nominal levels are not calibrated ground truth.
- No acceptance threshold was predeclared for ranking inversions/spread; monotonicity and endpoint separation are descriptive checks.
- Common dual-rater metrics are read from summary only; raw raters are intentionally not read. Blind judgment-error rules and recommendation remain pending separate review.
