# `.15` 续核：8884e9d9未更新，剩余P2仍可复现

用户转贴的 Claude 总结与上轮复验输入相同。本轮成功fetch功能分支后，远端仍为 `8884e9d904a66afea9124339cbbb07f9b36d38fe`；未发现后续修复。首次沙箱fetch因无法写FETCH_HEAD失败，按权限流程重试成功，不将缓存引用当成远端新核验。

## 本轮执行与结果

cwd：`/Users/zhouxin/Desktop/studytracker`。使用原探针，不修改预期；合成数据、临时库、fake模型、真实双worker及公共API，无直接DB修改，无真实调用。

```bash
git fetch origin claude/ielts-writing-ai-trial
git rev-parse origin/claude/ielts-writing-ai-trial

.venv/bin/python -B docs/design/iwa-prompt15-recheck-20261113/web/mixed_queue_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt15-recheck-20261113 \
  --old-repo /private/tmp/studytracker-iwa-prompt14-review-20261113 \
  --seed-probe /private/tmp/studytracker-iwa-prompt15-recheck-20261113/docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/web_gate_probe_adapted.py \
  --out docs/design/iwa-prompt15-recheck-20261113/followup/mixed-queue-evidence.json
```

结果 **15/20、exit1**。五个失败仍属同一P2：旧记录重新排队后confirm/skip应409而返回202，错误持久化核对状态；confirm还修改原读数。新评价`.15`，旧精修/改写`.14`的ID与结果未变，旧记录警告消失。仅证明读数与旧结果错配，不推断实际分数必然改变或真实用户受影响。

独立只读审查确认：`web.py:427`与`storage.py:357–367`只要求存在任意queued；正常重新生成在`storage.py:440–443`新增queued。作者`tests/test_image_check_20261113.py:561–582`及适配探针`:327–380`只覆盖直接确认旧完成记录，未覆盖重新排队。

## 状态、边界与下一步

- 主资料树 `/Users/zhouxin/Desktop/studytracker`，main@`6ded77d24586327ad94e151e172ae4811b4a2eed`，既有7modified/23untracked顶层入口保留。完整路径清单及其他5个已修改文件的SHA在`source-state-before.json`；本轮仅更新本报告README、两交接及新增本followup目录。
- 审阅树 `/private/tmp/studytracker-iwa-prompt15-recheck-20261113`，`codex/iwa-prompt15-recheck-20261113`@`8884e9d9`，95工具文件保持不变；`.14`运行源码树 `/private/tmp/studytracker-iwa-prompt14-review-20261113`，`codex/iwa-prompt14-review-20261113`@`cd82fc1b`，两源码树前后clean。本轮没有更新其他worktree；桌面资料树不包含功能分支产品。
- 未重跑完整套件、官方私有样本或真实浏览器；上一轮492Python+8Node、45/45、70/70等仍是上一轮结果，不能替代本P2验收。
- 本机试用不升级，沿用`.14`/vision none；未读取Key、真实私有配置/试用库，未备份迁移或重启，不声明本轮已认证live健康。保持用户“改正后确认继续”的偏好及closed账本；没有新付费授权/调用。
- 全部本轮结果仅本机未commit/push；未合并main，未部署生产后端/网页/数据库/外部服务，小程序未上传/提审/发布。旧交付ZIP未更新。
- 下一位先fetch核对是否有新提交；若仍8884e9d9则继续等待作者修复。新修复应让本探针20/20，并保持首次等待确认/skip/重启/正常再生成等路径通过；完成独立复验后才按已授权顺序升级本机试用，不自动发起真实批次。
