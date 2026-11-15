# 既有核图门禁复验：109/109

新源 `68b6d4f2`，仅使用临时合成数据、fake 客户端及既有探针，不改预期。旧记录排队 20/20、网页相邻 57/57、realcheck 15/15 与 17/17，均 exit 0。精确命令和数字证据亦见 [summary.json](summary.json)。

cwd `/Users/zhouxin/Desktop/studytracker`：

```bash
.venv/bin/python -B docs/design/iwa-prompt15-recheck-20261113/web/mixed_queue_probe.py \
  --repo /private/tmp/studytracker-iwa-task-conflicts-final-recheck-20261115 \
  --old-repo /private/tmp/studytracker-iwa-prompt14-review-20261113 \
  --seed-probe /private/tmp/studytracker-iwa-task-conflicts-final-recheck-20261115/docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/web_gate_probe_adapted.py \
  --out /private/tmp/iwa-final-regressions/mixed-queue.json

.venv/bin/python -B docs/design/iwa-prompt15-final-recheck-20261113/web/adjacent_probe.py \
  --repo /private/tmp/studytracker-iwa-task-conflicts-final-recheck-20261115 \
  --old-repo /private/tmp/studytracker-iwa-prompt14-review-20261113 \
  --seed-probe /private/tmp/studytracker-iwa-task-conflicts-final-recheck-20261115/docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/web_gate_probe_adapted.py \
  --out /private/tmp/iwa-final-regressions/web-adjacent.json

.venv/bin/python -B docs/design/iwa-prompt15-review-20261113/realcheck/probe.py \
  --source /private/tmp/studytracker-iwa-task-conflicts-final-recheck-20261115 \
  --out /private/tmp/iwa-final-regressions/realcheck.json

.venv/bin/python -B docs/design/iwa-prompt15-recheck-20261113/realcheck/adjacent_probe.py \
  --source /private/tmp/studytracker-iwa-task-conflicts-final-recheck-20261115 \
  --out /private/tmp/iwa-final-regressions/realcheck-adjacent.json

```

完整 stdout 日志不共享；本轮门禁复验没有真实调用或实际服务操作。Mac 升级由主审在全部复验后单独执行，见上级报告。
