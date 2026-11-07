# 题目 ID / 显示题号串题独立复核

- 工作树：`/private/tmp/studytracker-cambridge-fix-20261107`，分支 `codex/cambridge-explanations-fix-20261107`。
- 生产基线：`40cd8225db1b0a5da188b1dd99d4521dc5853328`。静态数据直接从该 Git 对象读取；同时断言当前 144 文件的题目 ID、number 和顺序与基线一致。
- 本报告只读审计业务文件，只新增本目录复现脚本与结果。

## 结论

| 科目 | 套数 / 题数 | 旧 helper 真实误查 | 涉及套数 | 新 helper 误查 |
| --- | --- | --- | --- | --- |
| 听力 | 72 / 2880 | 21 题，其中 12 题跨 Section | 1（剑18 Test1） | 0 |
| 阅读 | 72 / 2880 | 0 | 0 | 0 |

两科均没有缺失 ID 或套内重复 ID。听力共 30 题的 ID 数值与另一题 number 相同：剑18 Test1 的 21 题会被更早出现的其他题截获；剑18 Test2 的 Q1–9（ID32–40）先命中自身，因而旧 helper 没有误查。不能把所有数值相同都算成实际串题。

旧听力 `questionForId` 在同一次 `.find` 中允许 `id === lookup` **或** `number === lookup`；而 UI 的 `data-id`、review-card key 和导航传入的是题目 ID。由此，先出现的另一题显示题号会截获真实 ID，影响 `updateReviewCards` 的解析/证据卡替换、`openReviewCard` 的选题/Section 切换和 `playQuestionAudio` 的定位选择。这个数量是可复现的查找错误范围，不代表这些题的标准答案或服务器判分有误，也不统计用户实际触发次数。

新 helper 使用 `question.id || question.number` 作为每题唯一查找键；有 ID 时不再同时拿显示题号参与匹配。阅读 `questionById` 在生产基线起就只按 `question.id` 查找，本轮该 helper 未发生逻辑修改。

## 剑18 Test1 逐题错配

| 应查题号 | 传入实际 ID | 旧 helper 返回题号 | 返回题目的 ID | 跨 Section |
| --- | --- | --- | --- | --- |
| Q14 | 11 | Q11 | 1851 | 否 |
| Q15 | 12 | Q12 | 1852 | 否 |
| Q16 | 13 | Q13 | 1853 | 否 |
| Q17 | 14 | Q14 | 11 | 否 |
| Q18 | 15 | Q15 | 12 | 否 |
| Q19 | 16 | Q16 | 13 | 否 |
| Q20 | 17 | Q17 | 14 | 否 |
| Q27 | 18 | Q18 | 15 | 是 |
| Q28 | 19 | Q19 | 16 | 是 |
| Q29 | 20 | Q20 | 17 | 是 |
| Q30 | 21 | Q21 | 1854 | 否 |
| Q31 | 22 | Q22 | 1855 | 是 |
| Q32 | 23 | Q23 | 1856 | 是 |
| Q33 | 24 | Q24 | 1857 | 是 |
| Q34 | 25 | Q25 | 1858 | 是 |
| Q35 | 26 | Q26 | 1859 | 是 |
| Q36 | 27 | Q27 | 18 | 是 |
| Q37 | 28 | Q28 | 19 | 是 |
| Q38 | 29 | Q29 | 20 | 是 |
| Q39 | 30 | Q30 | 21 | 是 |
| Q40 | 31 | Q31 | 22 | 否 |

典型双选题 Q14（ID11）旧返回 Q11（ID1851），Q15（ID12）旧返回 Q12（ID1852）；Q29（ID20）旧返回 Q20（ID17），Q30（ID21）旧返回 Q21（ID1854）。新 helper 对以上四题及全部 5760 题的真实 ID 都返回正确题目。

## 方法与验证

`question-id-collisions.py` 从生产和当前模板提取实际 `allQuestions` 及 `questionForId` / `questionById` 函数，放入 Node `vm` 执行；按 UI 生成键的方式逐题调用，再对照预期 ID 和 number。JSON 保存旧/新函数源码、当前 helper SHA256、所有错配、潜在数值碰撞与每套结果。此方法没有重新实现或模拟 `.find` 判断逻辑。

复现命令（在上述工作树执行）：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-fix-20261107/question-id-collisions.py
node --test tests/test_listening_review_audio.js
```

第一个命令退出 0，得到上表统计；第二个命令 11/11 通过（含真实剑18全部40题与两组双选卡片）。当前模板新增的真实剑18数据测试还逐题验证 `openReviewCard` 的题目和 Section，并对双选题卡片替换进行校验。

范围：剑桥4–21整套听力与阅读静态题库和当前 Web 整套模板。未对历史数据库专项快照或其他书籍的所有 ID 分布作同样遍历；此报告也不能替代 5760 题解析内容的逐题人工语义验收。没有修改答案、题号、ID 或评分逻辑。
