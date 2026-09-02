# 工作日志（跨账号 / 跨任务 / 跨机器进度同步）

> 目的：更换 Codex 账号、任务或电脑后，AI agent / 人先读这里，30 秒接上进度。
> 约定：每个项目任务结束前先做交接审计；有实质进展或状态变化时**追加一条**（新条目放最上面），记“做了什么、现场状态、下一步、坑”，不记代码细节（看 git log/diff）。
> 注意：这里要记录 **git 之外的状态**（生产库操作、服务器上的手动步骤、外部服务状态），这些从 commit 历史里看不出来。

## 2026-09-02 `/tasks` 现场修复已上线

- 在唯一发布工作树 `/Users/zhouxin/.codex/worktrees/admin-option2-full-suite` 合并完成昨日任务独立滚动、显式管理 / 删除、学生中文姓名 / 拼音筛选候选三项现场修复；桌面脏旧工作树未触碰，`artifacts/` 只作本机 QA 证据且不会提交。
- 删除链路已加固为 staff-only 的安全软取消：网页 / 小程序共用服务，仅允许取消无任何学习 / 计时 / 提交 / 批改 / 外键历史的 pending 误布置任务；共享 PlanItem、审计与 409 冲突均覆盖。独立 `cancelled_at` tombstone 防止迟到进度写把任务复活，启动时 additive 增列 / 建索引。
- 发布前验证：定向 Python **52 passed**，全仓（忽略既有缺失音频资产测试）**655 passed + 72 subtests**，Node **9 passed**，CI 同款 unittest **68 passed**，拼写队列、Python / JS syntax、diff check 通过；两路独立删除 / 安全审阅均为 GO，双连接迟到写竞态复现也通过。生产只读预检 `quick_check=ok`、外键 0、共享 PlanItem 11 组。
- 昨日任务 1280×868 视觉对照已通过；学生候选因浏览器控制超时缺少新的 390×844 截图，`design-qa.md` 仍如实为 blocked，用户明确接受该证据缺口后授权发布。
- 业务提交 `5f9fedc2` 已推任务分支与 `main`；CI `33592609749`、任务分支 CI `33592601082`、部署 `33592609800` 均 success。生产 HEAD `5f9fedc2`、tracked 干净、服务 active、5002 / 1 worker / gthread / 6 threads、`NRestarts=0`；部署后 journal 无应用错误。SQLite `quick_check=ok`、外键 0，`cancelled_at` 列与索引已生效、取消行 0；未写生产业务 / 学生数据。内外 `/tasks` 未登录 302，任务 CSS / JS 哈希一致。小程序客户端未上传 / 提审 / 发布。

## 2026-09-02 `/tasks` 学生姓名 / 拼音筛选候选（仅本机）

- 修复主任务筛选“输入姓氏后只过滤行、不出现学生下拉”的断点：复用已有学生姓名 / 拼音搜索数据，新增可访问 combobox/listbox、最多 12 个候选、无匹配空态、触摸与完整键盘操作；点选填写完整姓名并立即筛选。输入拼音也会同步过滤任务行，历史未建档任务保留中文包含匹配。
- 移动候选使用 `32dvh` 高度上限、独立滚动和 44px 触摸项，保持方向 2 既有 Sage / 象牙视觉。临时加入两名“辛”姓合成学生和两条任务完成登录态路由 / 拼音合同检查，固定 ID 数据已精确清理，SQLite `quick_check=ok`。
- Node **7 passed**、Python **12 passed**、JS syntax / diff check 通过。内置预览无可控会话，Chrome 可列出本地任务页但无法接管 / 截图，故根 `design-qa.md` 最新结果为 blocked，待 `390×844` 补拍“辛”与 `xin` 展开态后完成同图比较。5088 合成数据预览运行中；本轮及上一批昨日任务 / 删除改动均未 commit、push、deploy，生产和小程序未触碰。

## 2026-09-02 `/tasks` 昨日任务滚动与删除入口修复（仅本机）

- 在 `/Users/zhouxin/.codex/worktrees/admin-option2-full-suite`、`codex/admin-option2-full-suite@852f4d82` 修复两个现场断点：昨日任务 panel 不再被 flex shrink + overflow hidden 裁切，列表成为独立可聚焦滚动区；每条昨日任务新增“管理 / 删除”，可准确过滤 / 翻页 / 选中主列表任务，右侧检查器在折叠区外显示危险态删除按钮。
- 删除仍复用既有权限 API 和不可恢复确认；新增请求失败恢复、中文无权限提示、成功后列表 / 昨日快照 / 计数 / 检查器同步，并从“更多操作”移除重复编辑 / 删除克隆。未改后端合同、题库、判分或生产数据。
- Chrome `1280×868` 合成数据验收：6 条昨日任务 list `278/476px`、`overflow-y:auto`，键盘滚动 `scrollTop 0→168`；drawer body `658/828px`，无横向溢出；6 个“管理 / 删除”均可见，首个入口准确聚焦右侧删除。对照图与截图在本机忽略目录 `artifacts/tasks-yesterday-delete-qa-20260902/`，`design-qa.md` 顶部为 passed。
- Node **6 passed**、Python **12 passed**、JS syntax 与 diff check 通过。4 条临时合成 QA 任务已精确清理、SQLite `quick_check=ok`；5088 合成数据预览已重新启动供用户检查。本轮未 commit / push / deploy，生产与小程序未触碰。下一步等待用户授权后提交、推送并部署。

## 2026-09-01 后台左上角 Logo 可见性修复已上线

- 用户提供的 `logo.PNG` 与仓库完整品牌图完全相同；实际缺陷不是文件丢失，而是共享后台 teal 图标 / teal 底色对比不足，以及入学测试页把带大白边的整图缩进 42px。两种壳层现统一使用透明品牌 mark，配米白底、描边和轻阴影；入学测试页同时修正为绝对静态路径。
- 业务提交 `f2a7c647` 已推送任务分支与 `main`；CI `33523054279`、部署 `33523054249` 均 success。生产 HEAD `f2a7c647`，服务 active，5002 / 1 worker / gthread / 6 threads，SQLite `quick_check=ok` / 外键 0，部署后无应用错误；未写生产业务数据，小程序未改 / 未发布。
- Node 结构测试 **5 passed**、diff check 通过；本机浏览器实测材料库和入学测试 Logo 均真实加载为 `238×210` 源图、`42×42` 显示并清晰可见。公网 CSS、HTML 和图标已核对。`artifacts/` 仍未跟踪、仅本机可见。

## 2026-09-01 方向 2 后台 12 个功能区已上线

- 独立工作树 `/Users/zhouxin/.codex/worktrees/admin-option2-full-suite`、分支 `codex/admin-option2-full-suite`；业务提交 `b05e15b4` 已推送任务分支与 `origin/main`。桌面旧 `main@6ded77d2` 脏工作树未触碰。统一深墨侧栏、暖象牙 / Sage 页头、搜索和列表 / 检查器框架已覆盖材料、词汇、任务、批改、计划、刷题、配卷、入学测试、报表、阶段报告、批量添加、用户管理，并保留原业务入口。
- 任务页增加 1680px 超宽屏上限并恢复日期 / 筛选 / 行 / 检查器自然比例；题型专项仍并入统一布置抽屉，历史重复、安全检查、确认复训与原因控件可见。浏览器逐页发现并修复用户页模板 500 与刷题页重复题库链接；12 / 12 页面最终 200。
- 1440×1024 全页和任务 2048×872 浏览器验收通过；截图在本机忽略目录 `artifacts/admin-suite-v2-qa-20260901/`，`design-qa.md` 顶部为 `passed`。Python 除缺失既有音频资产的两项静态 header 测试外 **642 passed / 72 subtests**；定向 34 passed，Node 5 passed，JS syntax 与 diff check 通过。
- GitHub CI `33520182316` 与部署 `33520182295` 均 success；生产业务 HEAD `b05e15b4`，tracked 工作树干净，服务 active，5002 / 1 worker / gthread / 6 threads，部署后日志无应用错误。SQLite 只读 `quick_check=ok`、外键 0；未写生产业务数据。新 CSS / JS 公网哈希与本地、服务器一致；`/practice` / 入学邀请 200，需登录后台入口 302 到登录。截图 `artifacts/` 与合成本地 `app.db` 仍未跟踪、仅本机可见；小程序未改、未上传 / 提审 / 发布。下一步由管理员登录正式站做真实数据逐页冒烟。

## 2026-09-01 /tasks 统一任务布置与防重复已上线

- 用户授权发布后，从原 worktree 新建 `codex/unified-task-assignment`；业务提交 `e971556f` 与任务内 import/lint 清理 `6e82b264` 已推送该分支及 `main`。合成 `app.db` 和 16 MiB `artifacts/` 未入 Git。
- GitHub 最终 CI `33512536726` 的 test job 通过，部署 `33512536754` success；全仓 Ruff 仍只报既有迁移脚本 advisory，本任务定向 Ruff 已全通过。Sol 重跑 Python `46/55 passed`、Node `23/23`、语法与 diff check 全通过。
- 生产 HEAD `6e82b264`，service active，5002 / 1 worker / gthread / 6 threads；SQLite `quick_check=ok`、外键 0，幂等列与唯一索引已生效，无生产业务/学生数据写入。公网静态资产与本地/服务器哈希一致，部署后日志无应用错误。小程序未上传/提审/发布；下一步只观察现场反馈。

## 2026-09-01 /tasks 方向 2 · Sol 最终 exact Chrome 验收通过

- Sol 读取最终 diff 后用 Chrome 精确 `1440×1024` / `390×844` 复核，并将方向 2 目标与最终桌面实现置于同一张 `artifacts/sol-visual-qa-20260901/target-vs-sol-1440x1024-approved.png`。桌面核心工作区结束约 y=733；移动卡状态/进度/截止日期可见；三段抽屉 body/footer overlap=0；移动检查器、筛选/日期、编辑/更多与五来源切换通过，console error/warning `[]`，无横向溢出。
- 最终回归由 Sol 重跑：Python `40/46/55 passed`，Node `23/23`，py_compile、JS syntax、diff check 全通过；防重复、409、幂等、复训审计、专项矩阵和旧任务链路无回归。`design-qa.md` 顶部覆盖结论更新为 `final result: passed`。
- 现场仍为原 detached HEAD `846900c6` 与原脏 worktree；合成 `app.db` 和 5079 预览保留给用户体验。未 commit/push/deploy、未写生产数据库，全部成果仅本机可见；下一步等待用户决定是否统一提交与部署。

## 2026-09-01 `/tasks` 方向 2 第四轮视觉残留修复（Luna，待 Sol exact 复验）

- 只修最后两个视觉布局问题：抽屉改成 header / 独立滚动 body / 静态发布 footer 三段，footer 不再覆盖五来源或题型专项字段；桌面 inspector 高度压到 460–500px，保留内部滚动与两项并排主操作。业务防重复、409、幂等、复训审计未改。
- IAB 真实 `1280×720` 核对：题型专项 body `y=113..623`、`scrollHeight=1034`，footer `y=623..720` 且 static、无重叠；普通/题型专项五来源可见；正常工作区 `scrollWidth=1265`、inspector `460px`、页面源 console error/warning `[]`。截图与非 exact 目标对照在 `artifacts/tasks-workspace-qa-20260901/`。
- Python `40/46/55 passed`（152/254/1189 warnings，2/2/3 subtests），Node **23/23**，py_compile、node check、diff check 全通过。`design-qa.md` 保持 `final result: blocked`，等待 Sol 第四次 exact Chrome 复验；临时 5087/数据库收尾清理，5079/app.db 体验环境保留。

## 2026-09-01 /tasks 方向 2 第三轮视觉残留修复（Luna，待 Sol exact 复验）

