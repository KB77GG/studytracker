#!/usr/bin/env python3
"""Build the online TOEFL practice bank from the organized 2026 real exams.

The importer deliberately keeps extraction quality visible:
- questions with a usable prompt are published even when no answer exists;
- automatic grading is enabled only when the mapped answer is structurally valid;
- incomplete source material is reported instead of replaced with invented text.

Run with the system Python because the existing OCR helper modules import
python-docx:

    python3 scripts/import_toefl_real_exams.py
"""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = Path("/Users/zhouxin/Desktop/新托福资料")
DATA_ROOT = REPO_ROOT / "data" / "toefl_practice"
ANSWER_ROOT = REPO_ROOT / "data" / "toefl_answer_keys" / "practice_crosswalk"
STATIC_ROOT = REPO_ROOT / "static" / "toefl"

LISTENING_Q_RE = re.compile(
    r"^Listening\s*\|?\s*Question\s+(\d+)\s+of\s+(\d+)", re.I
)
OPTION_PREFIX_RE = re.compile(
    r"^\s*(?:[¥yl2aq《\\|()]+\s*)*"
    r"(?:C?O|QO|OQ|©|〇)(?:\s*[©〇])?\s+(.+?)\s*$",
    re.I,
)
TOKEN_RE = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*|[?.,]")


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def practice_id(row: dict[str, str]) -> str:
    return row.get("practice_id") or row.get("\ufeffpractice_id") or ""


def online_exam_id(source_id: str) -> str:
    date = source_id[:10]
    suffix = source_id[10:].strip("-")
    if not suffix:
        return date
    return f"{date}_{suffix.replace('-', '_').upper()}"


def title_slug(exam_id: str) -> str:
    suffix = exam_id[10:].strip("_")
    if not suffix:
        return exam_id[:10]
    replacements = {
        "S1": "Set1",
        "S2": "Set2",
        "OFFLINE_CN": "Offline_CN",
        "OFFLINE": "Offline",
    }
    return f"{exam_id[:10]}_{replacements.get(suffix, suffix)}"


def load_answer_map(rows: list[dict[str, str]]) -> dict[tuple[str, str, str, int], str]:
    result: dict[tuple[str, str, str, int], str] = {}
    for row in rows:
        try:
            number = int(row.get("source_question_no") or "")
        except ValueError:
            continue
        answer = (row.get("correct_answer") or "").strip()
        if answer:
            result[
                (
                    practice_id(row),
                    row.get("subject") or "",
                    row.get("module") or "",
                    number,
                )
            ] = answer
    return result


def answer_for(
    answers: dict[tuple[str, str, str, int], str],
    source_id: str,
    subject: str,
    module: str,
    number: int,
) -> str:
    return answers.get((source_id, subject, module, number), "")


def load_helpers(source_root: Path):
    helper_root = source_root / "新托福分科刷题材料" / "整理输出"
    sys.path.insert(0, str(helper_root))
    listening = importlib.import_module("build_branded_listening_book")
    writing = importlib.import_module("build_writing_practice_book")
    speaking = importlib.import_module("build_branded_speaking_book_v2")
    speaking_root = helper_root / "口语转写_修订版"
    speaking.MANIFEST_PATH = speaking_root / "manifest.json"
    speaking.TRANSCRIPTS_DIR = speaking_root / "transcripts"
    return helper_root, listening, writing, speaking


def question_quality(item: dict) -> int:
    return (
        len(item.get("material") or "")
        + len(item.get("stem") or "") * 3
        + sum(len(value) for value in item.get("options") or []) * 2
    )


def split_reading_modules(items: list[dict]) -> dict[str, list[dict]]:
    result = {"m1": [], "m2": []}
    module = "m1"
    max_number = 0
    for item in items:
        number = item.get("number")
        material = item.get("material") or ""
        if number == 36 and "Type of Task Description" in material:
            module = "m2"
            max_number = 0
            continue
        if not isinstance(number, int):
            continue
        if (
            module == "m1"
            and item.get("kind") == "complete_words"
            and max_number >= 21
            and number <= 10
        ):
            module = "m2"
            max_number = 0
        result[module].append(item)
        max_number = max(max_number, number)
    return result


