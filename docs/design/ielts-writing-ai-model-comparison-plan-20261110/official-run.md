# 给 Codex：官方低分段样卷组（Pro 单模型）执行说明（2026-11-13，第七版）

> **用户 2026-11-13 已选择：读图有误时，先对照原图改正，再确认，随后继续评价。** 改正写进 `--corrections` 文件（核对记录保留识图模型的原始读数并标明已改正），不直接改 `image_descriptions.json`；看不清、无法核实的内容不能确认。这项选择用于下一次单独授权的 Task 1 批次；已关闭的账本不重开，识图仍按上一轮状态停用，新批次的范围和上限仍需用户确认。
> `.15` 起 realcheck 只有带核对记录的读数才评 TA；核对记录绑定题图文件和确认时的读数原文，确认后改动读数需重新确认。3.3–3.5 的流程是“读图 → `image_check.md` 核对表 → `realcheck-check-images` 确认（需要时加 `--corrections`）→ `--require-checked-images` 评价”。
> 下面仍保留第五版的停止规则：识图失败或结果不明时停下报告；**误读的处理改为上面用户选择的“改正后继续”**。

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

- 代码：固定在已经完成离线验证的 `.14` 源码 worktree，不因远端 HEAD 移动而隐式换版本；本机 Python 和实际私有配置路径见第 3.1 节。
- 试用配置：评价 `deepseek-v4-pro` / high / 32000 / 420 秒，精修和改写 Flash；识图当前暂停。不要把源码树默认 `.env` 路径当作已存在的运行配置。
- **付费上限需要用户确认**，分两部分：
  - **A. Task 2 一篇，既有批次已闭合**：原计划 1 篇 × 2 次 × 每次最多 1 次校验重试 = **最多 4 次文字请求**（原估算约 0.5–1 元），不自动续用余额。
  - **B. Task 1 四篇**：识图最多 **4 次**（每篇一次，1A 两篇虽共用图片也各读一次），按首篇 1 次、人工核图通过后余下 3 次执行。全部核图通过后，计划评价 4 篇 × 2 次 = **8 次评价**，计入每次最多 1 次校验重试后，累计上限仍是 **16 次文字请求**。金额是估算，识图费用另计。
  - 合计最多 **20 次文字请求 + 4 次识图**。这是估算，不是账单。第一阶段剩余的额度不挪用。

## 1. 数据（不进 Git）

> 第四版（提示词 `.14`）：数据包换成 `iwa-official-lowband-20261113.zip`（sha256 `e0eba0ee10b6a469e898a775062114413552f8a64afc7894e9bc9584f3e11486`）。唯一改动是 `official-2B-A` 一行加了
> `"copied_from_question": [{"paragraph": 1}, {"paragraph": 2}]` 和 `"copied_source"`（官方考官评语：答卷开头五行照抄题目）。
> 只有这样标注的抄题才不计入字数并告知模型；程序按相似度找到的句子只在页面上提示“待确认”。覆盖解压后**重新运行下面第 3 步**，
> 输出里 `official-2B-A` 应显示“已确认抄题：第 1、2 段 34 词，自写 194 词”（复核 f46756f 按空白分词核对的数字；上次运行按工具计数的总词数 228 与之一致）。数字不同就把两种口径的数字都报给用户，不要改模板凑数。

1. 解压 Claude 发的数据包到 `~/iwa-calibration/`：`official_lowband_template.jsonl`（题目、官方分、题图、分组已填，作文为空）、`img/official-1A.png`、`img/official-1B.png`、`img/official-1C.png`，以及改正后的 `official_template.jsonl`。
2. 把用户发给 Claude 的转录原文（从“PDF 里 5.0–6.0 分的手写稿共 5 篇”起到最后一段）原样存为 `~/iwa-calibration/official_lowband_transcript.txt`。不用删中文说明行，脚本会跳过。
3. 填入并拆成 Task 1 / Task 2 两个文件：

```bash
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/design/ielts-writing-ai-model-comparison-plan-20261110/fill_transcripts.py \
  --template ~/iwa-calibration/official_lowband_template.jsonl \
  --text ~/iwa-calibration/official_lowband_transcript.txt
```

   输出 `official_lowband_t1.jsonl`（4 篇）和 `official_lowband_t2.jsonl`（1 篇），只打印 id、词数、段数和 sha256。
   用户在转录里标的 `[seilmens?]`、`[77?]` 会还原成 `seilmens`、`77`，并写进该篇的 `transcription_note`。其余拼写和语法错误一律保留。

