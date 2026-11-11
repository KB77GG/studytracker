# 给 Codex：Flash / Pro 对照的执行说明（2026-11-11，按复核 7b222c8 修订）

**修订说明**：复核 `7b222c8` 指出 bash 执行脚本会漏算预算（中断后 189/184、并发 212/184）、识图可能重复且两边输入不同、全部失败仍继续、Mac bash 3.2 输出乱码，
以及盲评和统计不完整。原 `run_comparison.sh`、`summarize_comparison.py`、`tally_blind.py` 已删除，改为工具内的命令：
`realcheck-batch`（运行）、`realcheck-tally`（盲评计数）、`realcheck-summary`（汇总）。每次请求发出前都在持久账本里加锁预留并落盘。

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

  这些上限由**批次账本硬性执行**：每次请求发出前，在 `~/iwa-compare/ledger-<阶段>.jsonl` 里加锁预留并 fsync；发出后结果未知的请求（进程被杀、断电）也算已用。
  文字和识图分开计：第二阶段识图最多 2 次（每张图一次，失败也不重试）。
  粗估费用约 8–10 元，最坏约 15 元（按上一批平均用量：Flash 约 0.03 元 / 请求、Pro 约 0.09 元 / 请求；留出集作文更长，实际会高一些）。这是估算，不是账单，也不是费用上限。
- **授权以用户确认上面的上限为准。** 用户在 2026-11-10 说“授权单位就是全部一起”（当时是前四组），2026-11-11 要求加入官方样卷并把整套交给 Codex 执行。
  **开始真实调用前，请让用户确认第一阶段 224（或 184）次、第二阶段 18 次。** 没有确认的数字不要跑；用不完的次数不带到以后。
  旧 B 授权（Flash 跑 `teacher-t2-01` 最多 2 次）由本批的学生作文组覆盖，不再单独执行。
- **不在范围内**：精修 / 改写、思考 max、其他模型、改提示词或任何产品代码、合并 main、部署、访问生产。

## 1. 离线复核（不花钱，先做）

```bash
git fetch origin claude/ielts-writing-ai-trial && git checkout claude/ielts-writing-ai-trial && git pull --ff-only
.venv/bin/python -m unittest discover -s tools/ielts_writing_ai/tests -t .      # 应为 435 OK
node tools/ielts_writing_ai/tests/test_draft.js
```

- 复核业务提交：`57ea722`（多位评委、排序组、沿用识图结果、`--repeat`、盲评表）、`3ed1f59`（百分点精确相减、分模型计价、运行条件表），
  以及修复复核 `7b222c8` 的提交 `50d557f`（`ledger.py` 持久账本、`batch.py` 批次命令、`blindtally.py` 盲评计数、realcheck 的识图冻结 / `--images-only` / `--max-failure-rate`、指标与盲评表修正；见交接文档）。
- 重跑复核用的探针：`docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/batch_probe.py`（在传输层计数，复现中断续跑、并发启动、全部失败三个场景）
  和 `verify/metrics_blind_probe_fixed.py`（复核方指标与盲评用例，按修复后的预期）。用法写在两个文件开头。
- 记下 HEAD。真实运行全程用同一个 HEAD：账本和 `batch-<阶段>.json` 记录了源码指纹和提示词版本，代码不同就拒绝续跑。

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
.venv/bin/python -m tools.ielts_writing_ai realcheck-batch --stage main --dry --out ~/iwa-compare-dry
.venv/bin/python -m tools.ielts_writing_ai realcheck-batch --stage vision --dry --out ~/iwa-compare-dry
```

演示模型，不需要 Key，数据默认从 `~/iwa-calibration/` 读。确认两个阶段都以“阶段 … 完成”结束，每组都生成了 `compare-<组>/`，最后生成 `summary.md`；
再跑一次同样的命令，应当全部“跳过（已完成）”、账本不增加。彩排目录可以删掉。

## 5. 第一阶段（真实调用）

```bash
.venv/bin/python -m tools.ielts_writing_ai --env-file tools/ielts_writing_ai/.env realcheck-batch \
  --stage main --cap 224 \
  --price flash=<输入未命中缓存>,<输入命中缓存>,<输出> \
  --price pro=<输入未命中缓存>,<输入命中缓存>,<输出>
