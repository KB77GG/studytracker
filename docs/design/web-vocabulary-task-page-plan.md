# 网页背单词任务页：文件级实施计划

> 角色：Claude 出计划，Codex 执行。本文只是计划，不含产品代码改动。
> 需求来源：用户 2026-11-26 在 Claude 会话里给出的完整需求（Codex 在 Mac 本机整理，`docs/requirements/web-vocabulary-task-page.md` 未推送，仓库里不存在）。本文按该需求第 5 节的 8 项组织，需求原文以用户消息为准。
> 视觉方案：同目录 `web-vocabulary-task-page-prototype.html`（可交互状态稿，含 token、各状态布局和键盘规则演示；浏览器直接打开）。同一份已发布为私有 Artifact：https://claude.ai/artifact/2NvKaLykargHtu51ddT1DT（需用户分享后他人才能打开）。产品 CSS 以原型里 `.pv` 作用域的样式为起点，把 `@container` 改为 `@media`。

## 0. 核查基线与结论速览

**核查基线（Claude 云端，2026-11-26）**

- 仓库 `KB77GG/studytracker`，分支 `claude/clever-heisenberg-8evbm0` 与 `origin/main` 均为 **`f81a5e4a4d81282eb67b994a4cfcc5574fb78747`**，工作区 clean。已全量 fetch 远端 67 个分支，任何分支和历史里都没有 `docs/requirements/`。
- 用户转贴的 f81a5e4 已核实一致。Mac 旧树 `main@6ded77d2`（落后 157 提交、有既有脏改动）**不能**作为开发基线。
- 基线回归（隔离 venv，Python 3.13，按 CI 轻依赖安装）全部通过：
  - `python -m unittest tests.test_vocabulary_group_learning tests.test_vocabulary_group_learning_api tests.test_vocabulary_autonomous_review tests.test_vocabulary_flow_backlog_gate tests.test_auto_student_accounts tests.test_miniprogram_grading`：102 个通过。
  - `tests.test_task_date_gate tests.test_task_date_gate_display_contract`：5 个通过，需要 `pytest` 包。
  - `node --test tests/test_practice_task_lists.js tests/test_practice_shell.js tests/test_vocabulary_feedback.js`：27 个通过。

**结论速览**

| 项 | 决定 |
|---|---|
| 首版范围 | 只接 **v2 词汇任务**：`dictation_book_id` 非空，且 `vocabulary_goal ∈ {reading, listening, writing, comprehensive}`（`services/vocabulary_mastery.py:is_vocabulary_v2_task`）。旧听写、拼写训练、数字听写（`vocabulary_goal` 为空）保持原状，不出现在网页任务列表 |
| 页面 | `GET /practice/vocabulary/tasks/<task_id>`，新蓝图 `api/practice_vocabulary.py` |
| 后端新文件 | `services/practice_student_identity.py`、`services/practice_vocabulary_web.py`、`services/practice_vocabulary_tasks.py`、`services/task_plan_item_sync.py`、`services/vocabulary_task_submission.py` |
| 巨型文件改动 | `app.py` 约 20 行（查询条件和 payload 分支委托）；`api/miniprogram.py` 只把 PlanItem 同步和 v2 结算换成调用共享服务，行为不变 |
| 前端新文件 | `templates/practice/vocabulary_task.html`、`static/css/practice_vocabulary.css`、`static/js/practice_vocabulary_core.js`（纯逻辑，UMD，可 node 测）、`static/js/practice_vocabulary_render.js`、`static/js/practice_vocabulary_page.js` |
| 数据库迁移 | **不需要**，依据见 §7.4 |
| 小程序 | 不改、不上传 |

---

## 1. 首版任务矩阵

### 1.1 目标 → 阶段 → 题型（全部来自 `services/vocabulary_group_learning.py` 和 `services/vocabulary_mastery.py:_question_for`）

| 目标（列表标签） | 每组词数 | 阶段（服务端 `phase`） | 出现的 `mode` | 计分 |
|---|---|---|---|---|
| reading（阅读词汇） | 10 | familiarity → active_recall → context_discrimination → context_production → retry | active_recall：`en_to_zh`（meaning_recall）；辨析：`context_choice`（meaning_choice 或 collocation_choice）；产出：`context_fill`（example_fill 或 collocation_fill） | 有产出题时辨析题为 guide、不计分，产出题计分；无产出题时辨析降级为 degraded、计分 |
| writing（写作词汇） | 8 | 同上 | active_recall：`zh_to_en`（form_recall）；辨析和产出同上 | 同上 |
| listening（听力词汇） | 8 | familiarity → active_recall → retry（无语境维度） | `audio_to_zh`（meaning_recall，服务端 options，选择）＋ `audio_to_en`（audio_form_recall，拼写） | 每个 (sense, dimension) 计一次 |
| comprehensive（综合训练） | 6 | familiarity → active_recall（base_recall）→ context_discrimination（base_context）→ retry（有冷却）→ 关联维度补救波 | `zh_to_en`；语境题优先 `context_choice`，无可用选择题时为 `context_fill`（**`context_fill` 可能出现在 context_discrimination 阶段**）；补救题 `remediation_kind=related_dimension`，mode 取关联维度 | 首答计分；补救题不计分；**只有该目标有“立即订正”** |
| 任一目标中的数字/日期词 | — | 强制走 listening 构建 | `audio_to_zh` ＋ `audio_to_en`（`answer_type=numeric`，带 `prompt.input_hint`） | 同 listening |
| 课堂同义词（synonym sense） | — | meaning/form recall | `context_fill`（`prompt.sentence = "cue = ____"`） | 同所在维度 |

渲染规则：**渲染器只按 `mode` 分派，阶段只决定标签和进度条**。不能假设“某阶段一定是某题型”（综合目标的 `context_fill` 会出现在辨析阶段，同义词的 `context_fill` 会出现在主动提取阶段）。

### 1.2 六种题型的渲染与操作

| mode | 作答前展示 | 输入方式 | 提交值 | 作答前音频 | 作答前禁止展示 |
|---|---|---|---|---|---|
| `en_to_zh` | `prompt.word`、`prompt.phonetic`、`prompt.instruction` | 单行文本，`lang="zh"`，最长 200（服务端上限） | 文本 | 允许（词本身已展示） | 释义、例句译文 |
| `zh_to_en` | `prompt.meaning`、指令 | 单行文本，`lang="en"`，`maxlength=answer_length`（100） | 文本 | **不提供**（读音即答案） | 词形、音标、例句 |
| `audio_to_en` | 播放按钮、指令；数字题另显示 `prompt.input_hint` | 单行文本，`lang="en"`，`maxlength=answer_length` | 文本 | 主体 | 音标（服务端虽下发 `phonetic`，小程序不展示，网页保持同难度）、词形 |
| `audio_to_zh` | 播放按钮、4 个中文释义选项 | 单选（radiogroup） | **选项 label 文本**（与小程序 `selectedOptionLabel` 一致；服务端按中文判分） | 主体 | — |
| `context_choice` | `prompt.instruction`、`prompt.sentence`（meaning_choice）、`prompt.target_word`、`question.options` | 单选 | **选项 id** | 不提供 | — |
| `context_fill` | `prompt.instruction`、`prompt.sentence`（含 `____`）、`prompt.translation` 和 `translation_label` | 单行文本，`lang="en"` | 文本 | 不提供（会泄词） | 原句、目标词 |

