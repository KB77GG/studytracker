# `.15` 网页门禁复验（0701bcf5 / 8884e9d9）

源码树：`/private/tmp/studytracker-iwa-prompt15-recheck-20261113`，分支 `codex/iwa-prompt15-recheck-20261113`，HEAD `8884e9d9`。旧 `.14` 树 `/private/tmp/studytracker-iwa-prompt14-review-20261113`，HEAD `cd82fc1b`。源码只读；报告在主资料树，不代表主树旧产品已有改动。没有操作服务、Key、真实配置或生产，未读取学生数据，0 真实调用。

## 原场景结果

作者 `verify/web_gate_probe_adapted.py` 与上一轮原探针已逐行比较：只对旧完成记录改成 `409 / 无核对记录 / 旧记录标识 / 结果和ID不变 / 0调用` 的7项正向断言，以及相应空值读取；其余38项正例未删改。

原样运行 **45/45、findings=[]、exit0**。包含新提交确认/改正、skip不发读数且无TA/总分、身份/CSRF、重启等待、并发一胜一拒、额度和原读数保留。

- 原P3关闭：非对象JSON与非字符串description四例均422，不再500。
- 原完全完成记录场景关闭：confirm 409，`unchecked_legacy=true`，原结果/ID/读数不变，0模型调用。
- 独立相邻探针另外验证了旧完成记录的skip也是409。

## 尚余一个P2：旧记录重新生成排队，会重新开放确认入口

**位置**：`tools/ielts_writing_ai/web.py:427` 仅以“存在任意queued生成”决定待核对；`storage.py:357–367` 的原子写入条件同样只要求任意queued。它们没有确认这是首次生成前的等待状态，也没有排除已经采用旧读数的历史结果。

**自然复现流程**（无直接写DB、未替换调度函数）：

1. 用真实 `.14` 源码、fake模型生成一份带图且三类结果均ready的记录；关闭后用新源码打开同一临时库。
2. 新源码正确地将它标旧记录，直接confirm/skip均409。
3. 提交另一篇普通Task2，用阻塞fake模型占住实际JobRunner的两个worker，模拟服务器正在处理别人的作文。
4. 在旧记录点击“重新生成评价”，正常API返回202，新评价attempt进入queued，旧精修和改写仍ready。
5. 此时API变成`awaiting_check=true`、`unchecked_legacy=false`。发送confirm（140改160）或skip，都返回**202**。
6. 放开两个worker后，新评价按`.15`完成；旧精修和改写的ID、结果原文和`.14`版本全部保留。confirm场景的题图描述已改为160，整份记录的旧读数警告消失，但两个旧结果没有使用改正读数。

`mixed_queue_probe.py` 使用公共API、真实2-worker线程池和临时旧库，**15/20、exit1**：5个失败断言都属于此一问题，分别是confirm本应409/原读数不应改变/不应存核对记录，以及skip本应409/不应存核对记录。证据在`mixed-queue-evidence.json`。

**影响与限制**：一般已有带图记录升级后可通过正常重生成动作触发；当前试用库若没有旧作文则没有存量影响。未证明评分数值一定改变，只证明确认后的读数与未重新生成的旧结果错误配对。没有新增模型调用越限的发现。

**建议**：用持久的首次核对状态或生成历史来区分旧记录，不能让“重新生成排队”把旧记录转回首次等待；同一约束需用于页面判定和原子写库。按已选产品约定，旧记录应持续提示重新提交，confirm/skip均409。至少核对没有任何曾经启动/完成的生成，而非只查一个queued。若将来支持修改已有读数，需按生成版本保存对应关系，不可只改submission级标签。

## 精确命令

在 `/Users/zhouxin/Desktop/studytracker`：

```bash
.venv/bin/python -B /private/tmp/studytracker-iwa-prompt15-recheck-20261113/docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/web_gate_probe_adapted.py \
  --repo /private/tmp/studytracker-iwa-prompt15-recheck-20261113 \
  --old-repo /private/tmp/studytracker-iwa-prompt14-review-20261113 \
  --out docs/design/iwa-prompt15-recheck-20261113/web/author-adapted-evidence.json

.venv/bin/python -B docs/design/iwa-prompt15-recheck-20261113/web/mixed_queue_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt15-recheck-20261113 \
  --old-repo /private/tmp/studytracker-iwa-prompt14-review-20261113 \
  --seed-probe /private/tmp/studytracker-iwa-prompt15-recheck-20261113/docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/web_gate_probe_adapted.py \
  --out docs/design/iwa-prompt15-recheck-20261113/web/mixed-queue-evidence.json

.venv/bin/python -m ruff check docs/design/iwa-prompt15-recheck-20261113/web/mixed_queue_probe.py
.venv/bin/python -m black --check docs/design/iwa-prompt15-recheck-20261113/web/mixed_queue_probe.py
```

第一条45/45通过；第二条当前15/20、exit1；静态检查通过。未运行浏览器或真实识图。所有本轮报告/探针仅本机，未commit/push/deploy；交接由主审归并，旧报告未修改。
