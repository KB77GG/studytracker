# `/tasks` 方向 2 · 本轮视觉返修 QA（2026-09-01）

## Sol 第四次精确视口独立验收：通过（2026-09-01）

### 同一视觉输入与精确证据

- 目标图：`/Users/zhouxin/.codex/generated_images/01a05850-a764-7672-8bbb-93aafacb13ce/exec-480d1dcf-5f1e-4b23-afce-fe89a5cca987.png`。
- Chrome CSS viewport `1440×1024` 实现图：`artifacts/sol-visual-qa-20260901/tasks-workspace-1440x1024-sol-approved.png`。
- 目标与最终实现同图并排：`artifacts/sol-visual-qa-20260901/target-vs-sol-1440x1024-approved.png`。目标图按等比例同画幅归一后与实现水平并排，未用缩放浏览器视口伪造结果。
- Chrome CSS viewport `390×844`：`tasks-workspace-390x844-sol-approved.png`、`task-assignment-drawer-390x844-sol-approved.png`、`task-assignment-qtype-390x844-sol-approved.png`、`task-inspector-390x844-sol-approved.png`，均在 `artifacts/sol-visual-qa-20260901/`。

### Sol 独立检查结果

- 桌面首屏结构与目标一致：176px 深墨侧栏、正式 Sage Path mark 与完整图标导航、`TASKS` 页头/说明/搜索/提醒/布置入口、周/月/年、七日日期条、单行筛选、统一任务列表及右侧检查器。统计、Recent、Top、备忘录和待审核区均留在主工作区之后，不再占默认核心首屏。
- 1440×1024 实测几何：header `110px`、tabs `46px`、日期条 `44px`、筛选 `64px`、表头 `32px`、首行 `59px`、分页 `40px`、检查器 `460px`；主工作区 `y=272..733`。列表内容结束后不再由检查器制造 200px 级空高，两项主操作在同一行可见。
- 桌面横向几何：`innerWidth=1440`，`document/body.scrollWidth=1425`；没有页面横向溢出。页面源 console error/warning 为 `[]`。
- 移动首屏在 390×844 内可见首张任务卡；首行 `task-status` 与 `task-deadline` 的 computed `display=block`，状态圆点、百分比、进度条和完整截止日期均可见；`document.scrollWidth=375`。
- 移动抽屉为真实三段布局：header `y=0..127`、独立滚动 body `y=127..623`（题型专项 `scrollHeight=1498 > clientHeight=496`）、静态 footer `y=623..844`，body/footer overlap=`0`。五种来源全部可见、普通与题型专项字段均可滚动，发布操作固定占位且不覆盖内容。
- 移动详情检查器显示任务标题/状态、来源、学生范围、计划/截止、证据、备注、时间线、状态/计时和两项主操作；点击任务卡可打开，关闭按钮可用。
- 交互抽查：搜索“Demo 学员 B”只显示 1 条；清空后日期 `2026-09-01` 显示 2 条，再次点击恢复 6 条；切换任务行会同步检查器；“调整任务”打开编辑弹窗并可取消；“更多操作”显示当前任务的打开、编辑、删除入口；统一抽屉可切换题型专项。
- 最终自动化由 Sol 在最终文件状态重新运行：指定 Python 五文件 `40 passed, 152 warnings, 2 subtests passed`；扩展六文件 `46 passed, 254 warnings, 2 subtests passed`；旧任务/学生端/听写 `55 passed, 1189 warnings, 3 subtests passed`；Node `23/23 passed`；Python/JS syntax 与 `git diff --check` 全部通过。warnings 仅为既有 SQLAlchemy datetime/Query deprecation。
- 防重复、幂等键、HTTP 409、强制复训与审计、多学生题型专项和旧任务能力的服务/路由回归继续全绿；本轮末次变更仅为视觉模板/CSS 三段布局与高度预算，没有改这些服务端合同。本轮浏览器没有再次发布任务；同一工作树此前的真实合成数据 409/复训证据仍保留，最终自动化覆盖未回归。

### 五项 fidelity surfaces

