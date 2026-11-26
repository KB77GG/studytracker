# 刷题网页批 1 修复验收（2026-11-26）

批 1 的九项问题已修复，本地验证通过。**仅本机，未 commit/push/部署；远端 CI 未运行。** 批 2 导航统一、批 3 视觉改版不在本轮范围。

## 工作树与来源

- 实施：`/private/tmp/studytracker-practice-web-batch1-20261126`，`codex/practice-web-batch1-20261126`，HEAD/开工基线 `f81a5e4a4d81282eb67b994a4cfcc5574fb78747`，开工 clean。
- 基线对照：`/private/tmp/studytracker-practice-web-batch1-baseline-20261126`，detached 同一提交，保持 clean。
- 审查源：`claude/clever-heisenberg-8evbm0@54078056ede59d563c14dc1b0c69fc0d05b0c173`。10 份报告/原型/巡检文件只读复制，逐字节核验见 `source-provenance.json`；没有合并文档分支。
- 既有词汇页分支 `/private/tmp/studytracker-web-vocabulary-20261126` 保持 `fc3b049a` clean，本轮未修改或合入。
- 开工 fetch 时 main 为 `f81a5e4a`；工作期间另一任务将共享 `origin/main` 更新至 `79388e269e924e9ce591dd3e6de3762a61614ddf`（考前冲刺修复及文档）。本分支未移动基线。产品路径只有 CI 共享，临时三方合并成功且双方测试步骤保留，见 `validation/incoming-main-check.json`。发布前还需整合最新 main；不能宣称本候选已包含该并行修复。

## 九项对应结果

| 审查编号 | 最终行为 | 主要验证 |
|---|---|---|
| #1、#8 | 匿名/学生不渲染老师筛选、考试切换、预览及布置按钮；老师后台布局保留；删除 5 个无效复选框 | 角色渲染测试；真实合成老师浏览器登录与选科、布置入口检查 |
| #2 | 姓名确认后表单可靠隐藏；切换学生重新显示 | 1440/1280/1024/390 四档，阻断外部 CDN 后 computed display 均为 none、无溢出 |
| #3 | 模式能力与解析 readiness 同时满足才显示；无解析旧链接 302 回同题做题页 | 空/有解析、异步模式变化、接口失败与畸形数据；真实直链跳转；白名单参数及目标安全测试 |
| #4 | 无改动的普通任务直接返回；未保存/在途内容及已开始的模考计时有确认和失败保护；文案区分场景 | 三任务返回按钮、浏览器后退；真实模板 guard 与保存失败测试 |
| #5 | 网页任务没有来源时回 `/practice#practiceAssignedTasks`；显式来源优先；小程序环境保留原 fallback | 书签直入实测，shell 网页/小程序/来源测试；没有宣称微信真机通过 |
| #7 | `/practice` 不再显示指向自己的返回链接 | 角色渲染与浏览器 DOM 检查 |
| #10 | 姓名验证和切换同步 defaults；点击/滚动读取最新身份 | 真实点击 verified_student → 切换后原身份门禁拦截 → 再验证后的链接；账户/staff 单测 |
| #11 | 初始“尚未保存”；恢复草稿/读取历史有独立提示；实际保存成功才标当前 hh:mm | 恢复不清除新 dirty、不覆盖保存中/错误；实际写入时间提示测试 |

补充边界：精听本句尚未提交的文字原本只在内存中，本轮增加明确的退出丢失提示，没有改变首答计分/保存协议。首答请求在途或结果不确定时，返回和确认退出均保留在当前页，提示刷新确认；刷新后沿现有 API 恢复服务端记录，不自动重发首答。错因笔记存储失败保留 dirty 并允许重试。独审发现的精听退出遗漏和旧记录伪显示当前保存时间问题均已修复。

8 个产品文件、5 个测试文件和 1 个 CI 文件的最终 SHA 见 `manifest.json`。`app.py`、`api/miniprogram.py`、模型、判分、计时起点及保存接口未改。

## 自动验证

全部命令工作目录为实施树。

- Python 3.13：57/57；原生 Python 3.10：57/57，**无兼容别名**。完整 argv 在 `validation/python-regression-commands.json`，日志 `python-regression-py313.log` / `python-regression-py310.log`。`run_tests.py` 导入 app 前注入私有配置、临时 SQLite，禁止外连，未加载 `.env/app.db`，network calls=0。3.10 的旧老师测试有短 HMAC fixture 警告，不影响结果。
- Node：112/112（其中 shell 22），命令 `validation/node-command.json`，日志 `node-regression.log`。涵盖 shell、模式、身份、阅读入口、听读导航、精听重做、任务列表与后台结构。
- 静态：5 模板 Jinja、CI YAML、原生 3.10 编译、定向 Ruff、JS syntax、diff 检查通过；精确命令与日志 `static-checks-commands.json` / `static-checks.log`。
- 独立精听退出反例：`node docs/reviews/practice-web-batch1-20261126/independent_exit_probe.js` → 9/9，日志 `validation/independent-exit-probe.log`；刷新场景是重建客户端内存的 helper 验证，不是浏览器断网端到端测试。
- CI 文件已登记新增回归，本轮没有提交/推送，因此**没有新的远端 CI 结果**。

