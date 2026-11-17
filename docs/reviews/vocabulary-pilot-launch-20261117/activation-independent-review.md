# 私有试点启动脚本独立审查

2026-11-17；审查 worktree：`/private/tmp/studytracker-vocabulary-error-pilot-20261117`，分支 `codex/vocabulary-error-pilot-20261117`，基线 HEAD `513c732f`。本次只读审查产品并运行本地合成测试，仅新增此报告；未访问生产、未提交/推送/部署。工作树原有本阶段产品、测试、报告及根交接的未提交修改由各 owner 保留，根 agent 统一维护 `docs/CODEX_HANDOFF.md` 与 `docs/WORKLOG.md`。

## 结论

未发现阻止使用启动脚本的缺陷。审查范围是 `scripts/activate_vocabulary_pilot.py`、管理脚本新增的 `locked_check` 调用及其 `enroll_student` 事务行为，不把本地通过等同于生产启用成功。

- 默认预演以 SQLite `mode=ro` / `query_only` 读取，不创建名单锁文件，也不写名单或数据库。
- 应用前使用独立私有锁文件；待办 intent 先原子持久化并 fsync。私有名单要求当前 UID、0600、普通文件、单硬链接，拒绝最终路径符号链接。四人/六人必须是正整数且无重复。
- `BEGIN IMMEDIATE` 取得数据库写锁后重新验证 schema、七参数、有效全局 OFF、选中学生有效性、旧 active 批次，以及全库五张新表为空。全部学生在一个事务中入组；任一学生失败则全部回滚。
- 提交后重新读取全库：入组学生集合、人数、enabled 和 cohort 必须完全匹配，其他四表仍为空；不能将名单外入组或旧试点状态当成功。
- 数据库提交后名单最终写入失败会保留可识别的 pending intent；重试验证相同数据库身份、名单、参数和 cohort 后只补记事实，不重复入组。未提交的 intent 超过十分钟拒绝复用。
- 不修改 `.env`、不启停服务、不代领/代答、不导入历史错词；stdout 只包含聚合事实，异常输出不包含原始错误、学生 ID 或路径。

## 复现与结果

命令均在上述 worktree 执行：

```sh
/private/tmp/studytracker-stage2-py310/bin/python -m unittest tests.test_vocabulary_pilot_activation
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_vocabulary_pilot_activation
```

最终分别为 **15/15 通过（3.164s）**、**15/15 通过（2.858s）**。Python 3.13 有 fixture 连接释放 ResourceWarning 与既有 datetime.utcnow 弃用提示，无断言失败。所有本地测试进程已结束。

首次独立运行发现三个测试 fixture 的原生 INSERT 漏填 `created_at/updated_at`，在抵达断言前触发 NOT NULL 错误；已由实现 owner 修复，以上为修复后的复跑结果，未把初次失败误计为通过。测试覆盖中途入组失败全回滚、提交后名单写失败重试、全库名单外行拒绝、锁前预演之后新增旧 active/改变开关、跨数据库复用拒绝，以及输出隐私。

核验时源码 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| `scripts/activate_vocabulary_pilot.py` | `ac08f7eb0285e8327c29be3b6d9ae2541c6a3ff9805ea8fae184ac4c1b980386` |
| `scripts/manage_vocabulary_error_pilot.py` | `a93f715822e2ab11b4f766d770f449a18b8340a68ba9c4b0973d7b5635d05209` |
| `tests/test_vocabulary_pilot_activation.py` | `a8cf5bd8018f5a42e42a7853c791e2f9ac1401de793a18d0d19d609406d2d429` |

## 操作边界与交接

脚本检查自身进程与 `.env` 的有效配置，不声称已检查另一个 gunicorn 进程的实际配置。生产 worker OFF、实际服务参数、源码、迁移与启用后精确四人范围由根 agent 的 `verify_live.py --expected-size 4` 回读负责。

入组事务只能保证提交时没有旧 active，OFF 服务在提交至切 ON 的间隙仍可能创建旧批次。已向根 agent 报告；根选择 `service stop → activation apply → 原子写 flag → finally start` 的独立操作封装处理，交 core agent 另审。本报告不声称已独审该封装或已运行生产操作。

本次独审结果仅本机未提交文件可见，待根统一纳入发布与规范交接。下一步由根按实际四人私有名单完成操作封装审核、迁移/启动与无身份生产回读；不要仅凭本报告将试点标记已开启。
