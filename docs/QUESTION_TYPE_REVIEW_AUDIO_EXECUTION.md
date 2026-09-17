# Web 题型专项解析与听力片段执行报告

> 日期：2026-09-17
> 状态：本机候选、生产媒体差异修复、全量 / 定向回归、独立终审与生产验收均完成，结论 GO；业务提交已 commit / push / deploy，5092 隔离预览继续运行。
> 工作树：`/Users/zhouxin/.codex/worktrees/86d7/studytracker`
> 分支 / 开工基线 / 业务提交：`codex/question-type-review-audio` / `origin/main@df1463f9363996a2495477d5615935ada3e54e05` / `f881ef436c04c88ac15e287296009f5db39cd4da`

## 结果

- 已完成提交的 Listening / Reading 题型专项现在使用独立的授权复盘快照，展示冻结题目的解析与现有答案依据；缺字段的旧题显示明确中性提示，不伪造内容。
- Listening 训练态展示题组相关录音范围；提交后每题展示并播放经过当前音轨校验的片段，片段到终点自动暂停。定位数据无效、缺失或与当前媒体不匹配时，明确回退完整 Section。
- 旧任务和新任务都在读取时派生复盘数据；没有改写冻结 snapshot、`snapshot_hash`、历史成绩或答案。
- 考试节奏继续不暴露题组 / 逐题定位窗口；提交前仍不暴露答案、解析、原文、答案句或逐题片段。

## 根因

1. 学生结果页原先仍调用 `public_snapshot(snapshot)`。该函数按设计移除了 `answer`、`analysis`、`central_sentences`、`answer_sentences` 和 `transcript`，而 `results_json` 只有评分，没有解析，因此共享复盘卡拿不到任何解析或依据。
2. 冻结题目的 `start/end` 属于题库来源音轨坐标。部分线上同名 MP3 已替换成对话重建轨，不能依据文件名推断时间基准；旧定位只跳到一个起点，也没有终点、并发播放和版本漂移保护。
3. Reading 真实题库的 `central_sentences` 是数组。浏览器验收发现初版候选只兼容对象形态，已补成数组 / 对象双兼容并加入真实 Stepwells 回归。
4. 首轮独立审阅进一步发现：冻结题目的坐标属于**冻结 transcript**，不能直接拿去和后来更新的 sidecar 来源坐标做数值重叠。比如 IELTS 21 Test 3 S1 Q1 的冻结答案句约在 65 秒，而同一句 `Northern Ferries` 在当前 sidecar 是 109 秒；按数值硬碰会错误选到 `look at questions` 提示语。现改为“冻结坐标只选冻结证据行，再以证据文本语义对齐当前 sidecar”。
5. 第二轮独立审阅发现一对多拆句漏洞：IELTS 20 T1 S1 Q2 的冻结长句在当前 sidecar 被拆成两行，初版语义映射只选了更接近 `source_order` 的后半行，漏掉答案 `roof` 所在前半行。现以按词 `SequenceMatcher(autojunk=False)` 选择有新增覆盖的有序 sidecar 行，并要求组合文本完整覆盖冻结整行；覆盖不足时整题回退，不再把局部相似当可信片段。
6. 最终合成 probe 又堵住两个边界：不能因长铺垫已超过宽松阈值而漏掉短答案尾句；一题同时重叠多条冻结 transcript 时，也不能只映射其中一部分。现覆盖门槛为完整词序 100%，且每个重叠的冻结行都必须有完整映射，缺任一行即回退。

## 复盘与时间轴契约

