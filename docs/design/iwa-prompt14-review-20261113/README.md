# 写作 AI `.14` 离线复核（2026-11-13）

审阅基线为 `/private/tmp/studytracker-iwa-prompt14-review-20261113`，分支 `codex/iwa-prompt14-review-20261113`，HEAD `fd8e910b3d5f5a5385af5a99d073c3824bbe74b2`，业务提交 `d0650bb0`，提示词 `iwa-2026-11-13.14`。离线验证结束时该树 clean，未修改产品代码。本报告与探针写在主树 `/Users/zhouxin/Desktop/studytracker` 的本目录；主树仍为 `main@6ded77d2`，原有 7 个 modified / 23 个 untracked 入口保留，不把主树文档当成主树已经拥有 `.14` 产品代码。

原复核的两项抄题 P2 和一项超时配置 P3 已关闭。新增一项局限于**确认片段 `quote` 的完整词边界校验**的 P2，尚未修复；不能将本轮概括成产品无剩余问题。网页提交、本批四篇不带确认抄题标注的 Task 1，以及官方 2B-A 的两段整段确认都不触发该路径。前述具体路径的离线结果通过，与新 P2 分开记录。

本文只含合成例子、数字与运行说明。没有保存官方作文正文、学生材料、原始模型回答、reasoning、Key、Cookie 或账号凭证。

## 已关闭的问题与通过项

| 检查 | 本轮结果 | 证据 |
| --- | --- | --- |
| 原 P2：相似句自动扣词，把自写趋势句算作抄题，152→138 | 同一合成 Task 1 保持 152；评价输入没有 `copied_from_question`、`copied_note` 或 `word_count_without_copied`；页面仅有待确认提示，明确没有扣词，没有不足 150 的提示 | `confirmed-evidence.json` 的 `prior_false_positive` 及相应检查 |
| 原 P2：官方 2B-A 确认抄题 34 词只识别 18 词，得到 210 而非 194 | 读取本机原文，原始 228 词；确认第 1、2 段后准确排除 34，评价输入剩 194。初次确认探针在内存补元数据；随后段落探针直接加载本机已重填 JSONL 的整段确认，并与旧结果绑定的原文和题目逐字核对，均通过 | `confirmed-evidence.json` 的 `official`；`paragraph_probe.json` 的当前元数据、源稿一致、34/194 检查；两探针记录的是不同时间点的输入哈希，正文不变 |
| 原 P3：非法超时未在请求前拒绝 | `IWA_LLM_TIMEOUT`、`IWA_EVALUATE_THINKING_TIMEOUT`、`IWA_VISION_TIMEOUT` 的非有限值、零、负数和超过 3600 秒的值在建客户端及预留账本前失败 | `vision_budget_probe.json`；三个配置对应的校验、无客户端、无账本检查 |
| 普通确认标注校验 | 段号类型、越界、缺失/多次出现/跨段/普通词中间的 quote、重复区间、段与 quote 重叠、quote 互相重叠、歧义/多余键全部拒绝；依据缺失、空白、非字符串、超长等返回带行号的错误，1 与 200 字边界通过 | `confirmed-evidence.json` 的 `resolve_reject_*`、`load_reject_*`、`basis_length_*` |
| 确认标注的数据流 | 合法区间、依据入库并导出；评价输入只收到区间与准确扣词数；确认依据不发给模型 | 同文件 `realcheck` 与对应检查；仅 FakeClient |
| 网页权限边界 | 带会话/CSRF 的真实 Flask 测试客户端附加伪造 `copied_spans`、`copied_from_question`、`copied_source`，提交仍按普通作文处理：确认字段未入库、未发给模型、原 152 词保留 | 同文件 `web_*`、`forged_web_submission_*` |
| 旧库自动迁移 | 用 `f46756f8` 的真实旧 schema 建合成 SQLite，5 表 6 行；启动两次只新增一个可空 `copied_spans` 列，所有旧字段逐项相等，外键检查通过 | 同文件 `migration` 与 `migration_*` |

## 唯一新增 P2：一个词可拆成两个确认片段并重复扣词

