"""Allocate a finite calendar from explicit queues, skipping occupied content."""

from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace

from models import DictationBook, DictationWord, db
from services import task_planner as planner
from services import task_planner_resources as resources
from services.task_planner_history import HistoryIndex
from services.task_planner_vocabulary import selected_books


def _words(activity):
    selection = activity["selection"]
    start_id = planner._integer(selection.get("book_id"), "起始分册")
    start = planner._integer(selection.get("word_start"), "开始词序")
    if "book_ids" in selection:
        books = selected_books(selection)
    else:
        book = db.session.get(DictationBook, start_id)
        if not book or book.is_deleted or not book.is_active:
            raise planner.TaskPlannerError("词书不存在或已停用")
        books = [book]
    ids = [book.id for book in books]
    values = defaultdict(list)
    for book_id, sequence in DictationWord.query.with_entities(DictationWord.book_id, DictationWord.sequence).filter(
        DictationWord.book_id.in_(ids)
    ).order_by(DictationWord.book_id, DictationWord.sequence, DictationWord.id):
        values[book_id].append(sequence)
    for book in books:
        seqs = values[book.id]
        if not seqs or any(s is None or s < 1 for s in seqs) or len(seqs) != len(set(seqs)):
            raise planner.TaskPlannerError(f"分册“{book.title}”没有单词或存在无效/重复词序，请先整理")
    if start not in values[start_id]:
        raise planner.TaskPlannerError("开始词序在起始分册中不存在")
    for book in books[ids.index(start_id):]:
        for sequence in values[book.id]:
            if book.id == start_id and sequence < start:
                continue
            choice = {"book_id": book.id, "word_start": sequence, "word_end": sequence,
                      "vocabulary_goal": selection.get("vocabulary_goal") or "reading",
                      "dictation_mode": selection.get("dictation_mode") or "audio_to_en",
                      "dictation_order": selection.get("dictation_order") or "sequence"}
            yield {"kind": "dictation", "selections": [choice], "question_count": 0,
                   "label": f"{book.title} · 第{sequence}词"}


def _candidates(activity):
    from services import task_planner_series as series
    from services.task_planner_sequence import sequence_sources

    kind, selection = activity["kind"], activity["selection"]
    if kind == "dictation":
        yield from _words(activity)
        return
    if kind == "question_type":
        subject = selection.get("subject")
        standard_type = selection.get("standard_type") or "all"
        scope, start = activity.get("source_scope"), activity.get("start_group_id")
        if not scope or not start:
            raise planner.TaskPlannerError("请选择题型教材与起始题组")
        groups = [row for row in series._source_groups(subject, standard_type) if series._matches_scope(row, scope)]
        ids = [row["question_group_id"] for row in groups]
        if start not in ids:
            raise planner.TaskPlannerError("起始题组不属于所选范围，或已不可布置")
        for group in groups[ids.index(start):]:
            yield {"kind": kind, "selections": [{"subject": subject, "standard_type": standard_type,
                    "group_ids": [group["question_group_id"]], "pace": selection.get("pace") or "training"}],
                   "label": series._group_label(group), "question_count": group["question_count"]}
        return
    items = sequence_sources(kind, selection, activity["source_scopes"])["items"]
    ids = [row["id"] for row in items]
    if activity["start_resource_id"] not in ids:
        raise planner.TaskPlannerError("起始内容不属于所选教材或已不可布置")
    for item in items[ids.index(activity["start_resource_id"]):]:
        candidate = {"kind": item.get("task_kind", kind),
                     "selections": item.get("selections") or [item["selection"]],
                     "label": item["label"], "question_count": item.get("question_count", 0)}
        if kind == "reading_test":
            source = resources._reading_payload(item["selections"][0]["test_id"])
            counts = {int(passage.get("passage") or index): sum(len(group["questions"]) for group in passage["groups"])
                      for index, passage in enumerate(source["passages"], 1)}
            candidate["question_counts"] = [counts[choice["passage_number"]] for choice in item["selections"]]
        yield candidate


