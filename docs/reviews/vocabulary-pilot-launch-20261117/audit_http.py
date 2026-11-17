#!/usr/bin/env python3
"""Read-only UTC daily vocabulary HTTP aggregates; never emit log records.

Supports Nginx common/combined logs, explicit request_time=... tail tokens,
and JSON logs with time_local/time_iso8601, request, status, request_time.
Unlabelled custom columns are deliberately not guessed to be timings.
"""

import argparse
import gzip
import json
import math
import os
import re
import stat
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc  # noqa: UP017 - production supports Python 3.10
MAX_LINE_BYTES = 1024 * 1024
MAX_TIMINGS = 1_000_000
ENDPOINTS = {
    "queue": re.compile(r"/api/miniprogram/student/tasks/[0-9]+/vocabulary-queue"),
    "preflight": re.compile(r"/api/miniprogram/student/tasks/[0-9]+/vocabulary-review/preflight"),
    "summary": re.compile(r"/api/miniprogram/student/vocabulary-review/summary"),
    "today": re.compile(r"/api/miniprogram/student/vocabulary-review/today"),
}
COMMON = re.compile(
    r"^\S+\s+\S+\s+\S+\s+\[(?P<at>[^\]]+)\]\s+"
    r'"(?P<request>(?:\\.|[^"\\])*)"\s+(?P<status>[1-5][0-9]{2})\s+'
    r"(?:[0-9]+|-)(?P<tail>\s.*)?$"
)
TAIL_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|\S+')
REQUEST = re.compile(r"GET (?P<target>\S+) HTTP/[0-9.]+")
MONTHS = {
    month: i for i, month in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)
}
LOCAL_TIME = re.compile(
    r"([0-9]{2})/([A-Za-z]{3})/([0-9]{4}):([0-9]{2}):([0-9]{2}):([0-9]{2}) ([+-])([0-9]{2})([0-9]{2})"
)


def utc_bound(value):
    """Require an explicit UTC offset; normalize Z and +00:00 only."""
    parsed = datetime.fromisoformat(
        value.removesuffix("Z") + ("+00:00" if value.endswith("Z") else "")
    )
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("utc_bound_required")
    return parsed.astimezone(UTC)


def log_time(value):
    match = LOCAL_TIME.fullmatch(str(value))
    if match:
        day, month, year, hour, minute, second, sign, zone_hour, zone_minute = match.groups()
        if int(zone_hour) > 23 or int(zone_minute) > 59:
            raise ValueError("invalid_log_timezone")
        offset = timedelta(hours=int(zone_hour), minutes=int(zone_minute))
        if sign == "-":
            offset = -offset
        return datetime(
            int(year),
            MONTHS[month],
            int(day),
            int(hour),
            int(minute),
            int(second),
            tzinfo=timezone(offset),
        ).astimezone(UTC)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("log_timezone_required")
    return parsed.astimezone(UTC)


