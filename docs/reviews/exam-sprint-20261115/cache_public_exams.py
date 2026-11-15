"""Cache the observed public top-20 papers for import; no account is accessed."""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from services.ninefen_source import fetch_public_exam  # noqa: E402


def main():
    source = Path("/private/tmp/ninefen-public-assets-20261115")
    target = ROOT / "instance/exam_sprint/exams"
    target.mkdir(parents=True, exist_ok=True)
    feed = json.loads((ROOT / "data/exam_sprint/latest.json").read_text())
    cached = {
        json.loads(p.read_text()).get("data", {}).get("id"): p
        for p in source.glob("*.json")
        if p.stem.isdecimal() or p.name in ("reading-sample.json", "listening-sample.json")
    }
    rows = [r for groups in feed["subjects"].values() for g in groups for r in g["items"]]
    for index, row in enumerate(rows, 1):
        unit = row["source_id"]
        path = target / f"{unit}.json"
        if path.exists():
            continue
        payload = (
            json.loads(cached[unit].read_text()) if unit in cached else fetch_public_exam(unit)
        )
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"cached": index, "total": len(rows), "unit_id": unit}), flush=True)
        if unit not in cached:
            time.sleep(0.3)


if __name__ == "__main__":
    main()
