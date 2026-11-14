# 模考防作弊（考试诚信模式）实施计划 — 交给 Codex 执行

> 编写日期：2026-11-14。基线：`main@75ff855`。本文件是完整任务说明，执行前仍须按 `CLAUDE.md` 先读 `docs/CODEX_HANDOFF.md` 与 `docs/WORKLOG.md`。
> 本文中标注 **【需核对】** 的内容是未经真机或官方文档验证的判断，实施时必须先核对再写代码，不得照抄。

## 0. 一句话目标

让学生在 iPad / MacBook Air 上做雅思网页模考（`/exam/<id>`）时，离开页面、分屏、复制题干、粘贴作文、换设备这些行为**被记录、被警告、超限被锁定**，老师端能实时看到并一键解锁；再提供免费的真锁屏方案（Safe Exam Browser / iPad 引导式访问）。

做不到、也不要假装做到的事：网页无法物理阻止学生离开；用第二台设备拍照问 AI 无法用软件阻止，只能靠第二期的数据异常标记加老师抽查。

## 1. 红线（任何一条做不到就停下来问用户，不要变通）

1. **用户明天（2026-11-15）要用现有模考。在用户明确说“可以部署”之前，禁止 push 到 `main`**（push main 即自动部署并重启 gunicorn）。在隔离 worktree 和任务分支上开发。部署前向用户确认当天没有正在进行的模考。
2. **默认关闭。** 没有为某场模考显式开启时，学生端页面不加载任何新脚本，现有路由、JSON、模板输出、计时、草稿、交卷、复盘行为必须与现在完全一致。
3. **不改现有表。** 不对 `mock_exam`、`mock_exam_session` 及任何现有表做 `ALTER`，不给 `MockExam` / `MockExamSession` 加列、加 relationship、加 backref。只新增表。原因：代码先于迁移上线时，现有模型多一列就会让所有模考查询报错。
4. **故障放行（fail-open）。** 新功能的任何异常（表不存在、查询失败、JS 报错、接口超时）都必须退化成“本场未开启防作弊”，不能让学生打不开试卷、存不了草稿、交不了卷。
5. **锁定不拦交卷。** 现有草稿接口、交卷接口、到时自动交卷逻辑一行不动，也不因锁定状态拒绝请求。锁定只是前端遮罩加服务端状态；计时照常走，到时照常自动交卷判分。
6. **听力阶段不锁定**，只记录和警告。听力音频不可重播，误锁的代价不可挽回。
7. 遵守 `CLAUDE.md`：不往 `app.py` 加代码，新逻辑放新蓝图加 service；路由函数 < 60 行；不新写 `_normalize_*`。

## 2. 现状（已核对代码）

- 雅思模考学生流程在 `app.py` 8580–9010 行：`/exam/<id>` 登录（姓名 + pincode）→ `/exam/<id>/session/<token>` 章节页（`templates/exam/process.html`）→ 听力 / 阅读（复用 `templates/listening/test_practice.html`、`templates/reading/test_practice.html`，由 `exam_context` 区分模考态）→ 写作（`templates/exam/writing.html`）。
- 服务端掌握计时和截止时间（`services/mock_exam_runtime.py`）；草稿、开考接口在 `api/mock_exam_student.py`。离开页面不停表。
- 模考目前没有离开检测。`visibilitychange` / `pagehide` 只用于刷草稿（`static/js/practice_shell.js:570`）。
- 写作页不拦粘贴。同名同口令在第二台设备登录会拿到同一个 session，没有设备绑定。
- 入学测已有同类机制可参考：`api/entrance_session.py`（设备哈希、离开计次、超时锁定、老师解锁、心跳）、`entrance_web/assets/student.js:301`、模型 `EntranceTestDraft`。**参考其写法和测试方式，不要直接复用它的表。**
- 生产库是 SQLite，gunicorn 单 worker、6 线程、端口 5002。
- 托福模考（`/toefl/mock`，`api/toefl_mock.py`）是另一套流程，带麦克风授权弹窗。**不在本计划第一期范围内**，新模块按通用方式设计，留待雅思验证稳定后再接。

## 3. 第一期：系统内置考试诚信模式

### 3.1 新增文件（不改现有文件的逻辑）