- 在原 worktree detached HEAD `846900c65e3b094354c4ebb3d3367a7a918b0b0a` 仅修移动级联/抽屉 sticky CTA/桌面高度预算/检查器双主操作；新增最后加载 `static/tasks_workspace_final.css` 与结构断言，业务防重复链路未改。
- IAB 实测 1280×720：header 110.09、tabs 46、dates 44、filters 64、thead 32、首行 59、footer 40；状态/截止日期 visible、主操作同一行、scrollWidth 1265、页面源 console error/warning `[]`。证据 `artifacts/tasks-workspace-qa-20260901/tasks-workspace-1280x720-repair-final2.png`，目标同次组合图 `artifacts/tasks-workspace-qa-20260901/target-vs-current-repair-final2-1280qa.png`。
- Python `40/46/55 passed`（152/254/1189 warnings，2/2/3 subtests），Node `23/23`，py_compile、node check、diff check 通过。IAB 无 exact viewport，`design-qa.md` 保持 blocked，等待 Sol 用 Chrome 复验 1440/390；未 commit/push/deploy/生产写入。临时 5087/数据库已清理，用户 app.db/5079 保留未触碰。

## 2026-09-01 /tasks 方向 2 第二轮视觉返修（Luna，待 Sol exact viewport 复验）

- 在原 worktree detached HEAD `846900c65e3b094354c4ebb3d3367a7a918b0b0a` 继续返修，未 commit/push/deploy/写生产库；压缩侧栏、页头、日期/筛选和任务行，隐藏任务列表标题工具条，检查器改为内部信息滚动并固定状态/计时/两项主操作，移动状态/截止日期用高优先级规则恢复，抽屉元区改为稳定单列/双列且发布区不覆盖来源。
- IAB 仅实测 1280×720：scrollWidth `1265`，页面源 error/warning `[]`；编辑弹窗、五来源抽屉和检查器主操作可用。截图/同次目标对照在 `artifacts/tasks-workspace-qa-20260901/tasks-workspace-1280x720-repair-final.png`、`target-vs-current-repair-final-1280qa.png`。无 viewport capability，未伪造 1440/390，`design-qa.md` 保持 `final result: blocked` 等 Sol exact Chrome 复验。
- 最终自动化：Python `40/46/55 passed`（分别 152/254/1189 warnings，2/2/3 subtests）；Node 指定 `19/19`，含矩阵/工作台 `23/23`；py_compile、node check、diff check 全部通过。独立临时 5087/数据库已清理；用户保留 app.db/5079 未触碰。

## 2026-09-01 /tasks 方向 2 首屏返修（Luna，本轮待 Sol exact viewport 复验）

- 在既有脏 worktree `/Users/zhouxin/.codex/worktrees/c56a/studytracker`、detached HEAD `846900c65e3b094354c4ebb3d3367a7a918b0b0a` 继续工作，起始 `## HEAD (no branch)`，`HEAD...origin/main=0 0`；未 commit/push/deploy/写生产库。
- `/tasks` 首屏已改成日期标签/日期条/筛选/统一任务列表+右侧检查器，列表和检查器保留真实状态、计时、成绩、编辑、删除、批改、轨迹入口；正式 Sage mark/Font Awesome 导航、页头曲线、新 CSS/JS 工作区模块和结构测试已加入。原统一布置五来源、题型专项矩阵、防重复功能未改合同。
- 验证：指定五文件 Python **40 passed / 2 subtests**；六文件任务路由扩展 **46 passed / 2 subtests**；旧任务/学生端/听写回归 **55 passed / 3 subtests**；Node 指定三文件+matrix+workspace structure **23/23**；`py_compile`、`node --check`、`git diff --check` 通过，仅既有 SQLAlchemy 弃用警告。
- IAB 实际只能提供 `1280×720`：首屏顺序、抽屉、搜索、日期、分页、更多菜单可用，`document/body.scrollWidth=1265`，干净页 console error/warning `[]`；截图和目标并排图在 `artifacts/tasks-workspace-qa-20260901/`。IAB 无 viewport capability，故 `design-qa.md` 保持 `final result: blocked`，等待 Sol 用可控 Chrome 补 1440×1024 与 390×844。
- 独立临时 `/tmp/studytracker-qa.IUENjE`、端口 5087 和临时浏览器页已清理；用户保留的 `app.db` 与 5079 未触碰，仍仅本机可见。下一步只做 Sol exact viewport 视觉/overflow/console 复验，不要覆盖既有未提交成果。

## 2026-09-01 /tasks 方向 2 独立视觉复核未通过

- 使用 Luna 最终桌面截图与已确认目标图并排复核，确认用户判断成立：当前实现仍是旧任务页换肤/重排，未忠实还原目标的日期标签与逐日条、统一高密度任务列表、完整右侧检查器、图标化导航和页头品牌资产。
- 功能侧的统一任务入口、防重复矩阵、409 与幂等成果可保留；返修应集中于首屏信息架构和视觉 fidelity。覆盖性结论已写入 `design-qa.md`，对照图在 `artifacts/audit-tasks-design-20260901/01-target-vs-final-implementation.png`。
- 本轮未改业务代码、数据库或生产服务，未重新运行功能测试，未 commit/push/deploy；所有审计证据仍仅本机可见。

## 2026-09-01 /tasks 方向 2 统一任务入口与重复发布防护（仅本机）

### 本轮本地真实体验环境（仅本机，保留中）

- 为用户真实体验 `/tasks`，本工作树保留本地 `app.db` 合成数据：1 个体验管理员、3 个 Demo 学员、1 个 Demo 材料、6 条多来源/多状态任务。
- Flask 开发服务当前运行于 `http://127.0.0.1:5079`；Chrome 已登录本地体验管理员并停留在 `/tasks`，统一“布置新任务”抽屉已打开。
- 仅本机可见，可随时清理；未写生产数据库、未部署，未记录演示账号密码或任何令牌。

### P2 返修：409 内部码改为中文操作提示（仅本机）

- API 仍返回稳定 `duplicate_assignment_conflict`；前端映射为“检测到重复任务：请查看下方历史记录；如需复训，请二次确认并填写原因。”。题型专项与普通/材料/听力/阅读 409 都保留完整历史矩阵，不再把内部码展示给助教；未知错误仍保留通用发布失败文案。
- Chrome 真实 409 重做桌面/390px 证据：`artifacts/tasks-qtype-matrix-409-chrome-desktop-1440x1024.png`、`artifacts/tasks-qtype-matrix-409-chrome-mobile-390x844.png`；桌面 `body/document=1425`，移动 `body/document=375`、抽屉 `358`，页面源 console error/warning `[]`，Chrome 扩展自身日志不计入；四格完整，命中格“完全重复”，中文提示已核对。
- 定向 renderer **2 passed**；用户指定 Python **40 passed / 2 subtests**；用户指定 Node **19/19**；task routes **6 passed**；node syntax、diff check 通过。无数据库/schema 改动；本地服务已停止、`app.db*` 已清理，未 commit/push/deploy/写生产库，不宣称 Sol 已验收。

### Sol 独立最终复验（不覆盖此前 Luna 结果）

- Sol 独立源码审阅确认 P1/P2 已关闭：普通来源幂等/409、服务端事务重检、`retraining_mode` 不可绕过、token-free staff API、服务端审计来源、完整学生×题组矩阵、原子格 exact 语义、中文 409 提示。
- 工作树 `/Users/zhouxin/.codex/worktrees/c56a/studytracker`，detached HEAD `846900c65e3b094354c4ebb3d3367a7a918b0b0a`，`HEAD...origin/main=0 0`。Sol 自动化：指定五文件 Python **40 passed, 152 warnings, 2 subtests**；六文件扩展集合 **46 passed, 254 warnings, 2 subtests**；旧任务/学生端/听写回归 **55 passed, 1189 warnings, 3 subtests**；Node 三指定文件+matrix renderer **21/21**；`node --check`、`git diff --check` 通过，仅有既有 SQLAlchemy deprecation warnings。
- Sol 用独立新建/清理的本地合成数据完成 Chrome：1440×1024 列表+检查器首屏、scrollWidth `1425≤1440`、无孤立专项入口；专项两学生×两题组四格，真实 409 后仍完整，命中格“进行中/待批改 · 完全重复”、其余“未布置”；显式复训、普通单学生发布、旧入口重定向均通过。390×844 document/body `375`、drawer `358`，无溢出；中文 409 提示可见，页面源不含内部码，console error/warning `[]`（Chrome 扩展日志排除）。
- Sol 同一次视觉输入比较目标图与最终实现图，确认方向 2 的深墨侧栏、暖象牙工作区、Sage 主操作、列表+检查器、抽屉和移动响应式通过。临时 `app.db*` 已删除、5079 已停止；生产浏览器/生产数据/部署环境未验证。结论：**Sol 独立功能、自动化、浏览器、视觉验收通过**。截图：`artifacts/tasks-qtype-matrix-409-chrome-desktop-1440x1024.png`、`artifacts/tasks-qtype-matrix-409-chrome-mobile-390x844.png`。
- 当前改动仍仅本机可见，未 commit、未 push、未 deploy、未写生产数据库；本条为 Sol 独立复验，不覆盖此前 Luna 结果。

### P1 返修：question_type 学生 × 题组矩阵（仅本机）

- 在原有脏 worktree `/Users/zhouxin/.codex/worktrees/c56a/studytracker` 继续修复：duplicate history 响应新增请求题组全集与完整 `matrix_rows`，前端改用独立 renderer，预览与 409 都按学生×题组逐格展示，不再仅遍历历史 matches。
- 自动化新增两名学生×两题组四格服务/路由断言和 JS renderer 断言；实际验证“一格历史 + 三格未布置”、并发 409 后仍四格、token-free。用户指定 Python **40 passed / 2 subtests**，扩展集合 **46 passed / 2 subtests**，相关旧回归 **55 passed / 3 subtests**，用户指定 Node **19/19**，新增 renderer **1 passed**。
- 真实 Chromium 使用本地合成账号在 1440×1024 / 390×844 复验，四格可见、抽屉和页面无横向溢出、console error/warning 为空。证据图在 `artifacts/tasks-qtype-matrix-*.png`；目标图与桌面实现图同一次组合比较已更新 `design-qa.md`。
- 未 commit、push、deploy、写生产数据库；本机临时 `app.db` 仅用于验收，最终已停止服务并清理数据库文件。

### P2 返修：原子题组格显示完全重复（仅本机）

- 保持任务级 G1+G2 部分重叠语义不变；只把 question_type 的命中 `student × group` 矩阵行设为 `exact`，renderer 优先使用行字段并兼容旧响应回退到 match 字段。
- 浏览器重新验证预览与真实 409：G1（以及 409 中的 G2）显示“未开始 · 完全重复”，另外三格逐格显示“未布置”；返回只含 staff-safe 原任务入口，无 token。桌面 `body.scrollWidth=1425`，390px 页面 `document/body=375`、抽屉 `scrollWidth=358`，console error/warning `[]`。
- 重做并覆盖四张矩阵截图：`artifacts/tasks-qtype-matrix-desktop-1440x1024-final.png`、`artifacts/tasks-qtype-matrix-mobile-390x844-final.png`、`artifacts/tasks-qtype-matrix-409-desktop-1440x1024.png`、`artifacts/tasks-qtype-matrix-409-mobile-390x844.png`。目标图与最终 409 桌面实现图已在同一次视觉输入中组合复核。
- 最终命令：用户指定 Python **40 passed / 2 subtests**；扩展任务路由 **26 passed**；相关旧回归 **55 passed / 3 subtests**；用户指定 Node **19/19**；矩阵 renderer **1 passed**；py_compile、node syntax、diff check 全部通过。未 commit、push、deploy、写生产库；不要宣称 Sol 已验收。

