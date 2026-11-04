"""Local-only real-app acceptance fixture; no production data/config/network.

Run with ``python -m tests.recovery_e2e_support --serve`` for a disposable
loopback browser sandbox. The /__e2e controls exist only in this test module.
Business routes, templates, database writes, grading and scheduler are real.
Only the clock, resource directory, configuration and external I/O are replaced.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import secrets
import socket
import sys
import tempfile
import types
import uuid
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from flask import jsonify, request

from models import (
    PlanItem,
    PracticeSubmissionAttempt,
    ReadingTestSubmission,
    ScoreRecord,
    StudentProfile,
    Task,
    User,
    db,
)
from services import task_date_gate, task_planner

ROOT = Path(__file__).resolve().parents[1]
DAY_ONE = datetime(2026, 11, 1, 10, 0, tzinfo=task_date_gate.SHANGHAI)


class RecoverySandbox:
    def __init__(self):
        self.stack = ExitStack()
        self.directory = tempfile.TemporaryDirectory(prefix="recovery-e2e-")
        self.stack.callback(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.now = DAY_ONE
        self.outbound_attempts = []
        original_connect = socket.socket.connect

        def guard_connect(sock, address):
            if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
                return original_connect(sock, address)
            self.outbound_attempts.append(str(address))
            raise AssertionError("Acceptance fixture forbids external network")

        self.stack.enter_context(patch("socket.socket.connect", guard_connect))
        self.stack.enter_context(
            patch(
                "requests.sessions.Session.request",
                side_effect=AssertionError("No external requests"),
            )
        )
        config = types.ModuleType("config")
        config.Config = type(
            "RecoveryE2EConfig",
            (),
            {
                "TESTING": True,
                "SECRET_KEY": secrets.token_urlsafe(32),
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.root}/synthetic.db",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "UPLOAD_FOLDER": str(self.root / "uploads"),
                "TASK_PLANNER_ROOT": str(self.root),
            },
        )
        module_name = "_recovery_e2e_app_" + uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(module_name, ROOT / "app.py")
        self.module = importlib.util.module_from_spec(spec)
        self.stack.callback(sys.modules.pop, module_name, None)
        sys.modules[module_name] = self.module
        original_config = sys.modules.get("config")
        sys.modules["config"] = config
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
        normal_clock = task_date_gate._local_now
        self.stack.enter_context(
            patch.object(
                task_date_gate,
                "_local_now",
                lambda value=None: normal_clock(value if value is not None else self.now),
            )
        )
        sandbox = self

        class Clock(datetime):
            @classmethod
            def utcnow(cls):
                return sandbox.now.astimezone(task_date_gate.UTC).replace(tzinfo=None)

            @classmethod
            def now(cls, tz=None):
                return sandbox.now.astimezone(tz) if tz else cls.utcnow()

        self.stack.enter_context(patch.object(self.module, "datetime", Clock))
        self.reading_root = self.root / "static/reading_tests"
        self.reading_root.mkdir(parents=True)
        for folder in ("reading_jijing", "listening_tests", "listening"):
            (self.root / "static" / folder).mkdir(parents=True)
        self.stack.enter_context(
            patch.object(self.module, "_reading_test_root", lambda: self.reading_root)
        )
        self.stack.enter_context(
            patch.object(
                self.module, "_reading_jijing_root", lambda: self.root / "static/reading_jijing"
            )
        )
        self.stack.enter_context(
            patch.object(
                self.module,
                "send_subscribe_message",
                side_effect=AssertionError("No notifications"),
            )
        )
        for number in range(1, 7):
            test_id = f"ielts10_test{number}_reading"
            passages = []
            for p, start, end in ((1, 1, 13), (2, 14, 26), (3, 27, 40)):
                passages.append(
                    {
                        "passage": p,
                        "title": f"Synthetic Passage {p}",
                        "content": {
                            "paragraphs": [
                                {
                                    "text": "This is a synthetic reading passage. Every statement below is true."
                                }
                            ]
                        },
                        "groups": [
                            {
                                "group_id": f"g{p}",
                                "type": 1,
                                "desc": "TRUE FALSE NOT GIVEN",
                                "questions": [
                                    {
                                        "id": str(q),
                                        "number": q,
                                        "title": f"Synthetic statement {q}.",
                                        "answer": "TRUE",
                                        "options": [
                                            {"key": k, "text": k}
                                            for k in ("TRUE", "FALSE", "NOT GIVEN")
                                        ],
                                    }
                                    for q in range(start, end + 1)
                                ],
                            }
                        ],
                    }
                )
            (self.reading_root / f"{test_id}.json").write_text(
                json.dumps(
                    {
                        "id": test_id,
                        "title": f"Synthetic Cambridge 10 Test {number}",
                        "passages": passages,
                    }
                ),
                encoding="utf-8",
            )
        self.password = secrets.token_urlsafe(20)
        with self.app.app_context():
            assert db.engine.url.database == str(self.root / "synthetic.db")
            db.create_all()
            self.users = {}
            for role in ("assistant", "student", "other"):
                user = User(
                    username=f"e2e-{role}",
                    display_name=f"合成验收{role}",
                    role="student" if role == "other" else role,
                )
                user.set_password(self.password)
                db.session.add(user)
                db.session.flush()
                self.users[role] = user.id
            profile = StudentProfile(full_name="合成验收学生", user_id=self.users["student"])
            other = StudentProfile(full_name="合成隔离学生", user_id=self.users["other"])
            db.session.add_all([profile, other])
            db.session.commit()
            self.student_id, self.other_id = profile.id, other.id
        self.install_browser_controls()
        self.clients = {role: self.app.test_client() for role in self.users}
        for role, client in self.clients.items():
            response = client.post(
                "/login", data={"username": f"e2e-{role}", "password": self.password}
            )
            assert response.status_code == 302
        self.csrf = (
            self.clients["assistant"].get("/api/task-planner/bootstrap").get_json()["csrf_token"]
        )

    def close(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.stack.close()

    def set_time(self, value):
        self.now = datetime.fromisoformat(value) if isinstance(value, str) else value
        assert self.now.tzinfo is not None

    def staff(self, path, data, expected=200):
        response = self.clients["assistant"].post(
            path, json=data, headers={"X-CSRF-Token": self.csrf}
        )
        assert response.status_code == expected, (path, response.status_code, response.get_json())
        return response.get_json()

    def create_line(
        self,
        *,
        kind="reading_passage",
        days=3,
        passage=1,
        wait=True,
        start_test=1,
        student_id=None,
        name="合成阅读学习线",
    ):
        start = self.now.date()
        data = {
            "name": name,
            "kind": kind,
            "student_id": student_id or self.student_id,
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=days - 1)).isoformat(),
            "weekday_counts": [1] * 7,
            "selection": {} if kind == "reading_test" else {"passage_number": passage},
            "source_scopes": ["cambridge:10"],
            "start_resource_id": f"ielts10_test{start_test}_reading:{'all' if kind == 'reading_test' else passage}",
            "planned_minutes": 20,
            "wait_for_previous": wait,
            "skip_assigned": True,
            "request_key": str(uuid.uuid4()),
        }
        data["preview_hash"] = self.staff("/api/task-planner/series/preview", data)["preview"][
            "preview_hash"
        ]
        line = self.staff("/api/task-planner/series", data, 201)["series"]
        line = self.staff(
            f"/api/task-planner/series/{line['id']}/confirm", {"version": line["version"]}
        )["series"]
        self.staff(
            f"/api/task-planner/students/{student_id or self.student_id}/enable", {"enabled": True}
        )
        entries = self.entries(line["id"])
        self.staff(
            f"/api/task-planner/entries/{entries[0]['id']}/publish",
            {"version": entries[0]["version"]},
        )
        return line["id"], self.entries(line["id"])

    def entries(self, line_id):
        response = self.clients["assistant"].get(f"/api/task-planner/series/{line_id}")
        assert response.status_code == 200
        return response.get_json()["entries"]

    def inbox(self):
        response = self.clients["assistant"].get("/api/task-planner/inbox")
        assert response.status_code == 200
        return response.get_json()["items"]

    def recover(self, line_id, source_date, action="makeup"):
        data = {"series_id": line_id, "source_date": source_date, "action": action}
        preview = self.staff("/api/task-planner/inbox/preview", data)["preview"]
        assert preview["can_apply"], preview
        data.update(preview_hash=preview["preview_hash"], request_key=str(uuid.uuid4()))
        return preview, self.staff("/api/task-planner/inbox/apply", data)["result"]

    def tasks(self, role="student"):
        response = self.clients[role].get("/api/practice/tasks")
        assert response.status_code == 200, response.get_json()
        return [row for rows in response.get_json()["groups"].values() for row in rows]

    def task_link(self, task_id, role="student"):
        row = next(task for task in self.tasks(role) if task["id"] == task_id)
        url = urlsplit(row["url"])
        return row, url, parse_qs(url.query)

    def submit(self, task_id, *, correct=True, role="student", expected=200):
        row, url, args = self.task_link(task_id, role)
        client = self.clients[role]
        page = client.get(url.path + "?" + url.query)
        assert page.status_code == 200, (page.status_code, page.location)
        api = "/api" + url.path
        state = client.get(api + "/submission?" + url.query)
        assert state.status_code == 200, state.get_json()
        payload = {
            "task_id": task_id,
            "token": args["token"][0],
            "passage_number": int(args["passage"][0]),
            "answers": {str(q): "TRUE" if correct else "FALSE" for q in range(1, 41)},
            "duration_seconds": 900,
        }
        response = client.post(api + "/submit", json=payload)
        assert response.status_code == expected, response.get_json()
        return response.get_json()

    def run_due(self):
        with self.app.app_context():
            return task_planner.run_due()

    def original_snapshot(self, task_ids):
        with self.app.app_context():
            result = {}
            for model in (Task, ReadingTestSubmission, PracticeSubmissionAttempt):
                query = (
                    model.query.filter(model.id.in_(task_ids))
                    if model is Task
                    else model.query.filter(model.task_id.in_(task_ids))
                )
                result[model.__tablename__] = [
                    tuple(str(getattr(row, column.name)) for column in model.__table__.columns)
                    for row in query.order_by(model.id)
                ]
            plan_item_ids = [
                task.plan_item_id
                for task in Task.query.filter(Task.id.in_(task_ids))
                if task.plan_item_id
            ]
            result["plan_item"] = [
                tuple(str(getattr(row, column.name)) for column in PlanItem.__table__.columns)
                for row in PlanItem.query.filter(PlanItem.id.in_(plan_item_ids)).order_by(
                    PlanItem.id
                )
            ]
            result["score_record"] = [
                tuple(str(getattr(row, column.name)) for column in ScoreRecord.__table__.columns)
                for row in ScoreRecord.query.order_by(ScoreRecord.id)
                if any(f"（任务 #{task_id}）" in row.assessment_name for task_id in task_ids)
            ]
            return result

    def install_browser_controls(self):
        @self.app.get("/__e2e")
        def control():
            forms = "".join(
                f'<form method="post" action="/login"><input type="hidden" name="username" value="e2e-{role}"><input type="hidden" name="password" value="{self.password}"><input type="hidden" name="next" value="{target}"><button>登录合成{label}</button></form>'
                for role, target, label in (
                    ("assistant", "/task-planner", "助教"),
                    ("student", "/practices", "学生"),
                )
            )
            return f'<meta charset="utf-8"><h1>隔离验收控制台</h1><p>仅合成数据；北京时间 {self.now.isoformat()}</p>{forms}<a href="/__e2e/state">状态</a>'

        @self.app.post("/__e2e/time")
        def clock():
            self.set_time(request.get_json()["now"])
            return jsonify(now=self.now.isoformat())

        @self.app.post("/__e2e/run")
        def run():
            return jsonify(self.run_due())

        @self.app.get("/__e2e/state")
        def state():
            with self.app.app_context():
                return jsonify(
                    now=self.now.isoformat(),
                    tasks=[
                        {
                            "id": t.id,
                            "date": t.date,
                            "status": t.status,
                            "passage": t.reading_passage_number,
                            "test_id": t.reading_test_id,
                        }
                        for t in Task.query.order_by(Task.id)
                    ],
                )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    sandbox = RecoverySandbox()
    try:
        line_id, _ = sandbox.create_line()
        sandbox.set_time("2026-11-02T10:00:00+08:00")
        if args.serve:
            print(
                json.dumps(
                    {
                        "url": "http://127.0.0.1:5098/__e2e",
                        "line_id": line_id,
                        "synthetic_only": True,
                    }
                ),
                flush=True,
            )
            sandbox.app.run(host="127.0.0.1", port=5098, use_reloader=False, threaded=False)
        else:
            print(
                json.dumps(
                    {"inbox": sandbox.inbox(), "entries": sandbox.entries(line_id)},
                    ensure_ascii=False,
                )
            )
    finally:
        sandbox.close()


if __name__ == "__main__":
    main()
