# 给 Codex：官方低分段样卷组（Pro 单模型）执行说明（2026-11-13，第三版）

用户 2026-11-12 决定：试用的评价改用 `deepseek-v4-pro`；没有 5–6 分段的真实学生作文，**用官方样卷代替**。
用户已亲自转录了 PDF 里官方给分 5.0–6.0 的全部 5 篇手写答卷（发在给 Claude 的消息里）：

| id | 任务 | 官方分 | PDF 页 | 题图 |
|---|---|---|---|---|
| `official-1A-A` | Task 1A（继续教育人数柱状图） | 5.0 | 9 | `img/official-1A.png` |
| `official-1A-B` | Task 1A（同上） | 6.0 | 10 | `img/official-1A.png` |
| `official-1B-A` | Task 1B（广播电视受众折线图） | 6.0 | 11 | `img/official-1B.png` |
| `official-1C-A` | Task 1C（制砖流程图） | 5.0 | 13 | `img/official-1C.png` |
| `official-2B-A` | Task 2B（国际旅游利弊） | 5.5 | 23 | — |

这一组只回答：**Pro 对 5–6 分的作文，总分偏高还是偏低**；1A 的两篇（5.0 / 6.0）同题，另看顺序。不再比较 Flash（模型已选定）。

> 第一版（只列 5 篇 Task 2）里的 `official_template.jsonl` 有错：2B 的两行配成了 2A 的题目（提取时先匹配到了 PDF 目录里的同名标题）。
> 新数据包里的 `official_template.jsonl` 已改正；那份 Task 2 模板（4 / 6.5 / 7.5 / 8.5 分）仍无人转录，本次不用。

## 0. 前提与上限

- 代码：功能分支 HEAD（含 `f2509aa` 的 `IWA_EVALUATE_MODEL` 与 420 秒超时）。离线测试 `.venv/bin/python -m unittest discover -s tools/ielts_writing_ai/tests -t .` 应全部通过。
- 试用配置（`tools/ielts_writing_ai/.env`，用户已配好）：评价 `deepseek-v4-pro` / high / 32000 / 420 秒，精修和改写 Flash。
- **付费上限需要用户确认**，分两部分：
  - **A. Task 2 一篇，现在就能跑**：1 篇 × 2 次 × 每次最多 1 次校验重试 = **最多 4 次文字请求**（约 0.5–1 元）。
  - **B. Task 1 四篇，识图配好后再跑**：先识图 **4 次**（每篇一次，1A 两篇各读一次），再评价 4 篇 × 2 次 = **最多 16 次文字请求**（约 2–4 元，识图另按百炼计费）。
  - 合计最多 **20 次文字请求 + 4 次识图**。这是估算，不是账单。第一阶段剩余的额度不挪用。

## 1. 数据（不进 Git）

1. 解压 Claude 发的数据包到 `~/iwa-calibration/`：`official_lowband_template.jsonl`（题目、官方分、题图、分组已填，作文为空）、`img/official-1A.png`、`img/official-1B.png`、`img/official-1C.png`，以及改正后的 `official_template.jsonl`。
2. 把用户发给 Claude 的转录原文（从“PDF 里 5.0–6.0 分的手写稿共 5 篇”起到最后一段）原样存为 `~/iwa-calibration/official_lowband_transcript.txt`。不用删中文说明行，脚本会跳过。
3. 填入并拆成 Task 1 / Task 2 两个文件：

```bash
.venv/bin/python docs/design/ielts-writing-ai-model-comparison-plan-20261110/fill_transcripts.py \
  --template ~/iwa-calibration/official_lowband_template.jsonl \
  --text ~/iwa-calibration/official_lowband_transcript.txt
```

   输出 `official_lowband_t1.jsonl`（4 篇）和 `official_lowband_t2.jsonl`（1 篇），只打印 id、词数、段数和 sha256。
   用户在转录里标的 `[seilmens?]`、`[77?]` 会还原成 `seilmens`、`77`，并写进该篇的 `transcription_note`。其余拼写和语法错误一律保留。

## 2. A 部分：Task 2 一篇（用户确认 4 次之后）

```bash
OUT=~/iwa-compare-official-lowband-20261113
.venv/bin/python -m tools.ielts_writing_ai --env-file tools/ielts_writing_ai/.env realcheck \
  --samples ~/iwa-calibration/official_lowband_t2.jsonl --kinds evaluate --repeat 2 \
  --max-calls 4 --ledger $OUT/ledger-t2.jsonl --ledger-text-cap 4 --ledger-vision-cap 0 \
  --ledger-run official-t2 --max-failure-rate 0.5 --out $OUT/official-t2 --confirm-paid \
  --price-in <Pro 输入未命中缓存> --price-cached-in <Pro 输入命中缓存> --price-out <Pro 输出>
```

