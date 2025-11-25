from datetime import date, datetime
from pathlib import Path
from secrets import token_urlsafe

from flask import current_app, jsonify, request
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from models import (
    PlanEvidence,
    PlanItem,
    PlanItemSession,
    StudyPlan,
    User,
    StudentProfile,
    ParentStudentLink,
    db,
)

from . import api_bp
from .auth_utils import require_api_user

MAX_STUDENT_RESETS = 2

ALLOWED_EVIDENCE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "pdf",
    "mp3",
    "mp4",
    "wav",
    "doc",
    "docx",
}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
AUDIO_EXTENSIONS = {"mp3", "mp4", "wav"}


def _get_upload_root() -> Path:
    base = current_app.config.get("UPLOAD_FOLDER")
    if base:
        root = Path(base)
    else:
        root = Path(current_app.root_path) / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _item_payload(item: PlanItem) -> dict:
    sessions = [
        sess for sess in item.sessions if not getattr(sess, "is_deleted", False)
    ]
    evidences = [
        ev for ev in item.evidences if not getattr(ev, "is_deleted", False)
    ]
    return {
        "id": item.id,
        "task_name": item.task_name,
        "module": item.module,
        "planned_minutes": item.planned_minutes,
        "actual_seconds": item.actual_seconds or 0,
        "manual_minutes": item.manual_minutes or 0,
        "student_status": item.student_status,
        "review_status": item.review_status,
        "review_comment": item.review_comment,
        "student_comment": item.student_comment,
        "submitted_at": item.submitted_at.isoformat() if item.submitted_at else None,
        "student_reset_count": item.student_reset_count,
        "max_student_resets": MAX_STUDENT_RESETS,
        "evidence_policy": item.evidence_policy,
        "sessions": [
            {
                "id": sess.id,
                "started_at": sess.started_at.isoformat(),
                "ended_at": sess.ended_at.isoformat() if sess.ended_at else None,
                "duration_seconds": sess.duration_seconds,
            }
            for sess in sessions
        ],
        "evidence": [
            {
                "id": ev.id,
                "file_type": ev.file_type,
                "note": ev.note,
                "text_content": ev.text_content,
            }
            for ev in evidences
        ],
    }


@api_bp.get("/me")
@require_api_user()
def api_me():
    user: User = request.current_api_user
    profile = None
    children = []
    if user.role == User.ROLE_STUDENT and user.student_profile:
        profile = {
            "student_id": user.student_profile.id,
            "full_name": user.student_profile.full_name,
            "guardian_token": user.student_profile.guardian_view_token,
        }
    elif user.role == User.ROLE_PARENT:
        # Use ParentStudentLink to find children
        links = ParentStudentLink.query.filter_by(
            parent_id=user.id,
            is_active=True
        ).all()
        
        updated = False
        for link in links:
            # Find student profile by name
            kid = StudentProfile.query.filter_by(
                full_name=link.student_name,
                is_deleted=False
            ).first()
            
            if kid:
                if not kid.guardian_view_token:
                    kid.guardian_view_token = token_urlsafe(16)
                    updated = True
                children.append(
                    {
                        "student_id": kid.id,
                        "full_name": kid.full_name,
                        "guardian_token": kid.guardian_view_token,
                    }
                )
        if updated:
            db.session.commit()
    return jsonify(
        {
            "ok": True,
            "data": {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role,
                "profile": profile,
                "children": children,
            },
        }
    )


@api_bp.get("/students/<int:student_id>/plans/today")
@require_api_user(User.ROLE_STUDENT, User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def api_student_plan_today(student_id: int):
    user: User = request.current_api_user
    if user.role == User.ROLE_STUDENT:
        student_profile = user.student_profile
        if not student_profile or student_profile.id != student_id:
            return jsonify({"ok": False, "error": "forbidden_student"}), 403

    plan = (
        StudyPlan.query.filter(
            StudyPlan.student_id == student_id,
            StudyPlan.plan_date == date.today(),
            StudyPlan.is_deleted.is_(False),
        )
        .options(
            joinedload(StudyPlan.items).joinedload(PlanItem.sessions),
            joinedload(StudyPlan.items).joinedload(PlanItem.evidences),
        )
        .first()
    )
    if not plan:
        return jsonify({"ok": True, "data": None})

    return jsonify(
        {
            "ok": True,
            "data": {
                "plan_id": plan.id,
                "plan_date": plan.plan_date.isoformat(),
                "notes": plan.notes,
                "items": [
                    _item_payload(item) for item in plan.items if not item.is_deleted
                ],
            },
        }
    )


def _load_plan_item_for_student(item_id: int, user: User) -> PlanItem | None:
    item = (
        PlanItem.query.options(
            joinedload(PlanItem.plan),
            joinedload(PlanItem.sessions),
            joinedload(PlanItem.evidences),
        )
        .filter(PlanItem.id == item_id, PlanItem.is_deleted.is_(False))
        .first()
    )
    if not item:
        return None
    profile = user.student_profile
    if not profile or profile.id != item.plan.student_id or profile.is_deleted:
        return None
    return item


@api_bp.post("/students/plan-items/<int:item_id>/timer/start")
@require_api_user(User.ROLE_STUDENT)
def api_student_timer_start(item_id: int):
    user: User = request.current_api_user
    item = _load_plan_item_for_student(item_id, user)
    if not item:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    now = datetime.utcnow()
    session = PlanItemSession(
        plan_item=item,
        started_at=now,
        created_by=user.id,
        source="timer",
    )
    db.session.add(session)
    if item.student_status == PlanItem.STUDENT_PENDING:
        item.student_status = PlanItem.STUDENT_IN_PROGRESS
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "data": {
                "session_id": session.id,
                "started_at": now.isoformat(),
            },
        }
    )


