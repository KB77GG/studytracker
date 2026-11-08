# `.10` 删除建议复验：旧场景关闭，仍有四处确定的 P2

复验业务提交 `7639dd5a3dc3e51020899e403cc939f54e3bdc82`，源 HEAD `371aeeb8c443586a08dbc4ce427957dc8b41bc4c`，对比上一轮报告 `075f5af3`。提示词未改，仍是 `iwa-2026-11-08.10`。本轮只读产品和已提交的合成作文夹具，没有模型调用、Key/私有思考/学生资料读取、配置或业务代码修改。

**上轮两类问题的全部原反例已经关闭**：删除189/189、JSON结构175/175、历史指标120/120。新模块的常用否定/单引号以及计数和无效目标仍存在四处反例，都已通过真实 `normalize_evaluation → copytext.evaluation_text` 路径复现。下面的数字是服务端新加的说明，不是模型原本生成的错误数字；分数和学生原稿未被修改。

## P2-1：常用否定失效，明确要求保留却生成删后不足提醒

`tools/ielts_writing_ai/deletion.py:33`、`:35`、`:168`。

172词的真实合成Task1，问题引文为23词末段：

- `别删去这一段，应保留比较信息。`
- `Don’t delete this paragraph.`（弯撇号）
- `You shouldn't delete this paragraph.` / `You shouldn’t delete this paragraph.`

以上均没有删除操作，应保持172词；当前却在建议、顶部提示和复制结果中确定地写“删去后约剩149词，低于150”。对应的 `不要删掉这段`、`Do not delete`、`You should not delete`、ASCII `Don't delete` 正对照均正常。

中文并非没列关键词：`别(?=删|去掉|拿掉)` 已在规则里，但调用只传入删除动词**之前**的字符串，前瞻必然看不到删除动词。英文缩写及弯撇号未规范化。应先统一常用符号与否定形式，并在实际包含动词的上下文判断，不能让已写的规则永远无法命中。

## P2-2：单引号未被当作引文，删两个词变成删整句

`deletion.py:39`、`:101`、`:122`。

`Remove only 'In summary' from this sentence.` 或弯单引号版本，只删两个词，应剩170，不需要不足提醒。当前只屏蔽双引号，随后将 `sentence` 当成被删对象，扣23词并显示149。`Ignore the advice 'delete this paragraph' and keep it.` 也会将引用且明确拒绝的删除意见当成实际操作。相同文字改成双引号后均正常。

建议支持成对单引号/双引号并区分英语缩写的撇号，始终先识别引用边界，再判断引号外的动作。暂时无法区分时，不生成确定的整句删除字数。

## P2-3：不同描述指向同一原文，删除字数被重复累计

`deletion.py:83`、`:89`、`:209`。

同一条建议 `删去最后一段；删去最后一句。` 中，本篇末段恰好就是末句，都是同一段23词原文。正确结果是172−23=149；当前按两种单元各扣一次，显示126。`删去最后一段；删去“In summary”两个词。` 同样重复扣段内两词，显示147。中英、评分项、提升重点、Task2可选优化均复现；Task2正确244却显示211。

这是原文位置的重叠问题，单纯对 `(kind,index)` 去重不够。应把已确定的段、句、片段转换为原稿中的区间，合并重叠区间后计算一次。不能按文本相同就跨位置去重，也不能把不同可选建议跨条强行累计。本探针只检验**同一条建议**中的操作；“首段18词+末段23词”正确剩131、重复指同一段正确149、两渠道各自提示等正对照都通过。

## P2-4：明确但不存在的目标被当成“未指明目标”，删到别段

`deletion.py:142`、`:151`、`:191`。

原文只有5段，建议 `删去第九段。`。程序能解析到9，但越界时直接丢弃，返回“没有命名位置”；随后回退到问题引文所在的末段，给出确定的149词。提升重点里明确第九段又引用末段内容，也得到同样错误结果。

