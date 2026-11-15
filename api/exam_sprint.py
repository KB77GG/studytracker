"""Public weekly revision lists; practice and scoring use existing routes."""

import re

from flask import Blueprint, abort, current_app, render_template, send_from_directory

exam_sprint_bp = Blueprint("exam_sprint", __name__)

SUBJECT_LABELS = {"listening": "听力", "reading": "阅读"}


@exam_sprint_bp.get("/practice/sprint/<subject>")
def index(subject):
    if subject not in SUBJECT_LABELS:
        abort(404)
    from services.exam_sprint import load_sprint_view

    return render_template(
        "practice/exam_sprint.html",
        subject=subject,
        subject_label=SUBJECT_LABELS[subject],
        view=load_sprint_view(current_app.root_path, subject),
    )


@exam_sprint_bp.get("/practice/sprint/reading/<test_id>")
def reading_practice(test_id):
    from services.exam_sprint_store import load_ninefen_document

    payload = load_ninefen_document(current_app.root_path, "reading", test_id)
    if payload is None:
        abort(404)
    return render_template(
        "reading/test_practice.html",
        test=payload,
        practice_source="exam_sprint",
        practice_source_ref=test_id,
    )


@exam_sprint_bp.get("/practice/sprint/assets/<filename>")
def asset(filename):
    from services.exam_sprint import state_directory

    if not re.fullmatch(r"[a-f0-9]{64}\.(mp3|png|jpg|jpeg|webp|gif)", filename):
        abort(404)
    directory = state_directory(current_app.root_path) / "assets"
    path = directory / filename
    if path.is_symlink() or not path.is_file():
        abort(404)
    response = send_from_directory(directory, filename, conditional=True, max_age=31536000)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
