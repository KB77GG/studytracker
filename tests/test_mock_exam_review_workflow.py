import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask
from flask_login import LoginManager, login_user, logout_user

from api.mock_exam_review import mock_exam_review_bp
from models import (
    MockExam,
    MockExamReview,
    MockExamSession,
    StudentProfile,
    User,
    db,
)
from services import mock_exam_review_workflow as workflow


class MockExamReviewWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(
            __name__,
            template_folder=str(Path(__file__).resolve().parents[1] / "templates"),
        )
        self.app.config.update(
            SECRET_KEY="review-workflow-test-secret",
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        self.app.add_url_rule("/", endpoint="index", view_func=lambda: "index")
        self.app.add_url_rule("/login", endpoint="login", view_func=lambda: "login")
        self.app.add_url_rule("/practice", endpoint="practice_library", view_func=lambda: "practice")
        self.app.add_url_rule("/student/today", endpoint="student_today", view_func=lambda: "today")
        self.app.add_url_rule("/logout", endpoint="logout", view_func=lambda: "logout")
        self.app.add_url_rule(
            "/admin/mock-exams/<int:exam_id>/sessions/<int:session_id>",
            endpoint="mock_exam_admin.exam_session_detail",
            view_func=lambda exam_id, session_id: "detail",
        )
        self.app.add_url_rule(
            "/exam/<int:exam_id>/session/<token>",
            endpoint="mock_exam_process",
            view_func=lambda exam_id, token: f"continue-{exam_id}-{token}",
        )

        @self.app.post("/test-login/<int:user_id>")
        def test_login(user_id):
            login_user(db.session.get(User, user_id))
            return "ok"

        @self.app.post("/test-logout")
        def test_logout():
            logout_user()
            return "ok"

        @self.app.post("/test-remember/<int:session_id>")
        def test_remember(session_id):
            workflow.remember_browser_exam_session(session_id)
            return "ok"

        self.app.register_blueprint(mock_exam_review_bp)
        with self.app.app_context():
            db.create_all()
            self.teacher = User(
                username="review_teacher",
                password_hash="unused",
                role=User.ROLE_TEACHER,
                display_name="批改老师",
            )
            self.student = User(
                username="review_student",
                password_hash="unused",
                role=User.ROLE_STUDENT,
                display_name="学生甲",
            )
            self.other_student = User(
                username="review_other",
                password_hash="unused",
                role=User.ROLE_STUDENT,
                display_name="学生乙",
            )
            self.unbound_student = User(
                username="review_unbound_same_name",
                password_hash="unused",
                role=User.ROLE_STUDENT,
                display_name="学生甲",
            )
            db.session.add_all(
                [self.teacher, self.student, self.other_student, self.unbound_student]
            )
            db.session.flush()
            self.profile = StudentProfile(full_name="学生甲", user_id=self.student.id)
            self.other_profile = StudentProfile(full_name="学生乙", user_id=self.other_student.id)
            self.exam = MockExam(
                name="Review Test",
                listening_test_id="missing-listening",
                reading_test_id="missing-reading",
                writing_test_id="missing-writing",
                pincode="ABCDE",
            )
            db.session.add_all([self.profile, self.other_profile, self.exam])
            db.session.flush()
            self.mock_session = self._make_session(self.profile, "student甲")
            self.other_session = self._make_session(self.other_profile, "student乙")
            db.session.commit()
            self.teacher_id = self.teacher.id
            self.student_id = self.student.id
            self.profile_id = self.profile.id
            self.exam_id = self.exam.id
            self.mock_session_id = self.mock_session.id
            self.other_session_id = self.other_session.id
            self.unbound_student_id = self.unbound_student.id
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _make_session(self, profile, name):
        mock_session = MockExamSession(
            exam_id=self.exam.id,
            student_name=name,
            student_profile_id=profile.id,
            access_token=f"token-{name}",
            status=MockExamSession.STATUS_SUBMITTED,
            current_section=MockExamSession.SECTION_FINISHED,
            started_at=datetime.utcnow() - timedelta(minutes=80),
            finished_at=datetime.utcnow(),
            listening_submitted_at=datetime.utcnow() - timedelta(minutes=20),
            listening_correct=30,
            listening_total=40,
            listening_accuracy=75.0,
            listening_ielts_score=7.0,
            listening_results_json=json.dumps([]),
            reading_submitted_at=datetime.utcnow() - timedelta(minutes=5),
            reading_correct=32,
            reading_total=40,
            reading_accuracy=80.0,
            reading_ielts_score=7.5,
            reading_results_json=json.dumps([]),
            writing_submitted_at=datetime.utcnow() - timedelta(minutes=1),
            writing_essay_task1="The original task one essay.",
            writing_essay_task2="The original task two essay.",
            writing_task1_words=155,
            writing_task2_words=260,
        )
        db.session.add(mock_session)
        db.session.flush()
        workflow.ensure_review_draft(mock_session)
        return mock_session

    def _login(self, user_id):
        self.client.post(f"/test-login/{user_id}")

    def _issue_link(self, session_id=None):
        self._login(self.teacher_id)
        response = self.client.post(
            f"/admin/mock-exams/{self.exam_id}/sessions/{session_id or self.mock_session_id}/review-link",
            json={},
        )
        self.assertEqual(response.status_code, 200)
        url = response.get_json()["url"]
        self.client.post("/test-logout")
        return url

    def test_score_formula_half_up_not_scorable_and_override_reason(self):
        from services import mock_exam_review as logic

        result = logic.calculate_writing_scores(
            {"ta": "6", "cc": "6.5", "lr": "6", "gra": "6.5"},
            {"tr": "6.5", "cc": "6.5", "lr": "7", "gra": "6.5"},
        )
        self.assertEqual(result["task1"]["raw_average"], 6.25)
        self.assertEqual(result["task1"]["band"], 6.5)
        self.assertEqual(result["writing_raw"], 6.5)
        self.assertEqual(result["writing_band"], 6.5)
        invalid = logic.validate_score_payload(
            {"task1_ta": "6.0", "task1_band_override": "7.0"},
            require_complete=False,
        )[1]
        self.assertEqual(invalid["override_reason"], "override_reason_required")
        not_scorable = logic.calculate_writing_scores(
            {"ta": "not_scorable", "cc": "6", "lr": "6", "gra": "6"},
            {"tr": "6", "cc": "6", "lr": "6", "gra": "6"},
        )
        self.assertEqual(not_scorable["task1"]["state"], "not_scorable")
        self.assertIsNone(not_scorable["writing_band"])

    def test_capability_exchange_clean_url_and_cross_record_isolation(self):
        link = self._issue_link()
        self.assertIn("/mock-review/access/", link)
        access = self.client.get(link, follow_redirects=False)
        self.assertEqual(access.status_code, 303)
        self.assertIn("/mock-review/", access.headers["Location"])
        self.assertNotIn("access/", access.headers["Location"])
        self.assertEqual(access.headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertEqual(access.headers["Referrer-Policy"], "no-referrer")
        editor = self.client.get(access.headers["Location"])
        self.assertEqual(editor.status_code, 200)
        self.assertEqual(editor.headers["X-Robots-Tag"], "noindex, nofollow, noarchive")
        self.assertIn("The original task one essay.", editor.get_data(as_text=True))
        self.assertIn("老师修改稿", editor.get_data(as_text=True))

        other_link = self._issue_link(self.other_session_id)
        with self.app.app_context():
            other_review_id = db.session.get(MockExamSession, self.other_session_id).review.id
        wrong_clean = self.client.get(f"/mock-review/{other_review_id}")
        self.assertEqual(wrong_clean.status_code, 404)
        self.client.get(other_link)
        self.assertEqual(self.client.get(f"/mock-review/{other_review_id}").status_code, 200)

    def test_capability_expiry_tamper_and_version_rotation(self):
        link = self._issue_link()
        tampered = link + "tampered"
        self.assertEqual(self.client.get(tampered).status_code, 404)

        with self.app.app_context():
            review = db.session.get(MockExamSession, self.mock_session_id).review
            review.link_expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.session.commit()
        self.assertEqual(self.client.get(link).status_code, 404)

        current = self._issue_link()
        rotated = self._issue_link()
        self.assertEqual(self.client.get(current).status_code, 404)
        self.assertEqual(self.client.get(rotated, follow_redirects=False).status_code, 303)

    def test_capability_url_uses_forwarded_https_scheme(self):
        self._login(self.teacher_id)
        response = self.client.post(
            f"/admin/mock-exams/{self.exam_id}/sessions/{self.mock_session_id}/review-link",
            json={},
            headers={"X-Forwarded-Proto": "https"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["url"].startswith("https://"))

    def test_admin_open_reuses_active_capability(self):
        link = self._issue_link()
        with self.app.app_context():
            review = db.session.get(MockExamSession, self.mock_session_id).review
            link_version = review.link_version

        self._login(self.teacher_id)
        opened = self.client.get(
            f"/admin/mock-exams/{self.exam_id}/sessions/{self.mock_session_id}/review/open",
            follow_redirects=False,
        )
        self.assertEqual(opened.status_code, 302)
        with self.app.app_context():
            self.assertEqual(
                db.session.get(MockExamSession, self.mock_session_id).review.link_version,
                link_version,
            )
        self.assertEqual(self.client.get(link, follow_redirects=False).status_code, 303)

    def test_management_posts_require_json(self):
        self._login(self.teacher_id)
        base = f"/admin/mock-exams/{self.exam_id}/sessions/{self.mock_session_id}"
        for suffix in ("/review-link", "/review-link/revoke", "/review-link/reopen"):
            response = self.client.post(base + suffix)
            self.assertEqual(response.status_code, 415)

        issued = self.client.post(base + "/review-link", json={})
        self.assertEqual(issued.status_code, 200)
        revoked = self.client.post(base + "/review-link/revoke", json={})
        self.assertEqual(revoked.status_code, 200)
        reopened = self.client.post(base + "/review-link/reopen", json={})
        self.assertEqual(reopened.status_code, 200)

    def test_revoke_invalidates_capability_and_editor_scope(self):
        link = self._issue_link()
        self._login(self.teacher_id)
        with self.app.app_context():
            review_id = db.session.get(MockExamSession, self.mock_session_id).review.id
        revoked = self.client.post(
            f"/admin/mock-exams/{self.exam_id}/sessions/{self.mock_session_id}/review-link/revoke",
            json={},
        )
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(self.client.get(link).status_code, 404)
        self.assertEqual(self.client.get(f"/mock-review/{review_id}").status_code, 404)

    def test_save_optimistic_conflict_publish_and_original_immutable(self):
        link = self._issue_link()
        editor = self.client.get(link, follow_redirects=False)
        clean_url = editor.headers["Location"]
        page = self.client.get(clean_url)
        self.assertEqual(page.status_code, 200)
        fields = {
            "reviewer_name": "批改老师",
            "task1_ta": "6.0",
            "task1_cc": "6.5",
            "task1_lr": "6.0",
            "task1_gra": "6.5",
            "task2_tr": "6.5",
            "task2_cc": "6.5",
            "task2_lr": "7.0",
            "task2_gra": "6.5",
            "task1_teacher_draft": "Teacher revision one.",
            "task2_teacher_draft": "Teacher revision two.",
            "overall_feedback": "Good structure.",
            "task1_feedback": "Task one feedback.",
            "task2_feedback": "Task two feedback.",
        }
        saved = self.client.post(
            clean_url + "/save",
            json={"version": 1, "fields": fields},
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()["review"]["version"], 2)
        conflict = self.client.post(clean_url + "/save", json={"version": 1, "fields": fields})
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.get_json()["error"], "version_conflict")

        published = self.client.post(
            clean_url + "/publish",
            json={"version": 2, "fields": fields},
        )
        self.assertEqual(published.status_code, 200)
        self.assertEqual(published.get_json()["review"]["status"], "published")
        read_only_page = self.client.get(clean_url)
        self.assertEqual(read_only_page.status_code, 200)
        self.assertIn('data-review-field="task1_teacher_draft" rows="16" readonly', read_only_page.get_data(as_text=True))
        read_only = self.client.post(clean_url + "/save", json={"version": 3, "fields": fields})
        self.assertEqual(read_only.status_code, 409)
        with self.app.app_context():
            stored = db.session.get(MockExamSession, self.mock_session_id)
            self.assertEqual(stored.writing_essay_task1, "The original task one essay.")
            self.assertEqual(stored.writing_essay_task2, "The original task two essay.")

    def test_student_account_history_and_light_mode_scope(self):
        self._login(self.student_id)
        response = self.client.get("/api/practice/mock-exams")
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()["sessions"]
        self.assertEqual({row["id"] for row in rows}, {self.mock_session_id})
        self.assertEqual(rows[0]["review_status"], "draft")

        self.client.post("/test-logout")
        self.client.post(f"/test-remember/{self.mock_session_id}")
        light = self.client.get("/api/practice/mock-exams")
        self.assertEqual(light.status_code, 200)
        self.assertEqual([row["id"] for row in light.get_json()["sessions"]], [self.mock_session_id])
        cross = self.client.get(f"/practice/mock-exams/{self.other_session_id}/review")
        self.assertEqual(cross.status_code, 404)

    def test_anonymous_mock_session_scope_works_without_practice_name(self):
        self.client.post(f"/test-remember/{self.mock_session_id}")
        history = self.client.get("/api/practice/mock-exams")
        self.assertEqual(history.status_code, 200)
        self.assertEqual([row["id"] for row in history.get_json()["sessions"]], [self.mock_session_id])
        own_review = self.client.get(f"/practice/mock-exams/{self.mock_session_id}/review")
        self.assertEqual(own_review.status_code, 200)
        other_review = self.client.get(f"/practice/mock-exams/{self.other_session_id}/review")
        self.assertEqual(other_review.status_code, 404)

    def test_practice_name_binding_can_access_own_mock_history(self):
        with self.client.session_transaction() as browser:
            browser[workflow.PRACTICE_STUDENT_NAME_KEY] = "学生甲"

        history = self.client.get("/api/practice/mock-exams")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(
            [row["id"] for row in history.get_json()["sessions"]],
            [self.mock_session_id],
        )
        own_review = self.client.get(f"/practice/mock-exams/{self.mock_session_id}/review")
        self.assertEqual(own_review.status_code, 200)
        other_review = self.client.get(f"/practice/mock-exams/{self.other_session_id}/review")
        self.assertEqual(other_review.status_code, 404)

    def test_practice_name_binding_rejects_ambiguous_active_profiles(self):
        with self.app.app_context():
            db.session.add(StudentProfile(full_name="学生甲"))
            db.session.commit()
        with self.client.session_transaction() as browser:
            browser[workflow.PRACTICE_STUDENT_NAME_KEY] = "学生甲"

        history = self.client.get("/api/practice/mock-exams")
        self.assertEqual(history.status_code, 401)
        self.assertEqual(history.get_json()["error"], "not_verified")
        review = self.client.get(f"/practice/mock-exams/{self.mock_session_id}/review")
        self.assertEqual(review.status_code, 404)

    def test_anonymous_mock_scope_requires_matching_access_proof(self):
        self.client.post(f"/test-remember/{self.mock_session_id}")
        with self.client.session_transaction() as browser:
            browser.pop(workflow.EXAM_SESSION_PROOF_KEY, None)
        self.assertEqual(self.client.get("/api/practice/mock-exams").status_code, 401)

        self.client.post(f"/test-remember/{self.mock_session_id}")
        with self.client.session_transaction() as browser:
            browser[workflow.EXAM_SESSION_KEY] = self.other_session_id
        self.assertEqual(self.client.get("/api/practice/mock-exams").status_code, 401)
        self.assertEqual(
            self.client.get(f"/practice/mock-exams/{self.other_session_id}/review").status_code,
            404,
        )

        self.client.post(f"/test-remember/{self.mock_session_id}")
        with self.client.session_transaction() as browser:
            browser[workflow.EXAM_SESSION_PROOF_KEY] = "wrong-proof"
        self.assertEqual(self.client.get("/api/practice/mock-exams").status_code, 401)

    def test_unbound_same_name_student_cannot_access_history(self):
        self._login(self.unbound_student_id)
        history = self.client.get("/api/practice/mock-exams")
        self.assertEqual(history.status_code, 401)
        self.assertEqual(history.get_json()["error"], "not_verified")
        review = self.client.get(f"/practice/mock-exams/{self.mock_session_id}/review")
        self.assertEqual(review.status_code, 404)

    def test_unbound_student_can_use_explicit_practice_name_binding(self):
        self._login(self.unbound_student_id)
        with self.client.session_transaction() as browser:
            browser[workflow.PRACTICE_STUDENT_NAME_KEY] = "学生甲"

        history = self.client.get("/api/practice/mock-exams")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(
            [row["id"] for row in history.get_json()["sessions"]],
            [self.mock_session_id],
        )

    def test_editor_template_has_revision_aware_save_queue(self):
        template = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "admin"
            / "mock_exam_review_editor.html"
        ).read_text(encoding="utf-8")
        for marker in (
            "editRevision",
            "persistedRevision",
            "queuedSave",
            "publishQueued",
            "if (editRevision === requestRevision)",
            "sendSave('save', editRevision)",
            "publishStarted = false",
            "retrySaveLater()",
        ):
            self.assertIn(marker, template)
        self.assertNotIn("if (readOnly || saving) return;", template)

        catch_block = template.split("} catch (_error) {", 1)[1].split("} finally {", 1)[0]
        self.assertIn("publishQueued = true", catch_block)
        self.assertIn("publishStarted = false", catch_block)
        self.assertIn("setEditorLocked(false)", catch_block)
        self.assertIn("retrySaveLater()", catch_block)

    def test_public_review_templates_render_both_base_content_blocks(self):
        root = Path(__file__).resolve().parents[1]
        base = (root / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertNotIn("self.content_dashboard()", base)
        for relative in (
            "templates/admin/mock_exam_review_editor.html",
            "templates/practice/mock_exam_review.html",
        ):
            template = (root / relative).read_text(encoding="utf-8")
            self.assertIn("{% block content_dashboard %}", template)
            self.assertIn("{% block content_public %}", template)

    def test_student_cannot_see_draft_teacher_feedback_until_published(self):
        self._login(self.student_id)
        draft = self.client.get(f"/practice/mock-exams/{self.mock_session_id}/review")
        self.assertEqual(draft.status_code, 200)
        self.assertEqual(draft.headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertEqual(draft.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(draft.headers["X-Robots-Tag"], "noindex, nofollow, noarchive")
        draft_html = draft.get_data(as_text=True)
        self.assertIn("老师还在整理写作批改", draft_html)
        self.assertNotIn("Good structure.", draft_html)

        self.client.post("/test-logout")
        link = self._issue_link()
        clean_url = self.client.get(link, follow_redirects=False).headers["Location"]
        fields = {
            "reviewer_name": "批改老师",
            "task1_ta": "6", "task1_cc": "6", "task1_lr": "6", "task1_gra": "6",
            "task2_tr": "6", "task2_cc": "6", "task2_lr": "6", "task2_gra": "6",
            "overall_feedback": "Published feedback.",
        }
        response = self.client.post(clean_url + "/publish", json={"version": 1, "fields": fields})
        self.assertEqual(response.status_code, 200)

        self._login(self.student_id)
        published = self.client.get(f"/practice/mock-exams/{self.mock_session_id}/review")
        self.assertEqual(published.status_code, 200)
        self.assertIn("Published feedback.", published.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
