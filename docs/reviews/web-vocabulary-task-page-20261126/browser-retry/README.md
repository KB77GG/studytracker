# 网页词汇：本机原生浏览器补验

2026-11-26，root 在权限恢复后通过 CUA 操作本机原生 Chrome、Safari，验证合并后的词汇产品（产品提交 `96ce82de`）。本报告依据 root 的实际操作记录、落盘截图/AX 状态，以及此目录的只读数据库回读和服务端审计。此前 `main-integration/browser/` 的两次未完成预检仍保留为历史事实，本轮已实际进入页面执行下列场景。

环境为 `serve_fixture.py` 的虚构学生、词书和内存 SQLite。订正/缩放使用本机 5111；网络故障/计时使用独立 `serve_retry_fixture.py` 的 5114。未访问生产，没有真实学生写入或微信上传。产品 JS、计时器及系统时钟均未改动或注入替代实现。音频是合成提示音，不能据此评价真实音质。

## 本轮结论及证据

| 场景 | 结论 | 已保存证据与限制 |
|---|---|---|
| Chrome 订正页刷新 | 通过 | root 在综合训练输错拼写后进入订正，刷新仍显示同题正确答案 `focus` 和第 1/2 次；`screenshots/chrome-native-125-correction.jpg`、`chrome-localhost-125-correction.jpg`。 |
| Safari 订正页刷新 | 通过 | 仍在 `focus` 订正页，第 1/2 次，没有跳过；`screenshots/safari-correction-refresh.jpg` 及同名 `.ax.txt`。 |
| Safari 按键保持后不连跳 | AX 状态未连跳；视觉与 A08 完整验收仍待 | 普通题 CUA `Return`、`durationMs:1500` 后停留反馈页，没有连续进入下一题（`screenshots/safari-normal-answer-held-enter.*`）；订正题输入正确答案后自然进入下一道未作答题（`safari-held-enter.*`），不能把该截图写成仍停在反馈页。Chrome 同样执行保持 1500ms，观察到停在首答错误反馈页。收尾查看两张 Safari held-enter JPEG，均为空白内容区；它们不能作为反馈页的视觉证据，AX 与截图的差异未查明。没有硬件键盘事件或 `event.repeat` 日志，不能称为真实物理长按的完整验证。 |
| Chrome 原生 125%／150% | 当前大窗口场景通过，A14 未完成 | Chrome 自身缩放提示显示 125%／150%，订正输入及主按钮可见；`screenshots/chrome-localhost-125-correction.jpg`、`chrome-localhost-150-correction.jpg`。尚未完成 1280、1440 两档明确宽度组合，不能把截图像素尺寸当 CSS 视口宽度。 |
| 保存后实际回包丢失 | 通过 | 5114 在答案成功提交后关闭该请求 socket，客户端约 1 秒后用同一 attempt 自动重试；首答记录仍只有一条。详见下节、`transport-drop-browser-stats.json`、`audit-5114.jsonl`。 |
| Chrome DevTools Offline 及恢复 | 已完成真实离线同步失败、草稿保留和恢复后提交；未触发离线 `answers` 请求 | Network 显示 `net::ERR_INTERNET_DISCONNECTED`，实际失败的是重新聚焦引发的 `sync`；第二轮先确认输入 `focus`，恢复后原样保留，再提交 `answers` 200。不能写成已观察到离线 `answers` 重发。 |
| 实际离页超过 10 分钟 | 通过 | 导航到 `about:blank`，真实离页 603.267 秒；返回完成任务后保存用时 95 秒、结算一条。完成页刷新后仍为同一结算和 95 秒，详见下节。 |

## 保存后回包丢失与幂等恢复

5114 writing task 2 的首答 attempt 为 `vocabulary-group:2:first:7`。产品已保存 `depend` 后，QA wrapper 在 **15:30:30.372 UTC** 对当前 Werkzeug socket 执行 shutdown/close，审计 `socket_error_types=[]`。这是连接关闭，没有用 HTTP 503 替代。

同一 attempt 的第二次成功处理出现在 **15:30:31.394 UTC**，约 1.022 秒后，符合客户端一次自动重试。两次处理与刷新后的统计均为 `attempt_record_count=1`、`attempt_record_ids=[1]`；`first_answer=depend`、`first_is_correct=true`，没有重复首答。刷新后的 UI 已到第二题“集中”。

证据：

- `audit-5114.jsonl`：`post_committed_response`、`transport_drop_before_http_reply`、`transport_socket_closed` 及后续同 attempt 请求。
- `transport-drop-browser-stats.json`：断开时的计数与刷新后的只读模型回读。
- `screenshots/chrome-transport-drop-after-save.jpg` / `.ax.txt`，`chrome-transport-drop-refresh.jpg` / `.ax.txt`。

审计中的 `status_code=200` 表示产品准备发送的成功响应，不代表那次被关闭连接的响应已到达浏览器。

## Offline：保留实际经过的路径

第一次尝试在打开 DevTools 并切 Offline 后才尝试输入，未先确认输入字段已产生 `input` 事件。恢复时输入为空，因此这一次不能用于判断草稿是否丢失，保留为 `screenshots/chrome-offline.jpg` / `.ax.txt`。

第二次先刷新 task 2、输入 `focus`，AX 明确显示 `Value: focus` 和“答案待提交”，然后切 Offline 并点击提交。Network 的 `sync` 请求报 `net::ERR_INTERNET_DISCONNECTED`；没有 `answers` 请求。原因是 `practice_vocabulary_events.js` 的 `window.focus` 会先调用 `Recovery.refresh()` 保存草稿并同步；同步期间输入只读、按钮 busy，失败后切换至重试页。它没有伪称答案已保存。