位置：`tools/ielts_writing_ai/essay.py:279–280`，`resolve_copied()` 用相邻字符的 `isalnum()` 判断 quote 是否截断一个词。计词函数的 `WORD_RE` 则把英文撇号、弯撇号及连字符连接的部分算作同一个词。两个定义不一致：`don't` 中的 `don` / `t`、`don’t` 中的 `don` / `t`、`cost-effective` 中的 `cost` / `effective` 都被错误接受为完整词。

以下是完全合成、可复现的输入构造：

```python
text = "A cost-effective plan works. " + " ".join(["item"] * 147)
sample = {
    "id": "split-token-threshold",
    "task_type": "task1",
    "prompt": "The chart compares spending on a cost-effective plan over time.",
    "essay": text,
    "copied_from_question": [{"quote": "cost"}, {"quote": "effective"}],
    "copied_source": "Synthetic annotation for boundary regression",
}
```

原文按产品自己的计词函数是 **151 词**，其中 `cost-effective` 只占 **1 词**。`load_samples()` 接受两个片段，`realcheck.run()` 将它们作为两条确认 span 入库，评价输入实际得到 `word_count_without_copied: 149`，页面实际输出“原文 151 词，去掉后 149 词，低于 150 词要求”。同一原文词被扣了两次。这条证据经过 JSONL 加载、临时 SQLite、真实提示构造与结果规范化的完整流程，模型由 FakeClient 替代，不能据此声称真实模型分数已下降。

期望是拒绝这类截断词的确认标注。如果确认的是完整 `cost-effective`，最多扣 1 词，剩 150。三种连接形式共六个半词输入全部错误通过；普通字符区间重叠检查捕捉不到同一计词 token 内的两个不相交片段。

建议使用已有 `WORD_RE.finditer(normalized_essay)` 得到与计词一致的 token 区间，拒绝起点或终点落在任一 token 内部的 quote；保留完整 token、前后标点和原有字符区间互斥规则。修复测试至少包括三种连接符的左右半词、完整复合词正例，以及上述 151 词端到端场景。不要通过截断负数或调相似度阈值掩盖多扣。

`confirmed_probe.py` 结果 **61/71，exit 1**。十个失败均属于这一个问题：六个半词拒绝断言、三种经 loader 的拆词拒绝断言、一个不足 150 的端到端断言；不是十项独立发现。证据为 `confirmed-evidence.json` 中的 `token_boundary`、`boundary_threshold_end_to_end` 与 `findings`。

影响范围明确如下：网页不接收确认标注；官方 2B-A 使用 `{"paragraph": 1}` / `{"paragraph": 2}` 整段确认；本批 Task 1 没有 `copied_from_question`。这些路径不经过出错的 quote 端点判断，离线验证没有发现因此误扣。后续可执行批次应继续固定这些输入，不临时加入 quote 标注。

## 全套验证与精确复现命令

本机 Python **3.13.3**，468 项 Python 全通过、8 项 Node 全通过；来源是本目录 `offline-tests.log` / `offline-tests.json`。隔离 runner 使用 fake 配置、临时数据目录并禁止非回环网络，临时数据哨兵未写。本文没有把作者的多 locale 结果冒充本机重复执行结果。

识图/预算离线探针 **139/139，exit 0**，真实调用和网络尝试均为 0。覆盖三个超时在客户端/账本之前拒绝、首 1 加剩余 3 的识图顺序、最多 16 次文字请求（8 次正常评价加 8 次校验重试）、满额后的第 5 图和第 17 次文字请求被阻断、失败识图的 ready 门禁不再发文字请求或写账本，以及确认数据非法时 CLI 提前拒绝。它证明调用边界，不证明真实图表识别或评分质量。

段落/兼容适配探针 **70/70，exit 0**，保留旧 `.13` 探针和原输出，在本目录另存 `paragraph_probe.py` / `paragraph_probe.json`。只用旧真实 run 的回答正文与 submission 回放，不使用 reasoning 或旧的已规范化结果。两份旧 raw 经 `.14` 重新规范化均保留 **9 段**（实际 `.12` 基线仅留 8 段），各 `returned=kept=15`、`over_limit=0`；各项分数与 raw 及 `.12` 规范化结果均相同，总分仍是 **5.5 / 5.0**。这是旧回答的离线兼容检查，不是用 `.14` 重新询问模型后得到的新分数。

