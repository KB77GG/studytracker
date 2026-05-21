#!/usr/bin/env python3
"""Render exported idictation IELTS speaking questions into reviewable files."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\ufeff", "").replace("\u200b", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_question_number(text: str) -> str:
    return re.sub(r"^\s*\d+\s*[.)、]\s*", "", clean_text(text)).strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def material_order(material_rows: list[dict[str, str]]) -> dict[str, int]:
    order: dict[str, int] = {}
    for row in material_rows:
        material_id = clean_text(row.get("material_id"))
        if material_id and material_id not in order:
            order[material_id] = len(order)
    return order


def source_date(row: dict[str, str]) -> str:
    return clean_text(row.get("suggested_time") or row.get("updated_at"))


def organize(rows: list[dict[str, str]], order: dict[str, int]) -> dict[str, Any]:
    part1: OrderedDict[str, dict[str, Any]] = OrderedDict()
    part23: OrderedDict[str, dict[str, Any]] = OrderedDict()
    flat_rows: list[dict[str, Any]] = []
    seen_flat: set[tuple[str, str, str, str]] = set()

    rows = sorted(
        rows,
        key=lambda row: (
            order.get(clean_text(row.get("material_id")), 10_000),
            clean_text(row.get("part")),
            int(clean_text(row.get("issue_id")) or 0),
        ),
    )

    for row in rows:
        material_id = clean_text(row.get("material_id"))
        title = clean_text(row.get("material_title"))
        part = clean_text(row.get("part"))
        issue_id = clean_text(row.get("issue_id"))
        raw_question = clean_text(row.get("question"))
        date = source_date(row)
        if not material_id or not raw_question:
            continue

        key = (material_id, part, issue_id, raw_question)
        if key in seen_flat:
            continue
        seen_flat.add(key)

        normalized_question = strip_question_number(raw_question) if part in {"Part 1", "Part 3"} else raw_question
        flat_rows.append(
            {
                "material_id": material_id,
                "topic": title,
                "part": part,
                "issue_id": issue_id,
                "question": normalized_question,
                "source_date": date,
            }
        )

        if part == "Part 1":
            topic = part1.setdefault(
                material_id,
                {
                    "material_id": material_id,
                    "topic": title,
                    "source_date": date,
                    "questions": [],
                },
            )
            topic["source_date"] = max(topic["source_date"], date)
            topic["questions"].append(
                {
                    "issue_id": issue_id,
                    "question": normalized_question,
                    "source_date": date,
                }
            )
        else:
            topic = part23.setdefault(
                material_id,
                {
                    "material_id": material_id,
                    "topic": title,
                    "source_date": date,
                    "part2": None,
                    "part3": [],
                },
            )
            topic["source_date"] = max(topic["source_date"], date)
            if part == "Part 2":
                topic["part2"] = {
                    "issue_id": issue_id,
                    "card": raw_question,
                    "source_date": date,
                }
            elif part == "Part 3":
                topic["part3"].append(
                    {
                        "issue_id": issue_id,
                        "question": normalized_question,
                        "source_date": date,
                    }
                )

    return {
        "part1": list(part1.values()),
        "part23": list(part23.values()),
        "flat_rows": flat_rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    part1 = payload["part1"]
    part23 = payload["part23"]
    latest_date = payload.get("latest_source_date") or ""
    counts = payload.get("counts") or {}
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")

    lines = [
        "# IELTS Speaking Question Bank",
        "",
        f"- Generated at: {generated_at}",
        "- Source: idictation speaking export in `data/idictation_speaking/speaking_questions.csv`",
        f"- Latest source date in export: {latest_date or '-'}",
        f"- Part 1 topics: {len(part1)}",
        f"- Part 2/3 topics: {len(part23)}",
        f"- Total questions/cards: {counts.get('total_items', '-')}",
        "",
        "## Part 1",
        "",
    ]

    for index, topic in enumerate(part1, 1):
        date_suffix = f" ({topic['source_date']})" if topic.get("source_date") else ""
        lines.extend([f"### {index}. {topic['topic']}{date_suffix}", ""])
        for q_index, question in enumerate(topic["questions"], 1):
            lines.append(f"{q_index}. {question['question']}")
        lines.append("")

    lines.extend(["## Part 2 and Part 3", ""])
    for index, topic in enumerate(part23, 1):
        date_suffix = f" ({topic['source_date']})" if topic.get("source_date") else ""
        lines.extend([f"### {index}. {topic['topic']}{date_suffix}", ""])
        part2 = topic.get("part2")
        if part2:
            lines.extend(["#### Part 2", "", part2["card"], ""])
        if topic.get("part3"):
            lines.extend(["#### Part 3", ""])
            for q_index, question in enumerate(topic["part3"], 1):
                lines.append(f"{q_index}. {question['question']}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_outputs(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    questions_path = input_dir / "speaking_questions.csv"
    materials_path = input_dir / "speaking_materials.csv"
    rows = read_csv(questions_path)
    material_rows = read_csv(materials_path) if materials_path.exists() else []
    payload = organize(rows, material_order(material_rows))

    source_dates = [row["source_date"] for row in payload["flat_rows"] if row.get("source_date")]
    export_payload = {
        "source": "idictation_speaking",
        "source_files": {
            "questions": str(questions_path),
            "materials": str(materials_path) if materials_path.exists() else "",
        },
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "latest_source_date": max(source_dates) if source_dates else "",
        "counts": {
            "part1_topics": len(payload["part1"]),
            "part23_topics": len(payload["part23"]),
            "part1_questions": sum(len(item["questions"]) for item in payload["part1"]),
            "part2_cards": sum(1 for item in payload["part23"] if item.get("part2")),
            "part3_questions": sum(len(item["part3"]) for item in payload["part23"]),
            "total_items": len(payload["flat_rows"]),
        },
        "part1": payload["part1"],
        "part23": payload["part23"],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "ielts_speaking_questions.md"
    json_path = output_dir / "ielts_speaking_questions.json"
    flat_csv_path = output_dir / "ielts_speaking_questions_flat.csv"
    part1_csv_path = output_dir / "ielts_speaking_part1.csv"
    part23_csv_path = output_dir / "ielts_speaking_part23.csv"

    markdown_path.write_text(render_markdown(export_payload), encoding="utf-8")
    json_path.write_text(json.dumps(export_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(
        flat_csv_path,
        payload["flat_rows"],
        ["material_id", "topic", "part", "issue_id", "question", "source_date"],
    )
    write_csv(
        part1_csv_path,
        [
            {
                "material_id": topic["material_id"],
                "topic": topic["topic"],
                "question_no": index,
                "issue_id": question["issue_id"],
                "question": question["question"],
                "source_date": question["source_date"],
            }
            for topic in payload["part1"]
            for index, question in enumerate(topic["questions"], 1)
        ],
        ["material_id", "topic", "question_no", "issue_id", "question", "source_date"],
    )
    write_csv(
        part23_csv_path,
        [
            {
                "material_id": topic["material_id"],
                "topic": topic["topic"],
                "part2_issue_id": (topic.get("part2") or {}).get("issue_id", ""),
                "part2_card": (topic.get("part2") or {}).get("card", ""),
                "part3_questions": "\n".join(
                    f"{index}. {question['question']}" for index, question in enumerate(topic["part3"], 1)
                ),
                "source_date": topic.get("source_date", ""),
            }
            for topic in payload["part23"]
        ],
        ["material_id", "topic", "part2_issue_id", "part2_card", "part3_questions", "source_date"],
    )
    return {
        "markdown": markdown_path,
        "json": json_path,
        "flat_csv": flat_csv_path,
        "part1_csv": part1_csv_path,
        "part23_csv": part23_csv_path,
        "counts": export_payload["counts"],
        "latest_source_date": export_payload["latest_source_date"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render idictation speaking export into organized files.")
    parser.add_argument("--input-dir", default="data/idictation_speaking")
    parser.add_argument("--output-dir", default="data/idictation_speaking/organized")
    args = parser.parse_args()

    result = build_outputs(Path(args.input_dir), Path(args.output_dir))
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
