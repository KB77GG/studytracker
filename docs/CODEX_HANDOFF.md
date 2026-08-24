# StudyTracker — Codex 跨账号 / 跨电脑开发交接

> 这是账号无关、滚动更新的“当前状态”，不是聊天记录或永久变更日志。
> 最近更新：2026-08-24 23:00（Asia/Shanghai）。

## 2026-08-24 网页听力刷题提交后高亮保留（网页已上线）

- 为避开桌面旧主工作树的既有脏改动，本轮从最新 `origin/main@1c945a500a5f` 建立独立工作树
  `/Users/zhouxin/.codex/worktrees/listening-highlight-persistence/studytracker`，分支
  `codex/listening-highlight-persistence`；开始时与 `origin/main` 左右计数为 `0/0`、工作区干净。
  桌面 `/Users/zhouxin/Desktop/studytracker` 的旧 `main@6ded77d2` 及其交接文档、题库、脚本、原型等
  已有未提交/未跟踪内容均未触碰或覆盖。
- 根因是共享 `static/js/selection-highlight.js` 用“高亮根节点名 + 过滤后全文指纹”保存坐标；听力提交会在
  `listening-questions` 根节点内给 `.option-feedback` 注入选对/选错文字，MutationObserver 随后先拆除高亮，
  再用已经变化的指纹恢复，因而读不到旧指纹下的记录。阅读常用高亮位于不随判分改写的 Passage 根节点，
  所以表现为阅读保留、听力消失；两科高亮实际都只存浏览器 `localStorage`，没有提交后端。
- 修复只把 `.option-feedback` 加入高亮文本过滤器，使判分反馈不再参与指纹；该节点提交前为空，因此不会改变
  现有未提交状态的指纹，也不需要迁移已有浏览器高亮。新增
  `tests/test_selection_highlight_contract.py` 固化听力题目根、动态反馈写入和过滤器三者契约。
