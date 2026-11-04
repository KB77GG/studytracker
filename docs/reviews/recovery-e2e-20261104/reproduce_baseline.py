"""Reproduce the shipped grace-period recovery bug using synthetic HTTP flows.

Exit 0 means the BUG WAS REPRODUCED, not that the product passed acceptance.
Only recovery.py from the pinned Git revision is loaded into memory. Candidate
source files are never overwritten; all data belongs to RecoverySandbox's
private temporary database. No production configuration or service is used.

Run from the repository root with its Python environment:
    python docs/reviews/recovery-e2e-20261104/reproduce_baseline.py \
        --output docs/reviews/recovery-e2e-20261104/baseline-grace-race.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASELINE = "f0e040416c8a68e66ba1202e558d4c1690bdc91b"
SOURCE_PATH = "services/task_planner_recovery.py"
MODULE_NAME = "services.task_planner_recovery"
sys.path.insert(0, str(ROOT))

from models import Task, db  # noqa: E402
from tests.recovery_e2e_support import RecoverySandbox  # noqa: E402


def reproduce():
    current_source = ROOT / SOURCE_PATH
    candidate_before = hashlib.sha256(current_source.read_bytes()).hexdigest()
    source = subprocess.run(
        ["git", "show", f"{BASELINE}:{SOURCE_PATH}"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    baseline_module = types.ModuleType(MODULE_NAME)
    baseline_module.__package__ = "services"
    baseline_module.__file__ = f"git:{BASELINE}:{SOURCE_PATH}"
    # The fixture is initialized first so its safe config and real app are in
    # place before replacing one service module. Route imports then resolve to
    # the pinned module; all other candidate code stays unchanged.
    sandbox = RecoverySandbox()
    package = sys.modules["services"]
    prior_module = sys.modules.get(MODULE_NAME)
    prior_attribute = getattr(package, "task_planner_recovery", None)
    try:
        sys.modules[MODULE_NAME] = baseline_module
        package.task_planner_recovery = baseline_module
        exec(compile(source, baseline_module.__file__, "exec"), baseline_module.__dict__)
        line, entries = sandbox.create_line()
        old_id = entries[0]["published_task_id"]
        sandbox.set_time("2026-11-02T02:59:00+08:00")
        inbox = sandbox.inbox()
        old_task = next(task for task in sandbox.tasks() if task["id"] == old_id)
        assert old_task["can_write"] is True
        assert len(inbox) == 1
        assert inbox[0]["source_date"] == "2026-11-01"
        assert inbox[0]["tasks"][0]["id"] == old_id
        preview, applied = sandbox.recover(line, "2026-11-01")
        assert preview["can_apply"] is True
        assert len(applied["created_task_ids"]) == 1
        makeup_id = applied["created_task_ids"][0]
        assert makeup_id != old_id
        sandbox.set_time("2026-11-02T02:59:30+08:00")
        submission = sandbox.submit(old_id)
        assert submission["synced"] is True
        assert submission["task"]["status"] == "done"
        assert submission["result"]["correct"] == 13
        sandbox.set_time("2026-11-03T03:05:00+08:00")
        report = sandbox.run_due()
        assert (report["eligible"], report["published"], report["blocked"], report["failed"]) == (
            1,
            0,
            1,
            0,
        )
        with sandbox.app.app_context():
            assert db.session.get(Task, old_id).status == "done"
            assert db.session.get(Task, makeup_id).status == "pending"
        assert not sandbox.outbound_attempts
        result = {
            "purpose": "Reproduce the shipped defect; exit 0 is not product acceptance",
            "bug_reproduced": True,
            "baseline": BASELINE,
            "baseline_recovery_sha256": hashlib.sha256(source).hexdigest(),
            "candidate_source_unchanged": True,
            "clock_before": "2026-11-02T02:59:00+08:00",
            "old_can_write": old_task["can_write"],
            "inbox_count": len(inbox),
            "preview_can_apply": preview["can_apply"],
            "makeup_task_ids": applied["created_task_ids"],
            "old_submit_http": 200,
            "old_submission_status": submission["task"]["status"],
            "old_submission_correct": submission["result"]["correct"],
            "run_due_clock": sandbox.now.isoformat(),
            "run_due": report,
            "entries": [
                {"id": entry["id"], "date": entry["target_date"], "status": entry["status"]}
                for entry in sandbox.entries(line)
            ],
        }
    finally:
        if prior_module is None:
            sys.modules.pop(MODULE_NAME, None)
        else:
            sys.modules[MODULE_NAME] = prior_module
        if prior_attribute is None:
            delattr(package, "task_planner_recovery")
        else:
            package.task_planner_recovery = prior_attribute
        sandbox.close()
        assert hashlib.sha256(current_source.read_bytes()).hexdigest() == candidate_before
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write non-sensitive JSON evidence here")
    args = parser.parse_args()
    result = reproduce()
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
