# 思考模式与对照工具复核：请求范围通过，离线验收暂未通过

2026-11-04，受测 HEAD `bd93e1cf83fd93322fb31f0a58d8decc2f0aa87f`，包含业务 `afdd5600`（篇幅目标、支撑、计数修正）和 `90194f02`（思考开关与对照），提示词 `iwa-2026-11-04.6`。

**本轮真实请求0/30。** 用户已明确授权：离线复核通过后，high连通测试1篇最多2次，再off/high各7篇各最多14次，三阶段合计最多30次；high每次输出上限16000。独立审阅发现建议过滤回归、思考统计问题及人工复核表缺项，条件尚未满足，因此没有读取试用Key、没有启动付费账本。授权保持未使用，修复通过后可继续同范围，无须再确认相同授权。

304项Python、8项Node、ruff、black和JS检查均通过。这说明现有测试通过，不代表下面独立探针发现的缺陷不存在。本轮没有修改业务代码，交付是报告和便携探针。

## 需要先修的三组问题

### P2-1：已过滤的80%建议，经“改列”路径重新显示

位置：`tools/ielts_writing_ai/argument.py:221`先过滤建议；`:233`使用 `suggestion or comment` 构造改列后的可选优化。原建议被清空时，未经过过滤的comment会成为新的suggestion。

完整复现使用历史弱文作为输入，再明确添加离线构造字段（不是本轮真实模型输出）：问题类型unsupported，问题引文为“So goverment should make it cheap and more fast.”；同段支撑为“If the bus is more better, people will use it more and the traffic will be less.”；comment与suggestion都包含无来源的“减少80%排放”。

`normalize_evaluation`将其改列后，`suggestions_removed.argument=1`，但新的`improvements[].suggestion`仍含80%。`copytext.py:114`完整复制会输出它，页面`static/iwa.js:526`也直接显示。四组相同支撑的正反对照确认：comment和suggestion同时含80%时重新泄漏；另外三组不泄漏。

建议：凡最终成为建议的文本都经过同一来源校验；不要用未过滤comment填补已删建议。需要保留改列记录时，可以保留问题引文和同段支撑，并明确显示建议被删，不必将整条改列静默丢掉。修复后同时断言最终JSON、复制文本、删除计数一致，保留260词合法目标等正对照。

### P2-2：思考耗尽预算时，报告少算截断与思考用量

位置：`llm.py:224`先判断空正文，`:226`才判断finish_reason；`realcheck.py:103`的失败分支只保存usage，未提取reasoning_tokens；`:416`及`:425`只汇总已提取字段。

独立真实客户端解析探针（HTTP传输替身，不联网）得到：

| 场景 | 服务商模拟返回 | 工具报告 |
|---|---|---|
| 思考用尽预算、正文为空 | finish_reason=length，completion=16000，reasoning=15900 | error=empty、截断0、思考未报告 |
| 部分JSON被截断 | finish_reason=length，同样usage | 截断1，但思考仍未报告 |
| 一次失败＋一次成功 | 思考共31800，completion共32000 | 思考合计15900；completion共32000正确 |

这不是已经发生的真实账单损失，也不是调用上限失效；是用于校准思考预算的统计不可靠。失败响应里的usage仍完整保存，能够修复统计，不需要重新调用模型来还原。

建议：先识别明确的length结束原因；成功与失败都统一从usage提取思考token；部分请求未报告时显示已知小计与缺失次数，不能把部分合计当完整合计。保留总completion用量与失败调用计数。目前截断不会自动重试（调用发生在内容校验try外），不要宣称必然重试2次。

### P2-3：人工复核表缺少判断矛盾所需的证据

位置：`realcheck_compare.py:122`附近的sample_view丢弃Task 2问题的conflicts_with、needs_review；Task 1 consistency_issues仅保留主引文，丢掉数字和解释；render_manual_review不输出Task 1矛盾。

探针构造了含这些已接受字段的结果：首条论证引文可见，但另一处冲突引文和“需人工确认”状态不见；Task 1矛盾及其对照数字也不出现在人工表。原始run_data仍保留完整内容，数据并未丢失，但仅依据manual_review.md会漏看这轮最重要的Task 1/论证比较信息。