- 工作树 `/Users/zhouxin/.codex/worktrees/c56a/studytracker` 为 detached HEAD `846900c6`；起始状态为 `## HEAD (no branch)`，远端 `origin/main`，`HEAD...origin/main=0 0`。本轮没有 commit、push、deploy 或生产数据库写入。
- `/tasks` 现为方向 2 工作台：日期窗口/筛选、任务列表和右侧检查器首屏可见；统计、Recent、Top、备忘录仍保留。布置抽屉合并普通、材料、Listening、Reading、题型专项，普通来源单学生，专项支持多学生；旧专项入口安全重定向。
- 新 service 负责稳定资源身份、批量历史查询、学生×单位/题组矩阵、完全/部分重复、409 冲突详情和审计。统一识别 snapshot group IDs、Listening Section/题号、Reading Passage/题号、材料题号/范围、听写/口语序号范围；普通文字无法可靠判断时不显示“未布置”。
- 所有 staff 发布响应 token-free；统一表单首提生成并复用幂等 key，旧客户端有确定性 fallback；后端事务复核、整批原子、SQLite writer lock 和唯一索引保护双击/重试/并发。完全重复默认阻止，完成/部分重复需要确认+原因；合法错题 repush 验证来源、拒绝空 wrong groups，并写 actor/reason/source 审计。
- 自动化：原任务书 Python 精确命令 `38 passed, 2 subtests passed`；含新增 `tests/test_task_assignment_routes.py` 的扩展集合 `44 passed, 2 subtests passed`；Node `19/19 passed`；py_compile、diff check 通过。具体命令和结果已写入 `docs/CODEX_HANDOFF.md`。
- 真实 Chromium `127.0.0.1:5079` 已验收 1440×1024 / 390×844、专项矩阵、Listening Section、Reading Passage、材料题号、听写交叉范围、409 回显、显式复训、更多菜单和旧入口；console error `[]`，两视口无横向溢出。目标图与最终实现图在同一次组合输入中复核；证据在未跟踪 `artifacts/tasks-*.png`，报告为根目录 `design-qa.md`，最终 `final result: passed`。
- 本机浏览器仅使用合成数据，本地服务器已停止，临时 `app.db` 已从工作树清理；这些内容只本机可见，不进入生产、fixture、日志或学生隐私。交接文件已同步更新，最终 Git 状态已复核。

## 2026-08-31 听力表格题题干缺失热修（网页已上线）

- 在独立干净工作树 `/Users/zhouxin/.codex/worktrees/listening-form-stem-hotfix`、分支
  `codex/listening-form-stem-hotfix` 完成业务提交 `4520fd68`：空 `question.title` 改从 collect 的题号 marker 恢复完整原句，兼容
  同行左右 cell 与行末空白；已推送任务分支和 main，桌面旧 `main@6ded77d2` 的脏候选及其他用户改动均未触碰。
- 全听力/阅读表格题库扫描为 195 组 / 1,476 控件 / 230 个空逐题标题，0 个缺 source target，控件全部恰好一次；相关 Node
  **22/22 passed**；5 个原卷合法纯空列表项已逐一核对并固定成回归清单。正式音频根下全仓 Python 单次
  **623 passed / 72 subtests passed**，题库 gate PASS（84 Listening、128 在线 Reading、1 隔离 Reading、8,480 在线题、336 音频、
  48 图片）；JS syntax 与 diff check 通过。
- GitHub Actions `33321922334` success（37 秒）；生产 HEAD `4520fd68`、tracked clean，service active，5002 / 1 worker / gthread /
  6 threads，数据库 quick-check/外键正常，部署后无应用错误。公网三个代表页 200，剑20 T4S1 截图中的五题、剑19左右列表格和剑21
  T4S4 Q32 均已真实浏览器确认恢复，控制台 0 error；本地/生产/公网脚本哈希一致。未填写或提交答案、未创建任务、未写生产业务数据，
  无后端/schema/小程序改动；小程序未上传/提审/发布。下一步仅观察现场反馈。

## 2026-08-30 登录入口视觉改造（网页已上线）

- 从最新 `origin/main@01690d92` 建立干净发布工作树，保留桌面旧 `main` 的全部脏内容；业务提交 `f3e363aa` 已推送任务分支和 main。
  `/login` 与未验证 `/practices` 共用真实 Logo、生成楼梯图和响应式 49/51 品牌壳层；登录安全 `next`、课堂入口、姓名验证、浏览器进度
  与验证后 Practices 新导航均保留。
- 定向 unittest **14 passed**，部署工作流 Node gate 与 diff check 通过；本地及生产 1440×1024 / 390×844 浏览器验收无横向溢出，
  密码切换和两类错误状态正常，控制台无错误。截图在 `/tmp/studytracker-auth-release-qa/`，不提交 Git。
- GitHub Actions `33284599698` success；生产业务 HEAD `f3e363aa`、tracked clean、service active，5002 / 1 worker / gthread / 6 threads，
  公网 `/login`、`/practices` 和楼梯素材均已核验。未写生产数据库，未操作小程序；下一步只需观察真实用户首次加载与入口反馈。

## 2026-08-30 Practices 三项成果整合、导航与 39 题 Test 下架（网页已上线）

- 已审计全部分支/worktree/未提交成果并生成 `PARALLEL_WORK_INTEGRATION_REVIEW.md`；题型专项和 IELTS on Computer 成果均在当前
  `codex/practices-interaction-refactor@f8152ff0` 脏工作树中，本轮没有重复合并或覆盖它们。
- 新增统一的学生/staff/课堂/访客身份导航和两层返回契约，覆盖 Practices 首页、各目录、Test/Section/Passage、题型专项、任务、
  模考、提交/复盘与 Reading Study；登录 `next` 和显式返回参数只接受同源本地目标。桌面/390px 浏览器入口矩阵、浏览器后退和
  console 均通过。
- 用户明确授权暂时下架缺 Q40 的 `reading_jijing_83_test_95`。原 JSON 和历史记录解析保留；统一隔离清单让网页目录、助教网页/小程序
  选题和题型专项都不再枚举该 Test，并用源文件 SHA-256、目录残留和题数三道发布门禁防止误恢复。
- 全仓 `618 passed, 72 subtests passed`，相关 Node `18/18`，目标导航集 `21 passed, 17 subtests passed`，Writing 隔离回归
  `7 passed, 4 subtests passed`，JS syntax 与 diff check 通过。统一业务提交 `a31ac484` 已推送任务分支和 main；没有拆分三项成果。
- 发布前 SQLite 备份为 `backups/app.db.predeploy-a31ac484-20260830-0751.sqlite3`，SHA-256 `c5552508…f6e5`、quick-check ok。
  唯一一次部署 run `33281910942` success；生产 HEAD `a31ac484`、service active、5002/1 worker/gthread/6 threads，数据库 quick-check/
  外键正常且 additive attempt 表为 0 行。生产 gate PASS：84 Listening、128 在线 Reading、1 隔离 Reading、8,480 在线题、336 音频、
  48 图片；公网主要目录和三个代表题面均 200，机经 56 张卡、下架 ID 0，日志无应用错误。未写生产测试数据；小程序未上传/提审/发布。

## 2026-08-29 Reading 匹配题题干被压成竖排（仅本机）

- 用户在本地 task 9 发现 Q6 英文逐字竖排。浏览器计算布局确认数据完整，但 Reading 半屏内又做一层“选项库 + 题目”横向分栏：
  workspace 约 428px、row 约 190px，答案列约 176px，题干实际为 0px。
- `practice_shell.css` 现让 Reading 匹配题的共享选项库位于题目行上方，题目行改为约 254px 题干 + 160px 答案；同一任务复测 Q6
  正常三行显示，选项库、答案控件、清除答案和双栏滚动均保留。证据为
  `docs/evidence/question-type-practice-2026-08-29/reading-matching-prompt-width-fixed.png`，目录现为 56 张 PNG（约 10 MiB）。
- 静态清单确认 Reading 全部 136 个共享选项匹配题组 / 113 个 Passage 均走同一 `renderMatching` 与全局 Reading 修正规则；
  classification、通用 matching、features、headings、information、sentence endings 六类代表 Passage 均已真实打开，最小题干宽度
  统一为 254px，0 个仍为 0px。
- 定向 unittest `18 passed`，全仓 pytest `611 passed, 63 subtests passed`，相关 Node `15/15 pass`。本地 DB 因用户验收现为 9 个
  专项任务 / 8 个 attempt，最新 task 9 仍在 progress。改动未 commit/push/deploy，未写生产库、未操作小程序；仓库级发布继续受
  既有 39 题包阻断。

## 2026-08-29 全剑雅册数 / Test / 单篇目录（仅本机）

- 删除会把“全部剑雅”截成最前 N 篇的候选数量输入，新增按剑4—剑21、Test、Section/Passage 三级组织的安全目录；全部范围实测为
  18 册 / 72 套，Listening 287 个可练 Section、Reading 216 个可练 Passage。可直接筛到任一册，例如剑雅10阅读为 4 套 /
  12 个 Passage。
- 每个 Section/Passage 现在都有“点击选择此篇”、圆形选择标记和独立 `aria-pressed` 状态；选中剑雅21 Listening Section 1 为
  2 个完整题组 / 10 题，剑雅10 Reading Passage 2 为 2 个完整题组 / 13 题，未选内容不进任务。新增证据
  `student-all-cambridge-volumes.png`、`student-cambridge-catalog-single-passage.png`，目录现为 55 张 PNG（约 9.8 MiB）。
- 定向 unittest `17 passed`，全仓 pytest `610 passed, 63 subtests passed`，相关 Node `15/15 pass`。本地 5078 预览已重启到
  最新代码；DB 仍为 8 个专项任务 / 7 个 attempt，本轮没有创建新任务。改动未 commit/push/deploy，未写生产库、未操作小程序；
  仓库级发布仍受既有 39 题包阻断。

## 2026-08-29 题型专项支持选择单篇 Section / Passage（仅本机）

- 候选 Section/Passage 卡片现可点选，默认不选且开始按钮禁用；可只选一篇，也可继续组合多篇。创建任务时只提交所选卡片中的完整
  Question Group，不拆共享题干、选项库、文章或音频；助教/API 原有 `count` 行为与显式 `group_ids` 优先级保持兼容。
- 真实浏览器实测 Listening Section 1 选中后为 2 个完整题组 / 10 题，Reading Passage 1 为 3 个完整题组 / 13 题；选中卡有青色描边
  和勾选标记，未选卡不会进入任务。截图为
  `docs/evidence/question-type-practice-2026-08-29/student-single-passage-selected.png`，证据目录现为 53 张 PNG（约 9.7 MiB）。
- 定向 unittest `15 passed`，全仓 pytest `608 passed, 63 subtests passed`，相关 Node `15/15 pass`。本机 DB 仍为 8 个专项任务 /
  7 个 attempt，本轮没有新建任务。改动仍未 commit/push/deploy，未写生产库、未操作小程序；仓库级发布继续受既有 39 题包阻断。

## 2026-08-29 题型专项收拢为六个学生大类（仅本机）

- 按用户参考图把听力收拢为“全部、填空、单选、多选、地图、匹配”，阅读收拢为“全部、填空、单选、多选、匹配、判断”。
  内部 canonical type 未丢失，广义筛选、混合细型冻结快照、错题重练和同类新题仍按服务端门禁校验，旧快照/API 兼容。
- 学生页科目/题型改为横向标签并自动加载来源卡：听力地图题实测出现 6 个 Section / 32 题，阅读判断题实测出现 6 个 Passage /
  32 题；同一 Section/Passage 的多个完整题组会合并展示。截图新增
  `docs/evidence/question-type-practice-2026-08-29/student-reading-broad-types.png`，证据目录现为 52 张 PNG。
- 定向 unittest `14 passed`，全仓 pytest `607 passed, 63 subtests passed`，相关 Node `15/15 pass`。本机 DB 因用户继续验收现为
  1 个 QA 助教、1 个 QA 学生、8 个专项任务 / 7 个 attempt；为其已打开但原先 404 的两条听力任务补上两个只读 MP3 链接并验证
  HTTP 200，本地链接总数为 5。仍未 commit/push/deploy，未写生产库、未操作小程序；仓库级发布仍受既有 39 题包阻断。

## 2026-08-29 题型专项中文名称（仅本机）

- 学生端与助教端的科目、题型下拉、预览卡片、新任务标题、题面 badge 和结果页改为中文显示；canonical code/英文标签继续保留，
  不改变筛选和判分。事实/观点判断与四类 Reading 匹配题使用带区别提示的中文名，旧快照也能按 canonical code 显示中文。
- 题型 inventory/audit 已重建且统计仍为 1,271 组 / 6,240 题、1,260 可发布、11 人工复核、0 blocked。浏览器验证阅读下拉全部
  中文，并成功预览 2 个事实判断完整题组 / 10 题；新增截图为
  `docs/evidence/question-type-practice-2026-08-29/student-question-type-labels-zh.png`。
