# Independent release verifier review

Worktree: `/private/tmp/studytracker-vocabulary-error-pilot-20261117`; model baseline `f414a126` (HEAD at review start). Scope: `verify_release.py`, its existing `verify_production_entry.py` dependency, unchanged old model definitions, and SQLite additive schema creation. No production commands, production connection, business data, configuration import, app import or model inference were used.

## Findings and disposition

- The initial `/proc/*/environ` check did not cover values loaded from `.env`, and did not trim whitespace as `_env_bool` does. Root corrected both, preserving process-environment precedence and checking that `.env` predates worker startup. This is a conservative configuration inference from trusted source and normal file timestamps, not an authenticated query of the live Flask config.
- The initial verifier recorded latency without enforcing the earlier five-second limit. Root restored the limit.
- An empty hash manifest initially satisfied `all(...)`. Root added a required set of ten backend files; the negative control below rejects an empty manifest.
- No additional blocking issue found in the revised verifier. All production SQL uses the previous URI `mode=ro`, `query_only=ON`, and SQLite-authorizer connection; ORM replay disables autoflush and rolls back. HTTP requests are anonymous GETs to login and an unauthorized summary route, with redirects disabled. System commands are read-only `git`, `systemctl show` and `ss`; `GIT_OPTIONAL_LOCKS=0` prevents optional index writes. The replay import guard rejects app/config and heavy inference imports before importing models/services. Output retains service state, aggregate counts, booleans, hashes and timings; student IDs, names, tokens, response bodies and exception messages are omitted.
- The previous dependency loads two sample students and names inside its read-only process to reuse the existing service, but the revised outer verifier exports neither identities nor pseudonymous per-student payloads/counts. The synthetic negative controls below check that distinction.

## Local validation

Existing dependency suite command (Python 3.13):

`/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/miniprogram-entry-20261116/test_verify_production_entry.py -q`

Result: **7 tests passed** in 0.174 seconds. It denies INSERT/UPDATE/DELETE/DROP/ATTACH and disabling query-only, refuses to create a missing database, checks byte-for-byte unchanged synthetic DB after real service replay, verifies prohibited-import guards and output filtering. Existing timestamp deprecation/resource warnings did not fail the suite.

The reproducible additional local harness below mocks every release-verifier production access, retaining the real read-only SQLite connection against a temporary fixture. It checks positive before/after runs, feature-switch precedence and whitespace, newer dotenv rejection, exception-message privacy, timing rejection, empty/wrong manifests, nonzero pilot tables, and old-schema mismatch. It separately compares every old model class AST and executes `metadata.create_all` over an already-created old schema while capturing emitted DDL.

Run from the worktree:

`/Users/zhouxin/Desktop/studytracker/.venv/bin/python -c 'from pathlib import Path; p=Path("docs/reviews/vocabulary-error-pilot-20261117/independent/release-verifier-review.md"); exec(p.read_text().split("```python\n",1)[1].split("\n```",1)[0])'`

The harness prints only aggregate test counts and source hashes. It passed on both Python 3.13 and Python 3.10 (`/private/tmp/studytracker-stage2-py310/bin/python` with the same `-c` argument): **12 mock scenarios**, **75 unchanged old model classes**, **5 newly created empty tables**, **no ALTER/DROP/business DML**, and an exactly unchanged old `sqlite_master` schema. App AST confirms `from config import Config` and `app.config.from_object(Config)` without executing either module. `git diff --check` also passed.

Reviewed verifier SHA-256: `2343bdebc324f216aa00608705f9946d6f5078d51c12ed34b37e47b408a80b60`. No blocking finding remains for this version's read-only production use. This result does not claim that production has already been checked, that live students can complete a session, or that pilot activation is authorized.

Core/product files remain frozen; this review changes only this Markdown file. No commit, push, deployment or activation was performed by this reviewer.

