# 独立合成边界复核：3 类 P2，暂不通过“无误删”门槛

固定新源码 `/private/tmp/studytracker-iwa-task-conflicts-recheck-20261114`，HEAD `89c32d6b59f33ea2c4d3a592edd2248836d7de81`（业务 `a85808b`）；旧代码 `/private/tmp/studytracker-iwa-prompt15-final-recheck-20261113`，HEAD `40c0b5f1a9b6beaf8b6e2f0ab019e21c9263014c`。两树只读、前后 clean；未操作实际服务、配置、数据库或模型。

新 `adjacent_probe.py` 用 **完整 `review.normalize_evaluation`**，自行构造合法中文反馈、真实可验证引文和带正确 SHA 的 confirmed reading；不是只调用内部 `_values` 的测试。18 个合成情形 × 4 检查，**67/72，exit 1**。5 处失败归为下面 3 类问题；全部分项分数、原评语和单独计数检查通过。无来源数字移除数均为 0，说明误删来自新 `task_conflict` 规则。

## P2-1：同句裸数值相同即关联，误删不同实体、单位的正确建议

位置：`conflicts.py:27–32` 丢弃数值类别；`conflicts.py:87–89` 只查句子集合与裸数值集合相交。

完整归一化后的可复现反例：

| 原文 | TA 正确纠正 | 应保留的语言建议 | 新结果 |
| --- | --- | --- | --- |
| Men accounted for 20%, while women accounted for 20%. | Men accounted for 30% | women represented 20% | 被删，task_conflicts=1 |
| The share was 45%, while the journey lasted 45 minutes. | The share was 40% | the journey took 45 minutes | 被删，task_conflicts=1 |
| Television peaked at 22:00, while radio reached 22%. | Television peaked at 21:00 | radio attracted 22% | 被删，task_conflicts=1 |

各题图明确支持纠正后的男性比例/百分比/时间，也支持另一实体的原数字。语言引文与 TA 引文分别指向不同分句，只有数字偶然相同。三个正确建议都从复制文本中消失，并被“请按 TA 改正”的说明替代。旧 `40c0b5` 的相同完整归一化保留它们，因此是新过滤器引入的误删。

建议至少保留数值类别、具体出现位置和纠正对象关联。仅保留 `kind` 仍不能解决同句男女各 20% 的例子；不确定是否同一事实时保守不自动删。

## P2-2：重复短引文只取第一处，跨句错误归属

位置：`conflicts.py:58–64`，`self.text.find(needle)` 固定首处。

原文：`Radio reached 45% at noon. Television reached 45% at night.`

TA 唯一引文是 `Radio reached 45% at noon`，正确改为 40%；图中夜间电视确实 45%。LR 的短引文为 `reached 45%`，建议为 `Television attracted 45% at night`。短引文出现两次，建议明确针对第二句电视，但程序将引文绑定第一句，删除正确的电视建议。`quote_found=true` 只证明存在，不证明首处就是该条反馈的目标。旧版保留、新版删除；错误说明也进入复制文本。

不要简单改成“取所有出现位置，只要任意与 TA 相交就删除”，那仍会误删该例。应使用唯一可验证的位置/完整原引文；歧义无法消除时不作自动删除。

## P2-3：用于展示的 300 字符截断先发生，真实替换数字丢失后漏删

位置：`review.py:148–154` 验证完整原引文后只保留前 300 字符，随后 `conflicts.py:40` 对截断字段取数。

合成 345 字符、单句完整 TA 引文包含 `reached 45% at 22:00`，该部分位于第 300 字符之后。TA 合法建议完整保留句子、只改 45%→40%；图中支持 40%。LR 的短引文明确引用尾部数字，仍建议 `attracted 45% at 22:00`。

两个完整原引文都可在原文找到；但 TA 显示引文截断后已无 45%，结果 `task_conflicts=0`，旧数字建议继续显示和复制。该例没有依赖超出产品允许范围的输入，也没有“趋势判断”或小数字例外。旧版也不检查，属于新功能未覆盖的有效输入，不是新的评分回归。建议内部计算保留完整已验证引文/原文跨度，展示层再截断。

## 通过项与明确的范围限制

正常同实体纠正、语言建议跟随纠正、另一句的同值数字、4.5%→4.8%、22:30→22:45 均正确。未核图和读数确认后漂移时 TA 不评分，不触发冲突删除；TA 建议新增无来源数字会先被移除，不再驱动冲突检查。仅加数字、仅删数字不触发，符合设计。

以下在探针中明确标为 `limitation`，不算新缺陷：

- 小于 10 的普通数值被主动排除，因此 08:00→09:00 不触发。分钟 00 同理。
- 两个数值互换（45/40→40/45）不产生集合意义的“旧数字消失、新数字出现”，当前规则不检出。
- 同一份 TA 建议本身可以判断错误，只要所用数字在其他地方有来源就可能存活。规则会服从这条 TA 建议；本轮探针展示这一风险，但没有把自动核实任意 TA 语义作为本轮必须新增的能力。页面“请按 TA 改正”不能视为程序已验证 TA 事实正确。
- 纯趋势冲突仍不在设计范围，不据此阻止本次升级；本次阻断来自以上实际误删和有效数字替换漏检。

## 命令和产物

在 `/Users/zhouxin/Desktop/studytracker`：

```bash
.venv/bin/python -B docs/design/iwa-task-conflicts-recheck-20261114/adjacent_probe.py \
  --repo /private/tmp/studytracker-iwa-task-conflicts-recheck-20261114 \
  --out docs/design/iwa-task-conflicts-recheck-20261114/adjacent_probe.json

.venv/bin/python -B docs/design/iwa-task-conflicts-recheck-20261114/adjacent_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113 \
  --out docs/design/iwa-task-conflicts-recheck-20261114/adjacent_baseline.json

.venv/bin/python -m ruff check docs/design/iwa-task-conflicts-recheck-20261114/adjacent_probe.py
.venv/bin/python -m black --check docs/design/iwa-task-conflicts-recheck-20261114/adjacent_probe.py
```

新代码 67/72；旧代码也是 67/72，但失败集合不同，不能仅比较总数：旧代码没有新数字冲突过滤，正常新功能正例预期失败；**4 个新误删反例在旧版全部保留**。详细逐例预期、反馈、复制文本标志和计数见两份 JSON。Ruff/Black 通过。

页面本轮只审查源码 `iwa.js` 的 `removedNote` 分支与后端字段，没有运行真实浏览器；复制文本通过实际 `copytext.copies_for` 验证。没有付费请求、未取实际账户/Key/学生数据、未修改产品。新增合成探针和报告仅主资料树本机，交接由主审归并，本子任务未 commit/push/deploy。
