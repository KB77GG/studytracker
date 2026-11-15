# 生产只读验收器说明

`verify_production.py` 只使用 Python 标准库，由根 agent 审阅后通过 SSH stdin 执行；本文件不主动连接服务器。默认项目 `/root/apps/studytracker`，默认 HTTP `http://127.0.0.1:5002`。不 import `app` 或 `config`，不执行迁移、建表、试考、监考面板或策略写入。

参数：`--phase pre|post`，`--expected-head SHA`，可选 `--manifest-b64 BASE64_JSON`。post 没有准确 expected HEAD 不能通过；pre 可省略。可选 `--public-base https://studytracker.xin` 仅校验 manifest 中 `static/` 资源，不发送学生 capability。`--root`、`--base` 用于本机隔离自测。

数据边界：

- SQLite 以 URI `mode=ro` 打开，再设 `query_only=ON`，只读三张诚信表是否存在、policy 模式聚合，以及已有 exam/session 的进程内 HTTP 选样。不会输出姓名、口令、session ID、exam ID 或 access token。
- 登录页和未提交章节页只做 GET，不执行页面 JS、不跟随重定向、不点击科目入口、不 POST。HTML 仅在内存检查固定标记及 `exam_guard` 缺失；不保存正文、header、URL 或敏感错误消息。
- 优先已有历史未交卷会话，检查其状态及所有开始／截止／提交时间在请求前后相同，只输出布尔值。若已无未交卷会话，明确标为“章节未验”，总体失败；不新建会话补测。
- 所有 policy 模式按 off/monitor/enforce/unknown 聚合，monitor/enforce/unknown 必须全为0。policy 表不存在按代码默认off判定，并检查 GET 前后表存在状态和模式聚合不变。
- 核对生产 SHA、tracked clean、systemd 状态、gunicorn 文件中1worker/gthread/6threads/127.0.0.1:5002设置、实际直接子worker数及5002监听归属。不会读取或打印整个进程环境或服务 ExecStart。
- 只读服务器部署助手文件，输出 SHA 和是否包含 `create_all`、诚信建表脚本名、三表字面量；不输出脚本文本。字面量命中是供部署人核对的线索，不能单凭命中判断脚本执行了建表。
- 每个失败只输出异常类名，绝不输出可能携带 token、SQL 参数或完整 URL 的异常消息。公开结果不含 capability，但真实 HTTP GET 仍可能按服务器既有行为写入其常规访问日志；验收器不复制这些日志。

`ok=true` 要求准确版本（post）、干净tracked、服务与端口检查通过、两个现有页面200且固定标记齐全且不含守卫、会话状态不变、所有策略off、表与策略聚合不变、可选manifest和公开静态资源hash匹配。没有可验证的现有章节页时不能伪报成功。

本机必要自测（不访问生产）：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/exam-integrity-release-20261115/test_verify_production.py -v
```

自测用临时SQLite和HTTP响应stub，覆盖：无表保持无表且不创建会话；即使临时关闭query_only也被mode=ro阻止写入；开启或异常策略不误报关闭；全已交卷不伪造章节200；HTTP异常／302不泄露capability；post准确HEAD；manifest目录越界被拒。systemd/proc/ss的真实状态只能由生产执行后的证据证明，自测不会把stub当成生产验收。
