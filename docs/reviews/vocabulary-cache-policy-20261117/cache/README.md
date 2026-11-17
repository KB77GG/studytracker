# 缓存补丁实施与验证（2026-11-17）

本子任务仅操作 `/private/tmp/studytracker-vocabulary-cache-policy-20261117`，分支 `codex/vocabulary-cache-policy-audit-20261117`，基线 `d67e147b`（继承审计文档，产品与 main `45bc3a01` 一致）。开工工作树 clean。没有访问生产、commit、push、部署、改教学规则、数据库结构或小程序源码；这些发布事实由主审在总报告更新。主交接与 WORKLOG 由主审统一维护。

## 实施范围与审查

应用计划 A 的四文件补丁：

- `services/vocabulary_due_cache.py`：全局词库版本与学生在途版本分离；学生表 bulk DML 可声明所涉学生，未声明或空声明仍失效全部，词库 DML 无条件失效全部。
- `services/vocabulary_autonomous_review.py`：仅给 `_apply_review_item_state` 中的状态抢占 UPDATE 添加执行选项。已核对 WHERE 同时包含 `id=item.id`、`student_id=user.id`、`state_applied=False`，且 SET 只改 `state_applied=True`，不迁移归属；该执行选项是内部固定值，不取客户端输入。仓库产品中只有此一处声明。
- `tests/test_vocabulary_due_cache.py`：新增四项，不改原 14 项断言。
- `tests/test_vocabulary_flow_backlog_gate.py`：新增真实 API 路径的学生隔离测试，不改原测试断言。原八项 stage2 对抗测试保持不变。

补丁额外收敛：原方案的 `user_versions` 会为所有曾写入学生永久保留元数据；现在只为已有在途加载的学生维护版本，最后一个同生 loader 结束时清理。全局失效增加 global version 并清空学生版本；多日期/数据库 key 的并行 loader 仍共享同生版本，避免过早清理造成旧结果发布。该边界由独审八项测试及三个负对照另验，见 `../independent/README.md`。此处不是改 TTL 或教学规则。

## 负对照及回归

先仅应用测试补丁，在原产品上执行：

```sh
TZ=UTC PYTHONWARNINGS=ignore /private/tmp/studytracker-stage2-py310/bin/python -B -m unittest tests.test_vocabulary_flow_backlog_gate.VocabularyFlowBacklogGateTest.test_one_students_review_answer_keeps_other_students_counts_cached -q
```

按预期失败：reader 精确 loader 次数 `2 != 1`，证据 `negative-control-py310.log`。随后应用产品补丁，原补丁双版本各 **251/251** 通过（3.10 30.011 秒，3.13 25.097 秒），日志 `python310-suite.log` / `python313-suite.log`。加入元数据清理后的最终源码再次跑同套 **251/251**，最终日志为 `final-python310-suite.log` / `final-python313-suite.log`（30.380 / 25.673 秒）；不能把前一组日志当作最终源码验证。

主审要求独立八项边界测试纳入正式回归，已提升为 `tests/test_vocabulary_cache_lifecycle.py` 并加入同一词汇 CI 步骤。正式模块在 3.10、3.13 各 **8/8** 通过（0.268 / 0.240 秒），与上述 251 项合计每版本 **259 项通过**，未把分开执行误称单次 259。日志 `final-python310-lifecycle.log` / `final-python313-lifecycle.log`。负对照改为加载正式模块并再次检出全部三个退化，见 `final-negative-controls.json`。

精确命令（cwd 为本实施树）：

```sh
TZ=UTC PYTHONWARNINGS=ignore /private/tmp/studytracker-stage2-py310/bin/python -B -m unittest tests.test_classroom_vocabulary tests.test_classroom_vocabulary_learning tests.test_dictation_answers tests.test_vocabulary_mastery tests.test_vocabulary_group_learning tests.test_vocabulary_group_learning_api tests.test_vocabulary_autonomous_review tests.test_dictation_review tests.test_vocabulary_numeric_learning tests.test_vocabulary_numeric_review tests.test_vocabulary_review_performance tests.test_vocabulary_context_availability tests.test_vocabulary_flow_backlog_gate tests.test_vocabulary_due_cache tests.test_vocabulary_review_selection tests.test_vocabulary_stage2_adversarial -q
TZ=UTC PYTHONWARNINGS=ignore /private/tmp/studytracker-stage2-py310/bin/python -B -m unittest tests.test_vocabulary_cache_lifecycle -q
# 将解释器换成 /Users/zhouxin/Desktop/studytracker/.venv/bin/python 验证 3.13。
```

四个产品/测试文件及增强探针 Ruff 通过，git diff --check 通过；cache 模块、其测试及新增探针 Black 通过（没有扩大格式化其他历史巨型文件）。含正式测试与 CI 的六文件冻结 SHA 见 `source-sha256.json`。

## 并发探针：直接计数命中，验证请求与持久化

原探针按计划运行，四种并发均按其时延启发式命中 **12/12**，保存 `original-probe-py310.json`。这个脚本用“第二次耗时小于冷耗时 1/5”推断命中，未验证请求成功，因此另加 `cache_under_writes_verified.py`：复用同一 2400 词、0/1/3/6 写者、每人 3 秒首答一次、每种 12 轮的合成负载，但逐请求保存 HTTP status、JSON ok、精确计数 loader 调用次数；还在本地合成 SQLite 中核对 `state_applied=1` 且存在首答的记录数。

```sh
TZ=UTC PYTHONWARNINGS=ignore /private/tmp/studytracker-stage2-py310/bin/python -B docs/reviews/vocabulary-entry-stage2-20261117/independent-claude/cache_under_writes.py --output docs/reviews/vocabulary-cache-policy-20261117/cache/original-probe-py310.json
TZ=UTC PYTHONWARNINGS=ignore /private/tmp/studytracker-stage2-py310/bin/python -B docs/reviews/vocabulary-cache-policy-20261117/cache/cache_under_writes_verified.py --output docs/reviews/vocabulary-cache-policy-20261117/cache/verified-probe-py310.json
```

| 并行写者 | 实际缓存命中 | 第二次精确 loader 调用 | 已持久化首答 | 冷/暖中位数 ms |
| --- | --- | --- | --- | --- |
| 0 | 12/12 | 0 | 0 | 441.6 / 1.3 |
| 1 | 12/12 | 0 | 2 | 448.0 / 1.2 |
| 3 | 12/12 | 0 | 6 | 447.6 / 1.1 |
| 6 | 12/12 | 0 | 12 | 456.6 / 1.1 |

所有四场景中所有请求均 HTTP 200、ok=true，所有配置的写者都确实提交了首答，持久化首答数与成功请求数相等。本短探针没有完成整批，因此 `settlement_exercised=false`；不把它当结算并发覆盖，结算由既有全套测试覆盖。数据纯合成，无学生身份、实际题面或 token 输出。

增强探针首轮开发时误用不存在的 `answered_at` 列，执行退出 1；已改为核对模型实际首答列并重新通过。该开发错误保留 `probe-development-column-error.log`，不是产品/生产故障。

## 边界与交接

缓存只用于数字展示；门禁与选题继续实时判断。30 秒 TTL、写事务隔离、本人变更与词库变更失效保持。首次冷计数仍全量，本补丁不承诺冷入口与积压量无关，也不是生产并发压力测试。

本子任务完成时六个产品/测试/CI文件及本报告目录仅在本实施树可见，发布与生产验收由主审继续。独立测试已纳入正式 CI，原审计来源仍保留在 `independent/` 目录。不要覆盖桌面旧 main 或固定小程序工作树。
