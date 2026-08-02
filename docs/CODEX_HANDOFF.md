# StudyTracker — Codex 跨电脑开发交接

> 这是滚动更新的“当前状态”，不是聊天记录或永久变更日志。
> 最近更新：2026-08-02（Asia/Shanghai）。

## 使用规则

1. 开工先完整阅读根目录 `AGENTS.md`、`CLAUDE.md` 和本文件。
2. 随后运行 `git status --short --branch` 与 `git log -5 --oneline`。如果实际 Git 状态与本文不一致，以 Git 和可复现验证结果为准，并更新本文。
3. 不覆盖或删除来源不明的本地改动；先确认它们是否属于用户或另一项任务。
4. 收工或换电脑前更新“当前基线、近期完成、验证状态、发布状态、待办与下一步”。
5. 不在本文记录密码、令牌、Cookie、服务器密钥或学生隐私。

## 2026-08-02 当前任务：模考复盘与答题状态隔离（本地待发布）

- 工作树：`/Users/zhouxin/.codex/worktrees/mock-exam-review-isolation/studytracker`；分支：
  `codex/mock-exam-review-isolation`；基线：`origin/main@3d5a74fd`。没有改主工作树或其用户未跟踪文件。
- 本地实现已完成：复盘页显示完整题目结构、错题题干、选项、定位原句、解析，以及可展开的
  Section transcript / Passage 全文；“只看错题”会连同上下文一起筛选；写作 Task 1 显示题库图表，
  并可点击查看原图。
- 补齐学生端入口：成绩页提供「查看逐题复盘」，学生使用当前随机 session token 查看同一套复盘组件；
  仅整场 `submitted` 后才加载答案，错误 token 为 404，考试中访问会退回流程页。Task 1 图表也直接显示
  在学生成绩页。
- 学生端模考草稿改为 `exam_id + session_token + section + test` 隔离；听力不再复用旧姓名/guest 草稿，
  阅读不再加载普通刷题历史，并新增当前模考会话的本地草稿保存/恢复；成功交卷即清理。
- `NOT GIVEN` 的题库拆分值 `NOT` 已加入前后端判分别名。仅当历史结果明确为 `answer=NG/NOT GIVEN`、
  `value=NOT` 且旧判 0 分时，后台成绩列表/复盘才从保存答案幂等重算；其他历史成绩不动。
  用剑21 Test4 截图答案复现：32/40 → 37/40，Band 7.0 → 8.5，错题只剩 Q18/Q23/Q37。
- 验证：定向 Python 34 passed；全部 Node passed；Ruff、Black、模板普通/模考双模式渲染、
  `git diff --check` 通过；剑21 Test4 Task 1 图表静态请求返回 200 `image/png`；Chrome headless 1440px
  实际渲染复盘页布局正常。全仓 Python 327 项为
  325 passed + 2 个既有静态音频 fixture 404 失败。
- 用户已授权部署：将学生入口与前一提交一起推送 `main`，随后验证 GitHub Actions、生产 5002、
  学生成绩页入口和教师复盘；上线后再用两名测试学生同机同卷走一次真实端到端隔离。

## 当前基线

| 项目 | 当前状态 |
|---|---|
| 仓库 | `git@github.com:KB77GG/studytracker.git` |
| 分支 | `codex/toefl-student-workbench`，独立 worktree 为 `/Users/zhouxin/.codex/worktrees/f712/studytracker` |
| 分支基线 | `a6d20e4a 正式发布三套 TOEFL 2026 刷题流程`，已推送任务分支并进入 `main` |
| 远端 | `origin/main` 与 `origin/codex/toefl-student-workbench` 均包含 `a6d20e4a`；精确 HEAD 以 `git log -1` 为准 |
| 本次交接范围 | 只改当前独立 worktree；主工作树的用户未跟踪文件未覆盖。现有 `data/toefl_practice` 发布 JSON 零修改 |
| 后端生产 | 已部署 `a6d20e4a`；`studytracker.service=active`、`127.0.0.1:5002`，单 worker/gthread/threads=6 |
| 小程序 | 尚未上传、提审或发布，按授权由用户本人完成 |

## 2026-07-29 三套 TOEFL 2026 正式题包（已上线）