- 中文显示层定向 unittest `12 passed`；全仓 pytest `605 passed, 63 subtests passed`；相关 Node `15/15 pass`。本地预览仍在
  `127.0.0.1:5078`，本机 DB 现有 1 个 QA 助教、1 个 QA 学生、5 个专项任务 / 4 个 attempt。改动仍未 commit/push/deploy，
  未写生产库、未操作小程序；仓库级发布仍受既有 39 题包阻断。

## 2026-08-29 Question Group 题型专项完整通路（仅本机）

- 在 `/Users/zhouxin/.codex/worktrees/practices-interaction-refactor` 完成真实架构审计，并新增完整 Question Group 题型生成器、
  安全门禁、冻结快照、现有 Task/PlanItem 接入、学生自建、助教多选批量发布、服务端草稿/恢复/截止/判分、逐题结果和两种再推送。
  专项继续使用现有 Listening/Reading 正式题面和共享 renderer；提交前 public DOM 无答案泄露。
- `QUESTION_TYPE_INVENTORY.json` / `QUESTION_TYPE_AUDIT.html` 为 1,271 组 / 6,240 题；1,260 组可发布，11 组人工复核默认排除，
  0 组 blocked。浏览器真实跑完 17 Listening + 21 Reading 代表页和两套固定回归，38/38 DOM 门禁通过；完整助教→学生→复盘→
  再推送链路通过，50 张截图和矩阵保存在 `docs/evidence/question-type-practice-2026-08-29/`。
- 全仓最终为 `604 passed, 63 subtests passed`；专项 `11 passed, 2 subtests passed`，相关 Node `13/13`，目标 lint/compile/diff
  check 通过。仓库级全题库 gate 仍因既有 `reading_jijing_83_test_95.json` 只有 Q1–39 而返回非零；不能编造 Q40，所以发布仍
  NO-GO，下一步从可信合卷源修复并补真机/完整时长。
- 本地开发预览运行在 `127.0.0.1:5078`，浏览器已保留 `/practice` 和一条未提交专项样例；忽略的本机 DB 保留明确命名的
  1 个 QA 助教、1 个 QA 学生、4 个专项任务 / 3 个 attempt 供用户查看。上一阶段 5077、2 个 mock session/exam 和四个
  ielts17 临时链接已清理；当前 3 个只读 MP3 链接用于 Range 测试和固定回归。全部改动仅本机，未 commit/push/deploy，未写生产库，
  未操作小程序。

## 2026-08-29 IELTS 候选本机测试页已开启

- 这是上一阶段记录：曾在隔离 worktree 启动 `127.0.0.1:5077`，创建两条仅本地 Listening/Reading 预览会话，并用四个
  指向桌面主工作树现有音频的临时只读链接支持 Listening。浏览器确认音频预检为 4 Part / 25:19，Reading 60 分钟双栏
  和 40 题均正常；普通 Listening/Reading Practice 与 Intensive Listening 路由也均为 HTTP 200。
- 这些资源现已全部停止/删除，当前预览状态以上一节为准；这不是部署，候选仍未 commit/push/deploy。

## 2026-08-29 IELTS on Computer 四模式与正式模考候选（仅本机，NO-GO）

- 在 `/Users/zhouxin/.codex/worktrees/practices-interaction-refactor`、`codex/practices-interaction-refactor@f8152ff0`
  继续未提交的 Practices 重构；桌面旧 `main@6ded77d2` 的脏改动未覆盖，只读复用其本机 MP3。
- 建立官方体验基准和 Simulation / Practice / Intensive Listening / Review 能力矩阵。Simulation 新增全媒体预检、单一锁定
  audio、服务端 deadline/刷新恢复/2 分钟检查、服务端草稿，以及答案/解析/Transcript 的 payload 与 DOM 双重隔离；
  Reading 改为考试态 50/50 双栏并修复 type 8 completion 误判为 matching。
- 全库 gate 扫描 84 套 Listening、129 套 Reading、8,519 题、336 个有效音频、48 张图片；唯一 P0 为
  `reading_jijing_83_test_95.json` 只有 Q1–39。缺失题不能编造，因此总判定 NO-GO；详见
  `docs/IELTS_EXPERIENCE_ACCEPTANCE.md`。
- 挂接桌面已有未版本化 MP3 夹具后，全仓 `593 passed, 61 subtests passed`；Node 新专项 `15/15`，目标 Ruff、JS syntax、
  diff check 通过。Chromium 六张证据图已纳入 `docs/evidence/ielts-experience-2026-08-28/`；华为真机及 Listening/Reading
  完整时长流程仍未验证。
- QA 的 4 条本地模考 session、开发服务器和 5 个临时音频符号链接已清理。候选仍未 commit/push/deploy，未写生产库，
  未操作小程序。下一步先从可信合卷来源修复 39 题包并让 gate=0，再补真机和全流程，之后另请用户授权发布。

## 2026-08-27 网页端助教布置虾滑听力 / ZYZ 阅读（网页已上线）

- 在独立工作树 `/Users/zhouxin/.codex/worktrees/teacher-practice-jijing-options/studytracker`、分支
  `codex/teacher-practice-jijing-options`，从 `origin/main@378d4e83` 完成老师端新增“虾滑听力·刷题”和
  “ZYZ 阅读”来源；桌面旧 `main@6ded77d2` 及既有脏改动未触碰。业务提交为 `c09f2ee1`，生产部署提交为
  `4269c338`。
- 网页 `/tasks` 现明确提供虾滑 113 项和 ZYZ 57 个 Test；助教可创建/回填，学生网页 URL 与 ZYZ 选择项正常。一次性
  内存 DB 的真实助教 GET/POST 已通过，未写本机正式库。
- 网页/机经专项 `38 passed, 8 subtests passed`，全部 Node `44/44`，排除仓库长期缺失静态 MP3 夹具后的全仓 Python
  `560 passed, 48 subtests passed`，目标 lint/compile/diff check 通过。
- 两次 main push 均未生成 Actions run，故按用户部署授权执行受限脚本
  `ssh aliyun-server 'sudo /usr/local/sbin/deploy-studytracker'`，脚本成功更新到 `4269c338` 并重启服务。生产 tracked 干净，
  原有 17 个未跟踪备份/快照/调度库保留；service active，5002 / 1 worker / gthread / 6 threads，SQLite quick-check/外键
  正常，部署后应用错误 0。
- 生产选择器只读统计为 113 个虾滑 Part、57 个 ZYZ Test / 171 个 Passage；回环及公网两个样例题目页均 200，页面标识和
  本地/生产文件哈希一致。未写测试任务或学生业务数据；小程序兼容源码虽已提交，但固定发布目录未触碰，未上传、提审或发布。

## 2026-08-24 网页精听遗漏句收口（已上线）

- 干净发布工作树 `/private/tmp/studytracker-listening-completion-20260824`、分支
  `codex/listening-web-completion-20260824` 只修改网页精听播放器与契约测试，未夹带固定小程序目录的脏候选。
- 网页现会打开第一条缺句，末句后也会返回缺句；全部句子保存齐时明确说明后端已自动提交整项任务。反馈任务的只读诊断为
  57/58、缺第二句，并非单句已提交导致不能整项提交。
- Node `43 passed`，精听专项 `13 passed, 3 subtests passed`，全仓 Python（排除长期缺 MP3 fixture）
  `532 passed, 48 subtests passed`，Jinja 与 diff check 通过。
- 业务提交 `b974b04a` 已推送分支和 main；CI `32743783522` / `32743786121`、部署 `32743784037` 均 success。
  生产 HEAD 正确、service active、5002 / 1 worker / gthread / 6 threads、SQLite 正常、部署后错误 0；公网 200 且模板哈希匹配。
- 未写生产库，未代学生补句；小程序 Android 播放定位修复仍仅在桌面固定目录，尚未 commit/push/upload/review/publish。

## 2026-08-24 网页听力提交后高亮保留（已上线）

- 从最新 `origin/main@1c945a50` 建立独立工作树
  `/Users/zhouxin/.codex/worktrees/listening-highlight-persistence/studytracker`、分支
  `codex/listening-highlight-persistence`，未触碰桌面旧主工作树的既有脏改动。
- 根因是听力判分向高亮根内的 `.option-feedback` 写文字，改变全文指纹后 MutationObserver 无法从旧 key
  恢复高亮；现将该动态反馈排除出指纹，并新增契约测试。阅读 Passage、高亮 localStorage 结构、判分和后端均未改。
- 网页专项为 `25 passed, 8 subtests passed`，全部 Node 为 `42 pass`，JS 语法及 diff check 通过；真实 Chromium
  自动执行“高亮 → 注入判分反馈 → 重绘”后仍保留 `.ex-hl`。
- 业务提交 `66c935f0` 已推送发布分支和 main；CI `32741622722`、部署 `32741622780` success。生产为该业务
  HEAD、tracked 干净、service active，5002 / 1 worker / gthread / 6 threads，SQLite quick-check/外键正常，
  部署后应用错误 0；公网听力目录和脚本均为 200，脚本 SHA-256 与本次发布文件一致并含修复规则。
- 没有后端接口、数据库 schema/data 或小程序改动，未上传/提审/发布小程序；桌面旧主工作树既有脏改动未触碰。

## 2026-08-14 写作顶部科目导航补齐与层级优化（已上线）

- 用户反馈生产听力目录顶部缺少“写作”。提交 `fce9468e` 已为听力/阅读的真题与机经共 4 个目录补入写作链接，
  复用现有科目导航、Sage Path 品牌色和移动端规则；当前科目激活态及学习报告登录态规则保持不变。
- 专项 `11 passed, 8 subtests passed`，`git diff --check` 通过。CI `31814058995` 与部署 `31814059057`
  整体 success；公网听力/阅读目录均返回 200 且各有唯一 `/writing/` 科目链接。后续并行发布的 `88480851`
  线性包含修复，生产 HEAD 已为 `8848085`、tracked 干净、service active，5002 / 1 worker / gthread / 6 threads，
  部署后应用错误 0。
- 本跟进没有数据库写入，没有修改/上传/提审/发布小程序；学生刷新网页后即可在顶部切换到写作。
- 用户继续要求科目更大更清楚且不需要学习报告。提交 `0e921208` 已把共享导航调为桌面 16px / 移动端 15px、
  全项加粗、扩大最小宽度和 3px 激活线，并从听力/阅读真题与机经 4 个目录删除学习报告；六个同款页面统一只显示三科。
  CI `31815149885`、部署 `31815149801` 整体 success；生产 HEAD `0e92120`、service active、5002 / 1 worker /
  gthread / 6 threads、错误 0。公网 HTML 为 1 个写作链接 / 0 个学习报告，Chrome 1170×770 与 390×844 均无溢出；
  专项 `11 passed, 8 subtests passed`。没有数据库或小程序变更。

## 2026-08-14 IELTS 写作范文与打字训练网页模块上线

- 独立发布工作树 `/private/tmp/studytracker-ielts-writing-web`、分支 `codex/ielts-writing-web` 完成 40 道试点题：
  30 道大作文、10 道含原图小作文，每题有 6.0 / 6.5 / 7.0+ 三档完整范文、立场/总览、论点/特征、四/五段结构、
  每段功能与可复用表达。页面复用听力/阅读工作台及 Sage Path 品牌绿，桌面和真实 390px 视口验收通过。
- 新增网页专属 `/writing/` 蓝图和 `writing_typing_attempt` 表。学生打字记录由服务端计时并重算字数、WPM、全文准确率；
  草稿存在浏览器，完成接口校验归属且幂等。课堂/老师模式只在本页统计、不写学生表；生产验收后表仍为 0 行。
  未改小程序，未上传/提审/发布新小程序包。
- 业务提交 `587ab585` 已推送分支和 main；CI `31813362019`、部署 `31813362004` success。生产 HEAD 为该提交，
  service active，5002 / 1 worker / gthread / 6 threads，部署后应用错误 0；SQLite quick-check/外键正常。
  公网写作目录 200 且 40 张题卡，`/practice` 入口和 Task 1 原图正常。
