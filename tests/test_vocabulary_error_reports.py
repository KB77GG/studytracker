"""Synthetic-only authorization, reporting and read-only regression coverage."""

import json
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import jwt
from flask import Flask, g
from flask_login import LoginManager
from sqlalchemy import event

from api.vocabulary_error_reports import vocabulary_error_reports_bp
from models import (
    StudentProfile,
    TeacherStudentLink,
    User,
    VocabularyErrorQueue,
    VocabularyPolicyCheckpoint,
    VocabularyPolicyEvent,
    VocabularyReviewPolicyEnrollment,
    VocabularySense,
    db,
)
from services import vocabulary_error_queue as policy
from services import vocabulary_error_reporting as reporting

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 17, 4)
START = datetime(2026, 11, 1)


class VocabularyErrorReportsTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder=str(ROOT / "templates"))
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="synthetic-review-report-only",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            VOCABULARY_ERROR_REVIEW_ENABLED=True,
        )
        db.init_app(self.app)
        login = LoginManager(self.app)

        @login.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        self.app.register_blueprint(vocabulary_error_reports_bp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.users = {}
        for name, role in (
            ("teacher", "teacher"),
            ("other_teacher", "teacher"),
            ("assistant", "assistant"),
            ("admin", "admin"),
            ("student", "student"),
            ("linked", "student"),
            ("unrelated", "student"),
            ("parent", "parent"),
            ("inactive", "teacher"),
            ("planner", "course_planner"),
        ):
            self.users[name] = User(
                username=f"report-{name}",
                password_hash="synthetic",
                role=role,
                is_active=name != "inactive",
            )
        db.session.add_all(self.users.values())
        db.session.flush()
        self.profiles = {}
        for name in ("student", "linked", "unrelated"):
            profile = StudentProfile(
                user_id=self.users[name].id,
                full_name=f"合成{name}",
                primary_teacher_id=self.users[
                    "teacher" if name == "student" else "other_teacher"
                ].id,
            )
            db.session.add(profile)
            self.profiles[name] = profile
            db.session.add(
                VocabularyReviewPolicyEnrollment(
                    student_id=self.users[name].id,
                    enabled=True,
                    starts_at=START,
                )
            )
        db.session.flush()
        db.session.add(
            TeacherStudentLink(
                teacher_id=self.users["teacher"].id,
                student_id=self.profiles["linked"].id,
            )
        )
        self.sense = VocabularySense(
            canonical_key="report-sense",
            lemma="practice",
            meaning_zh="练习",
        )
        db.session.add(self.sense)
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.ctx.pop()

    def _queue(
        self,
        student="student",
        *,
        sense=None,
        dimension="meaning_recall",
        status="active",
        due=None,
    ):
        enrollment = db.session.get(VocabularyReviewPolicyEnrollment, self.users[student].id)
        queue = VocabularyErrorQueue(
            student_id=self.users[student].id,
            sense_id=(sense or self.sense).id,
            dimension=dimension,
            cohort_key=policy._cohort(enrollment),
            status=status,
            due_local_date=due or NOW.date(),
            opened_at=START,
            pause_until_local_date=NOW.date() + timedelta(days=3) if status == "paused" else None,
        )
        db.session.add(queue)
        db.session.flush()
        return queue

    def _event(self, queue, kind, *, day=None, student_id=None):
        row = VocabularyPolicyEvent(
            student_id=student_id or queue.student_id,
            queue_id=queue.id,
            source_key=f"synthetic-private-key-{queue.id}-{kind}-{day}",
            kind=kind,
            source="system",
            occurred_at=NOW,
            local_date=day or NOW.date(),
            detail_code="synthetic-private-detail",
        )
        db.session.add(row)
        db.session.flush()
        return row

    def _login(self, name):
        # This fixture keeps one app context; Flask-Login caches on its g.
        g.pop("_login_user", None)
        with self.client.session_transaction() as session:
            session.clear()
            if name:
                session["_user_id"] = str(self.users[name].id)
                session["_fresh"] = True

    def _bearer(self, name):
        token = jwt.encode(
            {"sub": str(self.users[name].id)},
            self.app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    def test_primary_and_linked_student_scope_excludes_unrelated(self):
        for name in self.profiles:
            self._event(self._queue(name, status="paused"), "paused")
        db.session.commit()
        result = reporting.weekly_report(self.users["teacher"], now=NOW)
        self.assertEqual(
            {s["profile_id"] for s in result["students"]},
            {
                self.profiles["student"].id,
                self.profiles["linked"].id,
            },
        )
        self.assertEqual(result["words"][0]["student_count"], 2)
        self.assertEqual(result["pilot_metrics"]["student_count"], 2)
        self.assertEqual(result["pilot_metrics"]["weekly_pauses"]["student_words"], 2)
        self.assertEqual({s["weekly_paused_words"] for s in result["students"]}, {1})
        self.assertNotIn(
            self.profiles["unrelated"].full_name, json.dumps(result, ensure_ascii=False)
        )

    def test_admin_and_assistant_match_existing_all_student_scope(self):
        for role in ("admin", "assistant"):
            with self.subTest(role=role):
                result = reporting.weekly_report(self.users[role], now=NOW)
                self.assertEqual(len(result["students"]), 3)

    def test_other_teacher_cannot_request_student_by_id_or_name(self):
        for args in ({"profile_id": self.profiles["student"].id}, {"student_name": "合成student"}):
            with (
                self.subTest(args=args),
                self.assertRaises(reporting.VocabularyReportError) as caught,
            ):
                reporting.assignment_load(self.users["other_teacher"], now=NOW, **args)
            self.assertEqual(caught.exception.code, "student_unavailable")
            self.assertEqual(caught.exception.status, 404)

    def test_ambiguous_name_never_guesses_authorized_student(self):
        db.session.add(
            StudentProfile(
                full_name="合成student",
                primary_teacher_id=self.users["other_teacher"].id,
            )
        )
        db.session.commit()
        with self.assertRaises(reporting.VocabularyReportError) as caught:
            reporting.assignment_load(self.users["teacher"], student_name="合成student", now=NOW)
        self.assertEqual(caught.exception.code, "student_unavailable")
        result = reporting.assignment_load(
            self.users["teacher"],
            profile_id=self.profiles["student"].id,
            now=NOW,
        )
        self.assertTrue(result["enabled"])

    def test_deleted_inactive_and_nonstudent_profiles_are_unavailable(self):
        profile = self.profiles["student"]
        for attr, value in (("is_deleted", True), ("is_active", False), ("role", "parent")):
            target = profile if attr == "is_deleted" else self.users["student"]
            old = getattr(target, attr)
            setattr(target, attr, value)
            db.session.commit()
            with self.subTest(attr=attr), self.assertRaises(reporting.VocabularyReportError):
                reporting.assignment_load(self.users["teacher"], profile_id=profile.id, now=NOW)
            setattr(target, attr, old)
            db.session.commit()

    def test_week_groups_senses_and_distinguishes_transitions_and_current_status(self):
        first = self._queue(status="paused")
        second = self._queue("linked", dimension="form_recall", status="maintenance")
        self._event(first, "paused")
        self._event(first, "reopened", day=NOW.date() - timedelta(days=1))
        self._event(second, "overdue_overload")
        self._event(second, "unanswerable")
        self._event(first, "answer")
        db.session.commit()
        result = reporting.weekly_report(self.users["teacher"], now=NOW)
        self.assertEqual(result["totals"], {kind: 1 for kind in reporting.EVENT_LABELS})
        word = result["words"][0]
        self.assertEqual((word["student_count"], word["event_count"]), (2, 4))
        self.assertEqual({e["status"] for e in word["events"]}, {"paused", "maintenance"})
        exported = json.dumps(result)
        self.assertNotIn("synthetic-private", exported)
        self.assertNotIn("source_key", exported)
        self.assertNotIn("password_hash", exported)

    def test_week_is_beijing_monday_to_sunday_inclusive(self):
        queue = self._queue()
        for day in (date(2026, 11, 15), date(2026, 11, 16), date(2026, 11, 22), date(2026, 11, 23)):
            self._event(queue, "paused", day=day)
        db.session.commit()
        # UTC Sunday 16:01 is Monday 00:01 in Beijing.
        result = reporting.weekly_report(self.users["teacher"], now=datetime(2026, 11, 15, 16, 1))
        self.assertEqual((result["week_start"], result["week_end"]), ("2026-11-16", "2026-11-22"))
        self.assertEqual(result["totals"]["paused"], 2)

    def test_expired_pause_display_does_not_resume_or_write(self):
        queue = self._queue(status="paused")
        queue.pause_until_local_date = NOW.date()
        self._event(queue, "paused")
        db.session.commit()
        statements = []

        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)

        event.listen(db.engine, "before_cursor_execute", capture)
        try:
            result = reporting.weekly_report(self.users["teacher"], now=NOW)
            reporting.assignment_load(
                self.users["teacher"], profile_id=self.profiles["student"].id, now=NOW
            )
        finally:
            event.remove(db.engine, "before_cursor_execute", capture)
        self.assertEqual(result["words"][0]["events"][0]["status_label"], "暂停期已到，可复测")
        self.assertTrue(all(s.lstrip().upper().startswith("SELECT") for s in statements))
        self.assertEqual(queue.status, "paused")
        self.assertFalse(db.session.dirty)

    def test_overload_warning_uses_actual_queue_without_mutating(self):
        for number in range(25):
            sense = VocabularySense(canonical_key=f"overload-{number}", lemma=f"word{number}")
            db.session.add(sense)
            db.session.flush()
            self._queue(sense=sense)
        db.session.commit()
        result = reporting.assignment_load(
            self.users["teacher"], student_name="合成student", now=NOW
        )
        self.assertTrue(result["student"]["overloaded"])
        self.assertEqual(result["student"]["overload_count"], 5)
        self.assertEqual(result["student"]["required_count"], 20)
        self.assertFalse(db.session.dirty)

    def test_event_queue_owner_mismatch_never_leaks(self):
        queue = self._queue("unrelated", status="paused")
        self._event(queue, "paused", student_id=self.users["student"].id)
        db.session.commit()
        result = reporting.weekly_report(self.users["teacher"], now=NOW)
        self.assertEqual(result["words"], [])

    def test_disabled_mode_does_not_query_or_need_pilot_tables(self):
        self.app.config["VOCABULARY_ERROR_REVIEW_ENABLED"] = False
        # Load auth before inspecting SQL; ordinary authentication remains necessary.
        teacher = self.users["teacher"]
        self.assertEqual(teacher.role, "teacher")
        statements = []

        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)

        event.listen(db.engine, "before_cursor_execute", capture)
        try:
            self.assertFalse(reporting.weekly_report(teacher, now=NOW)["enabled"])
            self.assertEqual(
                reporting.assignment_load(teacher, now=NOW), {"enabled": False, "student": None}
            )
        finally:
            event.remove(db.engine, "before_cursor_execute", capture)
        self.assertEqual(statements, [])
        VocabularyPolicyEvent.__table__.drop(db.engine)
        self._login("teacher")
        response = self.client.get("/api/teacher/vocabulary-review/weekly")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json["enabled"])

    def test_http_web_and_bearer_deny_nonstaff_and_inactive(self):
        for name in ("student", "parent", "inactive", "planner"):
            with self.subTest(name=name):
                self._login(name)
                self.assertEqual(
                    self.client.get("/api/teacher/vocabulary-review/weekly").status_code,
                    401 if name == "inactive" else 403,
                )
                self.assertEqual(
                    self.client.get("/teacher/vocabulary-review").status_code,
                    302 if name == "inactive" else 403,
                )
                self.assertEqual(
                    self.client.get(
                        "/api/miniprogram/teacher/vocabulary-review/weekly",
                        headers=self._bearer(name),
                    ).status_code,
                    403,
                )
        self._login(None)
        self.assertEqual(self.client.get("/api/teacher/vocabulary-review/weekly").status_code, 401)
        self.assertEqual(
            self.client.get("/api/miniprogram/teacher/vocabulary-review/weekly").status_code, 401
        )
        self.assertEqual(self.client.get("/teacher/vocabulary-review").status_code, 302)

    def test_http_cross_teacher_requests_return_only_generic_error(self):
        self._login("other_teacher")
        for prefix, headers in (
            ("/api/teacher", {}),
            ("/api/miniprogram/teacher", self._bearer("other_teacher")),
        ):
            for suffix in ("weekly", "assignment-load"):
                with self.subTest(prefix=prefix, suffix=suffix):
                    response = self.client.get(
                        f"{prefix}/vocabulary-review/{suffix}",
                        query_string={"profile_id": self.profiles["student"].id},
                        headers=headers,
                    )
                    self.assertEqual(response.status_code, 404)
                    self.assertEqual(response.json, {"ok": False, "error": "student_unavailable"})

    def test_http_staff_access_and_read_only_methods(self):
        for name in ("teacher", "assistant", "admin"):
            self._login(name)
            self.assertEqual(
                self.client.get("/api/teacher/vocabulary-review/weekly").status_code, 200
            )
            self.assertEqual(
                self.client.get(
                    "/api/miniprogram/teacher/vocabulary-review/weekly",
                    headers=self._bearer(name),
                ).status_code,
                200,
            )
        for rule in self.app.url_map.iter_rules():
            if rule.endpoint.startswith("vocabulary_error_reports."):
                self.assertEqual(rule.methods, {"GET", "HEAD", "OPTIONS"})

    def test_bad_filters_are_rejected_without_tracebacks(self):
        self._login("teacher")
        for url in (
            "weekly?week=bad-date",
            "weekly?profile_id=-1",
            "assignment-load?profile_id=nan",
            "assignment-load",
        ):
            with self.subTest(url=url):
                response = self.client.get("/api/teacher/vocabulary-review/" + url)
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.json["ok"])

    def test_html_escapes_identity_and_word_fields(self):
        self.profiles["student"].full_name = "<script>synthetic()</script>"
        self.sense.lemma = "<img src=x onerror=synthetic()>"
        self._event(self._queue(status="paused"), "paused")
        db.session.commit()
        self._login("teacher")
        with patch.object(reporting, "datetime") as clock:
            clock.utcnow.return_value = NOW
            response = self.client.get("/teacher/vocabulary-review")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("&lt;script&gt;synthetic()&lt;/script&gt;", html)
        self.assertIn("&lt;img src=x onerror=synthetic()&gt;", html)
        self.assertNotIn("<script>synthetic()", html)

    def test_checkpoint_material_failure_is_reported_without_queue_and_scoped(self):
        for name in ("student", "unrelated"):
            checkpoint = VocabularyPolicyCheckpoint(
                student_id=self.users[name].id,
                sense_id=self.sense.id,
                dimension="form_recall",
                cohort_key="synthetic",
                anchor_at=START,
                due_local_date=NOW.date(),
                interval_days=7,
                status="missed",
            )
            db.session.add(checkpoint)
            db.session.flush()
            db.session.add(
                VocabularyPolicyEvent(
                    student_id=self.users["student"].id,
                    checkpoint_id=checkpoint.id,
                    source_key=f"synthetic-checkpoint-{name}",
                    kind="unanswerable",
                    source="system",
                    occurred_at=NOW,
                    local_date=NOW.date(),
                )
            )
        db.session.commit()
        result = reporting.weekly_report(self.users["teacher"], now=NOW)
        self.assertEqual(result["totals"]["unanswerable"], 1)
        event_row = result["words"][0]["events"][0]
        self.assertEqual(event_row["dimension"], "form_recall")
        self.assertIn("抽查", event_row["status_label"])
        self.assertIsNone(event_row["resume_date"])

    def test_teacher_pause_explanation_uses_current_policy_setting(self):
        self.app.config["VOCABULARY_ERROR_REVIEW_PAUSE_DAYS"] = 4
        self._login("teacher")
        response = self.client.get("/teacher/vocabulary-review")
        self.assertEqual(response.status_code, 200)
        self.assertIn("4天暂停期", response.get_data(as_text=True))
        self.assertNotIn("7天暂停期", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