- `services/question_type_review.py` 对传入数据先深拷贝，再运行时构造授权复盘视图；原 snapshot 与 hash 保持不变。
- sidecar 固定从已跟踪的 `static/listening/<section>.json` 读取，并校验 sidecar `id` 与当前音频 stem。当前目标区间按实际媒体选择 `sidecar_current` 或 `source_original`；只有 target basis 需要 sidecar 的 `start/end` 或 `original_*` / `source_*` 坐标。
- 不使用不同题库语义不一致的 `lyc_index`，也不假定冻结题目坐标与当前 sidecar 来源坐标同轴。题目 `start/end` 只负责选出重叠的冻结 transcript 行；随后去掉 speaker 前缀、做 NFKC / 字母数字归一化，完整句相同则优先绑定。拆句 / 合句时按词序列逐段选择能新增冻结词覆盖的 sidecar 行，以 `source_order` 距离消歧，并用有序组合文本做最终校验：每条冻结证据必须 100% 覆盖，而且全部重叠冻结行都必须成功映射。没有完整可信覆盖就回退，不用相近时间、答案词或局部短语猜测。
- 逐题片段在答案句前留 3 秒、后留 2 秒；题组范围取组内全部有效题目的 `min(answer_start)` / `max(answer_end)`，前留 8 秒、后留 3 秒，不依赖题号顺序。
- `data/listening_audio_timeline_overrides.json` 显式绑定同名音频的已知版本：sidecar 文件 / SHA-256 固定不变，服务端按具体媒体 SHA-256 + 大小选择该版本的时间基准与预期时长。IELTS20 T1S1 的 279.84 秒纯对话版使用 `sidecar_current`，生产 436.218776 秒完整 Section 的 seek-index 重封装版使用 `source_original`；IELTS21 T3S1 的原容器与生产 seek-index 重封装版都使用 `sidecar_current`。未知同名媒体一律回退完整 Section。服务端按 stat 版本缓存媒体哈希；浏览器再以真实 `audio.duration` 做容差 0.75 秒的最终核验。
- sidecar 缺失、ID 不符、哈希改变、媒体大小 / 哈希改变、浏览器时长不符、边界非有限数 / 倒置 / 越界时都不猜测，逐题或题组回退完整 Section。失效合约下原文仍可阅读，但行级 seek / 精听 / 听写入口都禁用；`playWindow` 与 transcript `playFrom` 共用预期媒体时长闸门。播放器以 revision 令牌取消旧请求，切 Section 会暂停旧音频，`timeupdate` 到片段终点自动暂停。

## 改动范围

- 后端：`services/question_type_review.py`、`services/question_type_practice.py`、`api/question_type_practice.py`。
- 前端：`static/js/listening_clip_player.js`、`static/js/practice_renderers.js`、`static/css/practice_shell.css`、`templates/listening/test_practice.html`、`templates/question_type_practice/result.html`。
- 数据契约：新增一份很小的已知同名音轨版本清单；没有新增 / 修改 MP3、题库 JSON、数据库 schema 或生产配置。
- 测试：新增复盘服务和片段播放器测试，扩展路由、只读复盘、真实 Cambridge / JFDR、乱序题组、缺失 / 改变 / 不匹配 sidecar / 媒体版本和阅读数组依据覆盖。

## 全库审计

以 `/Users/zhouxin/Desktop/studytracker/static/listening` 的本机真实媒体作为只读音频根，扫描 `static/listening_tests`：

- 84 份测试文件、336 个 Section：**336 / 336** 时间轴契约可用。
- 3,360 题：**3,358** 题可生成逐题片段，2 题明确回退完整 Section。
- 658 题组：**656** 组可生成范围，包含异常题的 2 组明确回退完整 Section。
- 两个真实异常是 `ielts10_test2` S1 Q1（105.00–105.73，没有重叠的冻结 transcript 行）和 `ielts4_test3` S1 Q4（225.25 > 99.76）。
- 全库语义审计额外断言：每个可用问题的**每条冻结重叠 evidence**，在全部当前 evidence 的有序组合中按词覆盖率都是 100%，未给指定样例开白名单。IELTS 21 T3 S1 Q1 对齐 `Northern Ferries` 109.26–115.02、Q2 对齐 `seven days a week` 117.10–130.42；IELTS 21 T2 S1 Q1 / Q6 / Q7 分别落到 `13th January` 和正确的 `6th` / `natural` 句，均不含 `look at questions` 提示语。
- Cambridge 20 T1S1 Q2 现在同时映射 `roof` 前半句与 `need to book` 后半句，当前答案区间 66.84–81.48；Q6 的证据只落在 `Baxter Bridge` 句，当前答案区间 189.24–193.88。JFDR6 T1S1 Q1 语义对齐到 126.30–130.28，证据包含 Saturday。
- 发布前新增生产媒体只读审计：生产和本机 336 / 336 个 MP3 都存在且可由 `ffprobe` 读取；99 个整文件 SHA-256 不同、39 个容器时长差超过 0.75 秒。对这 99 个文件进一步用 `ffmpeg -map 0:a:0 -c:a copy -f hash -hash sha256 -` 去掉容器元数据后比较 MP3 packet，**99 / 99 内容完全相同，mismatches 为空**；其中 C20T1S1 生产完整轨与保留的 `pre_45sentence` 原轨 packet 相同，其余 98 个生产文件与本机 canonical 相同。因此 335 个 Section 只有容器 / seek-index 差异，唯一实际音轨版本差异是 C20T1S1 的完整轨与纯对话轨。非敏感摘要见 `docs/evidence/question-type-review-audio-2026-09-17/production-media-audit-summary.json`。