作答后反馈统一展示：正误（图标＋文字）、`revealed_answer`、你的答案、反馈卡（词形、音标、释义、搭配、例句和译文、用法提示），以及反馈卡里的重播按钮。英文拼写题额外显示**拼写比对**：两串都已公开后，在客户端用 LCS 对齐。漏写的字母以主色补在原位，写错或多写的字母加删除线，用 `<ins>` 和 `<del>` 标签输出，读下来正好是正确拼写。缺失字段整块隐藏，不显示“暂无”，也不生成内容。

`audio_to_zh` 选项：服务端 `build_meaning_recall_options` 正常会下发 `question.options`。为空时（干扰项不足），小程序用组内熟悉材料的释义回退，见 `miniprogram/utils/vocabulary-interaction.js:buildMeaningChoiceOptions`。网页改为在**适配层**用同一算法（FNV 稳定哈希，目标＋3 个干扰项）服务端生成，理由见 §5.2(b)。

### 1.3 其他类型保持原行为

- `vocabulary_goal` 为空的旧听写（`dictation_mode` 为 audio_to_en、zh_to_en、en_to_zh、spelling_drill，含数字听写）：不进入 `/api/practice/tasks` 查询；`_practice_task_payload` 对其返回 `None`。小程序仍走 `pages/student/dictation/*`。
- 直接访问 `/practice/vocabulary/tasks/<旧任务 id>`：页面显示“该词汇任务请在小程序完成”（服务端错误码 `task_not_vocabulary_v2`），不提供作答。
- `services/web_practice_tasks.py:web_practice_required` **不改**：写作和题型专项强制网页完成，词汇任务两端都可做。
- 听力、阅读、题型专项、写作的 payload 分支顺序和内容不动，新分支放在 `else: return None` 之前。

---

## 2. 入口接线

| 关注点 | 文件 | 改动 |
|---|---|---|
| 查询条件 | `app.py:api_practice_tasks`（约 9391 行） | `or_(...)` 里加 `vocabulary_task_clause()`（来自新 service）。时间窗口和已完成状态的条件沿用 |
| 进行中状态 | `app.py:api_practice_tasks` | 循环前一次查询 `vocabulary_states = vocabulary_flow_states(profile, rows)`，把结果传给 payload。只读，不写 Task |
| payload | `app.py:_practice_task_payload`（约 9305 行） | 签名加关键字参数 `vocabulary_states=None`。在 `else` 前加 `elif is_vocabulary_v2_task(task):` 分支，委托 `vocabulary_practice_fields(task, state)` 取 `category`、`title`、`url`。如果工作流状态是 `pending` 且 flow 为 active，则 `status_key="in_progress"`、标签为“进行中”。原因：开始学习不会写 Task.status，见 §2.2 |
| 来源标签 | `app.py:_practice_task_source_label` | 加词汇分支，返回目标标签：阅读词汇、听力词汇、写作词汇、综合训练（措辞取自 `templates/task_planner.html`） |
| URL | `services/practice_vocabulary_tasks.py`（新） | `/practice/vocabulary/tasks/{task.id}`，不带 token，身份见 §3 |
| 标题 | 同上 | `task.detail` 优先，否则为“{book.title} · 第{start}–{end}词”（end 为空时显示“起”） |
| 完成状态 | 无需改 | finalize 写 `Task.status="done"`、`accuracy`、`completion_rate=100`，已有 `task_date_access` 和 `practice_task_lists.js` 会把任务归入“已提交 / 已完成”，卡片显示“正确率 x%”（即首答正确率） |
| 返回刷新 | `templates/practice/index_content.html` | 加 `window.addEventListener('pageshow', e => { if (e.persisted && verified) loadAssignedTasks(); })`。浏览器“后退”命中 bfcache 时也会刷新任务状态。新页面“返回任务列表”用 `location.assign`，本身会重新加载 |
| 分组 | 无需改 | 助教/老师分组靠 `created_by` 的角色；planner 生成的任务 `created_by` 是确认人（`services/task_planner.py:368`），可正常分组 |
| 开关（§9-4） | `config.py` | 加 `PRACTICE_VOCABULARY_WEB_ENABLED = _env_bool("PRACTICE_VOCABULARY_WEB_ENABLED")`，写法同第 45 行的 `VOCABULARY_ERROR_REVIEW_ENABLED`。关闭时 `vocabulary_task_clause()` 不并入查询，页面和 API 返回 `feature_disabled`，页面显示“暂未开放”。测试里显式打开 |

### 2.1 新文件 `services/practice_vocabulary_tasks.py`（约 120 行）

```python
GOAL_LABELS = {"reading": "阅读词汇", "listening": "听力词汇", "writing": "写作词汇", "comprehensive": "综合训练"}

def vocabulary_task_clause():
    return and_(Task.dictation_book_id.isnot(None), Task.vocabulary_goal.isnot(None), Task.vocabulary_goal != "")

def vocabulary_flow_states(profile, tasks) -> dict[int, str]:
    # 一次 IN 查询 VocabularyLearningFlow(student_id=profile.user_id, task_id ∈ v2 任务)，返回 {task_id: "active"|"completed"}
    # profile.user_id 为空时返回 {}（学生没有账号，网页页面也会拒绝，见 §3）

def vocabulary_practice_fields(task, flow_state) -> dict | None:
    # 不是 v2 任务返回 None；返回 category="词汇"、source_label、title、url、in_progress
```

SQL 条件只粗筛，最终以 Python 侧 `is_vocabulary_v2_task(task)` 为准（它会规范化大小写和非法 goal）。

### 2.2 不影响原任务的保证

- 新分支只在 `is_vocabulary_v2_task(task)` 为真时命中。v2 任务没有 `listening_exercise_id`、`reading_test_id`、`grading_mode=question_type_practice/writing_practice`，与前面分支互斥。
- 列表测试固定听力、阅读、题型专项、写作各一条，断言其 payload 字段**逐字段不变**（见 §8 A02）。
- `/api/student/practices/today` 和 `/api/listening/verify` 的计数不改（模板和静态资源里没有调用前者）。

---

## 3. 身份适配

### 3.1 现状（已核实）

- 网页学生身份：`app.py:_current_practice_student_profile()`。正式学生账号（Flask-Login，`role=student`）优先，其次是姓名会话 `session["practice_student_name"]`（`/api/listening/verify` 写入，只校验姓名存在）。教师或课堂模式下返回 None。
- 这套逻辑在 `api/writing_library.py`、`api/practice_history.py`、`api/question_type_practice.py`、`api/reading_study.py` 里各有一份重写，优先级不完全一致（practice_history 是姓名会话优先）。
- 词汇服务全部以 `User`（`user.id` 为 `student_id`）为键：DictationRecord、VocabularyLearningFlow、Question、Settlement、ReviewSession 都是。归属检查是 `user.student_profile.full_name == task.student_name`（`_task_owner`）。
- `api/auth_utils.py:require_api_user` 只认 Bearer。网页 Cookie 会话调不了 `/api/miniprogram/student/*`，也**不应**为网页签发 Bearer。

### 3.2 新文件 `services/practice_student_identity.py`（约 90 行）

```python
@dataclass(frozen=True)
class PracticeStudent:
    profile: StudentProfile
    user: User               # 词汇服务需要的学生账号
    via: str                 # "account" | "name_session"
    identity_key: str        # HMAC(SECRET_KEY, f"practice-vocab:{profile.id}:{user.id}")[:20]

class PracticeIdentityError(Exception): code, status

def resolve_practice_student() -> PracticeStudent  # 失败时抛 PracticeIdentityError
```

解析顺序与 `app.py` 一致，账号优先：

