# Practices 学生端交互与题目渲染审计

更新日期：2026-08-28
工作树：`/Users/zhouxin/.codex/worktrees/practices-interaction-refactor`

## 路由链路

1. 学生在 `/practice` 绑定姓名；前端调用 `POST /api/listening/verify`，后端把姓名写入轻量 session，`GET /api/practice/identity` 用于恢复绑定状态。
2. `/practice` 进入听力/阅读目录：
   - 剑雅听力 `/listening/tests`
   - 剑雅阅读 `/reading/tests`
   - 听力机经 `/listening/jijing`
   - 阅读机经 `/reading/jijing`
   - 精听目录 `/listening`
3. 做题与精听：
   - 听力整套/Part `/listening/test/<test_id>?section=N`
   - 阅读整套/Passage `/reading/test/<test_id>?passage=N`
   - 听力机经 `/listening/jijing/<part_id>`
   - 阅读机经仍复用阅读做题页
   - 精听 `/listening/<exercise_id>`
4. 提交继续使用现有接口：
   - `POST /api/listening/test/<test_id>/submit`
   - `POST /api/reading/test/<test_id>/submit`
   - `POST /api/listening/jijing/<part_id>/submit`
   - 精听任务继续使用现有 segment progress 接口。
5. 复盘不新增路由：提交后在当前页面进入 `result-mode`；再次进入时通过现有 submission/history 接口恢复成绩和逐题结果。

## 返回与状态审计

改造前，目录和练习页之间主要依赖固定 `href`；精听固定返回 `/listening`，听力/阅读做题页把返回链接放在标题说明内。浏览器后退没有统一退出钩子，也没有结构化保存目录筛选、展开套题和滚动位置。

现在由 `static/js/practice_shell.js` 统一处理：

- 进入做题页前写入 `returnContext`：`sourcePath`、`sourceSearchParams`、`studentId`、`activeTab`、`filters`、`page`、`scrollPosition`、`sourceMode`、`targetPath`。
- 页面返回按钮和浏览器后退都调用同一个保存/退出流程，不调用 `history.back()`。
- 返回目录时恢复书籍 hash、筛选控件、展开的 `data-test-id` 套题和滚动位置。
- 普通练习直接保存后返回；模考由同一壳层显示“退出并保存进度”对话框。
- 听力、阅读、机经和精听顶部统一显示保存中、已保存或保存失败重试状态；无上下文时使用各自稳定目录作为 fallback。
- 答案仍写入原有本地草稿键；输入 debounce、`pagehide` 和 `visibilitychange` 会补充 flush。

## Cambridge IELTS 7 Test 2 Q4-Q8 根因

原始 `static/listening_tests/ielts7_test2.json` 的 Q4-Q8 题号、答案和题目 ID 没有乱序。问题位于 Web 渲染层：`collect` 字符串用大量 `&nbsp;` 模拟纸质双栏；旧代码直接正则替换 `$question_id$` 占位符，把不同视觉单元格压进同一个文本流。最终 DOM 因而把 “Previous insurance company” 和理赔问题拼接，并按纸面横向文本顺序形成 Q6、Q8、Q7 的错误阅读顺序。不是 React/Vue、响应式 CSS或后端判分问题。

`static/js/practice_renderers.js` 现在先把题面拆成带行号、栏位、标签和 question marker 的语义 cell，再按题号生成独立 field。通用规则得到以下顺序，无书号、Test 或题号特判：

- Q4 Previous insurance company
- Q5 Any insurance claims / Yes / No + accident details
- Q6 other driver name
- Q7 relationship
- Q8 car use（保留 `- social`）
- Start date 和 Recommended Insurance arrangement 在 Q9 前成为独立语义块

同一渲染器还会移除紧邻占位符、与当前题号相同的 OCR 残留，因此原始 Q9 的 `Name of company: 9【】` 不再显示多余的 `9`；原 JSON 未被改写。

### 批注复核：语义拆分不能破坏题面连续性

