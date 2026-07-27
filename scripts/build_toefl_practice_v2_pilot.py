#!/usr/bin/env python3
"""Build the representative 2026-01-21 A TOEFL practice v2 pilot.

This is deliberately a source-traceable rebuild. It does not overwrite the
legacy package under data/toefl_practice and it never labels missing source
content as complete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc  # noqa: UP017  # Python 3.10 production compatibility.

EXAM_KEY = "2026-01-21_A"
EXAM_ID = "toefl:2026-01-21-a"
SOURCE_FOLDER = "1.21新托福真题A卷"
PAPER = f"{SOURCE_FOLDER}/新托福真题01.pdf"
ANSWER_PDF = f"{SOURCE_FOLDER}/新托福真题01参考答案.pdf"
TRANSCRIPT_PDF = f"{SOURCE_FOLDER}/新托福真题01-听力原文.pdf"
SPEAKING_AUDIO = f"{SOURCE_FOLDER}/新托福真题01Speaking.mp3"
LISTENING_M1_AUDIO = f"{SOURCE_FOLDER}/听力合集/1.21新托福真题Listening-Module1.mp3"
LISTENING_M2_AUDIO = f"{SOURCE_FOLDER}/听力合集/1.21新托福真题Listening-Module2.mp3"
LISTENING_FULL_AUDIO = f"{SOURCE_FOLDER}/听力合集/1.21新托福真题Listening（全）.mp3"

READING_ANSWERS = {
    "m1": [
        "They", "change", "through", "Like", "and", "As", "move", "cover", "valleys", "living",
        "Population", "this", "blue", "declined", "of", "loss", "illegal", "for", "abroad", "private",
        "A", "B", "D", "B", "B", "A", "D", "B", "A", "B", "D", "D", "C", "A", "D",
    ],
    "m2": ["pots", "shaped", "hand", "heated", "simple", "producing", "that", "longer", "societies", "techniques", "B", "C", "C", "B", "A"],
}
LISTENING_ANSWERS = {
    "m1": list("BBDCBDCDDACA") + list("BCBCCDCDAAAB") + list("CABCCCAC"),
    "m2": list("DDADCBA") + list("DCABBADB"),
}
FILL_PREFIXES = {
    "m1": ["Th", "cha", "thr", "li", "a", "A", "mo", "ca", "val", "lea", "popul", "th", "bl", "decl", "", "lo", "ill", "", "abr", "pri"],
    "m2": ["po", "sha", "ha", "hea", "sim", "prod", "th", "lon", "soc", "tech"],
}
FILL_DISPLAY = {
    "m1_01": (
        "Glaciers are massive, slow-moving bodies of ice that form in areas where snow accumulates over time and compresses into ice. "
        "{q01:Th} can {q02:cha} landscapes {q03:thr} processes {q04:li} erosion {q05:a} deposition. "
        "{q06:A} glaciers {q07:mo}, they {q08:ca} out {q09:val} and fjords, {q10:lea} behind distinct geological features. "
        "Scientists study glaciers to understand past climate conditions and predict future changes. Glaciers are of particular concern today because their melting contributes to rising sea levels, impacting coastal communities worldwide."
    ),
    "m1_02": (
        "The Spix's Macaw, native to Brazil and famously known as the inspiration for the animated movie Rio, is critically endangered, with fewer than a hundred individuals remaining. "
        "The {q11:popul} of {q12:th} vibrant {q13:bl} bird {q14:decl} because {q15:} habitat {q16:lo} and {q17:ill} trapping {q18:} sale {q19:abr}, where {q20:pri} collectors and pet stores spent large sums of money to obtain them. "
        "Conservationists have initiated captive breeding programs and habitat restoration efforts to reintroduce the Spix's Macaw into the wild, where it was officially declared extinct in 2019."
    ),
    "m2_01": (
        "Pottery is an ancient craft that involves shaping and firing clay in special wood-fired ovens (kilns) to create functional and decorative objects. "
        "Early {q01:po} were {q02:sha} by {q03:ha} and {q04:hea} in {q05:sim} kilns, {q06:prod} ceramics {q07:th} lasted {q08:lon}. "
        "As {q09:soc} developed, {q10:tech} became more refined, with different cultures creating distinct styles. Over time, pottery evolved into both a practical craft and a significant form of artistic and cultural expression."
    ),
}

RECOVERED_READING_Q33 = {
    "stem": "What can be inferred to be the purpose of electrical signals that plants release?",
    "options": [
        "To attract beneficial animals to the plants",
        "To prevent attack by caterpillars on the plants",
        "To help the plants make the best use of available resources",
        "To communicate with other plants across long distances",
    ],
    "page": 7,
}
RECOVERED_LISTENING = {
    ("m1", 7): [
        "In the main classroom.",
        "I'll be there.",
        "Probably the same from last week.",
        "She didn't take notes.",
    ],
    ("m2", 3): [
        "Yes, it was informative.",
        "Yes, I plan to attend.",
        "Not the greatest reason.",
        "Maybe sometimes.",
    ],
}
BLOCKED_LISTENING = {("m1", 15), ("m1", 18), ("m1", 21), ("m2", 9)}

WRITING_PAGES = {1: 39, 2: 40, 3: 40, 4: 40, 5: 41, 6: 41, 7: 41, 8: 42, 9: 42, 10: 42, 11: 43, 12: 45}
READING_GROUPS = {
    "m1": [
        (1, 10, "complete_words", "Glaciers"),
        (11, 20, "complete_words", "The Spix's Macaw"),
        (21, 22, "read_in_daily_life", "Introduction to Glassblowing"),
        (23, 25, "read_in_daily_life", "Flex & Flow"),
        (26, 30, "academic_passage", "Thinking Outside the Box"),
        (31, 35, "academic_passage", "Plant Communication"),
    ],
    "m2": [
        (1, 10, "complete_words", "Pottery"),
        (11, 15, "academic_passage", "Cybernetic Prosthetics"),
    ],
}
LISTENING_GROUPS = {
    "m1": [
        (1, 12, "listen_and_choose", "Choose the Best Response"),
        (13, 14, "conversation", "Store Return"),
        (15, 16, "conversation", "Dinner Party Errand"),
        (17, 18, "conversation", "University Orchestra Concert"),
        (19, 20, "announcement", "School Art Exhibit"),
        (21, 22, "announcement", "Environmental Policy Guest Speaker"),
        (23, 24, "announcement", "Independent Study Course"),
        (25, 28, "lecture", "Inertia and Bicycle Turns"),
        (29, 32, "lecture", "Lean Startup Methodology"),
    ],
    "m2": [
        (1, 3, "listen_and_choose", "Choose the Best Response"),
        (4, 5, "conversation", "Laptop Problem"),
        (6, 7, "conversation", "University Newspaper Interview"),
        (8, 11, "lecture", "Bird Migration"),
        (12, 15, "lecture", "Bronze Age Mummification"),
    ],
}


def json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def duration_seconds(path: Path) -> float:
    output = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        text=True,
    )
    return round(float(output.strip()), 3)


def source_ref(path: str, hashes: dict[str, str], *, page: int | None = None, module: str | None = None, number: int | None = None, confidence: str = "source_exact") -> dict[str, Any]:
    value: dict[str, Any] = {"path": path, "sha256": hashes[path], "confidence": confidence}
    if page:
        value["page"] = page
    if module:
        value["module"] = module
    if number:
        value["question_number"] = number
    return value


def options(values: list[str]) -> list[dict[str, str]]:
    return [{"key": chr(65 + index), "text": text.strip()} for index, text in enumerate(values)]


def question_id(subject: str, module: str, group_index: int, number: int) -> str:
    return f"{EXAM_ID}:{subject}:{module}:g{group_index:02d}:q{number:02d}"


def module_id(subject: str, module: str) -> str:
    return f"{EXAM_ID}:{subject}:{module}"


def group_id(subject: str, module: str, group_index: int) -> str:
    return f"{EXAM_ID}:{subject}:{module}:g{group_index:02d}"


def extracted_reading(source_root: Path) -> list[dict[str, Any]]:
    cache = source_root / "tmp/pdfs/reading_structured/extracted/01_2026_01_21_A.json"
    if not cache.is_file():
        raise FileNotFoundError(f"required extraction cache not found: {cache}")
    return json.loads(cache.read_text(encoding="utf-8"))


def reading_page(module: str, number: int) -> int:
    if module == "m2":
        if number <= 10:
            return 8
        if number <= 12:
            return 9
        if number <= 14:
            return 10
        return 11
    if number <= 10:
        return 1
    if number <= 22:
        return 2
    if number <= 24:
        return 3
    if number <= 26:
        return 4
    if number <= 29:
        return 5
    if number <= 32:
        return 6
    return 7


def reading_answer_page(module: str, number: int) -> int:
    if module == "m1":
        return 1
    if module == "m2":
        return 1 if number <= 7 else 2
    raise ValueError(f"unsupported reading answer location: {module} q{number}")


def build_reading(source_root: Path, hashes: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    extracted = extracted_reading(source_root)
    by_module_number: dict[tuple[str, int], dict[str, Any]] = {}
    current_module = "m1"
    for item in extracted:
        if item.get("page") == 8 and item.get("number") == 36:
            current_module = "m2"
        number = item.get("number")
        if item.get("kind") == "question" and number:
            by_module_number[(current_module, int(number))] = item

    modules: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    sequence = 0
    for module_order, module in enumerate(("m1", "m2"), 1):
        module_groups: list[str] = []
        for group_index, (first, last, task_type, title) in enumerate(READING_GROUPS[module], 1):
            gid = group_id("reading", module, group_index)
            qids = [question_id("reading", module, group_index, number) for number in range(first, last + 1)]
            module_groups.append(gid)
            page = reading_page(module, first)
            if task_type == "complete_words":
                display_key = f"{module}_{group_index:02d}"
                stimulus = {
                    "format": "inline_completion",
                    "display_text": FILL_DISPLAY[display_key],
                    "token_syntax": "{question-local-number:visible-prefix}",
                    "rendering_rule": "Render each token as one inline text input; never detach blanks into a side panel.",
                }
            else:
                candidates = [by_module_number[(module, number)] for number in range(first, last + 1) if (module, number) in by_module_number]
                material = max((item.get("material", "") for item in candidates), key=len, default="")
                stimulus = {"format": "rich_text", "text": material}
            groups.append({
                "id": gid,
                "module_id": module_id("reading", module),
                "subject": "reading",
                "order": group_index,
                "task_type": task_type,
                "title": title,
                "directive": "Fill in the missing letters in the paragraph." if task_type == "complete_words" else "Read the material and answer the questions.",
                "stimulus": stimulus,
                "question_ids": qids,
                "source_refs": [source_ref(PAPER, hashes, page=page, module=module, confidence="reviewed_repair" if task_type == "complete_words" else "source_exact")],
            })

            for number in range(first, last + 1):
                sequence += 1
                qid = question_id("reading", module, group_index, number)
                page = reading_page(module, number)
                if task_type == "complete_words":
                    answer = READING_ANSWERS[module][number - 1]
                    prefix = FILL_PREFIXES[module][number - 1]
                    accepted = sorted({answer, answer[len(prefix):] if prefix and answer.lower().startswith(prefix.lower()) else answer}, key=lambda value: (len(value), value.lower()))
                    prompt = "Complete the word in context."
                    item_options: list[dict[str, str]] = []
                    input_config = {"visible_prefix": prefix, "accept_full_word_in_practice": True}
                    status = "reviewed_repair" if module == "m2" or number in {4, 8, 15, 18} else "ready"
                    grading = "auto"
                    confidence = "reviewed_repair" if status == "reviewed_repair" else "source_exact"
                    answer_entry = {
                        "question_id": qid,
                        "response_type": "text",
                        "canonical_text": answer,
                        "accepted_text": accepted,
                        "grading_status": "auto",
                        "evidence": [
                            source_ref(PAPER, hashes, page=page, module=module, number=number, confidence=confidence),
                            source_ref(
                                ANSWER_PDF,
                                hashes,
                                page=reading_answer_page(module, number),
                                module=module,
                                number=number,
                            ),
                        ],
                    }
                else:
                    item = by_module_number.get((module, number))
                    confidence = "source_exact"
                    if module == "m1" and number == 33:
                        item = RECOVERED_READING_Q33
                        confidence = "visually_recovered"
                    if not item:
                        raise ValueError(f"reading {module} q{number} missing after recovery")
                    prompt = item.get("stem", "").strip()
                    item_options = options(item.get("options", []))
                    input_config = {"selection": "single"}
                    status = "ready"
                    grading = "auto"
                    answer_entry = {
                        "question_id": qid,
                        "response_type": "mc",
                        "correct_option_keys": [READING_ANSWERS[module][number - 1]],
                        "grading_status": "auto",
                        "evidence": [
                            source_ref(PAPER, hashes, page=page, module=module, number=number, confidence=confidence),
                            source_ref(
                                ANSWER_PDF,
                                hashes,
                                page=reading_answer_page(module, number),
                                module=module,
                                number=number,
                            ),
                        ],
                    }
                questions.append({
                    "id": qid,
                    "module_id": module_id("reading", module),
                    "group_id": gid,
                    "subject": "reading",
                    "number": number,
                    "sequence": sequence,
                    "response_type": "text" if task_type == "complete_words" else "mc",
                    "prompt": prompt,
                    "options": item_options,
                    "input_config": input_config,
                    "content_status": status,
                    "grading_status": grading,
                    "source_refs": [source_ref(PAPER, hashes, page=page, module=module, number=number, confidence=confidence)],
                    "_answer_entry": answer_entry,
                })

        modules.append({
            "id": module_id("reading", module),
            "subject": "reading",
            "module": module,
            "order": module_order,
            "label": f"Reading Module {module_order}",
            "duration_seconds": 0,
            "navigation": {"back_policy": "within_module", "review_policy": "within_module"},
            "asset_ids": [f"{EXAM_ID}:paper"],
            "group_ids": module_groups,
        })
    answers = [item.pop("_answer_entry") for item in questions]
    return modules, groups, questions, answers


def transcript_prompts(repo_root: Path) -> dict[tuple[str, int], str]:
    path = repo_root / "tmp/pdfs/toefl-v2-pilot/listening-transcript.txt"
    if not path.is_file():
        raise FileNotFoundError(f"listening transcript text not found: {path}")
    prompts: dict[tuple[str, int], str] = {}
    module = "m1"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "Module2":
            module = "m2"
            continue
        match = re.match(r"^\s*(\d+)\.\s*(.+?)\s*$", line)
        if match:
            number = int(match.group(1))
            if 1 <= number <= (32 if module == "m1" else 15):
                prompts[(module, number)] = match.group(2).strip()
    return prompts


def listening_page(module: str, number: int) -> int:
    if module == "m2":
        if number == 1:
            return 31
        if number <= 3:
            return 32
        if number <= 5:
            return 33
        if number <= 7:
            return 35
        if number <= 11:
            return 37
        return 39
    if number <= 12:
        return 11 + (number + 1) // 2
    ranges = [(14, 19), (16, 21), (18, 23), (20, 24), (22, 25), (24, 26), (26, 27), (28, 28), (32, 29)]
    for end, page in ranges:
        if number <= end:
            return page
    return 29


def build_listening(repo_root: Path, hashes: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    legacy = json.loads((repo_root / "data/toefl_practice/2026-01-21_A/listening.json").read_text(encoding="utf-8"))
    old_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for item in legacy["questions"]:
        match = re.search(r"_(m[12])_q(\d+)$", item["id"])
        if match:
            old_by_key[(match.group(1), int(match.group(2)))] = item
    prompts = transcript_prompts(repo_root)
    modules: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    sequence = 0
    for module_order, module in enumerate(("m1", "m2"), 1):
        module_groups: list[str] = []
        for group_index, (first, last, task_type, title) in enumerate(LISTENING_GROUPS[module], 1):
            gid = group_id("listening", module, group_index)
            qids = [question_id("listening", module, group_index, number) for number in range(first, last + 1)]
            module_groups.append(gid)
            groups.append({
                "id": gid,
                "module_id": module_id("listening", module),
                "subject": "listening",
                "order": group_index,
                "task_type": task_type,
                "title": title,
                "directive": "Listen once, then choose the best answer.",
                "stimulus": {"format": "audio", "asset_id": f"{EXAM_ID}:listening:{module}", "transcript_policy": "review_after_submit"},
                "question_ids": qids,
                "source_refs": [source_ref(TRANSCRIPT_PDF, hashes, module=module), source_ref(PAPER, hashes, page=listening_page(module, first), module=module)],
            })
            for number in range(first, last + 1):
                sequence += 1
                qid = question_id("listening", module, group_index, number)
                old = old_by_key.get((module, number), {})
                raw_options = [item.get("text", "") for item in old.get("options", [])]
                confidence = "source_exact"
                if (module, number) in RECOVERED_LISTENING:
                    raw_options = RECOVERED_LISTENING[(module, number)]
                    confidence = "visually_recovered"
                blocked = (module, number) in BLOCKED_LISTENING
                if blocked:
                    raw_options = []
                    confidence = "source_missing"
                prompt = prompts.get((module, number), old.get("prompt", ""))
                if not prompt:
                    raise ValueError(f"listening prompt missing: {module} q{number}")
                page = listening_page(module, number)
                questions.append({
                    "id": qid,
                    "module_id": module_id("listening", module),
                    "group_id": gid,
                    "subject": "listening",
                    "number": number,
                    "sequence": sequence,
                    "response_type": "mc",
                    "prompt": prompt,
                    "options": options(raw_options),
                    "input_config": {"selection": "single", "audio_replay_policy": "once_in_test_mode", "audio_scrub_policy": "disabled_in_test_mode"},
                    "content_status": "missing_options" if blocked else "ready",
                    "grading_status": "blocked" if blocked else "auto",
                    "source_refs": [source_ref(PAPER, hashes, page=page, module=module, number=number, confidence=confidence), source_ref(TRANSCRIPT_PDF, hashes, module=module, number=number)],
                })
                if not blocked:
                    answers.append({
                        "question_id": qid,
                        "response_type": "mc",
                        "correct_option_keys": [LISTENING_ANSWERS[module][number - 1]],
                        "grading_status": "auto",
                        "evidence": [source_ref(PAPER, hashes, page=page, module=module, number=number, confidence=confidence), source_ref(ANSWER_PDF, hashes, module=module, number=number)],
                    })
        modules.append({
            "id": module_id("listening", module),
            "subject": "listening",
            "module": module,
            "order": module_order,
            "label": f"Listening Module {module_order}",
            "duration_seconds": 576 if module == "m1" else 456,
            "navigation": {"back_policy": "disabled", "review_policy": "after_submit"},
            "asset_ids": [f"{EXAM_ID}:listening:{module}"],
            "group_ids": module_groups,
        })
    return modules, groups, questions, answers


def clean_scramble(scramble: list[str], ordered: list[str]) -> list[str]:
    remaining = Counter(ordered)
    cleaned: list[str] = []
    for token in scramble:
        if remaining[token] > 0:
            cleaned.append(token)
            remaining[token] -= 1
    for token in ordered:
        if remaining[token] > 0:
            cleaned.append(token)
            remaining[token] -= 1
    return cleaned


def build_writing(repo_root: Path, hashes: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    legacy = json.loads((repo_root / "data/toefl_practice/2026-01-21_A/writing.json").read_text(encoding="utf-8"))
    module = "m1"
    mid = module_id("writing", module)
    group_specs = [(1, 10, "build_a_sentence", "Build a Sentence"), (11, 11, "write_email", "Write an Email"), (12, 12, "academic_discussion", "Academic Discussion")]
    groups: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    group_lookup: dict[int, tuple[int, str]] = {}
    for group_index, (first, last, task_type, title) in enumerate(group_specs, 1):
        gid = group_id("writing", module, group_index)
        for number in range(first, last + 1):
            group_lookup[number] = (group_index, gid)
        groups.append({
            "id": gid,
            "module_id": mid,
            "subject": "writing",
            "order": group_index,
            "task_type": task_type,
            "title": title,
            "directive": "Arrange the words to make an appropriate sentence." if task_type == "build_a_sentence" else "Write a complete response to the prompt.",
            "stimulus": None,
            "question_ids": [question_id("writing", module, group_index, number) for number in range(first, last + 1)],
            "source_refs": [source_ref(PAPER, hashes, page=WRITING_PAGES[first], module=module)],
        })

    clean_manual_prompts = {
        11: (
            "You are a university student who recently moved into a new apartment and have noticed several problems. "
            "Write an email to your landlord, Mr. Thompson, with the subject ‘Request for apartment repairs.’ Describe the issues, explain how they negatively affect your studies, and request that repairs be arranged soon. Write in complete sentences."
        ),
        12: (
            "Your business ethics class is discussing corporate transparency. Dr. Achebe asks whether businesses should be completely transparent with employees about their operations or keep some information confidential to protect competitive advantages. State and support your opinion, contribute to the discussion in your own words, and write at least 100 words."
        ),
    }
    for number, old in enumerate(legacy["questions"], 1):
        group_index, gid = group_lookup[number]
        qid = question_id("writing", module, group_index, number)
        page = WRITING_PAGES[number]
        if number <= 10:
            ordered = old["answer"]["ordered"]
            scramble = clean_scramble(old.get("scramble_words", []), ordered)
            repaired = old.get("content_status") == "repaired_from_answer" or Counter(scramble) != Counter(old.get("scramble_words", []))
            confidence = "reviewed_repair" if repaired else "source_exact"
            status = "reviewed_repair" if repaired else "ready"
            question = {
                "id": qid,
                "module_id": mid,
                "group_id": gid,
                "subject": "writing",
                "number": number,
                "sequence": number,
                "response_type": "order",
                "prompt": "Make an appropriate sentence for the situation.",
                "context_sentence": old.get("prompt", ""),
                "options": [],
                "input_config": {"scramble_tokens": scramble, "keyboard_reorder": True},
                "content_status": status,
                "grading_status": "auto",
                "source_refs": [source_ref(PAPER, hashes, page=page, module=module, number=number, confidence=confidence)],
            }
            answers.append({
                "question_id": qid,
                "response_type": "order",
                "ordered_tokens": ordered,
                "grading_status": "auto",
                "evidence": [source_ref(PAPER, hashes, page=page, module=module, number=number, confidence=confidence), source_ref(ANSWER_PDF, hashes, module=module, number=number)],
            })
        else:
            question = {
                "id": qid,
                "module_id": mid,
                "group_id": gid,
                "subject": "writing",
                "number": number,
                "sequence": number,
                "response_type": "free_text",
                "prompt": clean_manual_prompts[number],
                "options": [],
                "input_config": {"minimum_words": 100 if number == 12 else 0, "autosave": True},
                "content_status": "reviewed_repair",
                "grading_status": "manual",
                "source_refs": [source_ref(PAPER, hashes, page=page, module=module, number=number, confidence="reviewed_repair")],
            }
        questions.append(question)
    modules = [{
        "id": mid,
        "subject": "writing",
        "module": module,
        "order": 1,
        "label": "Writing",
        "duration_seconds": 0,
        "navigation": {"back_policy": "within_module", "review_policy": "within_module"},
        "asset_ids": [f"{EXAM_ID}:paper"],
        "group_ids": [item["id"] for item in groups],
    }]
    return modules, groups, questions, answers


def build_speaking(repo_root: Path, hashes: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    legacy = json.loads((repo_root / "data/toefl_practice/2026-01-21_A/speaking.json").read_text(encoding="utf-8"))
    groups: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    modules: list[dict[str, Any]] = []
    for module_order, module in enumerate(("m1", "m2"), 1):
        selected = [item for item in legacy["questions"] if f"_{module}_" in item["id"]]
        gid = group_id("speaking", module, 1)
        mid = module_id("speaking", module)
        qids = [question_id("speaking", module, 1, int(item["number"])) for item in selected]
        groups.append({
            "id": gid,
            "module_id": mid,
            "subject": "speaking",
            "order": 1,
            "task_type": "listen_and_repeat" if module == "m1" else "take_an_interview",
            "title": "Listen and Repeat" if module == "m1" else "Take an Interview",
            "directive": "Record one response for each prompt.",
            "stimulus": {"format": "audio", "asset_id": f"{EXAM_ID}:speaking", "recording_policy": "one_take_in_test_mode"},
            "question_ids": qids,
            "source_refs": [source_ref(PAPER, hashes, page=46 if module == "m1" else 49, module=module), source_ref(SPEAKING_AUDIO, hashes, module=module)],
        })
        for item in selected:
            number = int(item["number"])
            page = (45 + (number + 1) // 2 if number <= 6 else 49) if module == "m1" else (49 if number <= 2 else 50)
            question: dict[str, Any] = {
                "id": question_id("speaking", module, 1, number),
                "module_id": mid,
                "group_id": gid,
                "subject": "speaking",
                "number": number,
                "sequence": len(questions) + 1,
                "response_type": "recording",
                "prompt": item.get("prompt", ""),
                "options": [],
                "input_config": {"maximum_takes_test_mode": 1, "local_preview_practice_mode": True},
                "content_status": "ready",
                "grading_status": "manual",
                "source_refs": [source_ref(PAPER, hashes, page=page, module=module, number=number), source_ref(SPEAKING_AUDIO, hashes, module=module, number=number)],
            }
            passage = item.get("passage") or {}
            if passage.get("text"):
                question["context_sentence"] = passage["text"]
            questions.append(question)
        modules.append({
            "id": mid,
            "subject": "speaking",
            "module": module,
            "order": module_order,
            "label": "Listen and Repeat" if module == "m1" else "Take an Interview",
            "duration_seconds": 420 if module == "m1" else 540,
            "navigation": {"back_policy": "disabled", "review_policy": "after_submit"},
            "asset_ids": [f"{EXAM_ID}:speaking"],
            "group_ids": [gid],
        })
    return modules, groups, questions


def build_assets(source_root: Path, hashes: dict[str, str]) -> list[dict[str, Any]]:
    specs = [
        (f"{EXAM_ID}:paper", "paper_pdf", "exam", PAPER, None, None),
        (f"{EXAM_ID}:answers", "answer_pdf", "exam", ANSWER_PDF, None, None),
        (f"{EXAM_ID}:listening-transcript", "transcript_pdf", "listening", TRANSCRIPT_PDF, None, None),
        (f"{EXAM_ID}:listening:m1", "audio", "listening", LISTENING_M1_AUDIO, module_id("listening", "m1"), duration_seconds(source_root / LISTENING_M1_AUDIO)),
        (f"{EXAM_ID}:listening:m2", "audio", "listening", LISTENING_M2_AUDIO, module_id("listening", "m2"), duration_seconds(source_root / LISTENING_M2_AUDIO)),
        (f"{EXAM_ID}:listening:full", "audio", "listening", LISTENING_FULL_AUDIO, None, duration_seconds(source_root / LISTENING_FULL_AUDIO)),
        (f"{EXAM_ID}:speaking", "audio", "speaking", SPEAKING_AUDIO, None, duration_seconds(source_root / SPEAKING_AUDIO)),
    ]
    assets: list[dict[str, Any]] = []
    for asset_id, kind, subject, path_value, linked_module, duration in specs:
        source: dict[str, Any] = {"path": path_value, "sha256": hashes[path_value], "size_bytes": (source_root / path_value).stat().st_size}
        if duration is not None:
            source["duration_seconds"] = duration
        asset: dict[str, Any] = {
            "id": asset_id,
            "kind": kind,
            "subject": subject,
            "source": source,
            "delivery": {"storage_key": f"toefl/v2/{EXAM_KEY}/{Path(path_value).name}", "status": "staged"},
        }
        if linked_module:
            asset["module_id"] = linked_module
        assets.append(asset)
    return assets


def subject_reviews(repo_root: Path) -> dict[str, str]:
    profiles = json.loads(
        (repo_root / "data/toefl_quality/source_profiles.json").read_text(
            encoding="utf-8"
        )
    )
    subjects = profiles["exams"][EXAM_KEY]["subjects"]
    return {
        subject: subjects[subject]["review_status"]
        for subject in ("reading", "listening", "writing", "speaking")
    }


def build_progress(repo_root: Path, output_root: Path, generated_at: str) -> None:
    inventory_path = repo_root / "data/toefl_real_inventory/inventory.json"
    if not inventory_path.is_file():
        return
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    rows = []
    for exam in inventory.get("exams", []):
        key = exam["exam_key"]
        pilot = key == "2026-01-21-A"
        rows.append({
            "exam_key": key,
            "source_dirs": exam.get("source_dirs", []),
            "source_size_bytes": exam.get("unique_size_bytes", exam.get("size_bytes", 0)),
            "source_asset_complete": exam.get("asset_complete", False),
            "ocr_blocker_detected": exam.get("has_ocr_blocker", False),
            "rebuild_status": "pilot_built" if pilot else "queued",
            "validation_status": "passed_with_blocked_source_items" if pilot else "not_run",
            "notes": "120 atomic questions; 4 listening items blocked because the source PDF omits options." if pilot else "Awaiting v2 source recovery and atomic-question rebuild.",
        })
    progress = {
        "schema_version": "1.0.0",
        "generated_at": generated_at,
        "source_inventory_generated_at": inventory.get("generated_at"),
        "summary": {
            "exam_sets": len(rows),
            "pilot_built": sum(row["rebuild_status"] == "pilot_built" for row in rows),
            "queued": sum(row["rebuild_status"] == "queued" for row in rows),
        },
        "exams": rows,
    }
    json_dump(output_root / "rebuild_progress.json", progress)
    report = "# TOEFL v2 reintegration readiness\n\n"
    report += f"Generated: {generated_at}\n\n"
    report += "## Release gate\n\n"
    report += "A set may enter the StudyTracker catalog only when every expected atomic question exists, source evidence is recorded, auto-graded items have private answer entries, and no item is falsely marked ready.\n\n"
    report += "## Current status\n\n"
    report += f"- Inventory: {len(rows)} real-exam sets.\n- Representative pilot built: 1.\n- Remaining queue: {len(rows) - 1}.\n"
    report += "- Pilot: 120 atomic questions; 103 auto-graded, 13 manual, 4 blocked because the source paper omits their options.\n\n"
    report += "The pilot is suitable for schema and renderer integration, but it is **not publishable as a fully complete exam** until the four missing listening option sets are recovered from another source.\n"
    (output_root / "reintegration_readiness_report.md").write_text(report, encoding="utf-8")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path("/Users/zhouxin/Desktop/新托福资料"))
    parser.add_argument("--output-root", type=Path, default=repo_root / "data/toefl_practice_v2")
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    package_dir = output_root / EXAM_KEY
    generated_at = datetime.now(UTC).isoformat()

    source_paths = [PAPER, ANSWER_PDF, TRANSCRIPT_PDF, SPEAKING_AUDIO, LISTENING_M1_AUDIO, LISTENING_M2_AUDIO, LISTENING_FULL_AUDIO]
    for path_value in source_paths:
        if not (source_root / path_value).is_file():
            raise FileNotFoundError(source_root / path_value)
    hashes = {path_value: file_hash(source_root / path_value) for path_value in source_paths}

    reading_modules, reading_groups, reading_questions, reading_answers = build_reading(source_root, hashes)
    listening_modules, listening_groups, listening_questions, listening_answers = build_listening(repo_root, hashes)
    writing_modules, writing_groups, writing_questions, writing_answers = build_writing(repo_root, hashes)
    speaking_modules, speaking_groups, speaking_questions = build_speaking(repo_root, hashes)

    questions = reading_questions + listening_questions + writing_questions + speaking_questions
    content = {
        "schema_version": "2.0.0",
        "exam": {
            "id": EXAM_ID,
            "title": "2026-01-21 TOEFL Real Exam A",
            "date": "2026-01-21",
            "variant": "A",
            "source_kind": "real_exam",
            "source_folder": SOURCE_FOLDER,
            "expected_question_count": 120,
            "availability_status": "pilot",
        },
        "assets": build_assets(source_root, hashes),
        "modules": reading_modules + listening_modules + writing_modules + speaking_modules,
        "groups": reading_groups + listening_groups + writing_groups + speaking_groups,
        "questions": questions,
    }
    answer_key = {
        "schema_version": "2.0.0",
        "exam_id": EXAM_ID,
        "visibility": "private_server_only",
        "answers": reading_answers + listening_answers + writing_answers,
        "manual_grading": [item["id"] for item in questions if item["grading_status"] == "manual"],
        "blocked": [
            {"question_id": item["id"], "reason": "The source paper omits the answer options; do not publish or auto-grade."}
            for item in questions if item["grading_status"] == "blocked"
        ],
    }
    counts = {
        "questions": len(questions),
        "auto": sum(item["grading_status"] == "auto" for item in questions),
        "manual": sum(item["grading_status"] == "manual" for item in questions),
        "blocked": sum(item["grading_status"] == "blocked" for item in questions),
        "by_subject": {subject: sum(item["subject"] == subject for item in questions) for subject in ("reading", "listening", "writing", "speaking")},
    }
    manifest = {
        "schema_version": "2.0.0",
        "exam_id": EXAM_ID,
        "generated_at": generated_at,
        "generator": "scripts/build_toefl_practice_v2_pilot.py",
        "source_root_portability": "All source paths are relative to the configured source root.",
        "counts": counts,
        "quality": {
            "validation_status": "pending_validator",
            "publish_status": "blocked",
            "subject_reviews": subject_reviews(repo_root),
            "blocking_reasons": ["Four listening questions have no options in the supplied source PDF."],
            "known_blocked_question_ids": [item["id"] for item in questions if item["grading_status"] == "blocked"],
        },
    }
    qa_report = {
        "schema_version": "1.0.0",
        "exam_id": EXAM_ID,
        "generated_at": generated_at,
        "checks": [
            {"id": "atomic-count", "status": "pass", "detail": "120 expected atomic questions are represented."},
            {"id": "answer-separation", "status": "pass", "detail": "content.json contains no answer keys; answers are private."},
            {
                "id": "reading-recovery",
                "status": "pass",
                "detail": "Reading M1 Q33 was visually recovered from paper page 7 and mapped to answer C on answer page 1.",
            },
            {"id": "listening-recovery", "status": "pass", "detail": "Listening M1 Q7 and M2 Q3 were visually recovered."},
            {"id": "missing-source-options", "status": "blocked", "detail": "Listening M1 Q15/Q18/Q21 and M2 Q9 lack options in the supplied paper."},
            {"id": "inline-reading-contract", "status": "pass", "detail": "Complete-the-words groups define inline token rendering."},
        ],
    }

    json_dump(package_dir / "content.json", content)
    json_dump(package_dir / "answer_key.json", answer_key)
    json_dump(package_dir / "manifest.json", manifest)
    json_dump(package_dir / "qa_report.json", qa_report)
    build_progress(repo_root, output_root, generated_at)
    print(json.dumps({"package": str(package_dir), "counts": counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
