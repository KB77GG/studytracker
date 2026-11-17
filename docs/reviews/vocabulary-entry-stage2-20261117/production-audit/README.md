# 第一层部署只读核验边界（2026-11-17）

工作树 `/private/tmp/studytracker-vocabulary-entry-stage2-20261117`，分支 `codex/vocabulary-entry-stage2-20261117`，开工 HEAD `e19a8104`、clean。本子任务只新增此目录的审计脚本、合成自测和记录；未改产品、根交接、Git 或生产状态。根交接由主审统一更新。

## 已取得的直接生产证据

2026-11-17 08:07:19 CST，直接 SSH 命令返回 exit 0：

```sh
ssh root@47.110.45.193 'cd /root/apps/studytracker && git rev-parse HEAD && git status --porcelain --untracked-files=no && systemctl show studytracker.service -p ActiveState -p SubState -p NRestarts -p ExecMainStartTimestamp && .venv/bin/python --version && date --iso-8601=seconds'
```

输出：

```text
c7e852140cc613b708212a352ec680a0f9dcc8a2
NRestarts=0
ExecMainStartTimestamp=Tue 2026-11-17 07:41:05 CST
ActiveState=active
SubState=running
Python 3.10.12
2026-11-17T08:07:19+08:00
```

tracked Git 状态为空。此命令未读取学生数据、未写生产数据库、未调用学生业务接口。它未独立核实实际 worker 数、监听归属或 HTTP 响应。主审另有 `production-health-readback.txt`，应以其自身内容补充这些项目，不能将本记录的边界扩大。

## 未执行的深一层探针

`verify_stage1.py` 复用 SHA 固定的前次只读 helper。设计包括 mode=ro、query_only、SQL authorizer、最小 Flask/models、禁止 app/config/重模型导入；仅两次既有已开始任务的 `review_preflight(gate_only=True)`，用抛错替身确保 `_due_count` 从未被调用。业务行数、同一快照、total_changes 和 ORM 脏状态前后核验；输出仅匿名计数和耗时。不调用取题/提交/领取 HTTP，不生成登录凭据。

脚本拟对比 07:21:05–07:41:05 与 07:41:05–08:01:05 CST 两个 20 分钟窗口的匿名 vocabulary queue / dictation queue / dictation submit 状态计数。499 仅指客户端关闭请求，不认定全部为超时；submit 路由混合词汇/听写，日志无请求体，不能精确区分。无时延字段和少量/零样本均不能证明完全恢复。

本机合成自测初次因 fixture 未填 started_at 失败，补齐后 4/4 通过（`local-safety-tests.log`）；覆盖 SQLite 写/DDL/ATTACH/PRAGMA 拦截、缺失数据库不创建、真实 gate 代码零扫描且 fixture 文件 SHA 不变、日志窗口边界与脱敏、Python 3.10 语法。定向 Ruff 通过。精确命令：

```sh
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/vocabulary-entry-stage2-20261117/production-audit/test_verify_stage1.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check docs/reviews/vocabulary-entry-stage2-20261117/production-audit/*.py
```

生产执行首试 SSH 被沙箱拒绝（exit 255，Operation not permitted）。依规定提权重试后审批等待 748.5 秒被用户中止，没有 cell/session ID，也没有脚本已在生产启动的证据。输出重定向曾创建空 `stage1-production.json`，已改为明确的“未执行/审批中止”状态记录，**不能作为验收通过证据**。随后本机 `ps` 也被沙箱拒绝，无法枚举是否有残留本机进程；未盲目 kill，未碰生产服务。按主审要求停止新生产查询和审批。

## 仍未验证

本子任务未取得生产 gate_only 耗时/零扫描实跑结果，未取得部署前后等长日志统计，未验真实微信完整流程。不得称所有学生均已恢复。缓存安全审阅仅开始静态阅读，尚未运行其测试或新增对抗用例；不等于独立验收通过。

全部新文件目前仅本机；本子任务没有 commit、push、deploy、生产 DB/服务变更或小程序发布。
