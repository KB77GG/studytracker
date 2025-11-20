from collections import defaultdict
from datetime import date, timedelta

from flask import jsonify, request
from sqlalchemy.orm import joinedload

from models import PlanItem, ScoreRecord, StudentProfile, StudyPlan

from . import api_bp


def _build_report(student: StudentProfile, start: date, end: date) -> dict:
    items = (
        PlanItem.query.join(StudyPlan)
        .filter(
            StudyPlan.student_id == student.id,
            StudyPlan.plan_date >= start,
            StudyPlan.plan_date <= end,
            StudyPlan.is_deleted.is_(False),
            PlanItem.is_deleted.is_(False),
        )
        .options(
            joinedload(PlanItem.plan),
            joinedload(PlanItem.evidences),
        )
        .order_by(StudyPlan.plan_date.asc(), PlanItem.order_index.asc())
        .all()
    )

    module_breakdown = defaultdict(lambda: {"planned": 0, "actual": 0})
    reviewed_count = 0
    pending_items = []
    daily_map = {}
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        daily_map[day] = {
            "date": day,
            "planned_minutes": 0,
            "actual_minutes": 0,
            "total_tasks": 0,
            "reviewed_tasks": 0,
            "submitted_tasks": 0,
            "tasks": [],
        }

    for item in items:
        planned = item.planned_minutes
        actual_minutes = int((item.actual_seconds or 0) / 60)
        module_breakdown[item.module]["planned"] += planned
        module_breakdown[item.module]["actual"] += actual_minutes
        if item.review_status in (
            PlanItem.REVIEW_APPROVED,
            PlanItem.REVIEW_PARTIAL,
            PlanItem.REVIEW_REJECTED,
        ):
            reviewed_count += 1
        if item.review_status == PlanItem.REVIEW_PENDING:
            pending_items.append(
                {
                    "date": item.plan.plan_date.isoformat(),
                    "module": item.module,
                    "task_name": item.task_name,
                    "student_status": item.student_status,
                    "planned_minutes": planned,
                }
            )

        day_entry = daily_map[item.plan.plan_date]
        day_entry["planned_minutes"] += planned
        day_entry["actual_minutes"] += actual_minutes
        day_entry["total_tasks"] += 1
        if item.student_status == PlanItem.STUDENT_SUBMITTED:
            day_entry["submitted_tasks"] += 1
        if item.review_status in (
            PlanItem.REVIEW_APPROVED,
            PlanItem.REVIEW_PARTIAL,
            PlanItem.REVIEW_REJECTED,
        ):
            day_entry["reviewed_tasks"] += 1

        has_evidence = any(not ev.is_deleted for ev in item.evidences)
        day_entry["tasks"].append(
            {
                "module": item.module,
                "task_name": item.task_name,
                "planned_minutes": planned,
                "actual_minutes": actual_minutes,
                "student_status": item.student_status,
                "review_status": item.review_status,
                "review_comment": item.review_comment,
                "has_evidence": has_evidence,
            }
        )

    scores = (
        ScoreRecord.query.filter(
            ScoreRecord.student_id == student.id,
            ScoreRecord.is_deleted.is_(False),
        )
        .order_by(ScoreRecord.taken_on.desc())
        .limit(5)
        .all()
    )

    weekday_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    daily = []
    for day in sorted(daily_map.keys()):
        entry = daily_map[day]
        total_tasks = entry["total_tasks"] or 1
        daily.append(
            {
                "date": day.isoformat(),
                "weekday": weekday_labels[day.weekday()],
                "planned_minutes": entry["planned_minutes"],
                "actual_minutes": entry["actual_minutes"],
                "completion_rate": round(
                    entry["reviewed_tasks"] * 100.0 / total_tasks, 1
                ),
                "submitted_rate": round(
                    entry["submitted_tasks"] * 100.0 / total_tasks, 1
                ),
                "tasks": entry["tasks"],
            }
        )

    return {
        "student": {"id": student.id, "name": student.full_name},
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "summary": {
            "planned_minutes": sum(item.planned_minutes for item in items),
            "actual_minutes": round(
                sum((item.actual_seconds or 0) for item in items) / 60
            ),
            "completion_rate": round(
                reviewed_count * 100.0 / len(items), 1
            )
            if items
            else 0.0,
            "pending_count": len(pending_items),
        },
        "module_breakdown": dict(module_breakdown),
        "daily": daily,
        "pending": pending_items[:10],
        "scores": [
            {
                "exam_system": score.exam_system,
                "assessment_name": score.assessment_name,
                "taken_on": score.taken_on.isoformat(),
                "total_score": score.total_score,
                "components": score.component_scores,
            }
            for score in scores
        ],
    }


@api_bp.get("/guardian/report")
def api_guardian_report():
    token = (request.args.get("token") or "").strip()
    if not token:
        return jsonify({"ok": False, "error": "missing_token"}), 400

    student = StudentProfile.query.filter_by(
        guardian_view_token=token, is_deleted=False
    ).first()
    if not student:
        return jsonify({"ok": False, "error": "invalid_token"}), 404

    end_date = date.today()
    start_date = end_date - timedelta(days=6)
    return jsonify(
        {"ok": True, "data": _build_report(student, start_date, end_date)}
    )