```

- `--cap` 填用户确认的第一阶段上限（官方样卷没转录时是 184）。单价按 DeepSeek 官方当前价格（元 / 百万 token）；如有分时段价格，按实际运行时段，并记在回传 README 里。思考 token 已含在输出里，不另加。
- `--env-file` 必须明确给出（工具自己的配置文件，里面有 `IWA_LLM_API_KEY`）。命令为每次运行单独构造环境：不继承 shell 里的任何 `IWA_*` 设置，服务商固定为 DeepSeek、端点固定为官方地址，模型、思考档位、输出上限、超时由命令设定。缺 Key、端点不对、单价缺一项都会在发出任何请求前拒绝。
- 命令做的事：同一结果目录只允许一个批次（文件锁）；开始前核对“账本已用 + 剩余步骤最坏 ≤ `--cap`”；两个模型按组轮流先跑；每次请求先在账本预留；某个模型在某组最终失败超过计划篇数的一半就停；每组跑完生成 `compare-<组>/`（对照、人工复核表、盲评表、对应关系）；最后写 `summary.md`。
- **中断后**重跑同一条命令即可：已完成的运行跳过；没完成的结果目录改名为 `*.incomplete-时间` 保留，它发出的请求（包括结果未知的）都已在账本里，计入“已用”。所以中断后重跑，可能因为“已用 + 剩余最坏”超过上限而被拒绝——这时停下来问用户，不要自己调高 `--cap`。
- 退出码：`0` 完成；`2` 开始前拒绝（超上限、另一批次在跑、配置 / 单价 / 数据有误、批次条件与上次不同）；`3` 中止（首次调用就遇到 Key 或网络错误、达到账本上限、进程被杀）；`4` 某组最终失败过半；`5` 有题图没有可用的识别结果；`6` 两次运行不能对照。**除 0 以外都停下来问用户。**
- 预计耗时 2–4 小时（约 120 次评价，每次几十秒到一分半）。

## 6. 第二阶段（识图配好后）

识图配置：工具 `.env` 里加 `IWA_VISION_PROVIDER=qwen`、`IWA_VISION_API_KEY=<百炼 Key>`（与 DeepSeek 的 Key 分开）。

```bash
.venv/bin/python -m tools.ielts_writing_ai --env-file tools/ielts_writing_ai/.env realcheck-batch \
  --stage vision --cap 16 --price flash=… --price pro=…
```

先单独识别两张图（每张一次，识图账本上限 2），任何一张没有可用结果就以退出码 5 停止，两个文字模型都不跑；都可用时，Flash 和 Pro 都沿用这同一份识别结果（`--require-ready-images`），两边看到的图表内容完全相同。没配识图时开始前就拒绝。识图费用不在文字单价里，按百炼账单另计。

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
- 标“参考”的行是判断依据（程序的计数更正、被删的建议数、评委批注及程序按位置判断的覆盖情况），不用填。
  标了“【程序标注：需人工确认】”的论证问题，程序自己也没把握，判断时按“它说的对不对”来判。
- 填完后：

```bash
for g in rated_t2 teacher official lowband rated_t1; do
  .venv/bin/python -m tools.ielts_writing_ai realcheck-tally ~/iwa-compare/compare-$g
done
.venv/bin/python -m tools.ielts_writing_ai realcheck-summary --out ~/iwa-compare
```

  计数要求：判断栏只能是上面五种之一；④ 和“其他漏报”只能是非负整数。空格、`0.5`、`1–2` 之类会让计数标为“不完整”并以退出码 1 结束，列出要改的格子；汇总里也会标“不完整”。

你是另一家公司的模型，盲评表里不出现模型名；但这是第一遍判断。建议请一位老师抽查 10 条你判为 ① 或 ② 的条目，抽查结果写进回传 README。

## 8. 判定

按 [README.md](README.md) 第 5 节的规则下结论，写明每条规则用到的数字。分数部分以“AI 与评委的差距 vs 评委之间的差距”为准；排序集、低分段合成作文只看顺序，不当分数基准；
官方样卷看总分偏差，并注明“模型可能见过”。

## 9. 回传

新建 `docs/design/ielts-writing-ai-model-comparison-20261111-results/`，只放：

- `summary.md`、`summary.json`（只有数字和样本 id；分数字段按白名单导出，请求数和费用计入全部尝试）；
- `batch-log.txt`、`batch-main.json`、`batch-vision.json`、`ledger-main.jsonl`、`ledger-vision.jsonl`（时间、运行名、样本 id、模型名、错误码、token 数，不含正文）；
- 各组的 `blind_tally.json`（改名为 `blind_tally-<组>.json`）；
- `README.md`：HEAD、源码指纹、单价与时段、实际调用和费用、各组结论、按判定规则的结论、老师抽查结果、遇到的问题。

**不要提交**：`run_data.json`、`raw_calls.jsonl`、`report.md`、`compare.md`、`manual_review.md`、`blind_review.md`、`image_descriptions.json`、任何 JSONL 数据文件、题图、转录稿，以及思考内容。它们含作文原文、批注引文或模型原文，留在本机。

按仓库约定更新 `docs/CODEX_HANDOFF.md`（顶部新增一节）和 `docs/WORKLOG.md`（顶部一条），只推 `claude/ielts-writing-ai-trial`；不合并 main、不部署。
