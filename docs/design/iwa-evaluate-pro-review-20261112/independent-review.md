# 评价专用模型独立复核

- 源码：`/private/tmp/studytracker-iwa-holdout-review-20261111`，分支 `codex/iwa-holdout-review-20261111`，HEAD `85b8daad`（业务 `f2509aa8` / `4097aa2a`）。
- 范围：只读审查 `66f29264..85b8daad`；未修改产品、提示词、配置、Git、服务或学生材料。探针仅写临时目录。
- 未发现阻止本机启用评价 Pro / high / 32000 / 420 配置的问题。

## 核验

`/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B /private/tmp/iwa-evaluate-pro-review-20261112/probe.py`：6/6，通过。

1. 真实 ChatClient 构建的请求体，经 `_open` 离线替身检查：评价 Pro/high/32000/420；精修与改写 Flash/disabled/原预算/基础超时。服务商省略 model 时分别回落到实际请求模型。
2. 两个线程共用同一 ChatClient，一边 Pro 一边默认 Flash，互不污染；基础 model 始终 Flash。
3. 评价首轮不合法 JSON 后重试，两个请求均 Pro/high/420；最终记录/报告为 Pro。
4. HTTP 500 替身使评价失败时，请求记录、预留账本、数据库的生成记录仍为 Pro，不误记 Flash。
5. 配置文件和 shell 故意设置错误的评价模型及 420 超时，batch 两侧仍各自固定 Flash/Pro，high 和 300 秒。
6. 仅评价 realcheck 报告及 compare 条件识别实际评价模型；两边基础模型相同、评价模型不同，未传 allow-model-change 时拒绝比较，显式允许后通过。

探针使用内置合成作文、临时数据库、合成凭据、HTTP 响应替身；socket.connect 被主动禁止。真实模型调用 0，不读 Key 或学生原文。预期的一行 synthetic HTTP 500 日志属于第4项。

Ruff / Black 通过。未重复主审的全套测试，未执行官方样卷、付费连通或页面生成。

## 范围说明

420 秒只适用于开启思考的评价；off 仍沿用基础客户端超时120秒。这与 `IWA_EVALUATE_THINKING_TIMEOUT` 的配置含义相符，本次拟启用 high 不受影响。网络超时是 urllib 每次网络操作的超时，不是整个含重试评价的总耗时上限。

父 agent 负责把本结论与配置/服务实际操作统一写入规范交接。本子任务无 commit / push / deploy。
