# Reading Study Phase 1 · 正式版实施计划

> 本文档是可独立执行的实施说明书。执行者（Claude Opus / Codex / 人类）在动手前先通读本文与 `CLAUDE.md`。
> 产品需求原文见 `docs/reading_study_generation_standard.md`（数据格式）与本仓库既有讨论；本文只包含**已确认**的决策，不要重新发明方案。

## 0. 背景与现状（已完成的部分，不要重做）

- 每篇阅读 Passage 的句子级解析（翻译/结构拆解/难点/表达）已**离线预生成**为 JSON：`data/reading_study/{passage_id}.json`，格式见 `docs/reading_study_generation_standard.md`，校验器 `scripts/validate_reading_study.py` 全绿。
- 当前覆盖：**剑桥雅思 reading_test 204/204 全部完成**；reading_jijing 机经 113/171（其余 58 篇陆续补齐，导入脚本必须支持增量重跑）。
- 可视化交互原型已验收：`data/reading_study/browse.html`（双栏布局、句子点击、5 模块解析、语法术语点击弹窗）。**正式版前端以它为视觉与交互基准**。
- 运行时**不调用任何 AI**。生产只做：一次性导入 → 只读查询。

## 1. 总体架构（已确认，勿改）

```
data/reading_study/*.json ──(scripts/import_reading_study.py: 校验+role归一化+content_hash)──▶
  DB 表 reading_passage_analysis（每 Passage 一行,payload 为归一化 JSON）
  DB 表 student_saved_expression（学生收藏表达,按学生+归一化文本去重）
        ──▶ api/reading_study.py 蓝图（页面路由 + 只读 API + 收藏 API）
        ──▶ templates/reading/study.html + static/js/reading_study.js + static/css/reading_study.css
入口：reading/test_practice.html 增加 Reading Study 按钮（模考 exam_context 下隐藏）
```

## 2. 硬约束（违反任何一条都算实现错误）

1. **不往 `app.py`（9k 行）和 `api/miniprogram.py` 加任何代码**。新代码全部进新文件；入口按钮通过前端 fetch 判断，避免改 app.py 路由。
2. 路由函数保持瘦（< 60 行），校验/查询/组装逻辑抽 `_helper()`。
3. 蓝图在 `api/__init__.py` 的 `init_app()` 里注册，模式照抄现有蓝图。
4. 新模型加在 `models.py` 的 Mock Exam 区块之后，新开分组注释 `# ---- Reading Study (阅读句子解析) ----`；**不碰 Legacy 区块**。
5. 生产脚本**不得 `from app import app`**（避免在生产机重复加载 app 带来的内存风险）：导入/建表脚本用「最小 Flask app」模式（见 §4.3）。
6. 第一期不做：小程序端、SRS、AI 仿写、行文逻辑、按学生生成、生句收藏。
7. 提交遵守仓库惯例：`ruff check .` + `black .` 通过；新增测试用 unittest,可用 `.venv/bin/python -m unittest ...` 单独跑。

## 3. Role 归一化（本计划的核心技术点）

离线生成的 `structure[].role` 是自由 snake_case，共 **1449 种**；高频 60 种覆盖 85.7%，长尾有规律后缀。**导入时归一化成封闭概念词表,前端不再带解析器。**

- 参考实现（必须移植,不要重写规则）：`data/reading_study/browse.html` 内 `<script>` 里的
  `CONCEPTS`（≈35 个概念,含 zh/en/camp/desc/ex 讲解文案）、`FLAVORS`（时间/目的/条件…语义前缀）、`EXACT`（精确映射表）、`resolveRole()`（后缀/词干规则,含兜底）。
- 移植到 Python 模块 `api/reading_study_glossary.py`，导出：
  - `CONCEPTS: dict[str, dict]`（key=概念 id；值含 en/zh/camp/desc/ex）
  - `resolve_role(role: str) -> dict`：返回 `{concept, zh, en, camp}`；带 flavor 的返回如 `zh="目的状语从句", en="Purpose Clause"`（concept 仍是 `adverbial_clause`）
  - `glossary_payload() -> dict`：给前端的完整词典（概念讲解 + camp 中文名）
