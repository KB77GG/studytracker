"""Disposable SQLite and HTTP-stub tests of the read-only release probe."""

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("verify_production.py")
spec = importlib.util.spec_from_file_location("integrity_production_probe", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
SHA = "a" * 40
TOKEN = "synthetic-private-capability"
PRIVATE_TEXT = "Synthetic private name and pincode"


class Response:
    def __init__(self, body, status=200):
        self.body, self.code = body, status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, maximum):
        return self.body[:maximum]


class ReadOnlyProbeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="integrity-readonly-probe-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.database = self.root / "app.db"
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("CREATE TABLE mock_exam (id INTEGER PRIMARY KEY)")
            fields = ",".join(name + " TEXT" for name in probe.SESSION_FIELDS)
            connection.execute(
                "CREATE TABLE mock_exam_session "
                "(id INTEGER PRIMARY KEY,exam_id INTEGER,access_token TEXT," + fields + ")"
            )
            connection.execute("INSERT INTO mock_exam VALUES (1)")
            connection.execute(
                "INSERT INTO mock_exam_session "
                "(id,exam_id,access_token,status,current_section,started_at) "
                "VALUES (1,1,?,'in_progress','intro','2000-01-01')",
                (TOKEN,),
            )
        self.requests = []
        self.error = None
        self.redirect = False
        self.addCleanup(patch.stopall)
        patch.object(probe, "command", self.command).start()
        patch.object(probe, "service_info", return_value={"ok": True}).start()
        patch.object(
            probe, "deploy_script_info", return_value={"sha256": "b" * 64, "contains_literals": {}}
        ).start()
        patch.object(probe, "build_opener", return_value=self).start()

    def command(self, _root, *args):
        if args[:2] == ("git", "rev-parse"):
            return SHA
        if args[:2] in (("git", "status"), ("git", "ls-files")):
            return ""
        raise AssertionError("Unexpected command")

    def open(self, request, timeout):
        self.requests.append((request.get_method(), request.full_url))
        self.assertEqual(timeout, 15)
        self.assertNotIn("/admin/", request.full_url)
        if self.error:
            raise self.error
        if "/session/" in request.full_url:
            if self.redirect:
                return Response(b"redirect capability must not be persisted", 302)
            return Response(("cardPretest cardListening cardReading " + PRIVATE_TEXT).encode())
        return Response(("examName examPin btnLogin " + PRIVATE_TEXT).encode())

    def inspect(self, **kwargs):
        return probe.inspect(self.root, expected_head=kwargs.pop("expected_head", SHA), **kwargs)

    def add_policy(self, mode):
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("CREATE TABLE exam_integrity_policy (mode TEXT)")
            connection.execute("INSERT INTO exam_integrity_policy VALUES (?)", (mode,))

    def test_absent_tables_remain_absent_and_only_existing_pages_are_requested(self):
        result = self.inspect()
        self.assertTrue(result["ok"], result)
        self.assertEqual([method for method, _ in self.requests], ["GET", "GET"])
        db = result["database_and_pages"]
        self.assertTrue(db["query_only"])
        self.assertTrue(db["selected_session_state_and_timestamps_unchanged"])
        self.assertTrue(db["policy_aggregates_and_table_presence_unchanged"])
        self.assertFalse(any(db["policy"]["tables_present"].values()))
        with closing(sqlite3.connect(self.database)) as connection, connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM mock_exam_session").fetchone()[0], 1
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'exam_integrity_%'"
                ).fetchone()[0],
                0,
            )
        serialized = json.dumps(result)
        self.assertNotIn(TOKEN, serialized)
        self.assertNotIn(PRIVATE_TEXT, serialized)
        self.assertNotIn("/session/", serialized)

    def test_database_handle_is_readonly_even_if_query_only_is_temporarily_cleared(self):
        original = probe.integrity_policy_summary
        checks = []

        def attempt_write(connection):
            self.assertEqual(connection.execute("PRAGMA query_only").fetchone()[0], 1)
            connection.execute("PRAGMA query_only=OFF")
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("UPDATE mock_exam_session SET status='submitted'")
            connection.execute("PRAGMA query_only=ON")
            checks.append(True)
            return original(connection)

        with patch.object(probe, "integrity_policy_summary", attempt_write):
            self.assertTrue(self.inspect()["ok"])
        self.assertEqual(len(checks), 2)

    def test_enabled_policy_fails_acceptance_without_changing_it(self):
        self.add_policy("enforce")
        result = self.inspect()
        self.assertFalse(result["ok"])
        policy = result["database_and_pages"]["policy"]
        self.assertEqual(policy["enforce_rows"], 1)
        self.assertFalse(policy["all_exams_disabled"])
        with closing(sqlite3.connect(self.database)) as connection, connection:
            self.assertEqual(
                connection.execute("SELECT mode FROM exam_integrity_policy").fetchone()[0],
                "enforce",
            )

    def test_off_policy_passes_and_unknown_mode_is_not_falsely_certified(self):
        self.add_policy("off")
        self.assertTrue(self.inspect()["ok"])
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("UPDATE exam_integrity_policy SET mode='unexpected'")
        result = self.inspect()
        self.assertFalse(result["ok"])
        self.assertEqual(result["database_and_pages"]["policy"]["unexpected_mode_rows"], 1)
        self.assertNotIn('unexpected"', json.dumps(result))

    def test_no_existing_unsubmitted_session_is_explicitly_unverified(self):
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("UPDATE mock_exam_session SET status='submitted'")
        result = self.inspect()
        self.assertFalse(result["ok"])
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(
            result["database_and_pages"]["existing_chapter_page"],
            {"unverified_reason": "no_existing_unsubmitted_session"},
        )

    def test_http_exception_and_redirect_never_expose_capability_or_become_success(self):
        self.error = ValueError("GET /session/" + TOKEN + " " + PRIVATE_TEXT)
        result = self.inspect()
        self.assertFalse(result["ok"])
        self.assertNotIn(TOKEN, json.dumps(result))
        self.assertNotIn(PRIVATE_TEXT, json.dumps(result))
        self.assertEqual(
            result["database_and_pages"]["existing_chapter_page"], {"error": "ValueError"}
        )
        self.error = None
        self.redirect = True
        result = self.inspect()
        self.assertFalse(result["ok"])
        self.assertEqual(result["database_and_pages"]["existing_chapter_page"]["status"], 302)

    def test_post_requires_exact_head_while_pre_allows_unknown_expected_head(self):
        self.assertFalse(self.inspect(expected_head="c" * 40)["ok"])
        self.assertFalse(self.inspect(expected_head=None, phase="post")["ok"])
        self.assertTrue(self.inspect(expected_head=None, phase="pre")["ok"])

    def test_manifest_cannot_read_outside_checkout_and_errors_do_not_echo_input(self):
        result = self.inspect(manifest={"../" + TOKEN: "a" * 64})
        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"]["manifest"], "ValueError")
        self.assertNotIn(TOKEN, json.dumps(result))


if __name__ == "__main__":
    unittest.main()
