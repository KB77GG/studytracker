# Practices 模块架构审查与题型专项实现

审查日期：2026-08-29
工作树：`/Users/zhouxin/.codex/worktrees/practices-interaction-refactor`
分支 / 基线：`codex/practices-interaction-refactor` / `f8152ff01df98d04cca9860d31d49b8e2697aaef`

## 结论

当前实现属于 **B/D：部分共享渲染器，同时存在平行实现**，不是“完全统一”，也不是“每个页面完全独立”。

- 剑雅 Listening 与 Reading 的正式做题页各自拥有一套 `renderGroup` / `questionControl` 编排。
- 两者共同依赖 `static/js/practice_renderers.js`（表单、匹配、地图、复盘卡）和 `static/js/practice_table.js`（表格占位符）。
- Listening 机经、小程序端仍有自己的渲染路径；本轮没有继续复制第三套专项渲染器。
- 题型专项把“完整 Question Group 的冻结快照”注入现有 Listening / Reading 正式做题模板，因此专项与整套题共享实际题面和评分路径。

本轮发现并修复了两个真实页面回归：Reading 匹配段落题在异常源数据中出现错误选项/空提示；未登录学生专项页因 Jinja block 错配而主体空白。另修复了阅读页“已保存”旁仍常驻“重试”的状态冲突，以及 Listening 专项音频门禁硬编码“四个 Part”的文案错误。

## 已核对的数据到 DOM 链路

| 层 | Listening | Reading | 本轮结论 |
|---|---|---|---|
| 原始题库 | `static/listening_tests/*.json` | `static/reading_tests/*.json` | 原始 numeric `type` 不能跨科目直接解释 |
| 加载 / API | `app.py::_load_listening_test_payload`、`/api/listening/test/<id>` | `app.py::_load_reading_test_payload`、`/api/reading/test/<id>` | 原有加载器只做表格规范化，不产出统一语义题型 |
| 表格规范化 | `normalize_practice_tables` | `normalize_practice_tables` | 可复用，但不是完整题型 parser |
| 语义分类 | `services/question_type_practice.py` | 同左 | 联合 instruction、资源、选项与结构判定 canonical type；不单独相信 numeric type |
| Question Group 门禁 | group ID、题号、答案、占位符、共享选项、图片、Section 音频、时间点 | group ID、题号、答案、占位符、共享选项、文章、图片 | `publishable` 才可进入生成器；`manual_review` 默认排除 |
| 冻结快照 | 完整 Section 资源 + 选中完整 group | 完整 Passage 文章 + 选中完整 group | 题号重映射，所有 `$id$` 占位符同步重写；保存 SHA-256 |
| 浏览器题面 | `templates/listening/test_practice.html` | `templates/reading/test_practice.html` | 专项仍走原正式题面，不新建 `renderGroup` |
| 共享渲染 | `PracticeRenderers` / `PracticeTable` | `PracticeRenderers` / `PracticeTable` | 表单、匹配、地图、表格、复盘卡复用 |
| 保存 / 判分 | 专项 draft API + `grade_listening_test_answers` | 专项 draft API + `grade_reading_test_answers` | 服务端草稿、服务端截止时间、服务端评分；提交前 public payload 去答案与解析 |
| 任务 / 计划 | `Task` + `StudyPlan` + `PlanItem` | 同左 | `grading_mode=question_type_practice`；不是另造任务系统 |
| DOM 验收 | 17 个 Listening 题型记录代表页 | 21 个 Reading 题型记录代表页 | 共 38 个浏览器代表页，0 个 DOM 门禁失败；详见浏览器证据清单 |

## 题型事实清单

`QUESTION_TYPE_INVENTORY.json` 是机器可读事实源；`QUESTION_TYPE_AUDIT.html` 是人工审阅页。

- 1,271 个 Question Group，6,240 道题。
- 1,260 组可自动发布。
- 11 组因重复占位符引用进入 `manual_review`，不会被默认生成或推送。
- 0 组处于严重损坏 `blocked`。
- 20 个跨科目 canonical type；Listening 13 个、Reading 17 个，按实际 numeric/subtype 分支展开为 38 条题型记录。
- 每条记录保存 source numeric type、semantic subtype、renderer、资源依赖、全卷/专项/推送/复盘支持情况和代表题组。

