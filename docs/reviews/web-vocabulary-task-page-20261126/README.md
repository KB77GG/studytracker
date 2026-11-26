# 网页背词任务页：本地实施与验收

> 后续 Claude 审查修复与当前验证见 [review-fixes.md](review-fixes.md)；下文首次推送/CI记录保留为历史证据。

状态：实现及原验收记录已获用户认可；**A01–A14 尚未全部实测通过**。实现/补测已提交并推送任务分支，代码 `2f83ebd1` 的远端 CI 整体成功（三业务 job 成功、既有非阻断 lint 失败）；默认关闭、未部署或开启。2026-11-26。本轮补测与远端结果以 [审查分支记录](branch-review.md) 为准。

云端需要的完整命令、逐项结论、五个实现重点和未验边界，现集中在 [可直接粘贴给 Claude 的验证补充](claude-verification-paste.md)。上一轮复核确认30个产品/配置/测试文件与原验收manifest一致；没有把模拟IME、缩放空间代理或503故障模拟写成真实设备/原生缩放/真实断网验收。

## 来源与工作树

- 实施树：`/private/tmp/studytracker-web-vocabulary-20261126`
- 分支：`codex/web-vocabulary-task-page-20261126`
- 开发时 fresh fetch 的 `origin/main` 基线（不是当前分支 HEAD）：`f81a5e4a4d81282eb67b994a4cfcc5574fb78747`
- 计划/原型来源：`origin/claude/clever-heisenberg-8evbm0@479cab8af3b6b3e7abb364224edeca5ffe91fae8`；仅用 `git show` 提取到 [source](source/)，没有合并该文档分支。
- 用户批准计划 §9 全部九项。姓名会话可写、拒绝同名；网页版综合训练订正开启并展示正确答案、不计分；任务内复习门禁；允许粘贴；听音拼写答前不显音标；本端进入至首次结算计时；排除旧听写；`PRACTICE_VOCABULARY_WEB_ENABLED` 默认 false。
- 旧资料树 `/Users/zhouxin/Desktop/studytracker` 保持 `main@6ded77d24586327ad94e151e172ae4811b4a2eed`。开工原 8 modified / 27 顶层 untracked，0 staged。本轮仅更新其两份交接，未在旧树开发。开工状态与来源散列见 [baseline.json](baseline.json)。

## 最终实现

现有 `/api/practice/tasks` 和助教/老师两组任务继续使用，按开关加入词汇 v2；新增 `/practice/vocabulary/tasks/{id}`。既有四类刷题与旧听写行为保持。浏览器返回缓存页面会刷新任务列表。

新增主题蓝图与适配服务处理姓名/账号身份、CSRF、同源验证、队列清洗、只读状态、答案/订正、复习和结算。GET 不创建或推进学习；写请求仍经过共享日期与领域规则。姓名重复拒绝，任务归属统一查询，取消任务不会因 ORM 缓存而恢复可写。

把 Task→PlanItem 同步和词汇结算抽为共享服务；小程序保留原包装接口与前置门禁。首答、补练、复习及结算仍共用既有模型，不增加 schema 或修改教学算法。已保存结算校验队列令牌后只读返回，不重复追加时长、凭证或学习记录。

网页采用批准原型的大屏双栏熟悉材料、居中作答、固定底部主操作。7 个 JS 模块分别负责纯逻辑、渲染、详情、传输/音频、事件、恢复、页面状态；各模块少于 400 行。包含六题型、订正、阶段切换、结果、键盘/IME 守卫、弱网重试、按身份保存待提交请求、跨窗口同步和音频失败重播。

原验收 SHA-256 冻结在 [manifest.json](manifest.json)：21 产品/配置/CI 文件、9 测试文件。本轮新增补测后测试/CI 散列已改变，当前候选以 [prepush-manifest.json](prepush-manifest.json) 为准。原日志和原散列保留作历史证据；两个交接和本报告另计。

## 原验收验证（本轮补测见审查分支记录）

