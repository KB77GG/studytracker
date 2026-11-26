"""Record only the exact candidate already accepted on the production server."""

import fcntl
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.run_exam_sprint_weekly import ZONE, due_week, read_private_json, write_private_json

RUNTIME = Path("/Users/zhouxin/Library/Application Support/StudyTrackerExamSprint")
report = json.loads((Path(__file__).parent / "production-data-acceptance.json").read_text())
assert report["ok"] is True and report["snapshot_validation"]["ready"] == 140
with (RUNTIME / ".weekly.lock").open("a") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    raw = (RUNTIME / "instance/exam_sprint/current.json").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == report["snapshot_sha256"]
    now = datetime.now(ZONE)
    week = due_week(now)
    assert week == "2026-11-23"
    state_path = RUNTIME / "weekly-state.json"
    state = read_private_json(state_path)
    assert state["last_success_week"] <= week
    assert state.get("pending_publication_week") in (None, week)
    state.update(last_success_week=week, last_success_at=now.isoformat())
    state.pop("pending_publication_week", None)
    state.pop("pending_snapshot_sha256", None)
    state["manual_recovery"] = {
        "week": week,
        "at": now.isoformat(),
        "snapshot_sha256": digest,
        "prior_attempts_preserved": state.get("attempts", {}).get(week),
    }
    write_private_json(state_path, state)
    print(
        json.dumps(
            {
                "recovered_week": week,
                "prior_attempts_preserved": state.get("attempts", {}).get(week),
                "snapshot_sha256": digest,
            }
        )
    )
