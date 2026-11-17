# C3 新验收要求：当前证据与试点前缺口

审查工作树：`/private/tmp/studytracker-vocabulary-error-pilot-20261117`；产品基线/当前已提交 HEAD：`79dd34f4`（产品提交 `188d29f6`）。对照来源：审计分支提交 `45167aad` 对 `docs/VOCABULARY_REVIEW_PLAN.md` 新增的 C 部分。此子审查只使用本机代码、已有报告和合成数据库，没有访问或修改生产；没有改产品、配置、正式 CI 或教学规则。

**结论：不能声称 C3 已全部通过。已有默认 OFF 交付不因这些 ON 场景的试点前缺口而被阻止；但启用学生、提高日上限或宣称完成 C3 前，需要补下面的工作。** C2 的“三个不同日子练到答对、不清零”仍是待用户确认的建议，本次没有实现，也没有把它视为已接受规则。产品仍是此前确认的 B2 行为。

## 按 C3 逐项核对

| C3 要求 | 已有证据 | 尚缺/结论 |
| --- | --- | --- |
| 1. ON 时所有必做路径 SQL 条数及取回行数不随 0/2400/10000 旧历史增长，并纳入 CI | 原 `probe_mandatory_scale.py` 只覆盖 summary，0/5000/20000 额外旧 mastery + maintenance，8 SQL/次、0 旧 mastery 查询；未计 fetch 行数。本次补了下表 7 条实际服务路径，SQL/DBAPI fetch 行数三档相等，双 Python 通过。 | **部分覆盖**。未进入正式 CI；未覆盖所有学习步骤、题型、错误/忘记/订正/重试、空批/失效材料/午夜边界，也不是完整 HTTP 往返矩阵。不能将原 summary probe 冒称覆盖全流程。 |
| 2. 日上限 30/40 时仍每批最多 20 | 默认 20 时实际领取 20；本次额外实测如下表。 | **明确未达**：配置 30 会一次物化 30，配置 40 会一次物化 40。当前 `daily_limit` 同时用于每日配额、plan entries 和 session `batch_limit`。提高日上限前应独立限制每批 <=20，并验证分批累计配额/继续领取。默认 20 本次不受影响。 |
| 3. 资格扫描不在写事务内、锁持有毫秒级 | 领取先物化候选，再写入 session，并在锁内重验当前批；结算跳过旧 due-pool 扫描。本次单线程合成探针测了首 DML 到 commit 的近似窗口。 | **未完整验收**。`reserve_items()` 写锁后调用 `_planning()`；它 `.all()` 读取该生 active/paused 新队列及今天 checkpoint；随后 `_housekeeping()` 会读取并更新所有过期 pending checkpoint/本次转出项。不能声称完全没有锁内扫描。尚未把既有 `probe_write_lock_hold.py` 改造成 ON/OFF、文件 SQLite、并发场景的正式复测。 |
| 4. 当日错后隔题再测不增加全量选题 | 现有冻结批题面、首答幂等和订正测试继续适用。 | C2 新的隔题再测规则未确认、未实现，故不能声称该新规则通过。以后若实现，应复用已领取批次并单独验证请求/选题次数。 |
| 5. 2400 积压，ON/OFF，并发 1/3/6 基准与目标 | 已有两连接事务正确性测试验证幂等、配额及 enrollment/legacy claim 竞态。本次是单线程 SQLite 内存库，7 路径单次测量均几十毫秒以内。 | **缺少完整基准**。两连接正确性不是 1/3/6 性能基准，本次也未对比 OFF，不能断言 ON 不慢于 OFF、6 人 <1秒或生产延迟达标。 |
| 6. 四类接口每天 499 数量/比例，试点前后各一周 | 有旧日志统计脚本和先前故障趋势分析。 | **尚未完成试点前后一周对照**；未启用试点时不可能已有试点后数据。需明确接口路由口径、分母、时间窗和试点启用时间，保留两侧一周日志。 |

## 本次补充的合成探针

文件：`independent/probe_c3_gap.py`；结果：`independent/new-plan-gap-py310.json`、`independent/new-plan-gap-py313.json`。

固定 10 个当前必做错能力及其 10 条当前 mastery，另外加入 **0 / 2400 / 10000 条无关旧 mastery**，题库固定为测试夹具的 22 词；因正在测当前批次，不能把“0 条无关旧历史”说成数据库内总共零条 mastery。旧历史 sense 没有另造词库资料，所以它验证的是排除无关旧 mastery 的服务工作量，而非扩大词库/题库后的成本。每一档使用新的合成内存库，开启总开关并显式 enrollment，不读取生产数据。

