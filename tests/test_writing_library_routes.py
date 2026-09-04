"""Access control and server-owned attempt tests for the web writing library."""

from datetime import timedelta

import pytest
from flask import Flask
from flask_login import LoginManager

from api.writing_library import writing_library_bp
from models import StudentProfile, WritingTypingAttempt, db
from services.writing_library import get_exercise


@pytest.fixture()
def writing_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.update(
        SECRET_KEY="writing-library-test",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
    )
    db.init_app(app)
    login_manager = LoginManager(app)

    @login_manager.user_loader
    def _load_user(_user_id):
        return None

    app.add_url_rule("/", endpoint="index", view_func=lambda: "home")
    app.add_url_rule("/practice", endpoint="practice_library", view_func=lambda: "practice")
    app.add_url_rule(
        "/listening/tests", endpoint="listening_test_index", view_func=lambda: "listening"
    )
    app.add_url_rule(
        "/reading/tests", endpoint="reading_test_index", view_func=lambda: "reading"
    )
    app.register_blueprint(writing_library_bp)
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [StudentProfile(full_name="写作学生"), StudentProfile(full_name="另一位学生")]
        )
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def writing_client(writing_app):
    return writing_app.test_client()


def _verify(client, name="写作学生"):
    with client.session_transaction() as flask_session:
        flask_session["practice_student_name"] = name


def test_guest_is_redirected_to_identity_gate(writing_client):
    response = writing_client.get("/writing/")
    topics_response = writing_client.get("/writing/topics")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/practice#ieltsPractice")
    assert topics_response.status_code == 302
    assert topics_response.headers["Location"].endswith("/practice#ieltsPractice")
    assert writing_client.post("/writing/api/t2-010/typing/start", json={"band": "6.0"}).status_code == 401


def test_verified_student_can_open_catalog_and_complete_attempt(writing_app, writing_client):
    _verify(writing_client)
    catalog_response = writing_client.get("/writing/")
    detail_response = writing_client.get("/writing/t1-001")

    assert catalog_response.status_code == 200
    assert catalog_response.get_data(as_text=True).count('data-writing-card ') == 40
    detail_html = detail_response.get_data(as_text=True)
    assert "三档教学范文" in detail_html
    assert "逐字输入训练" in detail_html
    assert "t1-001-solar-panel.png" in detail_html

    started = writing_client.post(
        "/writing/api/t2-010/typing/start", json={"band": "7.0+"}
    )
    assert started.status_code == 200
    attempt_id = started.get_json()["attempt_id"]
    with writing_app.app_context():
        attempt = db.session.get(WritingTypingAttempt, attempt_id)
        attempt.started_at -= timedelta(seconds=60)
        db.session.commit()

    target = get_exercise("t2-010")["essays"]["7.0+"]["text"]
    finished = writing_client.post(
        f"/writing/api/t2-010/typing/{attempt_id}/finish",
        json={"band": "7.0+", "typed_text": target},
    )
    payload = finished.get_json()
    assert finished.status_code == 200
    assert payload["attempt"]["accuracy"] == 100.0
    assert payload["attempt"]["typed_word_count"] >= 250
    assert payload["attempt"]["speed_wpm"] > 0

    repeated = writing_client.post(
        f"/writing/api/t2-010/typing/{attempt_id}/finish",
        json={"band": "7.0+", "typed_text": "changed"},
    )
    assert repeated.get_json()["idempotent"] is True
    assert repeated.get_json()["attempt"]["accuracy"] == 100.0


def test_verified_student_can_browse_mother_topics_and_link_to_pilot(writing_client):
    _verify(writing_client)

    index_response = writing_client.get("/writing/topics")
    assert index_response.status_code == 200
    index_html = index_response.get_data(as_text=True)
    assert index_html.count("data-mother-topic-card ") == 27
    assert "252" in index_html
    assert "108" in index_html

    detail_response = writing_client.get("/writing/topics/t01")
    assert detail_response.status_code == 200
    detail_html = detail_response.get_data(as_text=True)
    assert "教育目标、课程与方法" in detail_html
    assert "4 条可复用逻辑链" in detail_html
    assert "Band 7.0+ 教学范文" in detail_html
    assert "展开全部 28 道同母题题干" in detail_html
    assert "/writing/t2-018" in detail_html

    pilot_html = writing_client.get("/writing/t2-018").get_data(as_text=True)
    assert "T01 · 教育目标、课程与方法" in pilot_html
    assert "/writing/topics/t01" in pilot_html

    assert writing_client.get("/writing/topics/not-a-topic").status_code == 404


def test_attempt_is_owned_by_verified_student(writing_client):
    _verify(writing_client)
    attempt_id = writing_client.post(
        "/writing/api/t2-010/typing/start", json={"band": "6.0"}
    ).get_json()["attempt_id"]
    _verify(writing_client, "另一位学生")

    response = writing_client.post(
        f"/writing/api/t2-010/typing/{attempt_id}/finish",
        json={"band": "6.0", "typed_text": "test"},
    )
    assert response.status_code == 404
    assert response.get_json()["error"] == "attempt_not_found"


def test_classroom_mode_runs_without_creating_student_record(writing_app, writing_client):
    with writing_client.session_transaction() as flask_session:
        flask_session["classroom_unlocked"] = True

    response = writing_client.post(
        "/writing/api/t2-010/typing/start", json={"band": "6.5"}
    )
    assert response.status_code == 200
    assert response.get_json()["client_only"] is True
    with writing_app.app_context():
        assert WritingTypingAttempt.query.count() == 0
