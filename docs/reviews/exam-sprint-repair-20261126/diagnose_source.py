"""Read-only source diagnostics: public papers and authentication result codes only."""

import json
import sys
import traceback
from pathlib import Path
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from services.ninefen_session import NinefenSession
from services.ninefen_source import API_BASE, fetch_public_exam, fetch_public_hotlist

RUNTIME = Path("/Users/zhouxin/Library/Application Support/StudyTrackerExamSprint")
OUT = ROOT / "instance/exam_sprint/diagnostic"
OUT.mkdir(parents=True, exist_ok=True)
stage = "hotlist"
try:
    feed = fetch_public_hotlist()
    (OUT / "feed.json").write_text(json.dumps(feed, ensure_ascii=False))
    rows = [r for gs in feed["subjects"].values() for g in gs for r in g["items"]]
    print(json.dumps({"stage": stage, "ok": True, "rows": len(rows)}), flush=True)
    stage = "session_readonly_status"
    session = NinefenSession(RUNTIME / "instance/exam_sprint/private/session.json")
    req = Request(
        API_BASE + "/practice/v1/unit-status?unitIds=" + rows[0]["source_id"],
        headers={"token": session._token, "Accept": "application/json"},
        method="GET",
    )
    with session._opener.open(req, timeout=20) as response:
        result = json.loads(response.read(2 * 1024 * 1024))
        code = result.get("code")
        safe_code = code if type(code) is int or isinstance(code, str) and code.isdigit() else None
        print(
            json.dumps(
                {
                    "stage": stage,
                    "http_status": response.status,
                    "api_code": safe_code,
                    "has_data": isinstance(result.get("data"), dict),
                }
            ),
            flush=True,
        )
    if code not in (200, "200"):
        raise SystemExit(2)
    stage = "public_papers"
    exams = OUT / "exams"
    exams.mkdir(exist_ok=True)
    for i, row in enumerate(rows, 1):
        unit = row["source_id"]
        data = fetch_public_exam(unit)
        (exams / f"{unit}.json").write_text(json.dumps(data, ensure_ascii=False))
        if i % 20 == 0:
            print(json.dumps({"stage": stage, "fetched": i}), flush=True)
    print(json.dumps({"stage": stage, "ok": True, "fetched": len(rows)}))
except Exception as exc:
    print(
        json.dumps(
            {
                "stage": stage,
                "error_type": type(exc).__name__,
                "http_status": getattr(exc, "code", None),
                "frames": [
                    {"file": Path(f.filename).name, "function": f.name, "line": f.lineno}
                    for f in traceback.extract_tb(exc.__traceback__)
                ],
            }
        ),
        flush=True,
    )
    raise SystemExit(1) from None
