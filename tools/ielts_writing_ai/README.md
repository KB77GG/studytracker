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
tools/ielts_writing_ai/bin/stop.sh      # 只停 PID 文件里的这个进程
```

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

## 测试

```bash
tools/ielts_writing_ai/.venv/bin/python -m unittest discover -s tools/ielts_writing_ai/tests -t .
```

测试只用内存 / 临时目录和本地假服务器，不联网、不调用付费 API、不读写任何真实数据。覆盖范围：断句、分数计算、模型输出校验、真实 HTTP 客户端行为、登录 / CSRF / 锁定、用户之间的隔离、额度、上传校验、失败重试、重启恢复、原稿不被修改，以及“不 import 主应用”的子进程检查。

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
- 每次修改提示词都要同步更新 `prompts.PROMPT_VERSION`，每条结果都会记录生成时用的模型和提示词版本。
