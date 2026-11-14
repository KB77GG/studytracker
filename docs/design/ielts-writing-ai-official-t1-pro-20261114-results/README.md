# 官方 Task 1：`.15` 新批次结果（2026-11-14）

**4 篇各评价 2 轮全部完成，批次已关闭；Mac `.15` 识图已开启。** 实际 3 次新识图、8 次 Pro 评价，没有重试、失败、超时、截断或结果未知。数字、账本、输入绑定审计 **277/277** 通过，但同题 5/6 分排序失败，**不能据此认为评分已校准**。老师的 10 项抽查仍未填写。

## 分数与适用范围

| 样本 | 官方总分 | 第 1 轮 | 第 2 轮 | 两轮均值减官方 |
|---|---:|---:|---:|---:|
| official-1A-A | 5.0 | 5.0 | 5.5 | +0.25 |
| official-1A-B | 6.0 | 5.0 | 5.0 | −1.00 |
| official-1B-A | 6.0 | 5.5 | 5.5 | −0.50 |
| official-1C-A | 5.0 | 5.5 | 5.5 | +0.50 |

- 8 次评价平均绝对差 **0.5625**，平均偏差 **−0.1875**；6/8 在官方总分 ±0.5 内，1/8 完全一致。产品报告保留三位小数，显示 0.562/−0.188；这里给出原始分数直接计算的精确值。
- 同题 1A 的官方 6 分篇未高于官方 5 分篇：四种跨轮配对为 **2 次逆序、2 次持平**，均值差 −0.25。这四种配对不是四组独立样本。
- 1A-A 总分重复差 0.5，其余三篇总分相同；单项仍有波动，1A-A 的 CC 差 1.0。全部单项分数见 [audit.json](audit.json)。
- 只有 **4 篇独立作文、3 张题图**，不是 8 篇。公开官方样卷可能进入模型训练材料；官方标签只有总分，没有可用于本轮验证的四项独立金标准。不能推广为真实学生总体准确率，也不能从略低的平均偏差推出统一加分规则。
- 核图由 **Codex 主审和独立 agent** 对照原图完成，不是老师或用户人工验收。老师 10 项抽查属于此前材料，仍待真实填写，本轮没有代填。

## 识图与输入确认

用户“读错先改正、确认后继续”的选择持续有效，本轮“ 一起执行 ”授权开启本机识图并执行新独立批次。固定上限为 **3 次新识图、16 次文字请求（包含校验重试）**，只运行 evaluate；没有另跑精修、改写或 Task 2。

旧 `official-1B-A` 原始识图输出只读复用，在新批次纠正后确认，保留原 `model_description`。另外三篇各识图一次；1A 两篇虽共用图，按批准范围各读一次。三份新读数核对后保留，图中估读值仍明确标为近似。四份确认均绑定题图和最终读数 SHA，八份结果均保存同一篇对应的已确认读数快照，运行前消息重放一致。旧批次的原读数、账本和 closed 文件字节未变。

这次成功运行验证了带确认读数的执行路径，不证明自动识图每次正确。1B 复用的是纠正后的旧读数，本次没有重新测量模型对 1B 的读图准确率。

## 内容抽查：原始风险与最终显示分开

主审已对照原稿、确认读数和归一化结果复核以下四项。它们是本轮模型反馈质量观察，不是原五项输入确认漏洞重新出现，也不等于教师评分结论。

| 样本 / 原始字段 | 发现 | 最终处理与影响 |
|---|---|---|
| 1A-A 第2轮 / lexical.issues[2] | 引文拼接不同位置，无法匹配原稿 | 保留但 `quote_found=false`；页面明确提示“未在原文中找到，不作为评分依据”，禁止定位。已检测，不称为静默通过；也不能据此证明模型原始分数完全未受其影响。 |
| 1A-B 第1轮 / coherence.issues[2] | 改句把女性某分项人数改成总人数 | 错误 suggestion 已过滤，标 `suggestion_removed=true`，不计作当前可见改句错误。 |
| 1A-B 第2轮 / coherence.issues[0] | 把全时段下降与后半段回升判为矛盾 | 错误 comment 仍保留；不同时间范围可以同时成立。原稿其他数据不准不构成这个逻辑批评的依据。 |
| 1B-A 第2轮 / task.strengths[2] | 对与确认读数相容的粗略晚间峰值描述，批评数值和时间不准 | `quote_found=true`，comment 仍保留；原句另有拼写问题，不支持这一数据批评。 |

八份反馈共检查 161 条引文，160 条在忽略大小写、空白后匹配。另有 6 条局部语言建议与图表或同一答案的 TA 纠错存在明确冲突而仍保留；其中保留原稿错误的情况单列，不统称模型新增事实。完整范围及分类见 [content-review.json](content-review.json)。没有将选择性反馈未提到的每个问题都计作漏报，没有把全部 raw 风险算成用户可见问题。完整对应片段仅本机私有 `content-review.private.json/md`，公开材料不贴原稿或反馈正文。

## 调用、时间与费用

