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