def merge_reading_entries(entries: list[dict], title: str) -> dict[str, list[dict]]:
    merged: dict[str, dict[tuple[str, int], dict]] = {"m1": {}, "m2": {}}
    for index, entry in enumerate(entries):
        items = json.loads(Path(entry["output"]).read_text(encoding="utf-8"))
        modules = split_reading_modules(items)
        if (
            title == "2026-03-29 国内线下"
            and index > 0
            and not modules["m2"]
        ):
            modules["m2"] = modules["m1"]
            modules["m1"] = []
        for module, values in modules.items():
            for position, item in enumerate(values):
                number = item.get("number")
                if not isinstance(number, int):
                    continue
                key = (
                    item.get("kind") or "question",
                    number,
                )
                current = merged[module].get(key)
                if current is None or question_quality(item) > question_quality(current):
                    copied = dict(item)
                    copied["_source"] = entry.get("relative_source") or entry.get("source")
                    copied["_sequence"] = index * 1000 + position
                    merged[module][key] = copied
    return {
        module: sorted(
            values.values(),
            key=lambda item: int(item.get("_sequence") or 0),
        )
        for module, values in merged.items()
    }


def clean_reading_material(text: str | None) -> str:
    if not text:
        return ""
    text = re.split(
        r"\n{2,}Listening\s+Listening Section\b",
        text,
        maxsplit=1,
        flags=re.I,
    )[0]
    return re.sub(r"\s+IDI\s*$", " [D]", text).strip()


def reading_task(module: str, number: int, kind: str) -> str:
    if kind == "complete_words":
        return "complete_words"
    if module == "m1" and number <= 25:
        return "read_daily"
    return "read_academic"


def build_reading(
    source_id: str,
    exam_id: str,
    row: dict[str, str],
    entries: list[dict],
    answers: dict,
) -> dict | None:
    modules = merge_reading_entries(entries, row["practice_title"])
    questions: list[dict] = []
    order = 0
    for module in ("m1", "m2"):
        previous_mc = 20 if module == "m1" else 10
        for item in modules[module]:
            number = int(item["number"])
            number_end = int(item.get("number_end") or number)
            kind = item.get("kind") or "question"
            if kind == "question":
                expected_min, expected_max = (
                    (21, 35) if module == "m1" else (11, 15)
                )
                number_text = str(number)
                if number > 99:
                    possible = int(number_text[:2])
                    if expected_min <= possible <= expected_max:
                        number = possible
                        number_end = number
                if not expected_min <= number <= expected_max or number <= previous_mc:
                    if previous_mc < expected_max:
                        number = previous_mc + 1
                        number_end = number
                previous_mc = max(previous_mc, number)
            material = clean_reading_material(item.get("material"))
            stem = (item.get("stem") or "").strip()
            options = [
                re.sub(r"\s+", " ", value).strip()
                for value in item.get("options") or []
                if re.sub(r"\s+", " ", value).strip()
            ]
            response_type = "fill" if kind == "complete_words" else "mc"
            if response_type == "fill" and not 1 <= number <= 20:
                continue
            if response_type == "fill" and not material:
                continue
            if response_type == "mc" and (len(options) < 2 or not (stem or material)):
                continue
            order += 1
            answer = None
            if response_type == "fill":
                words = [
                    answer_for(answers, source_id, "reading", module, value)
                    for value in range(number, number_end + 1)
                ]
                if words and all(words):
                    answer = {"words": words, "explanation": None}
            else:
                key = answer_for(answers, source_id, "reading", module, number)
                if key and key in {
                    chr(65 + index) for index in range(min(len(options), 4))
                }:
                    answer = {"keys": [key], "explanation": None}
            questions.append(
                {
                    "id": f"reading_{exam_id}_{module}_q{number}",
                    "task_type": reading_task(module, number, kind),
                    "order": order,
                    "number": str(number),
                    "number_end": str(number_end) if number_end != number else None,
                    "directive": item.get("directive")
                    or (
                        "Fill in the missing letters in the paragraph."
                        if response_type == "fill"
                        else "Read the passage and choose the best answer."
                    ),
                    "prompt": stem,
                    "passage": {"text": material} if material else None,
                    "audio_ref": None,
                    "options": [
                        {"key": chr(65 + index), "text": text}
                        for index, text in enumerate(options[:4])
                    ],
                    "answer": answer,
                    "response_type": response_type,
                    "content_status": "complete",
                    "grading_status": "auto" if answer else "review_only",
                    "source_ref": item.get("_source") or "",
                }
            )
    questions.sort(
        key=lambda question: (
            0 if "_m1_" in question["id"] else 1,
            int(question["number"]),
        )
    )
    for index, question in enumerate(questions, start=1):
        question["order"] = index
    if not questions:
        return None
    return {
        "exam": {
            "id": f"reading_{exam_id}",
            "subject": "reading",
            "date": exam_id[:10],
            "volume": exam_id[10:].strip("_"),
            "source_pdf": row.get("reading_sources") or "",
            "duration_seconds": 1800,
            "module_durations": {"m1": 1200, "m2": 600},
            "audio_modules": [],
        },
        "questions": questions,
    }


