"""Read and publish the public weekly revision list without touching student data.

Source titles are never used to guess a local exercise. Only reviewed mappings
whose source and local content fingerprints still match can become practice links.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from services.practice_library_offline import load_offline_test_ids

SUBJECT_PARTS = {"reading": 3, "listening": 4}
SHANGHAI = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc  # noqa: UP017 (Python 3.10 server)
SAFE_ID = re.compile(r"[a-zA-Z0-9_-]+\Z")
SCHEMA_VERSION = 1


@lru_cache(maxsize=1024)
def _asset_digest(path: str, size: int, modified_ns: int, inode: int) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_import_assets(root, document, assets):
    if not isinstance(assets, list):
        return False
    referenced = set(re.findall(r"/practice/sprint/assets/([^\"\\\s]+)", json.dumps(document)))
    filenames = set()
    for asset in assets:
        if not isinstance(asset, dict):
            return False
        filename, digest = asset.get("filename"), asset.get("sha256")
        if not isinstance(filename, str) or not re.fullmatch(
            r"[a-f0-9]{64}\.(mp3|png|jpg|jpeg|webp|gif)", filename
        ):
            return False
        if digest != filename.split(".")[0] or filename in filenames:
            return False
        if type(asset.get("byte_count")) is not int or asset["byte_count"] <= 0:
            return False
        filenames.add(filename)
        path = state_directory(root) / "assets" / filename
        if path.is_symlink() or not path.is_file():
            return False
        stat = path.stat()
        if (
            stat.st_size != asset["byte_count"]
            or _asset_digest(str(path), stat.st_size, stat.st_mtime_ns, stat.st_ino) != digest
        ):
            return False
    return referenced <= filenames


def content_digest(payload: dict) -> str:
    """Fingerprint a complete public exam response's data, excluding envelope."""
    data = payload.get("data")
    if not isinstance(data, dict) or not data.get("parts"):
        raise ValueError("Source exam has no parts")
    encoded = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Missing snapshot timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Snapshot timestamp must include timezone")
    return dt


def validate_snapshot(snapshot: dict) -> None:
    """Reject partial feeds rather than replacing a usable week with missing data."""
    if snapshot.get("schema_version") != SCHEMA_VERSION or snapshot.get("source") != "ninefen":
        raise ValueError("Unsupported sprint snapshot")
    _timestamp(snapshot.get("fetched_at"))
    subjects = snapshot.get("subjects")
    if not isinstance(subjects, dict) or set(subjects) != set(SUBJECT_PARTS):
        raise ValueError("Both subjects are required")
    for subject, count in SUBJECT_PARTS.items():
        groups = subjects[subject]
        if not isinstance(groups, list) or [g.get("part") for g in groups] != list(
            range(1, count + 1)
        ):
            raise ValueError("Incomplete part list")
        seen = set()
        for group in groups:
            rows = group.get("items")
            if not isinstance(rows, list) or len(rows) != 20:
                raise ValueError("Expected the public top 20 per part")
            if [row.get("rank") for row in rows] != list(range(1, 21)):
                raise ValueError("Invalid public ranks")
            for row in rows:
                if "mapping" in row and not isinstance(row["mapping"], dict):
                    raise ValueError("Invalid snapshot mapping")
                source_id = row.get("source_id")
                if not isinstance(source_id, str) or not re.fullmatch(r"[0-9]{1,30}", source_id):
                    raise ValueError("Invalid source ID")
                if (
                    source_id in seen
                    or not isinstance(row.get("title"), str)
                    or not row["title"].strip()
                ):
                    raise ValueError("Duplicate or untitled source item")
                seen.add(source_id)


def state_directory(root: str | Path) -> Path:
    configured = os.environ.get("EXAM_SPRINT_STATE_DIR")
    return Path(configured) if configured else Path(root) / "instance" / "exam_sprint"


def load_mappings(root: str | Path) -> dict:
    path = Path(root) / "data" / "exam_sprint" / "mappings.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("mappings"), list):
        raise ValueError("Invalid sprint mappings")
    rows = {}
    for row in payload["mappings"]:
        key = (row["subject"], row["source_id"])
        if key in rows or key[0] not in SUBJECT_PARTS:
            raise ValueError("Duplicate or invalid mapping")
        if not all(
            re.fullmatch(r"[0-9a-f]{64}", row.get(k, ""))
            for k in ("source_content_sha256", "target_sha256")
        ):
            raise ValueError("Unverified mapping")
        rows[key] = row
    return rows


