"""Verify batch-two navigation scope against HEAD without importing the app."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = Path(__file__).resolve().parent
ALLOWED_PRODUCT_FILES = {
    "static/js/practice_shell.js",
    "templates/auth/_entrance_shell.html",
    "templates/base.html",
    "templates/listening/index.html",
    "templates/listening/jijing_index.html",
    "templates/listening/test_index.html",
    "templates/practice/_workspace_header.html",
    "templates/practice/_workspace_styles.html",
    "templates/practice/exam_sprint.html",
    "templates/practice/index_content.html",
    "templates/question_type_practice/student_index.html",
    "templates/reading/jijing_index.html",
    "templates/reading/test_index.html",
    "templates/writing/index.html",
    "templates/writing/topics.html",
}
EXPLICIT_UNCHANGED_FILES = (
    "app.py",
    "models.py",
    "templates/listening/test_practice.html",
    "templates/listening/player.html",
    "templates/reading/test_practice.html",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def protected_product(path: str) -> bool:
    return (
        path in EXPLICIT_UNCHANGED_FILES
        or path.startswith(("api/", "services/"))
        or (
            path.endswith(".js")
            and path.startswith(("static/", "miniprogram/"))
            and path != "static/js/practice_shell.js"
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="HEAD", help="Git baseline; defaults to current HEAD")
    args = parser.parse_args()
    commands: list[dict] = []
    checks: list[dict] = []

    def run(argv: list[str], *, record_output: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, check=False)
        command = {"argv": argv, "cwd": str(ROOT), "exit_code": result.returncode}
        if record_output:
            command["stdout"] = result.stdout.decode("utf-8", errors="replace")
            command["stderr"] = result.stderr.decode("utf-8", errors="replace")
        else:
            command["stdout_sha256"] = sha256(result.stdout)
            command["stdout_bytes"] = len(result.stdout)
        commands.append(command)
        return result

    def git_text(*argv: str) -> str:
        result = run(
            ["git", *argv], record_output=not (argv[0] == "ls-files" and "--others" not in argv)
        )
        if result.returncode:
            raise RuntimeError(f"Git command failed: {argv!r}")
        return result.stdout.decode("utf-8")

    baseline = git_text("rev-parse", "--verify", f"{args.baseline}^{{commit}}").strip()
    branch = git_text("branch", "--show-current").strip()
    tracked_changes = sorted(
        filter(None, git_text("diff", "--name-only", "-z", baseline, "--").split("\0"))
    )
    untracked = sorted(
        filter(None, git_text("ls-files", "--others", "--exclude-standard", "-z").split("\0"))
    )
    changed = sorted(set(tracked_changes + untracked))
    tracked = sorted(filter(None, git_text("ls-files", "-z").split("\0")))

    def check(name: str, passed: bool, **evidence) -> None:
        checks.append({"name": name, "passed": bool(passed), **evidence})

    protected_changes = [path for path in changed if protected_product(path)]
    check(
        "protected_products_have_no_git_changes",
        not protected_changes,
        changed_paths=protected_changes,
        protected_tracked_count=sum(protected_product(path) for path in tracked),
        rule="app.py/models.py/api/**/services/**, listening/player and listening/reading test templates, all static and miniprogram JS except practice_shell.js",
    )
    product_changes = [
        path
        for path in changed
        if path.startswith(("static/", "templates/", "api/", "services/", "miniprogram/"))
        or path in {"app.py", "models.py", "config.py"}
    ]
    unexpected_products = sorted(set(product_changes) - ALLOWED_PRODUCT_FILES)
    check(
        "product_scope_allowlist",
        not unexpected_products,
        changed_paths=product_changes,
        unexpected_paths=unexpected_products,
    )

    def baseline_bytes(path: str) -> bytes:
        result = run(["git", "show", f"{baseline}:{path}"], record_output=False)
        if result.returncode:
            raise RuntimeError(f"Cannot read baseline file: {path}")
        return result.stdout

    def compare(name: str, path: str, extract=lambda value: value) -> None:
        try:
            before = extract(baseline_bytes(path))
            after = extract((ROOT / path).read_bytes())
            check(
                name,
                before == after,
                path=path,
                baseline_sha256=sha256(before),
                current_sha256=sha256(after),
                baseline_bytes=len(before),
                current_bytes=len(after),
            )
        except (OSError, ValueError, RuntimeError) as error:
            check(name, False, path=path, error=str(error))

    for path in EXPLICIT_UNCHANGED_FILES:
        compare("byte_identical:" + path, path)

    compare(
        "shell_init_and_all_save_exit_timer_code_byte_identical",
        "static/js/practice_shell.js",
        lambda data: data[data.index(b"  function init(options = {}, win = window) {") :],
    )

    def catalog_macro(data: bytes) -> bytes:
        start = data.index(b"{% macro render_intensive_catalog(")
        end = data.index(b"{% endmacro %}", start) + len(b"{% endmacro %}")
        return data[start:end]

    def progress_and_management(data: bytes) -> bytes:
        start = data.index(b"function refreshExerciseProgress(studentName) {")
        end = data.index(b"</script>", start)
        return data[start:end]

    compare(
        "intensive_catalog_macro_byte_identical", "templates/listening/index.html", catalog_macro
    )
    compare(
        "intensive_progress_card_and_management_script_byte_identical",
        "templates/listening/index.html",
        progress_and_management,
    )

    environment = Environment()
    templates = [
        path
        for path in changed
        if path.startswith("templates/") and path.endswith(".html") and (ROOT / path).is_file()
    ]
    for path in templates:
        try:
            environment.parse((ROOT / path).read_text(), name=path)
            check("jinja_parse:" + path, True)
        except Exception as error:
            check("jinja_parse:" + path, False, error=str(error))

    javascript = [path for path in changed if path.endswith(".js") and (ROOT / path).is_file()]
    for path in javascript:
        result = run(["node", "--check", path])
        check("node_check:" + path, result.returncode == 0)

    # Raw logs, historical patches and generated evidence are not source checks.
    source_suffixes = {".py", ".js", ".html", ".css", ".yml", ".yaml", ".md"}
    diff_paths = [
        path
        for path in changed
        if Path(path).suffix in source_suffixes and "/validation/" not in path
    ]
    tracked_diff_paths = [path for path in diff_paths if path in tracked_changes]
    if tracked_diff_paths:
        result = run(["git", "diff", "--check", baseline, "--", *tracked_diff_paths])
        check("git_diff_check_tracked_sources", result.returncode == 0, paths=tracked_diff_paths)
    for path in diff_paths:
        if path not in untracked or not (ROOT / path).is_file():
            continue
        result = run(["git", "diff", "--no-index", "--check", "--", "/dev/null", path])
        # --no-index implies --exit-code: 1 with no diagnostics is a clean new file.
        check(
            "git_diff_check_new_source:" + path,
            result.returncode in (0, 1) and not result.stdout and not result.stderr,
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - Python 3.10 compatibility
        "command": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        "worktree": str(ROOT),
        "branch": branch,
        "baseline_ref": args.baseline,
        "baseline_commit": baseline,
        "python": sys.version,
        "tracked_changes": tracked_changes,
        "untracked_paths": untracked,
        "checks": checks,
        "commands": commands,
        "summary": {
            "passed": sum(row["passed"] for row in checks),
            "failed": sum(not row["passed"] for row in checks),
            "jinja_templates": len(templates),
            "standalone_js": len(javascript),
        },
        "limits": [
            "Static scope and syntax verification only; no application import, browser execution, database access, network or production requests.",
            "Jinja parse does not resolve template context, render pages or validate inline JavaScript; browser/HTTP regressions are separate evidence.",
            "Git diff covers tracked files against the recorded baseline plus nonignored untracked filenames; ignored data/assets and historical runtime state are outside this check.",
            "No commit, push, deployment or mini-program publication is performed.",
        ],
    }
    (REPORT_DIR / "scope-check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    for row in checks:
        if not row["passed"]:
            print("FAIL " + json.dumps(row, ensure_ascii=False))
    return int(any(not row["passed"] for row in checks))


if __name__ == "__main__":
    raise SystemExit(main())
