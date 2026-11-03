# 雅思写作 AI 试用工具（独立版）

独立网页：手动输入题干、作文和（Task 1）题图，查看 **原稿评价 / 逐句精修 / 整篇改写**，可复制结果，并保留自己的历史记录。

## 隔离边界

| 项目 | 试用工具 | 主应用（不触碰） |
|---|---|---|
| 代码 | `tools/ielts_writing_ai/`，不 import `app` / `models` / `config` / `api` / `services` | `app.py` 等 |
| 进程 / 端口 | 自己的进程，默认 `127.0.0.1:5055`；拒绝 5000 / 5002 | gunicorn `:5002` |
| 数据库 | 自己的 SQLite：`<数据目录>/iwa.sqlite3`；拒绝 `app.db` 文件名和含其他表的库 | 生产库 |
| 配置 | 只读 `IWA_*` 变量和 `tools/ielts_writing_ai/.env` | `DEEPSEEK_API_KEY` 等不读 |
| 上传 | `<数据目录>/uploads/<用户>/` | — |
| 登录 | 管理员发放的试用码，Cookie 名 `iwa_session` | 学习系统账号 |
| 部署 | **不在** `deploy.yml` / `deploy-studytracker` 里；push 到 main 不会启动它 | 自动部署 |

不改导航、小程序、正式成绩、MockExamReview，也不做生产表迁移。

## 本地快速开始

在仓库根目录执行：

```bash
# 1. 独立虚拟环境（只需 Flask；gunicorn 仅测试环境用）
python3 -m venv tools/ielts_writing_ai/.venv
tools/ielts_writing_ai/.venv/bin/pip install -r tools/ielts_writing_ai/requirements.txt

# 2. 配置（默认 fake 演示模式，不调用任何付费 API）
cp tools/ielts_writing_ai/.env.example tools/ielts_writing_ai/.env

# 3. 创建试用用户（试用码只显示一次）
tools/ielts_writing_ai/.venv/bin/python -m tools.ielts_writing_ai user-add --name 张三 --days 14

# 4. 启动 / 查看状态 / 停止
tools/ielts_writing_ai/bin/start.sh     # → http://127.0.0.1:5055/
tools/ielts_writing_ai/bin/status.sh
tools/ielts_writing_ai/bin/stop.sh      # 只停核验通过的试用工具进程
```

**进程安全**

- **PID 文件**：记录 PID、进程启动时间（`ps lstart`）和启动方式。`stop.sh`、`status.sh`、`start.sh` 只有在“进程存活、启动时间一致、命令行属于本工具”三项都满足时，才认定这是本工具的实例。PID 被其他程序复用时，脚本不会发任何信号，只清理过期的 PID 文件。
- **旧版 PID 文件**：只有一个数字、没有启动时间，无法核验，脚本不会自动停止，并会给出手动确认的命令。
- **单实例锁**：同一个数据库只允许一个实例运行，锁文件是 `<数据库>.lock`，用操作系统的 `flock` 实现，进程退出后自动释放。第二个实例会在动任务状态之前直接退出，不会把正在运行的实例的任务标成“中断”。`IWA_LOCK_WAIT`（默认 5 秒）控制等待上一个进程退出的时间。
- **启动成功判定**：`start.sh` 只认刚启动的那个进程返回的健康检查。端口被别的服务器占用时会报启动失败，不会误报成功。
- **并发启停**：start 和 stop 之间用 `<数据目录>/iwa.ctl.lock` 互斥（基于 `mkdir`，因为 macOS 没有 `flock` 命令）。多个 start 同时运行时只会启动一个实例，其余的报“已在运行”。持锁进程已经退出时，锁会被自动接管。启动失败时，只有 PID 文件记录的是自己的 PID 才会删除它。
- **Shell 兼容**：脚本兼容 macOS 自带的 `/bin/bash` 3.2，所有变量都写成 `${VAR}`。原因是 bash 3.2 在 UTF-8 环境下会把紧跟在 `$VAR` 后面的中文字节读进变量名，导致报错；测试里有静态检查。

前台调试可以直接运行 `python -m tools.ielts_writing_ai serve`，按 Ctrl+C 退出。数据、日志、PID 和会话密钥都放在 `tools/ielts_writing_ai/var/`（已被 git 忽略）；用 `IWA_DATA_DIR` 可以改到别处。

## 接入真实模型

编辑 `.env`：

```bash
IWA_LLM_PROVIDER=deepseek          # 或 qwen / openai_compatible
IWA_LLM_API_KEY=sk-...             # 试用工具专用 Key，建议单独申请、单独限额
# IWA_LLM_MODEL=deepseek-chat      # qwen 默认 qwen-plus，可改 qwen-max 等

# Task 1 题图识别（可选）：先由识图模型提取图表数据，再交给文本模型评价
IWA_VISION_PROVIDER=qwen           # 默认 none：题图只保存展示，评价会提示“未核对图表数据”
# IWA_VISION_MODEL=qwen-vl-max-latest
# IWA_VISION_API_KEY=              # 不填沿用 IWA_LLM_API_KEY
```

运行 `python -m tools.ielts_writing_ai check` 可以查看生效配置（不会打印 Key）。修改配置后需要先 `stop.sh` 再 `start.sh`。

成本控制：每人每天 `IWA_DAILY_LIMIT` 次生成（一次批改消耗 3 次，重新生成消耗 1 次，删除记录不返还）；同时进行的模型调用数不超过 `IWA_MAX_WORKERS`。

## 评分规则（防止无依据的分数）

