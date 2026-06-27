#!/usr/bin/env python3
"""Import audited ETS Practice/OG reading samples into the TOEFL player."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

try:
    from scripts.audit_toefl_official_materials import (
        DEFAULT_OUTPUT as DEFAULT_AUDIT_OUTPUT,
        DEFAULT_SOURCE,
        clean_page_text,
        discover_sources,
        extract_pdf_text,
        sha256_file,
        slice_source_text,
    )
except ModuleNotFoundError:
    from audit_toefl_official_materials import (
        DEFAULT_OUTPUT as DEFAULT_AUDIT_OUTPUT,
        DEFAULT_SOURCE,
        clean_page_text,
        discover_sources,
        extract_pdf_text,
        sha256_file,
        slice_source_text,
    )


DEFAULT_DESTINATION = Path("data") / "toefl_practice"
NOTICE = "内部学习资料，禁止外传或用于商业用途"
QUESTION_RE = re.compile(r"(?m)^\s*(?P<number>\d{1,2})\.\s+(?P<body>\S.*)$")
OPTION_RE = re.compile(r"(?m)^\s*(?:\((?P<paren>[A-D])\)|(?P<plain>[A-D])\.)\s+")
PRACTICE_FILL_RE = re.compile(
    r"(?ms)^\s*Fill in the missing letters in the paragraph\.\s*"
    r"\(Questions?\s+(?P<start>\d+)\s*[-–]\s*(?P<end>\d+)\)\s*"
    r"(?P<body>.+?)(?=^\s*Read (?:a|an)\b|^\s*Reading Section\b|\Z)"
)
OG_FILL_RE = re.compile(
    r"(?ms)^\s*(?P<start>\d+)\s*[-–]\s*(?P<end>\d+)\.\s*"
    r"Fill in the missing letters in the paragraph\.\s*"
    r"(?P<body>.+?)(?=^\s*\d+\s*[-–]\s*\d+\.\s*"
    r"Fill in the missing letters|^\s*Read (?:a|an)\b|"
    r"^\s*Urbanization and Social Geography\s*$|\Z)"
)

SOURCE_METADATA = {
    "ets-practice-1": {
        "title": "ETS Student Practice Test 1",
        "subtitle": "官方完整样题",
        "source_kind": "student_practice",
        "expected_modules": {"m1": 20, "m2": 20},
        "duration_seconds": 24 * 60,
        "module_durations": {"m1": 12 * 60, "m2": 12 * 60},
        "sort_key": "2026-01-official-01",
    },
    "ets-og-chapter-6": {
        "title": "ETS Official Guide Chapter 6",
        "subtitle": "OG 官方完整样题",
        "source_kind": "official_guide",
        "expected_modules": {"m1": 35, "m2": 15},
        "duration_seconds": 29 * 60,
        "module_durations": {"m1": 20 * 60, "m2": 9 * 60},
        "sort_key": "2026-01-official-00",
    },
}


def normalize_space(value: str) -> str:
    return re.sub(r"[ \t]+", " ", value).strip()


def clean_content(value: str) -> str:
    lines = []
    for raw_line in value.splitlines():
        line = normalize_space(raw_line)
        if not line:
            if lines and lines[-1]:
                lines.append("")
            continue
        if re.search(r"Reading Section|Module \d|TIME LIMITS", line, re.I):
            continue
        if re.search(r"In an actual test|You can use Next and Back", line, re.I):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def reading_text(source_id: str, source_text: str) -> str:
    if source_id == "ets-practice-1":
        start_match = re.search(r"(?m)^\s*Reading Section, Module 1\s*$", source_text)
        end_match = re.search(
            r"(?m)^\s*Reading Section, Module 1\s*$\s*^\s*Answer Key\s*$",
            source_text,
        )
    else:
        start_match = re.search(r"(?m)^\s*—\s*Reading\s*$", source_text)
        end_match = re.search(r"(?m)^\s*—\s*Listening\s*$", source_text)
    if not start_match or not end_match or end_match.start() <= start_match.start():
        raise RuntimeError(f"Unable to isolate reading section for {source_id}")
    return source_text[start_match.start():end_match.start()]


def parse_options(block: str) -> tuple[str, list[dict]]:
    matches = list(OPTION_RE.finditer(block))
    if len(matches) != 4:
        return "", []
    prompt = clean_content(block[:matches[0].start()])
    options = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(block)
        key = match.group("paren") or match.group("plain")
        options.append({
            "key": key,
            "text": clean_content(block[match.end():end]),
        })
    return prompt, options


def extract_answer_maps(source_id: str, full_text: str) -> dict[str, dict[int, str]]:
    if source_id == "ets-practice-1":
        section_match = re.search(
            r"(?ms)Reading Section, Module 1\s+Answer Key(?P<body>.+?)"
            r"^\s*Listening Section\s*$",
            full_text,
        )
        if not section_match:
            raise RuntimeError("Practice Test 1 reading answer keys not found")
        section = section_match.group("body")
        module_chunks = re.split(r"(?m)^\s*Reading Section, Module 2\s*$", section)
        if len(module_chunks) != 2:
            raise RuntimeError("Practice Test 1 module answer split failed")
        maps = {}
        for module_id, chunk in zip(("m1", "m2"), module_chunks):
            pairs = re.findall(r"(?m)^\s*(\d{1,2})\s+([A-Za-z]+)\s*$", chunk)
            maps[module_id] = {int(number): answer for number, answer in pairs}
        return maps

    answer_start = full_text.find("READING\n                      Answer Key and Self-Scoring Chart")
    if answer_start < 0:
        raise RuntimeError("OG reading answer key not found")
    answer_text = full_text[answer_start:]
    module_1_start = answer_text.find("Module 1")
    module_1_end = answer_text.find("Add the totals", module_1_start)
    module_2_start = answer_text.find("Module 2", module_1_end)
    module_2_end = answer_text.find("Record the total", module_2_start)
    if min(module_1_start, module_1_end, module_2_start, module_2_end) < 0:
        raise RuntimeError("OG answer module boundaries not found")

    maps = {}
    for module_id, chunk in (
        ("m1", answer_text[module_1_start:module_1_end]),
        ("m2", answer_text[module_2_start:module_2_end]),
    ):
        pairs = re.findall(
            r"(?m)(?:^|\s)(\d{1,2})\.?\s+([A-D]|[A-Za-z]+)(?=\s|$)",
            chunk,
        )
        answers = {}
        for number, answer in pairs:
            if answer.lower() in {"module", "total", "contains", "question"}:
                continue
            answers[int(number)] = answer
        maps[module_id] = answers
    return maps


def fill_matches(source_id: str, page: str) -> list[re.Match]:
    pattern = PRACTICE_FILL_RE if source_id == "ets-practice-1" else OG_FILL_RE
    return list(pattern.finditer(page))


def complete_practice_fill_answers(body: str, fragments: list[str]) -> list[str]:
    stems = re.findall(
        r"\b([A-Za-z]+)(?=(?:[_-](?:\s*[_-])*)+)",
        body,
    )
    if len(stems) != len(fragments):
        raise RuntimeError(
            f"Practice fill stem count {len(stems)} does not match answers {len(fragments)}"
        )
    return [stem + fragment for stem, fragment in zip(stems, fragments)]


def module_for_page(page: str, current: str) -> str:
    match = re.search(r"(?m)^\s*Module\s+([12])\s*$", page)
    if not match:
        match = re.search(r"Reading Section, Module\s+([12])", page, re.I)
    return f"m{match.group(1)}" if match else current


def valid_question_matches(page: str, maximum: int) -> list[re.Match]:
    matches = []
    previous = 0
    for match in QUESTION_RE.finditer(page):
        number = int(match.group("number"))
        if not 1 <= number <= maximum or number < previous:
            continue
        matches.append(match)
        previous = number
    return matches


def passage_kind(passage: str) -> str:
    if re.search(r"\b(?:email|notice|social media post|course description)\b", passage, re.I):
        return "read_daily"
    return "read_academic"


def parse_reading_questions(
    source_id: str,
    source_text: str,
    answers: dict[str, dict[int, str]],
    expected_modules: dict[str, int],
) -> list[dict]:
    questions = []
    current_module = "m1"
    current_passage = ""
    order = 0

    for raw_page in reading_text(source_id, source_text).split("\f"):
        page = clean_page_text(raw_page)
        if not page:
            continue
        current_module = module_for_page(page, current_module)
        maximum = expected_modules[current_module]
        spans = []

        for match in fill_matches(source_id, page):
            start = int(match.group("start"))
            end = int(match.group("end"))
            expected = [answers[current_module].get(number) for number in range(start, end + 1)]
            if any(not answer for answer in expected):
                raise RuntimeError(
                    f"Missing {source_id} {current_module} fill answers {start}-{end}"
                )
            if source_id == "ets-practice-1":
                expected = complete_practice_fill_answers(match.group("body"), expected)
            order += 1
            questions.append({
                "id": f"reading_{source_id}_{current_module}_q{start}-{end}",
                "task_type": "complete_words",
                "order": order,
                "number": str(start),
                "number_end": str(end),
                "directive": "Fill in the missing letters in the paragraph.",
                "prompt": "",
                "passage": {"text": clean_content(match.group("body"))},
                "audio_ref": None,
                "options": [],
                "answer": {"words": expected, "explanation": None},
                "response_type": "fill",
            })
            spans.append(match.span())

        remainder = page
        for start, end in reversed(spans):
            remainder = remainder[:start] + "\n" + remainder[end:]
        matches = valid_question_matches(remainder, maximum)
        if not matches:
            continue

        prefix = clean_content(remainder[:matches[0].start()])
        if len(re.sub(r"\W", "", prefix)) >= 30:
            current_passage = prefix

        for index, match in enumerate(matches):
            number = int(match.group("number"))
            end = matches[index + 1].start() if index + 1 < len(matches) else len(remainder)
            block = remainder[match.start():end]
            prompt, options = parse_options(block)
            answer = answers[current_module].get(number)
            if not prompt or len(options) != 4 or answer not in {"A", "B", "C", "D"}:
                raise RuntimeError(
                    f"Invalid {source_id} {current_module} question {number}"
                )
            order += 1
            questions.append({
                "id": f"reading_{source_id}_{current_module}_q{number}",
                "task_type": passage_kind(current_passage),
                "order": order,
                "number": str(number),
                "number_end": None,
                "directive": "",
                "prompt": re.sub(r"^\s*\d{1,2}\.\s*", "", prompt),
                "passage": {"text": current_passage},
                "audio_ref": None,
                "options": options,
                "answer": {"keys": [answer], "explanation": None},
                "response_type": "mc",
            })
    return questions


def item_count(questions: list[dict]) -> int:
    total = 0
    for question in questions:
        if question.get("response_type") == "fill":
            total += len((question.get("answer") or {}).get("words") or [])
        else:
            total += 1
    return total


def load_clear_source_ids(audit_path: Path) -> set[str]:
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    risky_sources = set()
    for group in payload.get("file_duplicate_groups") or []:
        if group.get("classification") == "cross_set_content_duplicate":
            risky_sources.update(group.get("source_ids") or [])
    for match in payload.get("question_duplicate_matches") or []:
        risky_sources.add(match.get("left_source"))
        risky_sources.add(match.get("right_source"))
    return {
        source.get("source_id")
        for source in payload.get("sources") or []
        if source.get("source_id") not in risky_sources
    }


def import_source(source, destination: Path, audit_path: Path) -> dict:
    metadata = SOURCE_METADATA[source.source_id]
    clear_source_ids = load_clear_source_ids(audit_path)
    if source.source_id not in clear_source_ids:
        raise RuntimeError(f"{source.source_id} requires duplicate review")

    full_text = extract_pdf_text(source.pdf_path)
    scoped_text = slice_source_text(source, full_text)
    answers = extract_answer_maps(source.source_id, full_text)
    questions = parse_reading_questions(
        source.source_id,
        scoped_text,
        answers,
        metadata["expected_modules"],
    )
    actual_items = item_count(questions)
    expected_items = sum(metadata["expected_modules"].values())
    if actual_items != expected_items:
        raise RuntimeError(
            f"{source.source_id}: expected {expected_items} reading items, got {actual_items}"
        )

    exam_payload = {
        "exam": {
            "id": f"reading_{source.source_id}",
            "subject": "reading",
            "source_id": source.source_id,
            "source_kind": metadata["source_kind"],
            "duration_seconds": metadata["duration_seconds"],
            "module_durations": metadata["module_durations"],
            "audio_modules": [],
        },
        "questions": questions,
    }
    imported_at = datetime.now().astimezone().isoformat(timespec="seconds")
    manifest = {
        "schema_version": "1.0",
        "id": source.source_id,
        "title": metadata["title"],
        "subtitle": metadata["subtitle"],
        "source_kind": metadata["source_kind"],
        "source_pdf": str(source.pdf_path.relative_to(DEFAULT_SOURCE)),
        "source_sha256": sha256_file(source.pdf_path),
        "audit_source_id": source.source_id,
        "duplicate_status": "clear",
        "publish_status": "published",
        "sort_key": metadata["sort_key"],
        "notice": NOTICE,
        "imported_at": imported_at,
        "subjects": {
            "reading": {
                "page_count": len(questions),
                "item_count": actual_items,
                "answer_coverage": 1.0,
            }
        },
    }

    target = destination / source.source_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "reading.json").write_text(
        json.dumps(exam_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT_OUTPUT / "inventory.json")
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument(
        "--source-id",
        action="append",
        choices=sorted(SOURCE_METADATA),
        dest="source_ids",
    )
    args = parser.parse_args()

    source_ids = set(args.source_ids or SOURCE_METADATA)
    sources = {
        source.source_id: source
        for source in discover_sources(args.source.expanduser().resolve())
    }
    imported = []
    for source_id in sorted(source_ids):
        source = sources.get(source_id)
        if not source:
            raise RuntimeError(f"Source not found: {source_id}")
        imported.append(
            import_source(
                source,
                args.destination.resolve(),
                args.audit.resolve(),
            )
        )
    print(json.dumps({"imported": [item["id"] for item in imported]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
