# Core policy implementation and validation

Local worktree `/private/tmp/studytracker-vocabulary-error-pilot-20261117`, branch `codex/vocabulary-error-pilot-20261117`, baseline HEAD `f414a126`. This report covers the core subtask only. Root owns integration acceptance, handoff, deployment and pilot activation.

## Implemented files

- `models.py`: five new opt-in policy tables; no changes to existing table definitions.
- `services/vocabulary_error_queue.py`: opt-in enrollment guard, independent ability error queue, date scheduling, deterministic D7/D30 checkpoint quota, per-day persistent reservations, idempotent answers, overload handling, read-only summary and caller-transaction housekeeping.
- `config.py`: seven parameter defaults/environment inputs alongside root's default-OFF global flag.
- `tests/test_vocabulary_error_queue.py`: 32 synthetic core tests including real two-connection SQLite writer contention.
- `core-contract.md` in this folder: API, storage, settings and counter semantics for other agents.

## Exact verification

Executed from the worktree above:

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_vocabulary_error_queue -q
```

Python 3.13: **32 tests passed**, 3.028 seconds. Existing model timestamp defaults produce a Python 3.13 `datetime.utcnow` deprecation warning; no test failure.

```sh
/private/tmp/studytracker-stage2-py310/bin/python -m unittest tests.test_vocabulary_error_queue -q
```

Python 3.10: **32 tests passed**, 3.631 seconds.

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m black --check services/vocabulary_error_queue.py tests/test_vocabulary_error_queue.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check services/vocabulary_error_queue.py tests/test_vocabulary_error_queue.py
git diff --check
```

All passed. Only the inserted model block was formatted; unrelated legacy model formatting was preserved.

## Meaningful boundaries covered

- Global OFF performs no SQL even when called with a synthetic unknown student; invalid policy settings also remain irrelevant while OFF.
- No legacy mastery import; enrollment start and first-formal-attempt restrictions; task learning success cannot graduate an error queue.
- Shanghai date rollover, two successes separated by configured natural dates, reset on error, three separate failed review dates and seven-day pause/resume.
- Daily 20/4 quotas, optional 10, sample-only daily ceiling, stable samples, missed checkpoint dates and no hidden quota loss when fewer samples exist.
- Today priority, overload-only transfer after seven overdue dates, and empty claims persisting all-old transfers without answer credit.
- Same student, same answer through two concurrent SQLite connections advances once; two overlapping 15-slot reservations cannot allocate 30 slots under a 20-slot limit.
- Cross-student queue ownership, idempotency-key reuse across abilities/items, caller rollback, stale plans and cross-day stale slots.
- A new error from another task after review allocation does not let that old same-day slot count as an independent next-day success.
- Unusable material never counts as mastery; explicit skipping consumes slot capacity only after the adapter's separate validation contract.
- A stale failed materialization cannot downgrade a newer error cycle: queue-version validation under the writer lock rejects it. Skipping an already-issued bad item also preserves a newer future-due error.
- Non-default values exercise all seven parameters; invalid integers, zero/negative capacities and sample quota above total quota are rejected.

## Local-only state and limits

The core subtask made no commit, push, deployment, production request, production data change, pilot activation or mini-program publication. Its code was present only in this shared worktree when this report was written. The worktree also contains root/integration/teacher changes owned by those agents; they were not overwritten or included in the core-only assertions above.

All tests use synthetic data and temporary/in-memory SQLite. They establish core semantics and transactional behavior, not real student throughput or educational effectiveness. Adapter/report suites, full CI and any production OFF acceptance belong to the root task. Management must validate `policy_settings()` before activation and roll back an enrollment conflict; trial students remain separately opt-in.
