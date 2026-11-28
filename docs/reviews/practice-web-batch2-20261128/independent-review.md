# 第二批导航独立审查

审查对象：`/private/tmp/studytracker-practice-web-batch2-20261128`，分支 `codex/practice-web-batch2-20261128`，基线 `9c211ee807fa1084017cbf8e8a05c1c9fe95de77`。审查时为本机未提交候选；未提交、推送、部署或访问生产。

## 结论

已关闭本次独审发现的目录返回循环和精听匿名态双品牌头。当前没有已确认的阻断缺陷。源码边界检查及下列定向回归通过；浏览器服务 bind 被沙箱拒绝、提权未完成，本轮没有浏览器流程实测通过项。更广测试由本报告目录其他证据记录。

## 已关闭问题

1. **目录循环**：第一版从听力目录 A 经顶栏进入阅读目录 B，再进入 A，随后返回会 B→A→B 循环。原因是按 URL 存储的目录父级把 A 原来的 `/practice` 覆盖成 B。独审使用现有测试的 fake window/DOM click capture 复现，实际输出 `Back chain: /reading/tests → /listening/tests → /reading/tests`。修复后增加有时效及深度界限的父级链检查，重访目录保留此前无环父级；同一独立 DOM capture 路径复验输出 `INDEPENDENT_CYCLE_RECHECK_OK`，A→B→A 后返回 `/practice`。新增双目录与三目录循环回归已通过。
2. **精听匿名双品牌头**：共享顶栏与姓名验证 `entrance_shell` 原品牌栏曾同时显示。宏新增默认开启的 `show_brandbar`，只有精听调用关闭；登录页使用默认行为。独立复跑身份入口测试 5/5 通过。
3. **测试适配**：首轮 17 项 Python 出现 2 个 fixture error（原独立 Jinja fixture 未提供 `session`）及 4 个旧 HTML 字符串断言失败（写作链接新增导航属性）。这些不是 Flask 页面异常；补 fixture 并改为结构断言后，17/17 通过，没有删除教师/身份/目录能力检查。

## 产品范围检查

- `base.html` 仅对练习中心和题型专项的非员工视图切换共享顶栏，已登录学生也在此范围。教师、助教、管理员继续走后台布局与原功能块。
- 听力/阅读剑雅、机经、冲刺、写作及母题目录共用同一顶栏；品牌带独立 `data-practice-home`，不再被返回按钮逻辑覆盖。根练习中心无自身返回按钮。
- `/practices` 与 `/listening` 保留姓名验证、课堂/员工分支及目录；删除重复任务/记录展示和对应加载、退出引用，保留指向练习中心的任务入口。
- 共享顶栏窄屏规则重新显示返回和身份入口，仅调整新增导航所需布局；未接入第三批练习中心网格、配色、水印或 CDN 方案。
- 目录 h1 与书名 h2 分离，空目录仍有页面标题。

逐字比较 `git show HEAD:<path>` 与工作文件确认下列产品未变：

```text
app.py
models.py
api/miniprogram.py
services/practice_navigation.py
templates/listening/test_practice.html
templates/reading/test_practice.html
templates/listening/player.html
```

另按函数/宏边界逐字比较确认：`practice_shell.js` 从 `function init(options = {}, win = window)` 至导出完全不变；精听 `render_intensive_catalog` 宏及 `refreshExerciseProgress` 至管理删除脚本完全不变。保存、判分、计时、退出保护主体没有调整，上传/编辑/布置/删除权限与自由练习进度保留。

## 独立执行命令与结果

工作目录均为上述隔离树：

```sh
node --test tests/test_practice_shell.js tests/test_practice_task_lists.js tests/test_practice_center_identity.js
```

56/56 通过，包括保存失败阻止退出、未作答不拦截、身份更新、精听去重及来源返回。

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-batch1-20261126/run_tests.py tests.test_practice_center_batch1 tests.test_practice_workspace_regression tests.test_practice_portal_catalog_grouping tests.test_auth_entry_pages
```

17/17 通过，临时 SQLite、未读项目 `.env/app.db`、网络调用 0。双品牌头修复后另独立执行：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-batch1-20261126/run_tests.py tests.test_auth_entry_pages
git diff --check
```

5/5 通过；差异格式检查退出 0。

补充新增真实路由/Jinja 回归：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-batch1-20261126/run_tests.py tests.test_practice_navigation_batch2
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check tests/test_practice_navigation_batch2.py
```

10/10 通过（0.897 秒），Ruff 通过。测试在私有临时库建立、清理两个合成账号和一份合成学生档案，使用真实 Flask-Login 会话和实际模板：

- guest / verified / classroom / student_account / teacher 各身份分支；教师后台及精听管理权限保留。
- 8 个目录的唯一返回、完整品牌、页面 h1；4 个空目录标题。
- `/practice` 无自身返回；已登录学生的练习中心、题型专项仍使用共享顶栏。
- `/practices` 与 `/listening` 保留身份控件，没有重复任务区/加载请求代码；普通登录页继续保留原品牌栏。

这些 HTTP/Jinja 断言不执行 JavaScript，不验证浏览器历史、点击、可见性、CDN 加载或响应式布局，不能替代待执行的 `flows.js`。

## 限制

本次独审为源码、私有合成配置及 Node DOM mock 检查；没有访问生产、真实学生作答、微信真机或 Safari，也没有验证外部 CDN、真实音频或浏览器原生缩放。主审记录的浏览器服务启动限制不属于导航测试失败，也不意味着浏览器验收通过。上述命令依赖本机既有 Python 环境，其他电脑需使用安装项目依赖后的解释器。原任务范围内的环境限制不应被当作导航缺陷或已验收项目。