- 专项 `12 passed`；全仓 `520 passed, 44 subtests passed, 2 failed`，仅存量缺失 MP3 fixture 的两个 404；
  目标 lint/compile/JS syntax/JSON/diff check 全通过。桌面主工作树的既有脏改动未覆盖，仍落后远端 9 个提交。
## 2026-08-14 精听正式训练方式（后端/网页已上线，小程序待上传）

- 在 `/Users/zhouxin/.codex/worktrees/2b72/studytracker`、`codex/listening-dictation-release`
  完成助教布置五种训练方式、服务端正式首答锁定、长句自动降档、首答后复盘/升档，以及网页/小程序学生端一致体验。
  历史 NULL 任务保持学生自选；旧小程序缺少新字段时走合法三档兼容，新小程序助教选择器由后端 capability 控制。
- 听辨核对改为完整播放并揭示原文后的幂等完成制，不计 0% 正确率；已开始任务不能改正式方式，教师明细显示实际档位或
  “已核对”。生产已补两个 nullable 兼容列，未改已有任务、答案或进度。
- 业务提交 `88480851` 已推送发布分支与 main；CI `31814253746`、部署 `31814253358` success。生产为该提交、
  service active、5002、1 worker、gthread、6 threads，部署后错误 0；SQLite quick-check/外键正常，公网精听页 200。
- 整合后全仓排除长期缺失静态 fixture 为 `531 passed, 48 subtests passed`，全部 Node `42 pass`，目标编译/静态检查通过。
  微信开发者工具已打开正确 worktree 的 `miniprogram` 并重新编译为 `Errors: 0 / Problems: 0`；本轮未点击上传、提审或
  发布，现有审核中旧包不含本功能，下一步由用户从当前工具窗口上传新包并做五档与兼容真机回归。

## 2026-08-14 完整功能小程序已上传（审核中，尚未发布）

- 用户于 22:20 CST 更正：完整包只是从正确目录上传并等待审核，尚未发布；此前“已发布”的说法无效。上传包包含精听升级
  以及电话/邮编逐字符发音相关客户端修复，平台版本号、上传时间和审核进度尚未独立读取，审核通过后还要确认执行发布。
- 后端仍为已验证的业务提交 `6635b320`，本次状态更正不触发后端重部署。后端兼容及逐字符音频已上线，学生当前可完全退出
  线上旧包后重进先测数字音频；新包客户端改动待审核通过并发布后做完整真机联合回归。
- 正式发布工作树新增未跟踪 `.tmp/product-audit-listening-modes-20260814/`（2 张审计截图，约 184 KiB）；来源不属于本次
  更正，已保留且未纳入提交。

## 2026-08-14 电话/邮编逐字符发音与完整小程序发布包（后端已上线，小程序待发布）

- 在精听发布工作树 `/Users/zhouxin/.codex/worktrees/2b72/studytracker` 线性合入数字热修，再以
  `6635b320` 完成 19 个电话/邮编/编号的逐字符发音、审计映射、后端音频 URL 兼容与客户端根目录音频解析；
  提交已推送发布分支和 `main`。规则为 `0 → oh`、数字/字母逐个读、重复数字不读 double/triple；日期、年份、
  价格、数量和普通门牌保持自然读法。
- 写生产库前新建 `app.db.bak-20260814-book196-digitwise-before`（85,270,528 bytes，SHA-256 见交接）；
  19 份 DashScope MP3 全部生成成功并单事务换绑。Whisper small/base 与阿里云 ASR 交叉核验不再按千/百万位读；
  19/19 公网接口 200，样例 Range 206，数据库 quick-check/外键正常。学生答案、进度、任务状态未改，旧缓存和两份
  数据库备份保留；生产机没有运行本地重模型。
- 额外发现旧包会把 `uploads/...` 错拼为 `/api/uploads/...`。后端现把 151/151 条绑定音频输出为带版本指纹的
  `/dictation/words/{id}/tts?v=...`，新客户端也补根目录资产解析。后端已经生效，学生完全退出练习/小程序再进入即可，
  不必等新包；当前打开页面仍持有旧队列/缓存，不能只反复点播放。
- 项目级 Python 为 `512 passed, 44 subtests passed`（继续只忽略仓库长期缺失的静态 MP3 fixture）；全部 Node
  `40 pass`，目标 lint/compile/diff check 通过。微信开发者工具确认正确 worktree，普通编译 `Errors: 0 / Problems: 0`，
  唯一 debugger warning 为工具 SharedArrayBuffer 弃用提示；官方 `wcc/wcsc` 为 `32 WXML + 33 WXSS` 全通过，
  另有 49 JS / 36 JSON 全通过。
- CI `31806798880`、部署 `31806798923` success。生产为 `6635b320`、service active、5002、1 worker、gthread、
  6 threads，数据库正常且部署后错误 0。临时远端脚本已清理。开发者工具仍打开
  `/Users/zhouxin/.codex/worktrees/2b72/studytracker/miniprogram`，该目录同时含精听与数字修复；未上传、提审或发布，
  下一步由用户从该目录手动发完整包并做真机联合回归。

## 2026-08-14 数字听写发音恢复（第一阶段；已由上节接续）

- 确认不是小程序未重进：数字表达缺音频，word-id 路由会返回 400/502，Android 又把明确 HTTP 失败放大为
  重复播放请求。来源站没有可直接导出的逐题原录音，因此按用户授权使用项目现有阿里云 DashScope TTS。
- 生产写库前保留 `/root/apps/studytracker/app.db.bak-20260814-book196-dashscope-before`；数字书 151 条已
  150 条新生成、1 条复用并全部绑定 `audio_us`。部署前后两次全量验证均为 151/151 个接口 200，当前 Range
  为 206；无缺文件，SQLite quick_check 正常、外键错误 0，学生答案/进度未改。临时远端脚本已删除，备份保留。
- 提交 `1222b2f0` 已推送发布分支和 main；CI `31797920336`、部署 `31797920393` 均 success。生产为
  `1222b2f0`、service active、5002、1 worker、gthread、6 threads，部署后应用错误计数 0。后端新增数字原文
  DashScope 优先和可复用回填脚本；小程序明确 4xx/5xx 后不再交给播放器重试。
- 专项 `18 passed`，全仓排除长期缺失的静态 MP3 fixture 后 `508 passed, 44 subtests passed`，CI 门禁
  68 tests OK，16 个 Node 测试文件、目标静态/语法/compile/diff check 通过。后端与生产数据已上线；
  小程序保护代码已 commit/push，但尚未上传/提审/发布。若个别号码需特定逐位读法，按词书序号定点重生。

## 2026-08-14 精听智能听写稳定升级（后端/网页已上线，小程序待发布）

- 独立 worktree `/Users/zhouxin/.codex/worktrees/2b72/studytracker`、detached `HEAD@6ded77d2`
  已形成网页/小程序精听发布候选：三档确定性挖空、旧/新坐标恢复、输入草稿、长答案、首答/订正、失败保存和
  挑战多余词均统一；服务端新增 canonical 重算与首答幂等，客户端伪造正确率无法落库。
- 网页时间/进度/±5 秒限制在当前句，真实播放 promise 和句尾 rAF 监视接管按钮与停播；小程序改为
  `onSeeked + 400ms fallback + playback token + 50ms boundary monitor`，切句/暂停不会被旧 timer 拉起播放。
  小程序汇总从可见 progress 重算，跨模式/切句草稿不丢，加载/失败状态可见。
- 自动化：全部 Node `40 pass`；API 定向 `4 passed, 3 subtests passed`；全仓 Python
  `504 passed, 44 subtests passed, 2 failed`，仅存量缺失且被忽略的 `ielts10_test1_s1.mp3` 使两个静态 Range
  测试 404。正式剑20 T1S1 HTTP/Range 为 200/206；16/16 个正式 XDF MP3 的 ffprobe 时长与 JSON 末句 end
  全部相差 0.00s。语法、compile、diff check 通过。
- 真实浏览器：T1S1 音频 `readyState=4`，第一句在 4.526825s 自动暂停；句2显示 00:00–00:08、快进限制在
  13.21s。标准档草稿跨模式保留，4/4=100%；挑战多输 EXTRA 显示“多余”且 95.5%；刷新后 3/45、86.2%
  与逐句数据一致，`restaurants` 完整显示。证据在主工作区未跟踪
  `.tmp/listening-release-qa-20260814/`。
- 业务提交 `18484d1e` 已推送发布分支和 `main`；分支CI `31766305566`、主分支CI `31766349645`、部署
  `31766349635` 均 success。生产 HEAD 为 `18484d1e`，service active，5002、单worker、gthread、6线程；
  数据库 quick_check=ok、外键错误0，重启后应用错误0。公网精听页/新脚本200且脚本哈希匹配，音频Range 206。
  没有生产数据库写入、JSON/MP3改动或小程序上传/提审/发布；用户将自行上传发布小程序。
  微信开发者工具已经登录并打开正确 worktree；真实编译发现并补齐 app.json 所列 5 个页面缺失的 page JSON，
  新增四件套门禁。模拟器隔离任务已验收输入出现、草稿跨模式、一次首答、权威 33.3% 总分与 1 绿 2 红一致；
  真实剑20音频可从第二句非零时间戳播放、切句取消旧播放，并在第一句 00:04 精确停止，运行异常为 0。
  验收注入和临时自动化依赖已清理，干净重编译 `Errors: 0, Warnings: 0`；官方 `wcc/wcsc` 仍为
  `32 WXML + 33 WXSS` 全通过。全部 Node 更新为 `40 pass`，API 定向仍为 `4 passed, 3 subtests passed`。
  尚未做手机真机、上传、提审或发布；之后只有在用户明确授权时才能提交、推送、部署和发布。
  收尾已关闭 `5062` 开发服务器和浏览器页，并删除验收用的临时音频 symlink；主工作区真实 MP3 未改动。

## 2026-08-13 剑20 T1S1 覆盖为45句纯对话版（已上线）

- 用户确认试点更好后，沿用 canonical ID `ielts20_test1_s1` 覆盖线上原58句资源；公开 XDF 45句与本地
  742词完全一致，从现有原 MP3 裁出两段对话并
  删除46.710秒看题/说明，生成279.840秒纯对话 MP3和对应连续时间轴。生成器、JSON及5个门禁测试已新增；
  覆盖前生产任务数/句结果数均为0，不会造成旧进度错位；本机和生产均保留日期化旧JSON/MP3备份。
- 小程序精听停播从 `end-0.05s` 改为精确 `end`。Whisper base 全轨逐词匹配98.652%，41个可核验内部句界
  均未提前截断当前句尾，最小尾部余量约0.200秒；拼接点两侧对话完整。本地页面/API/Range请求为
  200/200/206，任务结束时已停止临时开发服务器。
- 目标 Ruff/Black/compile、JS语法、全部Node测试通过；新增/目录定向 `6 passed`，项目级为
  `496 passed, 7 subtests passed`。业务提交 `9aadc152` 已 push；CI `31711801740`、部署
  `31711801774` success。生产API为45句、页面/API 200、音频206且哈希匹配，服务active、5002、gthread、
  单worker子进程正常；公网音频为 `no-cache`。小程序代码已入库但包尚未上传/提审/发布，旧包仍提前50ms停止，
  会立即使用新45句数据和音频；后续按真实使用反馈定点修正。复现性修正 `8b1c69dc` 及其CI
  `31712275524` / 部署 `31712275451` 也 success：覆盖后仍可从日期化原轨备份生成相同哈希MP3；生产仍为
  45句/279.84秒、workers=1/gthread/threads=6，部署后无应用错误。

## 2026-08-13 剑雅精听句尾越句时间戳诊断（只读）

- 全量对账 iDictation 本地原始 API 响应与 288 个 Cambridge 精听 Section：13,104 句的数量、
  英文文本和源 MP3 URL 均无差异；12,949 句时间直接保留原站值，导入只把毫秒换为秒并四舍五入到
  0.01s（最大改变 0.005s）。另 155 句为剑21四套 Section 1，此前已因原站整段偏移在
  `78a7721a` 重对齐修正。
- 原始时间轴的 12,816 个相邻边界有 307 个重叠、4,027 个间隔≤50ms，并存在少数明显回跳；
  因此用户听到的“上句尾词落到下句”可以是原站边界数据本身，不是本项目导入换算制造。
  原站登录后同一练习的当前 UI 是否用余量遮蔽缺陷尚未精确对比。
