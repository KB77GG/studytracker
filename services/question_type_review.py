"""Post-submission review and current-audio guidance for specialty practice.

Question-type snapshots freeze the source paper and its original question
coordinates.  Audio files can later be replaced by verified dialogue-only
tracks, so current playback coordinates are derived at request time instead
of being written back into the frozen snapshot or its hash.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any

AUDIO_GUIDANCE_VERSION = 1
QUESTION_CONTEXT_BEFORE_SECONDS = 3.0
QUESTION_CONTEXT_AFTER_SECONDS = 2.0
GROUP_CONTEXT_BEFORE_SECONDS = 8.0
GROUP_CONTEXT_AFTER_SECONDS = 3.0
_SPEAKER_PREFIX_RE = re.compile(r"^\s*[A-Za-z][A-Za-z .’'\-]{0,30}:\s*")
_FROZEN_EVIDENCE_MIN_COVERAGE = 1.0


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _safe_asset_name(value: Any) -> str:
    name = str(value or "").strip()
    path = Path(name)
    if not name or path.is_absolute() or ".." in path.parts:
        return ""
    return name


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


@lru_cache(maxsize=64)
def _versioned_file_sha256(path_value: str, size: int, mtime_ns: int) -> str:
    """Hash a concrete file version once; stat fields invalidate the cache."""

    del size, mtime_ns
    digest = hashlib.sha256()
    try:
        with Path(path_value).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _timeline_overrides(project_root: Path) -> dict:
    payload = _load_json(project_root / "data/listening_audio_timeline_overrides.json")
    assets = payload.get("assets")
    return assets if isinstance(assets, dict) else {}


def _override_media_version(override: dict, media_path: Path | None) -> dict | None:
    """Select one explicitly trusted same-name media version.

    Some production MP3s were losslessly remuxed to add a seek index, while
    IELTS 20 T1S1 can legitimately be either the dialogue-only track or the
    original full Section.  The filename alone therefore cannot select a
    timeline basis.  When the concrete file exists, require an exact
    size/hash match.  A named default is only used by fixture environments
    where the ignored MP3 asset is intentionally absent.
    """

    versions = override.get("media_versions")
    if not isinstance(versions, list):
        return override
    candidates = [row for row in versions if isinstance(row, dict)]
    if media_path and media_path.is_file():
        media_stat = media_path.stat()
        media_sha256 = _versioned_file_sha256(
            str(media_path.resolve()), media_stat.st_size, media_stat.st_mtime_ns
        )
        for candidate in candidates:
            expected_size = candidate.get("media_size_bytes")
            expected_sha256 = str(candidate.get("media_sha256") or "").strip()
            if (
                _finite_number(expected_size)
                and int(expected_size) == media_stat.st_size
                and expected_sha256
                and expected_sha256 == media_sha256
            ):
                return candidate
        return None

    default_id = str(override.get("default_media_version") or "").strip()
    return next(
        (
            candidate
            for candidate in candidates
            if str(candidate.get("id") or "").strip() == default_id
        ),
        None,
    )


def _segments(payload: dict) -> list[dict]:
    rows = []
    for part in payload.get("parts") or []:
        if not isinstance(part, dict):
            continue
        rows.extend(row for row in part.get("segments") or [] if isinstance(row, dict))
    return rows


def _normalized_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
    return "".join(re.findall(r"[a-z0-9]+", normalized))


def _normalized_spoken_text(value: Any) -> str:
    text = _SPEAKER_PREFIX_RE.sub("", str(value or "").strip())
    return _normalized_text(text)


def _word_tokens(value: Any) -> list[str]:
    text = _SPEAKER_PREFIX_RE.sub("", str(value or "").strip())
    normalized = unicodedata.normalize("NFKC", text).lower()
    return re.findall(r"[a-z0-9]+", normalized)


def _matching_frozen_positions(
    frozen_tokens: list[str], candidate_tokens: list[str]
) -> tuple[set[int], int]:
    """Return substantial token matches from one current sidecar segment."""

    if not frozen_tokens or not candidate_tokens:
        return set(), 0
    comparable_length = min(len(frozen_tokens), len(candidate_tokens))
    minimum_block = 1 if comparable_length <= 4 else 2 if comparable_length <= 10 else 3
    positions = set()
    longest = 0
    matcher = SequenceMatcher(
        None,
        frozen_tokens,
        candidate_tokens,
        autojunk=False,
    )
    for block in matcher.get_matching_blocks():
        if block.size < minimum_block:
            continue
        positions.update(range(block.a, block.a + block.size))
        longest = max(longest, block.size)
    return positions, longest


def _frozen_coverage(frozen_tokens: list[str], candidate_tokens: list[str]) -> float:
    if not frozen_tokens:
        return 0.0
    matcher = SequenceMatcher(
        None,
        frozen_tokens,
        candidate_tokens,
        autojunk=False,
    )
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / len(frozen_tokens)


def _covering_segment_indexes(
    frozen_text: Any,
    frozen_order: int,
    segments: list[dict],
    segment_tokens: list[list[str]],
) -> list[int]:
    """Choose an ordered one-to-many sidecar span covering frozen evidence.

    A frozen transcript row can be split across several current sidecar rows.
    Partial similarity is therefore only trusted when the selected rows, in
    sidecar order, recover the complete frozen row's word sequence.
    """

    frozen_tokens = _word_tokens(frozen_text)
    if not frozen_tokens:
        return []
    candidates = []
    for index, tokens in enumerate(segment_tokens):
        positions, longest = _matching_frozen_positions(frozen_tokens, tokens)
        if not positions:
            continue
        candidates.append(
            {
                "index": index,
                "positions": positions,
                "longest": longest,
                "distance": abs(_candidate_order(segments[index], index) - frozen_order),
            }
        )

    selected = []
    covered: set[int] = set()
    remaining = candidates
    while remaining and len(covered) / len(frozen_tokens) < _FROZEN_EVIDENCE_MIN_COVERAGE:
        ranked = []
        for candidate in remaining:
            new_positions = candidate["positions"] - covered
            if not new_positions:
                continue
            ranked.append(
                (
                    len(new_positions),
                    candidate["longest"],
                    -candidate["distance"],
                    -candidate["index"],
                    candidate,
                )
            )
        if not ranked:
            break
        chosen = max(ranked)[-1]
        selected.append(chosen["index"])
        covered.update(chosen["positions"])
        remaining = [row for row in remaining if row["index"] != chosen["index"]]

    selected.sort()
    combined = [token for index in selected for token in segment_tokens[index]]
    if _frozen_coverage(frozen_tokens, combined) < _FROZEN_EVIDENCE_MIN_COVERAGE:
        return []
    return selected


def _candidate_order(segment: dict, index: int) -> int:
    source_order = segment.get("source_order")
    return int(source_order) if isinstance(source_order, int) else index


def _closest_candidate(
    indexes: list[int], segments: list[dict], frozen_order: int
) -> int:
    return min(
        indexes,
        key=lambda index: (
            abs(_candidate_order(segments[index], index) - frozen_order),
            index,
        ),
    )


def _frozen_segment_map(section: dict, segments: list[dict]) -> dict[int, list[int]]:
    """Bind frozen transcript rows to current sidecar rows by their content.

    Frozen question coordinates are only used to select the original evidence
    rows.  The selected text is then aligned to the sidecar, so a numeric
    offset or a same-name replacement cannot silently turn a cue into evidence.
    """

    segment_texts = [_normalized_spoken_text(segment.get("text")) for segment in segments]
    segment_tokens = [_word_tokens(segment.get("text")) for segment in segments]
    exact_lookup: dict[str, list[int]] = {}
    for index, full in enumerate(segment_texts):
        if full:
            exact_lookup.setdefault(full, []).append(index)

    mapping = {}
    for row_index, row in enumerate(section.get("transcript") or []):
        frozen_full = _normalized_spoken_text(row.get("en"))
        frozen_order = row.get("order")
        if not isinstance(frozen_order, int):
            frozen_order = row_index
        exact = exact_lookup.get(frozen_full) or []
        if exact:
            mapping[row_index] = [
                _closest_candidate(exact, segments, frozen_order)
            ]
            continue

        selected = _covering_segment_indexes(
            row.get("en"),
            frozen_order,
            segments,
            segment_tokens,
        )
        if selected:
            mapping[row_index] = selected
    return mapping


def _valid_range(start: Any, end: Any) -> bool:
    return _finite_number(start) and _finite_number(end) and 0 <= start < end


def _segment_source_range(segment: dict) -> tuple[float, float] | None:
    start, end = segment.get("original_start"), segment.get("original_end")
    if not _valid_range(start, end):
        start_ms, end_ms = segment.get("source_start_time"), segment.get(
            "source_end_time"
        )
        if _finite_number(start_ms) and _finite_number(end_ms):
            start, end = float(start_ms) / 1000.0, float(end_ms) / 1000.0
    if not _valid_range(start, end):
        return None
    return float(start), float(end)


def _segment_target_range(segment: dict, basis: str) -> tuple[float, float] | None:
    if basis == "sidecar_current":
        start, end = segment.get("start"), segment.get("end")
        return (float(start), float(end)) if _valid_range(start, end) else None
    return _segment_source_range(segment)


def _timeline_contract(
    section: dict,
    *,
    static_root: Path,
    audio_root: Path | None,
    project_root: Path,
) -> dict:
    audio_name = _safe_asset_name(section.get("audio"))
    if not audio_name:
        return {"available": False, "reason": "Section 音频引用无效"}
    sidecar_name = str(Path(audio_name).with_suffix(".json"))
    sidecar_path = static_root / "listening" / sidecar_name
    sidecar = _load_json(sidecar_path)
    expected_id = Path(audio_name).stem
    if not sidecar or str(sidecar.get("id") or "") != expected_id:
        return {"available": False, "reason": "当前音频缺少匹配的定位数据"}

    raw_sidecar = sidecar_path.read_bytes()
    sidecar_sha256 = hashlib.sha256(raw_sidecar).hexdigest()
    override = _timeline_overrides(project_root).get(audio_name)
    basis = ""
    expected_duration = None
    media_version = ""
    if isinstance(override, dict):
        if (
            override.get("sidecar") != sidecar_name
            or override.get("sidecar_sha256") != sidecar_sha256
        ):
            return {"available": False, "reason": "定位数据版本与当前音频不匹配"}
        media_path = audio_root / audio_name if audio_root else None
        selected_override = _override_media_version(override, media_path)
        if selected_override is None:
            return {"available": False, "reason": "当前音频文件版本与定位数据不匹配"}
        basis = str(selected_override.get("timeline_basis") or "")
        expected_duration = selected_override.get("media_duration_seconds")
        media_version = str(selected_override.get("id") or "").strip()
        if selected_override is override and media_path and media_path.is_file():
            media_stat = media_path.stat()
            expected_size = selected_override.get("media_size_bytes")
            expected_media_sha256 = str(
                selected_override.get("media_sha256") or ""
            ).strip()
            if _finite_number(expected_size) and media_stat.st_size != int(expected_size):
                return {"available": False, "reason": "当前音频文件版本与定位数据不匹配"}
            if expected_media_sha256 and _versioned_file_sha256(
                str(media_path.resolve()), media_stat.st_size, media_stat.st_mtime_ns
            ) != expected_media_sha256:
                return {"available": False, "reason": "当前音频文件版本与定位数据不匹配"}
    elif sidecar.get("audio") == audio_name:
        basis = "sidecar_current"
    else:
        source = sidecar.get("source") if isinstance(sidecar.get("source"), dict) else {}
        mapping = source.get("mapping") if isinstance(source.get("mapping"), dict) else {}
        original_names = {
            _safe_asset_name(source.get("original_audio")),
            _safe_asset_name(mapping.get("source_audio_file")),
        }
        if audio_name in original_names:
            basis = "source_original"
    if basis not in {"sidecar_current", "source_original"}:
        return {"available": False, "reason": "定位数据与当前 Section 音轨不匹配"}

    segment_rows = _segments(sidecar)
    if not segment_rows:
        return {"available": False, "reason": "当前音频定位数据为空"}
    source_ranges = [
        source_range
        for row in segment_rows
        if (source_range := _segment_source_range(row)) is not None
    ]
    target_ranges = [
        target_range
        for row in segment_rows
        if (target_range := _segment_target_range(row, basis)) is not None
    ]
    if not source_ranges or len(target_ranges) != len(segment_rows):
        return {"available": False, "reason": "当前音轨与原题坐标映射不完整"}

    timeline_end = max(end for _start, end in target_ranges)
    transcript = []
    for index, row in enumerate(segment_rows):
        target_range = _segment_target_range(row, basis)
        if target_range is None:
            continue
        start, end = target_range
        transcript.append(
            {
                "order": index,
                "start": round(start, 3),
                "end": round(end, 3),
                "en": str(row.get("text") or "").strip(),
                "cn": str(row.get("translation") or "").strip(),
            }
        )
    return {
        "available": True,
        "audio": audio_name,
        "basis": basis,
        "media_version": media_version or None,
        "sidecar_sha256": sidecar_sha256,
        "timeline_end": round(timeline_end, 3),
        "expected_duration": (
            round(float(expected_duration), 3)
            if _finite_number(expected_duration)
            else None
        ),
        "segments": segment_rows,
        "frozen_transcript": section.get("transcript") or [],
        "frozen_segment_map": _frozen_segment_map(section, segment_rows),
        "transcript": transcript,
    }


def _question_audio_review(question: dict, contract: dict) -> dict:
    unavailable = {
        "available": False,
        "reason": "本题定位边界不可用，已回退完整 Section",
    }
    source_start, source_end = question.get("start"), question.get("end")
    if not _valid_range(source_start, source_end):
        return unavailable
    if not contract.get("available"):
        return {"available": False, "reason": contract.get("reason") or unavailable["reason"]}

    frozen_rows = contract.get("frozen_transcript") or []
    row_map = contract.get("frozen_segment_map") or {}
    frozen_indexes = [
        index
        for index, row in enumerate(frozen_rows)
        if _valid_range(row.get("start"), row.get("end"))
        and max(float(source_start), float(row["start"]))
        < min(float(source_end), float(row["end"]))
    ]
    if not frozen_indexes or any(index not in row_map for index in frozen_indexes):
        return unavailable
    segment_indexes = sorted(
        {
            segment_index
            for frozen_index in frozen_indexes
            for segment_index in row_map.get(frozen_index, [])
        }
    )
    selected = []
    for segment_index in segment_indexes:
        segment = contract["segments"][segment_index]
        target_range = _segment_target_range(segment, contract["basis"])
        if target_range is not None:
            selected.append((segment, target_range[0], target_range[1]))
    if not selected:
        return unavailable

    mapped_start = min(row[1] for row in selected)
    mapped_end = max(row[2] for row in selected)
    if not _valid_range(mapped_start, mapped_end):
        return unavailable

    evidence = []
    seen = set()
    for row, _start, _end in selected:
        text = str(row.get("text") or "").strip()
        translation = str(row.get("translation") or "").strip()
        key = (text, translation)
        if not text or key in seen:
            continue
        seen.add(key)
        evidence.append({"text": text, "translation": translation})
    timeline_end = float(contract["timeline_end"])
    clip_start = max(0.0, mapped_start - QUESTION_CONTEXT_BEFORE_SECONDS)
    clip_end = min(timeline_end, mapped_end + QUESTION_CONTEXT_AFTER_SECONDS)
    if not _valid_range(clip_start, clip_end):
        return unavailable
    return {
        "available": True,
        "start": round(clip_start, 3),
        "end": round(clip_end, 3),
        "answer_start": round(mapped_start, 3),
        "answer_end": round(mapped_end, 3),
        "basis": contract["basis"],
        "timeline_fingerprint": contract["sidecar_sha256"],
        "expected_duration": contract.get("expected_duration"),
        "evidence": evidence,
    }


def _group_practice_audio(questions: list[dict], contract: dict) -> dict:
    reviews = [question.get("audio_review") for question in questions]
    if not reviews or any(not isinstance(row, dict) or not row.get("available") for row in reviews):
        return {
            "available": False,
            "reason": "题组定位不可用，可播放完整 Section",
        }
    timeline_end = float(contract["timeline_end"])
    start = max(
        0.0,
        min(float(row["answer_start"]) for row in reviews) - GROUP_CONTEXT_BEFORE_SECONDS,
    )
    end = min(
        timeline_end,
        max(float(row["answer_end"]) for row in reviews) + GROUP_CONTEXT_AFTER_SECONDS,
    )
    if not _valid_range(start, end):
        return {
            "available": False,
            "reason": "题组定位不可用，可播放完整 Section",
        }
    return {
        "available": True,
        "start": round(start, 3),
        "end": round(end, 3),
        "basis": contract["basis"],
        "timeline_fingerprint": contract["sidecar_sha256"],
        "expected_duration": contract.get("expected_duration"),
    }


def derive_listening_payload(
    payload: dict,
    *,
    static_root: Path,
    audio_root: Path | None = None,
    project_root: Path | None = None,
) -> dict:
    """Return a review-capable copy aligned to the currently served MP3 files."""

    result = copy.deepcopy(payload)
    root = project_root or static_root.parent
    for section in result.get("sections") or []:
        contract = _timeline_contract(
            section,
            static_root=static_root,
            audio_root=audio_root,
            project_root=root,
        )
        section["audio_timeline"] = {
            "version": AUDIO_GUIDANCE_VERSION,
            "available": bool(contract.get("available")),
            "basis": contract.get("basis"),
            "media_version": contract.get("media_version"),
            "fingerprint": contract.get("sidecar_sha256"),
            "expected_duration": contract.get("expected_duration"),
            "reason": contract.get("reason"),
        }
        if contract.get("available"):
            section["transcript"] = contract["transcript"]
        for group in section.get("groups") or []:
            questions = [row for row in group.get("questions") or [] if isinstance(row, dict)]
            for question in questions:
                question["audio_review"] = _question_audio_review(question, contract)
            group["practice_audio"] = _group_practice_audio(questions, contract)
    return result


def review_snapshot(
    snapshot: dict,
    *,
    static_root: Path,
    audio_root: Path | None = None,
    project_root: Path | None = None,
) -> dict:
    """Build an authorized post-submission view without mutating the snapshot."""

    result = copy.deepcopy(snapshot)
    if result.get("subject") == "listening":
        result["payload"] = derive_listening_payload(
            result.get("payload") or {},
            static_root=static_root,
            audio_root=audio_root,
            project_root=project_root,
        )
    return result


def reading_evidence(question: dict) -> list[str]:
    central = question.get("central_sentences")
    if isinstance(central, list):
        rows = central
    elif isinstance(central, dict):
        rows = central.get("sentences") or central.get("central_sentences") or []
    else:
        rows = []
    evidence = []
    for row in rows:
        text = row.get("sentence") if isinstance(row, dict) else row
        text = str(text or "").strip()
        if text and text not in evidence:
            evidence.append(text)
    return evidence


def review_question_index(snapshot: dict) -> dict[str, dict]:
    payload = snapshot.get("payload") if isinstance(snapshot, dict) else {}
    unit_key = "sections" if snapshot.get("subject") == "listening" else "passages"
    index = {}
    for unit in (payload or {}).get(unit_key) or []:
        for group in unit.get("groups") or []:
            for question in group.get("questions") or []:
                key = str(question.get("id") or question.get("number") or "")
                if key:
                    index[key] = question
    return index
