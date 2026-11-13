# `.15` 网页核图门禁独立复核

范围：`/private/tmp/studytracker-iwa-prompt15-review-20261113`，HEAD `652450ca`；旧源码树 `/private/tmp/studytracker-iwa-prompt14-review-20261113`，HEAD `cd82fc1b`。产品代码只读。所有调用是 FakeClient / StaticVision，全部数据库、上传文件和试用码均在独立临时目录；未读取真实 Key、私有配置或试用库，未连接任何服务器，未更改服务。

## 结论

新提交的主路径可用：等待核对前没有模型请求，核对改正后三个生成都使用改正读数；跳过时三种输入都不带图表读数，TA 和总分不可评。owner、CSRF、等待期间再生成、等待后重启、重复确认、两请求并发确认、原始读数留存及额度检查等 **38/38** 通过。

仍有 **1 个 P2（已有记录迁移）和 1 个 P3（接口类型检查）**。当前 Mac 试用库若仍是空作文库，P2 不影响它的现存记录；这不是新提交路径错误。但不能据此宣称一般旧库升级和改正操作已安全。

### WEB-P2-1：旧记录确认改正后仍沿用旧评分，页面却标作采用改正读数

- 入口：`tools/ielts_writing_ai/web.py:455` 写入确认和新读数，`:457` 仅启动 `queued` 记录；`_generation_view` 的 `:360` 返回原 `ready` 结果。
- 触发：用真正 `.14` 源码生成一份带图且三个结果均 ready 的合成记录，再由 `.15` 打开同一临时数据库。迁移新增 `image_check=NULL` 后，页面数据 `awaiting_check=true`，但原 TA/总分仍展示。把读数 `140` 改成 `160`，点确认。
- 实测：POST **202**、`edited=true`、读数已改正；**0 次新模型请求**，三个 generation ID 和评价结果逐字不变，仍是 `.14` 结果、总分 5.0。
- 用户可见的问题：前端 `static/iwa.js:388` 将新读数标成“已核对（按你的改正），用于评 Task Achievement”，`:411` 提示“开始批改”，但旧评价/精修/改写未基于新读数生成。`renderPanel` 只在 queued 时显示等待提示（`:465` 附近），旧 ready 分数仍展示。
- 建议：为生成结果绑定它实际采用的图表读数版本；旧结果保持历史身份，不能在修正后冒充新结果。可以要求明确重新生成并说明额度，也可禁止对已完成历史记录使用“确认后开始批改”入口，另外提供新评价流程。不要默默免费或重复调用，也不要只换标签而不处理旧结果。
- 限制：本探针只证明结果来源与页面读数错配，没有声称该数值改正必然使总分变化。

### WEB-P3-1：新接口对非对象 JSON、非字符串 description 返回 500

- 位置：`tools/ielts_writing_ai/web.py:451–471`。`get_json` 结果直接调用 `.get`；`description` 直接传入字符串归一化函数。
- 实测：JSON `['confirm']`、`1`、`{'action':'confirm','description':['x']}`、`{'action':'confirm','description':7}`，四例都是 **500**。未确认、未改变读数、未发模型请求，所以影响限于接口健壮性。
- 建议：先检查 payload 是对象、description 是字符串，再统一 422；正常浏览器提交不触发此项。

## 可复现命令

在 `/Users/zhouxin/Desktop/studytracker` 执行：

```bash
.venv/bin/python -B docs/design/iwa-prompt15-review-20261113/web/web_gate_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt15-review-20261113 \
  --old-repo /private/tmp/studytracker-iwa-prompt14-review-20261113 \
  --out docs/design/iwa-prompt15-review-20261113/web/web-gate-evidence.json
```

当前 exit **1**：38 项正常路径检查均通过，但 findings 含上述两处；不是 38 项失败。JSON 只存合成场景、状态和数字，不含学生材料或访问凭据。

```bash
.venv/bin/python -m ruff check docs/design/iwa-prompt15-review-20261113/web/web_gate_probe.py
.venv/bin/python -m black --check docs/design/iwa-prompt15-review-20261113/web/web_gate_probe.py
```

代码检查通过。本专项未运行浏览器、未评估真实视觉准确性；页面结论来自实际 API 数据和当前渲染函数路径。无 commit/push/deploy，交接由主审合并。
