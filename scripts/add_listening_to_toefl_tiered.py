#!/usr/bin/env python3
"""One-shot migration: add a Listening section to each of the 8 already-seeded
TOEFL tiered entrance papers.

The 8 papers were originally seeded as Reading + Writing only (sequences 1/2).
This script:
  1. For each paper title in PAPER_LISTENING_MAP:
     a. Skip if the paper has no rows (not yet seeded — fresh installs should
        run seed_toefl_tiered_papers.py instead).
     b. Skip if a listening section already exists at sequence=1.
     c. Otherwise: shift existing sections up by 1 (reading 1→2, writing 2→3)
        then insert a new listening section at sequence=1.
  2. Listening data comes from data/toefl_listening_q1_8/manifest.json.

Idempotent — safe to re-run. Audio files must be present at
uploads/entrance/audio/toefl_tiered_<date>.mp3 (transcoded separately, see
scripts README or the transcode block in seed_toefl_tiered_papers.py).

Usage:
    python3 scripts/add_listening_to_toefl_tiered.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import app  # noqa: E402
from models import (  # noqa: E402
    db,
    EntranceTestPaper,
    EntranceTestSection,
    EntranceTestQuestion,
)


MANIFEST_PATH = PROJECT_ROOT / "data" / "toefl_listening_q1_8" / "manifest.json"
AUDIO_URL_PREFIX = "/uploads/entrance/audio/toefl_tiered_"
AUDIO_FILE_DIR = PROJECT_ROOT / "uploads" / "entrance" / "audio"


# Paper title → listening date. Mirror of PAPERS in seed_toefl_tiered_papers.py.
PAPER_LISTENING_MAP = {
    "新版 TOEFL 入门诊断 A · Video Evidence": "2.23",
    "新版 TOEFL 入门诊断 B · Roman Empire Legacy": "3.30",
    "新版 TOEFL 中阶诊断 A · Expert Systems": "3.11",
    "新版 TOEFL 中阶诊断 B · Cybernetic Prosthetics": "4.8",
    "新版 TOEFL 高阶诊断 A · Ecological Systems Theory": "4.1",
    "新版 TOEFL 高阶诊断 B · Space Debris": "3.20",
    "新版 TOEFL 冲刺诊断 A · Magnetic Confinement Fusion": "3.27",
    "新版 TOEFL 冲刺诊断 B · Beyond Philosophy's Borders": "3.18",
}


def _opts(pairs):
    return json.dumps(
        [{"key": k, "text": t} for k, t in pairs], ensure_ascii=False
    )


def _load_manifest():
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


def _verify_audio_files(manifest):
    """Check that all required mp3 files are present locally before mutating DB."""
    missing = []
    for date in PAPER_LISTENING_MAP.values():
        path = AUDIO_FILE_DIR / f"toefl_tiered_{date}.mp3"
        if not path.exists():
            missing.append(str(path))
        if date not in manifest["dates"]:
            missing.append(f"manifest entry for {date}")
    return missing


def _build_listening_questions(section_id, date_entry):
    """Create EntranceTestQuestion rows for the 8 Q1-8 items."""
    questions = []
    for i, (ans, opts) in enumerate(
        zip(date_entry["answers"], date_entry["options"]), start=1
    ):
        q = EntranceTestQuestion(
            section_id=section_id,
            sequence=i,
            question_type="single_choice",
            stem="Choose the best response.",
            options_json=_opts([
                ("A", opts[0]), ("B", opts[1]),
                ("C", opts[2]), ("D", opts[3]),
            ]),
            correct_answer=ans,
            points=1,
            reference_answer=None,
        )
        questions.append(q)
    return questions


def add_listening_for_paper(paper, listening_date, manifest):
    """Add a listening section to one paper. Returns one of: 'created',
    'already_has_listening', 'no_sections'."""
    sections = (
        EntranceTestSection.query
        .filter_by(paper_id=paper.id)
        .order_by(EntranceTestSection.sequence.asc())
        .all()
    )
    if not sections:
        return "no_sections"

    for s in sections:
        if s.section_type == "listening":
            return "already_has_listening"

    # Shift existing section sequences up by 1 to make room at seq=1.
    # Do this in DESCENDING order to avoid UNIQUE-like collisions even though
    # there is no explicit constraint — defensive ordering.
    for s in sorted(sections, key=lambda x: x.sequence, reverse=True):
        s.sequence = s.sequence + 1

    db.session.flush()

    date_entry = manifest["dates"][listening_date]
    audio_url = f"{AUDIO_URL_PREFIX}{listening_date}.mp3"

    listening_section = EntranceTestSection(
        paper_id=paper.id,
        section_type="listening",
        sequence=1,
        title=f"Section 1 · Listening — Choose the Best Response ({listening_date})",
        instructions=(
            "戴上耳机播放音频，音频会逐题播报情景对话或单句提问，请选择最合适的回应。\n"
            "音频长度约 6-7 分钟，听完第 8 题即可停止。每题只有一个最佳答案。"
        ),
        audio_url=audio_url,
        passage=None,
        duration_minutes=6,
    )
    db.session.add(listening_section)
    db.session.flush()  # assign section.id

    for q in _build_listening_questions(listening_section.id, date_entry):
        db.session.add(q)

    # Also re-title shifted sections so the "Section N · ..." prefix matches
    # their new sequence number, if their current title starts with "Section ".
    for s in sections:
        if s.title and s.title.startswith("Section "):
            # rewrite "Section 1 · X" → "Section 2 · X", etc.
            parts = s.title.split("·", 1)
            if len(parts) == 2:
                s.title = f"Section {s.sequence} ·{parts[1]}"

    db.session.commit()
    return "created"


def main():
    if not MANIFEST_PATH.exists():
        print(f"Error: manifest not found at {MANIFEST_PATH}")
        sys.exit(1)

    manifest = _load_manifest()
    missing = _verify_audio_files(manifest)
    if missing:
        print("Error: required assets missing — aborting before any DB write:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)

    with app.app_context():
        summary = {"created": 0, "already_has_listening": 0, "not_seeded": 0}
        for title, date in PAPER_LISTENING_MAP.items():
            paper = EntranceTestPaper.query.filter_by(
                title=title, exam_type="toefl"
            ).first()
            if not paper:
                print(f"  [SKIP] paper not seeded: '{title}'")
                summary["not_seeded"] += 1
                continue
            result = add_listening_for_paper(paper, date, manifest)
            if result == "created":
                print(f"  [CREATED] listening (date={date}) for paper id={paper.id} '{title}'")
                summary["created"] += 1
            elif result == "already_has_listening":
                print(f"  [SKIP] paper id={paper.id} already has listening: '{title}'")
                summary["already_has_listening"] += 1
            elif result == "no_sections":
                print(f"  [WARN] paper id={paper.id} has no sections, skipping: '{title}'")
                summary["not_seeded"] += 1

        print()
        print(
            f"Done. created={summary['created']}, "
            f"already_has_listening={summary['already_has_listening']}, "
            f"not_seeded={summary['not_seeded']}"
        )


if __name__ == "__main__":
    main()
