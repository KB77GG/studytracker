# 为什么11月15日开始反馈：版本对照

本轮仅历史源码读取和本机合成内存SQLite实验，无生产访问或业务修改。全部新文件仅本机，未commit/push/deploy；主审负责两交接增量。

## 已证实

- 每个无法直接出填空题的到期语境词，为资格计数调用完整选择题builder的路径，在`771d6c90`（2026-08-27）已经存在。不能说这个慢算法是11月14日才新增。
- `2e82331a`（2026-11-14 23:10:59 +08:00）课堂同义词扩展给`build_context_question`加入了整本候选的`is_synonym_word`过滤。普通词也需要逐项读取sense标记。前置资格判断另加一次同义词检查。变更见`synonym-change.patch`。
- 在相邻时间、同一Mac、相同1000词合成数据上，变更前后仍存在约6.5—7秒的旧瓶颈；新增过滤有可测额外成本，但不是从快速到慢的全部原因。

| 场景 | 11月14变更前 ms | 当前未修版 ms | 差值 |
| --- | ---: | ---: | ---: |
| 普通词义复习 | 35.480 | 35.105 | -0.375ms |
| 可直接出语境填空 | 174.276 | 181.279 | +7.003ms |
| 只能出语境选择题 | 6491.036 | 6973.848 | +482.812ms / +7.44% |
| 语境选择题，重复释义 | 6550.779 | 7015.008 | +464.229ms / +7.09% |

四场景的due count、复习名单和顺序、完整preflight响应、首20题公开题面/答案hash均相同，16项比较通过。SQL数量也相同：前两场景11次，后两场景12次。两版完整建题资格检查仍为1000次。单次连续运行数值不作为严格统计显著性结论，也不作为生产延迟承诺。

## 对突然出现的解释边界

能够确定：旧算法会随到期词量及词书大小加重，并在特定语境题路径尤其慢；11月14更新增加了一层全书过滤；10秒客户端期限把“稍慢”表现为“进不去”。这提供了“旧瓶颈在临界负载下越过超时线”的合理机制。

不能确定：这两位学生当天到底是到期词增长、题型构成变化、服务器并发、还是新增过滤的边际开销成为最后触发因素。本实验不含历史学生数据或生产CPU时间线，不能把“数据积累”当作已证实的唯一原因，也不能声称最近发布绝对无关。是否更早已有499，应由主审按脱敏日志时间线判断。

## 精确来源与命令

- 变更前提交：`75ff855d381e4f872a466b7038177382452cbe5b`（`2e82331a^`）。只导出94个根Python/services/基准文件到`/private/tmp/studytracker-entry-pre-synonym-20261116`，普通目录无Git元数据，不是worktree或发布源。
- 当前未修产品：`878209f4d180ed1a9702b44257044ed394afd731`；运行源码目录`/private/tmp/studytracker-exam-integrity-20261114`当前文档HEAD为`b85c4746`，相对878209f4仅文档更新。
- 同一基准脚本：`/private/tmp/studytracker-entry-backend-20261116/scripts/benchmark_vocabulary_entry.py`；脚本SHA存于`comparison.json`。四类基准都只使用synthetic SQLite内存数据库。

cwd `/Users/zhouxin/Desktop/studytracker`：

```sh
PYTHONWARNINGS=ignore .venv/bin/python -B /private/tmp/studytracker-entry-backend-20261116/scripts/benchmark_vocabulary_entry.py --repo /private/tmp/studytracker-entry-pre-synonym-20261116 --size 1000 --output docs/reviews/miniprogram-entry-20261116/onset-history/pre-synonym.json
PYTHONWARNINGS=ignore .venv/bin/python -B /private/tmp/studytracker-entry-backend-20261116/scripts/benchmark_vocabulary_entry.py --repo /private/tmp/studytracker-exam-integrity-20261114 --size 1000 --output docs/reviews/miniprogram-entry-20261116/onset-history/current-unfixed.json
git diff 2e82331a^ 2e82331a -- services/vocabulary_context.py services/vocabulary_autonomous_review.py services/vocabulary_synonyms.py
git blame 878209f4 -L 314,360 -- services/vocabulary_autonomous_review.py
```

只新增本报告目录；未改主树既有7M/23U、后台候选产品或固定小程序源。下一步是结合更早日志作出带证据强弱的原因说明，不为解释问题而回滚或再部署。

## 主审补充：历史线上日志

只读汇总保留的Nginx日志（2026-11-02起；11-16仅截至检查时刻），见上级`onset-daily-logs.json`与`audit_onset_logs.py`。词汇queue请求中断499：11-02为17/1058，11-09为81/834，11-13为2/879，11-14为59/1243（4.75%），11-15为174/905（19.23%）。这些是请求次数，不是学生人数；499也可能来自主动离页，不能把历史全部499认定为同一超时原因。昨日截图对应的一次499则已与10秒前端期限及随后后台200对齐。

这段日志的小程序版本均为105，至少11-02已有，不能归因为昨日才上线的新前端包。旧瓶颈+近期同义词增量+当日词量/题型/并发可能共同越过10秒阈值；缺历史个体工作量/生产profiling，最终触发因素仍未唯一归因。昨日截图17:12早于19:54冲刺、23:36诚信一期部署，不应把这两次晚间部署当作该截图发生的起因。原性能测试只覆盖meaning到期场景，这次已补context-choice-only规模回归。

精确只读命令（cwd主资料树）：
```sh
ssh root@47.110.45.193 'python3 -' < docs/reviews/miniprogram-entry-20261116/audit_onset_logs.py > docs/reviews/miniprogram-entry-20261116/onset-daily-logs.json
```
本轮新增来源解释/历史聚合，未新增业务修改、部署、生产DB写入或小程序发布。修复候选和固定源状态仍沿用上一轮。
