# `.12` 开发样本例子清理及离线证据复核

结论：本轮范围内未发现新缺陷。已点名的样本措辞从系统规则中移除，原稿输入和八份历史夹具保留；改写与精修的实际消息没有改变。相关测试只能证明提示内容与输入保持，不能证明模型准确度或独立泛化。

审阅源为 `/private/tmp/studytracker-iwa-prompt10-review-20261108`，HEAD `135a3013`（业务 `e370b0c`），比较基线 `fba35562`。材料只来自已提交的七篇合成作文、公开正式输出夹具及代码；没有读取老师作文、学生材料、Key 或私有思考，没有真实模型调用。

## 实际检查

1. 不是只读常量，而是逐篇构造七篇开发样本的 evaluate / refine / rewrite 消息，共 21 组。系统规则中都不再出现已点名的 19 个措辞，包括 `much less crowded`、`cannot afford a car`、`forty passengers`、`Country A/B`、`lion's share`、公交及修路限定立场、两年比较和本批人工复核措辞。
2. 额外比较每篇原稿与每组系统规则的连续五个英文词重合，无命中。这只是辅助字面扫描，不是语义独立性证明。泛化后的限定立场、保留原意、不可凭空补数字及文内比较规则仍然存在；保留规则覆盖面本身是合理的，不要求删除所有曾受开发结果启发的通用规则。
3. 三类功能的 user 消息与基线完全相同，题干和原稿内容仍在；Task 2 评价通过真实段落发送、精修通过句子发送，均逐项核对。这里清理的是**系统规则中的样本例子**，不是删除请求中本来就必须提供的待评作文。文档中“在线提示不含样本词句”应按这一范围理解。
4. refine、rewrite 的完整消息和 context 与基线逐字/逐字段相同；七篇 rewrite-notes 消息及一次合成 describe-image 消息也相同。这次未把评价的新边界规则擅自扩展到其他功能。
5. 八份历史 `tests/fixtures/realcheck_*.json` 的路径集合与 Git blob、工作树 blob 全部与基线相同，`samples.py` 也相同。既有真实坏回答和原稿仍可用于离线回归，未通过修改旧夹具来让测试通过。
6. runtime 模块除 prompts 外没有变动；其余工具路径改动仅 README 与测试。所有输入对象调用前后保持不变。

## 新增四项测试能证明什么

`test_prompt11_review_20261109.py` 的四项测试分别检查实际 Task 1/2 提示中有准确边界、语言评分证据规则存在、19 个已知措辞不出现、通用替代说法存在。旧断言从已移除的词句改为相应通用说法，符合本轮契约变化；没有删除历史夹具。

它们是消息构造/文本规则测试，不是模型行为测试：不能据此认定误批消失、缺括号减少、句式识别变准，或同样评分应用到未见过的作文也可靠。新测试只覆盖评价系统规则，本独立探针补查了其他功能及 user 输入完整性。

## 开发集与留出集边界

七篇作文已用于多轮规则和提示调优，通用化不会消除这种开发历史。README 将它们重新定位为开发回归集是准确的。下一批如继续运行这七篇，结论应限于历史错误是否重现及格式可靠性；另用未参与调优的题材和独立老师判断评估泛化。

一个老师样本可用来对比该篇反馈是否合理或分差是否明显，不能单篇证明校准完成。专项完成后用户明确确认四处批注位置没有问题，主审已按用户确认记录；本专项仍未查看原稿或评语，不能表述为 agent 已独立验过。

## 可复现结果

在主资料树执行：

```bash
.venv/bin/python -B docs/design/ielts-writing-ai-prompt12-review-20261109/exposure_probe.py --repo /private/tmp/studytracker-iwa-prompt10-review-20261108 --output docs/design/ielts-writing-ai-prompt12-review-20261109/exposure_probe.json
.venv/bin/ruff check docs/design/ielts-writing-ai-prompt12-review-20261109/exposure_probe.py
.venv/bin/black --check docs/design/ielts-writing-ai-prompt12-review-20261109/exposure_probe.py
```

结果 **155/155**，ruff、black 通过。探针禁止 socket connect/bind/getaddrinfo；实际请求 0。

本专项只写 `exposure_probe.py`、`exposure_probe.json`、本说明三份审阅文件；未改产品、旧探针或两交接，没有 commit/push/deploy。主审汇总交付和交接审计。