开头一行应为“模型：deepseek / deepseek-flash，评价用 deepseek-v4-pro”“最多 4 次调用”。
**A 使用独立持久账本，文字总上限必须是 4，识图上限为 0。** `--max-calls 4` 只限制当前进程，不能替代账本的累计上限；不可预先给尚未授权的 B 留出 20 次额度。
中断或失败后仍沿用此账本，不换目录、换账本或提高上限来重试；已发出而结果不明的请求也计入这 4 次。

## 3. B 部分：Task 1 四篇（识图配好、用户确认后）

识图配置（2026-11-13 起支持 DeepSeek 读图，Flash 读图、Pro 评价，同一个 Key）：在 `tools/ielts_writing_ai/.env` 加

```bash
IWA_VISION_PROVIDER=deepseek
# 可选：IWA_VISION_MAX_TOKENS=2000、IWA_VISION_TIMEOUT=180（默认值）
```

`check` 应显示 `"vision_provider": "deepseek"`、`"vision_model": "deepseek-flash"`、`"vision_api_key_set": true`。读图请求会明确关闭思考。
**建议先只跑一张图做连通和人工读数核对**（例如把 `--samples` 换成只含 `official-1B-A` 一行的文件，`--max-calls 1 --ledger-vision-cap 1`），读数对了再跑四张；这一次也计入 4 次识图上限。

先只识图（每篇一次，结果含失败一并冻结）：

```bash
.venv/bin/python -m tools.ielts_writing_ai --env-file tools/ielts_writing_ai/.env realcheck \
  --samples ~/iwa-calibration/official_lowband_t1.jsonl --images-only --with-vision \
  --max-calls 4 --ledger $OUT/ledger-t1.jsonl --ledger-text-cap 16 --ledger-vision-cap 4 \
  --ledger-run official-t1-images --out $OUT/official-t1-images --confirm-paid
```

退出码 5 表示有图没有得到可用的识别结果：停下来告诉用户，不要跑评价。四张都可用时再评价：

```bash
.venv/bin/python -m tools.ielts_writing_ai --env-file tools/ielts_writing_ai/.env realcheck \
  --samples ~/iwa-calibration/official_lowband_t1.jsonl --kinds evaluate --repeat 2 \
  --image-descriptions $OUT/official-t1-images/image_descriptions.json --require-ready-images \
  --max-calls 16 --ledger $OUT/ledger-t1.jsonl --ledger-text-cap 16 --ledger-vision-cap 4 \
  --ledger-run official-t1 --max-failure-rate 0.5 --out $OUT/official-t1 --confirm-paid \
  --price-in <…> --price-cached-in <…> --price-out <…>
```

- B 仅在单独获得 16 次文字 + 4 次识图授权后使用 `ledger-t1.jsonl`；与 A 分账，不借用 A 的剩余额度。以上文字评价沿用冻结结果，不开启识图调用。
- 账本在每次请求发出前落盘；中断后重跑同一条命令，已发出的请求都算已用。A 累计文字最多 4，B 累计文字最多 16、识图最多 4，均不可改大。重跑前把没完成的结果目录改名保留，**账本原位保留**。
- 退出码：0 完成；2 参数 / 数据 / 账本有误；3 中止（首次调用就遇到 Key 或网络错误、达到账本上限）；4 最终失败超过一半；5 题图不可用。非 0 都停下来问用户。
- 单价按 DeepSeek 官方当前价格和实际时段（第一阶段核对过：Pro 高峰 9 / 0.30 / 27，空闲半价）。

## 4. 看什么

各 `report.md` 的“与老师评分对比”（这里的“老师”是官方总分）：平均绝对差和偏差（AI − 官方）。第一阶段 Pro 在 6.5–7.5 的作文上总分误差 0.286；
这一组看 **5–6 分的作文是否被明显打高**（例如普遍给到 6.5 以上）。Task 1 另看 `official-1A` 的排序（5.0 那篇不应高于 6.0 那篇），以及两次运行的总分差。

限制（写进回传 README）：只有总分，没有四项分；这些答卷流传很广，**模型很可能见过**；只有 5 篇。不需要盲评（没有逐条批注）。

## 5. 回传

新建 `docs/design/ielts-writing-ai-official-lowband-20261112-results/`，只放数字：各次 `report.json` 的 `calibration`、`ordering`、`repeat_spread`、`kinds.evaluate`、`usage`、`estimated_cost`，账本 `ledger.jsonl`，以及 README（HEAD、单价与时段、实际调用和费用、结论、限制）。
**不要提交**转录稿、`official_lowband_*.jsonl`、题图、`run_data.json`、`raw_calls.jsonl`、`report.md`（含引文）和思考内容。按约定更新 `docs/CODEX_HANDOFF.md` 与 `docs/WORKLOG.md`，只推 `claude/ielts-writing-ai-trial`。
