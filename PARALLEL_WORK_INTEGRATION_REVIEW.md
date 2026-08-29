# Practices 并行成果整合审计

审计日期：2026-08-29
整合工作树：`/Users/zhouxin/.codex/worktrees/practices-interaction-refactor`
整合分支：`codex/practices-interaction-refactor`
基线 / 当前 HEAD：`f8152ff01df98d04cca9860d31d49b8e2697aaef`（审计时与 `origin/main` 一致）

## 结论

题型分类/专项练习与 IELTS on Computer 体验两项成果都已存在于当前整合工作树的未提交、未跟踪文件中；没有发现另一枚包含同一成果、可以安全重复 cherry-pick 的提交。当前分支已经是合适的整合分支，后续导航修复必须直接建立在这里的真实路由和模板上。

因此本轮采用以下整合方式：

1. 保留当前全部未提交与未跟踪成果，不执行 reset、clean、restore 或覆盖式 checkout。
2. 不对题型专项或机考体验重复 merge/cherry-pick。
3. 先在当前工作区实现多入口导航契约，再运行统一回归和发布门禁。
4. 只有题型专项、机考体验、导航修复三者组成同一候选并通过门禁后，才允许形成单一提交/部署版本。

## 已检查的 Git 事实

已执行并核对：

```bash
git fetch --all --prune
git status --short --branch
git diff
git diff --cached
git branch --all --verbose --no-abbrev
git worktree list --porcelain
git log --all --oneline --decorate
git log --all --oneline --decorate -150 --extended-regexp --regexp-ignore-case --grep='question|classification|practice|listening|reading|IELTS|computer|simulation|renderer|task'
```

- 暂存区为空。
- 当前分支在审计时相对 `origin/main` 为 `0 ahead / 0 behind`；两项新成果均未 commit/push。
- 桌面主工作树 `/Users/zhouxin/Desktop/studytracker` 的本地 `main` 停在 `6ded77d2`，比 `origin/main` 旧 31 个提交，而且有来源不同的文档与数据改动；它不是本轮整合基线。
- `origin/main` 与当前整合基线均为 `f8152ff0`。
- 相关历史提交（如 `9607915a` 剑雅 21、`c26dff85` Reading Study、`db86a654`/`ca007272` 模考基础）已经包含在当前基线中；本轮两项完成成果没有另行提交。

## 两项已完成成果的实际位置

### A. 题型分类与题型专项通路

主要新增文件：

- `api/question_type_practice.py`
- `services/question_type_practice.py`
- `services/question_type_assignments.py`
- `scripts/build_question_type_inventory.py`
- `templates/question_type_practice/`
- `QUESTION_TYPE_INVENTORY.json`
- `QUESTION_TYPE_AUDIT.html`
- `PRACTICE_ARCHITECTURE_REVIEW.md`
- `tests/test_question_type_practice*.py`

主要接入文件：

- `api/__init__.py`
- `app.py`
- `models.py`
- `templates/practice/index_content.html`
- `templates/student_today.html`
- `templates/tasks.html`
- Listening / Reading 正式做题模板

数据与任务链路：完整 Question Group 分类 → 安全门禁 → 冻结快照 → 现有 `Task` / `StudyPlan` / `PlanItem` → `QuestionTypePracticeAttempt` 草稿/结果 → 学生端/助教端结果和再推送。

### B. IELTS on Computer 体验与共享渲染

主要新增文件：

- `services/ielts_exam_payload.py`
- `services/mock_exam_runtime.py`
- `static/js/practice_modes.js`
- `static/js/practice_renderers.js`
- `static/js/practice_shell.js`
- `static/js/simulation_audio.js`
- `static/css/practice_shell.css`
- `tests/test_ielts_exam_payload.py`
- `tests/test_mock_exam_runtime*.py`
- `tests/test_practice_modes.js`
- `tests/test_practice_renderers.js`
- `tests/test_practice_shell.js`
- `tests/test_simulation_audio.js`
- `docs/IELTS_EXPERIENCE_*.md`
- `docs/PRACTICES_INTERACTION_AUDIT.md`
- `docs/SIMULATION_PRACTICE_MODE_MATRIX.md`

主要接入文件：

- `app.py`
- `api/mock_exam_student.py`
- `static/css/exam.css`
- `templates/listening/test_practice.html`
- `templates/reading/test_practice.html`
- Listening / Reading / 机经 / 精听目录与练习页

该成果保留四种互斥模式、服务端时钟和草稿、Listening 单次连续播放门禁、Reading 双栏以及提交后复盘；导航修复不得回退这些 capability 或另建一套练习模板。

## 数据库与接口审计

本候选新增一张 additive 表：`question_type_practice_attempt`。

- 外键：`task_id -> task.id`，且每个任务唯一。
- 保存冻结快照 hash、服务端草稿、截止时间、提交结果和错题完整组 ID。
- 不修改或回填现有学生答案、任务、错题和提交记录。
- `api/__init__.py` 在应用初始化时调用 `QuestionTypePracticeAttempt.__table__.create(..., checkfirst=True)`；重复启动幂等。
- 没有新增 Alembic migration 文件，也没有重复 migration name。
- 机考运行时复用现有 `MockExam` / `MockExamSession` 字段；本候选只把新建模考默认 Listening 分钟由 30 调整为 32，不做存量数据更新。

部署前必须在生产备份/只读核对后确认建表权限，并在上线后验证该表存在；不得用覆盖数据库文件的方式发布。

## 共享文件与冲突保留清单

下列文件同时承载多项成果，后续冲突必须逐段处理，禁止简单选择 ours/theirs：

