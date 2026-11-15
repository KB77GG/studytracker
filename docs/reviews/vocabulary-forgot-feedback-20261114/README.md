# 词汇“忘了”反馈修复 — 2026-11-14

## 2026-11-15 发布授权与归档范围

用户已授权上传部署，并明确由本人稍后上传发布微信小程序。本次没有后端修改，不触发服务器部署；只将本报告中的精确5文件补丁、前后源码、可复验依赖与证据提交推送到任务分支 `codex/vocabulary-forgot-feedback-20261114`。已push归档提交 `2663da92492f6182a89ab6e7f64344c7159efe54` 并fetch回读一致，最终状态见规范交接最新条目。主线与实际固定发布树既有未提交内容不整体合并；`client-files/` 是复验快照，不是完整可上传小程序。

实际发布目录5SHA未变，11月15日复跑74Node/两页官方wcc/3JS语法全通过，见 `release-recheck-20261115.md`。用户解锁后已通过微信工具UI确认正确固定项目，点击普通编译仅见JSON构建日志，模拟器未启动；工具明确显示“未登录”，已显示扫码入口交用户登录，整包成功尚未确认。用户随后明确“我稍后自己登录并编译上传”，本轮不再等待登录，也不代做微信上传。

为支持其它机器独立复验，另保存8个未改的既有JS依赖及 `verification-dependencies-sha256.json`，均与11月14日冻结来源一致。仓库root下执行以下命令无需完整固定发布树，即可复现 **41/41 + 11/11**：

```sh
node --test docs/reviews/vocabulary-forgot-feedback-20261114/client-files/tests/test_vocabulary_forgot_client.js
node docs/reviews/vocabulary-forgot-feedback-20261114/independent_client_probe.js docs/reviews/vocabulary-forgot-feedback-20261114/client-files
```

以下11月14日记录及 `apply-result.json` 等保留当时的本机/未提交状态，不能当作11月15日同步状态。完整固定发布树其它既有改动仍仅本机，不声明本归档分支的顶层 `miniprogram/` 可直接用于上传。

## 结果与边界

真实固定小程序目录 `/Users/zhouxin/Desktop/studytracker-release/miniprogram` 已修：点击“忘了”保存未掌握记录后，当前题显示正确答案、释义/反馈和重听；明确点击“看过答案，继续”后才切题或结算。学习与今日词汇复习两页同步修复，包含网络超时恢复、跨日复习门禁、末题和重复事件保护。首次成绩、补练和后台排程不变。

这是本机修复，**未 commit/push/merge/deploy，微信未上传/提审/发布**。未访问生产或真实学生数据，未改变数据库/服务/通知。具体学生“满24小时仍没有复习”的个案尚无账号/词/时间证据；自动化不能替代真机或个案核查。

后端在合成数据上未发现漏排程：四类学习目标，首次及组末全忘记；结算和未结算各一组，共8场景，末题保存后复习时间已持久化。作答满24小时前1秒无法领取，恰24小时可领取全部3个合成词。综合任务组末重练受间隔和次数约束，并非忘记后马上重复；自主复习沿现有到期机制，不另加当批强制重练。

## 工作树与变更范围

| 位置 | 基线/分支 | 本轮变化 |
|---|---|---|
| `/Users/zhouxin/Desktop/studytracker-release` | `codex/miniprogram-release@d03a2749eb99cde041cdae18305b624956d46e90` | 5文件最小增量+两交接；原76 modified/35 untracked入口保持 |
| `/private/tmp/studytracker-vocabulary-forgot-client-20261114` | 实际发布源码完整前端及测试副本，无Git元数据 | 隔离实现/测试候选 |
| `/private/tmp/studytracker-vocabulary-forgot-feedback-20261114` | `codex/vocabulary-forgot-feedback-20261114@75ff855d381e4f872a466b7038177382452cbe5b` | 本报告目录、两交接；无主线产品改动 |
| `/Users/zhouxin/Desktop/studytracker` | `main@6ded77d24586327ad94e151e172ae4811b4a2eed` | 仅两交接增量；原7 modified/23 untracked入口保留 |

实际发布树的五个路径：

- `miniprogram/pages/student/vocabulary-learning/index.js`
- `miniprogram/pages/student/vocabulary-learning/index.wxml`
- `miniprogram/pages/student/vocabulary-review/index.js`
- `miniprogram/pages/student/vocabulary-review/index.wxml`
- `tests/test_vocabulary_forgot_client.js`（原已未跟踪）