## 2. A 部分历史执行示例

原 A 批次已经闭合；保留以下原输出目录与账本用于审计，不重跑或挪用余额。

```bash
OUT=~/iwa-compare-official-lowband-20261113
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m tools.ielts_writing_ai \
  --env-file /Users/zhouxin/Desktop/studytracker/.tmp/ielts-writing-ai-trial/.env realcheck \
  --samples ~/iwa-calibration/official_lowband_t2.jsonl --kinds evaluate --repeat 2 \
  --max-calls 4 --ledger $OUT/ledger-t2.jsonl --ledger-text-cap 4 --ledger-vision-cap 0 \
  --ledger-run official-t2 --max-failure-rate 0.5 --out $OUT/official-t2 --confirm-paid
```

开头一行应为“模型：deepseek / deepseek-flash，评价用 deepseek-v4-pro”“最多 4 次调用”。
**A 使用独立持久账本，文字总上限必须是 4，识图上限为 0。** `--max-calls 4` 只限制当前进程，不能替代账本的累计上限；不可预先给尚未授权的 B 留出 20 次额度。
中断或失败后仍沿用此账本，不换目录、换账本或提高上限来重试；已发出而结果不明的请求也计入这 4 次。
若需成本估算，另加执行时已核验数值的 `--price-in`、`--price-cached-in`、`--price-out`；不要把带尖括号的价格占位符直接当 shell 参数执行。

## 3. B 部分：Task 1 四篇分阶段执行

**本轮已因首图误读停止并关闭，不执行下列后续步骤。** 只有另行获得新一批执行的明确授权、样本和预算边界后，才使用这些步骤。不得把本轮未用的 3 次识图或 16 次文字请求视为自动续跑授权。

### 3.1 固定配置和同一账本

识图使用 DeepSeek Flash，文字评价使用 Pro `.14`，读图请求明确关闭思考。获准启用识图时，私有配置的 `IWA_VISION_PROVIDER=deepseek`；默认输出上限 2000、超时 180 秒。`check` 应显示 `vision_provider=deepseek`、`vision_model=deepseek-flash`、`vision_api_key_set=true`。**当前仍保持 `IWA_VISION_PROVIDER=none`，本文不要求改回。**

从首个识图请求开始就固定同一个 B 账本，三个阶段全部使用 `--ledger-text-cap 16 --ledger-vision-cap 4`。首步的 `--max-calls 1` 只限制本进程，不能把持久账本的识图总上限设成 1 再调高。A 与 B 分账，任何阶段都不换账本或提高上限。

以下路径按本机布局记录：执行工作目录是固定的、已经离线验证的 `.14` 源码 worktree 根目录，使用主树 Python 和实际私有配置。**本批 B 的实际 `OUT` 是 `/Users/zhouxin/iwa-compare-official-t1-20261113`，账本为该目录的 `ledger-t1.jsonl`，状态为 closed。下面保留该路径仅用于说明和审计，不可整段复制执行。** A 的旧目录 `~/iwa-compare-official-lowband-20261113` 已闭合，不能拿来充当 B 的输出或账本。未来获得新一批明确授权后，使用批准的新目录执行同样分阶段流程，并从该批首步到最后一步始终固定同一账本；不能用新目录绕过本批停止决定。

```bash
IWA_PY=/Users/zhouxin/Desktop/studytracker/.venv/bin/python
IWA_ENV=/Users/zhouxin/Desktop/studytracker/.tmp/ielts-writing-ai-trial/.env
# 本轮 B 已 closed；以下路径只供审计，不可继续执行本轮。
OUT=/Users/zhouxin/iwa-compare-official-t1-20261113
```

### 3.2 只准备首篇和其余三篇

在私有目录内拆分输入，不改原 JSONL。写入别的目录前，将相对 `image` 路径相对于**原输入文件所在目录**解析为绝对路径，避免图路径失效。首篇只含 `official-1B-A`；余下文件只能含 `official-1A-A`、`official-1A-B`、`official-1C-A`，与首篇不重叠。

