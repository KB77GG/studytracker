# 词汇审查分支合入 main 的验证记录

2026-11-26。工作树 `/private/tmp/studytracker-web-vocabulary-20261126`，分支 `codex/web-vocabulary-task-page-20261126`。起点 `f6f0f10445c4746bdbd1153f46db2411a0bda577` clean；本轮 fresh fetch 的 main 为 `f5b06cc3cb44fa1f77720ca771bde3134c83a71d`，共同基线 f81a5e4a。用户要求先合入该审查分支并推送跑 CI，联合部署仍暂缓。

## 合并结果

仅 `.github/workflows/ci.yml`、`docs/CODEX_HANDOFF.md`、`docs/WORKLOG.md` 发生文本冲突。CI 保留词汇 pytest 依赖及 main 新增冲刺 HTTP 步骤，两交接双方条目完整保留。产品代码自动合并，无本轮手工修改，词汇计时/事件/页面源码保持 f6f0f104。

独立复核在 `merge-review.md`：app.py/miniprogram.py 全函数 AST 与双方改动并集相符，新增 imports 无遗漏；web_practice_tasks.py 与 main 字节相同；CI 双方所有步骤及命令顺序保留；两交接全部非空行按原顺序保留。64 产品/测试/CI 文件 SHA 在 `manifest.json`。

## 本地验证

精确 argv、cwd、环境差异、耗时和 stdout/stderr 日志均在本目录；复现入口 `run_regressions.py`。

- `/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/web-vocabulary-task-page-20261126/main-integration/run_regressions.py py313`：574 unittest / 20 pytest 日期测试全通过。
- 同一 runner 参数 `py310-project`：Python 3.10.20 下相同 574 / 20 全通过。解释器为 `/Users/zhouxin/Desktop/studytracker/tmp/web-vocab-py310-20261126/bin/python`。
- 同一 runner 参数 `node`：9 个测试文件，111/111 通过；包括词汇 81 与冲刺/听力/模考 30。
- 40 个 Python 文件原生 3.10 py_compile、CI YAML 解析、runner Ruff、git diff 检查通过。

3.10 的两个初次环境失败完整保留：临时 venv 路径被冲刺 runner 的既有稳定路径检查拒绝（5 errors）；直接使用稳定 base interpreter 加 PYTHONPATH 后，1 个刻意清理 PYTHONPATH 的子进程依赖测试失败。最终在旧资料树忽略的 tmp 目录创建本地测试 venv，并用本 venv 的 .pth 复用匹配版本的既有依赖；不改产品路径检查、不 patch sys.executable、没有联网安装。创建命令和路径见 `py310-environment.json`，失败日志未覆盖。3.10 全套仍沿用既有 `run_compat_tests.py` 为旧测试 datetime.UTC 提供进程内标准别名；不能称未经兼容入口的全套原生运行。产品原生编译另行通过。

所有测试使用合成/临时数据库和 mock，不访问生产或修改真实学生任务；没有执行真实采集发布/会话续期脚本。

## 浏览器与剩余事项

本轮没有进入任务页，没有浏览器验收通过项。第一次原生 `cua.getApp('com.google.Chrome')` 未返回，root 中断 366.6 秒等待。第二次准备经 Chrome 扩展访问本机合成服务：普通启动遇 Operation not permitted，正规提权启动调用也未返回，root 在 209.1 秒后中断；尚未执行扩展标签连接。两次工具的 aborted by user 通用标签都不代表用户拒绝。root 于 14:46:42 UTC 用 `lsof -nP -iTCP:5111 -sTCP:LISTEN` 确认当时无监听（exit1/无输出）；没有已确认启动的服务 PID/session。详见 `browser/status.json` 和 README，所有原生/真设备项目保留未验。

Chrome/Safari 原生中文输入法、长按 Enter、原生 125%/150% 缩放、订正刷新、真断网及保存成功后丢响应、真实微信互切、离页 10 分钟后计时、老师/家长界面，均须以实际执行证据判断，不能以 Node 或上述合并测试代替。

用户转述的计时缓存累积问题保留为非阻断后续项。本轮不改已接受的计时逻辑；后续清理必须同时验证完成标记、首次结算重放、旧标签页不会重新写回已完成时段，不能直接删掉整组键而丢失冻结值。

## 批 1 与发布状态

批1仍在 `/private/tmp/studytracker-practice-web-batch1-20261126`，`codex/practice-web-batch1-20261126@f81a5e4a`，14 产品/测试/CI SHA 匹配，未合入本分支、未commit/push。与本候选重叠3文件：CI、practice/index_content、listening/test_practice。临时 `git merge-file -p` 预演均 exit0，但未实际联合集成/验收；不能仅凭同一文件判断必然冲突，也不能据文本预演称联合可上线。批1提交时须带 CI 引用的报告 runner。

合并提交 `96ce82dec4401407d03e32d8eeadf378a824ac56` 已推词汇审查分支。[CI 45842043031](https://github.com/KB77GG/studytracker/actions/runs/45842043031) overall success，test、task-planner、account-provisioning 三个业务作业全部成功；既有非阻断 advisory lint 仍失败，format skipped。完整状态与精确命令见 ci.json / ci-evidence.json。最终证据和交接以独立 `[skip ci]` 文档提交共享，最终文档HEAD以Git核对；产品与已测合并提交一致。本轮不推main、不部署、不改 `PRACTICE_VOCABULARY_WEB_ENABLED` 默认 false、不访问生产或微信上传/提审/发布。旧资料树仍 main@6ded77d2，保留原8M/27顶层U；本轮只更新两交接及忽略的测试 venv。批1原13M/7顶层U保持，收尾仅两交接追加。发布前仍需完成设备门槛、整合批1并取得后续发布授权。

收尾交接更新三个工作树各自的 `docs/CODEX_HANDOFF.md` 与 `docs/WORKLOG.md`。本词汇树随审查分支共享；旧资料树和批1的两交接只在本机，批1代码仍未提交。最终64项候选SHA和批1原14项SHA均匹配，见final-product-audit.json。
