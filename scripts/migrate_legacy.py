#!/usr/bin/env python3
"""
Bootstrap the new study workflow schema from legacy Task data.

Usage:
    python3 scripts/migrate_legacy.py

The script is idempotent: it only creates records that are missing.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime

from sqlalchemy import exists
from sqlalchemy.exc import IntegrityError

from app import app, db
from models import (
    PlanItem,
    PlanReviewLog,
    StudentProfile,
    StudyPlan,
    Task,
    TaskCatalog,
    TeacherStudentLink,
    User,
)


def normalize_category(value: str | None):
    if not value:
        return ("未分类", "未分模块", "未命名任务")
    normalized = value.replace("—", "-").replace("－", "-")
    parts = [p.strip() for p in normalized.split("-") if p.strip()]
    if len(parts) == 1:
        return (parts[0], "未分模块", parts[0])
    if len(parts) == 2:
        return (parts[0], parts[1], parts[1])
    exam, module, *rest = parts
    task_name = "-".join(rest) if rest else module
    return (exam, module, task_name)


def ensure_catalog(exam: str, module: str, task_name: str, default_minutes: int, creator_id: int | None):
    catalog = TaskCatalog.query.filter_by(
        exam_system=exam,
        module=module,
        task_name=task_name,
        is_deleted=False,
    ).first()
    if catalog:
        return catalog
    catalog = TaskCatalog(
        exam_system=exam,
        module=module,
        task_name=task_name,
        default_minutes=default_minutes or 0,
        created_by=creator_id,
    )
    db.session.add(catalog)
    db.session.flush()
    return catalog


def pick_teacher(student_tasks):
    for task in student_tasks:
        if task.created_by:
            user = User.query.get(task.created_by)
            if user and user.role in {User.ROLE_TEACHER, User.ROLE_ASSISTANT, User.ROLE_ADMIN}:
                return user.id
    fallback = (
        User.query.filter(User.role.in_([User.ROLE_TEACHER, User.ROLE_ASSISTANT, User.ROLE_ADMIN]))
        .order_by(User.id.asc())
        .first()
    )
    return fallback.id if fallback else None


def main():
    created_students = 0
    linked_students = 0
    created_plans = 0
    created_items = 0
    updated_items = 0

    with app.app_context():
        db.create_all()

        legacy_tasks = Task.query.order_by(Task.date.asc(), Task.id.asc()).all()
        if not legacy_tasks:
            print("No legacy tasks found; nothing to migrate.")
            return 0

        student_groups = defaultdict(list)
        for task in legacy_tasks:
            student_key = (task.student_name or "未填写学生").strip()
            student_groups[student_key].append(task)

        print(f"Found {len(student_groups)} distinct students across {len(legacy_tasks)} tasks.")

        # Seed StudentProfile
        student_profiles = {}
        for student_name, tasks in student_groups.items():
            profile = (
                StudentProfile.query.filter_by(full_name=student_name, is_deleted=False).first()
            )
            if not profile:
                profile = StudentProfile(full_name=student_name)
                db.session.add(profile)
                db.session.flush()
                created_students += 1
            student_profiles[student_name] = profile

            teacher_id = pick_teacher(tasks)
            if teacher_id and not db.session.query(
                exists().where(
                    TeacherStudentLink.teacher_id == teacher_id,
                    TeacherStudentLink.student_id == profile.id,
                )
            ).scalar():
                link = TeacherStudentLink(
                    teacher_id=teacher_id,
                    student_id=profile.id,
                    role="coach",
                    is_primary=True,
                    created_by=teacher_id,
                )
                db.session.add(link)
                linked_students += 1

        db.session.flush()

        plan_cache: dict[tuple[int, datetime.date], StudyPlan] = {}

        for task in legacy_tasks:
            student_name = (task.student_name or "未填写学生").strip()
            profile = student_profiles[student_name]
            try:
                plan_date = datetime.strptime(task.date, "%Y-%m-%d").date() if task.date else datetime.utcnow().date()
            except (ValueError, TypeError):
                plan_date = datetime.utcnow().date()

            plan_key = (profile.id, plan_date)
            plan = plan_cache.get(plan_key)
            if not plan:
                plan = (
                    StudyPlan.query.filter_by(
                        student_id=profile.id,
                        plan_date=plan_date,
                        is_deleted=False,
                    ).first()
                )
                if not plan:
                    creator_id = pick_teacher(student_groups[student_name])
                    if not creator_id:
                        # Fall back to first active user
                        fallback_user = User.query.filter_by(is_active=True).order_by(User.id.asc()).first()
                        creator_id = fallback_user.id if fallback_user else None
                    if not creator_id:
                        print(f"Warning: no teacher/admin user available for plan on {plan_date} ({student_name}); skipping.")
                        continue
                    plan = StudyPlan(
                        student_id=profile.id,
                        plan_date=plan_date,
                        status=StudyPlan.STATUS_PUBLISHED,
                        created_by=creator_id,
                        published_by=creator_id,
                        published_at=datetime.utcnow(),
                    )
                    db.session.add(plan)
                    created_plans += 1
                plan_cache[plan_key] = plan

            # Avoid duplicating items if we already migrated this task
            existing_item = (
                PlanItem.query.filter_by(
                    plan_id=plan.id,
                    task_name=task.category or task.detail,
                    custom_title=task.detail,
                    is_deleted=False,
                ).first()
            )
            if existing_item:
                updated_items += 1
                continue

            exam, module, task_name = normalize_category(task.category)
            catalog = ensure_catalog(
                exam=exam,
                module=module,
                task_name=task_name,
                default_minutes=task.planned_minutes or 0,
                creator_id=plan.created_by,
            )

            review_status = PlanItem.REVIEW_PENDING
            student_status = PlanItem.STUDENT_PENDING
            review_by = None
            review_at = None
            review_comment = None

            if task.status == "done":
                review_status = PlanItem.REVIEW_APPROVED
                student_status = PlanItem.STUDENT_SUBMITTED
                review_by = plan.created_by
                review_at = datetime.utcnow()
                review_comment = task.note or ""
            elif task.status == "progress":
                student_status = PlanItem.STUDENT_IN_PROGRESS

            order_index = len(plan.items) if plan.items else 0
            plan_item = PlanItem(
                plan=plan,
                catalog_id=catalog.id,
                exam_system=exam,
                module=module,
                task_name=task_name,
                custom_title=task.detail,
                instructions=task.note,
                order_index=order_index,
                planned_minutes=task.planned_minutes or (catalog.default_minutes or 0),
                actual_seconds=task.actual_seconds or 0,
                student_status=student_status,
                review_status=review_status,
                review_by=review_by,
                review_at=review_at,
                review_comment=review_comment,
            )
            db.session.add(plan_item)
            created_items += 1

            if review_status in (PlanItem.REVIEW_APPROVED, PlanItem.REVIEW_PARTIAL, PlanItem.REVIEW_REJECTED):
                log = PlanReviewLog(
                    plan_item=plan_item,
                    reviewer_id=review_by,
                    from_status=PlanItem.REVIEW_PENDING,
                    to_status=review_status,
                    comment=review_comment,
                    decided_at=review_at or datetime.utcnow(),
                    originated_from="migration",
                )
                db.session.add(log)

        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            print("Migration aborted due to integrity error:", exc, file=sys.stderr)
            return 1

        print(
            f"Done. Students created: {created_students}, "
            f"teacher links added: {linked_students}, plans created: {created_plans}, "
            f"plan items created: {created_items}, legacy duplicates skipped: {updated_items}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