1. `current_user` 已登录、`role=student`、`is_active`：要求 `current_user.student_profile` 存在（`user_id` 关联），否则报 `student_account_unlinked`。写入路径不按 display_name 模糊回退。
2. 当前是教师或课堂模式（staff 角色，或 `session["classroom_unlocked"]`，或 Cookie `classroom_unlocked=="1"`）：报 `staff_mode`（403），页面显示“教师或课堂模式下不能代学生作答”。这与列表接口在教师模式返回空分组一致。
3. 姓名会话：`StudentProfile.query.filter_by(full_name=name, is_deleted=False).limit(2)`。
   - 0 条：弹出会话，报 `identity_missing`。
   - 2 条：报 `ambiguous_student_name`（409），文案“系统中有同名学生，请使用学生账号登录”。同名档案是允许的（`tests/test_auto_student_accounts.py:test_same_name_profile_is_not_merged`），不拒绝就可能写进别人的掌握记录。
   - 1 条：要求 `profile.user` 存在、`is_active` 且 `role=student`，否则报 `student_account_missing`（“学生账号未开通，请联系老师”）。
4. 其他情况：报 `identity_missing`，页面给出“前往练习中心确认身份”链接到 `/practice`。**不新增登录页。**

本任务不重构其他蓝图的重复实现，避免扩大范围，作为后续事项记录在交接里。

### 3.3 任务归属、会话归属、CSRF、日期门禁

- **任务归属**：`task = db.session.get(Task, task_id)`。不存在，或 `task.student_name != student.profile.full_name` 时，统一返回 404 `task_not_found`，不区分“不存在”和“不是你的”。服务内部 `_flow_or_error` 和 `_task_owner` 会再校验一次。
- **会话归属**：复习会话的读写都带 `session_token`，服务用 `_session_for_user(user, session_id, token, require_token=True)` 校验 `student_id == user.id`。改 URL 或请求体里的 `session_id` 会得到 404 或 409，不会串号。
- **CSRF**：蓝图 `before_request` 只拦 `/api/practice/vocabulary/`，沿用 `api/classroom_vocabulary.py` 和 `api/task_planner.py` 的模式。
  - 非 GET 请求必须是 JSON。
  - `X-CSRF-Token` 用 `compare_digest` 与 `session["practice_vocabulary_csrf"]` 比较。token 在页面路由里用 `session.setdefault` 生成，写进模板 `<meta>`。
  - 带 `Origin` 时其 host 必须等于 `request.host`。
  - `content_length ≤ 16KB`。
- **身份漂移**：所有写请求带 `X-Practice-Identity: <identity_key>`，与当前解析结果不一致时返回 409 `identity_changed`。例如另一个标签页“切换学生”后，旧页再提交会被拒，页面进入“身份已变化，请返回任务列表”。
- **日期门禁**：页面和 `state` 只读调用 `task_date_access(task)` 决定开放、截止、宽限、完成状态。所有写操作由服务内的 `_require_daily_clearance → assert_task_write_allowed` 把关，适配层**不重写**窗口逻辑。结算路径与小程序 `submit_task` 一致，先 `assert_task_write_allowed`。宽限期标签直接用 `access.label`（“宽限期内·03:00 截止”）。

---

## 4. 页面状态设计

> 可交互稿：`docs/design/web-vocabulary-task-page-prototype.html`。下文是实现约束，视觉细节以原型为准。

### 4.1 布局（电脑端优先，1280/1440 验收，1024 兼容）

- **页头**（sticky，高 64px，白色纸面，下边 1px 线）：
  - 左：`← 返回任务列表`（`data-practice-back`，复用 `practice_shell.js`，`fallbackUrl="/practice#practiceAssignedTasks"`，标签覆盖为“返回任务列表”）。
  - 中：任务标题（单行省略）和小标签：目标标签、`第 2 / 5 组`、日期状态（今日 / 宽限期内·03:00 截止）。
  - 右：保存状态胶囊和“键盘”帮助按钮。
- **阶段轨**（页头下）：本组实际存在的阶段（由适配层提供每阶段题数，不含题目内容），依次为熟悉材料、主动提取、语境辨析、语境产出、错题再测。显示当前阶段和阶段内进度条。**不可点击、不显示未来题目**。复习门禁时换成“今日复习 3 / 12”。
- **主舞台**：最大宽 1120px，居中。
  - 熟悉阶段为 7:5 两栏：左侧词条，右侧例句、搭配、用法。
  - 作答阶段为单栏，最大宽 760px，输入区在视线中心，不渲染任何熟悉材料。
- **底部操作条**（sticky bottom，高 72px）：左侧放辅助操作（上一词、忘了、重播），右侧放主操作（看过·下一词 / 提交 / 继续 / 提交订正），按钮带键位提示 `⏎`。主按钮最小 44×120px，**位置固定**，状态切换时宽度不跳。
- **1024px**：熟悉阶段改单栏（例句区落到词条下方），页头标题区收窄，标签换行。**<720px**：不重做手机端，只保证页头两行、操作条可用、不横向滚动。
- **缩放 125% 和 150%**：用 rem 和 clamp 设字号，操作条不遮挡内容（主舞台 `padding-bottom` 等于操作条高度加 24px）。

### 4.2 状态清单与转换

| 视图状态 | 进入条件（服务端事实） | 主要内容 | 主操作 | 离开 |
|---|---|---|---|---|
| `booting` | 页面加载 | 骨架屏，状态胶囊显示“同步中” | — | `state` 返回 |
| `blocked` | `identity_missing`、`staff_mode`、`ambiguous_student_name`、`student_account_*`、`task_not_found`、`task_not_vocabulary_v2` | 原因、解决办法、入口链接 | 返回任务列表 / 前往练习中心 | — |
| `locked_future` | `access.state == "future"` | “尚未开放 · {date} 开放” | 返回 | — |
| `read_only` | `access.read_only` 且无 settlement（已截止未完成） | 已完成组数和首答数（来自只读 flow），说明“已于次日 03:00 截止，作答已保存” | 返回 | — |
| `review_gate` | 无 flow、未只读、`review_preflight(gate_only=True).required` | 说明“开始本任务前先完成今日复习”和题量 | 开始复习 → `POST review/claim` | 进入 `review_question` |
| `review_question`、`review_feedback`、`review_correction` | 复习会话的 items | 与任务题相同的渲染器，阶段轨换成复习进度 | 同 §4.3 | 全部作答且无待订正 → `review_settling` → `POST sync` |
| `familiarity` | `phase == "familiarity"` | 词条：词形（字典体）、音标、发音、释义；材料：例句（目标词加粗）、译文、搭配、用法 | 看过·下一词（未浏览的词调 `POST familiarity`；已浏览的词只在本地翻页） | 整组浏览完后服务端进入 active_recall |
| `question` | `current_question` 存在、不需订正 | §1.2 的题型渲染 | 提交（文本为空时提示，不发请求）；忘了 | `submitting` |
| `submitting` | 写请求在途 | 输入框只读，主按钮显示“提交中…”且宽度不变，状态胶囊显示“保存中” | 禁用 | 成功 → `feedback`；失败 → `save_failed` |
| `feedback` | 答题接口成功 | 正确：“✓ 回答正确”。错误：“✗ 首答错误 · 已记录”（再测阶段为“✗ 仍需巩固”）。忘了：“已标记为忘了 · 按未掌握记录”。附字母比对和反馈卡 | 继续（调 `POST sync`） | 服务端返回下一状态 |
| `correction` | `correction_required`（仅综合目标） | 琥珀色说明条“订正：照正确答案输入一次（不计分）”，显示正确答案、输入框、`第 n / 2 次` | 提交订正 | 正确或用尽 → `POST sync`；仍需订正 → 留在本状态，提示“还不对，再试一次” |
| `retry_intro`（客户端插页） | 首次进入 `phase == "retry"` 且有题 | “错题再测 · n 题 · 只用于巩固，不改变首答成绩” | 开始再测 | `question` |
| `group_done`（客户端插页） | `group_number` 增加 | 上一组的首答正确数、再测数、待复习数（取 `group_results` 最后一项，由适配层透传） | 开始第 k 组 | `familiarity` |
| `settling` | `completed && !settlement` | “正在提交任务结果…” | — | `result` 或 `settle_failed` |
| `settle_failed` | 结算网络失败或 5xx | “作答都已保存，只差最后一步结算” | 重试结算 | `settling` |
| `result` | `settlement` 存在（含刚结算完） | 首答正确率（大字）和 x / y；再测完成数、仍待复习数、资料不足跳过数；忘了的词列表（词、答案、重播）；说明“首答成绩已记录；再测用于巩固，不改变首答成绩；仍待复习的词会进入后续复习” | 返回任务列表 | — |
| `save_failed` | 写请求超时、断网或 5xx（自动重试 1 次后） | 保留输入，状态胶囊显示“保存失败 · 重试” | 重试（同一 attempt_id） | 成功后回到正常流 |
| `resynced`（toast） | 409 冲突后重新同步成功 | “进度已在其他窗口或设备更新，已同步到最新位置” | — | — |