基线完整文件SHA在 `release-source-sha256.json`，精确脏状态在 `*-status-before/after.txt`。`before/` 与 `client-files/` 保存5文件原稿/候选，`client-manifest.json` 给出前后SHA，`client-increment.patch` 只包含本轮增量。经文件系统授权，`apply_client_fix.py` 已应用并更新发布树两交接，结果 `apply-result.json`：5目标与冻结候选逐一相同，**2667个非目标文件SHA未变**。脚本含来源校验且不可重复应用。

主线小程序不含固定发布树全部历史增量，不能用主线整包替换固定目录。本轮过程中共享origin/main从75ff855d前进到课堂同义词2e82331a；其forgot排程未改，主线attempt_id修复在固定树早已存在，未混入其它功能。其它worktree未修改。

## 复现与验证

后端命令cwd为报告树，Python借用项目原 `.venv`；SQLite内存夹具、受控时钟，不import生产配置。

```sh
TZ=UTC PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m pytest -q --disable-warnings --tb=short -p no:cacheprovider tests/test_vocabulary_group_learning.py tests/test_vocabulary_autonomous_review.py tests/test_vocabulary_group_learning_api.py tests/test_vocabulary_mastery.py tests/test_vocabulary_numeric_review.py

TZ=UTC PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/vocabulary-forgot-feedback-20261114/backend_probe.py
```

结果 **117 passed/2 subtests passed**，桥接 **8/8**，主审独立复跑桥接exit0。`backend-audit.md` 给出后端答案序列化、组末重练、24小时排程的行号；`backend_probe.json` 为合成结果。

以下Node命令分别在候选目录与实际发布目录执行，均 **74/74**，日志 `client-tests.log` / `release-client-tests.log`。该数字包含旧脚本型测试的Node文件计数，不把脚本内部断言另行累加。

```sh
node --test tests/test_vocabulary*.js tests/test_dictation_audio.js tests/test_dictation_spell_queue.js
node --check miniprogram/pages/student/vocabulary-learning/index.js
node --check miniprogram/pages/student/vocabulary-review/index.js
node --check tests/test_vocabulary_forgot_client.js
/Applications/wechatwebdevtools.app/Contents/Resources/app.asar.unpacked/node_modules/wcc-exec/wcc -o /dev/null miniprogram/pages/student/vocabulary-learning/index.wxml miniprogram/pages/student/vocabulary-review/index.wxml
```

语法/官方两页WXML编译exit0；未改WXSS。未做完整开发者工具项目编译或iOS/Android真机验收，未跑全仓测试。

独立探针通过实际require页面模块、模拟网络与音频，分别用旧发布源码/候选/合入后发布源码运行：旧版 **2/11**，候选与合入后 **11/11**。旧版9项失败覆盖自动切题/末题结算/超时恢复等根因；故意注入的timeout/失配stderr在报告中保留，不代表最终用例失败。

```sh
node /private/tmp/studytracker-vocabulary-forgot-feedback-20261114/docs/reviews/vocabulary-forgot-feedback-20261114/independent_client_probe.js /private/tmp/studytracker-vocabulary-forgot-client-20261114
node /private/tmp/studytracker-vocabulary-forgot-feedback-20261114/docs/reviews/vocabulary-forgot-feedback-20261114/independent_client_probe.js /Users/zhouxin/Desktop/studytracker-release
```

在固定发布树应用前，以下正向检查通过；应用后逆向检查通过：

```sh
git apply --check --whitespace=error /private/tmp/studytracker-vocabulary-forgot-feedback-20261114/docs/reviews/vocabulary-forgot-feedback-20261114/client-increment.patch
git apply --reverse --check --whitespace=error /private/tmp/studytracker-vocabulary-forgot-feedback-20261114/docs/reviews/vocabulary-forgot-feedback-20261114/client-increment.patch
```

## 后续

从固定发布目录完整编译并真机验收：首次/组末/今日复习点忘了，确认答案和重听，显式继续，末题确认后结算，后续到期复习。另设备已经结算时仍恢复原结算；退出后重新进页面沿现有服务端进度恢复，本次没有新增跨页面持久化的“答案已读确认”门禁。

取得发布授权后按项目约定上传/提审/发布小程序。后台无需因本补丁部署。若学生明确已超过24小时仍不出现，应按该学生、单词和作答时间只读追踪；不批量重置成绩、到期时间或补造提交。交接已更新旧资料树、报告树和真实发布树的 `docs/CODEX_HANDOFF.md` / `docs/WORKLOG.md`。所有本轮成果仍只在同一Mac可见。

归档差异检查：除 `client-increment.patch` 的合法统一diff空白context标记外，`git diff --cached --check` 通过；补丁本身通过 `git apply --reverse --check --whitespace=error`。不为消除报告中的context空格而破坏可应用补丁。
