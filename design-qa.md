# 登录入口重设计 Design QA

日期：2026-08-30
目标页面：`/login`、`/practices`（未登录状态）

## Comparison target

- 唯一视觉事实源：`/Users/zhouxin/.codex/generated_images/01a04fe9-7e5f-7241-b5b2-b40aa7ab0774/exec-01c10a36-c06f-4f20-91b1-6669bf07840e.png`
- 最终实现截图：
  - `/tmp/studytracker-auth-release-qa/login-desktop-1440x1024.png`
  - `/tmp/studytracker-auth-release-qa/login-mobile-390x844.png`
  - `/tmp/studytracker-auth-release-qa/practices-desktop-1440x1024.png`
  - `/tmp/studytracker-auth-release-qa/practices-mobile-390x844.png`
- 初始实现证据：`/Users/zhouxin/Desktop/studytracker/artifacts/auth-entry-20260830/login-desktop-v1.png`
- 对比方法：在同一次原始分辨率图像查看输入中并列载入 1440×1024 视觉参考与最终 `/login` 截图；浏览器截图均使用用户指定真实视口，未做拉伸或裁切。

## Viewport and measured surfaces

- 桌面：1440×1024；品牌栏 110px，左右分栏 49% / 51%，表单宽 560px，输入框 66px，主按钮 62px，学生入口 118px；页面 `scrollWidth === innerWidth` 且无纵向滚动。
- 手机：390×844；品牌栏 82px，主视觉隐藏，表单优先；输入框 58px，主按钮 58px；两个页面均 `scrollWidth === innerWidth`，主按钮在首屏可达。
- 桌面 `/login` 关键位置：表单 x=814；用户名输入 y=372；密码输入 y=508；主按钮 y=627；学生入口 y=772。参考图对应位置约为 x=815、y=375、y=513、y=624、y=775。

## Findings and comparison history

1. 初始实现：
   - P2：左侧品牌文案比参考图向左约 33px，字号略大。
   - P2：右侧表单比参考图向左约 21px，后半段控件整体偏上约 20–30px。
   - P2：首个输入框因 `autofocus` 呈现焦点描边，和参考图静态状态不一致，手机端也可能在载入时立即弹出键盘。
2. 修复：
   - 将品牌文案锚点调到左栏 15.4%，缩小标题上限并上移约 9px。
   - 将桌面表单左侧锚点调到 x≈814，重新校准表单与字段间距。
   - 移除自动聚焦，保留真实 `label`、键盘可见焦点和密码按钮的无障碍状态。
3. 最终对比：
   - 品牌栏、分栏、Logo、标题、表单、按钮、学生入口和主留白均与参考图进入同一构图范围。
   - 生成楼梯图保持暖白、自然光和浅色弧形楼梯主体；其具体台阶与扶手形状并非对参考图像素复制，这是遵守“生成独立干净素材、不得裁切整张界面图”的有意差异。
   - `/login` 额外保留了业务需要的课堂入口，并按要求降为底部辅助文字链接。
   - `/practices` 共享同一品牌壳层，只替换为姓名验证内容；验证后的练习目录仍为原实现。

## Interaction, accessibility, and runtime checks

- 密码显示按钮：点击后 `type=text`、`aria-pressed=true`、`aria-label=隐藏密码`。
- 错误状态：账号错误由 Flask flash 返回并显示；姓名为空和姓名不存在均在 `role=alert` 区域显示，按钮会恢复可用。
- 学生入口链接固定为 `/practices`；课堂入口 `/classroom` 保留；员工入口返回 `/login?next=/practices`。
- 浏览器控制台：两个页面均 0 error、0 warning。
- 两套页面使用真实表单、真实标签、非颜色单独表达的错误文案、至少 58px 的移动触控控件，并尊重 `prefers-reduced-motion`。

## Final findings

- P0：0
- P1：0
- P2：0
- 可接受差异：楼梯为新生成的独立照片素材；登录页保留参考图未显示但业务仍需要的低调课堂入口。

final result: passed

---

# Vocabulary answer-feedback design QA

## Comparison target

