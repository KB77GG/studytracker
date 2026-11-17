# 试点评估口径与无身份只读导出

工作树 `/private/tmp/studytracker-vocabulary-error-pilot-20261117`，分支 `codex/vocabulary-error-pilot-20261117`，本阶段基线 `513c732f`。本子任务未操作生产、提交、推送或启用学生；主 agent 负责最终发布/试点与根交接。核心 source metadata/清零事件由 core agent 实现，本处只读消费。

## 精确定义

- **每错能力正式复测次数**：能力键为学生×词义×能力，当前 enrollment cohort 内所有新错能力都在分母，包含尚未复测的 0 次项；只数 `allocation.kind=error` 的正式首次 answer，按 allocation 去重。学习首答、样本题、可选题、订正及重放不计。即使同日后来新错误使旧冻结题不能推进独立成功，该题仍属于已承担的正式回答负担。提供总数、均值、P50/P90/最大值与未复测项数，跨再次入队累计，未把每个重入周期另当新能力。
- **清零至少 2 次比例**：分子为当前 cohort 中实际 `success_count>0 → 0` 的 `success_reset` 事件至少 2 次的能力数，分母为全部新错能力数。连续错误但进度一直为 0 不算；毕业后新错误开启新周期不算清零。拆分 `review_error / learning_error / sample_error / maintenance_error`，另给仅复测触发至少2次比例；未知 detail 仅列 other，不输出任意原文。
- **每学生/教师周暂停词数**：北京时间周一至周日，按学生×词义去重，同词不同能力暂停只算该生一个讲解词。教师范围沿用当前主教师与显式关联（去重），不是历史排课归属；一个词涉及两个学生算两份学生词工作量。CLI 仅输出每生/每教师分布与事件总数，教师网页只在现有授权范围展示学生本周数字。
- **保持率三类分开**：`graduation_d7`、`first_correct_d7`、`first_correct_d30`，按 checkpoint 明确来源划分。正式首次 sample answer 提供分子/分母；按期首答正确率只含目标自然日观察，延迟/提前观察单列，不混成按期保持率。
- **coverage 与未观察**：到期机会为分母；没有有效首答事件就未观察，不能当答对或答错。未选、缺席和材料不可用都影响 coverage；今日待测、已错过、尚未到期分别计数。即使 status=answered 但没有事件，也只报数据缺口，不推断成功。提供实际 anchor→作答天数与逾期天数分布。历史 pending 但日期已过按逻辑 missed 统计，无需为统计写库。
- **决策限制**：80%–85%仅为人工复盘参考；无自动改规则、自动降级、通知老师或重新分组行为。小样本和低 coverage 必须连同分母解释；第3/14天不能冒称观察到尚未到期的 D30。

## 实现与调用

共享纯读服务：`services/vocabulary_pilot_metrics.py`；网页在原授权周清单中加入累计指标、三类抽查表和每生本周暂停词数。OFF 原样返回，不查询指标表。

CLI 不导入 Flask/app/config、不读取姓名或答案，SQLite `mode=ro`、`query_only`、一致读事务、列白名单 authorizer、SQL进度检查10秒预算；最多500名 enrollment，每表100000条，超过预算明确失败，不输出不完整比率。读取完整快照后先关闭数据库连接，再做纯Python聚合，避免汇总计算延长生产读锁。默认只汇总已启用且已到 starts_at 的 enrollment；可显式 `--students` 收窄。输出只有汇总，不含 ID、姓名、账号、词条或答案。

```sh
venv/bin/python scripts/evaluate_vocabulary_error_pilot.py --database /path/to/app.db --as-of 2026-11-20T06:00:00Z
# 若只评估选定 cohort，可加 --students <内部ID...>；ID只作输入，不回显。
```

## 验证

在上述 worktree：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_vocabulary_pilot_metrics tests.test_vocabulary_error_reports -v
/private/tmp/studytracker-stage2-py310/bin/python -m unittest tests.test_vocabulary_pilot_metrics tests.test_vocabulary_error_reports -v
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check services/vocabulary_pilot_metrics.py services/vocabulary_error_reporting.py scripts/evaluate_vocabulary_error_pilot.py tests/test_vocabulary_pilot_metrics.py tests/test_vocabulary_error_reports.py
```

结果：双版本各29/29（11指标/18教师）通过；ruff通过。覆盖 0→0 不误记清零、重放去重、不同来源/延迟/缺失事件不混、零分母为 null、重入后的历史 as-of、周词义去重、跨学生绑定与教师授权、无身份输出、拒绝写库与身份列读取、精确启用时刻边界。未进行浏览器视觉或生产导出；不重复启动本地监听。

新增/修改文件当前仅本机可见：共享指标服务、CLI、指标测试、教师 service/template/test 与本记录。核心模型、规划性能文件及迁移的并行改动归其他 agent，不从本子任务提交。