用词约束：只用“首答正确”“再测通过”“仍待复习”“已浏览”。**禁止**出现“全部掌握”“已掌握”。熟悉阶段的“看过”不算掌握，结算页不把完成率写成掌握率。

### 4.3 键盘、焦点、音频、快捷键（实现放 `practice_vocabulary_core.js` 的纯函数 `routeKey(viewState, event, ctx)`，返回一个动作，可单测）

**通用守卫（最先判断）**

1. `event.isComposing || event.keyCode === 229`：忽略。另外监听 `compositionstart` 和 `compositionend`，组合期间 `ctx.composing=true`，`compositionend` 后的同一事件循环里也忽略 Enter，规避 Safari 先触发 compositionend 再触发 keydown 的顺序。中文输入法确认候选词因此不会误提交。
2. `event.repeat === true`：所有动作键都忽略，长按 Enter 不会连发。
3. **Enter 需要先松开**：用 `enterDown` 记录 Enter 是否处于按下状态（keydown 置 true，keyup 和 window blur 置 false）。视图状态切换时，**只有 `enterDown` 为 true** 才把 `enterArmed` 设为 false，等到 keyup 再恢复。这样用 Enter 提交时，那一下不会穿透到“继续”；用鼠标点按钮切换状态时，下一次 Enter 也不会被误吞。错误或忘了的反馈另外要求停留至少 500ms 才响应“继续”。
4. 有写请求在途（`inFlight`）：除 Esc 外全部忽略。按钮同时设 `disabled` 和 `aria-busy`。双击按钮会被单飞锁拦住。

**按状态**

| 状态 | Enter | 1–4 | ↑ / ↓ | ← / → | Alt/⌥ + R | R（焦点不在输入框） | Tab |
|---|---|---|---|---|---|---|---|
| familiarity | 看过·下一词 / 开始测试 | — | — | ← 上一词（只回看已浏览）；→ 等同 Enter | 重播 | 重播 | 正常 |
| question（文本） | 非空则提交，空则提示“请输入答案，或点「忘了」” | 作为文字输入，**不拦截** | 不拦截 | 不拦截（移动光标） | 仅音频题重播，`preventDefault` 防止 ⌥R 输入 ® | 无效（焦点在输入框） | 输入框 → 重播 → 忘了 → 提交 |
| question（选择） | 已选则提交，未选则提示 | 选中第 n 项 | 在选项间移动（roving tabindex） | 同 ↑ / ↓ | 仅音频题重播 | 仅音频题重播 | 进出选项组 |
| feedback | 继续（需已松开，错误需停留 500ms） | — | — | — | 重播反馈音频 | 重播 | 正常 |
| correction | 非空则提交订正 | 文字 | 不拦截 | 不拦截 | 重播 | — | 正常 |
| result、blocked | 聚焦主按钮时由浏览器原生激活 | — | — | — | — | — | 正常 |

- **“忘了”没有单键快捷键**：它会被记为未掌握，后果明显，只能点击，或 Tab 到按钮后按 Enter 或空格。
- **自动聚焦**：进入 `question` 或 `correction` 时 `input.focus({preventScroll:true})`，选择题聚焦当前选中项或第一项；进入 `feedback` 时聚焦“继续”。焦点在页头、键盘帮助等可交互元素上时不抢焦点。
- **输入框属性**：`autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" enterkeyhint="done" data-gramm="false"`；英文题 `lang="en" inputmode="text"`，中文题 `lang="zh"`。**不做 A–Z 过滤**：空格、连字符、撇号、中文、数字、日期都原样提交。`maxlength` 取 `answer_length`（英文 100），中文题取 200。只 `trim` 首尾空白，其余规范化由服务端负责（`dictation_answers.py`）。**不限制粘贴**：词汇没有现行粘贴政策，`exam_guard.js` 只用于模考，不引入。页面文案和代码注释都不承诺能控制所有第三方输入法。
- **音频**：URL 按 `miniprogram/utils/dictation-audio.js:resolveAudioUrl` 的规则解析，base 是 `/api`：`/dictation/words/{id}/tts` 解析为 `/api/dictation/words/{id}/tts`，`uploads/`、`static/` 开头的路径解析到站点根。按钮有四个状态：空闲（播放）、加载中（转圈，按钮宽度不变）、播放中（波形动画；`prefers-reduced-motion` 时为静态图标）、失败（“播放失败 · 重试”）。8s 无 `canplay` 视为失败。重复点击从头播放，不叠加。自动播放只在页面已有用户交互后进行，被浏览器拒绝时退回“点击播放”状态，不报错。作答前只播放该题型允许的音频（§1.2），`zh_to_en` 和 `context_*` 题作答前没有音频入口。
- **可见焦点**：`:focus-visible` 用 3px 主色描边并留 2px 偏移，深浅底都可见。正误和保存状态都带图标和文字，**不只靠颜色**。

### 4.4 视觉 token（遵循 `DESIGN.md` 的 Student 调色板和 canonical teal）

```css
--pv-canvas:#F4F1EA; --pv-surface:#FFFEFA; --pv-surface-cool:#F7FAF9; --pv-border:#E3E8EE;
--pv-ink:#18243A; --pv-ink-muted:#667085; --pv-primary:#20756F; --pv-primary-strong:#145C57;
--pv-primary-soft:#E6F5F2; --pv-success:#16A34A; --pv-success-soft:#DCFCE7; --pv-warning:#D97706;
--pv-warning-soft:#FEF3C7; --pv-danger:#DC2626; --pv-danger-soft:#FEE2E2;
--pv-font-ui: system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
--pv-font-entry: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Songti SC", serif; /* 只用于词头和例句 */
--pv-font-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;                     /* 键位提示 */
```

- 不引入外部字体（DESIGN.md 规定）。不加装饰渐变或光斑。卡片只给主舞台一层，不嵌套卡片。
- 词头字号 `clamp(44px, 4.2vw, 64px)`；作答输入 32px，字间距 0.02em，落在一条 2px 下划线上，像练习本的书写线。
- 状态色只用于语义（正确、警告、错误），主色只用于主操作和当前阶段。

---

## 5. 服务复用清单

### 5.1 新蓝图 `api/practice_vocabulary.py` 的端点与调用