应区分“没有提供目标”和“提供了无效/矛盾目标”。后者不得回退成另外一段；应该不给数字并提示定位问题。现有“有效首段位置与末段引文冲突”的正对照已经能给非数字提示，可以沿用该处理方向。

## 验证与边界

| 检查 | 结果 |
|---|---|
| 原删除探针（未修改） | 189/189，findings=0 |
| 原JSON结构探针（未修改） | 175/175 |
| 原指标探针（未修改） | 120/120 |
| 新意图/引号探针 | 22场景，146/178；8失败场景归并P2-1/2，14正对照通过 |
| 新目标/计数探针 | 17场景，92/112；8失败场景归并P2-3/4，9正对照通过 |
| 完整套件 | 387 Python（21.255s）+8 Node，全部通过 |
| 代码检查 | Ruff、Black（53文件）、JS语法、diff检查通过 |

两个新探针共52个失败断言属于上述四处问题，不是52个独立缺陷。主审已独立重跑全部五个探针，检查期望来自明确操作和原文计数，未用被审函数输出充当预期。全部只用已公开合成夹具。完整套件通过隔离runner运行：fake模型、临时库、外部IWA配置剔除、外部连接禁止；获准绑定本机回环端口，外部测试数据目录未被写入。

没有重复38个历史探针、三种locale、Python3.10或真实浏览器布局。本轮检验服务端结果和复制文本；未声称完整自然语言覆盖。旧JSON和报告契约保持通过，不代表`.10`真实模型格式率或评分准确度已改善。

## 复现

在仓库根目录运行，按本机修改 `PY` 和 `REPO`。原三个探针预期exit0；本轮两个新探针当前预期exit1，应修产品而不是翻转正确行为断言。

```bash
PY=/Users/zhouxin/Desktop/studytracker/.venv/bin/python
REPO=/private/tmp/studytracker-iwa-prompt10-review-20261108
OLD=docs/design/ielts-writing-ai-prompt10-review-20261108
NEW=docs/design/ielts-writing-ai-prompt10-recheck-20261108
$PY -B "$OLD/deletion_probe.py" --repo "$REPO" --output /tmp/iwa10-recheck-deletion.json
$PY -B "$OLD/schema_probe.py" --repo "$REPO" --output /tmp/iwa10-recheck-schema.json
$PY -B "$OLD/metrics_probe.py" --repo "$REPO" --output /tmp/iwa10-recheck-metrics.json
$PY -B "$NEW/intent_probe.py" --repo "$REPO" --output /tmp/iwa10-recheck-intent.json
$PY -B "$NEW/target_probe.py" --repo "$REPO" --output /tmp/iwa10-recheck-target.json
```

完整套件本机命令为桌面主树 `.venv/bin/python docs/design/iwa-prompt10-recheck-20261108/run_offline_tests.py`。runner只留本机；共享的 `offline-verification.json` / `offline-tests.log` 记录实际命令、结果和范围。

## 下一步与同步

建议修复聚焦三项基础约束：正确处理否定与引用边界；明确无效目标不能回退；原文区间去重后计数。继续保留严格JSON和原稿只读，不必为这四处问题改变提示词或思考强度。本轮仅审阅，没有代为实施修复。

当前不能给删除检查完整通过结论；先离线修复，再复验。`.10`真实运行需新授权；本轮没有开新账本、调用模型或提高16000上限。旧`.9`批次已结束，未用次数不转入新批。

审阅树 `/private/tmp/studytracker-iwa-prompt10-review-20261108`，本地分支 `codex/iwa-prompt10-review-20261108`，跟踪并仅推远端 `claude/ielts-writing-ai-trial`。本报告、探针和两份交接提交推送；主树本机runner及过程状态未提交。没有合并main、部署、访问生产数据库或操作小程序。旧失效IWA worktree和主树其他任务的未提交改动均保留。
