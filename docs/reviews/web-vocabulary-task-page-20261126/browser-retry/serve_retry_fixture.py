"""Local-only browser QA: inspect synthetic rows and drop one committed reply.

This imports the existing disposable in-memory fixture without running its
__main__. It never replaces product JavaScript or its timer. Do not deploy it.
"""

import argparse
import importlib.util
import json
import socket
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import abort, g, jsonify, request, session

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "serve_fixture.py"
spec = importlib.util.spec_from_file_location("qa_vocabulary_retry_base", SOURCE)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
app = fixture.app

from models import (  # noqa: E402
    DictationRecord,
    Task,
    User,
    VocabularyLearningFlow,
    VocabularyLearningQuestion,
    VocabularyTaskSettlement,
)

assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"
assert app.config["TESTING"] is True

AUDIT_PATH = HERE / "audit-5114.jsonl"
audit_lock = threading.Lock()
drop_lock = threading.Lock()
consumed_arms = set()


def now():
    return datetime.now(timezone.utc).isoformat()


def audit(event, **values):
    row = {"time_utc": now(), "epoch_ms": int(time.time() * 1000), "event": event, **values}
    with audit_lock:
        with AUDIT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()


def task_stats(task_id, attempt_id=None):
    """Only SELECTs; no names, credentials, expected answers or queue tokens."""
    task = fixture.db.session.get(Task, task_id)
    student = User.query.filter_by(username="qa-student").one()
    records = DictationRecord.query.filter_by(student_id=student.id, task_id=task_id).all()
    questions = VocabularyLearningQuestion.query.filter_by(
        student_id=student.id, task_id=task_id
    ).order_by(VocabularyLearningQuestion.question_order).all()
    settlements = VocabularyTaskSettlement.query.filter_by(
        student_id=student.id, task_id=task_id
    ).all()
    flow = VocabularyLearningFlow.query.filter_by(student_id=student.id, task_id=task_id).first()
    attempt_records = [r for r in records if r.attempt_id == attempt_id] if attempt_id else []
    return {
        "task_id": task_id,
        "goal": next(k for k, v in fixture.task_ids.items() if v == task_id),
        "record_count": len(records),
        "first_record_count": sum(bool(r.is_first_attempt) for r in records),
        "attempt_id": attempt_id,
        "attempt_record_count": len(attempt_records) if attempt_id else None,
        "attempt_record_ids": [r.id for r in attempt_records],
        "records": [
            {"id": r.id, "attempt_id": r.attempt_id, "word_id": r.word_id,
             "is_first_attempt": r.is_first_attempt, "is_correct": r.is_correct,
             "response_kind": r.response_kind, "student_answer": r.student_answer}
            for r in records
        ],
        "questions": [
            {"id": q.id, "word_id": q.word_id, "dimension": q.dimension,
             "first_attempt_id": q.first_attempt_id, "first_answer": q.first_answer,
             "first_is_correct": q.first_is_correct, "retry_attempt_id": q.retry_attempt_id,
             "correction_attempt_id": q.correction_attempt_id,
             "correction_count": q.correction_count}
            for q in questions
        ],
        "settlement_count": len(settlements),
        "settlements": [
            {"id": s.id, "settled_at": s.settled_at.isoformat(),
             "result": {k: v for k, v in json.loads(s.result_json).items()
                        if k in {"correct_count", "total_count", "scorable_count", "retry_count"}}}
            for s in settlements
        ],
        "db_task_actual_seconds": task.actual_seconds,
        "task_status": task.status,
        "task_student_submitted": task.student_submitted,
        "flow_phase": flow.phase if flow else None,
        "flow_state_version": flow.state_version if flow else None,
    }


@app.get("/__qa/stats")
def qa_stats():
    task_id = request.args.get("task_id", type=int)
    if task_id is not None and task_id not in fixture.task_ids.values():
        abort(404)
    attempt_id = request.args.get("attempt_id")
    if attempt_id and len(attempt_id) > 96:
        abort(400)
    return jsonify(
        synthetic_only=True,
        time_utc=now(),
        task_ids=fixture.task_ids,
        tasks=[task_stats(t, attempt_id) for t in ([task_id] if task_id else fixture.task_ids.values())],
    )


@app.after_request
def qa_observe_and_drop(response):
    # Arming is done on a normal successful navigation, before the answer whose
    # reply will be lost. Consuming this arm is server-side, not a lost cookie.
    arming = (
        request.path.startswith("/__qa/start/")
        and request.args.get("fault") == "transport_drop_once"
    ) or request.path == "/__qa/control/transport_drop_once"
    if arming and response.status_code < 400:
        session["qa_transport_arm"] = uuid.uuid4().hex
        audit("transport_drop_armed", path=request.path)

    if request.method != "POST" or not request.path.startswith("/api/practice/vocabulary/tasks/"):
        return response
    task_id = (request.view_args or {}).get("task_id")
    if task_id not in fixture.task_ids.values():
        return response
    # The product gate already parsed this body. Reading the request stream in
    # a QA before_request would interfere with its bounded body parser.
    payload = getattr(g, "practice_payload", {})
    attempt_id = payload.get("attempt_id")
    stats = task_stats(task_id, attempt_id)
    summary = {k: stats[k] for k in (
        "record_count", "first_record_count", "attempt_record_count",
        "attempt_record_ids", "settlement_count", "db_task_actual_seconds",
        "flow_phase", "flow_state_version",
    )}
    event = {
        "path": request.path, "task_id": task_id, "status_code": response.status_code,
        "attempt_id": attempt_id, "request_duration_seconds": payload.get("duration_seconds"),
        **summary,
    }
    audit("post_committed_response", **event)
    arm = session.get("qa_transport_arm")
    should_drop = (
        request.path == f"/api/practice/vocabulary/tasks/{task_id}/answers"
        and response.status_code == 200
        and session.get("qa_fault") == "transport_drop_once"
        and arm and attempt_id and stats["attempt_record_count"] == 1
    )
    if not should_drop:
        return response
    client_socket = request.environ.get("werkzeug.socket")
    if client_socket is None:
        audit("transport_drop_unsupported_no_socket", **event)
        return response
    with drop_lock:
        if arm in consumed_arms:
            return response
        consumed_arms.add(arm)
    # Product _reply committed before this hook. Closing this request's socket
    # prevents headers/body reaching the browser; no synthetic HTTP 503 exists.
    audit("transport_drop_before_http_reply", **event)
    errors = []
    try:
        client_socket.shutdown(socket.SHUT_RDWR)
    except OSError as error:
        errors.append(type(error).__name__)
    try:
        client_socket.close()
    except OSError as error:
        errors.append(type(error).__name__)
    audit("transport_socket_closed", **event, socket_error_types=errors)
    return response


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, choices=[5114, 5115], default=5114)
    parser.add_argument("--audit-file", default=None)
    args = parser.parse_args()
    if args.audit_file:
        candidate = Path(args.audit_file).resolve()
        if not candidate.is_relative_to(HERE):
            parser.error("audit file must be inside browser-retry")
        AUDIT_PATH = candidate
    else:
        AUDIT_PATH = HERE / f"audit-{args.port}.jsonl"
    audit("server_start", port=args.port, database="sqlite-memory-only")
    app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
