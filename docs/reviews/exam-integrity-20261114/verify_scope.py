"""Read-only local release-scope audit against the supplied plan commit."""

import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = "ecc06f23"
UNCHANGED = [
    "app.py",
    "api/mock_exam_student.py",
    "api/mock_exam_review.py",
    "api/mock_exam_admin.py",
    "services/mock_exam_runtime.py",
    "services/mock_exam_writing.py",
    "services/mock_exam_review.py",
    "services/mock_exam_review_workflow.py",
    "static/js/practice_shell.js",
    "static/js/selection-highlight.js",
]
NEW_CLASSES = {"ExamIntegrityPolicy", "ExamIntegrityState", "ExamIntegrityEvent"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    checks = []
    for name in UNCHANGED:
        same = git("show", BASE + ":" + name) == (ROOT / name).read_bytes()
        checks.append({"check": "unchanged " + name, "ok": same})
    old = ast.parse(git("show", BASE + ":models.py"))
    new = ast.parse((ROOT / "models.py").read_text())
    added = [
        node.name
        for node in new.body
        if isinstance(node, ast.ClassDef) and node.name in NEW_CLASSES
    ]
    new.body = [
        node
        for node in new.body
        if not (isinstance(node, ast.ClassDef) and node.name in NEW_CLASSES)
    ]
    checks.append(
        {
            "check": "all old model AST unchanged; exactly three new classes",
            "ok": ast.dump(old) == ast.dump(new) and set(added) == NEW_CLASSES,
        }
    )
    changed = set(git("diff", "--name-only", BASE).decode().splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").decode().splitlines())
    product = sorted(name for name in changed if not name.startswith("docs/"))
    checks.append(
        {
            "check": "no mini-program or deployment configuration edits",
            "ok": not any(
                name.startswith("miniprogram/") or name == ".github/workflows/deploy.yml"
                for name in changed
            ),
        }
    )
    report = {
        "baseline": git("rev-parse", BASE).decode().strip(),
        "head": git("rev-parse", "HEAD").decode().strip(),
        "branch": git("branch", "--show-current").decode().strip(),
        "worktree": str(ROOT),
        "checks": checks,
        "files": [
            {"path": name, "sha256": hashlib.sha256((ROOT / name).read_bytes()).hexdigest()}
            for name in product
        ],
    }
    report["ok"] = all(check["ok"] for check in checks)
    print(json.dumps(report, indent=2))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
