# 判断准则与格式复核：93d47ec

2026-11-04，Mac/Python3.13.3；源码 `93d47ec318cb9f783a396bdf20b07624865ae355`，提示词 `iwa-2026-11-04.5`。

**本轮离线复核尚未通过，真实模型请求0/14。** 266项Python、8项Node及代码检查通过，成对矛盾、段落绑定、中文校验、顶层格式和报告修复也得到独立验证；但“删除无来源数字建议”仍有两处可复现漏洞，其中一处直接来自上一批真实输出，并非另造的极端样本。因此未满足“复核通过后运行”的条件。本轮新授权仍保留：7篇合成作文、仅评价、最多14次实际请求；未启动付费批次，修复复核通过后可继续同一范围。

## 1. P2：同一句无来源数字建议仍从评分项进入页面和复制文本

用上一批 `t2-mid` 的真实DeepSeek评价原样重放，新规则将argument里的80%建议删去（suggestions_removed=1），但TR的 `issues[].suggestion` 仍包含：

> A full bus can cut emissions per person by over 80% compared with the same number of cars.

原稿没有80这个数字。`copytext.evaluation_text()` 的完整评价仍含80%；前端 `iwa.js` 也直接渲染评分项的建议。学生看到的仍是同一句未经提供来源的建议，旁边的论证节却提示已经删去了一条。

路径：`argument._suggestion` 只处理argument的问题/可选优化；`review._evidence_items` 的评分项建议没有同样处理（约第123行）。这不是说80%必然不真实，而是它在输入里没有来源，恰好就是本轮声明要解决的实际情况。

建议将同一条规则覆盖本次评价所有对用户展示的建议路径，至少包括评分项 `issues[].suggestion` 与argument建议；保留引文与原稿，不直接改学生文本。删除提示/统计应与实际覆盖范围一致。回归须同时检查服务端结果、完整复制文本以及前端使用的字段，不能只断言argument中删掉了数字。

## 2. P2：1980或180被误当成80%的来源

`argument.unsourced_figures`（约第112–120行）从建议提取数字后，用 `number in known` 在去空白的整篇原文中作子串判断。结果：

| 原文 | 建议 | 当前结果 | 应有结果 |
|---|---|---|---|
| 公交于1980年开通 | 减排80% | 保留 | 没有这一比例，应删除 |
| 城市运营180辆公交 | 减排80% | 保留 | 没有这一比例，应删除 |
| 原文没有数字 | 减排80% | 删除 | 正确 |
| 原文明确写80%减排 | 减排80% | 保留 | 数字来源匹配通过 |

建议至少按完整数值及比例标记匹配，不能把另一个数的尾部当作来源；保持“补1个例子”“第2段”的结构性提示可用。完整数字匹配也不证明统计命题本身正确，本次要求修复的是明确不同数字被混淆的实现错误，不要求程序解决所有语义事实核查。

两项证据均在 `argument_review_probe.json`：`real_output_advice_coverage`、`numeric_token_probe`。主agent已独立复跑确认。原始真实输出来自上一轮共享 `ielts-writing-ai-argument-recheck-20261104/run_data.json`，没有新的模型调用。

## 已确认通过的部分

- 5组成对引文正反例：真实不同引文保留，同一/包含/虚构/缺失引文丢弃；自相矛盾及段落判定冲突标为需人工确认。
- 可选优化不计为问题；97词原文的5个条目归并为1个实际段落，另4条计重复。
- 上轮首个坏JSON仍严格拒绝；诊断性补括号后层级错位明确提示，不采用修补输出。
- 全英文Task1被拒，并沿生产Generator路径重试一次；Task1比较保留可核实的claim/figures，对空、虚构、与claim相同的对照有过滤。
- 没有把历史模型错误“洗成通过”：旧强文剩余两条unsupported仍导致合成合理性失败；旧Task1即使只把解释翻成中文，漏报矛盾仍失败。这些须通过新提示词的真实效果检验，不是本轮额外代码阻塞项。
- 新计数守恒；全部Task2失败仍有论证章节；未运行的改写检查标为跳过且不进入通过分母。指标/流程探针18/18通过。
- 7篇评价最坏14次替身调用，max_tokens4500、HTTP retries0。全部是离线调用，不消耗已授权的实际请求。
- 旧立场评论在一致性判断撤回后仍保留，但已有明确“不采用”的提示，本轮不另列阻塞问题。

## 复现与交付

准确完整套件命令及结果见 `offline-verification.json`；Mac完整套件266/266（19.030秒）、Node8/8，ruff、black39文件、JS语法检查通过。测试仅使用临时库/假模型/本机假服务，外部IWA_DATA_DIR未写入。未读取私有Key、未改业务代码或原始历史报告，没有浏览器完整回归或真实识图结论。

在功能分支根目录执行（使用装有试用工具依赖的Python）：

```bash
PY=.venv/bin/python
DIR=docs/design/ielts-writing-ai-judgment-review-20261104
PYTHONDONTWRITEBYTECODE=1 "$PY" "$DIR/argument_review_probe.py" --repo . --output /tmp/iwa-judgment-argument-after.json
PYTHONDONTWRITEBYTECODE=1 "$PY" "$DIR/review_metrics_probe.py" --repo . --output /tmp/iwa-judgment-metrics-after.json
```

第一个探针记录实际行为，退出0不代表产品通过；修复后应比较新JSON，保留本目录历史证据。第二个探针包含预期行为断言。先补正式回归、修复两处数字过滤，再复核并执行已有的7篇评价/最多14次授权，无需重复申请同一未执行批次。

报告、两套探针/结果、离线验证与两份交接文档推送 `claude/ielts-writing-ai-trial`；文档提交见git log。没有修改业务源码，没有main合并/部署/生产或小程序操作。本机运行材料另保留于 `docs/design/iwa-judgment-review-20261104/`。