- 精确验证：
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_selection_highlight_contract.py tests/test_practice_workspace_regression.py tests/test_listening_test_index_workspace.py tests/test_reading_test_index_workspace.py tests/test_practice_catalog.py tests/test_practice_history.py`
  为 `25 passed, 101 warnings, 8 subtests passed`（warnings 均为既有 SQLAlchemy UTC 弃用提示）；
  `node --test tests/*.js` 为 `42 pass`；`node --check static/js/selection-highlight.js`、
  `node tests/test_practice_scoring.js`、`node tests/test_practice_table.js` 与 `git diff --check` 均通过。
  另用真实 Chromium 加载实际脚本，自动执行“题干高亮 → 注入 Correct answer → 等待 MutationObserver 重绘”，
  最终 DOM 为 `data-result=pass` 且 `.ex-hl` 仍存在；临时 HTML 已删除，Chrome 临时 profile 已移入废纸篓。
- 业务提交 `66c935f0d096a65025149f8b053b93729cb2dca5` 已原子推送
  `codex/listening-highlight-persistence` 与 `origin/main`。GitHub CI `32741622722` 整体 success，其中测试 job
  成功、仅 continue-on-error 的全仓 Ruff advisory 继续报告既有问题；部署 `32741622780` success。
- 生产 `/root/apps/studytracker` 为业务 HEAD `66c935f0`、tracked 工作区干净，`studytracker.service=active`；
  仍监听 `127.0.0.1:5002`，`workers=1 / worker_class=gthread / threads=6`，StudyTracker 主进程只有一个 worker。
  SQLite `quick_check=ok`、外键检查无输出，部署后 journal 应用错误计数为 0。公网 `/listening/tests` 与回环地址
  均返回 200；公网 `selection-highlight.js` 含 `.option-feedback` 排除规则，且 SHA-256 与本次发布文件一致：
  `1827c6c4138ee96bdea485fb9f7693117e6813bf0551dfcbddec26380ae6d639`。本地真实 Chromium 的提交后保留断言
  已通过；直接从 `file://` 加载公网脚本的额外验收因本机 Chrome SSL handshake/update 进程异常未产出断言，
  但公网 200、内容哈希及已通过的相同文件运行时测试共同覆盖了发布内容与行为。
- 本轮没有后端接口、数据库 schema/data 或小程序改动；未上传、提审或发布小程序。桌面旧主工作树的既有脏改动
  仍未触碰。后续若学生端仍显示旧行为，先完整刷新网页以淘汰既有标签页脚本，再复测“高亮题干 → 提交 → 复盘”。

## 2026-08-14 IELTS 写作范文与打字训练网页模块（后端/网页已上线）

- 正式发布工作树为 `/private/tmp/studytracker-ielts-writing-web`，分支
  `codex/ielts-writing-web`，由干净的 `origin/main@d500b396` 开始；业务提交
  `587ab585dfb6e6240308ce2af7770848b61b61b0` 已原子推送同名分支与 `origin/main`。桌面主工作树
  `/Users/zhouxin/Desktop/studytracker` 仍为 `main@6ded77d2`、落后远端 9 个提交；原有两份交接文档修改以及
  `.tmp/`、`artifacts/`、iDictation/ZYZ 导入数据与脚本、阅读/TOEFL 临时数据、设计/提案/原型等未跟踪内容
  均未覆盖或纳入本次提交。
- 用户在生产 `/listening/tests` 发现旧工作台顶部只有听力、阅读、学习报告，缺少反向进入写作的科目项。
  跟进提交 `fce9468e71a6deab9480eb9664666a7dad5536ea` 已在听力/阅读的真题与机经共 4 个目录模板补入唯一
  `/writing/` 链接，保留当前科目的 `aria-current` 与既有品牌色/移动端规则；没有新增视觉语言或改动练习页。
  对应回归覆盖 4 个公开目录，防止后续再次漏项。
- 用户随后要求三科切换更大更清楚，并确认该工作台不需要学习报告。提交
  `0e921208a87518e255f83be0a7db56a1a1567b66` 将共享科目导航提升为桌面 16px / 移动端 15px、全项 700 字重、
  64px / 48px 最小宽度与 3px 品牌绿激活线；链接仍占满 60px / 56px 顶栏高度，键盘焦点与 `aria-current`
  保持。听力/阅读真题与机经 4 个目录已同时删除登录态“学习报告”，写作页原本即只有三科，因此六个同款页面现统一为
  “听力 / 阅读 / 写作”。没有使用新字体、胶囊按钮或另一套颜色。
- 网页 `/practice` 的“剑雅真题”新增写作入口；新蓝图 `/writing/` 提供 40 道试点题目录（30 道 Task 2、
  10 道 Task 1），支持全文搜索和题型筛选。每题包含原题、小作文原图、6.0 / 6.5 / 7.0+ 三档完整教学范文、
  立场或总览、两组核心论点/特征、四段式与五段式结构、逐段功能和 3 条可复用表达。版本化内容位于
  `data/writing_library/pilot_40.json`，10 张原图位于 `static/writing_library/images/`；三档字数门禁保证
  Task 1 均不少于 150 词、Task 2 均不少于 250 词。题目与图片来自用户本机九分达人资料，范文和教学拆解为
  Sage Path 教研内容，并在页面明确不是官方评分样文。
- 页面复用现有听力/阅读的 `practice-workspace` 外壳、Sage Path `#2F8E87` 主色、暖白背景、左侧目录、
  圆角卡片、键盘焦点和移动端抽屉；没有引入另一套紫色或小程序视觉。打字工作台支持档位切换、浏览器草稿自动保存、
  目标/输入双栏、实时字数/WPM/前缀准确率/计时，以及完成时服务端按规范化全文 Levenshtein 距离重算最终准确率。
  学生练习通过服务端 `started_at` 计时并写入新增 `writing_typing_attempt` 表；完成接口校验学生归属、题号和档位且
  幂等。老师与课堂模式只做本页统计，返回 `client_only`，不会伪造学生记录。
- 访问模型沿用现有刷题身份：正式学生账号优先，其次为 `/practice` 已验证姓名；admin/teacher/assistant 与课堂模式
  可直接讲题但不落学生记录，未验证访客会回到 `/practice#ieltsPractice`。模块仅接网页，**未修改、上传、提审或发布
  小程序**；前一任务的小程序包仍是用户所述“已上传、审核中、尚未发布”。
- 验证均在发布工作树执行，Python 使用 `/Users/zhouxin/Desktop/studytracker/.venv/bin/python`：新增/入口专项
  `12 passed`；全仓 `520 passed, 44 subtests passed, 2 failed`，仅两个长期缺失且被忽略的
  `static/listening/ielts10_test1_s1.mp3` Range fixture 继续返回 404，与本次无关。目标 Ruff、Python
  `py_compile`、两个新增 JS 的 `node --check`、JSON 解析和 `git diff --check` 均通过。真实 Chrome 桌面目录、
  小作文原图详情、打字工作台及 CDP 390px 视口无横向溢出；课堂模式实际完成一次 39 词练习，实时准确率 100%、
  草稿和完成状态正常，历史仅显示在本页。QA 图仅本机位于
  `/Users/zhouxin/.codex/visualizations/2026/08/14/01a00084-1c7a-7801-b5e9-8c22c5dfe707/`，未纳入仓库。
- 首次上线 GitHub CI `31813362019` 与部署 `31813362004` 均 success。首次生产业务 HEAD 为
  `587ab585`，tracked 工作区干净；已有 15 个未跟踪数据库备份/本地资源（本轮部署前即存在）保持原样。服务于
  23:13:28 CST 重启后 active，监听 `127.0.0.1:5002`，`workers=1 / worker_class=gthread / threads=6`，
  主进程仅一个 worker 子进程，部署后 journal 的 traceback/exception/error/failed 计数为 0。
  新表存在且当前 0 行，SQLite `quick_check=ok`、外键检查无输出。公网 `/writing/` 为 HTTP 200、40 张题卡，
  `/practice` 含唯一写作入口，小作文原图为 `200 image/png / 176,951 bytes`；公网课堂模式 start API 返回
  `client_only=true`，复核表仍为 0 行，因此生产验收没有写学生练习数据。
- 导航跟进提交已原子推送 `codex/ielts-writing-web` 与 `main`；CI `31814058995`、部署 `31814059057` 整体
  success（lint job 仍仅为仓库既有 advisory 失败，目标测试成功）。随后并行发布的 `88480851` 线性包含本修复，
  2026-08-14 23:25 CST 生产 `/root/apps/studytracker` HEAD 为 `8848085`、tracked 工作区干净、服务 active；
  `gunicorn.conf.py` 仍为 `127.0.0.1:5002 / workers=1 / gthread / threads=6`，StudyTracker 主进程只有一个 worker
  子进程，部署后应用错误计数为 0。公网 `/listening/tests` 与 `/reading/tests` 均为 200，科目导航各含唯一
  `href="/writing/">写作</a>`；专项命令
  `/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest tests/test_practice_workspace_regression.py tests/test_writing_library_routes.py tests/test_writing_library_service.py -q`
  为 `11 passed, 8 subtests passed`，`git diff --check` 通过。本跟进没有数据库写入，也没有修改/上传/提审/发布小程序。
- 第二次导航优化已原子推送同名分支与 `main`；CI `31815149885`、部署 `31815149801` 整体 success，lint job
  仍只报仓库既有 advisory，测试 job 成功。2026-08-14 23:37 CST 生产 HEAD 为 `0e92120`、tracked 干净、
  `studytracker.service=active`，5002 / 1 worker / gthread / 6 threads、部署后应用错误 0。公网
  `/listening/tests` 含唯一写作链接且学习报告计数为 0；真实 Chrome 1170×770 与 390×844 页面均无横向溢出，
  三科标签、激活线和移动端 56px 点击高度正常。专项仍为 `11 passed, 8 subtests passed`，`git diff --check`
  通过；未写数据库、未修改/上传/提审/发布小程序。
- 下一位 agent 可直接从 `origin/main` 获取已上线模块。内容扩充应继续编辑版本化题库并跑字数/图片完整性测试；若要
  增加教师布置、批改或小程序入口，应作为独立需求设计，不要把逻辑继续堆入 `app.py`，也不要把当前教学档位误称为
  IELTS 官方评分。上线后的首个真实学生完成记录应只读抽查题号、档位、server duration、WPM 与 accuracy 是否合理，
  不要修改学生原文。
## 2026-08-14 精听正式训练方式（后端/网页已上线，小程序待用户上传）

- 正式工作树为 `/Users/zhouxin/.codex/worktrees/2b72/studytracker`，分支
  `codex/listening-dictation-release`。业务提交
  `8848085145ffe256ad0533c558721127174a5843` 已线性整合写作模块和写作导航修复，并原子推送同名发布分支与
  `origin/main`。既有未跟踪 `.tmp/product-audit-listening-modes-20260814/` 审计截图原样保留，未纳入提交；
  桌面主工作树的既有脏改动与未跟踪资料均未覆盖。
- 助教网页与小程序布置端现可为精听任务选择并保存
  `system / review / basic / standard / challenge`（系统推荐 / 听辨核对 / 关键词 / 标准 / 整句）。
  新任务正式首答由任务字段 `Task.listening_training_mode` 锁定；首答保存后开放句子复盘、跟读和不低于原档位的
  升档练习，订正仍只在本地核对，不覆盖不可变首答。学生已开始的任务不可修改训练方式；历史 NULL 任务继续保持
  学生自选，助教编辑历史任务时不会被误升级为系统推荐。
- 共享策略位于 `services/listening_training.py`：系统推荐通常给标准档，超过 15 秒或 20 个内容词的长句降为关键词；
  整句档遇长句降为标准。任务 API 给每句下发 `assigned_training_level` 与 `challenge_allowed`，提交接口校验新客户端
  上报的正式档位并把实际首答档位写入 `ListeningSegmentResult.training_level`。旧已安装小程序不上传档位时继续接受
  原有三档合法形态，避免灰度期间任务不可用；新客户端显式上报错误档位则返回 409。
- “听辨核对”是完成制：学生必须完整播放本句、再揭示原文，才可调用幂等 completion API；网页在未完成前禁用向前
  跳播，小程序没有句内跳播入口。该模式不写 0% 到任务汇总，教师明细显示“已核对/完成制”，不把它混入词级正确率。
  新 review API 对双设备并发重复提交使用唯一键和冲突回读，避免返回 500。
- 两端兼容门禁：小程序助教选择器只有在目录 API 返回 `capabilities.listening_training_modes=true` 时出现；旧任务和
  旧已安装小程序继续按原逻辑工作。网页由同一后端模板与契约一起上线。现有“已上传待审核”的小程序包来自本轮之前，
  **不包含本节训练方式改造**；本功能仍需要本次的新包另行上传、审核和发布。
- 本轮业务/测试改动包括：`models.py`、`app.py`、`api/{__init__,miniprogram,listening_training}.py`、
  `services/{listening_training,task_assignment_history}.py`、网页布置/播放器/教师明细模板、小程序助教和学生精听页三件套，
  以及 4 个精听/助教测试文件。启动时的 legacy schema safeguard 已在生产安全补齐两个 nullable 列
  `task.listening_training_mode` 与 `listening_segment_result.training_level`；未改已有任务、答案或进度数据。
- 整合最新 `origin/main` 后验证（Python 使用 `/Users/zhouxin/Desktop/studytracker/.venv/bin/python`）：精听专项
  `19 passed, 3 subtests passed`；全仓排除长期缺失且被 gitignore 的
  `tests/test_static_audio_headers.py` 静态 MP3 fixture 后为 `531 passed, 48 subtests passed`；全部
  `tests/*.js` 为 `42 pass`。Jinja、网页内联 JS、两个小程序 JS、Python compile、新增文件 Ruff/Black、微信官方编译器
  目标 WXML/WXSS 与 `git diff --check` 均通过。
- CI `31814253746` 与部署 `31814253358` 均 success。生产 `/root/apps/studytracker` 业务 HEAD 为 `88480851`，
  tracked 工作区干净；`studytracker.service` 于 23:24:15 CST 重启后 active，监听 `127.0.0.1:5002`，配置为
  `workers=1 / worker_class=gthread / threads=6`，主进程只有一个 worker 子进程，部署后 journal 的
  traceback/exception/error/failed 计数为 0。数据库 `quick_check=ok`、外键检查无输出；公网精听页为 200，
  受保护的小程序目录 API 返回预期未登录 401。
- 微信开发者工具 Stable 2.01.2510290 已打开正确目录
  `/Users/zhouxin/.codex/worktrees/2b72/studytracker/miniprogram` 并重新普通编译；界面显示 `Errors: 0`、
  `Problems: 0`（调试器仍列 3 条既有 warning）。本轮没有代替用户点击上传，也未提审或发布；下一步由用户直接在当前
  工具窗口上传新包，之后真机覆盖五种布置方式、首答锁定、首答后复盘升档、听辨完成制与历史任务兼容。

## 2026-08-14 电话/邮编逐字符发音修正与小程序整合（后端已上线，小程序已上传待审核）

- 正式发布工作树为 `/Users/zhouxin/.codex/worktrees/2b72/studytracker`，分支
  `codex/listening-dictation-release`。先从干净的精听发布 HEAD `d5d2e70f` 线性快进合入数字发音
  `1222b2f0` / `5f2ba4b4`，再形成业务提交
  `6635b32011aee0b5216233cc026c44f90da53469`；该提交已原子推送发布分支与 `origin/main`，因此本目录
  同时包含精听智能听写升级、数字音频失败保护、电话/邮编逐字符发音和音频 URL 修复。桌面主工作树
  `/Users/zhouxin/Desktop/studytracker` 仍为 `main@6ded77d2`、落后远端 5 个提交，原有两份交接文档修改及
  `.tmp/`、`artifacts/`、iDictation/ZYZ 导入数据与脚本、阅读/TOEFL 临时数据、设计/提案/原型均未覆盖。
  本轮核对时正式发布工作树另有未跟踪目录 `.tmp/product-audit-listening-modes-20260814/`，内含 2 张产品审计截图、
  共约 184 KiB，来源不属于本次状态更正，已原样保留且未纳入提交。
- 语义审计确认第一阶段生成的数字音频会把长号码按基数/分组数朗读，不符合电话号码、邮编和编号的听写目的。
  现以受版本控制的
  `data/dictation_tts_overrides/ielts_sun_number_dictation_phone_postcode.json` 固定 19 个精确序号：
  `22,24,27,31,36,40,43,51,73,89,90,103,113,114,116,118,122,123,124`。规则为每个数字/字母
  单独读，`0` 读 `oh`，重复数字不合并成 double/triple；例如 `94635550` 为
  `nine, four, six, three, five, five, five, oh`。日期、年份、价格、数量及 `17A`/`201 A` 等地址门牌
  没有纳入，不改变其自然读法。映射同时钉死 book ID `196`、完整书名、序号和原词，任一不符都会在生成前失败。
- `scripts/backfill_dictation_book_tts.py` 新增 `--spoken-text-map`：映射模式不受全局重复次数影响，只读一遍；
  仍保持默认 dry-run、MP3 校验、原子落盘、全量成功后单事务绑定，并拒绝把映射用于错误书本、部分范围或错位词条。
  生产 dry-run 先确认 19/19 精确匹配；写库前用 SQLite 在线备份
  `/root/apps/studytracker/app.db.bak-20260814-book196-digitwise-before`，大小 `85,270,528` bytes，SHA-256
  `180425bff5411515e126b0d857bc9ea4c0c818e98d77de7ca6ec8c039fee26d4`，`quick_check=ok`。
  随后 DashScope 新生成 19 份逐字符 MP3 并在一个事务内替换对应 `audio_us`；旧缓存文件未删除，上一阶段备份也保留，
  没有修改学生答案、进度或任务状态。
- 生产写入后 19/19 文件均大于 1 KiB，回环与公网 word-id 请求全部为 `200 audio/mpeg`，样例 Range 为
  `206 / 1024 bytes`；数据库 `quick_check=ok`、外键错误 0。成品拉回本机后用缓存的 Whisper small/base
  逐条核验，并对容易混淆的 6 条再用阿里云 ASR 交叉检查；号码已不再被读成千/百万位基数，孤立 B/D、R/are 等
  字母在 ASR 文本中仍会出现识别混淆，故最终事实源是受测的逐字符 spoken-text 映射与实际 TTS 输入。
  本机忽略证据位于 `output/transcribe/phone-postcode-digitwise-20260814/`；生产机没有运行 Whisper/Kokoro。
- 验收又发现第一阶段回填的数据库值为服务端文件路径 `uploads/tts_cache/...`，旧小程序以
  `https://studytracker.xin/api` 为 base 时会误拼为不存在的 `/api/uploads/...`。业务提交 `6635b320` 增加共享
  `services/dictation_audio.py`：书本接口和 legacy 任务队列现在把绑定音频统一序列化为带文件指纹的
  `/dictation/words/{id}/tts?v=...`；151/151 个词均已在生产核对为该契约，样例公网 Range 206。
  版本指纹也避免换音频后命中旧缓存。新小程序的 `resolveAudioUrl` 同时正确处理根目录
  `uploads/` / `static/` 资产。已打开旧页面仍持有旧队列和内存缓存，因此学生需要完全退出练习/小程序并重新进入一次；
  后端兼容已上线，不需要等新版小程序发布才能恢复。
- 自动化与编译：专项 Python `43 passed`；项目级
  `PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q --ignore=tests/test_static_audio_headers.py`
  为 `512 passed, 44 subtests passed`；全部 Node 为 `40 pass`。目标 Ruff、Black（新增/独立文件）、Python
  `py_compile`、JS `node --check`、JSON 解析与 `git diff --check` 通过。微信开发者工具 Stable 2.01.2510290
  地址栏再次确认项目为本 worktree 的 `miniprogram`，普通编译为 `Errors: 0`、`Problems: 0`；调试器唯一 warning
  是工具自身 SharedArrayBuffer 弃用提示。安装包内官方 `wcc` / `wcsc -lc` 全量为 `32/32 WXML`、
  `33/33 WXSS`，另有 `49/49 JS` 语法及 `36/36 JSON` 解析通过。
- CI `31806798880` 与部署 `31806798923` 均 success。生产 `/root/apps/studytracker` HEAD 为 `6635b320`，
  tracked 工作区干净；`studytracker.service` 于 21:53:42 CST 重启后 active，监听 `127.0.0.1:5002`，
  `workers=1 / worker_class=gthread / threads=6`，主进程只有 1 个 worker 子进程，重启后应用错误计数 0。
  远端三个 `/tmp` 验证脚本/映射副本已删除，正式音频和两份可恢复数据库备份保留。
- 用户于 2026-08-14 22:20 CST 更正外部状态：完整功能小程序只是刚上传并等待审核，**尚未发布**；此前“已发布”的
  记录无效。上传包来自正确目录 `/Users/zhouxin/.codex/worktrees/2b72/studytracker/miniprogram`，包含精听升级及
  电话/邮编逐字符发音相关客户端修复。平台版本号、上传时间和审核进度尚未独立读取；审核通过后仍需确认已经执行发布。
  后端兼容及逐字符音频已经上线，当前线上旧包的学生可完全退出练习/小程序再进入后先测数字音频；只有随新包提供的客户端
  改动需要等审核通过并发布后再做完整真机联合回归。

## 2026-08-14 数字听写发音恢复（第一阶段；已由上节逐字符修正接续）

- 发布工作树为 `/private/tmp/studytracker-number-audio-hotfix`，分支
  `codex/dictation-number-audio-hotfix`，基线 `d5d2e70f5722446538a004d33d172768050c02ab`；业务提交
  `1222b2f0c3ed0eb5e8453aeaba35453d35e733bf` 已 commit，已推送同名分支并快进到 `origin/main`。
  主工作区 `/Users/zhouxin/Desktop/studytracker` 仍为 `main@6ded77d2`，其既有两份交接文档改动及
  `.tmp/`、`artifacts/`、词书导入数据/脚本/测试、阅读/TOEFL 临时数据、设计/提案/原型等未跟踪内容
  均未覆盖或纳入业务提交；同一 macOS 用户仍可见，另一台电脑只能取得已推送的 `1222b2f0`。
- 故障确认为真实服务端音频故障而非小程序未重新进入：数字练习没有随导入绑定音频，部分合法数字表达被
  纯词形校验拒绝为 400，另一些表达在 Youdao 失败后为 502；小程序再把明确 HTTP 失败交给
  `InnerAudioContext`，Android 媒体栈会放大为重复请求并停在「正在加载」。来源站导出不含逐题源录音，
  当前站点实现本身也是有道发音 URL 与签名重试，故未搬运或热链第三方音频。
- 按用户授权改用项目已配置的阿里云 DashScope TTS。写生产库前创建 SQLite 在线备份
  `/root/apps/studytracker/app.db.bak-20260814-book196-dashscope-before`，大小 `84,992,000` bytes，
  SHA-256 `d83a7eddf9dc3dfb0bed61b35015292b5733ddd338b3dcd0b2384e212e62a98c`。数字练习词书 151 条均已
  生成/复用本地 MP3 缓存并绑定 `audio_us`：150 条新生成，大小写重复的同文本 1 条复用；先生成并验证
  全部目标文件，再以单事务绑定数据库。未修改学生答案、学习进度或任务状态。
- 新增 `scripts/backfill_dictation_book_tts.py`：默认 dry-run，支持限定书本/序号/提供商/音频字段，MP3
  校验、原子文件写入、有限重试和全量成功后单事务绑定；失败时不提交数据库。后端 word-id TTS 对含数字的
  数据库合法表达保留原文并优先使用 DashScope，默认生成链改为 `youdao,dashscope`，缓存读取链包含
  DashScope 且会复用已生成缓存。小程序 `dictation-audio.js` 对明确 4xx/5xx 立即退出 loading、只报告一次，
  不再把同一错误 URL 交给播放器内部重试。
- 精确验证：专项 Python `18 passed`；全仓首次为 `509 passed, 44 subtests passed, 2 failed`，两个失败仅是
  长期缺失且被忽略的 `/static/listening/ielts10_test1_s1.mp3` fixture；明确忽略该文件后为
  `508 passed, 44 subtests passed`。CI 同款依赖轻量门禁 `68 tests OK`；16 个 `tests/test_*.js` 文件全部
  通过，目标高信号 Ruff、JS `node --check`、Python `py_compile` 与 `git diff --check` 通过。
- 生产数据写入后及代码部署后均逐条请求 151 个 word-id 音频接口：全部为 `200 audio/mpeg`、长度大于
  1 KiB，无缺绑定、缺文件或失败接口；当前练习的 Range 请求为 `206`。SQLite `quick_check=ok`、外键错误 0。
  GitHub CI `31797920336` 与部署 `31797920393` 均 success；生产 HEAD 为 `1222b2f0`，服务于
  2026-08-14 19:52:24 CST 重启后 active，`127.0.0.1:5002`、`workers=1`、gthread、`threads=6`、
  单 worker 子进程。部署后 journal 的 traceback/exception/error/failed 均为 0；公网当前音频 Range
  返回 `206 audio/mpeg`。远端 `/tmp/backfill_dictation_book_tts.py` 已删除，正式缓存和上述可恢复备份保留。
- 后端代码与生产数据已经上线，学生可立即重新进入练习；小程序的“HTTP 失败不重复请求”保护代码已 commit/push，
  但尚未上传、提审或发布，需下一次小程序人工发版才生效。现有线上小程序因服务器已稳定返回音频，不依赖该发版
  才能继续当前练习。若后续发现某个邮编/号码需要特定的逐位读法，应记录词书序号后按指定 spoken text 定点重生，
  不要重新依赖来源站内部签名。

## 2026-08-14 精听智能听写稳定升级（后端/网页已上线，小程序待用户发布）

- 本轮工作树为 `/Users/zhouxin/.codex/worktrees/2b72/studytracker`，发布分支为
  `codex/listening-dictation-release`，基线为 `6ded77d24586327ad94e151e172ae4811b4a2eed`。业务提交
  `18484d1ee1f6f861e1f370dd5ab89c9222a43d91` 已 commit、推送发布分支并快进到 `origin/main`，后端/网页
  已部署；没有生产数据库写入、小程序上传/提审/发布，也没有改动 16 份剑20 JSON 或 MP3。业务改动包含
  `app.py`、新服务 `services/listening_cloze.py`、`templates/listening/player.html`、小程序精听页三件套、
  网页/小程序两份 `listening-cloze.js` 纯函数模块，以及契约 fixture 和 5 个精听测试文件；本节与
  `WORKLOG.md`。主工作区既有用户/其他任务脏改动未触碰；仅在其已存在的 `.tmp/` 下写入
  本轮浏览器与微信模拟器审阅截图。
- 网页与小程序共用同一份契约 fixture：新选择器保留原始 `segment.text` 的 whitespace
  坐标，把 `MAN:`/`WOMAN:` 等说话人标签标为不可答而不重编号。新网页写入原始
  `segment_text`、数值 `hidden_word_indices` 和平铺逐词 `answers`；旧网页的 stripped
  文本坐标、旧小程序的完整文本坐标均按保存文本原样恢复，绝不重算。任务进度 API 现返回
  已保存的 `segment_text`，使客户端能够区分这两种历史基准。
- 三档实现为“基础·关键词 / 标准·辨音 / 挑战·整句”：基础和标准使用确定性候选排序、
  数量边界与相邻降级；挑战只显示不泄露长度的整句输入，但仍保存逐词数组和数值下标。选择器默认
  排除说话人、纯标点、问候/填充、未明确拼写的人名；数字/时间/地址/明确拼写优先。`right`、`fine`、
  `sure` 只在回应语境排除，支持连字符和分开的逐字母拼写序列；名称白名单可配置。
- 网页“句子精听”恢复为先听、可显示原文核对；听写首次进入显示“先听，再填 / 开始作答”，
  不锁播放。两端使用固定宽度单词槽、可读 `aria-label`、挑战 textarea 和立即逐词反馈；订正
  只在本地评分，不会第二次 POST 或覆盖首答。保存进度、已开始作答和保存失败的首答均冻结本句难度；
  历史记录仅在下标恰好覆盖全部 spoken token 时才渲染为挑战，旧 60%/50% 记录保留逐词 UI。
  网页自由练习只有在 `localStorage` 真正写入后才显示侧栏勾选；任务模式只有服务端确认后才标记完成。
  小程序现在跨模式/切句保存未提交草稿，汇总值始终由可见 `progressMap` 重算，避免陈旧 Task 汇总与页面不一致。
  两端挑战模式保留并惩罚多输单词（显示“多余”），不再截断后仍给 100%；分数统一保留到一位小数。
  较长正确答案在反馈态按答案有限扩展，`restaurants` 不再被固定宽度截断。
- 音频链路也完成稳定修正：网页时间条、±5 秒和进度点击都限制在当前句范围；播放按钮由真实
  `play/pause` 事件驱动，`play()` 拒绝会显示错误；`requestAnimationFrame + timeupdate` 双保险在精确句尾停播。
  小程序不再用固定 120ms 猜测 seek 完成，而是等待 `onSeeked`，另有 400ms 兼容兜底；播放 token 能取消
  切句/暂停后的待播任务，50ms 边界监视与 `onTimeUpdate` 双保险避免越界。加载/失败状态现在可见。
- 服务端新增 canonical 首答判分：从任务对应 JSON 找到原句，兼容旧网页 stripped 坐标和完整说话人坐标，
  验证文本、下标、说话人标签和答案形态，并完全忽略客户端上报的 `correct_words/total_words` 后重算。
  首答记录改为幂等不可覆盖；网络丢响应后的重复 POST 返回第一次已保存结果，不增加 attempt 或篡改成绩。
  服务端现在同时返回 canonical 逐词结果，网页和小程序均以它覆盖客户端临时判色；模拟器用故意冲突的
  “本地 2/3、服务端 1/3”响应复验后，总分 `33.3% / 1 of 3` 与逐词 1 绿 2 红完全一致，不再出现总分和颜色矛盾。
- 验证（均在此 worktree，Python 使用
  `/Users/zhouxin/Desktop/studytracker/.venv/bin/python`）：`node --test tests/*.js` 为 `40 pass`；新增覆盖
  标准/挑战草稿恢复、挑战多余词、66.7% 小数、陈旧汇总、完整 `canplay→seeked→单次 play` 事件链、
  取消待播、句尾停播和全剑20契约。
  `tests/test_listening_cloze_exercise_contract.js` 扫描 16/16 个正式 Section、594 句，验证时间单调、
  三档确定性、说话人不可答，以及基础/标准不挖问候词或未拼写人名。进度 API 定向为
  `4 passed, 3 subtests passed`，覆盖服务端拒绝伪造文本/说话人下标、客户端伪造 100% 被重算、canonical
  逐词结果及首答幂等。
  `node --check`、Python `py_compile`、`git diff --check` 均通过。
- 全仓 `pytest -q` 结果为 `504 passed, 44 subtests passed, 2 failed`。两个失败仍为
  `tests/test_static_audio_headers.py`：它固定请求
  `/static/listening/ielts10_test1_s1.mp3`，但该 MP3 在本 worktree 不存在且被
  `.gitignore` 的 `static/listening/*.mp3` 忽略，故返回 404；本轮未伪造该旧 fixture。正式剑20 T1S1 资产则
  实测普通请求 `200 / 4,510,470 bytes / Accept-Ranges: bytes`，Range 请求
  `206 / Content-Range: bytes 0-1023/4510470`。
- 当前轮浏览器 QA 真实挂载剑20 T1S1 音频，不再只是静态界面：音频 `readyState=4` 后正常播放，第一句在
  `4.526825s` 自动暂停；句2时间条显示本句 `00:00–00:08`，不再显示全轨 `04:39`，连续两次前进5秒被
  正确限制为 `9.52s / 13.21s`。标准档切换模式后草稿仍在，真实 4/4 提交显示 `100%` 且侧栏只在保存后勾选；
  挑战整句多输 `EXTRA` 显示“多余”并得 `95.5%`；刷新后整体 `3/45、86.2%` 与逐句首答一致，已保存结果
  可恢复且不会因查看自动播放。长答案 `restaurants` 截图确认完整显示。16 个正式 XDF MP3 也逐一用
  `ffprobe` 核对：每份 JSON 最后 `end` 与对应音频时长差均为 `0.00s`。
- 微信开发者工具 `/Applications/wechatwebdevtools.app` 已登录，官方 CLI 打开的是本 worktree 的
  `miniprogram`。第一次真实编译暴露出 `app.json` 所列 5 个页面缺少同名 page JSON，SummerCompiler 因此报
  `path must be string`；已为 `pages/index`、`pages/student/{home,task,stats}`、`pages/parent/report` 补齐
  `{ "usingComponents": {} }`，并新增门禁保证 app.json 每个页面均有 JS/JSON/WXML/WXSS 四件套。
  清洁重编译后调试器 `Errors: 0, Warnings: 0`；安装包内官方 `wcc` / `wcsc -lc` 全量复验仍为
  `32/32 WXML`、`33/33 WXSS` 通过。
- 微信模拟器（基础库 3.17.1）用内存隔离任务跑完运行时验收，没有生产任务 POST 或数据库写入：默认先听页正常，
  点击开始后 3 个真实 input 可见，草稿 `table/six/evening` 在“句子精听 ↔ 听写模式”往返后不丢；提交只发
  1 次，服务端权威总分、汇总和逐词颜色一致。真实公网剑20 T1S1 音频 `audioReady=true`，第二句从非零时间戳
  播放 1.6 秒后显示 `00:01/00:08`；切回第一句立即取消旧播放且保持停止；第一句再次播放后在
  `00:04/00:04` 自动停止，运行期 exception/console error 均为 0。验收注入已通过再次普通编译彻底清除，
  自动化连接和 27MB 临时 npm 目录已删除，开发者工具保留在干净的 `pages/index/index`。
  浏览器与模拟器证据仅本机位于
  `/Users/zhouxin/Desktop/studytracker/.tmp/listening-release-qa-20260814/`，不是待发布产品资产。
  验收用 `5062` 开发服务器与浏览器页均已关闭；指向主工作区真实 T1S1 MP3 的临时只读 symlink 已精确删除，
  未复制、改写或删除主工作区音频。仍未做手机真机调试、微信上传/提审/发布；用户明确表示将自行上传发布。
- 发布分支 CI `31766305566`、主分支 CI `31766349645`、部署 `31766349635` 均为 success；CI 的 Ruff
  失败仅是仓库既有 advisory lint job，工作流整体成功且本次未修改所报旧文件。生产目录 HEAD 为
  `18484d1e`，`studytracker.service=active`（2026-08-14 11:18:00 CST 重启）；Gunicorn 监听
  `127.0.0.1:5002`，配置为 `workers=1 / worker_class=gthread / threads=6`，主进程仅 1 个 worker 子进程。
  生产数据库 `PRAGMA quick_check=ok`、外键错误 0，重启后 journal 的 traceback/exception/error/failed 计数为 0。
  公网 `/listening/ielts20_test1_s1` 与 `/static/js/listening-cloze.js` 均为 200，新脚本 SHA-256
  `a99d3ec8984d428612729808d77afc255c212d97e509fafe00321a7fed37b721` 与本地一致；页面含新流程代码，
  正式 T1S1 音频 Range 为 206。后端/网页已上线；微信小程序包仍待用户从本 worktree 手动上传、提审、发布。

## 2026-08-13 剑20 Test 1 Section 1 覆盖为45句纯对话版（已上线）

- 当前工作树为 `/Users/zhouxin/Desktop/studytracker`、分支 `main`。业务提交
  `9aadc1525b3d58452f30bbe42262d830cc75d73c` 已 commit/push 到 `origin/main` 并部署。
  后续复现性修正 `8b1c69dc568be66355dd36d4726671c7568a0e05` 也已 commit/push/deploy：正式资源
  覆盖后，生成器默认使用日期化原轨备份，并优先读取每句保存的 `original_start/end`；实测可重新生成
  完全相同 SHA-256 的279.840秒MP3。
  提交包含生成器 `scripts/build_xdf_intensive_pilot.py`、正式覆盖的
  `static/listening/ielts20_test1_s1.json`、门禁测试
  `tests/test_xdf_intensive_replacement.py`，以及
  `miniprogram/pages/student/listening/practice/index.js` 的句尾停止修正。
  本轮结束前另有来源不属于本任务的未跟踪 `data/idictation_zyz_vocab/`、
  `scripts/import_zyz_vocab.py`、`tests/test_import_zyz_vocab.py` 出现，与原有 `.tmp/`、`artifacts/`、
  阅读/TOEFL临时数据、设计/提案和 `prototypes/` 一样均未触碰、未提交。
- 生成脚本通过新东方公开接口 qId `1817` 取45句结构，规范化后与本地原58句的742个词逐词完全一致；
  再把新东方的两段剪辑时间轴映射回本地原音频。试点纯对话音频由本地原 MP3 的
  `40.990–205.280s` 与 `251.990–367.540s` 两段拼接生成，删去中间 `46.710s` 看题/说明块；
  成品 `static/listening/ielts20_test1_s1.mp3` 为 `279.840s`、`4,510,888` bytes、
  SHA-256 `ec0bc0dc1ab21bd1d18e6397a9c4b7978a292a66da8273c2637798dfa1c9dfa4`。
  该 MP3 命中仓库 `static/listening/*.mp3` ignore 规则，已在 JSON 部署前单独 rsync 并原子替换生产同名文件。
  本机旧原轨备份为 `static/listening/ielts20_test1_s1_pre_45sentence_20260813.mp3`；生产旧 JSON/MP3
  也分别备份为 `static/listening/ielts20_test1_s1_pre_45sentence_20260813.{json,mp3}`，可恢复。
- 覆盖前只读查询生产库：`listening_exercise_id='ielts20_test1_s1'` 的任务数为0，关联
  `listening_segment_result` 也为0，因此本次用原 canonical ID/文件名直接覆盖，没有旧任务进度错位。
  线上教师目录与原链接无需改变，之后新布置任务自动使用45句。
- 小程序逐句停止条件从 `segment.end - 0.05s` 改为精确 `segment.end`，去掉会主动削短尾音的50ms；
  网页原本已按精确 `end` 停止。本轮没有改后端代码或数据库记录，但已按用户授权替换生产JSON/MP3资源。
- 对试点 MP3 跑 Whisper base 全轨逐词校验：期望742词、ASR 744词，LCS 匹配732词（98.652%）；
  44个内部句界中41个可由相邻匹配词可靠核验，没有句界早于当前句最后一个词结束，最小尾部余量约
  `0.200s`。拼接点前后完整识别 `Not sure ... quite limited` 与
  `I've just thought of another idea ...`，没有把对话剪断。`scripts/audit_listening_alignment.py`
  单文件审计为 `checked=1 / issue_count=0`。
- 用户已在同一播放器中实际对比原58句版与45句纯对话试点，并明确反馈“45句的版本确实更好”。
  产品方向因此确定为：纯对话音轨、减少脆弱短句切点、播放器不提前50ms停止；后续扩展应沿用这三个原则，
  而不是只在旧时间戳上无条件增加尾部余量。
- 精确验证：`.venv/bin/ruff check scripts/build_xdf_intensive_pilot.py tests/test_xdf_intensive_replacement.py`、
  `.venv/bin/black --check ...`、Python `py_compile`、
  `node --check miniprogram/pages/student/listening/practice/index.js` 均通过；覆盖发布前新增/目录定向测试为
  `6 passed`，复现性修正后定向为 `7 passed`；全部 `tests/test_*.js` 通过；`.venv/bin/python -m pytest -q` 为
  `496 passed, 7 subtests passed`（仅存量弃用警告）。结束前仍需保持 `git diff --check` 通过。
- GitHub 首次覆盖的 CI `31711801740` / 部署 `31711801774`，以及复现性修正的 CI
  `31712275524` / 部署 `31712275451` 均 success。生产 HEAD 为 `8b1c69dc`，
  `studytracker.service=active`；Gunicorn 监听 `127.0.0.1:5002`、gthread、单 worker 子进程。
  生产页面/API为200且API返回45句（0.00–279.84秒），MP3 Range为206、大小4,510,888 bytes、
  SHA-256与本机一致；公网同样页面/API 200、音频206，`cache-control: no-cache`，不存在长期旧音频缓存头。
- 网页与后端资源已上线。小程序代码中的精确 `end` 停播修正虽已 commit/push并进入生产仓库，
  但微信小程序包尚未由用户上传、提审、发布；当前已发布旧包仍提前50ms停止，不过会立即使用新的45句JSON和
  纯对话MP3。下一步在实际使用中记录具体“第几句”问题，定点修正；扩展其他Section前仍先只读检查是否有旧任务。
  复现性修正后生产仍为45句/279.84秒，`workers=1 / worker_class=gthread / threads=6`，部署后日志未发现
  traceback/exception/error/failed。

## 2026-08-13 剑雅精听时间戳来源与越句现象核验（只读诊断）

- 当前工作树为 `/Users/zhouxin/Desktop/studytracker`，分支 `main`，诊断基线/`origin/main`
  均为 `a3a5fedf843797478842a78a05f9801720f47e3a`，左右差异为 `0/0`。本轮开始时没有 tracked 业务改动；
  已有 `.tmp/`、`artifacts/`、`data/reading_study/{browse,preview}.html`、
  `data/toefl_practice/ets-practice-{2,3,4,5}/`、`docs/design/`、两份 dictation 提案和 `prototypes/`
  均为本轮前存在的未跟踪内容，未修改。
- 已确认当前剑雅精听导入器 `scripts/import_idictation_xyy_listening.py` 不重新对齐句子：
  它直接读取 iDictation part 响应 `content[]` 的 `start_time/end_time/en_text/cn_text`，
  时间只做毫秒→秒与两位小数四舍五入，同时保留 `source_start_time/source_end_time`；
  播放音频 URL 也直接来自同一 part 响应的 `file_url`。
- 对本地保留的 iDictation 原始 API 响应
  `data/idictation_xyy_listening/raw.json`、导入报告与 `static/listening/ielts*.json`
  做了全量只读逐句对账：288 个 Cambridge Section、13,104 句全部存在，句数差异 0、
  文本差异 0、源音频 URL 差异 0。12,949 句时间与原始 API 值一致，导入四舍五入的
  最大改变仅 0.005 秒；余下 155 句全部是剑21 四套 Section 1，已在提交
  `78a7721a34b4083685316b79487996d16b541c1a` 因原站整段偏移而使用官方 MP3 轨重对齐修正。
- 原始 API 数据的 12,816 个相邻句边界中，307 个出现 `next.start < previous.end`
  的时间重叠，4,027 个间隔不超过 50ms；还存在少数明显的时间轴回跳。
  因此“句尾几个词落到下一句”可以来自原站逐句边界本身，不是导入换算制造的数秒级误差。
  原站当前公开 `/main/book` 页面可 200 加载，但精确到某个登录后练习的 UI 播放表现
  本轮没有冒充已对比；原站如果整段连续播放，同一数据缺陷可能不如逐句硬停明显。
- 本项目小程序句播放在 `segment.end - 0.05s` 到达时暂停；网页播放器按
  `segment.end` 暂停。小程序的 50ms 余量可能削掉极短尾音，但不足以单独解释“几个词”。
  本轮只诊断，没有修改播放器、JSON、MP3、数据库或生产状态。
- 用户随后提供新东方 IELTS Cat 对照页
  `https://ieltscat.xdf.cn/intensive/intensive/1817/2/1`。公开接口确认它是“剑雅20 Test 1
  Section 1 / Recommendation for Restaurants”：新东方为 45 句，本地/iDictation 在排除
  `PART 1` 后为 58 句；去掉每句重复说话人标签并规范标点后，两边 742 个英文词完全一致。
  新东方 44 个内部句界中有 42 个与本地/iDictation 落在相同词位（95.5%），另有 2 个
  新东方独有句界和 15 个本地独有句界，说明新东方主要是把较短片段合并成更长的精听句。
- 两边不能直接比较绝对秒数：新东方使用独立剪辑的纯对话 MP3，时长 `279.013875s`；
  本地/iDictation 原轨为 `435.570917s`，保留开场说明、看题时间和结尾。按共同词位分段校正后，
  前半段时间轴固定偏移中位数为 `40.620s`，共同句界残差绝对值中位数 `0.030s`、95 分位
  `0.120s`、最大 `0.140s`；中间删去约 `46.755s` 看题/说明块后，后半段固定偏移中位数
  为 `87.375s`，残差绝对值中位数 `0.015s`、95 分位 `0.055s`、最大 `0.075s`。
  因此这一个样本没有显示新东方逐句微调明显优于 iDictation；它听感更干净主要来自删掉非对话段、
  减少 13 个分句切点。新东方前端也没有显式句尾缓冲：`timeupdate` 到达 API `end` 后暂停/循环，
  浏览器事件粒度只可能带来少量越界播放，不能视作对时间戳缺陷的系统修复。
- 验证：`git status --short --branch`、`git log -5 --oneline`、
  `git rev-list --left-right --count HEAD...origin/main` 分别确认工作树、基线与 `0 0`；
  全量对账使用 `.venv/bin/python` 只读加载上述 raw/report/288 份 JSON，逐 part id 比较
  数量、文本、时间和 `file_url`，结果数字见上；`git show --stat 78a7721a`
  确认剑21修正只涉及四套 Section 1 JSON。新东方对照使用
  `curl -sS https://ieltscat.xdf.cn/api/newquestion/getIntensive -H 'content-type: application/x-www-form-urlencoded' --data 'qId=1817'`
  获取公开数据，再由 `.venv/bin/python` 对本地 `ielts20_test1_s1.json` 做规范化词序、共同边界及
  分段偏移统计；`ffprobe` 核对两条 MP3 时长，前端公开 bundle 只读确认逐句停止条件。
  本轮未改业务代码，不需重跑项目级测试；
  交接文档更新后 `git diff --check` 需保持通过。
- 下一位 agent 如要修正：先让用户给出 2–3 个可复现的“剑几 / Test 几 / Section 几 /
  第几句”，在同一 MP3 上核对该句与前后句的真实语音边界，再决定是只修数据、调整播放余量，
  还是对 288 个 Section 做一次可审计的批量重对齐。若采用新东方方案，必须重建或逐段映射其剪辑时间轴，
  不能把 0–279 秒的时间戳直接套到当前 0–435 秒原轨；可先以剑20 Test 1 Section 1 做 45 句试点。
  不要无条件给每句加大尾部余量，否则会把下一句的开头泄到当前句。

## 2026-08-12 听力 / 精听任务在小程序打开为空（后端已部署，小程序待用户发布）

- 当前工作树为 `/Users/zhouxin/Desktop/studytracker`，分支 `main`；本轮业务基线为 `bef6ca5450aa`，
  修复提交为 `db49c13c26cf`，已 push 到 `origin/main`。本轮开始时先安全暂存旧工作区改动，再 `git pull --ff-only`
  从 `fd711f1c` 快进到 `bef6ca54`；旧改动完整保留在
  `stash@{0}: codex-safety-before-pull-20260812`，没有丢弃或覆盖。
- 生产后台 Chrome 登录态只读核验：当前隐藏的“学习目标”下拉框实际为 `display:none`、`disabled=false`、
  `value=reading`；后台代码会把该值写入任何任务的 `Task.vocabulary_goal`。小程序首页和通用任务页又只凭
  `vocabulary_goal` 先走词汇 v2 门禁，所以被污染的听力任务会跳过原生听力路由，最终停在空白通用任务壳。
  生产“昨日任务”内嵌数据进一步显示 5 条听力记录中 4 条已完成记录 goal 为空，另 1 条待完成记录已误写为
  `reading`，解释了“昨天多数任务正常”与本故障可以同时成立。
- 当前故障任务的精听网页链接已只读打开并正常加载 58 句，剑雅整套网页链接正常加载 10 题，证明题库 JSON、
  token 链路和网页 URL 本身可用。生产 SSH 目前在密钥交换阶段由远端关闭，无法直接查询当前两条任务行；因此
  当前两条记录的 `vocabulary_goal` 仍是由相同创建路径、生产表单状态和小程序落页行为作出的高置信度推断，
  没有冒充数据库直查结论，也没有写生产数据库。
- 三层隔离已上线/就绪：`/tasks` 后端只允许 `dictation-*` 材料写学习目标；隐藏控件默认禁用并在离开词书来源时
  清空；小程序 API 对没有 `dictation_book_id` 的任务隐藏 stray goal；现有小程序首页、计时入口和通用详情页也
  必须同时看到词书 ID 与合法 goal 才能进入词汇 v2。后端/API/网页部分已部署，可兼容已污染任务且不依赖先清库；
  新增小程序防线需下一次由用户上传、提审、发布后生效。
- 本轮 9 个代码/测试文件已包含在 `db49c13c26cf`：`app.py`、`api/miniprogram.py`、
  `services/vocabulary_mastery.py`、`templates/tasks.html`、两个小程序任务页和三个回归测试文件。其余
  `.tmp/`、`artifacts/`、`data/reading_study/{browse,preview}.html`、
  `data/toefl_practice/ets-practice-{2,3,4,5}/`、`docs/design/`、两份 dictation 提案文档和 `prototypes/` 均为
  本轮前已存在的用户/其他任务内容，未修改。
- 验证：`.venv/bin/python -m pytest -q` 为 `492 passed, 7 subtests passed`；定向两轮分别为
  `45 passed`、`57 passed`；全部 `tests/test_*.js` 通过；两个改动小程序 JS 的 `node --check`、Python
  `compileall` 与 `git diff --check` 通过；新回归文件 Ruff/Black 通过。对旧巨型文件执行 Ruff 安全选择仍报告
  基线已有的 `app.py:2464 ParentStudentLink` 未定义，本轮未扩大范围修理。
- GitHub CI `31611257505` 的强制 test 与旧拼写门禁通过，整体 conclusion 为 success；存量 advisory Ruff job
  仍因仓库旧问题红，不阻断。部署 `31611257508` success，23:15:45 CST 重启服务并于 23:15:47 报告
  `Deployment successful`。登录态生产页刷新后真实 DOM 已变为隐藏控件 `disabled=true`、空值、占位
  “请选择学习目标”；公网 `/listening/tests` 为 200，根路由和未登录 `/tasks` 为预期 302。
- 本机到生产 SSH 仍在密钥交换阶段被关闭，因此未独立复核生产 Git HEAD、5002 进程参数、数据库 quick-check/
  外键和当前两条任务行；部署 workflow 的受限 SSH job 已成功完成。没有主动写业务数据，也无需清理历史任务行。
  小程序尚未由 agent 上传/提审/发布；用户应从当前主工作树
  `/Users/zhouxin/Desktop/studytracker/miniprogram` 发布，不能继续使用此前打开的
  `vocabulary-review-hotfix` 工作树。发布后让学生完全退出再进入，并先复测原听力/精听任务。

## 2026-08-12 取消单词严格键盘与输入授权（后端已部署，小程序待用户发布）

- 在同一正确发布工作树
  `/Users/zhouxin/.codex/worktrees/vocabulary-review-hotfix/studytracker`、分支
  `codex/vocabulary-review-hotfix` 完成一次性改造，并在提交前整合远端新增的“学生做题记录”
  `bec2dd27`，没有覆盖该并行功能。业务提交 `51623206d270` 已原子推送到任务分支和 `main`。
- 学生端所有五条单词自由文本作答链现在统一使用微信系统原生 `<input>`：旧听写练习、强化拼写、今日复习、
  词汇小组学习和自主间隔复习。严格键盘、输入模式切换组件及对应页面策略调用已删除；新客户端统一提交
  `input_mode=native`。首答判分、服务端幂等 attempt、错词纠正性重试、错词队列和后续间隔复习均保留，
  未改变判分归一化或掌握度结算规则。
- 后端输入策略改为 native 默认；为发布滚动期兼容，旧客户端提交的 `strict`、`compatible` 仍被接受，
  `compatible` 不再检查授权。已有有效授权只会作为旧提交的可选审计关联，不影响接受/拒绝。历史
  `dictation_input_grant` 表、记录和兼容 API 均保留，没有 schema 迁移、记录删除或生产数据写入。
- 网页 `/tasks` 的“单词任务输入授权”面板（含脚本/样式）和教师小程序学生页的“单词任务实体键盘”入口均已移除。
  旧授权 API 暂留只为兼容/审计，不再有产品入口；测试覆盖未授权 compatible、撤销后 compatible、native
  和旧 strict 均能提交，以及历史授权关联的保留行为。
- 整合最新 `main` 后，全部 Node 测试、全量小程序 JS 语法与 JSON 解析、目标 Ruff、Python compile 和
  `git diff --check` 通过；项目级
  `PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q --ignore=tests/test_static_audio_headers.py`
  为 `482 passed, 7 subtests passed`。仓库长期缺失的静态音频 fixture 仍按既有约定忽略。
- `main` CI `31575728750`、任务分支 CI `31575728809`、部署 `31575728757` 均 success。生产
  `/root/apps/studytracker` 已运行 `51623206d270`，服务于 15:52:00 CST 重启后 active；回环根路由 302，
  `127.0.0.1:5002`、1 worker、gthread、6 threads、单 worker 子进程均正确。数据库 `quick_check=ok`、
  外键错误 0，部署后应用错误 0；生产只保留既有未跟踪备份/调度库，没有 tracked 脏改动。
- 微信开发者工具 CLI 已重新打开正确项目
  `/Users/zhouxin/.codex/worktrees/vocabulary-review-hotfix/studytracker/miniprogram`（CLI 返回 `open`，HTTP 服务
  `127.0.0.1:63551`），等待用户手动上传、提审和发布。本地代码与后端已就绪，但小程序包尚未由 agent 上传；
  用户发布后仍应真机覆盖 `saving` 拼写、`incline` 所在流程、错答重试和跨复习到期点恢复，未完成真机验证前
  不把客户端闭环误报为完成。

## 2026-08-12 词汇任务中途复习门禁 / 自主复习确认键热修（后端已部署，小程序待发布）

- 本轮从最新 `origin/main@79698f2b` 创建独立工作树
  `/Users/zhouxin/.codex/worktrees/vocabulary-review-hotfix/studytracker`，分支
  `codex/vocabulary-review-hotfix`；业务提交 `1df19dfb8574` 已原子推送到该分支与 `main`。桌面原工作树
  带有来源不明的修改/未跟踪文件，本轮未触碰；没有写生产数据库，也没有代替用户上传或发布小程序。
- 生产只读核验确认两名学生不是同一个表面故障：蒋雅诺任务 `3364` 的 `saving` 维度于
  13:30:37 CST 到期，13:30:40 的下一次 queue 正好被服务端返回 409，随即创建自主复习 session `1`；
  陈相予任务 `3337` 也被引到 session `2`，首题为 `incline`。两人的教师任务学习流分别仍为 active
  （flow `13` / `2`），复习 session 也仍为 active，均为 0 答；Nginx/Gunicorn 没有任何对应 answer POST，
  `vocabulary_review_attempt` 也无两人的记录。因此已确认的共同根因是 queue 每次换题都重跑到期门禁，
  会把已经开始的任务在中途打断；没有服务端拒绝答案或数据丢失。
- 截图还确认严格键盘已显示 `saving`，但确认键处于不可用外观且点击没有到达服务端。服务端日志无法判定
  是独立 Boolean 属性与显示值短暂分叉，还是请求前客户端状态卡住，不能把具体微信运行时子因说成已证实。
  热修因此采用防御式处理：确认资格直接以组件当前显示值为事实源，不再由冗余 `canConfirm` 硬拦截；
  v2 两页提交时显示“提交中…”，answer 请求 15 秒超时后恢复可重试，attempt id 仍保证重复提交幂等。
- 后端保留“开始新任务前先复习”的规则，但已有 `VocabularyLearningFlow` 的任务不再被复习到期或 active
  session 中断；首页的复习欠账和 active session 不会清除。生产两人的任务都已有 flow，部署后可直接退出
  复习页并恢复原任务，无需删 session、重置 flow 或修改学生数据。
- 定向 51 个后端/API/小程序结构测试通过；项目级
  `PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q --ignore=tests/test_static_audio_headers.py`
  为 `482 passed, 7 subtests passed`。全部 `tests/test_*.js`、三个变更 JS 的 `node --check`、目标 Ruff 和
  `git diff --check` 通过。目标 Python 文件在本轮前就全部不符合当前 Black，未为热修批量格式化存量代码。
- CI `31573492201` 与部署 `31573492198` 均 success。生产 `/root/apps/studytracker` 已运行
  `1df19dfb8574`，服务于 15:20:11 CST 重启后 active/running；5002、1 worker、gthread、6 threads、单 worker
  子进程均正确，回环根路由 302，`quick_check=ok`、外键无错误，部署后 10 分钟应用错误计数为 0。两人的
  active flow / review session 均保留，按新规则 task gate 为 0，无需数据操作即可恢复原任务。
- 微信开发者工具 CLI 已打开正确项目
  `/Users/zhouxin/.codex/worktrees/vocabulary-review-hotfix/studytracker/miniprogram`（CLI 返回 `open`，HTTP 服务
  `127.0.0.1:63551`），等待用户手动上传、提审和发布。小程序发布后还需真机验证 `saving` 类拼写确认会发出
  answer POST、`incline` 类非拼写题也可提交及 15 秒失败恢复提示；未完成真机验证前不能宣称客户端问题闭环。

## 2026-08-11 教师任务页“昨日任务 / 再次布置”（已部署并通过生产验收）

- 本轮为避免覆盖桌面主工作树的来源不明改动，从最新 `origin/main@35991ae5` 创建独立工作树
  `/Users/zhouxin/.codex/worktrees/tasks-yesterday-repeat/studytracker`，分支 `codex/tasks-yesterday-repeat`，
  基线为 `35991ae5`，业务提交/生产 HEAD 为 `ecda60e1`；最终部署状态记录提交见当前 Git 日志。
  业务改动范围为 `app.py`、`templates/tasks.html`、新增 `services/task_assignment_history.py`、
  新增 `tests/test_task_assignment_history.py` 与交接文档；本轮未带入其他工作树改动。
- `/tasks` 布置表单现在会在学生/任务来源下方、具体材料选择上方显示选中学生的昨日任务。
  卡片包含任务名、类别、状态与资源来源；词书任务使用真实 `DictationBook.title` 并显示精确
  `第 X–Y 词`。结束位未存储时用词书总词数补充展示，但再次布置仍保留原始“至全部”语义。
- 只有未完成且未提交待批改的昨日任务显示“再次布置”。按钮不会立即写数据，而是安全回填
  今日现有表单的学生、来源、材料/题库、词序/句序、学习目标、出题顺序、计划用时与备注；
  老资源已停用或不存在时拒绝部分回填。教师仍必须复核后点原有“添加”，因此本轮没有新的直接写入端点。
  动态内容用 `textContent` 生成，并增加 `aria-live`、键盘焦点样式、窄屏单列和 44px 触控目标。
- 精确验证：
  `/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q tests/test_task_assignment_history.py tests/test_dictation_input_policy.py tests/test_task_review_permissions.py`
  为 `16 passed`（只有既有 SQLAlchemy / `datetime.utcnow` 弃用警告）；
  `/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check services/task_assignment_history.py tests/test_task_assignment_history.py`
  为 `All checks passed!`；同两文件 `black --check` 通过；
  `/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m py_compile services/task_assignment_history.py app.py` 与
  `git diff --check` 通过。此外用 Jinja 假数据渲染完整 `tasks.html`，抽取所有内联脚本后 `node --check`
  通过；Google Chrome 桌面宽度静态样例渲染已目视核对，截图为
  `/Users/zhouxin/.codex/visualizations/2026/08/11/019ff13b-61b4-7be2-a0bf-7505ec06606b/qa-yesterday-task-tall.png`。
  发布前项目级回归
  `PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q --ignore=tests/test_static_audio_headers.py`
  为 `481 passed, 7 subtests passed`；`node tests/test_dictation_spell_queue.js` 与最终 `git diff --check` 通过。
- 业务提交 `ecda60e1f9cda1e0aa30e959df29e66b9e73419d` 已原子推送到
  `origin/codex/tasks-yesterday-repeat` 与 `origin/main`。CI [31505122657](https://github.com/KB77GG/studytracker/actions/runs/31505122657)
  整体 `success`：强制轻量测试和 Node 门禁通过；存量全仓 Ruff 仍在 advisory job 报既有错误，该 job
  因 `continue-on-error` 不阻断，本轮新 service/test 的定向 Ruff 已单独通过。部署
  [31505122726](https://github.com/KB77GG/studytracker/actions/runs/31505122726) `success`，SSH 部署 job 用时 41 秒。
- 生产 `/root/apps/studytracker` 已运行 `ecda60e1f9cd`，只有既有未跟踪备份/调度库，无 tracked 脏改动。
  `studytracker.service` 于 2026-08-11 23:06:01 CST 重启后为 `active/running`；Gunicorn 仍是
  `127.0.0.1:5002`、`workers=1`、`worker_class=gthread`、`threads=6`，主进程加单 worker 子进程正常。
  本机回环 `/` 与 `/tasks` 均返回预期的未登录 `302`，部署后 `journalctl` 未见
  Traceback/ERROR/CRITICAL/OOM。
- 已在用户现有 Chrome 登录态中新建标签页验收真实生产 `/tasks`。选择“蒋雅诺”后显示
  2026-08-10 的 4 条已完成任务，两条词书分别显示 `第 31–104 词` 和 `第 1–52 词`，且无“再次布置”。
  选择测试账号后，未完成 `wl 3-1` 正确显示“进行中 / 第 1–50 词 / 再次布置”；点击后表单回填
  `material=dictation-7`、范围 `1–50` 并显示复核提示。验收未点“添加”，未创建任务或写数据库；
  原 Chrome 页中的未提交表单选择也未被刷新/覆盖。新生产验收标签已留给用户查看。
- 本轮无 schema/数据迁移，未改小程序，也无小程序上传/提审/发布。真实“无昨日任务”和
  “已停用旧资源拒绝回填”分支未在生产逐项点击，已由代码分支与定向测试覆盖。
- 桌面主工作树 `/Users/zhouxin/Desktop/studytracker` 本轮只读，仍为
  `main@fd711f1c`、明显落后 `origin/main`，且有多个已修改/未跟踪路径；本轮没有覆盖或并入这些改动。
  本任务已完成；若用户在真实日常学生上发现某类历史任务回填不全，下一位 agent 可直接从该任务 ID
  的 source/range 字段和浏览器回填值开始定向排查，不要更改生产任务数据。

## 2026-08-10 词汇答后辅助记忆卡与结果按钮比例（小程序已发布，后端待部署）

- 工作树为 `/Users/zhouxin/.codex/worktrees/9478/studytracker`，分支
  `codex/vocabulary-v2-release-20260809`，本轮基线/当前未提交前 HEAD 为 `386594064b08`。本轮在已发布热修之上新增答后反馈增强。
  用户已于 2026-08-10 晚间从正确 worktree 手动上传并发布本轮小程序；语义版本号和微信平台发布时间尚未由 agent 独立读取。
  对应代码及后端增强仍未 commit、push 或更新 `main`，生产后端仍未部署本轮增量。
- 新增共享 `vocabulary-feedback-card` 和响应归一化工具。小组学习页在提交成功后用既有平铺响应显示目标词、音节、音标、核心义、
  必要搭配、双语例句和可选用法提醒，并可重播发音；切题/刷新队列时清空旧反馈。自主复习服务只在答后响应和
  `first_attempt_id` 已存在的恢复分支返回同结构 `answer_feedback`，未答公开题面和同批其他未答项不携带该字段，避免
  `audio_to_en` / `zh_to_en` 提前泄词。此增量不需要数据库迁移。
- 用户截图中的浅绿色空块根因是严格键盘在结果态隐藏键列后仍保留组件外壳和 iPhone safe-area padding。两个词汇页现只在
  未出结果时渲染严格键盘；结果态使用独立 StudyTracker 绿色按钮。视觉初版的百分比宽度在虚拟 WXML block 下退化到
  `320rpx`，经二次对照改为稳定 `520rpx`（约页面宽度 70%），不再有空外壳，按钮上下留白正常；自主复习最后一题文案为
  “完成本批复习”。
- 回归结果：
  `PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q --ignore=tests/test_static_audio_headers.py`
  为 `475 passed, 7 subtests passed`；全部 `tests/test_*.js` 通过；四个变更 JS 文件 `node --check` 通过；目标 Ruff 和
  `git diff --check` 通过。微信开发者工具打开的是正确 worktree，iPhone 15 Pro Max 模拟状态同时覆盖答后卡顶部和滚动到底部的
  CTA，最终编译 `Errors: 0`；当前提示均为基础库/既有 WXSS 规则警告。设计对照记录为
  `/Users/zhouxin/.codex/worktrees/9478/studytracker/design-qa.md`，`final result: passed`；对照图保存在
  `/Users/zhouxin/.codex/visualizations/2026/08/10/studytracker-vocabulary-feedback/`。
- 当前业务改动涉及两个词汇页各自的 JS/JSON/WXML/WXSS、共享反馈组件/工具、
  `services/vocabulary_autonomous_review.py`、三个测试文件；交接与 QA 文件也为未提交修改。未触及生产数据或生产服务，生产后端仍是
  `26764e17677f`。截至 21:13 CST 的只读 Nginx 日志仍只见 `/83/` 页面引用，尚未看到新 page-frame 编号，因此“小程序已发布”目前
  以用户的微信平台操作确认为准，尚无新客户端拉包证据。未验证项为该新卡在真实登录 iPhone/Dynamic Type 下的最终密度、自主复习
  真实答题/刷新恢复，以及发布包被真机实际拉取；发音播放器本身未改且上一版真机已验收。
- 用户已明确授权提交、推送并部署后端。下一位 agent 先用 `git status --short --branch` 核对上述改动，重跑门禁后将发布分支快进
  更新到 `main` 触发部署；本轮后端字段为纯追加、无数据库迁移，旧客户端忽略，新前端在旧后端缺字段时安全隐藏。部署后核验
  生产 HEAD、CI/deploy、5002、1 worker/gthread/6 threads、错误日志和答后 `answer_feedback` 契约，再用真实学生验收普通小组学习
  答后卡及今日自主复习的答后/刷新恢复。

## 2026-08-10 词汇 v2 真机音频 / 输入 / 品牌色热修（已发布并通过真机音频验收）

- 正确发布 worktree 仍为 `/Users/zhouxin/.codex/worktrees/9478/studytracker`，分支
  `codex/vocabulary-v2-release-20260809`；热修业务提交为 `26764e17677f`。本轮开始时只有上一轮未提交的
  `docs/CODEX_HANDOFF.md`、`docs/WORKLOG.md` 修改；现新增词汇学习/自主复习页面、共享音频与选项工具、
  两个词汇服务及对应测试修改。业务提交已推送到发布分支和 `main` 并部署；用户已从正确 worktree 发布热修小程序，上传时
  约定版本号为 `16.0.75`。微信公众平台版本详情页受浏览器安全策略限制，agent 未绕过限制二次读取语义版本号；生产访问日志已
  独立证明真实 iPhone 拉取了新的 `/83/` 小程序包。
- 线上 `16.0.74` 真机暴露三项问题：播放按钮无声且熟悉/听音题没有可靠自动播放；听音写中文走 iOS 原生键盘、
  听音拼英文走小程序严格键盘，体验不一致；词汇 v2 正常交互误用了橙色而非 StudyTracker 品牌绿。生产访问日志此前已证明
  word-id TTS 返回 206 且有完整音频字节，故根因位于新页面的 iOS 播放生命周期：未设置
  `obeyMuteSwitch=false`，并在 `canplay` 前直接 `play()`。
- 已抽出可靠播放器：全局与实例均关闭“跟随静音键”，音频先下载/缓存，兼容 200/206，等 `onCanplay` 后播放，处理快速切题、
  重播和销毁竞态，并给按钮显示“正在加载 / 正在播放”。熟悉阶段首次进入、上一词/下一词，以及所有 audio 题切题后都会自动播放；
  手动按钮复用同一播放器。TTS 端点本来就是公开播放契约，不需要另加认证头。
- 听音→中文现统一为稳定四选一（尾组不足时按可用唯一释义降级），不再打开系统键盘；听音→英文继续使用小程序严格键盘。
  当前已冻结的任务 `3331` 由客户端从该组 familiarity 安全生成稳定选项，正确项强制保留且题序不依赖词位；新题快照由后端生成
  最多四个稳定中文选项，但仍提交选项标签并沿用 `answer_type=chinese`，所以旧 `16.0.74` 可继续手输中文，向后兼容。
  已存在的自主复习 session 会在公开响应时动态补选项，不改数据库快照或答案。普通交互色改为 `#087f77` 品牌绿和配套浅绿；
  橙色已从两个词汇页移除，红色只保留错答/错误语义。播放图标改为 CSS 三角形，避免系统 emoji 外观差异；触控项不低于 88rpx。
- 验证：`node tests/test_dictation_audio.js` 通过，覆盖静音键配置、206 下载、`canplay` 门禁、播放器销毁、正确释义不被裁掉及稳定乱序；
  六个词汇/小程序定向 pytest 文件合计 `78 passed`，包含“自主复习选择标签仍按中文正确判分”；全部 `tests/test_*.js` 通过。
  全仓 pytest 为 `474 passed, 7 subtests passed, 2 failed`，两个失败均是 worktree 长期未带
  `static/listening/ielts10_test1_s1.mp3` 导致既有 `test_static_audio_headers.py` 404，与本轮无关；同一 JSON fixture 通过。
  四个变更 JS 文件 `node --check`、`git diff --check` 通过。微信开发者工具 CLI 已打开正确 worktree，日志确认本轮文件逐项触发编译，
  IDE 底部为 0 errors / 0 warnings；未做真机声音/静音键终验。
- 生产发音抽样：任务 `3331` 当前组 8 个 word-id 音频均为有效 48 kHz 单声道 MP3；`analyst`、`assignment`、
  `audience`、`adventure`、`ankle`、`anger` 的生产文件 SHA-256 与有道词典 `type=2` 真人录音逐字节一致；词典对
  `abstract`、`advertisements` 只提供被质量门禁拒绝的低质量合成版本，因此生产按既有策略使用 Kokoro
  `af_heart / en-us / 0.88` 回退。word-id 路由先取 `audio_us`、再取 `audio_uk`，都缺失时才走上述质量门禁；
  送入发音的文本先去掉词性并由 `canonical_vocabulary_word` 取安全词形，生产默认每词只读一次。该审计不替代热修版真机听感终验。
- 发布状态：用户已明确授权 commit/push/deploy；`26764e17` 已推送到发布分支与 `main`。CI
  [31373716673](https://github.com/KB77GG/studytracker/actions/runs/31373716673) 和部署
  [31373716678](https://github.com/KB77GG/studytracker/actions/runs/31373716678) 均 success，部署前旧错词无限回插门禁通过。
  生产 `/root/apps/studytracker` 已运行 `26764e17677f`，服务于 17:15:50 CST 重启后 active/running；5002、1 worker、gthread、6 threads
  和 1 个 worker 子进程均正确。`PRAGMA quick_check=ok`、外键错误 0，根路由 302；`analyst` word-id 音频普通请求为
  `200 audio/mpeg 11757 bytes`，Range 为 `206 audio/mpeg 1024 bytes`，部署后日志应用错误为 0。本热修没有 schema 迁移或主动生产数据写入。
  生产自主复习 item 当前为 0；任务 `3331` 已冻结的 50 个 `audio_to_zh` 快照仍无 options，符合兼容设计，由热修客户端从当前组 familiarity
  补出选项，无需重建 flow 或修改任务数据。
- 用户确认热修小程序已发布。生产日志从 18:12:47 CST 起看到真实 iPhone（MicroMessenger 8.0.75）的页面资源由旧 `/82/`
  切换到新 `/83/`；截至 18:14:21 共 43 个新包请求，全部为 200、无 4xx/5xx。任务 `3331` 的 summary、detail、preflight、
  vocabulary queue、submit 及本组 8 个 word-id TTS 均连续 200；没有重新请求 familiarity 属预期，因为 flow 已在发布前越过该阶段，
  当前为 `retry`、`state_version=36`。近 30 分钟生产日志中 Traceback/ERROR/CRITICAL/OOM 为 0，服务与进程参数仍正常。
- 用户随后在真实 iPhone 确认新包发音正常，服务端无法证明的物理出声门禁已通过；本次音频热修发布闭环完成。本轮没有修改任务数据、
  数据库或生产服务。
- 真机截图同时暴露新的非阻断 UX 缺口：`错题再测` 答后反馈只显示“你的答案 / 正确答案”，没有呈现辅助记忆材料。不是资料缺失：
  learning 提交响应已有音节、音标、核心义、搭配、英例、中译和用法备注，任务 `3331` 的 50 词中前六项均为 50/50、用法备注 43/50；
  熟悉阶段也已有同组材料。最小后续方案是在**提交后**复用旧听写页的词汇反馈卡，严禁在作答前泄露；learning 仅需前端渲染，
  autonomous review 还需后端只在答后响应及已答恢复分支返回 enrichment。该增强已在后续本地工作中实现，尚未发布，见上一节。

## 2026-08-10 正确小程序 16.0.74 已发布并通过真机验收（发布事故已关闭）

- 15:55–15:57 的首个真实 v2 任务 `3331` 已正确保存为 `dictation_book_id=7`、范围 1–50、
  `vocabulary_goal=listening`；生产后端详情和 `dictation-queue` 均返回 200，新队列响应约 5.4 KiB。手机却进入旧“听写练习”页，
  显示“当日布置 0 词 + 自动复习 0 词”。访问日志证明客户端没有调用新版必经的
  `vocabulary-review/preflight`，而是直接让旧页面读取新 group queue；旧页面只识别 `res.words`，因此把新契约显示为空。
- 根因不是任务或数据库，而是小程序 `16.0.73` 上传了错误工作树。上传时微信开发者工具指向
  `/Users/zhouxin/Desktop/studytracker/miniprogram`；该主工作树仍为 `main@fd711f1c`、落后 `origin/main` 23 个提交，
  `home/index.js` 不含 `vocabularyGoal` / `vocabulary-learning` 路由。正确且已回归的前端在
  `/Users/zhouxin/.codex/worktrees/9478/studytracker/miniprogram`（发布分支业务基线 `21398163`，当前 docs HEAD 见 Git）。
- 已用微信开发者工具 CLI 将正确目录打开；解锁后确认 IDE 地址中的 `projectpath` 和资源管理器均指向正确发布工作树，
  手动重新编译为 `Errors: 0`、`Problems: 0`，4 条 warning 均为基础库/开发工具提示。正确目录定向回归：
  `tests/test_miniprogram_vocabulary_learning.py`、`tests/test_miniprogram_task_visibility.py`、
  `tests/test_vocabulary_group_learning_api.py` 合计 `20 passed`；旧错词 Node 门禁、四个关键页面 `node --check`、
  `git diff --check` 均通过。
- 用户已从确认无误的正确项目
  `/Users/zhouxin/.codex/worktrees/9478/studytracker/miniprogram` 发布 `16.0.74`，线上发布时间为
  2026-08-10 16:27:56（Asia/Shanghai）。iPhone 完全退出并重开后，线上客户端路径从错误版本 `/81/` 切换为
  `/82/`；任务 `3331` 依次调用 summary、task detail、`vocabulary-review/preflight`、`vocabulary-queue` 和
  `vocabulary-learning/familiarity`，全部返回 200。服务端 flow `id=1` 为 listening / 8 词一组，已从 familiarity 正常推进到
  `active_recall`，`state_version=8`，冻结题 100 道；`PRAGMA quick_check=ok`、服务 active、发布后应用错误为 0。
  因此发布事故已关闭，可以恢复创建新词汇任务；任务 `3331` 保留并继续使用。本次没有回滚或重新部署后端。

## 2026-08-10 词汇 v2 已正式上线（当前规范状态）

- 发布工作树为 `/Users/zhouxin/.codex/worktrees/9478/studytracker`，分支为
  `codex/vocabulary-v2-release-20260809`。业务发布 HEAD `21398163fa98a647d66cbf29be8a320a88fd60b4`
  已快进推送到 `origin/main`；最初发布的错误源版本 `16.0.73` 已由正确发布工作树构建的 `16.0.74` 于
  2026-08-10 16:27:56（Asia/Shanghai）取代。当前业务代码已 commit、已 push、已部署；本节交接更新会作为 docs-only 提交只推送到发布分支，避免再次触发
  `main` 部署，精确文档 HEAD 以 `git log -1` 为准。
- 更新 `main` 前已暂停创建新词汇任务，并对生产 `/root/apps/studytracker/app.db` 做 SQLite 在线备份：
  `/root/apps/studytracker/app.db.bak-20260810-vocabulary-v2`，大小 `64,397,312` bytes，SHA-256
  `dd5c1ec42c028e3913d54519a9a76aed1e11190b834739b4c69ebab63b6a2854`；备份
  `PRAGMA quick_check=ok`，含 194 本词书、3,190 个任务、最大任务 ID 3326。备份为生产机本地文件，未同步到 Git，
  不得把它加入仓库。
- GitHub `main` CI [31351428148](https://github.com/KB77GG/studytracker/actions/runs/31351428148) 整体 success：
  强制 test 和旧错词无限回插 Node 门禁通过；lint 仍因仓库存量 Ruff 问题失败但为 advisory。部署
  [31351428153](https://github.com/KB77GG/studytracker/actions/runs/31351428153) success，部署前同一旧错词门禁通过；
  生产 `/root/apps/studytracker` HEAD 为 `21398163fa98`，`studytracker.service` 于 11:02:42 重启并保持 active。
- 生产迁移核验：`PRAGMA quick_check=ok`、`pragma_foreign_key_check` 为 0；历史任务仍为 3,190 条且
  `vocabulary_goal IS NOT NULL` 为 0，没有把旧任务误升级。10 张词汇 v2 表均已创建且初始业务行数为 0。
  词书目标共回填 188 本：`reading=127`、`listening=39`、`comprehensive=21`、`writing=1`；课程体系为
  `IELTS=38`、`TOEFL=129`、`general=21`；ID 174 的目标和课程体系均保持 NULL。生产 gunicorn 仍为
  `127.0.0.1:5002`、`workers=1`、`worker_class=gthread`、`threads=6`。
- 生产 HTTP 与真机冒烟：`/` 返回预期登录重定向 302；未带令牌的新 summary 路由返回预期 `401 missing_token`。
  服务重启后真实 Android 学生继续提交 legacy 任务成功；正确小程序 `16.0.74` 发布后，真实 iPhone 学生又用任务 `3331`
  完成 summary → preflight → vocabulary queue → familiarity 的新版链路并进入 active recall，相关请求全部 200，未见迁移或应用错误。
  创建新词汇任务的暂停已解除；后续继续观察 context 阶段、任务结算与次日自主复习。
- Codex 已将 active 线程提醒 `d-30`（名称“背单词旧版退场门禁”）改以正确版本为起点：2026-09-09 16:27:56
  做 D+30 旧入口检查，2026-10-09 16:27:56 做 D+60 旧兼容检查。D+30 仅在新版覆盖率达到 95% 且连续 7 天无未完成 legacy 任务时规划移除 UI
  旧入口；D+60 还要求 D+30 已完成、无活跃 legacy 任务且无旧客户端依赖。提醒不会自动删除历史成绩或未经回归直接发布。
- 下一位 agent 的直接动作：无需再次部署本次代码；先检查实际 Git/生产状态。跟踪首个新 v2 任务的学习链、context 题与次日
  自主复习数据；到 D+30/D+60 由提醒按真实生产指标决定是否退场旧入口。若需回滚业务代码，先保留当前数据库及上述上线前备份，
  不要删除新表或历史记录。

## 2026-08-09 词汇 v2 正式发布分支（历史发布准备记录）

- 正式发布工作树为 `/Users/zhouxin/.codex/worktrees/9478/studytracker`，分支
  `codex/vocabulary-v2-release-20260809` 已将完整实现重放到最新 `origin/main@67927544888e`；两份交接文档冲突已人工
  合并，保留主线 TOEFL 已部署事实和词汇 v2 全部事实。重放后的业务提交为 `ba8b214d`，本节写入后会 amend，精确 HEAD
  以 `git log -1` 为准。
- 重放后完整发布回归：全部 `tests/*.js` 通过；
  `PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/pytest -q --ignore=tests/test_static_audio_headers.py`
  为 `472 passed, 7 subtests passed`，只有既有 SQLAlchemy/UTC 弃用警告；旧强化拼写 50 词门禁包含在 Node 全量中。
  微信开发者工具仍为 0 errors / 0 code problems。模拟器登录态失效，真实接口/真机仍必须在发布链路中完成。
- 发布分支已推送为 `ba51085a68726a0a7674f557ef914949af3b8619`；CI
  [31318885765](https://github.com/KB77GG/studytracker/actions/runs/31318885765) 成功，强制 test job（含旧错词 Node 门禁）通过；
  lint job 仍因仓库存量问题失败但按工作流为 advisory，整体结论为 success。不得先更新 `main`。后续顺序保持：
  用户在微信开发者工具上传，并在公众平台提审/发布、确认线上可获取 →
  暂停创建新词汇任务 → 备份生产库 → 更新 main 触发后端部署 → 核验迁移/映射/quick-check/5002/进程 → 真实登录学生与真机
  冒烟 → 恢复任务创建。用户已明确由本人处理小程序上传/提审/发布；完成后需告知实际版本和发布时间。
  D+30/D+60 提醒以实际小程序发布日期创建。

## 2026-08-09 旧强化拼写错词无限回插（已修复，发布门禁通过）

- 学生反馈“错一个词后，该词会持续与新词组合出现”。代码核对与 50 词队列复现确认该问题真实存在于旧版
  `miniprogram/pages/student/dictation/spell/index.js`：每次答错都会调用 `reinsertCurrentWord()`，按
  `REINSERT_GAP=3` 把当前词再次插回队列；没有每词重试次数上限，揭示答案也不会把该词标记完成。
- 50 词模拟中，若首词 `n` 始终答错、其余 49 词均答对，`n` 会先夹在新词之间出现 17 次；到第 66 次作答后
  队列只剩 `n`，之后可无限循环。因此并非固定“打 50 遍”，而是没有有限上限。
- 词汇 v2 小组状态机不存在同一问题：首答错题只在组末生成一次纠错重试，重试仍错会完成本组并记入
  `needs_review`。定向执行
  `PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/pytest -q tests/test_vocabulary_group_learning.py -k "wrong_mastery_encounter_requires_one_retry or retry_wrong_can_finish"`
  得到 `2 passed, 14 deselected`。但历史 `vocabulary_goal=NULL` 任务仍明确保留旧入口，所以仅部署 v2 不会消除
  现有学生遇到的循环。
- 已把旧强化拼写改为与 v2 一致的有限策略：主轮错词只追加到队尾一次；纠错轮仍错时把该词计为本轮完成并依赖首答时
  已建立的后续复习安排，不再回插。纠错项有显式页面标签；恢复到已有错误首答时会复用该首答，不会把纠错答案误当作新首答。
  首答成绩和教师统计保持不被纠错覆盖。
- 新增纯队列模块 `miniprogram/utils/dictation-spell-queue.js` 与 50 词发布门禁
  `tests/test_dictation_spell_queue.js`：持续答错的 `n` 只出现主轮、纠错轮各一次，50 个词共 51 次作答即可有限完成；重复点击
  重新拼写不会追加多个纠错副本，多错词按首错顺序进入纠错，纠错仍错不再排队。门禁已接入 `.github/workflows/ci.yml`，也在
  `.github/workflows/deploy.yml` 的 SSH 部署前执行，未来回归会直接阻止生产部署。
- 验证：相关定向 pytest 为 `17 passed, 26 deselected`；全部 `tests/*.js` 通过；零 deselect Python 回归命令
  `PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/pytest -q --ignore=tests/test_static_audio_headers.py` 为
  `458 passed, 7 subtests passed`；目标 Ruff、Node syntax 与 `git diff --check` 通过。微信开发者工具热重载后为 0 errors、
  0 code problems；模拟器登录态失效，真实词书请求返回 401，故尚未完成真实登录学生/真机端到端。
- 发布阻断已经解除，可以恢复既定“小程序先、后端后”流程；但本节更新时仍未 commit、push、写生产数据库、部署后端或
  上传/提审/发布小程序。真实登录学生与真机冒烟仍是发布过程门禁。

## 2026-08-09 登录页顶部比例修正（功能工作树，本地未提交）

- 用户在主工作树的小程序预览中指出登录卡片顶部“返回 / 账号登录”比例失衡。本轮只在词汇发布候选工作树
  `/Users/zhouxin/.codex/worktrees/9478/studytracker` 增量修改：`miniprogram/pages/index/index.wxml`、
  `miniprogram/pages/index/index.wxss`、`tests/test_miniprogram_guest_access.py` 以及本交接文档/工作日志；主工作树
  `/Users/zhouxin/Desktop/studytracker` 的既有脏改动没有被覆盖或改写。
- 第一版三列居中方案在整窗缩略图里被误判为通过，但用户提供的局部截图明确显示小程序原生按钮仍被拉宽，并把
  “账号登录”挤到只剩“登录”；该方案已撤回，交接不得继续把它写成正确结果。最终实现恢复为左右结构：返回使用原生
  `size="mini"`，同时用 `width/min-width/max-width/flex-basis=132rpx` 强约束，触控高度为 `80rpx`；右侧“账号登录”
  使用不换行纯文本标签。既有品牌色、卡片、主登录按钮和授权逻辑保持不变。
- 微信开发者工具 Stable 2.01.2510290 已切换到上述功能工作树，iPhone 15 Pro Max（430×932）同状态对照通过：
  用户局部截图与修正版完整截图已放在同一比较输入中核对，返回现为左侧紧凑按钮，“账号登录”在右侧完整显示且没有重叠；
  编译为 0 errors、0 code problems，3 条为工具/基础库提示。辅助功能树仍把“返回”识别为按钮、“账号登录”识别为文本；
  实际点击返回可回到欢迎页，再次进入登录页正常。审查截图暂存于 `/tmp/studytracker-login-auth-audit-2/`。
- 验证命令与结果：
  `PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/pytest -q tests/test_miniprogram_guest_access.py`
  为 `5 passed`；
  `PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/pytest -q --ignore=tests/test_static_audio_headers.py`
  为 `457 passed, 7 subtests passed`；
  `/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check tests/test_miniprogram_guest_access.py` 与
  `git diff --check` 均通过。未做真机 VoiceOver/读屏专项验收。
- 当前功能工作树仍为 detached HEAD `e1f1b3fafecf68cb065d29e0c76e67d30758fa8e`，共有 33 个 tracked 改动条目、
  13 个 untracked 路径（包含此前整套词汇 v2 工作）；全部仅本机可见，未 commit、push、写生产数据库、部署后端、
  上传/提审/发布小程序。下一位 agent 可从此工作树继续正式发布准备，不要误从当前主工作树上传小程序。

## 2026-08-09 词汇 v2 发布就绪审查（错词循环门禁已补齐）

- 结论：本地实现与自动化发布门禁已通过，微信开发者工具编译及关键模拟器交互也已通过，可以进入“整理发布分支 →
  提交/推送 → 小程序先发 → 后端后发”的正式发布流程；当前仍不是已提交或已上线状态。本轮修改了两个测试缺陷和交接文档，
  没有 commit、push、写生产数据库、部署后端或上传/提审/发布小程序。上方旧强化拼写错词门禁已补齐且完整回归通过。
- 词汇功能工作树为 `/Users/zhouxin/.codex/worktrees/9478/studytracker`，仍是 detached HEAD
  `e1f1b3fafecf68cb065d29e0c76e67d30758fa8e`；核对的 `origin/main` 为
  `67927544888eff91e3aadfa505d73377c13ada4f`，功能基线落后 7 个提交。当前共有 30 个 tracked 改动条目和 13 个
  untracked 路径；本轮只增量修改了本来已属词汇实现的词汇 context 服务、学习/复习页、对应测试以及两份交接文档，
  没有覆盖其他来源改动。
- 两个测试缺陷已修正：HTTP 测试现在把固定复习时钟同时注入 preflight 与 group queue；稳定排序测试把相邻 pair 改为
  等长的 `zip(seq[:-1], seq[1:], strict=True)`。功能工作树运行
  `PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/pytest -q --ignore=tests/test_static_audio_headers.py`
  得到 `456 passed, 7 subtests passed`；最新 `origin/main` 临时集成副本运行同一命令得到
  `470 passed, 7 subtests passed`，没有 deselect。唯一 ignore 的 `test_static_audio_headers.py` 依赖仓库长期缺失的两个静态音频
  fixture；两个变更测试文件 Ruff 为 `All checks passed`。此前 6 个 Node 测试文件共 11 项、词汇模块 Ruff、Python 编译/
  3.10 grammar、JS/JSON 和迁移幂等验证仍有效。
- 最新 `main` 临时 worktree 中，业务 tracked diff 通过三方应用，untracked 词汇文件也完整复制；只有
  `docs/CODEX_HANDOFF.md`、`docs/WORKLOG.md` 因主线同时更新而产生文档冲突，正式发布分支需人工保留双方最新事实。
  临时集成 worktree 仅用于验证，收尾时删除，不是可发布分支。
- context 填空中文辅助已补齐：例句有 `example_zh` 时题面明确显示“句子翻译”；缺少配套句译但有已审核中文词义时，
  显示“目标词义”，不会把词义冒充整句翻译；搭配补词同样显示“目标词义”。连中文词义都缺失的资料失败关闭，不再生成下方
  空白的填空题。学习页和今日复习页使用同一契约及视觉区块，新增服务端/页面结构测试覆盖标签和值。
- 分组大小按目标固定为 reading/listening/writing/comprehensive=`10/8/8/6`，只有综合掌握是 6 词一组。熟悉卡按老师选定的
  词书顺序（任务选择 random 时按服务端稳定随机顺序）浏览；主动提取、语境辨析、语境产出分别用 phase-specific seed 稳定乱序，
  与熟悉顺序及相邻阶段解耦，并尽量避免同一 sense 在阶段边界连续出现。稳定性只用于刷新/换设备恢复同一题序，不代表沿用词位。
- 教师真实 `/tasks` POST 冒烟通过：ID188 未显式选择时采用 `writing`，显式 override 可保存 `reading`，共创建 2 个任务，
  同时验证 PlanItem shadow 与 material mode。真实文件 SQLite 并发/CAS 冒烟连续 10 轮通过：每轮两个独立 session/线程竞争
  同一道首题，结果为 10 次成功、10 次预期冲突、0 重复首答，`state_version` 每轮只推进一次。两项均使用临时数据库，未写生产。
- 用户登录后，微信开发者工具 Stable 2.01.2510290 已用官方 CLI 打开功能 worktree；补齐中文辅助区后再次编译仍为
  0 errors、0 code problems；
  仅有热重载、SharedArrayBuffer、`getSystemInfo` 与灰度基础库等工具/基础库警告。模拟器已检查熟悉、中文主动提取、严格键盘输入、
  context 四选一、今日自主复习、错答反馈和下一题；iPhone 5（320×568）错题页无横向溢出或按钮遮挡。由于生产后端尚未部署，
  新接口返回 404 属预期；本轮用页面状态 mock 做 UI/交互验收，尚未做真实后端端到端、真机、上传或提审。
- 发布顺序必须固定为：① 在最新 `origin/main` 上创建 `codex/` 发布分支并人工合并两份交接文档；② 完整回归；③ **先上传、
  提审并发布新版小程序，确认线上已可获取新版本**；④ 在后端切换完成前暂停老师创建新的映射词书任务；⑤ 备份生产
  `app.db`，再部署后端并立即核验迁移 schema/映射计数、`PRAGMA quick_check`、5002 与进程参数；⑥ 做登录学生真实接口/
  真机冒烟后解除任务创建暂停。原因：新版小程序连接旧后端时，summary 404 会降级为 0 且旧任务继续 legacy 流程；反向顺序下，
  尚未更新的旧客户端会拿到带 `vocabulary_goal` 的 v2 任务，却不能理解 preflight/强制复习 409。
- 生产只读状态仍为“未部署”：HEAD `67927544888e`、服务 active、Python 3.10.12、约 15G 空间，数据库
  `quick_check=ok`、194 本/3,174 任务且无词汇 v2 schema；gunicorn 为 127.0.0.1:5002、1 worker、gthread、6 threads。
  `/usr/local/sbin/deploy-studytracker` 不备份数据库且不显式核验词汇迁移，不能直接裸跑；迁移由启动链间接触发且异常可能只记日志。
- 下一位 agent 可直接执行：获得用户明确授权后，在最新 main 建正式 `codex/` 发布分支，合入功能改动并解决两份文档冲突，
  重跑上述零 deselect 回归；随后严格按“小程序先、后端后”的顺序发布。真实后端/真机 E2E、生产库备份与迁移验收仍是发布操作中的
  必做门禁；完成前不得写成“已上线”。

## 2026-08-08 词汇 v2 小组学习链（本地未提交）

- 工作树仍为 `/Users/zhouxin/.codex/worktrees/9478/studytracker`，detached HEAD `e1f1b3fa`；本轮未
  commit、push、部署、写生产数据库或上传小程序。已有未提交改动均保留并在其上增量修改。
- opt-in `vocabulary_goal` 任务已接入服务端固定分组与 A–E 可恢复状态机：熟悉、稳定主动提取、语境辨析、
  语境产出、错题纠正重试；reading/listening/writing/comprehensive 分组大小分别为 10/8/8/6，最后组取余数。
  legacy `vocabulary_goal=NULL` 仍走原链路。新小程序专页显示组号/阶段，旧 practice/spell v2 入口在门禁后跳转。
- 服务端保存组边界、题目快照、queue token、attempt id、CAS `state_version` 和首答/重试字段；熟悉不改 mastery，
  同一 sense×dimension 遭遇最多结算一次，context 产出优先、缺失时显式 degraded choice 降级。错题至少重试一次，
  重试不改首答/教师分母/mastery；重试仍错计入 needs_review 但不阻塞完成。跨日变更继续执行自主复习 preflight。
- 稳定洗牌使用剩余计数优先和 hash tie-break，承接熟悉末词及正式阶段末词边界；存在可行排列时不会相邻出现同一 sense；
  listening 目标不会生成 context 题。已有 schema 会为中间版本补齐 `state_version` 等字段，SQLite 锁冲突归一为可重试 409。
- 验证：group+HTTP 20 项已通过；词汇/听写/小程序相关 Python 128 项、Node 测试脚本全量通过，未出现 skipped。
  全仓 Python 共 427 项，仅 2 个既有静态音频 fixture 缺失用例仍因 404 失败；本轮相关 128 项全部为绿。目标文件
  Ruff、`py_compile`、Python 3.10 grammar parse（19 个变更 Python 文件）、JSON/WXML 结构和 `git diff --check` 通过，Node 页面
  `--check` 通过。
- 在 61MB 生产只读副本的再副本上完成新增小组表迁移演练：二次迁移 SHA-256 不变，`PRAGMA quick_check=ok`，
  `state_version` 存在。随后用真实 ID188 写作词书初始化 922 词任务，得到固定 8 词/组、116 组、尾组 2 词、
  2,131 道冻结题；队列未出现答案字段，首次全书快照在本机耗时约 5.66 秒。原副本和生产数据库均未写入，临时
  验收副本已移入系统废纸篓。
- 未验证：当前机器没有独立 Python 3.10.12（grammar 用 Python 3.13 的 `feature_version=(3,10)` 检查）；未做真实文件
  SQLite 双会话/多线程压力测试、微信开发者工具/真机窄屏视觉验收或生产接口演练。WXML 结构检查对小程序专用属性做了
  XML 兼容化后解析，仍应在开发者工具中做最终编译检查。

## 使用规则

1. 开工先完整阅读根目录 `AGENTS.md`、`CLAUDE.md`、本文件和 `docs/WORKLOG.md`。
2. 随后运行 `git status --short --branch` 与 `git log -5 --oneline`。如果实际 Git 状态与本文不一致，以 Git 和可复现验证结果为准，并更新本文。
3. 不覆盖或删除来源不明的本地改动；先确认它们是否属于用户或另一项任务。
4. 每个项目任务收尾都做交接审计；有任何持久化事实变化时，更新“当前基线、近期完成、验证状态、发布状态、待办与下一步”，并在 `docs/WORKLOG.md` 顶部追加简短记录。
5. 不在本文记录密码、令牌、Cookie、服务器密钥或学生隐私。
6. 交接必须区分各 worktree 的绝对路径、分支/HEAD、既有与本轮脏文件，并区分本机未提交、已 commit、已 push、后端已部署及小程序已上传/提审/发布。
7. 未获用户明确授权时，不得为了完成交接自行 commit、push、部署、写生产库或发布；只更新本地文档并明确其同步范围。
8. 最终回复必须说明交接文档是否更新、位于哪里，以及下一账号或下一台电脑能否直接取得本轮内容。

## 2026-08-08 跨账号交接机制固化（本地未提交）

- 本机全局 `/Users/zhouxin/.codex/AGENTS.md` 已加入强制收尾交接审计；仓库根 `AGENTS.md`、
  `CLAUDE.md`、本文件和 `docs/WORKLOG.md` 也同步写明账号无关的事实源、交接字段和授权边界。
- 截至本次审计，主工作树 `/Users/zhouxin/Desktop/studytracker` 为 `main` / `fd711f1c`，落后
  `origin/main` 21 个提交，且在本轮开始前已有多项未提交和未跟踪工作；本轮没有覆盖这些业务改动。
- 词汇功能工作树 `/Users/zhouxin/.codex/worktrees/9478/studytracker` 仍为 detached HEAD
  `e1f1b3fa`，四维词汇、自主复习和小组学习链的本地未提交实现保持不变，其详细验证与待办见本文件
  对应章节。
- 本轮只固化交接规则和日志，没有改业务代码、生产数据库或外部系统，也没有 commit、push、后端部署、
  小程序上传/提审/发布。同一 macOS 用户下切换 Codex 账号可立即读取；另一台电脑暂时无法取得本轮文档改动。
- 规则验证：本机不存在会遮蔽全局规则的 `AGENTS.override.md`；全局与项目 `AGENTS.md` 合计不足 7 KiB，
  低于默认 32 KiB 指令上限；两个工作树的四份目标文档均通过 `git diff --check`。本轮是纯文档改动，未重复运行业务测试。

## 2026-08-08 四维词汇掌握与 context_use v1（独立工作树，未提交/未发布）

- 工作树：`/Users/zhouxin/.codex/worktrees/9478/studytracker`，detached HEAD 基线
  `e1f1b3fa`；全部改动仍为本地未提交状态，没有 commit、push、后端部署或小程序上传。
- 新任务按 `reading / writing / listening / comprehensive` 目标进入四维状态；历史
  `vocabulary_goal=NULL` 任务继续走旧听写/错词链路。四维独立 stage/due，间隔为
  1/3/7/14/30/60 天，跨过 30 天后仍以 60 天维护；提前答对不推进，答错次日重置。
- 新增保守 sense 归并、同日到期领取、严格首答幂等与结算、按词条 ID 的音频/TTS、老师目标选择、
  小程序逐题模式，以及 context_use 四类确定性题目。题面和服务端答案分栏固化；choice 固定 4 个
  真实候选框架，fill 会遮蔽全部批准变体；缺素材时失败关闭，不调用模型临时生成或判分。
- 词书空值回填：2–39 listening/IELTS；40–165 reading/TOEFL；166–173、175–187
  comprehensive/general；188 writing/TOEFL；192 listening/TOEFL；194 reading/TOEFL。
- 生产只读副本验证：原库 `quick_check=ok`，194 本/18,410 词条/3,157 任务；迁移首跑创建
  四张 v2 表与旧表索引，二次运行文件 hash 不变。历史任务非空 goal 为 0；回填 listening 39、
  reading 127、comprehensive 21、writing 1、未映射 6，ID174 保持空；partial unique 首答约束存在。
- 真实资料审计覆盖 188 本映射词书/16,181 词条：15,979 条有安全 target 且至少一种 context 题；
  `example_fill/collocation_fill/meaning_choice/collocation_choice` 可生成数依次为
  13,470/13,879/15,975/12,280。所有 choice 均为 4 个唯一选项且唯一答案 ID，fill 目标残留为 0。
  ID188 为 727/922，195 条脏数据继续隔离；另有 ID194 的 6 条未批准斜杠表达和 ID35 的
  `0.75 m` 失败关闭。
- “今日复习”现为独立 session/claim/answer/settle/continue 闭环，最多 20 题，跨词书按错误优先、
  逾期程度和到期时间稳定排序；30/60 天从同一队列消费。新版任务入口及 queue API 的服务端
  preflight 会拦 active session；当日完整 settlement 形成 student+review_date clearance，
  当天第二个新版任务不重复强制，但剩余 due 仍显示在今日复习。`reviewDone=1` 仅 UX 防循环，
  不是放行凭证。生产数据库、部署、commit/push 和小程序上传均未执行。
- 主审补掉了首版未覆盖的边界：客户端 `limit=1` 不能缩小强制批次；首答立即、且只一次更新维度
  状态，答错的 +24h 从真实答题时刻计算；真实错词优先级与首次解锁的 stage 0 分开；听力书的
  meaning recall 保持“听音→中文”；首次作答有数据库唯一索引，结算用 active→settling 原子状态
  抢占并要求 queue token。跨午夜会以完成日形成 clearance，全部答完但尚未结算的 active session
  仍会显示在首页。
- 小程序自主复习页复用严格英文键盘，支持现库实际存在的数字词和 `fiancé`，不会用原生输入冒充
  strict；补齐 audio→中文、context target/翻译展示、从首个未答项恢复、全答后自动结算，以及
  多标签页按当前页面来源返回任务。preflight 与 queue 之间若发生竞态，queue 的 409 也会正确回到
  自主复习页，不会只显示“网络错误”。
- 在生产只读库副本的再副本上重新验证自主复习迁移：四张新表与首答 partial unique 索引存在，
  二次执行 SHA-256 不变，`PRAGMA quick_check=ok`，四表历史行数均为 0；生产原库未访问写路径。
- 当前最终验证：四维/自主复习 Python 41 项、legacy/dictation/小程序结构 Python 66 项，共
  107 项通过；3 个 Node 脚本通过（输入策略 6 个子测试）；`py_compile`、Python 3.10 grammar
  parse、相关 Ruff、JS 语法、JSON 与 `git diff --check` 通过。当前机器仍无独立 Python 3.10.12
  运行时；尚未做微信真机、生产接口、教师网页完整 POST 或并发压力测试。

## 2026-08-08 TOEFL v2 正式考试流程与倒计时对齐（已部署）

- 开发 worktree `/Users/zhouxin/.codex/worktrees/fe6e/studytracker`，分支
  `codex/toefl-mock-review`；实现提交 `10c805f6`、听力状态串行修复 `02cd395e` 已推送任务分支与 `main`。
- 新 attempt 固定按 Reading → Listening → Writing → Speaking 推进；旧 attempt 通过
  `flowVersion` 缺省兼容原 R/L/S/W 顺序，避免进行中的学生被换序。
- 每个 Module / 写作任务先显示说明页，说明与 Speaking 麦克风检查不计时；点击开始后服务端才启动
  权威时钟，运行中不能暂停。Reading 使用 18/9 分钟（OG 保留来源可核对的 20/9），Listening 使用
  18/9，Writing 使用 6/7/10，Speaking 使用 3/5。
- 到时后封闭当前整个阶段，不再逐题快速跳转；Listening 不能回退，音频自动连续播放一次，不显示原生
  暂停/拖动/倍速控件，音频结束后才显示题目；Speaking 在进入本科前检查麦克风。
- 浏览器已验证四科顺序、说明页不计时、开始后倒计时、Reading M1→M2、Listening 门禁、Writing
  6→7 分钟切换、Speaking 开始前麦克风门禁。生产浏览器进一步验证正式 OGG 自动播放、播放中隐藏题目、
  播放结束后自动显示题目且短对话不泄露文字原句；顶部状态为“音频播放完毕”，无并发保存假警报。
- 定向 TOEFL 测试 73 passed；Node response queue 2 passed；变更文件 Ruff、JS syntax、diff check
  通过。全量 pytest 402 passed、2 failed，仍是既有缺失
  `static/listening/ielts10_test1_s1.mp3` 导致的静态音频 404。
- 最终 CI [31261278421](https://github.com/KB77GG/studytracker/actions/runs/31261278421)、任务分支 CI
  [31261069712](https://github.com/KB77GG/studytracker/actions/runs/31261069712) 与部署
  [31261278408](https://github.com/KB77GG/studytracker/actions/runs/31261278408) 均成功。生产业务代码包含
  `02cd395e`，服务 active，5002 保持 1 worker / gthread / 6 threads，近五分钟无服务错误；六套官方
  definition 均为 R/L/W/S，P1–P5 计时 18/9、18/9、6/7/10、3/5，OG Reading 保留 20/9；正式听力
  OGG Range 返回 206。本次无数据库迁移。

## 2026-08-08 TOEFL v2 批改、复盘与 2026 评分边界（已部署）

- 实现提交 `0dd91fd2`、评分收紧 `3c51e96d`、迁移状态保护 `e27092eb` 已推送
  `codex/toefl-mock-review` 与 `main`。开发 worktree 为
  `/Users/zhouxin/.codex/worktrees/fe6e/studytracker`。
- 教师口语 Listen and Repeat / Take an Interview、写作 Write an Email / Write for an Academic Discussion 现固定为 ETS task-level 0–5 整数；服务端拒绝 4.5、6 和自定义满分，旧 `score_max` 列保留但服务端固定为 5。
- 新增 `services/toefl_rubrics.py` 的简洁中文锚点/关注项和 `rubric_code` / `rubric_version` 审计字段；SQLite 迁移幂等回填已知 rubric，未知 manual task 仍为 pending 且 rubric 为空。
- `/report` 保留旧 `objective.correct/auto_total/answered/accuracy`，新增 `practice_breakdown.by_subject`，按 definition/answer key 实际可判题数分开 Reading/Listening；OG 覆盖 R=50/L=47，P1 覆盖 R=40/L=34。Writing/20、Speaking/55 仅在人工评分齐全后显示，绝不生成 1–6 band。
- 学生完成页、历史摘要、复盘页已明确本站练习统计与 ETS 官方成绩的边界；教师页显示四类 2026 rubric 的短中文量表与审计标识。录音私有存储、Range、权限、发布/重开、乐观锁和旧字段兼容链路保持不变。
- 最终验证：全部 `tests/test_toefl*.py` 共 70 passed；变更文件 Ruff、JS syntax、Node 14 项、
  `git diff --check` 通过。全量 pytest 为 398 passed、2 failed，仍只是缺失既有
  `static/listening/ielts10_test1_s1.mp3` 导致的 404。生产库副本迁移连续两次通过；真实生产库已先备份为
  `app.db.bak-20260808-toefl-review-v1`（完整性 `ok`），再新增 6 个 attempt 字段与 8 个 response
  字段，迁移后完整性 `ok`，没有历史 response 需要回填。
- CI [31252331389](https://github.com/KB77GG/studytracker/actions/runs/31252331389)、任务分支 CI
  [31252329005](https://github.com/KB77GG/studytracker/actions/runs/31252329005) 与部署
  [31252331391](https://github.com/KB77GG/studytracker/actions/runs/31252331391) 均成功。生产业务代码包含
  `e27092eb`，服务 active，5002 保持 1 worker / gthread / 6 threads，近十分钟无应用错误。
  公网 `/toefl/mock` 和 OG 开考页均为 200；真实浏览器显示 9 套 / 965 题、OG 120 题、四科选择和麦克风门禁正常，控制台无 error/warn。生产尚无已交卷新版 attempt，因此未用真实学生数据执行“老师发布 → 学生查看”冒烟；该闭环已由本地权限/发布测试覆盖。

## 2026-08-07 TOEFL v2 教师批改与学生错题复盘（实现基线，已随上节部署）

- 本节记录部署前的实现基线；最终提交、测试、迁移和发布状态以上一节为准。
- 已新增新版 attempt/response 的 review 状态、版本、评分、反馈、reviewer 和发布时间字段；新增
  `scripts/migrate_toefl_mock_review.py`，使用外部环境运行：
  `/Users/zhouxin/Desktop/studytracker/.venv/bin/python scripts/migrate_toefl_mock_review.py --database /path/to/app.db`。
  脚本只做显式 SQLite `ALTER TABLE`/索引/状态回填，重复执行幂等；生产执行前应先备份 SQLite。
- 已新增独立 `services/toefl_mock_review.py` 与 TOEFL 蓝图内的教师列表/详情、草稿保存、乐观锁、发布/重新开放、
  学生历史/逐题复盘和受保护录音流；新版录音改存公共 `/uploads` 之外的 `private_uploads/toefl_mock/`，
  只保留内部相对 token，播放支持 Range、`private/no-store`，并校验 attempt 归属、真实路径边界、后缀/MIME 和大小。
  运维与保留策略见 `docs/TOEFL_MOCK_REVIEW_RUNBOOK.md`。
- 本地定向结果：`tests/test_toefl_mock_v2.py` 及新迁移/闭环用例通过；当前共 29 项定向通过（含原有 24 项回归）。
  全量 pytest 为 `393 passed, 2 failed`；2 个失败均是既有 `tests/test_static_audio_headers.py` 依赖缺失的
  `static/listening/ielts10_test1_s1.mp3` 返回 404，未修改该静态链路。本次未执行生产迁移、部署或浏览器真实账号 QA。
- 本次本地变更路径：`.gitignore`、`config.py`、`api/toefl_mock.py`、`models.py`、`services/toefl_mock_review.py`、
  `scripts/migrate_toefl_mock_review.py`、`templates/toefl/{attempt_history,teacher_attempts,review_detail}.html`、
  `static/css/toefl_mock.css`、`static/js/toefl_mock.js`、`templates/toefl/mock_index.html`、
  `docs/TOEFL_MOCK_REVIEW_RUNBOOK.md`，以及相关测试文件。

## 2026-08-07 ETS Official Practice / OG 六套 v2（已部署）

- 新增 `ets-practice-1` 至 `ets-practice-5` 与 `ets-og-chapter-6` 六套完整四科题包：
  P1–P5 各 97 题，OG 120 题，合计 605 个原子题、0 blocked；Reading、Listening、Writing、
  Speaking 均来自本地官方 PDF/答案/媒体，公开内容和私有答案继续分离。
- 新增确定性导入流水线 `scripts/build_toefl_official_v2.py` 及官方媒体/三科解析模块；支持
  P1–P5 与 OG 的不同版式、OG 无下划线填词、Build a Sentence 多词块与干扰项、OG 口语
  8/10/12 秒源计时。v2 runtime 兼容每个 Listening group 独立原音频，旧三套整段音频行为不变。
- 六套严格 `--require-release-ready` 全部通过；210 个新媒体文件（约 64.5 MB）本地逐项核对
  SHA-256/大小，并已先同步到生产 `static/toefl/v2/ets-*`。rsync checksum dry-run 无文件差异，
  抽查 OGG/MP3/MP4 的 5002 Range 请求均返回 206。
- 本地验证：TOEFL 定向 39 passed；全仓排除既有缺失静态音频 fixture 后 384 passed、7 subtests；
  完整运行仅有同一基线的 2 个 `tests/test_static_audio_headers.py` 404 失败。Ruff、JS syntax、
  Node response queue、`git diff --check` 均通过。
- 实现提交 `0ab9a0a6` 已推送任务分支和 `main`；CI
  [31184914430](https://github.com/KB77GG/studytracker/actions/runs/31184914430) 与部署
  [31184914554](https://github.com/KB77GG/studytracker/actions/runs/31184914554) 均成功。生产 HEAD
  为 `0ab9a0a6`、服务 active，5002 保持 `workers=1 / gthread / threads=6`。
- 生产验收：公网 `/toefl/mock` 为 200，真实浏览器显示 9 套 / 965 题、九张卡均为
  `published / 正式门禁：通过`；P1 开题页显示 97 题 / 9 phase / 四科选择 / 麦克风门禁，
  控制台无 error/warn。六个 definition 均为 200、release ready，题量与听力 group 数为
  `97×5 + 120` 和 `23×5 + 29`，每套 Speaking 都是 11 题。

## 2026-08-03 刷题页姓名绑定可查看模考历史（已部署）

- 修复 `/practice` 已通过姓名绑定、今日任务正常显示，但 `/api/practice/mock-exams` 仍返回
  `401 not_verified` 并把“我的模考”整块隐藏的问题。根因是模考复盘只接受正式账号 profile 绑定或
  当前单场 token，没有复用刷题页已有的 `practice_student_name` 轻量身份。
- 现在无需学生密码：匿名姓名绑定可查看唯一 active `StudentProfile` 下的全部模考；已登录但尚未直绑
  profile 的学生也可通过显式“切换账号 → 输入姓名”使用同一规则。正式账号直绑仍优先，教师/管理员
  不会走姓名绑定；同名的多个 active profile 一律拒绝猜测，避免串号。
- 新增姓名绑定历史、跨学生隔离、同名歧义拒绝、已登录未直绑后显式姓名绑定回退测试；模考相关
  48 项通过，Ruff 与 `git diff --check` 通过。提交 `9a503252` 已推送任务分支与 `main`；CI
  [30810970416](https://github.com/KB77GG/studytracker/actions/runs/30810970416) 与部署
  [30810970394](https://github.com/KB77GG/studytracker/actions/runs/30810970394) 均成功。
- 生产业务代码已包含 `9a503252`、服务 active，5002 保持 `workers=1 / gthread / threads=6`。使用真实已交卷学生的
  姓名绑定链路做不输出内容的冒烟：模考列表从 401 改为 200，返回 1 场已交卷记录，复盘详情为 200。

## 2026-08-03 网页模考教师批改与学生复盘闭环（已部署）

- 开发工作树：`/Users/zhouxin/.codex/worktrees/7691/studytracker`；任务分支
  `codex/mock-exam-review-web` 已推送，业务 HEAD `4f4fefd3` 已 fast-forward 到 `main`。实现基于
  `origin/main@f5a7b2c7`，并保留当时主线最新的
  `api/mock_exam_student.py`、`exam/_review_components.html`、`_review_assets.html`、答题状态隔离和 TOEFL 发布内容。
- 已实现教师写作批改草稿/发布、独立签名批改 capability、短期编辑 scope、乐观锁与排队式自动保存；发布后
  capability 只读，可由后台重新开放。学生 token 复盘和 profile/当前浏览器授权复盘共用同一 context/组件，草稿
  不可见，已发布反馈在现有 token 复盘页展示。学生原文只读。
- 已补登录学生绑定校验、匿名模考 session 授权、链接版本/过期/撤销隔离、统一 `no-store`/`no-referrer`/
  `noindex` 响应头，以及无 `app`/模型导入的自包含迁移脚本。匿名 session 绑定 access-token proof，
  不能只伪造 session id；生产 `SECRET_KEY` 从环境读取，session cookie 明确 HttpOnly/SameSite=Lax，Secure
  由 `SESSION_COOKIE_SECURE` 环境布尔值控制。迁移命令：
  `.venv/bin/python scripts/migrate_mock_exam_review.py --database /path/to/app.db`；运行前应先备份生产 SQLite。
- 后台 issue/revoke/reopen POST 要求 JSON；capability URL 使用配置的 HTTPS 或受限的
  `X-Forwarded-Proto`。页面同时保留桌面双栏与窄屏布局。
- 验证：目标 review/migration/config 用例 45 项通过；Jinja 9 个模板解析、变更文件 Ruff、Python 编译和
  `git diff --check` 通过。官方全量 unittest 共发现 354 项，其中 2 个既有静态音频 fixture 缺失导致 404，
  另有 1 个既有 TOEFL unittest 模块因环境未安装 pytest 无法导入；这三项与本任务无关。本地 test client
  覆盖桌面/窄屏模板结构、发布链路和权限隔离；CI
  [30757325387](https://github.com/KB77GG/studytracker/actions/runs/30757325387) 与部署
  [30757325373](https://github.com/KB77GG/studytracker/actions/runs/30757325373) 均成功。
- 生产发布前已将 `app.db` 备份为 `app.db.bak-20260802-mock-review` 并通过完整性检查；迁移首次唯一回填
  8 场历史会话，第二次为 0 变更，歧义/缺失均为 0。生产 `.env` 已配置随机 `SECRET_KEY`、
  `SESSION_COOKIE_SECURE=1`、`MOCK_REVIEW_PUBLIC_SCHEME=https`，因此旧网页会话需重新登录一次。
  生产 HEAD `4f4fefd3`、服务 active、5002 `/practice` 返回 200，gunicorn 保持
  `workers=1 / gthread / threads=6`；匿名 history 为 401，错误 capability 为 404 且隐私头完整。
  真实已交卷学生 token 复盘和无登录教师批改页均完成不输出学生内容的生产冒烟，测试教师链接已立即撤销。
  家长端本次未接入。未记录任何 token、Cookie、密钥或学生隐私。

## 2026-08-02 当前任务：模考复盘与答题状态隔离（已部署）

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
- 提交 `bdb76d57`、`efc0896f` 已推送任务分支与 `main`；CI `30740988787`、部署 `30740988779`
  成功。生产 HEAD `efc0896f`，服务 active/running，5002 返回 200；学生成绩页入口、Task 1 图表、
  错误 token 404 与 gunicorn `workers=1 / gthread / threads=6` 均已核验。
- 下一步仅剩真实浏览器业务验收：用两名测试学生同机同卷确认草稿隔离，并分别从成绩页进入本人复盘。

## 当前双工作树基线（2026-08-08）

| 项目 | 当前状态 |
|---|---|
| 仓库 | `git@github.com:KB77GG/studytracker.git` |
| 发布工作树 | `/Users/zhouxin/.codex/worktrees/9478/studytracker`；`codex/vocabulary-v2-release-20260809` 已基于 `origin/main@67927544`，精确 HEAD 以 `git log -1` 为准 |
| 主工作树 | `/Users/zhouxin/Desktop/studytracker`；已有其他任务的未提交/未跟踪文件，本次未覆盖或改写 |
| 远端 | 发布分支尚未 push；精确远端状态以接手时 `git fetch` 与 `git log -1` 为准 |
| 本次交接范围 | 四维词汇、自主长期复习、小组学习链、context_use、旧强化拼写有限纠错、登录页比例和发布门禁 |
| 后端生产 | 词汇 v2 尚未部署；仍须遵守 5002、workers=1、gthread、threads=6，并在部署前备份数据库 |
| 小程序 | 尚未上传、提审或发布；必须先于后端发布并确认线上可获取 |

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
