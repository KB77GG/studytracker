# 热榜练习布置与固定模考组卷（2026-11-26）

实施树：`/Users/zhouxin/Desktop/studytracker/.tmp/exam-sprint-distribution-20261126`，分支 `codex/exam-sprint-distribution-20261126`，基线 `79388e269e924e9ce591dd3e6de3762a61614ddf`。用户追加要求7天热榜能用于模考/练习推送；延续此前完整冲刺模块发布授权。未代老师向真实学生布置/发送任务或消息。

## 完成行为

老师在 `/tasks` 的听力筛选及阅读分组中可以选最新已核验热榜。服务端发布前重验版本/媒体，阅读强制绑定对应单篇；保存原始Task resource ID和passage，周更不会将旧任务换成新题。复用既有日期、token、判分、完成记录及家长/教师报告链。

`/admin/mock-exams/create` 两科可分别选择已有整卷或热榜组卷。每个Part/Passage各选一篇；“按热度选一套40题”按当前排名顺序寻找完整组合，服务端仍要求各40题。创建后继续用原模考pincode分发。保存固定JSON内容、来源版本和媒体引用，ID由内容摘要确定；当前榜撤下不影响已保存试卷。

新组卷位于服务器 `instance/exam_sprint/papers/`，不进入Git，后续备份/搬迁需与assets/content和数据库一起保留。普通practice、公开JSON和匿名判分不能读取组卷答案；只允许既有授权模考端点读取，活动模考payload继续去除答案、解析和transcript。新的独立service承担逻辑，app.py整体减行。

小程序后端兼容：支持通用网页任务卡的客户端得到精确Task/token/passage网页指引；旧原生入口也支持校验后的ninefen阅读和同源hash图题。未修改固定小程序上传源，也未上传/提审/发布小程序，未宣称真实手机全部通过。

## 验收证据

- `validation.json`：23个产品/测试/CI文件SHA和精确命令；本地96项Python主回归、115项考试完整性回归与30项Node通过，两组Python有重叠不累加。新store损坏类型保护补跑6单测、北京时间日期fixture补跑4单测通过；全部定向Ruff/Black及Python3.10 AST通过。保留原完整性模板摘要守卫，仅更新本次已审核听力媒体路径修改的预期摘要。
- `current-papers-acceptance.json`：使用11/26真实已发布140篇，将20个排名分别组合为20套听力＋20套阅读，共1600题全对；真实模板函数渲染1600控件、14图和850占位通过，原题长ID按字符串处理。全离线、无来源API调用或学生DB写入。
- 新任务路由回归使用临时内存SQLite与合成身份，验证两科实际布置→错误token403→正确提交→Task.done和Submission；榜单撤下后旧任务仍可完成。模考创建回归覆盖40题/旧题库兼容/坏选择零写/学生禁建/重复pincode/公开loader拒绝。
- integration_map独立复核组卷schema、多选、媒体和模考读权限；question_matching实现学生兼容并通过42项相关回归（与上述96有重叠，不叠加）；未发现剩余阻塞。
- 浏览器视觉**未执行**：合成Flask页面和脚本已生成，但Chrome启动升级审批被中止（没有浏览器输出），未通过其他工具绕过。1440/390视口及真实手机布局未验证；不能把静态/Node通过说成浏览器验收。`render_mock_visual.py`、`check_mock_visual.cjs`和fixture可在以后明确允许时重现。

复现真实数据组卷验收（不联网、不写真实任务）：

```sh
EXAM_SPRINT_STATE_DIR='/Users/zhouxin/Library/Application Support/StudyTrackerExamSprint/instance/exam_sprint' /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/exam-sprint-distribution-20261126/verify_current_papers.py
```

## 写作核查边界

[writing-research.md](writing-research.md)：本机官方客户端0.9.20-rc.1有独立写作/专辑/按题型筛选、作文输入、草稿及复盘代码。可以作为题源候选；未核验当前实际题目/图表质量、数量、范文或AI/教师批改能力。公开目录在线核验审批被中止，没有换网络路径绕过；未读凭据、未写草稿/交作文/付费，未导入写作。

## 发布状态

业务提交 `dcfbd46dad34e957add0301d2a27d954b2c0b699` 加CI/日期fixture/重复布置兼容修复后，最终发布 **`3b26404ce21f7528e3c7e63703ca7f8268ad0465`** 已提交、原子推送任务分支及main，并已部署。首次CI的DB路由测试依赖错误由 `e82decbe` 修复；纯catalog/papers/Node仍留轻量job。最后提交还修复旧热榜任务重复布置选择的精确ID/篇章恢复，无法精确匹配时拒绝自动替换；更新已审核的听力模板摘要基线。

- 分支CI [45836190657](https://github.com/KB77GG/studytracker/actions/runs/45836190657) 和main CI [45836191351](https://github.com/KB77GG/studytracker/actions/runs/45836191351) 均success；test、account-provisioning、task-planner全成功，既有advisory lint仍failure，不声称全仓lint通过。
- Deploy [45836191831](https://github.com/KB77GG/studytracker/actions/runs/45836191831) success，精确发布HEAD一致。
- `production-acceptance.json`：生产 `/root/apps/studytracker` HEAD为3b26404c、tracked clean、active/running、NRestarts0、实际1 worker。5002只读GET两科200，目录阅读60/听力80，快照11/26 20:27；内存组卷两科各40/40判对。公网新JS 200且SHA与本次发布一致。未导入app/模型、未写生产学生记录、未保存生产模考。
- `verify_production.py --expected-head 3b26404ce21f7528e3c7e63703ca7f8268ad0465` 为只读验证器；实际通过SSH在服务器既有venv执行，调用argv保存在`release-facts.json`，不包含凭据。
- 本轮没有数据库schema改动，没有代老师布置真实任务或发送消息，也没有微信前端修改/上传/提审/发布。Mac周一06:00采集与每日会话维护保持原配置，runtime仍使用已验证的7bde8d67采集代码；本轮web组卷模块不需要重新安装collector。

本目录、runbook与两交接随独立`[skip ci]`文档提交同步，最终文档HEAD以Git核对，生产业务HEAD保持3b26404c，不为纯文档重复部署。旧主资料树main@6ded77d2原8M/27U保留、仅两交接增量，其他未提交业务仍仅本机；具体状态见`worktree-audit.json`。下一步老师从上述两个入口正常选学生/日期或创建pincode；以后有明确指令时再补浏览器真机与写作实际样题核查。
