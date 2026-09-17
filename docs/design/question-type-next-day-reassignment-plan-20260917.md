# 题型专项跨日再次布置与历史记录计划

## 范围与基线

- 用户反馈：前一天未完成的题型专项，第二天不能像单词任务一样再次布置，也难以查看同一学生、同一题组的旧记录。
- 执行工作树：`/Users/zhouxin/.codex/worktrees/86d7/studytracker`；分支 `codex/question-type-review-audio`；基线 `7b7e9fa2ec874a0f4d7b838250020ddb066a4115`，开工时干净。
- 本轮只修网页任务中心、题型专项 API 和老师只读历史页；不改小程序、微信页面、题库、评分、音频、schema 或生产数据。尚未获得本轮 commit / push / deploy 授权。

## 已确认根因

1. `services/task_assignment_duplicates.py` 把全部历史 `pending / progress / in_progress` 永久视为阻断，没有比较旧任务日期和新任务目标日期。
2. 题型专项预览的 `excluded_group_ids` 汇总全部历史题组，因此即使服务端将旧未完成任务放行，前端仍可能选不到原题组。
3. `services/task_assignment_history.py` 没有识别 `question_type_practice`；“昨日任务 → 再次布置”把专项降级成 `custom`，丢失科目、题型、完整 `group_ids` 和节奏。
4. 重复矩阵每个学生 × 题组只显示首条匹配，且浏览器自行按状态推断阻断；多次同组任务会被遮蔽，前后端政策也可能漂移。
5. 历史链接指向通用批改表单；专项结果页对没有 attempt 的任务返回 404，不能准确呈现未开始或进行中的旧专项。

## 规则

- 只对题型专项采用按任务日的跨日规则：旧的未完成任务日期严格早于新目标日期时，可无需复训确认再次布置；同日、倒序日期、缺失或非法日期默认仍阻断。老师可提前规划新任务，不以真实时钟是否已过 03:00 为条件；原有 `force_repeat + confirm_repeat + ≥2 字原因` 的显式人工复训权限保持不变。
- 次日 03:00 继续只控制旧任务的学生写权限；不修改旧任务日期、状态、快照、答案、成绩、提交时间或计时。
- `submitted / done / completed / finished` 和其他需要复训确认的历史继续要求二次确认与原因；客户端 `retraining_mode` 不能绕过服务端判断。
- 自动排除只排除仍阻断或仍需复训确认的题组；仅有更早未完成历史的题组默认可以进入新预览，同时完整展示所有对应历史。
- 每个新任务继续生成独立 Task、PlanItem、token、snapshot 和 attempt；幂等键仍保证浏览器重试只创建一批。

## 验证计划

- 纯服务：同日阻断、次日放行、未来/无日期/非法日期保守阻断、完成/已提交仍需确认、批量学生与部分题组、多条历史全部返回。
- 路由：昨日 pending/progress → 次日创建新 Task/PlanItem，原 group_ids 一致且旧记录不变；相同幂等键只创建一次；历史页查看不创建 attempt 或改写成绩。
- 前端合同与 Node：昨日专项完整回填、日期变化刷新、使用服务端 `requires_confirmation / blocking`、矩阵显示同组全部历史且不暴露 token。
- 回归：题型专项路由、任务日期闸门、上轮解析/音频复盘相关测试；最终运行目标 Ruff、Python compile、JS syntax 与 `git diff --check`。

## 发布状态

- 5092 既有用户预览保持运行，本轮不复用其数据库或端口。
- 浏览器交互使用隔离内存库与虚构学生；不写生产或真实学生数据。
- 用户已授权发布；业务提交和生产验收均完成。正式生产验证仅执行只读 GET 与无写入重复历史查询，不使用真实学生发布新任务。

## 执行状态

- 计划中的服务、路由、只读历史页、前端矩阵和回归均已落地；完整实现、不变量、精确命令与结果见 `docs/QUESTION_TYPE_NEXT_DAY_REASSIGNMENT_EXECUTION.md`。
- 主任务相关 Python 129 passed / 7 subtests passed，Node 46 passed；最后一项 workflow 一致性调整后窄集 23 passed。目标 Ruff、Python compile、JS syntax 与 diff check 通过。
- 独立首轮与最终测试、Reading/Listening 路由 probe 和 5093 Chrome 核心流程均通过；业务提交 `675a3473` 的两条 CI 与 Deploy 均 success，生产运行同一 SHA，独立生产验收 GO。5092 既有用户预览保持运行；完整发布证据见执行报告。
