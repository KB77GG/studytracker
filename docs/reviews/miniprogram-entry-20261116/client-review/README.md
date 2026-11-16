# 小程序任务入口与词汇加载候选，2026-11-16

候选 `/private/tmp/studytracker-entry-client-20261116` 是文件副本，不是 Git worktree，不可作为正式上传源。来源是固定发布树 `/Users/zhouxin/Desktop/studytracker-release`，分支 `codex/miniprogram-release`、HEAD `d03a2749eb99cde041cdae18305b624956d46e90`，含既有未提交前端。完整来源保持原状；只可核对 manifest 后应用精确补丁，不能覆盖整个来源目录。候选不含实例/生产数据/密钥；开发者私人配置不复制交付。所有本轮工作仅本机，未 commit/push/deploy/上传提审发布。

## 改动

7 产品文件、2 测试文件，完整清单与前后 SHA 见 manifest.json，增量见 client-increment.patch。

- 任务页取消全屏加载遮罩；显式等待/慢请求提示/错误/重试/返回。详情返回就显示标题与信息，详情和复习前置检查共用30秒总deadline，10秒给慢提示。只有加载完成且不在跳转时显示表单；上传/录音/计时操作/提交均校验入口状态。卸载和旧响应不复活界面，重试不自动执行，加载中再次触发不会重复请求。原网页/只读/所有原生跳转规则保留，跳转失败可重试。
- 词汇GET等候30秒，10秒只提示仍在加载；现有15秒写请求限制不变。保留HTTP状态用于区分网络/超时/服务繁忙/访问失败；日期门禁仍显示只读。任务准入旧响应有版本隔离，队列沿用现有版本隔离；不自动重发GET/POST。
- 公共按钮移除 flex:1，避免纵向错误面板把重试拉成巨大胶囊；已有横排navigation/confirm按钮局部伸展保留。

## 验证

以下 cwd 均为候选根：

```
node --test tests/test_entry_loading_client.js
node --test tests/test_entry_loading_client.js tests/test_vocabulary*.js tests/test_dictation_audio.js tests/test_dictation_spell_queue.js tests/test_web_practice_client.js
ENTRY_CLIENT_ROOT=/Users/zhouxin/Desktop/studytracker-release node --test --test-name-pattern='task entry retains|learning queue shows|entry markup' tests/test_entry_loading_client.js
```

新增15/15、合并100/100通过（full.log）；旧源三项选择验收0/3，符合预期（baseline.log）。包括虚拟13秒成功、30秒失败、入口总预算、迟到响应/卸载、显式重试、无自动POST、保存详情、导航失败、只读/网络/503与按钮样式契约。虚拟时钟未等待真实30秒，不冒称真机弱网验收。5改动JS的 node --check 均通过。

在候选 `miniprogram/` 目录：

```
/Applications/wechatwebdevtools.app/Contents/Resources/app.asar.unpacked/node_modules/wcc-exec/wcc -o /private/tmp/studytracker-entry-client-20261116-wxml.js pages/student/task/index.wxml pages/student/vocabulary-learning/index.wxml
/Applications/wechatwebdevtools.app/Contents/Resources/app.asar.unpacked/node_modules/wcc-exec/wcsc -o /private/tmp/studytracker-entry-client-20261116-wxss.js -pc 2 pages/student/task/index.wxss pages/student/vocabulary-learning/index.wxss styles/vocabulary-theme.wxss styles/vocabulary-forgot.wxss
```

两页官方WXML/WXSS编译exit0。未完成微信整包编译、真机、13秒现场网络复测或生产慢请求根因修复。前端调整避免过早放弃与空表单，不能单独证明服务端慢问题已消失。固定发布源码未修改，主审统一更新主仓交接。

## 独立复核后的追加修复

- 日期错误现在优先读取 `error` 机器码、再回退 `message`；带真实中文message的三种日期门禁保持只读，不能继续作答/结算。
- 学习页进入复习的两处跳转共用失败处理，明确显示“打开复习失败，请重试”；导航代际、队列代际与任务准入代际共同防止失败回调覆盖重试或卸载后的页面。
- 新增3项回归在首版候选先复现失败（review-findings-before.log，0/3、exit1），修复后并入100/100。固定源码的9个before SHA再次核对不变；补丁/manifest已更新，5JS语法再验通过。
