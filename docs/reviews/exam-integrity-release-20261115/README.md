# 雅思诚信模式第一期：发布与只读验收

2026-11-15，用户确认当天模考全部结束、当前无学生考试，明确授权部署第一期。已于当日23:36 CST完成部署，2026-11-16 08:50 CST只读验收通过；未打开教师监考面板、未建试考、未改任何场次策略，第二期不做。

工作树 `/private/tmp/studytracker-exam-integrity-20261114`，分支 `codex/exam-integrity-review`，起点Claude复核 `9275b7a8a460f5105e4cd8f63e015e4b85f9d4d0`，开工clean。重新fetch发现main新增冲刺模块154a642f／文档3d8e7b57，已合入 `3d8e7b57732045ecf30bc66037c61f0a04095bc1`，合并提交 `32b46bd935e0325f2300ea45558da3caac18b6d9`。冲突为蓝图导入和两交接，保留双方功能/历史；CI同时保留诚信及冲刺。阅读模板的默认off测试SHA更新为最新main原模板，仍逐字节验证；不是改产品迎合测试。独立核对剥离诚信两行注册/一行include后，共享蓝图入口及阅读模板与main完全一致。旧桌面主资料树不切分支、不pull，其他脏文件不纳入发布。

## 合并后测试

- 模考/诚信/课堂回归231，新增main冲刺和历史回归181，原练习目录/判分24，合计 **436 Python** 全通过。Node **131** 全通过。
- 只读验收器8个临时SQLite/HTTP stub自测通过；不是生产验收。定向Ruff/Black、diff和15项范围审计通过，27诚信产品相对main清单在scope-audit.json，24生产文件SHA在runtime-manifest.json。
- 两套Chrome157本机合成浏览器验收通过（JSON和截图同目录），三模式完整考试、off零请求、锁定自动交卷、解锁/急停、离线补发/60秒故障保留、换机、高亮与导航均保持。真实iPad/MacSafari分屏/通知/剪贴板等未验，不假称已完成。

精确命令（cwd本工作树）：

```sh
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_exam_integrity_service tests.test_exam_integrity_routes tests.test_exam_integrity_adversarial tests.test_exam_integrity_e2e tests.test_mock_exam_runtime tests.test_mock_exam_runtime_routes tests.test_mock_exam_review tests.test_mock_exam_review_workflow tests.test_mock_exam_student_review tests.test_mock_exam_template_isolation tests.test_selection_highlight_contract tests.test_practice_highlight_coordinates tests.test_migrate_mock_exam_review tests.test_classroom_vocabulary tests.test_classroom_vocabulary_learning tests.test_dictation_answers -q
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_exam_sprint tests.test_ninefen_source tests.test_exam_sprint_routes tests.test_exam_sprint_matching tests.test_ninefen_content tests.test_ninefen_assets tests.test_ninefen_session tests.test_exam_sprint_store tests.test_exam_sprint_import tests.test_exam_sprint_publish tests.test_exam_sprint_weekly tests.test_practice_history -q
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -c 'from config import Config; Config.SQLALCHEMY_DATABASE_URI="sqlite:///:memory:"; import unittest; names=["tests.test_practice_catalog","tests.test_practice_workspace_regression","tests.test_listening_jijing_index_workspace","tests.test_reading_jijing_index_workspace","tests.test_practice_portal_catalog_grouping","tests.test_jijing_scoring"]; result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromNames(names)); raise SystemExit(not result.wasSuccessful())'
node --test tests/test_exam_guard.js tests/test_practice_shell.js tests/test_mock_exam_review_frames.js tests/test_practice_renderers.js tests/test_mock_review_paper.js tests/test_simulation_audio.js tests/test_classroom_vocabulary.js tests/test_task_dictation_preset.js tests/test_classroom_synonym_client.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -W error::ResourceWarning -B -m unittest discover -s docs/reviews/exam-integrity-release-20261115 -p 'test_verify_production.py' -v
INTEGRITY_EVIDENCE_DIR=/private/tmp/studytracker-exam-integrity-20261114/docs/reviews/exam-integrity-release-20261115 node docs/reviews/exam-integrity-20261114/browser-check.cjs
INTEGRITY_EVIDENCE_DIR=/private/tmp/studytracker-exam-integrity-20261114/docs/reviews/exam-integrity-release-20261115 node docs/reviews/exam-integrity-20261114/browser-resilience.cjs
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/exam-integrity-release-20261115/verify_release_scope.py
ssh root@47.110.45.193 'cd /root/apps/studytracker && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - --phase pre' < docs/reviews/exam-integrity-release-20261115/verify_production.py > docs/reviews/exam-integrity-release-20261115/production-before.json
```