def duration(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def parse_line(line):
    """Return only endpoint category/time/status/duration, never identifiers."""
    try:
        if line.lstrip().startswith("{"):
            row = json.loads(line)
            if not isinstance(row, dict):
                return None
            request = row.get("request")
            if request is None:
                request = (
                    f"{row.get('request_method')} {row.get('request_uri', row.get('uri'))} HTTP/1.1"
                )
            at = row.get("time_iso8601", row.get("time_local"))
            status = str(row.get("status"))
            timing = duration(row.get("request_time"))
        else:
            row = COMMON.fullmatch(line.rstrip("\r\n"))
            if not row:
                return None
            request, at, status = row["request"], row["at"], row["status"]
            timing = None
            # User-agent/referer quoted fields cannot inject a timing label.
            for token in TAIL_TOKEN.findall(row["tail"] or ""):
                if token.startswith("request_time="):
                    timing = duration(token.partition("=")[2])
                    break
        match = REQUEST.fullmatch(str(request))
        if not match or not re.fullmatch(r"[1-5][0-9]{2}", status):
            return None
        path = match["target"].partition("?")[0]
        endpoint = next(
            (name for name, pattern in ENDPOINTS.items() if pattern.fullmatch(path)), None
        )
        if endpoint is None:
            return None
        return endpoint, log_time(at), int(status), timing
    except (ValueError, TypeError, KeyError, OverflowError):
        return None


def log_files(directory):
    """One glob; same-name .gz rotations and symlink/hardlink aliases count once."""
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError("log_directory_missing")
    seen_inode, seen_rotation, selected = set(), set(), []
    duplicates = 0
    # Prefer the uncompressed form if a rotation is present in both forms.
    candidates = sorted(directory.glob("access*.log*"), key=lambda p: (p.suffix == ".gz", p.name))
    for path in candidates:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            continue
        inode = (info.st_dev, info.st_ino)
        rotation = str(path.resolve()).removesuffix(".gz")
        if inode in seen_inode or rotation in seen_rotation:
            duplicates += 1
            continue
        seen_inode.add(inode)
        seen_rotation.add(rotation)
        selected.append((path, inode))
    return selected, duplicates


def percentile(values, fraction):
    """Exact nearest-rank quantile over all available request_time values."""
    return values[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def audit(directory, since, until):
    if since.tzinfo is None or until.tzinfo is None or since >= until:
        raise ValueError("invalid_window")
    since, until = since.astimezone(UTC), until.astimezone(UTC)
    if until - since > timedelta(days=366):
        raise ValueError("window_too_large")
    paths, duplicate_files = log_files(directory)
    if not paths:
        raise ValueError("no_retained_logs")
    groups = defaultdict(lambda: {"requests": 0, "status_499": 0, "status_5xx": 0, "timings": []})
    scanned, timed = 0, 0
    for path, expected_inode in paths:
        # rb is important: never create a missing path or modify rotation files.
        with path.open("rb") as raw:
            opened = os.fstat(raw.fileno())
            if (opened.st_dev, opened.st_ino) != expected_inode:
                raise ValueError("rotation_changed_retry")
            gzip_magic = raw.read(2) == b"\x1f\x8b"
            raw.seek(0)
            stream = (
                gzip.GzipFile(fileobj=raw, mode="rb") if gzip_magic or path.suffix == ".gz" else raw
            )
            try:
                while True:
                    line = stream.readline(MAX_LINE_BYTES + 1)
                    if not line:
                        break
                    if len(line) > MAX_LINE_BYTES:
                        raise ValueError("log_line_too_large")
                    scanned += 1
                    parsed = parse_line(line.decode("utf-8", errors="replace"))
                    if parsed is None:
                        continue
                    endpoint, at, status, timing = parsed
                    if not since <= at < until:
                        continue
                    group = groups[(at.date(), endpoint)]
                    group["requests"] += 1
                    group["status_499"] += int(status == 499)
                    group["status_5xx"] += int(500 <= status <= 599)
                    if timing is not None:
                        timed += 1
                        if timed > MAX_TIMINGS:
                            raise ValueError("timing_capacity_exceeded")
                        group["timings"].append(timing)
            finally:
                if stream is not raw:
                    stream.close()
    daily = []
    day = since.date()
    while datetime.combine(day, datetime.min.time(), UTC) < until:
        for endpoint in ENDPOINTS:
            group = groups[(day, endpoint)]
            values = sorted(group.pop("timings"))
            daily.append(
                {
                    "day_utc": day.isoformat(),
                    "endpoint": endpoint,
                    **group,
                    "request_time_seconds": {
                        "count": len(values),
                        "missing_count": group["requests"] - len(values),
                        "p50": percentile(values, 0.5),
                        "p95": percentile(values, 0.95),
                        "p99": percentile(values, 0.99),
                        "max": max(values) if values else None,
                    },
                }
            )
        day += timedelta(days=1)
    return {
        "ok": True,
        "read_only": True,
        "identities_exported": False,
        "since_utc_inclusive": since.isoformat(),
        "until_utc_exclusive": until.isoformat(),
        "scope": "all_requests_to_four_routes_not_student_cohort",
        "retained_logs_only": True,
        "files_read": len(paths),
        "duplicate_aliases_ignored": duplicate_files,
        "lines_scanned": scanned,
        "timing_quantile_method": "exact_nearest_rank",
        "timing_source": "explicit_request_time_only;unlabelled_custom_columns_not_inferred",
        "daily": daily,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", required=True, help="inclusive ISO timestamp with Z/+00:00")
    parser.add_argument("--until", required=True, help="exclusive ISO timestamp with Z/+00:00")
    parser.add_argument("--log-dir", type=Path, default=Path("/var/log/nginx"))
    args = parser.parse_args(argv)
    try:
        result = audit(args.log_dir, utc_bound(args.since), utc_bound(args.until))
    except Exception as error:
        # Never echo raw errors: filenames, log lines and parse inputs can identify students.
        result = {
            "ok": False,
            "read_only": True,
            "identities_exported": False,
            "error_type": type(error).__name__,
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
