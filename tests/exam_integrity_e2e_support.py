"""Disposable real-app exam fixture. No production configuration, data or network."""

from __future__ import annotations

import argparse
import importlib.util
import secrets
import sys
import tempfile
import types
import uuid
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from flask import jsonify, redirect, request
from flask_login import login_user

from models import MockExam, MockExamSession, StudentProfile, User, db

ROOT = Path(__file__).resolve().parents[1]


def exam_payload(kind):
    if kind == "writing":
        return {
            "id": "synthetic-writing",
            "title": "Synthetic writing",
            "tasks": [
                {
                    "task": n,
                    "kind_name": "Practice",
                    "min_words": 20,
                    "prompt": "Write about learning in a quiet room.",
                }
                for n in (1, 2)
            ],
        }
    question = {
        "id": "1",
        "number": 1,
        "title": "A quiet room helps students.",
        "answer": "TRUE",
        "options": [
            {"key": key, "text": key, "title": key, "content": key}
            for key in ("TRUE", "FALSE", "NOT GIVEN")
        ],
    }
    item = {
        "id": "synthetic-" + kind + "-part1",
        "passage": 1,
        "section": 1,
        "title": "Synthetic passage",
        "audio": "../../__integrity_fixture/audio.wav",
        "content": {
            "title": "A place to study",
            "paragraphs": [
                {"label": "A", "text": "A quiet room helps students focus on learning."}
            ],
        },
        "groups": [
            {"group_id": "g1", "type": 1, "desc": "TRUE FALSE NOT GIVEN", "questions": [question]}
        ],
    }
    return {
        "id": "synthetic-" + kind,
        "title": "Synthetic " + kind,
        "audio": "/__integrity_fixture/audio.wav",
        "passages" if kind == "reading" else "sections": [item],
    }


