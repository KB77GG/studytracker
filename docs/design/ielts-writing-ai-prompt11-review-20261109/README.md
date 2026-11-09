# 写作试用 `.11` 离线复核（2026-11-09）

结论：结构与既有运行行为通过复核；发现 **1 项新增 P2 提示词冲突**，建议先修正，再验证真实模型。此次没有调用模型，没有读取 Key、私有思考或学生素材，没有改业务、配置和旧评审文件。

审阅源 `/private/tmp/studytracker-iwa-prompt10-review-20261108`，本地分支 `codex/iwa-prompt10-review-20261108`，由干净 `436ad2f2` 快进到 `19169e627dabe68add012f8d38fd8f0052baa8e4`（业务 `8510ea8e`）；提示词 `iwa-2026-11-09.11`。80 个工具文件合并 SHA256 为 `816f422d3332da6c6ec07baa7a494505880d86a42e14d77bb6f323d1050a66e1`，复核前后一致。

## P2：把所有论证质量排除出 CC，导致同一提示互相矛盾

`tools/ielts_writing_ai/prompts.py:260–263` 新增规则将 task relevance 和 argument quality 都归入 TR，禁止以它们解释 CC/LR/GRA。但同一实际系统提示的 `ARGUMENT_CHECKLIST` 开头要求论证检查解释 TR 与 CC，末尾要求在 task 和 coherence 的评分理由里反映真实问题；`COMMON_DESCRIPTORS` 也要求 CC 判断逻辑推进和段落组织。

六篇 Task 2 的实际提示均有该冲突，`.10` 基线没有。`feedback_probe.py` 103 条检查中 97 条通过，6 条失败对应同一个根因，不能算六个产品缺陷。这里确认的是指令矛盾，**没有实测 `.11` 因此误扣或漏扣分数**。

