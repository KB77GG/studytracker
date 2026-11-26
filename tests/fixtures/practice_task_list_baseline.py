"""Capture a real list response, or regenerate its pinned historical snapshot.

Only a private in-memory database and temporary uploads are used. The capture
process imports all application modules from --repo; no live database, .env,
server, network, user checkout, or product helper mock is used. See the adjacent
README for the historical generation command and the CI assertion.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import types
from contextlib import ExitStack, redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

BASELINE_COMMIT = "f81a5e4a4d81282eb67b994a4cfcc5574fb78747"
HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "practice_task_list_a02.json"
SNAPSHOT = HERE / "practice_task_list_f81a5e4.json"
SOURCE_PATHS = (
    "app.py",
    "models.py",
    "api/__init__.py",
    "services/task_date_gate.py",
    "services/question_type_practice.py",
    "services/question_type_assignments.py",
    "services/writing_assignments.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_app(repo: Path, uploads: Path, *, enabled: bool):
    # Executed only in a fresh process so target imports cannot reuse the
    # current checkout's already-imported models or services.
    sys.path.insert(0, str(repo))
    config = types.ModuleType("config")
    config.Config = type(
        "SyntheticListConfig",
        (),
        {
            "TESTING": True,
            "SECRET_KEY": "public-synthetic-list-test-secret-not-a-credential",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "UPLOAD_FOLDER": str(uploads),
            "PRACTICE_VOCABULARY_WEB_ENABLED": enabled,
        },
    )
    sys.modules["config"] = config
    spec = importlib.util.spec_from_file_location("_a02_list_app", repo / "app.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.app


def capture(repo: Path, fixture: Path, *, enabled: bool) -> dict:
    data = json.loads(fixture.read_text(encoding="utf-8"))
    os.chdir(repo)
    with tempfile.TemporaryDirectory(prefix="practice-list-capture-") as temp, ExitStack() as stack:
        for target in ("socket.socket.connect", "socket.getaddrinfo"):
            guard = stack.enter_context(
                patch(target, side_effect=AssertionError("Network forbidden"))
            )
            stack.callback(guard.assert_not_called)
        app = _load_app(repo, Path(temp) / "uploads", enabled=enabled)
        from models import StudentProfile, Task, User, db

        assert Path(sys.modules["models"].__file__).resolve() == repo / "models.py"

        stack.enter_context(
            patch(
                "services.task_date_gate._local_now",
                return_value=datetime.fromisoformat(data["clock"]),
            )
        )
        with app.app_context():
            assert db.engine.url.database == ":memory:"
            db.drop_all()
            db.create_all()
            for row in data["users"]:
                db.session.add(User(**row, password_hash="synthetic", is_active=True))
            db.session.add(StudentProfile(id=1, full_name=data["student_name"], user_id=1))
            for row in data["tasks"]:
                fields = {"student_name": data["student_name"], **row}
                if "question_snapshot" in fields:
                    fields["question_ids"] = json.dumps(
                        fields.pop("question_snapshot"), ensure_ascii=False
                    )
                for key in ("submitted_at", "cancelled_at"):
                    if fields.get(key):
                        fields[key] = datetime.fromisoformat(fields[key])
                db.session.add(Task(**fields))
            db.session.commit()
            client = app.test_client()
            with client.session_transaction() as session:
                session["practice_student_name"] = data["student_name"]
            response = client.get("/api/practice/tasks")
            assert response.status_code == 200, response.get_data(as_text=True)
            body = response.get_json()
            assert body["ok"] and body["verified"]
            db.session.remove()
            db.engine.dispose()
            return body


def regenerate(repo: Path, fixture: Path, output: Path) -> dict:
    commit = subprocess.check_output(
        ["git", "rev-parse", f"{BASELINE_COMMIT}^{{commit}}"], cwd=repo, text=True
    ).strip()
    root_entries = subprocess.check_output(
        ["git", "ls-tree", "--name-only", commit], cwd=repo, text=True
    ).splitlines()
    # Source-only git archive keeps historical code isolated without copying
    # production assets or touching any existing checkout. Root migrations are
    # included because app startup may import them against the private DB.
    archive_paths = [name for name in root_entries if name.endswith(".py")]
    archive_paths += ["api", "services", "schemas", "scripts"]
    archive = subprocess.check_output(
        ["git", "archive", "--format=tar", commit, *archive_paths], cwd=repo
    )
    with tempfile.TemporaryDirectory(prefix="practice-list-history-") as temp:
        baseline = Path(temp).resolve()
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            for member in stream.getmembers():
                if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                    raise ValueError(f"Unexpected archive member: {member.name}")
                destination = (baseline / member.name).resolve()
                if baseline not in destination.parents:
                    raise ValueError(f"Archive path outside temporary root: {member.name}")
            stream.extractall(baseline)  # noqa: S202 -- all members validated above, Python 3.10.
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "capture",
                "--repo",
                str(baseline),
                "--fixture",
                str(fixture),
                "--flag",
                "off",
            ],
            check=True,
            text=True,
            capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        snapshot = {
            "baseline_commit": commit,
            "fixture_sha256": sha256(fixture),
            "capture_script_sha256": sha256(Path(__file__).resolve()),
            "historical_source_sha256": {name: sha256(baseline / name) for name in SOURCE_PATHS},
            "generation_command": "python tests/fixtures/practice_task_list_baseline.py regenerate --repo .",
            "endpoint": "/api/practice/tasks",
            "feature_flag": False,
            "response": json.loads(result.stdout),
        }
    output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"snapshot": output.name, "baseline_commit": commit, "sha256": sha256(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "regenerate"))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--output", type=Path, default=SNAPSHOT)
    parser.add_argument("--flag", choices=("off", "on"), default="off")
    args = parser.parse_args()
    # App startup diagnostic output goes to stderr, never into the JSON contract.
    with redirect_stdout(sys.stderr):
        if args.action == "capture":
            result = capture(args.repo.resolve(), args.fixture.resolve(), enabled=args.flag == "on")
        else:
            result = regenerate(args.repo.resolve(), args.fixture.resolve(), args.output.resolve())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
