# 九分学长考前冲刺：每周完整题库同步

## 当前状态与授权范围

来源是本机“九分学长考雅机考平台”的「懂的都懂」7天热榜。公开榜单为阅读 Part 1–3、听力 Part 1–4，每部分20条，共140条；不采集“更多排名”等额外权限内容。抓取时间与来源更新时间分开显示，不宣称命中率。

本轮用户已明确允许每周对新题或改版题使用本机登录会话，必要时空白交卷取得官方复盘答案，并允许会话受限长期保存在这台Mac。此前“一次测试交卷”的限制已由本轮明确授权扩展；不能再把它写成当前阻塞。每个unit及题面内容SHA最多尝试一次新交卷，优先复用现有同版本答案/复盘；不确定提交结果保留pending状态，禁止自动重复POST。账号会话、原始复盘及采集checkpoint只留本机，不上传服务器或Git。

本机全量准备已完成：140份公开题面、124题官方答案齐全，另16条听力沿用严格核对的原题映射；完整`current.json`及`data/exam_sprint/latest.json`种子均已落盘，阅读60/60、听力80/80可练。95个唯一来源媒体（80 MP3、14 PNG、1 JPEG）共763,206,054 bytes全部下载并验证。全量本机GET/访客提交与判分验收通过，1600/1600答案判对；同一完整快照现已在生产激活并完成线上验收。