| 文件 | 内容 |
|---|---|
| `services/exam_integrity.py` | 纯逻辑：策略读取、事件处理、离开计次、锁定和解锁、状态序列化。所有函数接受可注入的 `now`，便于单测。 |
| `api/exam_integrity.py` | 新蓝图：学生端事件 / 状态接口（token 鉴权，与现有模考接口一致），老师端监考面板和操作接口（登录鉴权，角色同 `api/mock_exam_admin.py::_can_manage`）。 |
| `static/js/exam_guard.js` | 学生端守卫脚本。UMD 写法，纯逻辑可被 Node 测试 `require`（参考 `static/js/practice_shell.js` 与 `tests/test_practice_shell.js`）。 |
| `static/css/exam_guard.css` | 遮罩、警告条、水印样式。 |
| `templates/exam/_integrity_guard.html` | 学生页面引入片段。未开启时渲染为空字符串。 |
| `templates/admin/mock_exam_integrity.html` | 老师监考面板。 |
| `templates/exam/integrity_guide.html` | 设备设置指引页（见第 5 节）。 |
| `scripts/create_exam_integrity_tables.py` | 建表兜底脚本，纯 `sqlite3`，带 `--database`、`--dry-run`，参考 `scripts/migrate_mock_exam_review.py`，不 import `app`。 |
| `docs/EXAM_INTEGRITY_RUNBOOK.md` | 老师用的故障处理手册（见第 7 节）。 |

### 3.2 允许改动的现有文件（每处只加最小接入点）

- `models.py`：在 Mock Exam 模型组之后新增 3 个模型，不动现有类。
- `api/__init__.py`：注册新蓝图。
- `templates/listening/test_practice.html`、`templates/reading/test_practice.html`、`templates/exam/writing.html`：在 `</body>` 前、已有 `{% if exam_context %}` 语义下加一行 `{% include "exam/_integrity_guard.html" %}`。
- `templates/exam/process.html`：加一行 include（用于规则确认卡片）。
- `templates/admin/mock_exam_sessions.html`、`templates/admin/mock_exams_index.html`：各加一个“监考 / 防作弊”入口链接。不改表格列数。
- `templates/admin/mock_exam_session_detail.html`：加一个 include 展示该生诚信记录摘要。
- `.github/workflows/ci.yml`：把新测试加进现有 job。

`app.py` 不改。模板需要的开关通过新蓝图注册的 Jinja 全局函数提供（例如 `exam_integrity_config(exam_id, token, section)`），该函数内部捕获一切异常并返回 `None`。

### 3.3 数据模型（3 张新表，与现有表无外键）

用通用键，便于以后接托福：`exam_kind`（本期固定 `"ielts_mock"`）加字符串引用。

- `exam_integrity_policy`：`exam_kind`、`exam_ref`（模考 id）唯一；`mode`（`off` / `monitor` / `enforce`）、`max_leaves`（默认 3）、`max_hidden_seconds`（默认 60）、`updated_by`、时间戳。**没有记录等同 `off`。**
- `exam_integrity_state`：`exam_kind`、`session_ref` 唯一；`device_hash`、`acked_at`、`last_seen_at`、`hidden_at`、`hidden_page_id`、`leave_count`、`hidden_seconds`、`blur_count`、`copy_blocked_count`、`paste_blocked_count`、`device_conflict_count`、`is_locked`、`locked_reason`、`locked_at`、`locked_section`、`unlock_count`、`unlocked_at`、`unlocked_by`、`exempt`、`exempt_by`。
- `exam_integrity_event`：`state_id`、`type`、`section`、`question_ref`、`duration_seconds`、`detail_json`（≤ 1KB）、`client_ts`、`created_at`。单场上限 2000 条，超出后只更新计数不再插入。

建表方式：老师打开监考面板时调用 `ensure_schema()`，用 `Model.__table__.create(bind, checkfirst=True)` 只建这 3 张表（每进程一次，带异常保护）。**学生端路径不做任何 DDL。** `scripts/create_exam_integrity_tables.py` 作为兜底。加一条测试，保证脚本建出的列与 SQLAlchemy 模型一致。

### 3.4 策略读取必须隔离

学生页面渲染时读取策略，用**独立连接**执行只读查询（`db.engine.connect()`），包在 `try/except` 里，失败返回 `off`。不要用 `db.session` 查，因为表不存在时的异常会污染当前请求的会话，连带回滚阅读开考等已挂起的写入。

另设硬开关：环境变量 `EXAM_INTEGRITY_DISABLED=1` 时全局视为 `off`。

### 3.5 三种模式