- 小程序现在会在 `end-0.05s` 暂停，可能削掉极短尾音，但不足以单独解释几个词。
  本轮未改业务代码/JSON/MP3/数据库，未 commit、push、部署或发布。下一步先收集 2–3 个精确句号复现，
  再决定定点修数据或做全库可审计重对齐。工作树为 `main@a3a5fedf`，与 `origin/main` 同步；
  既有未跟踪用户/其他任务内容未动。
- 对照用户提供的新东方 IELTS Cat 剑20 Test 1 Section 1：两边规范化后均为完全相同的 742 词；
  新东方 45 句、本地/iDictation 58 句，44 个新东方内部句界有 42 个落在相同词位。校正开场固定偏移和
  中间约 46.755 秒剪辑后，共同句界误差绝对值中位数仅 0.015–0.030 秒、最大 0.140 秒。
  新东方更顺主要因为使用 279.014 秒纯对话剪辑（本地原轨 435.571 秒）并减少 13 个切点，不是共同句界
  被大幅重新精修；其播放器也未加显式句尾缓冲。若试做同款，必须同步剪辑/重映射时间轴，不能直接抄秒数。

## 2026-08-12 听力 / 精听任务小程序空白（后端已上线，小程序待用户发布）

- 生产后台只读确认隐藏“学习目标”控件仍启用且默认 `reading`；昨日 5 条听力记录中 4 条干净、1 条待完成记录
  已误写 `reading`。小程序又先按 goal 进入词汇门禁，导致被污染的听力任务显示空白通用页；两个故障任务的
  网页题目分别正常加载 58 句和 10 题，资源与链接无缺失。
- 加入三层隔离：非词书任务不写 goal、API 不向非词书返回 stray goal、小程序必须同时有词书 ID + goal
  才走词汇页；表单隐藏字段同步禁用/清空。后端/API/网页已部署，可兼容已有脏任务且无需先改生产库；小程序
  防线等待用户从 `/Users/zhouxin/Desktop/studytracker/miniprogram` 手动上传/提审/发布。
- 全仓 `.venv/bin/python -m pytest -q` 为 `492 passed, 7 subtests passed`，全部 Node 测试、目标 JS 语法、
  Python compile 与 diff check 通过。生产 SSH 当前在密钥交换阶段被远端关闭，未能直查当前两条任务行，故明确
  保留“相同创建路径下的高置信度推断”边界。
- 业务提交 `db49c13c` 已 push 到 `main`；CI `31611257505` 强制 test 通过且整体 success，部署
  `31611257508` success，23:15:45 CST 重启服务。生产页刷新后隐藏 goal 已为 disabled + 空值，公网听力目录 200。
  本机生产 SSH 仍在握手阶段被关闭，未独立复核生产 HEAD/数据库/进程参数；没有主动写业务数据。小程序尚未
  上传/提审/发布，旧工作区内容仍在安全 stash，既有未跟踪文件未动。

## 2026-08-12 取消严格键盘与输入授权（后端已上线，小程序待发布）

- 同一发布工作树在整合最新 `main@bec2dd27` 后完成：五条单词作答链统一系统原生键盘，移除严格键盘/模式切换组件、
  网页 `/tasks` 授权面板和教师小程序授权入口；首答判分、纠正性重试、错词队列与间隔复习不变。
- 后端默认 native，旧 `strict` / `compatible` 提交继续接受且不再要求授权；历史授权表、记录、关联字段和兼容 API 保留，
  无迁移、无授权记录删除、无生产数据写入。未授权 compatible、撤销后 compatible、新 native 与旧 strict 均有回归覆盖。
- 全部 Node/小程序语法与 JSON、目标 Ruff/compile/diff check 通过；整合后项目级为
  `482 passed, 7 subtests passed`（继续忽略长期缺失静态音频 fixture）。业务提交 `51623206` 已推送分支与 `main`；
  CI `31575728750` / `31575728809` 和部署 `31575728757` 均 success。
- 生产为 `51623206`，15:52:00 CST 重启后 active，5002 / 1 worker / gthread / 6 threads 正常；
  `quick_check=ok`、外键错误 0、部署后应用错误 0。开发者工具已重新打开正确目录
  `/Users/zhouxin/.codex/worktrees/vocabulary-review-hotfix/studytracker/miniprogram`；下一步由用户上传、提审、发布并真机验证。

## 2026-08-12 词汇任务中途被复习打断 / 确认键无响应（后端已上线，小程序待发布）

- 只读核验生产服务器代码、Nginx/Gunicorn 日志及 SQLite：蒋雅诺任务 `3364` 在 `saving` 到期约 3 秒后
  下一次 queue 被 409 门禁打断，陈相予任务 `3337` 同样进入以 `incline` 开头的自主复习；两人复习均为
  active / 0 答，服务端没有收到 answer POST，原教师任务 flow 和数据均完整。张辰宇完成时没有到期维度，
  因而没有触发异常。确证的是“每次换题重跑复习到期检查”会中途打断；确认键内部状态分叉的精确微信运行时
  原因无法由服务端证明，已明确保留不确定性。
- 在独立工作树 `/Users/zhouxin/.codex/worktrees/vocabulary-review-hotfix/studytracker`、分支
  `codex/vocabulary-review-hotfix`、基线 `origin/main@79698f2b` 修复：复习门禁只阻止尚未创建学习流的新任务，
  已开始任务可持续/恢复；首页复习欠账不变。严格键盘以实际显示值决定确认，v2 页显示提交中状态并把 answer
  超时收紧为 15 秒可重试；新增真实时序后端回归和组件行为 Node 测试。
- 定向 `51 passed`；项目级为 `482 passed, 7 subtests passed`（继续忽略仓库长期缺失的静态音频 fixture）；
  全部 Node 测试、三个 JS 语法检查、目标 Ruff、diff check 通过。目标 Python 文件在基线就不符合 Black，
  本轮未批量重排存量代码。生产再次只读确认两人的 task flow 都是 active，因此后端发布后无需数据修复即可恢复。
- 业务提交 `1df19dfb` 已原子推送热修分支与 `main`；CI `31573492201`、部署 `31573492198` 均 success。
  生产实际运行该 HEAD，15:20:11 CST 重启后 active，5002 / 1 worker / gthread / 6 threads 正常；数据库
  `quick_check=ok`、外键无错误，部署后 10 分钟应用错误为 0。两人的 task flow 均 active，新门禁结果为 0，
  无需修改生产数据即可恢复原任务。
- 微信开发者工具已通过 CLI 打开正确项目
  `/Users/zhouxin/.codex/worktrees/vocabulary-review-hotfix/studytracker/miniprogram`，等待用户手动上传/提审/发布；
  后端已经生效，小程序确认键和 15 秒重试仍要等新包发布。发布后应真机覆盖拼写题、非拼写题、断网/超时重试和
  已开始任务跨到期点，并核验 answer POST；未真机验证前客户端闭环仍未完成。

## 2026-08-11 教师任务页昨日任务与再次布置（已上线）

- 在独立工作树 `/Users/zhouxin/.codex/worktrees/tasks-yesterday-repeat/studytracker`、分支
  `codex/tasks-yesterday-repeat` 完成 `/tasks` 表单增强：选中学生后在材料选择上方显示
  昨日任务，词书显示真实书名和精确词序；未完成/未提交任务可用“再次布置”回填今日表单，但不直接写库，老资源失效时拒绝部分回填。
- 三个定向 pytest 文件共 `16 passed`；目标 Ruff、Black check、Python compile、Jinja 完整渲染后的
  `node --check`、`git diff --check` 均通过。Chrome 静态宽屏目视核对通过，图在
  `/Users/zhouxin/.codex/visualizations/2026/08/11/019ff13b-61b4-7be2-a0bf-7505ec06606b/qa-yesterday-task-tall.png`。
- 发布前项目级 Python 回归为 `481 passed, 7 subtests passed`，部署 Node 门禁通过。业务提交
  `ecda60e1` 已推送任务分支和 `main`；CI `31505122657` 整体 success（存量 Ruff advisory 仍红，本轮目标文件通过），
  部署 `31505122726` success。生产为 `ecda60e1`、service active，5002 / 1 worker / gthread / 6 threads 正常，部署后无应用错误。
- Chrome 真实登录验收：蒋雅诺的 4 条已完成昨日任务正确显示且无快捷按钮；测试账号的 `wl 3-1`
  正确显示进行中、第 1–50 词与“再次布置”，点击后回填 `dictation-7` 和 1–50。未点“添加”，没有任务/数据写入；验收页已留在新 Chrome 标签供用户查看。
- 无 schema/数据变更，未改或发布小程序。桌面主工作树
  `/Users/zhouxin/Desktop/studytracker` 仍明显落后 `origin/main` 且带有其他已修改/未跟踪内容的
  `main@fd711f1c`，本轮未触碰。功能已上线；后续只需收集真实日常使用中的特殊历史任务回填缺口。

## 2026-08-10 词汇答后辅助记忆卡与结果按钮比例（小程序已发布，后端待部署）

- 在正确发布 worktree `/Users/zhouxin/.codex/worktrees/9478/studytracker` 完成答后辅助记忆卡：小组学习复用现有提交响应；
  自主复习仅在答后和已答刷新恢复时返回 `answer_feedback`，未答题面及同批未答项不携带资料。卡片显示词、音节/音标、核心义、
  搭配、双语例句、可选用法提醒和重播发音，切题会清空旧卡；无数据库迁移。
- 结果页的浅绿色空块确认来自严格键盘残留外壳和 safe-area。两个页面现仅在作答时显示键盘，结果态改为独立 `520rpx` 品牌绿 CTA；
  iPhone 15 Pro Max 对照确认空壳消失、按钮约占页面 70%、滚动可达。`design-qa.md` 为 `passed`，对照图在
  `/Users/zhouxin/.codex/visualizations/2026/08/10/studytracker-vocabulary-feedback/`。
- 全仓回归（忽略长期缺失静态音频 fixture）为 `475 passed, 7 subtests passed`；全部 Node、JS syntax、目标 Ruff、diff check 通过；
  微信开发者工具最终为 0 errors。用户已确认从正确 worktree 上传并发布本轮小程序，但截至 21:13 CST 的生产日志仍只见 `/83/`，
  尚无新客户端拉包证据；语义版本号/平台发布时间也未由 agent 独立读取。后端仍为 `26764e17`，本轮代码和交接尚未 commit/push/deploy。
- 用户随后明确授权提交、推送并部署后端。本轮后端仅答后追加 `answer_feedback`、无迁移，旧客户端与新前端/旧后端双向安全降级；
  下一步按发布门禁更新 `main`，核验 CI/deploy、生产 HEAD、5002、单 worker/gthread/6 threads、错误日志和答后/恢复契约，再做真实登录
  iPhone 验收。

## 2026-08-10 词汇 v2 真机音频 / 输入 / 品牌色热修（已发布并通过真机音频验收）

- `16.0.74` 真机确认新词汇页无声/不可靠自动播、中文与英文输入键盘混用、正常 UI 误用橙色。已在正确
  `/Users/zhouxin/.codex/worktrees/9478/studytracker` 发布 worktree 修复：iOS 静音键兼容 + 下载缓存 + `canplay` 后播放，熟悉和 audio
  切题自动播；听音中文统一为稳定选项，英文仍用严格键盘；两个词汇页恢复 `#087f77` 品牌绿和纯 CSS 播放图标。
- 后端为新题生成中文选项并给历史自主复习响应动态补选项，仍按中文标签判分，旧 `16.0.74` 可继续手输中文，因而后端可安全先发；
  当前冻结任务 3331 由新客户端从组内资料补选项，无需重建 flow 或改生产数据。
- 验证：专项 Python `78 passed`，全部 Node 通过，JS 语法与 diff check 通过；全仓为 `474 passed, 7 subtests passed, 2 failed`，
  两个失败仅因 worktree 缺既有 IELTS 静态 mp3 fixture。微信开发者工具确认正确 worktree、本轮文件均触发热编译，0 errors / 0 warnings。
