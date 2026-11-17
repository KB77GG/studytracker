# Read-only HTTP baseline and follow-up

`audit_http.py` is a standalone standard-library log reader for baseline, D3 and D14 checks. It imports no application/config/models, performs no HTTP calls, and never opens a database or sends messages. This task did not execute it on production. Root owns production execution and the four-person pilot; its output covers **all requests to the four routes**, not identifiable pilot students.

Run from the deployed repository using explicit UTC instants. The example is a complete preceding calendar day; replace bounds with the actual activation-aligned baseline and follow-up windows:

```sh
python3 docs/reviews/vocabulary-pilot-launch-20261117/audit_http.py \
  --since 2026-11-16T00:00:00Z --until 2026-11-17T00:00:00Z
```

The interval includes `since` and excludes `until`. Days are UTC after conversion from each log entry's timezone; an incomplete first/last day remains an incomplete day. An explicit offset of `+00:00` is also accepted. Naive or non-UTC CLI bounds are rejected. `--log-dir` defaults to `/var/log/nginx`; override it for synthetic/local tests. Capture stdout only if `ok=true` and the process exits zero. Failures expose only the exception class, never the input path, raw line or partial counts.

Each day contains exactly four categories: task queue, task preflight, review summary, and review today. Matching is limited to the exact GET route shapes; session IDs, task IDs, URI/query values, IPs, referers, agents and student identities never leave the parser. Per category it emits requests, 499 count, 5xx count, and available `request_time` count/missing count plus exact nearest-rank p50/p95/p99/max in seconds. A 499 indicates the client closed the request, not proof of any one underlying cause. Nginx durations, when logged, are total request times rather than isolated backend computation times.

The parser accepts standard common/combined lines and JSON with explicit timestamp/request/status fields. Timing requires an explicit JSON `request_time` or an unquoted `request_time=...` tail token. It ignores labels embedded in user-agent/referer strings and does not guess an unlabelled numeric column to be a duration. If the deployed format lacks timing, counts remain useful and timing quantiles are `null` with coverage zero; this does **not** indicate zero latency. No Nginx configuration change is part of this tool.

Log discovery uses one `access*.log*` glob, de-duplicates resolved logical rotation names and physical device/inode aliases, and prefers an uncompressed rotation if both it and its `.gz` form exist. Gzip magic is detected so an alias without `.gz` still works. Distinct unrelated copied files are not content-deduplicated: identical log lines can represent real repeated requests, so collapsing them would corrupt counts. Run against the normal retained rotation set rather than an arbitrary folder of copies. Opened inode mismatches, corrupt gzip, oversized lines, missing logs and exceeding one million timing samples fail closed; ordinary current-log appends may produce a point-in-time prefix. Retention limits and lines not recognized by the supported format mean zero rows cannot establish that no request occurred outside the observable log set.

Local verification in `/private/tmp/studytracker-vocabulary-error-pilot-20261117`, branch `codex/vocabulary-error-pilot-20261117`, baseline `513c732f`:

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest discover \
  -s docs/reviews/vocabulary-pilot-launch-20261117 -p test_audit_http.py -q
/private/tmp/studytracker-stage2-py310/bin/python -m unittest discover \
  -s docs/reviews/vocabulary-pilot-launch-20261117 -p test_audit_http.py -q
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check \
  docs/reviews/vocabulary-pilot-launch-20261117/audit_http.py \
  docs/reviews/vocabulary-pilot-launch-20261117/test_audit_http.py
```

Both runtimes passed **9 synthetic tests**, each 0.007s. Coverage includes UTC boundaries, all route/status classes, gzip/plain/soft/hard aliases, quoted timing injection, no timing inference from bytes or unlabelled columns, structured JSON, invalid bounds, corrupt-file privacy, size/rotation limits, explicit read-only open modes, unchanged source bytes and standard-library-only imports. Black and Ruff passed; Ruff's Python 3.11 `datetime.UTC` recommendation is intentionally suppressed for production Python 3.10 compatibility.

These are new local report scripts/tests only, not a service change. No production run, commit, push, deployment or student data mutation was performed by this subtask. Root will include them in the consolidated handoff and follow-up instructions; the shared tree's other concurrent changes remain owned by their respective agents.