@api_bp.post("/students/plan-items/<int:item_id>/timer/<int:session_id>/stop")
@require_api_user(User.ROLE_STUDENT)
def api_student_timer_stop(item_id: int, session_id: int):
    user: User = request.current_api_user
    item = _load_plan_item_for_student(item_id, user)
    if not item:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    session = (
        PlanItemSession.query.filter_by(
            id=session_id,
            plan_item_id=item.id,
            created_by=user.id,
            is_deleted=False,
        ).first()
    )
    if not session:
        return jsonify({"ok": False, "error": "session_not_found"}), 404

    if session.ended_at:
        return jsonify(
            {
                "ok": True,
                "data": {
                    "actual_seconds": item.actual_seconds or 0,
                    "session_seconds": session.duration_seconds,
                },
            }
        )

    session.close(datetime.utcnow())
    item.actual_seconds = (item.actual_seconds or 0) + session.duration_seconds
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "data": {
                "actual_seconds": item.actual_seconds or 0,
                "session_seconds": session.duration_seconds,
            },
        }
    )


@api_bp.post("/students/plan-items/<int:item_id>/submit")
@require_api_user(User.ROLE_STUDENT)
def api_student_submit(item_id: int):
    user: User = request.current_api_user
    item = _load_plan_item_for_student(item_id, user)
    if not item:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    manual_minutes = data.get("manual_minutes")
    try:
        manual_minutes = max(0, int(manual_minutes)) if manual_minutes is not None else 0
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_manual_minutes"}), 400
    comment = (data.get("comment") or "").strip()

    if manual_minutes:
        item.manual_minutes = manual_minutes
        manual_seconds = manual_minutes * 60
        if manual_seconds > (item.actual_seconds or 0):
            item.actual_seconds = manual_seconds
    if comment:
        item.student_comment = comment
    item.student_status = PlanItem.STUDENT_SUBMITTED
    item.submitted_at = datetime.utcnow()

    db.session.commit()
    return jsonify({"ok": True, "data": _item_payload(item)})


@api_bp.post("/students/plan-items/<int:item_id>/reset")
@require_api_user(User.ROLE_STUDENT)
def api_student_reset(item_id: int):
    user: User = request.current_api_user
    item = _load_plan_item_for_student(item_id, user)
    if not item:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if item.student_reset_count >= MAX_STUDENT_RESETS:
        return jsonify({"ok": False, "error": "reset_limit_reached"}), 400
    if item.review_status != PlanItem.REVIEW_PENDING:
        return jsonify({"ok": False, "error": "already_reviewed"}), 400

    item.student_status = PlanItem.STUDENT_PENDING
    item.submitted_at = None
    item.student_comment = None
    item.student_reset_count = (item.student_reset_count or 0) + 1
    db.session.commit()
    return jsonify({"ok": True, "data": _item_payload(item)})


@api_bp.post("/students/plan-items/<int:item_id>/evidence")
@require_api_user(User.ROLE_STUDENT)
def api_student_evidence(item_id: int):
    user: User = request.current_api_user
    item = _load_plan_item_for_student(item_id, user)
    if not item:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    policy = item.evidence_policy or PlanItem.EVIDENCE_OPTIONAL

    if request.is_json:
        data = request.get_json(silent=True) or {}
        text_value = (data.get("text") or "").strip()
        if not text_value:
            return jsonify({"ok": False, "error": "empty_text"}), 400
        if policy not in {
            PlanItem.EVIDENCE_TEXT,
            PlanItem.EVIDENCE_REQUIRED,
            PlanItem.EVIDENCE_OPTIONAL,
        }:
            return jsonify({"ok": False, "error": "text_not_allowed"}), 400
        storage_path = f"text://{item.id}/{token_urlsafe(8)}"
        evidence = PlanEvidence(
            plan_item=item,
            uploader_id=user.id,
            file_type="text",
            storage_path=storage_path,
            file_size=len(text_value.encode("utf-8")),
            text_content=text_value,
        )
    else:
        if "file" not in request.files:
            return jsonify({"ok": False, "error": "missing_file"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"ok": False, "error": "empty_filename"}), 400
        extension = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        if extension not in ALLOWED_EVIDENCE_EXTENSIONS:
            return jsonify({"ok": False, "error": "invalid_extension"}), 400
        if policy == PlanItem.EVIDENCE_IMAGE and extension not in IMAGE_EXTENSIONS:
            return jsonify({"ok": False, "error": "expect_image"}), 400
        if policy == PlanItem.EVIDENCE_AUDIO and extension not in AUDIO_EXTENSIONS:
            return jsonify({"ok": False, "error": "expect_audio"}), 400

        filename = secure_filename(file.filename)
        upload_root = _get_upload_root()
        student_dir = upload_root / f"student_{item.plan.student_id}"
        student_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{item.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
        save_path = student_dir / stored_name
        file.save(save_path)

        evidence = PlanEvidence(
            plan_item=item,
            uploader_id=user.id,
            file_type=extension,
            storage_path=str(save_path),
            original_filename=filename,
            file_size=save_path.stat().st_size,
        )
    db.session.add(evidence)
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "data": {
                "id": evidence.id,
                "file_type": evidence.file_type,
                "original_filename": evidence.original_filename,
                "text_content": evidence.text_content,
            },
        }
    )