- 入库时给每个 structure 项**增加** `concept`/`label_zh`/`label_en` 字段，**保留原始 `role`**（便于日后重归一化）。
- 概念词表（封闭,共 36）：`subject, verb_phrase, object, predicative, object_complement, complement, main_clause, coordinate_clause, relative_clause, noun_clause, adverbial_clause, prepositional_phrase, participial_phrase, infinitive_phrase, gerund_phrase, non_finite_clause, apposition, parenthesis, adverbial, linking_verb, passive_predicate, existential_clause, reporting_clause, direct_speech, attribution, discourse_marker, conjunction, formal_subject, absolute, comparative, cleft, inversion, adjective_phrase, noun_phrase, generic_phrase, heading`。

## 4. Phase A · 后端

### 4.1 models.py 新增两个模型

```python
# ---- Reading Study (阅读句子解析) ----

class ReadingPassageAnalysis(db.Model, TimestampMixin):
    __tablename__ = "reading_passage_analysis"
    id = db.Column(db.Integer, primary_key=True)
    passage_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    test_id = db.Column(db.String(64), nullable=False, index=True)      # 如 ielts16_test2_reading
    source_kind = db.Column(db.String(32), nullable=False, index=True)  # reading_test / reading_jijing
    passage_title = db.Column(db.String(255), nullable=False)
    difficulty = db.Column(db.String(16), nullable=False)               # simple/medium/complex
    schema_version = db.Column(db.Integer, nullable=False, default=1)
    generation_standard = db.Column(db.String(32), nullable=False, default="reading_study_v1")
    content_hash = db.Column(db.String(64), nullable=False)             # 源文段落归一化后的 sha256
    sentence_count = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(16), nullable=False, default="ready")
    payload_json = db.Column(db.Text, nullable=False)                   # 归一化后的完整解析 JSON

class StudentSavedExpression(db.Model, TimestampMixin):
    __tablename__ = "student_saved_expression"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profile.id"), nullable=False, index=True)
    text = db.Column(db.String(255), nullable=False)
    normalized_text = db.Column(db.String(255), nullable=False)         # lower + 空白折叠
    meaning_zh = db.Column(db.String(255), nullable=False, default="")
    source_kind = db.Column(db.String(32), nullable=False, default="")
    passage_id = db.Column(db.String(64), nullable=False, default="", index=True)
    sentence_id = db.Column(db.String(16), nullable=False, default="")
    __table_args__ = (db.UniqueConstraint("student_id", "normalized_text", name="uq_saved_expression_student_text"),)
```

> 注意：`student_profile` 的实际 `__tablename__` 以 models.py 现状为准（先查 `StudentProfile` 定义再写 FK）；字段风格对照 `StudentSavedWord`。

### 4.2 api/reading_study_glossary.py

见 §3。纯 Python、无 Flask 依赖、可单测。

### 4.3 scripts/import_reading_study.py（建表 + 导入一体）

- **最小 app 模式**（不 import app.py）：

```python
from flask import Flask
from config import Config          # 以仓库实际 config 类名为准
from models import db, ReadingPassageAnalysis

def _make_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app
```

- 流程：
  1. `--create-tables`：`db.create_all()`（幂等）。
  2. 扫描 `data/reading_study/*.json`，跳过非解析文件（顶层 keys 不符则忽略，如 preview.html 同目录的其他文件只认 `.json` 且校验 keys）。
  3. 复用 `scripts/validate_reading_study.py` 的 `load_source_passages()` + `validate_sample()` 逐篇校验，不合格**跳过并计数**（不中断整体）。
  4. `content_hash`：对源文各段 `normalize_space` 后按 label 排序拼接，取 sha256。
  5. 归一化：每句 `structure[]` 每项加 `concept/label_zh/label_en`（调 glossary 模块）。
  6. Upsert（按 `passage_id`）：新纪录插入；已存在且 `content_hash` 与 payload 相同则跳过；不同则覆盖并打印。
  7. `--dry-run` 只报告不写库。结束打印 summary：新增/更新/跳过/失败。
