#!/usr/bin/env python3
"""Extract Listening / Speaking / Writing sections from ETS official PDFs.

Reading already has a dedicated importer (import_toefl_official_reading.py).
This module covers the other three subjects for the same six official sources,
using the shared observation that every ETS booklet lays a subject out as:

    <Subject> Section                     directions / task overview
    <Subject> Section, Module N           question pages (repeated as a running
                                          header on the teacher layout)
    <Subject> Section, Module N
    Answer Key                            columnar "number  answer" table
    ...
    <Next Subject> Section

Question stems and options are identical in shape to Reading, so option parsing
and the "a real question carries four options" rule are reused from there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

try:
    from scripts.import_toefl_official_reading import (
        OPTION_RE,
        QUESTION_RE,
        clean_content,
        parse_options,
    )
except ModuleNotFoundError:
    from import_toefl_official_reading import (
        OPTION_RE,
        QUESTION_RE,
        clean_content,
        parse_options,
    )

# Listening stimulus headers, e.g. "Listen to a conversation." / "Listen to an
# announcement at a school art exhibit." / "Choose the best response."
STIMULUS_RE = re.compile(
    r"(?im)^\s*(?P<text>(?:Listen to (?:a|an|the)\b[^\n]*|Choose the best response\.?))\s*$"
)

TASK_BY_STIMULUS = (
    (re.compile(r"(?i)choose the best response"), "listen_response"),
    (re.compile(r"(?i)listen to (?:a|the) conversation"), "conversation"),
    (re.compile(r"(?i)listen to an? announcement"), "announcement"),
    (re.compile(r"(?i)listen to (?:a|an|the).*(?:talk|lecture|class)"), "academic_talk"),
)


@dataclass
class SectionQuestion:
    number: int
    module: str
    prompt: str
    options: list[dict]
    answer: str | None
    task: str
    stimulus: str = ""
    page_index: int | None = None
    media_label: str = ""
    response_seconds: int | None = None


@dataclass
class SectionExtract:
    subject: str
    questions: list[SectionQuestion] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


SUBJECT_LABELS = ("Reading", "Listening", "Writing", "Speaking")


def subject_spans(full_text: str) -> dict[str, tuple[int, int]]:
    """Where each subject starts and ends, by the order they appear.

    Booklets differ in subject order and only some subjects carry an answer
    key, so a subject is bounded by the next subject's opening header rather
    than by anything of its own. Running headers repeat the current subject's
    name, but never a later one, so the first foreign header is the boundary.
    """
    starts = []
    for label in SUBJECT_LABELS:
        match = re.search(rf"(?m)^\s*{label} Section\s*$", full_text)
        if match:
            starts.append((match.start(), label))
    starts.sort()
    spans = {}
    for index, (position, label) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(full_text)
        spans[label.lower()] = (position, end)
    return spans


def subject_body(subject: str, full_text: str) -> str:
    """Text belonging to one subject, answer key included."""
    spans = subject_spans(full_text)
    if subject not in spans:
        raise RuntimeError(f"Unable to isolate {subject} section")
    start, end = spans[subject]
    return full_text[start:end]


def subject_answer_maps(subject: str, full_text: str) -> dict[str, dict[int, str]]:
    """Parse the two columnar answer-key tables that follow a subject."""
    label = subject.capitalize()
    block = re.search(
        rf"(?ms){label} Section, Module 1\s+Answer Key(?P<body>.+?)"
        rf"^\s*(?:Listening|Speaking|Writing|Reading) Section\s*$",
        full_text,
    )
    if not block:
        # The last subject in a booklet has no following section header.
        block = re.search(
            rf"(?ms){label} Section, Module 1\s+Answer Key(?P<body>.+)",
            full_text,
        )
    if not block:
        raise RuntimeError(f"{subject} answer key not found")
    chunks = re.split(rf"(?m)^\s*{label} Section, Module 2\s*$", block.group("body"))
    maps: dict[str, dict[int, str]] = {}
    for module_id, chunk in zip(("m1", "m2"), chunks, strict=False):
        pairs = re.findall(r"(?m)^\s*(\d{1,2})\s+([A-Za-z]+)\s*$", chunk)
        maps[module_id] = {int(number): answer for number, answer in pairs}
    return maps


def module_for_page(page: str, current: str) -> str:
    match = re.search(r"Section, Module\s+([12])", page, re.I)
    return f"m{match.group(1)}" if match else current


def task_for_stimulus(stimulus: str, fallback: str) -> str:
    for pattern, task in TASK_BY_STIMULUS:
        if pattern.search(stimulus):
            return task
    return fallback


def questions_on_page(page: str, maximum: int) -> list[re.Match]:
    """Question stems on a page: a candidate must carry four options."""
    candidates = [
        match for match in QUESTION_RE.finditer(page) if 1 <= int(match.group("number")) <= maximum
    ]
    kept = []
    for index, match in enumerate(candidates):
        end = candidates[index + 1].start() if index + 1 < len(candidates) else len(page)
        if len(OPTION_RE.findall(page[match.start() : end])) == 4:
            kept.append(match)
    return kept


def option_runs(page: str) -> list[tuple[int, int, list[re.Match]]]:
    """Locate each A-B-C-D option block as (start, end, matches).

    Listening stems are numbered on the student layout but bare on the teacher
    layout, so questions are anchored on their options instead of on a leading
    number. That is the one feature both layouts always share.
    """
    labels = list(OPTION_RE.finditer(page))
    runs = []
    index = 0
    while index + 3 < len(labels):
        window = labels[index : index + 4]
        keys = [(match.group("paren") or match.group("plain")) for match in window]
        if keys == ["A", "B", "C", "D"]:
            runs.append((window[0].start(), window[-1].end(), window))
            index += 4
        else:
            index += 1
    return runs


def stem_before(page: str, start: int, floor: int) -> str:
    """The question stem is the last paragraph before an option block."""
    prefix = page[floor:start]
    blocks = [block for block in re.split(r"\n\s*\n", prefix) if block.strip()]
    return clean_content(blocks[-1]) if blocks else ""


def questions_by_options(page: str) -> list[tuple[int, str, list[dict]]]:
    """Every question on a page as (position, stem, options), in reading order."""
    runs = option_runs(page)
    found = []
    floor = 0
    for index, (start, label_end, _window) in enumerate(runs):
        stem = stem_before(page, start, floor)
        # Option D's text runs past its own label, so the block has to extend
        # beyond the run. Stop at the next question, then keep only D's own
        # paragraph so a trailing stem or page footer is not absorbed into it.
        ceiling = runs[index + 1][0] if index + 1 < len(runs) else len(page)
        tail = page[label_end:ceiling]
        paragraph = re.split(r"\n\s*\n", tail)[0]
        _prompt, options = parse_options(page[start:label_end] + paragraph)
        if len(options) == 4 and stem:
            found.append((start, re.sub(r"^\s*\d{1,2}\.\s*", "", stem), options))
        # The next stem starts after this block's last option, not at the next
        # option run, or it would be searched for in an empty span.
        floor = label_end + len(paragraph)
    return found


def extract_listening(full_text: str, maximum: int = 18) -> SectionExtract:
    """Pull listening questions, their stimulus text, and their module."""
    result = SectionExtract(subject="listening")
    answers = subject_answer_maps("listening", full_text)
    module = "m1"
    stimulus = ""
    task = "listen_response"
    counters = {"m1": 0, "m2": 0}

    for page_index, raw_page in enumerate(subject_body("listening", full_text).split("\f")):
        page = raw_page
        if not page.strip():
            continue
        module = module_for_page(page, module)

        stimuli = [
            (match.start(), clean_content(match.group("text")))
            for match in STIMULUS_RE.finditer(page)
        ]

        for position, stem, options in questions_by_options(page):
            # A question belongs to the last stimulus declared above it, which
            # may differ from the previous question's on multi-task pages.
            above = [text for offset, text in stimuli if offset < position]
            if above:
                stimulus = above[-1]
                task = task_for_stimulus(stimulus, task)
            counters[module] += 1
            number = counters[module]
            if number > maximum:
                result.warnings.append(
                    f"listening {module}: question {number} exceeds expected {maximum}"
                )
            result.questions.append(
                SectionQuestion(
                    number=number,
                    module=module,
                    prompt=stem,
                    options=options,
                    answer=answers.get(module, {}).get(number),
                    task=task,
                    stimulus=stimulus,
                    page_index=page_index,
                )
            )
    return result


# --- Writing ---------------------------------------------------------------

# "1. Where did you get your shoes?" then a blank template line, then the word
# bank: "visited / had / it / last month / the shop / a sale / I".
BUILD_SENTENCE_RE = re.compile(
    r"(?m)^\s*(?P<number>\d{1,2})\.\s+(?P<context>\S[^\n]*)\n"
    r"\s*(?P<template>[^\n]*_{3,}[^\n]*)\n"
    r"\s*(?P<bank>[^\n]*/[^\n]*)$"
)

WRITING_PROMPT_HEADS = (
    ("write_email", re.compile(r"(?im)^\s*Write an Email\s*$")),
    (
        "academic_discussion",
        re.compile(r"(?im)^\s*Write for an Academic Discussion\s*$"),
    ),
)


def writing_answer_map(full_text: str) -> dict[int, str]:
    """Writing answers are whole sentences and have no module split."""
    block = re.search(
        r"(?ms)Writing Section\s+Answer Key(?P<body>.+?)"
        r"^\s*(?:Listening|Speaking|Reading) Section\s*$",
        full_text,
    )
    if not block:
        block = re.search(r"(?ms)Writing Section\s+Answer Key(?P<body>.+)", full_text)
    if not block:
        return {}
    pairs = re.findall(r"(?m)^\s*(\d{1,2})\s{2,}(\S.*?)\s*$", block.group("body"))
    return {int(number): clean_content(answer) for number, answer in pairs}


def extract_writing(full_text: str) -> SectionExtract:
    """Build a Sentence items plus the two long-form writing prompts."""
    result = SectionExtract(subject="writing")
    answers = writing_answer_map(full_text)
    body = subject_body("writing", full_text)

    for match in BUILD_SENTENCE_RE.finditer(body):
        number = int(match.group("number"))
        bank = [word.strip() for word in match.group("bank").split("/") if word.strip()]
        result.questions.append(
            SectionQuestion(
                number=number,
                module="m1",
                prompt=clean_content(match.group("context")),
                options=[{"key": str(index), "text": word} for index, word in enumerate(bank)],
                answer=answers.get(number),
                task="build_sentence",
                stimulus=clean_content(match.group("template")),
            )
        )
    if not answers:
        result.warnings.append("writing: no Build a Sentence answer key found")

    # The two long-form prompts run from their heading to the next heading.
    heads = []
    for task, pattern in WRITING_PROMPT_HEADS:
        for match in pattern.finditer(body):
            heads.append((match.start(), task))
    heads.sort()
    for index, (start, task) in enumerate(heads):
        end = heads[index + 1][0] if index + 1 < len(heads) else len(body)
        prompt = clean_content(_strip_running_headers(body[start:end]))
        if not prompt:
            result.warnings.append(f"writing: empty prompt for {task}")
            continue
        result.questions.append(
            SectionQuestion(
                number=11 + index,
                module="m1",
                prompt=prompt,
                options=[],
                answer=None,
                task=task,
            )
        )
    return result


# --- Speaking --------------------------------------------------------------

SPEAKING_HEADS = (
    ("listen_repeat", re.compile(r"(?im)^\s*Listen and Repeat\s*$")),
    ("take_interview", re.compile(r"(?im)^\s*Take an Interview\s*$")),
)

# Utterances are speaker-labelled: "Trainer: ...", "Interviewer: ...". An
# utterance wraps across lines, so it runs to the next label, not to EOL.
UTTERANCE_RE = re.compile(r"(?m)^[ \t]*(?P<who>[A-Z][A-Za-z ]{2,20}):[ \t]+(?=\S)")


def utterances_in(chunk: str) -> list[str]:
    """Speaker-labelled utterances, each spanning to the next speaker label."""
    labels = list(UTTERANCE_RE.finditer(chunk))
    spoken = []
    for index, match in enumerate(labels):
        end = labels[index + 1].start() if index + 1 < len(labels) else len(chunk)
        text = clean_content(chunk[match.end() : end])
        if text:
            spoken.append(text)
    return spoken


def _strip_running_headers(text: str) -> str:
    cleaned = re.sub(r"(?m)^\s*TOEFL iBT.*$", "", text)
    cleaned = re.sub(r"(?m)^\s*(?:Writing|Speaking|Listening|Reading) Section.*$", "", cleaned)
    return cleaned


def extract_speaking(full_text: str) -> SectionExtract:
    """Listen and Repeat utterances plus Take an Interview questions."""
    result = SectionExtract(subject="speaking")
    body = subject_body("speaking", full_text)

    heads = []
    for task, pattern in SPEAKING_HEADS:
        for match in pattern.finditer(body):
            heads.append((match.start(), task))
    heads.sort()
    # The first hit of each task is the overview table, the second the real one.
    latest: dict[str, int] = {}
    for start, task in heads:
        latest[task] = start
    ordered = sorted((start, task) for task, start in latest.items())

    for index, (start, task) in enumerate(ordered):
        end = ordered[index + 1][0] if index + 1 < len(ordered) else len(body)
        chunk = _strip_running_headers(body[start:end])
        utterances = utterances_in(chunk)
        if not utterances:
            result.warnings.append(f"speaking: no utterances found for {task}")
            continue
        scenario = clean_content(chunk[: UTTERANCE_RE.search(chunk).start()])
        module = "m1" if task == "listen_repeat" else "m2"
        for offset, utterance in enumerate(utterances, start=1):
            result.questions.append(
                SectionQuestion(
                    number=offset,
                    module=module,
                    prompt=utterance,
                    options=[],
                    answer=None,
                    task=task,
                    stimulus=scenario,
                )
            )
    return result


# --- Official Guide Chapter 6 ----------------------------------------------

# The OG is a book export: it carries embedded object dumps and a per-copy
# ownership watermark, both of which land in the text layer.
OG_NOISE_RE = re.compile(
    r"SdkBytes\(bytes=0x[0-9a-f]*\)?"
    r"|^\s*[0-9a-f]{80,}\)?\s*$"
    r"|^\s*This ebook was issued to .*?$"
    r"|^\s*(?:CHAPTER 6:.*?)?THE OFFICIAL GUIDE TO THE TOEFL.*?$"
    r"|^\s*[A-Z][A-Z ]+\s+\d{6,}\s*$",
    re.MULTILINE,
)

OG_SECTION_RE = "(?im)^\\s*—\\s*{label}\\s*$"

# "1. Play track 53.  Then choose the best response."
OG_TRACK_RE = re.compile(r"(?i)\bplay\s+track\s+(?P<track>\d+)")


def og_clean(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", OG_NOISE_RE.sub("", text))


def og_subject_body(subject: str, sliced_text: str) -> str:
    """Slice one subject out of the OG chapter, which uses em-dash headers."""
    order = ("Reading", "Listening", "Writing", "Speaking")
    positions = []
    for label in order:
        match = re.search(OG_SECTION_RE.format(label=label), sliced_text)
        if match:
            positions.append((match.start(), label.lower()))
    positions.sort()
    for index, (start, label) in enumerate(positions):
        if label != subject:
            continue
        end = positions[index + 1][0] if index + 1 < len(positions) else len(sliced_text)
        return og_clean(sliced_text[start:end])
    raise RuntimeError(f"OG: unable to isolate {subject}")


OG_MODULE_SIZES = {"m1": 32, "m2": 15}

OG_LISTENING_TRACKS = {
    "m1": {
        **{number: 52 + number for number in range(1, 13)},
        **{number: 65 for number in range(13, 15)},
        **{number: 66 for number in range(15, 17)},
        **{number: 67 for number in range(17, 19)},
        **{number: 68 for number in range(19, 21)},
        **{number: 69 for number in range(21, 23)},
        **{number: 70 for number in range(23, 25)},
        **{number: 71 for number in range(25, 29)},
        **{number: 72 for number in range(29, 33)},
    },
    "m2": {
        **{number: 72 + number for number in range(1, 6)},
        **{number: 78 for number in range(6, 8)},
        **{number: 79 for number in range(8, 10)},
        **{number: 80 for number in range(10, 12)},
        **{number: 81 for number in range(12, 16)},
    },
}


def og_listening_task(module: str, number: int) -> str:
    if (module == "m1" and number <= 12) or (module == "m2" and number <= 5):
        return "listen_response"
    ranges = {
        "m1": ((13, 18, "conversation"), (19, 24, "announcement"), (25, 32, "academic_talk")),
        "m2": ((6, 9, "conversation"), (10, 11, "announcement"), (12, 15, "academic_talk")),
    }
    return next(task for start, end, task in ranges[module] if start <= number <= end)


def og_listening_answers(full_text: str) -> dict[str, dict[int, dict]]:
    """OG listening answers, flagging the unscored Module 1 questions."""
    header = re.search(
        r"(?m)^\s*LISTENING\s*$\s*^\s*Answer Key and Self-Scoring Chart\s*$",
        full_text,
    )
    if not header:
        raise RuntimeError("OG listening answer key not found")
    # The chart is followed by scripts and explanations, which also contain
    # "N. X" lines, so stop at the next subject's chart.
    tail = re.search(
        r"(?m)^\s*(?:WRITING|SPEAKING|READING)\s*$\s*^\s*Answer Key",
        full_text[header.end() :],
    )
    body = og_clean(
        full_text[header.end() : header.end() + (tail.start() if tail else len(full_text))]
    )
    chunks = re.split(r"(?m)^\s*Module\s+([12])\s*$", body)
    maps: dict[str, dict[int, dict]] = {"m1": {}, "m2": {}}
    for index in range(1, len(chunks), 2):
        module = f"m{chunks[index]}"
        if module not in maps:
            continue
        for match in re.finditer(
            r"(?m)^\s*(?P<number>\d{1,2})\.\s+(?P<answer>[A-D])\b(?P<tail>[^\n]*)$",
            chunks[index + 1],
        ):
            number = int(match.group("number"))
            # Charts are ordered; anything past the module size is downstream
            # prose that happens to look like a chart row.
            if number > OG_MODULE_SIZES[module] or number in maps[module]:
                continue
            maps[module][number] = {
                "answer": match.group("answer"),
                "scored": "unscored" not in match.group("tail").lower(),
            }
    return maps


def extract_listening_og(full_text: str, sliced_text: str) -> SectionExtract:
    """OG listening: numbered stems that name the audio track to play."""
    result = SectionExtract(subject="listening")
    answers = og_listening_answers(full_text)
    body = og_subject_body("listening", sliced_text)
    chunks = re.split(r"(?m)^\s*Module\s+([12])\s*$", body)

    for index in range(1, len(chunks), 2):
        module = f"m{chunks[index]}"
        counter = 0
        for page in chunks[index + 1].split("\f"):
            for _position, stem, options in questions_by_options(page):
                counter += 1
                entry = answers.get(module, {}).get(counter) or {}
                track = OG_TRACK_RE.search(stem)
                track_number = (
                    int(track.group("track")) if track else OG_LISTENING_TRACKS[module][counter]
                )
                result.questions.append(
                    SectionQuestion(
                        number=counter,
                        module=module,
                        prompt=stem,
                        options=options,
                        answer=entry.get("answer"),
                        task=og_listening_task(module, counter),
                        stimulus=f"track {track_number}",
                        media_label=f"track {track_number}",
                    )
                )
    return result


def og_writing_answer_map(full_text: str) -> dict[int, str]:
    """Read the ten canonical Build a Sentence answers from the OG explanations."""

    heading = re.search(r"(?i)Answer Explanations for Build a Sentence", full_text)
    if not heading:
        raise RuntimeError("OG writing answer explanations not found")
    body = og_clean(full_text[heading.end() :])
    answers = {}
    for match in re.finditer(
        r"(?ms)^\s*(?P<number>\d{1,2})\.\s+(?P<answer>.+?)\n\s*Explanation:",
        body,
    ):
        number = int(match.group("number"))
        if 1 <= number <= 10 and number not in answers:
            answers[number] = clean_content(match.group("answer"))
    if set(answers) != set(range(1, 11)):
        raise RuntimeError(f"OG writing answer map incomplete: {sorted(answers)}")
    return answers


def _og_numbered_blocks(body: str, numbers: range) -> dict[int, str]:
    matches = [
        match
        for match in re.finditer(r"(?m)^\s*(?P<number>\d{1,2})\.\s*(?P<head>.*?)\s*$", body)
        if int(match.group("number")) in numbers
    ]
    blocks = {}
    for index, match in enumerate(matches):
        number = int(match.group("number"))
        if number in blocks:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        blocks[number] = body[match.start() : end]
    return blocks


def extract_writing_og(full_text: str, sliced_text: str) -> SectionExtract:
    """Extract the OG Build a Sentence items and both long-form prompts."""

    result = SectionExtract(subject="writing")
    body = og_subject_body("writing", sliced_text)
    answers = og_writing_answer_map(full_text)
    starts = list(
        re.finditer(
            r"(?m)^\s*(?P<number>(?:[1-9]|10))\.\s+Make an appropriate sentence\.\s*$", body
        )
    )
    for index, match in enumerate(starts):
        number = int(match.group("number"))
        end_candidates = [
            candidate
            for candidate in (
                starts[index + 1].start() if index + 1 < len(starts) else None,
                (
                    re.search(r"(?m)^\s*11\.\s*$", body[match.end() :]).start() + match.end()
                    if re.search(r"(?m)^\s*11\.\s*$", body[match.end() :])
                    else None
                ),
            )
            if candidate is not None
        ]
        segment = body[match.end() : min(end_candidates) if end_candidates else len(body)]
        lines = [clean_content(line) for line in segment.splitlines() if clean_content(line)]
        context = next(
            (line for line in lines if "_" not in line and "/" not in line),
            "",
        )
        template = " ".join(line for line in lines if "_" in line)
        bank_line = next((line for line in lines if "/" in line), "")
        bank = [token.strip() for token in bank_line.split("/") if token.strip()]
        if not context or not template or len(bank) < 2:
            raise RuntimeError(f"OG writing item {number} is incomplete")
        result.questions.append(
            SectionQuestion(
                number=number,
                module="m1",
                prompt=context,
                options=[{"key": str(i), "text": token} for i, token in enumerate(bank)],
                answer=answers[number],
                task="build_sentence",
                stimulus=template,
            )
        )

    long_starts = list(re.finditer(r"(?m)^\s*(?P<number>1[12])\.\s*$", body))
    for index, match in enumerate(long_starts):
        number = int(match.group("number"))
        end = long_starts[index + 1].start() if index + 1 < len(long_starts) else len(body)
        prompt = clean_content(og_clean(body[match.end() : end]))
        result.questions.append(
            SectionQuestion(
                number=number,
                module="m1",
                prompt=prompt,
                options=[],
                answer=None,
                task="write_email" if number == 11 else "academic_discussion",
            )
        )
    if len(result.questions) != 12:
        raise RuntimeError(f"OG writing expected 12 questions, found {len(result.questions)}")
    return result


OG_SPEAKING_RESPONSE_SECONDS = {
    1: 8,
    2: 8,
    3: 10,
    4: 10,
    5: 10,
    6: 12,
    7: 12,
    8: 45,
    9: 45,
    10: 45,
    11: 45,
}


def extract_speaking_og(full_text: str) -> SectionExtract:
    """Extract source transcripts and media labels for all eleven OG speaking items."""

    result = SectionExtract(subject="speaking")
    heading = re.search(
        r"(?ms)^\s*SPEAKING\s*$\s*^\s*Listening Scripts, Video Transcripts, and Sample Test Taker Responses with Comments\s*$",
        full_text,
    )
    if not heading:
        raise RuntimeError("OG speaking transcript section not found")
    body = og_clean(full_text[heading.end() :])

    repeat_section = body[: body.find("Take an Interview")]
    for match in re.finditer(
        r"(?ms)^\s*(?P<number>[1-7])\.\s+Track\s+(?P<track>\d+)\s+Listening Script:\s*"
        r"(?P<prompt>.+?)(?=^\s*[1-7]\.\s+Track|\Z)",
        repeat_section,
    ):
        number = int(match.group("number"))
        result.questions.append(
            SectionQuestion(
                number=number,
                module="m1",
                prompt=clean_content(match.group("prompt")),
                options=[],
                answer=None,
                task="listen_repeat",
                stimulus="Student resource room office-equipment training.",
                media_label=f"track {match.group('track')}",
                response_seconds=OG_SPEAKING_RESPONSE_SECONDS[number],
            )
        )

    interview_section = body[body.find("Take an Interview") :]
    for match in re.finditer(
        r"(?ms)^\s*(?P<number>(?:8|9|10|11))\.\s+Video\s+(?P<video>[1-4])\s+Transcript:\s*"
        r"(?P<prompt>.+?)(?=^\s*Play Track)",
        interview_section,
    ):
        number = int(match.group("number"))
        result.questions.append(
            SectionQuestion(
                number=number,
                module="m2",
                prompt=clean_content(match.group("prompt")),
                options=[],
                answer=None,
                task="take_interview",
                stimulus="University research interview about art and creativity.",
                media_label=f"video {match.group('video')}",
                response_seconds=45,
            )
        )
    result.questions.sort(key=lambda item: item.number)
    if len(result.questions) != 11:
        raise RuntimeError(f"OG speaking expected 11 questions, found {len(result.questions)}")
    return result
