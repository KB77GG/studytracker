"""Compose immutable 40-question mock papers from verified weekly sprint entries."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

from services.exam_sprint import _local_target, state_directory
from services.exam_sprint_catalog import load_sprint_catalog
from services.exam_sprint_store import _immutable_bytes

PAPER_ID = re.compile(r"sprint_(reading|listening)_([a-f0-9]{24})\Z")
PARTS = {"reading": 3, "listening": 4}


class SprintPaperError(ValueError):
    """An incomplete or changed selection must not become a mock paper."""


def _bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def _rewrite(value, ids):
    if isinstance(value, str):
        return re.sub(r"\$([^$\s]+)\$", lambda m: f"${ids.get(m[1], m[1])}$", value)
    if isinstance(value, list):
        return [_rewrite(item, ids) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite(item, ids) for key, item in value.items()}
    return value


def _number_references(text, numbers):
    # Only explicit question/answer-box labels; never rewrite dates or quantities.
    pattern = r"\b(Questions?|boxes?)\s+(\d+)(?:\s*([–—-]|to|and)\s*(\d+))?"

    def replace(match):
        first = numbers.get(int(match[2]), int(match[2]))
        last = numbers.get(int(match[4]), int(match[4])) if match[4] else None
        return f"{match[1]} {first}" + (f"{match[3]}{last}" if last is not None else "")

    return re.sub(pattern, replace, str(text or ""), flags=re.I)


def _unit(payload, subject, item, part, offset):
    if subject == "reading":
        matches = [p for p in payload.get("passages", []) if p.get("passage") == item["passage"]]
        if len(matches) != 1:
            raise SprintPaperError("所选阅读篇章已不可用，请重新选题。")
        unit = deepcopy(matches[0])
    else:
        unit = deepcopy(payload)
        unit["section"] = part
        unit["id"] = f"sprint_section_{part}"
        audio = (unit.get("audio") or {}).get("local_path")
        if not audio:
            raise SprintPaperError("所选听力缺少音频，请重新选题。")
        unit["audio"] = audio if audio.startswith("/") else f"/static/listening_jijing/{audio}"
        # The source part contains a transcript; mock rendering removes teaching fields.
        unit["transcript"] = unit.pop("content", "")
        for group in unit.get("groups", []):
            group["questions"] = group.pop("items", [])
            group["collect_option"] = group.pop("collect_options", {"list": []})
    groups = unit.get("groups") or []
    questions = [q for group in groups for q in group.get("questions", [])]
    if not questions:
        raise SprintPaperError("所选题目没有可用试题。")
    ids, numbers = {}, {}
    for index, question in enumerate(questions, offset + 1):
        old_id = str(question.get("id") or question.get("number") or "")
        old_number = question.get("number")
        if not old_id or old_id in ids or type(old_number) is not int or old_number in numbers:
            raise SprintPaperError("所选题目的编号重复或不完整，请重新选题。")
        if not str(question.get("answer") or "").strip():
            raise SprintPaperError("所选题目缺少已核验答案。")
        ids[old_id] = f"s{part}_{old_id}"
        numbers[old_number] = index
    unit = _rewrite(unit, ids)
    for group in unit["groups"]:
        group.pop("answer_key", None)
        for key in ("desc", "title", "question_title"):
            if key in group:
                group[key] = _number_references(group[key], numbers)
        for question in group["questions"]:
            old_id = str(question.get("id") or question["number"])
            question["source_question_id"] = question.get("source_question_id") or old_id
            question["id"] = ids[old_id]
            question["source_number"] = question["number"]
            question["number"] = numbers[question["number"]]
    if subject == "reading":
        unit["passage"] = part
    source_range = f"{min(numbers)}–{max(numbers)}"
    current_range = f"{offset + 1}–{offset + len(questions)}"
    unit["title"] = item["title"]
    if source_range != current_range:
        unit["title"] += f"（原题 {source_range} → 本卷 {current_range}）"
    if isinstance(unit.get("question_name"), str):
        unit["question_name"] = _number_references(unit["question_name"], numbers)
    unit["question_count"] = len(questions)
    unit.pop("answer_key", None)
    return unit


def compose_sprint_paper(root, subject, selections, *, catalog=None):
    """Build in memory first. Selection values are exact versioned picker IDs."""
    if subject not in PARTS or len(selections) != PARTS[subject]:
        raise SprintPaperError("请为每个 Part / Passage 各选一道热榜题。")
    catalog = catalog or load_sprint_catalog(root, subject)
    units, sources, seen = [], [], set()
    offset = 0
    for part, selection in enumerate(selections, 1):
        group = next((g for g in catalog["groups"] if g["part"] == part), {})
        choices = [item for item in group.get("items", []) if item["selection_id"] == selection]
        if len(choices) != 1 or choices[0]["source_id"] in seen:
            raise SprintPaperError("热榜已更新或所选题目不属于该部分，请刷新后重新选题。")
        item = choices[0]
        seen.add(item["source_id"])
        resolved = _local_target(Path(root), item["mapping"])
        if not resolved:
            raise SprintPaperError("所选题目或音频校验失败，请重新选题。")
        unit = _unit(resolved[0], subject, item, part, offset)
        offset += unit["question_count"]
        units.append(unit)
        sources.append(
            {
                "part": part,
                "selection_id": selection,
                "title": item["title"],
                "mapping": deepcopy(item["mapping"]),
            }
        )
    if offset != 40:
        raise SprintPaperError(
            f"当前{('听力' if subject == 'listening' else '阅读')}共 {offset} 题；模考需要 40 题，请调整所选篇章。"
        )
    return {
        "schema_version": 1,
        "source": "exam_sprint_paper",
        "subject": subject,
        "title": f"7天热榜 · {('听力' if subject == 'listening' else '阅读')}模考",
        "edition": catalog.get("updated_at_label", ""),
        "sources": sources,
        "question_count": 40,
        "sections" if subject == "listening" else "passages": units,
    }


def save_sprint_paper(root, payload):
    subject = payload["subject"]
    digest = hashlib.sha256(_bytes(payload)).hexdigest()
    test_id = f"sprint_{subject}_{digest[:24]}"
    folder = state_directory(root) / "papers"
    if folder.is_symlink():
        raise SprintPaperError("组卷保存目录不可用。")
    path = folder / f"{test_id}.json"
    _immutable_bytes(path, _bytes({**payload, "id": test_id}))
    return test_id


def load_sprint_paper(root, subject, test_id):
    match = PAPER_ID.fullmatch(str(test_id))
    if not match or match[1] != subject:
        return None
    folder = state_directory(root) / "papers"
    path = folder / f"{test_id}.json"
    if folder.is_symlink() or path.is_symlink():
        return None
    try:
        payload = json.loads(path.read_bytes())
        if not isinstance(payload, dict):
            return None
        candidate = dict(payload)
        candidate.pop("id", None)
        if (
            payload.get("id") != test_id
            or payload.get("subject") != subject
            or payload.get("source") != "exam_sprint_paper"
            or hashlib.sha256(_bytes(candidate)).hexdigest()[:24] != match[2]
        ):
            return None
        return payload, path
    except (OSError, ValueError, TypeError):
        return None
