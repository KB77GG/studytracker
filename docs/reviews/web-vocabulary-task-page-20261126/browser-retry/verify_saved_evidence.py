"""Verify saved synthetic-browser evidence without starting services or writing DBs."""

import hashlib
import json
from datetime import datetime
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def read(name):
    return json.loads((HERE / name).read_text())


def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


events = [json.loads(line) for line in (HERE / "audit-5114.jsonl").read_text().splitlines()]
clock = read("screenshots/timer-wall-clock.json")
away = (instant(clock["returnedUtc"]) - instant(clock["leftUtc"])).total_seconds()
assert away >= 600
timer = read("timer-settlement-stats.json")["tasks"][0]
refreshed = read("timer-after-refresh-stats.json")["tasks"][0]
assert timer["settlement_count"] == refreshed["settlement_count"] == 1
assert timer["db_task_actual_seconds"] == refreshed["db_task_actual_seconds"] == 95
settles = [e for e in events if e["event"] == "post_committed_response"
           and e.get("task_id") == 1 and e["path"].endswith("/settle") and e["status_code"] == 200]
assert len(settles) == 1 and settles[0]["request_duration_seconds"] == 95
first_sync = next(e for e in events if e["event"] == "post_committed_response"
                  and e.get("task_id") == 1 and e["path"].endswith("/sync"))
wall = (instant(settles[0]["time_utc"]) - instant(first_sync["time_utc"])).total_seconds()
assert 0 < timer["db_task_actual_seconds"] <= wall - away + 3

drop = read("transport-drop-browser-stats.json")
assert drop["after_refresh"]["attempt_record_count"] == 1
assert drop["after_refresh"]["attempt_record_ids"] == drop["drop"]["attempt_record_ids"]
attempt = drop["drop"]["attempt_id"]
assert len([e for e in events if e["event"] == "transport_socket_closed"
            and e.get("attempt_id") == attempt]) == 1
replies = [e for e in events if e["event"] == "post_committed_response"
           and e.get("attempt_id") == attempt]
assert len(replies) == 2 and all(e["attempt_record_count"] == 1 for e in replies)
offline = read("offline-after-save-stats.json")["tasks"][0]
answers = [r for r in offline["records"] if r["student_answer"] == "focus"]
assert len(answers) == 1 and answers[0]["is_correct"]
assert "net::ERR_INTERNET_DISCONNECTED" in (HERE / "screenshots/chrome-offline-confirmed-input-failure.ax.txt").read_text()
assert "Value: focus" in (HERE / "screenshots/chrome-offline-draft-recovered.ax.txt").read_text()

manifest = json.loads((HERE.parent / "main-integration/manifest.json").read_text())
for item in manifest["files"]:
    assert hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"], item["path"]

print(json.dumps({"ok": True, "away_seconds": away, "wall_seconds": round(wall, 3),
                  "active_seconds": 95, "settlements_after_refresh": 1,
                  "dropped_attempt_records": 1, "offline_focus_records": 1,
                  "unchanged_product_files": len(manifest["files"]),
                  "scope": "saved evidence verification; does not replace native UI observations"}, indent=2))
