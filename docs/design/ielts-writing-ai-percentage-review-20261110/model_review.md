# Pro 请求与对照工具专项复核

审阅源 `/private/tmp/studytracker-iwa-percentage-review-20261110`，HEAD `57c825b4`，业务 `661180f3`。本复核只读产品代码；合成配置、合成请求与内存 HTTP 替身，不读取真实配置、Key、学生材料或私有思考，不外联网、不启动服务、不调用模型。

## 请求配置：不需要改业务代码

`IWA_LLM_PROVIDER=deepseek`、`IWA_LLM_MODEL=deepseek-v4-pro`、`IWA_EVALUATE_THINKING=high` 能通过配置校验。没有模型名称白名单；`build_client` 透传模型名。实际调用 `Generator._call → ChatClient.complete` 并捕获请求得到：

```json
{
  "model": "deepseek-v4-pro",
  "thinking": {"type": "enabled"},
  "reasoning_effort": "high",
  "max_tokens": 32000,
  "response_format": {"type": "json_object"}
}
```

调用层 timeout 为 300 秒。精修与改写仍为 off、不使用评价的思考预算/超时。证明本地客户端会如此构造请求，不证明远端账号权限、模型可用性、真实质量或实时性能。

## 对照工具可以使用，但有三项必须补充的使用说明

1. **现有人工表不是盲审表，也不完整。** `realcheck_compare.render_manual_review` 会输出两模型名称，仅列 TR/CC 的问题、论证问题、改列、Task 1 一致性等。四项 summary、GRA/LR 问题、改句 suggestion、overall_comment、priorities 不在表中。此次 although 误读在 GRA 理由/priority、错误因果在 suggestion，单看该表会漏掉待检目标。探针用 6 个独立标记证明遗漏，TR/CC 问题正对照存在。正式人工核对须从完整正式评价生成补充的匿名材料，不能只使用当前 `manual_review.md`。
2. **费用参数不能直接准确对照不同定价模型。** `realcheck` 的 `--price-in/out` 对所有输入用一个价格，不区分缓存命中/未命中。`realcheck-compare` 也只有一组价格，并把它同时用于 A/B；若不传，现有 `report.json` 各自保存的价格不会被沿用，费用栏为空。因此应分别按各模型的 cache-hit、cache-miss、output 用量和费率计算，思考已在 output 内，不再加一次。合成 1000 输入（800 hit/200 miss）、2000 输出时，简单价 Pro 为 0.0315；按给定的分缓存示例价格则为 0.02802。把 Pro 的两项价格传给 compare 会把 Flash 也算成 0.0315。
3. **同条件检查不等于所有条件均锁定。** flag 允许模型/服务商不同；仍拒绝提示词、作文/题干/题图、首轮实际消息指纹不同。输出上限、超时在消息之外，预算改变不会被拒；源码提交与规范化规则版本也不是此工具的严格检查项。正式对照仍须额外固定源码哈希、high、32000、300、同一输入集与实际返回模型版本，并记录时间。是否把两模型换名和强度同时变化也只警告，不阻止。

以上多数是现有工具的适用边界，不是此次百分点提交引入的运行回归。无需为这一轮模型选择强行改完整产品；可用离线补充审计/完整匿名材料补齐。

## 两轮重复与重试要分开计数

一次独立评价最多 2 次实际请求：首轮 + 仅在内容校验不合格时的一次重试。这个重试不是第二次独立重复。两模型、每篇各独立评价 2 次时：

| 作文数 N | 独立评价数（两模型 × 两轮 × N） | 含每次最多一次重试的 HTTP 上限 |
|---:|---:|---:|
| 7 篇开发集 | 28 | 56 |
| 7 + 1 老师 | 32 | 64 |
| 7 + 1 老师 + 3 新作文 | 44 | 88 |
| 7 + 1 老师 + 5 新作文 | 52 | 104 |

`realcheck` 在读入和执行时都拒绝重复样本 ID，不能简单将同一 JSONL 行复制两次。无需改变 ID 或产品代码：使用四个独立 run 目录（Flash-r1、Pro-r1、Flash-r2、Pro-r2），各自使用同样的唯一 ID，按轮对照，再另汇总重复性。最好交错/随机安排模型顺序，记录真实返回版本，避免“同一天”被误当作后端和负载完全相同。

开发集可以检查格式以及已知反馈问题的回归，不仅限于格式；但它不能提供独立泛化证据。独立新作文与老师样本另分层统计；每篇两轮用于观察波动，不能把重复运行当作新增独立作文扩大样本量。既有老师组原授权不应自动改成 Pro 或并入新的重复试验，本轮没有发起任何请求。

## 离线证据

`model_probe.py/json` 共 **27/27** 观察断言通过，其中既包括请求正对照，也包括上述工具边界的复现。不是 27 项产品缺陷测试，也不能称真实模型验证。执行：

```bash
.venv/bin/python -B docs/design/iwa-percentage-review-20261110/model_probe.py --repo /private/tmp/studytracker-iwa-percentage-review-20261110 --output docs/design/iwa-percentage-review-20261110/model_probe.json
```

探针文件 ruff/black 通过；产品工作树未改。仅新增主树本机审阅文件，未 commit/push/deploy；规范交接由 root 汇总。
