# 给 Codex：Flash / Pro 对照的执行说明（2026-11-11）

这份说明由 Claude 写，用户转交给 Codex 在用户的 Mac 上执行。计划和判定规则见同目录 [README.md](README.md)
（第 5 节是判定规则，跑之前已定死）；低分段合成作文的依据与限制见 [lowband.md](lowband.md)。

## 0. 范围与授权

- **比较什么**：评价（evaluate）这一步，`deepseek-flash` 对 `deepseek-v4-pro`。其余条件全部固定：
  提示词以运行时代码为准（应为 `iwa-2026-11-10.12`）、思考 high、输出上限 32000、超时 300 秒、严格 JSON、一次校验重试。
- **调用上限**（最坏情况 = 评价次数 × 2，即每次评价都用掉一次校验重试；实际一般约一半）：

  | 阶段 | 组 | 每个模型的评价 | 两个模型最多请求 |
  |---|---|---|---|
  | 第一阶段 | 开发集（7 篇内置样本 × 2 次） | 14 | 56 |
  | | 学生作文 `teacher-t2-01`（× 2） | 2 | 8 |
  | | 留出集 Task 2（4 篇双评委 × 2） | 8 | 32 |
  | | 排序集（10 篇 AI 参考文章 × 1） | 10 | 40 |
  | | 低分段合成作文（6 篇 × 2） | 12 | 48 |
  | | 官方样卷（5 篇 × 2，需先转录，见第 3 节） | 10 | 40 |
  | | **第一阶段合计** | | **224**（官方样卷没转录时 184） |
  | 第二阶段（识图配好后） | 留出集 Task 1（2 篇带题图 × 2） | 4 | 16 + 2 次识图 = **18** |
  | **总计** | | | **240 次文字请求 + 2 次识图** |

  粗估费用约 8–10 元，最坏约 15 元（按上一批平均用量：Flash 约 0.03 元 / 请求、Pro 约 0.09 元 / 请求；留出集作文更长，实际会高一些）。这是估算，不是账单，也不是费用上限。
- **授权以用户确认上面的上限为准。** 用户在 2026-11-10 说“授权单位就是全部一起”（当时是前四组），2026-11-11 要求加入官方样卷并把整套交给 Codex 执行。
  **开始真实调用前，请让用户确认第一阶段 224（或 184）次、第二阶段 18 次。** 没有确认的数字不要跑；用不完的次数不带到以后。
  旧 B 授权（Flash 跑 `teacher-t2-01` 最多 2 次）由本批的学生作文组覆盖，不再单独执行。
- **不在范围内**：精修 / 改写、思考 max、其他模型、改提示词或任何产品代码、合并 main、部署、访问生产。

## 1. 离线复核（不花钱，先做）

```bash
git fetch origin claude/ielts-writing-ai-trial && git checkout claude/ielts-writing-ai-trial && git pull --ff-only
.venv/bin/python -m unittest discover -s tools/ielts_writing_ai/tests -t .      # 应为 415 OK
node tools/ielts_writing_ai/tests/test_draft.js
```

- 复核两个业务提交：`57ea722`（多位评委、排序组、沿用识图结果、`--repeat`、盲评表）和 `3ed1f59`（百分点精确相减；两边各自计价并区分缓存命中；“运行条件”表；盲评表补全）。
- 复核同目录的三个脚本：`run_comparison.sh`（运行与预算检查）、`summarize_comparison.py`（只汇总数字）、`tally_blind.py`（盲评计数）。
- 记下 HEAD。真实运行全程用同一个 HEAD：报告里的“工具源码指纹”必须两边一致，对照报告会提示不一致。

## 2. 数据文件

用户会给你 `iwa-holdout-20261111b.zip`，解压到 `~/iwa-calibration/`（保持 `img/` 与各 jsonl 同目录）。**这些文件都不进 Git。**
它们包含机构内部资料和一篇学生作文；作文原文、评委姓名和评语原文不得出现在仓库、交接或共享报告里。