这 11 组人工复核不是“已确认错误”：它们只是不能在未人工看题时自动发布。门禁选择了保守失败而不是猜测占位符意图。

## 题型专项完整通路

### 学生自主练习

1. 学生先在 `/practice` 验证现有学生档案姓名。
2. `/practice/question-types` 选择科目、canonical type、题库范围、完整题组数和节奏。
3. `/api/question-type-practice/preview` 只返回通过门禁的完整题组。
4. `/api/question-type-practice/self` 创建现有 `Task`、`StudyPlan`、`PlanItem` 和冻结快照。
5. 带任务 token 的正式 Listening / Reading 页面加载已去答案的 public snapshot。
6. 草稿写入 `QuestionTypePracticeAttempt`；刷新后从服务器恢复。
7. 提交后服务器按共享评分服务判分，任务与计划项同步完成；随后才显示答案和解析。

### 助教批量布置

1. `/tasks/question-types` 复用现有学生档案，多选学生批量发布。
2. 发布前展示真实来源、原题号、资源状态、renderer 和完整性结论，可按完整 group 移除。
3. 每位学生得到独立 Task/PlanItem 和不可漂移的 snapshot hash。
4. 助教从逐题结果页查看学生答案、正确答案、来源与原题范围。
5. “推送错题完整题组”保持 group 边界；“推送同题型新题”调用同一生成器并排除原 group。

仓库当前没有独立 `Class` 实体，因此本轮没有伪造班级表。现有 UI 明确说明这一点，并以学生档案多选完成批量发布。若以后引入班级，应只增加“班级到学生集合”的选择层，不改变冻结快照、Task、PlanItem 和评分通路。

## 考试节奏与训练节奏

- Listening 考试节奏先做真实音频 metadata / duration 门禁；资源未就绪时不能开始。
- 开始后使用单一 `<audio>` 节点的锁定 playlist，无暂停、拖动、倍速、重听或训练辅助入口。
- 服务器以实际音频总时长加 120 秒复核时间生成截止时间；录音结束前隐藏最终交卷按钮。
- Reading 考试节奏以任务分钟数生成服务器截止时间。
- 训练节奏保留现有导航、手动提交和训练控件；答案和解析只在提交后进入 review mode。
- 截止后服务器使用最后一次成功保存的草稿判分，不能通过客户端时钟延长。

## 回归与浏览器证据

固定回归：

- Cambridge IELTS 21 Test 3 Listening Part 1：10 个作答控件、0 个空 `Question` 标签、音频 7:11 可读取。
- Cambridge IELTS 7 Test 2 Listening Section 1：10 个语义表单控件、0 个空 `Question` 标签、音频 5:44 可读取。

完整 UI 通路已实际执行：助教预览安全题组 → 批量发布 → 学生任务中心 → 作答 → 服务器自动保存 → 刷新恢复 → 提交 → 逐题复盘 → 助教逐题结果 → 错题完整组再推送 → 同题型新题再推送。

证据目录：`docs/evidence/question-type-practice-2026-08-29/`

- `BROWSER_TYPE_MATRIX.json`：38 条代表题型的 URL、原题组、renderer、DOM 指标与截图文件名。
- `listening-*.png` / `reading-*.png`：每条实际题型记录的整页截图。
- `fixed-*.png`：两套固定回归题。
- `assistant-*.png` / `student-*.png`：推送、任务中心、自动保存、提交、逐题结果和再推送。

## 发布判断

题型专项自己的发布门禁当前为 **GO**：`blocked_group_count=0`，全部 11 个需人工确认的 group 已默认隔离；专项关键测试和浏览器代表页通过。

整个仓库仍不能据此直接声称“已部署”。本轮没有 commit、push 或部署；生产端口 5002、gunicorn 单 worker / gthread / 6 threads 等生产约束没有改变。最终部署前仍需运行本文件列出的验证命令、审阅工作区中其他既有改动，并由用户明确授权 commit / push / deploy。

## 可复现验证

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/python scripts/build_question_type_inventory.py --audio-root /Users/zhouxin/Desktop/studytracker/static/listening
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q tests/test_question_type_practice.py tests/test_question_type_practice_routes.py tests/test_question_type_practice_contract.py
node --test tests/test_practice_renderers.js tests/test_practice_modes.js tests/test_simulation_audio.js
```