def _local_target(root: Path, mapping: dict) -> tuple[dict, str] | None:
    if mapping.get("target_kind") == "ninefen":
        from services.exam_sprint_store import load_mapping_target

        loaded = load_mapping_target(root, mapping)
        if loaded is None:
            return None
        try:
            if not _valid_import_assets(root, loaded[0], mapping.get("assets")):
                return None
        except (OSError, ValueError, TypeError, AttributeError):
            return None
        subject, target = mapping["subject"], mapping["target_id"]
        url = (
            f"/practice/sprint/reading/{target}?passage={mapping['passage']}"
            if subject == "reading"
            else f"/listening/jijing/{target}"
        )
        return loaded[0], url
    subject = mapping.get("subject")
    target_id = mapping.get("target_id", "")
    if (
        subject not in SUBJECT_PARTS
        or not isinstance(target_id, str)
        or not SAFE_ID.fullmatch(target_id)
    ):
        return None
    folder = root / "static" / f"{subject}_jijing"
    if target_id in load_offline_test_ids(folder):
        return None
    path = (
        folder / "parts" / f"{target_id}.json"
        if subject == "listening"
        else folder / f"{target_id}.json"
    )
    try:
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != mapping.get("target_sha256"):
            return None
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("id") != target_id:
            return None
        if subject == "reading":
            if data.get("source") != "idictation_reading_jijing":
                return None
            number = mapping.get("passage")
            if type(number) is not int or not any(
                p.get("passage") == number for p in data.get("passages", [])
            ):
                return None
            return data, f"/reading/jijing/{target_id}?passage={number}"
        audio = (data.get("audio") or {}).get("local_path")
        if (
            not isinstance(audio, str)
            or not audio
            or Path(audio).is_absolute()
            or ".." in Path(audio).parts
        ):
            return None
        if not (folder / audio).is_file():
            return None
        return data, f"/listening/jijing/{target_id}"
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def prepare_snapshot(
    root: str | Path, feed: dict, exam_fetcher=None, *, imported_mappings=None
) -> dict:
    """Attach only independently reviewed, content-verified practice mappings."""
    snapshot = json.loads(json.dumps(feed))
    snapshot["schema_version"] = SCHEMA_VERSION
    validate_snapshot(snapshot)
    mappings = load_mappings(root)
    mappings.update(imported_mappings or {})
    for subject, groups in snapshot["subjects"].items():
        for group in groups:
            for row in group["items"]:
                row.pop("practice_url", None)
                row.pop("mapping", None)
                row["unavailable_reason"] = "题目与答案待核对"
                if row.get("source_available") is not True or row.get("entry_mode") != "exam":
                    row["unavailable_reason"] = "来源暂未开放完整练习"
                    continue
                mapping = mappings.get((subject, row["source_id"]))
                if not mapping or not exam_fetcher:
                    continue
                if mapping.get("source_title") != row["title"]:
                    row["unavailable_reason"] = "来源题目有更新，待核对"
                    continue
                exam = exam_fetcher(row["source_id"])
                if content_digest(exam) != mapping["source_content_sha256"]:
                    row["unavailable_reason"] = "来源题目有更新，待核对"
                    continue
                row["mapping"] = mapping
                if _local_target(Path(root), mapping):
                    row["unavailable_reason"] = ""
                else:
                    row["unavailable_reason"] = "本地题目或音频待补齐"
    return snapshot


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def publish_snapshot(directory: Path, snapshot: dict) -> Path:
    """Keep an immutable capture before swapping the single live snapshot."""
    validate_snapshot(snapshot)
    capture = _timestamp(snapshot["fetched_at"]).astimezone(UTC)
    content = json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode("utf-8")
    suffix = hashlib.sha256(content).hexdigest()[:12]
    archive = directory / "history" / f"{capture:%Y%m%dT%H%M%S}-{suffix}.json"
    _atomic_json(archive, snapshot)
    destination = directory / "current.json"
    _atomic_json(destination, snapshot)
    return destination


def _load_snapshot(root: Path) -> dict | None:
    runtime = state_directory(root) / "current.json"
    seed = root / "data" / "exam_sprint" / "latest.json"
    for path in (runtime, seed):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            validate_snapshot(payload)
            return payload
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            continue
    return None


def _next_update(now: datetime) -> datetime:
    local = now.astimezone(SHANGHAI)
    candidate = local.replace(hour=6, minute=0, second=0, microsecond=0)
    candidate += timedelta(days=(7 - local.weekday()) % 7)
    if candidate <= local:
        candidate += timedelta(days=7)
    return candidate


def load_sprint_view(root: str | Path, subject: str, *, now: datetime | None = None) -> dict:
    if subject not in SUBJECT_PARTS:
        raise ValueError("Unknown sprint subject")
    now = now or datetime.now(UTC)
    snapshot = _load_snapshot(Path(root))
    view = {
        "available": snapshot is not None,
        "stale": False,
        "updated_at_label": "",
        "source_updated_at_label": "",
        "next_update_label": _next_update(now).strftime("%m月%d日 06:00（北京时间）"),
        "groups": [],
        "total": 0,
        "ready_count": 0,
    }
    if snapshot is None:
        return view
    fetched = _timestamp(snapshot["fetched_at"])
    view["updated_at_label"] = fetched.astimezone(SHANGHAI).strftime("%Y-%m-%d %H:%M")
    last_due = _next_update(now) - timedelta(days=7)
    view["stale"] = (
        (fetched < last_due and now > last_due + timedelta(hours=1))
        or now - fetched > timedelta(days=8)
        or fetched > now + timedelta(minutes=5)
    )
    if snapshot.get("source_updated_at"):
        view["source_updated_at_label"] = snapshot["source_updated_at"]
    view["groups"] = snapshot["subjects"][subject]
    try:
        current_mappings = load_mappings(root)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        current_mappings = {}
    for group in view["groups"]:
        for row in group["items"]:
            row["practice_url"] = None
            mapping = row.get("mapping") or {}
            verified = (
                row.get("source_available") is True
                and row.get("entry_mode") == "exam"
                and mapping.get("subject") == subject
                and mapping.get("source_id") == row["source_id"]
                and mapping.get("source_title") == row["title"]
                and (
                    mapping.get("target_kind") == "ninefen"
                    or mapping == current_mappings.get((subject, row["source_id"]))
                )
            )
            target = _local_target(Path(root), mapping) if verified else None
            if target:
                row["practice_url"] = target[1]
                row["unavailable_reason"] = ""
                view["ready_count"] += 1
            elif mapping:
                row["unavailable_reason"] = "本地题目或音频待核对"
            view["total"] += 1
    return view