- **每项都要有依据**：每个评分项都必须有评分理由，并且至少有一条能在学生原文中逐字找到的引文（优点和问题都带引文）。缺少理由或证据、缺少总评或提升重点的输出会被拒绝：系统自动重试一次（不额外扣额度），仍不合格就标记为失败，不显示任何分数。
- **引文核对**：找不到的引文会在页面和复制文本里标注“未在原文中找到，不作为评分依据”。
- **Task 1**：只有题图被识图模型读出了足够的数据时，才评 Task Achievement 和总分。
  - 识图模型必须返回结构化结果：可读性（sufficient / partial / unreadable）、图表类型、数据点、主要特征、读不清的部分。
  - 是否“足够”由服务端判定：
    - 柱状图、折线图、饼图、表格、组合图：至少 3 个带数值的数据点，并且有主要特征；读不清的部分不能多于读清的部分。
    - 地图：至少 2 处变化。
    - 流程图：至少 3 个步骤。
    - 描述里出现空白、看不清等字样，一律判为不足。
  - 识图接口调用成功不代表题图可用：返回纯文本、可读性为 partial 或 unreadable、数据不足，都会显示“题图信息不足（原因）”。
  - 未上传题图、未配置识图模型、识图失败、信息不足这几种情况下，TA 和总分都显示“不可评”，只保留 CC / LR / GRA；改写稿也会提示数据没有与题图核对。
- **复制文本**：由服务端生成，都带“AI 生成，仅供学习参考，不是正式成绩”和全部限制提示。唯一例外是单句“复制”按钮，只复制那一句改句。

## 测试

```bash
tools/ielts_writing_ai/.venv/bin/python -m unittest discover -s tools/ielts_writing_ai/tests -t .
node --test tools/ielts_writing_ai/tests/test_draft.js
```

测试只用内存 / 临时目录、本地假服务器，以及测试自己创建的进程。不联网、不调用付费 API、不读取开发者的 `.env`，也不读写任何真实数据。

覆盖范围：

- **文本与评分**：断句、分数计算、模型输出与证据校验、Task 1 不可评、复制文本的限制提示。
- **模型调用**：真实 HTTP 客户端的行为、不合格输出的自动重试。
- **账号与隔离**：登录、CSRF、错误次数锁定、用户之间的隔离、草稿按用户隔离（node）。
- **数据与流程**：额度、上传校验、失败重试、原稿不被修改。
- **进程**：重启恢复、单实例锁，以及启停脚本不会误停其他进程（PID 复用、启动时间不符、旧格式 PID 文件、端口被占用）。
- **不依赖主应用**：用子进程检查不会 import 主应用。

`test_scripts.py` 需要 `curl` 和 `ps`（macOS 和 Linux 都自带），每次会真实启动、停止几个临时实例，大约需要 20 秒。

- 测试会用本机找到的所有 bash（macOS 上包括 `/bin/bash` 3.2），在 UTF-8 locale 下逐条检查启动、状态、停止的提示信息，并严格按 UTF-8 解码输出。
- 需要额外覆盖其他 shell 或 locale 时，可以设置 `IWA_TEST_BASH`、`IWA_TEST_LOCALE`、`IWA_TEST_LOCPATH`。例如在 Linux 上用 `localedef -i en_US -f ISO-8859-1` 生成 Latin-1 locale，它对 0x80–0xFF 字节的分类和 macOS 相同，可以复现 bash 3.2 的这个问题。

## 试用用户管理

```bash
PY=tools/ielts_writing_ai/.venv/bin/python
$PY -m tools.ielts_writing_ai user-add --name 李四 --days 7 --daily-limit 15
$PY -m tools.ielts_writing_ai user-list
$PY -m tools.ielts_writing_ai user-disable 2       # 停用并立即登出
$PY -m tools.ielts_writing_ai user-enable 2
$PY -m tools.ielts_writing_ai user-reset-code 2    # 发新码，旧码和已登录会话一起失效
```

## 放到独立测试环境（后续）

1. 用单独的系统用户和单独的目录，例如 `/srv/iwa`；在 `.env` 里设置 `IWA_DATA_DIR=/srv/iwa/data`。**不要**和生产库放在同一个目录。
2. `IWA_SERVER=gunicorn tools/ielts_writing_ai/bin/start.sh`。脚本固定使用 `-c tools/ielts_writing_ai/gunicorn.conf.py`（单 worker、gthread、绑定 `IWA_HOST:IWA_PORT`，控制 socket 放在数据目录）。**不要**在仓库根目录直接运行 `gunicorn`：它会读到主应用的 `gunicorn.conf.py`，绑定 5002 端口。
3. 用独立的子域名或路径做反向代理，并开启 HTTPS；同时设置 `IWA_COOKIE_SECURE=1`、`IWA_TRUST_PROXY=1`，挂在子路径时再加 `IWA_URL_PREFIX=/writing-trial`。
4. 必须单进程运行：后台生成任务在进程内执行，重启时未完成的任务会被标记为“中断”，用户可以点“重新生成”。

## 已知限制

- AI 给的分数是**预估**：四项平均后按 0.5 就近进位（和系统模考批改的口径一致），会有误差，可能偏高。页面和复制出的文本都标注了“仅供参考”。
- `fake` 演示模式只返回带【演示】标记的固定示例，页面顶部有黄色横幅提示。
- 新建页的草稿只保存在本机浏览器，并且按账号隔离。同一浏览器换人登录时，会清除其他账号留下的未提交草稿；主动退出时会先确认，再清除自己的草稿。页面不缓存，退出后按浏览器“后退”也看不到之前的内容。
- 每次修改提示词都要同步更新 `prompts.PROMPT_VERSION`，每条结果都会记录生成时用的模型和提示词版本。