恢复 No throttling 后重试，仍是同一道题，AX 的输入值完整保留 `focus`。随后点击提交，实际 `answers` 返回 200、UI 回答正确；审计对应 `vocabulary-group:2:first:8`、记录 ID 8、该 attempt 计数 1（15:35:08.176 UTC）。本轮没有复现草稿丢失，不需要因第一轮不确定输入操作而修改产品。

证据：`screenshots/chrome-offline-confirmed-input-failure.jpg` / `.ax.txt`、`chrome-offline-draft-recovered.jpg` / `.ax.txt`，以及 `audit-5114.jsonl`。这验证的是实际离线时自动同步失败、恢复后草稿保留及正常提交；答案请求本身的保存后丢回包由上一节独立覆盖。

## 真实 10 分钟离页与结算刷新

root 将 reading task 1 导航到 `about:blank`：

- 离开：`2026-11-26T15:21:48.245Z`
- 返回：`2026-11-26T15:31:51.512Z`
- 实际间隔：**603.267 秒**，没有快进或注入时间。

返回后完成任务，首次 `/tasks/1/settle` 于 15:33:09.597 UTC 提交 `duration_seconds=95`，数据库 `Task.actual_seconds=95`、`settlement_count=1`。离页的约 10 分钟没有被并入用时。此合成任务产生 6 条作答事件、4 道计分首答；“记录数 6”不是重复计分。

完成页实际刷新后，`timer-after-refresh-stats.json` 再次读取为 95 秒、结算一条；与 `timer-settlement-stats.json` 的 settlement ID、时间和结果内容相同。证据：`screenshots/timer-wall-clock.json`、`timer-settlement-stats.json`、`timer-after-refresh-stats.json`、`screenshots/chrome-timer-complete-refresh.jpg` / `.ax.txt`。root 的最终 `browser-assertions.json` 也确认离页 603.267 秒、结算 95 秒/一条、Offline 恢复后的 `focus` 首答一条、丢回包 attempt 一条，全部断言通过；这些断言不涵盖上表列为未验的设备项目。

## 测试工具自身的验证

`selftest_retry_fixture.py` 是 HTTP 工具自测，不是浏览器验收。root 在 5115 成功执行后停止该测试服务；`selftest-result.json` 为 `ok=true`，实际连接丢失、同 attempt 一条、结算请求 17→777 秒但数据库仍 17 秒。其异常类实际记录为 `ProxyError`（ConnectionError 子类），不改写成其它异常。`selftest-audit-5115.jsonl`、`selftest-server-5115.log` 保留完整工具证据。

子 agent 更早的 5115 尝试被其残留沙箱拒绝 bind/connect，日志保留在带 `sandbox-failed` 的文件中；这些失败没有被当成通过。`selftest-static-and-readonly.json` 只证明语法及 GET stats 零 SQL 写入。更多复现说明见 `wrapper-notes.md`。

## 仍待完成

- Chrome 和 Safari **真实系统中文输入法**选词，以及真实硬件长按所要求的完整事件/行为验证；粘贴中文和 CUA 按键不冒充输入法。Safari 长按后的 AX 有页面状态而两张 JPEG 是空白，视觉需另行复核；订正刷新截图本身有完整页面。
- Chrome 原生 125%／150% 在明确 **1280、1440** 两档宽度下的完整检查。
- 真实手机／微信继续作答和订正中途互切。
- 老师、家长真实界面查看合成测试任务。
- 真实题库和语音质量；合成音不能替代。

`chrome-native-150-fixture-identity-missing.jpg` 保留了一次本机合成环境身份会话缺失的页面，原因未独立确认，不作为学习页缩放通过证据。另已确认 QA 的 `/__qa/start` 会清理并重建会话；重开其它合成任务后旧页可出现 CSRF 过期，刷新取得当前页面身份后继续验收。浏览器测试结果不扩大生产发布授权；全局产品开关仍保持默认关闭。

## 本机收尾

root 已回报完成清理：关闭本轮 Chrome 测试标签/独立窗口及 Safari 测试窗口，保留用户其它页面；Chrome 恢复 100%、No throttling，device toolbar 恢复原来的打开状态。5111、5114 服务均 Ctrl-C 退出 0，随后 `lsof` 确认 5111／5114／5115 无监听。

root 还核对了本候选 64 项产品/测试/CI SHA 与既有 manifest 全部一致。本轮增加的是本地浏览器验证工具、截图和记录，没有修改产品。文档同步范围限于 `browser-retry/` 与两份规范交接，目标为原词汇审查分支 `codex/web-vocabulary-task-page-20261126`；最终文档 SHA 及同步状态以 Git 为准。没有 main 推送、生产部署、配置或数据库变更，也没有小程序上传/提审/发布。

root 最后运行只读证据核对：

```text
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/web-vocabulary-task-page-20261126/browser-retry/verify_saved_evidence.py
```

`evidence-verification.json` 记录通过：从首次 sync 到结算的墙钟约 698.999 秒，其中实际离页 603.267 秒，数据库用时 95 秒；丢回包产生两个同 attempt 的 POST、仍对应同一条记录；Offline 恢复首答一条；64 项候选 SHA 一致。这是对已保存浏览器证据和源码散列的复核，不把读取日志冒充又运行了一次浏览器验收。
