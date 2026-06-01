#!/usr/bin/env python3
"""Repair IELTS entrance matching questions imported without options.

Older seeded entrance papers flattened Cambridge listening groups and lost
group-level option banks such as A/B/C matching choices. The same flattened
shape is also used for reading matching groups. This script updates only
existing questions that are currently missing options but can be rebuilt as
single-choice questions from the source JSON.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, EntranceTestPaper, EntranceTestSection
from scripts.seed_ielts_tiered_papers import PAPER_PLAN, _build_paper_data


def _question_needs_repair(question, expected):
    return (
        expected.get("question_type") == "single_choice"
        and expected.get("options_json")
        and (question.question_type != "single_choice" or not question.options_json)
    )


def repair():
    updated = 0
    with app.app_context():
        for plan in PAPER_PLAN:
            paper = EntranceTestPaper.query.filter_by(
                title=plan["title"], exam_type=plan["exam_type"]
            ).first()
            if not paper:
                continue

            for expected_section in _build_paper_data(plan)["sections"]:
                section = (
                    EntranceTestSection.query.filter_by(
                        paper_id=paper.id,
                        section_type=expected_section["section_type"],
                        sequence=expected_section["sequence"],
                    )
                    .order_by(EntranceTestSection.sequence)
                    .first()
                )
                if not section:
                    continue

                current_by_sequence = {q.sequence: q for q in section.questions}
                for expected_q in expected_section["questions"]:
                    q = current_by_sequence.get(expected_q["sequence"])
                    if not q or not _question_needs_repair(q, expected_q):
                        continue

                    # Validate generated options before mutating persisted data.
                    json.loads(expected_q["options_json"])
                    q.question_type = "single_choice"
                    q.stem = expected_q["stem"]
                    q.options_json = expected_q["options_json"]
                    q.correct_answer = expected_q["correct_answer"]
                    q.points = expected_q["points"]
                    updated += 1

        if updated:
            db.session.commit()

    return updated


def main():
    updated = repair()
    print(f"Updated {updated} entrance matching question(s).")


if __name__ == "__main__":
    main()
