# 听力源行与题干错位核查

本轮实施树：`/private/tmp/studytracker-cambridge-fix-20261107`，分支 `codex/cambridge-explanations-fix-20261107`，开工 HEAD `be9b122f`、工作区 clean。最初只读对照后，主 agent 根据用户桌面反馈与真实页面复现授权本机修复 renderer 和专用测试。本 agent 不改题库、答案、后端、两交接；未执行 commit/push/deploy。CSS、浏览器与规范交接由其他 agent 负责。

## 确认的根因

原数据没有在本轮导入中丢行：72 套、568 组的 collect/table 与本机原始 raw 全部一致。63 张结构化表格的 68 个合并坐标引用均未越界；这项检查不等于已逐格复核所有合并单元格的视觉语义。

显示层将多个题目的共享 title 按空格拆分，再依据相邻题目切成不同显示行。两个空之间的字符串既包含前题尾句，也包含下题开头；旧实现把整段放到后一行，无法正确区分归属。按原 collect 的完整目标行核查，165 组 form/1252 题中有 677 处非空的空后文字，其中 19 题、13 套/题组有可复现的实质尾句移行，修后为 0。标点等无单词片段未计入这 19 题。

优先复现位置如下，完整 19 题及前后显示行见 JSON 的 `before.suffix_mismatches`：

| 套题及 Section | 题号 | 原源行归属 | 修前显示问题 |
| --- | --- | --- | --- |
| C13 T1 S4 | Q35 / 36 / 38 | `and to deal with new dangers` / `of urban and rural blackbirds` / `by producing lower levels of hormones` | 各尾句移到下一题开头 |
| C12 T6 S1 | Q7 / 8 | `House` / `dances` | 分别跑到 Q8 / Q9 行 |
| C14 T2 S1 | Q7 / 8 | `club` / `regularly` | 分别跑到 Q8 / Q9 行 |
| C12 T5 S1 | Q8 | `(can be hired)` | 跑到 Q9 行；Q7 后静态装备清单也被共享 title 拼入 |
| C13 T3 S4 | Q36 / 38 / 39 | `has been noted between parents and children` / `of the lizards` / `taken` | 跑到后题行 |
| C5 T3 S2 | Q14 | `who can give information and advice on` | 跑到 Q15 行，混入后续列表 |
| C8 T1 S4 | Q39 | `density, ocean floor etc.` | 跑到 Q40 行 |

另外确认三类同源问题：

- 32 组被认定为 columns，实际 31 组只是标签/值的纸面留白或同句多空。只有 C7T2S1 有独立左右题块（Q6 左、Q8 右、Q7 下一行左）；按题号相邻自动配两列反而会错配 Q6/Q7。经主 agent 确认，统一按题号阅读顺序纵向显示完整题块；同一源句内的多空保持同行，不逐空拆句。
- 57 条静态源行（21 组）中的标签/值被分别渲染成独立块。这里覆盖所有 form，范围大于展示探针仅关注 columns 的 10 组。现按同一 source line 合并；例如 C18T1 的 `Name: Sadie Jones` 与 `Year of birth: 1991` 各保留一行，57 条拆行候选修后为 0。
- 5 题的提取 title 重复紧邻其前的原始说明行：C13T1Q34、C15T1Q36、C15T4Q38、C6T4Q21、C9T1Q36。仅当 title 与“紧邻前源行 + 当前完整目标行”词序完全相等时改用目标源行；前导说明仍在原位置，避免泛化删除别处同文。另 source cluster 中不再重印仅从拼接 title 推断出的 label，避免 C12T7 的 Claire 调查标题重复。

## 修复策略与边界

`sharedSourceRows` 只有在源跨度包含 cluster 全部 ID、顺序正确、每个恰好一次且无外部 ID 时，才使用原 collect 的逐行结构。完整保留空前空后文字、同句多个输入和题目之间的静态说明。39 个共享簇、102 题中有 23 个跨源 cell；全部目标源句修后完整，75 条含题源行的空格归属保持。独立 review 另验证这 39 个跨度内含 11 条中间静态行，合计 86 条源行顺序完整。

源跨度缺失、逆序或含未知 ID 时，不再尝试猜测分行；完整共享 title 作为一个连续块显示，各输入仍为独立逻辑题目。旧“单题双空”路径与保存/评分规则未修改，之前审定的电影名、数字方框、题干分词等保留。

静态标签与值仅按其共同源行组合；C7T2 的 Uses of car 标题置于其 `- social` 上方/前方，Q6/Q7/Q8 仍按题号连续。U+2212 `−` 仅增加为项目符号识别，防止 C18T1 的 poaching laws 等误用小标题样式。

本 agent 业务文件范围为：

- `static/js/practice_renderers.js`
- `tests/test_cambridge_line_layout.js`（新增 11 项）
- `tests/test_practice_renderers.js`（仅旧 columns 断言改为 flow）

未改任何题库 JSON、题干、选项、答案、题号、ID、评分实现或历史成绩。所有判断为源行/结构层面，不能据此宣称 2880 题全部语义或全部图表已人工终审。

## 复现与验证

```sh
cd /private/tmp/studytracker-cambridge-fix-20261107
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-layout-20261107/listening-layout-source.py
node --test tests/test_cambridge_line_layout.js tests/test_practice_renderers.js tests/test_cambridge_stem_controls.js
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_cambridge_pair_grading -q
node --check static/js/practice_renderers.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check --target-version py310 docs/reviews/cambridge-layout-20261107/listening-layout-source.py
git diff --check
```

60 项 Node 通过，包含 11 个新增行归属回归、全 144 套控件 ID/题号/唯一性和既有双空测试。跨真实 JS 序列化至 Python 的 130 个 ordinary/simulation 场景通过（1 项 unittest）。源审计、JS 语法、目标 Ruff 与 diff 检查通过。

`listening-layout-source.py` 从固定 `be9b122f` Git 对象取得旧 renderer，与当前 renderer 使用同一套当前数据对照；JSON 同时保存 before/after、raw SHA 和当前 renderer SHA。只读本机源数据，不导入 app、不触碰 DB、不调用网络。报告当前仅本机，最终提交与部署状态以主 agent 后续交接为准。
