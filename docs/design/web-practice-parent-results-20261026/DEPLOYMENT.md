# 网页练习与家长结果后台部署 — 2026-10-26

用户明确授权“部署上线吧，我还需要重新发布小程序对吗”。本轮已完成后台提交、非强制原子推送和生产验收；小程序仍由用户从固定目录上传、提审、发布。

## 已发布版本

- 实施工作树：`/Users/zhouxin/.codex/worktrees/web-practice-parent-results/studytracker`，分支 `codex/web-practice-parent-results`，发布基线 `65f1859683c94ef41c938319515702e12709e96c`。
- 业务提交：**`80f215b5b94a90e592c4669c2bee41f7c55eb562`**。只含5个运行文件+3个测试文件；没有提交小程序源码、models、schema、依赖或生产配置。本轮文档/前端增量补丁通过随后单独 `[skip ci]` 提交同步，不重复部署，最终文档HEAD看 `git log -1`。
- 推送命令：`git push --atomic origin HEAD:refs/heads/main HEAD:refs/heads/codex/web-practice-parent-results`。发布前及发布后 `git ls-remote` 分别核对基线65f18596及业务80f215b5，两分支一致，无强推或覆盖其他提交。
- [main CI 40328912509](https://github.com/KB77GG/studytracker/actions/runs/40328912509)、[任务CI 40328912836](https://github.com/KB77GG/studytracker/actions/runs/40328912836)、[Deploy 40328912486](https://github.com/KB77GG/studytracker/actions/runs/40328912486) 顶层均success。test与拼写门禁通过；仓库advisory Ruff仍有既有failure（continue-on-error），目标文件本地Ruff通过。用完整业务SHA查询push运行（GitHub连接器运行列表只支持PR，因此这里用gh）；deploy/main test jobs另外用GitHub连接器复核。

## 本地发布复验

在实施树重跑README中的13模块pytest组合：**172 passed / 31 subtests passed**；CI同款9模块unittest **68 passed**；`node tests/test_dictation_spell_queue.js`、目标Ruff、`git diff --check`通过。独立审阅 **40 passed / 23 subtests**，5运行文件SHA与backend-sha256.json一致，最终GO。

固定发布树本轮11个前端/测试目标SHA全部等于verification.json；`node --test tests/test_web_practice_client.js`再次 **11/11**，补丁reverse check通过。没有更改或上传小程序。

## 生产实际状态与验收

生产 `/root/apps/studytracker` HEAD为 **80f215b5**，tracked clean；5个运行文件SHA与backend-sha256.json逐字相等。服务自 **2026-10-26 21:15:23 CST** active/running，NRestarts=0；`127.0.0.1:5002`、`workers=1`、`gthread`、`threads=6`保持。回环/public login均HTTP200，公网未认证parent API401，部署后观察窗口warning以上journal0。

生产Python3.10运行合成内存SQLite测试：

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 aliyun-server 'cd /root/apps/studytracker && TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python -m unittest tests.test_miniprogram_web_practice tests.test_parent_web_practice_report'
```

**20 tests OK**（5.439秒）；只创建合成内存库，没有真实学生布置、作答、通知或生产业务数据写入。

独立真实库只读探针见 `production_parent_probe.py`，可复验命令：

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 aliyun-server 'cd /root/apps/studytracker && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - --repo /root/apps/studytracker --database /root/apps/studytracker/app.db' < docs/design/web-practice-parent-results-20261026/production_parent_probe.py
```

经SSH stdin执行，未上传生产文件；轻量Flask+模型+API蓝图，没有import app.py或重模型推理。SQLite全部5连接 `mode=ro`、`query_only=ON`；独立随机测试secret/JWT仅进程内，不读取生产密钥。写作/题型各1条有active parent link的既有任务，已绑定家长GET均200且ok/kind/summary正确；未绑定家长均403，无可写token泄漏。选中Task/attempt原列前后SHA相等。输出只有布尔/计数；不保存学生名、ID、token、答案或成绩。student GET=0、POST=0。

部署沿现有 `/usr/local/sbin/deploy-studytracker`，包含原有依赖安装、7个既有迁移脚本及静态同步/服务重启。本功能没有新增schema迁移，也没有手工SQL或改写历史关联；不能把自动部署的既有迁移步骤描述为“生产完全没有任何数据库操作”。没有执行生产模型推理。

## 小程序与兼容边界

- 用户仍需重新发布小程序，后台部署不会自动改变微信包。唯一上传目录：`/Users/zhouxin/Desktop/studytracker-release/miniprogram`，AppID `wx75cdd8fc1ca68c69`，`miniprogramRoot=./`。固定树仍 `codex/miniprogram-release@d03a2749eb99cde041cdae18305b624956d46e90`；76 modified/35 untracked入口全部保留，源码尚未commit/push，仅本机；本任务增量patch已随部署文档同步可跨机获取。
- 当前未上传/提审/发布、未验证完整微信GUI、iOS/Android真机及新客户端在线联调。先体验版检查写作提示/复制链接/网页完成/家长结果，以及听力和阅读专项；既有精听250ms滞后限制仍见固定树交接，不把本次后台GO当整包真机GO。
- 部署前已打开的旧打字页面，旧attempt没有任务绑定时finish会409，刷新后从原任务重新开始；localStorage草稿保留，但旧attempt用时不继承。这是避免猜测归属的兼容限制，未对生产旧记录做回填。
- 历史写作无绑定只显示Task原结果与缺失说明，不把自主练习最新结果归给某任务；新网页提交的准确绑定由本次服务完成。订阅提醒送达仍依赖授权。
- 桌面旧资料树 `/Users/zhouxin/Desktop/studytracker` 仍main6ded77d2、7 modified/22 untracked入口，仅本两交接本轮更新，业务脏内容不动。实施树在文档同步完成后仅 `.tmp/` 原文冻结/本机诊断未跟踪；不得把整个旧树或固定树的后台目录推上生产。

## 下一步

后端本轮无需再部署。用户在固定小程序目录完成体验版/真机核验后上传、提审与发布。若需回退后台，保持当前数据库与已写入的Task快照/attempt结果；先用此前基线65f18596评估兼容，再通过明确的代码回退提交，不恢复旧数据库或删除新增绑定。文档已记录每个树的真实状态；未完成的小程序动作不可写成已完成。
