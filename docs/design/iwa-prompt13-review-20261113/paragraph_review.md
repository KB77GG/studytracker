# 段落、UI/copy 与 realcheck 离线复核

审阅源码：`/private/tmp/studytracker-iwa-prompt13-review-20261113`，
`codex/iwa-prompt13-review-20261113`，HEAD
`fdf4704ee3ec1aa80aad5e5e9d59f04a6edbc380`。对照源码直接取自 Git
`9c60a347bca6868bc6d06c0b43dd65cf54da8412`，未修改产品文件。
证据保存在主资料树 `/Users/zhouxin/Desktop/studytracker` 的本目录，
主树仍为 `main` / `6ded77d24586327ad94e151e172ae4811b4a2eed`。

探针 60 项中 58 项通过，2 项失败来自同一篇官方样本的两次回放，代表一个漏检问题。
完整数字见 `paragraph_probe.json`；脚本按正确预期保留失败断言，退出码为 1。

## 实样漏检：已确认的 34 词抄题只检出 18 词

- 既有人工核对：总 228 词；前两段含 34 词抄题，自写 194 词。
- `.13` 实际：两次都标出 2 句、18 词，展示“去掉后约 210 词”；漏掉第一段中间的 16 词句。
- 三句的词数为 9 / 16 / 9。中间句匹配率低于 85% 阈值，因此未标出；具体匹配 token 数、比例、最长连续匹配及布尔结果已脱敏保存在 JSON。
- 这同时影响构造给模型的 `word_count_without_copied` 和页面/复制提示。页面与复制渠道正确传递了当前结果，但当前词数不完整。
- 回放只使用旧回答正文重新做后处理，没有请求新评分；四项分与总分均未被程序改动。不能据此推断真实模型在 `.13` 下会如何改变分数。
- 不建议单独降低阈值：本轮其他探针同时发现高相似度但含新增含义的句子被整句剔除，需要一并考虑漏检与误检。

## 已通过的修复与兼容性

| 检查 | 结果 |
| --- | --- |
| 两次官方回答段落 | 都保留 P1–P9；旧版均只保留 P1–P8 |
| 两次条目计数 | 各 `returned=15, kept=15, dropped=0, duplicates=0, over_limit=0`；旧版各 `kept=14, over_limit=1` |
| 分数保持 | TR/CC/LR/GRA 为 5.5/5.5/5/5 → 5.5、5.5/5/5/5 → 5.0；与原回答及旧版后处理一致 |
| 页面渲染与复制 | 实际 JS 渲染函数在最小 DOM 中生成 9 个段落节点、全部段号及 warnings；点击复制按钮传递服务端完整文本 |
| 旧结果兼容 | 删除 `copied_from_question` 字段后，渲染和复制仍通过 |
| realcheck | 两次 strict/normalization 首次检查接受；累计 18 段，30 返回 = 30 保留，无丢弃/重复/超限 |
| 20 段合成输入 | 排序后全部保留，不再存在 8 段上限 |
| 重复、无效段位与上限 | 错段号按真实引文重新定位；重复 2、无效 3、问题/优化超限 4；39 = 30 + 3 + 2 + 4 |
| 完全重复的 12 段 | 有正确段号提示时保留 12 个真实段位 |
| 段落容器形状错误 | 仍拒绝，未放宽有效引文要求 |

UI 证据是实际渲染函数、API view 与 copy 按钮事件的离线执行，不是浏览器视觉截图或真机验收。
realcheck 范围是首答归一化与 argument 指标路径，没有重新执行模型或完整付费流程。

## 未触发抄题的样本请求保持不变

实际运行新旧两个版本的 `build_evaluate` 并逐项比较完整 messages（不是只比较提示词版本或系统消息）：
开发 7、teacher 1、rated Task1 2、rated Task2 4、ordering 10、lowband 6，合计 30 篇，
全部 `copied=0`，全部 messages 完全相等。这里使用各样本本来提供的图像状态/描述；未额外调用识图。
五个私有 JSONL 的前后 SHA 一致。

## 复现与边界

```bash
.venv/bin/python -B docs/design/iwa-prompt13-review-20261113/paragraph_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt13-review-20261113 \
  --private-run /Users/zhouxin/iwa-compare-official-lowband-20261113/official-t2/run_data.json \
  --samples-dir /Users/zhouxin/iwa-calibration \
  --output docs/design/iwa-prompt13-review-20261113/paragraph_probe.json
.venv/bin/ruff check docs/design/iwa-prompt13-review-20261113/paragraph_probe.py
.venv/bin/black --check docs/design/iwa-prompt13-review-20261113/paragraph_probe.py
```

第一条预期 exit 1、58/60；Ruff 与 Black 通过。只选择私有运行数据的 `call.text` 与
`sample.submission`，不使用 reasoning、既有归一化 generations、usage 或私有设置。
输出仅含数字、布尔与选择字段的 SHA，不含真实作文、引文或模型评语；源私有文件未修改。
网络连接被禁止，没有读取 `.env`/Key，没有调用模型或修改试用/生产库。

本子任务仅新增本目录的探针、数字证据与说明，本机可见，未 commit/push/deploy；
没有合并 main 或小程序上传/提审/发布。规范交接由父任务统一汇总到
`docs/CODEX_HANDOFF.md` 与 `docs/WORKLOG.md`，避免并行覆盖。
下一步应同时修正新增含义误剔除与本实样漏检，再原样运行失败断言，不应改低正确预期。
