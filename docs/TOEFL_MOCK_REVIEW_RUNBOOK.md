# TOEFL v2 模考批改、复盘与录音运维

## 录音存储与访问

- 默认私有目录：`private_uploads/toefl_mock/<attempt-id>/<uuid>.<ext>`。
- 生产默认实际路径：`/root/apps/studytracker/private_uploads/toefl_mock/...`。
- 可用环境变量 `TOEFL_MOCK_RECORDING_FOLDER` 改到独立数据盘；该目录不得放进 Nginx 静态目录或公共 `/uploads`。
- 数据库 `toefl_mock_response.recording_token` 只保存私有目录内的相对 token。API、HTML 和日志不得返回服务器绝对路径或该 token。
- 老师/助教/管理员可在已交卷 attempt 的批改页播放；学生仅能播放自己的录音，且要等老师发布批改。播放统一走鉴权接口，并返回 `private, no-store`。

## 教学流程

1. 学生交卷后，在 `/toefl/mock/history` 打开自己的模考复盘。客观题立即显示题干、作答、正确答案、原文或原音频；主观题先显示待批改。
2. 老师在 `/toefl/mock/teacher/attempts` 按学生或状态筛选，进入详情后播放题目原音频和学生录音，查看写作原文，逐题填写固定的 0–5 整数任务级分数与反馈并保存草稿。满分固定为 5，不接受 0.5 分或自定义满分；每题响应保存对应的 `rubric_code` / `rubric_version`。
3. 全部已提交主观题评分完成后才能发布。发布后学生看到分数、反馈和自己的录音；需要修改时，老师先“重新开放”，修改后再发布。
4. 客观错题页老师和学生使用同一份只读题目结构，可打开原文/原音频，按“你的答案 → 正确答案 → 现有讲解/证据”顺序讲解。系统当前不保存老师对客观题的额外批注。

## 分数边界与学生文案

- 完成页、历史摘要和复盘页明确标注为“本站练习”。Reading / Listening 按 definition 与 answer key 的实际 eligible 题数展示 `correct / eligible_total`、已答、正确率和错题；例如 `ets-practice-1..5` 的实际自动题数为 R=40、L=34，`ets-og-chapter-6` 为 R=50、L=47。不能把这些题数称为 ETS official raw，也不能换算官方 0–30 或 1–6。
- Writing 的练习原始累计分仅在两道构答题都完成老师评分后显示，计算为 10 道 Build a Sentence 客观题（每题 1 分）加两道 0–5 任务级分，满分 `/20`。Speaking 仅在 11 道回答都完成老师评分后显示练习原始累计分 `/55`。
- 2026-01-21 起 ETS 官方单科与总分使用 1–6、0.5 递增。新版 Reading / Listening 为自适应测试，含非计分题，并经过 ETS 统计分析与质量检查；本站不自行生成 band。参考：[ETS Updated TOEFL iBT Test Overview](https://www.ets.org/pdfs/toefl/toefl-ibt-test-overview.pdf) 与 [ETS 2026 Test Specifications](https://www.ets.org/pdfs/toefl/toefl-ibt-test-specifications-2026.pdf)。

## 上线与备份

1. 先备份 `app.db`。因为旧数据库必须在新 ORM 代码启动前补列，首次上线要先把迁移脚本单独复制到服务器临时目录并执行，再 push/deploy 新代码：
   `scp scripts/migrate_toefl_mock_review.py aliyun-server:/tmp/`
   `ssh aliyun-server '/root/apps/studytracker/.venv/bin/python /tmp/migrate_toefl_mock_review.py --database /root/apps/studytracker/app.db'`
2. 迁移脚本可重复执行，且不得覆盖 `draft`、`reviewed` 或 `published` 状态。
3. 发布代码后，用真实学生和教师账号完成一次“录音上传 → 教师播放/批改/发布 → 学生复盘/播放”的端到端验证。
4. Git 部署不会删除私有录音目录，但它也不会自动备份。学生正式使用前，服务器备份必须同时覆盖：
   - `/root/apps/studytracker/app.db`
   - `/root/apps/studytracker/private_uploads/toefl_mock/`
   两者应来自同一备份时间点，否则数据库与文件可能无法对应。

## 保留策略

- 当前策略是“持续保留，禁止自动删除”，以免学生记录与文件失配。
- 若以后需要限期保留，应先增加带 dry-run、数据库交叉校验和审计日志的清理脚本，再由管理员明确设置保留天数；禁止直接按目录时间批量删除。
- 删除学生/attempt 时，应由应用工作流先撤销访问并记录审计，再删除对应私有文件。当前版本尚未实现自动级联文件删除。

## 当前评分边界

- 每道口语/写作题固定记录 ETS task-level 0–5 整数；`score_max` 仅为旧数据兼容列，服务端始终保存并展示 5，不允许编辑。
- 旧字段 `objective.correct` / `objective.auto_total` 保留；新 `practice_breakdown.by_subject` 提供按科目的本站练习统计，避免把 Reading、Listening 和 Writing Build a Sentence 混在一起。
- 当前不把任何本站练习累计分换算为 ETS 官方 0–30 或 1–6 scaled score，也不声称等同官方成绩。
