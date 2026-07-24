# 强化拼写 Sage Path 视觉 QA

日期：2026-07-23
目标页面：`pages/student/dictation/spell/index`
视觉来源：`/Users/zhouxin/Downloads/已生成图像 1 (1).png`

## 对照证据

- 同屏对照（左侧来源、右侧生产实现）：
  `/Users/zhouxin/.codex/visualizations/2026/07/23/studytracker-sage-spelling/source-vs-implementation.png`
- 390×844 初始空答案：
  `/Users/zhouxin/.codex/visualizations/2026/07/23/studytracker-sage-spelling/spell-390x844-blank.jpeg`
- 390×844 手动点击 `c`、`o` 后：
  `/Users/zhouxin/.codex/visualizations/2026/07/23/studytracker-sage-spelling/spell-390x844-typed-co.jpeg`
- 320×568：
  `/Users/zhouxin/.codex/visualizations/2026/07/23/studytracker-sage-spelling/spell-320x568.jpeg`
- 768×1024：
  `/Users/zhouxin/.codex/visualizations/2026/07/23/studytracker-sage-spelling/spell-768x1024.jpeg`
- iPad 768×1024、开发者工具 75% 显示比例，手动输入 `c`、`o` 后：
  `/Users/zhouxin/.codex/visualizations/2026/07/23/studytracker-sage-spelling/spell-ipad-75-typed-co-outline-no-caret.png`
- 方格输入区同屏聚焦对照（左侧来源、右侧修复后实现）：
  `/Users/zhouxin/.codex/visualizations/2026/07/23/studytracker-sage-spelling/cursor-focus-source-vs-final.png`

来源图像为 853×1844 px；iPad 实现由微信开发者工具按 768×1024 CSS 视口、DPR 2、75% 显示比例渲染，工具窗口截图为 1248×768 px。聚焦对照把来源裁区 763×340 px 与实现裁区 380×170 px 等比容纳到各自 720×320 px 画布，避免仅因密度和工具缩放差异产生误判。

## 检查结果

- 视觉层级：Sage Path 品牌头、成长路径进度、中文释义、中央重听、方格答案区、底部键盘均与来源保持同一视觉语言。
- 输入状态：初始十个方格完全为空；对照图中的 `c`、`o` 是 QA 时逐个点击键盘产生，不是首字母提示或预填。
- 当前输入位：只用琥珀色描边和轻微外圈标记，不在单字符方格内叠加闪烁竖线，避免出现悬空或偏位的伪光标。
- 播放入口：页面只有中央“重听”入口；键盘内没有第二个重听按钮。
- 键盘比例：字母键使用三行紧凑 QWERTY，标签通过独立文本层做光学垂直居中；确认键占满键盘宽度，平板端键盘最大宽度 560px。
- 响应式：320×568、390×844、768×1024 均完整显示主要操作；窄屏没有横向溢出，平板没有无限拉宽，底部保留安全区。
- 开发者工具：最终页面 0 error；3 条 warning 均为自动热重载、HarmonyOS 提示和灰度基础库提示，没有页面或组件告警。
- 字体与排版：中文释义、进度、重听与字母方格的字号、字重和行高保持原 Sage Path 层级，输入后字母在方格中垂直居中。
- 间距与布局：本次只删除方格内伪光标，不改变进度、释义、重听、答案方格和键盘之间的既有响应式节奏。
- 颜色与状态：当前格继续使用既有琥珀色状态色，已输入格使用青绿色；没有用闪烁动画重复表达同一状态。
- 图像质量：品牌图、成长路径背景和功能图标继续使用现有 JPG/SVG 资源，没有新增占位图、文本符号或 CSS 绘制替代物。
- 文案：页面仍只显示中性“重听”，未增加答案提示、严格模式标签或授权常驻文案。

## 本轮比较历史

- 先前 P2：iPad 空答案状态在当前方格中叠加闪烁竖线，竖线视觉位置不自然，并与方格描边重复表达焦点。
- 修复：删除 `.slot.active::after` 伪元素；保留 `.slot.active` 的琥珀色描边与轻微外圈。
- 修复后证据：iPad 空答案与手动输入 `c`、`o` 后均只显示活动方格描边；字母清晰落入前两个方格。聚焦同屏对照未发现新的 P0/P1/P2 差异。

## 有意差异

