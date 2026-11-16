# 小程序任务入口加载故障修复（2026-11-16，后台已部署）

## 当前发布结果（2026-11-16 14:41 CST验收）

用户已明确授权“所有修复都部署”。后台产品提交`c0b52743`、CI依赖补齐提交`959c2019b5525769cccd33dc16f4cf2ff3cf7c53`已push任务分支及main，并完成Deploy43817657937。分支CI43817235115与main CI43817658023三业务job成功；既有advisory lint失败保留。首轮CI43810754369因新纳入旧反馈测试缺少requirements已有pyphen依赖而失败，补齐CI环境后通过，未放宽测试或改产品预期。

生产验收`production-entry-acceptance.json` ok=true：HEAD959c2019、两产品SHA一致、tracked clean；14:34:57 CST起active/running、NRestarts0、单worker/gthread6/5002。两组时间关联数据的只读preflight分别1660.488/929.347ms、summary1388.168/914.995ms，全部低于5秒；mode=ro/query_only/authorizer拒写、无ORM写入/0 total_changes、同一快照业务行数保持。未import app/config/重模型，没有创建或代答任务/复习。公网登录200/0.167785s，匿名复习API401符合鉴权。标准部署链自身既有幂等迁移和重启照常执行，本次无新增schema或人工数据改写。

这是生产实际数据服务回放与健康验收，**不是微信真机完整旅程验收**；不能保证任意设备/网络均无问题。学生现有105包调用已修后台即可获得提速。

前端7产品+2测试修复仍在固定`/Users/zhouxin/Desktop/studytracker-release/miniprogram`，100Node/官方两页编译通过。本轮截至本记录未上传/提审/发布：CUA反复报告Mac锁屏，用户已两次回复解锁，微信工具登录/整包编译与平台状态仍在处理。不能把后台部署说成新微信包已上线。完整固定前端历史源码仍仅本机，本次精确补丁/哈希归档随报告共享；严禁用main顶层旧前端覆盖固定源。

下文保留诊断和发布前验证历史；当前状态以本节及后续前端发布记录为准。

## 结论与线上证据

用户确认两图分别是11月16日10:44任务页、11月15日词汇页。词汇截图匿名trace中的时间反解为北京时间2026-11-15 17:12:45.328；trace仅在客户端生成，不能据此在服务器按编号检索。按时间、接口、设备和小程序版本105关联日志：

- 昨日17:12:45任务详情和preflight均200；17:12:55 nginx vocabulary-queue **499/0bytes**，17:12:58 gunicorn同窗队列 **200/3642bytes**。符合10秒客户端超时先断开、后台稍后成功；13秒是页面时间到完成日志的差，不是精确handler计时。
- 今日10:44:32详情200，10:44:47 preflight200；10:45:05另一次preflight nginx499，10:45:08后台200；10:49:53队列再次499。期间已有复习领取/作答/结算成功记录，不是小程序整体不可用。
- 任务页把详情显示放到preflight之后，又无持久错误/重试状态，真实模块VM复现空标题/空内容和不可恢复的空表单。词汇错误页公共按钮flex:1导致巨大胶囊。
- 后台复习资格统计对每个只能出语境选择题的到期词重新解析、排序整本候选；summary/preflight/queue都会支付该成本。已用纯合成数据库复现，属于确定性能缺陷；本轮没有线上profiler，不能把全部线上耗时归为单一函数。
- 只读生产SQLite检查与日志聚合不调用业务API、不import app/config、不建flow或改成绩。姓名匹配未能独立确认，不把同窗日志账号当作已验证的实名映射。私有输入/计数留主目录被忽略的`.tmp/miniprogram-entry-20261116/`，不入交接或远端。日志报告移除姓名、账号/任务ID、IP、query、token和会话地址。

`log-summary.json`为脱敏日志证据。全时段另有3次任务列表/历史500及数据库锁异常，未确认与两图同因，不声称所有后台错误已解决。

## 实现与工作树

