# 写作试用 `.12` 离线复验（2026-11-09）

**复验通过，未发现本轮新增缺陷。** 上轮 CC 评分边界冲突已关闭，系统规则中的已知开发样本例子已移除，旧回归夹具、原稿输入、严格解析及预算控制保持。此结论不代表真实模型的 JSON 成功率或评分准确度已提高。

审阅源 `/private/tmp/studytracker-iwa-prompt10-review-20261108`，本地分支 `codex/iwa-prompt10-review-20261108`，由干净 `fba35562` 快进到 `135a301359e6758641a1cdadf1f540e614fc58f8`（业务 `e370b0c9`）。源提示词版本为 `iwa-2026-11-10.12`。81 个工具文件合并 SHA256 为 `f0178c720a8ecbe3796952122fb219453695ef93bd6ee073df4893f5d8ce39fd`，本轮前后一致。

## 修复验收

评分边界的新规则实际进入了七篇评价消息及一份 Task 1 有图状态正对照：TR 看任务回应、立场、相关性与展开支撑；CC 看组织、逻辑推进、分段、衔接和指代；Task 1 使用 TA 的概述、关键特征与数据规则；LR/GRA 只用相应语言证据。论证检查的开头和结尾均改成按每条发现的实际证据归入对应维度，不再要求每个问题同时反映到 TR 和 CC。原冲突两端都已处理，详见 [边界专项复核](boundary_review.md)。

系统规则中的 19 个已知样本措辞全部移除。独立检查覆盖 evaluate/refine/rewrite 的七篇消息共 21 组，另外核对旧八份 `realcheck_*.json` 夹具及 `samples.py` 的 Git/工作树内容均未变。通用规则仍保留原意、数字来源、限定立场和文内比较的约束。题干与作文仍完整保留在 **user 输入** 中：清理的是系统规则的样本例子，不是删除待评作文。精修、改写、说明重试和识图消息没有改变。详见 [样本例子与离线证据复核](exposure_review.md)。

旧结构探针确认三种 schema、占位拒绝、mid 两次坏 JSON 的严格拒绝及重试上限、六篇有效回复改变键序后的完整结果均不变。`llm.py/review.py/argument.py/jsonshape.py/config.py` 没有改动。六份缺括号、另一份提前闭合以及指定字段结尾的文档表述已更正。

## 验证结果

| 检查 | 结果 |
|---|---:|
| 完整 Python 套件 | 392/392，21.498 秒 |
| Node 草稿测试 | 8/8 |
| 新边界探针 | 199/199 |
| 新样本清理及输入保留探针 | 155/155 |
| 上轮结构探针（原文件未改） | 125/125 |
| 上轮反馈探针（原文件未改） | 103/103，原 P2 不再复现 |
| 原条件提醒探针 | 341/341 |
| 原提醒/回放统计探针 | 120/120 |
| ruff、black（55 文件）、JS 语法、diff 检查 | 通过 |

主资料树 `.venv/bin/python` 为 3.13.3；完整套件运行器是本机 `docs/design/iwa-prompt12-review-20261109/run_offline_tests.py`。测试剔除外部 IWA 配置与代理，使用假模型和临时数据库，网络限于回环地址；因本地端口需要沙箱外运行，按批准的同一运行器执行。外部测试数据目录未写。证据在 `offline-tests.json` 和 `offline-tests.log`。

主审逐个复跑了两份新探针和四份既有探针。没有重复三种 locale、Python 3.10、全部 50 个历史探针或完整浏览器流程；页面及运行代码未变。没有真实模型请求、私有 Key 或思考记录读取。

独立审阅树中的复跑命令：

```bash
PY=/Users/zhouxin/Desktop/studytracker/.venv/bin/python
OUT=/private/tmp/iwa-prompt12-recheck
mkdir -p "$OUT"
$PY -B docs/design/ielts-writing-ai-prompt12-review-20261109/boundary_probe.py --repo . --output "$OUT/boundary.json"
$PY -B docs/design/ielts-writing-ai-prompt12-review-20261109/exposure_probe.py --repo . --output "$OUT/exposure.json"
$PY -B docs/design/ielts-writing-ai-prompt11-review-20261109/structure_probe.py --repo . --output "$OUT/structure.json"
$PY -B docs/design/ielts-writing-ai-prompt11-review-20261109/feedback_probe.py --repo . --output "$OUT/feedback.json"
$PY -B docs/design/ielts-writing-ai-prompt10-reminder-review-20261109/reminder_probe.py --repo . --output "$OUT/reminder.json"
$PY -B docs/design/ielts-writing-ai-prompt10-reminder-review-20261109/metrics_reminder_probe.py --repo . --output "$OUT/metrics.json"
```

六个命令均退出 0。原 feedback 探针的历史 findings 对象仍存在，但 `reproduced` 为 false；这不是未关闭的问题。

## 老师样本及后续真实验证

用户本轮明确确认：**`teacher-t2-01` 的四处批注位置没有问题**。此项按用户确认记录，已经不再等待位置确认；不是本 agent 重新阅读原稿后的独立验收。

交接记录该文件由 Claude 整理在临时 scratch、未入 Git，用户表示文件在本地。本轮未在仓库及建议的 `~/iwa-calibration/` 找到对应 JSONL，也没有收到可定位的具体路径；未读取原稿或评语内容。因此老师样本的实际加载、内容哈希、字段完整性及真实请求准备仍未执行。后续只需要定位该文件，不要重复询问已经确认的四处批注。

真实验证仍须新授权；“批注位置没问题”不等于授权付费调用或发送作文。前批 8/14 已关闭，余次不能继续追加。未来开发回归组可用 `.12/high/32000/300 秒`，七篇只评价、最多十四次；如再加老师样本，应在文件已定位后单独明确最多两次及发送范围，所有调用统一计账，不能把老师样本悄悄加进原十四次计划。

这七篇只能检查已知错误与格式稳定性，删去例子不能恢复独立性。单篇老师作文可以对照这篇的反馈和总分差异；若只有总分，则不能计算四项分数误差，也不能凭一篇认定校准完成。后续依据实际报告再决定是否调整，不以离线通过声称真实效果。

## 交付状态

本目录十三份审阅文件与 `docs/CODEX_HANDOFF.md`、`docs/WORKLOG.md` 按既有授权仅同步功能分支 `claude/ielts-writing-ai-trial`，最终报告提交号见 Git 历史。主资料树 `/Users/zhouxin/Desktop/studytracker` 仍为旧 `main@6ded77d2`，原七个 modified 和二十三个 untracked 顶层入口及其他任务保留。本机运行器、源状态和过程记录在 `docs/design/iwa-prompt12-review-20261109/`，不提交。

没有修改产品或私有配置，未合并/推送 main、未部署、未访问生产或写库，小程序未上传/提审/发布。老师材料本身没有加入报告或仓库。
