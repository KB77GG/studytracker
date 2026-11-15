# 数字冲突修复复验通过，Mac 已升级（2026-11-15）

**原实样漏删和合成误删均已关闭，本机试用已切换到业务提交 `3c70332`。** 提示词仍为 `.15`，识图保持开启；本轮全部模型处理为离线重放，没有新增真实调用，也没有重新处理已保存的历史结果。

复核及升级源码为 `/private/tmp/studytracker-iwa-task-conflicts-final-recheck-20261115`，分支 `codex/iwa-task-conflicts-final-recheck-20261115`，验收时 HEAD **`68b6d4f232620bdf0f1facac0720e8744b88595c`**。后续文档共享提交不改变业务代码。已读取作者[修复交接](../iwa-task-conflicts-fix-claude-20261114/README.md)，以下结论来自本机独立验证。

## 复验结果

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 八份原始回答离线重放 | **205/205**，主审独立复跑一致 | [replay.json](replay.json)、[replay-root.json](replay-root.json)、[复核说明](replay-review.json) |
| 原数字冲突相邻反例 | **72/72**，预期未改 | [adjacent.json](adjacent.json) |
| 原确认绑定及排队门禁 | **109/109**：20 + 57 + 15 + 17 | [命令与结果](regressions/README.md) |
| 完整工具测试 | **507 Python + 8 Node** | [offline-tests.json](offline-tests.json) |
| 静态检查 | Ruff、Black 71 文件、JS 语法和 diff 通过 | [root-verification.json](root-verification.json) |

L9 和 L11 是本批仅有的两条新增删除，均与此前确认的数字冲突一致；另 **79 条可见建议逐字保持**。L9 的完整 TA 引文可以唯一定位，显示中的 TA 评论确实点名了被替换的百分比；原 TA 改正建议继续被无来源数字保护隐藏，新规则只据此拦住保留旧数值的 GRA 建议。L11 的时长冲突继续被拦住。没有发现内部完整引文或原始建议进入公开结果。

八份旧结果逐字段精确重现，新旧分数、模型消息、提示词上下文、原稿和读数输入均不变。原批 44 个文件及两源树产品 SHA 保持，网络尝试为 0。H1 的引文警示、H2 的原有建议过滤、H3/H4 的问题评论以及 L1/L4/L5/L7 的趋势冲突保持原状态，不宣称已修复这些模型判断。

相邻探针确认上轮四个合理建议不再误删（同句不同对象、百分比与时长、小时与百分比、重复短引文），超过 300 字的合法 TA 引文也能完整参与内部判断。分数、评语和独立删除计数保持。

## 为什么是 205，而不是 204

原探针的检查数由结果动态决定：每条保留建议检查 1 项，每条新增删除检查 2 项（删除标记、评语保持）。L9 从保留变为正确删除，因此总数自然由 204 增至 **205**。

原脚本另有 35 行私有调试代码依赖第一版 `_Sentences` 等内部接口，新版已删除这些接口，直接运行会在诊断阶段报错。此次[适配副本](replay_probe.py)只去掉这段诊断；所有归一化、验收检查、预期和输入/源码保护保持。验收段逐字一致及 SHA 记录在 [replay-review.json](replay-review.json)，完整补丁见 [replay-adaptation.md](replay-adaptation.md)。没有通过修改预期得到通过结果。

## 精确复验命令

从主资料树 `/Users/zhouxin/Desktop/studytracker` 执行。两源树须 clean；完整回答只输出至已 Git 忽略的私有目录。实样命令需要 Mac 上的私有批次文件，另一台电脑可独立运行合成探针。

