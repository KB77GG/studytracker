# 新托福真题刷题系统实施评审

## 2026-06-12 已实现范围

- `/practice` 已增加 TOEFL 入口，`/toefl/tests` 按套卷列出真题、ETS Practice 和 OG。
- 正式考试页已支持 MC、拼写填空、组句和自由写作，活动题面不返回答案。
- 阅读按 Module 单独计时；进入下一 Module 后禁止返回，Review 仅显示当前 Module。
- 已发布 `2026-01-21 A卷`、`ETS Student Practice Test 1` 阅读和
  `OG Chapter 6` 阅读。官方样题分别通过 40/40、50/50 答案覆盖门禁。
- 所有可见套卷必须有 `manifest.json`，且同时满足
  `publish_status=published`、`duplicate_status=clear`。
- `scripts/audit_toefl_official_materials.py` 输出官方资料文件和题目级重复审计；
  `scripts/import_toefl_official_reading.py` 可重复生成两套官方阅读数据。
- 官方资料审计确认 44 组纯副本、1 组同套重复说明音频、1 组跨套共享说明音频，
  未发现非说明媒体或题目块的跨套重复。

当前仍使用文件题库和浏览器本地续作；下文数据库 attempt/response 与 Task 回写方案
仍是后续持久化阶段，不应误认为已经落地。

## 结论

Claude 方案的主方向正确：结构化题库、媒体资产、服务端判分、作答与进度分离。
但原契约不能直接上线，至少要先修正题号命名空间、题面完整性门禁、
Build-a-Sentence 字段语义和来源追溯。

不建议把托福整套题直接塞进 `MaterialBank/Question`：

- `Question` 是平铺结构，没有 Module、题组、共享文章和共享音频。
- `StudentAnswer` 强依赖 legacy `Task`，不能自然表达一次整套尝试和多次重做。
- `EntranceTest*` 是明确隔离的入学测试域，不应承担日常刷题。
- 现有剑雅整套练习已有 JSON 加载、自动判分、`Task` 回写和提交记录，可复用其交互，
  但其资源类型、分数换算和表名均绑定 IELTS，不能直接冒充托福。

推荐新增考试无关的 `practice_exam` 领域，JSON 作为可审计导入物，题目导入数据库；
前端和任务系统复用现有整套练习的成熟行为。

## 当前数据基线

全量答案与汇编对应结果位于：

- `data/toefl_answer_keys/practice_crosswalk/exam_crosswalk.csv`
- `data/toefl_answer_keys/practice_crosswalk/question_answer_crosswalk.csv`
- `data/toefl_answer_keys/practice_crosswalk/report.md`

截至 2026-06-11：

| 指标 | 结果 |
|---|---:|
| 汇编套题 | 45 |
| 正常解析 | 31 |
| 带解析警告 | 8 |
| 资料标记不完整 | 3 |
| 无答案文件 | 2 |
| 答案版式暂不支持 | 1 |
| 解析答案行 | 4,355 |
| 其中 MC | 2,703 |

`2026-01-21 A卷` 已有听力、阅读、写作样例 JSON。其 47 道听力 MC 和
20 道阅读 MC 与独立 crosswalk 逐题比对，67/67 一致。但题面仍有以下阻塞项：

- 6 道听力题没有完整四个选项。
- 1 道阅读题没有题干、文章和选项。
- 4 道 Build-a-Sentence 的乱序词与答案词表不一致。

因此，“有答案”不等于“可自动判分”。发布门禁必须同时检查题面和答案。

## 原方案必须修正的字段

### 1. 题目 ID 必须包含 Module

错误：

```text
listening_2026-01-21_A_q1
```

正确：

```text
toefl-2026-01-21-a:listening:m1:q1
toefl-2026-01-21-a:listening:m2:q1
```

主卷和加试都会从 Q1 重新编号。日期也不是唯一键，同日可能有 A/B/C 卷、
套一/套二、普通卷和线下卷。

### 2. Build-a-Sentence 不能使用 `target_sentence`

题面中的完整句通常是情境句，不是学生要排列出的答案。例如：

```text
context_sentence: The professor announced a change in the syllabus.
ordered answer: Do you know if the due dates have been updated?
```

应使用：

- `context_sentence`：题面情境。
- `scramble_tokens`：学生可拖拽词块。
- `answer.ordered_tokens`：正确顺序。
- `content_status=scramble_mismatch`：两组 token 不一致时禁止自动判分。

### 3. 增加内容与判分双状态

每道题至少需要：

```json
{
  "content_status": "ready",
  "grading_status": "ready"
}
```

建议枚举：

- `content_status`: `ready`, `missing_prompt`, `missing_passage`,
  `missing_options`, `scramble_mismatch`
- `grading_status`: `ready`, `review_only`, `missing_answer`,
  `incomplete_content`, `manual_review`

MC 只有在答案存在、四个选项完整且正确选项仍在选项集合中时才能标为 `ready`。

### 4. 保留来源证据

每题必须携带：

- `source_ref.path`
- `source_ref.sha256`
- `source_ref.page`，可空
- `source_ref.subject`
- `source_ref.module`
- `source_ref.question_no`

答案回填使用：

```text
source_set_id + subject + module + source_question_no
```

禁止使用裸题号更新。

## 推荐数据库

使用六张最小表，选项和不同题型答案保留 JSON，避免为每种题型建子表。

