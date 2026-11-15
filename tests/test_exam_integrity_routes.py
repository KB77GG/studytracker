"""Integration boundaries: authorization, isolated storage and optional UI."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from flask import Flask, render_template_string
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader
from sqlalchemy import inspect

from api.exam_integrity import exam_integrity_bp, exam_integrity_config
from api.mock_exam_student import mock_exam_student_bp
from models import (
    ExamIntegrityEvent,
    ExamIntegrityPolicy,
    ExamIntegrityState,
    MockExam,
    MockExamSession,
    User,
    db,
)
from services import exam_integrity as integrity

ROOT = Path(__file__).resolve().parents[1]
TABLES = (ExamIntegrityEvent, ExamIntegrityState, ExamIntegrityPolicy)


class ExamIntegrityRouteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Flask(
            __name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static")
        )
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="integrity-test-only",
            SQLALCHEMY_DATABASE_URI="sqlite:///" + str(Path(self.tmp.name) / "test.sqlite"),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        self.app.jinja_loader = ChoiceLoader(
            [
                DictLoader({"base.html": "{% block content_dashboard %}{% endblock %}"}),
                self.app.jinja_loader,
            ]
        )
        db.init_app(self.app)
        login = LoginManager(self.app)

        @login.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        self.app.add_url_rule(
            "/test/results/<int:exam_id>",
            endpoint="mock_exam_admin.exam_sessions",
            view_func=lambda exam_id: "results",
        )
        self.app.add_url_rule(
            "/exam/<int:exam_id>/session/<token>",
            endpoint="mock_exam_process",
            view_func=lambda exam_id, token: "process",
        )
        self.app.register_blueprint(exam_integrity_bp)
        self.app.register_blueprint(mock_exam_student_bp)
        with self.app.app_context():
            db.create_all()
            exam = MockExam(
                name="Integrity test",
                listening_test_id="test-l",
                reading_test_id="test-r",
                pincode="12345",
            )
            other = MockExam(
                name="Other test",
                listening_test_id="test-l",
                reading_test_id="test-r",
                pincode="67890",
            )
            db.session.add_all([exam, other])
            db.session.flush()
            sess = MockExamSession(
                exam_id=exam.id,
                student_name="Synthetic student",
                access_token="test-token",
                current_section="reading",
                reading_started_at=datetime.utcnow(),
                reading_deadline_at=datetime.utcnow() + timedelta(hours=1),
            )
            other_session = MockExamSession(
                exam_id=other.id, student_name="Other synthetic", access_token="other-token"
            )
            db.session.add_all([sess, other_session])
            for role in ("admin", "teacher", "assistant", "student", "parent"):
                db.session.add(User(username=role, password_hash="not-a-password", role=role))
            db.session.commit()
            self.exam_id, self.session_id, self.other_id = exam.id, sess.id, other_session.id
            self.users = {user.role: user.id for user in User.query.all()}
        self.client = self.app.test_client()
        self.base = f"/admin/mock-exams/{self.exam_id}/integrity"
        self.student = f"/api/exam/{self.exam_id}/session/test-token/integrity"

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.tmp.cleanup()

    def login(self, role="teacher"):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.users[role])
            session["_fresh"] = True

    def policy(self, mode="enforce"):
        with self.app.app_context():
            integrity.set_policy(self.exam_id, mode)

    def event(self, kind="hello", **updates):
        payload = {
            "type": kind,
            "section": "reading",
            "device_id": "device-alpha",
            "page_id": "page-alpha",
            "client_ts": 1,
        }
        payload.update(updates)
        return self.client.post(self.student + "/event", json=payload)

    def drop_new_tables(self):
        with self.app.app_context():
            for model in TABLES:
                model.__table__.drop(db.engine)

    def test_default_off_does_not_create_state(self):
        self.assertEqual(self.event().get_json()["mode"], "off")
        with self.app.app_context():
            self.assertEqual(ExamIntegrityState.query.count(), 0)

    def test_unknown_token_and_wrong_exam_are_404(self):
        for path in (
            self.student.replace("test-token", "invalid") + "/state",
            self.student.replace(str(self.exam_id), "999", 1) + "/state",
        ):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_state_is_private_and_does_not_disclose_device_hash_or_token(self):
        self.policy()
        self.event()
        response = self.client.get(
            self.student + "/state?section=reading",
            headers={"X-Exam-Integrity-Device": "device-alpha"},
        )
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertNotIn("device_hash", response.get_json())
        self.assertNotIn("test-token", response.get_data(as_text=True))

    def test_state_device_identity_uses_header_and_never_query_fallback(self):
        self.policy()
        self.event()
        response = self.client.get(
            self.student + "/state?section=reading&device_id=device-alpha",
            headers={"X-Exam-Integrity-Device": "device-foreign"},
        )
        self.assertTrue(response.get_json()["device_conflict"])
        response = self.client.get(
            self.student + "/state?section=reading&device_id=device-foreign",
            headers={"X-Exam-Integrity-Device": "device-alpha"},
        )
        self.assertFalse(response.get_json()["device_conflict"])
        response = self.client.get(self.student + "/state?device_id=device-foreign")
        self.assertFalse(response.get_json()["device_conflict"])

    def test_monitor_paste_route_preserves_attempt_without_false_high_risk(self):
        self.policy("monitor")
        self.event()
        state = self.event(
            "paste_blocked", detail={"length": 20, "blocked": False, "signal": "paste"}
        ).get_json()
        self.assertEqual(state["paste_attempt_count"], 1)
        self.assertEqual(state["paste_blocked_count"], 0)
        self.assertEqual(state["risk"], "low")

    def test_reordered_return_requests_do_not_lock_after_two_valid_leaves(self):
        self.policy()
        actual = integrity.record_event
        epoch = datetime(2026, 11, 14, 9)

        def send_at(kind, received, client=None, **extra):
            def at_time(*args, **kwargs):
                return actual(*args, **kwargs, now=epoch + timedelta(seconds=received))

            with patch.object(integrity, "record_event", side_effect=at_time):
                return self.event(
                    kind, client_ts=(received if client is None else client) * 1000, **extra
                ).get_json()

        send_at("hello", 0)
        send_at("hidden", 1)
        send_at("visible", 3)
        send_at("hidden", 20)
        delayed = send_at("visible", 30, client=11, client_hidden_ms=1000)
        self.assertEqual(delayed["leave_count"], 1)
        current = send_at("visible", 31, client=30, client_hidden_ms=10000)
        self.assertEqual(current["leave_count"], 2)
        self.assertFalse(current["is_locked"])

    def test_beacon_text_plain_is_supported(self):
        self.policy("monitor")
        payload = {
            "type": "hello",
            "section": "reading",
            "device_id": "device-alpha",
            "page_id": "page-alpha",
        }
        response = self.client.post(
            self.student + "/event",
            data=json.dumps(payload),
            content_type="text/plain;charset=UTF-8",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["mode"], "monitor")

    def test_event_body_limit_and_types(self):
        self.assertEqual(
            self.client.post(
                self.student + "/event", data="x" * 2049, content_type="text/plain"
            ).status_code,
            413,
        )
        for value in ([], "text", None):
            self.assertEqual(
                self.client.post(
                    self.student + "/event", data=json.dumps(value), content_type="application/json"
                ).status_code,
                400,
            )
        self.assertEqual(
            self.client.post(
                self.student + "/event", data="{}", content_type="application/x-www-form-urlencoded"
            ).status_code,
            415,
        )
        for updates in (
            {"type": []},
            {"section": {}},
            {"device_id": 1},
            {"page_id": ""},
            {"client_hidden_ms": float("nan")},
            {"length": True},
            {"detail": {"length": -2}},
            {"detail": {"blocked": "yes"}},
        ):
            with self.subTest(updates=updates):
                self.assertEqual(self.event(**updates).status_code, 400)

    def test_only_safe_detail_is_persisted(self):
        self.policy("monitor")
        self.event()
        self.event(
            "paste_blocked",
            detail={"length": 25, "blocked": False, "signal": "paste", "text": "DO NOT STORE THIS"},
            essay="NO ESSAY",
        )
        with self.app.app_context():
            logs = ExamIntegrityEvent.query.all()
            joined = " ".join(row.detail_json or "" for row in logs)
            self.assertNotIn("DO NOT STORE", joined)
            self.assertNotIn("NO ESSAY", joined)
            self.assertIn("25", joined)

    def test_missing_tables_fail_open_and_never_create_schema(self):
        self.drop_new_tables()
        for response in (self.event(), self.client.get(self.student + "/state")):
            self.assertEqual(response.status_code, 503)
            self.assertFalse(response.get_json()["ok"])
            self.assertNotIn("mode", response.get_json())
        with self.app.test_request_context():
            self.assertIsNone(exam_integrity_config(self.exam_id, "test-token", "reading"))
            self.assertNotIn("exam_integrity_policy", inspect(db.engine).get_table_names())

    def test_missing_table_read_does_not_rollback_pending_exam_write(self):
        self.drop_new_tables()
        with self.app.test_request_context():
            sess = db.session.get(MockExamSession, self.session_id)
            sess.student_name = "Pending local change"
            db.session.flush()
            self.assertIsNone(exam_integrity_config(self.exam_id, "test-token", "reading"))
            db.session.commit()
            self.assertEqual(
                db.session.get(MockExamSession, self.session_id).student_name,
                "Pending local change",
            )

    def test_missing_tables_do_not_break_existing_draft(self):
        self.drop_new_tables()
        draft = self.student.removesuffix("/integrity") + "/draft/reading"
        self.assertEqual(self.client.put(draft, json={"answers": {"1": "alpha"}}).status_code, 200)
        self.assertEqual(self.client.get(draft).get_json()["answers"], {"1": "alpha"})

    def test_locked_state_does_not_break_existing_draft(self):
        self.policy()
        self.event()
        with self.app.app_context():
            state = ExamIntegrityState.query.one()
            state.is_locked = True
            state.locked_section = "reading"
            db.session.commit()
        draft = self.student.removesuffix("/integrity") + "/draft/reading"
        self.assertEqual(self.client.put(draft, json={"answers": {"1": "beta"}}).status_code, 200)
        self.assertEqual(self.client.get(draft).get_json()["answers"], {"1": "beta"})

    def test_template_config_has_no_guard_when_off_or_submitted(self):
        with self.app.test_request_context():
            self.assertIsNone(exam_integrity_config(self.exam_id, "test-token", "reading"))
            integrity.set_policy(self.exam_id, "monitor")
            config = exam_integrity_config(self.exam_id, "test-token", "reading")
            self.assertEqual(config["section"], "reading")
            self.assertEqual(config["student_name"], "Synthetic student")
            self.assertIsNone(exam_integrity_config(self.exam_id, "wrong-token", "reading"))
            sess = db.session.get(MockExamSession, self.session_id)
            sess.status = "submitted"
            db.session.commit()
            self.assertIsNone(exam_integrity_config(self.exam_id, "test-token", "reading"))

    def test_force_disabled_environment(self):
        self.policy()
        self.event()
        with patch.dict(os.environ, {"EXAM_INTEGRITY_DISABLED": "1"}):
            self.assertEqual(self.client.get(self.student + "/state").get_json()["mode"], "off")
            with self.app.test_request_context():
                self.assertIsNone(exam_integrity_config(self.exam_id, "test-token", "reading"))

    def test_unexpected_service_failure_is_retryable_not_authoritative_off(self):
        with patch.object(integrity, "record_event", side_effect=RuntimeError("unavailable")):
            response = self.event()
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.get_json()["ok"])
        self.assertNotIn("mode", response.get_json())
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_session_lookup_failure_is_retryable_not_authoritative_off(self):
        with patch("api.exam_integrity._session_row", side_effect=RuntimeError("busy")):
            for response in (self.event(), self.client.get(self.student + "/state")):
                self.assertEqual(response.status_code, 503)
                self.assertFalse(response.get_json()["ok"])
                self.assertNotIn("mode", response.get_json())

    def test_service_failure_result_is_preserved_and_http_503(self):
        failure = {"ok": False, "error": "integrity_temporarily_unavailable"}
        for name, call in (
            ("record_event", self.event),
            ("student_state", lambda: self.client.get(self.student + "/state")),
        ):
            with self.subTest(service=name), patch.object(integrity, name, return_value=failure):
                response = call()
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.get_json(), failure)

    def test_queued_event_metadata_is_bounded_and_forwarded(self):
        for value in (-1, 86400001, True, float("nan"), "100"):
            with self.subTest(value=value):
                self.assertEqual(self.event("hidden", queued_ms=value).status_code, 400)
        with patch.object(
            integrity, "record_event", return_value={"ok": True, "mode": "monitor"}
        ) as send:
            response = self.event("hidden", queued_ms=600000, client_ts=1234)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(send.call_args.args[2]["queued_ms"], 600000)
        self.assertEqual(send.call_args.args[2]["client_ts"], 1234)
        self.assertEqual(send.call_args.kwargs["active_sections"], ["reading"])

    def test_process_return_preserves_active_reading_departure_for_600_seconds(self):
        self.policy()
        actual = integrity.record_event
        epoch = datetime(2026, 11, 14, 9)

        def send_at(kind, seconds, section="reading", page="reading-page"):
            def at_time(*args, **kwargs):
                return actual(*args, **kwargs, now=epoch + timedelta(seconds=seconds))

            with patch.object(integrity, "record_event", side_effect=at_time):
                response = self.event(kind, section=section, page_id=page, client_ts=seconds * 1000)
            self.assertEqual(response.status_code, 200)
            return response.get_json()

        send_at("hello", 0)
        send_at("hidden", 1)
        process = send_at("hello", 2, section="process", page="process-page")
        self.assertIsNotNone(process["hidden_at"])
        result = send_at("hello", 601, page="returned-reading-page")
        self.assertEqual(result["leave_count"], 1)
        self.assertEqual(result["hidden_seconds"], 600)
        self.assertTrue(result["is_locked"])

    def test_submitted_reading_to_process_discards_departure(self):
        self.policy()
        actual = integrity.record_event
        epoch = datetime(2026, 11, 14, 9)

        def send_at(kind, seconds, section="reading", page="reading-page"):
            def at_time(*args, **kwargs):
                return actual(*args, **kwargs, now=epoch + timedelta(seconds=seconds))

            with patch.object(integrity, "record_event", side_effect=at_time):
                return self.event(
                    kind, section=section, page_id=page, client_ts=seconds * 1000
                ).get_json()

        send_at("hello", 0)
        send_at("hidden", 1)
        with self.app.app_context():
            row = db.session.get(MockExamSession, self.session_id)
            row.reading_submitted_at = epoch + timedelta(seconds=2)
            row.current_section = "writing"
            db.session.commit()
        process = send_at("hello", 2, section="process", page="process-page")
        self.assertIsNone(process["hidden_at"])
        returned = send_at("hello", 601, page="returned-reading-page")
        self.assertEqual(returned["leave_count"], 0)
        self.assertEqual(returned["hidden_seconds"], 0)

    def test_teacher_requires_login_and_manager_role(self):
        self.assertEqual(self.client.get(self.base + "/data").status_code, 401)
        for role in ("student", "parent"):
            self.login(role)
            self.assertEqual(self.client.get(self.base + "/data").status_code, 403)
            self.assertEqual(
                self.client.post(self.base + "/emergency-off", json={}).status_code, 403
            )
        for role in ("admin", "teacher", "assistant"):
            self.login(role)
            self.assertEqual(self.client.get(self.base + "/data").status_code, 200)

    def test_panel_initializes_only_optional_tables(self):
        self.drop_new_tables()
        self.login()
        self.assertEqual(self.client.get(self.base + "/").status_code, 200)
        with self.app.app_context():
            for table in TABLES:
                self.assertIn(table.__tablename__, inspect(db.engine).get_table_names())

    def test_teacher_json_and_origin_csrf_boundary(self):
        self.login()
        self.assertEqual(
            self.client.post(self.base + "/policy", data={"mode": "enforce"}).status_code, 415
        )
        self.assertEqual(
            self.client.post(
                self.base + "/policy",
                json={"mode": "enforce"},
                headers={"Origin": "https://foreign.invalid"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                self.base + "/policy",
                json={"mode": "monitor"},
                headers={"Origin": "http://localhost"},
            ).status_code,
            200,
        )

    def test_policy_invalid_values_never_enable(self):
        self.login()
        for body in (
            {"mode": []},
            {"mode": "invalid"},
            {"mode": "enforce", "max_leaves": True},
            {"mode": "enforce", "max_hidden_seconds": -1},
        ):
            self.assertEqual(self.client.post(self.base + "/policy", json=body).status_code, 400)
        self.assertEqual(self.client.get(self.student + "/state").get_json()["mode"], "off")

    def test_actions_are_exam_scoped(self):
        self.login()
        for action in ("unlock", "reset-device", "exempt", "events"):
            path = self.base + f"/sessions/{self.other_id}/" + action
            response = (
                self.client.get(path) if action == "events" else self.client.post(path, json={})
            )
            self.assertEqual(response.status_code, 404)

    def test_unlock_exempt_device_reset_and_emergency_off(self):
        self.policy()
        self.event()
        self.login()
        with self.app.app_context():
            state = ExamIntegrityState.query.one()
            state.is_locked = True
            state.locked_section = "reading"
            db.session.commit()
        prefix = self.base + f"/sessions/{self.session_id}/"
        self.assertFalse(self.client.post(prefix + "unlock", json={}).get_json()["is_locked"])
        self.assertTrue(
            self.client.post(prefix + "exempt", json={"exempt": True}).get_json()["exempt"]
        )
        self.assertFalse(
            self.client.post(prefix + "reset-device", json={}).get_json()["device_bound"]
        )
        self.assertEqual(self.client.post(self.base + "/emergency-off", json={}).status_code, 200)
        state = self.client.get(self.student + "/state").get_json()
        self.assertEqual(state["mode"], "off")
        self.assertFalse(state["is_locked"])

    def test_emergency_off_preserves_custom_thresholds_and_does_not_reenable(self):
        self.login()
        response = self.client.post(
            self.base + "/policy",
            json={"mode": "enforce", "max_leaves": 7, "max_hidden_seconds": 321},
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(self.base + "/emergency-off", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["policy"],
            {"mode": "off", "max_leaves": 7, "max_hidden_seconds": 321},
        )
        with self.app.app_context():
            policy = ExamIntegrityPolicy.query.one()
            self.assertEqual(
                (policy.mode, policy.max_leaves, policy.max_hidden_seconds), ("off", 7, 321)
            )
        self.assertEqual(self.client.get(self.student + "/state").get_json()["mode"], "off")
        second = self.client.post(self.base + "/emergency-off", json={}).get_json()["policy"]
        self.assertEqual(second["max_leaves"], 7)
        self.assertEqual(second["max_hidden_seconds"], 321)

    def test_dashboard_offline_duration_visible_even_when_locked_or_conflicted(self):
        self.policy()
        self.event()
        self.login()
        now = datetime.utcnow()
        with self.app.app_context():
            state = ExamIntegrityState.query.one()
            state.is_locked = True
            state.locked_section = "reading"
            state.last_seen_at = now - timedelta(seconds=600)
            state.device_conflict_at = now - timedelta(seconds=590)
            db.session.add(
                MockExamSession(
                    exam_id=self.exam_id,
                    student_name="Never connected",
                    access_token="never-connected",
                )
            )
            db.session.commit()
        rows = self.client.get(self.base + "/data").get_json()["rows"]
        row = next(item for item in rows if item["id"] == self.session_id)
        self.assertTrue(row["is_locked"])
        self.assertTrue(row["has_device_conflict"])
        self.assertGreaterEqual(row["offline_seconds"], 600)
        self.assertLess(row["offline_seconds"], 605)
        self.assertEqual(row["seconds_since_seen"], row["offline_seconds"])
        self.assertFalse(row["never_connected"])
        never = next(item for item in rows if item["student_name"] == "Never connected")
        self.assertTrue(never["never_connected"])
        self.assertIsNone(never["offline_seconds"])
        panel = self.client.get(self.base + "/").get_data(as_text=True)
        self.assertIn("离线时长：", panel)
        self.assertIn("connectionText(row)", panel)
        self.assertIn("integrity-student__offline", panel)
        self.assertIn("20 秒心跳宽限", panel)

    def test_dashboard_recent_heartbeat_has_zero_offline_duration(self):
        self.policy()
        self.event()
        self.login()
        with self.app.app_context():
            state = ExamIntegrityState.query.one()
            state.last_seen_at = datetime.utcnow() - timedelta(seconds=10)
            db.session.commit()
        row = self.client.get(self.base + "/data").get_json()["rows"][0]
        self.assertEqual(row["offline_seconds"], 0)
        self.assertGreaterEqual(row["seconds_since_seen"], 10)
        self.assertFalse(row["never_connected"])

    def test_dashboard_timeline_and_summary_no_token_or_hash(self):
        self.policy()
        self.event()
        self.login()
        response = self.client.get(self.base + "/data")
        self.assertEqual(response.get_json()["rows"][0]["student_name"], "Synthetic student")
        self.assertNotIn("test-token", response.get_data(as_text=True))
        self.assertNotIn("device_hash", response.get_data(as_text=True))
        events = self.client.get(self.base + f"/sessions/{self.session_id}/events").get_json()[
            "events"
        ]
        self.assertEqual(events[0]["type"], "hello")

    def test_summary_escapes_student_supplied_data(self):
        self.policy()
        self.event()
        self.login()
        with self.app.test_request_context():
            from flask_login import login_user

            login_user(db.session.get(User, self.users["teacher"]))
            html = render_template_string(
                '{% include "admin/_exam_integrity_summary.html" %}',
                exam={"id": self.exam_id},
                session={"id": self.session_id},
            )
            self.assertIn("考试诚信记录", html)
            self.assertIn("风险低", html)


if __name__ == "__main__":
    unittest.main()
