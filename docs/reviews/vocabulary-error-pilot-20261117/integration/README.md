# Error-review pilot: backend protocol integration

Follow-up independent management/client review and the optional N+1 correction are recorded in [management-review.md](management-review.md). At that later freeze the management suite has 16 tests and integration suite 24 tests, both passing on Python 3.10; the 22-test results below describe the initial integration acceptance.

## Local state and ownership

- Worktree: `/private/tmp/studytracker-vocabulary-error-pilot-20261117`.
- Branch: `codex/vocabulary-error-pilot-20261117`; baseline/HEAD at this report: `f414a126`.
- This integration is **uncommitted local work**. No commit, push, deployment, production database write, enrollment, or mini-program upload/release was performed by this integration task.
- The shared worktree also contains concurrent core/schema/config, teacher-report, management, and frontend work. Those files are owned by the coordinating agents; this report is not a claim that their independent acceptance or deployment is complete.
- Integration-owned changes: `services/vocabulary_error_review.py` (new adapter), `services/vocabulary_autonomous_review.py`, `services/vocabulary_group_learning.py`, `services/vocabulary_mastery.py`, `api/vocab_review.py`, and `tests/test_vocabulary_error_review_integration.py`.

## Behavior

The global switch OFF follows the original services and response shapes, including an explicit optional-mode request. A SQL-listener regression exercises claim, answer, settle and summary with the switch OFF and asserts zero queries against all five new tables.

For an enrolled student, mandatory selection and task entry use the new policy's current Shanghai-date plan. Historical mastery debt is never scanned for the mandatory gate, claim or settlement. Existing frozen questions, grading, item identity, corrections, idempotency, session tokens and settlement records remain authoritative. Same-word different-ability entries are separate items and consume separate daily slots. Guidance, correction, retry, and immediate remediation do not create independent successes in the policy.

Optional maintenance is explicitly selected by `GET /api/miniprogram/student/vocabulary-review/today?mode=maintenance`. It materializes existing due candidates, excludes active/paused error abilities and today's already allocated abilities, and uses the separate daily maintenance capacity. Optional sessions never block a new learning task. An already-active other mode returns `409 review_other_mode_active` plus its mode and session identity; it is never overwritten.

The old question builder materializes the selected batch before the write lock and revalidates that finite batch after acquiring it. Policy capacity and freshness are checked again in the same transaction. Invalid initial candidates are deferred with a reason rather than counted correct. Invalid frozen items may only be skipped after the existing server-side validator approves the reason; the skipped slot consumes capacity without advancing mastery or policy success. Empty claims call `refresh_day` so an all-overdue overload still durably transfers entries and writes its events.

Policy sessions expire at the natural-date boundary even if an origin task has a grace period. Enrollment and legacy claim are serialized in both directions: an in-flight legacy claim rechecks enrollment after owning the writer lock; enrollment rechecks active sessions under its own lock. With the global switch ON, the three first-answer paths ensure a real outer SQLite transaction before their SAVEPOINT, so a policy conflict rolls back the answer record and learning cursor/mastery together. OFF does not add this new behavior.

## Student response contract

Enabled empty claims, active session snapshots, settlements (including replay), and continuation responses include:

| Field | Meaning |
| --- | --- |
| `policy_enabled`, `policy_version` | `true`, `error_queue_v1` |
| `mandatory_remaining`, `mandatory_answered` | Today's remaining selected/reserved work and completed slots |
| `mandatory_limit`, `checkpoint_limit` | Configured mandatory and checkpoint capacities; defaults 20 and 4 |
| `maintenance_remaining`, `maintenance_limit` | Remaining daily optional capacity and configured limit; default 10 |
| `optional_available` | Whether optional capacity remains or an active optional batch must be resumed, **not** an exact eligible old-pool count |
| `overloaded`, `deferred_count`, `paused_count` | Core policy summary |
| `session_mode` | `mandatory` or `maintenance` |

`batch_limit` follows the applicable configured limit. Existing `items`/`words`, queue and session tokens, answer identities, score and correction fields remain compatible. Summary exposes a mandatory active session in the old active-session fields and optional activity separately in `optional_active_session_id`/`optional_active_session_token`. An optional batch whose ten slots are already reserved/answered remains accessible at zero remaining capacity until it is settled; it still does not prevent starting an actual new group-learning flow.

An empty mandatory materialization can have positive `remaining_due_count` and `continue_available` when one finite batch of broken candidates was deferred and other candidates remain. This means retry/continue, not that today's mandatory work is finished. Empty optional claims do not offer continuation simply because unused capacity remains. The in-progress task `gate_only` shortcut retains `None` counts and returns configured limits without calculating the queue.

## Reproducible validation

Commands run from this worktree using the local Python 3.10 environment:

```sh
/private/tmp/studytracker-stage2-py310/bin/python -m unittest tests.test_vocabulary_autonomous_review tests.test_vocabulary_group_learning tests.test_vocabulary_mastery tests.test_vocabulary_flow_backlog_gate -q
# 103 tests passed, existing test assertions unchanged; repeated after the transaction/race guards.

/private/tmp/studytracker-stage2-py310/bin/python -m unittest tests.test_vocabulary_error_review_integration -q
# 22 tests passed.

/private/tmp/studytracker-stage2-py310/bin/python -m unittest tests.test_vocabulary_error_queue tests.test_vocabulary_error_review_integration -q
# 54 tests passed (32 core + 22 integration), including the optional zero-budget resume regression.

/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check services/vocabulary_error_review.py tests/test_vocabulary_error_review_integration.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff format --check services/vocabulary_error_review.py tests/test_vocabulary_error_review_integration.py
git diff --check
```

The 22 integration tests cover OFF SQL isolation; no historical import/scan; HTTP mode and resume; same-word two-ability allocation; first-answer replay and correction; D1/D3 graduation; four checkpoints inside 20 slots; optional ten and forgot; midnight boundary; unusable candidates; all-overdue empty-claim transfers; configurable limits; finite-batch revalidation rollback; server-validated skips; learning guidance/retry exclusion; and three policy-failure rollback paths. Two tests use a temporary file SQLite database and independent threads/app contexts to prove both enrollment/legacy-claim race orderings.

Known pre-existing lint/style debt remains in the large touched legacy files; for example the `I001` error in `api/vocab_review.py` reproduces against `git show HEAD:api/vocab_review.py`. This task did not reformat entire legacy files to hide the narrow functional diff. Test warnings concern synthetic JWT secret length and pre-existing SQLAlchemy `Query.get` calls.

## Remaining release work

The coordinating agent must finish the combined suite, migration/management dry run, independent review, authorized deployment and readback. This report has no production-health or student-device acceptance evidence. New frontend assets are not claimed uploaded or released. Pilot enrollment and observation require the explicit activation process; no historical error flags should be imported.