1. Composition：首屏顺序、列表/检查器双栏、核心工作区高度和分页位置与方向 2 对齐。
2. Geometry：侧栏、页头、日期/筛选、59px 任务行、460px 检查器和三段抽屉均通过真实边界测量。
3. Typography：标题、说明、类型、任务内容、状态与事实区层级清晰；移动英文标题限制一至两行。
4. Color and assets：深墨、暖象牙、Sage 翡翠绿、正式 mark、Font Awesome 导航与真实页头曲线资产均实际加载。
5. Interaction and responsive behavior：筛选、日期、分页、选择行、检查器、编辑/更多、五来源抽屉、移动任务卡和底部详情均可用。

final result: passed

## 当前第四轮视觉残留修复（Luna，等待 Sol 第四次 exact Chrome 复验）

本轮只修 Sol 第三次 exact 复核留下的两个布局问题，不改变防重复、409、幂等、复训审计或任务业务逻辑；此前各轮独立结论保留为历史背景。

### 本轮修改与结构证据

- `templates/tasks.html` 将布置抽屉整理为 `header / .task-assignment-drawer__body / publish footer` 三段；表单使用 `auto minmax(0,1fr) auto`，最终级联强制 `align-items: stretch`。body 自己 `overflow-y:auto`，发布区是独立静态第三行，不再悬浮覆盖来源或字段。
- `static/tasks_workspace_final.css` 保持普通来源与题型专项共用该布局；桌面检查器最终高度覆盖为 `clamp(460px, calc(100vh - 564px), 500px)`，信息体继续内部滚动，列表自然决定工作区高度。
- `tests/test_tasks_workspace_structure.js` 新增/保留抽屉 body、非 overlay footer、compact inspector height、移动状态/截止日期高优先级和双主操作并排断言；未改业务 API 合同。

### IAB 实测（非 exact viewport）

- 当前可用浏览器实际是 `1280×720`，不是任务要求的 `1440×1024` 或 `390×844`。普通来源与题型专项均打开核对：表单 grid rows 为 `113.188px / 509.812px / 97px`；题型专项 body `y=113..623`、`clientHeight=510`、`scrollHeight=1034`，footer `y=623..720`、`position:static`，两者无交叠；五个来源均可见，字段可在 body 内滚动访问。
- 关闭抽屉后的工作区：header `110px`、tabs `46px`、日期条 `44px`、筛选 `64px`、表格 `y=272..658`、首行 `59px`、分页 `40px`；检查器 `y=272..732`、高度 `460px`，两项主操作仍同一行；`document/body.scrollWidth=1265`，页面源 console error/warning 为 `[]`。
- 最终 IAB 截图：`artifacts/tasks-workspace-qa-20260901/tasks-workspace-1280x720-final.png`、`artifacts/tasks-workspace-qa-20260901/tasks-drawer-qtype-1280x720-final.png`；目标与当前实现同一次比较输入：`artifacts/tasks-workspace-qa-20260901/target-vs-drawer-qtype-1280qa-final.png`。组合图明确标注实现为 IAB 1280×720，不能冒充同尺寸 exact 对照。

### 当前阻塞与结果

Luna 没有伪造或宣称 1440×1024 / 390×844 的新截图、computed style 或 overflow 结果；等待 Sol 使用可控 Chrome 完成第四次 exact 视口复验，重点确认移动普通/题型专项抽屉所有字段均不被 footer 覆盖、CTA 始终可见，以及桌面检查器压缩后的目标图对照。此前 Sol 第三次 exact 证据中已通过的移动状态/截止日期、双主操作、紧凑桌面预算必须保持。

final result: blocked

## 当前第三轮视觉残留修复（Luna，等待 Sol 第三次 exact Chrome 复验）

本条仅覆盖 Sol 第二次 exact 复核后发现的移动级联、抽屉 CTA 和桌面密度残留；此前独立视觉结论保留作历史背景，不被本条覆盖。

### 本轮修改

- 新增最后加载的 `static/tasks_workspace_final.css`，并在 `templates/tasks.html` 中置于旧模板样式与工作台模块之后，确保移动任务卡的状态/截止日期不再被 legacy nth-child 规则隐藏。
- 移动抽屉发布区恢复为真正的 `position: sticky` 底栏，设置 `scroll-padding-bottom` 和底部预留空间；五来源与所有字段仍保持可滚动访问。
- 桌面紧凑预算继续收紧：页头 106px 预算、页签 46px、日期条 40px 内容高度、筛选 55px 预算、表头 32px、任务行 46px 内容轨道、分页 40px；检查器两项主操作以并排双列呈现，“打开学生任务”仍在更多操作。
- `tests/test_tasks_workspace_structure.js` 增加最终级联、sticky/底部预留、紧凑预算和主操作并排的结构断言；未改防重复、409、幂等、复训审计或其他业务逻辑。

