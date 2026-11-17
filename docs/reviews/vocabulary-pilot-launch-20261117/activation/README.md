# Private first-pilot enrollment tool

Worktree: `/private/tmp/studytracker-vocabulary-error-pilot-20261117`, branch
`codex/vocabulary-error-pilot-20261117`. This child changed no production state,
environment file or service, and did not commit or push. Root owns canonical
handoff, deployment and the final controlled activation.

`scripts/activate_vocabulary_pilot.py` accepts a private regular, single-link,
current-owner mode-0600 JSON file containing `version: 1` and `student_ids`
(four or six unique positive integer IDs). Existing manifest metadata is retained.
The selected production pilot is four; six is supported without changing policy.
Do not put the private manifest or IDs in repository evidence.

```sh
venv/bin/python scripts/activate_vocabulary_pilot.py --database DATABASE --selection PRIVATE_JSON
venv/bin/python scripts/activate_vocabulary_pilot.py --database DATABASE --selection PRIVATE_JSON --apply
```

The default preview imports only standard-library helpers, opens SQLite in
read-only/query-only mode, and does not alter the database, manifest or lock file.
It checks active student roles, no selected legacy active review, `sources_v1`
schema/index readiness, all five policy tables empty, the approved seven effective
parameters (20/4/10, success gap 2, failure 3, pause 7, overdue 7), and global OFF.
Effective settings use database-directory `.env` followed by CLI-process
environment overrides, matching the existing loader. This does not inspect another
process's environment; root's live verifier and controlled service stop cover that.

Apply first persists a private pending intent binding exact selection, database
identity, parameters, current UTC cohort and the existing manager's digest. Its
ten-minute validity is rechecked under `BEGIN IMMEDIATE` using the manager's new
optional `locked_check` hook. All selected enrollments commit together; no historical
errors or mandatory records are imported. A sibling 0600 `.lock` prevents concurrent
manifest writers and survives atomic manifest replacement.

After commit the tool reads back the entire enrollment table, requiring exactly the
manifest cohort with no other enrollment or policy records, then marks the private
intent enrolled. If final manifest persistence fails, retry recognizes that exact
cohort and performs verification without reenrollment, even after ten minutes.
An uncommitted pending intent expires after ten minutes. Changed selection,
database, parameters, cohort, nonempty policy state or mismatched enrollment fails.
The tool is intentionally for first activation, not for modifying a pilot after use.
Stdout and handled failures expose aggregate facts and fixed error codes only.

Because global OFF keeps legacy behavior, root will stop the service before apply,
change only the feature flag afterward, and start in `finally`; the tool itself does
not edit `.env` or restart anything. This closes the enrollment-to-flag window.

Validation is separate from the earlier 396-test product suite. The two commands in
`validation.json` run the new 15 activation tests plus the existing 16 manager tests
on Python 3.10 and 3.13 (31 per version). Tests cover read-only/stdlib preview,
four/six enrollment, privacy and permissions, all seven parameters, schema checks,
whole-database outsiders, writer-lock races, legacy active races, rollback of the
second student, post-commit manifest failure/retry, cross-database intent rejection,
cohort/selection changes and expiration. Logs, exact commands and three-file hashes
are in this directory. Ruff and Black passed for the three files. Teacher agent's
independent 15-test dual-version replay also passed with no blocking finding.

Files to include in CI/manifest: `scripts/activate_vocabulary_pilot.py`,
`scripts/manage_vocabulary_error_pilot.py`, `tests/test_vocabulary_pilot_activation.py`.
New CI module: `tests.test_vocabulary_pilot_activation` (15 tests).