## 验证

### 自动化

- 全仓 Python（临时只读挂载桌面仓已有 `ielts10_test1_s1.mp3` 以满足仓库既有静态响应头 fixture，结束后已删除该链接）：
  - `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest -q`
  - **756 passed / 72 subtests passed**。
- 最终复盘 / 路由 / 工作区组合：**66 passed / 19 subtests passed**；包括全库 336 Section、3,360 题的冻结整句到当前 sidecar 词序列完整覆盖审计，以及一条冻结行拆成多条 sidecar、长铺垫后短答案不能丢、缺半句 / 缺整条重叠证据必须回退的合成回归。
- 相关 Node 组合：**92 passed**，覆盖片段终止、陈旧 metadata、单音频互斥、版本时长回退、失效 transcript 不可点、`playFrom` 时长闸门、复盘入口和只读锁定。
- `py_compile`、目标 Ruff、两个 JS `node --check`、`git diff --check` 全通过。
- 首次全仓运行在独立 worktree 缺上述未跟踪 MP3 时是 748 passed / 2 个静态音频 404；挂载真实 fixture 后及全部审阅修复的最终完整套件为 756 passed，说明不是本任务代码回归。
- 独立终审另跑 **54 passed / 2 subtests passed** 的 Python 窄集和 **55 passed** 的 Node 窄集；自建“长铺垫 + 短答案尾句”与“缺整条冻结行”两个 probe 均通过。独立扫描 336 个 Section 后确认 3,358 个可用问题的冻结词序均 100% 覆盖、snapshot 不变；`ffprobe` 成功读取 336 个真实 MP3，所有逐题 / 题组边界都未超过实际媒体时长。结论 **GO**。
- 生产资产差异修复后新增多版本契约回归：本任务 Python 目标组合 **55 passed / 2 subtests passed**；独立复审五文件窄集 **56 passed / 2 subtests passed**，新增断言精确媒体哈希选择 `source_original` / `sidecar_current` 且未知同名媒体回退；相关 Node **46 passed**，目标 Ruff、Python compile、JS syntax、JSON parse 和 `git diff --check` 通过。用只读下载到临时目录的生产 C20/C21 实体再跑运行时派生：C20 选择 `production_seek_indexed_original` / `source_original`，Q2 `roof` 两条依据落在 107.285–121.925 秒、片段 104.285–123.925；C21 选择 `production_seek_indexed` / `sidecar_current`，Q1/Q2 仍为 `Northern Ferries` / `seven days a week`。独立审阅又在生产 Python 3.10 内存中对 84 份 JSON / 336 Section 跑候选：336 时间轴可用、3,358 / 3,360 题和 656 / 658 题组可定位，只有既有两题回退，所有窗口不超生产真实媒体时长，输入 payload 不变。临时媒体副本已删除，生产未改；发布暂停已由独立审阅解除。

### 真实浏览器

使用应用内 Chromium + 隔离内存数据库 + 合成学生在本地完整走通：

