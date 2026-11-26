"""Reproduce merged vocabulary / sprint regressions with log and argv evidence."""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
OLD = ROOT / "docs/reviews/web-vocabulary-task-page-20261126/validation/review-fix-commands.json"
base = json.loads(OLD.read_text())["review-fix-full-py313"]["argv"][3:-1]
extra = """tests.test_exam_sprint_catalog tests.test_exam_sprint_assignments tests.test_exam_sprint_student tests.test_exam_sprint_papers tests.test_mock_sprint_creation tests.test_miniprogram_web_practice tests.test_miniprogram_teacher_jijing tests.test_miniprogram_parent_report tests.test_parent_web_practice_report tests.test_mock_exam_runtime tests.test_mock_exam_runtime_routes tests.test_mock_exam_student_review tests.test_mock_exam_template_isolation tests.test_exam_sprint_routes tests.test_ninefen_session tests.test_ninefen_auth tests.test_exam_sprint_weekly tests.test_exam_sprint_import tests.test_exam_sprint_publish tests.test_exam_integrity_service tests.test_exam_integrity_routes tests.test_exam_integrity_adversarial tests.test_exam_integrity_e2e""".split()
modules = list(dict.fromkeys(base + extra))
node_files = """tests/test_practice_vocabulary_core.js tests/test_practice_vocabulary_timing.js tests/test_practice_task_lists.js tests/test_practice_shell.js tests/test_vocabulary_feedback.js tests/test_exam_sprint_assignment_picker.js tests/test_mock_sprint_picker.js tests/test_listening_practice_client.js tests/test_mock_review_paper.js""".split()
parser = argparse.ArgumentParser()
parser.add_argument("mode", choices=["py313", "py310", "py310-stable", "py310-project", "node"])
args = parser.parse_args()
if args.mode == "node":
    commands = [["node", "--test", *node_files]]
else:
    python = "/Users/zhouxin/Desktop/studytracker/.venv/bin/python" if args.mode == "py313" else "/private/tmp/studytracker-web-vocab-py310/bin/python"
    if args.mode == "py310-stable":
        python = str(Path(python).resolve())
    elif args.mode == "py310-project":
        python = "/Users/zhouxin/Desktop/studytracker/tmp/web-vocab-py310-20261126/bin/python"
    # Existing pre-3.11 datetime.UTC test needs a process-only alias in this
    # previously reviewed runner. Product code is not altered by that alias.
    prefix = [python, "-m", "unittest"] if args.mode == "py313" else [python, str(ROOT / "docs/reviews/web-vocabulary-task-page-20261126/run_compat_tests.py")]
    commands = [[*prefix, *modules, *(["-v"] if args.mode == "py313" else [])], [python, "-m", "pytest", "tests/test_task_date_gate.py", "-q"]]
environment = os.environ.copy()
if args.mode == "py310-stable":
    # Execute the real, non-temporary 3.10 installation. Reuse its matching
    # venv dependencies without changing sys.executable or the stable-path guard.
    environment["PYTHONPATH"] = "/private/tmp/studytracker-web-vocab-py310/lib/python3.10/site-packages"
results = []
for index, command in enumerate(commands):
    log = OUT / f"{args.mode}-{index + 1}.log"
    start = time.monotonic()
    with log.open("w") as output:
        result = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, env=environment)
    item = {"argv": command, "cwd": str(ROOT), "returncode": result.returncode, "seconds": round(time.monotonic() - start, 3), "log": log.name, "env_overrides": {"PYTHONPATH": environment["PYTHONPATH"]} if args.mode == "py310-stable" else {}}
    results.append(item)
    (OUT / f"{args.mode}-commands.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(item), flush=True)
    print("\n".join(log.read_text().splitlines()[-12:]), flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
