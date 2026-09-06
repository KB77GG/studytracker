# Web 刷题执行复核

更新时间：2026-09-06
工作树：`/Users/zhouxin/.codex/worktrees/87b6/studytracker`
分支 / 业务提交 / 基线：`codex/question-type-web-refinement` / `b3fceb11f8e40314988e0ec4583b2fdc794fc104` / `dbf781e51f2689052920b59459fd58f1a2265a26`
状态：实现、自动化门禁、应用内浏览器验收、提交 / 推送和生产部署均已完成；未写生产业务数据，未改 schema，未改或发布小程序。

## 1. 扫描口径与可访问范围

“可访问”按实际 Web 目录和直达路由计算，不把仅存在于聊天或导入中间物的 JSON 算入。

| 入口 / 数据根 | 来源 | 文件 | 单元 | 题组 | 题目 |
| --- | --- | ---: | ---: | ---: | ---: |
| `/listening/tests` / `static/listening_tests/*.json` | Cambridge | 72 | 288 Sections | 568 | 2,880 |
| 同上 | JFDR 6 | 6 | 24 | 48 | 240 |
| 同上 | JFDR 7 | 6 | 24 | 42 | 240 |
| `/listening/jijing` / catalog + `parts/` | legacy 机经 | 232 Parts | 232 | 497 | 2,320 |
| 同上 | 虾滑 | 113 Parts | 113 | 178 | 1,130 |
| `/reading/tests` / `static/reading_tests` | Cambridge | 72 | 216 Passages | 613 | 2,880 |
| `/reading/jijing` / catalog | ZYZ 在线 | 56 | 168 | 498 | 2,240 |
| 目录下架但仍可按 ID 直达 | `reading_jijing_83_test_95` | 1 | 3 | 8 | 39 |

合计为 **558 文件 / 1,068 单元 / 2,452 题组 / 11,969 题**。其中 Listening 429 文件 / 681 单元 / 1,333 组 / 6,810 题；Reading（含离线直达）129 文件 / 387 单元 / 1,119 组 / 5,159 题。题型专项索引只覆盖 `listening_tests` 与 `reading_tests`，即 156 文件 / 1,271 组 / 6,240 题；两类机经仍复用整卷模板，故纳入共享渲染审计。

目录闭合性已核对：Listening 机经 catalog 的 345 个 Part 与 `parts/*.json` 精确相等；ZYZ catalog 引用 56 个文件，唯一额外 payload 正是 offline manifest 中的 `reading_jijing_83_test_95`。

## 2. 标签、实体、占位符与表格结论

- 全部题库没有 `script/iframe/style/svg/object/embed`、事件属性或 `javascript:`，也没有编码后的 HTML 标签。
- Cambridge Listening 的 `&nbsp;` 出现在 45 文件 / 57 题组，共 13,160 次；这是旧纸面表单分栏信息，需只解码一次后继续走白名单。
- Reading 只有 5 个 `collect` 使用结构标签：IELTS 21 Test 2 group 589 的 `table/tr/th/td/br`；IELTS 21 Test 4 groups 606、607、608、611 的 `div/p/ul/li`。
- 活动 `collect/table` 共 854 个题组；识别 4,885 个 marker occurrences，覆盖 4,873 个 question IDs。其中 4,861 个 exact-once，12 个 question IDs 在 11 组内重复（多出 12 次），4 个 ID 在 1 组内缺失，题组外孤儿 marker 为 0。
- 唯一缺 marker 的可达题组是 `static/listening_jijing/parts/jijing_76_test_113_part_3_1308.json` group 2903：Q26–30 只有 Q26 的 `$12915$`。页面现为 Q27–30 补通用编号回答行，不臆造题干。
- 196 个对象表格全部能正规化成无重叠网格。唯一原始 HTML table 是 group 589，语义形状 5×3，Q3/Q4 位于同一单元格。
- 当前语料中的 optional-end-tag、`rowspan=0`、结构空白、非法安全属性计数均为 0；sanitizer 的合成回归仍覆盖这些兼容边界。

