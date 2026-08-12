"""Web practice history API aggregation tests."""

import json
import unittest
from datetime import datetime

from flask import Flask
from flask_login import LoginManager

from api.practice_history import practice_history_bp
from models import (
    ListeningSegmentResult,
    ListeningTestSubmission,
    ReadingTestSubmission,
    StudentProfile,
    Task,
    db,
)


class PracticeHistoryApiTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="practice-history-test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)

        @login_manager.user_loader
        def _load_user(_user_id):
            return None

        self.app.register_blueprint(practice_history_bp)

        with self.app.app_context():
            db.create_all()
            db.session.add(StudentProfile(full_name="唐文婧"))
            db.session.flush()

            for section, correct, submitted_minute in (
                (1, 7, 22),
                (2, 7, 33),
                (4, 2, 50),
                (3, 5, 59),
            ):
                task = Task(
                    student_name="唐文婧",
                    date="2026-08-11",
                    category="雅思-听力-整套",
                    detail=f"Cambridge IELTS 17 Test 4 Listening Section {section}",
                    status="done",
                    listening_resource_type="cambridge_test",
                    listening_exercise_id="ielts17_test4",
                    question_ids=json.dumps({"listening_section_number": section}),
                )
                db.session.add(task)
                db.session.flush()
                db.session.add(
                    ListeningTestSubmission(
                        task_id=task.id,
                        student_name="唐文婧",
                        test_id="ielts17_test4",
                        test_title=f"Cambridge IELTS 17 Test 4 Listening Section {section}",
                        correct_count=correct,
                        total_count=10,
                        accuracy=correct * 10,
                        completion_rate=100,
                        duration_seconds=600,
                        submitted_at=datetime(2026, 8, 11, 5, submitted_minute),
                    )
                )

            # An older duplicate task for Section 1 must not inflate the daily total.
            duplicate_task = Task(
                student_name="唐文婧",
                date="2026-08-11",
                category="雅思-听力-整套",
                detail="Cambridge IELTS 17 Test 4 Listening Section 1",
                status="done",
                listening_resource_type="cambridge_test",
                listening_exercise_id="ielts17_test4",
                question_ids=json.dumps({"listening_section_number": 1}),
            )
            db.session.add(duplicate_task)
            db.session.flush()
            db.session.add(
                ListeningTestSubmission(
                    task_id=duplicate_task.id,
                    student_name="唐文婧",
                    test_id="ielts17_test4",
                    test_title="Cambridge IELTS 17 Test 4 Listening Section 1",
                    correct_count=0,
                    total_count=10,
                    accuracy=0,
                    completion_rate=100,
                    duration_seconds=300,
                    submitted_at=datetime(2026, 8, 11, 5, 10),
                )
            )

            reading_task = Task(
                student_name="唐文婧",
                date="2026-08-10",
                category="雅思-阅读-整套",
                detail="Cambridge IELTS 16 Test 2 Reading",
                status="done",
                reading_test_id="ielts16_test2",
            )
            db.session.add(reading_task)
            db.session.flush()
            db.session.add(
                ReadingTestSubmission(
                    task_id=reading_task.id,
                    student_name="唐文婧",
                    test_id="ielts16_test2",
                    test_title="Cambridge IELTS 16 Test 2 Reading",
                    correct_count=30,
                    total_count=40,
                    accuracy=75,
                    completion_rate=100,
                    duration_seconds=3000,
                    submitted_at=datetime(2026, 8, 10, 8, 0),
                )
            )

            intensive_task = Task(
                student_name="唐文婧",
                date="2026-08-08",
                category="雅思-听力-精听",
                detail="IELTS 15 Test 1 Section 1 精听",
                status="done",
                listening_resource_type="intensive",
                listening_exercise_id="ielts15_test1_s1",
                listening_access_token="test-token",
            )
            db.session.add(intensive_task)
            db.session.flush()
            db.session.add_all(
                [
                    ListeningSegmentResult(
                        task_id=intensive_task.id,
                        student_name="唐文婧",
                        segment_index=0,
                        correct_words=4,
                        total_words=5,
                        accuracy=80,
                        is_completed=True,
                        updated_at=datetime(2026, 8, 8, 5, 0),
                    ),
                    ListeningSegmentResult(
                        task_id=intensive_task.id,
                        student_name="唐文婧",
                        segment_index=1,
                        correct_words=3,
                        total_words=5,
                        accuracy=60,
                        is_completed=True,
                        updated_at=datetime(2026, 8, 8, 5, 1),
                    ),
                ]
            )
            db.session.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _verify_student(self):
        with self.client.session_transaction() as flask_session:
            flask_session["practice_student_name"] = "唐文婧"

    def test_requires_verified_student(self):
        response = self.client.get("/api/practice/history")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "not_verified")

    def test_sections_are_merged_into_one_daily_test_record(self):
        self._verify_student()
        response = self.client.get("/api/practice/history?limit=10")

        self.assertEqual(response.status_code, 200)
        listening = response.get_json()["records"][0]
        self.assertEqual(listening["title"], "剑桥雅思 17 · Test 4")
        self.assertEqual(listening["scope_label"], "4/4 Section")
        self.assertEqual(listening["correct_count"], 21)
        self.assertEqual(listening["total_count"], 40)
        self.assertEqual(listening["accuracy"], 52.5)
        self.assertEqual(listening["date"], "2026-08-11")
        self.assertEqual(listening["url"], "/listening/test/ielts17_test4?section=3")
        self.assertEqual(
            [attempt["accuracy"] for attempt in listening["attempts"]],
            [70.0, 70.0, 50.0, 20.0],
        )

    def test_history_includes_reading_and_server_owned_intensive_results(self):
        self._verify_student()
        records = self.client.get("/api/practice/history?limit=10").get_json()["records"]

        self.assertEqual(
            [record["kind"] for record in records],
            [
                "listening",
                "reading",
                "intensive",
            ],
        )
        self.assertEqual(records[1]["scope_label"], "整套")
        self.assertEqual(records[1]["url"], "/reading/test/ielts16_test2")
        self.assertEqual(records[2]["scope_label"], "已完成 2 句")
        self.assertEqual(records[2]["accuracy"], 70.0)
        self.assertIn("task_id=", records[2]["url"])
        self.assertIn("token=test-token", records[2]["url"])

    def test_limit_is_applied_after_cross_subject_sorting(self):
        self._verify_student()
        records = self.client.get("/api/practice/history?limit=1").get_json()["records"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "剑桥雅思 17 · Test 4")


if __name__ == "__main__":
    unittest.main()