官方解释明确把观点的组织、句段间联系和论证的逻辑推进列入 CC；TR 则看回应题目、立场及观点的相关性、展开和支撑。见 [IELTS 官方评分解释的 CC 部分](https://ielts.org/take-a-test/preparation-resources/writing-test-resources) 与 [官方 Academic Writing 评分说明](https://ielts.org/take-a-test/test-types/ielts-academic-test/ielts-academic-format-writing)（2026-11-09 核对）。

建议同时改两边的笼统措辞，而不是只从禁止列表中删掉 Coherence：

- TR：题目要求、立场、观点相关性和支撑是否充分。
- CC：观点与段落组织、逻辑推进、衔接及指代。
- LR/GRA：分别用词汇、语法自身证据；不能仅因离题或论点薄弱就解释语言分。
- 论证检查发现只进入有对应证据的评分项，不要求每个问题同时解释 TR 与 CC，也不机械重复扣分。

可参考的通用英文边界（建议，尚未写入产品）：

> Assess task fulfilment, position, relevance, and development/support of ideas under TR. Assess organisation, logical progression, paragraphing, and cohesive links under CC. Justify LR and GRA with lexical and grammatical evidence; do not infer language weaknesses from off-topic content or weak support alone. Map each argument finding to the criterion feature it actually evidences.

## 结构侧通过，真实改善仍是假设

- 实际提示中的三种完整示例均合法，连续闭合符峰值确为 2；占位示例原样照抄或只修改分数仍被拒。
- 两份 mid 原始坏 JSON 仍严格拒绝；诊断准确指出 argument 少闭合。替身重放恰好两次调用，带诊断重试后仍坏就失败，不补括号出分。high/32000/300 秒/json_object 参数保持。
- 六份有效回复（含 Task 1）分别用八个固定随机种子递归改变键顺序，整个归一化结果相同；旧平铺格式仍兼容。`llm.py/review.py/jsonshape.py/argument.py/visual.py/config.py` 与基线逐字一致。
- 新 fixture 的八条正式输出与上批公开文件逐字一致。详见 [结构复核](structure_review.md) 及 [125 项结构探针](structure_probe.json)。

需要更正的说明：`.8/.9/.10` 有六份缺括号回复，另有一份 `.8` 离题回复提前关闭对象，不能说全部括号错误都是漏括号。准确措辞应是“这六份缺括号回复有共同形状”。也不是每个对象都以标量结尾：position 仍是对象、根对象仍以 priorities 列表结尾；已证实的是指定评分项/argument 的键序及示例的闭合峰值变化。

离线测试证明示例、消息和校验行为，不能证明模型会遵守新顺序，或三类反馈误判已经改善。不要把规则字符串存在性测试当作语义准确率测试。

## 关于旧样本例子：建议移出在线提示，保留离线回归

建议删除/通用化提示里的开发样本专用例子，保留通用规则，把原句、坏回答和人工判定完整留在离线夹具。除列出的四个例子外，一并检查 `the lion's share of funding`、公交优先但必要修路的限定立场，以及 Task 1 A/C 两年比较示例。

四个例子不全是作文原句：`much less crowded` 是 mid 原稿原句；另外三个来自旧反馈或特定改法，同样属于开发材料暴露。精确原句扫描只能发现一部分，不能证明没有题目或答案提示。详见 [反馈与样本复核](feedback_review.md)。

这七篇已长期用于修改规则、阈值和提示，应称为**开发回归集**。即使删掉例子，也不能恢复成独立测试集。它们可继续检查历史问题和格式稳定性；评价泛化与评分准确度，需要没有参与修改的新题材留出样本和老师基准。此次只给建议，没有擅自移除例子或使用老师材料。

## 本机验证与复跑

主资料树 `/Users/zhouxin/Desktop/studytracker` 的 `.venv/bin/python`（3.13.3）：

| 验证 | 结果 |
|---|---:|
| 完整 Python 套件 | 388/388，21.320 秒 |
| Node 草稿测试 | 8/8 |
| 本轮独立结构探针 | 125/125 |
| 本轮反馈静态探针 | 97/103，6 失败归并上述 1 项 P2 |
| 原 schema 探针 | 175/175 |
| 原条件提醒探针 | 341/341 |
| 原提醒/回放统计探针 | 120/120 |
| ruff、black（54 文件）、JS 语法、git diff --check | 通过 |

完整套件使用本机 `docs/design/iwa-prompt11-review-20261109/run_offline_tests.py`：剔除外部 IWA 配置和代理，假模型、临时库，禁止非回环连接。初次受沙箱禁止端口影响，获准执行同一运行器后通过；外部测试数据目录未写。记录见 `offline-tests.json` 和 `offline-tests.log`。本轮未重复三种 locale、Python 3.10、全部 48 个历史探针或浏览器全流程；页面/运行代码没有变化。未把旧探针契约失效当新回归。

在独立审阅树可运行：

```bash
PY=/Users/zhouxin/Desktop/studytracker/.venv/bin/python
OUT=/private/tmp/iwa-prompt11-recheck
mkdir -p "$OUT"
$PY -B docs/design/ielts-writing-ai-prompt11-review-20261109/structure_probe.py --repo . --output "$OUT/structure.json"
$PY -B docs/design/ielts-writing-ai-prompt11-review-20261109/feedback_probe.py --repo . --output "$OUT/feedback.json"
$PY -B docs/design/ielts-writing-ai-prompt10-review-20261108/schema_probe.py --repo . --output "$OUT/schema.json"
$PY -B docs/design/ielts-writing-ai-prompt10-reminder-review-20261109/reminder_probe.py --repo . --output "$OUT/reminder.json"
$PY -B docs/design/ielts-writing-ai-prompt10-reminder-review-20261109/metrics_reminder_probe.py --repo . --output "$OUT/metrics.json"
```

反馈探针当前预期退出 1；其他为 0。修复提示后应按新的准确边界补正反例，不能只删除失败断言。

## 交付与下一步

本目录审阅文件与两份规范交接按既有授权只同步功能分支 `claude/ielts-writing-ai-trial`；最终报告提交号见 Git 历史。主树原 7 modified / 23 untracked 顶层入口及其他任务保留；本机运行器、源状态和首次沙箱日志留在 `docs/design/iwa-prompt11-review-20261109/`，不提交。产品源码未改，未合并或推送 main、未部署、未访问生产或写库，小程序未上传/提审/发布。

下一位先修正 CC/TR 边界和历史表述，按用户决定处理旧例子，再复验。没有新的付费授权；上一批 8/14 已关闭，剩余 6 次不追加。此次不申请或执行新的真实批次。
