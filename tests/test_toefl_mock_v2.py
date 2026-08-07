import io
import json

import pytest
from flask import Flask
from flask_login import LoginManager

from api.toefl_mock import toefl_mock_bp
from models import ToeflMockAttempt, db
from services.toefl_mock_v2 import (
    catalog,
    definition,
    load_private_answer_key,
    public_catalog,
    route_module_two,
    validate_navigation_state,
    validate_response_value,
)

OFFICIAL_SLUGS = {
    "ets-og-chapter-6",
    "ets-practice-1",
    "ets-practice-2",
    "ets-practice-3",
    "ets-practice-4",
    "ets-practice-5",
}
RELEASED_SLUGS = {
    "2026-01-27_A",
    "2026-01-28_A",
    "2026-01-28_B",
    *OFFICIAL_SLUGS,
}


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


def test_catalog_integrates_all_thirteen_source_backed_sets():
    exams = catalog()

    assert len(exams) == 13
    assert sum(item["counts"]["questions"] for item in exams) == 1445
    assert sum(item["counts"]["blocked"] for item in exams) == 7
    assert all(item["validation_status"] == "pass" for item in exams)
    assert {
        item["slug"] for item in exams if item["release_ready"]
    } == RELEASED_SLUGS
    assert {
        item["slug"] for item in exams if item["preview_ready"]
    } == RELEASED_SLUGS


def test_public_catalog_exposes_only_audio_ready_packages():
    exams = public_catalog()

    assert [item["slug"] for item in exams] == [
        "2026-01-27_A",
        "2026-01-28_A",
        "2026-01-28_B",
        "ets-og-chapter-6",
        "ets-practice-1",
        "ets-practice-2",
        "ets-practice-3",
        "ets-practice-4",
        "ets-practice-5",
    ]
    assert sum(item["counts"]["questions"] for item in exams) == 965


def test_published_pilots_keep_visual_ocr_repairs_and_clean_audio_delivery():
    expected_d_options = {
        "toefl:2026-01-27-a:listening:m1:g01:q05": "The last stop before Springfield.",
        "toefl:2026-01-27-a:listening:m1:g01:q06": "I don't have a key.",
        "toefl:2026-01-27-a:listening:m1:g03:q15": "She thought the man was going to book the flight for her.",
        "toefl:2026-01-27-a:listening:m1:g03:q16": "The professors will likely not understand her research.",
        "toefl:2026-01-27-a:listening:m1:g04:q18": "Cook a meal at home",
        "toefl:2026-01-27-a:listening:m1:g07:q24": "Registering early for workshops",
        "toefl:2026-01-27-a:listening:m1:g08:q26": "It allows the brain to process emotional experiences.",
        "toefl:2026-01-27-a:listening:m1:g08:q27": "To illustrate the various stages of sleep",
        "toefl:2026-01-27-a:listening:m1:g09:q29": "The guidelines for identifying problematic behavior",
        "toefl:2026-01-27-a:listening:m1:g09:q32": "To describe the consequences of inconsistent feedback",
        "toefl:2026-01-27-a:listening:m2:g01:q02": "Are you sure?",
        "toefl:2026-01-27-a:listening:m2:g05:q15": "It allows residents to grow their own produce.",
        "toefl:2026-01-28-b:reading:m1:g07:q33": "school systems have developed better examinations",
    }
    definitions = {
        slug: definition(slug)
        for slug in ("2026-01-27_A", "2026-01-28_A", "2026-01-28_B")
    }
    questions = {
        question["id"]: question
        for payload in definitions.values()
        for question in payload["questions"]
    }
    for question_id, expected in expected_d_options.items():
        d_option = next(
            option["text"]
            for option in questions[question_id]["options"]
            if option["key"] == "D"
        )
        assert d_option == expected

    encoded_options = "\n".join(
        option["text"]
        for question in questions.values()
        for option in question.get("options", [])
    )
    for fragment in (
        "due ee",
        "eVvIew",
        "ontinue >",
        "Next>",
        "显示 答",
        "understand spoken English. There are three types of tasks",
    ):
        assert fragment not in encoded_options
    audio_assets = [
        asset
        for payload in definitions.values()
        for asset in payload["assets"]
        if asset["kind"] == "audio"
    ]
    assert len(audio_assets) == 9
    assert all(asset["delivery"]["status"] == "published" for asset in audio_assets)
    assert all(
        asset["delivery"]["url"].startswith("/static/toefl/v2/")
        for asset in audio_assets
    )


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


