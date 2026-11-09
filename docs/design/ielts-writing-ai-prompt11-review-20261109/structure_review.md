# .11 输出结构独立复核

本项只核对结构、严格拒绝和旧回答兼容性，不判断模型下一批会不会更稳定。

- 审阅树：`/private/tmp/studytracker-iwa-prompt10-review-20261108`。
- HEAD：`19169e62`，业务 `8510ea8e`，对照基线 `436ad2f2`。
- 便携探针：`structure_probe.py`；结果：`structure_probe.json`，**125/125**。
- 所有输入来自已提交的合成作文及脱敏正式回复；脚本禁止 socket connect/bind，不读配置或密钥，不调用模型。

## 已核实

1. Task 2、Task 1 有图、Task 1 无图三种完整示例都可直接 JSON 解析，而且实际 `build_evaluate` 的系统提示只包含一次对应示例。各评分项最后为 `summary`；Task 2 的 `argument` 最后为 `position`，示例中连续闭合符最长为 2。所有占位原样回复均拒绝，即使将 band 改成 6.0 也不能通过证据校验。
2. 新 fixture 的 8 个正式回复与上批 `raw_calls.jsonl` 逐字相同。mid 两次原文严格拒绝，诊断均指出 `overall_comment` 和 `priorities` 落入 `argument`。在只作诊断的内存副本中，于 `improvements` 后加一个 `}` 就能恢复 JSON 结构，说明这两个缺口的归因准确；正式流水线未修补、未采用。
3. 用模型替身重放两次 mid 坏回复，整个生成流程恰好调用两次，第二次带准确诊断，然后拒绝出分。high/32000/300 秒/json_object 的参数都保留。坏回复后跟一份真正有效的回复可以正常恢复。
4. 对六份可用回复（包括 Task 1）分别以八个固定随机种子递归改变字典键序，归一化结果逐字段相同；扁平旧格式也等价。不是只比总分，而是整个结果等价。Task 1 在本轮新增正式测试里只是检查仍能解析，本独立探针补测了它的实际键序改变。
5. `llm.py`、`review.py`、`jsonshape.py`、`argument.py`、`visual.py`、`config.py` 与基线逐字相同。严格解析的正文前后声明、拼接对象、多代码块、列表根节点和缺括号反例仍然拒绝；完整对象及单代码围栏接受。

## 文档表述需要收窄（不是产品缺陷）

`prompts.py:_root_schema` 的历史说明，以及本轮交接和测试模块描述，写成了“真实运行六次括号错误全是列表后漏对象括号”。三批公开 fixture 实际包含：

| 批次 | 样本 | 原因 |
|---|---|---|
| .8 | under-length 首轮及重试 | 漏 `criteria` 的 `}`，两份 |
| .8 | off-topic 首轮 | **提前关闭 `argument`，`improvements` 落到顶层，`priorities` 落到对象之外** |
| .9 | under-length 首轮 | 三个评分项没有关闭，一份 |
| .9 | strong | 漏 `argument` 的 `}`，一份 |
| .10 | mid 首轮及重试 | 漏 `argument` 的 `}`，两份 |

所以是**六份缺括号回复，另有一份多括号回复**，不能写成所有括号错误只有同一种。更早 11 月 4 日还记录过另一份坏 JSON；本表仅清点 .8/.9/.10 三批。历史诊断和原始证据保留在探针输出的 `history` 中。

“每个对象都以普通字段结尾”也宜精确说成“评分项以字符串 summary 结尾、argument 以 position 结尾”；position 仍是对象，根对象仍以 priorities 列表结尾。当前示例闭合峰值确实从 4 降到 2，这个措辞问题没有造成运行拒绝或数据改变。

## 测试能证明的边界

新增五项测试有效覆盖既有坏回复不被放行、旧回答兼容、结构示例和规则文本存在。通用反馈规则测试是提示词文本断言，不能证明误批实际已消失；括号重排测试证明示例结构变简单，不能证明模型会遵循新顺序。保留严格解析是正确前提，下批真实批次才可观察格式率变化；同批改了结构与判断规则，质量改善不能单独归因于字段顺序。

## 复跑

在主树执行：

```bash
.venv/bin/python -B docs/design/ielts-writing-ai-prompt11-review-20261109/structure_probe.py --repo /private/tmp/studytracker-iwa-prompt10-review-20261108 --output docs/design/ielts-writing-ai-prompt11-review-20261109/structure_probe.json
.venv/bin/ruff check docs/design/ielts-writing-ai-prompt11-review-20261109/structure_probe.py
.venv/bin/black --check docs/design/ielts-writing-ai-prompt11-review-20261109/structure_probe.py
```

探针 125/125，ruff 通过，black 已规范格式。本子任务只写三份审阅文件；没有改业务、旧探针或交接，没有 commit/push/deploy。根 agent 统一完成项目交接审计。
