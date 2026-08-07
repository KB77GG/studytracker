#!/usr/bin/env python3
"""Normalize ETS official practice audio/video filenames into asset refs.

ETS ships the same logical assets under two naming families:

  student (Practice 1-2)   Listening1_Question Response_Question3.ogg
                           Listening1_Academic Talks_Questions15-18.ogg
                           Speaking_Listen_Repeat_Question4.ogg

  teacher (Practice 3-5)   Listening1_Listen_Response_Question3.ogg
                           Listening1_Academic_Talk_Questions_15-18.ogg
                           Speaking_Listen_Repeat_4.ogg

Both collapse onto one vocabulary here so the importer never branches on the
filename spelling. Singular/plural ("Conversation" vs "Conversations") varies
even inside a single set, so matching is done on a normalized token stream
rather than on literal names.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

MEDIA_SUFFIXES = {".ogg", ".mp3", ".mp4", ".m4a", ".wav"}

# Normalized task token -> canonical task type.
TASK_ALIASES = {
    "questionresponse": "listen_response",
    "listenresponse": "listen_response",
    "conversation": "conversation",
    "conversations": "conversation",
    "announcement": "announcement",
    "announcements": "announcement",
    "academictalk": "academic_talk",
    "academictalks": "academic_talk",
    "listenrepeat": "listen_repeat",
    "interview": "interview",
}


@dataclass(frozen=True)
class AudioRef:
    """One media file resolved to the questions it belongs to."""

    path: Path
    subject: str  # "listening" | "speaking"
    module: str | None  # "m1" | "m2" for listening; None for speaking
    task: str  # canonical task type
    role: str  # "directions" | "questions"
    numbers: tuple[int, ...]  # question numbers this asset covers

    @property
    def key(self) -> tuple:
        return (self.subject, self.module, self.task, self.role, self.numbers)


def _normalize(token: str) -> str:
    token = unicodedata.normalize("NFKC", token)
    return re.sub(r"[^a-z0-9]", "", token.lower())


def _parse_numbers(raw: str) -> tuple[int, ...]:
    raw = raw.strip()
    if not raw:
        return ()
    range_match = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", raw)
    if range_match:
        start, end = int(range_match.group(1)), int(range_match.group(2))
        if start <= end:
            return tuple(range(start, end + 1))
        return ()
    single = re.fullmatch(r"(\d+)", raw)
    return (int(single.group(1)),) if single else ()


def parse_media_name(path: Path) -> AudioRef | None:
    """Resolve one filename, or None when it is not a recognized asset."""
    stem = path.stem

    og_track = re.fullmatch(r"Chapter 6 - Track (?P<number>\d+)", stem, re.I)
    if og_track:
        number = int(og_track.group("number"))
        return AudioRef(
            path=path,
            subject="listening" if number <= 81 else "speaking",
            module=None,
            task="og_track",
            role="questions",
            numbers=(number,),
        )

    og_video = re.fullmatch(r"Chapter 6 - Video (?P<number>\d+)", stem, re.I)
    if og_video:
        return AudioRef(
            path=path,
            subject="speaking",
            module=None,
            task="interview",
            role="questions",
            numbers=(int(og_video.group("number")),),
        )

    speaking = re.match(
        r"(?i)^Speaking[_ ]+(?P<task>Listen[_ ]?Repeat|Interview)"
        r"(?:[_ ]+(?P<role>Directions?))?"
        r"(?:[_ ]+(?:Question)?[_ ]*(?P<num>\d+))?$",
        stem,
    )
    if speaking:
        task = TASK_ALIASES[_normalize(speaking.group("task"))]
        is_directions = bool(speaking.group("role"))
        return AudioRef(
            path=path,
            subject="speaking",
            module=None,
            task=task,
            role="directions" if is_directions else "questions",
            numbers=_parse_numbers(speaking.group("num") or ""),
        )

    listening = re.match(
        r"(?i)^Listening(?P<module>[12])[_ ]+(?P<task>.+?)"
        r"[_ ]+(?P<role>Directions?|Questions?)"
        r"[_ ]*(?P<num>\d+(?:\s*[-–]\s*\d+)?)$",
        stem,
    )
    if listening:
        task_key = _normalize(listening.group("task"))
        task = TASK_ALIASES.get(task_key)
        if task is None:
            return None
        role_key = _normalize(listening.group("role"))
        return AudioRef(
            path=path,
            subject="listening",
            module=f"m{listening.group('module')}",
            task=task,
            role="directions" if role_key.startswith("direction") else "questions",
            numbers=_parse_numbers(listening.group("num")),
        )

    return None


def collect_media(roots: list[Path]) -> tuple[list[AudioRef], list[Path]]:
    """Walk roots and split media into recognized refs and unrecognized files."""
    refs: list[AudioRef] = []
    unknown: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in MEDIA_SUFFIXES:
                continue
            ref = parse_media_name(path)
            if ref is None:
                unknown.append(path)
            else:
                refs.append(ref)
    return refs, unknown


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deduplicate_media(refs: list[AudioRef]) -> dict[tuple, AudioRef]:
    """Return one source per logical key, rejecting conflicting duplicates."""

    grouped: dict[tuple, list[AudioRef]] = {}
    for ref in refs:
        grouped.setdefault(ref.key, []).append(ref)
    selected = {}
    for key, candidates in grouped.items():
        hashes = {sha256_file(item.path) for item in candidates}
        if len(hashes) != 1:
            paths = ", ".join(str(item.path) for item in candidates)
            raise RuntimeError(f"Conflicting media for {key}: {paths}")
        selected[key] = min(candidates, key=lambda item: (len(str(item.path)), str(item.path)))
    return selected
