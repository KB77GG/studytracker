# Production entry verifier

Prepared locally only by the acceptance subtask; it has not accessed production or deployed anything. Root agent owns execution, interpretation and handoff. The source tree is `/private/tmp/studytracker-entry-backend-20261116`.

`verify_production_entry.py` is self-contained for SSH stdin and Python 3.10. It checks expected Git HEAD, both changed product SHA-256 values, tracked-clean status, systemd active state, exact gunicorn configuration, one actual worker, and ownership of the loopback port 5002 listener. Anonymous HTTP checks are GET `/login` → 200 and GET review-summary without credentials → 401. No login, capability token creation or private HTTP endpoint replay occurs.

For the two reported time windows, task IDs are selected privately from retained nginx logs and mapped via existing learning-flow rows. A window with zero/multiple matches is rejected. These are time-correlated records; no verified name mapping is claimed. IDs, names, tokens and session payloads never leave the runner.

The minimal Flask application imports only models and the reviewed vocabulary service dependencies, never application/config modules, `.env`, or speech/ML models. An import guard rejects app/config/torch/whisper/kokoro/tensorflow. The SQLite connection uses **URI mode=ro**, **PRAGMA query_only=ON**, and an authorizer that rejects writes, schema changes, ATTACH and PRAGMA mutation. It does not call `create_all`, claim, expire, ensure mastery, group initialization, answers or settlement. Review preflight and summary were inspected with their helper chains and are read-only. Only each case's preflight and summary are called once, for four measured calls total.

Each case uses a read transaction for a consistent short snapshot, compares indexed per-student counts across eight business tables, requires connection total_changes=0 and no dirty/new/deleted ORM entities, and rolls back/releases the connection. Concurrent production changes are not assessed; unchanged counts are within the runner's snapshot. Read locks can briefly defer SQLite writers, so run once after deployment and do not loop the diagnostic. Each call must finish under 5 seconds for overall ok=true; actual individual times are returned. This is not a proof that every client journey or arbitrary data scale is below timeout.

## Run

From the backend worktree, replace `RELEASE_SHA` with the exact deployed business SHA. The two expected product hashes are frozen in `production-entry-source-hashes.json`; root should verify they still match before execution.

```sh
ssh root@47.110.45.193 'cd /root/apps/studytracker && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - --expected-head RELEASE_SHA --context-sha CONTEXT_SHA --review-sha REVIEW_SHA' < docs/reviews/miniprogram-entry-20261116/verify_production_entry.py > docs/reviews/miniprogram-entry-20261116/production-entry-acceptance.json
```

No credentials or session identifiers should be substituted into this command. Exceptions are reduced to class names, without SQL parameters or response content. `ok=true` represents code/runtime/anonymous route checks and read-only production-data service replay; the JSON explicitly records `real_wechat_end_to_end=false`.

## Local safety verification

```sh
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/miniprogram-entry-20261116/test_verify_production_entry.py -v
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check docs/reviews/miniprogram-entry-20261116/verify_production_entry.py docs/reviews/miniprogram-entry-20261116/test_verify_production_entry.py
git diff --check
```

7/7 passed (0.133 seconds; `production-entry-verifier-tests.log`), Ruff and diff checks passed. The tests prove missing DB is not created, six write/attach/pragma attempts are denied, the real service runs against a synthetic read-only file DB with byte-identical before/after SHA, sensitive result fields are excluded, time-window selection is bounded and ambiguity fails closed, and the runner parses as Python 3.10 and rejects prohibited imports. No socket/network/process is started by these tests. Formatting used Black's single-process API; no approval or background process is pending.