| 模式 | 学生看到 | 行为 |
|---|---|---|
| `off`（默认） | 与现在完全一样 | 不加载脚本，不记录 |
| `monitor` 仅记录 | 开考前的规则说明 | 记录全部事件；不警告、不遮罩、不锁定、不绑定设备 |
| `enforce` 警告并锁定 | 规则说明、警告、遮罩 | 下述全部规则生效 |

上线后第一场真实模考先用 `monitor`，看 iPad 和 Mac 上的误报情况，再切 `enforce`。

### 3.6 离开判定（要精确，宁可漏判不可误伤）

**计次的离开（strike）只有一种来源：`document.visibilityState` 变为 `hidden`。** 包括切标签页、切 App、回主屏、锁屏、最小化。

- 每次页面加载生成随机 `page_id`。
- `hidden` 用 `navigator.sendBeacon` 上报；`visible` 用普通请求上报，并带上客户端自测的隐藏毫秒数作为 beacon 丢失时的兜底。时长以服务端两次事件的时间差为准。
- **同一 `page_id` 的 `hidden → visible`**：时长 ≥ 2 秒计 1 次离开，累加时长；< 2 秒只记日志不计次。
- **新 `page_id`、同一未交卷科目的 `hello` 遇到未闭合的 `hidden`**（学生离开后页面被刷新或被系统回收）：间隔 ≥ 10 秒计 1 次离开；< 10 秒视为普通刷新，不计次。
- **来自章节页或另一科目的 `hello` 遇到未闭合的 `hidden`**：视为考试内正常跳转，丢弃，不计次。这一条必须有测试，否则交完听力进阅读会被误记一次离开。
- 心跳每 20 秒一次（仅页面可见时）。服务端发现间隔 > 60 秒且没有 `hidden` 记录，记一条 `heartbeat_gap` 软事件，**不计次**（断网很常见）。

**软信号（只记录，不计次）：**

- `window` 失焦（`blur`）：`enforce` 下盖一层“点击继续答题”遮罩，点击或重新获得焦点即消失。原生 `confirm` / `alert` 弹窗、系统权限弹窗也会触发失焦，所以绝不能计次，遮罩也必须能手动关掉。
- 视口变窄（`innerWidth` 明显小于 `screen.width`，阈值建议 70%）：判为分屏，`enforce` 下遮住题目并提示“请退出分屏”，恢复宽度后自动消失。**【需核对】** iPad 分屏、侧拉、台前调度下各事件的真实触发情况，以真机为准调整阈值；拿不准就只记录不遮罩。

**不做的事：** 第一期不强制全屏（iPad Safari 全屏下键盘输入受限，提交确认弹窗也会退出全屏）；不做多标签页互斥。

### 3.7 后果阶梯（用户已确认）

仅 `enforce` 模式、仅阅读和写作阶段：

1. 第 1 次离开：返回时显示警告条，“已记录 1 次离开，累计 3 次或 60 秒将锁定”。
2. 第 2 次：同上，更醒目。
3. 累计 3 次，或累计隐藏 ≥ 60 秒：锁定。不作废成绩。
4. 听力阶段只走 1、2 的警告，不锁定；次数和时长照常累计。

锁定时全屏遮罩盖住题目，文案必须包含：锁定原因、“答案已保存”、“计时仍在继续”、“请联系老师解锁”。遮罩下页面原有的计时器和到时自动交卷必须继续运行（不要用 `inert`、不要停定时器、不要拦截页面自己的跳转）。客户端每 5 秒轮询状态，老师解锁后自动恢复，无需刷新。

解锁后计数不清零；再离开 1 次或再累计 30 秒即再次锁定。老师可对单个学生设“本场豁免”。

### 3.8 设备绑定（仅 `enforce`）

- 客户端在 `localStorage` 生成随机设备 id，服务端只存 SHA-256。首次 `hello` 时绑定。
- 不同设备 id 访问同一 session：新设备显示“本场考试已在另一台设备开始，如需更换请联系老师”，记录 `device_conflict`。老师面板有“允许换设备”按钮（清空绑定）。
- 无痕模式或清缓存会导致同一台设备被判冲突，手册里要写明处理办法。

### 3.9 复制、粘贴、打印（`enforce` 生效，`monitor` 只记录不拦）

