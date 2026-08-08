#!/usr/bin/env python3
"""Build six source-backed ETS official-practice packages for the v2 player."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from scripts.audit_toefl_official_materials import (
        DEFAULT_SOURCE,
        discover_sources,
        extract_pdf_text,
        sha256_file,
        slice_source_text,
    )
    from scripts.import_toefl_official_reading import (
        SOURCE_METADATA as READING_METADATA,
    )
    from scripts.import_toefl_official_reading import (
        extract_answer_maps,
        item_count,
        parse_reading_questions,
    )
    from scripts.toefl_official_assets import (
        AudioRef,
        collect_media,
        deduplicate_media,
    )
    from scripts.toefl_official_sections import (
        SectionExtract,
        SectionQuestion,
        extract_listening,
        extract_listening_og,
        extract_speaking,
        extract_speaking_og,
        extract_writing,
        extract_writing_og,
    )
except ModuleNotFoundError:
    from audit_toefl_official_materials import (
        DEFAULT_SOURCE,
        discover_sources,
        extract_pdf_text,
        sha256_file,
        slice_source_text,
    )
    from import_toefl_official_reading import (
        SOURCE_METADATA as READING_METADATA,
    )
    from import_toefl_official_reading import (
        extract_answer_maps,
        item_count,
        parse_reading_questions,
    )
    from toefl_official_assets import AudioRef, collect_media, deduplicate_media
    from toefl_official_sections import (
        SectionExtract,
        SectionQuestion,
        extract_listening,
        extract_listening_og,
        extract_speaking,
        extract_speaking_og,
        extract_writing,
        extract_writing_og,
    )


UTC = UTC
DEFAULT_DESTINATION = Path("data") / "toefl_practice_v2"
DEFAULT_MEDIA_DESTINATION = Path("static") / "toefl" / "v2"

OFFICIAL_METADATA = {
    "ets-practice-1": {
        "title": "ETS Student Practice Test 1",
        "date": "2025-11-15",
        "variant": "Practice 1",
    },
    "ets-practice-2": {
        "title": "ETS Student Practice Test 2",
        "date": "2025-11-15",
        "variant": "Practice 2",
    },
    "ets-practice-3": {
        "title": "ETS Teacher Practice Test 3",
        "date": "2025-12-17",
        "variant": "Practice 3",
    },
    "ets-practice-4": {
        "title": "ETS Teacher Practice Test 4",
        "date": "2025-12-17",
        "variant": "Practice 4",
    },
    "ets-practice-5": {
        "title": "ETS Teacher Practice Test 5",
        "date": "2025-12-18",
        "variant": "Practice 5",
    },
    "ets-og-chapter-6": {
        "title": "ETS Official Guide Chapter 6 Practice Test",
        "date": "2026-01-24",
        "variant": "OG Chapter 6",
    },
}

SUBJECT_ORDER = ("reading", "listening", "writing", "speaking")
COMPLETION_RE = re.compile(r"\b(?P<prefix>[A-Za-z]*)(?P<blank>(?:[_-](?:\s*[_-])*)+)(?![A-Za-z])")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def relative_source(path: Path, source_root: Path) -> str:
    return str(path.resolve().relative_to(source_root.resolve()))


def source_ref(
    path: Path,
    source_root: Path,
    *,
    module: str | None = None,
    question_number: int | None = None,
) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "path": relative_source(path, source_root),
        "sha256": sha256_file(path),
        "confidence": "source_exact",
    }
    if module:
        ref["module"] = module
    if question_number is not None:
        ref["question_number"] = question_number
    return ref


def ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return round(float(result.stdout.strip()), 3)


def safe_media_name(label: str, suffix: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return f"{stem}{suffix.lower()}"


def add_audio_asset(
    *,
    assets: list[dict[str, Any]],
    exam_id: str,
    slug: str,
    label: str,
    source_path: Path,
    source_root: Path,
    media_destination: Path,
    subject: str,
    module_id: str | None = None,
    publish: bool,
) -> tuple[str, float]:
    asset_id = f"{exam_id}:{subject}:audio:{label}"
    filename = safe_media_name(label, source_path.suffix)
    target = media_destination / slug / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)
    duration = ffprobe_duration(source_path)
    delivery: dict[str, Any] = {
        "storage_key": f"toefl/v2/{slug}/{filename}",
        "status": "published" if publish else "staged",
    }
    if publish:
        delivery["url"] = f"/static/toefl/v2/{slug}/{filename}"
    asset: dict[str, Any] = {
        "id": asset_id,
        "kind": "audio",
        "subject": subject,
        "source": {
            "path": relative_source(source_path, source_root),
            "sha256": sha256_file(source_path),
            "size_bytes": source_path.stat().st_size,
            "duration_seconds": duration,
        },
        "delivery": delivery,
    }
    if module_id:
        asset["module_id"] = module_id
    assets.append(asset)
    return asset_id, duration


def base_module(
    exam_id: str,
    subject: str,
    module: str,
    *,
    order: int,
    label: str,
    duration_seconds: int,
    group_ids: list[str],
    asset_ids: list[str],
    source_timing: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": f"{exam_id}:{subject}:{module}",
        "subject": subject,
        "module": module,
        "order": order,
        "label": label,
        "duration_seconds": duration_seconds,
        "navigation": {
            "back_policy": "disabled" if subject in {"listening", "speaking"} else "within_module",
            "review_policy": (
                "after_submit" if subject in {"listening", "speaking"} else "within_module"
            ),
        },
        "asset_ids": asset_ids,
        "group_ids": group_ids,
    }
    if source_timing:
        payload["timer_policy"] = "source"
    return payload


def completion_parts(
    passage: str, answers: list[str], start_number: int
) -> tuple[str, list[tuple[str, str]]]:
    matches = list(COMPLETION_RE.finditer(passage))
    if not matches:
        word_matches = list(re.finditer(r"\b[A-Za-z]+\b", passage))
        candidates: list[list[tuple[int, int]]] = []
        for answer in answers:
            normalized_answer = answer.casefold()
            rows = []
            for index, match in enumerate(word_matches):
                token = match.group().casefold()
                if not token or len(token) >= len(normalized_answer):
                    continue
                expected_prefix = normalized_answer[: len(token)]
                distance = sum(
                    left != right for left, right in zip(token, expected_prefix, strict=True)
                )
                if distance <= 1:
                    rows.append((index, distance))
            candidates.append(rows)

        paths: list[tuple[tuple[int, int, int], tuple[tuple[int, int], ...]]] = []

        def align(answer_index: int, previous: int, path: tuple[tuple[int, int], ...]) -> None:
            if answer_index == len(answers):
                positions = [item[0] for item in path]
                score = (
                    sum(len(word_matches[index].group()) for index in positions),
                    -sum(item[1] for item in path),
                    -(positions[-1] - positions[0]),
                )
                paths.append((score, path))
                return
            for index, distance in candidates[answer_index]:
                if index > previous:
                    align(answer_index + 1, index, (*path, (index, distance)))

        align(0, -1, ())
        if not paths:
            raise RuntimeError(f"Unable to recover completion markers for answers {answers!r}")
        best_score = max(item[0] for item in paths)
        best_paths = {item[1] for item in paths if item[0] == best_score}
        if len(best_paths) != 1:
            raise RuntimeError(f"Ambiguous completion recovery for answers {answers!r}")
        recovered = next(iter(best_paths))
        pieces = []
        values = []
        cursor = 0
        for answer_index, (word_index, _distance) in enumerate(recovered):
            match = word_matches[word_index]
            answer = answers[answer_index]
            prefix = answer[: len(match.group())]
            pieces.append(passage[cursor : match.start()])
            pieces.append(f"{{q{start_number + answer_index:02d}:{prefix}}}")
            values.append((prefix, answer[len(prefix) :]))
            cursor = match.end()
        pieces.append(passage[cursor:])
        return "".join(pieces), values
    if len(matches) != len(answers):
        raise RuntimeError(f"Completion markers {len(matches)} do not match answers {len(answers)}")
    pieces = []
    values = []
    cursor = 0
    for index, (match, answer) in enumerate(zip(matches, answers, strict=True)):
        prefix = match.group("prefix")
        answer_text = str(answer)
        suffix = (
            answer_text[len(prefix) :]
            if prefix and answer_text.casefold().startswith(prefix.casefold())
            else answer_text
        )
        pieces.append(passage[cursor : match.start()])
        pieces.append(f"{{q{start_number + index:02d}:{prefix}}}")
        values.append((prefix, suffix))
        cursor = match.end()
    pieces.append(passage[cursor:])
    return "".join(pieces), values


def build_reading(
    *,
    exam_id: str,
    source_id: str,
    source_path: Path,
    source_root: Path,
    full_text: str,
    scoped_text: str,
    modules: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    answers: list[dict[str, Any]],
) -> None:
    metadata = READING_METADATA[source_id]
    answer_maps = extract_answer_maps(source_id, full_text)
    legacy = parse_reading_questions(
        source_id,
        scoped_text,
        answer_maps,
        metadata["expected_modules"],
    )
    if item_count(legacy) != sum(metadata["expected_modules"].values()):
        raise RuntimeError(f"{source_id}: incomplete Reading extraction")

    by_module = {"m1": [], "m2": []}
    for item in legacy:
        module = re.search(r"_(m[12])_", item["id"]).group(1)
        by_module[module].append(item)

    sequence = 0
    for module_order, module in enumerate(("m1", "m2"), start=1):
        module_id = f"{exam_id}:reading:{module}"
        module_groups: list[str] = []
        group_order = 0
        index = 0
        rows = by_module[module]
        while index < len(rows):
            item = rows[index]
            group_order += 1
            group_id = f"{module_id}:g{group_order:02d}"
            group_question_ids: list[str] = []
            ref = source_ref(source_path, source_root, module=module)
            if item["response_type"] == "fill":
                start = int(item["number"])
                display, completion_values = completion_parts(
                    item["passage"]["text"], item["answer"]["words"], start
                )
                for offset, (prefix, suffix) in enumerate(completion_values):
                    number = start + offset
                    sequence += 1
                    question_id = f"{group_id}:q{number:02d}"
                    group_question_ids.append(question_id)
                    qref = source_ref(
                        source_path,
                        source_root,
                        module=module,
                        question_number=number,
                    )
                    questions.append(
                        {
                            "id": question_id,
                            "module_id": module_id,
                            "group_id": group_id,
                            "subject": "reading",
                            "number": number,
                            "sequence": sequence,
                            "response_type": "text",
                            "prompt": "Complete the missing letters in context.",
                            "options": [],
                            "input_config": {
                                "visible_prefix": prefix,
                                "input_kind": "missing_letters",
                            },
                            "content_status": "ready",
                            "grading_status": "auto",
                            "source_refs": [qref],
                        }
                    )
                    answers.append(
                        {
                            "question_id": question_id,
                            "response_type": "text",
                            "canonical_text": suffix,
                            "accepted_text": [suffix],
                            "grading_status": "auto",
                            "evidence": [qref],
                        }
                    )
                groups.append(
                    {
                        "id": group_id,
                        "module_id": module_id,
                        "subject": "reading",
                        "order": group_order,
                        "task_type": "complete_words",
                        "title": "Complete the Words",
                        "directive": item["directive"],
                        "stimulus": {"format": "inline_completion", "text": display},
                        "question_ids": group_question_ids,
                        "source_refs": [ref],
                    }
                )
                index += 1
                module_groups.append(group_id)
                continue

            passage = item["passage"]["text"]
            task_type = item["task_type"]
            run = []
            while index < len(rows):
                candidate = rows[index]
                if (
                    candidate["response_type"] != "mc"
                    or candidate["passage"]["text"] != passage
                    or candidate["task_type"] != task_type
                ):
                    break
                run.append(candidate)
                index += 1
            for candidate in run:
                number = int(candidate["number"])
                sequence += 1
                question_id = f"{group_id}:q{number:02d}"
                group_question_ids.append(question_id)
                qref = source_ref(
                    source_path,
                    source_root,
                    module=module,
                    question_number=number,
                )
                questions.append(
                    {
                        "id": question_id,
                        "module_id": module_id,
                        "group_id": group_id,
                        "subject": "reading",
                        "number": number,
                        "sequence": sequence,
                        "response_type": "mc",
                        "prompt": candidate["prompt"],
                        "options": candidate["options"],
                        "input_config": {"selection": "single"},
                        "content_status": "ready",
                        "grading_status": "auto",
                        "source_refs": [qref],
                    }
                )
                answers.append(
                    {
                        "question_id": question_id,
                        "response_type": "mc",
                        "correct_option_keys": candidate["answer"]["keys"],
                        "grading_status": "auto",
                        "evidence": [qref],
                    }
                )
            groups.append(
                {
                    "id": group_id,
                    "module_id": module_id,
                    "subject": "reading",
                    "order": group_order,
                    "task_type": task_type,
                    "title": clean_text(passage).split(". ", 1)[0][:80],
                    "directive": "Read the material and answer the questions.",
                    "stimulus": {"format": "rich_text", "text": passage},
                    "question_ids": group_question_ids,
                    "source_refs": [ref],
                }
            )
            module_groups.append(group_id)

        modules.append(
            base_module(
                exam_id,
                "reading",
                module,
                order=module_order,
                label=f"Reading Module {module[-1]}",
                duration_seconds=metadata["module_durations"][module],
                group_ids=module_groups,
                asset_ids=[f"{exam_id}:paper"],
                source_timing=True,
            )
        )


def ordered_bank_tokens(answer: str, bank: list[str], stimulus: str) -> list[str]:
    def normalized(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.casefold())

    target = normalized(answer)
    collapsed = re.sub(r"_{3,}(?:\s+_{3,})*", "\0", stimulus)
    fixed_parts = [normalized(part) for part in collapsed.split("\0")]
    variable_targets = []
    cursor = 0
    for index, fixed in enumerate(fixed_parts):
        if index == 0:
            # Some ETS frames include already-spoken context before the first
            # blank (for example, "Thanks.") that is not repeated in the key.
            cursor = len(fixed) if target.startswith(fixed) else 0
            continue
        if index == len(fixed_parts) - 1 and not fixed:
            variable_targets.append(target[cursor:])
            cursor = len(target)
            continue
        location = target.find(fixed, cursor)
        if location < 0:
            raise RuntimeError(f"Answer does not match response frame: {answer!r} / {stimulus!r}")
        variable_targets.append(target[cursor:location])
        cursor = location + len(fixed)
    if cursor != len(target):
        raise RuntimeError(f"Answer does not match response frame: {answer!r} / {stimulus!r}")

    normalized_bank = [normalized(token) for token in bank]
    candidates: set[tuple[int, ...]] = set()

    def fill_segment(
        segment_index: int,
        remainder: str,
        used: tuple[int, ...],
        selected: tuple[int, ...],
    ) -> None:
        if not remainder:
            if segment_index + 1 == len(variable_targets):
                candidates.add(selected)
            else:
                fill_segment(
                    segment_index + 1,
                    variable_targets[segment_index + 1],
                    used,
                    selected,
                )
            return
        for index, token in enumerate(normalized_bank):
            if index in used or not token or not remainder.startswith(token):
                continue
            fill_segment(
                segment_index,
                remainder[len(token) :],
                (*used, index),
                (*selected, index),
            )

    if variable_targets:
        fill_segment(0, variable_targets[0], (), ())
    if len(candidates) != 1:
        detail = "Unable" if not candidates else "Ambiguous"
        raise RuntimeError(f"{detail} word-bank alignment: {answer!r} / {stimulus!r} / {bank!r}")
    return [bank[index] for index in next(iter(candidates))]


def build_writing(
    *,
    exam_id: str,
    extracted: SectionExtract,
    source_path: Path,
    source_root: Path,
    modules: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    answers: list[dict[str, Any]],
) -> None:
    module_id = f"{exam_id}:writing:m1"
    module_group_ids = []
    sequence = 0
    task_groups = (
        (
            "build_sentence",
            "Build a Sentence",
            "Arrange the provided chunks to complete each response.",
        ),
        ("write_email", "Write an Email", "Write the requested email in complete sentences."),
        (
            "academic_discussion",
            "Academic Discussion",
            "Respond to the academic discussion in your own words.",
        ),
    )
    for group_order, (task, title, directive) in enumerate(task_groups, start=1):
        selected = [item for item in extracted.questions if item.task == task]
        if not selected:
            raise RuntimeError(f"Missing Writing task {task}")
        group_id = f"{module_id}:g{group_order:02d}"
        group_question_ids = []
        for item in selected:
            sequence += 1
            question_id = f"{group_id}:q{item.number:02d}"
            group_question_ids.append(question_id)
            ref = source_ref(
                source_path,
                source_root,
                module="m1",
                question_number=item.number,
            )
            if task == "build_sentence":
                bank = [option["text"] for option in item.options]
                ordered = ordered_bank_tokens(item.answer or "", bank, item.stimulus)
                questions.append(
                    {
                        "id": question_id,
                        "module_id": module_id,
                        "group_id": group_id,
                        "subject": "writing",
                        "number": item.number,
                        "sequence": sequence,
                        "response_type": "order",
                        "prompt": "Make an appropriate sentence for the situation.",
                        "context_sentence": f"{item.prompt}\nResponse frame: {item.stimulus}",
                        "options": [],
                        "input_config": {
                            "scramble_tokens": bank,
                            "expected_token_count": len(ordered),
                            "keyboard_reorder": True,
                        },
                        "content_status": "ready",
                        "grading_status": "auto",
                        "source_refs": [ref],
                    }
                )
                answers.append(
                    {
                        "question_id": question_id,
                        "response_type": "order",
                        "ordered_tokens": ordered,
                        "grading_status": "auto",
                        "evidence": [ref],
                    }
                )
            else:
                questions.append(
                    {
                        "id": question_id,
                        "module_id": module_id,
                        "group_id": group_id,
                        "subject": "writing",
                        "number": item.number,
                        "sequence": sequence,
                        "response_type": "free_text",
                        "prompt": item.prompt,
                        "options": [],
                        "input_config": {
                            "minimum_words": 100 if task == "academic_discussion" else 1
                        },
                        "content_status": "ready",
                        "grading_status": "manual",
                        "source_refs": [ref],
                    }
                )
        groups.append(
            {
                "id": group_id,
                "module_id": module_id,
                "subject": "writing",
                "order": group_order,
                "task_type": task,
                "title": title,
                "directive": directive,
                "stimulus": None,
                "question_ids": group_question_ids,
                "source_refs": [source_ref(source_path, source_root, module="m1")],
            }
        )
        module_group_ids.append(group_id)
    modules.append(
        base_module(
            exam_id,
            "writing",
            "m1",
            order=1,
            label="Writing",
            duration_seconds=1440,
            group_ids=module_group_ids,
            asset_ids=[f"{exam_id}:paper"],
        )
    )


def practice_media_index(source) -> dict[tuple, AudioRef]:
    refs, unknown = collect_media(list(source.media_paths))
    if unknown:
        raise RuntimeError(
            f"{source.source_id}: unrecognized media: " + ", ".join(path.name for path in unknown)
        )
    return deduplicate_media(refs)


def listening_ref_for_questions(
    media: dict[tuple, AudioRef], module: str, task: str, numbers: tuple[int, ...]
) -> AudioRef:
    key = ("listening", module, task, "questions", numbers)
    if key not in media:
        raise RuntimeError(f"Missing Listening media {key}")
    return media[key]


def build_listening(
    *,
    exam_id: str,
    slug: str,
    extracted: SectionExtract,
    source_path: Path,
    source_root: Path,
    media: dict[tuple, AudioRef],
    media_destination: Path,
    modules: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    answers: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    publish: bool,
    og: bool,
) -> None:
    sequence = 0
    for module_order, module in enumerate(("m1", "m2"), start=1):
        module_id = f"{exam_id}:listening:{module}"
        module_questions = [item for item in extracted.questions if item.module == module]
        grouped: list[tuple[AudioRef, list[SectionQuestion]]] = []
        if og:
            by_label: dict[str, list[SectionQuestion]] = {}
            for item in module_questions:
                by_label.setdefault(item.media_label, []).append(item)
            for label, items in by_label.items():
                number = int(label.rsplit(" ", 1)[-1])
                ref = media[("listening", None, "og_track", "questions", (number,))]
                grouped.append((ref, items))
        else:
            available = [
                ref
                for ref in media.values()
                if ref.subject == "listening" and ref.module == module and ref.role == "questions"
            ]
            for ref in sorted(available, key=lambda item: item.numbers):
                items = [item for item in module_questions if item.number in ref.numbers]
                if items:
                    if any(item.task != ref.task for item in items):
                        raise RuntimeError(f"Listening task/media mismatch for {ref.path}")
                    grouped.append((ref, items))
        covered = [item.number for _ref, items in grouped for item in items]
        expected = [item.number for item in module_questions]
        if Counter(covered) != Counter(expected):
            raise RuntimeError(f"{slug} {module}: Listening media coverage mismatch")

        module_group_ids = []
        module_asset_ids = []
        total_duration = 0.0
        for group_order, (media_ref, items) in enumerate(grouped, start=1):
            group_id = f"{module_id}:g{group_order:02d}"
            asset_id, duration = add_audio_asset(
                assets=assets,
                exam_id=exam_id,
                slug=slug,
                label=f"{module}-g{group_order:02d}",
                source_path=media_ref.path,
                source_root=source_root,
                media_destination=media_destination,
                subject="listening",
                module_id=module_id,
                publish=publish,
            )
            total_duration += duration
            module_asset_ids.append(asset_id)
            group_question_ids = []
            for item in items:
                sequence += 1
                question_id = f"{group_id}:q{item.number:02d}"
                group_question_ids.append(question_id)
                refs = [
                    source_ref(
                        source_path,
                        source_root,
                        module=module,
                        question_number=item.number,
                    ),
                    source_ref(
                        media_ref.path,
                        source_root,
                        module=module,
                        question_number=item.number,
                    ),
                ]
                questions.append(
                    {
                        "id": question_id,
                        "module_id": module_id,
                        "group_id": group_id,
                        "subject": "listening",
                        "number": item.number,
                        "sequence": sequence,
                        "response_type": "mc",
                        "prompt": re.sub(r"(?i)^Play track \d+\.\s*", "", item.prompt),
                        "options": item.options,
                        "input_config": {"selection": "single"},
                        "content_status": "ready",
                        "grading_status": "auto",
                        "source_refs": refs,
                    }
                )
                answers.append(
                    {
                        "question_id": question_id,
                        "response_type": "mc",
                        "correct_option_keys": [item.answer],
                        "grading_status": "auto",
                        "evidence": refs,
                    }
                )
            task = items[0].task
            groups.append(
                {
                    "id": group_id,
                    "module_id": module_id,
                    "subject": "listening",
                    "order": group_order,
                    "task_type": task,
                    "title": clean_text(items[0].stimulus) or task.replace("_", " ").title(),
                    "directive": "Play the official audio once, then answer this group.",
                    "stimulus": {
                        "format": "audio",
                        "asset_id": asset_id,
                        "playback_scope": "group",
                        "transcript_policy": "review_after_submit",
                    },
                    "question_ids": group_question_ids,
                    "source_refs": [
                        source_ref(source_path, source_root, module=module),
                        source_ref(media_ref.path, source_root, module=module),
                    ],
                }
            )
            module_group_ids.append(group_id)
        modules.append(
            base_module(
                exam_id,
                "listening",
                module,
                order=module_order,
                label=f"Listening Module {module[-1]}",
                duration_seconds=max(0, round(total_duration)),
                group_ids=module_group_ids,
                asset_ids=module_asset_ids,
            )
        )


def speaking_media_ref(
    media: dict[tuple, AudioRef], item: SectionQuestion, *, og: bool
) -> AudioRef:
    if og:
        label, raw_number = item.media_label.split()
        number = int(raw_number)
        task = "og_track" if label == "track" else "interview"
        return media[("speaking", None, task, "questions", (number,))]
    source_number = item.number if item.module == "m1" else item.number
    task = "listen_repeat" if item.module == "m1" else "interview"
    return media[("speaking", None, task, "questions", (source_number,))]


def build_speaking(
    *,
    exam_id: str,
    slug: str,
    extracted: SectionExtract,
    source_path: Path,
    source_root: Path,
    media: dict[tuple, AudioRef],
    media_destination: Path,
    modules: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    publish: bool,
    og: bool,
) -> None:
    sequence = 0
    for module_order, module in enumerate(("m1", "m2"), start=1):
        module_id = f"{exam_id}:speaking:{module}"
        selected = [item for item in extracted.questions if item.module == module]
        expected = 7 if module == "m1" else 4
        if len(selected) != expected:
            raise RuntimeError(f"{slug} {module}: expected {expected} Speaking questions")
        module_group_ids = []
        module_asset_ids = []
        for group_order, item in enumerate(selected, start=1):
            number = item.number if og or module == "m1" else item.number + 7
            sequence += 1
            group_id = f"{module_id}:g{group_order:02d}"
            question_id = f"{group_id}:q{number:02d}"
            media_ref = speaking_media_ref(media, item, og=og)
            asset_id, duration = add_audio_asset(
                assets=assets,
                exam_id=exam_id,
                slug=slug,
                label=f"speaking-q{number:02d}",
                source_path=media_ref.path,
                source_root=source_root,
                media_destination=media_destination,
                subject="speaking",
                publish=publish,
            )
            module_asset_ids.append(asset_id)
            refs = [
                source_ref(
                    source_path,
                    source_root,
                    module=module,
                    question_number=number,
                ),
                source_ref(
                    media_ref.path,
                    source_root,
                    module=module,
                    question_number=number,
                ),
            ]
            task_type = "listen_and_repeat" if module == "m1" else "take_an_interview"
            groups.append(
                {
                    "id": group_id,
                    "module_id": module_id,
                    "subject": "speaking",
                    "order": group_order,
                    "task_type": task_type,
                    "title": "Listen and Repeat" if module == "m1" else "Take an Interview",
                    "directive": "Listen once; recording starts immediately after the prompt.",
                    "stimulus": {
                        "format": "audio_cue",
                        "asset_id": asset_id,
                        "cue_start_seconds": 0,
                        "cue_end_seconds": duration,
                        "alignment_confidence": 1.0,
                    },
                    "question_ids": [question_id],
                    "source_refs": refs,
                }
            )
            questions.append(
                {
                    "id": question_id,
                    "module_id": module_id,
                    "group_id": group_id,
                    "subject": "speaking",
                    "number": number,
                    "sequence": sequence,
                    "response_type": "recording",
                    "prompt": "Listen to the official source audio and respond.",
                    "context_sentence": item.prompt,
                    "options": [],
                    "input_config": {
                        "preparation_seconds": 0,
                        "response_seconds": item.response_seconds or (12 if module == "m1" else 45),
                        "maximum_takes_test_mode": 1,
                        "local_preview_practice_mode": True,
                    },
                    "content_status": "ready",
                    "grading_status": "manual",
                    "source_refs": refs,
                }
            )
            module_group_ids.append(group_id)
        modules.append(
            base_module(
                exam_id,
                "speaking",
                module,
                order=module_order,
                label="Listen and Repeat" if module == "m1" else "Take an Interview",
                duration_seconds=180 if module == "m1" else 300,
                group_ids=module_group_ids,
                asset_ids=module_asset_ids,
            )
        )


def paper_asset(exam_id: str, source_path: Path, source_root: Path) -> dict[str, Any]:
    return {
        "id": f"{exam_id}:paper",
        "kind": "paper_pdf",
        "subject": "exam",
        "source": {
            "path": relative_source(source_path, source_root),
            "sha256": sha256_file(source_path),
            "size_bytes": source_path.stat().st_size,
        },
        "delivery": {
            "storage_key": f"toefl/v2/sources/{source_path.name}",
            "status": "local_source",
        },
    }


def build_source(
    source,
    *,
    source_root: Path,
    destination: Path,
    media_destination: Path,
    publish: bool,
) -> dict[str, Any]:
    slug = source.source_id
    exam_id = f"toefl:{slug}"
    metadata = OFFICIAL_METADATA[slug]
    full_text = extract_pdf_text(source.pdf_path)
    scoped_text = slice_source_text(source, full_text)
    media = practice_media_index(source)
    og = slug == "ets-og-chapter-6"
    listening = extract_listening_og(full_text, scoped_text) if og else extract_listening(full_text)
    writing = extract_writing_og(full_text, scoped_text) if og else extract_writing(full_text)
    speaking = extract_speaking_og(full_text) if og else extract_speaking(full_text)
    if listening.warnings or writing.warnings or speaking.warnings:
        raise RuntimeError(
            f"{slug}: extraction warnings: "
            + "; ".join(listening.warnings + writing.warnings + speaking.warnings)
        )

    modules: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    answer_rows: list[dict[str, Any]] = []
    assets = [paper_asset(exam_id, source.pdf_path, source_root)]

    build_reading(
        exam_id=exam_id,
        source_id=slug,
        source_path=source.pdf_path,
        source_root=source_root,
        full_text=full_text,
        scoped_text=scoped_text,
        modules=modules,
        groups=groups,
        questions=questions,
        answers=answer_rows,
    )
    build_listening(
        exam_id=exam_id,
        slug=slug,
        extracted=listening,
        source_path=source.pdf_path,
        source_root=source_root,
        media=media,
        media_destination=media_destination,
        modules=modules,
        groups=groups,
        questions=questions,
        answers=answer_rows,
        assets=assets,
        publish=publish,
        og=og,
    )
    build_speaking(
        exam_id=exam_id,
        slug=slug,
        extracted=speaking,
        source_path=source.pdf_path,
        source_root=source_root,
        media=media,
        media_destination=media_destination,
        modules=modules,
        groups=groups,
        questions=questions,
        assets=assets,
        publish=publish,
        og=og,
    )
    build_writing(
        exam_id=exam_id,
        extracted=writing,
        source_path=source.pdf_path,
        source_root=source_root,
        modules=modules,
        groups=groups,
        questions=questions,
        answers=answer_rows,
    )

    subject_counts = Counter(item["subject"] for item in questions)
    expected = {
        "reading": 50 if og else 40,
        "listening": 47 if og else 34,
        "speaking": 11,
        "writing": 12,
    }
    if dict(subject_counts) != expected:
        raise RuntimeError(f"{slug}: subject counts {dict(subject_counts)} != {expected}")
    generated_at = datetime.now(UTC).isoformat()
    content = {
        "schema_version": "2.0.0",
        "exam": {
            "id": exam_id,
            "title": metadata["title"],
            "date": metadata["date"],
            "variant": metadata["variant"],
            "source_kind": "official_practice",
            "source_folder": str(Path(relative_source(source.pdf_path, source_root)).parent),
            "expected_question_count": len(questions),
            "availability_status": "published" if publish else "reviewed",
        },
        "assets": assets,
        "modules": sorted(
            modules, key=lambda item: (SUBJECT_ORDER.index(item["subject"]), item["order"])
        ),
        "groups": groups,
        "questions": questions,
    }
    answer_key = {
        "schema_version": "2.0.0",
        "exam_id": exam_id,
        "answers": answer_rows,
        "blocked": [],
    }
    manifest = {
        "schema_version": "2.0.0",
        "exam_id": exam_id,
        "generated_at": generated_at,
        "generator": "scripts/build_toefl_official_v2.py",
        "source_root_portability": "All source paths are relative to the configured source root.",
        "counts": {
            "questions": len(questions),
            "auto": sum(item["grading_status"] == "auto" for item in questions),
            "manual": sum(item["grading_status"] == "manual" for item in questions),
            "blocked": 0,
            "by_subject": expected,
        },
        "quality": {
            "validation_status": "pending",
            "publish_status": "published" if publish else "ready",
            "subject_reviews": {subject: "pending" for subject in SUBJECT_ORDER},
            "review_basis": "Official PDF text, embedded answer tables, and question-scoped ETS media were cross-checked by the deterministic importer.",
            "release_authorization": {
                "status": "owner_authorized",
                "scope": list(SUBJECT_ORDER),
                "basis": "The owner explicitly requested completion, v2 conversion, and production release on 2026-08-07.",
            },
            "speaking_timing_policy": {
                "preparation_seconds": 0,
                "listen_and_repeat_response_seconds": "source-specific 8/10/12 seconds when stated; otherwise conservative 12 seconds",
                "take_an_interview_response_seconds": 45,
                "section_duration_seconds": 480,
            },
            "blocking_reasons": [],
            "known_blocked_question_ids": [],
        },
    }
    qa_report = {
        "schema_version": "1.0.0",
        "exam_id": exam_id,
        "generated_at": generated_at,
        "status": "pass",
        "checks": [
            {"id": "atomic-counts", "status": "pass", "detail": str(expected)},
            {
                "id": "answer-separation",
                "status": "pass",
                "detail": "Objective answers are private.",
            },
            {
                "id": "media-coverage",
                "status": "pass",
                "detail": "Every Listening group and Speaking item has one source-exact ETS asset.",
            },
            {
                "id": "source-traceability",
                "status": "pass",
                "detail": "All content and media carry source-relative SHA-256 references.",
            },
        ],
    }

    target = destination / slug
    target.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("content.json", content),
        ("answer_key.json", answer_key),
        ("manifest.json", manifest),
        ("qa_report.json", qa_report),
    ):
        (target / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return {"slug": slug, "questions": len(questions), "assets": len(assets)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--media-destination", type=Path, default=DEFAULT_MEDIA_DESTINATION)
    parser.add_argument(
        "--source-id", action="append", choices=sorted(OFFICIAL_METADATA), dest="source_ids"
    )
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    source_root = args.source.expanduser().resolve()
    selected = set(args.source_ids or OFFICIAL_METADATA)
    sources = {source.source_id: source for source in discover_sources(source_root)}
    results = []
    for source_id in sorted(selected):
        source = sources[source_id]
        if not source.pdf_path.is_file():
            raise RuntimeError(f"Missing source PDF: {source.pdf_path}")
        results.append(
            build_source(
                source,
                source_root=source_root,
                destination=args.destination.resolve(),
                media_destination=args.media_destination.resolve(),
                publish=args.publish,
            )
        )
    print(json.dumps({"built": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