扫描只把与同题组 question/item ID 相等的 `$numeric_id$` 当 marker；不能对 JSON dump 使用宽泛正则，否则会把 `US$90-$100` 等正文金额误报。

## 3. 共因与落地修复

### A. 原始结构标签外露

`ielts21_test2_reading.json` Passage 1 group 589 的完整视觉表格在 `collect` 内。旧链路只允许行内伪标签，因此虽然 5 个输入框存在，`table` 标签会作为文字实体外露。

修复后的 `PracticeTable.withStructuredPlaceholders` 只在顶层 `group.collect` 边界启用：

- 行内 `b/i/bc/iu/br/divider` 与结构 `table/thead/tbody/tfoot/tr/th/td/caption/colgroup/col/p/div/ul/ol/li` 都正规化为固定标签和固定 class。
- 来源属性默认全部丢弃，只允许 1–100 的整数 span、`rowspan=0` 和合法 `th scope`。
- 校验父子结构；孤立或错位的白名单标签也转义，避免浏览器修复 DOM 时移动答题控件。
- 支持 `td/th/tr/thead/tbody/tfoot/li/p/colgroup` 的 HTML optional-end-tag 语义，并抑制 table 容器纯空白文本。
- 重复 marker 只生成一个可答控件，其余变成 inert ghost；未知 marker 只显示空位。
- 真实 group 589 门禁固定 1 个语义 table、5 `tr`、3 `th`、12 `td`、5 个唯一控件及其单元格归属。

### B. 共享选项库把 completion 错判为 matching

旧启发式会把“共享选项不少于 3 且题目不少于 3”的 completion 当 matching，随后丢弃 `collect`。完整 placeholder + options 布局共 **59 组 / 286 题**；旧分发风险集合共 **47 组 / 228 题**，其中 canonical completion 子集为 **43 组 / 208 题**：Cambridge Reading completion **35 / 171**，另有 4 / 20 个 Cambridge single-choice 风险样本；ZYZ completion **8 / 37**。ZYZ 在线语料中完整 placeholder ownership 的更大覆盖面是 **15 组 / 73 题**，它包含合法 matching 等非 completion 类型，不能与 8 / 37 的误判子集混写。

修复以“本组每道题的 ID 是否已被 `collect/table` 完整拥有”为优先事实。完整拥有时不再走宽泛 matching renderer；snapshot 重写后的 marker 和新 ID 也复用同一判断。独立探针确认 ZYZ 8 / 37 目标子集及全部 15 / 73 完整 ownership 页面均每题恰好一个控件。

### C. 缺 marker 的结构题没有答题入口

结构内容渲染后，通过 `PracticeTable.unmappedItems` 找出未出现的 item，并输出中性的编号回答行。已有 marker 保持原位置；缺失题不从答案或其他字段反推题干。

### D. 目录与答题工作区信息密度

- 题型目录重排为紧凑 12 栅格：科目、题型、范围、库规模、节奏和分钟数首屏可见；移除重复预览区，只保留错误重试；固定底栏持续显示当前选择、清空与开始。
- Listening 移除练习页重复的全局导航和侧边判分卡，把标题、播放条、保存态压入紧凑头部；底栏成为唯一的全题号、上一题 / 下一题、待回看、计数和提交入口。专项拼卷按来源标注 Section，跨 Section 题号会切换后精确聚焦 input/select/radio/checkbox。
- Reading 桌面成为左右独立滚动的 50/50 双栏，分隔条可拖拽或键盘调节并以 sessionStorage 记忆，范围 38%–62%；1024 宽仍保留双栏，考试 / 移动模式不启用拖拽。底栏展示真实 Passage 编号和全部题号，跨 Passage 使用双 RAF 等待 DOM 后聚焦；用户手动 focus 会取消排队中的旧导航，避免焦点被抢回。
- 提交后的题型专项复盘由 capability 重绘后再次锁定所有答题控件，移除可写提交 / 重置入口，保留明确状态与答案内容。

