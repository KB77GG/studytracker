# 既有核图门禁回归

固定新源码 `/private/tmp/studytracker-iwa-task-conflicts-recheck-20261114`，HEAD `89c32d6b59f33ea2c4d3a592edd2248836d7de81`。本轮只复用四个现成离线探针，未改预期：

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 旧记录重新生成排队 | 20/20，exit 0 | `mixed-queue.json` |
| 网页门禁及逐结果读数绑定相邻项 | 57/57，exit 0 | `web-adjacent.json` |
| realcheck 原确认绑定反例 | 15/15，exit 0 | `realcheck.json` |
| realcheck 相邻项 | 17/17，exit 0 | `realcheck-adjacent.json` |

全部是临时合成数据、fake 客户端、禁真实网络的原探针；没有真实调用、服务或配置操作。没有遇到回环沙箱阻断，不需审批。共 109/109 通过只表示既有门禁保持，**不改变本轮数字冲突过滤器的独立失败结论**。

## 精确命令

cwd `/Users/zhouxin/Desktop/studytracker`：

```bash
.venv/bin/python -B docs/design/iwa-prompt15-recheck-20261113/web/mixed_queue_probe.py \
  --repo /private/tmp/studytracker-iwa-task-conflicts-recheck-20261114 \
  --old-repo /private/tmp/studytracker-iwa-prompt14-review-20261113 \
  --seed-probe /private/tmp/studytracker-iwa-task-conflicts-recheck-20261114/docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/web_gate_probe_adapted.py \
  --out docs/design/iwa-task-conflicts-recheck-20261114/regressions/mixed-queue.json

.venv/bin/python -B docs/design/iwa-prompt15-final-recheck-20261113/web/adjacent_probe.py \
  --repo /private/tmp/studytracker-iwa-task-conflicts-recheck-20261114 \
  --old-repo /private/tmp/studytracker-iwa-prompt14-review-20261113 \
  --seed-probe /private/tmp/studytracker-iwa-task-conflicts-recheck-20261114/docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/web_gate_probe_adapted.py \
  --out docs/design/iwa-task-conflicts-recheck-20261114/regressions/web-adjacent.json

.venv/bin/python -B docs/design/iwa-prompt15-review-20261113/realcheck/probe.py \
  --source /private/tmp/studytracker-iwa-task-conflicts-recheck-20261114 \
  --out docs/design/iwa-task-conflicts-recheck-20261114/regressions/realcheck.json

.venv/bin/python -B docs/design/iwa-prompt15-recheck-20261113/realcheck/adjacent_probe.py \
  --source /private/tmp/studytracker-iwa-task-conflicts-recheck-20261114 \
  --out docs/design/iwa-task-conflicts-recheck-20261114/regressions/realcheck-adjacent.json
```

完整 stdout 留 `/private/tmp/iwa-task-conflicts-regression-{mixed-queue,web-adjacent,realcheck,realcheck-adjacent}.log`，不纳入共享。开始时新源树只有主审新增的 `docs/CODEX_HANDOFF.md`、`docs/WORKLOG.md` 修改；前后 `git diff --stat -- tools/ielts_writing_ai` 为空。未跑全套或真实浏览器，未修改产品、交接、实际服务，未 commit/push/deploy。