## Claude 原巡检复跑

`serve_fixture.py` 使用真实 app.py、仓库题库、临时 SQLite 和合成用户。与原 boot.py 的区别仅为合成老师可登录，以及修正两条阅读 fixture 的 `_reading` 后缀；原脚本未修改。原文件与报告曾不一致：boot.py 缺后缀会造成额外任务 404，故前后统一修正 fixture，而非更改产品路由来掩盖数据错误。

前后各运行 crawl、flows、dialog、probe、probe2。`rerun_audit.js` 只替换本机端口、输出路径和已安装 Chromium 路径；`run_browser_suite.py` 记录精确 argv/退出码/用时。原始大型输出在 `/private/tmp/practice-web-batch1-before`、`/private/tmp/practice-web-batch1-after`，脱敏摘要已收在 `validation/browser-comparison.json`。

| 项目 | f81a5e4a 基线 | 修复后 |
|---|---|---|
| 目录/手机检查 | 28 个身份×目录场景 + 6 手机场景 | 同样 34 场景 |
| 做题/详情页 | 8 页，Reading Study 1 个 404 | 8 页最终均 200；旧 Study 链接实际先 302 |
| 前 500 个站内链接 | 499 个 200、1 个后台登录 302 | 500 个 200（学生后台入口已删除，集合随之变化） |
| 页面 JS 异常 | 0 | 0 |
| 三任务无作答返回 | 被确认框拦住 | 按钮和浏览器后退都回 `/practice` |
| 精听目录进入任务后返回 | 被确认框拦住 | 回 `/practices` |
| 学生预览/布置/无效筛选 | 出现 | DOM 中不存在 |
| 无解析的 Reading Study | 可见 | 隐藏 |

不能把所有原脚本退出码都称为通过：

1. `flows.js` 前后均有 1 个选择器超时：它取剑雅听力目录第一个链接，该链接位于未展开的书目。脚本虽 exit 0，内部记录 error，已保留。其他 13 条流程执行完毕；其中工作台没有 `data-practice-back` 按钮的条目仍记录“无返回按钮”，这属于后续导航统一范围。
2. 修后 `probe2.js` exit 1：脚本试图点击已经按 #1 删除的学生预览控件。新的验收同时断言学生 DOM 无该控件、老师真实界面仍有入口，故不是产品回归。原日志保留。
3. 本机 CDN 可用时，基线姓名表单已被外部样式隐藏，未重现报告的可见状态；补充验收在主动阻断 CDN 下确认修后四档均可靠隐藏。不宣称原 CDN 环境完全一致。
4. 音频文件不在 Git，音频 404 不算修复通过或新缺陷；没有音质/播放实测结论。

## 补充浏览器验收与截图

`acceptance.js` 的最终 9 项检查均通过，聚合在 `validation/acceptance-final.json`，原始与重验日志全部保留。覆盖四档学生布局、真实身份链接、三个无作答任务、书签 fallback、缺解析跳转和老师界面。身份探针首次错误地期望未验证用户能进入题库，后又使用了不能匹配导航装饰后绝对网址的选择器；只修正探针，未为通过探针修改产品。最终复验正确保留原身份门禁。

截图：
- [同环境修前学生页](screenshots/before-student-1440.png)
- [同环境修后学生页](screenshots/after-student-1440.png)
- [1280 学生页（阻断 CDN）](screenshots/student-1280.png)
- [老师后台布局与阅读选科](screenshots/teacher-1440.png)

本轮为本机 headless Chromium，不等于原生 Chrome/Safari、微信 webview、真实设备或生产账号验收。后两批的导航/视觉问题尚未处理。

## 可复现启动

```bash
# 在两个独立终端分别启动。两端均为临时合成数据库。
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-batch1-20261126/serve_fixture.py /private/tmp/studytracker-practice-web-batch1-baseline-20261126 5112
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-batch1-20261126/serve_fixture.py /private/tmp/studytracker-practice-web-batch1-20261126 5113

# 需可解析 playwright，AUDIT_CHROMIUM 可指定已安装的 Chromium 二进制。
python docs/reviews/practice-web-batch1-20261126/run_browser_suite.py before 5112
python docs/reviews/practice-web-batch1-20261126/run_browser_suite.py after 5113
node docs/reviews/practice-web-batch1-20261126/acceptance.js 5113
```

本机运行使用的依赖位置在 `validation/browser-environment.json`。收尾停止本轮 5112/5113 服务；用户原有 5055 服务未动。

## 交接与下一步

本轮新增/修改路径由 `manifest.json`、`source-provenance.json` 及报告目录列出；两份规范交接同步到实施树和旧资料树。旧资料树 `main@6ded77d2` 原 8M/27U 保留，仅两交接追加，包含并行考前冲刺与已推送词汇页记录；本轮不覆盖这些条目。

下一位先核对 Git 与文件 SHA，整合届时最新 main，保留双方 CI 和交接记录，再按用户授权提交/推送本批分支跑 CI。词汇页仍是独立分支，不能假定已在本批中。没有生产访问、服务/环境变更、数据库迁移或学生数据写入，没有微信上传/提审/发布。
