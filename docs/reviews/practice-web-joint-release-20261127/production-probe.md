# 生产只读验证

`verify_production.py` 由 root 审核后通过已有 SSH 权限在生产运行；本子任务没有执行 SSH 或生产请求。

它只使用标准库、只读文件/systemd/proc 和匿名 HTTP GET，不导入 Flask app、配置模块、数据库或模型。不能 POST、创建学生会话或做真实学生任务。原始环境、`.env`、响应正文、Cookie 和重定向参数不会输出；仅输出开关布尔值、状态码、散列和检查布尔值。

部署前：

```bash
ssh root@47.110.45.193 'cd /root/apps/studytracker && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - --preflight' < docs/reviews/practice-web-joint-release-20261127/verify_production.py > docs/reviews/practice-web-joint-release-20261127/production-preflight.json
```

这一步不访问尚未上线的词汇接口。检查 service active/running、单 worker、跟踪文件干净、`gunicorn.conf.py` 为 5002/gthread/6 threads、开关配置关闭以及原有 `/login`、`/practice` 健康，`/tasks`、`/materials` 仍要求登录。只读进程环境里缺少开关时，按 `config.py` 的规则查看 `.env` 的同名 key，再回落默认 false；不输出任何其它环境 key。配置文件与进程环境只能说明可见配置，部署后 HTTP gate 才是实际运行开关的主证据。

部署后：

1. 从已经通过测试并提交的联合树生成 `{relative_path: sha256}` JSON，以标准 Base64 传入 `--manifest-b64`。至少包含 `static/js/practice_shell.js`、`static/js/practice_modes.js`、`static/js/practice_vocabulary_render.js`，建议包含全部本次产品文件。
2. 向同一 SSH/stdin 命令传入 `--expected-head FULL_COMMIT_HASH --manifest-b64 BASE64_JSON`，不传 `--preflight`。参数必须使用安全 shell 引号；哈希仅允许 40 位十六进制，Base64 仅有标准字符。
3. 输出存 `production-postdeploy.json`，退出码 0 且 `ok=true` 才通过。

后验同时检查 loopback 与 `https://studytracker.xin` 的：

- `GET /practice/vocabulary/tasks/0` 返回 403，`pv-boot` 为 blocked/feature_disabled，没有身份或 CSRF 数据。
- `GET /api/practice/vocabulary/tasks/0/state` 返回 403/feature_disabled/no-store。编号 0 不引用真实学生任务，且 gate 在身份/任务查询之前执行。
- 公开静态资产与已验 SHA 一致；`/practice` HTTP 200 并含当前任务/确认身份/主入口标记。
- 词汇 renderer 含“网页版背单词暂未开放，请在小程序完成。”文案。HTTP 静态验证不能冒称真正看过浏览器渲染。

限制：匿名 `/practice` 不会取得真实学生任务，因此不把它写成“所有学生词汇卡片均已实测不出现”；关闭 gate 的运行响应、已验列表服务和源码散列共同说明关闭发布状态。配置文件 gthread/6 threads 与实际单 worker/5002 HTTP 健康分别验证，脚本不启动第二个 gunicorn 或加载 app 来打印配置。输入法、物理长按、缩放、手机互切、教师/家长真实 UI 的待验项保持不变。

编写时已做本地语法检查，并用临时目录与 mock 替代全部 systemd/proc/HTTP 调用验证 preflight/postdeploy 成功分支、错误运行 gate 拒绝及 manifest 非法路径拒绝。此检查没有 SSH、网络、生产执行或 app 导入，不算生产验收。可再次单独检查脚本语法：

```bash
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -c 'import ast; from pathlib import Path; ast.parse(Path("docs/reviews/practice-web-joint-release-20261127/verify_production.py").read_text()); print("syntax OK")'
```
