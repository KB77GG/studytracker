# 九分学长考前冲刺：本机实现与验收证据

## 当前事实与发布边界

工作树`/private/tmp/studytracker-exam-sprint-20261115`，分支`codex/exam-sprint-weekly-20261115`，基线`cb2610166d7654c81238f53c000e37eafa7e68e1`，业务HEAD **`154a642fabc017557b92abbefd022dc112a383a5`**。业务已commit/push功能分支与main，代码部署、343个公开文件上传/原子激活、完整140题线上验收及Mac launchd启用均已完成。本段后续文档更新尚未另行提交。小程序未上传/提审/发布。主资料树及其他worktree不代表已经拥有本实现；这里只记录实现树。

用户确认来源是本机九分学长软件，并选定每周一北京时间06:00。随后明确授权每周新题/改版题必要时空白交卷读取官方答案，允许登录会话受限长期保存在这台Mac。因此旧阶段“一次测试授权已用完、不能继续采集”的结论已经过期。自动采集有unit+完整题面SHA checkpoint，先复用同版复盘，不确定提交不重复POST；会话、原始复盘/答案与checkpoint均不进入Git、日志或服务器。

本机全量准备已完成：140份公开题面、124题官方答案齐全，另16条听力精确复用既有练习；完整`instance/exam_sprint/current.json`和`data/exam_sprint/latest.json`种子已落盘。阅读60/60、听力80/80全部ready，1600题本机访客判分全通过。95个唯一来源媒体（80 MP3、14 PNG、1 JPEG），共763,206,054 bytes全部验证。同一完整快照已在生产激活并验收，Mac定时已安装启用。

