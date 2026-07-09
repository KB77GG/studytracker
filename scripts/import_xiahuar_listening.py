#!/usr/bin/env python3
"""Import the self-contained "IELTS Listening 虾滑" HTML set into listening jijing.

Each source directory contains one HTML file with an embedded ``test-data`` JSON
payload and a sibling ``audio.mp3``. The importer converts that payload to the
existing listening-jijing part schema, copies audio into the ignored shared
audio directory, and adds a separate "虾滑听力" collection to catalog.json.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path("/Users/zhouxin/Downloads/IELTS Listening 虾滑")
DEFAULT_OUTPUT = PROJECT_ROOT / "static" / "listening_jijing"

SOURCE_DIR_RE = re.compile(
    r"^(?P<number>\d+)\.\s*P(?P<part>[1-4])\s+(?P<title>.+)$",
    re.IGNORECASE,
)
QUESTION_RANGE_RE = re.compile(r"(\d+)\s*[-–—]\s*(\d+)")
ANALYSIS_RANGE_RE = re.compile(
    r"第\s*(\d+)\s*(?:[-–—至到]\s*(\d+)\s*)?题"
)
FREQUENCY_ORDER = {"高频": 0, "次高频": 1, "非高频": 2}
TYPE_NAMES = {
    "fill": "填空题",
    "single": "单选题",
    "multiple": "多选题",
    "matching": "匹配题",
}
DEFAULT_SOURCE_CREDIT = (
    "素材来自“IELTS Listening 虾滑”目录，由🍠@Listening 永不虾滑整理，"
    "仅供个人学习。"
)


class TestDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.in_test_data = False
        self.chunks: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag == "script" and dict(attrs).get("id") == "test-data":
            self.in_test_data = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.in_test_data:
            self.in_test_data = False

    def handle_data(self, data: str) -> None:
        if self.in_test_data:
            self.chunks.append(data)


class PlainTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self.chunks.append(data)

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag in {"br", "p", "div", "li"} and self.chunks:
            self.chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li"}:
            self.chunks.append("\n")


def plain_text(value: Any) -> str:
    parser = PlainTextParser()
    parser.feed(str(value or ""))
    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in "".join(parser.chunks).splitlines()
    ]
    return "\n".join(line for line in lines if line)


def load_embedded_data(path: Path) -> dict[str, Any]:
    parser = TestDataParser()
    parser.feed(path.read_text(encoding="utf-8"))
    raw = "".join(parser.chunks).strip()
    if not raw:
        raise ValueError(f"{path}: missing script#test-data")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: test-data must be an object")
    return payload


def parse_source_identity(path: Path) -> tuple[int, int, str]:
    match = SOURCE_DIR_RE.match(path.parent.name)
    if not match:
        raise ValueError(f"{path}: unsupported source directory name")
    return (
        int(match.group("number")),
        int(match.group("part")),
        match.group("title").strip(),
    )


def parse_timestamp(value: str) -> int:
    parts = re.split(r"[:,]", value.strip())
    if len(parts) == 4:
        hours, minutes, seconds, millis = map(int, parts)
        # A few source files switch to MM:SS:ff,mmm after six minutes
        # (for example 06:10:00,000 means 00:06:10,000). IELTS section
        # audio is under an hour, so a non-zero "hours" field is that typo.
        if hours:
            hours, minutes, seconds = 0, hours, minutes
    elif len(parts) == 3:
        hours = 0
        minutes, seconds, millis = map(int, parts)
    else:
        raise ValueError(f"invalid timestamp: {value}")
    if minutes < 0 or seconds < 0 or millis < 0:
        raise ValueError(f"invalid timestamp: {value}")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def parse_time_range(value: str) -> tuple[int, int]:
    left, separator, right = str(value or "").partition("-->")
    if not separator:
        raise ValueError(f"invalid time range: {value}")
    return parse_timestamp(left), parse_timestamp(right)


def normalize_options(
    options: list[Any],
    *,
    prefix: str,
) -> list[dict[str, Any]]:
    normalized = []
    for index, option in enumerate(options):
        if not isinstance(option, (list, tuple)) or len(option) < 2:
            continue
        normalized.append(
            {
                "id": f"{prefix}_o{index + 1}",
                "title": str(option[0]).strip(),
                "content": str(option[1]).strip(),
            }
        )
    return normalized


def answer_for(payload: dict[str, Any], number: int) -> str:
    answer_key = payload.get("answerKey")
    if not isinstance(answer_key, dict):
        return ""
    key = f"q{number}"
    for section in ("text", "single", "matching", "map", "multipleMap"):
        values = answer_key.get(section)
        if isinstance(values, dict) and key in values:
            value = values[key]
            if isinstance(value, list):
                return ",".join(str(item).strip() for item in value)
            return str(value).strip()
    return ""


def multiple_answer(
    payload: dict[str, Any],
    group: dict[str, Any],
    numbers: list[int],
) -> str:
    answer_key = payload.get("answerKey") or {}
    values = answer_key.get("multiple") if isinstance(answer_key, dict) else {}
    group_key = "q" + re.sub(r"\D+", "_", str(group.get("id") or "")).strip("_")
    combined = values.get(group_key) if isinstance(values, dict) else None
    if isinstance(combined, list):
        return ",".join(str(item).strip() for item in combined)
    mapped = [answer_for(payload, number) for number in numbers]
    return ",".join(value for value in mapped if value)


def analysis_numbers(value: str) -> list[int]:
    numbers: list[int] = []
    for match in ANALYSIS_RANGE_RE.finditer(value):
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start <= end:
            numbers.extend(range(start, end + 1))
    return list(dict.fromkeys(numbers))


def build_transcript(
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], int]:
    content = []
    question_meta: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"starts": [], "ends": [], "analyses": []}
    )
    plain_english: list[str] = []
    timestamp_repairs = 0
    previous_end: int | None = None

    for order, row in enumerate(payload.get("transcriptLines") or []):
        if not isinstance(row, dict):
            continue
        start_time, end_time = parse_time_range(str(row.get("time") or ""))
        if end_time <= start_time:
            if previous_end is not None and end_time > previous_end:
                start_time = previous_end
            if end_time <= start_time:
                end_time = start_time + 1
            timestamp_repairs += 1
        previous_end = end_time
        en_text = plain_text(row.get("html"))
        cn_text = plain_text(row.get("cn"))
        analysis = plain_text(row.get("analysis"))
        content.append(
            {
                "order": order,
                "cn_text": cn_text,
                "en_text": en_text,
                "end_time": end_time,
                "start_time": start_time,
            }
        )
        plain_english.append(
            re.sub(r"[^a-z0-9]+", "", en_text.lower())
        )
        if analysis:
            for number in analysis_numbers(analysis):
                meta = question_meta[number]
                meta["starts"].append(start_time)
                meta["ends"].append(end_time)
                meta["analyses"].append(analysis)

    for highlight in payload.get("transcriptHighlights") or []:
        if not isinstance(highlight, dict):
            continue
        try:
            number = int(highlight.get("qid"))
        except (TypeError, ValueError):
            continue
        needle = re.sub(
            r"[^a-z0-9]+",
            "",
            plain_text(highlight.get("text")).lower(),
        )
        if len(needle) < 2:
            continue
        for row, normalized in zip(content, plain_english):
            if needle in normalized:
                meta = question_meta[number]
                meta["starts"].append(row["start_time"])
                meta["ends"].append(row["end_time"])

    finalized = {}
    for number, meta in question_meta.items():
        starts = meta["starts"]
        ends = meta["ends"]
        finalized[number] = {
            "start_time": min(starts) if starts else None,
            "end_time": max(ends) if ends else None,
            "analysis": "\n".join(dict.fromkeys(meta["analyses"])),
        }
    return content, finalized, timestamp_repairs


def item_payload(
    *,
    item_id: str,
    number: int,
    title: str,
    options: list[dict[str, Any]],
    answer: str,
    question_meta: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    meta = question_meta.get(number) or {}
    start_time = meta.get("start_time")
    end_time = meta.get("end_time")
    location = None
    if start_time is not None and end_time is not None:
        location = {"start_time": start_time, "end_time": end_time}
    return {
        "id": item_id,
        "number": number,
        "title": title,
        "options": options,
        "answer": answer,
        "analysis": meta.get("analysis") or "",
        "start_time": start_time,
        "end_time": end_time,
        "audio_location": location,
        "img_url": "",
        "is_multiple": 0,
    }


def inject_blank(
    text: str,
    number: int,
) -> tuple[str, bool]:
    patterns = (
        rf"(?<!\d){number}\s*[.．、)]?\s*_{{2,}}",
        rf"_{{2,}}\s*\(?\s*{number}\s*\)?(?!\d)",
    )
    for pattern in patterns:
        updated, count = re.subn(pattern, f"${number}$", text, count=1)
        if count:
            return updated, True
    return text, False


def build_fill_layout(
    group: dict[str, Any],
    questions: list[dict[str, Any]],
) -> tuple[str, dict[str, Any] | None]:
    placed: set[int] = set()
    loose_lines: list[str] = []
    table_cells: dict[tuple[int, int], list[str]] = defaultdict(list)
    max_row = -1
    max_col = -1

    for line in group.get("bodyLines") or []:
        if not isinstance(line, dict):
            continue
        text = str(line.get("text") or "").strip()
        for question in questions:
            number = int(question["id"])
            if number in placed:
                continue
            text, matched = inject_blank(text, number)
            if matched:
                placed.add(number)
        if line.get("list"):
            text = "• " + text
        if line.get("table") is not None:
            row = int(line.get("row") or 0)
            col = int(line.get("col") or 0)
            max_row = max(max_row, row)
            max_col = max(max_col, col)
            table_cells[(row, col)].append(text)
        elif text:
            loose_lines.append(text)

    for question in questions:
        number = int(question["id"])
        if number in placed:
            continue
        text, matched = inject_blank(str(question.get("text") or ""), number)
        loose_lines.append(text if matched else f"Q{number}: ${number}$")
        placed.add(number)

    table = None
    if table_cells:
        rows = []
        for row in range(max_row + 1):
            rows.append(
                [
                    "\n".join(table_cells.get((row, col), []))
                    for col in range(max_col + 1)
                ]
            )
        table = {"title": "", "content": rows}
    return "\n".join(loose_lines), table


def fill_instructions(group: dict[str, Any]) -> str:
    instructions = []
    for line in group.get("bodyLines") or []:
        if not isinstance(line, dict):
            continue
        text = str(line.get("text") or "").strip()
        if not text:
            if instructions:
                break
            continue
        if re.match(
            r"^(complete|write|answer|choose|label|fill)",
            text,
            re.IGNORECASE,
        ):
            instructions.append(text)
            continue
        if instructions:
            break
    return "\n".join(instructions)


def question_numbers_from_multiple(group: dict[str, Any]) -> list[int]:
    match = QUESTION_RANGE_RE.search(
        str(group.get("id") or group.get("title") or "")
    )
    if not match:
        return []
    start, end = map(int, match.groups())
    return list(range(start, end + 1))


def normalize_groups(
    payload: dict[str, Any],
    *,
    exercise_number: int,
    question_meta: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized = []
    for group_index, group in enumerate(payload.get("groups") or [], start=1):
        if not isinstance(group, dict):
            continue
        source_type = str(group.get("type") or "")
        prefix = f"xiahuar_{exercise_number:03d}_g{group_index}"
        base = {
            "group_id": prefix,
            "type_name": TYPE_NAMES.get(source_type, source_type or "题目"),
            "desc": "",
            "title": str(group.get("title") or ""),
            "question_title": "",
            "collect": "",
            "collect_options": {"title": "", "list": []},
            "table": None,
            "img_url": "",
            "items": [],
        }

        if source_type == "fill":
            questions = [
                question
                for question in group.get("questions") or []
                if isinstance(question, dict)
            ]
            collect, table = build_fill_layout(group, questions)
            base.update(
                {
                    "type": 5,
                    "desc": fill_instructions(group),
                    "source_collect": collect,
                    "source_table": table,
                }
            )
            for question in questions:
                number = int(question["id"])
                base["items"].append(
                    item_payload(
                        item_id=str(number),
                        number=number,
                        title=str(question.get("text") or ""),
                        options=[],
                        answer=answer_for(payload, number),
                        question_meta=question_meta,
                    )
                )

        elif source_type == "single":
            base.update(
                {
                    "type": 1,
                    "desc": str(group.get("instruction") or ""),
                }
            )
            for question in group.get("questions") or []:
                if not isinstance(question, dict):
                    continue
                number = int(question["id"])
                base["items"].append(
                    item_payload(
                        item_id=str(number),
                        number=number,
                        title=str(question.get("text") or ""),
                        options=normalize_options(
                            question.get("options") or [],
                            prefix=f"{prefix}_q{number}",
                        ),
                        answer=answer_for(payload, number),
                        question_meta=question_meta,
                    )
                )

        elif source_type == "matching":
            base.update(
                {
                    "type": 8,
                    "desc": str(group.get("instruction") or ""),
                    "collect_options": {
                        "title": str(group.get("optionsTitle") or ""),
                        "list": normalize_options(
                            group.get("options") or [],
                            prefix=prefix,
                        ),
                    },
                }
            )
            for question in group.get("questions") or []:
                if not isinstance(question, (list, tuple)) or len(question) < 2:
                    continue
                number = int(question[0])
                base["items"].append(
                    item_payload(
                        item_id=str(number),
                        number=number,
                        title=str(question[1]),
                        options=[],
                        answer=answer_for(payload, number),
                        question_meta=question_meta,
                    )
                )

        elif source_type == "multiple":
            numbers = question_numbers_from_multiple(group)
            combined_answer = multiple_answer(payload, group, numbers)
            description = "\n".join(
                value
                for value in (
                    str(group.get("instruction") or "").strip(),
                    str(group.get("questionText") or "").strip(),
                )
                if value
            )
            base.update(
                {
                    "type": 2,
                    "desc": description,
                    "collect_options": {
                        "title": "",
                        "list": normalize_options(
                            group.get("options") or [],
                            prefix=prefix,
                        ),
                    },
                }
            )
            for number in numbers:
                base["items"].append(
                    item_payload(
                        item_id=str(number),
                        number=number,
                        title=str(group.get("questionText") or ""),
                        options=[],
                        answer=combined_answer,
                        question_meta=question_meta,
                    )
                )
        else:
            raise ValueError(
                f"exercise {exercise_number}: unsupported group type {source_type}"
            )
        normalized.append(base)
    return normalized


def question_numbers(groups: list[dict[str, Any]]) -> list[int]:
    return sorted(
        {
            int(item["number"])
            for group in groups
            for item in group.get("items") or []
        }
    )


def collection_metadata(
    collection_id: str,
    title: str,
    books: list[dict[str, Any]],
) -> dict[str, Any]:
    tests = [test for book in books for test in book.get("tests") or []]
    parts = [part for test in tests for part in test.get("parts") or []]
    return {
        "id": collection_id,
        "title": title,
        "book_count": len(books),
        "test_count": len(tests),
        "part_count": len(parts),
    }


def validate_part(part: dict[str, Any]) -> None:
    numbers = question_numbers(part["groups"])
    if len(numbers) != 10:
        raise ValueError(f"{part['id']}: expected 10 questions, got {numbers}")
    if numbers != list(range(numbers[0], numbers[0] + 10)):
        raise ValueError(f"{part['id']}: non-contiguous questions {numbers}")
    for group in part["groups"]:
        for item in group["items"]:
            if not str(item.get("answer") or "").strip():
                raise ValueError(
                    f"{part['id']}: Q{item['number']} has no answer"
                )
    content = part.get("content") or []
    if not content:
        raise ValueError(f"{part['id']}: transcript is empty")
    if any(row["end_time"] <= row["start_time"] for row in content):
        raise ValueError(f"{part['id']}: invalid transcript timestamp")


def import_collection(
    source_root: Path,
    output_dir: Path,
    *,
    copy_audio: bool,
) -> dict[str, int]:
    html_files = sorted(source_root.rglob("*.html"))
    if not html_files:
        raise SystemExit(f"no HTML files found under {source_root}")

    catalog_path = output_dir / "catalog.json"
    if not catalog_path.exists():
        raise SystemExit(
            f"missing existing listening jijing catalog: {catalog_path}"
        )
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    existing_books = [
        book
        for book in catalog.get("books") or []
        if book.get("collection", "idictation") != "xiahuar"
    ]

    parts_dir = output_dir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    for stale in parts_dir.glob("xiahuar_*.json"):
        stale.unlink()

    audio_dir = output_dir / "audio"
    if copy_audio:
        audio_dir.mkdir(parents=True, exist_ok=True)
        for stale in audio_dir.glob("xiahuar_*.mp3"):
            stale.unlink()

    grouped_tests: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    seen_numbers: set[int] = set()
    transcript_rows = 0
    timed_questions = 0
    timestamp_repairs = 0

    for html_path in html_files:
        exercise_number, part_number, exercise_title = parse_source_identity(
            html_path
        )
        if exercise_number in seen_numbers:
            raise ValueError(f"duplicate exercise number: {exercise_number}")
        seen_numbers.add(exercise_number)
        relative = html_path.relative_to(source_root)
        frequency = relative.parts[1]
        if frequency not in FREQUENCY_ORDER:
            raise ValueError(f"{html_path}: unsupported frequency {frequency}")

        payload = load_embedded_data(html_path)
        content, question_meta, repaired = build_transcript(payload)
        timestamp_repairs += repaired
        groups = normalize_groups(
            payload,
            exercise_number=exercise_number,
            question_meta=question_meta,
        )
        numbers = question_numbers(groups)
        part_id = f"xiahuar_{exercise_number:03d}_p{part_number}"
        audio_filename = f"{part_id}.mp3"
        source_audio = html_path.parent / str(payload.get("audio") or "audio.mp3")
        if not source_audio.exists():
            raise ValueError(f"{html_path}: missing audio {source_audio}")
        if copy_audio:
            shutil.copy2(source_audio, audio_dir / audio_filename)

        source_credit = (
            str(payload.get("ownerInfo") or "").strip()
            or DEFAULT_SOURCE_CREDIT
        )
        part_payload = {
            "id": part_id,
            "paper_id": exercise_number,
            "in_book": "虾滑听力",
            "test_name": f"{exercise_number:03d}. {exercise_title}",
            "part_title": f"Part {part_number} · {frequency}",
            "part_number": part_number,
            "question_name": f"Q{numbers[0]}-{numbers[-1]}",
            "question_type": "、".join(
                dict.fromkeys(group["type_name"] for group in groups)
            ),
            "audio": {
                "url": "",
                "filename": audio_filename,
                "local_path": f"audio/{audio_filename}",
            },
            "content": content,
            "groups": groups,
            "collection": "xiahuar",
            "collection_title": "虾滑听力",
            "source_label": "🍠@Listening 永不虾滑 · 仅供个人学习",
            "source_credit": source_credit,
        }
        validate_part(part_payload)
        (parts_dir / f"{part_id}.json").write_text(
            json.dumps(part_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        timed_questions += sum(
            1
            for group in groups
            for item in group["items"]
            if item.get("start_time") is not None
        )
        transcript_rows += len(content)
        grouped_tests[(part_number, frequency)].append(
            {
                "test_name": f"{exercise_number:03d}. {exercise_title}",
                "parts": [
                    {
                        "id": part_id,
                        "paper_id": exercise_number,
                        "part_title": "练习",
                        "part_number": part_number,
                        "question_name": f"Q{numbers[0]}-{numbers[-1]}",
                        "question_type": part_payload["question_type"],
                        "question_count": 10,
                        "audio_path": f"audio/{audio_filename}",
                    }
                ],
            }
        )

    expected_numbers = set(range(1, len(html_files) + 1))
    if seen_numbers != expected_numbers:
        missing = sorted(expected_numbers - seen_numbers)
        extras = sorted(seen_numbers - expected_numbers)
        raise ValueError(f"exercise numbering mismatch: missing={missing}, extras={extras}")

    xiahuar_books = []
    for (part_number, frequency), tests in sorted(
        grouped_tests.items(),
        key=lambda pair: (
            pair[0][0],
            FREQUENCY_ORDER[pair[0][1]],
        ),
    ):
        tests.sort(key=lambda test: int(test["test_name"].split(".", 1)[0]))
        xiahuar_books.append(
            {
                "in_book": f"P{part_number} · {frequency}",
                "title": f"Part {part_number} · {frequency}",
                "label": "虾滑听力",
                "collection": "xiahuar",
                "collection_title": "虾滑听力",
                "tests": tests,
            }
        )

    idictation_meta = collection_metadata(
        "idictation",
        "机经",
        existing_books,
    )
    xiahuar_meta = collection_metadata(
        "xiahuar",
        "虾滑听力",
        xiahuar_books,
    )
    all_books = existing_books + xiahuar_books
    catalog.update(
        {
            "title": "听力机经",
            "collection_count": 2,
            "book_count": len(all_books),
            "part_count": idictation_meta["part_count"]
            + xiahuar_meta["part_count"],
            "collections": [idictation_meta, xiahuar_meta],
            "books": all_books,
        }
    )
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "parts": len(html_files),
        "questions": len(html_files) * 10,
        "transcript_rows": transcript_rows,
        "timed_questions": timed_questions,
        "timestamp_repairs": timestamp_repairs,
        "audio": len(html_files) if copy_audio else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--skip-audio",
        action="store_true",
        help="build JSON/catalog without copying source MP3 files",
    )
    args = parser.parse_args()

    result = import_collection(
        args.source,
        args.output_dir,
        copy_audio=not args.skip_audio,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
