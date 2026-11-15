# 雅思诚信模式第一期：发布与只读验收

2026-11-15，用户确认当天模考全部结束、当前无学生考试，明确授权部署第一期；不打开教师监考面板、不建试考、不改任何场次策略，第二期不做。当前为发布准备，部署后的真实结果随后补记。

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

## 发布与边界

待将本次报告和交接提交到审查分支，分支CI通过后快进合入远端main触发既有部署流程；生产验收只执行verify_production.py的post模式，要求准确HEAD、24SHA、服务配置不变、两既有页面200和所有诚信策略关闭。绝不访问监考面板、创建试考或修改策略；不手工建诚信表。原部署链既有迁移随标准部署照常，验收器不导入app/config也不写业务DB。

完成后更新交接并停止。用户之后自行打开面板、创建试考及设置策略；第一场真实考试仍建议monitor。小程序未新增本任务改动、不会上传/提审/发布；SEB/托福/第二期保持未做。
