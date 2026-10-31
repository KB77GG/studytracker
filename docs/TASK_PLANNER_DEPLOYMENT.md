# 任务安排试用版部署记录

日期：2026-10-31，Asia/Shanghai。用户明确授权制作测试版上线，供助教试用。入口：<https://studytracker.xin/task-planner>。

## 发布版本和验证

- 实施树 `/Users/zhouxin/.codex/worktrees/task-planner-beta/studytracker`，分支 `codex/task-planner-beta`，业务提交 `f8319d9e35bb2b5622ce283fde39aac99223cca7`。基线 `ee94abb30d56b3c9623c519f75c1ffa9679c65b5`，开工干净，业务提交22文件。业务已push任务分支及main，并完成后台部署。
- [任务分支CI41168358998](https://github.com/KB77GG/studytracker/actions/runs/41168358998)、[main CI41168421301](https://github.com/KB77GG/studytracker/actions/runs/41168421301)、[Deploy41168421279](https://github.com/KB77GG/studytracker/actions/runs/41168421279) 均success。两个CI的test/task-planner/account-provisioning均success；advisory lint仍报告仓库存量问题，目标9文件Ruff通过。
- 本地46项专项Python、71项既有回归、17项Node及Chrome合成全流程通过。精确命令与界限见[TASK_PLANNER_VALIDATION.md](TASK_PLANNER_VALIDATION.md)。全仓ML、所有资源真实浏览器、微信WebView/真机未测。
- 发布后代码7个SHA与本地逐字相等：api/task_planner.py、models_task_planner.py、services/task_planner.py、services/task_planner_resources.py、scripts/run_task_planner.py、static/js/task_planner.js、templates/task_planner.html。

## 生产数据库和服务

- 发布前使用Python sqlite3 `connect('file:/root/apps/studytracker/app.db?mode=ro',uri=True)`、`PRAGMA query_only=ON`及`source.backup(target)`生成一致性备份 `/root/backups/studytracker/task-planner-20261031-122157/app.db`，目录0700/文件0600，quick_check=ok。备份仅服务器可见，不能覆盖后续真实学习记录进行整库恢复。
- 部署沿既有自动脚本（含原有迁移和启动检查），生产实际HEAD为上述业务提交、tracked clean。新建且只新增 `task_planner_student`、`task_planner_entry`、`task_planner_event` 三表；与备份sqlite_master逐表SQL对比，原有表定义变化0。三表验收行数均0，所有学生自动布置默认关闭。上线后quick_check=ok。
- studytracker自 **2026-10-31 12:24:45 CST** active/running，NRestarts=0；`127.0.0.1:5002`、workers=1、worker_class=gthread、threads=6保持。部署后warning及以上journal为空。
- 公网HTTP：login200，task-planner302到login（含next），匿名bootstrap401，planner.js200。未借用真实学生创建任务、代答或改成绩，没有发微信；生产已登录的实际助教交互及真实学生首轮使用仍待试用反馈。

复核命令：

```sh
ssh root@47.110.45.193 'cd /root/apps/studytracker && git rev-parse HEAD && git status --short --untracked-files=no && systemctl show studytracker -p ActiveState -p SubState -p NRestarts -p ExecMainStartTimestamp && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_task_planner.py --dry-run'
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' https://studytracker.xin/task-planner
curl -sS -o /dev/null -w '%{http_code}\n' https://studytracker.xin/api/task-planner/bootstrap
```

## 定时器

已从本业务提交安装两文件到 `/etc/systemd/system/`，运行：

```sh
cd /root/apps/studytracker
install -m 644 deploy/task-planner/studytracker-task-planner.service /etc/systemd/system/studytracker-task-planner.service
install -m 644 deploy/task-planner/studytracker-task-planner.timer /etc/systemd/system/studytracker-task-planner.timer
systemd-analyze verify /etc/systemd/system/studytracker-task-planner.service /etc/systemd/system/studytracker-task-planner.timer
systemctl daemon-reload
systemctl enable --now studytracker-task-planner.timer
systemctl start studytracker-task-planner.service
systemctl show studytracker-task-planner.timer -p ActiveState -p SubState -p NextElapseUSecRealtime -p UnitFileState
systemctl show studytracker-task-planner.service -p Result -p ExecMainStatus
journalctl -u studytracker-task-planner.service -n 8 --no-pager
journalctl -u studytracker --since '2026-10-31 12:24:45' -p warning --no-pager
```

- Timer **enabled/active/waiting**，下一次 **2026-11-01 03:05:00 CST**，之后每日03:05至08:50每15分钟重试；09:00以后程序不执行发布。
- 12:33:15–12:33:17 CST手动启动服务验证成功，Result=success/ExecMainStatus=0；报告eligible/published/blocked/failed/skipped全0，outside_window=true。dry-run也返回全0/outside_window=true。这确认加载和时间门禁，不能宣称已观察凌晨真实调度或发布真实学生任务。
- `systemd-analyze verify`只有既有snapd/cloudmonitor单元兼容/弃用告警，没有planner单元错误；未修改那些服务。
- 全局暂停：`systemctl disable --now studytracker-task-planner.timer`；若oneshot正在执行，等待或停止后核对已发布任务。不要删除新表或整库恢复撤销发布。

## 交接和试用

助教登录后选学生和日期，选好具体内容，保存并确认，再为该学生启用自动布置；未完成任务仅在明确设置为前置时阻止对应安排。已有正式任务冲突或资源失效进入待处理；同日课程计划冲突会执行失败，由助教处理，不覆盖原计划。

长期教材顺序自动推进未提供，本版不新增外部付费API/AI/微信调用。小程序源码未改，无上传/提审/发布；本功能不要求重发小程序。

业务提交后实施树clean；本部署记录与两交接以独立 `[skip ci]` 文档提交同步main和任务分支，不再次部署。文档首次原子推送遇并行main更新，被非快进保护拒绝、两分支均未更改；随后文档rebase到1ddddbbb，逐段保留另一任务的代码与交接，不强推。最终文档HEAD以git log为准。

并行网页重做业务ae3f079d已独立部署。最终只读复核生产HEAD=ae3f079dd7f268035191dfd194cbf192a69a43e4、tracked clean，12:29:36 CST起active/running/NRestarts0；本功能上述七个SHA仍逐字相等，回环bootstrap401，timer enabled/active、下一次11月1日03:05。本文前述f8319d9e是任务安排的发布版本和当时验收，不代表阻止其他正常部署。

旧资料树 `/Users/zhouxin/Desktop/studytracker` main6ded77d2原7 modified/22 untracked入口保留，当前behind89（文档同步后将增加）；本轮只滚动两交接和原计划说明。另一“网页重做”任务最新代码与上线交接完整保留，不将其改动计入本任务范围。固定小程序树未动；临时合成预览服务与标签已关闭，截图只在 `/private/tmp/task-planner-beta-preview.jpg`。
