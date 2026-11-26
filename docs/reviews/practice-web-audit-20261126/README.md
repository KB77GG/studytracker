# 刷题网页巡检脚本（2026-11-26）

对应审查：`docs/design/practice-web-audit-20261126.md`。脚本只读，不连生产，不写仓库数据。

```bash
# 1) 用真实 app.py + 合成 SQLite 启动（需 Flask、Flask-Login、Flask-SQLAlchemy、PyJWT、pypinyin、requests、certifi、websocket-client、openpyxl）
python docs/reviews/practice-web-audit-20261126/boot.py "$(pwd)" 5055 &
# 2) 巡检（需要 Node + Playwright Chromium）
cd docs/reviews/practice-web-audit-20261126
node crawl.js    # 目录页、做题页、链接检查、截图 → out/
node flows.js    # 进入与返回流程 → out/flows.json
node dialog.js   # 任务页退出确认框
node probe.js    # 身份表单可见性、无效复选框
node probe2.js   # 预览面板按钮
```

- 合成数据：学生“测试学生”、王老师、李助教；今日剑雅听力、剑雅阅读（`ielts10_test1_reading`）、精听各一条，明日阅读一条。
- 本地没有 mp3 和外部 CDN，音频 404 与 `ERR_TUNNEL_CONNECTION_FAILED` 不计为缺陷。
- `results.json` 是本次（f81a5e4a）的结果摘要，修复后可对照。
- `out/` 为输出目录，不要提交。