- 首轮 Listening：提交前显示题组范围 `1:49–4:16`；提交后显示正确答案、解析、答案句证据和逐题按钮。真实 MP3 到片段终点自动暂停。首轮 Reading 的真实 Stepwells Q1 显示题库解析及原句，并据此修复数组形态依据兼容。
- 首轮审阅修复后重新验收 IELTS 21 T3 S1：Q1 页面显示 `Northern`、依据 `There's only one – it's called Northern Ferries` 和按钮 `1:46–1:57`；点击后真实媒体从 107.44 秒播放并在 117.28 秒自动暂停。Q2 依据为 `seven days a week`，按钮 `1:54–2:12`，没有把 `look at questions` 当答案证据。
- 合成失效合约页明确显示“当前音频缺少匹配的定位数据”，原文全部降为不可点击文本，题组 / 每题仅提供完整 Section 回退；点击后 `preview_unmapped.mp3` 从头连续播放。Reading 合成结果页显示 Davies Sisters Q1 的正确答案、解析和真实原句依据。
- 第二轮拆句修复后，IELTS 20 T1 S1 Q2 页面显示正确答案 `roof`、两条 evidence（前半句含 `go up on the roof`，后半句含 `need to book`）和按钮 `1:03–1:23`。点击真实重建音轨从 68.81 秒处于播放态，并在 83.70 秒自动暂停；服务端可信答案区间为 66.84–81.48，片段含 3 秒前 / 2 秒后上下文。控制台 error / warn 为 `[]`。
- 独立终审再次点击 `roof`：真实媒体从 64.160604 秒播放，在 83.682981 秒已暂停，duration 279.84；页面包含两条完整依据，console error / warn 为 `[]`。此前 IELTS21 语义错配、失效回退和 Reading 页面问题全部关闭。
- 终审后已停止 `127.0.0.1:5091`，删除 `ielts10_test1_s1.mp3`、`ielts20_test1_s1.mp3`、`ielts21_test3_s1.mp3`、`preview_unmapped.mp3` 等本轮 worktree 临时链接；没有覆盖桌面真实媒体。桌面 `ielts20_test1_s1.mp3` 仍为 4,510,888-byte 普通文件，SHA-256 `ec0bc0dc1ab21bd1d18e6397a9c4b7978a292a66da8273c2637798dfa1c9dfa4`。
- 匿名截图：
  - `docs/evidence/question-type-review-audio-2026-09-17/listening-result-analysis-and-clip.png`
  - `docs/evidence/question-type-review-audio-2026-09-17/reading-result-analysis-and-evidence.png`

### 当前用户预览（运行中）

- 用户入口为 `http://127.0.0.1:5092/preview`；三个不含 token 的稳定跳转入口为 `/preview/open/listening-practice`、`/preview/open/listening-review`、`/preview/open/reading-review`。入口页返回 200，三个跳转入口均已跟随重定向验证到最终页面 200。
- 预览包含三个完全虚构的示例学生 / 任务：Listening 训练态可体验题组范围播放；Listening 与 Reading 已提交结果都包含正确、错误、未作答的混合状态，并展示只读解析与依据。Chrome 已再次确认 IELTS 20 Test 1 Section 1 Q2 会显示 `roof` 完整原句与解析，点击后进入对应有界片段；真实媒体时长 279.84 秒。
- 隔离目录为 `/var/folders/ly/2q45cg3x51zdj5g09p6p56gh0000gn/T/studytracker-user-preview-w25d9d1g`，其中 `preview.py` 为启动脚本、`preview.log` 为日志、`preview.pid` 为 PID 记录；发布后已停止旧 PID 42674，并用最终模块重启为 PID 45861，仍监听 `127.0.0.1:5092`。数据使用 `tests/test_question_type_practice_routes.py` fixture 与 `sqlite:///:memory:`，不读取或写入真实学生 / 生产数据库。
- 媒体由 loopback Flask 从 `/Users/zhouxin/Desktop/studytracker/static/listening` 只读发送；执行工作树没有媒体软链接，也没有复制或改写源 MP3。临时访问 token 每次重启重建，只存在运行时，不写入仓库文档。
- 当前服务特意保留给用户查看，不要在交接时自动停止。需要清理时，先读取 `preview.pid`，再用 `ps` / `lsof` 核对该 PID 的命令确实指向上述绝对 `preview.py` 且监听 5092；随后只停止该进程并删除上述精确临时目录。不要删除 Desktop 源媒体。需要重启时使用 `/Users/zhouxin/Desktop/studytracker/.venv/bin/python` 加上述 `preview.py` 绝对路径；脚本已固定工作目录 / 项目根。

