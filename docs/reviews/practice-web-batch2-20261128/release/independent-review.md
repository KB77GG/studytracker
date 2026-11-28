# 批2导航发布前独立复核

复核工作树：`/private/tmp/studytracker-practice-web-batch2-20261128`，分支 `codex/practice-web-batch2-20261128`，开始时 HEAD / origin/main 为 `9c211ee807fa1084017cbf8e8a05c1c9fe95de77`。本审查不提交、推送或部署；发布操作由主 agent 执行。

## 首轮发现

**已修复并补验：家长账号被误标成学生身份。** 首轮新共享头 `templates/practice/_workspace_header.html` 的 `identity_name` 对所有已登录用户取账户名，而服务端 `navigation_defaults` 对家长账户返回 guest 或已确认学生身份。结果是家长未确认学生时显示“学生：家长名”；家长会话已确认孩子时，听读目录仍显示家长名，覆盖真正的 `practice_student_name`。这属于身份展示回归，不是权限或判分问题。

用独立 Jinja 环境渲染该 partial、设置 synthetic parent 用户，分别设置 guest/空会话和 verified_student/合成孩子会话，实际结果均为 `学生：合成家长`。建议只按 identity_mode 选择展示名：staff/student_account 使用账户名，verified_student 使用已验证会话名，guest 留空；既有 student Profile 可作为学生名称的优先来源。需要补家长 guest 与已验证孩子两种回归。

主 agent 已按上述身份模式修复 partial。本子审查在 `tests/test_practice_navigation_batch2.py` 新建合成家长账户，增加两个真实请求测试，分别覆盖未确认与已确认孩子；每种状态都检查 `/practice`、听读剑雅目录和 `/practices` 四页。修后 guest 显示“未确认身份”，verified_student 显示合成孩子，均不显示家长名。原教师、学生账号、课堂、登录栏等检查继续通过。当前没有已确认的发布阻断缺陷；浏览器验收结果由主 agent 单列。

## 已核对范围

- 25 文件 manifest 的 SHA256 在首轮独审时全部一致，未发现未说明的候选漂移。
- 目录来源和独立父级缓存限同源目标，有缓存时效与环路遍历上限；品牌、返回、退出不再被捕获成进入页面的来源。单测覆盖双目录/三目录循环、冲刺多层返回、显式新标签来源与外部 URL 拒绝。
- 共享 header 的品牌与 module-back 分离，根目录无自返回；五主项、右侧身份/退出在窄屏有独立覆盖规则，实际浏览器布局仍由主 agent 补验。
- 教师/助教/管理员的练习中心继续使用后台套件，精听管理控件原权限条件与操作代码保留。精听身份 gate 保留、重复任务及最近历史请求移除；默认登录品牌栏未删除。
- `app.py`、`models.py`、听读 `test_practice.html`、精听 `player.html` 均与 HEAD 逐字一致；`practice_shell.js` 从 `function init` 到文件结尾逐字一致，未改变保存与做题退出防护主体。
- 未实施第三批练习中心布局、题型配色、水印或 CDN 本地化。

## 独立执行

工作目录均为上述隔离树。

```sh
node --test tests/test_practice_shell.js tests/test_practice_task_lists.js tests/test_practice_center_identity.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-batch1-20261126/run_tests.py tests.test_practice_navigation_batch2 tests.test_auth_entry_pages
```

Node **56/56**，Python **15/15** 通过。Python 使用临时 SQLite、合成配置，network0，不读取项目 .env/app.db。以上现有测试没有家长身份覆盖，因此通过结果不能否定首轮发现。

修后原 Python 命令再次执行：**17/17** 通过（批2导航12项＋原身份入口5项），network0；不是用mock身份结果替代真实路由。

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check tests/test_practice_navigation_batch2.py
git diff --check -- tests/test_practice_navigation_batch2.py templates/practice/_workspace_header.html
```

Ruff 与定向差异检查退出0。首轮 manifest 匹配是修前事实；发布候选需由主 agent 刷新 manifest，纳入这两处明确的修复和测试变化。

## 边界

本子审查为代码、Jinja/HTTP、Node DOM mock 和下列截图复核；未独立操作浏览器点击、访问生产或真机验收。用户本轮已授权主 agent 部署；本审查没有执行发布操作或生产数据写入。此次仅编辑新增家长回归测试和本报告；规范交接由主 agent 在发布收尾统一更新。

## 浏览器截图独立抽检

人工逐张查看 `release/browser-first/` 的以下八张首屏截图（相对于本报告上级目录）：

- `-listening-tests-390.png`、`-listening-tests-1440.png`
- `-practices-390.png`、`-practices-1440.png`
- `-practice-390.png`、`-practice-1440.png`
- `-practice-question-types-390.png`、`-practice-question-types-1440.png`

八张均可完整看到 Sage Path 品牌、五项主导航、合成学生身份和退出刷题。1440px 顶栏为单行，390px 分为品牌、主导航、身份操作三行，未见本次抽检所涉及文字或控件被视口裁切、相互遮挡或溢出。听力目录、精听、题型专项均仅有一处“返回练习中心”；练习中心作为根入口无自返回。精听额外的“切换学生”在两个宽度都完整可见。主项激活态与各页模块对应。

截图仅覆盖上述四页、两个视口以及短合成学生名；不据此声称全部 22 个目录场景、长姓名、真实移动设备或交互点击已经独立验证。题型专项本机截图为空题库，不验证其做题提交。原水印、色彩和练习中心内容布局属于第三批范围，未作为本轮阻断。本次截图抽检未发现新增发布阻断。
