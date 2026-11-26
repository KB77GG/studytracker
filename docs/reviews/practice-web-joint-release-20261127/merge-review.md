# 联合候选独立合并审查

2026-11-27，子 agent 对 root 准备的联合树做只读审查。结论：**未发现阻挡“词汇默认关闭”部署的合并缺陷**。本结论不代表剩余真设备验收通过，也不替代 root 正在执行的联合测试、CI 和生产验收。

## 审查基线

- 联合树：`/private/tmp/studytracker-practice-web-joint-release-20261127`，分支 `codex/practice-web-joint-release-20261127`。
- fresh main：`f5b06cc3cb44fa1f77720ca771bde3134c83a71d`。
- 词汇：`0ab901e843ca01a7bc5cc8ffc78e11b372feaadb`，已包含上述 main。审查时联合树 HEAD 仍是该词汇文档提交，批 1 变更已应用，尚未形成联合提交。
- 批 1 来源：`/private/tmp/studytracker-practice-web-batch1-20261126`，基线 `f81a5e4a4d81282eb67b994a4cfcc5574fb78747`。该树原有 13M/7 顶层 U 保持；其 manifest 的 14 项 SHA 全部与来源文件匹配。
- 已核对 AGENTS/CLAUDE/两份交接；联合树这些文件与词汇树一致。没有改源树或产品文件，没有 commit/push/部署动作。仅新增本审查文件供 root 汇总交接。

## 三方结果

初次审查时，批 1 的 14 项中，联合树有 11 项与批 1 最终文件逐字节一致；词汇 main-integration 的 64 项中，有 61 项逐字节一致。两组差异都恰好是下列三个需同时保留的文件。随后 root 为真实组合修复了一个旧测试窗口 mock，产品三方结果不变；该测试差异在下节单列。

| 文件 | 核对结果 |
|---|---|
| `.github/workflows/ci.yml` | 批 1 新增的 3 条 Node 文件入口和私有 SQLite runner 步骤全部保留；词汇输入/计时、身份/结算步骤，以及 main 的冲刺认证/布置/组卷步骤全部保留。Node 20 与 pytest 依赖仍在。五个相关命名步骤各出现一次。runner 本身已复制到候选，CI 不会引用仅本机文件。 |
| `templates/practice/index_content.html` | 相对批 1 仅多词汇的 `pageshow` 持久页面恢复刷新任务列表逻辑。学生隐藏老师控件、`[hidden]` 兜底、姓名身份动态更新仍在；词汇返回列表后的刷新仍在。 |
| `templates/listening/test_practice.html` | 相对批 1 的差异恰好是 main 的 `sectionAudioUrl`、冲刺本地图片白名单与两处音频 URL 使用；与 `f81a5e4a..f5b06cc3` 的原修改逐块对应。批 1 的退出判断、恢复提示与保存时间逻辑没有覆盖这些冲刺兼容。 |

`static/js/practice_shell.js` 不是两候选之间的内容冲突：词汇候选未改它，联合树逐字节采用已验收的批 1 版本。词汇 `Page` 只使用该 shell 的返回导航和 `initialSaved: true`；新的“已同步”初始提示兼容词汇自己的 `view.status`，没有切换其请求、草稿、计时或结算协议。

### 联合测试兼容修复

root 首次 Node 组合运行 197 项中 5 项失败，原因是批 1 的 `tests/test_practice_center_identity.js` 模拟窗口缺少词汇新 `pageshow` 逻辑所调用的 `addEventListener`。已只读审查 root 的修复：新增 `windowListeners` 保存回调，保留全部原身份断言；新增一项调用真实模板脚本监听器的行为测试，验证非 persisted 不刷新、已验证学生 persisted 时刷新一次、切换回 guest 后不再刷新。没有删除 `pageshow` 产品代码、跳过测试或放宽断言。该修改合理且覆盖了本次组合独有的交互。

root 回报复跑 Node 198/198、独立精听退出 9/9 与旧拼写队列通过；本审查核对了测试代码与 CI 登记，并未另跑一遍同套测试。最终日志由 root 统一保存。批 1 manifest 的第 4 个预期差异现为该测试文件，因此不能再声称最终 14 项只有三个散列差异。

### 模考关闭完整性检查的历史模板快照