### 本轮视觉输入、实测与边界

- 已实际打开目标图、Sol 桌面/移动 exact 证据、目标并排复核图及本文件；目标源为 `/Users/zhouxin/.codex/generated_images/01a05850-a764-7672-8bbb-93aafacb13ce/exec-480d1dcf-5f1e-4b23-afce-fe89a5cca987.png`，本轮新实现截图为 `artifacts/tasks-workspace-qa-20260901/tasks-workspace-1280x720-repair-final2.png`，同次组合输入落盘为 `artifacts/tasks-workspace-qa-20260901/target-vs-current-repair-final2-1280qa.png`。组合图明确标注实现为 IAB 1280×720，尺寸不同，不能当作 exact viewport 对照。
- 可用 IAB 实际视口为 `1280×720`：页头 `110.09px`、页签 `46px`、日期条 `44px`、筛选 `64px`、表头 `32px`、首行 `59px`、分页 `40px`；状态和截止日期 computed `display:block`/visible，检查器“调整任务”和“查看学生进度”同一行，`document.scrollWidth=1265`。
- IAB 已确认最终样式表加载、页头/日期/筛选/分页/检查器编辑取消和五来源抽屉交互；页面源 console error/warning 为 `[]`。IAB 无 viewport capability，本轮没有伪造或声称 `1440×1024`、`390×844` 的 computed style、截图或 overflow 结果。

### 五项 fidelity surfaces

1. Composition：桌面实际可见日期/筛选/列表/检查器连续工作区；exact 1440 首屏仍待 Sol 复验。
2. Geometry：桌面高度预算与检查器按钮已压缩；移动 sticky 发布栏和内容底部预留已写入最终级联。
3. Type and hierarchy：`TASKS`、中文说明、状态/截止日期、双主操作层级保留。
4. Color and assets：深墨侧栏、暖象牙工作区、Sage 选中态/主操作与正式品牌资产未改。
5. Responsive behavior：当前 IAB 无横向溢出；移动 exact 卡片 computed style、CTA 覆盖检查和截图仍需 Sol 控制视口复验。

### 当前阻塞与结果

等待 Sol 使用可控 Chrome 完成第三次 `1440×1024` 与 `390×844` exact 复验、移动状态/截止日期截图、sticky CTA 不遮挡来源/字段检查，以及目标同尺寸并排对照。任何 exact 视觉结论在此之前均不提升为通过。

final result: blocked

本条覆盖本轮 `/tasks` 首屏信息架构返修；下方此前的矩阵/功能记录保留作历史背景，不覆盖本条结论。

## 本轮第二次视觉返修：Sol 精确视口问题的代码修正（2026-09-01）

### 修正后的比较输入与视口

- 延续已实际打开的任务管理目标图与 Sol 独立 1440×1024/390×844 证据；本轮把目标图与新实现截图再次置于同一次组合输入：`artifacts/tasks-workspace-qa-20260901/target-vs-current-repair-final-1280qa.png`。
- 新实现原图：`artifacts/tasks-workspace-qa-20260901/tasks-workspace-1280x720-repair-final.png`，来源为 IAB 实际 `1280×720`；目标源为 1487×1058，组合图将目标归一到高 720（1012×720），实现为 1280×720（展示时 1279×720），没有宣称同 CSS viewport。
- IAB 无 viewport capability。本轮没有伪造 exact `1440×1024` 或 `390×844`，也没有把 Sol 的独立截图冒充本轮 Luna 渲染证据。

### 本轮修正与可验证结果

- 桌面密度：侧栏压至 176px，页头 overline/说明拆开，日期/筛选压缩，隐藏额外 `ASSIGNMENTS / 任务列表` 标题工具条；首屏 IAB 工作区 y=146，任务行保留状态圆点、进度和截止日期。
- 检查器：增加内部信息滚动区；状态/计时控制和“调整任务”“查看学生进度”固定在检查器底部可用；“打开学生任务”仅作为低频入口进入“更多操作”。
- 移动 cascade：显式恢复 `.task-status` 与 `.task-deadline` 卡片单元的可见性，任务标题限制两行；筛选在窄屏改为两列；抽屉首行使用 `task-assignment-meta`，发布区在窄屏改为正常流布局，不覆盖五来源。
- 1280×720 IAB：scrollWidth `document=1265 / body=1265`，页面源 console `error=[] / warning=[]`；已操作检查器编辑/取消、打开/关闭抽屉并确认五种来源。