| 文件 | 内容 | sha256 |
|---|---|---|
| `holdout_rated_t2.jsonl` | 4 篇 Task 2 教师范文，两位评委（A / B）四项分，批注 | `b73be4e97e926125da617531736dc1e212bbb5c5559ae0aa112ae785d09edfc4` |
| `holdout_rated_t1.jsonl` + `img/` | 2 篇 Task 1，带题图 | `392796fe26efbaf28130cc8a0a043f84ba243bcfc878eab57777278e8a8cdf6f` |
| `holdout_ordering.jsonl` | 10 篇 AI 参考文章，两题各 5 档，只做排序 | `d6021f16e501c8f5384869f03ad2959fbec3be8cb2098ce170bb02e5daac7057` |
| `holdout_lowband.jsonl` | 6 篇 Claude 原创低分段作文（标称 5 / 5.5 / 6，未经人工评分），预埋错误 | `201fd264992085cb402038142950363f5888179443bb3cee5282c82933439795` |
| `teacher.jsonl` | 学生作文 `teacher-t2-01`，老师总分 6.5 与四处批注 | `f4f05e6055d398171ea2099f6131c85c4f8242a600e2fd70283a27decb888387` |
| `official_template.jsonl` | 官方样卷 5 篇的模板：题目、官方总分、页码已填，**作文为空** | `79ed627f3e7df57b878005d884463fa5df47ed38313eeeaa2fb1510920ffbbd4` |

## 3. 官方样卷转录（Codex 做）

来源：用户提供的 PDF《IELTS Academic Writing – Sample Tasks》（IELTS.org，2023）。考生答卷是手写扫描图，没有文字层。
Claude 尝试逐字转录时输出被 API 内容过滤拦截（整篇复制出版物），所以这一步交给你在本机完成。PDF 是用户的，只用于内部评估。

| id | 题 | 官方总分 | PDF 页 |
|---|---|---|---|
| `official-2A-A` | 2A（家境与应对成年生活） | 4 | 18 |
| `official-2A-B` | 2A | 6.5 | 19–20 |
| `official-2A-C` | 2A | 8.5 | 21–22 |
| `official-2B-A` | 2B（国际旅游利弊） | 5.5 | 23 |
| `official-2B-B` | 2B | 7.5 | 25–26 |

转录规则：

1. **逐字照抄，不改任何错误**（拼写、语法、标点、大小写都保留）。这些错误就是评分依据。
2. 划掉的字不录；用插入符号（^）补在行间的字录在插入位置。
3. 按手写的段落分段，段与段之间用一个 `\n`；同一段里的换行不保留。
4. 实在认不出的词写 `[?]`，并在该条加 `"transcription_note"` 说明位置。
5. `official-2B-A` 开头抄了题目原文（考官评语专门提到“抄题不得分”），**照录**。
6. `official-2B-B` 第一行是手写标题，不录进 `essay`，在 `transcription_note` 里注明“省略标题行”。
7. 把模板复制为 `~/iwa-calibration/official.jsonl`，只填 `essay`（和必要的 `transcription_note`），其他字段不动。
8. 校验：`.venv/bin/python -c "from tools.ielts_writing_ai import realcheck; [print(i['id'], len(i['essay'].split())) for i in realcheck.load_samples('$HOME/iwa-calibration/official.jsonl')]"`，记录每篇词数。

两点限制，解读结果时要带上：官方样卷只有总分，没有四项分；这些答卷在网上流传很广，**模型很可能见过**，分数可能比在没见过的作文上准。
转录做不了也没关系：`official.jsonl` 不存在时脚本会自动跳过这一组，第一阶段上限降为 184。

## 4. 彩排（不花钱，必须先跑）

```bash
DRY=1 bash docs/design/ielts-writing-ai-model-comparison-plan-20261110/run_comparison.sh
DRY=1 STAGE=vision bash docs/design/ielts-writing-ai-model-comparison-plan-20261110/run_comparison.sh
```

演示模型，不需要 Key，结果在 `~/iwa-compare-dry/`。确认每组都“退出码 0”、每组都生成了 `compare-<组>/`，最后生成 `summary.md`。彩排结果可以删掉。

## 5. 第一阶段（真实调用）

```bash
CONFIRM_CAP=224 \
PRICE_FLASH_IN=<Flash 输入未命中缓存> PRICE_FLASH_CACHED=<Flash 输入命中缓存> PRICE_FLASH_OUT=<Flash 输出> \
PRICE_PRO_IN=<Pro 输入未命中缓存> PRICE_PRO_CACHED=<Pro 输入命中缓存> PRICE_PRO_OUT=<Pro 输出> \
bash docs/design/ielts-writing-ai-model-comparison-plan-20261110/run_comparison.sh
```

