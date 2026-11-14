# 数字冲突过滤复核：暂不升级 Mac（2026-11-14）

**本轮复核不通过升级门槛。L11 已正确拦住，L9 仍保留；新规则还会误删合理建议。** Mac 保持原 `40c0b5f1` / 业务 `d92f0839` / `.15`，识图继续开启，本轮没有调用模型或重新处理历史记录。

复核对象是功能分支 `89c32d6b59f33ea2c4d3a592edd2248836d7de81`，业务提交 `a85808b4`；作者交接 [README](../iwa-task-conflicts-claude-20261114/README.md)已读取。独立源树 `/private/tmp/studytracker-iwa-task-conflicts-recheck-20261114`，分支 `codex/iwa-task-conflicts-recheck-20261114`。调用基线为 detached `18f5f08` 的固定复算树；旧运行树 `40c0b5f1` 与它产品相同。产品源码均未修改，后续共享提交只添加 docs。

## 八份真实原始回答：203/204

用 11 月 14 日已关闭批次的八份原始 JSON 和原 submission，分别执行旧、新 `review.normalize_evaluation`，禁用网络，没有重新请求模型。主审用独立私有输出目录再次执行，结论一致。

- 旧版 **8/8 逐字段精确再现**原保存结果，新旧 **8/8 分数、消息指纹、原稿与读数输入不变**。
- 仅 **L11** 新增删除，确认是合理拦截；该篇 `task_conflicts=1`，其余七份为 0。旧的无来源数字删除计数没有混入该计数。
- 另外 **80 条原有可见建议逐字保持**。本批未出现新增误删，但这不能推广到其他输入。
- **L9 未关闭**：相关 TA 改正建议先被既有无来源数字保护清空。新规则读取归一化后的空建议，失去数字替换依据，所以 GRA 建议仍保留 TA 评论已指出有误的数字。私有诊断确认原替换集合非空、引文同句、语言建议保留旧值；并非没定位到句子。
- H1 的未找到引文警示、H2 的旧建议过滤、H3/H4 的问题评论均保持。趋势类 L1/L4/L5/L7 按设计仍在，不把未承诺的趋势识别算成本次新缺陷。

详见 [replay.json](replay.json)、[逐项复核](replay-review.json)。完整重放结果、原始片段和差异只保存在主树 `.tmp/iwa-task-conflicts-recheck-20261114/`，未覆盖原批任何文件。不能通过直接信任已被过滤的原始 TA 建议来绕过无来源数字保护；L9 需要在保留既有保护的前提下明确处理。

## 合成相邻情形：67/72

18 个情形通过完整归一化入口验证，含合法已绑定的题图确认和真实可定位引文。5 个失败均由主审复跑确认；分数、评论保留和独立计数检查通过。

| 问题 | 具体触发 | 结果 |
|---|---|---|
| P2：同句数值偶合误删 | 男性 20% 被纠正为 30%，却删去同句女性正确 20% 的语言建议；45% 与 45 分钟、22:00 与另一实体 22% 也被混为一谈 | 3 个正确建议被删，复制文本也显示错误删除说明 |
| P2：重复短引文定位歧义 | 两句均含同一短引文；TA 纠正第一句，语言建议明确指向第二句，却被固定首处匹配关联到第一句 | 另 1 个正确建议被删 |
| P2：展示截断丢失纠错依据 | 完整合法 TA 引文超过 300 字符，被纠正数字位于尾部；先截断展示引文后再取数字 | 有效数字冲突漏删 |

四个误删反例在旧版都保留，是新增回归。长引文情形旧版本来也不检查，是本轮新增功能的有效输入遗漏。新旧探针总分恰好都是 67/72，但失败集合不同，不能只比较退出码或总数判断“无变化”。完整合成例、行号及建议在 [adjacent_review.md](adjacent_review.md)，新旧数字证据见 [adjacent_probe.json](adjacent_probe.json) / [adjacent_baseline.json](adjacent_baseline.json)。

保留数值类别还不足以区分同句两个实体的相同百分比。需要绑定具体事实与可靠的引文位置；引文歧义未消除时应保守不删。内部判断应使用完整已验证引文，展示截断不能改变判断。这里没有要求自动核实模型任意 TA 语义，也没有将小数字、数值集合互换或纯趋势规则的已声明限制混入失败项。

## 可复现命令

从主资料树 `/Users/zhouxin/Desktop/studytracker` 执行；独立 source 树必须 clean。原始批次只读，新的完整输出必须放入 ignored 私有目录。合成探针在另一台机器也可运行，实样重放需要 Mac 私有材料。

