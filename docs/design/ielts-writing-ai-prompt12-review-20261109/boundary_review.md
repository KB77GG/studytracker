# `.12` 评分边界专项复核

审阅源：`/private/tmp/studytracker-iwa-prompt10-review-20261108`，`135a3013`（业务 `e370b0c9`），基线 `fba35562`。只读已提交的合成样本、提示词及运行代码；没有读取老师/学生材料、Key 或私有思考，没有实际模型请求。仅写本说明及 `boundary_probe.py/json`，规范交接由主审汇总。

## 结论

上一轮 P2 已关闭：没有再将全部论证质量归入 TR 并禁止解释 CC。新规则将内容回应/立场/相关性/展开支撑归入 TR，组织/逻辑推进/分段/衔接指代归入 CC；Task 1 则单独使用 TA 的概述、关键特征和数据选择准确性规则。LR/GRA 根据相应语言证据，不从离题、缺数据或论点支撑薄弱直接推出语言问题。

论证检查的两处旧笼统句也一起改了：开头由“解释 TR 和 CC”改成每条发现解释其实际体现的 TR 或 CC；结尾由“在两项理由里反映问题”改成在对应评分项的理由里反映。新的边界段另明示不能机械把同一发现复制到两项。因此修复不是仅删一个 Coherence 单词，原冲突的两个方向均已处理。

新规则与原 `COMMON_DESCRIPTORS` 的 CC 逻辑推进、分段、指代条目相容；Task 1 无图时，独立的 TA 不可评规则仍保留并覆盖一般 TA 说明。实际 ready 正对照也正确取消不可评提示。没有发现本轮新增的评分维度矛盾。不同维度仍需按具体证据判断，不能据这些文本断言模型会稳定正确执行。

## 独立验证：199/199

便携探针实际构造七篇内置样本的评价消息，另加一份 Task 1 识图 ready 状态的纯合成正对照：

- 每份都只有一条正确的任务边界，带 LR/GRA 语言证据保护；六篇 Task 2 含 TR/CC 映射规则，Task 1 不带 Task 2 论证检查。
- 四个旧冲突/笼统指令片段均不再出现；基线 `.11` 六篇 Task 2 确有旧冲突句，确认差异来自修复。
- “不凑问题”“简短不等于未展开”“可选替换不算问题”“不增加事实”“先核实已有句式”等通用保护继续存在。
- 输入 submission 未变；同一提交的评价 user 消息和 context 与基线相同，样本内容没有被在线指令清理误删。
- 三种完整 schema 数据（Task 2、Task 1 有图/无图）与基线相同；精修、改写的完整消息与 context 也逐字段相同。
- `llm.py`、`review.py`、`argument.py`、`jsonshape.py`、`config.py`、`samples.py` 与基线逐字相同。

探针不调用客户端，且拒绝 socket 连接/绑定/解析事件；实际请求 0。ruff 通过，black 已规范。完整套件、旧探针及开发样本措辞清理由主审其他检查覆盖，不在本专项重复声称完成。

## 可复跑

在主资料树执行：

```bash
.venv/bin/python -B docs/design/ielts-writing-ai-prompt12-review-20261109/boundary_probe.py --repo /private/tmp/studytracker-iwa-prompt10-review-20261108 --output docs/design/ielts-writing-ai-prompt12-review-20261109/boundary_probe.json
.venv/bin/ruff check docs/design/ielts-writing-ai-prompt12-review-20261109/boundary_probe.py
.venv/bin/black --check docs/design/ielts-writing-ai-prompt12-review-20261109/boundary_probe.py
```

局限：199 条是消息构造、边界文本与不变性检查，不是 199 次模型验证。不能据此认定评分准确、误批减少或 JSON 失败率改善；这些仍需另行授权的真实验证和独立老师基准。
