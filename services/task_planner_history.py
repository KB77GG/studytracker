"""Strict, student-specific occupation of content for opt-in automatic plans.

This does not change the legacy explicit-reassignment policy. Load history once
per preview; compare stable identities and whole/part coverage without querying
the database for every candidate word or question group.
"""

from __future__ import annotations

import json

from models import Task
from models_task_planner import TaskPlannerEntry
from services import task_planner_resources as resources
from services.task_assignment_duplicates import (
    _overlap,
    resource_identity_from_payload,
    resource_identity_from_task,
)


def _json(value):
    try:
        result = json.loads(value or "{}")
        return result if isinstance(result, dict) else {}
    except (ValueError, TypeError):
        return {}


class HistoryIndex:
    def __init__(self, profile=None, exclude_entry_ids=(), exclude_task_ids=()):
        self.records = []
        self.canonical = {}
        self.groups = None
        if profile is None:
            return
        excluded = set(exclude_entry_ids)
        excluded_tasks = set(exclude_task_ids)
        for task in Task.query.filter_by(student_name=profile.full_name).all():
            if task.id in excluded_tasks or task.cancelled_at or task.status == Task.STATUS_CANCELLED:
                continue
            identity = self._identity(resource_identity_from_task(task))
            coverage = self._task_coverage(task)
            self.records.append((identity, coverage, "已经布置过"))
        for entry in TaskPlannerEntry.query.filter(
            TaskPlannerEntry.student_id == profile.id,
            TaskPlannerEntry.status.in_(["ready", "blocked", "failed"]),
        ).all():
            if entry.id not in excluded:
                self.reserve(_json(entry.prepared_json), "已确认的待布置内容")

    def _canonical_id(self, subject, value):
        key = (subject, value)
        if key not in self.canonical:
            try:
                if subject == "intensive":
                    canonical = resources._canonical_intensive_id(value)
                else:
                    loader = resources._reading_payload if subject == "reading" else resources._listening_payload
                    canonical = loader(value).get("id") or value
            except (ValueError, TypeError, KeyError):
                canonical = value
            self.canonical[key] = canonical
        return self.canonical[key]

    def _identity(self, identity):
        identity = dict(identity)
        base = identity["base"]
        if identity["kind"] == "reading" and base:
            identity["base"] = (self._canonical_id("reading", base[0]),)
        elif identity["kind"] == "listening" and len(base) == 2:
            subject = "listening" if base[0] == "cambridge_test" else "intensive"
            identity["base"] = (base[0], self._canonical_id(subject, base[1]))
        return identity

    def _coverage(self, rows):
        result = []
        for row in rows:
            if not isinstance(row, dict) or row.get("subject") not in {"reading", "listening"}:
                continue
            row = dict(row)
            row["test_id"] = self._canonical_id(row["subject"], str(row.get("test_id") or ""))
            try:
                row["unit_number"] = int(row["unit_number"]) if row.get("unit_number") else None
            except (ValueError, TypeError):
                row["unit_number"] = None
            result.append(row)
        return result

    def _task_coverage(self, task):
        snapshot = _json(task.question_ids)
        if task.grading_mode == "question_type_practice":
            refs = snapshot.get("group_refs") or []
            rows = [{"subject": snapshot.get("subject"), "test_id": ref.get("test_id"),
                     "unit_number": ref.get("unit_number"), "group_id": ref.get("question_group_id")}
                    for ref in refs if isinstance(ref, dict)]
            # Older snapshots may have stable group IDs but no coverage refs.
            known = {row.get("group_id") for row in rows}
            missing = set(snapshot.get("group_ids") or []) - known
            if missing:
                if self.groups is None:
                    self.groups = {row["question_group_id"]: row for row in resources._groups()}
                for group_id in sorted(missing):
                    group = self.groups.get(group_id)
                    if group:
                        rows.append({"subject": group["subject"], "test_id": group["test_id"],
                                     "unit_number": group["unit_number"], "group_id": group_id})
            return self._coverage(rows)
        if task.reading_test_id:
            return self._coverage([{"subject": "reading", "test_id": task.reading_test_id,
                                    "unit_number": task.reading_passage_number, "whole": True}])
        if task.listening_resource_type == "cambridge_test" and task.listening_exercise_id:
            return self._coverage([{"subject": "listening", "test_id": task.listening_exercise_id,
                                    "unit_number": snapshot.get("listening_section_number"), "whole": True}])
        return []

    def descriptor(self, prepared):
        return (self._identity(resource_identity_from_payload(prepared.get("duplicate_payload"))),
                self._coverage(prepared.get("coverage_units") or []))

    @staticmethod
    def _matches(left, right):
        if _overlap(left, right):
            return True
        # A group's identity survives a change to its display/type label.
        if left["kind"] == right["kind"] == "question_type":
            return (left["base"][:1] == right["base"][:1]
                    and bool((left["units"] or set()) & (right["units"] or set())))
        # Open-ended historic vocabulary ranges must not look like new words.
        return (left["kind"] == right["kind"] == "dictation"
                and left["base"] == right["base"] and not right["range"])

    def reason(self, prepared):
        identity, coverage = self.descriptor(prepared)
        for old_identity, old_coverage, reason in self.records:
            if self._matches(identity, old_identity) or resources._coverage_overlap(coverage, old_coverage):
                return reason
        return None

    def reserve(self, prepared, reason="本批安排已使用"):
        identity, coverage = self.descriptor(prepared)
        if self.records and identity["kind"] == "dictation" and identity["range"]:
            last, _coverage, last_reason = self.records[-1]
            if (last_reason == reason and last["kind"] == "dictation"
                    and last["base"] == identity["base"] and last["range"]
                    and last["range"][1] + 1 == identity["range"][0]):
                last["range"] = (last["range"][0], identity["range"][1])
                return
        self.records.append((identity, coverage, reason))


def strict_conflict_reason(prepared, profile, exclude_entry_ids=()):
    return HistoryIndex(profile, exclude_entry_ids).reason(prepared)
