# 提示词 .8 修复复验：老师批注通过，数字两类问题尚未完整关闭

复核基线：`597b2124d50257ffa69a40009bef5a0d5bc78202`，业务提交 `7af8397f`，提示词仍为 `iwa-2026-11-04.8`。本轮不改业务，未调用真实模型、未读 Key、未读学生素材。

结论：**暂未通过付费批次的离线前提**。上次报告的五个精确例子都不再复现；老师批注三项通过邻近回归，但数字两项在常见数量表达中仍有同根问题。不是要求无限扩展数词支持，也没有将已披露的 twice / a third 限制增加为缺陷。

用户现有授权仍是：离线通过后，用现有试用 Key 跑 `.8` / high、7 篇内置合成作文的评价，最多14次实际请求、每次输出上限16000；不含 max、其他模型、精修、改写、识图或老师素材。本轮 **0/14**，没有建立真实账本；修复并复核通过后可使用同一授权，不需重复询问。旧 A/B 批次已结束，不能复用。

## P2：并列百位、千位数仍被拼成新数

位置：`tools/ielts_writing_ai/figures.py:147–150`、`:173–176`（`split_en_numbers`）。

`and` 在 hundred / scale 后会无条件继续当前数字；它没有区分后面是同一个数的尾部，还是另一个并列的完整数。

| 原文中的数量 | 正确独立数值 | 实际解析 | 最终评价和复制文本 |
|---|---|---|---|
| `one hundred and two hundred passengers respectively` | 100、200 | 10200 | 正确100/200建议被删，错误10200建议被保留 |
| `one thousand and two thousand buses respectively` | 1000、2000 | 3000 | 正确1000/2000建议被删，错误3000建议被保留 |

反向对照也失败：原文写100和200，建议写同义的 `one hundred and two hundred`，建议被误删。原文写阿拉伯数字时，错误10200建议会被正确拒绝，说明放过它来自英文数词解析，而不是来源里本来存在这个数。

`forty and fifty` 的原修复有效；真正的 `one hundred and twenty-five` →125、`two thousand and twenty` →2020，以及1234567的完整英文写法都通过。建议依据完整数词组的结构分割并列项，而非只看 `and` 前一个词；明确的 `respectively` 并列语境不能被自动相加或重复乘规模。遇到不确定表达，至少不能将自行合成的新数当作可信来源。

证据：`figures_recheck.json` 的 `findings[0].cases`。每个案例同时记录来源解析、建议解析、丢弃计数、归一化结果与复制文本是否保留。

## P2：数量前的 from / to / of 仍被当成时间依据

位置：`tools/ielts_writing_ai/figures.py:189–190`、`:202–210`、`:304–305`（`confirmed_years` / `Sources`）。

这些原文都没有说明日期：

```text
The number of buses rose from 2000 to 2020 buses.
The sample consisted of 2000 buses and another fleet of 2020 buses.
Between 2000 and 2020 buses were recorded in the two cities.
```

程序把2000、2020认成两个年份，生成可信跨度20，导致下面的无来源建议进入最终结果和复制文本：

```text
Twenty years later, there were 2020 buses.
```

前置介词并不等于时间语境，尤其这些句子带有明确的数量单位。建议先排除数量及其区间，再以可辨认的日期上下文推算跨度；如果无法确认，应保留不确定性，不将其派生为可信时长。仅扩展介词名单不能解决这个问题。

正反对照：普通数量且无紧邻介词的原案例现在正确拒绝20年；真正的 `The study ran from 2000 to 2020.` 保留20年、拒绝30年；`in 2000 and 2020` 同样正确。

证据：`figures_recheck.json` 的 `findings[1].cases`。这些是对同一缺陷的常见上下文变体，不是新模型输出。

## 已通过

- 老师批注分母：1成功1失败为1/2=50%，成功口径另列1/1；不等批注数量、多失败为1/7，全失败0/5、条件比例为空。
- 老师批注位置：不同段相似句不覆盖；唯一字符区间相交才覆盖；重复引文只有部分相交时标“不确定”，不计覆盖。
- 老师批注对齐：倒序仍按引文和批注配对；缺失的一边标“无此批注”并提示；失败评价标“未评价”。新探针按“老师批注共”检索报告，文字与数值都验证过。
- `.8` 允许空问题、仍要求可信优点证据；没有证据的评价拒绝并重试。max仅影响评价，high/off预算不变；模型比较的消息、版本、样本保护仍在。
- 数字历史56项基线、12项正常补充断言通过；历史14条合成真实输出回放仍符合上轮预期。

## 验证与复跑

Mac、Python3.13.3：351项Python（21.194秒）和8项Node通过；ruff、black（48文件）、JS语法与diff检查通过。完整测试使用fake配置、临时库、仅回环网络；外部IWA_DATA_DIR未写入。探针使用模型替身或纯函数；日志中的 `http_500` 是刻意构造的失败，不是真实请求。

从仓库根运行（解释器按本机路径调整）：

```bash
PY=/Users/zhouxin/Desktop/studytracker/.venv/bin/python
REVIEW=docs/design/ielts-writing-ai-prompt8-recheck-20261105
$PY "$REVIEW/figures_recheck.py" --repo . --output /tmp/iwa-figures-recheck.json
$PY "$REVIEW/teacher_recheck.py" --repo . --output /tmp/iwa-teacher-recheck.json
$PY "$REVIEW/max_prompt_probe.py" --repo . --output /tmp/iwa-max-recheck.json
```

`figures_recheck` 的exit0表示记录过程成功，需看 `findings[].reproduced`；不能据exit0宣布产品通过。它复用已提交的上一轮探针和脱敏合成数据，旧文件原样保留。teacher和max探针断言的是正确行为。

精确测试命令、源HEAD及隔离结果见 `offline-verification.json`、`offline-tests.log`。本轮未重跑完整浏览器、Python3.10或全部locale，未评估新版真实模型质量。准备中的high-only付费运行器只在本机，入口禁用，未读配置或建真实账本。

## 交付与下一步

审阅工作树：`/private/tmp/studytracker-iwa-realcheck-review-20261103`，`claude/ielts-writing-ai-trial`；业务仍为597b2124。本报告、便携证据及两份规范交接仅推该功能分支，报告提交见git log。未合并main、未部署、未访问生产或写数据库，小程序未上传/提审/发布。

主资料树 `/Users/zhouxin/Desktop/studytracker` 仍main `6ded77d2`，原7个修改、23个未跟踪入口保留；本机runner和共享镜像只在该树，不应从此旧main发布。

下一轮只需补齐这两类数字规则并回归。通过后按已有14次授权启用新账本，再做 `.8` high 与旧 `.6` high 的人工比较。两版本还包含 `.7` 的语言/审题和数字后处理变化，该比较反映整体新版效果，不能将差异全部归因于去掉强制问题数或分数锚点。
