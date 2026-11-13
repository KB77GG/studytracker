# `.15`：确认抄题的词边界，以及题图读数“经人核对才评 TA”（Claude，2026-11-13）

> **交接说明**：Codex 把“老师审阅材料已补齐”的记录只写在了 Mac 本地的 `docs/CODEX_HANDOFF.md` / `docs/WORKLOG.md`，还没有推送。为避免和这份本地改动冲突，这一轮 Claude **没有改**这两个文件，交接内容写在本文。Codex 提交本地交接时，请把下面“交接条目”并进 `CODEX_HANDOFF.md` 顶部，把“日志条目”并进 `WORKLOG.md` 顶部（两边的内容都保留）。

## 交接条目（并入 `CODEX_HANDOFF.md`）

### 2026-11-13（夜）雅思写作 AI 试用工具：复核 cd82fc1 的两项——确认抄题词边界、题图读数经人核对才评 TA（提示词 .15；已推功能分支；未调用真实模型）

- **输入**：Codex 的 `.14` 复核与首张题图预试（`cd82fc1`）。
  - 新 P2：确认片段 `quote` 用 `isalnum` 判断词边界，与计词的 `WORD_RE` 不一致。`don't` / `don’t` / `cost-effective` 可以拆成两半各确认一次，合成 151 词被算成 149。
  - 首图预试：Flash 读数格式完整、程序判为 ready，但电视 16:00、22:00 两个数值明显读错，已停批、识图已停用。
  - 复核建议：把“结构可用”和“读数已核实”分开，提供可核对的读数表和人工确认入口，再按确认的数据评 TA；不把样本读数写进通用提示。
- **业务提交 `89e8c7c`（词边界）**：`essay.resolve_copied` 的 quote 起止不能落在任何计词 token 内部，也不能紧挨其他字母或数字。完整复合词照常可选，各片段词数相加不会重复。回归覆盖三种连接符的左右半词、完整词正例、标点边界、非 ASCII 字母，以及 151 词的端到端场景（拆词被拒；选完整词只扣 1 词，剩 150，不提示不足）。
- **业务提交 `9339cdb`（读数核对，提示词 `iwa-2026-11-13.15`）**：
  - **门槛**：`prompts.visual_available` 对 Task 1 要求 `image_status == "ready"` **且** `image_check.status == "confirmed"`。未核对或跳过核对时 TA 和总分不可评，读数也不发给模型。确认后发给模型的说明改为“读数已由人对照题图核对”。
  - **网页**：读完图后三项生成都停在 queued（额度已在提交时计入）。页面在题图下用文本框逐行列出读数（每个数据点一行），有两个按钮：
    - “读数无误，开始批改”：框内改过的以改正后的为准，模型原始读数存进 `image_check.model_description`；没改则保留模型原文。
    - “不核对，只看语言反馈”：不评 TA 和总分。
    - 端点 `POST /api/submissions/<id>/image-check`（`{"action": "confirm", "description": ...}` 或 `{"action": "skip"}`）带 CSRF、只限本人、只能一次。读数为空、超 2500 字或动作无效返回 422；已核对、Task 2 或无需核对返回 409。
    - 等待期间“重新生成”返回 409；服务重启后等待核对的生成不会被判为中断；页面不轮询，正在改的读数不会被刷新掉。
    - 提交表新增可空列 `image_check`，与 `copied_spans` 一样在旧库启动时自动补列。
  - **realcheck**：
    - `--images-only` 额外写 `image_check.md`（题图路径、sha256、逐行读数）。
    - 新命令 `realcheck-check-images`：`--sheet` 只写核对表；`--confirm id,... --by 核对人 [--corrections {id: 改正后的完整读数}] --out` 写出带核对记录（核对人、时间、题图 sha256、是否改正、改正时保留模型原始读数）的第 2 版读数文件，不覆盖已有的不同文件。
    - `--require-checked-images` 要求每篇带图的 Task 1 都已核对，且题图与核对时逐字节相同。
    - 未核对的读数只给语言反馈。`realcheck-batch` 没有核对环节，所以批次里的 Task 1 不再评 TA。
    - 对照指纹只在有核对记录时加入（旧报告不变）。
  - **新模块** `imagecheck.py`（核对表、确认、记录校验），没有往 `realcheck.py` 堆逻辑。
- **验证**：
  - `$V/python -m unittest discover -s tools/ielts_writing_ai/tests -t .` → **483 OK**，三种 locale 都 OK。新增 `test_image_check_20261113.py` 13 项，用合成折线图复现“格式正确、数值读错”；`TokenBoundaryTest` 2 项。原来假定“格式可用就评 TA”的 5 项已改为先确认（含一项现在正确地拒绝对照“未核对 vs 已核对”的两次运行）。
  - Node 8、ruff、black、`node --check`、`git diff --check` 通过。
  - **真实浏览器**（Playwright + Chromium，演示模型）：提交带图 Task 1 → 显示待核对说明和 14 行读数、右侧“请先核对” → 改正读数并等待 3 秒，改动没被刷新 → 确认后核对框消失，读数标“按你的改正”，出现 TA/CC/LR/GRA 分数；页面无脚本错误。
  - 与 `.14` 比较 30 篇本地作文的评价消息：27 篇逐字相同；3 篇带确认读数的 Task 1 只差 `visual_note` 一句。
  - 复核探针：
    - `vision_budget_probe.py` **139/139**。
    - `confirmed_probe.py` 换合成替身样本后，词边界 10 项失败全部消失（`findings: []`）。剩下的 4 项里，3 项是官方实样词数（替身样本必然不符），1 项是迁移逐字段比较：原探针只去掉 `copied_spans`，没去掉新列 `image_check`。改编版 `verify/confirmed_probe_adapted.py` 要求新列存在且旧行为空，结果 **67/70**，剩下 3 项需要 Mac 上的真实样本。
    - 改编版抄题 / 识图探针 22/22、32/32。
    - 历史探针全量重跑，相比上一轮只有 `thinking-review-20261104/compare_probe.py` 由 0 变 1。它用两份未核对、只差一个数值的读数构造“评价输入不同”，`.15` 起未核对读数不发给模型，两边输入相同。这正是本次要的行为，不是回归。
- **未变**：抄题“相似仅提示、确认才排除”、段落、DeepSeek 读图请求参数、评价模型与参数、账本。未合并 main、未部署、未访问生产，小程序未上传、提审或发布。本轮没有付费调用。
- **下一步**：
  1. Codex 复核 `.15`。可在 Mac 上用真实样本跑 `verify/confirmed_probe_adapted.py`（预期 70/70）和 `paragraph_probe.py`。
  2. 复核通过后，再把 Mac 试用服务换到 `.15`。识图仍保持 `none`，等用户决定后再开。
  3. Task 1 新批次需要用户另行授权，并决定读错时“改正后继续评 TA”还是“照旧停批”（见 `official-run.md` 第六版）。
  4. 老师填写 10 条抽查后汇总。

## 日志条目（并入 `WORKLOG.md`）

### 2026-11-13（夜）— 写作 AI 试用工具：确认抄题词边界；题图读数经人核对才评 TA（.15）

- `89e8c7c`：quote 片段不能截断计词 token，151→149 的重复扣词已修。
- `9339cdb`：网页读完图先让提交的人核对（可改正），确认后才批改，或选只看语言反馈；realcheck 新增 `image_check.md` 核对表、`realcheck-check-images` 和 `--require-checked-images`。未核对的读数不评 TA、不发给模型。
- 483 项 Python（三种 locale）+ 8 项 Node 通过，真实浏览器走通核对流程。未调用真实模型，只推功能分支。