class IntegritySandbox:
    def __init__(self, create_integrity=True):
        self.stack = ExitStack()
        self.directory = self.stack.enter_context(
            tempfile.TemporaryDirectory(prefix="integrity-e2e-")
        )
        self.root = Path(self.directory)
        self.stack.enter_context(
            patch(
                "requests.sessions.Session.request",
                side_effect=AssertionError("No external network"),
            )
        )
        config = types.ModuleType("config")
        config.Config = type(
            "IntegrityFixtureConfig",
            (),
            {
                "TESTING": True,
                "SECRET_KEY": secrets.token_hex(32),
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.root}/synthetic.db",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "UPLOAD_FOLDER": str(self.root / "uploads"),
            },
        )
        name = "_integrity_fixture_" + uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(name, ROOT / "app.py")
        self.module = importlib.util.module_from_spec(spec)
        original_config = sys.modules.get("config")
        sys.modules["config"] = config
        sys.modules[name] = self.module
        self.stack.callback(sys.modules.pop, name, None)
        try:
            spec.loader.exec_module(self.module)
        finally:
            if original_config is None:
                sys.modules.pop("config", None)
            else:
                sys.modules["config"] = original_config
        self.app = self.module.app
        self.app.template_folder = str(ROOT / "templates")
        self.app.static_folder = str(ROOT / "static")
        for kind in ("listening", "reading", "writing"):
            self.stack.enter_context(
                patch.object(
                    self.module,
                    f"_load_{kind}_test_payload",
                    lambda _id, kind=kind: (exam_payload(kind), None, "synthetic-" + kind),
                )
            )
        for module in ("api.mock_exam_student", "api.mock_exam_review"):
            self.stack.enter_context(
                patch(module + "._load_payload", side_effect=lambda kind, _id: exam_payload(kind))
            )
        with self.app.app_context():
            tables = [
                table
                for table in db.metadata.sorted_tables
                if create_integrity or not table.name.startswith("exam_integrity_")
            ]
            db.metadata.create_all(db.engine, tables=tables)
            self.teacher = User(
                username="integrity-fixture-teacher", role="admin", password_hash="unused"
            )
            db.session.add(self.teacher)
            db.session.add(StudentProfile(full_name="Synthetic Student"))
            exam = MockExam(
                name="Synthetic Integrity Exam",
                pincode="TEST1",
                listening_test_id="synthetic-listening",
                reading_test_id="synthetic-reading",
                writing_test_id="synthetic-writing",
                listening_minutes=30,
                reading_minutes=60,
                writing_minutes=60,
            )
            db.session.add(exam)
            db.session.commit()
            self.exam_id, self.teacher_id = exam.id, self.teacher.id
        self.client = self.app.test_client()

    def close(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.stack.close()

    def login(self):
        result = self.client.post(
            f"/api/exam/{self.exam_id}/start",
            json={"name": "Synthetic Student", "pincode": "TEST1"},
        )
        assert result.status_code == 200, result.data
        self.process_url = result.get_json()["session_url"]
        self.token = self.process_url.rsplit("/", 1)[1]
        self.api_url = f"/api/exam/{self.exam_id}/session/{self.token}"
        with self.app.app_context():
            self.session_id = MockExamSession.query.filter_by(access_token=self.token).one().id
        return self.process_url

    def expire(self, section, seconds=-1):
        with self.app.app_context():
            row = db.session.get(MockExamSession, self.session_id)
            setattr(row, section + "_deadline_at", datetime.utcnow() + timedelta(seconds=seconds))
            db.session.commit()

    def serve(self, port):
        # Fixture controls are registered here only; never imported by product code.
        @self.app.get("/__integrity_fixture/new/<mode>")
        def new_exam(mode):
            from services import exam_integrity

            assert mode in {"off", "monitor", "enforce"}
            exam = MockExam(
                name="Synthetic " + mode + " Exam",
                pincode="TEST1",
                listening_test_id="synthetic-listening",
                reading_test_id="synthetic-reading",
                writing_test_id="synthetic-writing",
                listening_minutes=30,
                reading_minutes=60,
                writing_minutes=60,
            )
            db.session.add(exam)
            db.session.commit()
            exam_integrity.set_policy(exam.id, mode)
            return redirect(f"/exam/{exam.id}")

        @self.app.get("/__integrity_fixture/teacher")
        def teacher_login():
            login_user(db.session.get(User, self.teacher_id))
            exam_id = int(request.args.get("exam_id", self.exam_id))
            return redirect(f"/admin/mock-exams/{exam_id}/integrity/")

        @self.app.get("/__integrity_fixture/controls")
        def controls():
            rows = MockExamSession.query.all()
            return "<h1>仅本机合成试考控制</h1>" + "".join(
                f"<p>Exam {row.exam_id} {row.current_section} "
                f'<a href="/__integrity_fixture/expire-now/{row.id}">缩短剩余时间到 3 秒</a></p>'
                for row in rows
            )

        @self.app.get("/__integrity_fixture/expire-now/<int:session_id>")
        def expire_now(session_id):
            row = db.session.get(MockExamSession, session_id)
            setattr(
                row, row.current_section + "_deadline_at", datetime.utcnow() + timedelta(seconds=3)
            )
            db.session.commit()
            return "Deadline changed. Reload the test paper to use this synthetic deadline."

        @self.app.post("/__integrity_fixture/expire")
        def expire_section():
            data = request.get_json()
            row = MockExamSession.query.filter_by(access_token=data["token"]).one()
            section = row.current_section
            setattr(
                row,
                section + "_deadline_at",
                datetime.utcnow() + timedelta(seconds=data.get("seconds", 3)),
            )
            db.session.commit()
            return jsonify(ok=True)

        @self.app.post("/__integrity_fixture/drop-integrity-tables")
        def drop_integrity_tables():
            # Destructive control exists only in this disposable loopback fixture.
            from sqlalchemy import inspect

            names = ("exam_integrity_event", "exam_integrity_state", "exam_integrity_policy")
            db.session.remove()
            for name in names:
                db.metadata.tables[name].drop(bind=db.engine, checkfirst=True)
            remaining = inspect(db.engine).get_table_names()
            return jsonify(
                ok=True,
                removed=list(names),
                integrity_tables_remaining=[name for name in names if name in remaining],
                legacy_session_table_present="mock_exam_session" in remaining,
                legacy_session_count=MockExamSession.query.count(),
            )

        @self.app.get("/__integrity_fixture/audio.wav")
        def fixture_audio():
            import io
            import wave

            stream = io.BytesIO()
            with wave.open(stream, "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(8000)
                audio.writeframes(b"\x00\x00" * 8000 * 5)
            return self.app.response_class(stream.getvalue(), mimetype="audio/wav")

        print(f"Fixture: http://127.0.0.1:{port}/exam/{self.exam_id}", flush=True)
        self.app.run(host="127.0.0.1", port=port, use_reloader=False, threaded=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5097)
    args = parser.parse_args()
    sandbox = IntegritySandbox()
    try:
        sandbox.serve(args.port)
    finally:
        sandbox.close()