### 五项 fidelity surfaces（本轮修正后）

1. Fonts and typography：`TASKS`、中文说明、任务标题/状态层级分离；任务标题和移动卡片使用受限换行。
2. Spacing and layout rhythm：压缩首屏纵向预算，移除标题工具条，检查器内部滚动，抽屉 meta 与发布区不再制造/覆盖空洞。
3. Colors and visual tokens：保留深墨侧栏、暖象牙工作区、Sage 主操作与 Sage 实心当前日；本轮未改既有色彩合同。
4. Image quality and asset fidelity：继续使用正式 Sage Path mark、Font Awesome 导航图标和 `tasks-header-wave.png`，未以文字/emoji/CSS art 替代可见资产。
5. Copy and content：页头为 `TASKS / 任务管理 / 布置、追踪并调整学生学习任务`；主操作明确为“调整任务”“查看学生进度”，历史功能入口仍可达。

### 当前阻塞与结果

- 自动化与当前 IAB 交互回归已通过；但 exact `1440×1024`、`390×844` 的本轮浏览器渲染、同视口截图、移动 overflow/console 仍需 Sol 的可控 Chrome 独立复验。
- 该证据门槛是当前唯一未完成的视觉验收项；不要把下方历史 `passed` 结论提升为本轮结论。

final result: blocked

## 现场与视觉输入

- 工作树：`/Users/zhouxin/.codex/worktrees/c56a/studytracker`；detached HEAD `846900c65e3b094354c4ebb3d3367a7a918b0b0a`；本轮继续保留既有脏实现，未 commit/push/deploy/写生产库。
- 已实际打开：目标图 `.../exec-480d1dcf-5f1e-4b23-afce-fe89a5cca987.png`、此前实现图 `artifacts/tasks-list-inspector-desktop-1440x1024-final.png`、此前并排复核图 `artifacts/audit-tasks-design-20260901/01-target-vs-final-implementation.png`、本文件。
- 本轮实现截图与目标图已置于同一次并排输入：`artifacts/tasks-workspace-qa-20260901/target-vs-current-1280qa.png`；实现原图为 `tasks-workspace-1280x720-clean.png`。IAB 实际视口为 **1280×720**，没有 viewport capability，因此没有伪造 1440×1024 或 390×844 证据。
- 已运行 user-context preflight：脚本存在且正常返回 saved context 缺失；按任务提供的视觉源继续，不视为插件阻塞。

## 本轮实际返修

- 默认首屏顺序已改为：深墨侧栏 → 标题/说明/搜索/提醒/布置 → Week/Month/Year → 逐日日期条 → 学生/分类/状态/截止日期筛选 → 统一任务列表 → 右侧检查器。统计、Recent、Top、备忘录降为次级折叠区域。
- 任务列表主列改为头像/中英文姓名、类型图标、标题/范围、计划用时、状态圆点/文字/进度条、截止日期；旧状态下拉、计时、证据、完成率、正确率、编辑/删除/批改/轨迹仍保留在检查器或“更多”操作中。
- 检查器补齐来源/布置时间、学生与范围、计划时间/截止日期、完成证据/提交方式/当前进度、教师备注、时间线、调整任务、学生进度和可操作更多菜单；现有真实 control hook 未改后端合同。
- 侧栏改用仓库正式 `static/brand/sagepath-mark.png` 与 Font Awesome 导航图标；页头使用本轮生成并复制到 `static/brand/tasks-header-wave.png` 的 sage 曲线资产。
- 新增 `static/tasks_workspace.css`、`static/js/tasks_workspace.js`，收拢响应式任务卡、日期选择和分页；统一抽屉五种来源与专项矩阵逻辑继续复用原模板/服务。

## 五项 fidelity surfaces（本轮 1280×720 实测）

