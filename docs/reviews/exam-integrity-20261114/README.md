# 雅思模考诚信模式第一期：本机实现与验收

2026-11-14 开始，2026-11-15 完成本机验收，随后获用户授权仅提交并推送专用审查分支 **`codex/exam-integrity-review`**。完整实现已提交推送为 **`c653c3ab120cb76b69535e5f4090c3a23c9b654f`**，[实现提交 CI](https://github.com/KB77GG/studytracker/actions/runs/43657508962) **success**，三组测试任务通过。全仓 lint 为非阻断 failure；结果详见 `ci-review.json`。**未合并／推送 main、未部署。** 本任务未在生产建表，未访问生产核验；没有访问或写入生产学生数据、重启服务、改外部配置、发布小程序。11 月 15 日不因本任务部署任何版本。

## 工作树与发布边界

- 实施树 `/private/tmp/studytracker-exam-integrity-20261114`，原实现分支 `codex/exam-integrity-20261114`，新审查分支 `codex/exam-integrity-review`，创建时 HEAD／基线 `ecc06f23`（完整 SHA 见 `scope-audit.json`）；从已推送的计划分支 `origin/claude/dazzling-johnson-a16p7t` 新建，开工时 clean。
- 原计划 `docs/EXAM_INTEGRITY_PLAN.md` 已在 ecc06f23，本轮保持其原文，实施核对结论在本报告和手册。
- 主资料树 `/Users/zhouxin/Desktop/studytracker` 仍 `main@6ded77d24586327ad94e151e172ae4811b4a2eed`，原 7 modified／23 untracked 顶层入口保留；本任务只在该树增量更新两份交接，不复制业务代码。现有改动路径见 `main-worktree-status.txt`。
- 收尾观察本机 `origin/main` 已由并行任务更新到 `cb2610166d7654c81238f53c000e37eafa7e68e1`，含课堂同义替换 `2e82331a`；本实施树尚未合入。该观察不等同本任务核验生产部署状态。发布前必须重新 fetch 并整合漂移，不能从旧桌面 main 发布。
- 用户已明确授权把完整第一期及证据提交并仅推送 `codex/exam-integrity-review`。完整实现提交 `c653c3ab120cb76b69535e5f4090c3a23c9b654f` 的远端 CI 已成功，本报告随后以仅文档提交同步；最终 HEAD 及其 CI 以本分支 Git／Actions 为准。逐文件清单（55 文件）见 `REVIEW_FILES.md`。此前原始验收报告中的状态文件是提交前快照，不代表推送后的当前状态。仍无 main／部署／生产访问授权；日后若单独授权发布，也须先确认当天没有正在进行的模考。

## 实现范围

第一期雅思网页：三档开关、保守离开计次、阅读／写作锁定、听力仅警告、设备绑定和换机、豁免、紧急关闭、复制／粘贴拦截、水印、规则确认、可选 Wake Lock、手机教师面板、时间线和诚信摘要。设备指引 `/exam/guide` 与老师手册 `/exam/integrity-help` 同时交付，技术手册见 `docs/EXAM_INTEGRITY_RUNBOOK.md`。

- 默认 off：四个学生模板与 ecc06f23 渲染逐字节一致；浏览器完整考试没有 `exam_guard` 资源或诚信请求。
- 仅新增 3 个无外键模型／表，不改任何旧模型；为请求重排、解锁基准和区分尝试／实际阻断，内部状态字段比计划示意多。DDL 脚本与模型列、索引一致，`--dry-run` 不开库，不创建错误路径数据库。
- 学生不 DDL；策略和状态使用独立连接／Session。缺表、写入失败、JSON／网络／CSS／JS 异常放行，不触碰原请求 `db.session`。全局硬开关 `EXAM_INTEGRITY_DISABLED=1`。
- 旧草稿、计时、开考、交卷、判分、复盘逻辑均未改；`app.py` 完全未改。`verify_scope.py` 对 10 个关键旧文件逐字节比对，旧 models AST 去掉新 3 类后完全一致。
- 为 20 秒紧急恢复目标留出超时余量，正常可见页心跳为 **15 秒**，请求超时 4 秒；锁定／设备冲突等状态 5 秒轮询。关闭后停止上报并撤除独立 DOM；开启后既有无脚本页面需下一科前刷新，面板明确说明。
- monitor 规则卡不禁 Start、不遮罩、不绑定设备、不拦剪贴板。enforce 才要求确认规则。听力连设备冲突和失焦也只提示，不遮住音频操作。分屏未完成真机验证，按计划保守选项只记录。
- 原始随机设备 ID 在 POST 正文／状态 GET 的 `X-Exam-Integrity-Device` 请求头中传递，GET URL 不含原值；数据库只存 SHA-256，不存剪贴板或作文粘贴正文。

实现文件和 SHA 清单：`scope-audit.json`。现有文件仅 10 处允许入口（CI、蓝图注册、models、4 学生模板、3 管理模板）；新增模块／测试另列清单，不改旧巨型文件逻辑。

## 验证与证据

最终 **158 Python / 86 Node** 通过。新增 Python 83 项（45 service、24 routes、9 独立对抗、5 真实 app 全流程），新守卫 Node 33 项；其余为原模考、复盘、高亮、renderer、音频等相关回归。日志分别为 `python-tests.log`、`node-tests.log`。不是全仓测试；CI 已接入新测试，实现提交的三组远端测试 job 已通过（见顶部链接与 JSON）；全仓 advisory lint 未通过。审查提交前核对 27 个产品文件 SHA 与本机验收快照完全一致，业务代码未再修改，未重复运行无变化的测试。

在本实施树执行：

```sh
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_exam_integrity_service tests.test_exam_integrity_routes tests.test_exam_integrity_adversarial tests.test_exam_integrity_e2e tests.test_mock_exam_runtime tests.test_mock_exam_runtime_routes tests.test_mock_exam_review tests.test_mock_exam_review_workflow tests.test_mock_exam_student_review tests.test_mock_exam_template_isolation tests.test_selection_highlight_contract tests.test_practice_highlight_coordinates tests.test_migrate_mock_exam_review -q
node --test tests/test_exam_guard.js tests/test_practice_shell.js tests/test_mock_exam_review_frames.js tests/test_practice_renderers.js tests/test_mock_review_paper.js tests/test_simulation_audio.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check api/exam_integrity.py services/exam_integrity.py services/exam_integrity_rules.py scripts/create_exam_integrity_tables.py tests/test_exam_integrity_service.py tests/test_exam_integrity_routes.py tests/test_exam_integrity_adversarial.py tests/test_exam_integrity_e2e.py tests/exam_integrity_e2e_support.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m black --check api/exam_integrity.py services/exam_integrity.py services/exam_integrity_rules.py scripts/create_exam_integrity_tables.py tests/test_exam_integrity_service.py tests/test_exam_integrity_routes.py tests/test_exam_integrity_adversarial.py tests/test_exam_integrity_e2e.py tests/exam_integrity_e2e_support.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/exam-integrity-20261114/verify_scope.py
node --check static/js/exam_guard.js
git diff --check
```

上述定向 Ruff／Black、JS 语法与 diff 检查通过；`api/__init__.py` 全文件既有 I001 已与基线核对，未借机重排；models 只新增区检查。独立审计屏蔽 ML/PDF 重依赖后，真实 app E2E 仍 5/5，CI 使用现有轻依赖 job 足够启动。

本机 Chrome **157.0.8103.78**，独立 headless context，浏览器网络限制 loopback，数据库和学生均为临时合成数据；使用实际路由、模板、计时与判分。执行：

```sh
node docs/reviews/exam-integrity-20261114/browser-check.cjs
node docs/reviews/exam-integrity-20261114/browser-resilience.cjs
```

脚本默认使用主资料树 Python、系统 Chrome 和 `/private/tmp/exam-integrity-browser-tools/node_modules/playwright`；可通过 `PYTHON`、`CHROME`、`PLAYWRIGHT_MODULE` 覆盖。Playwright 临时工具由官方 npm registry 安装，不改项目依赖文件。分别监听 127.0.0.1:5098／5099，退出时关闭浏览器和测试服务；临时手动 5097 服务也已停止。

| 验收项 | 证据与范围 |
| --- | --- |
| off / monitor / enforce 各一完整登录→听力→阅读→写作→成绩→复盘 | `browser-results.json`，三模式成功、page error 0；off 诚信请求 0；结果截图 `*-result.png` |
| 规则确认／听力三次离开不锁／阅读锁定→老师解锁 | `enforce-rules.png`、`reading-locked.png`；guard 真实上报，但 visibility 事件由测试控制注入，不冒称真实切 App |
| 锁定到时仍自动交卷出分 | 缩短合成场次截止时间后刷新加载，真实旧计时器自动提交阅读；原答案保存／评分语义另由 E2E 验证 |
| 外部粘贴拦截、内部相同文本放行、monitor 不拦 | 浏览器 ClipboardEvent 决策 + Node 反例；不是 iPad 系统剪贴板或拖放真机证明 |
| 紧急关闭 | 最终运行约 **2.829 秒**撤除所有 guard DOM，随后写作交卷／复盘成功 |
| 手机监考面板 | `teacher-mobile.png`，390×844；侧栏隐藏、页面无横向溢出，紧急关闭按钮中心 `elementFromPoint` 命中自身，不只做 isVisible |
| 设备冲突→老师允许换机→新设备接管 | `browser-resilience-results.json`；两独立 context 真 localStorage，旧页 hello 不增加、旧页收到冲突，新设备恢复 |
| 考试中删除新 3 表 | 只在临时库执行，确认旧 session 表存在；锁定撤除，真实 draft PUT、阅读与写作交卷到成绩页；`resilience-tables-missing-result.png` |
| 水印不影响题目／高亮坐标 | off/enforce 5 处几何 <2 px，原坐标测试 7 项通过；原生鼠标拖选和高亮前后段落几何不变，答题点击、题号聚焦、待回看可用；`resilience-reading-highlight.png` |
| 笔记 | 不适用：基线模考页没有笔记编辑器（听力错因笔记仅刷题复盘），不能虚报新功能验收通过 |

开发中独立复核并已关闭：旧 visible 延迟到达误闭合新区间／重复计次、monitor／豁免粘贴误判高风险、未锁学生误点解锁导致阈值降为 1、允许换设备后旧页抢回、紧急关闭 20 秒加网络超时余量、手机侧栏遮挡。均有反例或浏览器证据。

早期浏览器工具无法稳定处理确认弹窗，后用计划允许的 Playwright 完成。脚本曾因测试题缺 id、导航查询参数、固定页脚点击位置及交卷后响应读取竞态失败，已修测试夹具／断言；失败不计入最终通过，产品原有流程没有为测试绕过或改写。高亮断言核对实际选区与所有高亮 span，兼容原高亮拆 span 的行为。

## 尚未验证／下一步

- 未做 iPad Safari、Mac Safari 或真实学生试考；锁屏、通知中心／横幅、Split View、侧拉、台前调度、输入法和系统剪贴板仍必须按手册真机清单验收。不能把控制注入的 visibility 或 headless Chrome 当成 OS 真机证据。
- 设备指引按 Apple／WebKit／SEB 官方资料修正：没有声称可关闭“词典查询”；Wake Lock 不保证始终成功；现代 SEB WKWebView 的 Config Key 需要 JS API。引用和日期在手册。
- SEB 专用配置、通用入口、打开考试按钮、require_seb 与强校验均属独立后续阶段，本期未实现。第二期异常作答／打字数据、讲题抽查单、托福接入未做。
- 当前无本机实施阻塞；本轮仅审查同步，完成分支 CI 后停止等待 Claude 意见。下一位先核 Git、scope SHA、完整清单与报告，独立复核第一期；不继续第二期，不合 main 或部署。未来发布需要另行明确授权、确认无模考，再核最新 main 漂移并整合验证。所有场次默认 off，内部试考、真机验收后第一场真实考试先 monitor，再决定 enforce。
- 未对生产、教师真实操作、线上负载、真实学生网络环境或微信 web-view 做验收；小程序未改且无需因这项网页功能重新发布。

## 审查提交说明

官方文档核对依据、尚待真机验证项目以及与计划的 10 项差异已集中写入 `docs/CODEX_HANDOFF.md` 顶部；原计划保持不变。只有 `codex/exam-integrity-review` 被授权推送。实现提交与本节所附远端 CI 结果的 SHA 一一对应；追加的文档提交也等待 CI 后停止等待审查，不再开展第二期。