建议：人工表同时呈现成对引文、问题说明、需人工确认状态，以及Task 1矛盾的完整claim/figures/comment。无需让工具自动判断哪边更准；需要让人工能看全证据。

## 额外的同条件检查缺口（本批无图样本不触发）

两次离线真实realcheck流水线使用同一作文、题目和图片，但替身识图结果分别为Museum A=140和141。输入评价模型的messages SHA明确不同；对照工具仍给出相同样本指纹，errors/warnings均为空，允许比较。

`realcheck.py`导出的submission不含image_description，`realcheck_compare.py:38`指纹也只含task_type/prompt_text/essay_text/image_status，因此两个ready读图结果的差异没有被检查。

这是通用“同条件”声明的缺口；本轮计划7篇都不调用识图，不能把它写成此次必然影响结果。建议对实际进入模型的输入做规范化指纹（或完整导出所有输入字段），允许已声明的thinking/输出预算/超时差别，但拒绝其余语义输入差别。修改作文和提示词版本会被拒绝的两个正对照已通过。

## 已确认通过的部分

- 304 Python（19.865s）、8 Node、ruff、black（44文件）、node --check、git diff --check通过。Mac Python3.13.3，替身模型、临时数据库、只允许回环网络；测试外部IWA_DATA_DIR未写入。
- 前轮两条真实260词建议现在保留；中文百分之8、八十/八十一正确比较；1980/180仍不放行80%；Task 1两处计数更正可见，旧A/C矛盾仍保留。
- 7份新fixture与已提交的上一批真实输出逐字一致。填入已核实同段支撑的弱/中/短文场景改列成功；外段、问题引文本身和虚构支撑正反对照通过。50项正常行为断言通过，新的过滤缺陷单独标为reproduced=true。
- 请求边界：high仅用于evaluate，16000/300秒；off为4500/120；refine6000/120、rewrite2400/120仍disabled。只解析最终content，reasoning不会被当成最终JSON。realcheck强制HTTP retries=0，内容校验重试计入统一上限；首次timeout/network/401均一次就停止。
- 官方文档已在本机核对：`thinking:{type:enabled}`与顶层`reasoning_effort:high`符合文档；reasoning_content和最终content分开，usage有completion_tokens_details.reasoning_tokens。temperature在思考模式下被忽略。**参数写法得到文档支持，不等于已做真实连通性验证**。[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)、[Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)。

同段有引文仍只证明来源，不证明逻辑支撑；计数更正只是附加提示，不会修正原评语或重算分数。这些是已披露的能力限制，不另列成新的缺陷。

## 复现和交付

便携探针均不读.env、不调用外部模型：

```bash
python evidence_probe.py --repo /path/to/checkout --output evidence_probe.json
python thinking_client_probe.py --repo /path/to/checkout --output thinking_client_probe.json
python compare_probe.py --repo /path/to/checkout --output compare_probe.json
```

探针exit0表示探针成功执行，**不表示产品无缺陷**；阅读JSON里的实际错误类型、用量、reproduced及compare_accepted等字段。修复时请改成正确行为回归，不用修改这些历史结果来让旧记录变绿。主agent已独立重跑三套探针，结果一致。

完整测试精确命令记录于offline-verification.json，日志为offline-tests.log。本机runner为 `/Users/zhouxin/Desktop/studytracker/docs/design/iwa-thinking-review-20261104/run_offline_tests.py`，使用主树.venv。

Git的SSH认证仍失败，本轮用现有HTTPS凭据成功fetch相同仓库和功能分支；未更改origin地址、SSH文件或密钥。独立树从4d454f54快进到bd93e1cf，主树未切换，咨询和其他任务交接未发生冲突。

本报告、三套探针和离线证据仅推功能分支；不合并main，不部署，不改生产或小程序。尚未做新版真实连通、A/B、浏览器全流程、Python3.10、真实识图或教师评分校准。下一步先修三组问题并复核，再按现有授权启动独立总账本：smoke≤2、off≤14、high≤14，总≤30；本轮额度未使用。
