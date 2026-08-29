# IELTS on Computer 体验基准

更新日期：2026-08-28（Asia/Shanghai）
适用范围：StudyTracker 网页端 IELTS Listening / Academic Reading 的模拟、练习、精听与复盘

## 1. 证据规则

本基准只记录官方 IELTS、British Council、IDP 当前公开材料以及当前可访问的官方熟悉测试。不得用第三方产品覆盖官方逻辑，也不得复制官方品牌、Logo、图标、素材或页面代码。

每条结论分为三档：

- **正式规则已确认**：当前官方文字或教程明确描述正式考试行为，可作为模拟模式实现要求。
- **熟悉测试实测**：2026-08-28 在官方 Inspera 熟悉测试中实际操作确认；但官方明确说明该熟悉测试未计时，且计时、高亮、笔记与正式考试不同。
- **未确认**：没有足够官方证据。实现不得猜测；可以保留稳定的既有行为，但不能宣称与正式考试一致。

## 2. 官方来源

### 当前主来源

1. [IELTS Academic sample test questions](https://www.ielts.org/take-a-test/preparation-resources/sample-test-questions/academic-test)：官方题型清单、Listening 一次播放、熟悉测试入口及其差异声明。
2. [IELTS Listening 熟悉测试](https://demo-ielts.inspera.com/player/?assessmentRunId=131012334&context=exam)：2026-08-28 实测页面结构、题型、Part/题号导航和一次播放提示。
3. [IELTS Academic Reading 熟悉测试](https://demo-ielts.inspera.com/player/?assessmentRunId=131013388&context=exam)：2026-08-28 实测双栏、独立滚动、题型与题号状态。
4. [British Council: IELTS on computer](https://takeielts.britishcouncil.org/what-is-ielts/how-it-works/test-modes/ielts-on-computer)：正式考试的计时、音量、笔记、高亮/下划线和前后导航能力。
5. [IDP: How IELTS on computer works](https://ielts.idp.com/canada/prepare/article-how-computer-delivered-ielts-works)：正式界面的时钟、Review 标记、Settings、Reading 双栏、自动保存和 Listening 音量/复查行为。
6. [IDP: IELTS on Computer interface](https://ielts.idp.com/indonesia/about/which-test-do-i-take/computer-based-ielts/en-gb)：时钟的 10/5 分钟提醒、底部导航、Review、Settings、Help、Hide。
7. [IDP IELTS Focus — Listening（PDF，第 56 页）](https://info.ielts.idp.com/rs/561-EIU-022/images/IELTS%20Focus%20-%20Listening%20-%20Student%20Updated.pdf)：Listening 不可暂停/重启、音量位置、Part 前后时间、最终 2 分钟复查、无拼写检查。
8. [IDP: Highlighting in IELTS on Computer](https://ielts.idp.com/bangladesh/about/which-test-do-i-take/ielts-on-computer/how-to-highlight-text)：Listening/Reading 可选择文字并通过右键高亮、取消高亮。

### 重要限制

官方熟悉测试页面明确说明：它是接近正式考试的练习体验，但**未计时**，且 **timer、highlighting、notes 的行为与正式考试不同**。因此：

- 熟悉测试没有倒计时，不能推导正式考试没有倒计时。
- 熟悉测试的 `Show notes` / annotation sidebar 不能直接复制成正式考试笔记交互。
- 熟悉测试的结束页和按钮文字只能用于理解流程，不能作为正式提交文案的唯一证据。

## 3. 正式考试体验基线

### 页面顶部信息结构

- **正式规则已确认**：屏幕提供剩余时间；正式资料还确认 Settings、Help、Hide 和 Listening 音量控制。
- **熟悉测试实测**：顶部包括连接状态、Options、Show notes、考生标识；Listening 播放后显示 `Audio is Playing`。这些文字和图标不应照搬。
- **StudyTracker 基线**：模拟模式顶部只保留当前科目/Part、服务端截止时间倒计时、保存状态、Listening 音量和低干扰退出。不得出现正确率、训练入口、学习建议或大面积品牌装饰。

### Section / Part 切换

- **正式规则已确认**：可通过底部题号导航和前后按钮在允许范围内移动；Reading 可在三篇之间自由移动。
- **熟悉测试实测**：Listening 底部为 Part 1–4，每个 Part 展开对应 10 题；Reading 为 13/13/14 题。点击 Part 后不发生整页刷新。
- **未确认**：正式 Listening 是否允许在音频播放过程中任意切换到所有尚未播放的 Part 页面。
- **StudyTracker 基线**：不得因切题或切 Part 重载音频；在未确认前，不用自由切 Part 来触发播放或重听。

### Listening 播放器与音量

- **正式规则已确认**：录音只播放一次，不可暂停，不可重启/重听；可在考试中调整音量；没有倍速控制。每个 Part 播放前有读题时间，Part 后有检查时间；四个 Part 结束后有 2 分钟最终检查时间。
- **熟悉测试实测**：开始前弹层明确提示不可暂停或倒带，只在点击 `Play` 后开始；播放后没有暂停或进度拖动控件，只显示播放状态。由 Part 1 切到 Part 2 时仍显示 `Audio is Playing`。
- **StudyTracker 基线**：开始前必须验证 URL、metadata、有效时长和可播放状态；准备失败时禁止开考。正式开始后只保留音量，不暴露暂停、seek、重听和倍速；切题不得替换音频节点或重置时间。
- **未确认**：正式客户端精确采用单条整轨还是多个受控媒体片段；StudyTracker 可按现有资源组织播放，但必须保证行为等价且只播一次。

### 计时与提醒

- **正式规则已确认**：屏幕显示剩余时间；10 分钟和 5 分钟时提供提醒，时间结束自动停止/提交当前科目。Listening 约 30 分钟并另有 2 分钟最终检查；Reading 为 60 分钟且没有额外转写时间。
- **StudyTracker 基线**：倒计时必须基于服务端 `deadline_at`，刷新后不得重置；前端计时只负责显示，服务端必须拒绝过期后的继续作答/伪造剩余时间。
- **未确认**：当前正式客户端提醒的精确颜色、动画、声音和文案；不得臆造声音警报。

### 题号导航和状态

- **正式规则已确认**：底部导航可点击题号跳转，也有 Previous / Next；可以前后返回和修改答案；Review 用于标记稍后检查。
- **熟悉测试实测**：题号有 `Not attempted`、`Attempted`、`Active` 语义；填入答案后当前题立即从未作答变为已作答；Part 标签显示已答数量；末端有 `Review your answers` 汇总入口。
- **正式规则已确认**：IDP 当前资料描述 Review 后题号从方形变为圆形；颜色/图形不能作为唯一状态信号。
- **StudyTracker 基线**：至少同时提供当前、已作答、未作答、待检查四种文字/无障碍语义；点击题号不整页刷新、不改变 Reading 文章位置、不影响 Listening 音频。

### Previous / Next 逻辑

- **熟悉测试实测**：第一题 Previous 禁用，Next 可用；点击 Part/题号只切换题目内容与当前状态。
- **StudyTracker 基线**：第一题禁用上一题、最后一题禁用下一题；按钮只负责题目导航，不能在非末题触发交卷。
- **未确认**：正式考试在题组跨页边界时的精确滚动落点与动效。

### 文本输入

- **正式规则已确认**：答案直接输入屏幕，无单独答题卡；没有拼写检查，考生自行检查拼写和字数限制。
- **熟悉测试实测**：填空框出现在表格/笔记/句子原本语义位置，以题号作为 placeholder，统一无障碍名为 `Insert answer`。
- **StudyTracker 基线**：关闭 `spellcheck`、自动更正和自动大写；输入框必须在原题语义位置；不得生成 `Question N`、`Fill answer` 等虚假题干。
- **未确认**：正式客户端是否对粘贴、浏览器自动填充或 IME 做额外限制。

### 单选与多选

- **正式规则已确认**：单选点击一个答案，多选点击题目要求数量的答案；正式提交前不显示正误。
- **熟悉测试实测**：TRUE/FALSE/NOT GIVEN 为原位 radio group；多选题保留题组说明和选项关系。
- **StudyTracker 基线**：单选使用互斥控件，多选强制题目规定的最大选择数；选择后立即更新“已作答”，不判分、不自动排除选项。

### 配对题

- **正式规则已确认 / 熟悉测试实测**：选项库与人员/陈述保持可见关联，答案被移动到对应 gap；更换答案时以新选项替换。
- **StudyTracker 基线**：数据暂不支持可靠拖放时可使用每题选择控件作为保守回退，但必须只显示一份选项库、保留配对关系并记录为体验差异；不得把选项库复制到每题。

### 地图 / 平面图 / 图示题

- **熟悉测试实测**：地图保持为一个完整图像，题号 gap 位于地图语义位置，候选标签从共享选项库移动到 gap；熟悉测试未显示自由缩放工具。
- **StudyTracker 基线**：模拟模式不得增加自由缩放、自动定位或答案热点高亮；没有可靠坐标时不伪造热点，使用保留地图与共享选项库关系的回退。
- **未确认**：正式考试是否在无障碍安排下提供额外图像控制。

### Reading 文章与问题工作区

- **正式规则已确认**：文章在左、问题在右，同时可见；当前 IDP 资料明确为 split-screen。
- **熟悉测试实测**：1280×720 视口下左区约 640px、右区约 638px；两区高度均约 489px，分别 `overflow:auto/scroll`，文章与题目独立滚动，中间有分隔控件。
- **StudyTracker 基线**：桌面以接近等分的双栏为默认，两侧独立滚动；切题只定位右侧题目，左侧 `scrollTop` 必须保留。窄屏可切换文章/题目，但必须分别保留位置，并明确这是设备适配而非正式考场布局。
- **未确认**：正式分隔条是否允许拖动以及可调范围。

### 高亮和笔记

- **正式规则已确认**：Listening / Reading 可选中文字，使用高亮/下划线；官方 IDP 指引描述右键选择 Highlight，并可取消；正式资料确认有笔记工具。
- **StudyTracker 基线**：模拟模式只在能够稳定保存、删除、跨题恢复且不改变题面 DOM 时启用。若可靠性未通过门禁，应明确记录缺口，不能提供经常丢失的假功能。
- **未确认**：正式客户端的笔记作用域、跨 Part 生命周期、字符上限和完整快捷键；熟悉测试 annotation sidebar 不可作为正式规则。

### 键盘 Tab 顺序

- **熟悉测试实测**：页面使用原生 textbox/radio/button，并提供可访问名称；题号导航和 Previous/Next 是可聚焦按钮。
- **StudyTracker 基线**：Tab 顺序必须遵循视觉阅读顺序，进入题组后按题号前进，不能被隐藏面板或底部导航困住；Enter/Space 可操作选择项和按钮。
- **未确认**：正式客户端所有顶栏、题面和底栏控件的精确完整 Tab 序列。

### 提交、复查与结束

- **正式规则已确认**：时间到自动结束；提交后当前科目结束，不能继续修改。Reading 可在提交前检查未作答与拼写。
- **熟悉测试实测**：`Review your answers` 打开 Table of contents，按 Part 显示已答数量，再通过顶部 Next 继续结束流程。
- **StudyTracker 基线**：做题过程不常驻“提交并判分”；末 Part/Passage 才出现结束科目操作，并二次确认不可逆结果。超时自动提交；网络失败必须保留答案并提供可重试状态，不能清空。
- **未确认**：正式客户端手动提前结束时的精确确认文案、是否二次确认以及监考员参与流程。

## 4. 正式考试中不应出现的训练功能

模拟模式不得出现：

- 正确/错误、正确答案、分数、正确率、解析、原文定位、听力原文、AI 提示；
- 暂停、重听、拖动进度、倍速、单句循环；
- 精听、复习、Reading Study、即时反馈、错因笔记、题目难度、自动排除；
- 地图自由缩放、答案热点、自动定位正确原文；
- 右侧评分统计栏、已答统计卡片、装饰性大卡片和强品牌图形。

这些能力只能由模式 capability 明确开放，不能靠页面里分散的零散条件判断。

## 5. 当前无法确认、不得猜测的项目

1. 正式客户端的精确品牌布局、字体、像素、颜色和图标。
2. Listening 对尚未播放 Part 的页面访问限制。
3. 正式高亮/笔记的存储范围、恢复规则和完整快捷键。
4. Reading 中央分隔条是否可拖动。
5. 所有题型的完整 Tab 序列和屏幕阅读器提示词。
6. 正式提前结束科目的精确弹窗文案。
7. 无障碍安排下与标准机考不同的媒体/地图控制。

这些项目进入 `IELTS_EXPERIENCE_ACCEPTANCE.md` 的未确认/待真机项，不得为了“看起来完整”而实现猜测行为。