所有端点先执行 `resolve_practice_student()` 和任务归属检查（§3）。写端点还要经过 CSRF 和身份漂移检查。每个写端点只负责“取参数 → 调 service → commit 或 rollback → 返回清洗后的视图”，函数不超过 60 行。

| 端点 | 调用 | 说明 |
|---|---|---|
| `GET /practice/vocabulary/tasks/<id>` | 身份、归属、`task_date_access` | 渲染模板，内嵌 csrf、identity_key、任务元数据（标题、词书、范围、目标标签、日期状态），**不含题目** |
| `GET /api/practice/vocabulary/tasks/<id>/state` | 只读：`access.read_only` 时调 `get_vocabulary_group_queue(user, id, supports_correction=True)`（只读分支不写库）；否则查 flow 是否存在；无 flow 时再调 `review_preflight(user, id, gate_only=True)` | 返回 `stage ∈ {read_only, result, review_gate, not_started, in_progress}`。**GET 无副作用** |
| `POST …/sync` | 未只读且无 flow 时先调 `review_preflight(gate_only=True)`；需要复习则返回 `review_gate`（带 `attempt_id` 时同 `api/vocab_review.py:_gated_saved_group_response`，调 `recover_vocabulary_group_attempt` 只读恢复）；否则调 `get_vocabulary_group_queue(user, id, supports_correction=True, recovery_attempt_id=body.attempt_id)` | 首次调用创建 flow，即“开始”；与小程序“打开即领取”语义一致 |
| `POST …/familiarity` | `mark_familiarity_viewed(user, id, {queue_token, word_id})` | |
| `POST …/answers` | `submit_vocabulary_group_answer(user, payload)` | 适配层**强制** `task_id`（取 URL）、`input_mode="native"`、`supports_correction=True`；透传 `response_kind ∈ {answer, forgot}`、`retry`（bool）、`attempt_id` 和题目定位字段。返回内容加上反馈卡字段（见 5.2(c)） |
| `POST …/corrections` | `submit_vocabulary_group_correction(user, {task_id, queue_token, learning_question_id, answer, attempt_id})` | |
| `POST …/settle` | `settle_vocabulary_group_submission(user, id, {queue_token, duration_seconds})`（新共享服务，§5.3） | 遇到 `task_completed_read_only` 时改走只读 state 读回 settlement，返回 `{ok:true, already_settled:true, …settlement}` |
| `POST …/review/claim` | `claim_today_review(user, origin_task_id=id)` | 当天已有活动会话时直接恢复 |
| `POST …/review/answers` | `submit_review_answer(user, session_id, payload, session_token=…)` | payload 强制 `supports_correction=True`、`input_mode="native"` |
| `POST …/review/corrections` | `submit_review_correction(user, session_id, payload, session_token=…)` | |
| `POST …/review/settle` | `settle_review_session(user, session_id, {session_token, queue_token, duration_seconds, supports_correction:True})` | 首版不发 `skipped_items`（小程序也不发）；结算后前端调 `POST sync` |

异常映射沿用 `api/vocab_review.py` 的形状 `{"ok": false, "error": code, ...details}` 和服务给的状态码。蓝图注册 errorhandler，`VocabularyGroupLearningError`、`VocabularyAutonomousReviewError`、`VocabularyMasteryError`、`TaskDateGateError` 都先 `db.session.rollback()` 再返回。`SQLAlchemyError` 记日志后返回 500 `save_failed`。

### 5.2 确实需要的薄适配（`services/practice_vocabulary_web.py`，约 250 行）

- **(a) 身份 → User**：§3.2。网页没有 Bearer，必须有。
- **(b) 响应清洗 `sanitize_flow(payload)`**。电脑浏览器打开开发者工具就能看到全部响应，而需求要求“作答前不泄题”。
  - 非 familiarity 阶段，把 `familiarity` 只保留 `word_id` 和 `viewed`，去掉词形、释义、例句。
  - 从 `current_question` 去掉 `revealed_answer`、`first_answer`、`retry_*`。retry 阶段服务端会带上同题首答的答案，UI 在再测前不能展示。
  - flow 未结算时去掉 `forgot_items` 和 `last_saved_response.revealed_answer`。
  - `audio_to_zh` 的 options 为空时，在服务端用组内释义生成回退选项，算法与 `buildMeaningChoiceOptions` 一致（FNV-1a 32 位，种子 `question_id`），保证跨端稳定。
  - 补充 `phase_counts`（本组各阶段题数，不含内容）供阶段轨使用。
  - 只透传 `group_results` 最后一项，供“本组完成”插页使用。
  - **不改服务本身的返回契约**，小程序不受影响。
- **(c) 反馈卡 `answer_feedback(word, question)`**：`/dictation/submit` 路由在服务结果外又补充了 `_word_enrichment_payload` 和音节（`api/dictation.py:1300`），网页直接调服务，需要自己补。字段为 `canonical_vocabulary_word(word.word, word.accepted_answers)`、phonetic、`core_meaning_zh or translation`、usage_pattern、example_en、example_zh、usage_note、`_question_audio_url` 的同等 URL。首版不提供音节。不从 `api/dictation.py` 导入私有函数。
- **(d) 结算包装**：§5.3。
- **(e) 列表字段**：§2.1。

### 5.3 共享抽取（保留原 PlanItem 同步链路）

1. **新文件 `services/task_plan_item_sync.py`**：把 `api/miniprogram.py:587 _sync_plan_item_from_legacy_task` 和 `:920 _resolve_task_dictation_order`（以及 `VALID_DICTATION_ORDERS`）**原样搬过来**。
   - 函数改名为 `sync_plan_item_from_task_submission(task, *, note=None, evidence_files=None, duration=0, uploader_id=None)`。唯一的变化是 `PlanEvidence.uploader_id` 从参数 `uploader_id` 取，不再读 `request.current_api_user`。
   - `api/miniprogram.py` 保留同名包装 `_sync_plan_item_from_legacy_task(task, **kw)`，内部传 `uploader_id=getattr(getattr(request, "current_api_user", None), "id", None)`，因为 `tests/test_miniprogram_grading.py` 直接导入它。`_resolve_task_dictation_order` 改为从 service 导入的别名。共 4 个调用点不动。
2. **新文件 `services/vocabulary_task_submission.py`**：

   ```python
   def settle_vocabulary_group_submission(user, task_id, payload, *, uploader_id=None) -> dict:
       result = finalize_vocabulary_group_task(user, task_id, payload)   # 已有：幂等 settlement、写 Task 完成字段
       task = db.session.get(Task, task_id)
       if task:
           sync_plan_item_from_task_submission(task, note=payload.get("note"),
               evidence_files=payload.get("evidence_files") or [], duration=payload.get("duration_seconds", 0),
               uploader_id=uploader_id)
       return result   # 由路由负责 commit
   ```

   `api/miniprogram.py:submit_task` 的 v2 分支（约 2640–2680 行）只把 “finalize + `_sync_plan_item_from_legacy_task`” 两行换成调这个函数。前置的 `web_practice_required` 和 `_task_gate_response` 检查保持原位、原顺序。
3. **幂等性**：`finalize_vocabulary_group_task` 发现已有 settlement 就直接返回已存结果，不再写 `actual_seconds`。PlanItem 同步对时长取 `max`，`submitted_at` 取 `task.submitted_at`，重复调用不会叠加（满足 A13）。

### 5.4 网页与小程序共用任务记录

