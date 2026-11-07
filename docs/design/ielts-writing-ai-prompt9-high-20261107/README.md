# 写作 .9 / high 批次已结束：累计13/14，4/7可用

用户要求继续后，在原预算内新增8次实际请求，累计13/14；7篇处理完，4篇有效、3篇失败。运行器已关闭，未用1次不自动追加。详见[续跑结果与人工复核](continuation/README.md)；原中断5次用量仍未知，完整费用不能计算。

以下保留首次中断时的历史记录，后续状态以续跑报告和最新交接为准。

## 首次中断：服务异常，停在5/14

离线复验已经通过；本次真实批次未完成，不能判断 `.9` 是否改善 JSON 合格率或批改质量。这是一份传输中断记录，不是完整的 `realcheck` 结果。

## 范围与源码

- 用户已授权：7 篇内置合成作文，只做评价；`deepseek-flash` / `high`，总计最多 14 次实际 HTTP 请求，每篇最多 2 次，每次输出最多 16,000 token、超时 300 秒。不含精修、改写、识图、老师或学生素材。
- 执行源 HEAD：`9b09562dad8b2e5f348ad8f9d649777543ef52d5`；业务源 `f919067850cbe5fc7ebcaa4fdc2bf10633faeef7`，修复提交 `600938c3`。
- 提示词：`iwa-2026-11-06.9`。75 个工具文件的合并 SHA256：`f0e3cec234a5b3fb09e923be9cf649223efa793267771755ea89785e451039bc`，运行前后相同。
- 运行前离线验证：373 Python、8 Node、lint 通过；证据 205/205、页面/复制 107/107、结构 82/82、统计 100/100。详见[最终离线复验](../ielts-writing-ai-prompt9-finalcheck-20261107/README.md)，这些结果不能替代真实模型验证。

## 实际发生的请求

| 序号 | 样本 | 结果 |
|---|---|---|
| 1 | t2-weak | HTTP 500，约 15.2 秒 |
| 2 | t2-mid | HTTP 500，约 15.1 秒 |
| 3 | t2-good | HTTP 500，约 15.1 秒 |
| 4 | t2-strong | HTTP 200，但没有可用的完成状态、返回模型名或 usage；不算已验证的成功评价 |
| 5 | t2-off-topic | 等待响应时人工中断，进程退出 130；响应与服务端处理结果未知，仍计入请求预算 |

短文和无图 Task 1 尚未请求。未发起第二次尝试。传输账本在发送前落盘，所以这 5 次均保留计数；原始账本未改写。

当时 DeepSeek 官方状态页报告“网页/API 部分中断”，处于修复后监控状态，涉及 Flash API。保存的查询时间为 2026-11-07 07:34 UTC（北京时间 15:34），公告更新为 07:11 UTC。它佐证同时段存在服务异常，但不能证明每个请求的具体失败原因。[官方状态](https://status.deepseek.com/)，[事件记录](https://status.deepseek.com/incidents/7219383236287)。

观察到的是 500，没有观察到 401 或 402。官方把 500 定义为服务端错误，把 401 定义为鉴权失败、402 定义为余额不足。因此本批没有证据把问题归为 Key 错误，也不能据此保证 Key 或账户的全部状态正常。[官方错误码说明](https://api-docs.deepseek.com/quick_start/error_codes/)。

## 结果缺口与下一步

当前 `realcheck` 在整批返回后才保存报告与原始回答；中途退出后，只保住了传输账本，没有 `run_data.json`、`report.json/md`、`raw_calls.jsonl`。第 4 次原始响应也未保存，因此不能进一步归因为括号错误、严格解析失败或有效评价。

**token、思考 token、费用均未知，不是 0。首轮 JSON 率、最终成功率、分数、引文和反馈质量均无法计算。** 没有可用评价文件不等于服务端没有生成或没有计费。

原运行器已禁用，不能直接重跑，也不能删除账本。原授权最多还余 **9 次**：前 5 篇各余 1 次，短文和 Task 1 各余 2 次。待服务恢复后，必须使用关联本账本的续跑守卫，累计仍受全局 14 次和原样本各 2 次限制；不得另起一个 14 次批次。当前没有实现或启动续跑。

后续运行器宜增加连续服务错误停止机制、逐请求保存响应与用量，使中断后仍可审计；这是本次暴露的运行记录限制，尚未修改产品代码或运行器实现。保留严格解析，不用补括号的方式产生分数。

## 独立审计与交付

`interruption_audit.py` 仅读取本目录共享文件，禁用网络，对账 **36/36**；主审复跑通过。覆盖请求计数、逐样本预算、源指纹、未知用量和不生成虚假质量指标。可离线复现：

```bash
.venv/bin/python docs/design/ielts-writing-ai-prompt9-high-20261107/interruption_audit.py \
  --bundle docs/design/ielts-writing-ai-prompt9-high-20261107 \
  --output /tmp/iwa-prompt9-interruption-audit.json
```

- `transport.json`：共享账本；与本机原账本只差末尾一个换行。两份字节 SHA 及对应关系见独立审计，业务内容相同。
- `interruption.json`、`provider-status.json`：中断事实和官方状态记录。
- `runner-selftest.json`、`runner-independent-audit.json`：运行前纯离线调用守卫验证，均不计为真实请求。
- `interruption_audit.py/json/md`：可复现审计和结论。

本机执行目录为 `/Users/zhouxin/Desktop/studytracker/docs/design/iwa-prompt9-high-20261107/`；私有 `results/` 被忽略，运行器与 `.env` 不分享。实际执行过的命令是 `.venv/bin/python docs/design/iwa-prompt9-high-20261107/run_high.py --confirm-paid`，**不要重跑**。Key 未输出或提交，未改试用默认配置，数据库用临时目录。共享报告与交接只推功能分支；没有合并 main、部署、生产数据库写入或小程序上传/提审/发布。
