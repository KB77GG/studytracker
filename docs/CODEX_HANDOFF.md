# StudyTracker — Codex 跨账号 / 跨电脑开发交接

> 这是账号无关、滚动更新的“当前状态”，不是聊天记录或永久变更日志。
> 最近更新：2026-08-09（Asia/Shanghai）。

## 2026-08-09 词汇 v2 正式发布分支（最新 main，待小程序先发）

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