| 检查 | 结果 |
|---|---|
| Python 3.13 unittest 新增及相关回归 | 226/226，29.723 秒 |
| Python 3.10 相同 unittest（旧测试 UTC 别名兼容入口） | 226/226，32.947 秒 |
| 日期门禁 pytest | 两版本各 20/20，0.49 / 0.39 秒 |
| Node 新页面与原任务列表/导航/词汇反馈 | 58/58，其中新页面 31 项 |
| 10 个 Python 产品文件原生 3.10 编译 | 通过，不注入 UTC 别名 |
| 新增 Python 产品/测试/验收脚本 Ruff | 通过 |
| 两个模板 Jinja 解析、7 个 JS 语法检查 | 通过 |
| `git diff --check` | 通过 |

完整输出见 [validation](validation/)。并发专项使用两个真实 SQLite DBAPI 连接与线程屏障，同 attempt 仅一首答记录、一次 stage 推进。网页/小程序独立客户端交替后，首答 5/6=83.3% 不因重试而改变；网页结算与家长端/PlanItem 一致，重复传入 900 秒不会改首次 65 秒。

### 可复现命令

在实施树根运行。验收时 `.venv` 曾临时链接到 Mac 原环境；已移除该链接，以下直接使用绝对路径。

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest \
 tests.test_task_plan_item_sync tests.test_vocabulary_task_submission \
 tests.test_practice_student_identity tests.test_practice_vocabulary_tasks \
 tests.test_practice_vocabulary_web tests.test_practice_vocabulary_routes \
 tests.test_practice_vocabulary_task_list tests.test_practice_vocabulary_adversarial \
 tests.test_vocabulary_group_learning tests.test_vocabulary_group_learning_api \
 tests.test_vocabulary_autonomous_review tests.test_vocabulary_flow_backlog_gate \
 tests.test_auto_student_accounts tests.test_miniprogram_grading \
 tests.test_task_date_gate tests.test_task_date_gate_display_contract \
 tests.test_vocabulary_error_review_integration tests.test_vocabulary_numeric_learning \
 tests.test_vocabulary_numeric_review tests.test_vocabulary_stage2_adversarial -q

# 使用上面相同的模块列表，去掉 -q：
/private/tmp/studytracker-web-vocab-py310/bin/python \
 docs/reviews/web-vocabulary-task-page-20261126/run_compat_tests.py <相同模块列表>

/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest tests/test_task_date_gate.py -q
/private/tmp/studytracker-web-vocab-py310/bin/python -m pytest tests/test_task_date_gate.py -q
node --test tests/test_practice_vocabulary_core.js tests/test_practice_task_lists.js \
 tests/test_practice_shell.js tests/test_vocabulary_feedback.js
git diff --check
```

Python 3.10 的旧测试 `test_miniprogram_grading` 使用 3.11 才提供的 `datetime.UTC`，所以兼容入口仅在测试进程补 `timezone.utc` 别名。没有改产品来掩盖兼容问题。首次 3.10 环境缺 Flask/JWT；新建独立环境并安装轻量测试依赖。第一次全组因缺 pytest 导入失败，补依赖后重跑通过。`test_task_date_gate.py` 是 pytest 函数，unittest 不收集其测试，已单独实际跑 20 项，不能把模块导入当日期测试通过。

## 浏览器验收

用 CUA 控制本机 in-app browser，全部是 [serve_fixture.py](serve_fixture.py) 创建的内存数据库和虚构身份。TTS 为本地合成音，未访问真实语音服务或加载模型。没有连接生产数据库。验收服务已关闭；以后可从实施树运行：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python \
 docs/reviews/web-vocabulary-task-page-20261126/serve_fixture.py
# 本机入口：http://127.0.0.1:5111/__qa/start/comprehensive
```

`127.0.0.1` 仅该 Mac 可访问，不能交给用户手机作为可用预览链接。测试专用 `/__qa/` 路由只在验收脚本存在，产品蓝图不包含这些路由。

已实际操作与核对：

