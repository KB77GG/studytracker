# Graduation D7 checkpoint and migration contract

Worktree `/private/tmp/studytracker-vocabulary-error-pilot-20261117`, branch `codex/vocabulary-error-pilot-20261117`, starting HEAD `513c732f`. Root approved this schema contract and owns production deployment/migration/activation. Core agent does not commit, push, deploy, enroll students or access production.

## Behavior

The accepted B2 rule remains: two qualified independent first-answer successes separated by two natural dates graduate an error ability. Only a new graduation during an enabled cohort creates a new D7 sampling opportunity. It shares the existing maximum four daily sample slots; no extra daily burden or backfill is introduced. It is an opportunity for sampling, not a promise every graduated ability will be tested when more than four are due.

Sources remain separate:

| source_kind | source_key | anchor_at | interval_days | origin_event_id |
| --- | --- | --- | --- | --- |
| first_correct | initial | first correct exposure | 7 or 30 | NULL |
| graduation | graduation:<closed-event-id> | actual graduation | 7 | immutable closed event |

`cohort_key` always remains the enrollment cohort. `interval_days` remains the actual elapsed interval; no negative/special interval codes. Repeated graduations of the same student/sense/ability each link to a distinct closed event and create a distinct D7 opportunity. Retried answers do not create duplicate events/checkpoints; the closing answer, event and checkpoint share the caller transaction and roll back together. Optional-maintenance completion does not schedule graduation sampling.

The existing checkpoint `pending/answered/missed` states and answer events retain origin-specific denominators and outcomes. A source that was not selected by its target date is missed. When first-correct and graduation opportunities for the same ability coincide, planning allocates only one using the stable selection order; the other does not borrow the answer and becomes missed. Reports must show coverage and source separately, not treat all missed items as failures or merge first-correct D30 with graduation D7.

## Model changes and indexing

`VocabularyPolicyCheckpoint` gains:

- `source_kind VARCHAR(24) NOT NULL DEFAULT 'first_correct'`.
- `source_key VARCHAR(96) NOT NULL DEFAULT 'initial'`.
- `origin_event_id INTEGER NULL`, foreign key to `vocabulary_policy_event.id` (SQLAlchemy `use_alter` breaks the metadata cycle for sorting; SQLite stores the actual FK).
- `selection_key VARCHAR(64) NOT NULL`, deterministic SHA-256 computed by shared pure helper `services/vocabulary_checkpoint_identity.py` and the ORM insert default.

Unique key changes from `(student_id,sense_id,dimension,cohort_key,interval_days)` to `(student_id,sense_id,dimension,cohort_key,source_kind,source_key,interval_days)`. Existing first-correct selection hashes are preserved exactly; graduation hashes additionally include source kind/key.

Indexes added:

- `ix_vocab_checkpoint_select(student_id,cohort_key,status,due_local_date,selection_key,id)`.
- `ix_vocab_error_paused(student_id,cohort_key,status,pause_until_local_date,id)`.

Performance agent owns planning, bounded cleanup and reservation snapshots. Core owns these columns, deterministic identity, graduation hooks and success-reset events. Existing `VocabularyPolicyAllocation.checkpoint_id` and `VocabularyPolicyEvent.checkpoint_id` continue to reference the same checkpoint table/IDs.

## Reset metric

New event `kind='success_reset'` occurs only when an active error queue actually changes from positive successful-review progress to zero due to a new error. Repeated 0→0 errors, replayed answers, and a fresh error cycle after completed graduation do not count. `detail_code` is `learning_error` or `review_error`, with explicit `sample_error` / `maintenance_error` for an unusual concurrent path that truly resets active progress. Transition version keys give event idempotency. No event-table schema change or retrospective reset inference is required. The teacher metric uses actual reset events for each unique new error ability, not all wrong answers.

## Explicit migration

`scripts/migrate_vocabulary_checkpoint_sources.py --database PATH` defaults to URI read-only dry-run. `--apply` is required to write. Missing files are not created; output contains only aggregate schema/count/status data and exception type, never path, row payload or student identity.

An old UNIQUE constraint cannot be removed by `ADD COLUMN`, so migration rebuilds **only the checkpoint table** inside one `BEGIN IMMEDIATE` transaction. It preserves every old column/value/ID, copies old opportunities as `first_correct/initial`, computes their original stable key, preserves explicit old indexes/triggers, restores allocation/event references, and creates the two new indexes. It changes no enrollment, student, answer or mastery record and creates no new opportunities. It accepts the exact supported old/new column and unique-key layouts; partial schemas or conflicting named indexes fail closed.

SQLite foreign-key mode is read and disabled outside the transaction, verified disabled, then restored after success or rollback. Referential checks cover the checkpoint and its allocation/event dependents before commit. Failure after copy, after drop, or before commit rolls back both DDL and rows. Already migrated valid schema/indexes is an idempotent no-op.

Root's rollout order: recheck production OFF/empty enrollment and schema; deploy new code with global OFF; run migration dry-run, explicit apply, and readback; verify allowed schema changes and preserved business records; only then consider the separately managed pilot activation. `db.create_all()` does not perform this migration. If release validation fails, keep policy OFF; rollback does not require deleting the new provenance fields or learning history.

## Local ownership and tests

New files owned by core: pure identity helper, migration script, `tests/test_vocabulary_graduation_checkpoints.py`, `tests/test_vocabulary_checkpoint_migration.py`, and this folder. `models.py` changes only the two declared policy classes plus the pure-helper import. Core edits only its scheduling/reset/answer hooks in the shared queue service; performance edits the planning/lock functions in parallel.

Exact final commands/results are in `validation.md` after validation finishes. Earlier standalone tests passed ten graduation/reset cases and eight migration cases on Python3.13; this is not production verification or the full repository test suite.