def first_question_source_lines(section) -> list[str]:
    lines: list[str] = []
    in_source = False
    skip_source = False
    for raw in section.lines:
        if raw.startswith("### 来源："):
            in_source = True
            skip_source = "听力原文" in raw
            continue
        if in_source and not skip_source:
            lines.append(raw)
    return lines


def clean_listening_body(lines: list[str], listening) -> list[str]:
    result: list[str] = []
    for raw in lines:
        line = listening.clean_ocr_line(raw).strip()
        if not line or listening.PAGE_MARKER.fullmatch(line):
            continue
        if line.startswith(("抽取方式：", "文件夹：")):
            continue
        if re.fullmatch(r"[\\|a-z]{1,2}", line, re.I):
            continue
        result.append(line)
    return result


def listening_segments(section, listening) -> dict[tuple[str, int], list[list[str]]]:
    grouped: dict[tuple[str, int], list[list[str]]] = {}
    current_key: tuple[str, int] | None = None
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if current_key is not None:
            body = clean_listening_body(current, listening)
            if body:
                grouped.setdefault(current_key, []).append(body)
        current = []

    for raw in first_question_source_lines(section):
        cleaned = listening.clean_ocr_line(raw).strip()
        match = LISTENING_Q_RE.match(cleaned)
        if match:
            flush()
            number = int(match.group(1))
            total = int(match.group(2))
            module = "m1" if total >= 20 else "m2"
            current_key = (module, number)
            continue
        if current_key is not None:
            current.append(raw)
    flush()
    return grouped


def parse_listening_candidate(lines: list[str]) -> tuple[str, list[str]]:
    options: list[str] = []
    pre_option: list[str] = []
    for line in lines:
        low = line.lower()
        if low.startswith(
            (
                "choose the best response",
                "listen to a conversation",
                "conversation, announcement",
                "you will listen only one time",
                "in an actual test",
            )
        ):
            continue
        match = OPTION_PREFIX_RE.match(line)
        if match:
            option = re.sub(r"\s+", " ", match.group(1)).strip()
            if option:
                options.append(option)
            continue
        if options:
            options[-1] = f"{options[-1]} {line}".strip()
        else:
            pre_option.append(line)
    if len(options) == 3 and pre_option:
        candidate = pre_option[-1]
        if len(candidate) >= 8 and not candidate.lower().startswith("listen to"):
            options.insert(0, candidate)
            pre_option.pop()
    prompt_candidates = [
        value
        for value in pre_option
        if len(value) >= 8 and not value.lower().startswith("listening")
    ]
    prompt = prompt_candidates[-1] if prompt_candidates else ""
    return prompt, options[:4]