- 拦截 `copy` / `cut`（输入框和作文框内除外），计数上报。
- **不要全局拦 `contextmenu` 和文本选择**：`static/js/selection-highlight.js:594` 的高亮功能依赖它们，高亮是雅思机考的真实功能，必须保持可用。
- 写作框：拦 `paste`、`drop`，以及 `beforeinput` 中的 `insertFromPaste` / `insertFromDrop`。允许学生在作文内部剪切、粘贴自己写的内容：记住框内最近一次复制 / 剪切的文本，粘贴内容与之相同才放行。被拦截的粘贴上报长度，不上报内容。
- `@media print` 下隐藏正文。

### 3.10 水印与防息屏

- 题目区叠一层平铺水印（学生姓名加开考时间），`position: fixed; pointer-events: none`，低透明度。**必须验证**不影响高亮坐标（`tests/test_practice_highlight_coordinates`、`tests/test_selection_highlight_contract`）和题目点击；复盘页不加水印。
- 守卫启用时请求 `navigator.wakeLock.request('screen')`，页面重新可见时重新申请，失败静默。目的是防止 iPad 自动锁屏被误记为离开。**【需核对】** iPadOS Safari 对 Wake Lock 的支持版本。

### 3.11 开考前规则确认

章节页（`process.html`）在开启模式下多一张“考试规则与设备检查”卡片：列出规则（离开会被记录、累计 3 次或 60 秒锁定、禁止复制粘贴、计时不暂停），显示建议（开勿扰模式、自动锁定调到最长、关闭其他 App），给出设备指引页链接。学生点“我已阅读并承诺遵守”后上报 `ack`。未确认时，由守卫脚本在前端禁用各科 Start 按钮。

这张卡片的显示和按钮禁用全部由新脚本完成，`process.html` 原有脚本不改。

### 3.12 接口

学生端（token 鉴权，返回头沿用 `no_store`）：

- `GET  /api/exam/<exam_id>/session/<token>/integrity/state`
- `POST /api/exam/<exam_id>/session/<token>/integrity/event`，请求体 `{device_id, page_id, type, section, question, client_ts, client_hidden_ms}`，`type` 取值 `hello|ack|hidden|visible|heartbeat|blur|viewport|copy_blocked|paste_blocked`。兼容 `sendBeacon` 的 `application/json` 与 `text/plain`。请求体上限 2KB。返回当前状态。

老师端（前缀 `/admin/mock-exams/<exam_id>/integrity`，POST 的 CSRF 防护方式与 `api/mock_exam_review.py:34` 一致）：

- `GET  /` 监考面板页面；`GET /data` 面板轮询数据。
- `POST /policy` 设置模式和阈值。
- `POST /sessions/<session_id>/unlock`、`/reset-device`、`/exempt`。
- `POST /emergency-off` 把本场模式设为 `off`。

`mode` 变为 `off` 后，学生端在下一次心跳或轮询（≤ 20 秒）内撤掉所有遮罩并停止上报。

### 3.13 老师监考面板

- 顶部：本场模式切换（关闭 / 仅记录 / 警告并锁定）、阈值、红色“紧急关闭本场防作弊”按钮、指引页和手册链接。
- 学生列表，每 5 秒刷新：姓名、当前科目、状态（正常 / 离开中 / 已锁定 / 设备冲突 / 超过 60 秒无心跳）、离开次数、累计离开秒数、被拦复制和粘贴次数、最后活跃时间。锁定和设备冲突的行置顶高亮。
- 每行按钮：解锁、允许换设备、本场豁免、查看时间线（事件列表，含时间、科目、题号、时长）。
- 手机上要能用，老师巡场时用手机解锁。
- 成绩详情页显示该生的诚信摘要和风险等级（低：无离开；中：有离开未锁定；高：被锁定过、有设备冲突或粘贴被拦）。

### 3.14 守卫脚本的自我约束

- 整个脚本包在 `try/catch` 里，用 `defer` 加载，不读写页面已有的全局变量，不调用 `stopPropagation`，除 `copy` / `cut` / `paste` / `drop` / `beforeinput` 外的监听一律 `passive`。
- 状态接口连续失败时不显示任何遮罩，不锁定，静默重试。
- 所有遮罩挂在 `body` 末尾的独立节点上，不移动、不包裹页面已有 DOM。

## 4. 第二期：对付“拍照 + 另一台设备”（第一期验收通过后再做）