## 4. 自动化审计与门禁

最终复跑命令：

```sh
node --check static/js/practice_table.js
node --check static/js/practice_renderers.js
node tests/test_practice_table.js
node --test \
  tests/test_practice_renderers.js \
  tests/test_listening_practice_navigation.js \
  tests/test_question_type_review_readonly.js \
  tests/test_reading_practice_navigation.js \
  tests/test_practice_modes.js \
  tests/test_practice_shell.js

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. \
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_question_type_practice.py \
  tests/test_question_type_practice_contract.py \
  tests/test_reading_practice_layout.py \
  tests/test_practice_interaction_e2e.py \
  tests/test_practice_markup_audit.py \
  tests/test_question_type_catalog_ui_contract.py \
  tests/test_question_type_practice_routes.py \
  tests/test_mock_exam_template_isolation.py

/Users/zhouxin/Desktop/studytracker/.venv/bin/python \
  scripts/audit_practice_markup.py --json
git diff --check
```

结果：PracticeTable 独立脚本通过；独立终审 Node test runner **46 / 46**；Python **58 passed / 169 warnings / 10 subtests passed**；CI 同款 unittest **68 passed**，spelling queue 与本任务 Python 目标 Ruff 通过；scanner JSON 正常生成；`git diff --check` 通过。主任务此前的窄集复跑（Node 37 / 37、Python 38 + 10 subtests）也通过。

`scripts/audit_practice_markup.py --json` 的进程退出码为 0，但报告 `ok:false`，因为它忠实列出源语料中 11 组重复 marker 与 1 组缺 marker，共 12 个已知 finding；`--strict` 对这些已知源问题会按设计返回非零。运行时保护和对应回归已覆盖它们，不能把严格模式非零写成门禁通过，也不应静默改题库消除报告。

## 5. 应用内浏览器验收

本地隔离预览：`http://127.0.0.1:5117/practice/question-types`。使用临时 SQLite 学生账号，仅写 `/tmp/studytracker-question-type-preview.WuIvug/preview.db`；未访问生产写接口。

| 区域 | 实测动作 | 结果 |
| --- | --- | --- |
| 目录 | Listening 首屏统计；切换 Reading、题型和来源；选择 / 清空 / 开始 | 18 volumes / 72 tests / 287 publishable Sections 可见；固定 CTA 与选择摘要同步，Pass |
| Listening 专项 | 1 Section / 10 题；Q2 文本输入和保存；实际播放后暂停 | 值保存、播放器状态变化、底栏无重复提交入口，Pass |
| Listening 整套 | Q11 radio、Q17 select、Q22 combined checkbox；跨 Section 全题号 | 各控件精确聚焦；来源标签、计数与 Section 同步，Pass |
| Reading 整套 | group 589；键盘调分隔条 50→53；Q1；跨 Passage Q14；刷新 | 5×3 语义表格、5 唯一控件；双栏独立滚动；草稿 `dream` 恢复，Pass |
| Reading 直达 P3 | `/reading/test/ielts21_test2_reading?passage=3` | 顶部和底栏均显示 Passage 3，14 题，Pass |
| Reading 焦点竞态 | 发起跨篇导航后立即手动聚焦另一控件 | 排队回调不再抢回焦点，正常跨篇导航仍工作，Pass |
| 专项提交 / 复盘 | Reading 5 题提交 `rats`，1 / 5；刷新复盘 | 所有控件 disabled；提交 / 重置消失；结果保留，Pass |
| 响应式 | 1440×1000、1366×768、1024×768 | 无横向溢出；Listening 头 / 底栏不遮题；Reading 1024 双栏与 radio 可达，Pass |

实际截图和四张对照参考保存在 `docs/design/question-type-web-execution-20260905/`；逐图比较、视口、状态和差异说明见仓库根 `design-qa.md`。

## 6. 提交、CI 与生产部署

