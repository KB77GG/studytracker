"""Teacher mock creation, including immutable weekly sprint composition."""

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from models import MockExam, db
from services.exam_sprint_catalog import load_sprint_catalog
from services.exam_sprint_papers import SprintPaperError, compose_sprint_paper, save_sprint_paper


def _minutes(name, default):
    try:
        return min(180, max(1, int(request.form.get(name) or default)))
    except (TypeError, ValueError):
        return default


def _selected_papers(catalogs, loaders):
    """Validate both subjects and writing before any files or exam are persisted."""
    ids, papers = {}, {}
    for subject in ("listening", "reading"):
        mode = request.form.get(f"{subject}_source", "existing")
        if mode == "sprint":
            selections = request.form.getlist(f"{subject}_sprint_part")
            papers[subject] = compose_sprint_paper(
                current_app.root_path, subject, selections, catalog=catalogs[subject]
            )
        elif mode == "existing":
            test_id = request.form.get(f"{subject}_test_id", "").strip()
            if not test_id or not loaders[subject](test_id)[0]:
                raise SprintPaperError("请选择有效的听力和阅读题目。")
            ids[subject] = test_id
        else:
            raise SprintPaperError("请选择有效的题库来源。")
    writing = request.form.get("writing_test_id", "").strip()
    if writing and not loaders["writing"](writing)[0]:
        raise SprintPaperError("所选写作题目不存在。")
    return ids, papers, writing


def create_mock_exam():
    from app import (
        _generate_mock_exam_pincode,
        _load_listening_test_payload,
        _load_reading_test_payload,
        _load_writing_test_payload,
        _mock_exam_listening_options,
        _mock_exam_reading_options,
        _mock_exam_writing_options,
    )

    catalogs = {s: load_sprint_catalog(current_app.root_path, s) for s in ("listening", "reading")}
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            if not name:
                raise SprintPaperError("请填写模考名称。")
            ids, papers, writing = _selected_papers(
                catalogs,
                {
                    "listening": _load_listening_test_payload,
                    "reading": _load_reading_test_payload,
                    "writing": _load_writing_test_payload,
                },
            )
            pincode = (
                request.form.get("pincode", "").strip().upper() or _generate_mock_exam_pincode()
            )
            if len(pincode) > 16 or not pincode.isascii() or not pincode.isalnum():
                raise SprintPaperError("Pincode须为1至16位字母或数字。")
            if MockExam.query.filter_by(pincode=pincode).first():
                raise SprintPaperError("Pincode已使用，请换一个。")
            for subject, paper in papers.items():
                ids[subject] = save_sprint_paper(current_app.root_path, paper)
            exam = MockExam(
                name=name,
                listening_test_id=ids["listening"],
                reading_test_id=ids["reading"],
                writing_test_id=writing or None,
                listening_minutes=_minutes("listening_minutes", 32),
                reading_minutes=_minutes("reading_minutes", 60),
                writing_minutes=_minutes("writing_minutes", 60),
                pincode=pincode,
                is_active=True,
                created_by=current_user.id,
            )
            db.session.add(exam)
            db.session.commit()
            flash(f"模考「{exam.name}」已创建，pincode：{exam.pincode}")
            return redirect(url_for("admin_mock_exams_index"))
        except SprintPaperError as exc:
            flash(str(exc))
    return render_template(
        "admin/mock_exams_form.html",
        exam=None,
        sprint_catalogs=catalogs,
        listening_options=_mock_exam_listening_options(),
        reading_options=_mock_exam_reading_options(),
        writing_options=_mock_exam_writing_options(),
        suggested_pincode=_generate_mock_exam_pincode(),
    )