- 单价按 DeepSeek 官方当前价格（元 / 百万 token）填写；如有分时段价格，按实际运行时段，并记在回传 README 里。思考 token 已含在输出里，不另加。
- Key 从工具自己的 `.env` 读（`IWA_LLM_API_KEY`），脚本只覆盖服务商、模型名、思考档位、输出上限和超时。不要把 Key 写进命令、日志或 Git。
- 脚本做的事：每组两个模型轮流先跑；每次运行用 `--max-calls` 硬限最坏次数；开始前检查“已用 + 剩余最坏 ≤ CONFIRM_CAP”；每组跑完生成 `compare-<组>/`（对照、人工复核表、盲评表、对应关系）；最后写 `summary.md`。
- 中途停下（网络、Key、你手动中断）后，重跑同一条命令即可继续；已完成的步骤跳过，未完成的结果目录改名为 `*.incomplete-时间` 保留，其调用数仍计入已用。
- **遇到以下情况停下来问用户**：脚本因超上限拒绝；退出码 3（首次调用就失败，多半是 Key 或网络）；对照报告拒绝对照（条件不一致）；任一模型在某组最终失败率超过一半。不要调高 `CONFIRM_CAP`。
- 预计耗时 2–4 小时（约 120 次评价，每次几十秒到一分半）。

## 6. 第二阶段（识图配好后）

识图配置：工具 `.env` 里加 `IWA_VISION_PROVIDER=qwen`、`IWA_VISION_API_KEY=<百炼 Key>`（与 DeepSeek 的 Key 分开），可用 `check` 命令验证。

```bash
STAGE=vision CONFIRM_CAP=18 PRICE_FLASH_IN=… PRICE_FLASH_CACHED=… PRICE_FLASH_OUT=… PRICE_PRO_IN=… PRICE_PRO_CACHED=… PRICE_PRO_OUT=… \
bash docs/design/ielts-writing-ai-model-comparison-plan-20261110/run_comparison.sh
```

Flash 那次识图（2 次）并保存识别结果，Pro 那次沿用同一份识别结果，两边看到的图表内容完全相同。没配识图时脚本拒绝开始。识图费用不在文字单价里，按百炼账单另计。

## 7. 盲评（判断准不准的关键）

对每组的 `~/iwa-compare/compare-<组>/blind_review.md`，**先填完判断，再打开 `blind_key.json`**。

- 必做：`rated_t2`、`teacher`、`official`、`lowband`、`rated_t1`；可选：`dev`、`ordering`。
- 只判每篇的第一次运行；id 带 `#r2` 的段落是重复运行，可以留空（计数时默认跳过）。
- “判断”栏填：
  - `正确`：引文、说明和建议都对；
  - `①`：误读原文事实（例如说原文没有让步，其实有）；
  - `②`：改句改变了原意或逻辑（例如把并列改成因果）；
  - `③`：把可选的润色说成错误；
  - `不确定`。
- 每篇最后两行填**数字**：`④` 行 = 评委（或预埋清单）列出的明确错误中这一方没有指出的条数，对照 JSONL 里的 `teacher_findings` 和 `manual_review.md` 的“与老师批注对照”；`官方样卷`组没有批注，④ 填 0。`其他漏报` = 你发现的其他明显漏报条数。
- 填完后：

```bash
for g in rated_t2 teacher official lowband rated_t1; do
  .venv/bin/python docs/design/ielts-writing-ai-model-comparison-plan-20261110/tally_blind.py ~/iwa-compare/compare-$g
done
.venv/bin/python docs/design/ielts-writing-ai-model-comparison-plan-20261110/summarize_comparison.py ~/iwa-compare
```

你是另一家公司的模型，盲评表里不出现模型名；但这是第一遍判断。建议请一位老师抽查 10 条你判为 ① 或 ② 的条目，抽查结果写进回传 README。

## 8. 判定

按 [README.md](README.md) 第 5 节的规则下结论，写明每条规则用到的数字。分数部分以“AI 与评委的差距 vs 评委之间的差距”为准；排序集、低分段合成作文只看顺序，不当分数基准；
官方样卷看总分偏差，并注明“模型可能见过”。

## 9. 回传

新建 `docs/design/ielts-writing-ai-model-comparison-20261111-results/`，只放：

- `summary.md`、`summary.json`（脚本生成，只有数字和样本 id）；
- `ledger.txt`（每次运行的时间、模型、退出码、实际调用数）；
- 各组的 `blind_tally.json`（改名为 `blind_tally-<组>.json`）；
- `README.md`：HEAD、源码指纹、单价与时段、实际调用和费用、各组结论、按判定规则的结论、老师抽查结果、遇到的问题。

**不要提交**：`run_data.json`、`raw_calls.jsonl`、`report.md`、`compare.md`、`manual_review.md`、`blind_review.md`、`image_descriptions.json`、任何 JSONL、题图、转录稿，以及思考内容。它们含作文原文、批注引文或模型原文，留在本机。

按仓库约定更新 `docs/CODEX_HANDOFF.md`（顶部新增一节）和 `docs/WORKLOG.md`（顶部一条），只推 `claude/ielts-writing-ai-trial`；不合并 main、不部署。
