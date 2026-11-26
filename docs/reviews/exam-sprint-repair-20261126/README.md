# 2026-11-26 考前冲刺周更恢复与验收

## 当前事实与发布边界

工作树：`/Users/zhouxin/Desktop/studytracker/.tmp/exam-sprint-repair-20261126`。分支：`codex/exam-sprint-repair-20261126`，基线`f81a5e4a`。业务修复`7bde8d672d8067b3b8b62236b299d7f9bafa53d7`已提交、推送功能分支和main并部署；分支[CI 45825718426](https://github.com/KB77GG/studytracker/actions/runs/45825718426)和main [CI 45828206265](https://github.com/KB77GG/studytracker/actions/runs/45828206265)均overall success，三个required job通过，既有advisory lint仍failure；[Deploy 45828206189](https://github.com/KB77GG/studytracker/actions/runs/45828206189)成功。

**代码、数据和本机定时任务全部完成，没有剩余发布阻塞。** 最终生产HEAD为`7bde8d67`，tracked clean、active/running、NRestarts=0、实际worker=1，快照SHA一致。听阅两入口生产HTTP及公网HTTPS均200，显示同步时间`2026-11-26 20:27`且无过期提示，下一计划为`2026-11-30 06:00`。先前数据验收报告中的`b68d49d8`仅为上传数据时的历史代码HEAD，最终代码验收另有独立报告。

用户原“发布并启用每周更新”、会话维护及新题/改版题必要空白交卷授权继续有效，本轮明确“你处理”；不包含其他账号、源站额外权限或凭据外传。本文及[运行手册](../../EXAM_SPRINT_RUNBOOK.md)为11月26日事实；[11月15日记录](../exam-sprint-20261115/README.md)只作首次上线历史。规范交接由主agent更新`docs/CODEX_HANDOFF.md`和`docs/WORKLOG.md`；文档及证据的最终提交状态以Git为准。

## 故障与实际恢复

11月23日周更失败的直接证据：独立保存的旧会话调用官方只读unit-status返回HTTP401。旧sync仅记录异常类，runner又丢弃子进程输出，使日志无法区分认证与其他故障。

用户在官方软件正常重新登录后，`refresh_local_session.py --save`从固定profile的精确日志记录提取会话，官方只读GET成功才原子写入600文件。它是本次受限助手，不支持任意SST、多账号自动发现，不修改客户端profile、不导出个人资料。JWT userid只作为期望owner，本地decode不是签名验证；同owner随后由真实官方renew响应核对。

独立官方续期实测返回安全摘要`renewed`、`durability_confirmed=true`。续期后客户端原会话只读GET仍有效，只说明这次没有观察到立即撤销，不能承诺旧token永远有效、永不过期或续期永不影响其他会话。

最新快照捕获于`2026-11-26T12:27:01.394201Z`：完整140篇可练，阅读60/听力80，125原生＋15人工映射。414个公开文件上传并原子激活，快照SHA256：

```text
eaea443d63fa4775caad5f070ff838f90ba971e07ff12b08c0d03824c82b8e79
```

生产验收通过后，`record_recovery.py`持周更锁并核验报告/本机快照SHA一致，记录本周`2026-11-23`成功，保留attempts=3和人工恢复说明；不删checkpoint、不抹掉失败历史。脚本固定日期及报告，不可直接用于未来周。

Mac installer升级已成功：14个runtime代码SHA与`7bde8d67`一致，`session_renewal_enabled=true`；launchctl runs=1/last exit=0，日志`session_renewal_completed`后`already_published`。`last_success_week=2026-11-23`且旧attempts=3保留。验收报告不记录owner、session值。

## 修复行为

- 安全诊断：固定schema记录阶段、错误枚举、源码行号；401/403为`session_rejected`。runner只转发白名单JSON，单行4 KiB、总解析256 KiB、160条上限；任意异常message、HTTP正文和其他输出丢弃。
- 官方正常续期：固定HTTPS端点、单次空JSON POST、token头、10秒、同owner/别名一致校验，禁重定向/代理凭据/POST重试；600原子替换，700目录。目录fsync失败明确“已提交但持久化未确认”，不回滚重发。
- 每日维护：已发布周也最多24小时一次，先持久化attempt。认证拒绝/owner错误持续阻断至正常登录恢复，网络失败保原会话并冷却。
- 恢复控制：`--check`零网络/零状态写入；`--resume-session-after-login`不采题、不发布、不重置周更计数。要求新文件版本及真实同身份续期，`skipped_recent`不清阻断，中断仍保阻断，成功后重复相同命令无副作用。
- 原保护保留：每周3次、每unit/source SHA一次新交卷、不确定提交pending、失败旧榜。候选发布不需要源会话；安装器持锁更新，不终止在途POST。runtime代码白名单由13个增至14个。

## 证据索引

| 文件 | 范围与结论 |
|---|---|
| [session-lifecycle.md](session-lifecycle.md) | 官方客户端静态续期证据、协议边界、22项auth离线测试；“未联网”限定静态调查子任务，本轮主流程真实续期另见本文。 |
| [imported-acceptance.json](imported-acceptance.json) | 140 GET＋140访客POST，1600/1600判对、两科140/140 ready；850占位、1450长ID、14图，临时内存库记录数不变。 |
| [production-data-acceptance.json](production-data-acceptance.json) | `2026-11-26T13:04:12.909254+00:00`，旧代码`b68d49d8`上验新数据：140 GET、94媒体HEAD、匿名阅读13/13/听力10/10，`synced=false`，快照SHA一致；服务active/running、NRestarts=0、1 worker/gthread6/5002。 |
| [production-code-acceptance.json](production-code-acceptance.json) | 最终代码部署验收`ok=true`：HEAD`7bde8d67`、tracked clean、active/running、NRestarts=0、实际worker=1；新快照SHA一致，两科入口200、同步时间正确且无过期提示。 |
| [schedule-acceptance.json](schedule-acceptance.json) | 本机新版runtime安装与注册回读：14代码SHA、续期开关、首次日志、本周成功和保留计数；没有会话内容。 |
| [verify_imported.py](verify_imported.py)、[verify_imported_render.js](verify_imported_render.js) | 全量本机题页/渲染/判分，导入app前强制临时SQLite内存库。 |
| [verify_release.py](verify_release.py) | SSH stdin只读Git/systemd/公开文件及匿名loopback HTTP；不导入app/config/DB，不读源凭据。默认两次匿名判分须`synced=false`；`--skip-guest-post`可改成纯GET/HEAD。 |
| [diagnose_source.py](diagnose_source.py)、[cache_public.py](cache_public.py) | 公开源诊断/缓存辅助脚本；写入被忽略的instance目录，不等于发布。 |
| [refresh_local_session.py](refresh_local_session.py) | 本次精确profile的受限会话接入；`--save`有官方GET和本机私有写入，不是只读复验。 |
| [record_recovery.py](record_recovery.py) | 固定11月23日的人工成功记录，仅在验收报告/精确SHA一致后使用，保留周更计数。 |

## 验证与复现命令

最终weekly、session、auth、import、publish五个模块130/130测试通过，其中weekly39项＋auth22项共61项。review发现的“本地冷却误当恢复成功”“中断提前解除阻断”“换inode后重复恢复误阻断”均修复并有回归。安全诊断Ruff、格式、diff检查与Python3.10 AST通过；业务分支CI成功。

在本工作树运行以下离线测试，不读取真实会话：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_exam_sprint_weekly tests.test_ninefen_auth tests.test_ninefen_session
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check scripts/sync_exam_sprint.py scripts/run_exam_sprint_weekly.py scripts/install_exam_sprint_launchd.py services/ninefen_session.py services/ninefen_auth.py tests/test_exam_sprint_weekly.py tests/test_ninefen_session.py tests/test_ninefen_auth.py
```

以下保留数据恢复阶段的可复现SSH stdin命令，默认含两次匿名判分，不更新代码/重启服务。该命令的旧HEAD参数用于重现当时验收方法，不能在当前新HEAD上直接期待通过；当前复验应使用完整SHA `7bde8d672d8067b3b8b62236b299d7f9bafa53d7`并另存报告，不覆盖历史数据验收。

```sh
ssh -o BatchMode=yes -o IdentityAgent=none -o ConnectTimeout=10 root@47.110.45.193 'cd /root/apps/studytracker && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - --expected-head b68d49d8ceec127871456c39f5a7d0b41cc75965' < docs/reviews/exam-sprint-repair-20261126/verify_release.py > docs/reviews/exam-sprint-repair-20261126/production-data-acceptance.json
```

## 完成边界与后续观察

main CI/Deploy、最终生产HEAD、代码/数据一致性、两公网入口及本机定时回读均已完成。修复文档及证据通过独立skip-ci文档提交同步，精确文档HEAD以Git为准；生产业务HEAD不因文档更新再次重启。

修复后的跨日自动续期、下一真实周采集与长期稳定性尚未发生；离线测试、一次续期及首次launchd运行不能代替。Mac需保持登录、开机联网，休眠后补查。浏览器/手机视觉不属于本次HTTP与判分通过范围，不为增加证据额外交卷。后续正常观察11月30日06:00到期周及每日续期安全事件，失败时按运行手册保旧榜和checkpoint，不重置计数或盲重发POST。
