# Final independent transaction and pilot selection review

Scope: uncommitted launch changes in `/private/tmp/studytracker-vocabulary-error-pilot-20261117`, branch `codex/vocabulary-error-pilot-20261117`, baseline `513c732f`. Reviewed the planning, review adapter, initial-flow transaction, projected catalogs and pilot selector owned by other agents. Core schema/graduation changes were previously implemented by this reviewer and are not represented as independent review. No production connection, commit, push or deployment was performed. Root owns the canonical handoff and final release verification.

## Findings and disposition

1. **Selected synonym source could change between question preparation and reservation. Resolved locally.** `_source_signature` previously included Word and its Book but omitted Sense. A synthetic request edited the selected synonym Sense from `accurate` to `precise` immediately before the SQLite outer transaction. The claim succeeded with frozen answer `accurate` while the current Sense was `precise`. The integration owner now fingerprints all scalar columns of the selected Word, Sense and effective Book, and explicitly refreshes those related rows under the writer. The new formal negative control rejects the edit with `review_claim_changed` and verifies rollback leaves no session/allocation while preserving the independently committed source edit.

2. **The effective representative Book was omitted when Word.book was missing. Resolved locally.** The same signature refresh now includes `mastery.representative_book` when it supplies the actual goal. A second formal negative control changes that Book from listening to reading after preparing an orphan-book numeric item. It now rejects the stale question atomically. This is distinct from the scalar selector fallback omission documented in `optional-selection-review.md`.

3. **A preexisting representative Word rebound to another Sense could generate the wrong ability question. Resolved locally.** Synthetic setup creates an error for Sense A, then rebinds its representative Word to Sense B before claiming. The existing bulk resolver prefers the representative ID; the initial adapter accepted it and created an item with `item.sense_id=A` but `item.word.sense_id=B`. This would apply an answer about B to A's queue. The owner correction is limited to the ON path: treat such material as unusable, preserve its history, move it through the existing `unanswerable` route and consume no answered allocation. The newly added formal regression initially failed because a session was incorrectly claimed, and now passes. It also verifies optional selection continues with ten valid items and does not make false success progress on the quarantined ability. The OFF resolver is unchanged.

## Reservation and rollback assessment

- Planning reads counts, finite candidates and bounded cleanup IDs before acquiring the SQLite writer. It carries the enrollment `state_version`; each policy mutation acquires/increments the same enrollment version. Reservation checks that the acquired version equals the prepared version plus one. Concurrent policy changes therefore invalidate the prepared allocation plan rather than silently allocating the obsolete set. Existing per-item identity/version and daily ability constraints remain in force. Mandatory batches are capped at 20 even if an operator configures a larger daily budget.
- Empty claims also persist bounded housekeeping through `refresh_day`, avoiding the former case where a fully overdue queue remained projected forever. Invalid materials are filtered out of paused/transfer housekeeping IDs so deferral cannot be overwritten by another projected transition in the same claim.
- SQLite's legacy transaction mode requires a real outer transaction before the first SAVEPOINT. Claim uses explicit `BEGIN` before nested session insertion; initial pilot flow uses `BEGIN IMMEDIATE` before its SAVEPOINT after preparing the catalog. The focused tests verify that a subsequent exception rolls back the initial flow/session work instead of leaving a nested-savepoint commit behind.
- OFF exits through the existing path without reading the five policy tables. Projected catalogs and limited sense initialization are guarded by the ON preparation path. Existing snapshots without the pilot-only frozen-options marker keep their prior rendering path. A formal OFF query-capture test still passes.

Two boundaries remain explicit:

- Prepared plans contain `day` and `cohort`, but reservation currently checks their enrollment version rather than separately asserting those fields. The HTTP caller captures one `now` and passes the same prepared plan within that request; cohort changes through supported enrollment operations advance the version. This is not a presently reachable HTTP cross-day reuse, but callers must not retain/reuse the internal plan across dates. A future reusable-plan API should add explicit date/cohort checks.
- Non-selected catalog distractors are intentionally frozen from the preparation read. The writer revalidates selected source rows, not every row in the whole book. Thus this is a preparation-time catalog snapshot, not a claim that every distractor reflects the instant the writer lock was acquired. Re-reading the whole catalog under the lock would undo the performance benefit. Source-projection equivalence and edit visibility are covered separately by the performance module.

