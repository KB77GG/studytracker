# 只读生产启动与随访验收器

`verify_live.py` 在 `/private/tmp/studytracker-vocabulary-error-pilot-20261117`、`codex/vocabulary-error-pilot-20261117`（本轮基线513c732f）开发。此子任务只本机编写/合成测试，未访问生产、提交、推送或启用学生；主agent负责实际运行和规范交接。

## 调用

在服务器仓库目录，用生产虚拟环境Python执行；stdin执行也可，脚本不依赖自身`__file__`。不创建JWT，不登录，不代领题、代答或结算。

```sh
# 部署后、迁移前：总开关OFF，允许旧checkpoint schema；本轮4人名单必须已私下保存。
venv/bin/python -B docs/reviews/vocabulary-pilot-launch-20261117/verify_live.py --expected-head RELEASE_SHA --manifest /private/backend-manifest.json --selection /private/pilot-selection.json --expected-size 4 --allow-pending-migration
# 迁移后、启用前：仍OFF，要求新schema与索引齐全，无enabled enrollment。
venv/bin/python -B docs/reviews/vocabulary-pilot-launch-20261117/verify_live.py --expected-head RELEASE_SHA --manifest /private/backend-manifest.json --selection /private/pilot-selection.json --expected-size 4
# 开关启用并重启后、以及后续回读：必须恰好名单中4人生效，名单外0人enabled。
venv/bin/python -B docs/reviews/vocabulary-pilot-launch-20261117/verify_live.py --expected-head RELEASE_SHA --manifest /private/backend-manifest.json --selection /private/pilot-selection.json --expected-size 4 --enabled
```

默认root `/root/apps/studytracker`，可用`--root`指定。名单沿用`select_vocabulary_pilot.py --save-private`的JSON格式，只读取`student_ids`；人数由`--expected-size {4,6}`明确指定（默认6，本轮实际传4），要求恰好该数量的唯一正整数、文件不为symlink、当前执行用户所有、无组/其他用户权限。名单及参数中的内部IDs不输出。

manifest为`{相对路径:sha256}`字典，逐文件核验并拒绝越界；至少覆盖脚本`REQUIRED`列出的核心代码和验收依赖，其中含`gunicorn.conf.py`、`services/vocabulary_checkpoint_identity.py`和此前`verify_production_entry.py`。还核验实际Git HEAD及tracked-clean。不要把服务器外的源文件hash当生产已一致。

批准默认七参数为20/4/10/2/3/7/7；必要时显式`--expected-parameters`传含七个大写参数名的JSON对象。默认不接受参数漂移。脚本只读取`.env`与master/worker进程初始环境，按当前config的“环境优先、文件首条赋值优先”规则解析；不import app/config、不输出其他环境值。检查.env及源码时间早于worker启动，防止文件已改而进程仍旧。非空`GUNICORN_CMD_ARGS`当前会安全失败，不能据未知覆盖项断言1worker/6threads。

## 检查与输出范围

- systemd active/running、0自动重启、实际1个gunicorn worker；配置及ExecStart/WorkingDirectory确认gthread/6threads/127.0.0.1:5002，socket归本服务所有。
- 仅匿名GET：本机和公网login 200、词汇summary 401。没有任何学生认证请求。
- schema调用迁移脚本的纯`inspect`，核旧/新列与unique/index；不调用迁移写函数。
- selected enabled集合必须精确匹配，开始时间已到；OFF阶段enabled集合为空。只输出计数。
- 用最小Flask+models+service，对名单全部学生依次调用summary/preflight；拒绝停用账号、重名/多profile歧义及无对应词汇任务。姓名仅在内存用于既有任务绑定，不输出。
- SQLite URI mode=ro、query_only、authorizer拒绝DML/DDL/ATTACH/配置改变/扩展函数，10秒SQL进度预算。每人独立一致读snapshot，核policy表前后计数相同、total_changes=0、无待写ORM。只给汇总调用数/P50/最大/总耗时，要求每次读<5秒。
- stdout为单一JSON，只含聚合计数、布尔、耗时和运维状态；错误只给类型及固定白名单错误码，不回显SQL、路径、姓名、IDs、答案、token或任意异常原文。通过exit0，否则exit1。

这验证实际部署/数据上的只读service行为和匿名HTTP，不是真机、认证HTTP端到端或生产并发写入验收。启动后的首次实际学生任务与长期保持率仍由正常使用/后续汇总观察。

## 本机验证

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/vocabulary-pilot-launch-20261117/test_verify_live.py -q
/private/tmp/studytracker-stage2-py310/bin/python docs/reviews/vocabulary-pilot-launch-20261117/test_verify_live.py -q
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check docs/reviews/vocabulary-pilot-launch-20261117/verify_live.py docs/reviews/vocabulary-pilot-launch-20261117/test_verify_live.py
```

双版本各11项通过，Black/Ruff通过：私有4/6人精确名单、CLI默认6/显式4、两种规模名单外enabled拒绝、路径越界、写/DDL/ATTACH/PRAGMA/BEGIN IMMEDIATE拒绝、精确入组集合/未来开始、实际进程覆盖及旧worker、Gunicorn参数覆盖、错误不泄露、真实临时库OFF/ON服务重放字节不变、迁移前后schema只读inspect。没有本地server或遗留进程。根agent尚需运行生产验收并记录结果；此文不冒称已上线验证。

本轮人数调整按根agent明确指令：有效教师关系筛选只得到4名合格学生，沿用既有授权范围选择4人；验收不会扩大名单或补造教师关联。该筛选事实由根生产取数确认，本子任务未生产取数/写入。
