# 词汇页与刷题批1联合发布（2026-11-27）

用户已明确授权部署；沿此前分两步发布约定，本次词汇全局开关保持关闭，刷题批1修复随同上线。此文档是联合候选的当前记录，之前两个报告的“仅本机/未部署”描述属于历史阶段，最终状态以本文件后续发布记录和交接为准。

## 候选与范围

- 隔离树 `/private/tmp/studytracker-practice-web-joint-release-20261127`，分支 `codex/practice-web-joint-release-20261127`。
- fresh main `f5b06cc3cb44fa1f77720ca771bde3134c83a71d`；快进整合已含该main的词汇 `0ab901e843ca01a7bc5cc8ffc78e11b372feaadb`。
- 刷题批1从 `/private/tmp/studytracker-practice-web-batch1-20261126@f81a5e4a` 按14项manifest逐SHA核验后，以三方patch导入，新测试与原审查/验收文档复制。原工作树未变，未合Claude文档分支。
- 产品三方差异只有CI、任务首页和听力模板，全部自动合并并独审。保留词汇pageshow、main冲刺媒体兼容和批1的身份/返回/保存/解析入口修复。`merge-review.md`列出逐块核对。
- 联合阶段仅适配两测试文件：身份测试补真实窗口事件mock并新增缓存返回/切换身份断言；模考完整性测试更新经独审的听读模板SHA，保留四页实际渲染字节一致断言。产品没有为了测试改行为。
- `manifest.json`记录75项候选产品/测试/CI SHA与28项相对main改动的产品文件；发布前后按这些散列核对。

## 验证

工作目录均为联合树。精确argv、日志、退出码和耗时在`py313-commands.json`、`py310-commands.json`、`node-commands.json`。

```text
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-joint-release-20261127/run_checks.py py313
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-joint-release-20261127/run_checks.py py310
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/practice-web-joint-release-20261127/run_checks.py node
```

- Python3.13与3.10各：词汇/冲刺/模考等574 unittest、日期20 pytest、批1私有SQLite57 unittest全部通过。
- 3.10的574套件沿原已审runner仅对旧测试datetime.UTC做进程内兼容别名；产品未注入别名。批1 57项和日期20项直接原生3.10运行，无别名。生产Python3.10编译检查独立通过。
- Node198/198，独立精听退出9/9，部署拼写队列guard exit0。
- 71项原生3.10编译/Jinja/JS/YAML检查通过（`static-checks.json`），定向Ruff与产品/测试/CI范围diff通过。缺PyYAML时改用已安装Ruby YAML，没有安装依赖。
- 初跑Node5项因旧mock缺window监听失败；Python唯一失败为旧模板SHA。初始日志保留，修复测试适配后上述套件全过，未删测试或放宽产品断言。
- 生产预检`production-preflight.json`通过：旧生产3b26404c tracked clean、active/running、worker1、gthread6、5002，词汇flag未配置/默认false；本轮未修改生产环境、未加载app或模型来验证。

## 发布状态

产品提交 **`efeac80c468cc47a6347d6136b6736c1ddbd0996`** 已commit/push至联合分支及main，并成功部署。

- 分支CI [45859881600](https://github.com/KB77GG/studytracker/actions/runs/45859881600)：overall success，test/account-provisioning/task-planner三业务作业全部success；既有非阻断lint failure仍存在，不称全仓lint通过。
- 部署 [45860718737](https://github.com/KB77GG/studytracker/actions/runs/45860718737)：success；生产启动时间2026-11-27 00:39:46 CST。
- main CI [45860718805](https://github.com/KB77GG/studytracker/actions/runs/45860718805)：overall success，三个业务作业全部success，与分支CI为同一SHA；旧非阻断lint failure仍保留，完整结果见main-ci.json。
- `production-postdeploy.json`全部检查通过：生产HEAD与产品提交一致、tracked clean、active/running、NRestarts0、实际单worker，配置gthread6/5002保持；28项产品SHA和11项公网静态资产SHA全部一致。`production-postdeploy-command.json`记录精确只读命令。
- localhost和公网的词汇任务0页面/GET state均403 feature_disabled/no-store；页面boot为blocked，且没有学生身份/CSRF数据，关闭提示文案已随JS发布。生产开关未配置，默认false。`/practice`和登录页健康，受保护后台仍跳转登录。没有匿名调用任何写接口。
- 刷题批1修复已生效；词汇代码已部署，但**尚未开放给学生**。剩余真设备门槛保留，不能将部署授权当作开启授权。
- 当前报告、生产证据与最终交接以独立`[skip ci]`文档提交同步main/联合分支，不重复部署。最终文档HEAD以Git为准，服务器业务HEAD仍为上述产品提交。

产品/测试/CI范围`git diff origin/main基线..产品提交 --check`通过；全量原始文档diff有patch上下文、初始失败日志空行和复制runner末尾空行的格式告警，原始证据保留，见`diff-check-evidence.json`。它们未改变测试结果；不能把全量文档diff说成零告警。

## 尚未验收与操作边界

默认关闭部署不代表已开放背词。系统拼音/完整物理长按、1280/1440原生125%/150%组合、手机互切、老师家长真实UI等仍保留在`web-vocabulary-task-page-20261126/browser-retry/README.md`。Safari held-enter截图空白问题未解决；订正刷新、Chrome离线/丢回包和10分钟离页计时的真实证据仍有效。

本次无模型/表结构变更、无人工生产学生记录写入，无小程序前端改动/上传/提审/发布，不扩大到刷题批2/批3。生产只读探针不能宣称已登录所有学生实际看过任务列表；关闭接口运行结果、列表自动测试和源码散列共同说明默认关状态。
