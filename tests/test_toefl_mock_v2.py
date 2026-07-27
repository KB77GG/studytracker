import io
import json

import pytest
from flask import Flask
from flask_login import LoginManager

from api.toefl_mock import toefl_mock_bp
from models import db
from services.toefl_mock_v2 import (
    catalog,
    definition,
    load_private_answer_key,
    route_module_two,
)


@pytest.fixture()
def app(tmp_path):
    test_app = Flask(__name__, template_folder="../templates", static_folder="../static")
    test_app.config.update(
        SECRET_KEY="toefl-mock-test",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=str(tmp_path / "uploads"),
        TESTING=True,
    )
    db.init_app(test_app)
    login_manager = LoginManager(test_app)
    login_manager.user_loader(lambda _user_id: None)
    test_app.add_url_rule("/", endpoint="index", view_func=lambda: "index")
    test_app.add_url_rule("/login", endpoint="login", view_func=lambda: "login")
    test_app.register_blueprint(toefl_mock_bp)
    with test_app.app_context():
        db.create_all()
    yield test_app
    with test_app.app_context():
        db.session.remove()
        db.drop_all()


def test_catalog_integrates_all_seven_source_backed_sets():
    exams = catalog()

    assert len(exams) == 7
    assert sum(item["counts"]["questions"] for item in exams) == 840
    assert sum(item["counts"]["blocked"] for item in exams) == 7
    assert all(item["validation_status"] == "pass" for item in exams)
    assert not any(item["release_ready"] for item in exams)


def test_conflicting_answer_pdf_entries_use_corroborating_evidence():
    answer_key = load_private_answer_key("2026-01-28_A")
    by_id = {item["question_id"]: item for item in answer_key["answers"]}

    reading = by_id["toefl:2026-01-28-a:reading:m2:g01:q06"]
    assert reading["canonical_text"] == "orate"
    assert all("参考答案" not in item["path"] for item in reading["evidence"])
    assert any(item["path"].endswith("wechat_complete_words_full.json") for item in reading["evidence"])

    listening = by_id["toefl:2026-01-28-a:listening:m1:g07:q24"]
    assert listening["correct_option_keys"] == ["A"]
    assert all("参考答案" not in item["path"] for item in listening["evidence"])
    assert any(item["path"].endswith("听力原文.pdf") for item in listening["evidence"])


def test_definition_is_public_safe_and_preserves_repaired_q33():
    payload = definition("2026-01-21_A")
    encoded = json.dumps(payload, ensure_ascii=False)

    assert "correct_option_keys" not in encoded
    assert "canonical_text" not in encoded
    assert '"sha256"' not in encoded
    assert '"source_folder"' not in encoded
    assert "1.21新托福真题A卷/" not in encoded
    q33 = next(
        item
        for item in payload["questions"]
        if item["id"] == "toefl:2026-01-21-a:reading:m1:g06:q33"
    )
    assert q33["available"] is True
    assert len(q33["options"]) == 4


def test_definition_follows_spec_section_order_and_does_not_invent_m2():
    payload = definition("toefl:2026-01-28-b")

    assert payload["sections"] == ["reading", "listening", "speaking", "writing"]
    phase_sections = [item["section"] for item in payload["phases"]]
    assert phase_sections == sorted(
        phase_sections,
        key=("reading", "listening", "speaking", "writing").index,
    )
    assert payload["phases"][0]["id"] == "reading:m1"
    assert payload["phases"][0]["duration_seconds"] == 1080
    assert payload["phases"][1]["id"] == "reading:m2"
    assert payload["phases"][1]["duration_seconds"] == 540
    assert payload["adaptive"]["reading"]["branches"] == ["default"]
    assert payload["adaptive"]["reading"]["available"] is False


def test_route_m2_scores_module_one_but_returns_only_verified_default():
    answer_key = load_private_answer_key("2026-01-21_A")
    first = next(
        item
        for item in answer_key["answers"]
        if ":reading:m1:" in item["question_id"]
    )
    response = first.get("canonical_text") or first["correct_option_keys"][0]

    routed = route_module_two(
        "2026-01-21_A",
        "reading",
        {first["question_id"]: response},
    )

    assert routed["route"] == "default"
    assert routed["adaptive_available"] is False
    assert routed["score"]["answered"] == 1
    assert routed["score"]["correct"] == 1


def test_attempt_api_requires_preview_and_supports_save_resume_route_report(app):
    client = app.test_client()

    blocked = client.post(
        "/api/toefl/attempts/start",
        json={"testId": "2026-01-21_A", "sections": ["reading"]},
    )
    assert blocked.status_code == 409

    started = client.post(
        "/api/toefl/attempts/start",
        json={
            "testId": "2026-01-21_A",
            "sections": ["reading"],
            "preview": True,
        },
    )
    assert started.status_code == 201
    attempt = started.get_json()["attempt"]
    assert attempt["preview"] is True
    assert attempt["current_phase"] == "reading:m1"

    qid = "toefl:2026-01-21-a:reading:m1:g06:q33"
    saved = client.post(
        "/api/toefl/responses",
        json={"attemptId": attempt["id"], "questionId": qid, "response": "C"},
    )
    assert saved.status_code == 200
    wrong_section = client.post(
        "/api/toefl/responses",
        json={
            "attemptId": attempt["id"],
            "questionId": "toefl:2026-01-21-a:listening:m1:g01:q01",
            "response": "A",
        },
    )
    assert wrong_section.status_code == 400

    state = client.put(
        f"/api/toefl/attempts/{attempt['id']}/state",
        json={
            "state": {"phaseIndex": 0, "groupIndex": 4},
            "currentPhase": "reading:m1",
            "remainingSeconds": 900,
        },
    )
    assert state.status_code == 200
    assert state.get_json()["attempt"]["state"]["returnTo"] == "/toefl/mock"
    invalid_state = client.put(
        f"/api/toefl/attempts/{attempt['id']}/state",
        json={"currentPhase": "reading:invented"},
    )
    assert invalid_state.status_code == 400

    invalid_recording = client.post(
        "/api/toefl/recordings",
        data={
            "attemptId": attempt["id"],
            "questionId": qid,
            "audio": (io.BytesIO(b"not audio"), "response.webm"),
        },
        content_type="multipart/form-data",
    )
    assert invalid_recording.status_code == 400

    routed = client.post(
        f"/api/toefl/attempts/{attempt['id']}/route-m2",
        json={"subject": "reading"},
    )
    assert routed.status_code == 200
    assert routed.get_json()["route"] == "default"

    resumed = client.get(f"/api/toefl/attempts/{attempt['id']}/resume")
    resumed_payload = resumed.get_json()
    assert resumed_payload["attempt"]["responses"][qid] == "C"
    assert resumed_payload["attempt"]["remaining_seconds"] == 900

    completed = client.post(f"/api/toefl/attempts/{attempt['id']}/complete")
    assert completed.status_code == 200
    report = client.get(f"/api/toefl/attempts/{attempt['id']}/report")
    assert report.status_code == 200
    assert report.get_json()["objective"]["correct"] == 1
    assert report.get_json()["objective"]["auto_total"] == 50
    assert report.get_json()["routes"]["reading"]["route"] == "default"


def test_catalog_and_exam_pages_render(app):
    client = app.test_client()

    catalog_page = client.get("/toefl/mock")
    exam_page = client.get("/toefl/mock/2026-01-28_B?preview=1")

    assert catalog_page.status_code == 200
    assert "7" in catalog_page.get_data(as_text=True)
    assert exam_page.status_code == 200
    assert "STAGING PREVIEW" in exam_page.get_data(as_text=True)