- **增量特性是必须的**：58 篇机经补齐后会再跑一次同一脚本。

### 4.4 api/reading_study.py 蓝图

`reading_study_bp = Blueprint("reading_study", __name__)`,在 `api/__init__.py` 注册。

页面路由：
- `GET /reading/study/<test_id>` → 查 `ReadingPassageAnalysis.query.filter_by(test_id=...)`；无任何 ready 记录返回 404；渲染 `reading/study.html`,注入 `test_id`、按 p1/p2/p3 排序的 passage 元信息列表（id/title/difficulty/sentence_count）、返回练习页的 URL。

API（JSON）：
- `GET /api/reading-study/catalog?test_id=<id>` → `{"test_id":..., "passages":[{passage_id,title,difficulty,sentence_count}]}`；无 test_id 时返回全部（按 source_kind 分组,给未来目录页用）。
- `GET /api/reading-study/passage/<passage_id>` → payload_json 原样返回（已含归一化 concept）。404 当不存在。
- `GET /api/reading-study/glossary` → `glossary_payload()`。
- `GET /api/reading-study/expressions?passage_id=<id>` → 当前学生在该篇已收藏的 `normalized_text` 列表；未登录/未验证返回 `{"student": null, "saved": []}`。
- `POST /api/reading-study/expressions` body `{text, meaning_zh, passage_id, sentence_id, source_kind}` → 去重保存；无学生身份返回 401 + `{"error":"need_student"}`。
- `DELETE /api/reading-study/expressions`（body 带 `text` 或 query `normalized_text`）→ 取消收藏。

学生身份：复用 web 练习页的现有机制 `_current_practice_student_profile()`（app.py:1470，session 轻量姓名验证 + 正式账号）。**不要复制实现**——把该函数所需逻辑抽薄封装或直接 `from app import ...` 会违反约束 5？不会：蓝图在应用运行时被 app.py 加载,循环引用风险高。**做法**：在蓝图内实现一个瘦 `_current_student()`,只读 `flask_login.current_user` 与 `session["practice_student_name"]` 查 `StudentProfile`,逻辑对照 app.py:1470 保持一致（约 15 行,可接受的少量重复,并加注释指向原函数）。

### 4.5 测试（tests/test_reading_study.py 起步,可拆多文件）

1. glossary：高频精确映射（subject/relative_clause/…）、flavor 组合（purpose_clause→目的状语从句）、兜底(未知标签)。
2. import：临时 sqlite + 两个小样例 JSON（fixture 可放 tests/fixtures/）→ 首跑插入、二跑全 skip、改 payload 后重跑 update、坏 JSON 跳过不炸。
3. API：建内存 app 注册蓝图 → catalog/passage 404 与 200、expressions 未登录 401、登录后保存→重复保存不新增→列表→删除。
4. 全部用 unittest,能 `.venv/bin/python -m unittest tests.test_reading_study -v` 单独跑。

## 5. Phase B · 前端

以 `data/reading_study/browse.html` 为基准移植,拆成三件套：
- `templates/reading/study.html`：骨架 + Jinja 注入（test_id、passages、返回链接）。顶部不再要 Test 下拉（单 Test 范围）,保留 Passage 1/2/3 tab（用注入的元信息渲染,不再前端探测）。Practice/Reading Study 模式切换按钮：Practice 链接回 `/reading/test/<test_id>`（或 jijing 对应页）。
- `static/css/reading_study.css`：照搬 browse.html 全部样式（含 `.g-*` 弹窗、`.role` 可点击样式、响应式断点）。
- `static/js/reading_study.js`：
  - 数据源改为 API：`/api/reading-study/passage/<pid>`、`/api/reading-study/glossary`（页面加载取一次并缓存）。
  - 标签渲染直接用后端归一化的 `label_zh/label_en/concept`,弹窗内容查 glossary（按 concept）。**删除前端 resolveRole 解析器**。
  - 「加入表达库」接真实 API：进页面拉 `/api/reading-study/expressions?passage_id=` 标记已收藏；点击 POST/DELETE 切换;401 时弹提示引导先在练习页完成姓名验证（给出跳转链接）。