- 同一个 `VocabularyLearningFlow(student_id=user.id, task_id)`，有唯一约束。同一套 `VocabularyLearningQuestion`、`DictationRecord`（唯一约束 `student_id + attempt_id`）、`VocabularyTaskSettlement` 和 Task/PlanItem。
- 网页的 attempt_id 与小程序**同一格式**（§6.1），同一题跨端重复提交会幂等收敛到首个记录。
- 老师和家长的既有视图读的是同一份数据：Task 的 `accuracy`、`status`、`actual_seconds`，PlanItem 的 `student_status=submitted`，以及 DictationRecord（`/miniprogram/parent/tasks/<id>` 和 `_parent_dictation_task_report`）。

### 5.5 `supports_correction` 的正确声明

- 现状：HTTP 路由在客户端没传 `true` 时注入 `False`（`api/dictation.py:1281`、`api/vocab_review.py`）；服务直接调用时默认 `True`。没传 `supports_correction=1` 时，`get_vocabulary_group_queue` 会调 `_release_legacy_pending_correction` 释放待订正题。**git 中的小程序 v2 页面没有订正 UI**，所有分支都检查过，见 §9-2。
- 网页适配层在 sync、answers、review/answers、review/settle 上**显式**传 `True`。不依赖默认值，任何地方都不传 `False`。
- **发布顺序约束**：订正 UI（`correction` 状态）必须和答题端点在**同一个可部署提交**里上线（§7.3 的 S5 和 S7 之间不能部署）。否则综合目标的学生答错后会停在服务端要求订正、但界面没有订正入口的状态。
- 测试：用网页答错一道综合目标题，返回 `correction_required=true`；随后网页再调 `sync`，`correction_required` 仍为 true（**没有**被释放）。对照组：小程序路由不带参数时会释放（已有行为，补一个断言）。
- 跨端：学生订正到一半切到旧版小程序，旧客户端走兼容分支释放订正并把该词记为薄弱词。这是既有设计，交接里写明，不当成缺陷。

---

## 6. 恢复与并发

### 6.1 标识

| 动作 | attempt_id | 依据 |
|---|---|---|
| 首答 | `vocabulary-group:{task_id}:first:{learning_question_id}` | 与小程序 `vocabulary-learning/index.js` 相同。同题重复提交返回 `idempotent:true` 和首个记录 |
| 再测、补救 | `vocabulary-group:{task_id}:retry:{learning_question_id}` | 同上（补救题位于 retry 阶段，`retry=true`） |
| 订正 | `vocabulary-group:{task_id}:correction:{lqid}:{first|retry}:{correction_count+1}` | 服务在再测答错时会重开订正槽，id 里带上阶段和次数才能唯一；长度不超过 96 |
| 复习首答 | `web-vocabulary-review:{session_id}:{review_item_id}` | 服务对已作答的题直接返回持久化的首答（`submit_review_answer` 的“second tab”分支） |
| 复习订正 | `web-vocabulary-review-correction:{session_id}:{item_id}:{n}` | |

### 6.2 幂等、重复提交、旧回包

- **单飞**：同一时刻只允许一个写请求。按钮 `disabled`，键盘在 `inFlight` 时被路由函数忽略（§4.3 第 4 条）。
- **待确认日志**：发写请求前，把 `{kind, attempt_id, payload, position}` 写进 `sessionStorage["pv:{task_id}:{identity_key}:pending"]`，2xx 后清除。刷新后，如果日志里的题仍是当前题，先用**同一个 attempt_id 重发**，期间不接受新输入；否则丢弃。未发送的输入草稿按 lqid 存在 sessionStorage。读写都包 try/catch，存储不可用时页面照常工作。
- **超时与重试**：`AbortController` 15s。超时或断网后等 1s 自动重发一次（同一个 attempt_id），仍失败则进入 `save_failed`，保留输入。**任何情况下都只在 2xx 且 `ok:true` 后才显示“已保存”。**
- **旧回包丢弃**：每个请求带递增的 `seq`。改变视图的响应只在 `seq === latestSeq` 时应用。`sync` 的响应还要校验位置键 `(queue_token, group_index, phase, phase_index, current_question.learning_question_id)`，旧位置的响应不能覆盖新位置。
- **冲突码处理**：
  - `state_conflict`：带 `retryable` 时先重发一次，否则重新 sync。
  - `question_not_current`、`queue_changed`、`correction_not_current`、`correction_required`、`task_already_completed`：重新 sync，并弹 toast（§4.2）。
  - `idempotent:true` 且 `student_answer` 与本地输入不同：显示提示条“这道题已在其他窗口或设备提交，以下是已保存的结果”。

### 6.3 末题保存和结算异常

- 末题答完后 sync 得到 `completed:true` 且无 settlement，自动结算（单飞）。
- `retry_incomplete`、`group_flow_incomplete`、`correction_incomplete`：重新 sync，按服务端给出的剩余工作继续，**不显示完成**。
- 网络错误或 5xx：进入 `settle_failed`，可重试；刷新后 `state` 仍是 completed 且无 settlement，会再次结算。
- 结算其实已成功但回包丢失：重试时被门禁拒为 `task_completed_read_only`，适配层改为只读取回 settlement，返回成功。
- 结算前跨过 03:00（`task_expired`）：进入 `read_only`，文案“已过截止时间，结算未完成；作答记录已保存”。这是既有规则，不放宽。
- 时长：发送本标签页从加载到结算的秒数，沿用小程序“首次结算覆盖 `Task.actual_seconds`”的语义（§9-8）。重复结算不改时长。

### 6.4 跨标签与跨设备

- `BroadcastChannel("pv-task-{task_id}")`：一个标签页写成功后广播 `{type:"advanced", position}`。其他标签页收到后标记为过期，在获得焦点或变为可见时自动 sync。不支持时退回 `visibilitychange` 后 sync。
- 跨设备：页面重新可见且空闲时 sync。正在输入且当前题未变时保留输入。服务端位置已前进时丢弃输入，并显示 toast。
- 双标签同时处于复习门禁：`claim_today_review` 当天幂等，返回同一个活动会话。

---

## 7. 实施拆分

### 7.1 开发基线

1. `git fetch origin main`，确认 `origin/main` 包含 `f81a5e4a4d81282eb67b994a4cfcc5574fb78747`。如果 main 已前进，以新的 HEAD 为基线，并检查本文提到的函数和行号是否漂移。
2. 只在隔离 worktree 里实施：`git worktree add /private/tmp/studytracker-web-vocabulary-20261126 -b codex/web-vocabulary-task-page-20261126 origin/main`。**不要**在 `/Users/zhouxin/Desktop/studytracker`（main@6ded77d2，有脏改动）里开发、pull 或复制后端代码。
3. Python 用 Mac 上的 `.venv/bin/python`。生产解释器是 **3.10**（代码注释 `noqa: UP017` 和交接里的 3.10 隔离环境 `/private/tmp/studytracker-stage2-py310`），所以语法要兼容 3.10，测试在 3.10 和 3.13 下都跑。

### 7.2 文件级改动