日志：python-tests.log（231）、merged-main-tests.log（181）、practice-regression.log（24）、node-tests.log（131）。历史两期报告不覆盖，本目录为本次发布依据。

## 生产只读基线

`production-before.json`：生产HEAD `154a642fabc017557b92abbefd022dc112a383a5`，tracked clean，服务active/running、worker1/gthread6/127.0.0.1:5002、实际worker1，原113个未跟踪文件。已有模考登录及章节GET均200、无exam_guard，会话状态和开始/截止/提交字段未变；诚信三表均不存在，全部场次默认off。读取使用SQLite mode=ro/query_only、只GET不执行JS、不POST、不跟随科目入口；token/姓名/口令/正文不输出也不保存。部署脚本只读字面量审计未见create_all或诚信迁移名，不运行任意迁移作验收。

## 发布与生产只读验收结果

发布提交 **`878209f4d180ed1a9702b44257044ed394afd731`** 已由审查分支快进推到main；推前再次fetch确认main仍为3d8e7b57，没有遗漏新提交。分支CI通过后才推main。下列三个工作流均completed/success：

- [审查分支 CI 43726849639](https://github.com/KB77GG/studytracker/actions/runs/43726849639)。
- [main CI 43730767904](https://github.com/KB77GG/studytracker/actions/runs/43730767904)。两个CI的test、account-provisioning、task-planner均成功；既有非阻断lint failure仍存在，不能宣称全仓lint通过。
- [自动部署 43730767905](https://github.com/KB77GG/studytracker/actions/runs/43730767905)，2026-11-15 23:36:34 CST完成。

`production-after.json` 为2026-11-16 08:50:09 CST实际只读采样，exit0／ok=true：

- 生产HEAD准确匹配878209f4，tracked clean，原113个未跟踪文件计数保持；24个生产文件SHA和3个公网静态资源SHA全部一致。
- 服务active/running，自11-15 23:36:30 CST启动，NRestarts=0；配置和实际均单worker，gthread、6线程、127.0.0.1:5002保持，监听归属正确。
- 已有模考登录页和历史未交卷会话章节页均GET200、关键控件存在、没有exam_guard；检查前后该会话状态及开始/截止/提交时间保持，未执行JS/POST或打开科目页。
- **三张诚信表现已存在，策略0行，monitor/enforce均0，所有场次默认off。** 验收器用SQLite mode=ro/query_only，验收前后策略汇总和表状态保持；未人工建表、未访问监考面板、未创建试考或修改策略。

**建表路径与计划差异**：部署前三表不存在，部署后存在。固定标记核对确认本次标准部署日志含`Creating course_plan table...`（`deployment-schema-source.json`）；既有`create_plan_table.py:6`调用无范围参数`db.create_all()`，已注册的诚信模型因此也会被创建。不是学生路径或本次验收执行DDL，也不代表已启用场次。该既有迁移行为比计划所述“老师首次打开面板时建表”更早；本次没有改旧迁移、旧表或部署脚本。

完整精确post命令保存在`production-check-command.txt`（含runtime-manifest的非敏感base64）；运行目录为本报告工作树。工作流读取命令：

```sh
gh run view 43726849639 --repo KB77GG/studytracker --json databaseId,headSha,headBranch,status,conclusion,url,workflowName,event,createdAt,updatedAt,jobs
gh run view 43730767904 --repo KB77GG/studytracker --json databaseId,headSha,headBranch,status,conclusion,url,workflowName,event,createdAt,updatedAt,jobs
gh run view 43730767905 --repo KB77GG/studytracker --json databaseId,headSha,headBranch,status,conclusion,url,workflowName,event,createdAt,updatedAt,jobs
```

结果分别见ci-review.json、ci-main.json、deploy.json。验收证据及两交接以独立`[skip ci]`文档提交同步main和审查分支，不再次部署；生产代码HEAD仍为878209f4，文档HEAD以Git为准，不把代码CI冒称文档提交的CI。

部署与只读验收已完成，停止。用户自行打开面板、建试考和设置策略；真实iPad/MacSafari通知/分屏/系统剪贴板等仍待用户验收。小程序本任务未上传/提审/发布；SEB/托福/第二期保持未做。