1. Composition：列表与检查器已进入工作区首屏，日期条/筛选紧邻列表；无默认“任务记录与计时”重复标题、独立任务窗口摘要卡或按学生大分组卡。
2. Geometry：列表与检查器双栏，计划/实际用时分行显示避免覆盖状态/截止日期；抽屉标题固定、来源分段，底部发布操作固定可见。
3. Type and hierarchy：任务页头、时间范围、列表工具栏、状态/进度和检查器事实区形成连续层级；桌面实际截图中可读。
4. Color and assets：深墨侧栏、暖象牙工作区、sage 主操作/选中态、正式 Logo 与 Font Awesome 图标已实装；目标曲线资产已进入页头。
5. Copy and responsive behavior：搜索、分页、更多操作、抽屉来源和历史功能入口仍可达；移动断点的任务摘要卡/底部检查器与抽屉规则已写入专用 CSS，但本轮未取得可控 390px 浏览器渲染证据。

## 当前浏览器证据与阻塞项

- IAB 当前视口：`innerWidth=1280`、`innerHeight=720`；`document.documentElement.scrollWidth=1265`、`body.scrollWidth=1265`，当前视口无横向溢出。
- IAB 页面源 console error/warning：新建干净页读取为 `[]`。已实测普通抽屉、题型专项抽屉、来源数量 5、搜索过滤、日期选择、分页、检查器更多菜单；没有创建任务或写生产数据。
- 本轮未在浏览器重新执行 409/复训发布；既有防重复、幂等、矩阵、复训和旧入口由自动化回归继续覆盖。
- P2 evidence gate：IAB 无 viewport capability，无法提供用户要求的 exact `1440×1024` 与 `390×844` 截图/scrollWidth/交互证据；等待 Sol 使用可控 Chrome 完成 exact viewport 复验，并重新制作同尺寸目标图对照。

## 本轮截图

- `/Users/zhouxin/.codex/worktrees/c56a/studytracker/artifacts/tasks-workspace-qa-20260901/tasks-workspace-1280x720-clean.png`
- `/Users/zhouxin/.codex/worktrees/c56a/studytracker/artifacts/tasks-workspace-qa-20260901/task-assignment-drawer-1280x720.png`
- `/Users/zhouxin/.codex/worktrees/c56a/studytracker/artifacts/tasks-workspace-qa-20260901/target-vs-current-1280qa.png`

final result: blocked

# `/tasks` 方向 2 Design QA

日期：2026-09-01（Asia/Shanghai）
工作树：`/Users/zhouxin/.codex/worktrees/c56a/studytracker`
范围：任务列表、右侧检查器、统一布置抽屉、题型专项预览与重复发布状态。

## 2026-09-01 独立视觉复核结论（覆盖下方原验收结论）

用户指出最终页面没有忠实按照已确认效果图实现。独立复核将任务管理目标图与最终
`artifacts/tasks-list-inspector-desktop-1440x1024-final.png` 并排比较，确认该判断成立；
组合证据为 `artifacts/audit-tasks-design-20260901/01-target-vs-final-implementation.png`。

- **结构级 P1：未通过。** 目标首屏是“周/月/年主标签 → 每日日期条 → 一行筛选 → 统一任务列表 + 固定右侧检查器”；实现仍保留“任务记录与计时”二级标题、单块日期摘要、独立筛选卡和按学生分组/备忘录卡，信息架构不是同一构图。
- **列表级 P1：未通过。** 目标用头像、类型图标、进度条、截止日期和单行任务记录形成高密度可扫视列表；实现继续使用旧式表格控件、日期换行、状态下拉、计时器与按钮堆叠，首屏可扫视性和视觉密度明显偏离。
- **检查器 P1：未通过。** 虽已加入右侧检查器，但目标中的任务范围、完成证据、教师备注、时间线及底部主次操作层级没有完整还原；实现只是较窄的字段摘要卡。
- **品牌与导航 P2：未通过。** 深墨/象牙/Sage 色彩方向接近，但目标的品牌图标、导航图标、完整分组、页头曲线资产、标题比例和留白没有忠实实现，当前仍像旧后台换肤。
- **抽屉功能可用但视觉未验收。** 统一入口、题型专项、重复矩阵与 409 防护属于功能成果；现有效果图没有提供抽屉的逐状态视觉目标，因此不能用功能通过替代视觉忠实度通过。
- **移动端仅能确认无明显横向溢出。** 当前证据中的任务卡列宽、标题换行和状态/计时控件密度仍需重新设计；不能据截图宣称完整可用性或无障碍合规。

独立结论：功能整合可以保留，但页面视觉不能以当前版本验收。应由 Luna 在同一 worktree
按目标图重做首屏构图，再用同视口并排图复验；下方旧记录中的 `P0/P1/P2 = 0` 与
`final result: passed` 已被本节明确否定。