同一探针从当前本机 `official_lowband_t2.jsonl` 加载整段确认，先核对原文、题目、词数与旧 run 一致，再构造 `copied_spans`；两次结果及两次新请求都确认 **34 词、剩 194 词**，确认依据未出现在请求。实际 `iwa.js` 渲染函数在 Node VM 的最小 DOM 中显示全部 9 段及全部提示，复制按钮启用且点击得到完整复制文本；去掉新增结果字段仍兼容。此处不是截图或真实浏览器声明。20 段、重复文本及非法段位的原压力检查也继续通过。

比较消息时直接载入 **`abf48d49a446582749a53d320a7c6e6364d0841e` 的真实 `.12` 模块**（`iwa-2026-11-10.12`），不手工重建旧提示词。内置 7 篇，加 teacher 1、rated Task 1 两篇、rated Task 2 四篇、ordering 10 篇、lowband 6 篇，共 **30/30 的完整 messages 相同**。这些样本均没有确认区间；五份外部 JSONL、旧 run 和当前官方 JSONL 在探针前后哈希不变，只公开数字、哈希和布尔结论。

以下从主树执行；这些都是已运行的离线命令，不包含真实模型命令：

```bash
cd /Users/zhouxin/Desktop/studytracker

.venv/bin/python -B docs/design/iwa-prompt14-review-20261113/run_offline_tests.py

.venv/bin/python -B docs/design/iwa-prompt14-review-20261113/confirmed_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt14-review-20261113 \
  --private-sample /Users/zhouxin/iwa-calibration/official_lowband_t2.jsonl \
  --output docs/design/iwa-prompt14-review-20261113/confirmed-evidence.json

.venv/bin/python -B docs/design/iwa-prompt14-review-20261113/vision_budget_probe.py \
  --source /private/tmp/studytracker-iwa-prompt14-review-20261113 \
  --out docs/design/iwa-prompt14-review-20261113/vision_budget_probe.json

.venv/bin/python -B docs/design/iwa-prompt14-review-20261113/paragraph_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt14-review-20261113 \
  --private-run /Users/zhouxin/iwa-compare-official-lowband-20261113/official-t2/run_data.json \
  --samples-dir /Users/zhouxin/iwa-calibration \
  --baseline abf48d49 \
  --output docs/design/iwa-prompt14-review-20261113/paragraph_probe.json

.venv/bin/python -m ruff check \
  docs/design/iwa-prompt14-review-20261113/confirmed_probe.py \
  docs/design/iwa-prompt14-review-20261113/paragraph_probe.py
.venv/bin/python -m black --check \
  docs/design/iwa-prompt14-review-20261113/confirmed_probe.py \
  docs/design/iwa-prompt14-review-20261113/paragraph_probe.py

git -C /private/tmp/studytracker-iwa-prompt14-review-20261113 diff --check
git -C /private/tmp/studytracker-iwa-prompt14-review-20261113 status --short --branch
```

runner 内实际测试命令的工作目录为审阅树：

```bash
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest discover -v \
  -s tools/ielts_writing_ai/tests -t .
node --test tools/ielts_writing_ai/tests/test_draft.js
```

`confirmed_probe.py` 需要本机私有官方原文文件；`paragraph_probe.py` 还需要历史 run 和五份本机外部 JSONL。输出只含哈希、段号、计词/评分数字与布尔结论；其他机器没有这些文件时不能宣称已经复跑官方实样或 30 篇消息兼容性。合成回归与迁移数据不含隐私。

## Task 1 后续执行边界

用户已授权本批最多 **16 次文字请求 + 4 次识图**，执行仍需沿用下列具体门禁。原执行说明“首图试读后再跑四篇全量识图”会重复读取第一条：账本按尝试记账，不按样本 ID 去重，也不提供单独 realcheck 的自动续跑。不能把已花掉的 1 次留在另一本账本，或在下一命令扩大上限。