def best_listening_candidate(candidates: list[list[str]]) -> tuple[str, list[str]]:
    parsed = [parse_listening_candidate(lines) for lines in candidates]
    return max(
        parsed,
        key=lambda value: (
            len(value[1]) == 4,
            len(value[1]),
            len(value[0]),
            sum(map(len, value[1])),
        ),
        default=("", []),
    )


def listening_task(module: str, number: int) -> str:
    if (module == "m1" and number <= 12) or (module == "m2" and number <= 3):
        return "listen_and_choose"
    if (module == "m1" and number <= 18) or (module == "m2" and number <= 7):
        return "conversation"
    return "academic_talk"


def listening_directive(task_type: str) -> str:
    if task_type == "listen_and_choose":
        return "Choose the best response"
    if task_type == "conversation":
        return "Listen to a conversation."
    return "Listen to an announcement or academic talk."


def media_candidates(folder: Path, exam_id: str, kind: str) -> list[Path]:
    date = exam_id[:10]
    slug = title_slug(exam_id).lower()
    suffix = exam_id[10:].strip("_").lower()
    result = []
    for path in sorted(folder.glob("*")):
        name = path.stem.lower()
        if not name.startswith(date.lower()):
            continue
        if suffix == "offline" and ("offline" not in name or "offline_cn" in name):
            continue
        if suffix == "offline_cn" and "offline" not in name:
            continue
        if suffix in {"a", "b", "c"} and f"_{suffix}_" not in f"_{name}_":
            continue
        if suffix in {"s1", "s2"} and f"set{suffix[-1]}" not in name:
            continue
        if not suffix and any(token in name for token in ("_a_", "_b_", "_c_", "set", "offline")):
            continue
        score = sum(token in name for token in slug.split("_"))
        if kind.lower() in name:
            score += 2
        result.append((score, path))
    if not result:
        return []
    best_score = max(score for score, _ in result)
    return [path for score, path in result if score == best_score]


def copy_media(paths: list[Path], destination: Path) -> list[str]:
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for source in paths:
        target = destination / source.name
        if not target.exists() or target.stat().st_size != source.stat().st_size:
            shutil.copy2(source, target)
        copied.append(target.name)
    return copied


def listening_audio_modules(
    exam_id: str, folder: Path, copy_assets: bool
) -> list[dict]:
    paths = media_candidates(folder, exam_id, "")
    if not paths:
        return []
    filenames = (
        copy_media(paths, STATIC_ROOT / "audio")
        if copy_assets
        else [path.name for path in paths]
    )
    by_module: dict[str, str] = {}
    full = ""
    for filename in filenames:
        low = filename.lower()
        if "module1" in low:
            by_module["m1"] = filename
        elif "module2" in low:
            by_module["m2"] = filename
        elif "full" in low:
            full = filename
    if full:
        by_module.setdefault("m1", full)
        by_module.setdefault("m2", full)
    return [
        {
            "id": module,
            "label": f"Listening Module {module[-1]}",
            "url": f"/static/toefl/audio/{filename}",
        }
        for module, filename in sorted(by_module.items())
    ]