用户已明确授权“发布并启用每周更新”。业务提交`154a642fabc017557b92abbefd022dc112a383a5`已commit并push功能分支与main，网页及激活代码已部署。分支[CI 43710428721](https://github.com/KB77GG/studytracker/actions/runs/43710428721)和main [CI 43711098532](https://github.com/KB77GG/studytracker/actions/runs/43711098532)均overall success，三个required job成功；既有advisory lint仍failure。[Deploy 43711098583](https://github.com/KB77GG/studytracker/actions/runs/43711098583)成功，生产HEAD已回读为`154a642f`。343个公开文件已上传并原子激活，完整140题线上验收通过，Mac launchd已安装启用且首次运行正常跳过已发布周。小程序没有上传、提审或发布。

## 管道与校验

网页入口为 `/practice/sprint/listening` 与 `/practice/sprint/reading`，原听力/阅读四个目录顶部提供入口，并保留Part和返回来源导航。

1. `services/ninefen_source.py`获取公开榜单和题面。固定HTTPS域、证书与hostname验证、响应上限、超时、有限重试、拒绝重定向；两科七组必须完整。
2. `services/exam_sprint_import.py`验证完整榜单，优先复用题面SHA及本地文件均未变更的人工映射或原生导入。不能按标题猜版本；失效旧导入不会遮住有效人工映射。
3. 缺答案时由显式授权的`services/ninefen_session.py`采集官方复盘。所有题目身份、题干、选项、说明与正文必须和当前公开题面匹配。答案按question ID和完整source SHA绑定；source rightAnswer=null不能用来猜答案。`collect_ninefen_answers.py`默认只读，只有显式`--allow-new-attempts`才允许有checkpoint保护的新交卷。
4. `services/ninefen_assets.py`只下载`https://static.9fnnn.com/practice/`白名单媒体，限制格式、大小、超时、重试及路径。资产按实际内容SHA不可变保存；每题manifest核验source SHA、URL全覆盖、字节数、格式与文件SHA。公开源payload不改写。
5. `services/ninefen_content.py`转换为现有阅读/听力做题及判分格式；不支持或缺失的题型/图片/答案直接中止，不裁剪或伪造。`services/exam_sprint_store.py`保存带来源版本的不可变JSON及完整性receipt；新版本生成新ID，保留旧版本。
6. `scripts/sync_exam_sprint.py`持互斥锁运行。只有所有来源开放题目均完整可练，才生成候选、归档并原子替换本机`current.json`；失败保旧期。`--dry-run`不替换当前快照且不新交卷，但可能获取公开数据、读取匹配复盘并写入可复用缓存/不可变文档。
7. `scripts/publish_exam_sprint.py`仅传显式白名单中的公开媒体、转换后文档/receipt和候选快照。服务器`activate_exam_sprint.py`重新校验140条榜单、每个开放题目的身份/内容/资产、人工映射及下架状态，再原子激活并归档。既有不可变文件不覆盖；校验失败保留远端旧期。

网页读取时重新核对人工映射撤销、本地JSON SHA、下架清单、媒体引用覆盖与实际SHA。媒体hash缓存按路径、size、mtime、inode区分；坏metadata、缺媒体、同长度改写均关闭对应链接。过期或失败不得伪造新的同步时间。

## 本机目录与隐私边界

默认运行数据为`<项目根>/instance/exam_sprint/`，Git忽略。`EXAM_SPRINT_STATE_DIR`可指定替代目录，相关读写进程必须使用同一个值。

- `exams/<unit>.json`：公开原题；`media/<unit>.json`：与原题hash绑定的完整媒体manifest。
- `assets/<sha>.<ext>`：不可变媒体；`content/{reading,listening}/`：版本化练习及receipt。
- `private/`：本机会话、官方答案缓存、复盘及checkpoint；目录700、敏感文件600，不打印令牌，不上传。
- `current.json`、`history/`：当前与历史公开快照；`media-validation.json`：本轮媒体验收结果。
- `data/exam_sprint/mappings.json`：16条旧题人工映射；`latest.json`已更新为完整140题种子（124原生导入＋16人工映射）。种子仍依赖对应本地/服务器媒体与版本文档，只有代码或种子并不等于题库已部署。

稳定Mac runtime为`~/Library/Application Support/StudyTrackerExamSprint`。安装器只复制必要代码、运行数据和当前人工映射依赖；主资料树提供16条旧听力音频时必须显式给`--legacy-assets-root`，不依赖工作树软链接。会话绝不放入plist、日志、命令行值、远端或仓库。

## 复验与本机准备

以下命令在`/private/tmp/studytracker-exam-sprint-20261115`执行，解释器借用主资料树venv。它们不是部署授权。

```sh
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/exam-sprint-20261115/verify_local.py
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/exam-sprint-20261115/verify_imported.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_practice_history -q
node --test tests/test_practice_shell.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/cache_exam_sprint_media.py --workers 2
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/publish_exam_sprint.py --state-dir instance/exam_sprint --dry-run
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/install_exam_sprint_launchd.py
```

媒体命令最多2并发，已完整且hash有效的题直接复用，失败题不覆盖旧manifest；联网受沙箱审批约束。发布dry-run只做本地完整校验，不运行ssh/rsync。安装脚本不带`--install`只输出计划。完整快照未生成时发布dry-run应失败，不能为了通过而降低校验。

离线榜单复验可用`sync_exam_sprint.py --from-file <albums.json> --fetched-at <真实捕获ISO时间> --exam-dir <公开题面目录> --dry-run`；必须保留真实捕获时间。不要将离线结果称为新一轮联网更新。

本轮最终本机验收：`verify_local.py`的196项Python通过（不含单独通过的history9项）；`verify_imported.py`完成140个GET、140次访客POST、1600/1600判对、95个练习引用媒体HEAD、828处占位符及1440个长question ID校验，内存数据库记录数不变。公开发布dry-run校验343个公开文件且140/140 ready，只读发布审计无阻断。本机浏览器真实阅读页已验13/13及图表完整；之后屏幕再次锁定，完整榜单刷新与移动端仍待复核。

本轮历史验收与新管道证据见`docs/reviews/exam-sprint-20261115/README.md`。旧资料树的`static/listening_jijing/audio`为既有媒体；工作树相应路径的忽略软链接仅供本机开发，不随Git传输。

## 发布、定时启用及后续维护

本轮已完成：业务154a642f部署、343个公开文件上传及原子激活、140题线上验收、Mac launchd安装与首次运行回读。生产HEAD/快照一致，快照SHA256为`0eb2ca7f78e1405df312625f4e814100d73555b9bcb76b110657ccd5a42214fc`。以下步骤保留为后续维护流程，不需要重复发布同一版本。不要从落后且有其他脏改动的旧桌面main发布。生产仍保持5002、单worker、gthread6；本功能不需数据库schema变更或生产重模型推理。

部署激活脚本与网页代码后，先用`publish_exam_sprint.py --state-dir instance/exam_sprint --dry-run`确认候选，再执行同命令去掉`--dry-run`上传公开资产并激活；必须回读远端快照hash、可练总数、题页/音频/图片与判分。原始题面、会话、checkpoint、私有复盘和原始答案包均不在上传白名单。

本轮在首次远端完整发布及验证成功后，已用以下命令建立本机稳定runtime并注册launchd。未来重新初始化时，`--initial-publish-confirmed`同样必须代表真实完成的首次发布：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/install_exam_sprint_launchd.py --install --initial-publish-confirmed --legacy-assets-root /Users/zhouxin/Desktop/studytracker
```

安装器要求Mac系统时区为Asia/Shanghai、稳定Python及本地受限会话，复制后先在隔离runtime执行完整本地发布校验，成功才注册。更新安装持有与runner相同的锁；正在运行采集时拒绝更新，不会先bootout终止在途POST。

launchd任务名`com.sagepath.studytracker-exam-sprint`，每周一06:00 Asia/Shanghai，另每30分钟检查补跑，并在加载时检查。新runtime记录首次已发布周，首次加载不会立即重抓全量。需要这台Mac保持登录、开机联网且来源登录会话有效；休眠或关机时不会在服务器代为读取账号，唤醒或恢复后补跑当前到期周。

每周最多3次管道尝试。同步失败不标成功；同步已成功但上传失败时保存候选SHA，后续只重试同一候选的发布，不重新交卷。发生pending提交或身份/正文不完整时停住并保留checkpoint，不能删除记录后强行重试。会话过期需通过正常登录续期。

早期systemd榜单方案已被Mac launchd取代，当前`deploy/exam-sprint/`提供launchd plist；不安装或同时启用旧systemd定时。不得把本机会话复制到生产机器。

## 线上与调度验收结果

生产2026-11-15 20:17 CST验收通过：HEAD154a642f、tracked clean、active/running、NRestarts=0；gunicorn仍127.0.0.1:5002、1 worker、gthread、6 threads。140个练习GET及95个媒体HEAD（80音频、15图片）均通过；匿名阅读13/13、听力10/10且`synced=false`。公网HTTPS听阅入口均200且标题正确。脚本不导入app/config/数据库，未读取学生表或来源凭据。

Mac 20:19 CST回读：label注册、runs=1、last exit code=0；首次日志`already_published`，对应周2026-11-09，attempts为空，无新增交卷。周一06:00及1800秒补查配置一致，下一次计划为**2026-11-16 06:00 Asia/Shanghai**；13个runtime代码SHA、快照SHA一致，private700/session600。无ssh-agent依赖的BatchMode连接probe已exit0。正常空闲时launchd显示`not running`，不代表job未启用。

生产和调度报告及精确SSH stdin验收命令见[验收README](reviews/exam-sprint-20261115/README.md)。未来真实新一周自动采集尚未发生；本机5096预览已停止。屏幕再次锁定后的完整榜单浏览器刷新、移动端/微信视觉体验仍未复核，不影响已通过的HTTP、判分与调度注册结果。本轮主发布流程没有剩余阻断。

## 暂停与故障恢复

暂停调度可在本机卸载该launchd job，保留runtime和全部checkpoint；重新加载会按已发布周和pending状态恢复。操作前确认是否有正在进行的采集，不以强制杀进程作为更新步骤。已发布学生练习版本不删除，旧快照/历史保留。

重试前先区分题面/题型变更、会话过期、网络失败、媒体完整性、上传或远端激活失败。缺项期间继续展示旧期并保留真实时间。人工映射错误可从映射清单撤销，之后按正常代码发布流程同步。launchd注册、计划时间及首次跳过已回读通过；真实新一周到期采集尚未发生，届时正常观察日志，不为验收额外触发新交卷。
