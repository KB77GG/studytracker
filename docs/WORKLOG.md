# 工作日志（跨机器进度同步）

> 目的：在任何一台电脑上开工时，AI agent / 人先读这里，30 秒接上进度。
> 约定：每次有实质进展的会话结束时**追加一条**（新条目放最上面）；记"做了什么、现场状态、下一步、坑"，不记代码细节（看 git log/diff）。
> 注意：这里要记录 **git 之外的状态**（生产库操作、服务器上的手动步骤、外部服务状态），这些从 commit 历史里看不出来。

---

## 2026-08-02 学生端模考逐题复盘入口（发布中）

- 新增 token 隔离的学生复盘路由 `/exam/<exam_id>/session/<token>/review`；只有整场状态为
  `submitted` 才加载题库和答案，未交卷会退回考试流程，错误 token 返回 404。
- 学生成绩页新增「查看逐题复盘」入口；学生复盘与教师后台复用同一套题干、答案、对应原文、全文、
  解析和写作图表组件，避免两端显示能力继续分叉。Task 1 图表也直接补到学生成绩页。
- 验证：模考复盘相关定向 Python 34 passed，真实 `app.url_map` 已注册学生路由，Ruff、全部 Node 与
  `git diff --check` 通过；用户已授权与前一提交一起推送 `main`，生产结果待 GitHub Actions 和 5002 验证。

## 2026-08-01 模考复盘上下文、答题隔离与 NOT GIVEN 误判修复（本地已完成/未部署）

- 独立工作树 `/Users/zhouxin/.codex/worktrees/mock-exam-review-isolation/studytracker`，分支
  `codex/mock-exam-review-isolation`，基于 `origin/main@3d5a74fd`；主工作树及其未跟踪文件未改。
- 复盘页补完整题组题干、题目选项、题目解析、逐题定位原句；听力按题目时间戳定位 transcript，
  阅读读取 central sentence，并支持按 Section/Passage 展开完整听力原文或阅读文章；写作 Task 1
  同时显示题库图表，并可点击查看原图。
- 根因修复：模考听力草稿原按浏览器旧 `listening_student/guest` 键恢复，阅读还会读取普通刷题的
  最近提交；现改为严格按模考 `session_token` 隔离，模考模式跳过普通练习历史，阅读增加同会话草稿恢复，
  成功交卷后清理本会话草稿。
- 发现并修复独立判分缺陷：部分题库把 `NOT GIVEN` 拆成 `key=NOT/text=GIVEN`，旧判分器不认识
  `NOT`。新前后端统一映射；教师打开成绩列表/复盘时只对可明确识别的这类历史误判幂等重算。
  剑21 Test4 截图答案由旧 32/40 校正为 37/40，真实错题为 Q18/Q23/Q37。
- 验证：定向 Python 30 项、全部 Node 测试、Ruff、Black、模板双模式渲染和 diff check 通过；
  剑21 Test4 Task 1 图表静态请求返回 200 `image/png`；
  Chrome headless 1440px 实际渲染复盘页，题组、答案表、逐题原句/解析和阅读/听力两科布局正常；
  Python 全仓 327 项中 325 通过，2 个既有静态音频 Range 测试因独立工作树缺 mp3 fixture 返回 404。
- 本地任务分支已完成；未 push、未部署，生产会话尚未变更。上线后首次打开考试 8 成绩列表即可触发窄范围历史修正。

## 2026-07-29 三套 TOEFL 2026 正式刷题流程（已部署）

