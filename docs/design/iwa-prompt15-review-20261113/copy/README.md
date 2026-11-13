# `.15` 抄题词边界与存储迁移独立复核

审阅工作树：`/private/tmp/studytracker-iwa-prompt15-review-20261113`，分支 `codex/iwa-prompt15-review-20261113`，HEAD `652450ca03efaa3ae794202368a2f42a88fca18a`。业务词边界修复 `89e8c7ce`，识图/迁移 `9339cdbc`，对照基线 `cd82fc1b`。报告与新增合成探针位于主资料树 `/Users/zhouxin/Desktop/studytracker` 的本目录；产品工作树未修改，收尾仍 clean。

**本专项未发现新的阻断问题。原确认片段拆词并重复扣词的 P2 已关闭。** 这只是程序边界、迁移和旧回答兼容性的离线结论，不证明识图准确、AI 评价判断正确或评分已校准。网页人工核图与实跑执行器另行复核。

## 验证结果

| 检查 | 结果 | 范围 |
| --- | --- | --- |
| 作者最小改编的 `confirmed_probe_adapted.py`，使用 Mac 真实官方 JSONL | 70/70 | 旧十个词边界失败全部消失；完整词正例、loader 拒绝半词、普通确认校验、网页不能注入确认标注、真实抄题 34/194、旧库字段保持 |
| 原 `paragraph_probe.py` 原样运行，使用真实历史两次回答 | 70/70 | 两次均保留9段、计数15=15、无超限；原分数5.5/5.0不变；34词抄题/194词自写；真实JS渲染函数和复制事件；30篇既有文本输入比较 |
| 本轮新增 `token_migration_probe.py` | 22/22 | 独立 token 区间/计数性质、151→150正例与 `.14` 数据库迁移 |

`confirmed_probe_adapted.py` 相比原探针的实质改动只有迁移检查：除了已存在的 `copied_spans`，要求新增 `image_check` 恰好出现一次、旧行仍为 NULL，去掉该新列之后逐表逐字段相等。没有删去原十项失败的正确预期。70 而非旧报告71，是原探针在已拒绝半词后不再执行“坏标注成功入库”的漏洞演示分支；不是少跑一项未解决的拒绝断言。

### 独立词区间性质检查

`essay.py:255–265` 用同一个 `WORD_RE` 检查 quote 起止是否位于计词 token 内部；`resolve_copied` 在293行调用它，仍保留唯一出现、不能跨段与区间互斥检查。完整 `don't`、`don’t`、`cost-effective` 各占1词，左右半词拒绝。

新增探针遍历12个完全合成文本的2592个唯一候选片段，包括多连字符、数字连接词、标点、非ASCII字符及CR/CRLF：313个接受、2279个拒绝；所有接受的片段都包含完整原始 token，计数等于其覆盖的 token 数。294组不相交的已接受片段，没有共享或重复扣同一个 token，没有意外异常。另经真实 `load_samples → _copied_spans → build_evaluate` 检查三种完整复合词：原151词、仅扣1词、实际消息保留150词，确认依据不进消息。这里只构造提示，没有请求模型。

### `.14` 已有库的迁移

以 `cd82fc1b` 的真实 `SCHEMA` 建合成SQLite，包含5表6行以及非空的确认抄题元数据、ready图读数、旧结果和额度。调用当前 `init_schema` 两次：只增加一个可空 `image_check` 列；旧列定义、旧行每个字段和外键均保持；原抄题元数据继续准确计1词。此处没有打开或迁移用户的实际试用库，也不测试进程重启时任务恢复语义。

### 真实样本和消息兼容性口径

官方两份历史模型回答仅做离线重放；未用 `.15` 重新问模型，因此5.5/5.0仍是旧回答的分数，不是新的评分验证。原稿/题目与当前本机输入匹配；当前官方JSONL与历史run、五份外部JSONL在复核前后哈希不变。

原 `paragraph_probe.py` 的30篇消息对照不注入 `image_check` 或新确认读数。当前本机这30篇在该构造下与真实 `.12` 模块输出逐字相等；**不能据此声称已核过“新确认题图只差一行”的路径**。这一路径由识图专项另行验证。UI检查是实际JS函数运行于Node VM/最小DOM，并非真实浏览器截图。

## 可复现命令

从主资料树执行，Python为本机项目venv（3.13.3）。三个探针都清除继承的 `IWA_*` 设置并禁止网络调用，不读取 `.env` 或Key。

```bash
.venv/bin/python -B /private/tmp/studytracker-iwa-prompt15-review-20261113/docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/confirmed_probe_adapted.py \
  --repo /private/tmp/studytracker-iwa-prompt15-review-20261113 \
  --private-sample /Users/zhouxin/iwa-calibration/official_lowband_t2.jsonl \
  --output docs/design/iwa-prompt15-review-20261113/copy/confirmed-adapted.json

.venv/bin/python -B /private/tmp/studytracker-iwa-prompt15-review-20261113/docs/design/iwa-prompt14-review-20261113/paragraph_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt15-review-20261113 \
  --private-run /Users/zhouxin/iwa-compare-official-lowband-20261113/official-t2/run_data.json \
  --samples-dir /Users/zhouxin/iwa-calibration --baseline abf48d49 \
  --output docs/design/iwa-prompt15-review-20261113/copy/paragraph-original.json

.venv/bin/python -B docs/design/iwa-prompt15-review-20261113/copy/token_migration_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt15-review-20261113 \
  --output docs/design/iwa-prompt15-review-20261113/copy/token-migration.json

.venv/bin/python -m ruff check docs/design/iwa-prompt15-review-20261113/copy/token_migration_probe.py
.venv/bin/python -m black --check docs/design/iwa-prompt15-review-20261113/copy/token_migration_probe.py
```

本目录只有合成代码、计数、哈希、评分数字和布尔结论，未导出官方/学生原稿、引文、模型回答、reasoning或凭据。`token-migration.json`记录四个关键源码文件SHA；真实原文与run SHA见其余两份JSON。

本专项未改产品、实际数据库、配置或服务，0真实调用，未commit/push/deploy；未重跑全套Python、多locale或Python3.10。规范两交接由主agent合并，本agent不并发修改。
