# `.15` 最后一个网页 P2 复验通过

固定源码 `/private/tmp/studytracker-iwa-prompt15-final-recheck-20261113`，分支 `codex/iwa-prompt15-final-recheck-20261113`，HEAD `e3901a0c4312f42c7a90996f47e18b4d96d4935d`（业务 `d92f0839`）。旧 `.14` 播种树 `/private/tmp/studytracker-iwa-prompt14-review-20261113`，HEAD `cd82fc1b`。两树只读，报告写在 `/Users/zhouxin/Desktop/studytracker/docs/design/iwa-prompt15-final-recheck-20261113/web/`；主资料树旧产品不因此获得新实现。

## 结论与证据

原剩余 P2 已关闭：旧记录重新生成排队时不再重新开放确认。原 `mixed_queue_probe.py` **预期未改、20/20、exit 0**（上一版 15/20）。confirm 和 skip 均 409；原读数、核对空值、旧精修和改写的 ID/完整结果保持；`awaiting_check=false`、`unchecked_legacy=true` 在重生成前后都正确。使用公共 API、真正的默认两个后台 worker、`.14` 源码播种的临时旧库与 fake 模型，无直接改库。

作者的 `web_gate_probe_adapted.py` 原样 **45/45、findings=[]、exit 0**。首次核对、改正、skip、重启、并发、权限/CSRF、额度、旧记录直接确认和畸形请求的通过结果保持。

本轮新增 `adjacent_probe.py` **57/57、exit 0**：

- 真实 `.14` 旧记录三项同时重新生成，最新三个 attempt 全部 queued，历史 ready 记录仍使窗口关闭；confirm/skip 与原子写库均拒绝。放开真正双 worker 后三项完成，均记录 `checked=false`、无错配、评价无 TA，消息未包含图表读数，legacy 提示继续保持。
- 合成临时库额外构造“全部 queued，但一项已有 started_at”，页面、端点和原子写库仍拒绝；首次窗口正例和不存在作文的负例均正确。这一项是明确标注的存储边界测试，不声称由公共入口自然产生。
- 新提交改正并确认后，评价/精修/改写三结果，以及各自重新生成，都绑定同一正确 SHA；实际 fake 请求都包含改正读数，不能再次确认。
- 在 fake 已收到请求后改变临时库读数，输出仍保存它实际收到的旧输入快照，读取页面时三输出全部标错配。查询页面不会重写已保存结果。
- skip 后三结果记录未核对，消息不含读数；Task 1 无图、Task 2 均不附 `chart_reading`。
- `.14` 无快照旧结果保留整体 legacy 提示；不会伪称已有精确快照，也不会将 unknown 自动判断为 mismatch。

详见 [原反例数字](mixed-queue-evidence.json)、[作者探针数字](author-adapted-evidence.json)、[相邻检查数字](adjacent-evidence.json)。全部是合成数据/临时 SQLite/fake 客户端；真实调用 0，新相邻探针的网络尝试 0。未打开真实配置、Key、私有样本或实际试用库，未操作试用服务或生产。

## 实现审查

- `storage.py:95–100` 的 `CHECK_WINDOW_SQL` 查全部生成历史：至少一条 queued，且不存在非 queued 或 `started_at IS NOT NULL` 的记录；不是仅看最新结果。
- `storage.py:365–370` 将同一表达式直接放进 UPDATE 的 WHERE，写入时原子核验；`check_window_open`（375–385）与 `web.py` 的页面/端点使用相同判定，不只相信之前的页面状态。
- `review.py:920–929` 对用于本次请求的同一个 submission 副本计算并持久化快照；未在调用结束后重新读取可能已变的数据库读数。`review.py:102–118` 比较当前是否有效确认及确认读数 SHA；未核对读数不发给模型，因此记录为 `false/null`。
- `web.py:363–364` 暴露 `reading_mismatch`；`static/iwa.js:489–490` 在结果内容之前显示错配提示。真实浏览器未在本专项重跑，只有源代码审查与 API 结果验证。

## 精确命令

以下 cwd 均为 `/Users/zhouxin/Desktop/studytracker`：

```bash
.venv/bin/python -B docs/design/iwa-prompt15-recheck-20261113/web/mixed_queue_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113 \
  --old-repo /private/tmp/studytracker-iwa-prompt14-review-20261113 \
  --seed-probe /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113/docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/web_gate_probe_adapted.py \
  --out docs/design/iwa-prompt15-final-recheck-20261113/web/mixed-queue-evidence.json

.venv/bin/python -B /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113/docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/web_gate_probe_adapted.py \
  --repo /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113 \
  --old-repo /private/tmp/studytracker-iwa-prompt14-review-20261113 \
  --out docs/design/iwa-prompt15-final-recheck-20261113/web/author-adapted-evidence.json

.venv/bin/python -B docs/design/iwa-prompt15-final-recheck-20261113/web/adjacent_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113 \
  --old-repo /private/tmp/studytracker-iwa-prompt14-review-20261113 \
  --seed-probe /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113/docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/web_gate_probe_adapted.py \
  --out docs/design/iwa-prompt15-final-recheck-20261113/web/adjacent-evidence.json

.venv/bin/python -m ruff check docs/design/iwa-prompt15-final-recheck-20261113/web/adjacent_probe.py
.venv/bin/python -m black --check docs/design/iwa-prompt15-final-recheck-20261113/web/adjacent_probe.py
```

预期依次为 20/20、45/45、57/57，最后两条检查通过。初轮相邻脚本 Ruff 发现一个未使用 import，已移除；产品文件无改动。

## 边界与交接

本专项未发现新的阻断。它验证状态门禁和输入/输出绑定，不证明读图或评分准确，也不替代主审的全套、私有实样或本机升级检查。快照新增前的结果缺乏历史读数证据，`reading_mismatch` 明确不反推；本轮已验证真实 `.14` 旧记录由 legacy 提示覆盖。不能据此宣称修复了任意外部工具改写的历史库。

新源码树前后 clean；没有更改产品、任何真实库/配置/服务、账本或生产，没有 commit/push/deploy，也没有小程序上传/提审/发布。本子任务的报告、探针与脱敏 JSON 仅本机可见；总报告与规范交接由主 agent 合并。下一步由主审汇总其余复验，通过后按既定流程升级本机，识图继续 none、旧账本保持关闭。
