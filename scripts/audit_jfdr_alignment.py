#!/usr/bin/env python3
"""Per-segment confidence audit for jfdr6 forced alignment.

For each aligned segment, check whether its leading content words actually
appear in the whisper word stream within a window around the segment's
assigned start time. Low hit-rate => the segment drifted (aligned to the
wrong audio position). Prints a per-section summary + the specific drifted
segments so we can decide fixes precisely.

Usage:
    .venv/bin/python scripts/audit_jfdr_alignment.py [--only jfdr6_test1_s1] [--model small]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALIGNED_DIR = PROJECT_ROOT / "data" / "jfdr6" / "aligned"
CACHE_DIR = PROJECT_ROOT / "data" / "jfdr6" / "whisper_cache"

STOP = {"the", "a", "an", "to", "of", "and", "is", "it", "i", "you", "in", "for",
        "s", "m", "re", "ll", "t", "that", "this", "on", "at", "so", "we", "he",
        "she", "they", "well", "oh", "ok", "okay", "yes", "no", "um", "uh"}


def norm(text: str) -> list[str]:
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return [w for w in text.split() if w]


def content_words(text: str, n: int = 4) -> list[str]:
    out = [w for w in norm(text) if w not in STOP and len(w) > 2]
    return out[:n]


def load_words(model: str, exercise_id: str) -> list[tuple[float, str]]:
    cache = CACHE_DIR / f"{exercise_id}.{model}.json"
    c = json.loads(cache.read_text(encoding="utf-8"))
    words = []
    for seg in c["segments"]:
        for w in seg.get("words", []):
            words.append((float(w["start"]), norm(w["word"])[0] if norm(w["word"]) else ""))
    return words


def audit(exercise_id: str, model: str) -> dict:
    aligned = json.loads((ALIGNED_DIR / f"{exercise_id}.json").read_text(encoding="utf-8"))
    words = load_words(model, exercise_id)
    segments = aligned["segments"]
    window = 8.0  # seconds around the assigned start to look for the words

    drifted = []
    checked = 0
    good = 0
    for seg in segments:
        cw = content_words(seg["text"])
        if len(cw) < 2:
            continue  # too short to judge (e.g. "OK.")
        checked += 1
        near = {w for t, w in words if seg["start"] - window <= t <= seg["end"] + window}
        hits = sum(1 for w in cw if w in near)
        rate = hits / len(cw)
        if rate < 0.5:
            drifted.append({"id": seg["id"], "start": seg["start"],
                            "rate": round(rate, 2), "text": seg["text"][:55]})
        else:
            good += 1
    return {
        "id": exercise_id,
        "segments": len(segments),
        "checked": checked,
        "good": good,
        "drifted": drifted,
        "confidence": round(good / checked, 2) if checked else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only")
    parser.add_argument("--model", default="small")
    args = parser.parse_args()

    ids = ([args.only] if args.only
           else [p.stem for p in sorted(ALIGNED_DIR.glob("jfdr6_*.json"))])
    for exercise_id in ids:
        r = audit(exercise_id, args.model)
        print(f"\n{r['id']}: confidence {r['confidence']} "
              f"({r['good']}/{r['checked']} content segments OK, {len(r['drifted'])} drifted)")
        for d in r["drifted"]:
            print(f"  id{d['id']:>3} @{d['start']:>7.2f}s rate={d['rate']}  {d['text']}")


if __name__ == "__main__":
    main()
