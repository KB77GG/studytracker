# 42bfc549 复核与思考模式 A/B：15/30 次已完成

四项修复的独立离线复核通过，随后按已有授权完成 high 连通测试和同条件 off/high 对照。**high 对部分上下文判断有改善，但仍有误批和无来源建议，尚不能据这 7 篇合成作文认定评分准确或直接切成默认模式。** 本轮没有修改业务代码、私有配置或默认 off；没有合并 main、部署或生产操作。

## 范围与可复现基线

- 源码：`42bfc5493fca663a4daec382bab871719ae68416`，业务提交 `ef07ce26`；提示词 `iwa-2026-11-04.6`；DeepSeek `deepseek-flash`。
- 复核树：`/private/tmp/studytracker-iwa-realcheck-review-20261103`，分支 `claude/ielts-writing-ai-trial`。资料主树 `/Users/zhouxin/Desktop/studytracker` 的旧 main/既有改动保持原状。
- 真实调用：**15/30**，smoke high 1 次，off 7 次，high 7 次。全部为内置合成作文的评价，无精修、改写、识图、学生数据；临时 SQLite，不读写试用数据库、不占试用额度。
- 总账本在每次发送前落盘，阶段上限 2/14/14、总上限 30；HTTP 自动重试关闭、拒绝重定向、smoke 失败不进入 A/B。现有账本拒绝重跑，本次已结束，未用额度不用于自动增加样本。
- high 为 16000 输出 token / 300 秒，off 为 4500 / 120 秒；七篇首次实际请求的消息 SHA 全部一致。服务商报告的 high 输入 token 每篇多 25，但消息正文指纹不变；不把 token 计数差误判为输入不一致。
- 共享 raw_calls/run_data 已去除模型思考正文；正式回答、usage、reasoning_tokens、reasoning_chars、消息 SHA 保留。完整本机结果在忽略的 `docs/design/iwa-thinking-ab-20261104/results/`，权限受 umask 077 保护。

## 实测结果（smoke 不并入 A/B）

| 指标 | off | high |
|---|---:|---:|
| 实际请求 / 首轮有效 / 最终成功 | 7 / 7 / 7 | 7 / 7 / 7 |
| 延迟 p50 / p90 | 11.786 / 13.219 秒 | 33.393 / 68.510 秒 |
| 输入 token | 13,265 | 13,440 |
| 输出 token | 12,838 | 49,740 |
| 其中思考 token | 未报告（关闭） | 34,834 |
| 单次输出峰值 / 上限 | 2,139 / 4,500 | 12,244 / 16,000 |
| 重试 / 截断 / 超时 | 0 / 0 / 0 | 0 / 0 / 0 |
| 评分引文核实 | 110/110 | 109/109 |
| 论证条目：采用 / 返回 | 46/46 | 53/53 |
| 自动论证检查 | 4/5 | 5/5 |
| 全部自动合理性检查（另各跳过 1 项） | 16/17 | 17/17 |

独立 smoke 用了 1 次、78.761 秒、13,718 输出 token（其中思考 11,512），达到 16000 上限的 85.74%。整批 15 次均 HTTP 200、正常 stop。独立账本/报告/对照审计 **275/275 一致**。本批没有失败调用，失败用量修复由离线探针验证，不冒称实际触发过。

