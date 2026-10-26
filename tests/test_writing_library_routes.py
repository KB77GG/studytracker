"""Access control and server-owned attempt tests for the web writing library."""

import json
from datetime import date, timedelta

import pytest
from flask import Flask
from flask_login import LoginManager

from api.writing_library import writing_library_bp
from models import StudentProfile, Task, WritingTypingAttempt, db, utcnow_naive
from services.writing_assignments import (
    WritingAssignmentError,
    build_snapshot,
    complete_task,
    dump_snapshot,
    typing_attempt_ids,
)
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


def _assigned_writing_task(app, resource_type, resource_id):
    with app.app_context():
        snapshot = build_snapshot(resource_type, resource_id)
        task = Task(
            date=date.today().isoformat(),
            student_name="写作学生",
            category="雅思-写作-练习",
            detail=snapshot["title"],
            status="pending",
            grading_mode="writing_practice",
            question_ids=dump_snapshot(snapshot),
        )
        db.session.add(task)
        db.session.commit()
        return task.id


def test_assigned_exercise_completes_task_after_typing(writing_app, writing_client):
    _verify(writing_client)
    task_id = _assigned_writing_task(writing_app, "exercise", "t2-010")
    page = writing_client.get(f"/writing/t2-010?task_id={task_id}")
    assert page.status_code == 200
    assert f'data-assigned-task-id="{task_id}"' in page.get_data(as_text=True)

    started = writing_client.post(
        "/writing/api/t2-010/typing/start",
        json={"band": "6.0", "task_id": task_id},
    )
    attempt_id = started.get_json()["attempt_id"]
    target = get_exercise("t2-010")["essays"]["6.0"]["text"]
    finished = writing_client.post(
        f"/writing/api/t2-010/typing/{attempt_id}/finish",
        json={"band": "6.0", "typed_text": target, "task_id": task_id},
    )
    assert finished.status_code == 200
    assert finished.get_json()["task_completed"] is True
    with writing_app.app_context():
        task = db.session.get(Task, task_id)
        assert task.status == "done"
        assert task.completion_rate == 100.0
        assert task.student_submitted is True


def test_assigned_mother_topic_can_be_confirmed_complete(writing_app, writing_client):
    _verify(writing_client)
    task_id = _assigned_writing_task(writing_app, "mother_topic", "t01")
    page = writing_client.get(f"/writing/topics/t01?task_id={task_id}")
    assert page.status_code == 200
    assert "确认完成学习" in page.get_data(as_text=True)

    completed = writing_client.post(
        f"/writing/api/topics/t01/tasks/{task_id}/complete",
        json={"duration_seconds": 420},
    )
    assert completed.status_code == 200
    with writing_app.app_context():
        task = db.session.get(Task, task_id)
        assert task.status == "done"
        assert task.actual_seconds == 420


def test_one_student_cannot_complete_another_students_writing_task(writing_app, writing_client):
    task_id = _assigned_writing_task(writing_app, "mother_topic", "t01")
    _verify(writing_client, "另一位学生")

    page = writing_client.get(f"/writing/topics/t01?task_id={task_id}")
    assert page.status_code == 200
    assert "确认完成学习" not in page.get_data(as_text=True)
    completed = writing_client.post(
        f"/writing/api/topics/t01/tasks/{task_id}/complete",
        json={"duration_seconds": 60},
    )
    assert completed.status_code == 409
    with writing_app.app_context():
        assert db.session.get(Task, task_id).status == "pending"


def _start_assigned(client, task_id):
    response = client.post(
        "/writing/api/t2-010/typing/start", json={"band": "6.0", "task_id": task_id}
    )
    assert response.status_code == 200
    return response.get_json()["attempt_id"]


def _finish(client, attempt_id, **extra):
    return client.post(
        f"/writing/api/t2-010/typing/{attempt_id}/finish",
        json={"band": "6.0", "typed_text": "saved student text", **extra},
    )


def test_start_binds_multiple_attempts_and_finish_can_recover_omitted_task_id(
    writing_app, writing_client
):
    _verify(writing_client)
    task_id = _assigned_writing_task(writing_app, "exercise", "t2-010")
    first = _start_assigned(writing_client, task_id)
    second = _start_assigned(writing_client, task_id)
    with writing_app.app_context():
        task = db.session.get(Task, task_id)
        assert typing_attempt_ids(task) == [first, second]
        assert task.status == "pending"
    response = _finish(writing_client, first)
    assert response.status_code == 200
    assert response.get_json()["task_completed"] is True
    delayed = _finish(writing_client, second, task_id=task_id)
    assert delayed.status_code == 409
    assert delayed.get_json()["error"] == "task_completed_read_only"
    with writing_app.app_context():
        assert db.session.get(WritingTypingAttempt, first).status == "completed"
        assert db.session.get(WritingTypingAttempt, second).status == "in_progress"


@pytest.mark.parametrize("complete_first", [False, True])
def test_attempt_cannot_complete_another_assignment_of_same_exercise(
    writing_app, writing_client, complete_first
):
    _verify(writing_client)
    original = _assigned_writing_task(writing_app, "exercise", "t2-010")
    repeated_task = _assigned_writing_task(writing_app, "exercise", "t2-010")
    attempt_id = _start_assigned(writing_client, original)
    if complete_first:
        assert _finish(writing_client, attempt_id, task_id=original).status_code == 200
    response = _finish(writing_client, attempt_id, task_id=repeated_task)
    assert response.status_code == 409
    assert response.get_json()["error"] == "writing_attempt_task_mismatch"
    with writing_app.app_context():
        task = db.session.get(Task, repeated_task)
        assert task.status == "pending"
        assert task.student_submitted is False
        assert typing_attempt_ids(task) == []


