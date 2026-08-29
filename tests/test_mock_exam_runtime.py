import json
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from services import mock_exam_runtime as runtime


class MockExamRuntimeTest(unittest.TestCase):
    def session(self):
        return SimpleNamespace(
            current_section="intro",
            status="in_progress",
            finished_at=None,
            listening_started_at=None,
            listening_deadline_at=None,
            listening_submitted_at=None,
            listening_answers_json=None,
            listening_duration_seconds=0,
            reading_started_at=None,
            reading_deadline_at=None,
            reading_submitted_at=None,
            reading_answers_json=None,
            reading_duration_seconds=0,
        )

    def test_start_is_idempotent_and_keeps_server_deadline(self):
        session = self.session()
        now = datetime(2026, 8, 28, 10, 0, 0)
        started, deadline = runtime.start_section(session, "listening", 32, now)
        repeated = runtime.start_section(session, "listening", 32, now + timedelta(minutes=5))

        self.assertEqual((started, deadline), repeated)
        self.assertEqual(deadline, now + timedelta(minutes=32))
        self.assertEqual(session.current_section, "listening")

    def test_legacy_thirty_minute_listening_gets_official_review_time(self):
        self.assertEqual(runtime.listening_runtime_minutes(30), 32)
        self.assertEqual(runtime.listening_runtime_minutes(45), 45)
        self.assertEqual(runtime.listening_runtime_seconds(30, 1519.2), 1640)
        self.assertEqual(runtime.listening_runtime_seconds(30, 99999), 32 * 60)

    def test_expired_submission_uses_last_server_draft_not_new_client_answers(self):
        session = self.session()
        now = datetime(2026, 8, 28, 10, 0, 0)
        runtime.start_section(session, "reading", 60, now)
        self.assertTrue(runtime.save_draft(session, "reading", {"1": "saved"}, now))

        answers, expired = runtime.submission_answers(
            session,
            "reading",
            {"1": "changed after time"},
            now + timedelta(minutes=61),
        )
        self.assertTrue(expired)
        self.assertEqual(answers, {"1": "saved"})

    def test_expired_draft_is_rejected_and_persist_writes_final_snapshot(self):
        session = self.session()
        now = datetime(2026, 8, 28, 10, 0, 0)
        runtime.start_section(session, "listening", 30, now)
        self.assertFalse(
            runtime.save_draft(
                session,
                "listening",
                {"1": "late"},
                now + timedelta(minutes=30),
            )
        )
        runtime.persist_section_grade(
            session,
            "listening",
            {"correct": 1, "total": 1, "accuracy": 100, "ielts_score": 9, "results": [], "wrong_numbers": []},
            {"1": "answer"},
            1800,
            True,
            now=now + timedelta(minutes=30),
        )
        self.assertEqual(json.loads(session.listening_answers_json), {"1": "answer"})
        self.assertTrue(session.listening_auto_submitted)
        self.assertEqual(session.current_section, "reading")

    def test_audio_completion_caps_review_at_two_minutes_without_refresh_extension(self):
        session = self.session()
        now = datetime(2026, 8, 28, 10, 0, 0)
        runtime.start_section(session, "listening", 32, now)
        first = runtime.close_listening_to_review_window(session, now + timedelta(minutes=25))
        repeated = runtime.close_listening_to_review_window(session, now + timedelta(minutes=26))
        self.assertEqual(first, now + timedelta(minutes=27))
        self.assertEqual(repeated, first)


if __name__ == "__main__":
    unittest.main()
