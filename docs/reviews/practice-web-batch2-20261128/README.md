# 网页刷题第二批导航补丁（2026-11-28）

> 当前状态：用户已授权部署；浏览器 44/44、双 Python 各85、扩展66、Node207及退出9均通过。最新发布过程、命令、最终补丁/manifest见 [release/README.md](release/README.md)。下文为第一次本地交付存档（包括当时权限限制）；旧 batch2.patch / manifest.json 不包含发布前最后修复，请勿再用于部署。

实现已完成，双 Python 与 Node 回归通过；浏览器流程脚本已补充，但本轮因本地监听权限未完成而未实跑。未提交、推送或部署，不能据此宣称第二批已上线。

## 基线与范围

- `git fetch origin main` 核实基线为 `9c211ee807fa1084017cbf8e8a05c1c9fe95de77`。
- 实施树：`/private/tmp/studytracker-practice-web-batch2-20261128`，分支 `codex/practice-web-batch2-20261128`，开工 clean；HEAD 保持基线。
- 依据 main 中 [11月27日联合发布记录](../practice-web-joint-release-20261127/README.md) 和 [11月26日审计](../../design/practice-web-audit-20261126.md) 的第二批 #6、#9、#12、#18。GitHub 网页抓取未成功，以上文件由已 fetch 的 main 直接读取，没有把旧本机资料树当最新源码。
- `/Users/zhouxin/Desktop/studytracker` 为旧资料树，`main@6ded77d24586327ad94e151e172ae4811b4a2eed`，开工 8 modified / 27 顶层 untracked / 0 staged。本轮只更新它的两份交接，未覆盖既有业务改动。

## 行为变化

1. 新共享 `practice/_workspace_header.html` 接入剑雅听读、机经、写作/母题、冲刺目录，以及非员工练习中心、题型专项和精听入口。品牌保持 Sage Path；主导航为练习中心、听力、阅读、写作、题型专项。右侧只有一个上下文返回入口，练习中心自身不显示返回自身。
2. `practice_shell.js` 为目录返回生成来源文字、真实 href 和点击/浏览器后退落点。保留“冲刺→目录→详情→目录→冲刺”父级；目录重复访问不会形成 A→B→A 返回环路。品牌、返回、退出不会被当成进入新练习的来源。
3. `/practices` 和兼容 `/listening` 只保留精听目录、姓名验证/切换和原管理功能；任务及重复最近记录区、相应请求移除，提供练习中心任务区链接。已登录学生使用学生顶栏；教师、助教、管理员的 `/practice` 后台套件保持。课堂入口和精听上传、编辑、布置、删除条件保持。
4. 听读目录的页面 h1 与书名 h2 分开，空目录仍有 h1；页面 title 使用“页面名 · Sage Path”。精听未验证界面不再叠第二个品牌顶栏；原登录页保留原品牌栏。

没有修改判分、计时、保存接口及做题主体。没有实施第三批的练习中心重排、题型配色、水印调整或 CDN 本地化。窄屏 CSS 仅调整本次共享顶栏的换行和入口可见性，实际布局仍待浏览器验收。

## 可复现验证

工作目录为实施树，其他电脑用已安装项目依赖的 Python 替代本机绝对解释器路径。

```sh
cd /private/tmp/studytracker-practice-web-batch2-20261128
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-batch2-20261128/run_checks.py python
/Users/zhouxin/Desktop/studytracker/tmp/web-vocab-py310-20261126/bin/python docs/reviews/practice-web-batch2-20261128/run_checks.py python
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-batch2-20261128/run_checks.py node
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-batch2-20261128/verify_scope.py
```

`validation/*-commands.json` 保存实际 argv、cwd、退出码、耗时及日志位置。Python 使用已有批1隔离 runner：临时 SQLite、注入合成配置，不读取项目 `.env/app.db`，网络调用为 0；Python3.10 原生运行，无 datetime 兼容别名。Node 覆盖批1、词汇、模考、冲刺及本次共享导航；另有精听退出保护独立探针。

最终结果：Python3.13 **83/83**，原生 Python3.10 **83/83**，Node **207/207**，独立精听退出探针 **9/9**。新增10项真实路由/Jinja测试覆盖访客、姓名身份、学生账号、课堂、教师、8个目录及4个空目录；它们不执行浏览器 JS。定向 Ruff、CI YAML、Jinja 解析、独立 JS 语法与源文件差异检查通过，完整静态边界结果见 `scope-check.json`。没有执行全仓测试或远端 CI。