| 模型/用途 | 新请求 | 输入 token | 缓存命中 | 输出 token（含思考） | 估算人民币 |
|---|---:|---:|---:|---:|---:|
| Flash / 识图 | 3 | 2,208 | 384 | 1,877 | 0.00933968 |
| Pro / evaluate | 8 | 22,930 | 16,256 | 123,350 | 1.69769640 |
| 合计 | 11 | 25,138 | 16,640 | 125,227 | **1.70703608** |

按逐次实际请求时间确认均为 11 月 14 日周六，使用空闲价格；每百万 token 输入未命中/缓存命中/输出：Flash 1/0.02/4 元，Pro 4.5/0.15/13.5 元。Pro 的 105,291 个思考 token 已包含在输出内，没有重复计费。以上为实际 usage 按[DeepSeek 官方价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)估算，非账单，不包含旧批次已支付的那次 1B 识图。

评价实际于北京时间 **11:18:19—11:36:36** 运行。11 个响应均为裸 JSON；8 份最终结果均 ready，没有围栏恢复、格式失败或内容校验重试。批次自动关闭，未用的 8 次文字额度不自动续用。

## 本机服务与源码

- 调用时固定源码 `/private/tmp/studytracker-iwa-prompt15-final-recheck-20261113`，分支 `codex/iwa-prompt15-final-recheck-20261113`，HEAD `18f5f08ffb0019f602ad64ec2565d8bd19fb31e9`，运行前后 clean；业务仍是 `d92f0839`，提示词 `iwa-2026-11-13.15`，95 个产品文件 SHA 不变。后续共享提交只改 docs。
- 主资料树 `/Users/zhouxin/Desktop/studytracker` 仍 main@`6ded77d24586327ad94e151e172ae4811b4a2eed`，原 7 modified / 23 untracked 顶层入口及其他任务的 5 个修改文件 SHA 保持，不从该旧树发布产品。
- 一致性备份后只将私有配置 `IWA_VISION_PROVIDER=none` 改为 `deepseek`，并重启本机服务；Flash/off/2000/180，评价 Pro/high/32000/420，精修改写 Flash。备份在主树 `.tmp/ielts-writing-ai-trial/backup-before-vision-enable-20261114/`。
- PID 38918、127.0.0.1:5055 健康且源码 cwd 正确；登录、页面、CSRF、退出检查通过，额度 30/30。真实试用库仍 1 账号、0 作文、0 生成、0 用量；批次使用独立临时库，不消耗网页试用配额。启用和登录检查自身均 0 模型调用。
- 未合并 main，未操作生产后端、网页或数据库；外部模型调用仅本轮 11 次；小程序未上传、提审或发布。本机识图按授权保持开启。

## 可复核证据与命令

公开本目录只含数字、哈希、中文概述和审计脚本；原稿、题图、确认读数、完整反馈和思考、教师包、Key、私有配置、数据库及执行器留在 Mac。完整新批次位于主树 `.tmp/iwa-official-t1-20261114/run/`，不要重复执行付费阶段。

审计严格要求调用时 HEAD `18f5f08`；文档共享后运行树 HEAD 会变化。因此已另建只读复算树 `/private/tmp/studytracker-iwa-official-t1-replay-20261114`（detached `18f5f08`、clean），用它再次复算 277/277 通过。其他 Mac 如有私有材料，可先用 `git worktree add --detach <复算目录> 18f5f08` 建同基线，再替换下列 source 路径。

```bash
cd /Users/zhouxin/Desktop/studytracker
.venv/bin/python -B docs/design/ielts-writing-ai-official-t1-pro-20261114-results/audit_export.py \
  --private-root /Users/zhouxin/Desktop/studytracker/.tmp/iwa-official-t1-20261114 \
  --source /private/tmp/studytracker-iwa-official-t1-replay-20261114 \
  --out /private/tmp/iwa-t1-20261114-audit.json --phase complete
# 277/277；主审独立复跑一致，0 模型调用。
.venv/bin/python -B docs/design/ielts-writing-ai-official-t1-pro-20261114-results/audit_selfcheck.py \
  --source /private/tmp/studytracker-iwa-official-t1-replay-20261114
# 16/16，合成数据，无网络；含首轮坏 JSON→一次重试成功及错误标志负例。
.venv/bin/python -B .tmp/iwa-official-t1-20261114/test_runner.py
# 53/53，fake；执行前已独立复跑，绝不调用真实模型。
.venv/bin/python -B .tmp/iwa-official-t1-20261114/runner.py status
# 只读：closed=true，text 8/8、vision 3/3、failed/unknown=0。
```

[activation.json](activation.json)、[login-check.json](login-check.json)记录本机服务；[source-integrity.json](source-integrity.json)记录源与数据不变；[audit-development-notes.json](audit-development-notes.json)说明审计契约调整。产品未改，本轮不重复上一轮已通过的 494 Python / 8 Node 离线全套。

## 下一步

先对照本轮保留的内容问题和官方评语分析评分差异；未经新授权不增加模型请求或重开新旧 closed 批次。老师填完 10 项后再汇总真实人工意见。当前只能给出本轮小样本观测，不能宣布评分准确性验收通过。
