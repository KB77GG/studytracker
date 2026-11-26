"""Student-facing guidance for assignments completed on the practice website."""

from flask import current_app

from models import PlanItem, Task
from services.exam_sprint_student import ninefen_reading_task_path
from services.question_type_assignments import assignment_url as question_type_url
from services.writing_assignments import assignment_url as writing_url

WEB_PRACTICE_INSTRUCTION = "请前往刷题网页练习，完成后结果会同步至家长端。"
PLAN_RESOURCE_MODES = {
    "writing_exercise": "writing_practice",
    "writing_mother_topic": "writing_practice",
    "question_type_practice": "question_type_practice",
}


def web_practice_payload(task):
    """Return guidance even for an invalid binding, never a generic submit path."""
    if isinstance(task, PlanItem):
        linked = Task.query.filter_by(plan_item_id=task.id).first()
        if linked:
            practice = web_practice_payload(linked)
            if practice:
                return practice
        return _guidance(PLAN_RESOURCE_MODES.get(task.resource_type), None)
    mode = getattr(task, "grading_mode", None)
    if mode == "writing_practice":
        path = writing_url(task)
    elif mode == "question_type_practice":
        path = question_type_url(task)
    elif str(getattr(task, "reading_test_id", "") or "").startswith("ninefen_"):
        mode = "exam_sprint_reading"
        path = ninefen_reading_task_path(current_app.root_path, task)
    else:
        return None
    return _guidance(mode, path)


def _guidance(mode, path):
    labels = {
        "writing_practice": "雅思写作练习",
        "question_type_practice": "题型专项练习",
        "exam_sprint_reading": "7天热榜阅读练习",
    }
    if mode not in labels:
        return None
    return {
        "kind": mode,
        "label": labels[mode],
        "instruction": WEB_PRACTICE_INSTRUCTION,
        "url": f"https://studytracker.xin{path}" if path else None,
    }


def web_practice_required(task):
    practice = web_practice_payload(task)
    if not practice:
        return None
    return {
        "ok": False,
        "error": "web_practice_required",
        "message": WEB_PRACTICE_INSTRUCTION,
        "web_practice": practice,
    }
