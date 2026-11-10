# `.12` / Flash high：A 组真实评价报告

这是 2026-11-09 的 **A 组开发回归集**，共 7 篇内置合成作文，只运行评价。实际 **9/14 次请求，6/7 篇最终成功**；B 组老师样本因本地文件尚未到位，仍为 **0/2 次**，不包含在本包中。A 已结束，未用次数不追加。

执行源为 `817c4c4be172fa5603048a12085e60e4c99dfa38`，提示词 `iwa-2026-11-10.12`，模型 `deepseek-flash`，思考 `high`，输出上限 32000 token，超时 300 秒。每篇最多首轮加一次内容校验重试；没有运行精修、改写、识图或老师样本。81 个 tracked 工具文件组合 SHA256 为 `f0178c720a8ecbe3796952122fb219453695ef93bd6ee073df4893f5d8ce39fd`。

## 结果与证据

| 指标 | 结果 |
|---|---:|
| 首轮 JSON 可解析 | 6/7 |
| 首轮完整校验通过 | 5/7 |
| 最终成功 | 6/7 |
| 实际请求 | 9 |
| 截断 / 超时 / 用量缺报 | 0 / 0 / 0 |
| 最长 HTTP / 输出峰值 | 84.834 秒 / 13,506 token |
| 输入 / 输出 token | 29,322 / 56,708 |
| 输出中包含的思考 token | 39,165，不能另加计费 |
| 引文核实 | 81/81 |
| 论证条目 | 44 给出 = 44 采用 |
| 宽松合理性检查 | 11/12，另跳过 1 项 |

- **good 首轮**是可解析 JSON，但把 `argument`、`overall_comment` 放进 `criteria`；程序报“缺少总评”，重试后成功。这是字段层级错误，不是 JSON 语法错误。
- **strong 两轮**都因多余闭合括号使字段落在根对象外，严格拒绝，最终没有分数。强文细项和完整等级序列因此无法检验，不能把其原始分数或空问题列表当作成功结果。
- 弱文的过度概括这次被指出；短文不再误批 `old people`；离题作文的 GRA 不再直接用离题解释语言不足。但反馈质量仍不稳定，详见 [人工复核](manual_review_A.md)。

费用按空闲时段、缓存命中 20,224 / 未命中 9,098 / 输出 56,708 的实际用量估算为 **0.23633448 元**，不是账户账单或未来费用上限。[费用计算](shared-evidence/A/cost_estimate.json)使用[官方价格表](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)。

## 可直接做离线回归的三处真实案例

| 案例 | 输入与正式回复位置 | 已采用结果 |
|---|---|---|
| 已有 although，却建议加入让步从句 | `run_data.json` 的 `t2-mid`；`formal_responses.json` 回复 2 | GRA 理由/总评/提升重点误读句式；不能仅凭引文存在证明判断正确。 |
| 改句增加错误因果 | `t2-off-topic`；回复 7，CC issue 的 suggestion | 将并列的网课优点改成 “This flexibility also means that digital materials can be updated quickly...” 的因果，改变原逻辑。 |
| 可推导的 5 个百分点被删除 | `t1-no-image`；回复 9 的第 4 条 priority；原稿 70%→75% | 本次运行源将其删去。`661180f` 是之后的程序修复，不回写本历史报告；应使用这些原始正式回答另做回放。 |

此外，短文可选优化新增无来源的“数十辆”未被过滤；Task 1 的 A≈75% / C≈80% 矛盾、缺图不可评，以及原文 172 / 下限 150 的条件删减提醒正常。开发集可以检验历史问题是否复发，但不能证明新作文上的准确性；这里没有独立教师评分基准，也不是 `.10` 与 `.12` 的受控 A/B 对照。

## 文件与隐私边界

- [自动报告](shared-evidence/A/report.md)、[报告 JSON](shared-evidence/A/report.json)、[最终结果与原稿](shared-evidence/A/run_data.json)。
- [9 份正式回复](shared-evidence/A/formal_responses.json)、[调用记录](shared-evidence/A/raw_calls.jsonl)、[传输账本](shared-evidence/A/transport.json)。回复包含失败原文，可复现严格解析；账本中的 `.bin` 文件名是原始响应引用，本包不提供这些私有原始文件。
- [人工复核](manual_review_A.md)、[主指标审计](metrics_audit_A.json) **127/127**、[补充审计](metrics_supplement_A.json) **124/124**。
- [runner 自测](runner-selftest.json)及[独立离线审计](runner_independent_audit.json)记录了调用前的范围、预算、持久化与异常停止检查。
- [打包检查](package_validation.json)：所有样本 ID 都是 7 篇内置合成作文，`teacher` 与 `teacher_findings` 为空；无思考正文或凭证模式；唯一 `reasoning` 键是补充审计结果中 39,165 的非负整数用量计数。没有读取真实凭据、私有响应或老师文件。真实 Key 的精确扫描由主审另行执行。

源目录 7 份 `sample-*.json` 是逐篇检查点，内容已汇总在 `run_data.json`，为避免冗余未复制。本包保留 7 份合并证据文件及 7 份人工/审计文件；14 份复制文件与源文件逐字一致。补充审计结果中的 `price_inputs_tokens.reasoning = 39165` 是用量计数，不是思考正文，保持原字段名以免改动审计证据。

`report.md` 末尾“原始调用记录仅保存在本机”是生成器的原始文案；本包中的 `raw_calls.jsonl` 已移除思考正文，只保留正式回复和统计。没有学生材料、Key、私有思考或可执行的付费 runner。本包准备阶段尚未提交或推送，最终同步状态由主审交接记录说明。

## 复跑离线审计

`--repo` 必须指向干净的 **817c4c4** 源码树；补充审计会核对该 HEAD、工具文件 SHA 和提示词。不要把新修复版本代入历史身份检查，也不要从报告目录发起真实模型调用。

```bash
python -B docs/design/ielts-writing-ai-prompt12-high-20261109/metrics_audit.py \
  --group A --repo /path/to/clean-817c4c4 \
  --evidence docs/design/ielts-writing-ai-prompt12-high-20261109/shared-evidence/A \
  --output /tmp/iwa12-A-metrics.json

python -B docs/design/ielts-writing-ai-prompt12-high-20261109/metrics_supplement.py \
  --repo /path/to/clean-817c4c4 \
  --evidence docs/design/ielts-writing-ai-prompt12-high-20261109/shared-evidence/A \
  --output /tmp/iwa12-A-supplement.json
```

以上脚本禁止网络，仅读取脱敏证据和指定源码。审计结果中的数值计数键 `reasoning` 不包含思考文字，包内保持原样。
