#!/usr/bin/env python3
"""Apply reviewed reading corrections only, without rebuilding source data.

The builder independently preserves pre-A on future imports. The checked-in
manifest also supplies those introductions to existing published/legacy payloads.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main():
    from services.cambridge_content_corrections import apply_content_corrections

    manifest = json.loads((ROOT / "data/cambridge_content_corrections/reading.json").read_text())
    changed = []
    for test_id in manifest["tests"]:
        path = ROOT / "static/reading_tests" / f"{test_id}.json"
        before = json.loads(path.read_text())
        payload = json.loads(path.read_text())
        apply_content_corrections(payload, subject="reading")
        if payload != before:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            changed.append(test_id)
    print(json.dumps({"changed": changed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
