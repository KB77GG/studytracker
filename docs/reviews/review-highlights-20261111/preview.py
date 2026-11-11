"""Synthetic browser QA only: in-memory DB, real templates/routes, no app import."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from flask import jsonify, render_template, request  # noqa: E402

from api import mock_exam_student  # noqa: E402
from models import MockExamSession, StudentProfile, db  # noqa: E402
from services.ielts_exam_payload import build_simulation_payload  # noqa: E402
from services.ielts_practice_scoring import (  # noqa: E402
    grade_listening_test_answers,
    grade_reading_test_answers,
)
from tests.test_mock_exam_student_review import MockExamStudentReviewRouteTest  # noqa: E402

fixture = MockExamStudentReviewRouteTest()
fixture.setUp()
app = fixture.app
app.config["TEMPLATES_AUTO_RELOAD"] = True
payloads = {
    kind: json.loads(
        (ROOT / "static" / f"{kind}_tests" / f"ielts18_test1{suffix}.json").read_text()
    )
    for kind, suffix in [("listening", ""), ("reading", "_reading")]
}
graders = {"listening": grade_listening_test_answers, "reading": grade_reading_test_answers}
saved = {}
mock_exam_student._load_payload = lambda kind, _id: payloads.get(kind)

with app.app_context():
    row = MockExamSession.query.filter_by(access_token="student-session-token").one()
    profile = StudentProfile(full_name="合成复盘学生")
    db.session.add(profile)
    db.session.flush()
    row.student_profile_id = profile.id
    for kind, payload in payloads.items():
        questions = [
            q
            for unit in payload.get("sections", payload.get("passages", []))
            for group in unit.get("groups", [])
            for q in group.get("questions", [])
        ]
        answers = {
            str(questions[0]["id"]): "qa_wrong",
            str(questions[1]["id"]): str(questions[1].get("answer", "")).split("/")[0].strip(),
        }
        grade = graders[kind](payload, answers)
        setattr(row, f"{kind}_answers_json", json.dumps(answers))
        setattr(row, f"{kind}_results_json", json.dumps(grade["results"]))
        setattr(row, f"{kind}_total", grade["total"])
        setattr(row, f"{kind}_correct", grade["correct"])
        setattr(row, f"{kind}_accuracy", grade["accuracy"])
        setattr(row, f"{kind}_ielts_score", grade["ielts_score"])
    db.session.commit()


def catalog():
    return "Local synthetic highlight QA"


for path, endpoint in [
    ("/reading/tests", "reading_test_index"),
    ("/reading/jijing", "reading_jijing_index"),
    ("/listening/tests", "listening_test_index"),
]:
    if endpoint not in app.view_functions:
        app.add_url_rule(path, endpoint, catalog)


@app.get("/preview/<kind>")
def ordinary(kind):
    return render_template(f"{kind}/test_practice.html", test=payloads[kind])


@app.get("/exam/<int:exam_id>/session/<token>/<kind>")
def exam_paper(exam_id, token, kind):
    return render_template(
        f"{kind}/test_practice.html",
        test=build_simulation_payload(payloads[kind], kind),
        exam_context={
            "exam_id": exam_id,
            "session_token": token,
            "exam_name": "Synthetic QA",
            "student_name": "QA",
            "section": kind,
            "section_label": kind,
            "minutes": 60,
            "deadline_at": None,
            "started_at": None,
            "submit_url": "/synthetic-submit",
            "next_url": "/practice",
            "exit_url": "/practice",
        },
    )


@app.route("/api/<kind>/test/<test_id>/<action>", methods=["GET", "POST"])
def practice_api(kind, test_id, action):
    if action == "submission":
        return jsonify(ok=True, submission=saved.get(kind))
    answers = (request.get_json() or {}).get("answers") or {}
    grade = graders[kind](payloads[kind], answers)
    saved[kind] = dict(
        answers=answers,
        results=grade["results"],
        correct_count=grade["correct"],
        total_count=grade["total"],
        accuracy=grade["accuracy"],
        ielts_score=grade["ielts_score"],
    )
    return jsonify(ok=True, synced=False, result=grade)


@app.get("/api/reading-study/catalog")
def study_catalog():
    return jsonify(passages=[])


if __name__ == "__main__":
    # A unittest SQLite :memory: fixture shares one connection; serialize QA
    # requests rather than simulating production's separate file-backed connections.
    app.run(host="127.0.0.1", port=5097, use_reloader=False, threaded=False)