- 未显示来源图右上角“严格拼写”，遵循已确认产品要求。
- 未显示来源图键盘上方“实体键盘需教师授权”，授权规则保留在服务端和模式切换逻辑中，不做常驻文案。
- 来源图的键帽更高；生产实现按学生反馈缩短键帽和操作区，保持手指可点范围并减少页面比例失衡。

## 缺陷分级

- P0：0
- P1：0
- P2：0

final result: passed

---

# 刷题库二期统一工作台 Design QA

## Comparison Target

- 视觉基准：现有 `/listening/tests` 工作台与用户提供的 3a 设计截图。
- 实现页面：
  - `http://127.0.0.1:5001/practice`
  - `http://127.0.0.1:5001/listening/tests`
  - `http://127.0.0.1:5001/reading/tests`
  - `http://127.0.0.1:5001/listening/jijing`
  - `http://127.0.0.1:5001/reading/jijing`
- 对照证据：
  - `/tmp/studytracker-workspace-phase2-task1-comparison.png`
  - `/tmp/studytracker-workspace-phase2-task2-comparison.png`
  - `/tmp/qa-1280-contact.png`
  - `/tmp/qa-768-contact.png`
  - `/tmp/qa-375-contact.png`
- 视口：1280 × 844、768 × 844、375 × 844。
- 状态：访客未绑定；剑雅默认书、`#cambridge-12`、`#jfdr-6`；阅读学习入口已渐进显示；阅读机经更多分组展开；移动端目录抽屉打开与关闭。

## Findings

- No actionable P0, P1, or P2 findings remain.
- 五个页面在三档视口均满足 `scrollWidth === innerWidth`，无页面级横向溢出。
- 剑雅听力、剑雅阅读和两类机经共用同一顶栏、题库侧栏、内容层级、进度与状态视觉；门户按题库分组后仍保持五个 IELTS 入口一键直达。
- 阅读 Test 保持平铺主路径；听力机经保持 Part 直达；未为高频操作增加手风琴或中间选择层。
- 375/768 下侧栏改为抽屉；选择题库、scrim 点击、关闭按钮与 Esc 均可关闭，正文滚动宽度不受影响。
- 57 组阅读机经默认显示 10 组，其余可展开；听力机经长目录独立滚动，虾滑听力分组可访问。
- 已刷状态、正确率、继续条、Reading Study 渐进入口、剑雅 hash 直达与 9 分达人分组均保留。
- Chrome DevTools 控制台在回归页无页面错误；课堂模式仍绕过学生绑定，访客模式仍要求先绑定，未绑定学生不渲染继续条。

## Engineering Guardrails

- 公开 URL 与 Flask endpoint 未改。
- `test_practice.html`、`jijing_part.html`、`player.html` 及阅读做题模板与改版前一致。
- `app.py` 只增加目录纯函数调用与模板数据；新聚合逻辑全部位于 `api/practice_catalog.py`。
- 判分与提交代码未改；旧听力专用类前缀、旧 JS/样式文件名与旧模式导航组件引用均为零。
- 完整测试：229 tests passed。

final result: passed

---

# TOEFL Formal Exam UI Design QA

## Comparison Target

- Source visual truth:
  - `/Users/zhouxin/Desktop/studytracker/tmp/pdfs/toefl_ui_refs/reading/page-03.png`
  - `/Users/zhouxin/Desktop/studytracker/tmp/pdfs/toefl_ui_refs/writing/page-1.png`
  - `/Users/zhouxin/Desktop/studytracker/tmp/pdfs/toefl_ui_refs/og/page-015.png`
- Implementation:
  - `http://127.0.0.1:5001/toefl/test/2026-01-21_A/reading`
  - `http://127.0.0.1:5001/toefl/test/2026-01-21_A/writing`
- Implementation screenshots:
  - `/Users/zhouxin/Desktop/studytracker/tmp/design-qa/reading-implementation.png`
  - `/Users/zhouxin/Desktop/studytracker/tmp/design-qa/writing-implementation.png`
  - `/Users/zhouxin/Desktop/studytracker/tmp/design-qa/reading-mobile-final.png`
- Viewport: desktop 1280 x 720; mobile 390 x 844
- States: Reading multiple choice question 4; Writing build-a-sentence question 1

## Full-View Comparison Evidence