```bash
.venv/bin/python -B docs/design/iwa-task-conflicts-recheck-20261114/replay_probe.py \
  --baseline /private/tmp/studytracker-iwa-official-t1-replay-20261114 \
  --candidate /private/tmp/studytracker-iwa-task-conflicts-recheck-20261114 \
  --run-data /Users/zhouxin/Desktop/studytracker/.tmp/iwa-official-t1-20261114/run/evaluate/run_data.json \
  --raw-calls /Users/zhouxin/Desktop/studytracker/.tmp/iwa-official-t1-20261114/run/evaluate.raw-calls.private.jsonl \
  --private-out /Users/zhouxin/Desktop/studytracker/.tmp/iwa-task-conflicts-recheck-20261114/replay-again \
  --out /private/tmp/iwa-task-conflicts-replay.json
# 203/204，exit 1：finding:L9:newly_removed 失败。

.venv/bin/python -B docs/design/iwa-task-conflicts-recheck-20261114/adjacent_probe.py \
  --repo /private/tmp/studytracker-iwa-task-conflicts-recheck-20261114 \
  --out /private/tmp/iwa-task-conflicts-adjacent.json
# 67/72，exit 1：4 个新增误删、1 个长引文漏检。
```

探针保留正确期望，不将失败改成“符合设计”以获得绿色结果。没有修改产品测试或原始样本，也没有启动新的真实批次。

## 常规回归检查

本机 Python 3.13.3，**502 Python + 8 Node 全部通过**；特意设置外部 `IWA_VISION_PROVIDER=none`，测试使用 fake 模型、临时数据目录且阻断非回环连接，数据哨兵未被写入。完整日志仅本机，数字证据见 [offline-tests.json](offline-tests.json)。首次沙箱内有 24 项回环端口权限错误，获得沙箱外执行许可后同套件通过；不把权限错误当产品失败。首次子任务的沙箱外请求未完成，最终通过结果来自主审补跑。

```bash
.venv/bin/python -B docs/design/iwa-task-conflicts-recheck-20261114/run_offline_tests.py \
  --repo /private/tmp/studytracker-iwa-task-conflicts-recheck-20261114 \
  --out /Users/zhouxin/Desktop/studytracker/.tmp/iwa-task-conflicts-recheck-20261114/offline-approved
```

产品 Ruff / Black（71 文件）、`node --check tools/ielts_writing_ai/static/iwa.js` 及报告探针静态检查通过。本轮未重复作者的三种 locale、Python 3.10 或全部历史探针，也未运行真实浏览器。常规套件通过不能替代上面暴露具体误删的定向反例。

既有排队门禁 **20/20**、网页相邻项 **57/57**、realcheck **15/15 + 17/17** 均通过，原五项确认绑定问题没有回归。四条命令及数字证据见 [regressions/README.md](regressions/README.md)；合计 109 项通过不改变本轮新规则的失败结论。

## 本机、共享与下一步

- 主资料树仍 main@`6ded77d24586327ad94e151e172ae4811b4a2eed`，原 7 modified / 23 untracked 顶层入口和其他任务改动保留。只增加本轮报告、探针及交接增量。
- 本机运行树保持 `/private/tmp/studytracker-iwa-prompt15-final-recheck-20261113`@`40c0b5f1`，PID 38918、5055 健康。没有备份迁移、修改配置/数据库或重启；本轮未重新登录实际账号或读取试用库，不把此前的库计数当成本轮新认证。只读 `control.py check` 确认识图 deepseek/Flash/2000/180、评价 Pro/high/32000/420，control 路径未变；见 [service-state.json](service-state.json)。
- 原 `1 图 / 0 文字` 和新 `3 图 / 8 文字` 两个 closed 批次均不重开。原稿、题图、确认读数、完整回答/思考、配置、Key 和库不入 Git；本轮真实模型调用 **0**。
- 按既有共享授权，仅将脱敏报告/探针与本写作任务交接提交推送到 `claude/ielts-writing-ai-trial`；最终提交与回读见 Git 和主树交接确认条。没有合并 main、部署生产后端/前端/数据库；小程序未上传、提审或发布。
- Claude 可先复现公开四个误删反例和长引文漏检，再处理 L9 的内部纠错信息保留，修后保持现有来源校验。目标仍是实样 **204/204** 和合成 **72/72**，再决定升级。老师 10 项仍待填写，评分校准、趋势冲突和 H3/H4 不在本轮关闭范围。