- 正式套题：`2026-01-27_A`、`2026-01-28_A`、`2026-01-28_B`；每套 120 个原子题、0 blocked，manifest 为 `publish_status=published`，runtime 与严格 release gate 均为 ready。
- 用户明确免除额外来源终审；manifest 用 `release_authorization.status=owner_authorized` 记录发布授权，四科 `subject_reviews` 继续保持真实的 pending，未伪写 approved。
- Speaking 已按 `docs/TOEFL_MOCK_FLOW_SPEC.md` 重塑为 11 个单题 group：
  - Q1–Q7 Listen and Repeat：准备 0 秒、录音 12 秒；
  - Q8–Q11 Take an Interview：准备 0 秒、录音 45 秒；
  - module 计时 180 + 300 = 480 秒。
- 逐题 cue 复用现有三条原始 speaking MP3，不转码、不改源文件。范围由转写逐词时间戳生成；Q1/Q8 含 intro/scenario，门禁校验 cue 边界、原音频时长和 ≥0.96 对齐置信度。公开 definition 只给 cue/计时，不给口语原文。
- 学生端流程为一次点击 → 原题播放一次 → 自动录音 → 到时停止 → 上传 → 自动下一题。服务端按当前 group、题级 response time 与 one-take policy 校验；正式模式不能重录，preview 可失败重试。
- 线上音频状态：9 条 listening/speaking URL 全部 Range 206；三条 speaking MP3 的生产 SHA-256 与本地来源一致，因此本次没有重复上传音频。

### 验证与发布

