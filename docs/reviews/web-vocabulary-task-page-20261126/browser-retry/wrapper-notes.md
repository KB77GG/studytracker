# 本地回包丢失验收工具

`serve_retry_fixture.py` 导入原 `../serve_fixture.py`，不运行原文件的 `__main__`，继续使用原产品模板、JS 和计时器。数据库明确断言为 `sqlite:///:memory:` 和 TESTING，绑定仅 127.0.0.1；允许端口仅 5114（root 浏览器验收）或 5115（工具自测）。没有产品、schema、交接或 Git 修改。

```text
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/web-vocabulary-task-page-20261126/browser-retry/serve_retry_fixture.py --port 5114
```

- 正常进入：`http://127.0.0.1:5114/__qa/start/comprehensive`
- 下一次已成功保存的答案丢回包：`http://127.0.0.1:5114/__qa/start/writing?fault=transport_drop_once`
- 当前会话单独重新布置一次故障：`/__qa/control/transport_drop_once`，再回原任务。
- 只读统计：`/__qa/stats`；可按 `?task_id=2&attempt_id=...` 过滤。
- 审计默认追加到 `audit-5114.jsonl`，不覆盖已有证据；服务启动、故障布置、各 POST 提交后计数及结算请求秒数/Task 实际秒数均有 UTC 和 epoch_ms。

`transport_drop_once` 在产品 `_reply` 已 commit 后执行 `werkzeug.socket.shutdown(SHUT_RDWR)` 和 `close()`，关闭该请求的连接，未返回模拟 HTTP 503。是否真正丢失仍应由客户端网络错误验证；审计本身不替代客户端证据。一次性标记在服务端消费，避免丢失响应中的 Cookie 更新未送达而每次重试都断开。下一次同 attempt 请求保留原产品幂等处理。

统计字段只含合成任务、首答/再测记录、提交结果摘要及计数，不返回 Cookie、CSRF、身份校验头或 queue token；不会返回未作答题的正确答案。`db_task_actual_seconds` 读取 `Task.actual_seconds`，因为本项目 `VocabularyTaskSettlement.result_json` 本身不存用时。

## 已执行的工具验证

- Python 3.13 编译、Python 3.10 AST 语法通过。
- 在独立内存 fixture 中用 Flask test_client 调 GET `/__qa/stats` 和 task/attempt 过滤，均返回 200；6 任务、单任务过滤正确；SQL 监听确认这两次查询没有 INSERT/UPDATE/DELETE/DDL。结果 `selftest-static-and-readonly.json`。
- 子 agent 尝试运行 `selftest_retry_fixture.py` 时，其执行环境仍拒绝 bind/connect（EPERM），与 root 后续已授予权限的环境不同。服务子进程 PID 68420 已退出；这次没有网络验证通过结论。失败日志和启动审计保留为 `selftest-server-5115-sandbox-failed.log`、`selftest-audit-5115-sandbox-failed.jsonl`。

root 可运行同自测脚本；它只用 5115、自动启动并停止自测服务，期望验证：真正 ConnectionError、同一 attempt 重放后数据库只有一条记录、首答不变、结算 17 秒后重放 777 秒仍保留 17 秒且 settlement 仅一条。结果将写 `selftest-result.json`，审计 `selftest-audit-5115.jsonl`。脚本拒绝覆盖已有同名审计，重跑前应另存旧证据。**HTTP 工具自测不是浏览器、IME 或真实离页验收。**

## 订正路线更正

“忘了”有意跳过订正，不能用于进入订正页。`services/vocabulary_group_learning.py` 仅在综合目标下首答错误且 `not forgot` 时设 `pending_correction_question_id`。应输入明确错误拼写（如 `xxx`）提交，反馈后点继续，再验证订正页刷新。