1. 守卫脚本记录每题首次作答和最后修改的相对时间（监听 `input` / `change`，题号从 DOM 属性读取，需先看两个练习模板的实际结构），随心跳聚合上报，存入 `exam_integrity_state` 的新 JSON 列或单独表。
2. 写作记录每 30 秒的聚合打字数据：按键次数、字符增量、单次最大插入长度、删除次数。不记录具体按键内容。
3. 老师端自动标记（只提示，不自动处罚）：
   - 阅读某篇从进入到全部答完的时间短于合理阅读时间；
   - 长时间无作答后短时间内连续答对多题；
   - 模考正确率明显高于该生近期刷题记录；
   - 作文出现大段文字而按键数很少，或全程匀速、几乎没有删改。
4. 被标记的场次，系统从答对的题里挑 3–5 道生成“讲题抽查单”，老师让学生当面讲思路，结果记在复盘里。
5. 在家考的建议流程（写进指引页，不需要开发）：学生用手机开腾讯会议，放在侧后方拍人和屏幕。

阈值先用保守值，全部做成可调，上线后根据真实数据校准。

## 5. 第三期：真锁屏方案（iPad 和 MacBook Air）

### 5.1 设备指引页（随第一期一起交付）

`/exam/guide` 静态页面，学生和老师都能打开，内容：

- **考前通用**：开勿扰或专注模式；自动锁定调到最长；关闭其他 App 和标签页；连电源。
- **iPad 引导式访问**（系统自带，老师或家长设密码）：设置 → 辅助功能 → 引导式访问 → 打开并设定密码；在考试页面连按三次顶部按钮（或主屏幕按钮）启动；选项里关闭词典查询。**【需核对】** 当前 iPadOS 的中文菜单名称。要写明局限：引导式访问锁的是 Safari 这个 App，学生仍能在 Safari 里开新标签页，所以必须同时开第一期的 `enforce` 模式，切标签页会被记为离开。
- **MacBook**：系统没有自带的单应用锁，只能用第一期的检测，或用 5.2 的 Safe Exam Browser。

### 5.2 Safe Exam Browser 接入（单独一个阶段，单独验收）

Safe Exam Browser（SEB）免费开源，有 macOS 和 iPad 版，相当于 Lockdown Browser。以下均为 **【需核对】**，实施前先读官方文档 `https://safeexambrowser.org/developer/`，以文档为准：

1. 用官方 SEB Config Tool 生成一份固定配置文件，不要手写文件格式。配置内容：起始地址指向一个通用考试入口页；网址白名单只放行本站域名；设置退出密码；iPad 上启用系统考试模式（单 App 锁定）。
2. 新增通用入口页（例如 `/exam/enter`）：学生输入模考编号后跳到现有的 `/exam/<id>` 登录页。现有登录页和链接保持可用。
3. 指引页和登录页提供两个按钮：“下载 Safe Exam Browser”（跳官方下载页 / App Store）、“用 Safe Exam Browser 打开考试”（配置文件链接）。
4. 策略表加一项 `require_seb`。开启后，非 SEB 环境打开试卷页显示拦截遮罩和上述两个按钮。先做弱校验（User-Agent 含 SEB 标识），再按官方文档做 Config Key 强校验。这是全计划中唯一允许拦住试卷的地方，规则是：**`require_seb` 开启且能确认不在 SEB 内时才拦截；判断不出来时放行并记录。**
5. Codex 本机有 Mac，可以装 macOS 版 SEB 自测；iPad 版必须由用户真机验收后才能对学生启用。

## 6. 测试与验收（“能跑通”的证据）

### 6.1 自动化测试（全部加入 `ci.yml`）

- `tests/test_exam_integrity_service.py`：离开计次的每条规则（2 秒宽限、同页返回、刷新 10 秒规则、跨科目跳转丢弃、心跳间隔不计次）、阈值锁定、听力不锁定、解锁后再锁规则、豁免、设备冲突、事件上限、`monitor` 模式不锁定。
- `tests/test_exam_integrity_routes.py`：按 `tests/test_mock_exam_runtime_routes.py` 的方式起内存库。覆盖学生接口、老师接口鉴权、紧急关闭。
- **故障放行测试**：不建 3 张新表，现有模考的草稿、开考、交卷、复盘路由测试全部照常通过；Jinja 全局函数返回 `None`。
- **锁定不拦交卷测试**：锁定状态下草稿保存、交卷、到时自动判分结果与未锁定完全一致。
- **默认关闭测试**：没有策略记录时，听力 / 阅读 / 写作 / 章节页渲染结果不含 `exam_guard` 字样。
- `tests/test_exam_guard.js`：守卫脚本的纯逻辑（状态机、粘贴放行判断、视口判断）。
- 现有模考相关测试全部通过，至少包括 `ci.yml` 中 `test_mock_exam_*`、`test_selection_highlight_contract`、`test_practice_highlight_coordinates`、`test_practice_shell.js`、`test_mock_exam_review_frames.js`。