| 表 | 作用 |
|---|---|
| `practice_exam` | 一份分科套题、版本、发布状态、内容哈希 |
| `practice_module` | m1/m2、顺序、整段音频和题号范围 |
| `practice_group` | 对话、讲座、阅读文章或任务组，共享题面 |
| `practice_question` | 题号、题型、选项、答案、来源和就绪状态 |
| `practice_attempt` | 学生一次开始/提交/重做及汇总成绩 |
| `practice_response` | 单题作答快照、判分结果和得分 |

关键约束：

```text
practice_exam.external_id UNIQUE
practice_module(exam_id, external_id) UNIQUE
practice_question.external_id UNIQUE
practice_response(attempt_id, question_id) UNIQUE
```

`practice_exam` 还应保存 `schema_version`、`content_sha256` 和 `source_set_id`。
导入器以 `external_id + content_sha256` 幂等更新；已产生作答的发布版本不能原地改答案，
必须生成新版本。

## API 与判分

建议 API：

```text
GET  /api/practice-exams
GET  /api/practice-exams/{external_id}
POST /api/practice-exams/{external_id}/attempts
PATCH /api/practice-attempts/{attempt_id}
POST /api/practice-attempts/{attempt_id}/submit
GET  /api/practice-attempts/{attempt_id}
```

活动作答接口不能返回标准答案。提交后，复盘接口才返回答案和解析。

判分规则：

| response_type | 规则 |
|---|---|
| `mc` | 大写后精确匹配选项 key |
| `fill` | Unicode/空白/大小写归一后匹配允许答案集合 |
| `order` | token 序列精确匹配；标点单独归一 |
| `free` | 不自动判分，保存文本供自评或教师批改 |

总题数和正确率的分母只包含 `grading_status=ready` 的自动判分题。
缺题面、缺选项或缺答案的题可以展示，但不能静默计错。

## 与现有任务系统对接

新增：

```text
PlanItem.RESOURCE_PRACTICE_EXAM = "practice_exam"
Task.practice_exam_id
Task.practice_scope_json
Task.practice_access_token
```

`practice_scope_json` 用于指定整科、单 Module 或题号范围。提交后由
`practice_attempt` 汇总回写 `Task.accuracy`、`Task.completion_rate`、
`Task.submitted_at`，再调用现有 `_sync_plan_item_from_task`。

不要复用：

- `reading_test_id` 或 `listening_exercise_id`：它们带有 IELTS 特定路由和资源语义。
- `ListeningTestSubmission/ReadingTestSubmission`：包含 IELTS band 字段和换算逻辑。
- `EntranceTestAttempt`：其邀请、一次性测试和报告流程不同。

## 导入流水线

1. 从汇编 Markdown、阅读 extracted JSON 和答案文件生成 staging JSON。
2. 用 crosswalk 按 canonical key 回填答案。
3. 使用 `schemas/toefl_practice_exam.schema.json` 做结构校验。
4. 执行内容校验：题号范围、重复 ID、四选项、正确 key、媒体存在、排序 token 一致。
5. 输出逐题 QA 报告，不把警告吞掉。
6. 在单事务中幂等导入数据库，默认状态 `draft`。
7. 只有所有待计分题均为 `grading_status=ready` 时才允许 `published`。

## 实施顺序

### PR 1：契约、导入和表结构

- 新增六张表和独立建表脚本。
- 实现 schema validator、内容 validator 和幂等 importer。
- 导入 `2026-01-21 A卷` 为 `draft`，验证来源哈希和 67 道 MC。

### PR 2：服务端作答

- 实现目录、试题、autosave、submit、review API。
- 服务端判分，不信任前端提交的 `correct`。
- 测试 Module 重号、缺答案降级、重复提交和版本冻结。

### PR 3：前端渲染

- 先支持 MC、fill、order、free 四种 response renderer。
- 听力按 Module 播放整段音频。
- 阅读按 group 共享文章和图片，避免每题重复传输。

### PR 4：Task/PlanItem 与进度

- 新增 `practice_exam` 资源绑定。
- 回写正确率、完成率、用时和错题。
- 目录页展示最近一次状态，不覆盖历史 attempt。

### PR 5：批量发布

- 用同一流水线生成全部套题。
- 工程 canary 使用已有样例 `2026-01-21 A卷`。
- 最近发布候选优先 `2026-04-08`、`2026-04-01`、`2026-03-27`；
  发布前必须重新跑题面完整性 validator。
- 若优先追求首批全题号覆盖，使用 `2026-03-25` 作为回退样本：
  当前 crosswalk 为阅读 20/20、听力 47/47、写作排序 10/10。
- `2026-03-14 国内线下`、`2026-03-21 国内线下` 和
  `2026-04-11 国内线下` 保持 draft，等待答案或版式补齐。

## 上线验收

- 同一套 m1/q1 与 m2/q1 能同时存在、分别作答和判分。
- 导入器重复运行不产生重复题。
- 修改已发布答案会触发版本冲突，而不是覆盖历史结果。
- 活动作答 API 不泄露标准答案。
- 缺选项题不会进入自动判分分母。
- `2026-01-21 A卷` 的 67 道 MC 与 crosswalk 逐题一致。
- 刷题提交后 `Task`、`PlanItem`、attempt 和逐题 response 数据一致。
- 页面刷新、断网重连和再次进入可恢复 autosave。