- `/Users/zhouxin/Desktop/studytracker/tmp/design-qa/reading-comparison.png`
- `/Users/zhouxin/Desktop/studytracker/tmp/design-qa/writing-comparison.png`

The implementation matches the source hierarchy: thin teal section divider, section/question status at left, timer at right, large white exam canvas, Reading split pane, Writing centered prompt, real circular speaker imagery, answer line, and word bank.

## Focused Region Evidence

Separate crops were not required because both comparison images retain the source and implementation at the same 720-pixel height. The toolbar, status strip, Reading option controls, Writing avatars, answer line, and word tokens remain legible in the combined files.

## Findings

- No actionable P0, P1, or P2 findings remain.
- Fonts and typography: Arial/Helvetica UI text and Georgia passage text preserve the official hierarchy and reading density. Weight and wrapping remain legible at desktop and mobile widths.
- Spacing and layout: desktop split panes and Writing dialogue rows match the source composition. Mobile has no page, toolbar, or passage horizontal overflow.
- Colors and tokens: white canvas, dark toolbar, charcoal text, and restrained teal dividers follow the official screenshots while retaining Sage Path branding.
- Image quality: Writing uses speaker portraits extracted from the provided real-question PDF rather than placeholders. Crops remain sharp at the rendered 72-pixel size.
- Copy and content: test chrome is concise and exam-specific. Dynamic question content comes from the imported structured source.
- Interactions: Help, Review, Back, Next, timer hiding, Listening must-answer behavior, module audio, word ordering, undo, free writing, and submission feedback were exercised.
- Accessibility: controls are semantic, focus-visible styles are present, images have alt text, inputs are labeled, and mobile tap targets remain usable.

## Patches Made During QA

- Hid the Listening audio drawer on Reading and Writing pages.
- Replaced oversized speaker placeholders with cropped source portraits and source-matched dialogue spacing.
- Removed duplicated Writing directive text.
- Removed mobile toolbar and passage horizontal scrolling.
- Verified Reading Review navigation, Listening forward-only navigation, must-answer modal, Writing token selection and undo, and responsive width.

## Follow-up Polish

- P3: add source-matched toolbar icons if a licensed official icon asset set becomes available.
- P3: preserve richer social-post or notice artwork when future structured imports include clean image regions alongside text.

final result: passed

---

# Parent Practice Detail Design QA

## Comparison Target

- Source visual truth: `/Users/zhouxin/Downloads/87.jpg`
- Implementation screenshot: `/tmp/studytracker-parent-detail-qa.png`
- Combined comparison evidence: `/tmp/studytracker-parent-detail-comparison.png`
- Viewport: WeChat DevTools iPhone 12/13 simulator
- State: parent guest demo, completed vocabulary dictation task

The source is the existing parent report screen rather than a detail-screen mock. The comparison therefore checks design-system continuity and information hierarchy, not pixel identity between different screens.

## Focused Region Evidence

The combined comparison keeps the source overview card and the implementation result, summary, feedback, filters, and first word card legible. A separate crop was not needed.

## Findings

- No actionable P0, P1, or P2 findings remain.
- Fonts and typography: the implementation preserves the source's bold section hierarchy, compact gray metadata, and large teal result number without clipping.
- Spacing and layout rhythm: 28-30rpx page/card spacing, 24rpx radii, four-column metrics, and stacked white cards match the source density and remain readable on the simulator width.
- Colors and visual tokens: pale green page background, white cards, teal emphasis, and restrained semantic status colors remain consistent with the parent report.
- Image quality and asset fidelity: this state contains no decorative image assets; the UI does not substitute placeholders or generated artwork.
- Copy and content: the first screen answers the parent's questions directly with assigned/tested/correct/review counts, mastery context, teacher feedback, filters, and word-level evidence.
- Interaction states: filter controls, image preview, audio playback, retry, pull-to-refresh, and home-to-detail navigation are implemented. Automated API tests cover linked and unlinked parent access.

## Patches Made During QA

- Added a dedicated parent detail route instead of crowding the overview timeline.
- Added task-type-aware summary metrics and result filters.
- Added explicit pending-review treatment for subjective answers.
- Added latest-attempt and spaced-review mastery context for vocabulary tasks.

## Follow-up Polish

- P3: a future exact detail-screen mock could refine the lower word-card density beyond the currently visible first viewport.

final result: passed