用户已明确授权“发布并启用每周更新”。分支[CI 43710428721](https://github.com/KB77GG/studytracker/actions/runs/43710428721)和main [CI 43711098532](https://github.com/KB77GG/studytracker/actions/runs/43711098532)均overall success，三个required job成功；既有advisory lint仍failure。[Deploy 43711098583](https://github.com/KB77GG/studytracker/actions/runs/43711098583)成功，生产HEAD已回读为`154a642f`。343个公开文件上传及原子激活成功，线上140/140可练验收通过，launchd已安装启用并回读首次正常跳过。未来真实新一周自动采集尚未发生，不能把注册/首次跳过等同跨周运行实证。操作手册见`docs/EXAM_SPRINT_RUNBOOK.md`；规范跨任务状态由`docs/CODEX_HANDOFF.md`与`docs/WORKLOG.md`统一维护。

## 已落地的完整管道

- 网页四个听阅目录提供考前冲刺入口，独立蓝图、Part切换、来源/真实同步时间/过期状态和返回导航；原生导入复用既有做题与判分路径。
- `ninefen_source`只取公开七组140榜单及公开题面，验证完整schema、固定HTTPS/证书、限时/限量/有限重试、无重定向。
- `ninefen_session`只在显式允许时交卷，复盘题目、选项、正文、题组说明等均与当版公开题面一致才绑定答案。缺字段、重复题ID或pending不确定状态不成为再次交卷许可。
- `ninefen_assets`及批量缓存脚本按内容SHA保存不可变媒体，完整manifest绑定source SHA；安全白名单、格式/大小/字节校验，失败不产出半份manifest。原始题面不改写。
- `ninefen_content`和`exam_sprint_store`转换并保存按来源版本区分的不可变练习及receipt；缺答案、未知题型、无法保真的布局失败停止，不猜答案或裁掉题目。
- `exam_sprint_import`只有全部来源开放题目可练才返回候选；同版旧导入或严格人工映射可复用。坏旧导入不遮住有效人工映射；缺答案/媒体或source SHA变化不借旧答案继续发布。
- `sync_exam_sprint`互斥、全量准备、归档及原子替换本机快照。`publish_exam_sprint`显式文件白名单只传公开媒体、练习/receipt和快照；`activate_exam_sprint`在生产逐项再验后原子激活，失败保旧。
- `run_exam_sprint_weekly`与安装器使用Mac稳定隔离runtime及launchd，周一06:00上海时区、30分钟补跑、每周最多3次管道尝试。新runtime首次加载跳过当前已发布周；上传失败的后续尝试只重发已冻结候选，不再运行采集。

人工映射证据保留于`MAPPING_REVIEW.md`、`mapping-audit.json`、`mapping-candidates.json`：16条听力题号/题干/选项与录音文字相符；音频来源一致性依据是题面及录音文字，并非源MP3字节完全相同。阅读同名候选被拒绝，不能按标题替代内容比对。这是可继续复用的历史匹配证据，不代表当前阅读仍只能显示榜单。

## 新管道验证

以下为已经运行的命令和结果，cwd均为本工作树。每轮测试有重叠，不累加成虚假独立总数。

```sh
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/exam-sprint-20261115/verify_local.py
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/exam-sprint-20261115/verify_imported.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_practice_history -q
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/publish_exam_sprint.py --state-dir instance/exam_sprint --dry-run
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_exam_sprint_import tests.test_ninefen_assets tests.test_exam_sprint tests.test_exam_sprint_store tests.test_ninefen_content -q
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/cache_exam_sprint_media.py --workers 2
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check tests/test_exam_sprint_import.py
```

- `verify_local.py`最终**196项Python通过**，并再次验证16条旧题真实访客路径；结果见`local-acceptance.json`。history另行**9项通过**，不计入196。此前五模块关联75项通过属于重叠回归，不与196相加。
- `verify_imported.py`对完整140份练习执行**140 GET＋140次访客POST**，均200；**1600/1600**答案判对且`synced=false`，95个练习引用媒体HEAD均200。真实模板脚本检查140份文档、**828处占位符替换、1440个长question ID**及15张图；隔离内存SQLite记录数前后不变，没有学生或提交记录写入。结果见`imported-acceptance.json`（2026-11-15T09:54:09.315753+00:00）。95个页面引用媒体包含原题复用音频，和95个来源缓存媒体是两项不同集合。
- 公开发布dry-run为140/140 ready（124原生＋16人工映射），**343个公开文件**＝95媒体＋248内容/receipt，源题面、raw答案包、private及checkpoint不在上传白名单。候选SHA256：`0eb2ca7f78e1405df312625f4e814100d73555b9bcb76b110657ccd5a42214fc`；报告见`publish-dry-run.json`。
- 新增资产回归覆盖`assets=[]`或遗漏音频、10种坏metadata、已命中SHA缓存后同长度修改。网页关闭损坏链接且不抛500。
- 媒体真实缓存首次136/140成功、4条网络失败；复用严格TLS信任根后补齐4条，最终140/140，136份缓存复用、无剩余失败。没有跳过不支持格式；来源95个URL均覆盖。
- 140份manifest逐项复核source SHA、媒体SHA、长度、格式与安全URL；95个文件合计763,206,054 bytes。80 MP3全部经ffprobe识别并用ffmpeg完整解码，无错误；15图片经sips读取尺寸通过。报告在忽略的`instance/exam_sprint/media-validation.json`，运行摘要`instance/exam_sprint/media/run-summary.json`。
- 媒体与导入相关4代码文件定向Black/Ruff已通过；本次新增资产测试文件Black/Ruff通过。未声称全仓lint/test或远端CI全绿。
- 发布前依赖检查：在本机Python3.13进程中仅允许Flask及其传递依赖导入，主动屏蔽certifi等其他第三方库，CI新增11模块**172测试通过**；certifi缺失走系统信任根，未要求额外CI依赖。相对本轮基线的36个新增/改动Python文件均通过`ast.parse(..., feature_version=(3, 10))`语法检查；这是兼容性静态检查，不是远端CI运行记录。

最终只读发布审计无阻断：67个Git候选文件秘密模式扫描未发现真实凭据（两命中为合成测试token和历史授权说明）；private仅检查权限，目录700、session/checkpoint600且本人所有，runtime无tracked文件且忽略生效。逐项回核140个来源SHA及140份媒体manifest均通过；相对本机cached origin/main的改动均属本任务，无无关用户文件。session/weekly/publish离线67项复验通过，`git diff --check`通过。该审计当时没有联网fetch或执行发布；随后发布阶段的commit/push与部署事实见本文开头，不将两阶段混为一谈。

只读审查已发现并关闭：旧映射撤销不即时生效、坏mapping导致500、复盘缺关键正文仍被复用、prepared版本绕过另一个pending、失效旧导入遮挡人工映射、缺资产metadata误判可练、等长资产损坏未发现。

Mac隔离runtime审查关闭两项：遗漏`activate_exam_sprint.py`导致发布ImportError，以及缺少16条legacy JSON/音频导致未改题被重新采集。安装器已显式复制当前reviewed映射对应文件、核JSON SHA、限制音频根目录，并在注册前做隔离runtime发布dry-run。实现agent报告的离线验证为：12项临时runner/安装夹具通过；isolated code-only runtime的sync/publish/weekly `--help`均exit0；临时目录复制16 JSON+16 MP3成功。这些是离线阶段证据；实际launchd安装和首次运行验收见下文，真实新一周到期采集尚未发生。

## 早期16题阶段证据（保留范围）

以下验证发生在只有16个严格旧题映射的早期阶段，用来证明原目录/原判分路径没有回归；不能当作最终124个原生导入的真实端到端证据。

```sh
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/exam-sprint-20261115/verify_local.py
node --test tests/test_practice_shell.js
node --check static/js/practice_shell.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/audit_exam_sprint_matches.py --source-dir /private/tmp/ninefen-public-assets-20261115
```

当时70项Python通过、7项Node通过；真实内存app的16做题页GET200、16音频HEAD200、160个规范有效答案判对，访客提交`synced=false`，没有学生记录写入。首次把`tires/tyres`两种答案一起当输入导致8/10；改为其中一种有效写法后均10/10，未修改原答案/判分。

早期联网dry-run记录`fetched_at=2026-11-15T03:25:05.051262+00:00`，140条/16映射且不发布。旧`--dry-run`当时只准备榜单；现脚本已升级完整导入，不能照搬旧成功结论。沙箱网络失败均依要求升级审批，不绕路。

Chrome原生UI早期查看过听力16/80、Part1→4、阅读0/60及导航，这些是历史截图状态。随后在本机真实阅读练习页完成13/13判对，图表完整；之后屏幕再次锁定，完整140题榜单刷新及移动端未能继续复核。程序化的60/60＋80/80 ready和全量渲染检查不替代这些浏览器验收。旧预览脚本只读、控件/提交禁用，不是生产app；本机5096预览已停止，微信真机和真实下一周launchd采集仍未验证。

## 生产与Mac调度最终验收

343个公开文件（95媒体＋248内容/receipt）已上传，候选快照原子激活成功。生产报告时间为2026-11-15T12:17:20.134297+00:00（北京时间20:17）：HEAD `154a642fabc017557b92abbefd022dc112a383a5`、tracked clean，service active/running、NRestarts=0；生产仍127.0.0.1:5002、1 worker、gthread、6 threads。快照SHA `0eb2ca7f78e1405df312625f4e814100d73555b9bcb76b110657ccd5a42214fc`与本机一致，140/140 ready。

线上140个练习GET和95个媒体HEAD（80音频、15图片）均通过；两次匿名规范答案POST分别阅读13/13、听力10/10，均`synced=false`。脚本只读取Git/systemd/公开文件并访问匿名回环HTTP，不导入app/config/数据库，不读学生表或来源session。公网[阅读入口](https://studytracker.xin/practice/sprint/reading)与[听力入口](https://studytracker.xin/practice/sprint/listening)均HTTPS 200且标题正确，两份响应为68,247及79,265 bytes。

实际已运行的精确SSH stdin验收命令（本工作树cwd；默认含两次无身份访客判分，纯GET/HEAD复核可加`--skip-guest-post`）：

```sh
ssh root@47.110.45.193 'cd /root/apps/studytracker && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - --expected-head 154a642fabc017557b92abbefd022dc112a383a5' < docs/reviews/exam-sprint-20261115/verify_release.py > docs/reviews/exam-sprint-20261115/production-acceptance.json
```

Mac调度报告时间2026-11-15T20:19:16.587409+08:00：runtime `/Users/zhouxin/Library/Application Support/StudyTrackerExamSprint`，label `com.sagepath.studytracker-exam-sprint`已注册。首次runs=1、last exit code=0；日志`already_published`周2026-11-09，attempts={}，没有新增交卷。周一06:00、每1800秒补查、Asia/Shanghai均匹配；下一次**2026-11-16T06:00:00+08:00**。13个代码文件SHA与发布树一致，快照SHA一致，private目录700、session600且非symlink；错误日志为空。空闲时显示`not running`是已完成检查后的正常状态。

无ssh-agent的无人值守连接probe实际exit0，命令：

```sh
ssh -o BatchMode=yes -o IdentityAgent=none -o ConnectTimeout=10 root@47.110.45.193 true
```

Mac需保持登录、开机联网，唤醒后补跑当前到期周。真实新一周采集尚未发生；本报告只确认安装、注册、权限、连接和首次幂等跳过，不能声称已经完成下一周真实运行。

| 证据 | 内容 |
| --- | --- |
| [production-acceptance.json](production-acceptance.json) | 生产HEAD/service、140 GET、95媒体HEAD及两次匿名判分 |
| [verify_release.py](verify_release.py) | 上述SSH stdin验收脚本，无app/config/DB导入 |
| [schedule-acceptance.json](schedule-acceptance.json) | launchd注册、首次退出状态、计划时间、权限及代码/快照SHA |
| [publish-dry-run.json](publish-dry-run.json) | 上传白名单与激活候选预检 |
| [imported-acceptance.json](imported-acceptance.json) | 本机140 GET/POST、1600题及真实模板渲染结果 |
| [local-acceptance.json](local-acceptance.json) | 196项Python与16条旧题访客验收 |

## 本机数据与下一步

`instance/exam_sprint/`含公开题面、媒体、manifest、版本练习和本机私有采集数据，整体被Git忽略。只上传发布器明确允许的公开子集，不用rsync整个运行目录。工作树`static/listening_jijing/audio`仍是指向旧资料树既有媒体的忽略软链接；正式隔离runtime安装需显式传`--legacy-assets-root /Users/zhouxin/Desktop/studytracker`并复制所需16文件。343个公开媒体/内容文件已上传生产并完成完整线上验收；private仍只在本机。

本轮主流程已完成：140题上线、公开数据验收、Mac每周定时启用，没有剩余发布阻断。保持Mac登录、开机联网；休眠后唤醒会补跑。下一步正常观察2026-11-16 06:00的新周执行，不为验收重复触发采集。屏幕解锁后可补完整榜单刷新与移动端/微信视觉复核。本机5096预览已停止。早期systemd方案已由launchd取代，当前deploy目录只提供该plist，不同时启用旧定时。业务已远端可得；private及运行缓存仅本机，后续文档提交状态以规范交接和Git为准。