### 6.2 本机浏览器全流程（Playwright 或手动，留截图）

每种模式各跑一遍“登录 → 听力 → 阅读 → 写作 → 成绩 → 复盘”：

1. `off`：与基线逐页对比，网络面板里没有任何 integrity 请求。
2. `monitor`：流程无任何提示和阻碍，面板能看到事件。
3. `enforce`：规则确认 → 阅读中切走 3 次 → 锁定 → 面板解锁 → 自动恢复 → 交卷成功。
4. `enforce`：锁定后不解锁，等到截止时间，确认自动交卷并出分。
5. `enforce`：写作粘贴外部文本被拦，内部剪切粘贴正常。
6. `enforce`：听力阶段切走 3 次不锁定。
7. 第二个浏览器打开同一 session，出现设备冲突；面板点“允许换设备”后可继续。
8. 考试进行中点“紧急关闭”，20 秒内遮罩全部消失，交卷正常。
9. 考试进行中删掉 3 张新表（仅本机库），页面继续可用，交卷正常。
10. 高亮、笔记、题目导航在 `enforce` 下全部可用。

### 6.3 用户真机验收（部署后、对学生启用前）

给用户一张清单，在 iPad Safari 和 MacBook Safari / Chrome 上各用一场“试考”跑一遍 6.2 的第 3、5、6、8 项，另加：iPad 自动锁屏、下拉通知中心、来通知横幅、分屏、侧拉时的表现。任何误锁都要先调整规则再启用 `enforce`。

## 7. 故障处理手册 `docs/EXAM_INTEGRITY_RUNBOOK.md`（必须交付）

面向老师，用大白话，按“现象 → 怎么办”写，监考面板顶部放链接。至少包括：

| 现象 | 处理 |
|---|---|
| 学生屏幕显示已锁定 | 监考面板找到该生点“解锁”，几秒后自动恢复，不用刷新 |
| 学生说没离开却被锁 | 先解锁；看时间线确认原因；必要时对该生点“本场豁免” |
| 提示已在另一台设备开始 | 确认是本人换设备后点“允许换设备” |
| 遮罩不消失或页面卡住 | 让学生刷新页面，答案已保存在服务器，计时不受影响 |
| 多名学生同时异常 | 点“紧急关闭本场防作弊”，考试继续，20 秒内全部恢复 |
| 面板打不开 | 不影响学生考试；考后联系技术人员 |
| 学生断网 | 与现在一样，答案本地暂存，恢复网络后自动保存 |
| 需要彻底停用 | 服务器设环境变量 `EXAM_INTEGRITY_DISABLED=1` 并重启服务（写清具体命令和谁来执行） |

学生端每个遮罩上都要有一句“遇到问题请举手联系老师，答案已保存”。

## 8. 上线步骤

1. **2026-11-15 的模考用现有线上版本，不部署任何东西。**
2. 第一期开发和 6.1、6.2 全部通过后，把证据交给用户，等用户明确授权再 push `main`。部署时间避开所有模考时段。
3. 部署后所有模考默认 `off`。先用一场内部模考走一遍完整流程，确认现有功能无变化。
4. 老师打开监考面板（此时自动建表），新建“试考”，按 6.3 真机验收。
5. 第一场真实模考用 `monitor`，考后看误报。
6. 确认无误报后改用 `enforce`。
7. 第二期、SEB 阶段各自重复 2–6。

回滚：每场可随时点“紧急关闭”；全局可设 `EXAM_INTEGRITY_DISABLED=1`；新表留着不影响任何现有功能，无需回滚数据库。

## 9. 交接要求

- 按 `CLAUDE.md` 更新 `docs/CODEX_HANDOFF.md` 和 `docs/WORKLOG.md`：写清分支、提交、测试命令和结果、是否已部署、生产库是否已建表、哪些项只做了本机验证、哪些等用户真机验收。
- 小程序不需要改动和重新发布：模考是网页，小程序只是用 web-view 打开。
- 遇到本文没覆盖、且可能影响现有模考的决定，停下来问用户。
