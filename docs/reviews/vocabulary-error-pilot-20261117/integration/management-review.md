# Independent management, optional-selection and client review

Reviewed in `/private/tmp/studytracker-vocabulary-error-pilot-20261117`, branch `codex/vocabulary-error-pilot-20261117`, baseline `f414a126`. Initial review was read-only. The coordinator then explicitly delegated the two fixes below. No production access, enrollment, global-switch change, commit, push or release was performed by this review task.

## Management acceptance and fixes

`scripts/manage_vocabulary_error_pilot.py` defaults to SQLite `mode=ro`, `query_only=ON`, a read authorizer and a ten-second SQL progress deadline. It does not import app/config on preview. Selected identities are used internally and bound into the digest but are not exported. SQL parameters bind IDs; table names come from a fixed allowlist. Default recent-activity discovery is preview-only. Applying requires explicit IDs (at most 50), an explicit reviewed start and digest; expired starts are rejected. Under `BEGIN IMMEDIATE`, the script repeats preview/readiness checks and enrolls the entire selection in one transaction. A failing second enrollment rolls back the first. Active review sessions block activation. The new error/checkpoint/allocation/event tables remain empty: there is no historical mastery import. The script never writes the server's global switch.

The initial digest did not identify its database or the seven effective parameters. This allowed a digest from a structurally identical database, or from before a valid parameter change, to pass. The delegated fix adds:

- `database_identity`: a SHA-256 of canonical database path plus filesystem device/inode. Only the hash is exported. `PRAGMA database_list` is the sole additional permitted read pragma. A different target or replacing the same path with another inode requires a new preview.
- `policy_parameters`: the seven validated normalized public knobs. The preview reads only their keys from `.env` beside the database, using Config's first-occurrence/quote behavior; process environment overrides the file. It never copies unrelated settings or changes `os.environ`.
- Apply recomputes both under the writer lock, compares the full digest, configures its isolated Flask app with precisely that reviewed parameter set, and verifies agreement with core `policy_settings()`. Its global flag remains false even if `.env` contains `VOCABULARY_ERROR_REVIEW_ENABLED=1`.

Configuration binding describes the database-directory `.env` plus the management process environment. Operators must invoke the tool with the same relevant environment as the service. This is not an inspection of parameters already loaded into a running worker. The readonly fixture hashes the database file and tests denied writes; this is database-readonly evidence, not a claim that SQLite can never touch WAL/shared-memory metadata.

Validation: `/private/tmp/studytracker-stage2-py310/bin/python -m unittest tests.test_vocabulary_policy_management -q` passed **16 tests**. The five added tests cover matching core defaults/validation, `.env` precedence and private-key exclusion, cross-database/same-path replacement rejection, valid parameter changes, and apply's exact reviewed settings with the global flag still false. The original 11 tests also pass.

## Optional selection: N+1 removed, residual cost disclosed

Initial inspection found an avoidable per-candidate policy lookup: every legacy due ability checked enrollment and its error row, and unblocked candidates also checked today's allocations. If nearly all old candidates were active/paused in the new policy, finding ten optional questions could inspect the entire old pool and issue thousands of new policy SELECTs.

The delegated local fix loads enrollment once, all active/paused ability keys for the cohort once, and today's allocated ability keys once. Candidate filtering uses those sets. The original paged legacy order/eligibility and stop-after-capacity behavior are unchanged; there is no arbitrary truncation. `reserve_items` still rechecks the final at-most-daily-limit maintenance batch under the write lock, so a new error after the bulk snapshot causes a normal rollback/retry instead of slipping through.

A synthetic Python 3.10, in-memory SQLite probe made every legacy due ability teacher-paused and measured `_optional_candidates` only, excluding fixture construction, core plan, final reservation, HTTP, commit and production I/O:

| Old due abilities | Before SELECTs | After SELECTs | Before seconds | After seconds |
| --- | ---: | ---: | ---: | ---: |
| 22 | 48 | 7 | 0.0338 | 0.0149 |
| 500 | 1,010 | 13 | 0.2317 | 0.0574 |
| 2,400 | 4,840 | 43 | 0.9543 | 0.1118 |

These are single synthetic measurements, not production latency predictions. The reproducible invariant is the new policy-query count: an integration test grows a genuine old pool from 22 to 220 abilities, including active and paused exclusions, and confirms the added policy reads stay at **three**. The remaining SELECT growth is legacy page hydration. A second test injects a new mandatory error after selection and confirms the locked reservation rejects and rolls back the optional claim.

The optional path is still **not constant work**: the legacy SQL may scan/sort all due metadata, and materialization may visit all candidates when few are eligible. Default global OFF does not enter this path; un-enrolled students retain the old services. After enabling a pilot, a heavy optional request can still compete for CPU/SQLite resources with other students in the same process. The final batch limit bounds reservation work, not candidate discovery. Further optimization would require indexed policy exclusions in the legacy metadata query or a separately maintained optional eligibility index, with ordering/equivalence checks; this review does not silently change selection semantics.

Validation: `/private/tmp/studytracker-stage2-py310/bin/python -m unittest tests.test_vocabulary_error_review_integration -q` passed **24 tests** (the original 22 plus bulk-filter scale and final freshness guard). The local probe is `/private/tmp/policy_optional_review_probe.py`; it contains only synthetic fixtures and no production data.

## Four client-file diff review

Compared candidate `/private/tmp/studytracker-vocabulary-error-client-20261117/miniprogram` with the fixed release source `/Users/zhouxin/Desktop/studytracker-release/miniprogram` for home/review JS and WXML. The checked changes preserve the OFF display, use returned limits, default to mandatory, explicitly request maintenance, handle mode conflicts and expose a continuation button for empty mandatory materialization with a remaining count. Same-word ability item identities continue to use the existing renderer contract.

Two findings were sent to the coordinator, who owns the client files, and both are now fixed in the inspected candidate:

1. The empty branch of `continueReview` now updates `remainingDueCount`, clears stale session/question/skip fields, and has a regression. The prior code could retain a positive count after the final unusable candidate was deferred.
2. `fetchSession` now clears a previous `conflictingReviewMode` at the start of a fresh load, with a regression for a later normal error.

The coordinator also fixed recovery of a stored maintenance settlement to clear `returnTaskId`; this review checked that `applyPolicyPresentation` now does so. This reviewer inspected the fixes and their added client assertions but did not rerun the coordinator's reported 115 client tests or official two-page compilation. No upload/device verification is claimed. Home's optional entrance relies on the already-tested backend rule that an active optional batch remains available at zero remaining daily capacity until settled; its wording still says “go practice” rather than distinguishing “resume”, a minor presentation choice.

## Freeze and next step

Product/test changes from this follow-up are limited to `scripts/manage_vocabulary_error_pilot.py`, `tests/test_vocabulary_policy_management.py`, `services/vocabulary_error_review.py`, and `tests/test_vocabulary_error_review_integration.py`. All four pass Ruff check, Ruff format check and Black formatting; `git diff --check` is clean. They are ready for the coordinator's final combined Python 3.10/3.13 suite, manifest refresh and authorized release workflow. All work remains local and uncommitted at handoff.