1. 全程固定同一批次账本及 `--ledger-text-cap 16 --ledger-vision-cap 4`，保存源码、样本、题图和最终冻结识图结果的哈希。上限由调用方参数提供，并非不可改的账本表头，后续命令必须继续传相同值。
2. 首次仅取第一条：`--images-only --with-vision --limit 1 --max-calls 1`。这 1 次计入上述 4 次，检查实际题图对应关系、描述和状态后再继续。若失败，失败/未知尝试仍占预算，不能自动补一个“免费重试”。
3. 后续样本文件明确只保留剩余三条，以 `--images-only --with-vision --max-calls 3` 执行；不重新输入原四条。两次结果必须 ID 无交集、合并后正好四条且全部 ready，才能冻结。
4. 合并识图结果一次，外部核对冻结结果对应的样本及图像哈希。结果映射本身按 ID 匹配，不能只凭同名 ID 推断题图未改变。
5. 评价用原四条样本、`--kinds evaluate --repeat 2 --image-descriptions <冻结文件> --require-ready-images --max-calls 16`，继续同一账本及 16/4 上限。此阶段不再启用识图；8 次计划评价各最多一次格式校验重试，最坏文字请求 16。
6. 完成后复算账本预留数、实际请求数、失败/未知数以及图片 ID 覆盖；不能把剩余额度解释为自动追加批次的授权。

离线证据中的最坏流程为图 1+3、文字 16、8 次评价、4 篇不同作文；真实效果尚待下方记录。上述修正针对执行顺序，没有改变产品代码或声称原命令已发生真实超额。

## 真实执行与最终本机状态

- 本机没有新 ZIP；按用户明确说明与已核对官方评语，只给既有模板添加第1、2段确认字段。已保留原文件备份并重填，Task1字节不变，Task2只增加确认字段，34/194符合；哈希见 `data-update-check.json`，没有改原文凑数。
- 本机私有试用 `.env` 已短暂启用 Flash 识图并把服务指向本审阅树 `.14`。SQLite一致性备份后启动自动新增 `copied_spans` 列，账户1、作文/生成/用量0前后不变；登录、退出、30/30额度检查通过。
- 新批次固定同一独立账本16文字/4图，先只读 `official-1B-A`，实际 **1 次识图、0 次文字**。Flash/off/2000/180，HTTP与结构通过，程序标ready；但人工核原图发现电视16:00约21–22%被读为14%、22:00约39–40%被读为45%。两位agent独立视检确认，数值是模型原始输出，不是程序渲染改变；未据此推断真实TA分数变化。
- 首图人工门禁未通过，没有创建批准文件。剩余3图及8次评价均未开始，本批关闭，余额不自动复用。完整证据、账本与费用复算见 [Task1首图报告](../ielts-writing-ai-official-t1-pro-20261113-results/README.md)。824输入、958输出，5.43秒，高峰估算0.009312元，非账户账单。
- 为防止已知错误读数直接进入网页TA，本机 `IWA_VISION_PROVIDER` 已恢复 `none`，模型/地址参数保留，识图是**已配置并连通、暂未启用**。服务继续 `.14`，文字评价Pro/high/32000/420，精修改写Flash；最终PID92571、5055健康，登录正常；私有库数据与额度未变。
- 老师10条材料已整理为18页Word/PDF：7篇完整原稿＋10条原反馈与AI初判＋空白老师判定区；逐项完整性、18页视觉检查通过，尚无老师结论。文件0600且Git忽略，仅本机，见 `teacher-delivery.json`。
- 原3项已修、新quote边界P2仍待Claude修复；不能因为本轮实际路径不受影响就称产品全面无缺陷。没有改产品代码，正式调用源HEAD保持fd8e910b。

本轮只提交脱敏复核、数字报告、执行说明和规范交接到功能分支；提交和push状态以最终Git回读及主树交接确认条为准。Word/PDF、原稿、图片、模型回答/思考、私有配置与数据库都不提交。没有合并main、部署生产、写生产数据库或小程序上传/提审/发布。
