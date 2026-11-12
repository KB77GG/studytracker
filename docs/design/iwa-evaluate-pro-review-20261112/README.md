# 评价专用 Pro 配置：本机复核与启用（2026-11-12）

已核对功能分支 `85b8daad5b6da0cb5a2bbe653d9926bd75c2d334`（业务 `f2509aa`、`4097aa2`）。未发现阻止启用的缺陷。本轮及11月13日账号准备的新增真实模型请求均为 **0**，没有继续第一阶段账本，也没有运行官方组。

## 本机配置

实际私有配置在 `/Users/zhouxin/Desktop/studytracker/.tmp/ielts-writing-ai-trial/.env`，不是仓库内的默认示例路径。只更新模型及评价选项，并把独立数据路径固定在该目录的 `var/`；Key、端点及其他原配置原值保留，备份权限为0600。配置和备份均不提交。

- 基础模型 `deepseek-flash`；评价模型 `deepseek-v4-pro`。
- 评价思考 `high`，总输出上限32000，单次请求超时420秒。
- 精修、改写继续Flash；它们的原参数不变。
- 仅监听127.0.0.1:5055；独立SQLite，不导入主应用、不访问生产。
- 生效配置见 `effective-settings.json`，只含公开摘要和Key是否存在，不含Key。

独立运行源码位于 `/private/tmp/studytracker-iwa-holdout-review-20261111`。本机控制命令（主工作树根目录）：

```bash
.venv/bin/python .tmp/ielts-writing-ai-trial/control.py check
.venv/bin/python .tmp/ielts-writing-ai-trial/control.py status
.venv/bin/python .tmp/ielts-writing-ai-trial/control.py stop
.venv/bin/python .tmp/ielts-writing-ai-trial/control.py start
```

该私有控制脚本明确选择上述源码、Python和配置，清除继承的IWA与代理变量。普通终端可用start；本次工具会话使用start-live保持子服务生命周期。程序初始没有运行，配置原未指定独立数据目录；本次初始化的是专用试用库，没有移动或覆盖既有应用数据库。

11月12日运行快照见`runtime-check.json`（当时用户数0）。**11月13日已创建“测试老师”**，沿用CLI默认：每日30次生成、无到期日；试用码只在本机0600私有文件，不提交。登录→额度30/30→作文输入页→退出→登录页的本机HTTP检查均通过，用户数1、作文/生成/用量仍0，见`account-check-20261113.json`。访问地址 `http://127.0.0.1:5055/`。

上次持续工具会话结束后服务也停止，因此11月13日改由临时macOS用户后台任务`local.studytracker.iwa-trial`执行私有控制脚本`start-live`；未安装登录/开机自启项。`control.py stop`可停止服务。普通终端可直接`control.py start`；下一次登录Mac后若服务未运行需手动启动。后台启动日志在私有`var/launcher.log`。

## 验证

```bash
.venv/bin/python docs/design/iwa-evaluate-pro-review-20261112/run_offline_tests.py
.venv/bin/python docs/design/iwa-evaluate-pro-review-20261112/model_routing_probe.py
```

- 完整453项Python、8项Node通过，31秒左右；Python3.13.3，Mac本机条件。
- 独立探针6/6：真正请求体参数、并发不串模型、校验重试仍Pro、失败记录和账本仍Pro、对照批次强制自身模型及300秒、compare按实际评价模型识别差异。
- 工具目录Ruff、Black（65文件）、JS语法检查通过。
- 首次沙箱禁止回环监听导致23错误，允许本机回环后同一隔离测试通过；测试阻断非回环连接、未读Key、临时数据库哨兵未写。
- 没有重复多locale、Python3.10、全部历史探针或全网页流程。本次未评估模型判断或分数准确性。
- 91个tracked工具文件与源提交一致，源码哈希见 `source_state.json`。产品没有本机补丁。

## 尚未执行

- 官方组：`~/iwa-calibration/official.jsonl`不存在，5篇模板正文均为空；20次请求尚无新授权。先补齐并核对逐字稿，再按`official-run.md`使用新账本。不得重用已完成的184次账本。
- 老师10条抽查材料存在：`/Users/zhouxin/iwa-compare-real-20261112/teacher_spotcheck.private.md`。尚无老师填写结果，AI盲评不能写成老师确认。
- 执行说明“最坏约5.5元”是按平均用量乘满20次的估算，**不是费用硬上限**；20次、每次32000 token的输出预算远大于平均用量。将来授权需要区分请求上限和金额估算。

用户11月13日授权提交推送：本目录10个文本文件及两份规范交接仅同步`claude/ielts-writing-ai-trial`，提交号和远端一致性以最终Git回读为准。配置、登录码、数据库、控制/账号脚本仍仅本机可见，不进Git；`__pycache__`不提交。功能代码85b8daad本身未改；主main未合并，生产后端/前端/数据库与小程序均未部署或发布。
