# StudyTracker — 工程约定（给人类 & AI agent 共同遵守）

> 本文件是“防止代码变屎山”的硬约定。**任何人或 AI agent 在本仓库写代码前，先读这里。**
> 详细架构地图见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 跨机器进度同步（多台电脑开发）

- **每次会话开工时，先读 [docs/WORKLOG.md](docs/WORKLOG.md)**——最近干了什么、生产现场状态、下一步待办都在那里（本地记忆不跨机器，git 才是同步载体）。
- 有实质进展的会话**结束时向 WORKLOG.md 顶部追加一条**并随代码一起提交；git 之外的状态（生产库操作、服务器手动步骤）必须记进去。
- 题库导入类操作照 [docs/IMPORT_PIPELINES.md](docs/IMPORT_PIPELINES.md) 手册执行。

## 项目是什么

托福/雅思学习追踪系统，两端：

- **后端**：Flask + SQLAlchemy（Python 3.13）。入口 `app.py`，API 蓝图在 `api/`，数据模型在 `models.py`，配置在 `config.py`。
- **小程序前端**：微信小程序，在 `miniprogram/`。按角色分 `pages/student`、`pages/teacher`、`pages/parent`。

## 两条独立部署链路（务必分清）

- **后端**：`git push` 到 `main` 即触发 GitHub Actions（`.github/workflows/deploy.yml`）SSH 到服务器跑 `/usr/local/sbin/deploy-studytracker`。
- **小程序前端**：**必须用微信开发者工具手动上传、提审、发布**。改了 `miniprogram/` 不会因为 push 而上线，也不需要先 commit 才能上传。
- 改了后端接口、前端又在调它时：**先确认后端已部署**，否则前端会打到一个还没上线的接口。

## 生产环境硬约束（agent 经常踩，先记住）

- 生产 gunicorn **必须** `workers=1` + gthread + `threads=6`；多 worker 会因 Kokoro 重复加载 **OOM**。
- 生产端口是 **5002**，不是 5000。
- **禁止在生产机跑本地重模型推理**（Whisper / Kokoro 大模型常驻会吃满内存饿死全机）；口语走腾讯 SOE + 阿里云 ASR 云服务。

---

## 写新代码的硬规则（这些是防屎山的核心）

### 后端

1. **不要再往 `app.py`（9k 行）和 `api/miniprogram.py`（5k 行）堆东西。** 新接口放进**对应主题的蓝图**（`api/dictation.py`、`api/materials.py`、`api/entrance.py`…）；没有合适的就**新建一个蓝图文件**，别图省事塞进巨型文件。
2. **路由函数保持瘦。** 单个函数目标 < 60 行。校验、判分、统计、写库这类逻辑抽成独立的 `_helper()` 函数或放进 service 模块，路由只做“收参数 → 调逻辑 → 返响应”。
3. **不要再各写各的 `_normalize_*`。** 文本/答案清洗类函数目前在 7 个文件里重复。新的归一化逻辑放进**共享模块**（见 ARCHITECTURE 的 backlog），需要时复用：
   - 已有 `api/dictation.py` 的 `_normalize_english_phrase` / `_normalize_chinese_translation`；
   - 答案判对的归一化对齐 `api/dictation.py` 的现有匹配逻辑。
4. **DB 查询尽量复用既有模式**，别在每个 handler 里重发明一套 filter 链。
5. **`models.py`**：新模型按主题分组放置；**不要往 `# ---- Legacy models` 区块加东西**，那是待删的旧代码。

### 小程序前端

1. **所有网络请求必须走 `miniprogram/utils/request.js` 的 `request()` 封装**——它统一处理鉴权、401、访客模式。**禁止直接 `wx.request`**（目前有 5 个页面违规，是反面教材，别学）。
2. **不要再往 `pages/student/hammer/index.js`（2.2k 行、97 个 state 字段）加东西。** 它已经过载；新功能拆子模块/组件。
3. **访客模式**统一用 `utils/demo-data.js` 的 builder + 共享判断，别每个页面复制粘贴 `guestMode` 逻辑（目前已复制 33+ 次）。
4. **样式**：公共按钮/卡片/配色优先抽到共享 wxss / `app.wxss`，别在每个页面内联重复（改个按钮色不应该要动 5~10 个文件）。

### 通用

- **改动尽量小而聚焦**，一个 commit 一件事。
- **删代码前先确认它真没用**（grep 引用），尤其 `models.py` 的 legacy 区块要单独评估。
- 提交信息中文 OK，说清“做了什么/为什么”。

---

## 本地开发 & 测试

```bash
# 安装运行依赖
pip install -r requirements.txt
# 安装开发/工具依赖（lint、格式化、测试）
pip install -r requirements-dev.txt

# 跑测试（unittest）
python -m unittest discover -s tests -p "test_*.py"

# 代码检查 / 格式化（不会自动改业务逻辑，只查风格与明显错误）
ruff check .          # 查问题
ruff check --fix .    # 自动修可安全修复的
black .               # 格式化（先看 diff 再提交）
```

> 注意：完整测试套件会拉起 `app.py`，需要安装全部依赖（含较重的 whisper/kokoro/weasyprint）。
> 纯逻辑/脚本测试不依赖这些，可单独跑。

## 提交前自检（可选但推荐）

```bash
pip install pre-commit && pre-commit install   # 装一次
# 之后每次 git commit 会自动跑 ruff/black/基础检查
```
