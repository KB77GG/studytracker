# A 缓存补丁独立复审（2026-11-17）

主审后续整合：原八项已提升至 `tests/test_vocabulary_cache_lifecycle.py` 并纳入词汇 CI。正式路径在两解释器各8项通过；`negative_controls.py` 已从正式模块加载并按当前 `set(users)` 代码匹配，三项负对照再次全部检出。准确运行命令、最终日志与六文件SHA见 `../cache/README.md`。原本文件以下结果保留为独立审阅时记录。


结论：当前候选没有发现阻止发布的缓存隔离或事务正确性问题。原提案新增的永久 `user_versions` 元数据增长问题已由实施者修为仅保留在途用户，并通过独立并发测试及负对照。此结论只覆盖 A；生产健康、B1 取数、CI 和部署由主审另行核对。

工作树 `/private/tmp/studytracker-vocabulary-cache-policy-20261117`，分支 `codex/vocabulary-cache-policy-audit-20261117`，复审基线 `d67e147b`。开工 clean，复审时另一 agent 应用了 A 的两个产品文件和两个测试文件。本子任务只新增本目录，未覆盖其他文件，没有访问生产、commit、push、部署或改规范交接；主审负责统一写入 `docs/CODEX_HANDOFF.md` 和 `docs/WORKLOG.md`。本目录是否已同步，以主审最终交接和 Git 状态为准。

## 代码核对

- `BULK_USERS_OPTION` 在产品中只有一处使用：`_apply_review_item_state` 的 Query.update。WHERE 同时限定 `id=item.id`、`student_id=user.id`、`state_applied=False`，仅更新 `state_applied`；声明 `(user.id,)` 与语句实际作用域一致，不接收客户端给定的失效范围。
- 学生表未提供或提供空 scope 时仍全局失效。词库表先于学生表分支处理，即使带用户 scope 仍全局失效。选项是内部可信契约，不会自动证明任意未来调用者的 SQL WHERE；以后新增使用点须重新检查作用域。
- ORM before-flush、批量语句前、外层事务结束均保留原失效路径；外层 commit 或 rollback 后再次清除，嵌套事务结束不提前解除未提交状态。请求只读与显示缓存的旧隔离规则未改。
- 每用户版本只负责阻止该用户加载中的旧结果发布；全局 epoch 保护词库变化。原提案会永久保存所有曾写过的用户（即使没有缓存），已改成只维护有在途 loader 的用户。最后一个同用户 loader 退出才能删除版本；同用户不同日期/引擎 key 并发时不能过早清除。
- 进程内快照仍有 128 条/100,000 词义 ID 上限；版本元数据不再随历史活动用户数累积。外部进程或 raw SQL 写入仍靠 30 秒 TTL，精确冷计数仍全量。生产单 worker/gthread 设计没有变化。

## 独立验证

`test_cache_independent.py` 使用真实线程协调，以及临时合成 SQLite 事务；没有使用生产学生、词条或答案。8 项测试：

1. 其他用户在本用户加载期间写入，结果仍能发布并被下一次读取命中。
2. 同用户跨日期/数据库两个 loader 在途，首个退出不允许第二个失效前的结果发布。
3. 全局失效清空每用户版本后，旧 loader 不因版本回到零而发布。
4. 10,000 个无在途加载用户失效后，版本元数据仍为空。
5. 有明确学生范围的批量 DELETE 回滚，只清该生。
6. 有范围的嵌套 UPDATE 完成后，外层结束前读取始终绕过缓存；外层回滚不影响另一生的已缓存结果。
7. 词库批量写即使带学生选项仍清除双方。
8. 空学生范围保守全局失效。

最终结果：Python 3.10.20 **8/8，0.272 秒**；Python 3.13.3 **8/8，0.224 秒**。这 8 项是独立补充，不是计划的 251 项的一部分。现有缓存/对抗断言没有修改；完整产品回归由实施者另跑。

```sh
PYTHONPATH=. PYTHONWARNINGS=ignore TZ=UTC /private/tmp/studytracker-stage2-py310/bin/python -B docs/reviews/vocabulary-cache-policy-20261117/independent/test_cache_independent.py
PYTHONPATH=. PYTHONWARNINGS=ignore TZ=UTC /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/vocabulary-cache-policy-20261117/independent/test_cache_independent.py
PYTHONPATH=. PYTHONWARNINGS=ignore TZ=UTC /private/tmp/studytracker-stage2-py310/bin/python -B docs/reviews/vocabulary-cache-policy-20261117/independent/negative_controls.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check docs/reviews/vocabulary-cache-policy-20261117/independent
```

负对照只在 Python 内存中替换方法，未改磁盘产品代码。三个故意回归均被测试检出，分别得到 1 次 assertion failure、0 error：提前删除同用户在途版本；忽略全局 epoch；对所有历史写者永久保存版本。避免仅验证测试能运行而未覆盖实际竞态。

本次不承诺真实多人使用时固定命中率或耗时；请求状态/loader 计数的压力探针和生产版本回读由主审/实施报告提供。
