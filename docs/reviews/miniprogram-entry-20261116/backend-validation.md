# Backend entry performance validation — 2026-11-16

- Worktree: `/private/tmp/studytracker-entry-backend-20261116`
- Branch: `codex/miniprogram-entry-20261116`
- Implementation/test baseline: `878209f4d180ed1a9702b44257044ed394afd731`.
- Source changes: `services/vocabulary_context.py` and `services/vocabulary_autonomous_review.py`; new availability equivalence tests, expanded review performance test, and reproducible `scripts/benchmark_vocabulary_entry.py`.
- No production access or database changes, no commit/push/deploy by this subtask. All benchmarks use an independent synthetic in-memory SQLite database; no application config or real student records are loaded.

## Change

Review eligibility previously built full context choices for every due word that lacked a direct fill question. A request-local `ContextChoiceAvailability` now prepares catalog lemma/meaning once and determines whether the unchanged choice builders can succeed. Unique distractor labels need no sorting; duplicate labels retain the exact original SHA order and first-three-then-deduplicate rule using `heapq.nsmallest`. Collocation existence retains the original requirement for three distinct valid frames and excludes synonym entries.

Actual question builders, snapshots, grading, review ordering, due-time rules, schema, group initialization, and API preflight call structure are unchanged. No global cache or cross-request state was introduced. The two repeated queue preflight calls were intentionally left unchanged.

## Completed tests

Run from the worktree above:

```sh
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_vocabulary_context_availability tests.test_vocabulary_review_performance -q
```

Result: **7 tests, 1.781 seconds, OK**. Includes deterministic randomized equivalence against the actual unchanged builders, duplicate distractors, hash collisions preserving original order, collocation boundaries, synonyms, next-request catalog edits, and a 1,000-word context-only workload with a linear parsing bound and no full question construction during preflight.

```sh
TZ=UTC PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_classroom_vocabulary tests.test_classroom_vocabulary_learning tests.test_dictation_answers tests.test_vocabulary_mastery tests.test_vocabulary_group_learning tests.test_vocabulary_group_learning_api tests.test_vocabulary_autonomous_review tests.test_dictation_review tests.test_vocabulary_numeric_learning tests.test_vocabulary_numeric_review tests.test_vocabulary_review_performance tests.test_vocabulary_context_availability -q
```

Result: **212 tests, 15.361 seconds, OK**. This includes the 7 tests above; counts are not additive. The test output was returned directly by the tool and was not separately saved to a log file.

## Reproducible before/after benchmark

The same candidate script imports the requested baseline or candidate source tree:

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/benchmark_vocabulary_entry.py --repo /private/tmp/studytracker-exam-integrity-20261114 --output docs/reviews/miniprogram-entry-20261116/backend-baseline.json
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/benchmark_vocabulary_entry.py --repo /private/tmp/studytracker-entry-backend-20261116 --output docs/reviews/miniprogram-entry-20261116/backend-after.json
```

Both completed successfully. Each case has 1,000 synthetic catalog/mastery rows. Results are local elapsed times, not production latency promises:

| Case | Baseline ms | Candidate ms | Due count | Full eligibility question builds, before → after |
| --- | ---: | ---: | ---: | ---: |
| Meaning | 35.889 | 43.096 | 1000 | 0 → 0 |
| Context with direct fill | 179.169 | 188.515 | 1000 | 0 → 0 |
| Context choice only | 6993.708 | 173.625 | 1000 | 1000 → 0 |
| Context choice, duplicate meanings | 6978.527 | 554.469 | 999 | 1000 → 0 |

All four cases retain identical selected-candidate/order SHA-256, complete preflight payload SHA-256, and first-20 public/answer snapshot SHA-256. SQL counts remain 11 for the first two cases and 12 for the two choice-only cases. Full evidence is in `backend-baseline.json` and `backend-after.json`.

## Formatting/check limitations

An initial targeted Ruff run found import ordering, an unused random-test loop variable, and benchmark loop-closure warnings. Those reported issues were corrected; only the import-specific Ruff command was rerun and returned `Found 1 error (1 fixed, 0 remaining)`. A final complete Ruff run was **not** performed by this subtask before handoff.

Black `--check` reported that the five changed Python files would be reformatted. A subsequent read-only multi-file Black `--diff` failed because its multiprocessing manager could not bind a local socket inside the sandbox. A sandbox escalation for that read-only diff was later aborted by the user; no formatting was applied by this subtask. Do not claim Black passed. Main agent may complete formatting/targeted checks without changing implementation semantics.

No test or benchmark process remains active from this subtask. No full repository suite, production performance replay, or real-device verification was run here. Root agent owns final handoff documentation and release status.

## Root final audit

Root reran the exact 212-test command above: **212/212, 15.297 seconds, OK**, saved in `backend-root-tests-corrected.log`. An earlier root invocation referenced nonexistent `tests.test_vocabulary_context`: 192 tests passed plus one import error; corrected module selection produced the result above. Original failed invocation is retained in `backend-root-tests.log`.

Root final full targeted Ruff for the five implementation/test/benchmark files passed, and `git diff --check` passed. The two new Python files and the newly added class were formatted using Black's single-process API. Three pre-existing files already required whole-file Black formatting at baseline; their unrelated formatting was preserved. No claim of whole-repository or whole-file Black cleanliness.

Independent `independent_equivalence.py` replay: **48,768 checks, 0 differences**. Root benchmark replay: choice 168.702ms, duplicates 549.871ms; all four case selection/preflight/batch hashes agree with baseline. No additional production changes.
