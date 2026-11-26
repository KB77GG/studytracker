# 九分学长考前冲刺：每周完整题库同步

## 当前状态（2026-11-26）

来源是本机“九分学长考雅机考平台”的「懂的都懂」7天热榜。公开榜单为阅读 Part 1–3、听力 Part 1–4，每部分20条，共140条；不采集“更多排名”等额外权限内容。抓取时间与来源更新时间分开显示，不宣称命中率。入口为 `/practice/sprint/listening` 与 `/practice/sprint/reading`。

11月23日周更失败的直接原因已确认：独立保存的旧会话调用官方只读 unit-status 返回 HTTP 401。用户正常重新登录后，本机绑定会话已恢复，官方正常续期也已实测成功。续期后原客户端会话的只读 GET 仍有效，只能说明这次观察没有立即撤销旧会话，不能推断服务器永远不撤销或 token 永不过期。

最新快照捕获于 **2026-11-26T12:27:01.394201Z**，阅读60/60、听力80/80可练，125条原生导入＋15条严格人工映射。414个公开文件已上传并原子激活，快照 SHA256 为 `eaea443d63fa4775caad5f070ff838f90ba971e07ff12b08c0d03824c82b8e79`。生产140个题页 GET、94个媒体 HEAD、匿名阅读13/13及听力10/10判分均通过，提交均为 `synced=false`。本机140 GET＋140访客 POST、1600/1600答案判对，850处占位符、1450个长题目ID及14张图校验通过，临时内存数据库记录数不变。

