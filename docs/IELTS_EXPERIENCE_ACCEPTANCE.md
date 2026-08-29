# IELTS on Computer 体验验收

更新日期：2026-08-29
基准：[`IELTS_EXPERIENCE_BASELINE.md`](IELTS_EXPERIENCE_BASELINE.md)
模式边界：[`SIMULATION_PRACTICE_MODE_MATRIX.md`](SIMULATION_PRACTICE_MODE_MATRIX.md)
浏览器证据：[`evidence/ielts-experience-2026-08-28/README.md`](evidence/ielts-experience-2026-08-28/README.md)

## 状态口径

- `PASS`：有自动化及本机真实浏览器证据；不等同已部署。
- `PARTIAL`：主要逻辑具备，但仍有设备、内容或端到端证据缺口。
- `FAIL`：存在直接阻断发布的已知问题。
- `UNVERIFIED`：尚无足够证据，不能按通过计算。

当前候选的 P0 交互代码已经收口，但发布总判定仍为 **NO-GO**：全库扫描发现一套 Reading 合卷只有 39 题；华为真机和完整时长端到端流程也尚未验收。不得把“本机候选通过自动化”表述为已完成、已上线或与正式 IELTS 完全等价。

## A. 官方差异与修复状态

| 严重度 | 差异 / 要求 | 当前状态 | 证据与边界 |
|---|---|---|---|
| P0 | Listening 必须预检全部媒体后，由一次用户动作开考 | PASS（本机） | 四个 Part 的 URL、metadata、duration 全部有效后才启用开始；失败则留在预检页。 |
| P0 | Listening 单次连续播放，不可暂停、seek、调速、重播，切 Part 不换媒体节点 | PASS（本机） | Simulation 只创建一个无原生 controls 的 `<audio>`；锁定 seek/pause/rate，`ended` 才推进；浏览器切 Part 后 `src` 未变且继续播放。 |
| P0 | Simulation 不得泄露答案、解析、原文、评分或训练能力 | PASS（本机） | 服务端递归剥离答案/解析/Transcript；模板不创建 score、review、training、transcript DOM；HTML 契约和浏览器检查通过。 |
| P0 | 计时、刷新恢复、截止提交由服务端掌握 | PASS（逻辑/浏览器） | 开考幂等；刷新不能加时；过期后客户端新答案被忽略并以最后服务端草稿结算；Listening 播完只会把已有截止时间收紧到最多 2 分钟，不会延长。 |
| P0 | Reading/Listening 草稿具备服务端恢复 | PASS（本机） | 本地即时草稿 + 服务端防抖/pagehide 保存；浏览器实际写入并从 GET 恢复 Reading Q1 与 Listening Q1。 |
| P1 | Reading 为文章/题目双栏并独立滚动，切题不重置文章位置 | PASS（桌面） | Simulation 采用约 50/50 双栏，左右滚动独立；真实 Chromium 1280×720 证据通过。移动端保留适配切换，不作为正式考场桌面等价证据。 |
| P1 | 考试模式只有必要导航与标记，不出现评分栏、重做、学习提示或地图缩放工具 | PASS（本机） | capability 集中控制；Simulation DOM 不创建相应节点；地图 zoom 在 Simulation 禁用。 |
| P1 | 10/5 分钟提示与题号状态清晰 | PASS（本机） | 服务端剩余时间驱动提示；当前、已答、未答、待检查同时有文字与状态 class。 |
| P1 | 配对/地图尽量保留真实任务形式 | PARTIAL | 共享选项池和专用地图工作区已恢复；源数据缺少 drag-to-gap/热点坐标时仍只能用选择控件回退，不能伪造坐标。 |
| P0 | 每套完整 Listening/Reading 必须恰有 40 题 | FAIL | 全库唯一阻断：`reading_jijing_83_test_95.json` 为 1–39，共 39 题。[可查题页](https://completeielts.com/ancient-societies-classification/)显示第三篇 *Ancient Societies Classification* 本身止于总体 Q39；缺失 Q40 不能凭空补造，需回到合卷原始来源修复。 |

## B. 15 项核心验收

| # | 验收项 | 状态 | 证据 / 未完成项 |
|---:|---|---|---|
| 1 | 整套 Listening 无需刷新 | PASS（本机） | 单一播放列表节点串联四个 Part。 |
| 2 | 播放无中断、重载、归零 | PASS（本机） | 切题/切 Part 不改 `src`；刷新按服务端已过时间映射到播放列表位置。 |
| 3 | Simulation 只播放一次 | PASS（本机） | 无暂停、seek、rate、replay 入口；事件层回滚非法操作。 |
| 4 | 可查看并修改全部答案 | PASS | Previous/Next、Part/Passage、题号导航、标记与草稿恢复均可用。 |
| 5 | 当前/已答/未答/待检查明确 | PASS | class、`data-state` 与 aria-label 同步，不只靠颜色。 |
| 6 | 提交前看不到答案和评分 | PASS（本机） | 公共 payload 无答案字段，Simulation DOM 无复盘与评分节点。 |
| 7 | Reading 同时使用文章和问题 | PASS（桌面） | 双栏独立滚动截图与浏览器断言通过。 |
| 8 | 切 Reading 题时文章位置稳定 | PASS | 左侧 `scrollTop` 保留，右侧定位题目。 |
| 9 | 题型保留任务形式 | PARTIAL | form/note/table/matching/map 有专用结构；无坐标的数据不能完全复刻拖放。 |
| 10 | 无考试外训练工具 | PASS（本机） | Simulation capability 和 DOM 双重隔离。 |
| 11 | 无评分栏/装饰卡片/学习提示干扰 | PASS（本机） | 浏览器节点计数为 0；考试工作区使用平直边界。 |
| 12 | 页面自身可解释操作 | PASS（本机） | 预检、播放状态、计时、导航、标记、保存与结束提示均在页面表达。 |
| 13 | 键盘和鼠标完成整套 | PARTIAL | 控件标签、键盘输入与焦点契约具备；完整 40 题真实键盘流程未录制。 |
| 14 | 返回/刷新不丢考试状态 | PASS（本机） | 退出确认、本地草稿、服务端草稿、服务端时钟恢复均已覆盖。 |
| 15 | 40 题稳定提交 | PARTIAL | 提交/截止/幂等自动化通过；完整时长浏览器录制和 39 题坏包修复前不能全局 PASS。 |

## C. 四种模式隔离

| 模式 | 唯一 mode | 允许能力 | 浏览器结果 |
|---|---|---|---|
| Simulation | `simulation` | 作答、导航、标记、保存、受控计时/音频 | 无答案、原文、解析、评分、重做、音频控制；通过。 |
| Practice | `practice` | 自主音频控制、作答、保存、提交 | 提交前没有复盘卡；通过。 |
| Intensive Listening | `intensiveListening` | 定位、重听、听写、显示原文等训练能力 | 独立播放器只激活该模式；通过。 |
| Review | `review` | 原题、学生答案、正确答案、解析、错题状态 | Practice 成功提交后才切入；40 张复盘卡浏览器验证通过。 |

`practice_modes.js` 强制四个显式标志中恰有一个为真；能力表是显示/挂载训练和评分功能的唯一入口。模式解析及能力契约有独立 Node 测试。

## D. 全库内容与资源门禁

执行：

```bash
/Users/zhouxin/Desktop/studytracker/.venv/bin/python scripts/check_ielts_practice_library.py \
  --audio-root /Users/zhouxin/Desktop/studytracker/static/listening
```

扫描结果：84 套 Listening、129 套 Reading、8,519 题、336 个非空且可被 `ffprobe` 读取时长的音频、48 张引用图片。JSON、容器、题号唯一/连续、声明题号、占位符、图片和音频检查均通过，只有以下 P0：

```text
P0 not_full_40_question_test static/reading_jijing/reading_jijing_83_test_95.json: count=39, range=1-39
```

因此全库门禁返回非零，发布必须保持 NO-GO。音频根位于桌面主工作树的本机共享资源，不在 Git 中；另一台电脑或干净 clone 不能从仓库自动取得这些 MP3。

## E. 自动化与真实浏览器证据

- 全仓 Python：`593 passed, 61 subtests passed`。运行时为隔离 worktree 挂接桌面主工作树已有的 `ielts10_test1_s1.mp3` 测试夹具；未挂接时唯二失败是该文件 404 的静态 Range 既有测试。
- 新增/目标 Python 文件 Ruff：通过；`git diff --check`：通过。
- Node 模式、renderer、shell、锁定音频：`15/15 pass`；四个相关 JS `node --check`：通过。
- 浏览器确认 Simulation HTML 无答案/解析/Transcript 字段；Listening 只有一个无 controls 音频节点，预检显示 4 Part / 25:19，开始后切 Part 不更换 `src`；Reading 双栏、题号状态和无训练 DOM 通过。
- 浏览器确认 Practice 提交前无复盘；提交成功后进入 Review 并显示学生答案、正确答案、原文和解析；精听独立页面处于 `intensiveListening`。

## F. 尚缺的真实体验证据

- [ ] 华为平板横屏/竖屏真实 Chrome 或系统 WebView。
- [ ] Safari 与 Chrome 各一次完整 40 题键盘/鼠标流程。
- [ ] Listening 从预检开始，完整播放约 25 分钟，自动进入 2 分钟检查并提交的连续录像；当前是单元/路由测试和中途浏览器观测，不冒充全时长证据。
- [ ] Reading 从 60 分钟开考到三篇提交的连续录像。
- [ ] 13 英寸 MacBook Air 首次进入、输入/切题延迟、长任务内存和音频节点挂载次数。
- [ ] 80% / 100% / 125% / 150% 缩放下完整答题，而非仅布局抽查。

## G. 发布判定

当前：**NO-GO**。

进入发布候选至少还需：

1. 从可信合卷源补齐或重新组装 `reading_jijing_83_test_95.json`，使完整测试为 40 题，并让全库 gate 返回 0；不得发明第 40 题。
2. 完成华为真机和上述完整时长流程证据。
3. 复核生产机 5002、单 worker / gthread / 6 threads，并在得到用户明确授权后再 commit、push、deploy；本轮尚未执行这些动作。
