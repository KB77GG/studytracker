# `.15` 修复后：抄题与迁移回归、本机升级静态核查

工作树 `/private/tmp/studytracker-iwa-prompt15-recheck-20261113`，分支 `codex/iwa-prompt15-recheck-20261113`，HEAD `8884e9d9`（精确SHA见JSON），本轮业务修复 `0701bcf5`。先读了新约定 `docs/design/iwa-prompt15-fix-claude-20261113/README.md`，以及该树AGENTS/CLAUDE和两交接。起止工作树clean。本目录写在旧主资料树 `/Users/zhouxin/Desktop/studytracker`，不表示旧主树具有新产品代码。

**抄题边界未退步；本专项无新增阻断项。升级部分仅静态审阅，未操作实际服务、配置或数据库。**

## 复跑结果

| 检查 | 结果 | 依据 |
| --- | --- | --- |
| 作者 `confirmed_probe_adapted.py` + Mac 真实官方样本 | 70/70 | 原样运行；34词确认抄题、194词自写，三种连接符半词拒绝、完整词保留、普通非法标注拒绝、旧schema迁移全部保持 |
| 独立 `token_migration_probe.py` | 22/22 | 从上轮逐字复制，未改变用例/预期；2592候选、313接受、2279拒绝、294双片段，0半词或重复扣；三种完整词均151→150；`.14`真实SCHEMA的5表6行连续迁移两次全部保持 |
| 原 `.14` `paragraph_probe.py` + Mac真实历史回答 | 70/70 | 原样运行；两个历史回答仍保留9段、计数15=15、0超限；分数5.5/5.0不变，完整确认34/194；实际JS渲染和复制事件通过 |
| 本机升级源码静态检查 | 9/9 | `upgrade-static.json`；未读`.env`值或运行control |

`essay.py` 与首轮 `.15`（`652450ca`）逐字相同；新代码没有碰已通过的词边界实现。`storage.init_schema()` 仍只按缺失列增加可空 `image_check`；从 `.14` 出发已有 `copied_spans` 不重建或修改。独立合成迁移核实了已有非空抄题元数据、ready读图结果、历史评价和额度逐字段不变、外键通过。

`paragraph_probe.py` 的旧回答仅离线重放，不是新模型评分；30篇消息对照的构造没有注入新的人工确认读数，只能证明这些文本输入的兼容性。该探针中的Node VM不是浏览器截图。实样文件和历史run前后SHA不变，报告只含数字/哈希，不含正文或思考过程。

## 本机升级静态结论及顺序

私有控制脚本 `.tmp/ielts-writing-ai-trial/control.py:7` 当前仍指向 `.14`：

```text
/private/tmp/studytracker-iwa-prompt14-review-20261113
```

通过全部复核后，目标ROOT应改为新审阅树；`PYTHON`继续使用主资料树venv，`CONFIG`继续指控制脚本同目录`.env`。不需要复制配置进worktree或改变Key。该脚本明确清掉继承的`IWA_*`、PYTHONPATH和代理，再设置现有私有配置路径。当前`config.py`、`__init__.py`、bin启停脚本及gunicorn配置相对`.14`基线`cd82fc1b`没有改动。

后续执行者应遵循以下次序；本专项**没有执行**这些运行操作：

1. 用旧控制路径的非秘密`check`和可信PID检查，核对实际数据目录、DB路径、端口仍为5055，以及vision仍为none。`start-live`固定读取`CONFIG.parent/var/iwa.pid`，必须与实际DATA_DIR相符。本次不读`.env`，因此这一点尚未用实际配置认证。
2. 核对没有正在生成的任务，再停止旧实例。若由临时launchd任务维持，先确认旧wrapper会退出且不会自动拉起旧实例；重用相同标签之前处理旧任务状态。不能只改ROOT然后把“已在运行”当新版本启动成功。
3. 在新代码首次启动之前，备份私有control.py、`.env`、会话secret_key，以及SQLite一致性快照；有用户上传时保留上传目录。采用SQLite backup API，或在所有写入停止后完整处理WAL；不能只复制一个仍有未合并WAL的主DB文件。备份仍放本机0700/0600目录，不提交配置或数据。
4. 只替换控制脚本ROOT，保留已核对的配置与数据路径；新`check`应显示模型、预算、超时等沿用原值，vision保持none。启动后核对实际进程工作目录/导入源码与新树一致，不能只看health返回成功。
5. 启动会按 `create_app` 的 **实例锁→init_schema→fail_interrupted** 次序执行。`init_schema`只补可空列已用合成库验证；但完整启动还会标记普通queued/running任务中断、pending读图失败，故不能把迁移字段保持等同于全部任务状态绝对不变。ready但未核对的Task1排队项有保留分支。升级前若有活跃任务，应先处理或等其结束。
6. 核对新增列为NULL、既有业务字段及账户/历史/额度计数不变、旧完成记录显示legacy提示且不能补确认；检查登录/退出和页面。无需提交作文或调用真实模型。失败时停新实例并恢复原control/必要的私有快照，先确认没有新用户写入再恢复DB，避免覆盖新数据。

以上是静态部署建议，**不声明当前PID/健康状态、launchd状态、实际库字段或私有配置已被本专项核验**。沙箱下`ps`权限不足导致PID不可信时也不能误认为服务已停。保持“识图关闭、新批次未开始”的既有边界；用户选择改正后继续，不等于重新打开已关闭账本。

## 精确复现命令

从 `/Users/zhouxin/Desktop/studytracker` 执行；解释器为本机项目venv（Python3.13.3）。三个探针都离线，阻断网络、清除外部`IWA_*`，不读Key或真实试用库。

```bash
.venv/bin/python -B /private/tmp/studytracker-iwa-prompt15-recheck-20261113/docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/confirmed_probe_adapted.py \
  --repo /private/tmp/studytracker-iwa-prompt15-recheck-20261113 \
  --private-sample /Users/zhouxin/iwa-calibration/official_lowband_t2.jsonl \
  --output docs/design/iwa-prompt15-recheck-20261113/copy/confirmed-adapted.json

.venv/bin/python -B docs/design/iwa-prompt15-recheck-20261113/copy/token_migration_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt15-recheck-20261113 \
  --output docs/design/iwa-prompt15-recheck-20261113/copy/token-migration.json

.venv/bin/python -B /private/tmp/studytracker-iwa-prompt15-recheck-20261113/docs/design/iwa-prompt14-review-20261113/paragraph_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt15-recheck-20261113 \
  --private-run /Users/zhouxin/iwa-compare-official-lowband-20261113/official-t2/run_data.json \
  --samples-dir /Users/zhouxin/iwa-calibration --baseline abf48d49 \
  --output docs/design/iwa-prompt15-recheck-20261113/copy/paragraph-original.json

git -C /private/tmp/studytracker-iwa-prompt15-recheck-20261113 diff --exit-code 652450ca..HEAD -- tools/ielts_writing_ai/essay.py
git -C /private/tmp/studytracker-iwa-prompt15-recheck-20261113 diff --exit-code cd82fc1b..HEAD -- tools/ielts_writing_ai/config.py tools/ielts_writing_ai/__init__.py tools/ielts_writing_ai/bin tools/ielts_writing_ai/gunicorn.conf.py
```

本目录是脱敏本机审阅材料，尚未commit/push；未改旧报告、规范交接或产品。规范交接由主agent汇总。没有付费调用、生产操作或部署；多locale/全套测试、识图门禁专项与实际升级均由主流程另行记录。