- 生产任务 3331 当前组 8 个音频均为有效 48 kHz MP3；其中 6 个与有道词典真人美音文件逐字节一致，`abstract` 与
  `advertisements` 触发既有低质量门禁后使用 Kokoro `en-us` 回退。规范词形/去词性与单次发音配置均核对通过。
- 热修业务提交 `26764e17` 已推送发布分支和 `main`；CI `31373716673`、部署 `31373716678` 均 success。生产已运行该 HEAD，
  服务 active，5002 / 1 worker / gthread / 6 threads 正确；数据库 quick-check、外键、200/206 音频和启动后错误日志均正常。
  没有 schema 迁移或主动数据写入。
- 用户确认已从正确 worktree 发布约定为 `16.0.75` 的热修包；生产从 18:12:47 CST 起看到真实 iPhone 资源由 `/82/` 切到 `/83/`，
  43 个新包请求全部 200。任务 3331 的 summary/preflight/queue/submit 和 8 个 TTS 请求均成功，近 30 分钟无应用错误。微信平台
  版本详情受浏览器安全策略限制，agent 未绕过读取；用户随后在真实 iPhone 确认发音正常，物理出声门禁通过。服务端只读审计未修改
  文件、数据库或服务。
- 截图又确认 v2 `错题再测` 答后反馈只显示答案，未显示辅助记忆卡；资料本身齐全，learning 提交响应已有音标/核心义/搭配/例句/译文/
  用法备注，旧听写页也已有可复用卡片。建议下一轮只在提交后显示，learning 仅改前端；autonomous review 需答后/已答恢复接口增量，
  禁止未答队列携带会泄题的 enrichment。本增强尚未实现；本条 docs-only 更新只推送发布分支。

## 2026-08-10 正确小程序 16.0.74 已发布并通过真机验收

- 任务 `3331` 的生产数据和新后端队列正确；线上 iOS 客户端却未调用 preflight，直接用旧听写页解析新 group queue，因只读取
  `res.words` 而显示 0 词。根因是 `16.0.73` 从桌面旧主工作树 `main@fd711f1c` 上传，该目录没有 v2 路由；正确前端位于
  `/Users/zhouxin/.codex/worktrees/9478/studytracker/miniprogram`。
- 正确目录定向 Python `20 passed`，旧错词 Node 门禁、关键 JS 语法和 diff check 通过；开发者工具已确认正确项目路径并手动重编译为
  `Errors: 0`、`Problems: 0`。用户于 16:27:56 正式发布 `16.0.74`；iPhone 客户端由 `/81/` 切换到 `/82/`，原任务
  3331 的 summary、preflight、vocabulary queue、familiarity 全部 200，并已进入 active recall。数据库 quick-check、服务和日志正常。
- 发布事故已关闭，可恢复创建新词汇任务；任务 3331 保留。后端保持 `main@21398163`，无需重新部署。D+30/D+60 提醒已同步改以
  16.0.74 的发布时间为起点。

## 2026-08-10 词汇 v2 小程序与后端正式上线

- 用户确认小程序线上版本 `16.0.73` 于 10:56:02 发布；随后暂停新词汇任务创建，备份生产库为
  `/root/apps/studytracker/app.db.bak-20260810-vocabulary-v2`（`quick_check=ok`，SHA-256 见交接文档），再将
  `21398163` 快进推送到 `main`。CI `31351428148` 与部署 `31351428153` 均为 success，旧版错词无限回插门禁在两条
  流水线都通过。
- 生产 HEAD `21398163`、服务 active；5002 / 1 worker / gthread / 6 threads 保持不变。迁移后数据库完整性和外键检查正常，
  3,190 个历史任务中 0 个被升级为 v2；188 本词书目标映射正确，10 张 v2 表已创建且无初始化业务行。新 summary 路由返回
  预期未授权 401；重启后真实 Android 微信学生继续提交旧任务成功，兼容链路正常。可解除新词汇任务创建暂停，首个真实 v2
  任务建议小词量观察。
- 已创建 active 提醒 `d-30`：2026-09-09 10:56 检查 D+30 旧 UI 入口退场门禁，2026-10-09 10:56 检查 D+60
  后端兼容退场门禁；不满足指标则延期，不自动删除历史数据。业务代码已 commit/push/deploy；本条 docs-only 交接提交只推送
  到 `codex/vocabulary-v2-release-20260809`，不再次更新 `main` 或重启生产。

## 2026-08-09 词汇 v2 正式发布分支（历史准备记录）

- 发布分支 `codex/vocabulary-v2-release-20260809` 已将实现重放到最新 `origin/main@67927544`，人工合并交接冲突并保留主线
  TOEFL 事实；工作树为 `/Users/zhouxin/.codex/worktrees/9478/studytracker`。业务提交在本节前为 `ba8b214d`，精确 HEAD 看 Git。
- 重放后全部 Node 通过；零 deselect Python 为 `472 passed, 7 subtests passed`；微信开发者工具 0 errors / 0 code problems。
  模拟器登录态失效，真实接口/真机仍待发布阶段验收。
- 发布分支 `ba51085a` 已推送；CI `31318885765` 整体 success，强制 test 与旧错词门禁通过，lint 仍为存量 advisory。
  用户明确由本人完成小程序上传/提审/发布。确认线上可获取并告知实际版本/发布时间后，再暂停新词汇任务、备份生产库、更新
  main 触发后端部署和生产核验。D+30/D+60 提醒以实际小程序发布日期设置。

## 2026-08-09 旧强化拼写错词无限回插修复（发布门禁通过/待发布）

- 学生反馈已由代码与 50 词模拟确认：旧 `dictation/spell` 每次错答都按 gap=3 回插同一词且无上限；若 `n` 始终
  错、49 个新词均正确，`n` 在新词结束前出现 17 次，第 66 次作答后队列只剩 `n`，之后无限循环。不是固定 50 遍。
- 旧入口现已改为“主轮错词只追加一次纠错；纠错仍错放行并进入后续复习”，首答成绩不被覆盖；恢复历史错答也不会重复
  提交首答。新增 50 词 Node 门禁，持续答错词只出现 2 次、总计 51 次完成；门禁同时接入 CI 和生产 deploy 的 SSH 前置步骤。
- 定向测试 17 passed；全部 Node 测试通过；完整 Python 为 `458 passed, 7 subtests passed`；Ruff、语法、diff check 通过。
  微信开发者工具为 0 errors / 0 code problems；模拟器登录态已失效，真实接口/真机仍待发布阶段验收。
- 发布阻断已解除，下一步恢复“小程序先、后端后”流程。当前仍未 commit/push/写生产库/部署/上传/提审/发布。

## 2026-08-09 登录页返回按钮与标题比例修正（本地未提交）

- 第一版三列居中方案在整窗缩略图中误判，用户局部截图证明原生返回按钮仍过宽并遮挤“账号登录”；已撤回该方案。
  最终改为左右结构：原生 `mini` 返回按钮以 `132rpx` 的 width/min/max/flex-basis 强约束、高 `80rpx`，右侧标签不换行。
- 微信开发者工具在 iPhone 15 Pro Max 上重编译为 0 errors / 0 code problems；用户局部参考与修正版共同对照后，返回按钮
  已紧凑、“账号登录”完整可见；返回→欢迎页→再次登录交互通过。3 条提示均来自工具/基础库；真机 VoiceOver 尚未专项验证。
- 定向测试 `5 passed`；功能工作树零 deselect 回归为 `457 passed, 7 subtests passed`；目标 Ruff 和 diff check 通过。
  当前仍为 detached `e1f1b3fa`，33 个 tracked 改动条目、13 个 untracked 路径，全部仅本机可见；未 commit、push、
  写生产库、部署后端或上传/提审/发布小程序。

## 2026-08-09 context 填空中文辅助与题序核对（本地未提交）

- 补齐学习页和今日复习页的 context fill 中文辅助区：例句优先显示“句子翻译”；没有配套句译时诚实标为“目标词义”；
  搭配补词显示“目标词义”。连中文词义也缺失的资料失败关闭，不再生成无中文提示的填空题。
- 核对并保留分组/题序设计：reading/listening/writing/comprehensive 分别为 10/8/8/6 词一组；熟悉阶段按任务确定的
  词表顺序浏览，主动提取、语境辨析、语境产出分别稳定乱序并处理阶段边界重复，刷新可恢复但不沿用熟悉位置。
- 验证：定向 50 passed；功能工作树全量为 `456 passed, 7 subtests passed`，最新 `origin/main@67927544` 临时集成副本为
  `470 passed, 7 subtests passed`，均只 ignore 长期缺失静态音频 fixture 的测试；全部 Node 脚本、目标 Ruff 与 diff check 通过。
  微信开发者工具 Stable 2.01.2510290 重编译为 0 errors / 0 code problems，iPhone 5 模拟器中文辅助区布局可见。
- 临时 latest-main worktree 已清理；生产仍未部署，新接口 404 属预期。当前 detached `e1f1b3fa` 改动仅本机可见，未 commit、
  push、写生产库、部署、上传或提审；正式发布顺序仍为小程序先、后端后。

## 2026-08-09 词汇 v2 发布就绪复核（本地验证通过/等待发布授权）

- 修正两个测试自身缺陷后，当时功能工作树零 deselect 回归为 `454 passed, 7 subtests passed`，最新 `origin/main@67927544`
  临时集成副本为 `468 passed, 7 subtests passed`；后续翻译补丁后的最新数字见上方条目。仅 ignore 仓库长期缺失两个音频 fixture 的
  `test_static_audio_headers.py`。两个变更测试 Ruff 通过；既有 Node 11 项、编译、3.10 grammar、JS/JSON 与迁移幂等结果仍有效。
- 教师真实 `/tasks` POST 冒烟通过 ID188 默认 writing 与显式 reading override；临时文件 SQLite 双线程 CAS 连跑 10 轮，
  10 成功/10 预期冲突/0 重复推进。均未触及生产数据。
- 用户完成微信开发者工具登录后，功能 worktree 在 Stable 2.01.2510290 编译为 0 errors / 0 code problems；模拟器覆盖熟悉、
  主动提取、严格键盘、context 选择、自主复习、错答纠正，iPhone 5 320×568 无溢出。生产新接口尚未部署，UI 检查使用页面
  状态 mock；真实后端 E2E、真机、上传/提审仍待正式发布阶段。
- 兼容性核对确定只能“小程序先、后端后”：新版客户端可把旧后端 summary 404 安全降级并继续旧任务；旧客户端不能理解新后端
  为 v2 任务返回的 preflight/强制复习门禁。需先发布并确认新版可获取，在后端切换前暂停创建新词汇任务；再备份生产库、部署、
  核验 schema/映射计数/quick-check/5002/进程参数，最后做真实登录学生与真机冒烟。
- 当前仍是 detached `e1f1b3fa`，30 个 tracked 改动条目、13 个 untracked 路径；未 commit、push、写生产库、部署或发布。
  正式发布须经用户授权，在最新 main 上建 `codex/` 分支并人工合并两份交接文档冲突。详细事实与命令见
  `docs/CODEX_HANDOFF.md` 顶部。

## 2026-08-08 跨账号交接规则固化（本地未提交）

- 新增本机全局 `/Users/zhouxin/.codex/AGENTS.md` 规则：每个项目任务收尾必须检查交接，账号记忆不作为
  唯一事实源；要求记录 worktree/HEAD/脏状态、验证、部署、未完成项和可直接执行的下一步。
- 同步更新主工作树与 `9478/studytracker` 词汇功能工作树内的 `AGENTS.md`、`CLAUDE.md`、
  `docs/CODEX_HANDOFF.md` 和本日志。本轮没有改业务代码，两个工作树原有未提交内容均保留。
- 未 commit、push 或部署。同一 macOS 用户下的另一个 Codex 账号可立即读取这些本机文件；若换电脑，仍需在
  用户明确授权后提交并推送，不能把本地文档误报成远端已同步。

## 2026-08-08 词汇 v2 小组学习链（本地未提交/未发布）

- 在 `9478/studytracker` 保留上一阶段未提交改动，增量完成 opt-in 词汇任务的小组学习链服务、API、专页和测试；
  未 commit/push/deploy、未写生产数据库、未上传小程序。`vocabulary_goal=NULL` legacy 闭环未改路由语义。