- 三套严格 `--require-release-ready` 均通过；七套 source-traceable validator 均通过。
- 相关 Python 30 passed；全部 Node 14 passed；相关 Ruff、JS syntax、Python compile、diff check 通过。
- 全仓 Python 329 passed，2 个既有静态音频 fixture 测试因本 worktree 没有目标音频返回 404，与本次 TOEFL 链路无关。
- CI [30416264782](https://github.com/KB77GG/studytracker/actions/runs/30416264782) 与部署 [30416264768](https://github.com/KB77GG/studytracker/actions/runs/30416264768) 成功；生产仓库 HEAD `a6d20e4a`，服务 active，端口和 gunicorn 约束已复核。
- 生产浏览器确认目录为 3 套 / 360 题、三卡均 `published / 正式门禁：通过`，Speaking 单项显示 11 题 / 2 phase / 正式模考按钮；控制台无 error/warn。
- 未在自动化浏览器授权真实麦克风，以免采集环境音。后续真实设备 QA：登录学生完整录完 11 题，再核对教师人工批改、报告与断线恢复。

## 2026-07-27 TOEFL V2 学生端考试工作台（历史记录，已由 2026-07-29 发布取代）

- 实现提交：`281ca626 重建 TOEFL v2 学生端考试工作台`；当前分支为
  `codex/toefl-student-workbench`，没有 push、merge、生产部署或小程序上传。
- 页面保持旧 TOEFL 刷题路由可用，新 `/toefl/mock` 入口继续显式显示 `STAGING PREVIEW`，支持套题目录、考前门禁、科目选择、设备检查、Reading → Listening → Speaking → Writing、resume、完成和报告。
- 服务端继续使用 v2 package、public definition、`ToeflMockAttempt` / `ToeflMockResponse`；新增/收紧了角色权限、同站 `returnTo`、definition-driven phase/group 导航、服务端倒计时、M1 route-m2 闭环、完成后只读、题型/重复 token 校验、录音时长与 MIME 校验、私有录音 token 隔离。
- Reading 使用来源 definition 的完整 passage/邮件/notice/inline Complete Words/MC/order；M1/M2 显示 18/9 分钟。Writing 的 Build a Sentence 保留重复 token，Email / Discussion 使用 7/7/10 分钟。
- Listening 已有真实音频组件契约：单次播放、禁拖动、audio-driven 状态；`local_source` 或不可用资产会明确阻断，并只在 Staging 提供显式跳过。Speaking 有独立麦克风测试、准备/作答倒计时、自动停止上传、失败重试；当前来源缺少可验证的题级 Speaking timing，正式模式仍阻断。
- 报告只把 `auto` 客观题纳入分母，blocked 题明确排除，manual 显示 `pending_teacher_review`；报告标注为 staging preview，不冒充正式成绩单。当前 Reading/Listening 仍只返回已验证的 `default` M2，`adaptive_available=false`。
- 新增结构/API/前端测试覆盖：权限、状态跳转与计时防篡改、route-m2 绕过、快速输入 flush、重复 token、录音题型、resume、单项模式、returnTo、blocked 分母、public definition 不泄露答案/来源路径。

### 终审修复（`cb268bb9`）

- `validate_navigation_state` 现在读取 definition 的 module `navigation.back_policy`：Listening disabled 回退返回 409，Reading/Writing 的 `within_module` 回退仍可用。
- attempt state 增加服务端维护的 `phaseTimers` 快照；跨 writing 子 phase 返回时恢复已访问 phase 的剩余值，客户端不能把已访问 phase 重置为定义满时长。
- state 的 audio 只接受 definition 内 Listening phase、`ready/skipped/played` 三个布尔字段；`skipped=true` 只允许 preview，并可通过 PUT → resume 恢复。
- response/recording 现在只允许当前 phase 的题，不能在 Reading M2 修改 M1；前端 flush 抽为 `toefl_response_queue.js`，实际等待 pending 与已 in-flight 请求，任一失败都会阻止前进并保留重试值。
- 终审复现新结果：`listening_forward_status=200`、`listening_forbidden_back_status=409 back_navigation_disabled`；`audio_state_put_status=200`、`audio_persisted=True`；Writing `100 → 420 → 100`，再次前进/返回保持 `≤200 / ≤100`；past-module response 为 `409 question_not_current`。
- 目录卡片现在区分 `题包审计：ready` 与 `正式门禁：未通过`；只有 `release_ready=true` 才显示正式门禁通过，不再把 manifest 的 ready 写成含混的“发布状态：ready”。

### 验证与浏览器 QA

- `python3 -m pytest -q tests/test_toefl_mock_v2.py tests/test_toefl_mock_frontend.py`：20 passed；`node --test tests/test_toefl_response_queue.js`：2 passed。
- TOEFL v2 + 旧 TOEFL rescue / 题库质量 / 导入 / 审计兼容集：72 passed。
- 全仓 `python3 -m pytest -q`：323 passed；2 个既有 `tests/test_static_audio_headers.py` 失败，均因该 worktree 缺少测试音频 fixture 而返回 404，未改静态音频链路。
- 相关 Ruff、`node --check static/js/toefl_mock.js`、Python 编译检查、`git diff --check` 均通过。
- 本地 `127.0.0.1:5001` fresh browser session 已走查目录、桌面/390×844 移动布局、Reading 18:00 与 inline 输入、快速输入后切题/刷新恢复、Listening `local_source` 明确跳过且题目仍显示、Writing Build a Sentence 重复 token；fresh session 控制台无 error/warn。真实麦克风权限弹窗和 MediaRecorder 录音未在无测试设备的浏览器中执行。

### 尚未完成 / 下一步

- 七套四科 source review 仍为 pending；现有音频仍是 `local_source`，未进入发布存储；Speaking 题级准备/作答时长证据仍缺；因此正式 release gate 仍不可用。
- 真实 adaptive easy/hard 分支没有来源证据，不能实现或伪造；当前仅允许 default 路由。
- 需要在真实学生登录、教师 review 流程和有麦克风/可播放音频的设备上继续 QA。上线前还需逐套完成来源复核、音频发布和正式门禁验证；本提交不包含部署。

## 背景记录：TOEFL 题库抢救与模考系统重做

### 用户目标与发布约束

- 用户要求按 `docs/TOEFL_MOCK_FLOW_SPEC.md` 的四科、自适应、计时和恢复流程完整重做 TOEFL 模考系统。
- 题库按“一套一套抢救、一套一套人工审阅、通过后再上线”的方式推进。
- 禁止模型猜测题目、选项、答案或音频对应关系；无法从来源证据确定的内容保持 `review_required`。
- staging 预览不等于线上发布；四科人工来源复核、媒体发布与严格门禁通过前，不得把套题状态改成 published。

### 2026-07-27 七套整合、证据清理与 spec-driven staging 纵向流程（历史记录；实现已随上方提交落盘）

- 七套 v2 包已全部进入 rescue worktree，共 840 个原子题、7 个 source-blocked：
  - `2026-01-21_A`：120 / blocked 4
  - `2026-01-21_B`：120 / blocked 1
  - `2026-01-21_C`：120 / blocked 1
  - `2026-01-27_A`：120 / blocked 0
  - `2026-01-27_B`：120 / blocked 1
  - `2026-01-28_A`：120 / blocked 0
  - `2026-01-28_B`：120 / blocked 0
- 清理阶段逐页渲染并复核了原来的 18 个 blocker，其中 11 个有充分来源证据，已固化到通用
  builder：B 卷 Reading M2 Q13、Listening M1 Q1/Q7 与 M2 Q1；C 卷 Listening M2 Q1/Q5；
  1 月 27 日 A 卷 Listening M1 Q1/Q2 与 M2 Q1；1 月 28 日 A 卷 Reading M2 Q6 与
  Listening M1 Q24。后两题的答案 PDF 与其他来源冲突，因此自动判分证据明确改用完整原文/听力原文，
  不把错误答案 PDF 当作证据。
- 剩余 7 题没有足够证据，继续 blocked：1 月 21 日 A 卷 Listening M1 Q15/Q18/Q21、M2 Q9；
  1 月 21 日 B 卷 Reading M2 Q12；1 月 21 日 C 卷 Reading M1 Q24；1 月 27 日 B 卷
  Listening M1 Q25。
- 七套均重新用本地原始来源根目录校验 SHA-256、引用、公开/私有答案分离与结构，全部 `pass`；
  严格 `--require-release-ready` 则七套全部按预期 `blocked`。1 月 27 日 A、1 月 28 日 A/B
  已达到 0 source-blocked / `publish_status=ready`，但四科人工审阅仍为 `pending`，不能正式发布。
- 新增 definition-driven 运行层：
  - `GET /toefl/mock` 七套 staging 目录；
  - `GET /toefl/mock/<testId>?preview=1` 新流程预览；
  - `GET /api/toefl/tests/<testId>/definition` 只返回 public-safe definition；
  - attempt start、response 增量保存、录音、M2 路由、resume、state、complete、report API 已接通；
  - `ToeflMockAttempt` / `ToeflMockResponse` 保存服务端续考状态，启动时幂等建表。
- 流程顺序按 spec 为 Reading → Listening → Speaking → Writing；Reading M1/M2 使用 18/9 分钟，
  写作三个阶段使用 7/7/10 分钟，听力保持 audio-driven。题数从来源 definition 读取，
  不把第一套 Listening 32+15 强裁成 spec 示例的 18+16。
- Reading / Listening M1 结束后调用服务端 M2 路由，但七套来源都只有一份可核对 M2；
  当前明确返回 `route=default`、`adaptive_available=false`，没有跨套拼接或猜造 easy/hard 题。
- blocked 题在 staging 可见但禁用，不进入判分分母；非 preview attempt 对所有未过门禁套题返回 409。
- 浏览器实测：
  - 目录正确显示 7 套 / 840 题与每套 blocked 数；
  - 1 月 21 日 A 卷可建立 staging attempt，计时从 18:00 开始；
  - Complete Words 已按 spec 在段落内联输入；
  - 输入答案后服务端显示“已保存”，刷新通过 URL `attemptId` 恢复答案与计时；
  - 快速连续填写两个文本题后立即切题，两题均在刷新后恢复；修复了共用 debounce 导致的丢答风险；
  - Reading M2 第一组的 Back 正确禁用，不能跨 Module 回退；单项完成后 `returnTo` 正确生效；
  - 导航到 Reading Q33，题干/四选项正确显示，选择 C 后服务端保存；
  - 浏览器控制台 0 error。
- 自动化：TOEFL v2、题库审计、旧导入与旧刷题兼容回归共 45 项通过；新服务/API/模型/
  测试/通用 builder Ruff、前端 JS 语法和 `git diff --check` 均通过。
- 尚未完成：
  - 学生端工作台实现已由上方 `281ca626` 在本地提交，但当前分支仍未 push；
  - 未部署生产，线上仍没有这七套新流程；
  - 原始音频仍是 `local_source`，未复制到发布存储；staging 只呈现不可用状态；
  - 剩余 7 个 blocked 题和七套四科人工来源复核仍需逐项完成；
  - 需要在真实登录学生/教师账号下再做一次权限与人工批改闭环 QA。

### 2026-07-27 续做：Q33 与 v2 staging（任务分支同步）

- 实际分支仍为 `codex/toefl-rescue`；本段从 `f2b54c00` 继续并随任务分支同步，精确 HEAD 以 `git log -1` 为准。
- 已视觉核对 `2026-01-21_A` Reading M1 Q33：
  - 题卷 `1.21新托福真题A卷/新托福真题01.pdf` 第 7 页给出完整题干与四选项；
  - 答案 `1.21新托福真题A卷/新托福真题01参考答案.pdf` 第 1 页明确为 C；
  - 两个来源文件 SHA-256 与 `data/toefl_quality/source_profiles.json` 一致。
- 没有修改 `data/toefl_practice/2026-01-21_A/reading.json` 或其他现有发布 JSON。已建立独立
  `data/toefl_practice_v2/2026-01-21_A/` staging：公开 `content.json` 不含答案，私有
  `answer_key.json` 记录 Q33=C 及题卷页/答案页证据。
- 复用了本地“新托福真题 v2 重建”契约、schema、pilot builder 与 validator，并做了 rescue 融合：
  - 单套生成不再强制依赖另一工作树的全库 inventory；
  - 发布门禁新增 `--require-release-ready`，结构通过但仍有 blocked 题时必须非零退出；
  - 四科人工审阅状态从 `data/toefl_quality/source_profiles.json` 写入 staging manifest，
    未全部 `approved` 时不能发布。
- 当前 staging 为 120 个原子题：Reading 50、Listening 47、Writing 12、Speaking 11；
  103 auto、13 manual、4 blocked。结构与来源校验 0 error。
- 严格发布门禁按预期 exit 1：Listening M1 Q15/Q18/Q21、M2 Q9 仍缺来源选项；
  套卷仍是 `pilot` / `blocked`；四科 source review 仍为 `pending`。
- 七套 v2 后续已全部整合进本 rescue worktree；清理后总计 840 个原子题、7 个 blocked。
  `2026-01-27_A`、`2026-01-28_A`、`2026-01-28_B` 已为 0 blocked / `ready` 候选，
  但仍需四科人工 `approved` 才能成为可发布套卷。详见上一节。
- 已验证：

```text
.venv/bin/python -m unittest \
  tests.test_toefl_practice_v2_rescue \
  tests.test_toefl_bank_quality \
  tests.test_import_toefl_real_exams \
  tests.test_toefl_practice
38 tests passed

.venv/bin/python scripts/validate_toefl_practice_v2.py \
  data/toefl_practice_v2/2026-01-21_A \
  --source-root '/Users/zhouxin/Desktop/新托福资料'
passed; 120 questions; 0 validation errors

.venv/bin/python scripts/validate_toefl_practice_v2.py \
  data/toefl_practice_v2/2026-01-21_A \
  --source-root '/Users/zhouxin/Desktop/新托福资料' \
  --require-release-ready
exit 1 as expected; 4 source-blocked questions + pilot/blocked/pending-review gates
```

- 下一步优先处理剩余 7 个明确 blocker；没有新增来源前不得猜补。随后对 0 blocker 的三套逐科
  做人工抽验并把审阅状态从 `pending` 改为 `approved`。

### 本次已完成（随任务分支同步）

- 新增纯逻辑审计模块 `services/toefl_bank_quality.py`：
  - 检查 manifest 发布状态、题目 ID/题号/Module 覆盖、四选项、答案可用性、填空数量、组句可构造性、音频引用与静态文件；
  - 检查不同 Listening Module 是否错误复用同一整段音频；
  - 只有无 critical/high、且来源科目人工标记 `approved` 时才判定为 release-ready。
- 新增 CLI `scripts/audit_toefl_practice_bank.py`：
  - 默认生成 `data/toefl_quality/latest_audit.json` 与 `docs/toefl_quality_audit.md`；
  - `--require-release-ready EXAM_ID` 在目标套卷仍有 critical/high 时以退出码 1 阻断发布。
- 新增 `data/toefl_quality/source_profiles.json`：
  - 已为 `2026-01-21_A` 建立源题卷、答案、听力原文、M1/M2 听力和口语音频的相对路径、SHA-256、页数/时长证据；
  - 四科 `review_status` 均为 `pending`，未冒充已审阅。
- 新增 `tests/test_toefl_bank_quality.py`，覆盖完整可发布样例、不完整已发布套卷、非四选项、来源缺题、模块共用音频和人工审阅门禁。
- 原始 PDF 已做视觉页级核对：
  - `2026-01-21_A` Reading：M1 Q1-Q35、M2 Q1-Q15；
  - Listening：M1 Q1-Q32、M2 Q1-Q15；
  - Writing：10 道 Build a Sentence + Email + Academic Discussion；
  - Speaking：7 道 Listen and Repeat + 4 道 Interview。
- 重要冲突：用户提供的 wofo 流程 spec 写 Listening M1 18 / M2 16，但第一套原始 PDF 明确是 M1 32 / M2 15。后续引擎必须 definition-driven；在用户审阅前不要把第一套强行裁剪成 spec 数量。

### 审计结果

- 全库：47 套、143 科、2,863 个题目对象、4,033 个计分项。
- 47 套全部处于 published，其中 32 套仍为 partial（68.1%）。
- critical 226、high 386、medium 23；严格门禁下 0/143 科可直接发布。
- 50 道选择题不是完整四选项；99 个自动题缺可靠答案；13 套听力的 M1/M2 复用同一整段音频。
- `2026-01-21_A` 当前发布门禁有 14 项 critical/high：
  - Reading M1 缺 Q33；
  - Listening M1 缺 Q7/Q15/Q18/Q21；
  - Listening M2 缺 Q3/Q9；
  - Writing Q2/Q3/Q4/Q5/Q7/Q8/Q10 的正确序列无法由当前展示词块构造；
  - 四科均未经过人工 `approved`。
- Listening 当前 `order` 不连续是导入器过滤上述残缺题后未重新编号造成的 medium 问题。

### 已运行验证

```text
.venv/bin/python -m unittest tests.test_toefl_bank_quality tests.test_import_toefl_real_exams tests.test_toefl_practice
33 tests passed

.venv/bin/ruff check services/toefl_bank_quality.py scripts/audit_toefl_practice_bank.py tests/test_toefl_bank_quality.py
All checks passed

git diff --check
passed

.venv/bin/python scripts/audit_toefl_practice_bank.py \
  --source-root '/Users/zhouxin/Desktop/新托福资料' \
  --require-release-ready 2026-01-21_A
exit 1 as expected; 14 critical/high blockers
```

### 本次任务分支同步文件

本次新增：

- `services/toefl_bank_quality.py`
- `scripts/audit_toefl_practice_bank.py`
- `tests/test_toefl_bank_quality.py`
- `data/toefl_quality/source_profiles.json`
- `data/toefl_quality/latest_audit.json`
- `docs/toefl_quality_audit.md`
- `docs/TOEFL_MOCK_FLOW_SPEC.md`（此前由 Claude 生成，本次只读取、未改）

本次没有修改现有题库 JSON、`toefl_practice.py`、前端、数据库或生产。

用户既有未跟踪文件仍需保留：

- `data/reading_study/browse.html`
- `data/reading_study/preview.html`
- `docs/dictation_input_policy_proposal.md`
- `docs/dictation_strict_result_layout_fix.md`
- `prototypes/`

### 次日精确起点

1. 开工先读本文件、`CLAUDE.md`、`docs/TOEFL_MOCK_FLOW_SPEC.md` 和 `docs/toefl_quality_audit.md`，再运行 `git status --short --branch` 与 `git log -5 --oneline`。
2. Reading Q33 已在 v2 staging 完成双证据恢复；不要写回现有发布 JSON。
3. 七套 spec-driven staging 运行层已经完成；不要重复实现，也不要把 staging 误写为已上线。
4. 继续处理剩余 7 个 blocker：A 卷 Listening M1 Q15/Q18/Q21、M2 Q9；B 卷 Reading
   M2 Q12；C 卷 Reading M1 Q24；1 月 27 日 B 卷 Listening M1 Q25。没有新增题卷页、
   答案或音频证据时保持 blocked。
5. 每完成一科就运行审计门禁并生成审阅清单；用户人工确认后才把该科 `subject_reviews` 改为 `approved`。
6. 0 blocker 的三套先做真实登录学生/教师账号 QA，再处理音频发布存储；严格门禁通过后才考虑生产发布。
7. 学生端工作台已在本地提交 `281ca626`，当前分支仍未 push；合并 `main`、部署和发布仍需单独明确授权。

### 本次提交涉及的已跟踪文件

以下文件已随实现提交 `d890cfa4` 推送；不要擅自覆盖、删除或重复实现。

实现提交已包含的文件：

- `miniprogram/components/english-keyboard/index.js`
- `miniprogram/components/english-keyboard/index.wxml`
- `miniprogram/components/english-keyboard/index.wxss`
- `miniprogram/pages/student/dictation/practice/index.wxml`
- `miniprogram/pages/student/dictation/practice/index.wxss`
- `miniprogram/pages/student/dictation/review/index.wxml`
- `miniprogram/pages/student/dictation/spell/index.js`
- `miniprogram/pages/student/dictation/spell/index.json`
- `miniprogram/pages/student/dictation/spell/index.wxml`
- `miniprogram/pages/student/dictation/spell/index.wxss`
- `miniprogram/utils/dictation-review.js`
- `services/dictation_review.py`
- `tests/test_dictation_review.js`
- `tests/test_dictation_review.py`
- `tests/test_miniprogram_spelling_markup.py`
- `design-qa.md`
- `docs/CODEX_HANDOFF.md`
- `docs/WORKLOG.md`
本次新增的未跟踪设计稿 `docs/dictation_strict_result_layout_fix.md` 仅作审阅参考，未纳入提交；它与本次相关但不作为部署事实来源。

本次新增并已随实现提交跟踪的生产资源：

- `miniprogram/images/growth-path-background.jpg`
- `miniprogram/images/icons/backspace-outline.svg`
- `miniprogram/images/icons/check-outline.svg`
- `miniprogram/images/icons/flag-outline.svg`
- `miniprogram/images/icons/speaker-wave-outline.svg`

用户既有的未跟踪内容：

- `data/reading_study/browse.html`
- `data/reading_study/preview.html`
- `docs/dictation_input_policy_proposal.md`
- `prototypes/`

上述用户既有文件本次没有修改。

## 近期完成

### 单词任务键盘可用性修复（已提交至 main，待小程序手动发布）

- 强化拼写页已按选定 Sage Path 参考图重做生产界面：品牌头、成长路径进度、居中中文释义、中央重听、方格拼写区和清新背景均已接入；未显示“严格拼写”和“实体键盘需教师授权”常驻文案。
- 初始方格全部为空，不预填或提示首字母；只有学生实际点击的字母会进入方格。视觉 QA 中的 `c`、`o` 是手动点击产生。当前输入位只用琥珀色方格描边标记，不在方格内显示容易产生错位感的闪烁竖线。
- 强化拼写只保留页面中央“重听”；强化记忆和词汇复习继续使用页面原有播放入口，共享键盘不再承载任何重听按钮。
- 键盘顶部新增只显示学生当前输入的“你的拼写”答案区，点击字母会即时更新；不读取或渲染目标答案。
- 共享键盘字母改为小写，使用独立文本层做光学垂直居中；确认键占满键盘宽度，背景图压缩为约 104KB JPEG，避免小程序主包被近 1MB PNG 占满。
- 强化记忆严格模式改为“题目卡占剩余空间 + 键盘固定底部”，移除严格模式下的空操作栏；无实体键盘授权时不再保留空的模式切换栏。
- 严格模式范围仍只限单词任务白名单的 `spell`、`practice`、`review`，阅读和听力页面未接入。

### 听写严格拼写首答恢复与结果态修复

- 实现提交：`d890cfa4`（2026-07-24）。根因是稳定的 task 首答幂等键正确锁住历史判定，但旧幂等响应缺少历史答案，前端把本次输入与历史判定错误拼接。
- 服务端新增兼容字段：幂等/重试响应返回历史 `student_answer` 和首答快照，任务队列返回已完成词的首答答案/判定；不改变首答计分、finalize、`queue_incomplete`、自动复习或权限语义。
- 前端恢复以服务端队列为事实源；历史答案和 `is_correct` 始终来自同一条记录，丢本地进度时从首个未首答词继续。没有开放学生重开改分入口；网络重试仍使用稳定幂等键。
- 结果态布局只作用于严格英文模式：收起输入控件、保持播放按钮圆形不压缩；compatible/native、`en_to_zh`、音频和三页既有交互保持原作用域。

### 单词任务严格拼写与提交失败防复发

- 提交：`ad258bc0`（2026-07-21，单词任务启用严格拼写与教师兼容授权）。
- `practice` 和 `spell` 两条学生答题流程均增加了切词锁，避免连续点击导致跨题或漏记。
- 提交接口报告队列缺题时，前端会根据 `queue_incomplete` 定位漏掉的单词并引导补做，不再只显示失败后卡住。
- 共用漏题识别逻辑位于 `miniprogram/utils/dictation-review.js`。
- 同批改动还包含严格英文输入和教师/助教兼容授权逻辑。

### 随后的主线改动

- `918126e4`（2026-07-21）：助教后台增加单词输入授权。
- `9607915a`（2026-07-21）：导入剑桥雅思21听力阅读真题（4套）。

## 验证状态

- 在 `ad258bc0` 状态下，Python 完整测试共 288 项通过，仓库内 JavaScript 测试全部通过。
- 本次只新增交接文档与入口规则，不涉及业务代码，未重复运行完整业务测试。
- 后续提交 `918126e4`、`9607915a` 的验证情况应以各自提交记录、CI 和实际复测为准；本文不推断未亲自验证的结果。
- 2026-07-23 最终本地验证：Python 全量 294 项通过；随后针对最终资源路径再跑相关 Python 21 项通过；仓库全部 Node 测试 12 项通过。
- 微信开发者工具清理临时 QA 条件后的普通编译为 0 error、3 条 warning，均为基础库/开发工具提示；已检查 iPhone 5（320×568）、iPhone 12/13 Pro（390×844）和 iPad（768×1024）模拟尺寸。
- 2026-07-23 20:08 再次在强化记忆测试状态验证：iPhone 12 点击 `Q` 后“你的拼写”即时显示 `q` 且确认键启用；iPhone 5 窄屏完整显示答案区、三行键帽及操作区。随后移除强化记忆/词汇复习键盘内重复“重听”，仅保留页面原有播放入口；临时 QA 分支和编译条件已全部移除。
- 2026-07-23 21:53 强化拼写最终视觉复核：390×844 初始答案为空，手动点击 `c`、`o` 后仅对应方格显示字母；确认键完整铺满键盘。来源与生产实现同屏对照记录在根目录 `design-qa.md`，结果 `passed`。
- 2026-07-24 严格拼写首答恢复：服务端 + 小程序结构定向 38 项通过，全部 Node 测试通过；Python 全量执行 295 项，本次相关用例通过，另有 3 项既有静态音频 fixture/Accept-Ranges 测试失败（工作树没有测试 mp3，未改无关静态链路）；`git diff --check` 和提交检查通过。

## 发布状态

- 后端和小程序是两条独立链路，详见 `CLAUDE.md`。
- 后端：实现提交 `d890cfa4` 已推送到 `main`。GitHub Actions [30082924695](https://github.com/KB77GG/studytracker/actions/runs/30082924695) 与后续状态提交的 [30083176762](https://github.com/KB77GG/studytracker/actions/runs/30083176762) 均成功；生产已部署包含 `d890cfa4` 的 main，`studytracker.service` 为 active，日志确认 `127.0.0.1:5002`，`/listening/tests` 返回 HTTP 200。
- 生产硬约束已核验：`gunicorn.conf.py` 为 `workers = 1`、`worker_class = "gthread"`、`threads = 6`；本次未在生产机运行 Whisper/Kokoro 等重模型。
- 小程序：此前已准备上传单词防复发改动，但本文没有“已上传/已提审/已发布”的确认记录。
- 2026-07-23 的键盘体验修复随 `d890cfa4` 一并进入后端仓库，但前端仍须单独通过微信开发者工具上传；后端无数据库迁移。
- 本次修复保持服务端首答定分、task finalize/queue_incomplete、自动复习和输入授权语义；新增字段是向后兼容的。旧客户端会忽略字段，新客户端遇到旧服务端幂等响应不会把当前输入冒充历史答案，但旧服务端无法提供队列历史快照，部署窗口需优先后端、再由用户上传小程序。
- 小程序仍未上传、提审或发布；上传版本、审核状态和实际发布时间待用户本人填写。

## 当前待办与下一步

1. 用真实学生账号在微信开发者工具/真机检查强化拼写与强化记忆的重听、长词、答错重试、暂时跳过、任务重进/换设备恢复，并确认严格英文结果态布局。
2. 由用户本人手动上传、提审、发布小程序；本任务未执行这些操作。
3. 若要消除全量测试中的 3 项静态音频失败，需补回对应测试 mp3 fixture 后单独修复/复测；该问题不属于本次改动。

## 收工更新模板

更新时替换过期内容，不要在文件末尾无限追加：

```markdown
最近更新：YYYY-MM-DD HH:mm（Asia/Shanghai）

当前分支 / HEAD / 远端状态：
本次完成：
涉及文件或提交：
已运行验证及结果：
后端部署状态：
小程序上传 / 审核 / 发布状态：
尚未提交或未跟踪内容：
已知问题：
建议下一步：
```
