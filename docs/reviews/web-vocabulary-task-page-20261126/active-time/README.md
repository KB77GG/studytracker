# 网页词汇：累计实际学习时间

2026-11-26，用户明确选择可见页面内的活跃时间，替代原“首次进入到结算”的墙钟时间。当前代码位于 `/private/tmp/studytracker-web-vocabulary-20261126`，分支 `codex/web-vocabulary-task-page-20261126`；本轮起点为已推送的 `fc3b049a`。本地代码与自动验证已完成，将沿既有授权仅同步该词汇审查分支并跑 CI；最终提交和 CI 结果在收尾补记。尚未合并或部署。

## 最终口径

- 页面可见，且最近 5 分钟内有真实输入、键盘、指针或滚轮操作时才累计。进入有效学习页、从隐藏状态返回视为一次活动。
- 切到后台、正常离页立即暂停；可见但无操作最多再计 5 分钟。再次操作从当前时刻继续，不补空闲或离页时间。
- 自动同步、重绘、程序 focus/scroll 和纯 keydown repeat 事件不刷新活动期限。保存失败、只读、未开放、阻止访问、结果及结算等待状态停计。
- 任务用时包含该任务内的复习活动；复习结算只计对应 session。按学生、任务和复习 session 隔离。
- 每个页面保存自己的已发生时段，结算取同一浏览器各标签页时段的并集；重叠的 1 分钟只算 1 分钟。
- 正常每 5 秒落盘一次，离页与结算立即保存。刷新保留累计值。首次结算快照冻结，重试不增加等待时间；明确 incomplete 后仅从恢复时刻继续，已完成值不变。

因此“17:00 学 10 分钟，关闭页面，22:00 再学 15 分钟”累计 25 分钟。它仍是带 5 分钟空闲宽限的学习时间估算，不是逐秒证明正在学习。

## 兼容与边界

旧 v1 墙钟记录无法还原活跃时长，未结算任务从进入本版本开始累计，旧记录不删除、不伪转换。旧 journal 已发送请求保持原 payload 重放；服务端首次结算及页面显示结果仍是权威值，不导入为新版活跃区间，也不重算历史成绩。

存储被禁用时退到当前页内存，不能保证跨刷新或标签页保存。正常 5 秒采样下异常关闭可能丢最后未持久化段；浏览器冻结或计时器延迟时不能保证损失绝对不超过 5 秒。读取其他仍活动标签页时也可能少计其尚未落盘片段。系统时间回退保守处理，不补偿负数或异常时段。不跨浏览器或设备合并。

## 实现与验证

5 个产品文件、2 个测试文件和 1 个 CI 文件变化；完整 36 文件 SHA 清单见 `manifest.json`（8 个标为本轮变化）。新增独立 `practice_vocabulary_timing.js`；传输层保留请求、音频和存储能力；页面和事件模块接入生命周期。后端、保存接口、评分、模型及小程序没有改动。

- Node 81/81：`node --test tests/test_practice_vocabulary_core.js tests/test_practice_vocabulary_timing.js tests/test_practice_task_lists.js tests/test_practice_shell.js tests/test_vocabulary_feedback.js`。其中 core 33 + 新计时 21；原 6 个墙钟专用测试迁移为活跃口径，原 3 个页面级刷新/结算测试保留。日志 `node-regression.log`，精确命令在 `node-static-commands.json`。
- Python 3.13、原生 3.10 各 47/47：`-m unittest tests.test_practice_vocabulary_routes tests.test_vocabulary_task_submission tests.test_practice_vocabulary_web -v`。全部内存合成数据库，未加 UTC 兼容别名；本轮后端文件与审查基线相同。解释器、argv、用时与日志在 `python-commands.json`。
- 独立公开 API / 事件接线探针 16/16：`node docs/reviews/web-vocabulary-task-page-20261126/active-time/independent_timing_probe.js`，结果 `independent-timing-probe.json`，结论 `independent-review.md`。已修复复核发现的完成值覆盖和超出窗口跨度的损坏冻结值问题。
- 4 个产品 JS 语法、Jinja 模板解析、CI YAML 解析和 `git diff --check` 通过。CI 已登记独立计时测试。

本轮浏览器补验没有执行：合成服务普通启动被沙箱拒绝，提权启动请求未完成；root 中断等待后确认 5111 无监听。详见 `browser-status.json`。实际 Jinja 渲染与 9 个脚本路径/加载顺序检查通过，见 `template-assets.json`，但这不是浏览器运行证据。

上述时序探针使用注入时间和事件，不冒充 Chrome/Safari 原生输入法、真断网、手机互切或原生缩放验收。原开启前设备清单仍保留。

## 联合发布安排

用户要求先完成词汇页，再与网页批 1 一起部署。批 1 仍在 `/private/tmp/studytracker-practice-web-batch1-20261126`，未合入本分支；共享 `origin/main` 已有考前冲刺 `79388e26`，也未合入本候选。共同发布前须整合两批及最新 main，保留双方 CI 与交接记录。

本轮不改全局开关，`PRACTICE_VOCABULARY_WEB_ENABLED` 仍默认 false；未访问生产、改配置或数据、触发部署或微信发布。任务分支同步与 CI 的最终事实以本报告收尾记录和规范交接为准。
