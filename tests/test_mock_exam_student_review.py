import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from api.mock_exam_student import mock_exam_student_bp
from models import MockExam, MockExamSession, db

ROOT = Path(__file__).resolve().parents[1]


def _result(qid: int, answer: str, value: str, awarded: int = 0) -> dict:
    return {
        "ids": [str(qid)],
        "numbers": [qid],
        "q": str(qid),
        "answer": answer,
        "value": value,
        "marks": 1,
        "awarded": awarded,
        "correct": awarded == 1,
        "status": "correct" if awarded else "wrong",
        "status_label": "正确" if awarded else "错误",
    }


class MockExamStudentReviewRouteTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(
            __name__,
            template_folder=str(ROOT / "templates"),
            static_folder=str(ROOT / "static"),
        )
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="student-review-test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)

        @self.app.get("/exam/<int:exam_id>/session/<token>")
        def mock_exam_process(exam_id, token):
            return f"process:{exam_id}:{token}"

        @self.app.get("/exam/<int:exam_id>/session/<token>/result")
        def mock_exam_result(exam_id, token):
            return f"result:{exam_id}:{token}"

        @self.app.get("/practice")
        def practice_library():
            return "practice"

        self.app.register_blueprint(mock_exam_student_bp)

        with self.app.app_context():
            db.create_all()
            exam = MockExam(
                name="学生可见模考",
                listening_test_id="listening-test",
                reading_test_id="reading-test",
                writing_test_id="writing-test",
                pincode="12345",
            )
            db.session.add(exam)
            db.session.flush()
            submitted_at = datetime(2026, 8, 1, 4, 0)
            session = MockExamSession(
                exam_id=exam.id,
                student_name="测试学生",
                access_token="student-session-token",
                status=MockExamSession.STATUS_SUBMITTED,
                current_section=MockExamSession.SECTION_FINISHED,
                finished_at=submitted_at,
                listening_submitted_at=submitted_at,
                listening_correct=0,
                listening_total=1,
                listening_accuracy=0,
                listening_ielts_score=1.0,
                listening_results_json=json.dumps([_result(1, "alpha", "beta")]),
                reading_submitted_at=submitted_at,
                reading_correct=0,
                reading_total=1,
                reading_accuracy=0,
                reading_ielts_score=1.0,
                reading_results_json=json.dumps([_result(2, "NG", "FALSE")]),
                writing_submitted_at=submitted_at,
                writing_essay_task1="The chart shows...",
                writing_task1_words=3,
            )
            in_progress = MockExamSession(
                exam_id=exam.id,
                student_name="未交卷学生",
                access_token="in-progress-token",
                status=MockExamSession.STATUS_IN_PROGRESS,
            )
            db.session.add_all([session, in_progress])
            db.session.commit()
            self.exam_id = exam.id

        self.client = self.app.test_client()
        self.payloads = {
            "listening": {
                "sections": [
                    {
                        "title": "Section 1",
                        "transcript": [{"start": 1, "end": 3, "en": "The answer is alpha."}],
                        "groups": [
                            {
                                "desc": "Write ONE WORD ONLY.",
                                "questions": [{"id": 1, "number": 1, "start": 1, "end": 3}],
                            }
                        ],
                    }
                ]
            },
            "reading": {
                "passages": [
                    {
                        "title": "Passage 1",
                        "content": {
                            "title": "A test passage",
                            "paragraphs": [{"label": "A", "text": "Source sentence."}],
                        },
                        "groups": [
                            {
                                "desc": "Write TRUE, FALSE or NOT GIVEN.",
                                "questions": [
                                    {
                                        "id": 2,
                                        "number": 2,
                                        "title": "Question stem.",
                                        "central_sentences": {"sentences": ["Source sentence."]},
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
            "writing": {
                "tasks": [
                    {
                        "task": 1,
                        "prompt": "Describe the chart.",
                        "image": "images/task1.png",
                    }
                ]
            },
        }

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _load_payload(self, kind, _test_id):
        return self.payloads[kind]

    def test_submitted_student_can_review_only_with_exact_session_token(self):
        with patch("api.mock_exam_student._load_payload", side_effect=self._load_payload):
            response = self.client.get(f"/exam/{self.exam_id}/session/student-session-token/review")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("学生可见模考 · 逐题复盘", page)
        self.assertIn("Question stem.", page)
        self.assertIn("对应原文", page)
        self.assertIn("Source sentence.", page)
        self.assertIn("/static/writing_tests/images/task1.png", page)
        self.assertIn("The chart shows...", page)

        missing = self.client.get(f"/exam/{self.exam_id}/session/wrong-token/review")
        self.assertEqual(missing.status_code, 404)

    def test_in_progress_student_is_redirected_without_loading_answers(self):
        with patch("api.mock_exam_student._load_payload") as loader:
            response = self.client.get(f"/exam/{self.exam_id}/session/in-progress-token/review")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/exam/", response.headers["Location"])
        self.assertIn("/session/in-progress-token", response.headers["Location"])
        loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
