"""Shared legacy Task submission projection into its linked PlanItem.

The caller owns the transaction. Keep the legacy metadata, duration and evidence
semantics here so web and mini-program submissions update the same records.
"""

import json
import os
from datetime import datetime

from models import PlanEvidence, PlanItem, db

VALID_DICTATION_ORDERS = {"sequence", "random"}


def resolve_task_dictation_order(task):
    order = (getattr(task, "dictation_order", "") or "").strip().lower()
    return order if order in VALID_DICTATION_ORDERS else "sequence"


def sync_plan_item_from_task_submission(
    task, *, note=None, evidence_files=None, duration=0, uploader_id=None
):
    item = getattr(task, "plan_item", None)
    if not item:
        return None
    if getattr(task, "dictation_book_id", None):
        current_exam = item.exam_system or ""
        item.exam_system = (
            current_exam if current_exam not in {"", "未分类", "材料练习"} else "词汇"
        )
        item.module = "词汇"
        item.task_name = "单词默写"
        item.resource_type = PlanItem.RESOURCE_DICTATION
        item.resource_id = f"dictation_book:{task.dictation_book_id}"
        item.resource_metadata = json.dumps(
            {
                "vocabulary_goal": getattr(task, "vocabulary_goal", None),
                "learning_goal": getattr(task, "vocabulary_goal", None),
                "dictation_mode": getattr(task, "dictation_mode", None) or "audio_to_en",
                "dictation_order": resolve_task_dictation_order(task),
                "dictation_word_start": getattr(task, "dictation_word_start", None) or 1,
                "dictation_word_end": getattr(task, "dictation_word_end", None),
            },
            ensure_ascii=False,
        )
    item.student_status = PlanItem.STUDENT_SUBMITTED
    item.submitted_at = task.submitted_at or datetime.now()
    if note:
        item.student_comment = str(note)[:255]
    if duration and duration > 0:
        item.actual_seconds = max(int(item.actual_seconds or 0), int(duration))
    elif task.actual_seconds:
        item.actual_seconds = max(int(item.actual_seconds or 0), int(task.actual_seconds or 0))
    for file_url in evidence_files or []:
        file_type = "image"
        lower_url = str(file_url).lower()
        if lower_url.endswith((".mp3", ".wav", ".m4a")):
            file_type = "audio"
        elif lower_url.endswith((".pdf", ".doc", ".docx")):
            file_type = "doc"
        db.session.add(
            PlanEvidence(
                plan_item_id=item.id,
                uploader_id=uploader_id,
                file_type=file_type,
                storage_path=file_url,
                original_filename=os.path.basename(file_url),
            )
        )
    return item
