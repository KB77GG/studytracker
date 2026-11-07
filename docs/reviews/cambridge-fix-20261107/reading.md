# 阅读校正实施与验证 — 2026-11-07

工作树 `/private/tmp/studytracker-cambridge-fix-20261107`，分支 `codex/cambridge-explanations-fix-20261107`，基线 `40cd8225db1b0a5da188b1dd99d4521dc5853328`。本子任务开工时该树clean；随后主agent及听力/展示agent并行修改同树，各自文件归属不混写。旧资料树 `/Users/zhouxin/Desktop/studytracker` 的业务及题库未改，只读借用 `.venv`、raw源与前轮审计。

## 完成内容

- 恢复5篇 `pre-A` 导语：剑4T3P2、剑6T2P1、剑6T3P2、剑9T1P2、剑20T4P3。作为 `paragraphs` 首项、`label=pre-A`，现有A–Z段落、标签、正文逐字保持；7题直接依据重新出现在做题正文。
- 纠正3题解析与依据：剑4T3Q5恢复Sudan and India快递项目；剑7T4Q34恢复B unexpected及疲劳滞后依据；剑12T5Q29恢复ii课程标题双义与C段依据。移除这3题串到其他题的 `locating_words`，不保留误导同义词。
- 纠正3题引文转录：剑14T1Q34 `dissatisfaction`，剑9T2Q32 `encountered`及截断尾词，另经独立原文核对窄修剑9T2Q31 `fall`、`from`及多余尾词。前两题的同义词引用中同样错字同步纠正。所有新 `central_sentences` 均精确取自当前文章，`index/length/target_para` 与原文匹配。
- **保留全部2880题的评分键、可接受答案、ID、题号、题型、原题干、选项及所有未列校正字段。** 不重算历史成绩。

`data/cambridge_content_corrections/reading.json` 含9套、6个题目校正、5篇导语。manifest仅含教学内容和导语，不能改评分字段。主agent的共享 `apply_content_corrections` 同时供新导入与旧快照的展示副本使用；本子任务未改服务或模板。

`scripts/build_reading_test_practice.py` 一般性保留源 `pre-A`，组装完完整payload后调用共享helper，使未来重建不会覆盖这些已审定内容。受控manifest导语也让历史静态/专项快照无需访问私有raw即可恢复。将来更新审定内容时应同步manifest，不应只改发布JSON。

## 本子任务文件归属

- 修改：阅读构建器及9个阅读JSON，精确清单见 `reading_verification.json.changed_reading_files`。
- 新增：`data/cambridge_content_corrections/reading.json`；`tests/test_cambridge_reading_corrections.py`；本目录 `reading.md`、`reading_apply.py`、`reading_verify.py`、`reading_verification.json`。
- 没有修改主agent的共享helper、服务、模板、听力文件或规范两交接；主agent负责整合交接与发布状态。

## 精确验证

以下cwd均为本修复工作树：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_cambridge_reading_corrections -v
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-fix-20261107/reading_verify.py --raw /Users/zhouxin/Desktop/studytracker/data/idictation_reading/raw.json --output docs/reviews/cambridge-fix-20261107/reading_verification.json
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-fix-20261107/reading_apply.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check --target-version py310 scripts/build_reading_test_practice.py tests/test_cambridge_reading_corrections.py docs/reviews/cambridge-fix-20261107/reading_apply.py docs/reviews/cambridge-fix-20261107/reading_verify.py
git diff --check -- scripts/build_reading_test_practice.py static/reading_tests
```

结果：9项单测通过；72套源在内存重建后全部目标校正/导语一致；9个JSON实际有差异，全部2880题除明确白名单校正字段外与基线逐值一致，原A–Z正文未改。`reading_apply.py` 重跑 `changed=[]`，幂等；Ruff（生产Python3.10目标）和diff检查通过。未将全量raw重建写回题库，图片下载在验证中被mock为禁用，未触发网络或模型。

`reading_verify.py` 的raw路径仅用于本地复验；发布运行只依赖已提交的JSON/manifest，不要求上传原始快照。原始source SHA-256：`0487d669ad899761572d5361cf8dd992cd69d05d8763c5474db55e61a1f28b13`。

## 未验证及下一步

当前改动仅本机未提交，子任务没有commit/push/deploy、数据库写入或小程序操作。共享helper、旧专项/模考、网页布局和导语隐藏标签的集成验收由主agent/展示agent执行，不能把本9项单测当成浏览器验收。尚未逐题审定全库语义；本轮未修76条已有Web保护的数据判断选项残留，也未宣称其是现行控件故障。下一步主agent运行整合回归和独立交叉审阅，核对发布授权后决定提交部署。
