# 合并后浏览器验收预检记录

2026-11-26，本子 agent 在 `/private/tmp/studytracker-web-vocabulary-20261126` 准备验证合并后的词汇页面。root 后续报告产品提交为 `96ce82de`。**两次尝试均未进入任务页，本轮浏览器验收没有执行。**

## 第一次：原生 Chrome 连接未返回

已读取 AGENTS、CLAUDE、两交接及现有 `serve_fixture.py`。`cua.getState()` 成功，确认存在 Chrome 扩展浏览器，原生 Chrome、Safari 和微信开发者工具在应用清单中。

随后调用 `cua.getApp('com.google.Chrome')` 没有返回原生 UI 状态。root 中断等待后，工具回报 `aborted by user after 366.6s`；实际中断来源是 **root agent**，不是用户拒绝权限。该轮没有启动服务、打开任务标签或写文件。

## 第二次：合成服务启动权限步骤未完成

root 指示改用 Chrome 扩展连接，先正规启动 localhost 合成服务。执行：

```text
cwd: /private/tmp/studytracker-web-vocabulary-20261126
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/web-vocabulary-task-page-20261126/serve_fixture.py
```

普通权限执行以 exit 1 结束，输出 `Operation not permitted`。随后同一命令以 `sandbox_permissions=require_escalated` 重试，申请绑定 `127.0.0.1:5111`，仅使用现有内存合成数据库。虽然外层 functions.exec 和 exec_command 都请求 1000ms yield，调用没有及时返回控制权，未得到 session ID、PID 或启动成功输出。root 再次中断后工具回报 `aborted by user after 209.1s`。这也不是用户拒绝或自动审批拒绝。

在中断后，root 明确要求停止浏览器与服务调用，仅写本记录。子 agent 未自行重查监听端口；root 随后回报已在 **2026-11-26 14:46:42 UTC** 执行 `lsof -nP -iTCP:5111 -sTCP:LISTEN`，exit 1、无输出，确认该时刻没有 5111 监听。这不是对未来状态的保证；没有获得成功 session/PID，也没有已确认需停止的服务进程。本轮没有尝试 Chrome 扩展标签连接。

## 保留待验

- 浏览器停在订正页刷新后仍保留订正状态、正确答案。
- 真实离开页面 10 分钟后返回并结算，离页时间不计入。
- Chrome、Safari 原生中文输入法和长按 Enter。
- 原生 125%／150% 缩放。
- 真断网提交；服务端已保存但网络回包丢失后的恢复。
- 手机／微信继续作答，以及订正期间互切。
- 老师和家长真实界面。

没有新浏览器断言、截图或真实设备通过结论；自动测试证据应单独引用。现有合成服务中的“保存后返回 503”故障不能冒充网络层丢包，本次也没有运行它。

本子 agent 只新增本文件及 `status.json`，未改产品、Git 状态、生产数据或配置，没有部署或小程序上传。规范交接由 root 统一更新。
