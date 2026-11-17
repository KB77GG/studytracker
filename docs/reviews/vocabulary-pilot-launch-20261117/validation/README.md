# 最终双 Python 词汇回归

实施树 `/private/tmp/studytracker-vocabulary-error-pilot-20261117`，分支
`codex/vocabulary-error-pilot-20261117`，输入 HEAD `513c732f`。本次只跑本地合成测试，
没有生产访问、提交、推送、部署或学生启用。完整回归针对冻结后的本轮修改。

| 解释器 | 结果 | 时间 | 日志 |
| --- | --- | ---: | --- |
| Python 3.10 | 396/396 通过 | 53.078s | `final-python310.log` |
| Python 3.13 | 396/396 通过 | 45.300s | `final-python313.log` |

两进程退出码均为0。源文件开始/结束采样56文件SHA一致，见`source-at-start.json`及
`final-result.json`；CI和文档不在源码采样范围。此前测试参数失配已经纠正，最终完整运行
无跳过、失败或错误。没有把不同阶段的零散通过数拼成一次396通过。

修前393双版本通过后，独立事务复核发现题源重验遗漏；已补Word/Sense/实际代表书的
有限字段签名、eager refresh与错误sense关联隔离。三个新增负控先红后绿，再执行本次
396完整双版本。修前日志和源码摘要保存在`before-source-revalidation-*`，没有用其替代
修后验收。

## 范围与重现

旧21模块349项完整沿用上一阶段最终命令，包括原259项及策略core32、integration24、
teacher18、management16。特别保留`tests.test_vocabulary_mastery`和
`tests.test_dictation_review`，没有只复制CI中较短片段造成漏测。

新增5模块47项：graduation10、checkpoint_migration8、pilot_metrics11、pilot_selection3、
policy_performance15。总计26模块396项。该词汇范围不是全仓库的全部测试。

精确解释器、参数数组、环境和日志路径均在`commands.json`，从上述工作树执行。
解释器分别为 `/private/tmp/studytracker-stage2-py310/bin/python` 和
`/Users/zhouxin/Desktop/studytracker/.venv/bin/python`，设置`TZ=UTC`、
`PYTHONWARNINGS=ignore`，使用`-B -m unittest ... -q`。

## 性能限制与发布判断

本轮完整功能/结构回归通过不等于全部时钟目标通过。双Python必做矩阵及大词书首进
均<1秒，可选partial极端六并发最大1071/1144ms；详见
[`../performance/concurrency-results.md`](../performance/concurrency-results.md)。
主审已明确接受该限制作为6人小试点约束，保持不导旧积压、必做路径隔离；不能将完整C3
写成全通过。生产名单、迁移、发布与启用由主审处理并更新规范交接。

本目录结果目前只在本机工作树可见，本agent未commit/push/deploy。
