# `.15` 第二次修复：Mac实样、词边界迁移及识图预算回归

源码：`/private/tmp/studytracker-iwa-prompt15-final-recheck-20261113`，分支 `codex/iwa-prompt15-final-recheck-20261113`，HEAD `e3901a0c4312f42c7a90996f47e18b4d96d4935d`（业务 `d92f0839`）。本专项先读了该树AGENTS、CLAUDE、两交接顶部及`iwa-prompt15-fix2-claude-20261113/README.md`，再核对Git状态与最近提交。源码工具95文件前后SHA一致，专项执行前后源码树clean。主资料树 `/Users/zhouxin/Desktop/studytracker` 的旧业务代码没有被替换。

**本专项全部通过，无新增阻断项。** 使用原探针及原预期，仅将目标源码和输出目录改为本轮；7个私有输入SHA前后完全一致。没有真实调用、读取Key/私有配置或试用库，没有修改运行服务/账本/生产。报告只有计数、合成用例标签和哈希，不含官方正文、学生作文、完整回答或思考过程。

| 检查 | 结果 | 关键结论 |
| --- | --- | --- |
| 作者 `confirmed_probe_adapted.py` + Mac官方实样 | **70/70，exit0** | 原228词、确认抄题34词、自写194词；三种连接符半词均拒绝；迁移5表6行，两次启动保留旧字段 |
| 原 `.14` `paragraph_probe.py` + Mac历史回答/样本 | **70/70，exit0** | 两份旧回答各9段保留，原分数5.5/5.0不变；30篇文本输入的评价消息兼容；实际JS渲染与复制事件通过 |
| 独立 `token_migration_probe.py` | **22/22，exit0** | 2592候选、313接受、2279拒绝、294双片段；半词、重复扣词、意外异常均0；三种完整词151→150；`.14` schema 5表6行连续迁移两次保持 |
| 原 `vision_budget_probe.py` | **139/139，exit0** | 合成最坏路径16文字/4识图限额仍正确，网络尝试0；没有读真实账本或恢复已关闭批次 |

数值证据分别为`confirmed-adapted.json`、`paragraph-original.json`、`token-migration.json`、`vision-budget.json`。`input-integrity.json`记录全部精确命令、解释器版本、执行耗时、源码SHA及7个私有输入的前后SHA。

## 精确复现命令

cwd：`/Users/zhouxin/Desktop/studytracker`，解释器项目`.venv` Python3.13.3。执行时清除继承的`IWA_*`、代理、`PYTHONPATH`和`PYTHONSTARTUP`，设`PYTHONDONTWRITEBYTECODE=1`；四个探针各自阻断网络并使用临时数据。

```bash
.venv/bin/python -B /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113/docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/confirmed_probe_adapted.py \
  --repo /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113 \
  --private-sample /Users/zhouxin/iwa-calibration/official_lowband_t2.jsonl \
  --output docs/design/iwa-prompt15-final-recheck-20261113/copy/confirmed-adapted.json

.venv/bin/python -B /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113/docs/design/iwa-prompt14-review-20261113/paragraph_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113 \
  --private-run /Users/zhouxin/iwa-compare-official-lowband-20261113/official-t2/run_data.json \
  --samples-dir /Users/zhouxin/iwa-calibration --baseline abf48d49 \
  --output docs/design/iwa-prompt15-final-recheck-20261113/copy/paragraph-original.json

.venv/bin/python -B docs/design/iwa-prompt15-recheck-20261113/copy/token_migration_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113 \
  --output docs/design/iwa-prompt15-final-recheck-20261113/copy/token-migration.json

.venv/bin/python -B /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113/docs/design/iwa-prompt14-review-20261113/vision_budget_probe.py \
  --source /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113 \
  --out docs/design/iwa-prompt15-final-recheck-20261113/copy/vision-budget.json
```

## 适用范围与交接

官方实样和历史回答只做离线重放，不是重新评分。30篇消息兼容构造未注入人工确认读数，不能用它证明所有已核图输入兼容。Node VM验证不等于真实浏览器验收；本专项不重复多locale全套，也不认证真实服务健康。

当前结果由本机报告交给主agent归并，规范交接和上传由主agent统一处理；本专项未自行commit/push/deploy。私有样本及历史回答继续仅本机保留。服务是否升级，以主报告最终状态为准，不能把本专项通过等同于本机已切换`.15`。用户“改正读数、确认后继续”的偏好保留，真实新批次仍需范围和上限授权；本专项没有开启新批次。