用户最终明确本轮只保障**浏览器刷题网页**，微信页面、小程序和微信内置 WebView 不属于本次实施 / 验收范围，也不再作为网页候选的发布阻塞项。Safari 未单独验证；未做主观音频听辨。自动化和 Chrome 真实媒体已验证加载、seek、互斥播放、边界停止与回退，但不把这些等同为所有浏览器都已通过。

## Git、发布与下一步

- 业务提交为 **`f881ef436c04c88ac15e287296009f5db39cd4da`**（`fix: restore question type review guidance`），从 `origin/main@df1463f9363996a2495477d5615935ada3e54e05` 原子推送任务分支 `codex/question-type-review-audio` 与 `main`。提交不含 MP3、预览脚本 / 日志 / PID、数据库、schema、配置、题库或小程序改动。
- GitHub Actions 任务分支 CI [35202935845](https://github.com/KB77GG/studytracker/actions/runs/35202935845)、主线 CI [35202935884](https://github.com/KB77GG/studytracker/actions/runs/35202935884) 和 Deploy [35202935965](https://github.com/KB77GG/studytracker/actions/runs/35202935965) 均为 **success**；两个 test job 与旧拼写队列门禁通过。advisory Ruff job 仍只报告仓库既有迁移 / 辅助脚本问题并按工作流设计不阻断，本任务目标 Ruff 全过。
- 生产 `/root/apps/studytracker` 已运行 `f881ef43`、分支 main、tracked 干净，原 17 个未跟踪备份 / 静态快照 / 调度库保留。`studytracker.service` 自 2026-09-17 17:03:02 CST 起 active，`NRestarts=0`，`127.0.0.1:5002`、`workers=1 / gthread / threads=6`，实际一主一 worker；Python 3.10.12。部署后 journal 未见 Traceback / Exception / CRITICAL / 新应用错误。SQLite 只读 `quick_check=ok`、外键错误 0。
- 生产 9 个运行时文件 SHA-256 与最终候选逐一一致；C20 / C21 MP3 哈希保持部署前生产版本不变。服务端运行时确认 C20 自动选择 `production_seek_indexed_original / source_original`，`roof` 两条依据 107.285–121.925 秒；C21 选择 `production_seek_indexed / sidecar_current`。未上传或改写生产媒体。
- 独立旧任务只读 HTTP 验收：一个已提交 Listening 专项为 12 / 12 解析、12 / 12 依据、12 / 12 片段、3 / 3 题组范围；一个已提交 Reading 专项为 17 / 17 解析与 17 / 17 依据，均 200、`read_only=true`。GET 前后冻结 snapshot / hash、已存作答、成绩、提交时间和计时全部不变；未输出或记录学生、任务 ID 或 token。
- 公网 `https://studytracker.xin/practice/question-types`、Listening 与 Reading 代表页均 200；`listening_clip_player.js`、`practice_renderers.js`、`practice_shell.css` 的公网 SHA-256 与候选一致，新 JS 为 `Cache-Control: no-cache`。Chrome 验收确认 Listening 10 个输入、唯一提交、真实媒体 duration 436.218776 / readyState 4 / paused；Reading 有 7 个文本框、18 个 radio、40 题导航和唯一提交；目录筛选正常，三页 console error / warn 为空。未填写、提交或创建真实任务，验收标签已关闭。
- 最终交接仅再以 `[skip ci]` 纯文档提交同步，不重复部署。小程序无改动、未上传 / 提审 / 发布；Safari 未单独验证，主观音频听辨未做。后续只需观察真实网页反馈。