- 已将 `2026-01-27_A`、`2026-01-28_A`、`2026-01-28_B` 从线上 preview 升为正式题包；每套 120 题、0 blocked，目录显示 `published / 正式门禁：通过`。旧 `data/toefl_practice` JSON 和旧版路由未修改。
- Speaking 重建为 11 个原子题组：Q1–Q7 Listen and Repeat 为 0 秒准备 / 12 秒录音，Q8–Q11 Take an Interview 为 0 秒准备 / 45 秒录音；两阶段 180 + 300 = 480 秒。Q1/Q8 cue 包含任务说明与场景，其余 cue 只播放当前题。
- cue 由三条原始 MP3 的逐词时间戳生成，门禁要求范围在音频时长内且对齐置信度 ≥0.96；公开 definition 不再下发口语原文。页面单次点击后自动播放、录音、限时停止、上传并进入下一题；服务端拒绝跨题、超时和正式模式第二次录音。
- 用户明确免除额外四科来源终审，manifest 以 `owner_authorized` 记录这项发布授权，没有伪写四科 review 为 approved。三套严格 `--require-release-ready` 均为 120 questions / 0 errors / pass；七套结构与来源校验仍全部通过。
- 音频无需重复上传：线上 9 条 listening/speaking MP3 均返回 Range 206；三条 speaking MP3 的线上 SHA-256 与本地来源逐一一致。
- 验证：相关 Python 30 passed；全部 Node 14 passed；全仓 Python 329 passed，另有 2 个既有 `tests/test_static_audio_headers.py` 因本 worktree 缺少静态 fixture 返回 404；相关 Ruff、JS syntax、Python compile 和 diff check 通过。
- 发布提交 `a6d20e4a` 已推送任务分支与 `main`；并行的 `fd711f1c` 已保留。CI [30416264782](https://github.com/KB77GG/studytracker/actions/runs/30416264782) 与生产部署 [30416264768](https://github.com/KB77GG/studytracker/actions/runs/30416264768) 成功。服务器 HEAD 为 `a6d20e4a`，`studytracker.service=active`，监听 `127.0.0.1:5002`，gunicorn 保持 `workers=1 / gthread / threads=6`。
- 生产浏览器已验收三套目录、正式门禁、Speaking 单项入口和前端脚本，无 console error/warn；出于不采集环境音，未在自动化浏览器中授权真实麦克风。下一步应由登录学生在真实设备完成一遍 11 题录音，再验收教师人工批改闭环。

## 2026-07-27 模考后台「复制链接 + 逐题复盘」与综合分进位修复（已部署）

- 起因：配完卷只能进考试页手动抄网址；教师端看不到学生做题详情。
- 模考列表页新增「复制链接」「复制邀请语（含 pincode 与使用说明）」，剪贴板 API 失败时回退
  execCommand；列重排为 ID/名称/配卷/Pincode/状态/分发/操作，按钮竖排不再被挤出可视区。
- 新增 `api/mock_exam_admin.py`（`/admin/mock-exams/<id>/sessions` 成绩列表、`/sessions/<sid>`
  逐题复盘）+ `services/mock_exam_review.py` 纯逻辑。复盘直接读交卷时写入的 `*_results_json`，
  **不重新判分**，按 section/passage + 题组展示 学生答案/正确答案/判定，支持「只看错题」；
  写作显示原题 prompt + 原文 + 词数（仍人工评分）。时间统一按北京时间展示。
- 修复既有算分缺陷：综合分原用 `round()`（银行家舍入），平均 6.25 会显示 6.0。按雅思口径
  （.25 进半分、.75 进整分）改为 half-up，学生成绩页与复盘页共用 `mock_exam_review.overall_band`。
  这会**改变历史会话页面上显示的综合分**（库里不存综合分，每次渲染时算），只影响 .25 的情形。
- 验证：本地 seed 两条会话浏览器实测三页正常、复制按钮真实点击成功、只看错题隐藏 24/77 行、
  控制台 0 error；新增 13 项单测；全量测试见当次记录；ruff/black 通过；验证数据已清理。
- 后续可做：成绩导出 CSV。

## 2026-07-27 TOEFL 目录状态语义澄清（本地提交，未 push / 未部署）

- 在 `codex/toefl-student-workbench` 追加实现提交 `3b1d4fd0`：目录卡片把 manifest 的 `publish_status=ready` 显示为“题包审计：ready”，并单独显示“正式门禁：未通过/通过”（由 `release_ready` 决定）。没有修改数据、其他页面、生产或小程序。
- 页面测试新增断言：非 release-ready 套题出现“题包审计：ready · 正式门禁：未通过”，且不出现含混的“发布状态：ready”。
- 验证：`tests/test_toefl_mock_v2.py` + `tests/test_toefl_mock_frontend.py` 20 passed；Ruff 和 `git diff --check` 通过。当前分支仍未 push。

## 2026-07-27 TOEFL V2 终审四组问题修复（本地提交，未 push / 未部署）

- 在 `codex/toefl-student-workbench` 追加提交 `cb268bb9`，没有 push、merge、生产部署或小程序发布，也没有修改已发布 JSON。
- 修复 Listening `back_policy=disabled` 被服务端放行、Writing 子 phase 回退重置计时、audio state PUT 后 resume 丢失、Reading M2 修改 M1 答案四项缺口。
- 服务端现在保存 per-phase `phaseTimers`，只恢复已访问 phase 的 snapshot；audio state 仅允许 Listening phase 和 `ready/skipped/played` 布尔白名单，preview 外禁止 skipped；答题只接受当前 phase。
- 将快速输入 flush 抽成实际被前端使用的 `static/js/toefl_response_queue.js`，Node 行为测试验证 pending/in-flight 等待、失败传播和重试值保留。
- 终审复现结果：Listening forward 200 / forbidden back 409；audio PUT 200 / resume persisted True；Writing `100 → 420 → 100`，再次前进/返回不回满；past-module response 409。
- 验证：TOEFL v2 + 旧兼容相关 72 passed；Node queue 2 passed；全仓 323 passed，另有 2 个既有静态音频 fixture 缺失导致的 404 失败；Ruff、JS 语法、Python 编译和 diff check 通过。
- 下一步仍是 source review、音频发布、Speaking timing 证据和真实设备/账号 QA；正式 release gate 通过前不得部署。

## 2026-07-27 TOEFL V2 学生端工作台重建（本地提交，未 push / 未部署）

- 在 `codex/toefl-student-workbench` 上从 `5801849c` 继续，完成提交 `281ca626`；没有 push、merge、生产部署或小程序发布，旧 TOEFL 路由保持并行可用。
- 重建学生端流程：套题目录、考前门禁、科目选择、Speaking 麦克风测试、Reading / Listening / Speaking / Writing 工作台、resume、完成与 staging 报告。服务端收紧权限、状态迁移、倒计时、M1 route-m2、完成后只读、题型校验、录音上传隔离和 `returnTo` 安全路径。
- Reading/Listening 继续 definition-driven；Reading 18/9 分钟，Writing 7/7/10 分钟；Listening 对 `local_source` 音频明确显示缺口，不使用错误音频或静默完成；Speaking 无题级可验证 timing 时正式模式阻断。报告排除 blocked/manual 客观题分母，manual 为 `pending_teacher_review`。
- 新增前端/API 测试覆盖快速输入 flush、重复 token、单项模式、resume、计时防篡改、M2 route 绕过、录音题型和 public definition 脱敏。
- 验证：相关 16 项通过；TOEFL v2 + 旧兼容相关 69 项通过；全仓 320 项通过，另有 2 个既有静态音频 fixture 缺失导致的 404 失败。Ruff、JS 语法、Python 编译和 diff check 通过。
- 浏览器 fresh session 已验证目录、桌面/移动布局、Reading 快速输入保存与刷新恢复、Listening 音频缺口显式跳过、Writing 重复 token；控制台无 error/warn。真实麦克风权限和录音设备 QA 尚未完成。
- 下一步：真实学生/教师账号权限与人工批改闭环、发布音频、补齐 Speaking timing 证据、完成四科人工 review；真实 adaptive 分支仍无证据，不能实现。正式 release gate 通过前不得部署。

## 2026-07-27 TOEFL 七套 v2 整合、证据清理与新 spec 运行层（本地未提交、未部署）

- rescue worktree 已整合 7 套 / 840 个原子题，不改写旧的已发布 JSON。逐页复核原来的 18 个
  blocker 后，11 个题目由原题页、完整源文本或听力原文恢复；剩余 7 个无充分证据，继续 blocked。
- 当前逐套 blocked 为 4 / 1 / 1 / 0 / 1 / 0 / 0。七套来源哈希和结构校验全部通过；
  严格发布门禁七套仍全部阻塞。`2026-01-27_A`、`2026-01-28_A/B` 虽 0 blocked，
  仍因四科人工审阅 pending 不能发布。
- 1 月 28 日 A 卷 Reading M2 Q6 与 Listening M1 Q24 的答案 PDF 和其他来源冲突；
  修复分别采用能还原 `elaborate` 的完整源文本和明确要求 credited sources 的听力原文，
  并在私有答案证据中排除冲突的答案 PDF。
- 新增 `/toefl/mock` staging 目录、public definition、服务端 attempt/response 状态、增量保存、
  刷新续考、M2 路由、录音、完成与报告 API；流程按 Reading→Listening→Speaking→Writing。
- 当前来源只有一个可信 M2，路由明确返回 default，不编造 easy/hard；题数按每套 definition，
  不强行套用 spec 中的示例题数。
- 相关自动化 45 项通过，Ruff、JS 语法与 diff 检查通过；浏览器实测目录、开考、18 分钟
  Reading M1 计时、段落内联填词、快速连续两题保存/刷新恢复、M2 禁止跨模块回退、`returnTo`
  和 Q33=C，控制台 0 error。
- 当前未 commit/push、未部署；音频未进发布存储，七套仅为 staging 预览。下一步先完成全量
  回归与真实账号 QA，再逐套完成人工来源复核和剩余 7 个 blocked 项抢救。

## 2026-07-27 TOEFL Q33 双证据恢复与 v2 staging 门禁（任务分支同步）

- 在独立 `codex/toefl-rescue` worktree 从 `f2b54c00` 继续并随任务分支同步；未合并 `main`、未部署。
- `2026-01-21_A` Reading M1 Q33 已按题卷第 7 页恢复完整题干/四选项，按答案 PDF 第 1 页确认 C；
  两个来源 SHA-256 匹配既有来源档案。现有 `data/toefl_practice` 发布 JSON 零改动。
- 建立 `data/toefl_practice_v2/2026-01-21_A` staging：120 个原子题，103 auto、13 manual、
  4 blocked；公开内容与私有答案分离，Q33 记录题卷页和答案页双证据。
- 接入本地 v2 重建契约/schema/builder/validator，并补真正的 `--require-release-ready` 门禁；
  四科审阅状态直接复用 `data/toefl_quality/source_profiles.json`。
- 结构/来源校验 0 error，相关 38 项 unittest 通过；严格发布门禁按预期 exit 1，因为 Listening
  M1 Q15/Q18/Q21、M2 Q9 仍缺选项，且套卷/四科审阅状态尚未达到发布条件。
- 本地另一工作树已有 7 套 v2（840 题，合计 18 blocked；仅 `2026-01-28_B` 为 0 blocked 候选）。
  后续应把 rescue 来源审阅门禁作为所有 v2 包的统一上线前置，不能只看结构 validator。
- 下一步：独立复核 v2 候选恢复的 Listening M1 Q7、M2 Q3，再处理四道 source-blocked 听力题。

## 2026-07-26 TOEFL 题库抢救启动（任务分支同步，保留 50% 额度次日接力）

- 用户决定按“一套一套抢救、人工审阅后再上线”的方式完整重做 TOEFL 模考，目标流程见未跟踪的 `docs/TOEFL_MOCK_FLOW_SPEC.md`。
- 本次只完成题库质量门禁和 `2026-01-21_A` 来源结构档案，没有修改现有题库、刷题前后端、数据库或生产。
- 新增 `services/toefl_bank_quality.py`、`scripts/audit_toefl_practice_bank.py`、`tests/test_toefl_bank_quality.py`、`data/toefl_quality/` 和 `docs/toefl_quality_audit.md`；仅随 `codex/toefl-rescue` 任务分支同步，不触发生产部署。
- 全库审计：47 套/143 科/2,863 题目对象；32 套 published 但仍 partial；50 道非完整四选项、99 个自动题缺答案、13 套听力 M1/M2 共用同一整段音频；严格门禁下 0 科可直接发布。
- 第一套源 PDF 页级结构已核对：Reading 35+15、Listening 32+15、Writing 12、Speaking 11。它与 wofo spec 的 Listening 18+16 有冲突，后续引擎必须 definition-driven，不要强行裁剪来源题。
- 第一套当前阻塞：Reading 缺 Q33；Listening 缺 M1 Q7/15/18/21 与 M2 Q3/9；Writing 7 道组句词块无法构造答案；四科均待人工批准。
- 验证：相关 33 项 unittest 通过，ruff 通过，`git diff --check` 通过；`--require-release-ready 2026-01-21_A` 按预期退出 1 并报告 14 项 critical/high。
- 用户要求本次最多使用 50% 可用额度，剩余留到次日在另一台电脑继续；精确文件、命令和下一步见 `docs/CODEX_HANDOFF.md`。

## 2026-07-24 听写严格拼写首答恢复与结果态修复（后端已部署，待小程序发布）

- 根因：任务首答 attempt id 是稳定幂等键，服务端会正确保留旧首答成绩，但旧幂等响应没有返回历史答案；前端又把本次输入和历史判定拼接，导致“本次输入正确却显示错误”。
- 修复：服务端响应新增 `student_answer` 与首答快照字段，任务队列返回已完成词的首答答案/判定；前端恢复优先使用服务端队列，幂等/重试结果用同一条记录的答案与判定映射，丢本地进度后从首个未首答词继续。没有开放学生重开改分入口，正常首答仍不可改写。
- 结果态继续仅收起严格英文键盘的输入控件，播放按钮保持不压缩；compatible/native、中文模式、音频、自动复习、教师授权、申诉和 finalize/queue_incomplete 流程未改语义。
- 验证：定向服务端 + 小程序结构 38 项通过；全量 Python 295 项中本次相关用例通过，另有 3 项既有静态音频 fixture/Accept-Ranges 测试失败（测试音频未在该工作树提供，未改无关静态链路）；全部 Node 测试通过，`git diff --check` 和提交检查通过。
- 发布：实现提交 `d890cfa4` 已 commit/push；GitHub Actions [30082924695](https://github.com/KB77GG/studytracker/actions/runs/30082924695) 与后续状态提交的 [30083176762](https://github.com/KB77GG/studytracker/actions/runs/30083176762) 均成功。生产已部署包含 `d890cfa4` 的 main，`studytracker.service` active，`/listening/tests` 在 5002 返回 HTTP 200；gunicorn 已核验 `workers=1`、`gthread`、`threads=6`。后续仅文档提交不改变业务代码。
- 当前状态：小程序尚未上传、提审或发布。无关未跟踪的 `data/reading_study`、`prototypes/`、`docs/dictation_input_policy_proposal.md`、`docs/dictation_strict_result_layout_fix.md` 等继续保留且不进本次提交。

## 2026-07-24 模考分部导航修复（消除提交按钮误触）

- 问题：模考听力(4部分)/阅读(3篇)科目内，右下角常驻橙色"提交并结束"按钮，做完一部分想翻页却容易误触直接交卷；翻页只能靠顶部标签或底部题号。
- 修复（纯前端 `templates/listening/test_practice.html` + `reading/test_practice.html`）：右下角按钮改为分部感知——非最后一部分时为蓝色「下一部分 →」（点击只翻页、无弹窗、无判分），仅在最后一部分变橙色「提交并结束 X」（保留二次确认）。销毁性操作只在真正末部分出现，误触点消除；顶部标签/底部题号跳转也同步按钮状态；超时自动交卷、普通练习页零回归。
- 浏览器实测：听力4部分/阅读3篇逐部分推进、三条导航路径同步、末部分确认取消不提交、非模考页无影响，控制台零错误。

## 2026-07-24 剑21 听力刷题数据修复（题干缺失 + 点题跳转错乱）

- 根因均为 idictation 剑21 新书源数据录入差异：①多选组题干只存在 `collect_option.title`、组级 `title` 为空（波及全 4 套共 13 组，不止用户报的 3 个 part）；②题目级 `start_time/answer_sentences` 全空 → 点题跳 0:00（波及全部 160 题）。
- 修复在 `build_listening_test_practice.py` 数据层：组题干回退 `collect_option.title`；时间第四级回退解析 `ai_central_sentences.location_sentence` 句索引（160/160 可解析），合成剑20 形状的 `answer_sentences`。只重建剑21 四套 JSON，剑4-20 与精听文件零触碰，前端零改动。
- 验证：两项扫描清零；3 题 whisper 截段转写抽验定位正确；精听时间轴独立验证本来就准确（0.95-0.99 相似度），不在修复范围。

## 2026-07-23 单词任务键盘可用性修复（本地未发布）

- 强化拼写已按 Sage Path 参考图重做生产界面，保留品牌头、成长路径进度、中文释义、中央重听、方格答案区和清新背景；没有“严格拼写”、常驻教师授权提示或首字母预填。单字符方格的当前输入位只保留琥珀色描边，不显示容易错位的闪烁竖线。
- 强化拼写中央只有一个重听入口；强化记忆和词汇复习使用页面原有播放入口。共享键盘只负责字母、退格、确认、重试、跳过和下一题。
- 键盘字母改为小写并用独立文本层做光学垂直居中，确认键铺满宽度；背景资源压缩为约 104KB JPEG。强化记忆页继续使用“题目卡 + 底部键盘”稳定分区。
- 覆盖 320×568、390×844、768×1024 开发者工具模拟尺寸；390×844 初始方格全空，手动点击 `c`、`o` 后只显示真实输入，最终普通编译 0 error。
- Python 全量 294 项、最终相关 Python 21 项、仓库全部 Node 测试 12 项通过；阅读/听力页面的全仓范围检查无键盘引用；视觉 QA 见根目录 `design-qa.md`。
- 临时 QA 页面分支和开发者工具编译条件已移除；当前没有 commit / push / 小程序上传，后端与数据库无变更。下一步是真实学生账号真机回归后由用户手动上传。

## 2026-07-22 三科模考上线 + 教师材料布置启用

- **三科模考**（commit `a9799065`）：模考在听力/阅读之外新增写作科（60min、Task1/Task2、自动存稿、截止自动交卷、不自动判分留老师评）。写作题库剑4–21 共 72 套已构建入库（`static/writing_tests/`，Task1 图表图齐全）。旧两科模考零回归。
- **教师按材料布置剑雅阅读**：生产 MaterialBank 已导入剑4–21 全量 **216 篇 / 2880 题**（type=`ielts_reading_practice`）。入口在 web 后台 `/materials` 与 `/tasks`（小程序端无需发版，学生端消费已有任务流）。
- 生产已执行：`scripts/migrate_mock_exam_writing.py`（幂等补列）；库备份 `app.db.bak-20260722`。
- 修复昨日遗留：剑21 听力 Test2 题目配图漏提交（已补）；`test_practice_tables` 计数 193→196。
- **下一步/待办**：老师实际建一场剑21 三科模考做真人 QA；可选项——写作 AI 预评分接入（评分 skill 已有，未接）；模考结果页总分目前只平均听力+阅读。

## 2026-07-21 剑桥雅思21 听力阅读导入上线

- 剑21 听力 4 套（整卷刷题 + 精听 16 section + 16 mp3）与阅读 4 套（整卷刷题 + catalog 全量重建）导入并部署（commit `9607915a`）。数据来自 idictation.cn 既有流水线，跑法与坑位见 [docs/IMPORT_PIPELINES.md](IMPORT_PIPELINES.md)。
- 生产手动步骤（git 外）：16 个 mp3 scp 到服务器 `static/listening/`（mp3 在 .gitignore）；阅读 raw 数据在服务器 `/tmp/idict_reading_raw.json`。
- 生产库备份：`app.db.bak-20260721`。
