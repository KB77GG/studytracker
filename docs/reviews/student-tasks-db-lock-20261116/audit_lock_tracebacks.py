"""Read-only, identity-free summary of server tracebacks (NOT yet run on production).

Purpose: tell *which statement on which route* raised each "database is locked",
which the aggregated counts in log-summary.json cannot show.  It only reads text
(journalctl output or a file); it never opens the database, imports the app or
calls any API.

Kept per traceback: timestamp to the second, HTTP method, route with numeric ids
replaced and the query string dropped, project frames as file:function, the
exception class, the SQLite message and the SQL verb + table.
Never kept: bound parameters, query strings, tokens, names, ids, IPs.

Usage on the server (read-only):
    journalctl -u studytracker --since '2026-11-15 00:00:00' --no-pager -o cat \
        | python3 audit_lock_tracebacks.py > lock-tracebacks.json
(``-o cat`` keeps Flask's own "[date time] ERROR in module:" header, which is
where the timestamp comes from; a journald line prefix is also tolerated.)
Or: python3 audit_lock_tracebacks.py saved-log.txt
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter

RECORD = re.compile(r"\] (?:ERROR|CRITICAL|WARNING) in \w+: ")
START = re.compile(r"Exception on (\S+) \[(\w+)\]")
JOURNAL_PREFIX = re.compile(r"^\S+ \S+ \S+\[\d+\]: ")
STAMP = re.compile(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})")
FRAME = re.compile(r'File "([^"]+)", line \d+, in (\S+)')
FINAL = re.compile(r"((?:\w+\.)*\w*(?:Error|Exception))(?::\s*(.*))?$")
SQL = re.compile(r"\[SQL:\s*(\w+)(?:\s+(?:INTO|FROM)?\s*(\w+))?", re.IGNORECASE)
SQLITE_MESSAGES = (
    "database is locked",
    "database table is locked",
    "too many SQL variables",
    "disk I/O error",
    "attempt to write a readonly database",
    "database disk image is malformed",
)


def safe_route(raw: str) -> str:
    return re.sub(r"/\d+(?=/|$)", "/:id", raw.split("?", 1)[0])


def project_frame(path: str, function: str) -> str | None:
    if path.startswith("<") or "site-packages" in path or "/lib/python" in path:
        return None
    parts = path.replace("\\", "/").split("/")
    return f"{'/'.join(parts[-2:])}:{function}"


def summarise(lines) -> dict:
    events, current = [], None
    for raw_line in lines:
        line = JOURNAL_PREFIX.sub("", raw_line.rstrip("\n"))
        if RECORD.search(line):
            if current:
                events.append(current)
            stamp = STAMP.search(line)
            started = START.search(line)
            current = {
                "time": f"{stamp.group(1)} {stamp.group(2)}" if stamp else None,
                "unhandled": bool(started),  # False: caught and logged by the handler itself
                "method": started.group(2) if started else None,
                "route": safe_route(started.group(1)) if started else None,
                "project_frames": [],
                "exception": None,
                "sqlite_message": None,
                "sql": None,
            }
            continue
        if current is None:
            continue
        frame = FRAME.search(line)
        if frame:
            label = project_frame(frame.group(1), frame.group(2))
            if label and label not in current["project_frames"]:
                current["project_frames"].append(label)
            continue
        sql = SQL.search(line)
        if sql:
            verb = sql.group(1).upper()
            current["sql"] = verb if verb in {"COMMIT", "BEGIN", "ROLLBACK"} else f"{verb} {sql.group(2) or ''}".strip()
        for message in SQLITE_MESSAGES:
            if message in line:
                current["sqlite_message"] = message
        final = FINAL.search(line.strip())
        if final and not line.startswith((" ", "\t")):
            current["exception"] = final.group(1)
    if current:
        events.append(current)
    events = [event for event in events if event["exception"] or event["sqlite_message"]]
    return {
        "read_only_text_analysis": True,
        "tracebacks": events,
        "by_route_and_message": [
            {"route": route, "method": method, "sqlite_message": message, "sql": sql, "count": count}
            for (route, method, message, sql), count in sorted(
                Counter((e["route"], e["method"], e["sqlite_message"], e["sql"]) for e in events).items(),
                key=lambda item: str(item[0]),
            )
        ],
    }


if __name__ == "__main__":
    stream = open(sys.argv[1], encoding="utf-8", errors="replace") if len(sys.argv) > 1 else sys.stdin
    print(json.dumps(summarise(stream), ensure_ascii=False, indent=2))