通过 SQLite DBAPI cursor 的 `fetchone/fetchmany/fetchall` 统计实际返回行数；每次操作提交后记录。Python 3.10.20 和 3.13.3 的结果一致，且脚本对三档 SQL/行数相等作断言：

| 路径 | 每次 SQL 数 | 实际 fetch 行数 |
| --- | ---: | ---: |
| 首页 summary | 9 | 15 |
| 任务 preflight | 12 | 17 |
| 领取 10 题 | 79 | 212 |
| 当前批首题答对 | 26 | 12 |
| 完成 10 题后的结算 | 32 | 52 |
| 学习任务首次取题 | 35 | 50 |
| 已启动任务再次取题 | 16 | 14 |

领取、作答、首次任务取题仍有当前能力的定点旧 mastery 读写；这不是旧到期池全量资格扫描。SQL/行数相等证明上述具体路径不因本探针增加的旧历史而多取数据，不等于数据库内部 COUNT 成本严格 O(1)，也不证明所有题型/新队列规模都固定成本。

另固定 44 个可出题的错能力（22 词 × 词义/拼写两能力），分别改变日上限，调用真实 `claim_today_review()`：

| 每日上限 | 实际一次物化题数 | 返回 batch_limit |
| ---: | ---: | ---: |
| 20 | 20 | 20 |
| 30 | 30 | 30 |
| 40 | 40 | 40 |

这给出了 C3 第 2 条的可复现反例，不只是代码推断。

本次单线程每路径只测一次，用于验证结构和发现量级，不能作为统计性能验收。持久化的 Python 3.10 结果最大操作 29.644ms、首 DML 到 commit 最大 25.719ms；Python 3.13 分别 28.893ms、25.699ms。该窗口不是操作系统锁跟踪，不包含文件库磁盘 I/O、SQLite 锁等待或真实 6 线程竞争；尤其不能替代指定写锁探针。

## 建议的下一轮范围（不在这次部署中变更）

1. 如仍拟试点既有 B2，先将每批限制与每日配额拆开，补 30/40 分批测试；在处理前保持默认日上限 20。
2. 把本次“旧历史大小 × 固定当前批”结构扩为完整请求矩阵，覆盖错误/订正/不同能力/清理分支，测 DBAPI 行数并纳正式 CI；另测新队列规模、当天 checkpoint 数和长时间未领取后的清理规模，避免将问题从旧 mastery 扫描搬到新队列。
3. 在与生产相同 SQLite 模式的临时文件库上，复用/扩展 `probe_write_lock_hold.py` 与 `probe_vocabulary_flow.py`，分别 ON/OFF、积压2400、并发1/3/6，多次采样；记录读扫描是否在写锁内及锁等待。
4. C2 先取得明确确认再设计，不能以“未否定”替代接受；若改为 C2，应以最终规则重做上述验收，不把现有 B2 的通过数挪作 C2 证明。
5. 由根任务按真实试点时间安排前后一周四类接口 499 统计；此子审查没有生产动作或学生启用权限。

## 精确复现命令与交接状态

在上述工作树执行：

```sh
/private/tmp/studytracker-stage2-py310/bin/python docs/reviews/vocabulary-error-pilot-20261117/independent/probe_c3_gap.py > docs/reviews/vocabulary-error-pilot-20261117/independent/new-plan-gap-py310.json
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/vocabulary-error-pilot-20261117/independent/probe_c3_gap.py > docs/reviews/vocabulary-error-pilot-20261117/independent/new-plan-gap-py313.json
```

两次退出码均 0。仅有测试夹具短 JWT key 提示（Python3.10）及 sqlite 日期适配器弃用提示（Python3.13），不包含学生信息。最初为了构造“零旧历史”删去所有 mastery 也删掉当前题目的材料前提，导致 `total_count==10` 断言失败；修正为保留固定当前批 10 条 mastery 后运行上述最终探针。此修正只涉及合成夹具，没有改产品。

本轮仅新增本报告、探针及两份 JSON，当前未 commit/push。工作树既有 `docs/VOCABULARY_REVIEW_PLAN.md`、客户端 README 的未提交改动及 CI/部署/客户端回读文件由根任务拥有，未覆盖。产品 HEAD 保持 `79dd34f4`，本报告不声明新的部署、小程序发布或试点开启。
