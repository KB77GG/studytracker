# 词汇入口第二层独立对抗审阅

审阅树 `/private/tmp/studytracker-vocabulary-entry-stage2-20261117`，分支
`codex/vocabulary-entry-stage2-20261117`，基线 HEAD
`e19a81045da782bd2a245caee0222dcbdf87b84b`。审阅对象为该树未提交的第二层候选，
不是线上第一层补丁的重新发布验收。审阅者只新增本报告和
`tests/test_vocabulary_stage2_adversarial.py`，没有修改产品、生产数据、配置或服务，
没有 commit/push/deploy；规范交接由主审统一更新。

## 结论

当前候选没有本次独立审阅尚未关闭的阻断。审阅中发现两个相关原子性问题，
实现 agent 已修复，并经独立双连接测试关闭。所有测试使用临时文件 SQLite 和合成数据，
不读取真实学生、生产库或网络。

1. **选批后、写锁前的数据变化**：另一连接可以提交同词当日正式作答、把词条改成无效，
   或把到期时间改到未来；预先物化的批次不能直接落库。现实现取得写锁后，
   只重新验证选中不超过20个 sense 的候选元数据、资格及实际题面/答案，
   同时刷新 ORM identity map；发生变化返回409，由现有路由统一回滚。
   独立三反例全部通过。禁用 `_revalidate_claim_candidates` 的负对照中，
   原四项套件恰好三项失败、零错误，证明测试确实覆盖该窗口。
2. **SQLite 首次 SAVEPOINT 提前持久化**：没有旧批次过期写入时，Python SQLite
   legacy 模式不会为前面的 SELECT 建立实际事务；首次 SAVEPOINT 释放会提交新空批次，
   后续409及 route rollback 仍不能撤销。独立 Python3.10 测试先复现残留 active=1，
   应为0。现 `_begin_claim_outer_transaction()` 仅在 SQLite 实际未处于事务时显式 BEGIN，
   使 session、题目和重验共同受外层回滚约束；未更改全局事务设置。
   修后通过，禁用该 helper 的单项负对照仍恰好一失败、零错误。

## 已核对的行为

- 代表词不存在/NULL、代表词本身 sense 为 NULL、跨 sense 代表词、跨书 fallback、
  相同时间与维度优先级，SQL候选与保留的 `_due_candidates` 参考实现相等。
- 数量缓存被替换为0时，真实到期门禁仍要求复习，真实队列仍完整按顺序领取；
  缓存被替换为虚构正数时，不会产生门禁或题目。缓存只影响显示。
- 凌晨01:00的宽限任务复习批次仍归原任务日期，冷却/候选计算使用当前北京时间日期。
- 复跑实现者的随机排序/资格、冷却、有限选批、结算锁内范围，以及缓存TTL、跨日、
  提交/回滚、批量写入、应用隔离、同生并发合并与内存上限检查。
- 结算原有CAS、唯一结算记录、路由失败回滚路径保留。没有把缓存用于授权、排序或选题。

## 精确验证

以下 cwd 均为上述审阅树。

```sh
TZ=Asia/Shanghai PYTHONWARNINGS=ignore /private/tmp/studytracker-stage2-py310/bin/python -B -m unittest tests.test_vocabulary_stage2_adversarial tests.test_vocabulary_due_cache tests.test_vocabulary_review_selection -q
TZ=Asia/Shanghai PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_vocabulary_stage2_adversarial tests.test_vocabulary_due_cache tests.test_vocabulary_review_selection -q
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check tests/test_vocabulary_stage2_adversarial.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/black --check tests/test_vocabulary_stage2_adversarial.py
git diff --check
```

Python3.10 **30/30，5.548秒**；Python3.13 **30/30，4.872秒**。
其中本审阅新增8项、缓存14项、实现者选批8项，不将两解释器重复运行相加计数。
Ruff、Black和diff检查通过。较早宽限测试有一次 `date` 对比数据库字符串的夹具失败，
改为ISO日期比较后通过；这是测试类型错误，非产品缺陷。

SAVEPOINT 负对照可复现命令（只临时mock，不改源文件）：

```sh
TZ=Asia/Shanghai PYTHONWARNINGS=ignore /private/tmp/studytracker-stage2-py310/bin/python -B - <<'PY'
import io, unittest
from unittest.mock import patch
from services import vocabulary_autonomous_review as review
name = 'tests.test_vocabulary_stage2_adversarial.VocabularyStage2AdversarialTest.test_first_claim_conflict_rolls_back_insert_even_without_prior_write'
with patch.object(review, '_begin_claim_outer_transaction', return_value=None):
    result = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromName(name))
assert result.testsRun == 1 and len(result.failures) == 1 and not result.errors
print('expected negative control: 1 failure, 0 errors')
PY
```

## 验证边界与哈希

这里未做生产负载、真正手机、网络故障或全部历史数据验证。锁内重验仅限选中的20个sense，
但再次生成语境选择题仍可能读取整本候选词书；写锁成本仍受词书大小和题型影响，
不得声称完全恒定。精确数字的30秒缓存是有限陈旧的显示快照，不能把该快照描述为每次实时重算。
性能数字以主审基准报告为准。

本报告最终运行时 SHA256：

| 文件 | SHA256 |
| --- | --- |
| services/vocabulary_autonomous_review.py | d5d39ceb72e8a37175e7fd0158f13c0709604358652085886565125d8fc50f8c |
| services/vocabulary_review_selection.py | 0fff00ca0ce9dc87ea4cd6a30f08e28b6bc4ca3b1f00a1175ab234164a418e76 |
| services/vocabulary_due_cache.py | 0406ee02ba6cabc723c6c6cc7754e1ea73febfa8e025cea62b79bdba54eba6e1 |
| tests/test_vocabulary_stage2_adversarial.py | a95241082dbe560a352dd696168c3dc1a61ff4fe778d8a879dec586a13543b41 |