def build_listening(
    source_id: str,
    exam_id: str,
    row: dict[str, str],
    section,
    answers: dict,
    listening,
    audio_folder: Path,
    copy_assets: bool,
) -> dict | None:
    audio_modules = listening_audio_modules(exam_id, audio_folder, copy_assets)
    if not audio_modules:
        return None
    available_modules = {module["id"] for module in audio_modules}
    segments = listening_segments(section, listening)
    questions: list[dict] = []
    for order, ((module, number), candidates) in enumerate(
        sorted(segments.items(), key=lambda item: (item[0][0], item[0][1])),
        start=1,
    ):
        if module not in available_modules:
            continue
        prompt, options = best_listening_candidate(candidates)
        if len(options) < 2:
            continue
        task_type = listening_task(module, number)
        key = answer_for(answers, source_id, "listening", module, number)
        answer = (
            {"keys": [key], "explanation": None}
            if key and key in {
                chr(65 + index) for index in range(len(options))
            }
            else None
        )
        questions.append(
            {
                "id": f"listening_{exam_id}_{module}_q{number}",
                "task_type": task_type,
                "order": order,
                "number": str(number),
                "number_end": None,
                "directive": listening_directive(task_type),
                "prompt": prompt if task_type != "listen_and_choose" else "",
                "passage": None,
                "audio_ref": module,
                "options": [
                    {"key": chr(65 + index), "text": text}
                    for index, text in enumerate(options)
                ],
                "answer": answer,
                "response_type": "mc",
                "content_status": "complete",
                "grading_status": "auto" if answer else "review_only",
                "source_ref": row.get("listening_sources") or "",
            }
        )
    if not questions:
        return None
    return {
        "exam": {
            "id": f"listening_{exam_id}",
            "subject": "listening",
            "date": exam_id[:10],
            "volume": exam_id[10:].strip("_"),
            "source_pdf": row.get("listening_sources") or "",
            "duration_seconds": 1740,
            "module_durations": {"m1": 900, "m2": 840},
            "audio_modules": audio_modules,
        },
        "questions": questions,
    }


def answer_tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text)


def normalize_words(words: list[str]) -> Counter:
    return Counter(
        value.lower()
        for value in words
        if re.search(r"[A-Za-z]", value)
    )


def repair_scramble(scramble: list[str], ordered: list[str]) -> tuple[list[str], bool]:
    available = normalize_words(scramble)
    required = normalize_words(ordered)
    repaired = list(scramble)
    changed = False
    for word, count in (required - available).items():
        source_values = [
            value for value in ordered if value.lower() == word
        ][:count]
        repaired.extend(source_values)
        changed = True
    if len([value for value in repaired if re.search(r"[A-Za-z]", value)]) < 3:
        repaired = list(reversed(ordered))
        changed = True
    return repaired, changed


def collect_writing_questions(section, writing) -> list[dict]:
    lines: list[str] = []
    for raw in section.lines:
        if writing.PAGE_MARKER.fullmatch(raw.strip()):
            continue
        cleaned = writing.clean_line(raw)
        if cleaned or not raw.strip():
            lines.append(cleaned)
    return writing.fill_missing_questions(
        writing.dedup(writing.tokenize(lines))
    )


def build_writing(
    source_id: str,
    exam_id: str,
    row: dict[str, str],
    section,
    answers: dict,
    writing,
) -> dict | None:
    source_questions = collect_writing_questions(section, writing)
    questions: list[dict] = []
    used_numbers: set[int] = set()
    for source in source_questions:
        total = int(source["total"])
        original_number = int(source["n"])
        if total in (10, 12):
            number = original_number
        elif total == 2:
            number = 10 + original_number
        else:
            continue
        if number in used_numbers or source.get("missing"):
            continue
        task = writing.task_name(source)
        body = [
            line for line in writing.clean_block(source.get("body", []))
            if line
        ]
        if not body:
            continue
        used_numbers.add(number)
        common = {
            "id": f"writing_{exam_id}_m1_q{number}",
            "order": len(questions) + 1,
            "number": str(number),
            "number_end": None,
            "passage": None,
            "audio_ref": None,
            "options": [],
            "source_ref": row.get("writing_sources") or "",
        }
        if task == "Build a Sentence":
            content = [
                line for line in body
                if line.lower() != "make an appropriate sentence."
            ]
            if not content:
                continue
            prompt = content[0]
            scramble = answer_tokens(" ".join(content[1:]))
            ordered = answer_tokens(
                answer_for(answers, source_id, "writing", "m1", number)
            )
            repaired = False
            if ordered:
                scramble, repaired = repair_scramble(scramble, ordered)
            if not scramble:
                continue
            answer = (
                {"ordered": ordered, "explanation": None}
                if ordered
                else None
            )
            questions.append(
                {
                    **common,
                    "task_type": "build_a_sentence",
                    "directive": "Make an appropriate sentence.",
                    "prompt": prompt,
                    "target_sentence": prompt,
                    "scramble_words": scramble,
                    "answer": answer,
                    "response_type": "order",
                    "content_status": (
                        "repaired_from_answer" if repaired else "complete"
                    ),
                    "grading_status": "auto" if answer else "review_only",
                }
            )
        else:
            prompt = "\n".join(body).strip()
            if len(prompt) < 20:
                continue
            questions.append(
                {
                    **common,
                    "task_type": (
                        "write_email"
                        if task == "Write an Email"
                        else "academic_discussion"
                    ),
                    "directive": task,
                    "prompt": prompt,
                    "answer": None,
                    "response_type": "free",
                    "content_status": "complete",
                    "grading_status": "manual",
                }
            )
    if not questions:
        return None
    return {
        "exam": {
            "id": f"writing_{exam_id}",
            "subject": "writing",
            "date": exam_id[:10],
            "volume": exam_id[10:].strip("_"),
            "source_pdf": row.get("writing_sources") or "",
            "duration_seconds": 1380,
            "module_durations": {"m1": 1380},
            "audio_modules": [],
        },
        "questions": questions,
    }


