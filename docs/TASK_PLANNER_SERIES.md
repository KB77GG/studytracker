# 连续安排与听力整套

2026-10-31 根据试用反馈扩展，用户明确授权后已提交、推送并部署。业务版本 `4b992e7929b0a2de019e913300a643d0326d2c31`，入口 <https://studytracker.xin/task-planner>；最新状态见 `CODEX_HANDOFF.md` 顶部。

## 操作方式

同一学生可以有多条学习线，例如阅读判断题、听力选择题和词汇。每条线有自己的材料范围、起点、日期范围和每周任务量。

同一材料平日少、周末多时，在一条线里设置星期一至日的配额，共用一个顺序；不需要为平日和周末分别维护起点。

| 星期 | 示例任务量 |
| --- | --- |
| 周一至周五 | 每天1组 |
| 周六、周日 | 每天2组 |

0表示该星期休息。题型专项按完整题组计量，同时预览题数；词汇按词数计量。整组题不为凑固定题数被拆开。

单日安排继续保留；连续安排支持7天、30天和自定义起止日期，结束日包含在内，单次范围最长31天。日期仍遵守现有未来90天上限。先预览每天的具体内容，再保存整批草稿、一次确认。选择一个月不表示重复发送同一组题30次。

## 本次范围

- 题型专项连续安排：选择听力或阅读、题型、明确教材或试卷范围、起始题组，按自然顺序取后续题组。题组已有稳定ID和教材/Test/Section或Passage/组内位置；数据库自增编号和原目录文件名字典序不作为学习顺序。
- 词汇连续安排：选择词书、起始词序、学习目标，每天按配额依次分配，预览中显示各天的起止词序。内容不足需调整范围或配额，不自动换书或循环回头。
- 听力单日安排：新增整套Test及单个Section，区别于精听；复用既有听力任务与学生练习入口。听力整套、阅读整篇和精听的周期排程不属于本次首批连续安排范围。
- 同一学生可建立多条学习线；每条线生成独立的、具有具体日期和资源的草稿，沿用现有正式Task/PlanItem、日期执行和学生自动开关。
- 学习线统一确认或取消未布置部分，已发布正式任务保持历史。周期条目不单独改期或更换学生；调整这条线时取消未布置部分后重新预览创建。普通单日安排仍可编辑。

## 未完成与临时调整

连续安排默认按已确认日期执行，也可选择等待本线上一项有效完成/提交。有效状态沿用原服务：退回和部分通过不放行，词汇必须有同学生结算。

选择等待时，上一安排未发布、被取消、未完成或被退回，将阻止本线后续安排。其他学习线不受它直接阻塞；内容重复仍按既有去重规则拦截。

旧任务到次日03:00后只读，03:05调度不能假设学生还能补交旧任务。因此阻塞时提示助教安排补做、取消未布置部分并重新排程；不悄悄改旧任务日期、不自动顺延整个日历、不自动跳过未做内容。本版不是无限自动续排器。

## 数据与校验

只新增学习线和条目关联表，不修改已上线安排表、原Task或成绩列。每个日期条目冻结具体资源，整批创建和确认原子提交。保存要求预览摘要匹配，客户端请求键用于防止重试重复创建。

明确的日期、配额和来源由服务端校验；前端不能指定可信题目快照或跳过权限/CSRF/去重。与已布置任务、其他待布置安排、整套/Section/专项相交内容继续交叉去重。教材变化后重新预览，确认后的失效资源在发布前拦截。

新代码仍使用现有服务器和题库，不增加AI选题或外部付费API，不发送微信提醒。自动开关由助教为学生开启，无需学生确认。

## 验收入口

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_task_planner tests.test_task_planner_resources tests.test_task_planner_series -v
node --test tests/test_task_planner_client.js tests/test_task_planner_series_client.js
```

实际测试计数、浏览器结果、未验证项和发布状态记录于 `CODEX_HANDOFF.md`。测试只使用合成学生与临时数据库，不为截图中的真实学生写入任何任务。

## 本轮发布验收

- 分支CI [41172481854](https://github.com/KB77GG/studytracker/actions/runs/41172481854)与main CI [41172849083](https://github.com/KB77GG/studytracker/actions/runs/41172849083)成功，三个测试job通过；advisory lint延续仓库存量failure。72项planner Python、71项旧任务回归、31项Node通过。新CLI只改help文案，Ruff与既有拼写队列门禁通过。
- [部署41172849064](https://github.com/KB77GG/studytracker/actions/runs/41172849064)第一次在 `create_plan_table.py` 导入app建新表时遇 `database is locked`，未重启原服务；执行纯模型 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_task_planner.py --init-schema` 返回schema ready，再用 `gh run rerun 41172849064 --failed` 重跑成功。未定位首次持锁者，不据报错推断app自己持锁。后续新增planner表应在导入app的旧迁移步骤前显式运行此CLI；本次未修改服务器部署脚本或杀进程。
- 一致性备份 `/root/backups/studytracker/planner-series-20261031-132940/app.db`，233811968 bytes，目录0700/文件0600、quick_check=ok。与备份对比只新增series及series_item两表，旧表定义变化0；新表均0行、live quick_check=ok。不要用整库恢复覆盖后续学习记录。
- 生产业务HEAD及10个运行文件SHA匹配，服务自 **2026-10-31 13:36:02 CST** active/running、NRestarts0，5002/单worker/gthread6保持。重启后warning以上journal0；timer enabled/active/waiting、下次11月1日03:05 CST；CLI dry-run exit0/outside_window=true、发布0，不表示真实凌晨发布已验证。
- 回环login200、planner302到login，匿名bootstrap/series/series-sources均401；两个JS和CSS200且SHA一致。公网login200、新series.js的SHA为 `71798f41cdf2cae0afac9c6696210c67d8f7ce54c8ed9f66ce640e36c592a0df`，与本地一致。生产轻量只读资源探针列84整套/336Section、阅读来源146/听力来源102，不导入app/重模型，不创建真实学生任务或发通知。
- **未完成完整GUI与390px验收**：Mac锁屏、Chrome不可用，先前IAB只能确认首页渲染，点击未生效。真实学生首轮使用、微信WebView与全套听力端到端待助教试用；本次无小程序改动、上传、提审或发布。