业务修复 `7bde8d672d8067b3b8b62236b299d7f9bafa53d7` 已提交、推送功能分支和main并部署。分支 [CI 45825718426](https://github.com/KB77GG/studytracker/actions/runs/45825718426)及main [CI 45828206265](https://github.com/KB77GG/studytracker/actions/runs/45828206265)均overall success，三个required job通过，既有advisory lint仍failure；[Deploy 45828206189](https://github.com/KB77GG/studytracker/actions/runs/45828206189)成功。生产最终HEAD回读为`7bde8d67`，tracked clean、active/running、NRestarts=0、实际worker=1，新快照SHA一致。听阅入口的生产HTTP和公网HTTPS均200，显示同步时间`2026-11-26 20:27`，无过期提示，下次为`2026-11-30 06:00`。Mac installer升级及回读成功：14个runtime代码SHA一致、续期开关已启用，launchd runs=1/exit=0，日志为 `session_renewal_completed` 后 `already_published`。本周 `2026-11-23` 已记录成功，原attempts=3保留。代码、数据和本机定时任务全部完成，没有剩余发布阻塞。

用户此前“发布并启用每周更新”、每周新题/改版题必要时空白交卷、会话受限长期保存在这台Mac的授权持续有效，本轮另明确要求“你处理”。这不扩大到其他账号、额外权限题库或上传凭据。修复后的跨日续期、下一真实周采集及长期稳定性尚未实际验证。当前证据见[11月26日修复验收](reviews/exam-sprint-repair-20261126/README.md)；[11月15日首次上线记录](reviews/exam-sprint-20261115/README.md)仅作历史。

## 管道与完整性

1. `services/ninefen_source.py`获取公开榜单和题面。固定HTTPS域、证书与hostname验证、响应上限、超时、有限重试、拒绝重定向；两科七组必须完整。
2. `services/exam_sprint_import.py`优先复用题面SHA及本地文件均未变更的人工映射或原生导入。不能按标题猜版本；失效旧导入不会遮住有效人工映射。
3. 缺答案时由显式授权的`services/ninefen_session.py`采集官方复盘。题目身份、题干、选项、说明与正文必须和当前题面匹配。答案按question ID和完整source SHA绑定，`rightAnswer=null`不能猜答案。每个unit及题面SHA最多尝试一次新交卷；不确定提交保留pending，禁止自动重复POST。`collect_ninefen_answers.py`默认只读，显式`--allow-new-attempts`才允许受checkpoint保护的新交卷。
4. `services/ninefen_assets.py`只下载`https://static.9fnnn.com/practice/`白名单媒体，限制格式、大小、超时、重试及路径。内容SHA不可变缓存；manifest核验source SHA、URL覆盖、字节数、格式与文件SHA，公开原payload不改写。
5. `services/ninefen_content.py`转换为现有题页及判分格式；不支持或缺失的题型/图片/答案直接中止，不裁剪或伪造。`services/exam_sprint_store.py`保存版本化不可变JSON及receipt，新版本生成新ID并保留旧版。
6. `scripts/sync_exam_sprint.py`持互斥锁运行。完整榜单全部开放题目可练才生成候选、归档并原子替换本机`current.json`，失败保旧期。`--dry-run`不替换快照且不新交卷，但可能获取公开数据、读取匹配复盘并写可复用缓存。
7. `scripts/publish_exam_sprint.py`只传白名单内的公开媒体、转换后文档/receipt和候选快照。服务器`activate_exam_sprint.py`重新核验完整性、人工映射及下架状态，再原子激活并归档；不可变文件不覆盖，失败保远端旧期。

网页读取时重新核对人工映射撤销、JSON SHA、下架清单、媒体引用覆盖与实际SHA。媒体hash缓存按路径、size、mtime、inode区分；坏metadata、缺媒体、同长度改写均关闭链接。失败不伪造同步时间。

## 本机目录与隐私

默认数据为`<项目根>/instance/exam_sprint/`，Git忽略。`EXAM_SPRINT_STATE_DIR`可指定替代目录，相关进程必须使用同一值。稳定runtime为 `/Users/zhouxin/Library/Application Support/StudyTrackerExamSprint`。

- `exams/<unit>.json`为公开题面，`media/<unit>.json`为与题面SHA绑定的manifest；`assets/<sha>.<ext>`及`content/{reading,listening}/`为不可变媒体、版本化练习和receipt。
- `current.json`、`history/`为当前及历史快照。`private/`为会话、官方答案缓存、复盘和checkpoint，目录700/敏感文件600；不进Git、不上传服务器，不把token写入plist、日志或命令行。
- runtime根下`weekly-state.json`、`weekly-config.json`和日志是本机控制数据；owner、文件版本等元数据只保存在受限文件。
- `data/exam_sprint/mappings.json`仍有16条已审核候选映射，本次实际采用15条。`data/exam_sprint/latest.json`仍是11月15日仓库种子，不是11月26日runtime快照。仅取得代码或种子不等于题库部署完成。

安装器只复制必要代码、运行数据和当前人工映射依赖。主资料树提供旧听力音频时显式给`--legacy-assets-root`，不依赖工作树软链接。小程序没有因本次修复上传、提审或发布。

## 周更与正常会话续期

launchd任务`com.sagepath.studytracker-exam-sprint`每周一06:00 Asia/Shanghai运行，另每1800秒补查，并在加载时检查。这台Mac需保持登录、开机联网；休眠/关机期间不在服务器代读账号，唤醒后检查当前到期周。空闲时`not running`不代表未启用。

每周最多3次管道尝试。同步失败不标成功；同步成功但发布失败时保存候选SHA，后续只重试该候选发布，不重新交卷。候选发布不依赖源会话，也不因续期失败受阻。不要删除checkpoint、重置计数或改变旧快照时间来强行重跑。

修复后的安装器显式启用`session_renewal_enabled`。runner在已发布周也最多每24小时尝试一次官方续期，请求前先持久化attempt；成功及网络失败均受每日上限约束。`services/ninefen_auth.py`对固定官方 `/api/user-auth/v1/session/renew` 发一次空JSON POST，token请求头、10秒超时，拒绝重定向/环境代理凭据/任何POST自动重试。只接受相同owner及无歧义会话，原子保存token和续期时间，不保存响应个人资料。

HTTP401/403、明确认证拒绝或owner缺失/不符进入`login_required`并停止自动续期。网络故障保原文件；服务端可能已经旋转token，不能立即补发。替换已提交但仅目录fsync失败时返回`renewed`及`durability_confirmed=false`，不回滚、不视作可重试失败。

正常重新登录、替换绑定会话后，`--resume-session-after-login`只验证会话，不采题、不发布、不重置周更计数。恢复过程中保留阻断，真实同身份续期成功才解除；本地`skipped_recent`不算验证。文件版本未变化时不重试；已恢复的相同文件重复命令为无副作用跳过。`--check`零网络、零状态写入，不创建周更锁。

## 安全诊断与故障恢复

固定JSON日志包含阶段、错误枚举、受限HTTP状态和源码模块/行号，不记录任意异常message、HTTP body或凭据。runner只转发白名单事件，单行最多4 KiB、总解析256 KiB、最多160条，其他stdout/stderr丢弃。`session_rejected`加401/403用于辨别会话问题，不代表可无限重试。

1. 先查看安全日志及`--check`，区分会话、题型/题面、媒体、上传或激活失败；确认周更次数和pending候选。
2. 认证被拒时让用户在官方客户端正常重新登录。本轮`refresh_local_session.py --save`是固定profile的受限日志读取助手，只处理精确会话记录，不支持任意SST或多账号自动发现，不导出个人资料、不修改客户端profile。JWT userid只是期望owner，本地decode不是签名校验；先通过官方只读GET验证会话，再原子保存600文件，并由真实官方renew响应核对同owner。
3. 安装修复代码后执行会话恢复命令；成功不重置周更次数。若本周次数已耗尽，仍需显式人工恢复流程，不自动清零。
4. 采集/转换后先本地全量验收、发布dry-run，再传公开文件并回读生产快照、题页、媒体及匿名判分。全部通过才记本周成功。
5. 本次`record_recovery.py`仅在生产验收成功、精确快照SHA一致后，持周更锁记录`2026-11-23`成功并保留attempts=3。它是固定日期修复脚本，不是未来周通用的“标成功”工具。

本次工作树为 `/Users/zhouxin/Desktop/studytracker/.tmp/exam-sprint-repair-20261126`，解释器使用主资料树venv。以下维护示例中联网或写状态命令仍须符合已有授权，不为复验额外新交卷：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/run_exam_sprint_weekly.py --runtime-dir "/Users/zhouxin/Library/Application Support/StudyTrackerExamSprint" --check
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/exam-sprint-repair-20261126/refresh_local_session.py --save
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/run_exam_sprint_weekly.py --runtime-dir "/Users/zhouxin/Library/Application Support/StudyTrackerExamSprint" --resume-session-after-login
EXAM_SPRINT_STATE_DIR="/Users/zhouxin/Library/Application Support/StudyTrackerExamSprint/instance/exam_sprint" /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/exam-sprint-repair-20261126/verify_imported.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/publish_exam_sprint.py --state-dir "/Users/zhouxin/Library/Application Support/StudyTrackerExamSprint/instance/exam_sprint" --dry-run
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/install_exam_sprint_launchd.py
```

安装脚本不带`--install`仅输出计划；实际更新使用`--install --legacy-assets-root /Users/zhouxin/Desktop/studytracker`。只有新建runtime且首次生产发布确已完成时才用`--initial-publish-confirmed`。更新安装持runner同一把锁，不先终止在途POST。生产保持5002、1 worker、gthread6，无数据库schema变更或生产重模型推理。旧systemd榜单方案不与Mac launchd并行启用。

## 验证范围与未验证项

证据及精确命令见[修复README](reviews/exam-sprint-repair-20261126/README.md)。11月15日的“124原生＋16映射、95媒体、343文件、首次跳过已发布周、下一次11月16日”等仅为历史。

本次已实测正常登录恢复、官方续期、代码和数据发布及新版runtime首次运行；修复后的跨日续期、下一真实周自动采集及长期稳定性尚未发生。浏览器完整榜单刷新和移动端/微信视觉体验不包含在HTTP/判分验收内。暂停时保留runtime和全部checkpoint，先确认无在途采集；不强杀进程，不删已发布版本或历史。修复文档由主agent随后统一作skip-ci提交推送；文档提交不代表需要再次重启已验收的生产业务版本。


## 热榜题目用于练习布置与模考（2026-11-26）

- 网页后台 `/tasks` → 布置新任务 → 听力的“7天热榜”筛选，或阅读的“7天热榜 · 阅读”分组。阅读只布置当前榜单对应篇章，服务端重新核验版本及篇章，不接受页面篡改到同卷其它篇。任务保留既有学生、日期、令牌和成绩回写链。
- `/admin/mock-exams/create` → 每科“题库来源”选“7天热榜 · 自选组卷”；听力4个Part、阅读3个Passage各选一篇，必须各40题。可点击“按热度选一套40题”，也可与另一科已有整套题库搭配，写作仍可使用现有可选剑雅卷。创建后沿用原模考pincode分发流程。
- 模考保存不可变内容快照到服务器 `instance/exam_sprint/papers/`，ID带内容摘要，已开考试及复盘不随周榜变化。迁移/备份需同时保留此目录、现有content/assets及数据库；它不随Git同步，周更发布器不会删除或覆盖它。
- 组卷答案只允许既有授权模考运行/复盘处理器读取；普通刷题页面、公开JSON及匿名判分不能读取新组卷快照。模考作答页继续使用去答案的simulation payload。
- 热榜阅读在支持通用网页任务指引的小程序显示网页入口；旧原生阅读入口也补齐版本/图题读取。没有修改小程序前端、没有上传提审发布；源码兼容验证不等于所有真实手机已验收。
- 本次九分学长写作仅做静态能力核查；未导入写作、未交作文、未启用或承诺该软件的范文/AI批改。证据边界见 `docs/reviews/exam-sprint-distribution-20261126/writing-research.md`。