- 服务端事实源固定分组、题目快照、阶段/题序、queue token、attempt id 和 CAS 版本；A–E 阶段可刷新恢复，熟悉不计
  mastery，context 同一 sense×dimension 只结算一次，产出缺失时显式降级或跳过并记录诊断，retry wrong 可完成但进入
  needs_review。前端新专页显示组号/阶段，旧 v2 入口和跨日/竞态错误按服务端状态跳转或刷新。
- 已验证：group+HTTP 20 项通过；词汇/听写/小程序相关 Python 128 项通过且 0 skipped；所有现有 Node 测试脚本通过；
  全仓 Python 427 项只有 2 个既有静态音频 fixture 404 失败。目标 Ruff、py_compile、Python 3.10 grammar、
  JSON/WXML 结构、Node `--check` 和 diff check 通过。
- 61MB 生产只读副本的再副本上，小组表迁移二次运行 hash 不变且 `quick_check=ok`；真实 ID188/922 词写作任务生成
  116 组（8 词/组、尾组 2 词）与 2,131 道冻结题，队列无答案字段，首次全书快照本机约 5.66 秒。生产库和原副本
  未写入，临时验收副本已移入系统废纸篓。
- 未验证/后续：没有独立 Python 3.10.12，未做真实 SQLite 文件双会话压力测试；未在微信开发者工具、真机窄屏、生产 API 或
  生产数据库上运行。当前工作树仍有大量既有用户未提交改动和新增未跟踪文件，不能据此声明已发布。

---

## 2026-08-08 TOEFL 2026 正式流程与倒计时对齐（已部署）

- 新模考顺序改为 Reading → Listening → Writing → Speaking，并为旧进行中 attempt 保留旧顺序兼容。
- 每阶段增加不计时说明页；服务端只在学生点击开始后启动权威倒计时，运行中不可暂停，到时封闭整个
  Module/任务。R 18/9（OG 20/9）、L 18/9、W 6/7/10、S 3/5。
- Listening 改为无原生控制条的单次自动连续播放、禁止返回，音频结束后才显示题目；Speaking 麦克风
  检查移到进入 Speaking 时执行。Writing 任务间不可返回。
- 浏览器已覆盖四科顺序、阶段说明、计时启动与跨阶段推进；定向 73 passed、Node 2 passed、Ruff、
  JS syntax、diff check 通过。全量 402 passed、2 个既有静态音频 fixture 404。
- 提交 `10c805f6`、`02cd395e` 已推送任务分支与 `main`；CI `31261278421`、任务分支 CI
  `31261069712`、部署 `31261278408` 成功。生产业务代码包含 `02cd395e`、服务 active、5002 仍为
  1 worker/gthread/6 threads，近五分钟无错误。
- 六套生产 definition 均为 R/L/W/S 和预期秒数；正式听力 OGG Range 206。生产浏览器确认音频自动播放、
  播放时隐藏题目、播完显示题目且状态保存无假警报。本次没有数据库迁移。

## 2026-08-08 TOEFL v2 教师批改、学生复盘与 2026 评分边界（已部署）

- 提交 `0dd91fd2`、`3c51e96d`、`e27092eb` 已推送任务分支与 `main`。教师批改、学生历史/复盘、私有录音鉴权播放、草稿/发布/重开和乐观锁闭环已上线。
- 已将四类口语/写作人工题收紧为服务端固定 0–5 整数，取消教师可编辑满分；新增四类 2026 rubric 的简洁中文锚点、关注项和 `rubric_code` / `rubric_version`，并补幂等 SQLite 迁移。未知 manual task 保持 pending，不写入未知 rubric。
- `/report` 保留旧 objective 字段，新增 `practice_breakdown.by_subject`：Reading/Listening 使用 definition/answer key 的实际 eligible_total，仅展示本站练习答对数、正确率和错题；OG 测 R=50/L=47，P1 测 R=40/L=34。Writing/20、Speaking/55 只在人工评分齐全后展示。
- 最终 TOEFL 测试 70 passed；变更文件 Ruff、JS syntax、Node 14 项、diff-check 通过。全量 pytest 398 passed、2 个既有音频 fixture 404。生产库先备份为 `app.db.bak-20260808-toefl-review-v1` 再迁移，迁移前后完整性均为 `ok`；生产没有历史 response 需要回填。
- CI `31252331389`、任务分支 CI `31252329005`、部署 `31252331391` 均成功。生产业务代码包含 `e27092eb`、服务 active、5002 保持 1 worker/gthread/6 threads；公网目录与 OG 开考页真实浏览器冒烟通过，9 套/965 题和设备门禁正常、控制台无错误。生产暂无已交卷新版 attempt，未生成测试学生数据。

## 2026-08-08 四维词汇掌握与 context_use v1（本地未提交/未发布）

- 在独立工作树 `9478/studytracker` 完成新任务 opt-in 的四维状态、长期复习队列、sense 归并、
  词书目标/课程体系回填、老师目标选择和小程序逐题模式；旧任务保持原链路。
- context_use v1 仅使用结构化资料生成例句挖空、搭配选择、句意词义选择、搭配补词；题面/答案分栏，
  服务端首答判分，选择题答后才返回纠错标签。听力题通过 word-id 音频/TTS，不在快照给目标词。
- 已用生产只读副本的再副本验证首迁/二迁：原库 194 本、18,410 词条、3,157 任务且
  `quick_check=ok`；goal/course 回填数量正确、历史任务不升级、二次 hash 不变，旧表索引和首答
  partial unique 已落库。生产库没有被修改。
- 全量映射资料审计为 188 本/16,181 词条，15,979 条可安全出 context 题；四题型生成数为
  13,470/13,879/15,975/12,280，choice 四项/唯一答案和 fill 零残留检查通过。ID188 仍有
  195/922 条需人工清洗，另有 7 条特殊表达失败关闭。
- 本轮补齐独立 Today review：四张 session/item/attempt/settlement 表、跨书最多 20 题、服务端
  题目快照与答案隔离、首答/领取/结算幂等、错误 +24h 与 1/3/7/14/30/60 天复习、首页入口、
  新版任务 mandatory preflight 和 daily clearance。active session 不能放行 queue，伪造
  `reviewDone=1` 也不能放行；settled 后当天第二个任务可进，剩余 due 保留。
- 主审进一步收紧：强制批次不能由客户端降到 1 题；首答立即更新状态并以答题时刻计算 +24h；
  错词和未启动 stage 0 分开排序；听力 meaning recall 保留音频提示；首答唯一索引、queue token、
  原子 settling 和跨午夜 clearance 已补齐。自主复习页改用严格键盘并支持数字/`é`，补 audio→中文、
  context 目标词、多标签返回与 queue 竞态跳转；全答未 settle 的会话不会从首页消失。
- 在生产只读副本的再副本上验证四张自主表和首答 partial unique：二次迁移 hash 不变、
  `quick_check=ok`、历史行数 0。四维/自主复习 Python 41 项，legacy/dictation/小程序结构 66 项，
  合计 107 项；3 个 Node 脚本、编译、3.10 grammar、Ruff、JSON 与 diff check 均通过。当前机器
  无独立 Python 3.10.12；未 commit、push、部署或上传小程序，未做教师网页完整 POST、微信真机、
  生产接口或并发压力验证；生产数据库没有修改。

## 2026-08-03 刷题页姓名绑定模考历史修复（已部署）

- 根因：刷题页姓名验证和今日任务使用 `practice_student_name`，新模考接口却只接受正式账号 profile 绑定或
  当前单场 token；接口 401 后前端会隐藏整块“我的模考”。生产库中的目标学生实际已有已交卷模考，数据未丢。
- 修复：匿名姓名绑定可读取唯一 active profile 的全部本人模考；已登录但尚未直绑 profile 的学生可显式切换姓名
  后按同一规则进入；正式账号直绑优先，教师/管理员不回退，同名 active profile 歧义拒绝。
- 模考相关 48 项测试、Ruff、diff-check 通过。提交 `9a503252` 已推送任务分支和 `main`；CI
  `30810970416`、部署 `30810970394` 均成功。
- 生产业务代码已包含 `9a503252`、服务 active、5002 与 1 worker/gthread/6 threads 未变；真实姓名绑定冒烟已从
  401 改为列表 200，返回本人已交卷记录，复盘详情 200。未记录学生内容、Cookie 或 token。

## 2026-08-03 网页模考教师批改与学生复盘闭环（已部署）

- 在 `codex/mock-exam-review-web` 上完成第一阶段网页闭环，并先 rebase 到
  `origin/main@f5a7b2c7`；保留主线学生逐题复盘组件、答题状态隔离和 TOEFL 发布内容。
- 教师端支持草稿、Task 1/2 四项评分、half-up 计算、修改稿、分题/三科点评、发布与重新开放；签名 capability
  与短期 scoped 编辑会话独立于学生 token。自动保存使用 revision + queued save/publish，发布失败可重试且不会卡死。
- 学生端 token 复盘与 `/practice` profile/当前模考浏览器授权入口复用同一 context；只有已发布教师反馈可见，原文只读。
  登录学生必须有绑定的 `StudentProfile.user_id`，匿名刚考完只由签名浏览器 session 锁定当前单场。
- 新增自包含、可提前运行的 SQLite 迁移：
  `.venv/bin/python scripts/migrate_mock_exam_review.py --database /path/to/app.db`。只按唯一 active profile 回填，
  deleted/歧义不猜，重复执行安全；生产操作仍需先备份数据库。匿名 session 额外绑定 access-token proof，
  `SECRET_KEY` 从环境读取，session cookie 为 HttpOnly/SameSite=Lax，Secure 由环境布尔值控制。
- 补齐后台 JSON POST、capability HTTPS scheme 和学生复盘隐私响应头。目标 review/migration/config 用例 45 项通过；
  Jinja、Ruff、Python 编译、diff-check 通过。官方全量 unittest 354 项中 2 个既有音频 fixture 404、1 个既有 TOEFL
  模块因环境没有 pytest 无法导入；CI `30757325387` 与部署 `30757325373` 均成功。
- 实现提交 `a41d79ee`、审查修复 `431a186a` / `f45f3520`、下拉契约修复 `4f4fefd3` 已推送任务分支和
  `main`。生产发布前备份 `app.db.bak-20260802-mock-review` 并通过完整性检查；迁移首次回填 8 场、第二次
  0 变更、无歧义或缺失。生产配置随机 `SECRET_KEY`、Secure cookie 与固定 HTTPS scheme；旧网页 session
  需重新登录一次。
- 生产 HEAD `4f4fefd3`，服务 active，5002 `/practice` 200，gunicorn 保持 1 worker/gthread/6 threads；
  学生 token 复盘与无登录教师批改页真实冒烟均通过，测试教师链接已撤销。家长端未接入；未记录任何
  token、Cookie、密钥或学生隐私。

## 2026-08-02 学生端模考逐题复盘入口（已部署）

- 新增 token 隔离的学生复盘路由 `/exam/<exam_id>/session/<token>/review`；只有整场状态为
  `submitted` 才加载题库和答案，未交卷会退回考试流程，错误 token 返回 404。
- 学生成绩页新增「查看逐题复盘」入口；学生复盘与教师后台复用同一套题干、答案、对应原文、全文、
  解析和写作图表组件，避免两端显示能力继续分叉。Task 1 图表也直接补到学生成绩页。
- 实现提交 `bdb76d57`、学生入口提交 `efc0896f` 已推送任务分支与 `main`；CI
  [30740988787](https://github.com/KB77GG/studytracker/actions/runs/30740988787) 与生产部署
  [30740988779](https://github.com/KB77GG/studytracker/actions/runs/30740988779) 成功。
- 验证：模考复盘相关定向 Python 34 passed，Ruff、全部 Node 与 `git diff --check` 通过；生产服务器
  HEAD `efc0896f`，`studytracker.service=active/running`，`127.0.0.1:5002/exam/8` 返回 200，学生成绩页
  已输出复盘入口与 Task 1 图表，错误 token 返回 404，图表静态文件返回 `200 image/png`；gunicorn 保持
  `workers=1 / gthread / threads=6`。

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
