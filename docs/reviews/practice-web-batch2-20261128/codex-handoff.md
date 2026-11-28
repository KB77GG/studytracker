# 可直接交给 Codex 的接手指令

> 当前状态：第二批已提交、推送main并部署，生产43/43检查通过。最终补丁、29项源清单、命令、CI及发布结果见 [release/README.md](release/README.md)。下文为第一次本地交付存档；旧 batch2.patch / manifest.json / tar.gz 不包含发布前最后修复，请勿用于部署。

请接续 StudyTracker 网页刷题第二批导航优化。附件 `batch2.patch` 的基线是 main `9c211ee807fa1084017cbf8e8a05c1c9fe95de77`，依据仓库 `docs/design/practice-web-audit-20261126.md` 第二批 #6/#9/#12/#18。第一批已由 `docs/reviews/practice-web-joint-release-20261127/README.md` 确认部署。

先读目录链 AGENTS、CLAUDE、CODEX_HANDOFF、WORKLOG，核对 Git 实际状态；不要覆盖已有脏文件。fetch main，在隔离 worktree 应用附件（先 `git apply --check`），main 若推进需先审查差异。此补丁尚未提交或发布，不能把旧主树中的内容当成已经拥有它。

实现范围：共享工作台顶栏，品牌不再带 module-back；目录唯一来源返回及多层返回/环路保护；练习中心无自返回；精听入口去重复任务与最近记录区，保留身份和管理功能；页面 h1/书名 h2/title。教师后台和课堂权限保持。不要修改判分、计时、保存逻辑，不提前实施第三批网格/配色/水印/CDN 改版。

运行 `docs/reviews/practice-web-batch2-20261128/run_checks.py python`、`run_checks.py node`、`verify_scope.py`。Python 使用已安装项目依赖的解释器，内部 runner 注入临时配置和 SQLite，不读取项目 .env/app.db。新路由测试已登记 CI，但尚无远端 CI 结果。

优先补浏览器验收：先用既有 `docs/reviews/practice-web-batch1-20261126/serve_fixture.py <本次树绝对路径> 5116` 启动私有合成服务，再设置 `BASE=http://127.0.0.1:5116`、`OUT=docs/reviews/practice-web-batch2-20261128/browser` 运行 `node docs/reviews/practice-web-audit-20261126/flows.js`。Playwright/Chromium 路径按本机配置。脚本复用原流程并增加目录返回、品牌、身份、教师、窄屏检查；上一轮因 bind 沙箱限制且提权未完成，未真正执行浏览器流程，不要把语法检查或 Node DOM mock 标成浏览器通过。

核对每页返回文字与落点，以及“阅读冲刺→剑雅阅读→做题→剑雅阅读→冲刺”和目录跨科重访无循环；检查匿名/姓名确认/切换/学生账号/课堂/教师视角。缺音频和外部 CDN 失败单列环境限制，不通过放宽导航断言制造通过结果。结果保存新报告，不覆盖 11月26/27 原证据。

最后更新两份规范交接，明确本机/已提交/已推送/已部署状态。没有用户新授权不得 commit、push main、部署、写生产数据库或发布小程序。