def test_three_released_sets_have_atomic_speaking_cues_and_2026_timing():
    for slug in ("2026-01-27_A", "2026-01-28_A", "2026-01-28_B"):
        payload = definition(slug, ["speaking"])
        phases = payload["phases"]
        groups = payload["groups"]
        questions = payload["questions"]

        assert payload["release"]["ready"] is True
        assert payload["release"]["formal_mode_available"] is True
        assert [phase["duration_seconds"] for phase in phases] == [180, 300]
        assert sum(phase["duration_seconds"] for phase in phases) == 480
        assert len(groups) == len(questions) == 11
        assert all(len(group["question_ids"]) == 1 for group in groups)
        assert [
            question["input_config"]["response_seconds"]
            for question in questions
        ] == [12] * 7 + [45] * 4
        assert all(
            question["input_config"]["preparation_seconds"] == 0
            for question in questions
        )
        assert all(
            group["stimulus"]["format"] == "audio_cue"
            and group["stimulus"]["cue_end_seconds"]
            > group["stimulus"]["cue_start_seconds"]
            >= 0
            and group["stimulus"]["alignment_confidence"] >= 0.96
            for group in groups
        )
        public_json = json.dumps(payload, ensure_ascii=False)
        assert "Welcome to the wood shop" not in public_json
        assert "What kind of movies do your family" not in public_json
        assert "Enter your name and student ID" not in public_json


