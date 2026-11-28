# 网页刷题第二批导航已部署（2026-11-28）

用户授权后，第二批导航已提交、推送main并通过正式部署。生产业务HEAD为 `695f84d68d2d29657ee9526918ab0365e21eaefa`，2026-11-28 12:23:20 CST启动；只读后验43/43通过。分支与main同SHA CI均为overall success，三个业务作业全部成功，结果见下表。

本报告取代[初始补丁报告](../README.md)中的待浏览器/待授权状态；初始失败、旧补丁保留为历史证据，当前补丁和manifest均在本目录。

## 候选与发布状态

| 项目 | 已确认状态 |
| --- | --- |
| 实施工作树 | `/private/tmp/studytracker-practice-web-batch2-20261128` |
| 分支 | `codex/practice-web-batch2-20261128` |
| 开发基线 / 开发起点HEAD | `9c211ee807fa1084017cbf8e8a05c1c9fe95de77` |
| 本机候选 | 产品与测试已commit/push；发布证据与规范交接另做skip-ci文档同步，避免重复部署 |
| 最终产品 manifest / 补丁 | [source-manifest.json](source-manifest.json) 29 项、[product-manifest.json](product-manifest.json) 15 项，均记录逐文件 SHA256；[batch2.patch](batch2.patch) 为 161334 字节，临时 index 适用性检查通过 |
| 发布提交 | `695f84d68d2d29657ee9526918ab0365e21eaefa`（产品提交9bf0cf7a，随后695f84d6仅适配旧日期显示测试） |
| 推送 / main 状态 | 任务分支和main已快进至 `695f84d68d2d29657ee9526918ab0365e21eaefa`，未force push |
| 远端 CI | [分支CI46106789381](https://github.com/KB77GG/studytracker/actions/runs/46106789381) overall success，test/account-provisioning/task-planner均成功；[mainCI46107250772](https://github.com/KB77GG/studytracker/actions/runs/46107250772)同SHA overall success，三个业务作业成功。旧advisory lint失败继续披露 |
| 后端 / 网页部署 | [Deploy46107250763](https://github.com/KB77GG/studytracker/actions/runs/46107250763) success；12:23:20 CST服务启动，生产HEAD与发布提交相同 |
| 生产后验 | [production-postdeploy.json](production-postdeploy.json) **43/43通过**，15产品文件和公网practice_shell.js SHA全部匹配；[精确SSH命令](production-postdeploy-command.json) |
| 数据库 / 配置 / 小程序 | 无本次schema变更、人工生产学生记录写入或生产配置调整；既有部署链正常执行。词汇保持开启；无小程序上传/提审/发布 |

旧资料树 `/Users/zhouxin/Desktop/studytracker` 有既有业务改动，并非本候选工作树。规范交接已统一更新两树的 `docs/CODEX_HANDOFF.md` 与 `docs/WORKLOG.md`，不得把本机未提交结果写成远端或生产已有。

## 产品范围与独审修复

本次依照第二批 #6、#9、#12、#18：品牌与上下文返回分离，目录只保留一个返回入口；听读、机经、写作、母题、冲刺、题型专项与学生练习中心统一顶栏；来源导航保留多层父级，避免目录重访返回环路；精听保留身份确认、切换学生及原教师管理入口，移除重复任务和最近记录区及其重复请求。

独审额外发现并修复家长身份展示：共享头依据 `identity_mode` 选择身份名，家长未确认孩子时显示未确认身份，已确认时显示孩子，不误显示家长为学生。两个新增真实请求测试覆盖这两种状态，原学生、课堂与教师检查保留。详见 [independent-review.md](independent-review.md)。

没有修改判分、计时、保存接口及做题主体；未实施第三批的练习中心布局重排、题型配色、水印或 CDN 本地化。`app.py`、`models.py`、听读做题模板与精听播放器仍保持基线内容；`practice_shell.js` 的做题初始化及退出保护主体保持，最终候选静态范围检查 39 / 39 通过。

## 验证结果与证据

| 验证 | 结果 | 证据及边界 |
| --- | --- | --- |
| Python 3.13 定向回归 | **85 / 85 通过** | [py313.log](py313.log)、[python-commands.json](python-commands.json) |
| 原生 Python 3.10 定向回归 | **85 / 85 通过** | [py310.log](py310.log)；未使用 datetime 兼容别名 |
| 扩展冲刺 / 写作 / 模考 / 完整性测试 | **66 / 66 通过** | [extra-1.log](extra-1.log)、[extra-commands.json](extra-commands.json)；初轮 2 条旧顶栏字符串断言改为共享头结构断言，初轮失败保留在 [extra-first-1.log](extra-first-1.log) |
| Node 导航及既有功能 / 精听退出探针 | **207 / 207、9 / 9 通过** | 最终候选重跑 [extra-2.log](extra-2.log)、[extra-3.log](extra-3.log)，完整 argv 见 [extra-commands.json](extra-commands.json) |
| Chromium 完整流程 | **44 / 44 通过** | [browser/flows.json](browser/flows.json)，复用并增强原 `flows.js` |
| 目录截图 | **22 张** | `browser/`：11 个目录，1440 × 900 与 390 × 844；横向溢出断言通过 |
| 截图独审 | **8 张未见阻断问题** | 独审查看首轮中的练习中心、剑雅听力、精听、题型专项各两个宽度；不冒充全部 22 张独立复核 |
| 本机冲刺 fixture 自检 | **8 / 8 通过** | [serve-fixture-notes.json](serve-fixture-notes.json)，真实模板及目标页面 GET；额外阻断 socket 与 DNS，零调用 |
| 生产探针本机自检 | **通过** | [production-probe-selftest.json](production-probe-selftest.json)：12 个页面 / gate 检查、manifest 规则及无网络边界 |
| 生产发布后只读验收 | **43 / 43 通过** | [production-postdeploy.json](production-postdeploy.json)：本机回环与公网10目录结构、写作匿名门禁、健康、身份门禁、版本及SHA |
| 生产发布前只读预检 | **17 / 17 通过** | [production-preflight.json](production-preflight.json)，只说明发布前运行状态 |
| 最终 Ruff / 静态范围 / 补丁检查 | **通过 / 39 / 39 / 通过** | [scope-check.json](../scope-check.json)、[patch-check.json](patch-check.json)；补丁以基线临时 Git index 执行 `git apply --check --cached`，未改真实暂存区 |

Python runner 注入合成配置并创建临时 SQLite，不读取项目 `.env` 或 `app.db`，网络调用为 0。测试之间存在覆盖重叠，不把表中数量相加当作独立功能数。以上不是全仓测试，也不代替远端 CI。

浏览器 44 项包含姓名确认、3 条当天合成任务、各来源目录进入与页面返回 / 浏览器后退、冲刺多层返回、跨目录重访无环路、11 个目录的品牌 / 单返回 / 身份 / 标题 / 溢出、精听切换身份且无重复任务请求，以及合成教师后台与精听管理入口。浏览器仅访问本机 fixture，没有使用真实学生账号或提交成绩。

## 首轮失败与修复记录

1. 环境启动曾在沙箱内遇到 Chromium `TargetClosed`；初始补丁阶段另有本机 `bind` 被拒记录。这些是启动失败，不是一次完成的浏览器流程。取得本机监听及 Chromium 执行条件后才开始完整验收。
2. 第一次完整浏览器流程 [browser-first/flows.json](browser-first/flows.json) 为 **36 / 39 通过**。3 项失败分别为：身份确认后异步任务尚未渲染就统计，得到 0；剑雅听力测试组未展开导致入口不可见；隔离树缺少运行时冲刺资产，真实阅读热榜为 0 / 60 可练习，找不到入口。
3. 修复测试等待：身份表单隐藏后继续等待可见任务，再断言当天任务恰好 3 条；听力流程显式展开目标测试组，避免读取隐藏链接。私有 Flask GET 与首轮截图均确认原合成任务数据正确，未改产品或任务日期逻辑。
4. 冲刺采用下节的明确合成导航 fixture，不伪造真实热榜资产齐全。第二次完整浏览器流程为 **44 / 44 通过**；首轮受失败影响未完整执行的后续步骤得以运行，并纳入完整检查。没有另一次“第二轮流程失败”。

## 本机冲刺样例及环境边界

[serve_fixture.py](serve_fixture.py) 包装既有批 1 fixture，复用真实 Flask app、临时 SQLite、合成师生和任务；再复用 `tests/test_exam_sprint_routes.py:sprint_view`，仅在进程内替换阅读冲刺 view。它提供一条入口，指向仓库真实剑雅阅读路由 `/reading/test/ielts10_test1_reading?passage=1`，页面明确展示“本机合成导航样例：仅验证导航，不代表真实热榜”。听力冲刺仍使用真实 loader。

该方案验证冲刺来源、真实目录模板 / JS、真实阅读页面以及返回链，不验证当前热榜内容、排名、映射准确性或运行时资产完整性。没有复制生产数据，没有改产品、仓库 seed、运行时热榜状态或数据库模型。seed 仍为 2026-11-15；缺失运行时资产的原阅读目录 0 / 60 是环境事实，不因合成导航通过而消失。

明确未验收：生产登录后的真实师生旅程、真实热榜内容与音频可播放性、外部 CDN / 字体质量、Safari、系统 IME、原生浏览器缩放、微信及其他真机、长姓名的所有布局组合。浏览器拦截外部 origin 请求；部分本机 MP3 缺失，题型目录可能跳过缺音频条目。这些结果与导航通过分开记录，不将 Chromium 模拟窄视口称为真机验收。

## 可复现命令

以下在候选工作树执行。另一台电脑应使用已安装相同项目依赖的解释器、Playwright 和 Chromium 路径；不要指向生产或真实学生数据库。

```sh
cd /private/tmp/studytracker-practice-web-batch2-20261128
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-batch2-20261128/run_checks.py python
/Users/zhouxin/Desktop/studytracker/tmp/web-vocab-py310-20261126/bin/python docs/reviews/practice-web-batch2-20261128/run_checks.py python
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-batch2-20261128/run_checks.py node
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-batch2-20261128/verify_scope.py --baseline 9c211ee807fa1084017cbf8e8a05c1c9fe95de77
```

上述复现工具默认输出到上级 `validation/`；本次发布证据的实际 argv、退出码和日志在本目录 `*-commands.json`，最终发布应保留两者对应关系。扩展检查命令：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-batch1-20261126/run_tests.py \
  tests.test_exam_sprint_routes tests.test_writing_library_routes tests.test_writing_library_service \
  tests.test_mock_exam_runtime tests.test_mock_exam_runtime_routes \
  tests.test_mock_exam_review_workflow tests.test_exam_integrity_routes
```

终端 A 启动本机服务；已存在本轮 5116 服务时不要重复启动：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python \
  docs/reviews/practice-web-batch2-20261128/release/serve_fixture.py \
  /private/tmp/studytracker-practice-web-batch2-20261128 5116
```

终端 B 执行浏览器回归；将 `OUT` 改为新目录可保留既有发布证据：

```sh
NODE_PATH=/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules \
AUDIT_CHROMIUM=/Users/zhouxin/Library/Caches/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-mac-arm64/chrome-headless-shell \
AUDIT_TEACHER=1 AUDIT_SCREENSHOTS=1 BASE=http://127.0.0.1:5116 \
OUT=docs/reviews/practice-web-batch2-20261128/release/browser-recheck \
node docs/reviews/practice-web-audit-20261126/flows.js
```

## 生产预检与发布后验要求

2026-11-28 03:52:35 UTC 的只读预检确认生产 HEAD 为 `efeac80c468cc47a6347d6136b6736c1ddbd0996`、受跟踪文件干净，systemd active/running，运行时 worker 为 1。仓库 gunicorn 配置为 `127.0.0.1:5002`、workers=1、gthread、threads=6，loopback 与公网健康。配置值与运行时 worker 计数是两类证据，不把配置读取称为运行时逐线程审计。

登录 / 练习中心匿名 GET 为 200，任务 / 资料入口保持跳转登录。现有词汇功能保持开启：匿名任务页及 state 接口均返回 401 `identity_missing` 和 no-store，不暴露学生或 CSRF payload。本次没有读取或修改词汇开关，不得按旧默认关闭文档把它关闭。

[verify_production.py](verify_production.py) 仅使用标准库，读取固定 Git / systemd / proc 元数据、允许列表内产品文件与匿名 GET；不 import app / models，不读学生数据库、秘密或服务环境，不发送 POST，不记录 Cookie、姓名或 token。主 agent 已执行预检；后验须指定最终完整 SHA 与最终 15 产品文件 SHA256 manifest，再检查 loopback / 公网目录品牌、唯一返回、h1、身份 gate、服务健康及公网 JS 内容 SHA。写作匿名入口保留既有跳转，只读探针不声称验证其登录后页面。

生产后验通过：HEAD一致、tracked clean、active/running、NRestarts0，实际1worker；gthread/6threads/5002配置保持。10目录在回环及公网均满足单品牌/五主导航/唯一来源返回（中心无自返回）/h1/匿名身份；写作匿名门禁保持。15产品SHA及公网JS一致，词汇匿名page/state仍401 identity_missing/no-store。本轮5116已Ctrl+C停止，lsof无监听；来源不明5055未动。

## 补丁交给另一位 Codex

本目录 batch2.patch 取代上级目录历史补丁，适用于基线9c211ee8的独立树。已发布main上不要重复应用；直接fetch main并读取本报告及规范交接。离线审查可在基线独立树执行 `git apply --check /path/to/release/batch2.patch`、`git apply /path/to/release/batch2.patch`，再按上面的命令复验。补丁不包含滚动交接、原始日志或自身；本报告、source-manifest及验证证据与补丁一并传递。

## 首次远端 CI 及测试契约修正

首次分支CI [46105985596](https://github.com/KB77GG/studytracker/actions/runs/46105985596) 在9bf0cf7a上：test/task-planner通过，account-provisioning因一条精听旧任务区状态字符串断言失败；非阻断lint仍有存量失败。完整结果与失败日志保存在branch-ci-first.json / branch-ci-first-failures.log。没有据此推送main。

仅将 tests/test_task_date_gate_display_contract.py 的web任务状态展示断言移到现有练习中心 renderTaskList（后端status_label仍由workflow_label生成），并断言精听链接任务区且不再请求重复任务。其他日期门禁断言不动，15产品文件SHA未改变。独审确认语义保持；重跑同CI组合94/94、日期门禁pytest20/20、原生Python3.10静态契约5/5和Ruff通过，精确命令见ci-contract-fix-commands.json。最终源清单29项和补丁已刷新并再次独立index apply --check通过。

## 收尾同步

两次成功CI完整JSON见 [branch-ci.json](branch-ci.json) 与 [main-ci.json](main-ci.json)，部署见 [deploy.json](deploy.json)。既有非阻断lint日志保存在branch-ci-advisory-lint.log；本次所有改动Python文件定向Ruff通过。最终源/补丁SHA再次核对见 [release-source-check.json](release-source-check.json)。

发布证据及两份规范交接以单独 `[skip ci]` 文档提交同步任务分支和main，生产继续运行已验业务695f84d6；文档提交号用 `git log -1` 核对。实施树收尾应clean；旧资料树原8M/27顶层U业务保持，只有它的两份镜像交接仍仅本机。未进行小程序上传、提审或发布。
