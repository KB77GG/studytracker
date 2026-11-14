# “忘了”后端排程与答案返回核查

核查基线：`/private/tmp/studytracker-vocabulary-forgot-feedback-20261114`，
`codex/vocabulary-forgot-feedback-20261114@75ff855d381e4f872a466b7038177382452cbe5b`。
本专项只新增本目录的探针、输出与说明，没有产品代码改动、生产访问或真实学生资料写入。

## 结论与源码位置

- 学习接口 `services/vocabulary_group_learning.py:1646` 的 `_serialize_answer()` 对忘记同样返回 `revealed_answer`；自主复习 `services/vocabulary_autonomous_review.py:1193` 的 `_answer_result()` 也返回答案、忘记类型与延期标记。
- `services/vocabulary_group_learning.py:1692` 将显式 `forgot` 作为错误记录，保留首答。`:894` 的 `_set_retry_questions()` 将首次错误放入组末重练；综合模式存在同词间隔保护，间隔不足的题会延期复习。`:879` 的 `_defer_forgotten_retry()` 保留再次忘记的延期状态，确保该维度不晚于下一天到期。
- `services/vocabulary_mastery.py:829` 的 `_apply_dimension_answer()` 在错误时将该维度掌握阶段归零，并设为 `now + timedelta(days=1)`。这是**作答后24小时**，不是“下一自然日零点”。`services/vocabulary_autonomous_review.py:419` 的到期筛选使用实际到期时间。
- 自主复习 `services/vocabulary_autonomous_review.py:1524` 持久化忘记类型、设置延期并调用掌握度更新。学习中最后一次忘记的排程在答题请求保存时已经生效，**不依赖随后调用 finalize**；下述探针专门覆盖未结算情况。
- 本机发布源 `miniprogram/pages/student/vocabulary-learning/index.js:819` 在忘记成功后直接 `fetchQueue()`；`vocabulary-review/index.js:843` 刚显示结果即 `nextItem()`。发布源绝对路径为 `/Users/zhouxin/Desktop/studytracker-release/miniprogram`。这两处可以解释“正确答案没显示就跳走”；属于前端行为，不能据此断言后端永久丢词。该定位基于修复前发布源，后续候选行号可能变化。

## 可复现验证

在上述实现树根目录执行：

```bash
TZ=UTC PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m pytest -q --disable-warnings --tb=short -p no:cacheprovider tests/test_vocabulary_group_learning.py tests/test_vocabulary_autonomous_review.py tests/test_vocabulary_group_learning_api.py tests/test_vocabulary_mastery.py tests/test_vocabulary_numeric_review.py
```

结果：**117 passed、2 subtests passed，10.57秒**。输出有18877条现有依赖弃用警告，未将其描述为零警告。
其中 `test_vocabulary_autonomous_review.py:2057` 覆盖六种复习题型忘记后在下一次到期出现，`:473` 覆盖延期重练再次忘记，组学习测试覆盖首次与组末忘记、幂等和错误首答分数保护。

```bash
TZ=UTC PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -W ignore docs/reviews/vocabulary-forgot-feedback-20261114/backend_probe.py --output docs/reviews/vocabulary-forgot-feedback-20261114/backend_probe.json
```

探针使用既有 unittest 夹具的 `sqlite:///:memory:`，每次回答后显式提交，在最后回答后过期 ORM 缓存再读排程。
reading/listening/writing/comprehensive 四目标各三词，每目标分别执行“结算”和“停在最后一题反馈、未结算”两种场景，共 **8/8通过**：

- 首次与组末全部点忘记，每次响应都含正确答案，全部作为错误，均不要求即时抄写纠正。
- 四目标每场景分别作答18/12/18/12次，其中组末重练9/6/9/6次，已结算场景准确率均为0。
- 未结算场景 `VocabularyTaskSettlement` 数量仍为0，但三个词的相关维度到期时间已持久化。
- 作答当天及24小时前1秒都没有到期词；恰好24小时后，无论是否结算，三个词均进入“今日复习”。输出只包含合成统计，没有 token、答案明细或真实身份。

脚本目标 Ruff 与 Black 检查通过。以上是服务层合成验证和既有API回归，不代表已核对用户所述学生的真实请求、微信包版本、真机页面或生产排程；未访问生产数据库，不推断该学生实际历史。根任务负责前端修复验证与两份交接更新。
