"""Synthetic privacy, rotation, timing and boundary checks; no server access."""

import ast
import contextlib
import gzip
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).with_name("audit_http.py")
SPEC = importlib.util.spec_from_file_location("pilot_http_audit", PATH)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

ROUTES = {
    "queue": "/api/miniprogram/student/tasks/987654321/vocabulary-queue",
    "preflight": "/api/miniprogram/student/tasks/987654321/vocabulary-review/preflight",
    "summary": "/api/miniprogram/student/vocabulary-review/summary",
    "today": "/api/miniprogram/student/vocabulary-review/today",
}
SECRET = "SYNTHETIC_PRIVATE_TOKEN_NEVER_OUTPUT"


def line(endpoint="queue", status=200, stamp="17/Nov/2026:08:00:00 +0800", tail="", method="GET"):
    return (
        f"198.51.100.73 - synthetic-user [{stamp}] "
        f'"{method} {ROUTES[endpoint]}?token={SECRET} HTTP/1.1" {status} 7654321 '
        f'"https://private.example/{SECRET}" "agent request_time=999 {SECRET}" {tail}\n'
    )


class AuditHttpTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.since = audit.utc_bound("2026-11-17T00:00:00Z")
        self.until = audit.utc_bound("2026-11-19T00:00:00+00:00")

    def tearDown(self):
        self.temp.cleanup()

    def run_audit(self):
        return audit.audit(self.directory, self.since, self.until)

    def row(self, result, endpoint="queue", day="2026-11-17"):
        return next(
            row for row in result["daily"] if row["endpoint"] == endpoint and row["day_utc"] == day
        )

    def assert_private(self, output):
        for private in (
            SECRET,
            "198.51.100.73",
            "synthetic-user",
            "987654321",
            "private.example",
            str(self.directory),
        ):
            self.assertNotIn(private, output)
        self.assertNotIn("/api/", output)

    def test_four_exact_get_routes_and_statuses_only(self):
        text = "".join(
            line(endpoint, status) for endpoint in ROUTES for status in (200, 401, 499, 500, 503)
        )
        text += line(method="POST")
        text += line().replace("/vocabulary-queue?", "/vocabulary-queue/extra?")
        text += line().replace("/api/miniprogram/student/", "/api/miniprogram/teacher/")
        text += "malformed " + SECRET + "\n"
        path = self.directory / "access.log"
        path.write_text(text)
        before = path.read_bytes()
        result = self.run_audit()
        self.assertEqual(len(result["daily"]), 8)
        for endpoint in ROUTES:
            row = self.row(result, endpoint)
            self.assertEqual((row["requests"], row["status_499"], row["status_5xx"]), (5, 1, 2))
            self.assertEqual(row["request_time_seconds"]["count"], 0)
            self.assertIsNone(row["request_time_seconds"]["p95"])
            self.assertEqual(row["request_time_seconds"]["missing_count"], 5)
        self.assertEqual(path.read_bytes(), before)
        self.assert_private(json.dumps(result))

    def test_utc_half_open_window_and_daily_timezone_conversion(self):
        stamps = [
            "17/Nov/2026:07:59:59 +0800",  # before since
            "17/Nov/2026:08:00:00 +0800",  # inclusive since
            "18/Nov/2026:07:59:59 +0800",  # still UTC day 17
            "18/Nov/2026:08:00:00 +0800",  # UTC day 18
            "18/Nov/2026:18:59:59 -0500",  # final second
            "19/Nov/2026:08:00:00 +0800",  # exclusive until
        ]
        (self.directory / "access.log").write_text("".join(line(stamp=stamp) for stamp in stamps))
        result = self.run_audit()
        self.assertEqual(self.row(result, day="2026-11-17")["requests"], 2)
        self.assertEqual(self.row(result, day="2026-11-18")["requests"], 2)

    def test_gzip_plain_rotation_and_inode_aliases_not_counted_twice(self):
        current = self.directory / "access.log"
        current.write_text(line())
        os.link(current, self.directory / "access-hardlink.log")
        (self.directory / "access-symlink.log").symlink_to(current)
        rotated = self.directory / "access.log.1"
        rotated.write_text(line("summary"))
        with gzip.open(self.directory / "access.log.1.gz", "wt") as stream:
            stream.write(rotated.read_text())
        with gzip.open(self.directory / "access.log.2.gz", "wt") as stream:
            stream.write(line("today"))
        # A suffix-free alias of gzip must still decompress correctly.
        (self.directory / "access-a-gzip.log").symlink_to(self.directory / "access.log.2.gz")
        result = self.run_audit()
        self.assertEqual(result["files_read"], 3)
        self.assertEqual(result["duplicate_aliases_ignored"], 4)
        self.assertEqual(sum(row["requests"] for row in result["daily"]), 3)

    def test_explicit_timing_exact_quantiles_and_no_quoted_or_bytes_inference(self):
        timings = [0.1, 0.2, 0.3, 0.4, 1.5]
        text = "".join(line(tail=f"request_time={value}") for value in timings)
        text += line(tail="0.987")  # no configured meaning for positional custom columns
        text += line(tail="request_time=NaN")
        text += line(tail="request_time=-0.1")
        text += line(tail="request_time=inf")
        (self.directory / "access.log").write_text(text)
        stats = self.row(self.run_audit())["request_time_seconds"]
        self.assertEqual(
            stats, {"count": 5, "missing_count": 4, "p50": 0.3, "p95": 1.5, "p99": 1.5, "max": 1.5}
        )

    def test_json_format_uses_only_explicit_structured_values(self):
        row = {
            "time_iso8601": "2026-11-17T08:00:00+08:00",
            "request": f"GET {ROUTES['preflight']}?token={SECRET} HTTP/2.0",
            "status": "499",
            "request_time": "10.001",
            "remote_addr": "198.51.100.73",
            "student_name": SECRET,
        }
        fallback = {
            "time_local": "17/Nov/2026:08:00:01 +0800",
            "request_method": "GET",
            "request_uri": ROUTES["today"],
            "status": 200,
            "request_time": 0.25,
        }
        (self.directory / "access-json.log").write_text(
            json.dumps(row) + "\n" + json.dumps(fallback) + "\n"
        )
        result = self.run_audit()
        self.assertEqual(self.row(result, "preflight")["status_499"], 1)
        self.assertEqual(self.row(result, "preflight")["request_time_seconds"]["max"], 10.001)
        self.assertEqual(self.row(result, "today")["request_time_seconds"]["max"], 0.25)
        self.assert_private(json.dumps(result))

    def test_bounds_must_be_explicit_utc_and_ordered(self):
        for value in ("2026-11-17", "2026-11-17T00:00:00", "2026-11-17T00:00:00+08:00"):
            with self.assertRaises(ValueError):
                audit.utc_bound(value)
        with self.assertRaises(ValueError):
            audit.audit(self.directory, self.until, self.since)

    def test_cli_failure_never_prints_paths_raw_lines_or_partial_result(self):
        path = self.directory / f"access-{SECRET}.log.gz"
        path.write_bytes(b"not gzip " + SECRET.encode())
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            code = audit.main(
                [
                    "--since",
                    self.since.isoformat(),
                    "--until",
                    self.until.isoformat(),
                    "--log-dir",
                    str(self.directory),
                ]
            )
        self.assertEqual(code, 1)
        result = json.loads(captured.getvalue())
        self.assertFalse(result["ok"])
        self.assertNotIn("daily", result)
        self.assert_private(captured.getvalue())

    def test_bounded_line_timing_and_rotation_race_fail_closed(self):
        path = self.directory / "access.log"
        path.write_text(line(tail="request_time=0.1") * 2)
        with patch.object(audit, "MAX_TIMINGS", 1), self.assertRaises(ValueError):
            self.run_audit()
        with patch.object(audit, "MAX_LINE_BYTES", 5), self.assertRaises(ValueError):
            self.run_audit()
        real = audit.log_files

        def stale(directory):
            files, duplicates = real(directory)
            return [(item, (inode[0], inode[1] + 1)) for item, inode in files], duplicates

        with patch.object(audit, "log_files", side_effect=stale), self.assertRaises(ValueError):
            self.run_audit()

    def test_imports_are_stdlib_only_and_all_log_open_modes_are_readonly(self):
        tree = ast.parse(PATH.read_text())
        imports = {
            node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        }
        imports |= {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertEqual(
            imports,
            {
                "argparse",
                "gzip",
                "json",
                "math",
                "os",
                "re",
                "stat",
                "collections",
                "datetime",
                "pathlib",
            },
        )
        (self.directory / "access.log").write_text(line())
        original = Path.open
        modes = []

        def check(path, mode="r", *args, **kwargs):
            modes.append(mode)
            self.assertNotIn("w", mode)
            self.assertNotIn("a", mode)
            self.assertNotIn("+", mode)
            return original(path, mode, *args, **kwargs)

        with patch.object(Path, "open", check):
            self.run_audit()
        self.assertEqual(modes, ["rb"])


if __name__ == "__main__":
    unittest.main()
