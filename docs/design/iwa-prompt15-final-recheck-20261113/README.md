# `.15` 最终复验通过：旧记录排队P2关闭，本机试用已升级

复核基线 `e3901a0c4312f42c7a90996f47e18b4d96d4935d`，业务修复 `d92f0839`。原剩余P2在不改变预期的反例中从15/20变为 **20/20**；原五项问题现全部关闭，未发现新的升级阻断。Mac试用已从`.14`切换到`.15`，识图仍为`none`，0真实模型调用，关闭的批次不重开。

## 独立复验

| 检查 | 本轮结果 |
| --- | --- |
| 原双worker排队反例（预期未改） | **20/20**，confirm/skip均409、旧标签保留、旧精修/改写不变 |
| 作者适配网页探针 | **45/45** |
| 新网页相邻检查 | **57/57**：全部三项再生成、历史started_at、各输出绑定、请求期间输入变化可见、skip/无图边界 |
| 原realcheck / 相邻检查 | **15/15、17/17** |
| Mac官方实样确认 / 原段落与历史回答 | **70/70、70/70**；34抄题/194自写、两旧回答9段和5.5/5.0保持 |
| 词边界与迁移 / 识图预算 | **22/22、139/139**，0网络尝试 |
| 完整套件（外部IWA_VISION_PROVIDER=none） | **494 Python + 8 Node** |
| 静态检查 | 产品Ruff、Black69文件、JS语法；新报告脚本Ruff/Black通过 |

SQL条件现同时要求存在排队任务且全部历史生成从未开始，页面与原子写库共用同一条件。仅看最新三项都queued也不能重新开放旧记录核对。每份新的带图Task1结果记录`chart_reading`，实际输入与当前确认读数不符时页面警告。未核对时读数不传模型，指纹为null；这并不表示模型使用了未核实的数字。

限制：没有快照的历史结果不会被`reading_mismatch`反推读数版本；`.14`旧记录已验证持续显示legacy提示。相邻探针中started_at和请求期间更改读数的边界用合成库直接设置，原20项则全部经公共API与真实双worker。未重跑多locale、Python3.10或真实浏览器核图交互；作者相关报告仅作参考，Mac实测范围如上。未声称模型评分质量已完成校准。

在主资料树执行：

```bash
.venv/bin/python -B docs/design/iwa-prompt15-final-recheck-20261113/run_offline_tests.py
```

跨机器可用 `python -B run_offline_tests.py --repo /path/to/checkout --out /path/to/evidence`；需已安装项目依赖、Node与本机测试端口权限。包装器清继承配置/代理、禁止非回环网络、使用临时数据。首次沙箱运行24权限错误，获准同脚本重跑后全部通过；完整日志仍留Mac。其他精确命令与结果见[网页专项](web/README.md)、[realcheck专项](realcheck/README.md)、[实样专项](copy/README.md)及`validation-summary.json`。

## 本机升级与核验

- 升级前旧`.14`实际PID92571、5055健康；数据库1用户、0作文/生成/用量，active/pending均0。
- 已停止旧实例，使用SQLite backup API做一致性快照，并备份control、私有配置、会话密钥与上传目录。备份位于`.tmp/ielts-writing-ai-trial/backup-before-prompt15-final-20261113-222434/`，0700/0600，仍仅本机。
- 仅将私有`control.py`的ROOT改为新源码树。新PID **31407**、5055健康，实际进程cwd核对为`/private/tmp/studytracker-iwa-prompt15-final-recheck-20261113`，临时launchd标签仍`local.studytracker.iwa-trial`。
- 数据库只新增可空`image_check`列，迁移前后全部原字段逐表校验一致，完整性/外键通过；用户1、作文/生成/用量0不变。随后登录、页面、CSRF、退出检查通过，额度30/30；没有提交作文。
- `.env`和会话secret原字节不变，评价仍Pro/high/32000/420，精修改写Flash，**vision none**。旧Task1账本和`batch-closed.json` SHA不变。`upgrade.json`与`login-check.json`只保存非秘密配置、计数与布尔结果。
- 精确本机操作：`.venv/bin/python -B .tmp/ielts-writing-ai-trial/upgrade_prompt15_final.py`，然后`.venv/bin/python -B .tmp/ielts-writing-ai-trial/login_check_prompt15.py`。私有脚本不提交。前者固定本次旧版本/空库前置条件，不用于重复升级；备份失败和启动验证失败会恢复旧控制路径并核验旧服务重启。

## 共享与交接

用户本轮明确要求一并上传本机复核材料。共享旧两轮审阅/复验（含followup）的46份脱敏文件，以及本轮报告/探针/聚合证据与`docs/CODEX_HANDOFF.md`、`docs/WORKLOG.md`，仅提交至`claude/ielts-writing-ai-trial`。旧报告中的“仅本机/未推送”和“.14未升级”是当时状态，当前状态以本报告和规范交接最新条目为准；原旧ZIP未重打包。

三份Claude独立记录均已读取并合并其当前事实：`iwa-prompt15-claude-20261113`、`iwa-prompt15-fix-claude-20261113`、`iwa-prompt15-fix2-claude-20261113`。原始说明仍在功能分支保留。旧反例用于历史回归，原网页探针对已拒绝的旧记录仍按旧成功预期读取，会报空值错误；当前验收用作者adapted版本与独立排队探针。两个历史全套runner保留当时Mac路径，本轮runner已支持路径参数。

私有样本/题图、学生或教师材料、完整模型回答/思考、Key、配置、SQLite、账号与完整日志不上传。`share-audit.json`为旧46份白名单，`delivery-manifest.json`记录本轮共享文件。7个私有输入SHA未变，95产品文件未改；报告同步不改变产品代码。

主资料树`/Users/zhouxin/Desktop/studytracker`仍main@`6ded77d24586327ad94e151e172ae4811b4a2eed`，原7modified/23untracked顶层入口及其他任务改动保留，不从此旧树发布。新独立树分支`codex/iwa-prompt15-final-recheck-20261113`，e3901a0c基线；本轮仅新增报告及交接文档。旧8884e9d9、652450ca和cd82fc1b源码树不修改；运行路径已切到新树。提交后的文档HEAD与远端同步结果由Git及主资料树最终确认条记录。

没有合并/推送main或部署生产后端、网页、数据库及外部服务，小程序未上传/提审/发布。后续Task1批次仍须单独明确范围和调用上限，按既定“读错先改正、确认后继续”执行。教师82页完整包已在Mac补齐，10项抽查仍待老师填写；不把AI初判当教师认可。
