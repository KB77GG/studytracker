#!/usr/bin/env python3
"""Inventory dated TOEFL material sets without modifying source files.

Outputs:
  - inventory.json: complete machine-readable inventory
  - exams.csv: one row per normalized exam set
  - files.csv: one row per source file assigned to an exam set
  - duplicates.csv: exact duplicate files grouped by SHA-256
  - summary.md: human-readable readiness report

The scanner treats the materials as internal study resources. Generated reports
include the notice: "内部学习资料，禁止外传或用于商业用途".
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


DEFAULT_SOURCE = Path.home() / "Desktop" / "新托福资料"
DEFAULT_OUTPUT = Path("data") / "toefl_real_inventory"
NOTICE = "内部学习资料，禁止外传或用于商业用途"

DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".md", ".markdown"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg", ".aiff", ".aac", ".flac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".heic"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}
RELEVANT_EXTENSIONS = (
    DOCUMENT_EXTENSIONS
    | AUDIO_EXTENSIONS
    | VIDEO_EXTENSIONS
    | IMAGE_EXTENSIONS
    | ARCHIVE_EXTENSIONS
)
SECTIONS = ("reading", "listening", "speaking", "writing")
NON_EXAM_COLLECTION_ROOTS = {
    "SagePath词册",
    "lacircle_archive",
    "output",
    "sagepath_vocab",
    "tmp",
    "tmp_pdfs",
    "wechat_toefl",
    "新托福分科刷题材料",
    "评分标准",
    "课件输出",
    "课程安排",
    "输出词册",
}

SECTION_PATTERNS = {
    "reading": re.compile(r"阅读|reading", re.I),
    "listening": re.compile(r"听力|listening|listen(?:\s+and)?\s+response|announcement|academic[\s_-]*talk", re.I),
    "speaking": re.compile(r"口语|speaking|interview|listen[\s_-]*and[\s_-]*repeat", re.I),
    "writing": re.compile(r"写作|writing|academic[\s_-]*discussion|build[\s_-]*a[\s_-]*sentence", re.I),
}

ANSWER_PATTERN = re.compile(r"参考答案|答案|解析|answer[\s_-]*key|answers?", re.I)
TRANSCRIPT_PATTERN = re.compile(r"听力原文|原文|transcript", re.I)
FULL_PAPER_PATTERN = re.compile(r"真题|practice[\s_-]*test|full[\s_-]*length", re.I)
PARTIAL_PATTERN = re.compile(
    r"缺|仅|部分|待补|后续",
    re.I,
)

DATE_PATTERN = re.compile(
    r"(?<!\d)(?:(?P<year>20\d{2})\s*[./年-]\s*)?"
    r"(?P<month>1[0-2]|0?[1-9])\s*[./月-]\s*"
    r"(?P<day>3[01]|[12]\d|0?[1-9])(?:\s*日)?(?!\d)"
)

VARIANT_PATTERNS = (
    (re.compile(r"国内\s*线下|线下|offline", re.I), lambda _m: "OFFLINE-CN"),
    (re.compile(r"(?<![A-Za-z])([ABC])\s*卷", re.I), lambda m: m.group(1).upper()),
    (re.compile(r"托福\s*([ABC])(?:\s*卷)?", re.I), lambda m: m.group(1).upper()),
    (re.compile(r"套\s*([一二三四五六七八九十\d]+)", re.I), lambda m: f"S{_chinese_number(m.group(1))}"),
)


@dataclass(frozen=True)
class SourceAssignment:
    exam_date: str
    variant: str
    source_dir: Path

    @property
    def exam_key(self) -> str:
        suffix = "" if self.variant == "default" else f"-{self.variant}"
        return f"{self.exam_date}{suffix}"


def _chinese_number(value: str) -> int:
    if value.isdigit():
        return int(value)
    digits = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    if value in digits:
        return digits[value]
    if value.startswith("十"):
        return 10 + digits.get(value[1:], 0)
    if value.endswith("十"):
        return digits.get(value[:-1], 0) * 10
    if "十" in value:
        tens, ones = value.split("十", 1)
        return digits.get(tens, 0) * 10 + digits.get(ones, 0)
    return 0


def extract_date(value: str, default_year: int = 2026) -> str | None:
    """Return a normalized ISO date found in a path component or filename."""
    matches = list(DATE_PATTERN.finditer(value))
    if not matches:
        return None
    match = matches[-1]
    year = int(match.group("year") or default_year)
    month = int(match.group("month"))
    day = int(match.group("day"))
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def extract_variant(value: str) -> str | None:
    normalized = value.replace("Ａ", "A").replace("Ｂ", "B").replace("Ｃ", "C")
    for pattern, converter in VARIANT_PATTERNS:
        match = pattern.search(normalized)
        if match:
            variant = converter(match)
            return variant if variant and variant != "S0" else None
    return None


def nearest_dated_directory(path: Path, root: Path, default_year: int) -> tuple[Path, str] | None:
    """Find the dated collection directory carrying an exam date.

    Repeated same-date subdirectories are collapsed into their outer collection.
    A different nested date still wins, which handles copied date collections
    such as ``1.21.../3.17新托福真题/...`` correctly.
    """
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        return None
    if relative_parts and relative_parts[0] in NON_EXAM_COLLECTION_ROOTS:
        return None

    current = path.parent
    dated_ancestors: list[tuple[Path, str]] = []
    while current != root and root in current.parents:
        exam_date = extract_date(current.name, default_year)
        if exam_date:
            dated_ancestors.append((current, exam_date))
        current = current.parent
    if current == root:
        exam_date = extract_date(current.name, default_year)
        if exam_date:
            dated_ancestors.append((current, exam_date))

    if not dated_ancestors:
        return None
    chosen_dir, chosen_date = dated_ancestors[0]
    for ancestor, exam_date in dated_ancestors[1:]:
        if exam_date != chosen_date:
            break
        chosen_dir = ancestor
    return chosen_dir, chosen_date


def is_ignored_path(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(
        part.startswith(".")
        or part.startswith("._")
        or part in {"__MACOSX", "__pycache__", "node_modules"}
        for part in parts
    )


def iter_relevant_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file() or is_ignored_path(path, root):
            continue
        if path.suffix.lower() in RELEVANT_EXTENSIONS:
            yield path


def assign_sources(
    files: list[Path],
    root: Path,
    default_year: int,
) -> tuple[dict[Path, SourceAssignment], list[Path]]:
    grouped: dict[tuple[Path, str], list[Path]] = defaultdict(list)
    unmatched: list[Path] = []
    for path in files:
        dated = nearest_dated_directory(path, root, default_year)
        if not dated:
            unmatched.append(path)
            continue
        source_dir, exam_date = dated
        grouped[(source_dir, exam_date)].append(path)

    assignments: dict[Path, SourceAssignment] = {}
    for (source_dir, exam_date), source_files in grouped.items():
        variant = extract_variant(source_dir.name)
        if not variant:
            variants = {
                found
                for path in source_files
                if (found := extract_variant(path.name))
            }
            if len(variants) == 1:
                variant = variants.pop()
            elif len(variants) > 1:
                variant = "MIXED"
        assignment = SourceAssignment(
            exam_date=exam_date,
            variant=variant or "default",
            source_dir=source_dir,
        )
        for path in source_files:
            assignments[path] = assignment
    return assignments, unmatched


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def probe_pdf(path: Path, text_threshold: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ocr_status": "not_checked",
        "text_characters": None,
        "pages": None,
    }
    pdftotext = shutil.which("pdftotext")
    pdfinfo = shutil.which("pdfinfo")
    if not pdftotext:
        result["ocr_status"] = "unknown_pdftotext_missing"
        return result

    try:
        text_proc = run_command([pdftotext, str(path), "-"], timeout=120)
        if text_proc.returncode != 0:
            result["ocr_status"] = "pdf_read_error"
            result["probe_error"] = text_proc.stderr.strip()[:300]
        else:
            text_characters = len(re.sub(r"\s+", "", text_proc.stdout))
            result["text_characters"] = text_characters
            if text_characters == 0:
                result["ocr_status"] = "ocr_required"
            elif text_characters < text_threshold:
                result["ocr_status"] = "low_text_check"
            else:
                result["ocr_status"] = "text_extractable"
    except (OSError, subprocess.SubprocessError) as exc:
        result["ocr_status"] = "pdf_read_error"
        result["probe_error"] = str(exc)

    if pdfinfo:
        try:
            info_proc = run_command([pdfinfo, str(path)], timeout=30)
            if info_proc.returncode == 0:
                page_match = re.search(r"^Pages:\s+(\d+)", info_proc.stdout, re.M)
                if page_match:
                    result["pages"] = int(page_match.group(1))
        except (OSError, subprocess.SubprocessError):
            pass
    return result


def probe_media(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"media_status": "unknown_ffprobe_missing"}
    args = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=format_name,duration:stream=codec_type,codec_name,sample_rate,channels,width,height",
        "-of",
        "json",
        str(path),
    ]
    try:
        proc = run_command(args, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"media_status": "probe_error", "probe_error": str(exc)}
    if proc.returncode != 0:
        return {
            "media_status": "probe_error",
            "probe_error": proc.stderr.strip()[:300],
        }
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"media_status": "probe_error", "probe_error": "invalid ffprobe JSON"}

    format_data = payload.get("format") or {}
    streams = payload.get("streams") or []
    stream = next(
        (row for row in streams if row.get("codec_type") in {"audio", "video"}),
        streams[0] if streams else {},
    )
    duration = format_data.get("duration")
    return {
        "media_status": "playable" if streams else "no_media_stream",
        "container": format_data.get("format_name"),
        "duration_seconds": round(float(duration), 3) if duration else None,
        "codec_type": stream.get("codec_type"),
        "codec": stream.get("codec_name"),
        "sample_rate": int(stream["sample_rate"]) if str(stream.get("sample_rate") or "").isdigit() else None,
        "channels": stream.get("channels"),
        "width": stream.get("width"),
        "height": stream.get("height"),
    }


def inspect_archive(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "archive_status": "not_inspected",
        "archive_members": None,
        "archive_extensions": {},
        "archive_sections": [],
    }
    if path.suffix.lower() != ".zip":
        result["archive_status"] = "unsupported_archive"
        return result
    try:
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
    except (OSError, zipfile.BadZipFile) as exc:
        result["archive_status"] = "archive_read_error"
        result["probe_error"] = str(exc)
        return result

    extensions = Counter(Path(name).suffix.lower() or "[none]" for name in names)
    sections: set[str] = set()
    for name in names:
        sections.update(detect_sections(name))
    result.update(
        {
            "archive_status": "readable",
            "archive_members": len(names),
            "archive_extensions": dict(sorted(extensions.items())),
            "archive_sections": sorted(sections),
        }
    )
    return result


def detect_sections(value: str) -> set[str]:
    return {
        section
        for section, pattern in SECTION_PATTERNS.items()
        if pattern.search(value)
    }


def classify_file(path: Path, archive_info: dict[str, Any] | None = None) -> dict[str, Any]:
    extension = path.suffix.lower()
    searchable = str(path)
    sections = detect_sections(searchable)
    archive_sections = set((archive_info or {}).get("archive_sections") or [])
    sections.update(archive_sections)

    if extension in DOCUMENT_EXTENSIONS:
        kind = "document"
    elif extension in AUDIO_EXTENSIONS:
        kind = "audio"
    elif extension in VIDEO_EXTENSIONS:
        kind = "video"
    elif extension in IMAGE_EXTENSIONS:
        kind = "image"
    elif extension in ARCHIVE_EXTENSIONS:
        kind = "archive"
    else:
        kind = "other"

    is_answer = bool(ANSWER_PATTERN.search(searchable))
    is_transcript = bool(TRANSCRIPT_PATTERN.search(searchable))
    is_full_paper = (
        kind == "document"
        and not is_answer
        and not is_transcript
        and bool(FULL_PAPER_PATTERN.search(path.name))
        and not sections
    )
    section_evidence = "explicit"
    if is_full_paper:
        sections.update(SECTIONS)
        section_evidence = "inferred_full_paper"

    return {
        "kind": kind,
        "sections": sorted(sections),
        "section_evidence": section_evidence,
        "is_answer": is_answer,
        "is_transcript": is_transcript,
        "is_full_paper": is_full_paper,
        "is_partial": bool(PARTIAL_PATTERN.search(searchable)),
    }


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def build_file_records(
    files: list[Path],
    assignments: dict[Path, SourceAssignment],
    root: Path,
    text_threshold: int,
    probe_pdfs: bool,
    probe_media_files: bool,
    workers: int,
) -> list[dict[str, Any]]:
    assigned_files = sorted(assignments, key=lambda item: str(item).lower())
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        hashes = list(pool.map(sha256_file, assigned_files))

    hash_cache: dict[str, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    for path, digest in zip(assigned_files, hashes):
        extension = path.suffix.lower()
        cached = hash_cache.get(digest)
        if cached is None:
            probe: dict[str, Any] = {}
            archive_info: dict[str, Any] = {}
            if extension == ".pdf" and probe_pdfs:
                probe.update(probe_pdf(path, text_threshold))
            elif extension in AUDIO_EXTENSIONS | VIDEO_EXTENSIONS and probe_media_files:
                probe.update(probe_media(path))
            elif extension in ARCHIVE_EXTENSIONS:
                archive_info = inspect_archive(path)
                probe.update(archive_info)
            cached = {"probe": probe, "archive_info": archive_info}
            hash_cache[digest] = cached

        classification = classify_file(path, cached["archive_info"])
        assignment = assignments[path]
        stat = path.stat()
        records.append(
            {
                "exam_key": assignment.exam_key,
                "exam_date": assignment.exam_date,
                "variant": assignment.variant,
                "source_dir": _relative(assignment.source_dir, root),
                "path": _relative(path, root),
                "name": path.name,
                "extension": extension,
                "size_bytes": stat.st_size,
                "sha256": digest,
                **classification,
                **cached["probe"],
            }
        )
    return records


def section_status(section: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = [row for row in rows if section in row["sections"]]
    explicit = [row for row in evidence if row["section_evidence"] == "explicit"]
    inferred = [row for row in evidence if row["section_evidence"] == "inferred_full_paper"]
    content = [
        row
        for row in evidence
        if row["kind"] in {"document", "image"}
        and not row["is_transcript"]
        and not (row["is_answer"] and section not in row["sections"])
    ]
    playable_media = [
        row
        for row in evidence
        if row["kind"] in {"audio", "video"}
        and row.get("media_status", "playable") == "playable"
    ]
    archived_media = [
        row
        for row in evidence
        if row["kind"] == "archive"
        and any(ext in AUDIO_EXTENSIONS | VIDEO_EXTENSIONS for ext in row.get("archive_extensions", {}))
    ]

    if section in {"reading", "writing"}:
        status = "ready" if content else "missing"
    elif content and playable_media:
        status = "ready"
    elif content and archived_media:
        status = "archive_only"
    elif content:
        status = "content_only"
    elif playable_media:
        status = "media_only"
    elif archived_media:
        status = "archive_only_no_content"
    else:
        status = "missing"

    return {
        "status": status,
        "content_files": len(content),
        "playable_media_files": len(playable_media),
        "archive_media_files": len(archived_media),
        "explicit_evidence_files": len(explicit),
        "inferred_evidence_files": len(inferred),
    }


def build_exam_records(file_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in file_records:
        grouped[row["exam_key"]].append(row)

    exams: list[dict[str, Any]] = []
    for exam_key, rows in grouped.items():
        if not any(
            row["sections"]
            or row["is_answer"]
            or row["is_transcript"]
            or row["is_full_paper"]
            for row in rows
        ):
            continue
        unique_hashes = {row["sha256"] for row in rows}
        section_map = {section: section_status(section, rows) for section in SECTIONS}
        ocr_counts = Counter(
            row.get("ocr_status")
            for row in rows
            if row["extension"] == ".pdf" and row.get("ocr_status")
        )
        media_formats = Counter(
            row["extension"].lstrip(".")
            for row in rows
            if row["kind"] in {"audio", "video", "archive"}
        )
        missing_sections = [
            section
            for section, detail in section_map.items()
            if detail["status"] in {"missing", "media_only", "archive_only_no_content"}
        ]
        not_ready_sections = [
            section
            for section, detail in section_map.items()
            if detail["status"] != "ready"
        ]
        source_dirs = sorted({row["source_dir"] for row in rows})
        asset_complete = not not_ready_sections
        has_ocr_blocker = bool(
            ocr_counts.get("ocr_required")
            or ocr_counts.get("low_text_check")
            or ocr_counts.get("pdf_read_error")
        )
        import_candidate = bool(
            asset_complete
            and rows[0]["variant"] != "MIXED"
            and not has_ocr_blocker
            and not any(row["is_partial"] for row in rows)
            and any(row["is_answer"] for row in rows)
        )
        exams.append(
            {
                "exam_key": exam_key,
                "exam_date": rows[0]["exam_date"],
                "variant": rows[0]["variant"],
                "source_dirs": source_dirs,
                "source_dir_count": len(source_dirs),
                "file_count": len(rows),
                "unique_file_count": len(unique_hashes),
                "duplicate_copy_count": len(rows) - len(unique_hashes),
                "size_bytes": sum(row["size_bytes"] for row in rows),
                "unique_size_bytes": sum(
                    next(row["size_bytes"] for row in rows if row["sha256"] == digest)
                    for digest in unique_hashes
                ),
                "sections": section_map,
                "missing_sections": missing_sections,
                "not_ready_sections": not_ready_sections,
                "asset_complete": asset_complete,
                "has_ocr_blocker": has_ocr_blocker,
                "import_candidate": import_candidate,
                "answer_files": sum(1 for row in rows if row["is_answer"]),
                "transcript_files": sum(1 for row in rows if row["is_transcript"]),
                "partial_markers": sorted({row["path"] for row in rows if row["is_partial"]}),
                "ocr_counts": dict(sorted(ocr_counts.items())),
                "media_formats": dict(sorted(media_formats.items())),
            }
        )
    return sorted(exams, key=lambda row: (row["exam_date"], row["variant"]))


def build_duplicate_groups(file_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in file_records:
        grouped[row["sha256"]].append(row)
    duplicates = []
    for digest, rows in grouped.items():
        if len(rows) < 2:
            continue
        duplicates.append(
            {
                "sha256": digest,
                "copy_count": len(rows),
                "size_bytes": rows[0]["size_bytes"],
                "reclaimable_bytes": rows[0]["size_bytes"] * (len(rows) - 1),
                "exam_keys": sorted({row["exam_key"] for row in rows}),
                "paths": sorted(row["path"] for row in rows),
            }
        )
    return sorted(duplicates, key=lambda row: (-row["reclaimable_bytes"], row["sha256"]))


def build_inventory(
    root: Path,
    default_year: int = 2026,
    text_threshold: int = 200,
    probe_pdfs: bool = True,
    probe_media_files: bool = True,
    workers: int = 4,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    files = list(iter_relevant_files(root))
    assignments, unmatched = assign_sources(files, root, default_year)
    file_records = build_file_records(
        files,
        assignments,
        root,
        text_threshold,
        probe_pdfs,
        probe_media_files,
        workers,
    )
    exams = build_exam_records(file_records)
    duplicates = build_duplicate_groups(file_records)
    exam_keys = {exam["exam_key"] for exam in exams}
    unclassified_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in file_records:
        if row["exam_key"] not in exam_keys:
            unclassified_groups[row["exam_key"]].append(row)
    unclassified_collections = [
        {
            "candidate_key": key,
            "source_dirs": sorted({row["source_dir"] for row in rows}),
            "files": sorted(row["path"] for row in rows),
        }
        for key, rows in sorted(unclassified_groups.items())
    ]
    extension_counts = Counter(row["extension"].lstrip(".") for row in file_records)
    ocr_counts = Counter(
        row.get("ocr_status")
        for row in file_records
        if row["extension"] == ".pdf" and row.get("ocr_status")
    )
    section_status_counts = {
        section: dict(
            sorted(Counter(exam["sections"][section]["status"] for exam in exams).items())
        )
        for section in SECTIONS
    }
    return {
        "notice": NOTICE,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_root": str(root),
        "rules": {
            "default_year": default_year,
            "pdf_text_threshold": text_threshold,
            "pdf_probe_enabled": probe_pdfs,
            "media_probe_enabled": probe_media_files,
            "exam_grouping": "nearest dated directory + normalized卷别",
            "duplicate_detection": "exact SHA-256 match",
        },
        "summary": {
            "unique_exam_count": len(exams),
            "exam_file_count": sum(1 for row in file_records if row["exam_key"] in exam_keys),
            "dated_file_count": len(file_records),
            "dated_unique_file_count": len({row["sha256"] for row in file_records}),
            "unmatched_relevant_file_count": len(unmatched),
            "unclassified_dated_collection_count": len(unclassified_collections),
            "duplicate_group_count": len(duplicates),
            "duplicate_copy_count": sum(row["copy_count"] - 1 for row in duplicates),
            "reclaimable_bytes": sum(row["reclaimable_bytes"] for row in duplicates),
            "asset_complete_exam_count": sum(1 for exam in exams if exam["asset_complete"]),
            "structured_import_candidate_count": sum(
                1 for exam in exams if exam["import_candidate"]
            ),
            "extension_counts": dict(sorted(extension_counts.items())),
            "ocr_counts": dict(sorted(ocr_counts.items())),
            "section_status_counts": section_status_counts,
        },
        "exams": exams,
        "files": file_records,
        "duplicates": duplicates,
        "unclassified_dated_collections": unclassified_collections,
        "unmatched_relevant_files": sorted(_relative(path, root) for path in unmatched),
    }


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def flatten_exam_for_csv(exam: dict[str, Any]) -> dict[str, Any]:
    row = {
        "exam_key": exam["exam_key"],
        "exam_date": exam["exam_date"],
        "variant": exam["variant"],
        "source_dirs": " | ".join(exam["source_dirs"]),
        "file_count": exam["file_count"],
        "unique_file_count": exam["unique_file_count"],
        "duplicate_copy_count": exam["duplicate_copy_count"],
        "size_mb": round(exam["unique_size_bytes"] / 1024 / 1024, 2),
        "answer_files": exam["answer_files"],
        "transcript_files": exam["transcript_files"],
        "asset_complete": exam["asset_complete"],
        "has_ocr_blocker": exam["has_ocr_blocker"],
        "import_candidate": exam["import_candidate"],
        "missing_sections": ",".join(exam["missing_sections"]),
        "not_ready_sections": ",".join(exam["not_ready_sections"]),
        "partial_markers": " | ".join(exam["partial_markers"]),
        "ocr_counts": json.dumps(exam["ocr_counts"], ensure_ascii=False),
        "media_formats": json.dumps(exam["media_formats"], ensure_ascii=False),
    }
    for section in SECTIONS:
        row[f"{section}_status"] = exam["sections"][section]["status"]
    return row


def flatten_file_for_csv(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "sections": ",".join(row["sections"]),
        "archive_sections": ",".join(row.get("archive_sections") or []),
        "archive_extensions": json.dumps(row.get("archive_extensions") or {}, ensure_ascii=False),
    }


def markdown_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_summary(inventory: dict[str, Any]) -> str:
    summary = inventory["summary"]
    lines = [
        "# 托福资料盘点报告",
        "",
        f"> {NOTICE}",
        "",
        f"- 生成时间：{inventory['generated_at']}",
        f"- 扫描目录：`{inventory['source_root']}`",
        f"- 唯一套卷：**{summary['unique_exam_count']}**",
        f"- 套卷文件：**{summary['exam_file_count']}**",
        f"- 精确重复组：**{summary['duplicate_group_count']}**",
        f"- 多余副本：**{summary['duplicate_copy_count']}**",
        f"- 可回收空间：**{summary['reclaimable_bytes'] / 1024 / 1024:.1f} MB**",
        f"- 四科题面/媒体齐备：**{summary['asset_complete_exam_count']}**",
        f"- 可直接进入结构化导入：**{summary['structured_import_candidate_count']}**",
        f"- 有日期但无法识别科目的目录：**{summary['unclassified_dated_collection_count']}**",
        f"- 未归入日期套卷的相关文件：**{summary['unmatched_relevant_file_count']}**",
        "",
        "## 套卷完整度",
        "",
        "| 套卷 | 来源目录 | 阅读 | 听力 | 口语 | 写作 | 答案 | 可导入 | OCR | 备注 |",
        "|---|---:|---|---|---|---|---:|---|---|---|",
    ]
    for exam in inventory["exams"]:
        ocr_summary = ", ".join(
            f"{key}:{value}" for key, value in exam["ocr_counts"].items()
        ) or "-"
        notes = []
        if exam["duplicate_copy_count"]:
            notes.append(f"重复副本 {exam['duplicate_copy_count']}")
        if exam["partial_markers"]:
            notes.append(f"部分/缺失标记 {len(exam['partial_markers'])}")
        if exam["variant"] == "MIXED":
            notes.append("同目录存在多个卷别，需人工拆分")
        lines.append(
            "| {key} | {sources} | {reading} | {listening} | {speaking} | "
            "{writing} | {answers} | {candidate} | {ocr} | {notes} |".format(
                key=markdown_escape(exam["exam_key"]),
                sources=exam["source_dir_count"],
                reading=exam["sections"]["reading"]["status"],
                listening=exam["sections"]["listening"]["status"],
                speaking=exam["sections"]["speaking"]["status"],
                writing=exam["sections"]["writing"]["status"],
                answers=exam["answer_files"],
                candidate="是" if exam["import_candidate"] else "否",
                ocr=markdown_escape(ocr_summary),
                notes=markdown_escape("；".join(notes) or "-"),
            )
        )

    lines.extend(
        [
            "",
            "## 待人工识别",
            "",
        ]
    )
    if inventory["unclassified_dated_collections"]:
        for collection in inventory["unclassified_dated_collections"]:
            lines.append(
                f"- `{markdown_escape(collection['candidate_key'])}`："
                f"{markdown_escape(', '.join(collection['source_dirs']))}；"
                f"{len(collection['files'])} 个文件"
            )
    else:
        lines.append("- 无")

    lines.extend(
        [
            "",
            "## OCR 状态",
            "",
            "| 状态 | PDF 数量 |",
            "|---|---:|",
        ]
    )
    for status, count in summary["ocr_counts"].items():
        lines.append(f"| {markdown_escape(status)} | {count} |")

    lines.extend(
        [
            "",
            "## 媒体格式",
            "",
            "| 扩展名 | 文件数 |",
            "|---|---:|",
        ]
    )
    for extension, count in summary["extension_counts"].items():
        if f".{extension}" in AUDIO_EXTENSIONS | VIDEO_EXTENSIONS | ARCHIVE_EXTENSIONS:
            lines.append(f"| {markdown_escape(extension)} | {count} |")

    lines.extend(
        [
            "",
            "## 重复文件",
            "",
            "| 副本数 | 大小 MB | 可回收 MB | 所属套卷 | 路径示例 |",
            "|---:|---:|---:|---|---|",
        ]
    )
    for group in inventory["duplicates"][:30]:
        lines.append(
            "| {copies} | {size:.1f} | {reclaim:.1f} | {keys} | {path} |".format(
                copies=group["copy_count"],
                size=group["size_bytes"] / 1024 / 1024,
                reclaim=group["reclaimable_bytes"] / 1024 / 1024,
                keys=markdown_escape(", ".join(group["exam_keys"])),
                path=markdown_escape(group["paths"][0]),
            )
        )
    if not inventory["duplicates"]:
        lines.append("| 0 | 0 | 0 | - | - |")

    lines.extend(
        [
            "",
            "## 状态说明",
            "",
            "- `ready`：题面已识别；听力/口语同时存在可播放媒体。",
            "- `content_only`：有题面，但缺少可直接播放的媒体。",
            "- `media_only`：有媒体，但没有识别到题面。",
            "- `archive_only`：题面存在，媒体仍在压缩包内，需要解压和转码。",
            "- `ocr_required`：PDF 基本无文本层，需要 OCR。",
            "- `low_text_check`：文本层过少，需要人工确认是否为封面、答案页或扫描件。",
            "",
            "完整明细见 `inventory.json`、`exams.csv`、`files.csv` 和 `duplicates.csv`。",
            "",
        ]
    )
    return "\n".join(lines)


def write_reports(inventory: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(render_summary(inventory), encoding="utf-8")

    exam_rows = [flatten_exam_for_csv(exam) for exam in inventory["exams"]]
    exam_fields = [
        "exam_key",
        "exam_date",
        "variant",
        "source_dirs",
        "file_count",
        "unique_file_count",
        "duplicate_copy_count",
        "size_mb",
        "reading_status",
        "listening_status",
        "speaking_status",
        "writing_status",
        "asset_complete",
        "has_ocr_blocker",
        "import_candidate",
        "answer_files",
        "transcript_files",
        "missing_sections",
        "not_ready_sections",
        "partial_markers",
        "ocr_counts",
        "media_formats",
    ]
    write_csv(output_dir / "exams.csv", exam_fields, exam_rows)

    file_fields = [
        "exam_key",
        "exam_date",
        "variant",
        "source_dir",
        "path",
        "name",
        "extension",
        "kind",
        "sections",
        "section_evidence",
        "is_answer",
        "is_transcript",
        "is_full_paper",
        "is_partial",
        "size_bytes",
        "sha256",
        "ocr_status",
        "text_characters",
        "pages",
        "media_status",
        "container",
        "duration_seconds",
        "codec_type",
        "codec",
        "sample_rate",
        "channels",
        "width",
        "height",
        "archive_status",
        "archive_members",
        "archive_extensions",
        "archive_sections",
        "probe_error",
    ]
    write_csv(
        output_dir / "files.csv",
        file_fields,
        (flatten_file_for_csv(row) for row in inventory["files"]),
    )

    duplicate_rows = []
    for index, group in enumerate(inventory["duplicates"], 1):
        for path in group["paths"]:
            duplicate_rows.append(
                {
                    "group_id": index,
                    "sha256": group["sha256"],
                    "copy_count": group["copy_count"],
                    "size_bytes": group["size_bytes"],
                    "reclaimable_bytes": group["reclaimable_bytes"],
                    "exam_keys": ",".join(group["exam_keys"]),
                    "path": path,
                }
            )
    write_csv(
        output_dir / "duplicates.csv",
        [
            "group_id",
            "sha256",
            "copy_count",
            "size_bytes",
            "reclaimable_bytes",
            "exam_keys",
            "path",
        ],
        duplicate_rows,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventory dated TOEFL exam materials and generate import-readiness reports."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--text-threshold", type=int, default=200)
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--skip-pdf-probe", action="store_true")
    parser.add_argument("--skip-media-probe", action="store_true")
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    if not source.is_dir():
        print(f"Source directory not found: {source}", file=sys.stderr)
        return 2

    inventory = build_inventory(
        source,
        default_year=args.year,
        text_threshold=args.text_threshold,
        probe_pdfs=not args.skip_pdf_probe,
        probe_media_files=not args.skip_media_probe,
        workers=args.workers,
    )
    output = args.output.expanduser().resolve()
    write_reports(inventory, output)

    summary = inventory["summary"]
    print(NOTICE)
    print(f"Unique exams: {summary['unique_exam_count']}")
    print(f"Exam files: {summary['exam_file_count']}")
    print(f"Duplicate groups: {summary['duplicate_group_count']}")
    print(f"Asset-complete exams: {summary['asset_complete_exam_count']}")
    print(f"Structured import candidates: {summary['structured_import_candidate_count']}")
    print(f"Reports: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
