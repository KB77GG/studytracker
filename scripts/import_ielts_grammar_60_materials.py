#!/usr/bin/env python3
"""Import the original IELTS Grammar 60-part pack into MaterialBank.

Dry-run is the default. Pass --commit to write. Existing materials with the
same exact title are skipped unless --replace-unused is supplied; replacement
is refused when the material is already attached to a task.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_JSON = ROOT / "data" / "ielts_grammar_60" / "materials.json"


def load_payload(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    materials = payload.get("materials")
    if not isinstance(materials, list):
        raise ValueError("materials.json must contain a materials list")
    if len(materials) != 60:
        raise ValueError(f"expected 60 materials, got {len(materials)}")
    return materials


def validate_material(material: dict) -> None:
    required = {"title", "type", "description", "questions"}
    missing = required - set(material)
    if missing:
        raise ValueError(f"{material.get('code', '?')}: missing {sorted(missing)}")
    if material["type"] != "grammar":
        raise ValueError(f"{material.get('code', '?')}: type must be grammar")
    if len(material["questions"]) != 12:
        raise ValueError(f"{material.get('code', '?')}: expected 12 questions")

    for expected_sequence, question in enumerate(material["questions"], start=1):
        if question.get("sequence") != expected_sequence:
            raise ValueError(
                f"{material.get('code', '?')}: invalid sequence "
                f"{question.get('sequence')}"
            )
        if question.get("question_type") == "choice":
            keys = {option.get("key") for option in question.get("options", [])}
            if question.get("reference_answer") not in keys:
                raise ValueError(
                    f"{material.get('code', '?')} Q{expected_sequence}: "
                    "choice answer is not present in options"
                )


def delete_unused_material(material, Question, QuestionOption, db) -> None:
    question_ids = [
        row.id
        for row in Question.query.filter_by(material_id=material.id).all()
    ]
    if question_ids:
        QuestionOption.query.filter(
            QuestionOption.question_id.in_(question_ids)
        ).delete(synchronize_session=False)
        Question.query.filter(
            Question.id.in_(question_ids)
        ).delete(synchronize_session=False)
    db.session.delete(material)
    db.session.flush()


def create_material(material_data, created_by, models) -> None:
    MaterialBank, Question, QuestionOption, db = models
    material = MaterialBank(
        title=material_data["title"],
        type="grammar",
        description=material_data.get("description", ""),
        created_by=created_by,
        is_active=True,
    )
    db.session.add(material)
    db.session.flush()

    for question_data in material_data["questions"]:
        question = Question(
            material_id=material.id,
            sequence=question_data["sequence"],
            question_type=question_data["question_type"],
            content=question_data["content"],
            reference_answer=question_data.get("reference_answer", ""),
            hint=question_data.get("hint", ""),
            explanation=question_data.get("explanation", ""),
            points=question_data.get("points", 1),
        )
        db.session.add(question)
        db.session.flush()

        for option_data in question_data.get("options", []):
            db.session.add(QuestionOption(
                question_id=question.id,
                option_key=option_data["key"],
                option_text=option_data["text"],
            ))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--created-by", type=int)
    parser.add_argument("--replace-unused", action="store_true")
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    materials = load_payload(args.json)
    for material in materials:
        validate_material(material)

    from app import app
    from models import MaterialBank, Question, QuestionOption, Task, db

    created = 0
    skipped = 0
    replaced = 0
    blocked = []

    with app.app_context():
        models = (MaterialBank, Question, QuestionOption, db)
        for material_data in materials:
            existing = MaterialBank.query.filter_by(
                title=material_data["title"],
                is_deleted=False,
            ).first()

            if existing:
                if not args.replace_unused:
                    print(f"[SKIP] {material_data['code']} title already exists")
                    skipped += 1
                    continue
                task_count = Task.query.filter_by(material_id=existing.id).count()
                if task_count:
                    blocked.append(
                        f"{material_data['code']} material_id={existing.id} "
                        f"is used by {task_count} task(s)"
                    )
                    continue
                delete_unused_material(
                    existing, Question, QuestionOption, db
                )
                replaced += 1

            create_material(material_data, args.created_by, models)
            created += 1
            print(f"[READY] {material_data['code']} {material_data['title_cn']}")

        if blocked:
            db.session.rollback()
            print("\nImport blocked; no changes were committed:")
            for item in blocked:
                print(f"  - {item}")
            return 2

        if args.commit:
            db.session.commit()
            mode = "COMMITTED"
        else:
            db.session.rollback()
            mode = "DRY-RUN"

    print(
        f"\n{mode}: created={created}, replaced={replaced}, "
        f"skipped={skipped}, total={len(materials)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
