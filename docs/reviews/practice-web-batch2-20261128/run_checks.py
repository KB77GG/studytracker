"""Repeat batch-two checks with a private database; preserve earlier release evidence."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "validation"
PYTHON_MODULES = [
    "tests.test_practice_center_batch1", "tests.test_reading_study",
    "tests.test_practice_navigation", "tests.test_practice_navigation_routes",
    "tests.test_practice_workspace_regression", "tests.test_practice_portal_catalog_grouping",
    "tests.test_practice_catalog", "tests.test_reading_practice_layout",
    "tests.test_teacher_practice_access", "tests.test_listening_intensive_catalog",
    "tests.test_question_type_catalog_ui_contract", "tests.test_exam_sprint_catalog",
    "tests.test_auth_entry_pages", "tests.test_practice_navigation_batch2",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["python", "node"])
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.mode == "python":
        commands = [[sys.executable, "docs/reviews/practice-web-batch1-20261126/run_tests.py", *PYTHON_MODULES]]
        label = "py" + str(sys.version_info.major) + str(sys.version_info.minor)
    else:
        reviews = ROOT / "docs/reviews"
        vocab = json.loads((reviews / "web-vocabulary-task-page-20261126/main-integration/node-commands.json").read_text())[0]["argv"][2:]
        batch1 = json.loads((reviews / "practice-web-batch1-20261126/validation/node-command.json").read_text())["argv"][2:]
        commands = [
            ["node", "--test", *dict.fromkeys(vocab + batch1)],
            ["node", "docs/reviews/practice-web-batch1-20261126/independent_exit_probe.js"],
        ]
        label = "node"
    results = []
    for index, argv in enumerate(commands, 1):
        log = OUT / f"{label}-{index}.log"
        started = time.monotonic()
        with log.open("w") as output:
            result = subprocess.run(argv, cwd=ROOT, env=os.environ.copy(), stdout=output, stderr=subprocess.STDOUT)
        row = {"argv": argv, "cwd": str(ROOT), "exit_code": result.returncode,
               "seconds": round(time.monotonic() - started, 3), "log": str(log.relative_to(HERE))}
        results.append(row)
        (OUT / f"{label}-commands.json").write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps(row), flush=True)
        print("\n".join(log.read_text().splitlines()[-8:]), flush=True)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