初始验证曾遇到旧独立 Jinja fixture 缺少 `session` 和旧顶栏链接字符串断言不再匹配，已补 mock 并改为结构断言，未删除身份/教师检查。精听旧任务预览的两个测试改为实际精听脚本验证身份和切换时不再请求重复任务，原练习中心任务分组测试保留。初始 fixture 错误日志在 `validation/initial-template-fixture-errors.log`；独审发现及修复的目录环路、匿名双品牌头见 [independent-review.md](independent-review.md)。

## 浏览器补验命令与限制

使用既有批1真实 Flask app + 私有 SQLite fixture。先在终端 A 启动，再在终端 B 运行增强的原审计脚本。不要连接生产或使用真实学生数据。

```sh
# 终端 A；需允许本机端口监听
cd /private/tmp/studytracker-practice-web-batch2-20261128
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-batch1-20261126/serve_fixture.py /private/tmp/studytracker-practice-web-batch2-20261128 5116

# 终端 B；其他电脑可安装项目测试所需的 Playwright/Chromium 后省略本机路径
cd /private/tmp/studytracker-practice-web-batch2-20261128
NODE_PATH=/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules \
AUDIT_CHROMIUM=/Users/zhouxin/Library/Caches/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-mac-arm64/chrome-headless-shell \
AUDIT_TEACHER=1 AUDIT_SCREENSHOTS=1 \
BASE=http://127.0.0.1:5116 \
OUT=docs/reviews/practice-web-batch2-20261128/browser \
node docs/reviews/practice-web-audit-20261126/flows.js
```

- 本轮普通启动完成合成库准备后，`bind` 返回 `Operation not permitted`；正规提权重试未完成并被中断，没有成功启动 5116 或运行 Chromium。现有 5055 服务来源不属于本轮，未借用或停止。具体记录见 `browser/browser-run.json`。
- 浏览器按钮点击、浏览器后退、截图、390/1280/1440 实际布局、Safari、系统 IME、原生缩放、微信真机、真实账号和生产环境均未因本轮自动测试而验收。
- 仓库缺部分 MP3；听力题型目录会跳过缺音频条目。外部 CDN/字体在受限网络可能失败。这些条件须与导航断言结果分开记录，不能用音频 404 或 CDN 失败推断导航通过/失败。
- 新增脚本语法检查通过不等于所有新增浏览器断言已经跑通；拿到本机监听和浏览器权限后必须执行上面的流程命令，处理真实失败再发布。

## 补丁交付

`batch2.patch` 包含产品、测试、CI 登记、增强 flows 及复现工具，不包含两份滚动交接、原始日志或补丁自身。`patch-check.json` 记录以基线临时 Git index 实际执行 `git apply --check --cached` 的结果；没有改用户 index。`manifest.json` 列出交付文件及 SHA256。

补丁适用性检查已通过；额外尝试向独立 index 完整应用时，Git 写共享对象目录被沙箱拒绝，因此不声称本机已在第二份工作树完整应用。该尝试未改真实暂存区或工作文件，详见 `patch-check.json`。

给另一台电脑上的 Codex：将 `batch2.patch` 和本目录说明作为附件传过去；本机路径不能在云端直接访问。可以直接使用 [codex-handoff.md](codex-handoff.md) 的指令。

```sh
git fetch origin main
git worktree add -b codex/practice-web-batch2-review /tmp/studytracker-batch2-review 9c211ee807fa1084017cbf8e8a05c1c9fe95de77
cd /tmp/studytracker-batch2-review
git apply --check /path/to/batch2.patch
git apply /path/to/batch2.patch
python docs/reviews/practice-web-batch2-20261128/run_checks.py python
python docs/reviews/practice-web-batch2-20261128/run_checks.py node
python docs/reviews/practice-web-batch2-20261128/verify_scope.py
```

若届时 main 已推进，先核对差异，在隔离树按实际冲突适配并重跑验证，不在脏主树直接套补丁。浏览器验收完成后再请用户决定提交/推送/部署；push main 会触发部署。

## 发布与交接

本轮只有本机实现和证据；未 commit、push、部署、写生产数据库、改生产配置或进行小程序上传/提审/发布。上一轮 main 的第一批已部署状态由 11月27日发布报告确认，本轮没有重新检查服务器。旧资料树另有 11月27日词汇开关开启记录，本轮未重验，不以 Git 中较早的“默认关闭”报告覆盖它。

两树 `docs/CODEX_HANDOFF.md` 和 `docs/WORKLOG.md` 会记录本次实际路径、状态、验证、浏览器阻塞及直接下一步。另一台电脑目前只能通过手工传递本补丁接续，不能从远端取得未提交成果。
