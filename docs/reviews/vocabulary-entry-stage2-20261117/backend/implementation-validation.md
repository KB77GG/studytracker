# 第二层后台候选选择与事务验证

## 基线和范围

- 实施树：`/private/tmp/studytracker-vocabulary-entry-stage2-20261117`。
- 分支：`codex/vocabulary-entry-stage2-20261117`；实施基线 `e19a8104`，包含已发布的第一层 `c7e85214`。
- 本子任务修改 `services/vocabulary_autonomous_review.py`，新增 `services/vocabulary_review_selection.py`、`tests/test_vocabulary_review_selection.py`，调整 `tests/test_vocabulary_review_performance.py` 的固定查询预算。
- `services/vocabulary_due_cache.py`、缓存测试、CI 和独立对抗测试由主审/其他 agent 完成，本报告不将其实现归为本子任务。
- 未修改前端、schema、间隔规则、复习批量 20、冷却规则、评分或已有题目生成器。原 `_due_candidates` 完整实现保留为参考和独立等价验证依据。
- 本轮全部实现仍在本机，**未 commit、push 或部署**。没有访问或修改生产数据库；本文件不代表发布授权。

## 实现

1. **新鲜候选选择**：SQL 联合四个到期维度，沿用关联补练、原维度补练、错误/未测、到期时间、末次作答、代表词位置、维度顺序的完整排序。代表词优先及缺失时 fallback、已有但无 sense 的代表词跳过、最近失败的订正状态、补练预算与本日冷却均保留。每次最多载入 128 条候选元数据对应的 ORM 对象，在合格义项首次出现时去重。存在性检查遇到首个合格词即停；领取在物化 20 题后停止。
2. **精确数字的轻量 loader**：`_eligible_due_sense_ids` 为每个 sense 找到一个合格维度即停，不选获胜维度、不排序；只有当日补练额度已满、补练类别可能影响资格时，才加载最近题记录。其返回集合与完整参考结果集合等价，供主审实现的 30 秒展示缓存使用。
3. **显示和决策分开**：门禁的 `required`、领取名单、结算后的 `continue_available` 均使用当前资格，不能由展示缓存中的 0 或正数决定。原 409 整数 `due_count` 契约保留；第一层既有 `gate_only` 已放行分支继续返回 `None`。短时缓存中的数字可能在 TTL 内滞后，但不是放行依据。
4. **领取写锁**：在清理过期批次、绑定任务或插入新批次之前准备数字快照和 20 题。插入新 session 获得 SQLite 写锁后，只重新检查所选至多 20 个 sense 的资格、维度、排序元数据及完整 public/answer 快照。任何变化返回 `409 review_claim_changed`，由原路由回滚。ORM 查询使用 `populate_existing()`，避免跨连接更新被 identity map 旧对象遮蔽。
5. **领取原子性**：Python SQLite legacy 事务模式下，首个 SAVEPOINT 可能是顶层，RELEASE 会提前提交空 session。现在仅在新 claim 的 SQLite driver 尚未进入实际事务时显式执行 `BEGIN`，使 session 插入、重验和题目写入共同受原路由 commit/rollback 控制；没有全局修改 SQLite 事务策略。
6. **结算写锁**：全量展示数字快照及“排除本批后仍有合格词”的新鲜存在性检查均在 legacy 订正修改/CAS 前完成。锁内只重算本批至多 20 个 sense，修正展示计数，并据此与写前的新鲜 outside existence 合成 `continue_available`。已有 `result_json` 幂等返回保持。

## 性能边界

- 冷的精确数字仍需遍历到期积压，复杂度仍与积压相关；30 秒缓存仅降低重复显示计数成本。
- SQL 元数据流仍可能在数据库内部扫描/排序该生到期元数据和相关历史。`fetchmany(128)` 限制的是 ORM 物化与 Python 资格处理，并不意味着数据库只读取 128 行。
- 若优先候选大部分无效或全部不合格，存在性/选批可能遍历多页甚至全部候选；不承诺入口 O(1) 或绝对时间上界。
- 有效 2400 词合成样本中，存在性只做 1 次资格检查、领取只做至多 21 次资格检查取得 20 题；这不是所有数据的上界。
- 为兼容精确数字，公开 preflight 冷计数加新鲜门禁可以比只做计数多固定 3 次 SQL，因此旧定向预算由 13 改为 16；没有放宽随积压增长的查询约束。
- 写锁保证针对正常独立 HTTP 请求；直接 service 调用者若带着已经写入的外层事务进入，已有锁不能由本服务撤销。
- 最终时延、并发 HTTP 状态和持锁基准由主审统一运行，避免多 agent 同时测试污染结果；本报告不借用旧版测量作为最终版性能事实。

## 验证事实

工作目录均为实施树。

在最后的 `continue_available` 独立判定和 SQLite 外层 BEGIN 修订**之前**，执行：

```sh
TZ=Asia/Shanghai PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_classroom_vocabulary tests.test_classroom_vocabulary_learning tests.test_dictation_answers tests.test_vocabulary_mastery tests.test_vocabulary_group_learning tests.test_vocabulary_group_learning_api tests.test_vocabulary_autonomous_review tests.test_dictation_review tests.test_vocabulary_numeric_learning tests.test_vocabulary_numeric_review tests.test_vocabulary_review_performance tests.test_vocabulary_context_availability tests.test_vocabulary_flow_backlog_gate tests.test_vocabulary_review_selection tests.test_vocabulary_due_cache -q
```

结果 **237 项通过，21.321 秒**，原始日志 `python313-suite.log`。不能把它称为最后两处修订之后的全套结果。

最后两处修订之后，执行：

```sh
TZ=Asia/Shanghai PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_vocabulary_review_selection tests.test_vocabulary_stage2_adversarial -q
```

结果 **16 项通过，4.017 秒**（selection 8 + 独立对抗 8），输出直接由工具返回，未另外保存伪造原始日志。包括：

- 12 个固定随机数据集（每组 80 个 mastery）的全部候选字段、资格集合、排序、限定 sense 子集及首 20 题 public/answer 快照与参考一致。
- 无效优先候选跨页补满 20 题；代表词跨 sense、缺失 fallback、无 sense 跳过及同序边界。
- 缓存 0 之后新词到期仍必须复习，领取名单不受缓存抑制；缓存正数但实际无待复习不会生成批次。
- 本地午夜冷却、03:00 前任务宽限日与当前复习日边界。
- 冷计数发生在 claim 首次 DML、settle CAS 之前，锁内仅重查本批。
- 缓存正数/0 与实际相反时，`continue_available` 始终依照新鲜资格。
- 两连接在准备后改变冷却、代表词内容或到期时间时拒绝旧候选；无过期旧批次、没有前置 DML 时，冲突后的 rollback 也不会留下 active 空 session。

最后仅用 Black 库格式化本轮修改 hunks/新文件，无语义修改。以下定向检查通过：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check services/vocabulary_autonomous_review.py services/vocabulary_review_selection.py tests/test_vocabulary_review_selection.py tests/test_vocabulary_review_performance.py
git diff --check
```

两产品文件及新 selection 测试用 `ast.parse(..., feature_version=(3,10))` 通过。主审负责最终实际 Python 3.10 全套、真实 HTTP 并发/持锁检查和最终文件 SHA；不把本子任务的 AST 兼容检查冒充 Python 3.10 实跑。

本子任务无仍运行的测试或基准进程。规范交接文档由主审统一更新。