- Source visual truth: `/Users/zhouxin/Downloads/IMG_0223.PNG`
- User-directed changes to that source: remove the empty pale-green result keyboard shell; resize the result CTA to a balanced standalone control; add post-answer memory support without exposing it before submission.
- Rendered implementation:
  - `/Users/zhouxin/.codex/visualizations/2026/08/10/studytracker-vocabulary-feedback/final-top.png`
  - `/Users/zhouxin/.codex/visualizations/2026/08/10/studytracker-vocabulary-feedback/final-bottom.png`
- Combined comparison evidence: `/Users/zhouxin/.codex/visualizations/2026/08/10/studytracker-vocabulary-feedback/comparison.png`

## Viewport and normalization

- Source pixels: `944 × 2048`; attachment corresponds to the iPhone 15 Pro Max portrait aspect.
- WeChat Developer Tools target: iPhone 15 Pro Max, portrait, CSS viewport approximately `430 × 932`, shown by the tool at 75% preview scale.
- Raw implementation crop: `248 × 538` pixels from the Developer Tools preview.
- Comparison copies: source and each implementation state normalized to `472 × 1024`; the combined comparison is `1416 × 1024`.
- Density/canvas normalization: surrounding Developer Tools chrome was cropped out; source, top implementation, and scrolled-bottom implementation use the same portrait aspect before comparison.

## State and interaction coverage

- Route: `pages/student/vocabulary-learning/index`.
- State: group 1/7, retry phase, `audio_to_en`, correct answer for `analyst`, full answer feedback available.
- Verified top and scrolled-bottom states so both the memory card and result CTA were visible at the intended mobile width.
- Verified the page scrolls to the CTA and the CTA remains fully reachable above the home indicator.
- Developer Tools compilation reported 0 errors. The retained warnings are existing/base-library notices; the deliberate unauthenticated setup request was removed from the final error count.
- Functional answer, refresh-restoration, no-leak, and next-item behavior are covered by automated tests; the visual fixture did not send a real answer or advance production state.

## Required fidelity surfaces

- Fonts and typography: retained the existing system font stack and established page hierarchy. Word, syllable, phonetic, labels, example, translation, and hint remain legible without clipping or awkward wrapping.
- Spacing and layout rhythm: the empty keyboard shell and its safe-area padding are gone. The result CTA is a standalone `520rpx` pill (about 70% of page width), with balanced space above and below. The longer feedback content scrolls naturally rather than compressing the card.
- Colors and visual tokens: retained StudyTracker green `#087f77`, existing success green, white card, and pale-green support surface. The pale-green surface now contains meaningful feedback rather than unexplained empty space.
- Image quality and asset fidelity: replay uses the repository's existing speaker icon asset; no placeholder, emoji, inline SVG, handcrafted SVG, or new raster asset was introduced.
- Copy and content: answer feedback adds target word, syllables, phonetic, core meaning, necessary collocation, one bilingual example, and optional usage note. Retry copy remains explicit that another error will not create an infinite loop.
- Responsiveness/accessibility: CTA and replay control retain at least `88rpx` height. Long English and Chinese content wraps. The CTA is reachable at the bottom of the iPhone 15 Pro Max viewport; `rpx` sizing keeps the same relative width on narrower phones.

## Findings

- No actionable P0/P1/P2 findings remain.
- The final layout intentionally differs from the source screenshot by adding the requested memory card and replacing the oversized empty keyboard shell with a content-free standalone CTA area.

## Comparison history

1. Initial source review:
   - P1: the English keyboard hid its keys after submission but left its pale-green shell and safe-area padding, creating a large empty block.
   - P2: the full-width CTA inside that shell had disproportionate visual weight.
   - Fix: render the keyboard only before submission and render a separate result CTA after submission.
2. First implementation review:
   - P2: percentage width resolved against a virtual WXML block and fell back to the `320rpx` minimum, making the CTA too narrow.
   - Fix: use a stable `520rpx` width and matching minimum, capped by `100%`.
3. Final comparison:
   - The empty shell is absent, the CTA is visually balanced, feedback content is readable, and no overlap, clipping, or unreachable control remains.

## Follow-up polish

- None required for this change. A physical-device pass after a future mini-program upload can reconfirm text density with the user's actual Dynamic Type setting.

final result: passed

---

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
