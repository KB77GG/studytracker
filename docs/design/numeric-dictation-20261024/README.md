# 数字听写：后台已部署，小程序待另一台电脑发布

## 当前状态

用户确认后，后台业务提交 `1cac6c0ce3544dbc7d982f24885da652ad29725c` 从 `codex/numeric-dictation-release` 非强制原子推送 main 和任务分支。仅 5 个后台运行文件及 4 个测试文件，不包含小程序运行文件。生产实际 HEAD 和五文件 SHA 与候选一致。

- [生产部署 40105560898](https://github.com/KB77GG/studytracker/actions/runs/40105560898) 成功；[CI 40105560862](https://github.com/KB77GG/studytracker/actions/runs/40105560862) / [CI 40105560891](https://github.com/KB77GG/studytracker/actions/runs/40105560891) 成功。
- `studytracker.xin` / `/root/apps/studytracker` / 5002，服务北京时间 2026-10-24 23:08:23 起 active，NRestarts=0，单 worker/gthread/6 threads，login 200；抽样后 warning/error journal 无条目。
- 备份 `/root/backups/studytracker/numeric-dictation-20261024T150621.422224Z/app.db`，212156416 字节，SHA-256 `e6bf28a400000b588843ba2b504483d5c9bb8651f061f8a4382bedfa8d0b59f3`，quick_check=ok。只在服务器保存数据库，不将备份带入 Git。
- 没有业务 schema 迁移，没有创建学生任务、作答或推送；词书和词条、task 表与备份摘要相同。服务在线期间有 3 条其他词库的真实新作答，相关 mastery/flow/question 状态相应变化；旧记录无删除，冻结题目/答案/序号不变。不能声称整个活跃数据库逐字未变化。

## 学习链路验证

原英文 parser 不支持三本 142 条含纯数字 token 的答案（127/12/3），其中 91 条也没有释义。现在数字类产生 `audio_form_recall`，无释义只跳过词义题；阅读/写作/综合目标也仅为数字子集改用听写。普通含数字英文、原词条和已有任务快照保持原行为。明确日期与数值只接受确定等价答案，电话保留前导零；16 条特殊格式按原文保守匹配。

发布目录 `/Users/zhouxin/Documents/Codex/2026-10-24/task-2/numeric-dictation-release` 从主线 `99dc19ad` 创建；候选目录 `numeric-dictation-fix` 未作为脏树直接推送。完整本地组合 **205 passed / 206 subtests passed**，部署 spell queue 门禁通过；生产 Python 3.10.12 运行 `tests.test_vocabulary_numeric_learning`、`tests.test_vocabulary_numeric_review` **20 tests OK**，仅使用内存 SQLite。四目标数字-only、部分选词、混合任务、前导零/日期/金额/小数、future-due 兜底及旧已开始任务保持不变均被覆盖。

生产代码读取真实 book 199/200/201，2511 条全部能构建听写题，旧过滤 142 条全部覆盖；总数字题 156 条，另外 14 条为原英文 parser 能处理的明确日期。没有用真实学生账号创建/提交测试任务。助教任务学习的后台链路和既有客户端模式契约已验证，尚未做微信真机端到端提交。

## 真实音频证据

7 条真实音频 HTTP200、MP3 完整解码、正常本机 `afplay` 播放均成功。6 条来自本次新词库，取样前新规则缓存不存在，取样后新增 DashScope 缓存且 SHA 与 HTTP 内容相同；金额样例使用已绑定录音，不能说它由本次新规则重新生成。未全库预热、未新增服务或密钥。

| 原词条 | 本机离线 Whisper small 转写 |
|---|---|
| 463 Beacon | 463 beacon |
| June 27 | June 27th |
| 7:00 | 7 o'clock |
| 0217856361 | 0217856361 |
| 16.50 | 16.50 |
| 1.3% | 1.3% |
| 14 pounds（既有绑定录音） | 14 pounds. |

这里区分三层：获取/生成成功、真实解码与播放器完成、工具转写内容吻合。**没有人工主观听感评价，ASR 不能代替人工。** 初次 Python 请求因本机 CA 包缺失失败，改系统 curl 正常证书验证成功；没有禁用 TLS。初次沙盒播放器无法建 AudioQueue，使用正常本机音频权限后七项均 exit0；未改安全配置。结构化证据见 [deployment-evidence.json](deployment-evidence.json)。原 MP3 及分层报告在本机 `task-2/prepared/numeric-audio/`，未提交音频二进制。

## 后天小程序发布交接

用户明确：小程序在**另一台电脑桌面**，后天再发布。本次不上传、提审或发布小程序；该电脑精确目录和当前 Git 状态须现场核对，不猜路径，不覆盖脏修改。

旧学习页按 `mode=audio_to_en` 显示原生文本输入，并使用冻结 `prompt.audio_tts_url`，能提交数字与标点；更新前仍可能显示“英文拼写”的旧提示。自主复习入口有独立的现存客户端错误：

- 文件：`miniprogram/pages/student/vocabulary-review/index.js`，基线第 175 行声明 `const attemptId = ...`，第 187 行 POST `data` 却写未定义变量简写 `attempt_id`。
- 复现：进入学生自主复习，领取/打开当前题，输入一个非空答案，点击提交；在 `request(...)` 参数求值阶段抛 `ReferenceError: attempt_id is not defined`，网络请求尚未发出，`submitting` 已置 true。此错误不只影响数字题。
- 最小修复：把 `attempt_id,` 改为 `attempt_id: attemptId,`。另两页 WXML 显示 numeric 的公开 instruction/input_hint，保留原生文本输入，不新增键盘或权限。
- 当前线上微信包的实际源码版本未核；若与上述基线一致，自主复习提交仍会受阻。**后台部署不能修复这一客户端错误，不能宣称自主复习全入口已可用。**

便携增量 [client-pending.patch](client-pending.patch) 包含上述 3 个客户端文件及 `tests/test_vocabulary_numeric_client.js`，在本发布基线 `git apply --check` 通过，尚未应用到本发布树/线上小程序。另一台电脑先取此交接，再从真实小程序仓库根目录：

```sh
git status --short --branch
git apply --check /实际位置/client-pending.patch
# 无冲突且确认现有改动后，才应用；失败不得强制覆盖
git apply /实际位置/client-pending.patch
node --test tests/test_vocabulary_numeric_client.js tests/test_vocabulary_feedback.js tests/test_miniprogram_dictation_input_policy.test.js
```

此组合在原候选 **11 passed / 0 failed**；两页 WXML 官方编译通过。然后在微信开发者工具实际目标目录上传、提审、发布，并真机验学习/自主复习、错误答案及恢复。后端已先上线，无需再次给学生推任务。

## 兼容回滚

不得完整退回 `9ae4ed9a` 或恢复旧 DB；那会让新 numeric 快照被丢弃或错判。已准备 [兼容回滚包](numeric-compatibility-rollback-README.md)：只关闭新 numeric 出题，保留数字快照读取、首次/重试/纠错判分、反馈和音频。**没有执行回滚。**

该补丁对业务提交 `1cac6c0c` 五文件 SHA 守卫与 `git apply --check` 均通过；隔离回滚状态 **134 passed / 198 subtests**，另 8 个预先生成的冻结快照三项兼容测试通过。执行前重新核版本与实时变更，用同目录校验脚本和 manifest，不用 `--reject`、强制覆盖或数据库恢复。