## 组合视觉输入

本轮使用 `product-design:image-to-code` 流程。目标图与真实 Chromium 实现截图在同一次组合视觉输入中连续载入比较；桌面实现保持 1440×1024，窄屏另行以 390×844 复验；不是按文件名或文字猜测。

- 任务管理目标图：`/Users/zhouxin/.codex/generated_images/01a05850-a764-7672-8bbb-93aafacb13ce/exec-480d1dcf-5f1e-4b23-afce-fe89a5cca987.png`
- 共用后台方向基准：`/Users/zhouxin/.codex/generated_images/01a05850-a764-7672-8bbb-93aafacb13ce/exec-80ea9a25-3b04-4a63-8f63-f6aa6b94fd0a.png`
- 现生产页参考：`/Users/zhouxin/Desktop/studytracker/artifacts/admin-redesign-current-tasks-20260901.png`（仅理解布局；其中真实姓名未复制）
- 最终目标图+实现图组合中的实现截图：`/Users/zhouxin/.codex/worktrees/c56a/studytracker/artifacts/tasks-list-inspector-desktop-1440x1024-final.png`
- 本次 P1/P2 修复的目标图+实现图组合：目标仍为上面的任务管理目标图，实现图为
  `/Users/zhouxin/.codex/worktrees/c56a/studytracker/artifacts/tasks-qtype-matrix-409-desktop-1440x1024.png`；两张图在同一次视觉输入中复核，确认抽屉内矩阵不会把未命中题组折叠掉，且命中的原子题组格显示“完全重复”。

## 五项 fidelity surfaces

1. Composition：深墨色左导航、暖象牙工作区、Sage 主操作；日期窗口、筛选、任务列表与右侧检查器在桌面首屏连续出现。统计、Recent、Top、备忘录保留为次级区域，不再遮挡核心任务工作流。
2. Geometry：桌面列表与检查器采用双栏；`+ 布置新任务` 打开右侧抽屉；原 11 列表格的 ID、证据、完成率、正确率、备注等低频/细节进入检查器或“更多操作”，任务行主列保持可读。
3. Type and hierarchy：`TASKS / 任务管理`、`NEW ASSIGNMENT`、`SPECIALTY PRACTICE`、状态徽标、题组元数据和检查器事实字段形成稳定层级；日期条明确显示当前 Week/Month/Year 窗口。
4. Color and tokens：导航使用深墨色，工作区使用暖象牙，内容面为白色，主按钮/选中态为 Sage 翡翠绿，重复警告为琥珀，阻止/删除为红色，边框和辅助文案保持低对比。
5. Content, controls, responsive behavior：保留 Week/Month/Year、任务统计、计时、完成率、正确率、备忘录、昨日任务、普通/材料/听力/阅读/题型专项入口；题型专项显示完整 Question Group、原题号、renderer、音频/文章/图片/时间点、按组移除与逐学生历史。390px 使用移动任务行网格和单列抽屉，无横向滚动。

## 验收视口与交互