def test_official_packages_preserve_source_timing_and_group_audio():
    practice = definition("ets-practice-1")
    og = definition("ets-og-chapter-6")

    assert [phase["duration_seconds"] for phase in practice["phases"][:2]] == [720, 720]
    assert [phase["duration_seconds"] for phase in og["phases"][:2]] == [1200, 540]
    listening_groups = [
        group for group in practice["groups"] if group["subject"] == "listening"
    ]
    assert listening_groups
    assert all(
        group["stimulus"]["playback_scope"] == "group"
        for group in listening_groups
    )
    og_speaking = [
        question["input_config"]["response_seconds"]
        for question in og["questions"]
        if question["subject"] == "speaking"
    ]
    assert [
        question["number"]
        for question in og["questions"]
        if question["subject"] == "speaking"
    ] == list(range(1, 12))
    assert og_speaking == [8, 8, 10, 10, 10, 12, 12, 45, 45, 45, 45]


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
    assert blocked.status_code == 401

    started = client.post(
        "/api/toefl/attempts/start",
        json={
            "testId": "2026-01-21_A",
            "sections": ["reading"],
            "preview": True,
            "returnTo": "https://evil.example/steal",
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
            "state": {"phaseIndex": 0, "groupIndex": 1},
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

    for group_index in range(2, 6):
        stepped = client.put(
            f"/api/toefl/attempts/{attempt['id']}/state",
            json={
                "state": {"phaseIndex": 0, "groupIndex": group_index},
                "currentPhase": "reading:m1",
            },
        )
        assert stepped.status_code == 200
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

    premature = client.post(f"/api/toefl/attempts/{attempt['id']}/complete")
    assert premature.status_code == 409
    advance = client.put(
        f"/api/toefl/attempts/{attempt['id']}/state",
        json={
            "state": {"phaseIndex": 1, "groupIndex": 0},
            "currentPhase": "reading:m2",
        },
    )
    assert advance.status_code == 200
    past_module_response = client.post(
        "/api/toefl/responses",
        json={"attemptId": attempt["id"], "questionId": qid, "response": "A"},
    )
    assert past_module_response.status_code == 409
    advance_group = client.put(
        f"/api/toefl/attempts/{attempt['id']}/state",
        json={
            "state": {"phaseIndex": 1, "groupIndex": 1},
            "currentPhase": "reading:m2",
        },
    )
    assert advance_group.status_code == 200
    completed = client.post(f"/api/toefl/attempts/{attempt['id']}/complete")
    assert completed.status_code == 200
    report = client.get(f"/api/toefl/attempts/{attempt['id']}/report")
    assert report.status_code == 200
    assert report.get_json()["objective"]["correct"] == 1
    assert report.get_json()["objective"]["auto_total"] == 50
    assert report.get_json()["routes"]["reading"]["route"] == "default"
    assert report.get_json()["manual"]["total"] == 0
    assert report.get_json()["release"]["preview_required"] is True

    closed_response = client.post(
        "/api/toefl/responses",
        json={"attemptId": attempt["id"], "questionId": qid, "response": "A"},
    )
    assert closed_response.status_code == 409
    closed_route = client.post(
        f"/api/toefl/attempts/{attempt['id']}/route-m2",
        json={"subject": "reading"},
    )
    assert closed_route.status_code == 409


def test_catalog_and_exam_pages_render(app):
    client = app.test_client()

    catalog_page = client.get("/toefl/mock")
    exam_page = client.get("/toefl/mock/2026-01-28_B?preview=1")

    assert catalog_page.status_code == 200
    catalog_html = catalog_page.get_data(as_text=True)
    assert catalog_html.count("开始正式刷题") == 9
    assert "2026-01-27 TOEFL Real Exam A" in catalog_html
    assert "2026-01-28 TOEFL Real Exam A" in catalog_html
    assert "2026-01-28 TOEFL Real Exam B" in catalog_html
    assert "ETS Student Practice Test 1" in catalog_html
    assert "ETS Official Guide Chapter 6 Practice Test" in catalog_html
    assert "2026-01-21 新托福真题" not in catalog_html
    assert exam_page.status_code == 200
    assert "ONLINE PREVIEW" in exam_page.get_data(as_text=True)


def test_catalog_distinguishes_audit_ready_from_formal_gate(app):
    page = app.test_client().get("/toefl/mock").get_data(as_text=True)

    assert "题包审计：published" in page
    assert "正式门禁：通过" in page
    assert "发布状态：ready" not in page


def test_state_rejects_navigation_jump_and_timer_increase(app):
    client = app.test_client()
    started = client.post(
        "/api/toefl/attempts/start",
        json={"testId": "2026-01-21_A", "sections": ["reading"], "preview": True},
    ).get_json()["attempt"]
    attempt_id = started["id"]
    jump = client.put(
        f"/api/toefl/attempts/{attempt_id}/state",
        json={
                "state": {"phaseIndex": 1, "groupIndex": 1},
                "currentPhase": "reading:m2",
        },
    )
    assert jump.status_code == 409
    for group_index in range(1, 6):
        stepped = client.put(
            f"/api/toefl/attempts/{attempt_id}/state",
            json={
                "state": {"phaseIndex": 0, "groupIndex": group_index},
                "currentPhase": "reading:m1",
            },
        )
        assert stepped.status_code == 200
    bypass_route = client.put(
        f"/api/toefl/attempts/{attempt_id}/state",
        json={
            "state": {"phaseIndex": 1, "groupIndex": 0},
            "currentPhase": "reading:m2",
        },
    )
    assert bypass_route.status_code == 409
    assert bypass_route.get_json()["error"] == "m2_route_required"
    increase = client.put(
        f"/api/toefl/attempts/{attempt_id}/state",
        json={
            "state": {"phaseIndex": 0, "groupIndex": 0},
            "currentPhase": "reading:m1",
            "remainingSeconds": 999999,
        },
    )
    assert increase.status_code == 409


def test_listening_back_policy_disables_same_phase_back_navigation(app):
    client = app.test_client()
    started = client.post(
        "/api/toefl/attempts/start",
        json={"testId": "2026-01-21_A", "sections": ["listening"], "preview": True},
    ).get_json()["attempt"]
    attempt_id = started["id"]
    forward = client.put(
        f"/api/toefl/attempts/{attempt_id}/state",
        json={
            "state": {"phaseIndex": 0, "groupIndex": 1},
            "currentPhase": "listening:m1",
            "remainingSeconds": None,
        },
    )
    assert forward.status_code == 200
    backward = client.put(
        f"/api/toefl/attempts/{attempt_id}/state",
        json={
            "state": {"phaseIndex": 0, "groupIndex": 0},
            "currentPhase": "listening:m1",
            "remainingSeconds": None,
        },
    )
    assert backward.status_code == 409
    assert backward.get_json()["error"] == "back_navigation_disabled"


def test_writing_phase_timer_snapshots_survive_back_and_forward(app):
    client = app.test_client()
    started = client.post(
        "/api/toefl/attempts/start",
        json={"testId": "2026-01-21_A", "sections": ["writing"], "preview": True},
    ).get_json()["attempt"]
    attempt_id = started["id"]
    low_build = client.put(
        f"/api/toefl/attempts/{attempt_id}/state",
        json={
            "state": {"phaseIndex": 0, "groupIndex": 0},
            "currentPhase": "writing:build_a_sentence",
            "remainingSeconds": 100,
        },
    ).get_json()["attempt"]
    assert low_build["remaining_seconds"] == 100
    first_email = client.put(
        f"/api/toefl/attempts/{attempt_id}/state",
        json={
            "state": {"phaseIndex": 1, "groupIndex": 0},
            "currentPhase": "writing:write_email",
        },
    ).get_json()["attempt"]
    assert first_email["remaining_seconds"] <= 420
    low_email = client.put(
        f"/api/toefl/attempts/{attempt_id}/state",
        json={
            "state": {"phaseIndex": 1, "groupIndex": 0},
            "currentPhase": "writing:write_email",
            "remainingSeconds": 200,
        },
    ).get_json()["attempt"]
    assert low_email["remaining_seconds"] == 200
    back_to_build = client.put(
        f"/api/toefl/attempts/{attempt_id}/state",
        json={
            "state": {"phaseIndex": 0, "groupIndex": 0},
            "currentPhase": "writing:build_a_sentence",
        },
    ).get_json()["attempt"]
    assert back_to_build["remaining_seconds"] <= 100
    forward_again = client.put(
        f"/api/toefl/attempts/{attempt_id}/state",
        json={
            "state": {"phaseIndex": 1, "groupIndex": 0},
            "currentPhase": "writing:write_email",
        },
    ).get_json()["attempt"]
    assert forward_again["remaining_seconds"] <= 200
    back_again = client.put(
        f"/api/toefl/attempts/{attempt_id}/state",
        json={
            "state": {"phaseIndex": 0, "groupIndex": 0},
            "currentPhase": "writing:build_a_sentence",
        },
    ).get_json()["attempt"]
    assert back_again["remaining_seconds"] <= 100


def test_audio_state_is_whitelisted_and_survives_resume(app):
    client = app.test_client()
    started = client.post(
        "/api/toefl/attempts/start",
        json={"testId": "2026-01-21_A", "sections": ["listening"], "preview": True},
    ).get_json()["attempt"]
    audio = {"listening:m1": {"ready": True, "skipped": True, "played": False}}
    saved = client.put(
        f"/api/toefl/attempts/{started['id']}/state",
        json={
            "state": {"phaseIndex": 0, "groupIndex": 0, "audio": audio},
            "currentPhase": "listening:m1",
            "remainingSeconds": None,
        },
    )
    assert saved.status_code == 200
    resumed = client.get(f"/api/toefl/attempts/{started['id']}/resume")
    assert resumed.get_json()["attempt"]["state"]["audio"] == audio
    invalid = client.put(
        f"/api/toefl/attempts/{started['id']}/state",
        json={
            "state": {
                "phaseIndex": 0,
                "groupIndex": 0,
                "audio": {"reading:m1": {"ready": True}},
            },
            "currentPhase": "listening:m1",
            "remainingSeconds": None,
        },
    )
    assert invalid.status_code == 400


def test_group_scoped_official_audio_state_is_accepted(app):
    client = app.test_client()
    payload = definition("ets-practice-1", ["listening"])
    group_id = payload["groups"][0]["id"]
    started = client.post(
        "/api/toefl/attempts/start",
        json={
            "testId": "ets-practice-1",
            "sections": ["listening"],
            "preview": True,
        },
    ).get_json()["attempt"]
    audio = {group_id: {"ready": True, "skipped": False, "played": True}}

    saved = client.put(
        f"/api/toefl/attempts/{started['id']}/state",
        json={
            "state": {"phaseIndex": 0, "groupIndex": 0, "audio": audio},
            "currentPhase": "listening:m1",
            "remainingSeconds": None,
        },
    )

    assert saved.status_code == 200
    assert saved.get_json()["attempt"]["state"]["audio"] == audio


def test_response_validation_rejects_wrong_shape_but_allows_repeated_tokens():
    order = {
        "response_type": "order",
        "input_config": {"scramble_tokens": ["a", "the", "the", "."]},
    }
    assert validate_response_value(order, ["the", "the"]) is None
    assert validate_response_value(order, ["the", "the", "the"]) == "response_tokens_invalid"
    assert validate_response_value(order, ["missing"]) == "response_tokens_invalid"
    mc = {
        "response_type": "mc",
        "options": [{"key": "A"}, {"key": "B"}],
        "input_config": {"selection": "single"},
    }
    assert validate_response_value(mc, "A") is None
    assert validate_response_value(mc, "C") == "response_option_invalid"
    recording = {"response_type": "recording"}
    assert validate_response_value(recording, {"recorded": True}) == "recording_upload_required"


def test_blocked_question_is_not_writable_and_stays_out_of_denominator(app):
    client = app.test_client()
    started = client.post(
        "/api/toefl/attempts/start",
        json={"testId": "2026-01-21_A", "sections": ["listening"], "preview": True},
    ).get_json()["attempt"]
    blocked_id = "toefl:2026-01-21-a:listening:m1:g03:q15"
    response = client.post(
        "/api/toefl/responses",
        json={"attemptId": started["id"], "questionId": blocked_id, "response": "A"},
    )
    assert response.status_code == 409
    audio_state = client.put(
        f"/api/toefl/attempts/{started['id']}/state",
        json={
            "state": {"phaseIndex": 0, "groupIndex": 0},
            "currentPhase": "listening:m1",
            "remainingSeconds": None,
        },
    )
    assert audio_state.status_code == 200
    assert definition("2026-01-21_A", ["listening"])["questions"]
    assert route_module_two("2026-01-21_A", "listening", {})["score"]["auto_total"] == 29


def test_speaking_requires_device_check_and_recording_question_type(app):
    client = app.test_client()
    missing_check = client.post(
        "/api/toefl/attempts/start",
        json={"testId": "2026-01-27_A", "sections": ["speaking"], "preview": True},
    )
    assert missing_check.status_code == 409
    started = client.post(
        "/api/toefl/attempts/start",
        json={
            "testId": "2026-01-27_A",
            "sections": ["speaking"],
            "preview": True,
            "deviceCheck": {"microphone": "passed"},
        },
    ).get_json()["attempt"]
    writing_qid = "toefl:2026-01-27-a:writing:m1:g02:q08"
    invalid = client.post(
        "/api/toefl/recordings",
        data={
            "attemptId": started["id"],
            "questionId": writing_qid,
            "durationMs": "1000",
            "audio": (io.BytesIO(b"not audio"), "response.webm"),
        },
        content_type="multipart/form-data",
    )
    assert invalid.status_code == 400


def test_single_section_and_ownership_are_scoped_to_attempt(app):
    first_client = app.test_client()
    started = first_client.post(
        "/api/toefl/attempts/start",
        json={"testId": "2026-01-28_A", "sections": ["writing"], "preview": True},
    ).get_json()["attempt"]
    assert started["sections"] == ["writing"]
    resumed = first_client.get(f"/api/toefl/attempts/{started['id']}/resume")
    assert resumed.status_code == 200
    assert resumed.get_json()["definition"]["sections"] == ["writing"]
    second_client = app.test_client()
    assert second_client.get(f"/api/toefl/attempts/{started['id']}/resume").status_code == 404


def test_recording_upload_saves_opaque_id_without_returning_file_path(app):
    client = app.test_client()
    started = client.post(
        "/api/toefl/attempts/start",
        json={
            "testId": "2026-01-27_A",
            "sections": ["speaking"],
            "preview": True,
            "deviceCheck": {"microphone": "passed"},
        },
    ).get_json()["attempt"]
    qid = "toefl:2026-01-27-a:speaking:m1:g01:q01"
    saved = client.post(
        "/api/toefl/recordings",
        data={
            "attemptId": started["id"],
            "questionId": qid,
            "durationMs": "1000",
            "audio": (io.BytesIO(b"preview audio bytes"), "response.webm"),
        },
        content_type="multipart/form-data",
    )
    assert saved.status_code == 200
    payload = saved.get_json()
    assert payload["recordingId"]
    assert "toefl_mock" not in payload["recordingId"]
    resumed = client.get(f"/api/toefl/attempts/{started['id']}/resume").get_json()
    assert resumed["attempt"]["responses"][qid]["recorded"] is True
    assert "toefl_mock" not in json.dumps(resumed["attempt"]["responses"])


def test_recording_upload_enforces_current_question_and_response_limit(app):
    client = app.test_client()
    started = client.post(
        "/api/toefl/attempts/start",
        json={
            "testId": "2026-01-27_A",
            "sections": ["speaking"],
            "preview": True,
            "deviceCheck": {"microphone": "passed"},
        },
    ).get_json()["attempt"]
    next_qid = "toefl:2026-01-27-a:speaking:m1:g01:q02"
    out_of_order = client.post(
        "/api/toefl/recordings",
        data={
            "attemptId": started["id"],
            "questionId": next_qid,
            "durationMs": "1000",
            "audio": (io.BytesIO(b"preview audio bytes"), "response.webm"),
        },
        content_type="multipart/form-data",
    )
    assert out_of_order.status_code == 409
    assert out_of_order.get_json()["error"] == "question_not_current"

    first_qid = "toefl:2026-01-27-a:speaking:m1:g01:q01"
    over_limit = client.post(
        "/api/toefl/recordings",
        data={
            "attemptId": started["id"],
            "questionId": first_qid,
            "durationMs": "14001",
            "audio": (io.BytesIO(b"preview audio bytes"), "response.webm"),
        },
        content_type="multipart/form-data",
    )
    assert over_limit.status_code == 400
    assert over_limit.get_json()["error"] == "recording_duration_invalid"


def test_formal_recording_is_one_take(app):
    client = app.test_client()
    started = client.post(
        "/api/toefl/attempts/start",
        json={
            "testId": "2026-01-27_A",
            "sections": ["speaking"],
            "preview": True,
            "deviceCheck": {"microphone": "passed"},
        },
    ).get_json()["attempt"]
    with app.app_context():
        attempt = db.session.get(ToeflMockAttempt, started["id"])
        attempt.is_preview = False
        db.session.commit()

    qid = "toefl:2026-01-27-a:speaking:m1:g01:q01"

    def upload():
        return client.post(
            "/api/toefl/recordings",
            data={
                "attemptId": started["id"],
                "questionId": qid,
                "durationMs": "1000",
                "audio": (io.BytesIO(b"formal audio bytes"), "response.webm"),
            },
            content_type="multipart/form-data",
        )

    assert upload().status_code == 200
    repeated = upload()
    assert repeated.status_code == 409
    assert repeated.get_json()["error"] == "recording_take_limit_reached"