high 的输出约为 off 的 **3.87 倍**，中位延迟约 **2.83 倍**。按本轮核对的 [DeepSeek 官方价格](https://api-docs.deepseek.com/quick_start/pricing/) 和实际缓存命中/未命中 token，估算 off **$0.00862–0.01724**、high **$0.03054–0.06109**；含 smoke 全批 **$0.04770–0.09541**。这是非高峰/高峰区间，不是账户账单；思考 token 已含在输出中，不再次加算。原工具报告未填单价，费用仍显示未知，独立估算见 real_metrics_audit.json。

## 人工结论与新发现

详见 [论证逐条复核](manual_argument_review.md)、[语言反馈补充](manual_language_review.md) 和已填写的 [人工对照表](comparison/manual_review.md)。

- **可见改善**：high 在 good 中承认原文已经给出新路诱发驾车的机制；对 strong 的 `an expensive treadmill` 接受为合理比喻；mid 的正确 which 从句不再被当成指代错误。限定立场、合理让步均未被强迫改成立场矛盾。
- **共同保留的真问题**：两档均识别离题、97 词/单段不足、Task 1 A75<C80 与“两年 A 最高”的冲突；缺图 TA 和总分保持不可评。
- **仍有上下文误读**：high 在短文中忽略已经出现的 `in big cities`，Task 1 的衔接理由还把概述没写的内容说成已写。语言建议里仍有把正确结构当作问题、添加作者未确认含义或趋势的情况。
- **P2：英文拼写数字漏过来源检查**。high 的 mid/TR 建议写 `a full bus carries about forty times as many people as a car using only a fraction of the fuel per person`。原稿、题目和允许来源没有这个 40 倍事实，但 `suggestion_removed=false`、删除计数 0，复制文本仍带它。`figures.py:27` 的数字规则和 `:36` 的中文百分比规则未覆盖英文数词，`:67` 的提取因此返回空；统一最终检查也无法补救解析盲区。原 80% 回填修复成立，这是本轮真实模型暴露的新边界。见 [便携探针](english_number_probe.py) / [结果](english_number_probe.json)。

自动“弱文至少 1 个论证问题”的阈值不是教师真值；弱语言未必意味着逻辑错误。off 的这项失败、high 的通过不能独立证明高低。相同道理，high 分数上涨也不是准确度提高的证据。

## 离线验证与重跑

- 原 80% 四组对照、comment 回填、最终扫尾及计数：**60 项断言通过**。
- 空正文截断、失败 reasoning 合计 31800、缺失用量不当零：通过。
- 对照证据完整性、140/141 不同消息拒绝、仅 thinking 选项变化允许、旧报告指纹警告：通过。
- 完整离线套件：**320 Python**（20.376 秒）、**8 Node**；ruff、black（45 文件）、node --check、git diff --check 通过。Mac 默认条件执行，未声称本轮在 Python 3.10 或所有 locale 重跑。
- 真实 runner 的独立替身验证：401、无效 JSON、截断分别在 1/2/1 次停止，不进入 A/B；正常路径 1+7+7；每次发送前磁盘账本已有记录。无额外真实调用。
- 浏览器全流程本轮没有重跑；只复核涉及删除提示的 UI 源码与复制文本。

从仓库根目录可以离线重跑（探针不会调用模型）：

```bash
PY=/path/to/venv/bin/python
B=docs/design/ielts-writing-ai-thinking-ab-20261104
$PY "$B/evidence_recheck.py" --repo "$PWD" --output /tmp/iwa-evidence-recheck.json
$PY "$B/thinking_client_recheck.py" --repo "$PWD" --output /tmp/iwa-thinking-client-recheck.json
$PY "$B/compare_recheck.py" --repo "$PWD" --output /tmp/iwa-compare-recheck.json
$PY "$B/real_metrics_audit.py" --bundle "$B" --output /tmp/iwa-real-metrics.json
$PY "$B/english_number_probe.py" --repo "$PWD" --fixtures "$B" --output /tmp/iwa-english-number.json
```

历史复核材料未改。新探针 exit 0 表示断言或审计如实完成；英文数字探针记录的是当前缺陷，修复时应新增正确行为的正式回归。

## 下一步

1. 修复英文数词（含百分比/倍数）的统一来源解析，保留原有中文百分比、完整数字与篇幅目标正对照；使用本次真实最终输出作为离线 fixture，不必为复现再付费。
2. 调整判断与建议：核对整段语境；将风格偏好列为可选优化；语言替换不得暗加事实或改变原意。
3. 暂时保留默认 off；high 可继续作为老师复核时的试验选项。保留 16000/300 的当前配置，本批不足以安全下调上限，也没有证据需要加大。
4. 修复后先离线复核。要验证评分准确度，仍需带老师评分的独立样本，而不是继续对这 7 篇调阈值。下一批真实调用另定范围，本批账本已经结束。
