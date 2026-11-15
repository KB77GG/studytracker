# 第一期审查分支完整改动清单

比较基线：`ecc06f2393a5f3a0646f36f3a6dceda4902c1c08`；目标分支：`codex/exam-integrity-review`。

共 **55 个文件**：27 个产品／测试／CI 文件、28 个文档／验收证据文件。`ci-review.json` 在首轮分支 CI 完成后写入。`docs/EXAM_INTEGRITY_PLAN.md` 已在基线，不另行修改。无 main 合并、部署配置改动或小程序改动。

## 产品、测试与 CI

- `.github/workflows/ci.yml`
- `api/__init__.py`
- `api/exam_integrity.py`
- `models.py`
- `scripts/create_exam_integrity_tables.py`
- `services/exam_integrity.py`
- `services/exam_integrity_rules.py`
- `static/css/exam_guard.css`
- `static/js/exam_guard.js`
- `templates/admin/_exam_integrity_summary.html`
- `templates/admin/mock_exam_integrity.html`
- `templates/admin/mock_exam_session_detail.html`
- `templates/admin/mock_exam_sessions.html`
- `templates/admin/mock_exams_index.html`
- `templates/exam/_integrity_guard.html`
- `templates/exam/integrity_guide.html`
- `templates/exam/integrity_help.html`
- `templates/exam/process.html`
- `templates/exam/writing.html`
- `templates/listening/test_practice.html`
- `templates/reading/test_practice.html`
- `tests/exam_integrity_e2e_support.py`
- `tests/test_exam_guard.js`
- `tests/test_exam_integrity_adversarial.py`
- `tests/test_exam_integrity_e2e.py`
- `tests/test_exam_integrity_routes.py`
- `tests/test_exam_integrity_service.py`

## 文档与验收证据

- `docs/CODEX_HANDOFF.md`
- `docs/EXAM_INTEGRITY_RUNBOOK.md`
- `docs/WORKLOG.md`
- `docs/reviews/exam-integrity-20261114/README.md`
- `docs/reviews/exam-integrity-20261114/REVIEW_FILES.md`
- `docs/reviews/exam-integrity-20261114/browser-check.cjs`
- `docs/reviews/exam-integrity-20261114/browser-resilience-results.json`
- `docs/reviews/exam-integrity-20261114/browser-resilience.cjs`
- `docs/reviews/exam-integrity-20261114/browser-results.json`
- `docs/reviews/exam-integrity-20261114/ci-review.json`
- `docs/reviews/exam-integrity-20261114/enforce-result.png`
- `docs/reviews/exam-integrity-20261114/enforce-rules.png`
- `docs/reviews/exam-integrity-20261114/implementation-status.txt`
- `docs/reviews/exam-integrity-20261114/main-worktree-status.txt`
- `docs/reviews/exam-integrity-20261114/monitor-result.png`
- `docs/reviews/exam-integrity-20261114/node-tests.log`
- `docs/reviews/exam-integrity-20261114/off-result.png`
- `docs/reviews/exam-integrity-20261114/python-tests.log`
- `docs/reviews/exam-integrity-20261114/reading-locked.png`
- `docs/reviews/exam-integrity-20261114/resilience-device-conflict.png`
- `docs/reviews/exam-integrity-20261114/resilience-locked-before-table-drop.png`
- `docs/reviews/exam-integrity-20261114/resilience-new-device-active.png`
- `docs/reviews/exam-integrity-20261114/resilience-old-device-conflict-after-reset.png`
- `docs/reviews/exam-integrity-20261114/resilience-reading-highlight.png`
- `docs/reviews/exam-integrity-20261114/resilience-tables-missing-result.png`
- `docs/reviews/exam-integrity-20261114/scope-audit.json`
- `docs/reviews/exam-integrity-20261114/teacher-mobile.png`
- `docs/reviews/exam-integrity-20261114/verify_scope.py`

报告中的学生、试卷和口令均为合成数据；不含生产数据库或真实学生资料。`implementation-status.txt`、`main-worktree-status.txt`、scope JSON 的 HEAD 为验收时快照，最终提交以分支 Git 记录为准。
