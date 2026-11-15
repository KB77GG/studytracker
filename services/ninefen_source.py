"""Read only the anonymous, public part of 九分学长's seven-day ranking.

No login state is accepted or inspected. The extra ranking rows endpoint is
deliberately not implemented: each of the seven sections exposes twenty rows.
"""

from __future__ import annotations

import json
import math
import re
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

API_BASE = "https://www.9fnnn.com/api"
HOTLIST_PATH = "/practice/v1/high-frequency/albums"
PUBLIC_ROW_LIMIT = 20
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_ATTEMPTS = 3
SUBJECT_PARTS = {"reading": 3, "listening": 4}


class NinefenSourceError(ValueError):
    """The source could not produce a complete, verified public snapshot."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise NinefenSourceError("Source redirected; review the source endpoint before retrying")


def verified_https_handler():
    """Use system trust plus the CA bundle shipped with the existing HTTP stack.

    Python.org macOS interpreters can have no configured OpenSSL CA file. This
    adds trusted roots while retaining hostname and certificate verification.
    """
    context = ssl.create_default_context()
    try:
        import certifi
    except ImportError:
        pass
    else:
        context.load_verify_locations(cafile=certifi.where())
    return urllib.request.HTTPSHandler(context=context)


def _object(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise NinefenSourceError(f"Invalid {name}")
    return value


def _text(value: Any, name: str, *, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()) or len(value) > 300:
        raise NinefenSourceError(f"Invalid {name}")
    return value.strip()


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise NinefenSourceError(f"Invalid {name}")
    return value


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,24}", value):
        raise NinefenSourceError("Invalid source ID: expected a decimal string")
    return value


def _public_item(row: Any, channel: str, seen_ids: set[str]) -> dict:
    row = _object(row, "ranking row")
    if row.get("channel") != channel:
        raise NinefenSourceError("Ranking row channel mismatch")
    source_id = _identifier(row.get("id"))
    if source_id in seen_ids:
        raise NinefenSourceError("Duplicate ranking source ID")
    seen_ids.add(source_id)
    rank = _integer(row.get("rank"), "rank", 1)
    reports = _integer(row.get("sevenDayReportTotal"), "seven-day report count")
    title = _text(row.get("title"), "title")
    entry_mode = _text(row.get("entryMode"), "entry mode")
    if (
        type(row.get("available")) is not bool
        or type(row.get("lockedForOrdinaryUsers")) is not bool
    ):
        raise NinefenSourceError("Missing public row availability")
    return {
        "source_id": source_id,
        "source_part_id": _identifier(row.get("partId")),
        "source_part_code": _text(row.get("partCode"), "part code"),
        "source_version_title": title,
        "entry_mode": entry_mode,
        "source_available": row["available"] and not row["lockedForOrdinaryUsers"],
        "title": title,
        "title_zh": _text(row.get("titleZh"), "Chinese title", required=False),
        "rank": rank,
        "heat_label": f"近7天上报 {reports} 次",
    }


def _public_group(slot: Any, channel: str, seen_ids: set[str]) -> dict:
    slot = _object(slot, "ranking section")
    label = _text(slot.get("label"), "section label")
    match = re.fullmatch(r"Part ([1-4])", label)
    if not match or slot.get("key") != f"part:{label}" or slot.get("channel") != channel:
        raise NinefenSourceError("Invalid ranking section identity")
    part = int(match.group(1))
    rows = slot.get("list")
    if (
        slot.get("publicRowLimit") != PUBLIC_ROW_LIMIT
        or type(slot.get("count")) is not int
        or slot["count"] != PUBLIC_ROW_LIMIT
        or not isinstance(rows, list)
        or len(rows) != PUBLIC_ROW_LIMIT
    ):
        raise NinefenSourceError("Public ranking must contain exactly twenty rows per section")
    items = [_public_item(row, channel, seen_ids) for row in rows]
    if sorted(row["rank"] for row in items) != list(range(1, PUBLIC_ROW_LIMIT + 1)):
        raise NinefenSourceError("Public ranking ranks must be exactly 1 through 20")
    return {"part": part, "items": sorted(items, key=lambda row: row["rank"])}


def parse_public_hotlist(payload: Any, fetched_at: datetime | None = None) -> dict:
    """Validate the observed API schema; a partial response must never replace a snapshot."""
    payload = _object(payload, "response")
    if payload.get("code") not in (200, "200"):
        raise NinefenSourceError("Source did not return a successful public response")
    albums = _object(payload.get("data"), "response data").get("list")
    if not isinstance(albums, list):
        raise NinefenSourceError("Invalid album list")
    subjects = {}
    seen_ids: set[str] = set()
    for album in albums:
        album = _object(album, "album")
        if album.get("groupCode") != "weekly_dynamic":
            continue
        channel = album.get("channel")
        if channel not in SUBJECT_PARTS or channel in subjects:
            raise NinefenSourceError("Unexpected or duplicate weekly ranking subject")
        if album.get("publicRowLimit") != PUBLIC_ROW_LIMIT:
            raise NinefenSourceError("Public ranking access scope changed")
        slots = album.get("slots")
        if not isinstance(slots, list) or len(slots) != SUBJECT_PARTS[channel]:
            raise NinefenSourceError("Incomplete public ranking sections")
        groups = [_public_group(slot, channel, seen_ids) for slot in slots]
        if sorted(group["part"] for group in groups) != list(range(1, len(slots) + 1)):
            raise NinefenSourceError("Missing or duplicate public ranking section")
        subjects[channel] = sorted(groups, key=lambda group: group["part"])
    if set(subjects) != set(SUBJECT_PARTS):
        raise NinefenSourceError("Both reading and listening rankings are required")
    fetched_at = fetched_at or datetime.now(timezone.utc)  # noqa: UP017 (Python 3.10 server)
    if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        raise NinefenSourceError("Fetch time must include a timezone")
    return {
        "source": "ninefen",
        "fetched_at": fetched_at.isoformat(),
        # The observed API has no source update time; don't invent one from fetch time.
        "source_updated_at": None,
        "subjects": subjects,
    }


def _fetch_json(path: str, timeout: float) -> dict:
    if isinstance(timeout, bool) or not math.isfinite(timeout) or not 0 < timeout <= 60:
        raise NinefenSourceError("Timeout must be between 0 and 60 seconds")
    request = urllib.request.Request(
        API_BASE + path,
        headers={"Accept": "application/json", "User-Agent": "StudyTracker-PublicHotlist/1.0"},
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirect(), verified_https_handler())
    for attempt in range(MAX_ATTEMPTS):
        try:
            with opener.open(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise NinefenSourceError("Source response exceeded the size limit")
            try:
                return _object(json.loads(raw), "JSON response")
            except (ValueError, UnicodeError) as exc:
                raise NinefenSourceError("Source returned invalid JSON") from exc
        except urllib.error.HTTPError as exc:
            exc.close()
            if exc.code not in (429, 500, 502, 503, 504) or attempt == MAX_ATTEMPTS - 1:
                raise NinefenSourceError(f"Source HTTP request failed ({exc.code})") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == MAX_ATTEMPTS - 1:
                raise NinefenSourceError("Source request timed out or was unreachable") from exc
        time.sleep(attempt + 1)
    raise NinefenSourceError("Source request failed")  # Defensive; all loop paths return or raise.


def fetch_public_hotlist(timeout: float = 20) -> dict:
    """Fetch one public album response; never request pagination or credentials."""
    return parse_public_hotlist(_fetch_json(HOTLIST_PATH, timeout))


def fetch_public_exam(unit_id: str, timeout: float = 20) -> dict:
    """Read one public exam for inspection; anonymous responses may omit all answers."""
    unit_id = _identifier(unit_id)
    response = _fetch_json(f"/practice/v1/units/{unit_id}/exam", timeout)
    data = _object(response.get("data"), "exam data")
    if response.get("code") not in (200, "200") or data.get("id") != unit_id:
        raise NinefenSourceError("Source returned an unexpected exam")
    charge = data.get("isCharge")
    if not ((type(charge) is int and charge == 0) or (type(charge) is str and charge == "0")):
        raise NinefenSourceError("Exam is outside the public access scope")
    return response