| 文件 | 新建 / 修改 | 约行数 | 内容 |
|---|---|---|---|
| `services/task_plan_item_sync.py` | 新 | 80 | §5.3-1 |
| `api/miniprogram.py` | 改 | -50 / +10 | 同步改为包装，v2 结算改调共享服务 |
| `services/vocabulary_task_submission.py` | 新 | 40 | §5.3-2 |
| `services/practice_student_identity.py` | 新 | 90 | §3.2 |
| `services/practice_vocabulary_web.py` | 新 | 250 | §5.2 (b)(c)、错误码到视图的映射、元数据构建 |
| `api/practice_vocabulary.py` | 新 | 300 | §5.1 的 11 个端点和 before_request |
| `api/__init__.py` | 改 | +2 | 导入并注册 `practice_vocabulary_bp` |
| `templates/practice/vocabulary_task.html` | 新 | 180 | 页面骨架，引入 `_navigation_defaults.html`、`practice_shell.css/js` 和新资源，`<noscript>` 提示 |
| `static/css/practice_vocabulary.css` | 新 | 600 | §4.4 的 token 和各状态样式 |
| `static/js/practice_vocabulary_core.js` | 新 | 350 | 纯逻辑（UMD）：`routeKey`、attempt_id 构造、回退选项算法、字母比对、音频 URL 解析、seq 和位置守卫、错误码到动作的映射 |
| `static/js/practice_vocabulary_render.js` | 新 | 400 | 按视图状态和 mode 渲染 DOM，只用 `textContent`，不拼 innerHTML |
| `static/js/practice_vocabulary_page.js` | 新 | 400 | 控制器：fetch 封装（CSRF 和身份头、超时、重试）、状态机、音频播放器、BroadcastChannel、sessionStorage 日志 |
| `services/practice_vocabulary_tasks.py` | 新 | 120 | §2.1 |
| `app.py` | 改 | 约 +20 | §2 的查询、payload 和来源标签 |
| `config.py` | 改 | +1 | `PRACTICE_VOCABULARY_WEB_ENABLED`（§9-4） |
| `templates/practice/index_content.html` | 改 | +3 | pageshow 时刷新列表 |
| `.github/workflows/ci.yml` | 改 | +4 | 新测试并入 vocabulary job 和 node 步骤 |
| `tests/test_task_plan_item_sync.py` | 新 | | 搬迁前后同输入同输出（含 evidence、时长取 max、词汇元数据） |
| `tests/test_practice_student_identity.py` | 新 | | §3.2 各分支 |
| `tests/test_practice_vocabulary_web.py` | 新 | | 清洗不泄题、回退选项与 JS 算法对照向量、反馈卡缺字段 |
| `tests/test_practice_vocabulary_routes.py` | 新 | | 仿照 `tests/test_vocabulary_group_learning_api.py` 用最小 Flask 应用注册 dictation、mp、vocab_review 和新蓝图；`session_transaction` 模拟姓名会话 |
| `tests/test_practice_vocabulary_task_list.py` | 新 | | 仿照 `tests/test_auto_student_accounts.py` 的导入 app 手法（内存库、禁网），验证 `/api/practice/tasks` |
| `tests/test_practice_vocabulary_core.js` | 新 | | node:test |
| `docs/reviews/web-vocabulary-task-page-<date>/browser_check.py` | 新 | | Playwright 验收脚本，用离线夹具和本地 Flask |

JS 拆成 3 个文件、每个不超过 400 行，是为了不再产生第二个 `hammer/index.js`（CLAUDE.md 的前端规则）。网页**不用** `miniprogram/utils/request.js`，那是小程序约定；网页请求统一走 `practice_vocabulary_page.js` 里的 `api()`，它负责 CSRF 头、身份头和超时。

### 7.3 依赖顺序和可独立验证的小步（一个 commit 一件事）

| 步骤 | 内容 | 验证 | 能否单独部署 |
|---|---|---|---|
| S1 | PlanItem 同步抽取（行为不变） | `tests.test_task_plan_item_sync tests.test_miniprogram_grading tests.test_vocabulary_group_learning_api` | 能 |
| S2 | 共享结算服务，小程序路由改调 | 同上，再加新的结算幂等用例 | 能 |
| S3 | 身份解析服务 | `tests.test_practice_student_identity` | 能（未接线） |
| S4 | 网页适配服务 | `tests.test_practice_vocabulary_web` | 能（未接线） |
| S5 | 蓝图、模板骨架和 API | `tests.test_practice_vocabulary_routes` | **否**：必须与 S7 一起上线（订正 UI 约束，§5.5） |
| S6 | 前端纯逻辑 | `node --test tests/test_practice_vocabulary_core.js` | 能 |
| S7 | 前端渲染、控制器和 CSS | 本地浏览器加 S9 脚本 | 与 S5 同批 |
| S8 | 列表接线 | `tests.test_practice_vocabulary_task_list` 和 A02 不回退断言 | 放最后，保证列表不会链接到未完成的页面 |
| S9 | 浏览器验收脚本和截图 | §8 | — |
| S10 | CI 登记、交接文档 | CI 通过 | — |

S5 的实现不能早于 S1 和 S2。S3、S4 可以并行；S6 可以和 S5 并行。

### 7.4 数据库迁移：不需要

- 状态全部落在已有表：`vocabulary_learning_flow`、`vocabulary_learning_question`、`dictation_record`、`vocabulary_task_settlement`、`vocabulary_review_session`、`vocabulary_review_item`、`vocabulary_review_attempt`、`vocabulary_review_settlement`、`task`、`plan_item`。字段已覆盖首答、再测、订正、忘了、`input_mode` 和结算（`models.py` 1276–2256 行）。
- 网页身份用 Flask session，CSRF token 在 session 里。URL 不带 token，所以不需要新的 access-token 列。
- “进行中”状态从已有 flow 表只读推导，不写 Task。
- 如果实施时发现需要新列或新表，**停下来回报**，不要用 `db.create_all` 代替显式迁移（交接里 B4 的经验）。

---

## 8. 验证与交付

### 8.1 A01–A14 对应

| 编号 | 自动化（文件 :: 用例要点） | 手工 / 浏览器 |
|---|---|---|
| A01 | `task_list`：助教和老师各建一条 reading v2 任务，分别进入 `groups.assistant` 和 `groups.teacher`，`url` 为 `/practice/vocabulary/tasks/{id}`，`source_label` 为“阅读词汇”，标题含词书和范围；`routes`：页面元数据中的 book_id 和范围与 Task 一致 | 列表点击进入，页头词书和范围正确 |
| A02 | `task_list`：听力、阅读、题型专项、写作各一条，payload 逐字段等于改动前的快照；`vocabulary_goal=NULL` 的听写和 spelling_drill 不出现；`web_practice_required(v2)` 返回 None | 原有四类卡片照常跳转 |
| A03 | `routes`：未开始 → `review_gate` 或 `not_started`，sync 后进入 familiarity；进行中刷新后回到原题（同一 lqid）；已完成 → result，且 `DictationRecord` 首答条数不变、flow 数仍为 1 | 刷新、关闭重开 |
| A04 | `routes`：用 `now` 注入或打补丁构造 future、today、宽限期（次日 02:59）、03:00 后截止，断言 state 和列表 `task_date_state` 一致，截止后写操作返回 `task_expired` | 列表和页头标签一致 |
| A05 | `routes`：B 的姓名会话访问 A 的 task_id 返回 404；伪造 `session_id` 或 `session_token` 被拒；`X-Practice-Identity` 不匹配返回 409；无 CSRF 或 Origin 不同返回 403；教师或课堂模式返回 403；同名档案返回 409；正式学生账号和姓名会话两条合法路径都可用 | 两个浏览器、两个学生交叉验证 |
| A06 | `routes` + `web`：四个目标和数字词、同义词夹具覆盖 6 种 mode；非 familiarity 阶段响应里没有 familiarity 的内容字段，`current_question` 没有 `revealed_answer`；缺例句或搭配不报错，并产生 diagnostics | 原型对照，逐题型截图 |
| A07 | `routes`：答对、答错、忘了（`response_kind=forgot`，答案为空）、再测、综合目标订正（≤2 次、用尽后 deferred）；再测答对后首答 `first_is_correct` 和 `Task.accuracy` 不变 | 走一遍综合目标任务 |
| A08 | `core.js`：`routeKey` 覆盖 isComposing、keyCode 229、repeat、未松开 Enter、inFlight、输入框里的数字键不拦截、选择题 1–4、⌥R 的 `preventDefault`；`routes`：同一 attempt_id 并发两次只产生一条 DictationRecord | Playwright：`keyboard.down('Enter')` 长按、双击按钮、用 `page.dispatchEvent` 模拟 compositionstart/end 组合输入 |
| A09 | `core.js`：音频 URL 解析；控制器单测（假 Audio）：加载超时 → 失败 → 重试 | Playwright 拦截 tts 请求延迟 5s 或返回 500，检查按钮状态；`zh_to_en` 和 `context_*` 题作答前没有音频按钮 |
| A10 | `routes`：同一 attempt_id 重发返回 `idempotent`；`core.js`：日志重放和 seq 丢弃 | Playwright 设为离线后提交显示“保存失败”且输入保留，恢复后重试成功且计分只有一次；`route.abort` 丢掉响应后刷新，按服务端恢复 |
| A11 | `routes`：用两个客户端模拟网页和小程序（Bearer）交替答同一题，结果收敛；旧位置提交返回 `question_not_current` | 两个标签页加小程序真机或开发者工具（只读验证，不上传） |
| A12 | `routes`：有漏题或待订正时结算返回 409 且 Task 未完成；结算成功后重放返回 `already_settled`；结算接口打补丁抛 `OperationalError` → 409 → 重试成功 | Playwright 让 settle 返回 500 后点“重试结算” |
| A13 | `routes`：网页结算后 Task（status、accuracy、actual_seconds）、PlanItem（submitted、时长取 max、resource_metadata）与 `/miniprogram/parent/tasks/<id>` 返回一致；重复结算后 settlement 仍 1 条，mastery、ReviewSession 计数不变 | 家长端、老师端只读查看 |
| A14 | — | Playwright 1440×900、1280×800、1024×768 和缩放 125%、150% 截图；Tab 遍历所有可交互元素都有可见焦点；正误和保存状态有文字；主按钮不被裁切 |

