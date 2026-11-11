# realcheck-batch 执行器复验

基线：`/private/tmp/studytracker-iwa-holdout-review-20261111`，`codex/iwa-holdout-review-20261111`，HEAD `d84c412a8513a049d4b3dfc6e6f29a170f741236`，业务 `50d557fd`。只读产品，输出限于本目录 `runner_*` 文件。未读取真实 Key、试用配置、学生或机构正文，未调用网络/真实模型。

## 原预算问题已关闭，正常失败停机也通过

原样重跑作者提供的 `verify/batch_probe.py`，五项检查全部通过，原始结果在 `runner_claimed_probe.json`：

- 子进程在第5次替身请求中被杀，账本保留5次，其中1次结果未知；同上限重跑拒绝、0次新增请求。
- 离线测试明确增加上限后续跑，传输计数与账本都为61，上限保持有效。此加额度只发生在合成探针，不是付费授权操作。
- 两个正常存活批次同时启动，一个成功、另一个exit2；总替身请求56，没有重复启动。
- 全部评价返回非法JSON，在第一个模型/组以exit4停止，未写`.done`，没有继续后续模型/组。
- 旧bash启动器已删，新Python输出可严格按UTF-8读取，原中文紧邻变量的编码问题不再适用。

代码核对：`realcheck.py:106–119` 在调用传输前向账本预留；`ledger.py:195–224` 在文件排他锁内统计/检查/追加，`:160–162` fsync；未完成预留计为已用。不是仅在整组结束时计数。因此下面的新问题**没有重新突破总请求上限**。

## 剩余 P2：杀掉批次父进程，仍运行的子进程不持有批次锁

位置：`batch.py:377–380` 仅批次父进程持有 `.batch.lock`；`:288` 用 `subprocess.run` 启动真实执行的 realcheck 子进程，没有传递该文件描述符（默认 close_fds）。父进程被SIGKILL时内核释放锁，正在请求中的子进程仍继续。

独立合成集成探针 `runner_parent_lock_probe.py` 保留完整 batch/realcheck/ledger，仅在 FakeClient 传输处设等待点：

1. 正常计划最坏112次，使用**相同的112上限**，不人为加预算。
2. dev/Flash正常完成14次。dev/Pro第一请求预留并进入替身时，杀掉批次父进程，保留realcheck子进程。
3. 确认子进程仍活着，但另一个进程已经能取到 `.batch.lock`。
4. 重跑相同命令。已有15次、剩余最坏84次，99≤112，所以预算检查合理通过；但是它同时启动了第二个dev/Pro子进程。
5. 放开等待，两份dev/Pro同时完成并写同一个结果目录；第二批次最终exit0。

实测结果（`runner_parent_lock_probe.json`）：

| 项目 | 结果 |
|---|---:|
| 首个批次父进程退出 | -9 |
| 首个realcheck子进程仍存活 | true |
| 子进程存活期间批次锁已释放 | true |
| 第二个realcheck与首个重叠 | true |
| 正常计划替身调用 | 56 |
| 实际替身调用 / 账本预留 | 70 / 70 |
| dev/Pro调用（原计划14） | 28 |
| 总量≤112 | true |
| 结束后遗留子进程 | false |

影响是同一模型/组被并行重复执行、额外费用、同路径结果互相覆盖；不是突破总账本上限。正常父进程存活时的双启动测试覆盖不到这个生命周期边界。

建议让真实执行中的realcheck子进程继承并持有同一批次锁（例如显式传递锁fd），直到其退出；或者以能可靠等待所有子进程结束的方式统一生命周期。验证必须杀父进程而非只杀child，并确认第二次批次在child仍活着时拒绝。单靠“Ledger已经限额”不能替代“一次只运行一个批次”的约定。

## 命令与范围

从 `/Users/zhouxin/Desktop/studytracker` 运行：

```sh
.venv/bin/python /private/tmp/studytracker-iwa-holdout-review-20261111/docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/batch_probe.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out docs/design/iwa-batch-recheck-20261111/runner_claimed_probe.json
.venv/bin/python docs/design/iwa-batch-recheck-20261111/runner_parent_lock_probe.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out docs/design/iwa-batch-recheck-20261111/runner_parent_lock_probe.json
```

父进程边界探针显式禁止socket连接，只用自身临时目录和内置合成作文，kill仅针对探针自己创建的batch父进程。exit0表示探针完成，具体行为看JSON，不能当成待测产品通过。数据/识图来源冻结与汇总/盲评由另两位评审覆盖；本文件不重复判断。本轮脚本/报告仅本机，未commit/push/deploy，产品工作树保持clean。
