import json
import re
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from flask_login import LoginManager

from api.mock_exam_review import mock_exam_review_bp
from api.mock_exam_student import mock_exam_student_bp
from models import MockExam, MockExamReview, MockExamSession, StudentProfile, db
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
        login_manager = LoginManager(self.app)

        @login_manager.user_loader
        def load_user(_user_id):
            return None

        @self.app.get("/exam/<int:exam_id>/session/<token>")
        def mock_exam_process(exam_id, token):
            return f"process:{exam_id}:{token}"

        @self.app.get("/exam/<int:exam_id>/session/<token>/result")
        def mock_exam_result(exam_id, token):
            return f"result:{exam_id}:{token}"

        @self.app.get("/practice")
        def practice_library():
            return "practice"

        for endpoint in ("listening_test_index", "reading_test_index", "reading_jijing_index", "login"):
            self.app.add_url_rule(f"/test/{endpoint}", endpoint=endpoint, view_func=lambda: "index")

        @self.app.post("/test-remember/<int:session_id>")
        def test_remember(session_id):
            review_workflow.remember_browser_exam_session(session_id)
            return "ok"

        self.app.register_blueprint(mock_exam_student_bp)
        self.app.register_blueprint(mock_exam_review_bp)

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
                listening_answers_json=json.dumps({"1": "beta"}),
                listening_results_json=json.dumps([_result(1, "alpha", "beta")]),
                reading_submitted_at=submitted_at,
                reading_correct=0,
                reading_total=1,
                reading_accuracy=0,
                reading_ielts_score=1.0,
                reading_answers_json=json.dumps({"2": "FALSE"}),
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
            self.mock_session_id = session.id

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
        self.assertEqual(page.count('data-mock-review-paper'), 2)
        self.assertIn('title="Listening 原题、作答与解析"', page)
        self.assertIn('title="Reading 原题、作答与解析"', page)
        self.assertNotIn("查看原卷与高亮", page)
        self.assertIn("/static/writing_tests/images/task1.png", page)
        self.assertIn("The chart shows...", page)
        for section in ("listening", "reading"):
            self.assertIn(
                f"/exam/{self.exam_id}/session/student-session-token/review/{section}", page
            )
        self.assertEqual(page.count('embed=1'), 2)

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

    def test_original_paper_restores_saved_grade_and_exact_exam_highlight_scope(self):
        for section, question_id, answer in (("listening", "1", "beta"), ("reading", "2", "FALSE")):
            with self.subTest(section=section), patch(
                "api.mock_exam_student._load_payload", side_effect=self._load_payload
            ), patch("api.mock_exam_student.db.session.commit") as commit:
                response = self.client.get(
                    f"/exam/{self.exam_id}/session/student-session-token/review/{section}"
                )
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response.headers["Cache-Control"])
            self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
            page = response.get_data(as_text=True)
            context = json.loads(re.search(r"const practiceContext = (.+);", page).group(1))
            self.assertTrue(context["read_only"])
            self.assertFalse(context["embed_review"])
            self.assertEqual(context["task_type"], "mock_exam_review")
            self.assertEqual(context["session_id"], self.mock_session_id)
            self.assertEqual(
                context["highlight_path"],
                f"/exam/{self.exam_id}/session/student-session-token/{section}",
            )
            self.assertEqual(context["initial_review"]["answers"], {question_id: answer})
            grade = context["initial_review"]["result"]
            self.assertEqual(grade["correct"], 0)
            self.assertEqual(grade["total"], 1)
            self.assertEqual(grade["ielts_score"], 1.0)
            self.assertEqual(grade["results"][0]["value"], answer)
            self.assertEqual(grade["results"][0]["awarded"], 0)
            self.assertNotIn("submit_url", context)
            self.assertNotIn("draft_url", context)
            self.assertIn("selection-highlight.js", page)
            self.assertIn("const examContext = null;", page)
            commit.assert_not_called()

    def test_embedded_original_paper_keeps_same_auth_grade_and_highlight_path(self):
        for section in ("listening", "reading"):
            with self.subTest(section=section), patch(
                "api.mock_exam_student._load_payload", side_effect=self._load_payload
            ):
                response = self.client.get(
                    f"/exam/{self.exam_id}/session/student-session-token/review/{section}?embed=1"
                )
            self.assertEqual(response.status_code, 200)
            page = response.get_data(as_text=True)
            context = json.loads(re.search(r"const practiceContext = (.+);", page).group(1))
            self.assertTrue(context["read_only"])
            self.assertTrue(context["embed_review"])
            self.assertEqual(context["initial_review"]["result"]["correct"], 0)
            self.assertEqual(
                context["highlight_path"],
                f"/exam/{self.exam_id}/session/student-session-token/{section}",
            )

    def test_original_paper_access_checks_precede_loading_answer_payload(self):
        with patch("api.mock_exam_student._load_payload") as loader:
            for suffix, expected in (
                ("wrong-token/review/listening", 404),
                ("student-session-token/review/writing", 404),
                ("student-session-token/review/invalid", 404),
                ("in-progress-token/review/listening", 302),
                ("in-progress-token/review/reading", 302),
                ("in-progress-token/review/reading?embed=1", 302),
            ):
                with self.subTest(suffix=suffix):
                    response = self.client.get(f"/exam/{self.exam_id}/session/{suffix}")
                    self.assertEqual(response.status_code, expected)
                    self.assertIn("no-store", response.headers["Cache-Control"])
            loader.assert_not_called()

        with self.app.app_context():
            session = db.session.get(MockExamSession, self.mock_session_id)
            session.reading_submitted_at = None
            db.session.commit()
        with patch("api.mock_exam_student._load_payload") as loader:
            response = self.client.get(
                f"/exam/{self.exam_id}/session/student-session-token/review/reading"
            )
            self.assertEqual(response.status_code, 404)
            loader.assert_not_called()

    def test_original_paper_missing_library_payload_returns_not_found(self):
        with patch("api.mock_exam_student._load_payload", return_value=None):
            response = self.client.get(
                f"/exam/{self.exam_id}/session/student-session-token/review/listening"
            )
        self.assertEqual(response.status_code, 404)

    def test_profile_review_directly_embeds_the_same_token_scoped_original_papers(self):
        with self.app.app_context():
            profile = StudentProfile(full_name="合成复盘学生")
            db.session.add(profile)
            db.session.flush()
            db.session.get(MockExamSession, self.mock_session_id).student_profile_id = profile.id
            db.session.commit()
        self.client.post(f"/test-remember/{self.mock_session_id}")
        with patch("api.mock_exam_student._load_payload", side_effect=self._load_payload):
            response = self.client.get(f"/practice/mock-exams/{self.mock_session_id}/review")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertNotIn("查看原卷与高亮", page)
        self.assertEqual(page.count('data-mock-review-paper'), 2)
        self.assertEqual(page.count('embed=1'), 2)
        for section in ("listening", "reading"):
            self.assertIn(
                f"/exam/{self.exam_id}/session/student-session-token/review/{section}", page
            )
        self.assertIn(f"practice_return=/practice/mock-exams/{self.mock_session_id}/review", page)
        self.assertIn("practice_source=mock_exam_review", page)

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
