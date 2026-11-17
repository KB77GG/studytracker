# 学生小程序候选

来源：`/Users/zhouxin/Desktop/studytracker-release@d03a2749`，保留既有76M/37U。候选：`/private/tmp/studytracker-vocabulary-error-client-20261117`，文件副本，不是上传目录。

精确修改home、vocabulary-review各JS/WXML共4文件：试点首页区分今日必做和自选巩固，限额读服务器；mode=maintenance仅显式可选入口发送；自选不返回新任务门禁；同词多能力保留；活动另一类批次提供显式继续入口；空继续清除旧数字/批次。OFF保留旧显示和请求。新增12项前端测试（合并既有共115）。

在候选根执行：

```sh
node --test tests/test_vocabulary_error_policy_client.js tests/test_student_home_grace_client.js tests/test_entry_loading_client.js tests/test_vocabulary*.js tests/test_dictation_audio.js tests/test_dictation_spell_queue.js tests/test_web_practice_client.js
node --check miniprogram/pages/student/home/index.js
node --check miniprogram/pages/student/vocabulary-review/index.js
```

115/115通过，`client-tests.log`。候选miniprogram目录执行官方编译均exit0：

```sh
/Applications/wechatwebdevtools.app/Contents/Resources/app.asar.unpacked/node_modules/wcc-exec/wcc -o /private/tmp/vocabulary-error-client-wxml.js pages/student/home/index.wxml pages/student/vocabulary-review/index.wxml
/Applications/wechatwebdevtools.app/Contents/Resources/app.asar.unpacked/node_modules/wcc-exec/wcsc -o /private/tmp/vocabulary-error-client-wxss.js -pc 2 pages/student/home/index.wxss pages/student/vocabulary-review/index.wxss styles/vocabulary-theme.wxss styles/vocabulary-forgot.wxss
```

`prepare_patch.py`核451来源SHA，只有4产品变化，447完全一致；输出manifest、patch、最终4文件及测试。这里只是增量归档，不是完整小程序包，不能用后台树或该files目录覆盖固定整包。`apply_fixed_client.py`默认只核对；--apply先核所有451SHA、备份4原文件到/tmp，才复制5目标文件并复核447非目标。

应用/固定源复验事实由根收尾追加。尚无本轮整包编译、真机、上传、提审或发布证据。用户真正发包目录始终是 `/Users/zhouxin/Desktop/studytracker-release/miniprogram`。