```python
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path.cwd()
HERE = ROOT / "docs/reviews/vocabulary-error-pilot-20261117"
source_path = HERE / "verify_release.py"
source = source_path.read_text()
ast.parse(source, feature_version=(3, 10))
runner = SimpleNamespace()
namespace = {"__name__": "independent_release_runner"}
exec(compile(source, str(source_path), "exec"), namespace)
runner.__dict__.update(namespace)

prior_path = ROOT / "docs/reviews/miniprogram-entry-20261116/verify_production_entry.py"
prior_namespace = {"__name__": "independent_prior_runner"}
exec(compile(prior_path.read_text(), str(prior_path), "exec"), prior_namespace)
prior = SimpleNamespace(**prior_namespace)
REQUIRED = {
    "models.py", "config.py", "services/vocabulary_error_queue.py",
    "services/vocabulary_error_review.py", "services/vocabulary_error_reporting.py",
    "api/vocabulary_error_reports.py", "api/vocab_review.py",
    "services/vocabulary_autonomous_review.py", "services/vocabulary_group_learning.py",
    "services/vocabulary_mastery.py",
}
PRIVATE = "synthetic-private-marker"
scenarios = 0

def run_case(*, after=False, dotenv="0", initial=None, changed_dotenv=False,
             slow=False, rows=0, bad_schema=False, manifest_mode="valid", error=False):
    global scenarios
    scenarios += 1
    with tempfile.TemporaryDirectory(prefix="release-verifier-review-") as directory:
        fixture = Path(directory)
        root = fixture / "root/apps/studytracker"
        root.mkdir(parents=True)
        for name in REQUIRED:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# synthetic product\n")
        (root / "config.py").write_text(
            "class Config:\n    VOCABULARY_ERROR_REVIEW_ENABLED = "
            "_env_bool('VOCABULARY_ERROR_REVIEW_ENABLED')\n"
        )
        (root / ".env").write_text(f"OTHER_SECRET={PRIVATE}\nVOCABULARY_ERROR_REVIEW_ENABLED={dotenv}\n")
        stamp = 200000 if changed_dotenv else 100000
        os.utime(root / ".env", (stamp, stamp))
        proc = fixture / "proc"
        (proc / "100/task/100").mkdir(parents=True)
        (proc / "200").mkdir()
        (proc / "100/task/100/children").write_text("200")
        (proc / "stat").write_text("btime 100000\n")
        (proc / "200/stat").write_text("200 (gunicorn) S " + "0 " * 18 + "100000\n")
        environment = f"PRIVATE={PRIVATE}\0".encode()
        if initial is not None:
            environment += b"VOCABULARY_ERROR_REVIEW_ENABLED=" + initial.encode() + b"\0"
        for pid in ("100", "200"):
            (proc / pid / "environ").write_bytes(environment)
        with sqlite3.connect(root / "app.db") as seed:
            seed.execute("CREATE TABLE existing_business(id INTEGER)")
            if after:
                for name in runner.TABLES:
                    seed.execute(f"CREATE TABLE {name}(id INTEGER)")
                if rows:
                    seed.execute("INSERT INTO vocabulary_review_policy_enrollment VALUES (1)")
            schema = seed.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
            ).fetchall()
        old_sha = prior.digest([row for row in schema if row[2] not in runner.TABLES])
        manifest = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in REQUIRED}
        if manifest_mode == "empty":
            manifest = {}
        elif manifest_mode == "wrong":
            manifest["models.py"] = "0" * 64
        manifest_path = root / "docs/reviews/vocabulary-error-pilot-20261117/backend-manifest.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(json.dumps(manifest))
        commands, http_calls = [], []

        def command(_root, *args):
            commands.append(args)
            if args == ("git", "rev-parse", "HEAD"):
                return "synthetic-head"
            assert args == ("git", "status", "--porcelain", "--untracked-files=no")
            return ""

        def anonymous_http(base):
            assert base in {"http://127.0.0.1:5002", "https://studytracker.xin"}
            http_calls.append(base)
            return [{"route": "/login", "status": 200, "ok": True}]

        def check_case(_app, *_case):
            if error:
                raise RuntimeError(PRIVATE)
            return {
                "ok": True, "query_only": True, "total_changes_zero": True,
                "case": PRIVATE, "student_id": 987654321,
                "selected_business_counts": {PRIVATE: 777},
                "calls": {"preflight": {"elapsed_ms": 5000 if slow else 3,
                                        "result": {"student_name": PRIVATE, "token": PRIVATE}}},
            }

        fake_previous = SimpleNamespace(
            command=command,
            service_info=lambda _root: {"ok": True, "systemd": {"MainPID": "100"}},
            anonymous_http=anonymous_http,
            readonly_connection=prior.readonly_connection,
            digest=prior.digest,
            select_cases=lambda *_args: [(PRIVATE, 987654321, 111), (PRIVATE, 987654322, 112)],
            make_readonly_app=lambda *_args: object(),
            check_case=check_case,
            PROHIBITED_IMPORTS=prior.PROHIBITED_IMPORTS,
        )

        def redirected_path(value):
            value = str(value)
            if value.startswith("/root/apps/studytracker"):
                return root / value[len("/root/apps/studytracker"):].lstrip("/")
            if value.startswith("/proc/"):
                return proc / value[len("/proc/"):]
            if value == "/var/log/nginx":
                return fixture / "fake-logs"
            raise AssertionError("unexpected_production_path")

        spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _module: None))
        argv = ["verify_release.py", "--expected-head", "synthetic-head"]
        if after:
            argv += ["--after", "--old-schema-sha", "bad" if bad_schema else old_sha]
        before = (root / "app.db").read_bytes()
        output = io.StringIO()
        with patch.dict(namespace, Path=redirected_path), \
             patch.object(importlib.util, "spec_from_file_location", return_value=spec), \
             patch.object(importlib.util, "module_from_spec", return_value=fake_previous), \
             patch.object(os, "sysconf", return_value=100), \
             patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
            exit_code = namespace["main"]()
        encoded = output.getvalue()
        assert PRIVATE not in encoded and "987654321" not in encoded
        result = json.loads(encoded)
        assert exit_code == (0 if result["ok"] else 1)
        assert before == (root / "app.db").read_bytes()
        assert len(commands) == len(http_calls) == 2
        return result

assert run_case()["ok"]
assert run_case(after=True)["ok"]
assert not run_case(initial=" true ")["ok"]
assert not run_case(dotenv="'true'")["ok"]
assert run_case(dotenv="true", initial=" false ")["ok"]
assert not run_case(changed_dotenv=True)["ok"]
assert not run_case(slow=True)["ok"]
assert run_case(error=True)["error_type"] == "RuntimeError"
assert not run_case(after=True, rows=1)["ok"]
assert not run_case(after=True, bad_schema=True)["ok"]
assert not run_case(after=True, manifest_mode="empty")["ok"]
assert not run_case(after=True, manifest_mode="wrong")["ok"]
assert not any(name in sys.modules for name in prior.PROHIBITED_IMPORTS)

# Compare existing models against the actual pre-change HEAD, ignoring line numbers.
old_source = subprocess.check_output(["git", "show", "f414a126:models.py"], text=True)
new_source = (ROOT / "models.py").read_text()
def class_map(text):
    return {node.name: ast.dump(node, include_attributes=False)
            for node in ast.parse(text).body if isinstance(node, ast.ClassDef)}
old_classes, new_classes = class_map(old_source), class_map(new_source)
assert all(new_classes.get(name) == tree for name, tree in old_classes.items())
assert set(new_classes) - set(old_classes) == {
    "VocabularyReviewPolicyEnrollment", "VocabularyErrorQueue", "VocabularyPolicyCheckpoint",
    "VocabularyPolicyAllocation", "VocabularyPolicyEvent",
}
app_ast = ast.parse((ROOT / "app.py").read_text())
assert any(isinstance(node, ast.ImportFrom) and node.module == "config"
           and any(item.name == "Config" for item in node.names) for node in app_ast.body)
assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
           and node.func.attr == "from_object" and any(isinstance(arg, ast.Name) and arg.id == "Config"
           for arg in node.args) for node in ast.walk(app_ast))

from sqlalchemy import create_engine, event
from models import db
engine = create_engine("sqlite://")
metadata = db.metadata
old_tables = [table for table in metadata.sorted_tables if table.name not in runner.TABLES]
metadata.create_all(engine, tables=old_tables)
schema_sql = "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
with engine.connect() as connection:
    old_schema = connection.exec_driver_sql(schema_sql).all()
statements = []
def capture(_connection, _cursor, statement, *_args):
    statements.append(statement)
event.listen(engine, "before_cursor_execute", capture)
metadata.create_all(engine)
event.remove(engine, "before_cursor_execute", capture)
with engine.connect() as connection:
    after_schema = connection.exec_driver_sql(schema_sql).all()
    assert [row for row in after_schema if row[2] not in runner.TABLES] == old_schema
    for name in runner.TABLES:
        assert connection.exec_driver_sql(f"SELECT COUNT(*) FROM {name}").scalar_one() == 0
new_tables = {row[1] for row in after_schema if row[0] == "table"} - {row[1] for row in old_schema if row[0] == "table"}
assert new_tables == set(runner.TABLES)
assert not any(sql.lstrip().upper().startswith(("ALTER ", "DROP ", "INSERT ", "UPDATE ", "DELETE ")) for sql in statements)
assert sum(sql.lstrip().upper().startswith("CREATE TABLE ") for sql in statements) == 5
engine.dispose()
assert not any(name in sys.modules for name in prior.PROHIBITED_IMPORTS)
print(json.dumps({"mock_scenarios_passed": scenarios, "unchanged_old_model_classes": len(old_classes),
                  "new_tables": len(new_tables), "no_alter_or_business_dml": True,
                  "verifier_sha256": hashlib.sha256(source.encode()).hexdigest()}, indent=2))
```
