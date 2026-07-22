# 题库导入流水线运行手册

> 剑雅新书（剑22 及以后）出版后，照此手册增量导入。2026-07 剑21 实测全程零代码改动。
> 9分达人系列是另一条流水线（jfdr 前缀，见 scripts/build_jfdr6_listening.py 一族），不在本文范围。

## 数据源：idictation.cn

- 接口需登录态，且会话 cookie 是 **httpOnly**，脚本直连拿不到。做法：用户在浏览器登录一次 → 在已登录页面内注入签名 fetch（HMAC-SHA256，secret 与 `scripts/import_idictation_xyy_listening.py` 的 `signed_body` 同构）→ 数据 POST 回本地小型 CORS 接收器落盘。
- **combined 目录**（`/api/study/zhenti/v1/combined/jianya/list`）一次含三科：每个 test 节点有 `listening.children`（part id）、`reading.children`（passage id）、`writing.xiaozuowen/dazuowen`（写作题面 + Task1 图 URL）。**写作无需单独抓**。
- 音频/图片在阿里云 OSS，下载不需要登录。

## 各科跑法（均基于合并后的 raw 文件 + `--no-fetch`）

抓到的目录/part 响应合并进两个 untracked 文件（勿提交）：
`data/idictation_xyy_listening/raw.json`（`{catalog, parts}`）与 `data/idictation_reading/raw.json`（console 导出格式）。

1. **听力**：`import_idictation_xyy_listening.py --no-fetch --books 4-XX --insecure`
   必须用**全范围**（否则重写掉 git 追踪的 import_report.json 里旧书记录）；已有音频/JSON 自动跳过。
   然后 `build_listening_test_practice.py ieltsXX_testN` **逐套**构建（别用 `--all`，避免旧文件时间戳无谓 diff）。
2. **阅读**：坑① `build_reading_test_practice.py` 读 `raw["entries"]` 清单而非 catalog，新书要先按目录追加 entries；
   坑② 构建用 `--output-dir <临时目录>/reading_tests`（目录名固定，作图片路径前缀），只回拷新书文件 + catalog.json。
   MaterialBank：`.venv/bin/python import_idictation_reading_materials.py --no-fetch --books 4-XX`（按标题幂等去重）。
3. **写作**：`build_writing_test_practice.py`（读 xyy raw.json 的 catalog）一跑即得 `static/writing_tests/` 全量。

## 上线

- 静态 JSON/图片进 git，push 即部署；**mp3 在 .gitignore**，需单独 `scp` 到 `aliyun-server:/root/apps/studytracker/static/listening/`（服务器上 untracked 留存，deploy reset --hard 不清）。
- 刷题库/模考选卷目录全部由静态文件 glob/catalog 驱动，**小程序前端无需发版**。
- 生产 MaterialBank：raw 上传服务器后用 `/root/apps/studytracker/.venv/bin/python` 跑同一脚本 `--no-fetch`；改 MockExam 等模型字段后跑 `scripts/migrate_mock_exam_writing.py` 这类幂等补列脚本。生产库操作前先 `sqlite3 app.db ".backup ..."`。
- 注意：Claude Code auto 模式下生产库写入会被权限分类器拦截，这类命令由人手动执行。
