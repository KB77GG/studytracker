# AGENTS.md — 给 Codex / AI coding agent 的入口指引

> 本仓库同时有 `CLAUDE.md`（人类 & AI 共同遵守的工程约定，**务必先读**）。
> Codex 不会自动读 CLAUDE.md，所以这里把它列为第一入口。

## 先读

1. **`CLAUDE.md`** — 项目是什么、两条独立部署链路、生产硬约束、写新代码的防屎山硬规则。**动手前必读。**
2. 详细架构见 `docs/ARCHITECTURE.md`。

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