- 后台实施树 `/private/tmp/studytracker-entry-backend-20261116`，分支`codex/miniprogram-entry-20261116`，基线/HEAD`878209f4d180ed1a9702b44257044ed394afd731`。新建时clean。修改`services/vocabulary_context.py`、`services/vocabulary_autonomous_review.py`、`tests/test_vocabulary_review_performance.py`；新增资格等价测试、合成基准脚本和本报告。使用请求内词书预处理与轻量选择题可用性判断；实际建题/评分函数不改，保留前三干扰项再去重等原规则。没有删除每日复习门禁或改排程。
- 固定前端源 `/Users/zhouxin/Desktop/studytracker-release`，分支`codex/miniprogram-release`，HEAD`d03a2749eb99cde041cdae18305b624956d46e90`。原76 modified/35 untracked，应用后76 modified/37 untracked。只应用7产品+2测试文件，清单/SHA在`client-review/manifest.json`；442个其他miniprogram/tests文件保持。备份在主目录私有`.tmp/miniprogram-entry-20261116/client-backup/`，未覆盖他任务改动。
- 前端修复：任务详情立即可见，显式加载/错误/重试/返回，30秒总期限、10秒慢提示；等待和失败禁提交；卸载/迟到/跳转失败处理。词汇GET30秒、写请求仍15秒，无自动重新领取/自动重复POST；错误分类和真实中文message日期门禁保留。修复按钮纵向膨胀。
- 前端候选 `/private/tmp/studytracker-entry-client-20261116`为普通副本，不是Git worktree，也不是上传源。精确patch已归档，正式上传只使用固定目录，不能用旧桌面main或后台树整包覆盖。
- 主资料树 `/Users/zhouxin/Desktop/studytracker`仍main@`6ded77d24586327ad94e151e172ae4811b4a2eed`，既有7modified/23untracked顶层入口保留，完整路径见`source-status-before.txt`。本轮只增报告/忽略私有证据和两交接。最新观察origin/main`b85c4746`相对后台基线仅他任务文档增量；未合并，发布前仍须重新核对。

## 验证

固定小程序目录：

```sh
node --test tests/test_entry_loading_client.js tests/test_vocabulary*.js tests/test_dictation_audio.js tests/test_dictation_spell_queue.js tests/test_web_practice_client.js
```

100/100通过（主审在实际固定源复跑，`client-release-tests.log`）。新增15场景包括13秒成功、30秒超时、任务总预算、迟到/卸载、显式重试、无自动写入、访问门禁中文message和跳转失败。旧源三个核心验收0/3、首版候选两类边界由独立复核发现后关闭。官方wcc/wcsc两页编译及5JS语法通过；命令见client-review/README.md。独立正常提交恰好1POST、五类原生跳转通过。

后台基准（cwd后台树）：

```sh
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/benchmark_vocabulary_entry.py --repo /private/tmp/studytracker-exam-integrity-20261114 --size 1000 --output docs/reviews/miniprogram-entry-20261116/backend-baseline.json
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/benchmark_vocabulary_entry.py --repo /private/tmp/studytracker-entry-backend-20261116 --size 1000 --output docs/reviews/miniprogram-entry-20261116/backend-root-recheck.json
```

1000词语境选择题preflight由6993.708ms到168.702ms；重复释义由6978.527ms到549.871ms。均为本机合成SQLite，非生产延时承诺。四场景的复习名单/顺序、preflight响应及首20题题面/答案hash逐一相等（`benchmark-parity.json` 16/16）。复习计数不再构建完整题目；实际出题沿用原builder。重复释义分支仍有候选遍历/hash成本，不承诺所有规模线性。

后台完整回归、独立等价探针结果及命令见`backend-validation.md`和`independent_equivalence.py`（收尾同步）。未跑全仓测试或真机弱网；小程序整包/真实账号复测和生产改善须发布后验收。

## 发布边界与下一步

发布前状态保留作历史：初诊时生产878209f4、本轮未发布。现在后台已升级959c2019并通过上节验收；小程序发包状态单独跟踪。

用户已授权，后台提交/推送/部署/验收均已完成；线上旧105包可受益于后台提速。前端修复须从固定目录微信工具编译、真机检查后由用户上传/提审/发布。不得从旧桌面main部署，不重算成绩、不清除任务/复习记录。应用记录`client-apply.json`，三树的`docs/CODEX_HANDOFF.md`和`docs/WORKLOG.md`记录本次边界。