### 8.2 命令（Mac，worktree 根目录）

```bash
# 新增
.venv/bin/python -m unittest tests.test_task_plan_item_sync tests.test_practice_student_identity \
  tests.test_practice_vocabulary_web tests.test_practice_vocabulary_routes tests.test_practice_vocabulary_task_list -v
node --test tests/test_practice_vocabulary_core.js

# 回归（本计划核查时 f81a5e4 上全部通过：102 + 5 + 27）
.venv/bin/python -m unittest tests.test_vocabulary_group_learning tests.test_vocabulary_group_learning_api \
  tests.test_vocabulary_autonomous_review tests.test_vocabulary_flow_backlog_gate tests.test_auto_student_accounts \
  tests.test_miniprogram_grading tests.test_task_date_gate tests.test_task_date_gate_display_contract -v
.venv/bin/python -m unittest tests.test_vocabulary_error_review_integration tests.test_vocabulary_numeric_learning \
  tests.test_vocabulary_numeric_review tests.test_vocabulary_stage2_adversarial -v
node --test tests/test_practice_task_lists.js tests/test_practice_shell.js tests/test_vocabulary_feedback.js

# Python 3.10 兼容（用交接中的 3.10 隔离环境重跑以上两组 unittest）
/private/tmp/studytracker-stage2-py310/bin/python -m unittest <同上模块> -v

# 静态检查
.venv/bin/python -c "from jinja2 import Environment, FileSystemLoader as L; Environment(loader=L('templates')).get_template('practice/vocabulary_task.html')"
ruff check services/practice_*.py services/task_plan_item_sync.py services/vocabulary_task_submission.py api/practice_vocabulary.py
git diff --check
.venv/bin/python docs/reviews/web-vocabulary-task-page-<date>/browser_check.py
```

注：`tests.test_task_date_gate` 需要 `pytest` 包。导入 app 的测试按 CI `account-provisioning` job 的轻依赖安装。

### 8.3 交付状态必须分开写明

| 状态 | 含义 | 本轮 |
|---|---|---|
| 本地完成 | worktree 内改完，§8.2 全部通过 | Codex 执行后填写 |
| 已提交 | commit 到 `codex/web-vocabulary-task-page-<date>` | 需用户授权 |
| 已推送分支 | 推送到任务分支，跑分支 CI（不部署） | 需用户授权 |
| 已推送 main = 触发部署 | `deploy.yml` 自动部署到生产 5002 | **需用户单独明确授权** |
| 生产验收 | 只读回读发布 HEAD、文件 SHA、单 worker；匿名访问新页面得到 blocked | 部署后 |
| 小程序 | 无改动，无上传、提审、发布 | 不涉及 |

生产库：本功能不需要任何手动写库或迁移。

---

## 9. 需要用户确认的实质歧义（附推荐默认值）

| # | 问题 | 推荐默认 | 理由 / 代价 |
|---|---|---|---|
| 1 | **只有姓名会话的学生可以写入长期掌握记录。** 任何人输入同学姓名都能替他作答，而首答不可改，会长期进入复习排程和老师可见的成绩 | 沿用现有网页流程（姓名会话或正式学生账号），加上同名拒绝、identity_key 和 CSRF | 与听力、阅读、写作网页任务一致，不新增登录。风险是同学恶意代答（既有问题）。备选方案：网页写入只认正式学生账号，姓名会话只读，需要用户决定 |
| 2 | **网页会是第一个声明支持订正的客户端。** 综合目标在网页有“立即订正”，小程序（git 版本）没有 | 开启（服务端设计的 v2 契约，需求也要求实现订正 UI） | 两端体验有差异；跨端切换时旧客户端会释放订正并把词记为薄弱，属既有兼容行为 |
| 3 | 订正时是否显示正确答案 | 显示（照着正确答案再输入一次，不计分） | 仓库没有先例；订正本身不计分，遮挡答案会增加挫败感 |
| 4 | 是否加开关逐步开放 | 加 `PRACTICE_VOCABULARY_WEB_ENABLED`，默认关；关闭时列表不出词汇卡，页面显示“暂未开放” | 与 B3、B4 错词政策“默认关闭版本”的发布习惯一致；部署和开放分两步 |
| 5 | 复习门禁的承接方式 | 在任务页内完成一批复习后自动回到任务；不提供“继续复习”入口 | 需求只要求在任务流程内衔接门禁，不做独立复习入口 |
| 6 | 是否限制粘贴 | 不限制 | 词汇没有现行粘贴政策，`exam_guard.js` 只用于模考 |
| 7 | 听音拼写是否显示音标 | 不显示（与小程序同难度） | 服务端虽下发了 `phonetic` |
| 8 | 用时口径 | 沿用小程序：本端从进入到结算的时长，首次结算覆盖 `Task.actual_seconds` | 跨端分段学习时只记最后一端（既有语义）；要改需另立需求 |
| 9 | 旧听写类任务在网页的呈现 | 不出现在网页列表 | 需求要求“不支持类型保留原行为” |

无需用户确认、由 Codex 按本文自行决定的实现细节：类名和拆分方式、动画时长、toast 位置、骨架屏样式。

---

## 10. 交接要求（Codex 执行时）

- 开工先读 `docs/CODEX_HANDOFF.md` 和 `docs/WORKLOG.md`，核对 worktree、分支、HEAD。
- 收尾更新这两份文件：写明 worktree 绝对路径、分支和 HEAD、§8.2 精确命令与结果、§8.3 各状态、未验证项，以及 §9 中用户的决定。
- 本计划文件和原型目前**只在 Claude 云端会话的工作区**，未 commit 或 push。Codex 能否取得取决于用户是否授权推送，或由用户转交。
