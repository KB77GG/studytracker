"""Cache only current public ranking/papers; never read source sessions or submit."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from services.ninefen_source import (
    HOTLIST_PATH,
    _fetch_json,
    fetch_public_exam,
    parse_public_hotlist,
)

OUT = ROOT / "instance/exam_sprint/diagnostic"
OUT.mkdir(parents=True, exist_ok=True)
raw = _fetch_json(HOTLIST_PATH, 20)
feed = parse_public_hotlist(raw)
(OUT / "albums.json").write_text(json.dumps(raw, ensure_ascii=False))
(OUT / "feed.json").write_text(json.dumps(feed, ensure_ascii=False))
folder = OUT / "exams"
folder.mkdir(exist_ok=True)
rows = [r for gs in feed["subjects"].values() for g in gs for r in g["items"]]
for i, r in enumerate(rows, 1):
    unit = r["source_id"]
    data = fetch_public_exam(unit)
    (folder / f"{unit}.json").write_text(json.dumps(data, ensure_ascii=False))
    if i % 20 == 0:
        print(json.dumps({"public_papers": i}), flush=True)
print(json.dumps({"ok": True, "total": len(rows), "fetched_at": feed["fetched_at"]}))