入口改造（唯一允许触碰的既有文件是模板,不碰 app.py）：
- `templates/reading/test_practice.html`：页面头部加一个隐藏的 `Reading Study` 按钮；`{% if not exam_context %}` 才渲染该节点（**模考绝不出现**）;页面 JS 启动时 fetch `/api/reading-study/catalog?test_id=当前id`,有 ready passage 才显示按钮,点击去 `/reading/study/<test_id>`。
- `templates/reading/test_index.html` 与 `jijing_index.html`：每套 Test 行尾加小链接「学习」,同样由一次 catalog fetch（不带 test_id,拿全量后端已分组数据）控制显隐;实现简单为先,不追求首屏零闪烁。

## 6. Phase C · 本地验证（执行者必须做完再交付）

1. `.venv/bin/python scripts/import_reading_study.py --create-tables && .venv/bin/python scripts/import_reading_study.py` → summary 全部 ready(≈317)。
2. `.venv/bin/python -m unittest tests.test_reading_study -v` 全绿;`ruff check .`、`black --check .` 通过（只格式化自己新增/改动的文件）。
3. 起本地 flask（`.claude/launch.json` 的 `flask` 配置,端口 5001）,浏览器走通：
   - `/reading/tests` 出现「学习」入口 → `/reading/study/ielts16_test2_reading` 双栏渲染、切 P1/P2/P3、点句子出 5 模块、点语法标签弹讲解;
   - 收藏表达：未验证身份 → 提示;完成姓名验证后保存/取消/刷新保持;
   - 模考页确认无 Reading Study 按钮。
4. 移动宽度(≤640px)抽查一屏。

## 7. Phase D · 部署 runbook（需用户确认后执行）

1. `data/reading_study/*.json` 与代码一起 commit（preview/browse.html 两个原型文件**不提交**,留本地;或移入 scratch）。push → GitHub Actions 自动部署后端。
2. SSH 到服务器（部署走 `studydeploy` 用户,生产目录 `/root/apps/studytracker`,DB `/root/apps/studytracker/app.db`,端口 5002）：
   ```bash
   cd /root/apps/studytracker
   .venv/bin/python scripts/import_reading_study.py --create-tables
   .venv/bin/python scripts/import_reading_study.py
   ```
   导入是纯 IO,不加载任何模型,不影响 gunicorn(workers=1 + gthread)。
3. 生产验证:`/reading/study/ielts16_test2_reading` 可打开;模考页无入口。
4. 后续 58 篇机经补齐后:重新 commit 数据 + 服务器重跑 import(增量)。

## 8. 明确不做（Phase 1 边界,再确认一次）

生句收藏、AI 仿写、行文逻辑分析、阅读总结、SRS、单词复习、小程序页面、学生触发的实时 AI 生成、表达库的复习页(只做保存)。

## 9. 验收标准

- [ ] 剑桥雅思任一 Test 从练习列表两跳内进入 Reading Study,切句流畅（纯 DB 读,无 AI 调用）。
- [ ] 每句 5 模块完整;语法标签点击弹「阵营+讲解+例句」,1449 种原始 role 全部有合理归类,无「点了没反应」。
- [ ] 收藏表达跨刷新持久,同一表达对同一学生只存一条。
- [ ] 模考模式看不到任何 Reading Study 入口。
- [ ] app.py 与 api/miniprogram.py 的 diff 为 0 行。
- [ ] 测试、ruff、black 全绿;导入脚本幂等可增量。
