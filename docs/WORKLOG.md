# 工作日志（跨机器进度同步）

> 目的：在任何一台电脑上开工时，AI agent / 人先读这里，30 秒接上进度。
> 约定：每次有实质进展的会话结束时**追加一条**（新条目放最上面）；记"做了什么、现场状态、下一步、坑"，不记代码细节（看 git log/diff）。
> 注意：这里要记录 **git 之外的状态**（生产库操作、服务器上的手动步骤、外部服务状态），这些从 commit 历史里看不出来。

---

## 2026-07-22 三科模考上线 + 教师材料布置启用

- **三科模考**（commit `a9799065`）：模考在听力/阅读之外新增写作科（60min、Task1/Task2、自动存稿、截止自动交卷、不自动判分留老师评）。写作题库剑4–21 共 72 套已构建入库（`static/writing_tests/`，Task1 图表图齐全）。旧两科模考零回归。
- **教师按材料布置剑雅阅读**：生产 MaterialBank 已导入剑4–21 全量 **216 篇 / 2880 题**（type=`ielts_reading_practice`）。入口在 web 后台 `/materials` 与 `/tasks`（小程序端无需发版，学生端消费已有任务流）。
- 生产已执行：`scripts/migrate_mock_exam_writing.py`（幂等补列）；库备份 `app.db.bak-20260722`。
- 修复昨日遗留：剑21 听力 Test2 题目配图漏提交（已补）；`test_practice_tables` 计数 193→196。
- **下一步/待办**：老师实际建一场剑21 三科模考做真人 QA；可选项——写作 AI 预评分接入（评分 skill 已有，未接）；模考结果页总分目前只平均听力+阅读。

## 2026-07-21 剑桥雅思21 听力阅读导入上线

- 剑21 听力 4 套（整卷刷题 + 精听 16 section + 16 mp3）与阅读 4 套（整卷刷题 + catalog 全量重建）导入并部署（commit `9607915a`）。数据来自 idictation.cn 既有流水线，跑法与坑位见 [docs/IMPORT_PIPELINES.md](IMPORT_PIPELINES.md)。
- 生产手动步骤（git 外）：16 个 mp3 scp 到服务器 `static/listening/`（mp3 在 .gitignore）；阅读 raw 数据在服务器 `/tmp/idict_reading_raw.json`。
- 生产库备份：`app.db.bak-20260721`。
