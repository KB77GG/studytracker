# 2026-11-15 固定发布源码只读复核

当前固定源码 `/Users/zhouxin/Desktop/studytracker-release`，分支 `codex/miniprogram-release`，HEAD `d03a2749eb99cde041cdae18305b624956d46e90`；76 modified / 35 untracked 顶层入口。本轮不修改该树、不 commit/push、不上传/提审/发布、不访问生产。

5目标 SHA 与 `client-manifest.json` 的 after 值全部一致；运行前后均一致，Git 脏状态字符串未变。具体 SHA 见 `release-recheck-20261115-sha256.json`，状态见同名前缀 status.txt。

在该固定树执行：

- `node --test tests/test_vocabulary*.js tests/test_dictation_audio.js tests/test_dictation_spell_queue.js`：exit 0，74 passed / 0 failed，日志 `release-recheck-20261115-node.log`。
- `/Applications/wechatwebdevtools.app/Contents/Resources/app.asar.unpacked/node_modules/wcc-exec/wcc -o /dev/null miniprogram/pages/student/vocabulary-learning/index.wxml`：exit 0。
- 同一官方 wcc 命令编译 `miniprogram/pages/student/vocabulary-review/index.wxml`：exit 0。
- `node --check` 分别检查两页 `index.js` 及 `tests/test_vocabulary_forgot_client.js`：3条均 exit 0。精确参数、stdout/stderr 见 `release-recheck-20261115-compile.json`。

本机实际候选的“忘了”成功与恢复路径会停留显示正确答案、解释和原词重听，明确点击“看过答案，继续”才切题或结算；忘记仍按未掌握处理。测试覆盖末题/超时恢复/迟到事件，后端排程未改。

限制：这些是实际源码的模块行为测试、两页 WXML 编译和 JS 语法检查；本轮未运行微信开发者工具整包普通编译、iOS/Android 真机或真实学生端到端流程，不能据此宣称整包/线上已发布。用户随后应从固定目录 `miniprogram/` 上传。主线不含该发布树全部历史前端增量，不能用主线整包覆盖。

新日志和本记录仅写入报告树 `docs/reviews/vocabulary-forgot-feedback-20261114/`；主 agent 负责统一交接与最小补丁归档推送，状态以其最终 Git 核验为准。
