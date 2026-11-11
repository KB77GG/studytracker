# 数据来源与请求条件复核

基线：`/private/tmp/studytracker-iwa-holdout-review-20261111`，`76ab483fe0c944c1c7c0164cdf53d2bca9f1bbd7`。只读产品；所有新增请求测试用原创合成文字和 FakeClient，禁用 socket.connect/getaddrinfo，没有 Key、私有作文或真实请求。

## 已通过

- 旧 `percentage_probe.py` 原样重跑 **33/33**：重复百分比的零差、5.125 与 0.004 精确差均保留，错误的 5.12 与零差被拒。两项旧 P2 均 `reproduced=false`。原真实合成 Task 1 的 5 个百分点建议与复制文本保留，普通 5% 规则未放宽。
- `source_probe.py` **14/14**（其中最后一项验证下面的失败边界确实复现）。评分、老师名称、老师评语、批注、分组、标称档位和 conditions 加上唯一标记后，实际模型 messages/context 都不含这些标记；和无标签样本的 messages SHA 完全相同。评委标签仍保留在本地结果供复核。
- 评价的重复运行和模型切换保持 messages SHA 一致；high / 32000 / 300 / JSON mode / retries=0 一致。重复有独立 id 和独立评价调用，不是复用第一次评分。
- 题图首轮识别成功时，只读一次；本模型重复和第二个模型共享相同 description，Pro 不再调用识图，评价 messages SHA 一致，对照成功。
- 新对照记录预算、超时、源码指纹等差异，但差异为 warning 而非拒绝。执行层仍须锁同一源码和配置，不能只以生成了 compare.md 判断条件完全相同。

## P2：首次识图不可用时，重复调用并破坏共享条件

位置：`tools/ielts_writing_ai/realcheck.py:343`、`:349`、`:362`；`__main__.py:151`。

缓存仅存成功的读图结果。一个图片样本运行两次：第一次不可读时没有缓存，第二次会再次调用识图。如果第二次成功，导出的共享文件只保留成功结果，于是：

| 模型 | 第一次评价看到的图 | 第二次评价看到的图 |
|---|---|---|
| Flash | 不可用 | 成功结果 |
| Pro（沿用导出） | 成功结果 | 成功结果 |

已实际复现：一个图调用识图两次，四次评价全部执行后 compare 才拒绝首个样本。CLI 按唯一图片数计算“最多识图次数”，与这个路径不符。两图都遇到失败时可分别重读；因此第二阶段“最多 2 次识图”未被独立守住，虽然总的 `--max-calls` 仍能阻止整轮无限调用。

建议：在两个文字模型之前，每个图只预读一次并冻结成功/失败状态；结果不够用时停止第二阶段，或按事先约定让两模型都使用同一缺图状态。不要只在第二个模型全部跑完后才发现输入不同。此问题影响第二阶段；第一阶段不发图。

## 复现命令

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B \
  /Users/zhouxin/Desktop/studytracker/docs/design/iwa-holdout-execution-review-20261111/source_probe.py \
  --repo /private/tmp/studytracker-iwa-holdout-review-20261111 \
  --output /Users/zhouxin/Desktop/studytracker/docs/design/iwa-holdout-execution-review-20261111/source_probe.json
```

旧百分点探针在审阅树内执行：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B \
  docs/design/ielts-writing-ai-percentage-review-20261110/percentage_probe.py \
  --repo /private/tmp/studytracker-iwa-holdout-review-20261111 \
  --evidence docs/design/ielts-writing-ai-prompt12-high-20261109/shared-evidence/A \
  --output /Users/zhouxin/Desktop/studytracker/docs/design/iwa-holdout-execution-review-20261111/source_percentage.json
```

产物仅本机，未 commit/push/deploy；主交接由父任务统一更新，避免并发覆盖。

发布说明：以上是复核完成时的工作状态；本次报告与合成探针由主审一并同步功能分支，最终提交见 git log。私有数据与演示结果未提交。