```bash
"$IWA_PY" - "$OUT" <<'PY'
import os
os.umask(0o077)
import json
from pathlib import Path
import sys

source = Path.home() / "iwa-calibration/official_lowband_t1.jsonl"
rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
expected = {"official-1A-A", "official-1A-B", "official-1B-A", "official-1C-A"}
assert len(rows) == 4 and {r["id"] for r in rows} == expected
for row in rows:
    image = (source.parent / row["image"]).resolve()
    assert image.is_file()
    row["image"] = str(image)
out = Path(sys.argv[1]) / "inputs"
out.mkdir(parents=True, exist_ok=True, mode=0o700)
groups = {
    "t1-first.jsonl": [r for r in rows if r["id"] == "official-1B-A"],
    "t1-remaining.jsonl": [r for r in rows if r["id"] != "official-1B-A"],
    "t1-all.jsonl": rows,
}
for name, group in groups.items():
    target = out / name
    content = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in group)
    if target.exists():
        assert target.read_text() == content, f"拒绝覆盖不同内容：{target}"
    else:
        target.write_text(content)
    target.chmod(0o600)
print("输入准备完成：首篇1、余下3、总计4；题图绝对路径已检查")
PY
```

### 3.3 第一阶段只读首篇

```bash
"$IWA_PY" -m tools.ielts_writing_ai --env-file "$IWA_ENV" realcheck \
  --samples "$OUT/inputs/t1-first.jsonl" --images-only --with-vision \
  --max-calls 1 --ledger "$OUT/ledger-t1.jsonl" --ledger-text-cap 16 --ledger-vision-cap 4 \
  --ledger-run official-t1-image-first --out "$OUT/official-t1-image-first" --confirm-paid
```

**必须停在此处人工核图。** 结果目录里的 `image_check.md` 逐行列出读数和题图 sha256，用它对照原图核对标题、图例、坐标与单位、曲线/柱对应关系、关键数值、趋势或流程顺序。`ready` 和退出码 0 仅证明输出结构及信息量达到程序门槛，**不证明数字或图意准确**。首篇必须既为 `ready`，又经人工确认无误，才可进入下一阶段。

第五版规定：任何人工核图发现误读，立即停止整批；上一轮即在此门禁停止。**第七版起按用户选择**：误读的数值或标签对照原图改正，写进 `--corrections` 文件，在核对记录里保留原始读数，再确认、继续；不得直接改识图结果文件冒充原识图输出。看不清、拿不准的不确认，该篇不评 TA；识图失败或结果不明仍停下报告，不自动重试。

### 3.4 第二阶段只读余下三篇

仅在首篇人工核图通过后运行；不再把四篇全集传给识图命令。

```bash
"$IWA_PY" -m tools.ielts_writing_ai --env-file "$IWA_ENV" realcheck \
  --samples "$OUT/inputs/t1-remaining.jsonl" --images-only --with-vision \
  --max-calls 3 --ledger "$OUT/ledger-t1.jsonl" --ledger-text-cap 16 --ledger-vision-cap 4 \
  --ledger-run official-t1-images-remaining --out "$OUT/official-t1-images-remaining" --confirm-paid
```

同样人工逐份核对这三份读图；任一不是 `ready` 或出现误读，停止本批，不进入评价，不自动重试。两阶段合计最多 4 次识图，每篇恰好一次；共享同一图片的 1A 两篇仍各有一份按样本 ID 保存的结果。

### 3.5 合并冻结结果并执行八次评价

仅在四份结果全为 `ready` 且四份均完成人工核图之后，合并两个 `version: 2` 文件。保留每个样本结果对象原样，禁止覆盖重复 ID、缺行或将失败改成成功。以下只做本地合并与结构检查，**不能代替人工核图**：

