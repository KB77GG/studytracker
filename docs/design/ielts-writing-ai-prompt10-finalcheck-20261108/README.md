# `.10` 删除检查第二次复验：原四项关闭，仍有三类 P2

复验业务 `95763337`，源 HEAD `03d2d4c4a44c110e67c4d89967d08b3088bfde61`，基线 `c82ebbfcee25cbfcb17a42aeebb9370b980b2c2a`。提示词仍为 `iwa-2026-11-08.10`。只读产品代码与已提交的合成作文输出，没有读取Key、私有思考或学生材料，没有配置/业务修改、真实模型请求或生产操作。

**上一轮四处问题的原场景均已修复**：五个原探针未改即可通过。新检查发现一项计数结果回归及两项既有遗漏。问题影响服务端追加的删除字数提醒，不会直接修改原稿或分数；结果和复制文本均能复现。不是把未覆盖的所有自然语言变体都算缺陷，而是明确动作、原文位置和普通序号的处理仍有结构性问题。

## P2-1：局部删词丢失段落位置，被误合并为已经删掉的文字

位置：`tools/ielts_writing_ai/deletion.py:245–248`、`:141–153`。

172词的合成Task1：末段23词，第二段和末段各有一次 `Country A`。建议：

> 删去最后一段；删去第二段中的“Country A”两个词。

正确应为172−23−2=**147**；结果与复制文本都写**149**。英文、提升重点、调换动作顺序均复现；反向“删第二段，再删末段中的Country A”应134，实际136。同一段内真实重叠、不同整段、不同建议独立计数的正对照通过。

原因：`passage`路径只保存引文文本，未保存“第二段”这个限定；计数时优先选择已经被删除范围内的相同词，导致明明位于不同段落的两个位置被合并。应先在明确段落内解析局部引文的位置，再合并实际区间；不能为了去重而选择某一次出现。

阈值反例进一步确认了实际影响：仅在首段加一个`clearly`，总字数变为173，末段仍23词、第二段目标仍2词。正确删后148词，旧版会提醒；新版错算150，**整条字数不足提醒消失**。原稿并未被自动删除，问题在于用户按建议操作时会缺少该提醒。

`baseline_compare.py`固定当前normalize/copy，仅在进程内切换新旧deletion模块，确认旧版在上述不同位置场景报147、新版149，因此属于可观察的新回归。但旧版只是按文本长度相加而碰巧算对，不代表旧定位正确，也不建议回退整套实现。

## P2-2：前一句或另一动作的否定，抑制了明确的删除建议

位置：`deletion.py:49`、`:222–224`、`:239–241`。

以下都明确要求删去23词结尾段，应提示剩149词，当前却完全不提示：

- `Do not remove the introduction. Delete the conclusion.`
- `This paragraph is not necessary and you should delete the conclusion.`
- `不要重复概述而应删去结尾段。`

把第一例的英文句点换为分号就正常。反向写 `Delete the conclusion. Do not remove the introduction.` 时，则把不应删除的首段纳入目标冲突，显示“无法确定”。评分项和提升重点均复现。

原因：未按英文句点拆分，每小句只处理第一个删除动词；动词前任何否定均会影响这个删除动作，即使否定的是“必要性”“保留”“重复”。这不是缺几个否定词，而是没有绑定各自动作的作用域。旧版也有同样结果，属于既有遗漏。建议先识别独立动作，再限定各自的否定和目标；复杂情况下给保守提示，不应静默当成“没有删除”。

## P2-3：明确序号换成普通写法，仍被当成没指定目标

位置：`deletion.py:73–80`、`:193–219`、`:266–269`。

- `删去第 2 段。`、`Delete the 2nd paragraph.`：应删36词第二段、剩136，当前退回问题引文所在末段、报149。
- `删去第 9 段。`、`Delete the ninth paragraph.`、`Delete the 9th paragraph.`：原文只有5段，不能给确定数字；当前仍回退末段、报149。

`第二段` / `second paragraph`、`第九段` / `paragraph 9`的原写法已正常。缺口是把“有明确位置但未解析”与“完全没有位置”混为一类；旧版也有。至少应先识别显式位置表达是否存在，无法解析或越界时禁止回退，再处理普通空格、序数格式。

## 验证

