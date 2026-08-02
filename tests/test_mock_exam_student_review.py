import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from api.mock_exam_student import mock_exam_student_bp
from models import MockExam, MockExamReview, MockExamSession, db
from services import mock_exam_review_workflow as review_workflow

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
        self.assertEqual(response.headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow, noarchive")
        page = response.get_data(as_text=True)
        self.assertIn("学生可见模考 · 逐题复盘", page)
        self.assertIn("Question stem.", page)
        self.assertIn("对应原文", page)
        self.assertIn("Source sentence.", page)
        self.assertIn("/static/writing_tests/images/task1.png", page)
        self.assertIn("The chart shows...", page)

        missing = self.client.get(f"/exam/{self.exam_id}/session/wrong-token/review")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertEqual(missing.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(missing.headers["X-Robots-Tag"], "noindex, nofollow, noarchive")

    def test_in_progress_student_is_redirected_without_loading_answers(self):
        with patch("api.mock_exam_student._load_payload") as loader:
            response = self.client.get(f"/exam/{self.exam_id}/session/in-progress-token/review")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/exam/", response.headers["Location"])
        self.assertIn("/session/in-progress-token", response.headers["Location"])
        loader.assert_not_called()

    def test_published_teacher_review_is_visible_on_existing_token_route_only_after_publish(self):
        with self.app.app_context():
            session = MockExamSession.query.filter_by(access_token="student-session-token").first()
            review = review_workflow.ensure_review_draft(session)
            review.overall_feedback = "SECRET draft feedback"
            review.task1_teacher_draft = "SECRET draft correction"
            db.session.commit()

        with patch("api.mock_exam_student._load_payload", side_effect=self._load_payload):
            draft = self.client.get(f"/exam/{self.exam_id}/session/student-session-token/review")
        self.assertEqual(draft.status_code, 200)
        draft_page = draft.get_data(as_text=True)
        self.assertNotIn("SECRET draft feedback", draft_page)
        self.assertNotIn("SECRET draft correction", draft_page)

        with self.app.app_context():
            review = MockExamReview.query.join(MockExamSession).filter(
                MockExamSession.access_token == "student-session-token"
            ).first()
            review.status = MockExamReview.STATUS_PUBLISHED
            review.reviewer_name = "李老师"
            review.listening_feedback = "Published listening feedback"
            review.reading_feedback = "Published reading feedback"
            review.overall_feedback = "Published overall feedback"
            review.next_stage_advice = "Published next step"
            review.task1_ta = review.task1_cc = review.task1_lr = review.task1_gra = "6"
            review.task2_tr = review.task2_cc = review.task2_lr = review.task2_gra = "7"
            review.task1_band = 6.0
            review.task2_band = 7.0
            review.writing_raw = 6.6666666667
            review.writing_band = 6.5
            review.task1_teacher_draft = "Published teacher correction"
            review.task2_teacher_draft = "Published Task 2 correction"
            review.question_feedback_json = json.dumps(
                {"task1": "Task 1 published note", "task2": "Task 2 published note"}
            )
            db.session.commit()

        with patch("api.mock_exam_student._load_payload", side_effect=self._load_payload):
            published = self.client.get(
                f"/exam/{self.exam_id}/session/student-session-token/review"
            )
        self.assertEqual(published.status_code, 200)
        published_page = published.get_data(as_text=True)
        for text in (
            "Published listening feedback",
            "Published reading feedback",
            "Published overall feedback",
            "Published next step",
            "Published teacher correction",
            "Published Task 2 correction",
            "Writing Band",
            "6.5",
            "TA",
        ):
            self.assertIn(text, published_page)


if __name__ == "__main__":
    unittest.main()