```bash
.venv/bin/python -B docs/design/iwa-task-conflicts-final-recheck-20261115/replay_probe.py \
  --baseline /private/tmp/studytracker-iwa-official-t1-replay-20261114 \
  --candidate /private/tmp/studytracker-iwa-task-conflicts-final-recheck-20261115 \
  --run-data /Users/zhouxin/Desktop/studytracker/.tmp/iwa-official-t1-20261114/run/evaluate/run_data.json \
  --raw-calls /Users/zhouxin/Desktop/studytracker/.tmp/iwa-official-t1-20261114/run/evaluate.raw-calls.private.jsonl \
  --private-out /Users/zhouxin/Desktop/studytracker/.tmp/iwa-task-conflicts-final-recheck-20261115/replay-again \
  --out /private/tmp/iwa-final-replay-again.json

.venv/bin/python -B docs/design/iwa-task-conflicts-recheck-20261114/adjacent_probe.py \
  --repo /private/tmp/studytracker-iwa-task-conflicts-final-recheck-20261115 \
  --out /private/tmp/iwa-final-adjacent-again.json

.venv/bin/python -B docs/design/iwa-task-conflicts-recheck-20261114/run_offline_tests.py \
  --repo /private/tmp/studytracker-iwa-task-conflicts-final-recheck-20261115 \
  --out /Users/zhouxin/Desktop/studytracker/.tmp/iwa-task-conflicts-final-recheck-20261115/offline-again
```

以上复用本轮实际命令，只将产物名称改成 `again` 防止覆盖已有证据。门禁四条精确命令见 [regressions/README.md](regressions/README.md)。测试包装器使用 fake 模型、临时数据目录、阻断非回环连接，并故意设置外部 `IWA_VISION_PROVIDER=none`；哨兵数据目录未写入。实际运行 Python 3.13.3，未重复作者另两种 locale、Python 3.10 或全部历史探针。

## Mac 已升级

复验通过后，先确认无运行中任务，使用 SQLite backup API 一致性备份数据库并保留私有配置/会话材料，再将私有 `control.py` 的源码目录切到新树。备份在 `.tmp/ielts-writing-ai-trial/backup-before-task-conflicts-20261115-221302/`，旧运行树 `40c0b5f1` 保留用于回退。

新进程 **PID 56425**、`127.0.0.1:5055` 健康，实际 cwd 与新源码一致；数据库 schema 和全部原有行保持，70 项受保护配置/批次文件哈希不变。登录、认证页、CSRF、退出和额度 **30/30** 验证通过，仍为 1 账号、0 作文、0 生成、0 用量；没有触发生成请求。详见 [service-state.json](service-state.json)、[login-check.json](login-check.json)。本轮完成的是 HTTP 验证，没有重复真实浏览器完整核图流程。

识图仍为 DeepSeek Flash，2000 tokens / 180 秒；评价为 Pro / high / 32000 / 420，精修与改写仍 Flash。配置和会话 secret 原字节保持。旧 `1 图 / 0 文字` 与新 `3 图 / 8 文字` 两个批次继续 closed，不续用余额；本轮真实模型调用 **0**。

## 边界与交接

这项检查仍采取保守过滤，并未理解所有实体、单位或事实：

- 如果一条完整 TA 引文同时包含两个相同数值，只纠正一个、另一个保留，集合比较可能漏检；这是既有保守边界，与原探针的数值集合互换情形一致，未形成新的升级阻断项。
- 数值类别只是百分比、普通数字等已有粗分类，不等于完整的实体和单位语义解析。
- TA 评论点名一个数字，不等于该模型评论已被独立证实正确。

趋势方向冲突、H3/H4 评论与评分校准仍待教师实际意见；老师 10 项抽查尚未填写。本次通过仅关闭已复现的程序问题，不代表模型已校准，也不授权追加付费批次。

主资料树仍为 `/Users/zhouxin/Desktop/studytracker` 的旧 `main@6ded77d2`，既有 7 modified / 23 untracked 顶层入口和其他任务改动保留，不作为试用运行源。本轮只新增脱敏报告及本写作任务交接增量；完整原稿、题图、确认读数、回答/思考、配置、Key、数据库、备份和完整日志均留 Mac。按既有授权仅将脱敏材料同步功能分支，最终 commit/push SHA 以 Git 回读和规范交接确认条为准；没有合并 main、部署生产后端/前端/数据库或发布小程序。