- 业务提交 **`b3fceb11f8e40314988e0ec4583b2fdc794fc104`** 已在再次 fetch 并确认 `origin/main` 未移动后，通过 `git push --atomic` 同步到 `codex/question-type-web-refinement` 与 `main`。本报告的最终生产状态随后以 `[skip ci]` 纯文档提交同步，不触发第二次部署。
- GitHub 顶层任务分支 CI [34000980578](https://github.com/KB77GG/studytracker/actions/runs/34000980578)、主线 CI [34000980567](https://github.com/KB77GG/studytracker/actions/runs/34000980567) 和 Deploy [34000980581](https://github.com/KB77GG/studytracker/actions/runs/34000980581) 均为 success。两个 CI 的 test job 通过；advisory lint job 仍因未改的 `app.py`、旧脚本等存量 Ruff 问题失败，workflow 按配置 `continue-on-error`，本任务目标 Ruff 全过。
- 生产 `/root/apps/studytracker` 为 `main@b3fceb11`、tracked clean，部署前后 17 个既有 untracked 备份 / 静态目录 / 调度库不变。`studytracker.service` 自 2026-09-06 08:20:02 CST active/running，`NRestarts=0`；5002、master + 1 worker、gthread、6 threads 精确符合约束。SQLite `quick_check=ok`、外键 0；服务启动后 journal 无 warning / error。
- 公网根路由 302；目录、Reading IELTS 21 T2 整套 / `?passage=3`、Listening IELTS 21 T1、旧 Listening 机经均 200。PracticeTable `5978d1420cca66f08c24b09beaf2abdd01aa838c1027b417c71464668c720675`、PracticeRenderers `3333b1c3567570b917cfb9722d289b7b8801ddbc1d8d22ac38bcf6e093b025cd`、practice CSS `074b51efc49ff15a2238d6abde16dee3c9dc394deecb4c18ef9ef53bdab15335` 的本机 / 服务器 / 公网 SHA-256 一致，公网均为 `Cache-Control: no-cache`。
- 生产 Chrome 只读复核：Reading raw table 变为 5 行 / 15 cell、5 个唯一控件且无标签外露；Listening S1 是 10 题号 / 10 题 / 唯一提交；目录有 8 个筛选按钮 / 固定选择栏 / 唯一开始；旧机经 group 2903 所在 Part 的 Q21–30 十个输入完整。没有输入、提交、播放、创建任务或写学生数据，临时生产标签页已关闭。

## 7. 审阅记录、边界与未验证项

- 三个并行实现分别完成目录、Listening、审计脚本；主任务逐项复核并整合。独立终审又发现并修复 sanitizer 对隐式 `p/colgroup` 关闭、Reading 直达 P3 底栏编号和跨篇导航 / 手动 focus 竞态；新增回归后再次通过。终审结论为 **GO**，未发现 sanitizer 可利用绕过或三页 UI 阻断回归。
- 审阅发现曾出现无依据题文变更，已恢复原文；`static/reading_tests/ielts21_test2_reading.json` 与 HEAD 现无差异，Reading 截图均在恢复后重拍。页面展示忠实保留源文本，不把其中任何英文词误标为缺陷。
- 数据题干、答案、评分、提交协议、数据库 schema、生产配置和小程序均未改。`services/question_type_practice.py` 只更新 renderer 元数据名称。
- 未在真实生产账号、Safari / 微信 WebView、真机触屏或生产音频 CDN 上验收；本地浏览器覆盖的是 Chromium 应用内浏览器和开发用临时账号。
- 非阻断的未来数据边界：若以后把文本 / placeholder 非法地直接放在 `<table>` 或 `<tr>` 下，浏览器仍会做 foster-parenting；inline 标签包裹 block 标签也可能产生语义无效但无执行面的 DOM。当前可达语料没有这种结构，唯一 raw table 的 5 个 marker 都合法位于 cell 内。
- 当前业务代码、测试、报告和截图均已 commit / push，后端已部署；本轮没有生产数据库业务写入、schema 变更或小程序发布。下一步只需观察真实学生反馈；真实账号提交、Safari / WebKit、微信 WebView 与真机触屏仍待实测。
