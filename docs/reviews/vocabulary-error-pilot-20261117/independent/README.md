# 独立边界审查

2026-11-17；工作树 `/private/tmp/studytracker-vocabulary-error-pilot-20261117`，分支 `codex/vocabulary-error-pilot-20261117`，基线 `f414a126`。未操作生产、提交、推送或固定前端。本审查只读检查 core/adapter/学习 hooks；唯一产品修改是经主 agent 指示修复原教师报告两项遗漏，见 `../teacher/README.md`。

## 发现与关闭

1. **没有可出题项时跳过过载清理。** 全部 22 项都已逾期超过 7 天时，计划返回空批，但旧 adapter 不执行转低频；这些项还会被可选池排除。与 implementation agent 同时发现；core 新增锁后重算的 `refresh_day`，adapter 空批调用。独立测试确认 22 项和对应事件持久化、可选池可领取。
2. **旧冻结题不能为当天刚出现的新错误记隔日成功。** 学生先领题，再在进行中的学习任务犯同能力错误，再回答已领题。owner 增加未来 due 检查；独立测试确认保留作答与完成额度，队列 success_count 仍为 0，次日到期。
3. **过期的“题目不可用”计划会降级后来新错误。** 独立第 7 例在修复前明确失败（预期 active，实际 maintenance）。core 给 deferral 增加 version 检查；修复后相同用例在双版本通过。该检查也保留已冻结坏题跳过与后来的新周期之间的边界。
4. **教师报告漏掉仅 checkpoint 的材料异常，以及暂停期文案写死。** 两项先失败再修复：queue/checkpoint 外连接并分别校验学生归属；暂停天数跟随配置。教师套件双版本各 18/18 通过。

当前独立审查没有未关闭的高风险发现。验证不是生产可用性保证；本轮未启用任何真实学生。

## 验证

`test_policy_edges.py` 使用原有旧协议 fixture 的合成数据库，不继承本轮 owner 的测试断言。7 项覆盖上述前三项、错过 D7 后不伪装成次日抽查、真实 HTTP 旧客户端缺少 correction 字段仍能错题结算、跨学生 session 读/答拒绝、5000 条旧 mastery 不被 mandatory summary/preflight 查询或导入。

另读审并独立重跑 owner 的两项文件数据库/双连接并发测试：同一首答只推进一次、并发申请不能分配 30 个名额。全局 OFF 不访问新表、首答/订正分离与暂停跨日等由 owner 核心和集成套件覆盖，教师 OFF 路径另有零 SQL 实测。

双版本均通过：独立 7/7、文件数据库并发 2/2。精确命令（工作目录为上述 worktree）：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest discover -s docs/reviews/vocabulary-error-pilot-20261117/independent -p 'test_*.py' -v
/private/tmp/studytracker-stage2-py310/bin/python -m unittest discover -s docs/reviews/vocabulary-error-pilot-20261117/independent -p 'test_*.py' -v
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_vocabulary_error_queue.VocabularyErrorPolicyConcurrencyTest -v
/private/tmp/studytracker-stage2-py310/bin/python -m unittest tests.test_vocabulary_error_queue.VocabularyErrorPolicyConcurrencyTest -v
PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/vocabulary-error-pilot-20261117/independent/probe_mandatory_scale.py > docs/reviews/vocabulary-error-pilot-20261117/independent/scale-py313.json
PYTHONPATH=. /private/tmp/studytracker-stage2-py310/bin/python docs/reviews/vocabulary-error-pilot-20261117/independent/probe_mandatory_scale.py > docs/reviews/vocabulary-error-pilot-20261117/independent/scale-py310.json
```

## 规模探针

合成内存 SQLite；同时增加旧 mastery 池和显式低频 queue，必做队列为空，每档运行 summary 25 次。结果原文见 `scale-py313.json` / `scale-py310.json`。

| 每个池新增行数 | Python 3.13 中位耗时 | Python 3.10 中位耗时 | 每次 SQL | 旧 mastery 查询 |
| --- | --- | --- | --- | --- |
| 0 | 1.145 ms | 1.648 ms | 8 | 0 |
| 5000 | 1.262 ms | 1.554 ms | 8 | 0 |
| 20000 | 1.525 ms | 1.979 ms | 8 | 0 |

结论限于该入口：旧低频池不被逐条扫描，显式 maintenance 行没有逐条出题。`maintenance_count` 仍做带索引 COUNT，不能宣称数学意义上与行数完全无关；本探针显示 20000 行的增量远小于此前逐词判题扫描。时间为本机、合成、并行运行两个解释器时的量级，不能换算生产 SLA；可选领取自身及大量 active 新队列不是本探针测量对象。

所有新测试、探针和结果目前仅在本机共享工作树。根级 `CODEX_HANDOFF.md` / `WORKLOG.md` 由主 agent 汇总，不在此子任务中覆盖。
