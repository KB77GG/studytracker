# 批次锁与中断续跑复验：通过

源码：`/private/tmp/studytracker-iwa-holdout-review-20261111`，分支 `codex/iwa-holdout-review-20261111`，HEAD `f5c3f51d603e69fe2600953f17720e33be5273e6`（业务 `45072df9`）。本轮仅复核批次锁、子进程结束记录、续跑与原持久预算的相邻行为；没有新增发现。产品工作树 clean，未改产品或交接。

## 结论与源码

- `batch.py:347–349` 用 `pass_fds=(self.lock_fd,)` 让执行请求的 realcheck 子进程继承同一把批次锁。`run_stage` 的锁位于 `:480–485`，关闭位于 `:532–533`。杀掉父进程之后，子进程继续持锁；第二批次退出码 2，没有新请求。
- `__main__.py:246–254` 在报告写完、计算最终退出码之后记录 `exit_status.json`。`batch.py:170–175` 只把退出码 0 且已有报告的运行视为可沿用。`:288–302` 核对数据指纹、补写 `.done` 并跳过，避免父进程未能标记时重跑整组。
- 子进程最终失败（退出码 4）不会被误当作已完成。已发生请求仍在账本中；原上限无法覆盖再次完整运行时，续跑在发请求前拒绝。
- 上一轮已修复的请求前持久预留、未知请求计数、正常双启动、失败率停机，作者探针再次全部通过。本轮未发现预算回归。

## 三组验证

### 1. 上一轮父进程探针原样复跑

原脚本未修改，结果写入本目录 `runner_original_parent_lock.json`：

| 项目 | 修复前 | 本轮 |
|---|---:|---:|
| 子进程存活时批次锁已释放 | true | false |
| 第二批次退出码 | 0 | 2 |
| 两个 realcheck 重叠执行 | true | false |
| dev/Pro 请求数 | 28 | 14 |
| 此探针结束时总请求 | 70 | 28 |

28 不是整批总数：旧探针只等待子进程完成，没有再次启动剩余组。整批续跑另由下面的独立正向探针验证。

### 2. 作者探针与新增真实进程测试

- `verify/batch_probe.py`：**5/5**，结果 `runner_claimed_batch.json`。子进程第 5 次请求被杀时账本计 5（1 次结果未知）；相同上限重跑 0 新增并拒绝；离线显式增上限后传输/账本均 61；正常双启动 `[0,2]`；非法 JSON 批次以 4 停止。
- `ParentKilledTest.test_a_run_outliving_its_batch_keeps_the_lock_and_is_not_repeated`：**1/1**，结果 `runner_claimed_process.json`。这是作者新增的真实进程测试，确认父进程被杀后锁持续，之后续跑总请求 56。
- `runner_author_checks.py` 仅给作者探针/测试加禁止网络连接的 audit hook、清除继承的 IWA 环境变量，保留原场景与断言。

### 3. 独立的完整生命周期探针

`runner_lifecycle_probe.py` 使用真实 batch/realcheck/ledger，只替换 FakeClient 传输等待点及失败回复；每个子进程禁止 socket 连接。四个外部组均由内置原创合成作文生成，正常全计划 56 请求、最坏上限 112。两种场景共 **20/20** 个正向断言通过，结果 `runner_lifecycle_probe.json`。

**子进程成功场景**：

1. Flash 完成 14 次，Pro 第 1 次进入替身传输后 SIGKILL 父进程。
2. 子进程保持锁，第二批次退出 2，新增 0 次。
3. 放开子进程后累计 28 次，子进程记录退出码 0；此时尚无 `.done`。
4. 以原来的 **112 上限**续跑，沿用 Pro 结果并补写 `.done`，只运行尚未完成的其他组。
5. 全批传输计数 / 账本均为 **56**，dev/Pro 仍为 **14**，没有归档成 incomplete，也没有重复执行。
6. 再次续跑退出 0，新增请求 **0**。

**子进程失败场景**：

1. 同样杀父，随后让 Pro 全部输出非法 JSON；子进程记退出码 **4**，累计 **42** 次，未写 `.done`。
2. 原 112 上限续跑，已有 42 + 剩余最坏 84 = 126，退出 **2**，新增 **0** 次。
3. 未沿用失败结果，也未发起后续组。账本与传输计数均为 42。

## 可复现命令

在 `/Users/zhouxin/Desktop/studytracker`：

```sh
.venv/bin/python docs/design/iwa-batch-recheck-20261111/runner_parent_lock_probe.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out docs/design/iwa-batch-recheck-20261112/runner_original_parent_lock.json
.venv/bin/python docs/design/iwa-batch-recheck-20261112/runner_author_checks.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-recheck-20261112/runner_claimed_batch.json --mode batch
.venv/bin/python docs/design/iwa-batch-recheck-20261112/runner_author_checks.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-recheck-20261112/runner_claimed_process.json --mode process
.venv/bin/python docs/design/iwa-batch-recheck-20261112/runner_lifecycle_probe.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out docs/design/iwa-batch-recheck-20261112/runner_lifecycle_probe.json
.venv/bin/python -m ruff check docs/design/iwa-batch-recheck-20261112/runner_author_checks.py docs/design/iwa-batch-recheck-20261112/runner_lifecycle_probe.py
.venv/bin/python -m black --check docs/design/iwa-batch-recheck-20261112/runner_author_checks.py docs/design/iwa-batch-recheck-20261112/runner_lifecycle_probe.py
```

这些调用全部是模型替身，未读取 Key、`.env` 或学生原稿。SIGKILL 仅作用于探针自身创建的批次父进程；结束时子进程均已释放锁。输出只有本机新增 `runner_*` 文件，未 commit/push/deploy。全套产品测试、其他审阅范围与交接由主审汇总，本文件不重复作结论。
