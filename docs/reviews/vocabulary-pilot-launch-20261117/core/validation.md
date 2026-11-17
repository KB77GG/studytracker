# Graduation checkpoint core validation

Worktree `/private/tmp/studytracker-vocabulary-error-pilot-20261117`, branch `codex/vocabulary-error-pilot-20261117`, baseline `513c732f`. These are local synthetic results for the graduation/core/migration subtask. Root owns the final combined release verification and production rollout; the performance and reporting agents are editing separate functions/modules in this shared tree.

## Final related suites

Commands run from this worktree:

```sh
/private/tmp/studytracker-stage2-py310/bin/python -m unittest tests.test_vocabulary_error_queue tests.test_vocabulary_graduation_checkpoints tests.test_vocabulary_checkpoint_migration -q
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_vocabulary_error_queue tests.test_vocabulary_graduation_checkpoints tests.test_vocabulary_checkpoint_migration -q
```

- Python 3.10: **50 tests passed**, 7.466 seconds.
- Python 3.13: **50 tests passed**, 6.344 seconds. Existing ORM `datetime.utcnow()` defaults emit a deprecation warning; no failing test.
- Breakdown: 32 existing core cases, 10 new graduation/reset cases, 8 new migration cases. This is not the full repository suite or production verification.

Additional checks:

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check services/vocabulary_checkpoint_identity.py scripts/migrate_vocabulary_checkpoint_sources.py tests/test_vocabulary_checkpoint_migration.py tests/test_vocabulary_graduation_checkpoints.py
git diff --check
```

Both passed. Black formatted the four new Python files; only the two owned policy model classes and owned hook functions were formatted in shared legacy files. An AST comparison against `git show 513c732f:models.py` found 80 classes, with only `VocabularyErrorQueue` and `VocabularyPolicyCheckpoint` changed; no class was added/removed and all other 78 class ASTs matched exactly.

## Meaningful behavior coverage

- First-correct D7/D30 keep `source_kind=first_correct`, `source_key=initial`, no origin event, and exactly the deployed stable selection SHA.
- Only an actual two-delayed-success graduation schedules D7. It references the immutable closed event and actual graduation timestamp; replay does not duplicate it.
- Repeated error/graduation cycles create distinct D7 opportunities with distinct event provenance. They do not masquerade as initial D7/D30 or overwrite earlier outcomes.
- Five simultaneous graduation opportunities yield four allocated samples; the unselected opportunity becomes missed. Coincident first-correct/graduation opportunities for one ability use one slot, and the unused source does not borrow the answer.
- A failed graduation sample reopens only its ability for the next natural date and retains sample source/outcome. New errors after completed graduation are not false “progress resets.”
- `success_reset` records actual positive→zero progress only, distinguishes learning/review sources, excludes repeated zero→zero errors and idempotent replays.
- Graduation event/checkpoint creation rolls back atomically with its answer. OFF creates neither opportunities nor retrospective history.

## Migration safety coverage

The file-backed fixtures contain nonempty old D7/D30 checkpoints plus real allocation/event foreign-key references. Tests verify:

- Default dry-run uses an existing database read-only, leaves bytes unchanged, and does not create a missing file. CLI errors print type only, without database paths.
- Old checkpoint IDs, every old column value, dependent allocation/event rows, all other table rows, and all unrelated `sqlite_master` definitions remain identical after the rebuild. Only the checkpoint definition and declared queue index differ.
- Old opportunities become `first_correct/initial` with preserved selection SHA; no student row or additional opportunity is created.
- The migrated checkpoint column definitions and foreign keys exactly match the current ORM-created schema, and repeated D7 graduation sources can coexist with initial D7.
- Failures injected after copy, after old-table drop and before commit each fully roll back schema and data with foreign-key mode restored, tested with both initial FK modes 0 and 1.
- Repeating migration is a no-op. Partial/unsupported schemas, an active caller transaction and conflicting named-index definitions are refused.
- Existing empty policy tables migrate without creating students or checkpoints; this matches the expected pre-pilot deployment case but does not replace a fresh production readback.

Early test construction exposed two synthetic-fixture defects (reading an expired detached book ID and missing old review-item non-null defaults); those were corrected before the final runs above. No production data was involved and no product assertion was weakened to pass them.

## State and next step

Core-owned files: `models.py` declared policy changes, owned hooks in `services/vocabulary_error_queue.py`, `services/vocabulary_checkpoint_identity.py`, `scripts/migrate_vocabulary_checkpoint_sources.py`, the two new test modules and this folder. The full schema/API/rollout contract is in `contract.md` here.

All changes are currently local to the shared worktree. This subtask has not committed, pushed, deployed, modified a production database, enrolled students or published a mini-program. Root should include new files in CI/manifest, independently audit migration, run combined suites after the other agents freeze, then keep global OFF through the explicit migration and readback before pilot activation.