| 检查 | 主审独立复跑结果 |
| --- | --- |
| 原删除探针 | 189/189，findings=0 |
| 原JSON结构探针 | 175/175 |
| 原指标探针 | 120/120 |
| 上轮意图探针 | 178/178，findings=0 |
| 上轮目标探针 | 112/112，findings=0 |
| 新意图探针 | 27场景186/217；10失败场景归并P2-2，17正对照通过 |
| 新目标探针 | 20场景102/128；10失败场景归并P2-1/3，10正对照通过 |
| 新旧模块对照 | 13场景，确认局部位置合并结果回归；跨句否定/序号为原有遗漏，原稿/分数/源码均不变 |
| 完整测试 | 397 Python（21.277s，wrapper21.55s）+8 Node，全部通过 |
| 检查 | Ruff、Black（53文件）、JS语法、diff检查通过 |

新探针合计57个失败断言对应三类问题，不是57个问题。预期按实际删除位置计算，没有把被审函数输出作为预期；完整normalize→copy路径保留原稿及分数。产品78个tracked文件SHA前后一致：`b07c3243f909598cad0a5482ed4a72a4152e7432b34ad39b3b45429111ee14b2`。

完整测试采用fake模型、临时库、剔除外部IWA环境、只允许回环网络。第一次受沙箱回环端口限制失败，经允许后重跑成功，外部测试数据目录未被写入。未重复全部40个历史探针、三种locale、Python3.10或浏览器全流程；本轮页面未变，只验证结果数据与复制文本，不声称真实模型质量已改善。

## 复跑

在仓库根目录执行。旧五探针预期exit0；新两探针当前exit1表示上述正确行为尚未达到，不要翻转预期掩盖问题。

```bash
PY=/Users/zhouxin/Desktop/studytracker/.venv/bin/python
REPO=/private/tmp/studytracker-iwa-prompt10-review-20261108
FIRST=docs/design/ielts-writing-ai-prompt10-review-20261108
SECOND=docs/design/ielts-writing-ai-prompt10-recheck-20261108
NEW=docs/design/ielts-writing-ai-prompt10-finalcheck-20261108
$PY -B "$FIRST/deletion_probe.py" --repo "$REPO" --output /tmp/iwa10-final-old-deletion.json
$PY -B "$FIRST/schema_probe.py" --repo "$REPO" --output /tmp/iwa10-final-old-schema.json
$PY -B "$FIRST/metrics_probe.py" --repo "$REPO" --output /tmp/iwa10-final-old-metrics.json
$PY -B "$SECOND/intent_probe.py" --repo "$REPO" --output /tmp/iwa10-final-old-intent.json
$PY -B "$SECOND/target_probe.py" --repo "$REPO" --output /tmp/iwa10-final-old-target.json
$PY -B "$NEW/intent_probe.py" --repo "$REPO" --output /tmp/iwa10-final-intent.json
$PY -B "$NEW/target_probe.py" --repo "$REPO" --output /tmp/iwa10-final-target.json
$PY -B "$NEW/baseline_compare.py" --repo "$REPO" --output /tmp/iwa10-final-baseline.json
```

`baseline_compare.py`退出0只表示对比成功、源码/输入/分数不变，不表示所有功能用例通过。逐例看`classification`。加载旧模块只在进程内，没有回退工作区文件。

完整套件本机命令：桌面主资料树 `.venv/bin/python docs/design/iwa-prompt10-finalcheck-20261108/run_offline_tests.py`。共享的 `offline-verification.json` 和 `offline-tests.log` 保存精确命令、结果、隔离条件；runner和首次沙箱失败日志只留本机。

## 下一步

避免继续靠扩大关键词清单追逐表达变体。建议收紧三个处理约束：每个动作分别确定否定与目标；先保留局部位置、再做原文区间并集；显式位置无法解析时不得回退。如果短期无法可靠处理复合建议，可以对这类建议统一提示先核对字数，不给伪精确的剩余词数。

本轮没有修改产品、开新账本、调用模型或提高16000上限；`.10`真实验证仍需新授权。先修复离线三类问题或明确采用上述保守退路，再讨论新批次。JSON/分数/原稿契约继续保留。

审阅树 `/private/tmp/studytracker-iwa-prompt10-review-20261108`，本地 `codex/iwa-prompt10-review-20261108` 跟踪远端 `claude/ielts-writing-ai-trial`。本报告与探针按已有报告同步授权仅推该功能分支，最终文档提交号见git log；不合并main、不部署。主资料树 `/Users/zhouxin/Desktop/studytracker` 仍main `6ded77d2`，既有7 modified/23 untracked入口与其他任务资料保留，仅新增本机验证材料和交接记录。