初版语义渲染把每道 form/note completion 题包装成独立卡片，并在没有真实字段名时显示
`Q7 · Question 7`；无占位符的 `• take a picnic`、`• 17th, from 10 a.m. to 3 p.m.` 等行又被当成分节条，
造成原本连续的 notes 像一组互不相关的小题。复核后改为两种明确布局：普通 notes 使用单列连续讲义流，真正含纸面双栏
空白的 form 才使用双栏；仅真实粗体标题产生分节，普通提示/日期继续留在所属段落；题号由输入框的 placeholder 和
无障碍名称承担，不再生成 `Question N` 兜底标题。该规则扫描听力/阅读数据中的 195 个 form group、1,476 个输入位，
每个题目仍恰好渲染一个控件。

## 题型与复盘布局

- Form/Table：语义 field/table、可换行、响应式输入宽度；桌面双栏，窄屏按题号单栏。
- Map：桌面约 3:2 地图/题目分栏，图片 `object-fit: contain`，支持放大、缩小、重置、全屏和放大后拖动；窄屏上下排列。没有坐标数据时不虚构热点。
- Matching：选项库只渲染一次并 sticky；每题独立一行、下拉选择、明确清除按钮，长文本自然换行。
- Reading：桌面文章约 56%、题目约 44%，两侧独立滚动；点击题号只滚动题目面板。窄屏使用“文章 / 题目”切换并保留两侧 scrollTop。
- Review：每题附近显示文字化的正确/错误/未作答、学生答案、正确答案和现有解析；支持当前题、展开全部、只看错题和题号联动。题号导航同时用文字提示、边框形状和状态标记，不只依赖颜色。
- Audio：切题、展开解析和切换视图不替换 `<audio>` 节点；真实浏览器检查中切换到 Q7 前后 `src` 保持不变。

## 验证结果

- Node 单元/组件测试：`node --test tests/test_practice_renderers.js tests/test_practice_shell.js`，6/6 通过。
- Python 路由/组件/E2E 契约：`python -m unittest tests.test_practice_interaction_e2e tests.test_reading_practice_layout tests.test_practice_workspace_regression`，10/10 通过。
- 内置 Chromium E2E：目录 → Q4-Q8 输入 → 自动保存 → 页面返回 → 目录 hash/展开状态恢复 → 再进入答案恢复 → 浏览器后退；提交后点击 Q7，Q7 卡片定位并展开解析，均通过。
- 地图题 `ielts11_test2` Section 2：地图/题目无重叠、`object-fit: contain`、zoom transform 生效。
- 配对题 `ielts10_test3` Section 2：1 个 sticky 选项库、5 行题目、无重叠。
- 阅读：文章和题目 `overflow-y:auto`，左侧保持 scrollTop 420；点击 Q7 后只移动右侧。390×844 下文章/题目切换保留两侧位置。
- 元素边界矩阵：1280×800、1440×900、1920×1080、1024×768、1180×820、820×1180、768×1024、390×844 均无 form field 重叠，输入框最小实测宽度 168px，底部预留 96px（手机 140px）。1600×1000、1024×768、约 853px 宽分别覆盖 80%、125%、150% 的等效 CSS 视口。批注修正后又在 1492×1321 与 390×844 复核 IELTS 17 Test 1 Section 1：Q7 无重复标题，日期行与 Q10 连续，桌面和手机均无横向溢出。
- Safari 实机抽查：Q4-Q8 语义顺序、输入控件、固定顶/底栏正常。
- Google Chrome 实机抽查：阅读双栏、独立滚动区、底部题号导航正常。

## 未验证项与现有数据问题

- 没有可连接的华为平板真机；已用 Chromium 平板横/竖屏尺寸和窄屏切换覆盖，但不能声称完成该设备的真机验收。
- 本地仓库缺少 `static/listening/ielts7_test2_s1.mp3`，因此该样例的音频请求在本地为 404；精听元数据和页面交互仍可验证，生产音频部署状态本轮未检查。
- 本地数据库没有 `reading_passage_analysis` 表，渐进增强的 Reading Study catalog 请求返回 500；阅读做题与本次分屏不依赖该接口。本轮未执行数据库迁移。
- 现有地图题数据没有可用的题目热点百分比坐标，因此复盘只在题目列表显示结果，没有编造地图高亮位置。
- 未执行生产部署、生产数据库写入、小程序上传/提审/发布。
