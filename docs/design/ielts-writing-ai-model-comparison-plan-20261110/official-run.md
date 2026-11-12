# 给 Codex：官方样卷组（Pro 单模型）执行说明（2026-11-12）

用户 2026-11-12 决定：试用的评价改用 `deepseek-v4-pro`；暂时没有 5–6 分段的真实学生作文，**用官方样卷代替**。
这一组只回答一个问题：**Pro 在 4–8.5 分整个范围里，总分偏高还是偏低、档位顺序对不对。**
不再和 Flash 比较（模型已经选定），所以只跑 Pro，上限减半。

## 0. 前提

- 代码：功能分支上包含提交 `f2509aa`（`IWA_EVALUATE_MODEL`、评价超时默认 420 秒）的 HEAD。先跑离线测试：
  `.venv/bin/python -m unittest discover -s tools/ielts_writing_ai/tests -t .`（应为 453 OK）。
- **付费上限需要用户确认：最多 20 次文字请求**（5 篇 × 每篇 2 次 × 每次最多 1 次校验重试），不识图。
  按第一阶段 Pro 的实际用量（每次评价约 0.27 元），10 次评价约 2.7 元，最坏约 5.5 元；这是估算，不是账单，也不是费用上限。
  用户 2026-11-12 的原话是“分数5-6我暂时没有，就用官方的吧”；**跑之前请用户确认 20 次这个数字**。第一阶段剩余的额度不挪用。

## 1. 转录 5 篇官方答卷

按 [codex-run.md](codex-run.md) 第 3 节的规则，把用户提供的《IELTS Academic Writing – Sample Tasks》（IELTS.org，2023）里 5 篇 Task 2 手写答卷逐字录入
`~/iwa-calibration/official_template.jsonl` 的 `essay` 字段，另存为 `~/iwa-calibration/official.jsonl`（不进 Git）。

| id | 题 | 官方总分 | PDF 页 |
|---|---|---|---|
| `official-2A-A` | 2A | 4 | 18 |
| `official-2A-B` | 2A | 6.5 | 19–20 |
| `official-2A-C` | 2A | 8.5 | 21–22 |
| `official-2B-A` | 2B | 5.5 | 23 |
| `official-2B-B` | 2B | 7.5 | 25–26 |

要点：错误照抄不改；划掉的字不录；插入的字录在插入处；认不出写 `[?]`；`official-2B-A` 抄题的开头照录；`official-2B-B` 的标题行不录。
如果你不能逐字转录这些出版物，就停下来告诉用户，由用户自己录入（约 1200 词），不要用摘要或改写代替。

录完校验：

```bash
.venv/bin/python -c "from tools.ielts_writing_ai import realcheck; [print(i['id'], len(i['essay'].split())) for i in realcheck.load_samples('$HOME/iwa-calibration/official.jsonl')]"
```

## 2. 配置（试用配置，也是这一组用的配置）

`tools/ielts_writing_ai/.env` 里应为（改完先 `check`，不要把 Key 打印出来）：

```bash
IWA_LLM_PROVIDER=deepseek
IWA_LLM_MODEL=deepseek-flash
IWA_EVALUATE_MODEL=deepseek-v4-pro
IWA_EVALUATE_THINKING=high
IWA_EVALUATE_THINKING_MAX_TOKENS=32000
IWA_EVALUATE_THINKING_TIMEOUT=420
```

```bash
.venv/bin/python -m tools.ielts_writing_ai --env-file tools/ielts_writing_ai/.env check
```

确认输出里 `"evaluate_model": "deepseek-v4-pro"`、`"evaluate_thinking": "high"`、`"evaluate_thinking_timeout": 420.0`，`llm_base_url` 是 DeepSeek 官方地址。

## 3. 运行（用户确认 20 次之后）

```bash
OUT=~/iwa-compare-official-20261112
.venv/bin/python -m tools.ielts_writing_ai --env-file tools/ielts_writing_ai/.env realcheck \
  --samples ~/iwa-calibration/official.jsonl --kinds evaluate --repeat 2 \
  --max-calls 20 --ledger $OUT/ledger.jsonl --ledger-text-cap 20 --ledger-run official-pro \
  --max-failure-rate 0.5 --out $OUT/official-pro --confirm-paid \
  --price-in <Pro 输入未命中缓存> --price-cached-in <Pro 输入命中缓存> --price-out <Pro 输出>
```

- 开头一行应显示“模型：deepseek / deepseek-flash，评价用 deepseek-v4-pro”，“最多 20 次调用”。
- 账本在每次请求发出前落盘；中断后重跑同一条命令时，账本里已有的请求都算已用，上限仍是 20（不要改大）。
  重跑前把没完成的 `$OUT/official-pro` 改名保留。
- 退出码：0 完成；2 参数 / 数据 / 账本有误；3 中止（首次调用就遇到 Key 或网络错误、达到账本上限）；4 最终失败超过一半。非 0 都停下来问用户。
- 单价按 DeepSeek 官方当前价格和实际运行时段填写（第一阶段核对过：高峰 9 / 0.30 / 27，空闲半价）。

## 4. 看什么

`$OUT/official-pro/report.md` 里：

- **与老师评分（总分）**：这里的“老师”是官方总分。看平均绝对差和偏差（AI − 官方）。第一阶段在 6.5–7.5 的作文上 Pro 总分误差 0.286，CC 偏高；这一组主要看 **4 分和 5.5 分这两篇是否被打得明显偏高**。
- **排序检查**：`official-2A`（4 / 6.5 / 8.5）和 `official-2B`（5.5 / 7.5）两组，标称更高的作文 AI 总分不应更低。
- **重复运行波动**：同一篇两次总分差。

限制（写进回传 README）：只有总分，没有四项分，看不出 CC 是否偏高；这些答卷流传很广，**模型很可能见过**，分数可能比在没见过的作文上准；只有 5 篇。

不需要盲评：这一组没有逐条批注。如果顺手看到明显误读原文的反馈，记在私有备注里即可。

## 5. 回传

新建 `docs/design/ielts-writing-ai-official-pro-20261112-results/`，只放数字：`report.json` 里 `calibration`、`ordering`、`repeat_spread`、
`kinds.evaluate` 的格式指标、`usage`、`estimated_cost`，账本 `ledger.jsonl`（只有 id、模型、错误码、token 数），以及 README（HEAD、单价与时段、实际调用和费用、结论、限制）。
**不要提交**转录稿、`official.jsonl`、`run_data.json`、`raw_calls.jsonl`、`report.md`（含引文）和思考内容。
按约定更新 `docs/CODEX_HANDOFF.md` 与 `docs/WORKLOG.md`，只推 `claude/ielts-writing-ai-trial`。