| 文件 | 必须保留的题型专项能力 | 必须保留的机考体验能力 | 导航适配重点 |
|---|---|---|---|
| `app.py` | Task/PlanItem 接入、学生任务列表、题型入口 | mock runtime、simulation payload、两科正式路由 | 入口身份和显式 return context |
| `models.py` | `QuestionTypePracticeAttempt`、资源类型 | MockExam 默认时长 | 仅 additive schema，不做破坏性迁移 |
| `templates/practice/index_content.html` | 题型专项入口与任务卡 | 统一 Practices 首页 | 首页是退出模块的默认落点之一 |
| `templates/listening/test_practice.html` | 专项 frozen payload | Simulation/Practice/Review、音频门禁 | 内部返回、退出模块、任务来源 |
| `templates/reading/test_practice.html` | 专项 frozen payload | 双栏、Simulation/Practice/Review | 内部返回、退出模块、任务来源 |
| `templates/student_today.html` / `templates/tasks.html` | 学生任务和助教结果入口 | 既有任务/预览 | 进入时携带来源上下文，结果返回原入口 |
| `templates/base.html` | 全站题型入口可达 | 统一 shell 资源 | 不能让公开学生路由经过 StaffAuthGuard |

## 其他 worktree / 分支排除项

以下可见工作区包含来源不同的并行改动，不属于本轮两个已完成成果，不能整体合并或覆盖：

- `/Users/zhouxin/.codex/worktrees/fc33/studytracker`：旧 detached 基线上的九分达人阅读/导入工作，且修改 `app.py`、Practice 入口和 Reading 模板；与本轮共享文件冲突高。
- `/Users/zhouxin/.codex/worktrees/b275/studytracker`：听力/词汇/小程序方向的未提交改动。
- `/Users/zhouxin/.codex/worktrees/b65e/studytracker`：小程序访客/词汇方向改动。
- `/Users/zhouxin/Desktop/studytracker-release`：小程序发布工作区，含大量客户端未提交改动。
- `/Users/zhouxin/.codex/worktrees/vocabulary-learning-appeal/studytracker`：词汇申诉方向改动。
- `/private/tmp/...` 中的若干 worktree 记录路径已不存在；本轮不主动 prune，以免扩大操作范围。

当前整合候选不会从这些工作区机械复制共享模板；如果后续需要纳入其中某一独立业务，必须另行做精确 diff 审计。

## 已知发布门禁

两项功能本身的自动化和浏览器代表页已有通过证据，但仓库级 IELTS 题库门禁仍记录一项 P0：

```text
static/reading_jijing/reading_jijing_83_test_95.json
count=39, range=1-39
```

缺失的 Q40 没有可信来源时不得编造。导航实现和统一回归应继续完成；最终部署前必须再次运行全库 gate，并把这个既有内容阻断与本轮代码结果分开报告。若无法取得可靠原题来源，则候选可以完成、测试和提交，但不能谎称满足仓库级 GO 或已安全部署。

## 整合执行顺序

1. 以当前工作区为唯一候选，冻结上述成果位置。
2. 建立统一 Practices 入口上下文：身份类型、内部返回目标、退出模块目标、来源标签。
3. 覆盖目录、Test/Section/Passage、题型专项、任务、课堂、学生姓名、助教/老师预览、提交/复盘和浏览器后退。
4. 运行目标测试、全仓测试、Node 测试、题库/媒体/DOM 门禁和真实浏览器多入口回归。
5. 记录线上 commit、部署标识、数据库版本和回滚点后，才决定是否执行一次统一部署。

## 2026-08-30 整合实施与最终判定

导航实现已直接落在本报告定位的统一工作树，没有重复 merge/cherry-pick，也没有回退题型专项或机考 renderer。新增/接入重点为：

- `services/practice_navigation.py`：四类身份默认出口与安全本地目标校验。
- `static/js/practice_shell.js`：即时父级返回、模块退出、显式新标签页上下文、列表恢复与浏览器后退护栏。
- `app.py`、`api/question_type_practice.py`、`api/mock_exam_student.py`：login/classroom next、题型任务和模考运行时全链路参数传播。
- Listening / Reading / Writing / 精听 / 机经 / mock exam / Reading Study / Practices 模板：统一 back/exit 控件和移动端可见性。
- `tests/test_practice_navigation*.py`、`tests/test_practice_shell.js`、`tests/test_practice_interaction_e2e.py`：服务端安全、路由传播和客户端状态契约。

统一候选的最终代码门禁为：全仓 Python `618 passed, 72 subtests passed`，相关 Node `18/18 passed`，JS syntax 与
`git diff --check` 通过；真实浏览器的听力/阅读目录→整卷→返回、浏览器后退、题型专项、四类身份和 390px 移动视口均通过，console
error 为 0。

只读生产基线已记录为 `f8152ff01df98d04cca9860d31d49b8e2697aaef`、deploy run `33079779450`、SQLite
`user_version=0 / quick_check=ok / 71 tables`、service active、5002/1 worker/gthread/6 threads；这是当前代码回滚点。

用户随后明确授权暂时下架这套不完整 Test。实现没有删除源题或历史记录：`static/reading_jijing/offline_tests.json` 以源文件 SHA-256
锁定隔离项，主网页目录、助教网页/小程序选题和题型专项统一排除；门禁反向检查隔离源存在/哈希/题数以及 catalog 不得残留。完整资源
gate 现为 **PASS**：84 Listening、128 在线 Reading、1 隔离 Reading、8,480 在线题、336 有效音频、48 图片。浏览器复核阅读机经
56 张卡、下架 ID 0 个，题型专项仍可用。因此题型专项、IELTS on Computer 和多入口导航的统一候选已转为发布 **GO**；下一步按用户
授权创建生产 SQLite 备份，再用项目现有 main 工作流只部署一次。
