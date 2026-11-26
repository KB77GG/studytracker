# A02：原有网页任务列表的历史基线契约

`practice_task_list_f81a5e4.json` 的预期结果来自真实历史提交
`f81a5e4a4d81282eb67b994a4cfcc5574fb78747`，不是从当前实现的关闭开关状态复制。
生成器用 `git archive` 将该提交的 Python 源码解包到临时目录，再启动独立进程加载历史
`app.py`，实际请求 `GET /api/practice/tasks`。历史 checkout、主工作树和生产服务均不修改。

`practice_task_list_a02.json` 固定北京时间 2026-11-26 12:00，提供全合成的三名用户、11 项任务、
公开的测试令牌和冻结的专项/写作快照。接口应输出 8 项任务：助教和老师各 4 项，包含听力、
阅读、题型专项和写作；同时覆盖未来、截止、今日、完成日期状态，以及未开始、进行中、
已提交、已完成工作流。取消任务、其他学生任务、超出历史窗口的已完成任务应被过滤。

基线与当前代码使用完全相同的 fixture 和捕获脚本；只替换时钟，不替换查询、列表函数、
URL 生成函数或快照解析函数。数据库仅用独立的 `sqlite:///:memory:`，上传目录为临时目录，
导入前注入私有测试配置，所有 socket 连接/DNS 调用均被禁止。没有读取 `.env` 或真实学生数据。
捕获 JSON 不包含本机路径、随机值或真实凭据；令牌全部是显式的公开合成值。

在拥有上述 Git 对象的仓库根重新生成历史快照：

```bash
python tests/fixtures/practice_task_list_baseline.py regenerate --repo .
```

仅捕获指定源码目录当前行为，输出完整 HTTP JSON：

```bash
python tests/fixtures/practice_task_list_baseline.py capture --repo . --flag off
python tests/fixtures/practice_task_list_baseline.py capture --repo . --flag on
```

回归命令（Python 3.10 与 3.13 均可原生运行）：

```bash
python -m unittest tests.test_practice_vocabulary_task_list -v
```

CI 不需要历史 Git 对象或网络：它校验 fixture/捕获脚本 SHA-256 和固定历史提交号，然后分别在
独立进程、全新内存库中捕获当前 off/on 行为；比较响应的所有字段、每组任务数量和顺序，
不会丢弃或归一化任何字段。快照另存 7 个关键历史源码文件 SHA-256，可对照固定 Git 对象复核。

本契约验证任务列表 HTTP 数据；它不证明浏览器实际跳转、旧任务详情页或真实设备交互。
修改 fixture/捕获脚本时必须从固定历史提交重新生成快照；不能用当前代码更新预期值来消除回归。
