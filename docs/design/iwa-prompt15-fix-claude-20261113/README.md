# `.15` 复核后的修复：核对记录绑定读数与结果（Claude，2026-11-13）

> **交接说明**：Codex 的 `.15` 复核（`iwa-prompt15-review-20261113`）和合并后的交接仍只在 Mac 本地，未推送。为避免冲突，Claude 这一轮仍**没有改** `docs/CODEX_HANDOFF.md` / `docs/WORKLOG.md`。Codex 提交本地交接时，请把下面两条并进去（与上一轮 `iwa-prompt15-claude-20261113/README.md` 的内容一起，各自保留）。复核报告目录也由 Codex 自己提交；Claude 没有把它放进 Git，以免和 Mac 上未跟踪的同名目录冲突。

## 交接条目（并入 `CODEX_HANDOFF.md`）

### 2026-11-13（夜）雅思写作 AI 试用工具：`.15` 复核的 3 个 P2、2 个 P3 已修（提示词仍 .15；已推功能分支；未调用真实模型）

- **用户选择（2026-11-13）**：读图有误时，先对照原图改正，再确认，随后继续评价。看不清、无法核实的内容不确认。这项选择用于下一次单独授权的 Task 1 批次；已关闭的账本不重开，识图仍停用，新批次的范围和上限仍需用户确认。已写进 `official-run.md` 第七版。
- **业务提交 `0701bcf`**：
  - **P2 读数绑定**：核对记录新增 `reading_sha256`（确认时读数原文的 sha256）。网页核对、`realcheck-check-images` 都写入它。三处会核对它：`load_image_outcomes`、`realcheck.run` 开始前（`imagecheck.verify`，在任何请求之前）、`prompts.visual_available`（构造提示时）。读数确认后被改过，或者记录里没有指纹，一律算未核对：不评 TA，读数也不发给模型。
  - **P2 统一入口**：
    - `load_samples` 拒绝样本 JSONL 里直接写的 `image_check` / `image_frozen`，核对记录只能来自核对文件。
    - `--require-checked-images` 要求每篇 Task 1 都有题图和核对记录，没有题图的也拒绝。
    - 运行前对每条核对记录再做完整校验：记录字段齐全、题图 sha256 一致、读数指纹一致。
  - **P2 旧完成记录**：只有生成仍在排队时才能核对。写库时 `set_image_check(waiting_only=True)` 也要求存在排队中的生成。`.14` 已出结果的记录：`awaiting_check=false`，新字段 `unchecked_legacy=true`；确认或跳过都返回 409，不新增调用，原结果和 generation ID 不变。页面标明“生成于读数核对功能上线之前，TA 和总分仅供参考，需按核对读数评分请重新提交”。
  - **P3 对照**：输入指纹只加“读数是否算已核对”，不含核对人、时间、原始读数。核对人、时间不同的两次运行可以对照；“已核对 vs 未核对”仍拒绝。
  - **P3 接口**：非对象 JSON、非字符串 `description` 返回 422。
  - **测试隔离**：新的命令行测试清掉外部 `IWA_*` 变量。另加一项测试，在 `IWA_VISION_PROVIDER=none` 下也通过。
  - 合法流程发给模型的内容不变，所以提示词版本仍是 `iwa-2026-11-13.15`。
- **验证**：
  - `$V/python -m unittest discover -s tools/ielts_writing_ai/tests -t .` → **492 OK**，三种 locale 都 OK；整套在导出 `IWA_VISION_PROVIDER=none` 时也 OK。Node 8 项、ruff、black、`node --check`、`git diff --check` 通过。
  - 新增回归 9 项：读数被改或缺指纹、提示门槛核对原文、JSONL 内嵌三种写法被拒、无题图被拒、运行前校验（0 调用）、仅核对人不同可对照、四种畸形请求 422、网页记录绑定存储文本、旧完成记录 409 且结果不变。
  - **复核者的独立探针**（在本机对修复后代码运行，Mac 上的报告目录未改）：
    - `realcheck/probe.py` **15/15**（原 10/15）。
    - `web/web_gate_probe.py` 跑到旧记录场景时会报错：它在确认后读取核对记录，而修复后这里返回 409、没有记录。改编版 `verify/web_gate_probe_adapted.py` 改为断言修复后的行为（409、无记录、页面标旧记录、结果与 ID 不变、0 调用），结果 **45/45**（原 38 项 + 新 7 项），findings 为空。
    - `vision_budget_probe.py` 139/139。
    - `verify/confirmed_probe_adapted.py` 用合成替身样本 67/70，剩下 3 项要用 Mac 上的官方原文跑，预期 70/70。
    - 改编版抄题 / 识图探针 22/22、32/32。
  - 真实浏览器（Playwright，演示模型）再走一遍核对流程：改动没被刷新掉，确认后出 TA，页面无错误。
- **未变**：抄题、段落、读图请求参数、评价模型、账本。未合并 main、未部署、未访问生产，小程序未上传、提审或发布。没有付费调用。
- **下一步**：
  1. Codex 复核。在 Mac 上用真实样本跑 `confirmed_probe_adapted.py`，用 `.14` 树跑 `web_gate_probe_adapted.py`，再跑复核者自己的 `realcheck/probe.py`。
  2. 通过后再把试用服务切到 `.15`，识图仍保持 `none`，等用户决定。
  3. Task 1 新批次需用户授权范围和上限，读错时按“改正后继续”处理。
  4. 老师填写抽查后汇总。

## 日志条目（并入 `WORKLOG.md`）

### 2026-11-13（夜）— 写作 AI 试用工具：`.15` 复核修复（核对记录绑定读数与结果）

- `0701bcf`：核对记录绑定确认时的读数原文；JSONL 不能内嵌核对记录；旧完成记录不能补确认；对照不受核对人、时间影响；接口畸形请求返回 422。记录用户“改正后继续”的选择。
- 492 项 Python（三种 locale）+ 8 项 Node 通过；复核者 realcheck 探针 15/15，网页探针改编版 45/45。未调用真实模型，只推功能分支。
