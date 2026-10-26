import json
import time
import unittest
from datetime import datetime, timedelta

import jwt
from flask import Flask
from flask_login import LoginManager

from api.miniprogram import mp_bp
from api.question_type_practice import question_type_practice_bp
from api.writing_library import writing_library_bp
from models import (
    ParentStudentLink,
    QuestionTypePracticeAttempt,
    StudentProfile,
    Task,
    User,
    WritingTypingAttempt,
    db,
)
from services.task_date_gate import beijing_today
from services.writing_library import get_exercise


class ParentWebPracticeReportTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="parent-web-test",
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)
        login_manager.user_loader(lambda user_id: db.session.get(User, int(user_id)))
        self.app.register_blueprint(mp_bp)
        self.app.register_blueprint(writing_library_bp)
        self.app.register_blueprint(question_type_practice_bp)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        parent = User(username="parent", password_hash="test", role=User.ROLE_PARENT)
        other_parent = User(username="other_parent", password_hash="test", role=User.ROLE_PARENT)
        student = User(username="student", password_hash="test", role=User.ROLE_STUDENT)
        other_student = User(username="other_student", password_hash="test", role=User.ROLE_STUDENT)
        db.session.add_all([parent, other_parent, student, other_student])
        db.session.flush()
        self.profile = StudentProfile(user_id=student.id, full_name="合成学生甲")
        self.other_profile = StudentProfile(user_id=other_student.id, full_name="合成学生乙")
        self.link = ParentStudentLink(
            parent_id=parent.id, student_name="合成学生甲", is_active=True
        )
        db.session.add_all([self.profile, self.other_profile, self.link])
        db.session.commit()
        self.headers = self._headers(parent)
        self.other_headers = self._headers(other_parent)
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _headers(self, user):
        token = jwt.encode(
            {"sub": str(user.id), "exp": int(time.time()) + 3600},
            "parent-web-test",
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    def _task(self, *, kind="writing_practice", snapshot=None, status="pending"):
        task = Task(
            date=beijing_today().isoformat(),
            student_name=self.profile.full_name,
            category="写作" if kind == "writing_practice" else "题型专项",
            detail="合成练习",
            grading_mode=kind,
            status=status,
            question_ids=json.dumps(
                snapshot or {"writing_resource_type": "exercise", "writing_resource_id": "t1-001"}
            ),
            accuracy=0.0,
            listening_access_token="never-expose-this-token",
        )
        db.session.add(task)
        db.session.commit()
        return task

    def _attempt(
        self,
        *,
        profile=None,
        exercise="t1-001",
        completed=True,
        accuracy=96.5,
        text="Synthetic typed essay.",
    ):
        row = WritingTypingAttempt(
            student_profile_id=(profile or self.profile).id,
            exercise_id=exercise,
            band="7",
            started_at=datetime(2026, 10, 26, 1),
            completed_at=datetime(2026, 10, 26, 1, 5) if completed else None,
            status="completed" if completed else "in_progress",
            duration_seconds=300,
            typed_text=text,
            typed_word_count=120,
            target_word_count=125,
            speed_wpm=24,
            accuracy=accuracy,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def _bind(self, task, *rows):
        snapshot = json.loads(task.question_ids)
        snapshot["writing_attempt_ids"] = [row.id for row in rows]
        task.question_ids = json.dumps(snapshot)
        db.session.commit()

    def _detail(self, task, headers=None):
        response = self.client.get(
            f"/api/miniprogram/parent/tasks/{task.id}", headers=headers or self.headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("never-expose-this-token", response.text)
        return response.json["detail"]

    def _specialty(self, *, submitted=True, subject="reading"):
        snapshot = {
            "subject": subject,
            "question_count": 3,
            "payload": {
                "passages" if subject == "reading" else "sections": [
                    {
                        "groups": [
                            {
                                "title": "<b>Frozen group prompt</b>",
                                "questions": [
                                    {
                                        "id": "one",
                                        "number": 1,
                                        "title": "<p>Question one</p>",
                                        "answer": "CHANGED_SOURCE",
                                    },
                                    {"id": "two", "number": 2},
                                    {"id": "three", "number": 3},
                                ],
                            }
                        ]
                    }
                ]
            },
        }
        task = self._task(
            kind="question_type_practice",
            snapshot=snapshot,
            status="done" if submitted else "pending",
        )
        attempt = QuestionTypePracticeAttempt(
            task_id=task.id,
            student_name=task.student_name,
            subject=subject,
            standard_type="multiple_choice_multiple",
            pace="training",
            snapshot_hash="synthetic-hash",
            status="submitted" if submitted else "in_progress",
            answers_json=json.dumps({"one": "A", "two": "B"}),
            results_json=json.dumps(
                {
                    "results": [
                        {
                            "id": "one",
                            "q": "1",
                            "value": "WRONG_SAVED",
                            "answer": "ORIGINAL_SAVED",
                            "status": "incorrect",
                            "marks": 1,
                            "awarded": 0,
                        },
                        {
                            "ids": ["two", "three"],
                            "numbers": [2, 3],
                            "q": "2-3",
                            "value": "A,B",
                            "answer": "B,C",
                            "status": "partial",
                            "marks": 2,
                            "awarded": 1,
                        },
                    ]
                }
            ),
            total_count=3,
            correct_count=1,
            accuracy=33.3,
            duration_seconds=95,
            submitted_at=datetime(2026, 10, 26, 1, 5) if submitted else None,
        )
        db.session.add(attempt)
        db.session.commit()
        return task, attempt

    def test_bound_writing_result_filters_student_resource_and_incomplete_attempts(self):
        task = self._task(status="done")
        actual = self._attempt()
        other_student = self._attempt(profile=self.other_profile, text="Private other student")
        other_exercise = self._attempt(exercise="t1-002", text="Wrong exercise")
        draft = self._attempt(completed=False, text="Unsubmitted draft")
        self._bind(task, actual, other_student, other_exercise, draft)
        detail = self._detail(task)
        self.assertEqual(detail["kind"], "writing_typing")
        self.assertEqual(detail["accuracy"], 96.5)
        self.assertEqual(detail["accuracy_label"], "打字准确率")
        self.assertEqual(detail["writing_result"]["typed_text"], actual.typed_text)
        self.assertEqual(detail["writing_result"]["speed_wpm"], 24)
        self.assertEqual(detail["writing_result"]["band"], "7")
        self.assertEqual(len(detail["writing_history"]), 1)
        self.assertTrue(detail["writing_result"]["completed_at"].endswith("Z"))
        self.assertEqual(detail["summary"]["assigned_total"], 0)

    def test_same_exercise_tasks_do_not_share_results(self):
        first, second = self._task(status="done"), self._task(status="done")
        attempt_one = self._attempt(text="First task result")
        attempt_two = self._attempt(text="Second task result", accuracy=50)
        self._bind(first, attempt_one)
        self._bind(second, attempt_two)
        self.assertEqual(self._detail(first)["writing_result"]["typed_text"], "First task result")
        self.assertEqual(self._detail(second)["writing_result"]["typed_text"], "Second task result")

    def test_legacy_writing_never_guesses_latest_attempt(self):
        task = self._task(status="done")
        task.accuracy = 82
        db.session.commit()
        self._attempt(text="Must not attach this independent exercise")
        detail = self._detail(task)
        self.assertIsNone(detail["writing_result"])
        self.assertEqual(detail["accuracy"], 82)
        self.assertIn("未绑定", detail["summary_text"])

    def test_unsubmitted_writing_has_no_zero_score(self):
        task = self._task()
        draft = self._attempt(completed=False)
        self._bind(task, draft)
        detail = self._detail(task)
        self.assertIsNone(detail["accuracy"])
        self.assertIsNone(detail["writing_result"])
        self.assertIn("尚未提交", detail["summary_text"])

    def test_zero_accuracy_is_kept_after_real_submission(self):
        task = self._task(status="done")
        self._bind(task, self._attempt(accuracy=0))
        self.assertEqual(self._detail(task)["accuracy"], 0)

    def test_mother_topic_has_completion_and_duration_without_typing_grade(self):
        task = self._task(
            status="done",
            snapshot={
                "writing_resource_type": "mother_topic",
                "writing_resource_id": "education",
                "writing_topic_result": {
                    "duration_seconds": 180,
                    "completed_at": "2026-10-26T01:05:00Z",
                },
            },
        )
        detail = self._detail(task)
        self.assertEqual(detail["kind"], "writing_mother_topic")
        self.assertIsNone(detail["accuracy"])
        self.assertEqual(detail["writing_result"]["duration_seconds"], 180)
        self.assertNotIn("待批改", detail["summary_text"])

    def test_specialty_uses_saved_result_without_regrading_and_is_read_only(self):
        for subject in ("reading", "listening"):
            with self.subTest(subject=subject):
                task, attempt = self._specialty(subject=subject)
                before = (
                    task.question_ids,
                    attempt.answers_json,
                    attempt.results_json,
                    attempt.updated_at,
                )
                detail = self._detail(task)
                self.assertEqual(detail["kind"], "question_type_practice")
                self.assertEqual(detail["accuracy"], 33.3)
                self.assertEqual(detail["summary"]["correct_total"], 1)
                self.assertEqual(detail["summary"]["attempted_total"], 3)
                self.assertEqual(detail["items"][0]["correct_answer"], "ORIGINAL_SAVED")
                self.assertEqual(detail["items"][0]["student_answer"], "WRONG_SAVED")
                self.assertEqual(detail["items"][0]["prompt"], "Question one")
                self.assertEqual(detail["items"][1]["result_status"], "partial")
                self.assertEqual(detail["items"][1]["marks"], 2)
                self.assertEqual(
                    before,
                    (
                        task.question_ids,
                        attempt.answers_json,
                        attempt.results_json,
                        attempt.updated_at,
                    ),
                )

    def test_specialty_draft_never_exposes_answer_or_grade(self):
        task, _ = self._specialty(submitted=False)
        detail = self._detail(task)
        self.assertIsNone(detail["accuracy"])
        self.assertEqual(detail["items"], [])
        self.assertNotIn("ORIGINAL_SAVED", json.dumps(detail))
        self.assertIn("尚未提交", detail["summary_text"])

    def test_missing_specialty_attempt_does_not_create_one(self):
        task = self._task(kind="question_type_practice", snapshot={"question_count": 5})
        self.assertEqual(QuestionTypePracticeAttempt.query.count(), 0)
        self.assertIsNone(self._detail(task)["accuracy"])
        self.assertEqual(QuestionTypePracticeAttempt.query.count(), 0)

    def test_only_active_bound_parent_can_read_results(self):
        task = self._task()
        url = f"/api/miniprogram/parent/tasks/{task.id}"
        self.assertEqual(self.client.get(url, headers=self.other_headers).status_code, 403)
        self.link.is_active = False
        db.session.commit()
        self.assertEqual(self.client.get(url, headers=self.headers).status_code, 403)

    def test_recent_feed_uses_result_summary_and_keeps_mother_topic_ungraded(self):
        writing = self._task(status="done")
        self._bind(writing, self._attempt(accuracy=0))
        mother = self._task(
            status="done",
            snapshot={"writing_resource_type": "mother_topic", "writing_resource_id": "education"},
        )
        response = self.client.get(
            "/api/miniprogram/parent/stats",
            query_string={"student_name": self.profile.full_name},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        feed = {row["id"]: row for row in response.json["recent"]}
        self.assertEqual(feed[writing.id]["accuracy"], 0)
        self.assertIn("打字练习已完成", feed[writing.id]["result_summary"])
        self.assertIsNone(feed[mother.id]["accuracy"])
        self.assertEqual(feed[mother.id]["result_kind"], "writing_mother_topic")

    def test_real_writing_start_finish_is_visible_to_parent(self):
        task = self._task()
        with self.client.session_transaction() as session:
            session["practice_student_name"] = self.profile.full_name
        started = self.client.post(
            "/writing/api/t1-001/typing/start", json={"band": "6.0", "task_id": task.id}
        )
        self.assertEqual(started.status_code, 200)
        attempt = db.session.get(WritingTypingAttempt, started.json["attempt_id"])
        attempt.started_at -= timedelta(seconds=60)
        db.session.commit()
        typed_text = get_exercise("t1-001")["essays"]["6.0"]["text"]
        finished = self.client.post(
            f"/writing/api/t1-001/typing/{attempt.id}/finish",
            json={"band": "6.0", "task_id": task.id, "typed_text": typed_text},
        )
        self.assertEqual(finished.status_code, 200)
        self.assertTrue(finished.json["task_completed"])
        detail = self._detail(task)
        self.assertEqual(detail["state"], "completed")
        self.assertEqual(detail["writing_result"]["typed_text"], typed_text)
        self.assertEqual(detail["accuracy"], finished.json["attempt"]["accuracy"])
        feed = self.client.get(
            "/api/miniprogram/parent/stats",
            query_string={"student_name": self.profile.full_name},
            headers=self.headers,
        ).json["recent"]
        self.assertEqual(feed[0]["id"], task.id)
        self.assertEqual(feed[0]["result_kind"], "writing_typing")

    def test_real_specialty_submit_preserves_multi_mark_result_and_blank_answer(self):
        snapshot = {
            "task_type": "question_type_practice",
            "subject": "listening",
            "question_count": 3,
            "snapshot_hash": "synthetic-snapshot",
            "standard_type": "multiple_choice_multiple",
            "pace": "training",
            "payload": {
                "sections": [
                    {
                        "groups": [
                            {
                                "question_group_id": "multi",
                                "type": "2",
                                "title": "Choose TWO letters",
                                "collect_option": {
                                    "list": [
                                        {"key": "A", "text": "Alpha"},
                                        {"key": "B", "text": "Beta"},
                                        {"key": "C", "text": "Gamma"},
                                    ]
                                },
                                "questions": [
                                    {"id": "q1", "number": 1, "answer": "B,C"},
                                    {"id": "q2", "number": 2, "answer": "B,C"},
                                ],
                            },
                            {
                                "question_group_id": "blank",
                                "type": "1",
                                "questions": [
                                    {
                                        "id": "q3",
                                        "number": 3,
                                        "answer": "roof",
                                        "title": "Complete the word",
                                    }
                                ],
                            },
                        ]
                    }
                ]
            },
        }
        task = self._task(kind="question_type_practice", snapshot=snapshot)
        submitted = self.client.post(
            f"/api/question-type-practice/task/{task.id}/submit?token={task.listening_access_token}",
            json={"answers": {"q1,q2": "A,B"}, "duration_seconds": 90},
        )
        self.assertEqual(submitted.status_code, 200)
        detail = self._detail(task)
        self.assertEqual(detail["accuracy"], submitted.json["result"]["accuracy"])
        self.assertEqual(detail["summary"]["correct_total"], 1)
        self.assertEqual(detail["summary"]["attempted_total"], 2)
        self.assertEqual(detail["items"][0]["number"], "1,2")
        self.assertEqual(detail["items"][0]["marks"], 2)
        self.assertEqual(detail["items"][0]["awarded"], 1)
        self.assertEqual(detail["items"][0]["result_status"], "partial")
        self.assertEqual(detail["items"][1]["result_status"], "unanswered")
        self.assertEqual(detail["items"][1]["result_label"], "未作答")