- 1440×1024：`tasks-list-inspector-desktop-1440x1024-final.png` 显示首屏任务列表+检查器，日期窗口和筛选紧邻列表；最终 `document.documentElement.scrollWidth=1425 <= innerWidth=1440`，正文 `body.scrollWidth=1425`。
- 390×844：`tasks-list-mobile-visible-390x844-final.png` 显示可读的日期/类别/任务/状态/计时行；`document.documentElement.scrollWidth=375`、`innerWidth=390`，表单抽屉 `clientWidth=scrollWidth=358`。
- 统一抽屉：普通任务、材料库、听力题库、阅读题库、题型专项并列；普通来源单学生，题型专项可多选学生。专项预览实测 2 个完整组，并显示 Demo Student One / Demo Student Two 的四个独立「学生 × 题组」矩阵单元：仅第一位学生的第一组有历史，另外三格明确“未布置”（合成浏览器数据仅存在本地）。
- P1 矩阵响应：`resource.units` 返回本次请求的每个 group，`matrix_rows` 对 2 名学生 × 2 个 group 恰好返回 4 行；命中行含原任务 ID、日期、状态、重叠题组和 staff-safe 查看入口，未命中行含“未布置”，不含 token 或答案。
- P1 409 重显：预览后在后台本地合成第二位学生的历史题组，点击发布真实收到 `HTTP 409 duplicate_assignment_conflict`；抽屉仍显示 4 个矩阵单元，命中的 G1/G2 原子格显示“未开始 · 完全重复 / 原任务 #1/#2”，未命中格明确“未布置”，未退化为笼统提示。
- P2 状态语义：任务级 `students[].matches[].overlap_type` 对 G1+G2 仍为 `partial`，供发布策略和审计使用；只有 question_type 的原子 `matrix_rows` 命中格覆盖为 `exact`，renderer 优先使用行语义，所以 G1 显示“完全重复”，其余三格显示“未布置”。
- P2 409 文案：真实 409 仍保留完整矩阵，但 `#taskQtaStatus` 显示“检测到重复任务：请查看下方历史记录；如需复训，请二次确认并填写原因。”；普通来源复用同一映射且把中文提示插入历史容器，不覆盖矩阵；页面正文不再暴露 `duplicate_assignment_conflict`。
- 窄屏矩阵：`tasks-qtype-matrix-mobile-390x844-final.png` 与 `tasks-qtype-matrix-409-mobile-390x844.png` 均同时显示四格；`document.documentElement.scrollWidth=375`、`body.scrollWidth=375`、抽屉 `scrollWidth=358`，均不超过 `innerWidth=390`。
- Chrome 409 证据：`artifacts/tasks-qtype-matrix-409-chrome-desktop-1440x1024.png` 与 `artifacts/tasks-qtype-matrix-409-chrome-mobile-390x844.png`；Chrome 页面源 console error/warning `[]`（不计 Chrome 扩展自身日志），桌面四格和中文提示同屏，移动端四格完整可见且 DOM 中文提示已核对。
- Listening Section 2：Demo Student One 显示“进行中 · 完全重复”、原任务 #1、日期、Section 2 和 staff-safe 查看链接；Reading Passage 1 对 Demo Student Two 显示“待批改 · 完全重复”、原任务 #3。
- 材料题号：材料题目范围显示原任务 #2 的部分重复；听写 5–9 与历史 3–8 显示原任务 #4 的“进行中 · 部分重复”、重叠 5–8。
- 普通 Listening 发布：实际点击添加后保持抽屉打开，HTTP 409 的 `duplicate_assignment_conflict` 详情重新显示在抽屉中；勾选复训确认并填写原因后本地合成任务可发布。
- 旧入口：`/tasks/question-types` 实际重定向到 `/tasks?source=question_type#taskForm` 并打开专项抽屉。
- 检查器“更多操作”是可展开的真实 `details` 菜单，实测能显示编辑/删除按钮；控制台 error 日志为 `[]`。
- 本次修复新增 `static/js/task_assignment_matrix.js` 的 renderer 单测；Node DOM 字符串断言确认四个学生×题组单元各渲染一次，且 staff-safe 链接不泄露 token。

## P2 横向溢出修复迭代历史

1. Sol 首轮指出 P2：抽屉表单横向排列造成 `taskForm.scrollWidth=1816`；任务列表首屏被统计/Recent/备忘录推到下方；旧 11 列和说明式“更多操作”不符合目标构图；390px 有水平滚动条。
2. 第一轮返修：任务工作台排序为“标题 → 日期窗口 → 筛选 → 列表+检查器”，抽屉改为纵向固定视口，低频字段进入检查器/菜单。
3. 第二轮返修：补齐所有资源字段的防抖历史刷新和 revision guard；移动端初步虽然 `scrollWidth` 归零，但任务名出现逐字竖排。
4. 最终返修：390px 任务表行改为三列网格，修复长任务名、状态和计时入口的可读性；补日期窗口条并重新跑 1440/390 实测。最终两种视口均无页面或抽屉横向溢出。

## Findings

- P0：0
- P1：0
- P2：0
- 有意差异：目标稿使用示例头像、姓名和较丰富的任务密度；实现使用真实数据库查询结果。浏览器验收只使用本地合成学生与任务，不把生产截图中的姓名写入代码、fixture、文档或日志。
- 未在生产浏览器、生产数据库或学生真实发布链路执行写操作；这些属于本轮明确禁止范围。

历史记录（已被本文件顶部本轮 QA 覆盖）：此前 Luna/矩阵专项视觉结论为 passed；本轮 exact viewport evidence gate 尚未完成。
