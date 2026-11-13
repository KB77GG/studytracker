# 官方 Task 1 单图预试：人工核图未通过

2026-11-13 北京时间 11:19，仅执行 `official-1B-A` 广播／电视受众图的首次识图。模型返回结构可用，但有两处足以影响 Task Achievement 事实核对的数值错误，因此停在首图，没有继续执行剩余三次识图或八次评价。

| 电视曲线时间 | 模型读数 | 人工看图约值 | 判断 |
|---|---:|---:|---|
| 16:00 | 14% | 21–23%，约 22% | 明显偏低 |
| 22:00 | 45% | 38–41%，约 40% | 明显偏高 |
| 20:00 | 47% | 45–46% | 较小的峰值时间归位误差 |

人工观察晚间峰值约在 19:30、约 47%。系列、单位、广播早峰、电视晚峰和深夜低值的大方向正确。以上人工数字是按坐标与曲线估读，不是图上逐点标注的官方精确值；两个明显错误已出现在模型原始 JSON 的 `data_points` 中，程序渲染结果与原始结构化结果一致。

本次固定源为独立树 `/private/tmp/studytracker-iwa-prompt14-review-20261113`，HEAD `fd8e910b3d5f5a5385af5a99d073c3824bbe74b2`，提示词 `iwa-2026-11-13.14`。识图使用 DeepSeek Flash、关闭思考、2000 token 上限、180 秒超时。账本实际 **1 次识图、0 次文字、0 次重试、0 个未知结果**；授权总上限 4 次识图／16 次文字，本批停止，不自动使用余额。没有 Task 1 评分结果，也不能据此判断 Pro 的评分准确性。

请求耗时 **5.430 秒**，输入 824 token（全部未命中缓存）、输出 958 token，共 1782 token。按本批记录的 Flash 高峰单价每百万输入 2 元、输出 8 元，以 Decimal 复算：`824×2/1,000,000 + 958×8/1,000,000 = 0.009312 元`。这是估算，不是账单。单价与高峰时段以本轮核对的 [DeepSeek 官方价格页](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/) 为准。

可复现的只读数字审计：

```bash
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B \
  /Users/zhouxin/Desktop/studytracker/docs/design/ielts-writing-ai-official-t1-pro-20261113-results/audit_export.py \
  --private-root /Users/zhouxin/iwa-compare-official-t1-20261113 \
  --source /private/tmp/studytracker-iwa-prompt14-review-20261113 \
  --out /Users/zhouxin/Desktop/studytracker/docs/design/ielts-writing-ai-official-t1-pro-20261113-results/vision_review.json
```

脚本只输出数值白名单和核对布尔值；原稿、题图、完整回答、识图描述、私有配置与思考内容不导出。视觉约值属于两位审阅者的人工核图结论，脚本只复核原始读数、渲染一致性、账本、用量和费用。公开证据为本目录的 `vision_review.json`，私有原始材料保留在本机输出目录。

本机最终继续运行 `.14` 文字评价，Pro/high/32000/420。因首图人工核对未通过，网页自动识图已暂时停用（provider=none，已配置的Flash参数保留）；本轮未产生Task1分数。完整私有账本与原始结果保留，不改读数、不重跑首图，也不自动续用余额。

给后续开发者：请把“结构可用”和“读数核实”分开。现有门禁只能检查返回格式、数据量与可读性声明，无法证明具体数值正确；可先提供可核对的读数表和人工确认入口，再据确认的数据评TA。不要把本题的具体答案直接加进通用提示词；本次也未证明加token或加思考必然修复读图。