def _merge(parts, kind):
    """Combine a day's groups or adjacent available words into native tasks."""
    result = []
    for row in parts:
        if result and kind == "question_type":
            previous = result[-1]
            previous["selection"]["group_ids"].extend(row["selection"]["group_ids"])
        elif result and kind == "dictation" and (
            result[-1]["selection"]["book_id"] == row["selection"]["book_id"]
            and result[-1]["selection"]["word_end"] + 1 == row["selection"]["word_start"]
        ):
            previous = result[-1]
            previous["selection"]["word_end"] = row["selection"]["word_end"]
        else:
            result.append(row)
            continue
        previous["unit_count"] += row["unit_count"]
        previous["question_count"] += row["question_count"]
        previous["content_labels"].extend(row["content_labels"])
    return result


def allocate_requests(requests, profile, skip_assigned=True):
    """No writes. Queues are independent; reservations cover the entire batch."""
    history = HistoryIndex(profile)
    batch = HistoryIndex()
    queues, skipped, rows, prepared_rows = {}, [], [], []
    for request in requests:
        activity = request["activity"]
        activity_id = request["activity_id"]
        if activity_id not in queues:
            queues[activity_id] = iter(_candidates(activity))
        day = request["target_date"].isoformat()
        parts, accepted = [], 0
        while accepted < request["quantity"]:
            candidate = next(queues[activity_id], None)
            if candidate is None:
                missing = request["quantity"] - accepted
                raise planner.TaskPlannerError(
                    f"{day}“{activity.get('name') or '连续学习'}”剩余可用内容不足，还缺{missing}"
                    f"{'词' if activity['kind'] == 'dictation' else '项'}；请补充教材、调整起点或减少安排数量"
                )
            if candidate["kind"] == "dictation":
                # The queue was read from actual validated rows. Check occupied
                # ranges cheaply, then freeze/validate the merged native task.
                choice = candidate["selections"][0]
                prepared = [{"kind": "dictation", "title": candidate["label"], "selection": choice,
                             "duplicate_payload": {"dictation_book_id": choice["book_id"],
                                                   "word_start": choice["word_start"],
                                                   "word_end": choice["word_end"]}}]
            else:
                prepared = [resources.prepare_resource(candidate["kind"], choice) for choice in candidate["selections"]]
            reason = next((reason for item in prepared if (reason := history.reason(item))), None)
            if reason and skip_assigned:
                skipped.append({"title": candidate["label"], "reason": reason, "activity_id": activity_id,
                                "activity_name": activity.get("name", ""), "target_date": day})
                continue
            # Existing explicit repeat policy remains in force when auto-skip is off.
            for item in prepared:
                if batch.reason(item):
                    raise planner.TaskPlannerError("本批安排包含重复内容，请开启自动跳过或调整教材", status=409)
                history.reserve(item)
                batch.reserve(item)
            for index, item in enumerate(prepared):
                parts.append({"target_date": day, "kind": candidate["kind"], "title": item["title"],
                              "selection": dict(item["selection"]), "unit_count": int(index == 0),
                              "question_count": (candidate["question_counts"][index] if "question_counts" in candidate
                                                 else candidate["question_count"] if index == 0 else 0),
                              "content_labels": [item["title"]], "activity_id": activity_id,
                              "activity_name": activity.get("name", ""),
                              "planned_minutes": activity.get("planned_minutes", 20),
                              "note": activity.get("note", "")})
                if activity["kind"] == "reading_test":
                    parts[-1]["bundle_id"] = f"{activity_id}:{day}:{item['selection']['test_id']}"
            accepted += 1
        for row in _merge(parts, activity["kind"]):
            prepared = resources.prepare_resource(row["kind"], row["selection"])
            planner._conflicts(SimpleNamespace(id=None, student_id=profile.id,
                                               target_date=request["target_date"]), prepared, profile)
            row["title"] = prepared["title"]
            if row["kind"] == "dictation":
                row["content_labels"] = [prepared["title"]]
            rows.append(row)
            prepared_rows.append(prepared)
    return rows, prepared_rows, skipped