def speaking_audio_modules(
    exam_id: str, folder: Path, copy_assets: bool
) -> list[dict]:
    paths = media_candidates(folder, exam_id, "speaking")
    if not paths:
        return []
    path = paths[0]
    filename = (
        copy_media([path], STATIC_ROOT / "speaking")[0]
        if copy_assets
        else path.name
    )
    url = f"/static/toefl/speaking/{filename}"
    return [
        {"id": "m1", "label": "Listen and Repeat", "url": url},
        {"id": "m2", "label": "Take an Interview", "url": url},
    ]


def interview_questions(paragraphs: list[str]) -> list[str]:
    result: list[str] = []
    for paragraph in paragraphs:
        pieces = re.split(r"(?<=\?)\s+", paragraph)
        for piece in pieces:
            piece = piece.strip()
            if "?" in piece and len(piece) >= 12:
                result.append(piece)
    if not result:
        result = [value for value in paragraphs if len(value.strip()) >= 20]
    return result[:4]


def build_speaking(
    exam_id: str,
    row: dict[str, str],
    transcript,
    audio_folder: Path,
    copy_assets: bool,
) -> dict | None:
    audio_modules = speaking_audio_modules(exam_id, audio_folder, copy_assets)
    if not audio_modules or transcript is None:
        return None
    questions: list[dict] = []
    for number, text in enumerate(transcript.repeat_items[:7], start=1):
        questions.append(
            {
                "id": f"speaking_{exam_id}_m1_q{number}",
                "task_type": "listen_and_repeat",
                "order": len(questions) + 1,
                "number": str(number),
                "number_end": None,
                "directive": "Listen and repeat. You may record only once in test mode.",
                "prompt": text,
                "passage": {
                    "text": transcript.scenario
                } if transcript.scenario else None,
                "audio_ref": "m1",
                "options": [],
                "answer": None,
                "response_type": "record",
                "content_status": "complete",
                "grading_status": "manual",
                "source_ref": "local speaking audio transcript",
            }
        )
    interview = interview_questions(transcript.interview_paragraphs)
    if not interview and transcript.fallback_paragraphs:
        interview = transcript.fallback_paragraphs[:4]
    for offset, text in enumerate(interview, start=1):
        questions.append(
            {
                "id": f"speaking_{exam_id}_m2_q{offset}",
                "task_type": "take_an_interview",
                "order": len(questions) + 1,
                "number": str(offset),
                "number_end": None,
                "directive": "Answer the interviewer's question.",
                "prompt": text,
                "passage": None,
                "audio_ref": "m2",
                "options": [],
                "answer": None,
                "response_type": "record",
                "content_status": "complete",
                "grading_status": "manual",
                "source_ref": "local speaking audio transcript",
            }
        )
    if not questions:
        return None
    return {
        "exam": {
            "id": f"speaking_{exam_id}",
            "subject": "speaking",
            "date": exam_id[:10],
            "volume": exam_id[10:].strip("_"),
            "source_pdf": row.get("folder") or "",
            "duration_seconds": 960,
            "module_durations": {"m1": 420, "m2": 540},
            "audio_modules": audio_modules,
        },
        "questions": questions,
    }