## Selector privacy and selection semantics

`scripts/select_vocabulary_pilot.py` uses only the standard library. Its production connection is `mode=ro` plus `query_only`, a restrictive SELECT/column authorizer, a 15-second SQL progress deadline and a 500,000-row bound. It does not import the application/config or models, and cannot write the database. SQL includes IDs and formal attempt metadata needed for selection, but no names, usernames, answers or credentials.

Eligibility requires active student status, recent formal first answers (at least 20 across at least three tasks in 28 days, activity in seven days), an active teacher assignment, no active review session and no previous enrollment row. Retries/remediation are excluded. The six-person default chooses three low-error and three high-error students using stable ratio/ID ordering. This intentionally spans the observed difficulty range; it is **not** randomized and does not estimate the average student effect.

Stdout contains aggregate counts/ranges only. The optional private manifest contains student IDs and group membership; `O_EXCL`, `O_NOFOLLOW` where available, symlink rejection and mode 0600 prevent ordinary overwrite/public-file accidents. Error output uses a fixed code or exception type, not raw exception text. Teacher willingness is explicitly reported as unverified; the selector performs no messages or external actions. Enrollment is a separate authorized operation and must recheck active/unfinished status under its own writer because selection is a read-time snapshot.

## Verification

The two selected-source negative controls and the following focused transaction/selector tests passed on both runtimes: **10 tests**, Python 3.13 **1.007s**, Python 3.10 **1.212s**. A preliminary invocation used the wrong unittest class name for the stale-plan test and failed discovery; the corrected command below is the reported result.

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest \
 tests.test_vocabulary_pilot_selection \
 tests.test_vocabulary_error_review_integration.ErrorReviewIntegrationTest.test_off_makes_no_new_table_queries_and_keeps_legacy_shape \
 tests.test_vocabulary_error_review_integration.ErrorReviewIntegrationTest.test_revalidation_rejects_changed_batch_atomically \
 tests.test_vocabulary_error_review_integration.ErrorReviewIntegrationTest.test_optional_final_reservation_rechecks_new_error_after_bulk_snapshot \
 tests.test_vocabulary_error_queue.VocabularyErrorPolicyCoreTest.test_stale_plan_rejected_and_capacity_reserved_across_sessions \
 tests.test_vocabulary_policy_performance.PolicyPerformanceTest.test_initial_pilot_flow_has_real_writer_before_savepoint_and_rolls_back \
 tests.test_vocabulary_policy_performance.PolicyPerformanceTest.test_claim_rechecks_selected_synonym_sense_after_preparation \
 tests.test_vocabulary_policy_performance.PolicyPerformanceTest.test_claim_rechecks_missing_word_book_mastery_goal_after_preparation -q
```

Repeat with `/private/tmp/studytracker-stage2-py310/bin/python` for production's Python version. After the third correction, all three new consistency regressions were independently rerun on both runtimes: **3 tests passed**, Python 3.13 **0.428s**, Python 3.10 **0.498s**. Use the last two tests in the command above plus `tests.test_vocabulary_policy_performance.PolicyPerformanceTest.test_policy_claim_quarantines_representative_reassigned_to_another_sense` to reproduce. The integration owner separately runs the combined release suite and performance checks.

The final AST reread of all top-level classes in `models.py` against baseline `513c732f` again found exactly 80 classes, only `VocabularyErrorQueue` and `VocabularyPolicyCheckpoint` changed, no added/deleted classes, all other 78 class ASTs identical. `git diff --check` passed. No unresolved blocking correctness issue remains in this review scope after the three corrections; the explicit boundaries above remain.

Migration tests and old-model AST evidence are in `core/validation.md`: they cover nonempty checkpoint tables, allocation/event references, duplicate intervals across sources, injected failure rollback and repeat application. Root still must confirm the actual production schema and deploy/migrate while disabled before activation. This review does not supersede those gates or the measured optional-path performance limitation: the six-user extreme partially blocked scenario around 1.144 seconds is accepted only as a stated pilot limitation, **not** a full strict C3 pass.