@pytest.mark.parametrize("complete_first", [False, True])
def test_unbound_or_legacy_attempt_is_never_guessed_onto_a_task(
    writing_app, writing_client, complete_first
):
    _verify(writing_client)
    task_id = _assigned_writing_task(writing_app, "exercise", "t2-010")
    attempt_id = writing_client.post(
        "/writing/api/t2-010/typing/start", json={"band": "6.0"}
    ).get_json()["attempt_id"]
    if complete_first:
        assert _finish(writing_client, attempt_id).status_code == 200
    response = _finish(writing_client, attempt_id, task_id=task_id)
    assert response.status_code == 409
    assert response.get_json()["error"] == "writing_attempt_task_mismatch"
    with writing_app.app_context():
        assert db.session.get(Task, task_id).status == "pending"
        assert typing_attempt_ids(db.session.get(Task, task_id)) == []


def test_bound_attempt_replay_after_cutoff_is_read_only(writing_app, writing_client):
    _verify(writing_client)
    task_id = _assigned_writing_task(writing_app, "exercise", "t2-010")
    attempt_id = _start_assigned(writing_client, task_id)
    finished = _finish(writing_client, attempt_id, task_id=task_id)
    assert finished.status_code == 200
    first_result = finished.get_json()["attempt"]
    with writing_app.app_context():
        task = db.session.get(Task, task_id)
        task.date = (date.today() - timedelta(days=3)).isoformat()
        db.session.commit()
        original_note = task.student_note
        original_timestamp = task.submitted_at
    replay = _finish(writing_client, attempt_id, task_id=task_id, typed_text="replacement")
    assert replay.status_code == 200
    assert replay.get_json()["idempotent"] is True
    assert replay.get_json()["attempt"] == first_result
    with writing_app.app_context():
        task = db.session.get(Task, task_id)
        assert task.student_note == original_note
        assert task.submitted_at == original_timestamp
        assert db.session.get(WritingTypingAttempt, attempt_id).typed_text == "saved student text"


def test_omitted_task_id_does_not_bypass_assignment_cutoff(writing_app, writing_client):
    _verify(writing_client)
    task_id = _assigned_writing_task(writing_app, "exercise", "t2-010")
    attempt_id = _start_assigned(writing_client, task_id)
    with writing_app.app_context():
        task = db.session.get(Task, task_id)
        task.date = (date.today() - timedelta(days=3)).isoformat()
        db.session.commit()
    response = _finish(writing_client, attempt_id)
    assert response.status_code == 409
    assert response.get_json()["error"] == "task_expired"
    with writing_app.app_context():
        assert db.session.get(Task, task_id).status == "pending"
        assert db.session.get(WritingTypingAttempt, attempt_id).status == "in_progress"


def test_mother_topic_retains_completion_summary_on_replay(writing_app, writing_client):
    _verify(writing_client)
    task_id = _assigned_writing_task(writing_app, "mother_topic", "t01")
    endpoint = f"/writing/api/topics/t01/tasks/{task_id}/complete"
    assert writing_client.post(endpoint, json={"duration_seconds": 420}).status_code == 200
    with writing_app.app_context():
        task = db.session.get(Task, task_id)
        original_snapshot = task.question_ids
        result = json.loads(original_snapshot)["writing_topic_result"]
        assert result["duration_seconds"] == 420
        assert result["completed_at"].endswith("Z")
    repeated = writing_client.post(endpoint, json={"duration_seconds": 9999})
    assert repeated.get_json()["idempotent"] is True
    with writing_app.app_context():
        task = db.session.get(Task, task_id)
        assert task.question_ids == original_snapshot
        assert task.actual_seconds == 420


def test_stale_completion_cannot_overwrite_another_tab_result(writing_app):
    task_id = _assigned_writing_task(writing_app, "exercise", "t2-010")
    with writing_app.app_context():
        stale = db.session.get(Task, task_id)
        Task.query.filter_by(id=task_id).update(
            {Task.status: "done", Task.accuracy: 73.5}, synchronize_session=False
        )
        # Same interleaving as a second transaction committing after this one
        # read pending state, without refreshing the stale ORM object.
        assert stale.status == "pending"
        with pytest.raises(WritingAssignmentError, match="writing_task_changed_retry"):
            complete_task(stale, submitted_at=utcnow_naive(), accuracy=1)
        db.session.refresh(stale)
        assert stale.status == "done"
        assert stale.accuracy == 73.5


@pytest.mark.parametrize(
    ("day_delta", "status", "error"),
    [(-3, "pending", "task_expired"), (1, "pending", "task_not_open"), (0, "done", "task_completed_read_only")],
)
def test_start_rejects_closed_assignment_without_creating_attempt(
    writing_app, writing_client, day_delta, status, error
):
    _verify(writing_client)
    task_id = _assigned_writing_task(writing_app, "exercise", "t2-010")
    with writing_app.app_context():
        task = db.session.get(Task, task_id)
        task.date = (date.today() + timedelta(days=day_delta)).isoformat()
        task.status = status
        db.session.commit()
    response = writing_client.post(
        "/writing/api/t2-010/typing/start", json={"band": "6.0", "task_id": task_id}
    )
    assert response.status_code == 409
    assert response.get_json()["error"] == error
    with writing_app.app_context():
        assert WritingTypingAttempt.query.count() == 0
        assert typing_attempt_ids(db.session.get(Task, task_id)) == []