def subject_stats(payload: dict) -> dict:
    questions = payload["questions"]
    auto = sum(question.get("grading_status") == "auto" for question in questions)
    manual = sum(question.get("grading_status") == "manual" for question in questions)
    review = sum(question.get("grading_status") == "review_only" for question in questions)
    return {
        "question_objects": len(questions),
        "auto_graded": auto,
        "manual_review": manual,
        "answer_missing": review,
    }


def report_markdown(report: dict) -> str:
    lines = [
        "# TOEFL 全量在线题库导入报告",
        "",
        f"- 生成时间：`{report['generated_at']}`",
        f"- 真题套数：`{report['exam_count']}`",
        f"- 已发布科目：`{report['subject_count']}`",
        f"- 可作答题目对象：`{report['question_count']}`",
        f"- 自动判分题：`{report['auto_graded']}`",
        f"- 人工复核题：`{report['manual_review']}`",
        f"- 答案缺失但题面可作答：`{report['answer_missing']}`",
        "",
        "## 套卷明细",
        "",
        "| 套卷 | 阅读 | 听力 | 写作 | 口语 | 状态 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for item in report["exams"]:
        counts = item["subjects"]
        lines.append(
            f"| {item['title']} | {counts.get('reading', 0)} | "
            f"{counts.get('listening', 0)} | {counts.get('writing', 0)} | "
            f"{counts.get('speaking', 0)} | {item['content_status']} |"
        )
    lines.extend(
        [
            "",
            "## 题号风险",
            "",
            "- 阅读与听力在 Module 2 会重新从 1 编号；在线 ID 强制包含 `m1/m2`，不能只按题号关联。",
            "- 阅读填词题在题面中常以 1-10、11-20 的题组对象出现，但答案表是一题一行；导入器按范围回填。",
            "- 写作部分来源既有 12 题连续编号，也有 10 道组句 + 2 道独立写作；后者统一映射为 11、12。",
            "- OCR 漏题不会生成空白作答页；题面存在但答案缺失的题保留为 `review_only`。",
            "- 听力/口语只有找到对应压缩音频时才发布，避免将纯文字误标成完整听力题。",
        ]
    )
    return "\n".join(lines) + "\n"


def run(source_root: Path, copy_assets: bool = True) -> dict:
    helper_root, listening, writing, speaking = load_helpers(source_root)
    exam_rows = load_csv(ANSWER_ROOT / "exam_crosswalk.csv")
    answer_rows = load_csv(ANSWER_ROOT / "question_answer_crosswalk.csv")
    answers = load_answer_map(answer_rows)

    reading_root = source_root / "tmp" / "pdfs" / "reading_structured"
    reading_manifest = json.loads(
        (reading_root / "manifest.json").read_text(encoding="utf-8")
    )
    reading_by_title: dict[str, list[dict]] = {}
    for entry in reading_manifest:
        reading_by_title.setdefault(entry["date"], []).append(entry)

    listening_sections = {
        section.title: section
        for section in listening.parse_markdown(
            helper_root / "托福真题整理_听力.md"
        )
    }
    writing_sections = {
        section.title: section
        for section in writing.parse_markdown(
            helper_root / "托福真题整理_写作.md"
        )
    }
    transcripts = speaking.load_transcripts()
    for duplicate, original in speaking.DUPLICATE_TRANSCRIPTS.items():
        if original in transcripts:
            transcripts[duplicate] = transcripts[original]

    listening_audio = (
        source_root
        / "新托福分科刷题材料"
        / "SagePath_2026新托福听力刷题_网页版"
        / "audio"
    )
    speaking_audio = (
        source_root
        / "新托福分科刷题材料"
        / "SagePath_2026新托福口语刷题包"
        / "audio"
    )

    report_exams: list[dict] = []
    totals = Counter()
    for row in exam_rows:
        source_id = practice_id(row)
        exam_id = online_exam_id(source_id)
        title = row["practice_title"]
        exam_dir = DATA_ROOT / exam_id
        exam_dir.mkdir(parents=True, exist_ok=True)
        for subject in ("reading", "listening", "writing", "speaking"):
            path = exam_dir / f"{subject}.json"
            if path.exists():
                path.unlink()

        payloads = {
            "reading": build_reading(
                source_id,
                exam_id,
                row,
                reading_by_title.get(title, []),
                answers,
            ),
            "listening": build_listening(
                source_id,
                exam_id,
                row,
                listening_sections.get(title),
                answers,
                listening,
                listening_audio,
                copy_assets,
            )
            if listening_sections.get(title)
            else None,
            "writing": build_writing(
                source_id,
                exam_id,
                row,
                writing_sections.get(title),
                answers,
                writing,
            )
            if writing_sections.get(title)
            else None,
            "speaking": build_speaking(
                exam_id,
                row,
                transcripts.get(title),
                speaking_audio,
                copy_assets,
            ),
        }
        stats: dict[str, dict] = {}
        for subject, payload in payloads.items():
            if not payload:
                continue
            write_json(exam_dir / f"{subject}.json", payload)
            stats[subject] = subject_stats(payload)
            totals["subject_count"] += 1
            totals["question_count"] += stats[subject]["question_objects"]
            totals["auto_graded"] += stats[subject]["auto_graded"]
            totals["manual_review"] += stats[subject]["manual_review"]
            totals["answer_missing"] += stats[subject]["answer_missing"]

        complete = (
            stats.get("reading", {}).get("question_objects", 0) >= 20
            and stats.get("listening", {}).get("question_objects", 0) >= 40
            and stats.get("writing", {}).get("question_objects", 0) >= 10
            and stats.get("speaking", {}).get("question_objects", 0) >= 9
        )
        manifest = {
            "schema_version": "1.1",
            "id": exam_id,
            "title": title,
            "subtitle": "2026 新托福真题在线练习",
            "source_kind": "real_exam",
            "source_practice_id": source_id,
            "source_folder": row.get("folder") or "",
            "source_pdf": row.get("reading_sources") or row.get("listening_sources") or "",
            "answer_pdf": row.get("primary_answer_file") or "",
            "answer_status": row.get("status") or "",
            "duplicate_status": "clear",
            "content_status": "complete" if complete else "partial",
            "publish_status": "published" if stats else "draft",
            "sort_key": exam_id,
            "notice": (
                "题面来自本地真题 OCR/转写；自动判分仅用于答案已可靠映射的题目。"
            ),
            "subjects": stats,
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }
        write_json(exam_dir / "manifest.json", manifest)
        report_exams.append(
            {
                "id": exam_id,
                "title": title,
                "content_status": manifest["content_status"],
                "subjects": {
                    subject: value["question_objects"]
                    for subject, value in stats.items()
                },
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "exam_count": len(report_exams),
        **dict(totals),
        "exams": report_exams,
    }
    write_json(DATA_ROOT / "import_report.json", report)
    (DATA_ROOT / "import_report.md").write_text(
        report_markdown(report), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
        help="Root of the 新托福资料 source library.",
    )
    parser.add_argument(
        "--no-copy-assets",
        action="store_true",
        help="Build JSON without copying compressed audio into static/toefl.",
    )
    args = parser.parse_args()
    report = run(args.source_root, copy_assets=not args.no_copy_assets)
    print(
        f"Imported {report['exam_count']} exams, "
        f"{report['subject_count']} subjects, "
        f"{report['question_count']} answerable question objects."
    )


if __name__ == "__main__":
    main()