```bash
"$IWA_PY" - "$OUT" <<'PY'
import os
os.umask(0o077)
import json
from pathlib import Path
import sys

out = Path(sys.argv[1])
expected = {"official-1A-A", "official-1A-B", "official-1B-A", "official-1C-A"}
images = {}
for name in ["official-t1-image-first", "official-t1-images-remaining"]:
    saved = json.loads((out / name / "image_descriptions.json").read_text())
    assert saved.get("version") == 2 and isinstance(saved.get("images"), dict)
    assert not images.keys() & saved["images"].keys(), "重复样本 ID"
    images.update(saved["images"])
assert set(images) == expected
assert all(r.get("status") == "ready" and isinstance(r.get("description"), str)
           and r["description"].strip() for r in images.values())
target = out / "image_descriptions.t1-frozen.json"
content = json.dumps({"version": 2, "images": images}, ensure_ascii=False, indent=2) + "\n"
if target.exists():
    assert target.read_text() == content, "拒绝覆盖不同冻结结果"
else:
    target.write_text(content)
target.chmod(0o600)
print("已合并4份ready结果；人工核图必须另行完成")
PY
```

人工核图通过后，用 `realcheck-check-images` 把核对写进一份新文件（不调用模型；核对人、时间和每张题图的 sha256 都记在文件里，题图之后被换就拒绝评价）。只有用户同意改正时才加 `--corrections`：

```bash
"$IWA_PY" -m tools.ielts_writing_ai --env-file "$IWA_ENV" realcheck-check-images \
  --samples "$OUT/inputs/t1-all.jsonl" \
  --descriptions "$OUT/image_descriptions.t1-frozen.json" \
  --confirm official-1A-A,official-1A-B,official-1B-A,official-1C-A --by "<核对人>" \
  --out "$OUT/image_descriptions.t1-checked.json"
```

再执行文字评价。下面沿用核对过的结果，**不加 `--with-vision`**；`--require-checked-images` 要求四篇都有核对记录：

```bash
"$IWA_PY" -m tools.ielts_writing_ai --env-file "$IWA_ENV" realcheck \
  --samples "$OUT/inputs/t1-all.jsonl" --kinds evaluate --repeat 2 \
  --image-descriptions "$OUT/image_descriptions.t1-checked.json" --require-checked-images \
  --max-calls 16 --ledger "$OUT/ledger-t1.jsonl" --ledger-text-cap 16 --ledger-vision-cap 4 \
  --ledger-run official-t1 --max-failure-rate 0.5 --out "$OUT/official-t1" --confirm-paid
```

计划是 4 篇 × 2 次共 8 次评价；校验重试也计入累计 16 次文字请求。若需要成本估算，再按实际执行时已核验的价格添加 `--price-in`、`--price-cached-in`、`--price-out`，不把旧时段单价当当前账单。

- 三阶段使用同一个 B 账本，累计文字最多 16、识图最多 4；A 的独立账本文字最多 4、识图为 0，均不可改大或互借。
- 账本在请求前落盘；已发出而结果不明的请求也占额度。中断、失败、人工核图误读均先保留结果并停下，不能自动重跑或换目录重建账本。
- 退出码：0 完成；2 参数 / 数据 / 账本有误；3 中止；4 最终失败超过一半；5 题图不可用。非 0 停止；退出码 0 仍须经过人工核图门禁。

## 4. 看什么

各 `report.md` 的“与老师评分对比”（这里的“老师”是官方总分）：平均绝对差和偏差（AI − 官方）。第一阶段 Pro 在 6.5–7.5 的作文上总分误差 0.286；
这一组看 **5–6 分的作文是否被明显打高**（例如普遍给到 6.5 以上）。Task 1 另看 `official-1A` 的排序（5.0 那篇不应高于 6.0 那篇），以及两次运行的总分差。

限制（写进回传 README）：只有总分，没有四项分；这些答卷流传很广，**模型很可能见过**；只有 5 篇。不需要盲评（没有逐条批注）。

## 5. 回传

新建 `docs/design/ielts-writing-ai-official-lowband-20261112-results/`，只放数字：各次 `report.json` 的 `calibration`、`ordering`、`repeat_spread`、`kinds.evaluate`、`usage`、`estimated_cost`，账本 `ledger.jsonl`，以及 README（HEAD、单价与时段、实际调用和费用、结论、限制）。
**不要提交**转录稿、`official_lowband_*.jsonl`、题图、`run_data.json`、`raw_calls.jsonl`、`report.md`（含引文）和思考内容。按约定更新 `docs/CODEX_HANDOFF.md` 与 `docs/WORKLOG.md`，只推 `claude/ielts-writing-ai-trial`。