- 综合目标：熟悉 → 拼写错答 → 显示差异 → 照答案订正 → 数字键语境选择 → 选择题错答/文字订正 → 50%（2/4）首答结果、2 个仍待复习；刷新回到原题。
- 写作目标：模拟首次写成功但响应丢失，自动重发同答案；连续保存失败后显示重试，恢复后原答案提交成功；语境填空两题；结算连续失败不显示已完成，重试后得到 100%（4/4）结果。
- 复习门禁：显示本批 1 题 → 看词写义 → “忘了”明确按未掌握记录 → 复习结算后自动返回原任务。
- 听力：听音选义与听音拼写；答前没有英文词/音标；合成音频失败显示重播，恢复后可播放。
- 未来任务只读提示；帮助弹窗、Esc 关闭、Tab 焦点与 3px 可见轮廓；中文 IME/长按/多窗口边界另外有 Node 和双客户端自动化测试。
- 1440×900、1280×800、1024×768、390×844；窄屏转单栏，未发生横向溢出，底部主操作在视口内。
- 另测 1152×720 和 960×600 可用视口，作为 1440 屏下 125%/150% 缩放可用空间的代理；两者主按钮底边分别 707.5 / 587.5，处于视口内。**这不是浏览器原生缩放测试**，IAB 的缩放快捷键没有改变缩放；真实 125%/150% 缩放与 Safari/Edge 尚待发布前人工核验。

截图在 [screenshots](screenshots/)。建议先看 [最终熟悉页](screenshots/page-final-1440.jpg)、[订正页](screenshots/correction-1440.jpg)、[填空页](screenshots/context-fill-1440.jpg)、[最终结果页](screenshots/result-final-1440.jpg)。旧 `result-1440.jpg` 是修复阶段完成标记前的过程证据；最终版本以 `result-final-1440.jpg` 为准。

独立复核和浏览器发现后已修复：语境选择题反馈显示内部选项 ID、结算后阶段标记复位、同会话切焦点重置复习时长、跨题同步时可能播放上一题音频。对应 Node 回归均已加入，最终 31 项通过。选择题订正把公开标签映射到原选项 ID；不更改领域判分。

## 验收对应与边界

| 计划 | 证据 |
|---|---|
| A01–A02 入口和兼容 | 实际 app 任务列表 5 项、列表 service 3 项；现有 Node 任务/导航回归 |
| A03–A05 状态、日期、身份 | routes/web/identity 测试；GET 零写入、默认 off 11 端点零写入；未来页浏览器截图 |
| A06–A07 题型/订正 | 四目标实际领域全流程六 mode；数字/同义词；任务与复习 context_choice 订正；综合流程浏览器实走 |
| A08–A10 键盘、音频、重试 | 31 Node；双连接幂等；浏览器同 ID 重试、保存失败恢复、音频失败重播 |
| A11 跨端 | 独立 cookie/Bearer 客户端交替、旧位置拒绝；尚未真实微信设备联调 |
| A12–A13 结算及同步 | 失败回滚/重放、家长 API/PlanItem 一致；浏览器结算失败重试 |
| A14 布局/可访问性 | 四种视口和两个缩放空间代理；原生缩放、其他浏览器与真实输入法仍保留人工验收项 |

没有做全仓测试、全浏览器兼容或生产性能测量。真实 TTS 的音质与延迟、小程序真机切换、生产姓名档案重复情况未验收；测试不等于这些环境已经通过。

## 交付与下一步

用户已授权仅提交、推送 `codex/web-vocabulary-task-page-20261126` 并运行 CI。当前补测和远端状态见 [branch-review.md](branch-review.md)；原接受的验证正文保留作历史记录。旧资料树仍只更新 `docs/CODEX_HANDOFF.md`、`docs/WORKLOG.md`，不能把它当作含本实现的源码树。

没有授权合并/推送 main、部署或开启功能；无生产数据库、环境变量、服务重启、通知或小程序上传/提审/发布。默认关闭部署前需两项补测、CI 和代码审查；开启前完成 branch-review 中列明的真设备实测，并另行取得授权。全量或名单开启本轮不作决定。不要在旧 `main@6ded77d2` 资料树开发，也不要合并 Claude 文档分支。
