# 数字题兼容回滚包（仅本机验证，未执行回滚）

用途：从当前完整数字听写候选关闭新 numeric 题生成，同时保留已有 numeric 快照的读取、首次/重试/纠错判分、反馈和 `?numeric=1` 音频。不能用原 `9ae4ed9a` 完整代码替代此兼容状态；不能恢复旧数据库覆盖学生新进度。

## 精确适用基线

- 来源目录：`/Users/zhouxin/Documents/Codex/2026-10-24/task-2/numeric-dictation-fix`。
- 来源 Git 基线：`9ae4ed9a3a58838beded8850258b313f4be72e43` **加本轮完整候选改动**。补丁不能直接用于未经修复的该提交。
- 完整候选五个运行文件内容指纹：`866e4d8f4b52ad1972e0f3fcd4ac987217933feacc783268810d523b8be33e53`。每个文件 SHA-256 和回滚后 SHA-256 均在 `numeric-compatibility-rollback-manifest.json`。正式业务部署 commit 为 `1cac6c0ce3544dbc7d982f24885da652ad29725c`；即使 commit 不同，必须先验证五文件内容与此清单完全一致。
- 补丁 `numeric-compatibility-rollback.patch` SHA-256：`4361e41b8d2742b791eaa22fa488e89f62158358a5d1c4aa4a3d284b57fe64c3`。

只改三个服务文件：

1. `services/vocabulary_mastery.py`：恢复原 `_question_for` 和 `get_vocabulary_task_queue` 的生成行为。
2. `services/vocabulary_group_learning.py`：恢复原熟悉卡与 `_build_group_specs` 分类路由。
3. `services/vocabulary_autonomous_review.py`：恢复原候选资格条件。

`dictation_numeric.py`、`api/dictation.py` 完全不变；三个服务的 numeric 判分、快照校验、冻结音频反馈都保留。无 schema 迁移、词条修改、任务/成绩/进度处理。回滚后新任务重新受旧数字过滤限制，但此前已存在的 numeric 题仍可作答；这正是临时关闭新题能力的降级边界。

## 使用顺序（尚未执行）

先在隔离发布工作树核实当前部署 commit、备份现状并保留所有其他用户改动。将本目录的 patch、manifest 和验证脚本一起带到执行环境。下列路径示例只针对本机，不应原样猜测服务器目录：

```sh
cd /绝对路径/发布工作树
python3 docs/design/numeric-dictation-20261024/verify_numeric_rollback_baseline.py .
git apply --check docs/design/numeric-dictation-20261024/numeric-compatibility-rollback.patch
git apply docs/design/numeric-dictation-20261024/numeric-compatibility-rollback.patch
```

任何哈希不一致或 `--check` 失败立即停止，针对实际差异重新审查，不使用 `--reject`、强制覆盖或复原数据库。通过之后按既有项目流程提交/部署这个兼容增量，并复核服务、已冻结题目和音频；不直接 reset 生产仓库。只有确认需要回滚时才执行。

## 已完成验证

隔离副本：`/Users/zhouxin/Documents/Codex/2026-10-24/task-2/prepared/numeric-rollback-validation-8qpmdlfw`。从源 HEAD archive 构建，叠加完整候选后仅应用上述回滚内容；主候选和 `numeric-dictation-release` 未修改，未联网/部署/写生产。

- 对完整源候选 `git apply --check` 通过；对隔离兼容副本反向 `git apply --reverse --check` 通过。
- 数字规则、数字音频 mock、原英文判分、原 mastery/分组/自主复习：**134 passed / 198 subtests passed**。
- `test_numeric_compatibility_rollback.py`：**3 tests OK**，使用完整候选预先生成的 8 个冻结数字快照；覆盖任务与组内判分、电话前导零、日期/金额/小数/百分比/时间、实际 SQLite 自主复习首次/纠错/忘记分支、numeric skip reason 为 None、冻结答案与音频回放不变，以及关闭新 numeric 生成后原英文仍能出题。
- 音频测试全部 mock；本包没有产生真实音频。

复现命令：

```sh
cd /Users/zhouxin/Documents/Codex/2026-10-24/task-2
TZ=UTC PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python prepared/test_numeric_compatibility_rollback.py
cd prepared/numeric-rollback-validation-8qpmdlfw
TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q --disable-warnings --tb=short -p no:cacheprovider tests/test_dictation_numeric.py tests/test_dictation_numeric_audio.py tests/test_dictation_answers.py tests/test_vocabulary_mastery.py tests/test_vocabulary_group_learning.py tests/test_vocabulary_autonomous_review.py
```

校验脚本只读五个运行文件与清单，不访问数据库；单独的验证脚本只读取清单指定隔离目录并创建内存 SQLite。
