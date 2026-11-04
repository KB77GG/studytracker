# Task 2 论证结构复核：49b4c4e

复核日期：2026-11-04，Mac / Python 3.13.3。源码：`49b4c4e71c47355ae38a5fc46ef9a66c00e107be`，提示词 `iwa-2026-11-04.4`。

**结论：离线复核尚未通过，真实模型请求 0/14。** 已有的 217 项 Python 测试、8 项 Node 测试和代码检查通过，但补充探针复现了下面 3 项问题。第一项会使评价失败，并中断 realcheck 报告生成；另两项影响本轮拟验收的论证指标。因此尚未满足用户“复核通过后运行”的条件，没有读取或修改私有 Key，也没有运行付费批次。该 7 篇、仅评价、最多 14 次实际请求的条件授权仍保留，修复复核通过后可继续。

本次只新增审阅材料，不修改业务源码。上一轮改写修复 `7a83b20f` 同时随分支拉取，相关回归包含在完整测试中；本轮没有重新验证真实改写效果。

## 1. P2：枚举字段类型不正确，会绕过无效条目处理并中断报告

位置：`tools/ielts_writing_ai/argument.py:81、82、107`；传播至 `review.py:454` 和 `realcheck.py:370、385`。

将 `role`、`verdict` 或问题 `type` 设置为合法 JSON 的数组/对象，例如 `"role": ["body"]`，字典成员判断会抛 `TypeError: unhashable type`。三种字段 × 两种类型全部复现。相比之下，未知字符串枚举能正常丢弃并计数。

端到端替身返回的第一份评价除该字段外有效，第二份准备了正常输出。记录确认第一份响应成功、JSON 合法、正文确实包含异常字段；实际只调用一次，评价成为 `failed/internal_error`。同样样本、不改字段的对照组一次即 `ready`。随后调用 `realcheck.build_report(data)` 又因重校验首轮输出抛出相同 TypeError，整份报告无法生成。

建议及验收：

- 字典成员判断前检查值是否为字符串；无效条目按既定规则丢弃、计数。
- 剩余有有效段落时允许保留评价；完全无有效段落时抛 `ArgumentInvalid`，按既定流程重试一次。不要为了重试而拒绝其余有效条目。
- 对三种枚举字段覆盖数组、对象、未知字符串；报告重放首轮输出也必须能完成，不能让错误结构中断整份报告。

证据：`argument_evidence_probe.json` 的 `enum_cases` / `pipeline`；`argument_metrics_probe.json` 的 `malformed_role_reporting`。

## 2. P2：强作文被判段落偏离，合理性检查仍通过

位置：`tools/ielts_writing_ai/realcheck.py:640–657`。

构造合法且引文可核实的 argument：4 个段落的 `verdict` 全为 `off_position`，`problems=[]`。强作文的“不应出现 off_position / unclear_position”仍返回 `ok: true`，因为只检查 `problems[].type`。函数已经收集了偏离段落，但只在离题样本的 `argument_any_of` 中使用。

建议：禁止偏离的检查同时检查段落判定；问题列表的条数仍可单独统计，不应把两者混为一类。增加“只有段落偏离、问题列表为空”的正反对照，确保强作文检查失败，而无偏离的正常作文通过。

证据：`argument_metrics_probe.json` 的 `strong_off_position_paragraphs`。

## 3. P2：格式错误条目从丢弃率中消失

位置：`tools/ielts_writing_ai/argument.py:78–79、102–103`；`realcheck.py:439–470、879`。

模型输出 1 条立场、4 条合法段落、8 条字符串格式的问题，共 13 条。8 条格式错误的问题被跳过，`dropped=0`，报告仍显示“丢弃 0 条，占模型给出的 0%”。按当前报告所称的“全部返回条目”口径，应是 8/13，约 61.5%。现有单测甚至明确把非对象条目标为“ignored, not counted”，所以完整测试无法揭示此口径问题。

建议：格式不合法也计入丢弃数；明确保留、无效、去重和上限截断的分类及分母。若只统计最终成功输出，也应在报告明示，不应让读者将它理解为所有首轮/重试原始输出的丢弃率。README 的建议阈值“≤10%”应与最终定义一致。

证据：`argument_metrics_probe.json` 的 `malformed_items_not_counted`。

## 已通过与本轮范围

- 本机完整测试：217/217 Python，8/8 Node；运行隔离器仅允许本机假服务，使用临时数据库，外部 `IWA_DATA_DIR` 未写入。
- `ruff check tools/ielts_writing_ai`、`black --check tools/ielts_writing_ai`（37 文件）、`node --check tools/ielts_writing_ai/static/iwa.js`、`git diff --check` 通过。
- 离线预算探针：7 篇只评价，全部输出不合格时恰好调用模型替身 14 次，每篇 attempt 0/1，`max_tokens=4500`、HTTP `retries=0`。这些不是网络/付费请求。
- UI/复制代码保留了“AI 标注”说明，不将论证另行计分。引文存在不等于判断准确，真实判断质量仍未验证。
- 长引文先截断再校验的观察也保存在探针中；当前展示的是原文中真实存在的前缀，没有展示虚构后缀，本次不把它另列为阻塞问题。
- 未重新跑完整浏览器体验、Python 3.10、真实识图、教师评分校准或真实改写。没有创建或启动试用服务器，没有生产/小程序操作。

## 复现与修复后复核

在包含本目录的功能分支仓库根运行（Python 需具备试用工具依赖）：

```bash
PY=.venv/bin/python
DIR=docs/design/ielts-writing-ai-argument-review-20261104
PYTHONDONTWRITEBYTECODE=1 "$PY" "$DIR/argument_evidence_probe.py" --repo . --output /tmp/iwa-argument-evidence-after.json
PYTHONDONTWRITEBYTECODE=1 "$PY" "$DIR/argument_metrics_probe.py" --repo . --output /tmp/iwa-argument-metrics-after.json
```

两个探针记录实际行为，退出 0 只表示执行完成，不表示产品验收通过；修复后应比较新结果，保留本目录历史 JSON。探针只用替身和临时数据库，不加载私有配置。实际评审的执行命令及结果见 `offline-verification.json`；完整测试日志见 `offline-tests.log`。

先将上述场景写为正式回归、修复，再复核。通过后执行已有授权范围：7 篇内置合成样本、仅 evaluate、最多 14 次实际请求，不运行精修、改写或识图；继续使用持久调用计数和临时数据库。重点再看首轮通过率、论证条目丢弃率、4 项论证合理性检查及输出 token 峰值。

报告与两套探针将随交接文档提交、推送到 `claude/ielts-writing-ai-trial`；精确文档提交见 git log。无业务源码修改，无 main 合并或部署。
