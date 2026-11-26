"""Refresh the explicitly approved local session from the known Ninefen profile.

Only exact file:// token/user LevelDB log records are considered. No credential
or profile values are printed. This never edits the application's own storage.
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from services.ninefen_session import _private_write

PROFILE = Path("/Users/zhouxin/Library/Application Support/xxgg-electron/Local Storage/leveldb")
TARGET = Path(
    "/Users/zhouxin/Library/Application Support/StudyTrackerExamSprint/instance/exam_sprint/private/session.json"
)


def varint(raw, pos):
    result = 0
    for shift in range(0, 70, 7):
        value = raw[pos]
        pos += 1
        result |= (value & 127) << shift
        if value < 128:
            return result, pos
    raise ValueError("Invalid encoded length")


def blobs(raw):
    pos = 0
    fragments = bytearray()
    while pos + 7 <= len(raw):
        if 32768 - pos % 32768 < 7:
            pos += 32768 - pos % 32768
            continue
        length = int.from_bytes(raw[pos + 4 : pos + 6], "little")
        kind = raw[pos + 6]
        pos += 7
        part = raw[pos : pos + length]
        pos += length
        if len(part) != length:
            raise ValueError("Incomplete log")
        if kind == 1:
            yield part
        elif kind == 2:
            fragments = bytearray(part)
        elif kind == 3:
            fragments.extend(part)
        elif kind == 4:
            fragments.extend(part)
            yield bytes(fragments)
            fragments.clear()
        elif kind != 0:
            raise ValueError("Unknown log kind")


def read_current():
    found = {}
    for path in PROFILE.glob("*.log"):
        for batch in blobs(path.read_bytes()):
            if len(batch) < 12:
                continue
            sequence, count = struct.unpack_from("<QI", batch)
            pos = 12
            for i in range(count):
                kind = batch[pos]
                pos += 1
                n, pos = varint(batch, pos)
                key = batch[pos : pos + n]
                pos += n
                if kind == 1:
                    n, pos = varint(batch, pos)
                    value = batch[pos : pos + n]
                    pos += n
                elif kind == 0:
                    value = None
                else:
                    raise ValueError("Unknown batch kind")
                if key in (b"_file://\x00\x01token", b"_file://\x00\x01user"):
                    if key not in found or sequence + i > found[key][0]:
                        found[key] = (sequence + i, value)

    def decode(name):
        value = found.get(b"_file://\x00\x01" + name.encode(), (0, None))[1]
        if not value:
            return None
        if value[0] == 1:
            return value[1:].decode("latin1")
        if value[0] == 0:
            return value[1:].decode("utf-16-le")
        raise ValueError("Unsupported storage encoding")

    token = decode("token")
    user = json.loads(decode("user") or "{}")
    if (
        not isinstance(token, str)
        or not 16 <= len(token) <= 8192
        or any(ord(c) < 33 or ord(c) > 126 for c in token)
    ):
        raise ValueError("No valid current source session")
    owner = user.get("userId") or user.get("id")
    if owner is None:
        import base64

        pieces = token.split(".")
        if len(pieces) == 3:
            claims = json.loads(base64.urlsafe_b64decode(pieces[1] + "=" * ((-len(pieces[1])) % 4)))
            owner = claims.get("userid")
    if not isinstance(owner, (str, int)) or isinstance(owner, bool) or not str(owner):
        raise ValueError("No current owner identity")
    return token, str(owner)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    token, owner = read_current()
    existing = json.loads(TARGET.read_text())
    print(
        json.dumps(
            {
                "current_app_token_found": True,
                "current_owner_found": True,
                "differs_from_saved": token != existing.get("token"),
                "save_requested": args.save,
            }
        )
    )
    if args.save or args.verify:
        from urllib.request import Request, build_opener

        from services.ninefen_session import _NoRedirect
        from services.ninefen_source import API_BASE, verified_https_handler

        unit = "2102715008296194050"
        req = Request(
            API_BASE + "/practice/v1/unit-status?unitIds=" + unit,
            headers={"token": token, "Accept": "application/json"},
            method="GET",
        )
        with build_opener(_NoRedirect(), verified_https_handler()).open(
            req, timeout=20
        ) as response:
            result = json.loads(response.read(2 * 1024 * 1024))
        if result.get("code") not in (200, "200"):
            raise ValueError("Fresh application session rejected")
        rows = result.get("data", {}).get("list", [])
        if len(rows) != 1 or rows[0].get("unitId") != unit:
            raise ValueError("Authenticated unit status mismatch")
        if args.save:
            _private_write(TARGET, {"token": token, "owner": owner})
        print(json.dumps({"session_saved": args.save, "authenticated_status_verified": True}))
