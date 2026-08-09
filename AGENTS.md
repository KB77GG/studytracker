# AGENTS.md — 给 Codex / AI coding agent 的入口指引

> 本仓库同时有 `CLAUDE.md`（人类 & AI 共同遵守的工程约定，**务必先读**）。
> Codex 不会自动读 CLAUDE.md，所以这里把它列为第一入口。

## 先读

1. **`CLAUDE.md`** — 项目是什么、两条独立部署链路、生产硬约束、写新代码的防屎山硬规则。**动手前必读。**
2. **`docs/CODEX_HANDOFF.md`** — 跨账号、跨任务或跨电脑继续开发时的规范事实源，记录当前进度、验证结果、发布状态和下一步。
   读取后必须用 `git status --short --branch` 和 `git log -5 --oneline` 核对，不能把可能过期的交接记录当成唯一事实来源。
3. 详细架构见 `docs/ARCHITECTURE.md`。

## 跨账号 / 跨任务 / 跨电脑进度交接

- 本机可能由多个 Codex 账号轮流工作。聊天记录和账号记忆不作为交接依据；仓库文件、实际 Git 状态和可复现验证结果才是事实源。
- 开工时先读 `docs/CODEX_HANDOFF.md` 和 `docs/WORKLOG.md`，再核对当前 worktree 绝对路径、分支、HEAD、远端跟踪状态和工作区改动；工作区不干净时不要盲目 `pull`、切分支或覆盖文件。
- **每个项目任务结束前必须执行交接审计。** 只要本轮有代码、数据、配置、文档、验证结论、部署/外部状态、阻塞项或下一步变化，就滚动更新 `docs/CODEX_HANDOFF.md`，并在 `docs/WORKLOG.md` 顶部追加简短记录；若无可持久化变化，也要确认现有交接仍准确并在最终回复中说明无需更新。
- 交接必须写明：worktree 绝对路径、分支/HEAD、既有与本轮未提交或未跟踪改动、完成事项、精确测试与结果、后端/小程序/数据库的发布状态、未验证项、阻塞项和下一位 agent 可直接执行的下一步。
- 只保留当前仍有用的状态与少量近期记录，不粘贴聊天流水账；不要写密码、令牌、Cookie、学生隐私或其他敏感信息。
- 同一 macOS 用户下切换 Codex 账号可读取本机未提交文件；另一台电脑只能取得已经 commit 并 push 的内容。未提交或未跟踪文件必须列出路径和用途；需要跨电脑接续的进行中代码应在得到授权后放到任务分支、提交并推送。
- `commit` / `push` 仍然只在用户明确要求时执行；没有授权时只更新本地交接文件，并在结果中说明尚未同步到远端。
- 最终回复必须说明本轮交接更新到了哪些文件，以及当前是否仅本机可见、是否已 commit/push/deploy。

## 专项任务：导入新的《9分达人听力》书

如果任务是「把某本 9分达人听力导入刷题/精听系统」：

- **严格按 `docs/jfdr_import_runbook.md` 执行**（自包含手册，含每一步命令、参照文件、血泪坑、上线顺序）。
- 书 6（`jfdr6`）已完整上线，是金标准参照。
- 关键前提（手册里有细节，这里先划重点，别踩）：
  - 后端/目录/前端对任意 `jfdr{书号}` **已零改动支持**（`api/listening_series.py`），**不要改后端代码**。
  - 只需把 3 个流水线脚本（`scripts/prepare_jfdr6_assets.py` / `align_jfdr_listening.py` /
    `build_jfdr6_listening.py`）参数化成吃 `--book`（默认 6，向后兼容）。
  - 子 agent 提取用 **opus**（默认模型会撞用量上限）。
  - 对齐必须 **`--method lcs`**（默认）。
  - 判分自测用 `scripts/grade_jfdr_selfcheck.py --book N`（不要依赖 dev server，它会崩）。
  - 上线顺序：先 rsync mp3 → 再 push 后端（push main 触发部署）→ 验证生产 5002 → 小程序前端由人手动发版。

## 通用护栏（来自 CLAUDE.md，最容易被忽略的几条）

- 生产 gunicorn **必须** `workers=1` + gthread + `threads=6`；多 worker 会因 Kokoro 重复加载 **OOM**。
- 生产端口是 **5002**，不是 5000。
- **禁止在生产机跑本地重模型推理**（Whisper/Kokoro 常驻吃满内存）；对齐/转写只在本地 Mac 跑。
- 不要再往 `app.py`、`api/miniprogram.py` 这两个巨型文件堆代码；新逻辑拆蓝图/共享模块。
- 本地跑 Python 用 `.venv/bin/python`（系统 python3 缺依赖）。
- commit/push 只在明确被要求时做。