root 的 Python 574 项初跑唯一失败为 `test_exam_integrity_e2e.test_default_off_four_templates_are_byte_identical_to_plan_baseline` 的旧模板 SHA。独立逐块复核相对 `f5b06cc3` 的听力/阅读模板：修改仅为批 1 已批准的保存提示、恢复状态、退出文案/guard；阅读另包含既定 Reading Study readiness gate。两个完整性 include 均原样且各一处，`exam/_integrity_guard.html`、`static/js/exam_guard.js`、完整性服务/路由及 process/writing 模板均无差异。

因此可将这两个 **已审查的上游模板快照**更新为下值，保留原 SHA 断言、四页面遍历及“关闭时实际响应等于去掉 include 后模板渲染”的字节相等断言，不删除或跳过测试：

- listening 去 include SHA：`adb2382bcad0be14e5c4e1d1ec991017c516ed71f5d86d1ab840e264459f89cc`
- reading 去 include SHA：`5d998b3c9ff56cd6f28f738eb4205d97c1cfe7135c198a483f13e24a8b7c1e81`

旧 main 去 include SHA 已独立重算为原断言的 `aad8dda7…` / `498e7025…`，确认是授权模板修改使快照过期；不能把此更新写成完整性行为修复。root 负责修改测试注释、重新运行并记录结果，本审查不改产品或测试。

## 行为审查

- 批 1 保持 8 产品、5 测试、1 CI 的原范围，不混入后两批导航/视觉改版。
- 默认无作答任务不弹退出确认；dirty/在途保存/已启动模考仍确认，保存失败不离开。精听未提交文字明确提示可能丢失；首答在途或保存不确定通过 `beforeLeave` 再次拦截，不盲目重发首答。此机制有模板级 guard 与独立反例测试。
- `markRestored` 不清除新 dirty、在途保存或错误状态。只有实际保存成功才显示当前保存时间；历史记录读取使用独立提示。
- Reading Study 入口同时受模式能力与解析 readiness 控制；无解析直链重定向只构造本站对应题目的路径，参数白名单保留任务/导航上下文，不采用调用者的任意返回地址。
- 词汇配置仍通过 `_env_bool(..., default=False)`；API `before_request` 先执行 `_enabled()`，再身份/数据访问。页面自己的启用检查保留。此次合并未改变关开关时的保护顺序。
- 部署 workflow 未改，仍只由 main push 触发。生产运行约束与开关实际值须由 root 部署后读取，不以源码默认值推断生产环境值。

## 本审查执行的核对

- 来源 manifest 14 项 SHA 匹配；联合树对两份 manifest 的差异集合如上。
- 逐块比较：`git diff HEAD -- .github/workflows/ci.yml templates/practice/index_content.html static/js/practice_shell.js`；`git diff --no-index` 比较批 1 与联合树三个共同文件；`git diff f81a5e4a..f5b06cc3 -- templates/listening/test_practice.html` 核对 main 部分。
- `ruby -e 'require "yaml"; d = YAML.load_file(".github/workflows/ci.yml"); puts d.fetch("jobs").keys'` 成功解析四个 CI jobs。
- Python 文本/存在性断言：五个相关 CI 步骤各存在一次，新增 Node 文件与私有 runner 路径均真实存在。
- 首次尝试本地 `.venv` 的 PyYAML 解析因缺少 `yaml` 包失败；未安装依赖或改代码，改用已安装 Ruby YAML 解析通过。这是审查工具环境差异，不计为产品测试失败。

## 合并后验证要求

由 root 在联合树执行，结果应写本目录正式验证记录；本审查没有重复运行业务测试：

1. 词汇 main-integration 回归及默认关闭接口/零 SQL、A02 历史 payload 对比；保留原 3.10 兼容测试入口限制说明。
2. 批 1 私有 SQLite runner 的 9 模块（原 57 项，命令见批 1 `validation/python-regression-commands.json`），覆盖学生/老师角色、Reading Study 跳转、目录、导航和老师权限；使用 3.13 与原生 3.10。
3. Node 合并批 1 的 10 文件与词汇 core/timing、冲刺 picker 等相关套件；不以旧分支测试冒充联合候选结果。
4. `node docs/reviews/practice-web-batch1-20261126/independent_exit_probe.js`（原 9 项）以及部署 workflow 的 `node tests/test_dictation_spell_queue.js`。
5. 联合候选远端 CI 成功后再推 main 部署；生产只读检查版本、服务/worker、5002、默认关接口和词汇入口隐藏。

真实系统拼音/完整物理长按、指定宽度原生缩放、手机互切、老师家长真实界面等旧待验项仍保留。此次部署授权允许按既定默认关闭步骤上线代码，不应把这些待验项目改成通过或顺带打开词汇开关。
