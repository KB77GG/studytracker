"""Read-only release proof against the newly fetched exam-sprint main."""

import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REVIEW_BASE = "9275b7a8a460f5105e4cd8f63e015e4b85f9d4d0"
MAIN = "3d8e7b57732045ecf30bc66037c61f0a04095bc1"
PROTECTED = (
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
    ".github/workflows/deploy.yml",
)
NEW_MODELS = {"ExamIntegrityPolicy", "ExamIntegrityState", "ExamIntegrityEvent"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    checks = [
        {
            "check": "merged pinned latest main into review",
            "ok": subprocess.call(["git", "merge-base", "--is-ancestor", MAIN, "HEAD"], cwd=ROOT)
            == 0,
        }
    ]
    for name in PROTECTED:
        checks.append(
            {
                "check": "unchanged " + name,
                "ok": git("show", MAIN + ":" + name) == (ROOT / name).read_bytes(),
            }
        )
    baseline = ast.parse(git("show", MAIN + ":models.py"))
    current = ast.parse((ROOT / "models.py").read_text())
    current.body = [
        node
        for node in current.body
        if not (isinstance(node, ast.ClassDef) and node.name in NEW_MODELS)
    ]
    checks.append(
        {"check": "legacy models unchanged", "ok": ast.dump(baseline) == ast.dump(current)}
    )
    incoming = git("diff", REVIEW_BASE + "..." + MAIN, "--name-only").decode().splitlines()
    incoming_product = [
        name
        for name in incoming
        if not name.startswith("docs/")
        and name
        not in {
            ".github/workflows/ci.yml",
            "api/__init__.py",
            "templates/reading/test_practice.html",
        }
    ]
    checks.append(
        {
            "check": "all incoming-main product files preserved byte-for-byte",
            "ok": all(
                git("show", MAIN + ":" + name) == (ROOT / name).read_bytes()
                for name in incoming_product
            ),
            "paths": incoming_product,
        }
    )
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    checks.append(
        {
            "check": "CI retains integrity and incoming synonym tests",
            "ok": all(
                name in ci
                for name in (
                    "tests.test_exam_integrity_service",
                    "tests/test_exam_guard.js",
                    "tests/test_classroom_synonym_client.js",
                    "tests.test_exam_sprint",
                )
            ),
        }
    )
    paths = git("diff", MAIN, "--name-only").decode().splitlines()
    product = sorted(name for name in paths if not name.startswith("docs/"))
    report = {
        "review_base": REVIEW_BASE,
        "merged_main": MAIN,
        "tested_head": git("rev-parse", "HEAD").decode().strip(),
        "branch": git("branch", "--show-current").decode().strip(),
        "worktree": str(ROOT),
        "checks": checks,
        "product_files_relative_to_merged_main": [
            {"path": name, "sha256": hashlib.sha256((ROOT / name).read_bytes()).hexdigest()}
            for name in product
        ],
        "ok": all(item["ok"] for item in checks),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
