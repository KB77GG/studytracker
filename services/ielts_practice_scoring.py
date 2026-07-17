"""Pure IELTS listening/reading practice scoring helpers.

The web routes and the practice pages both need the same answer semantics:
combined ``Choose TWO`` groups award one mark per selected correct option,
while a single question with multiple correct options is all-or-nothing.
Keeping the server-side implementation here makes the submission endpoint
the only authority for persisted scores and gives tests a small import target.
"""

from __future__ import annotations

import re

READING_FULL_JUDGMENT_ANSWERS = {"YES", "NO", "NOT GIVEN", "TRUE", "FALSE"}
READING_SHORT_JUDGMENT_ANSWERS = {"Y", "N", "NG", "T", "F"}
READING_JUDGMENT_ALIASES = {
    "Y": "YES",
    "YES": "YES",
    "N": "NO",
    "NO": "NO",
    "NG": "NOT GIVEN",
    "NOTGIVEN": "NOT GIVEN",
    "NOT GIVEN": "NOT GIVEN",
    "T": "TRUE",
    "TRUE": "TRUE",
    "F": "FALSE",
    "FALSE": "FALSE",
}


def normalize_answer(value) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("‘", "'")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
    )


def clean_answer(value) -> str:
    text_value = normalize_answer(value)
    text_value = re.sub(r"[.,!?;:，。！？；：]", "", text_value)
    text_value = re.sub(r"\s+", " ", text_value)
    return text_value.strip()


def split_alternatives(answer) -> list[str]:
    return [
        clean_answer(part) for part in re.split(r"\s*/\s*", str(answer or "")) if clean_answer(part)
    ]


def split_letters(value) -> list[str]:
    letters = [
        part.strip().upper() for part in re.split(r"\s*[,/]\s*", str(value or "")) if part.strip()
    ]
    return list(dict.fromkeys(letters))


def is_letter_answer(answer) -> bool:
    letters = split_letters(answer)
    return bool(letters) and all(re.fullmatch(r"[A-Z]", letter) for letter in letters)


def _option_key(option: dict) -> str:
    return str(option.get("key") or option.get("title") or "").strip().upper()


def _option_states(options: list[dict], expected: list[str], submitted: list[str]) -> list[dict]:
    expected_set = set(expected)
    submitted_set = set(submitted)
    states = []
    for option in options or []:
        key = _option_key(option)
        if not key:
            continue
        if key in submitted_set and key in expected_set:
            state = "selected_correct"
            label = "选择正确"
        elif key in submitted_set:
            state = "selected_wrong"
            label = "选择错误"
        elif key in expected_set:
            state = "missed_correct"
            label = "正确答案/漏选"
        else:
            state = "unselected_wrong"
            label = "未选"
        states.append({"key": key, "status": state, "label": label})
    return states


def _status(awarded: int, marks: int) -> str:
    if awarded == marks:
        return "correct"
    if awarded > 0:
        return "partial"
    return "incorrect"


def _status_label(status: str, awarded: int, marks: int, *, over_limit: bool = False) -> str:
    if status == "correct":
        return f"✓ 选择正确 {awarded}/{marks}"
    if status == "partial":
        return f"部分正确 {awarded}/{marks}"
    if over_limit:
        return f"✕ 超出最多选择 {marks} 项，0/{marks}"
    return f"✕ 选择错误 0/{marks}"


def _result_feedback(
    *,
    answer,
    value,
    marks: int,
    awarded: int,
    options: list[dict] | None = None,
    expected: list[str] | None = None,
    submitted: list[str] | None = None,
    over_limit: bool = False,
    kind: str = "question",
) -> dict:
    expected = expected or []
    submitted = submitted or []
    status = _status(awarded, marks)
    return {
        "marks": marks,
        "awarded": awarded,
        "correct": status == "correct",
        "status": status,
        "status_label": _status_label(status, awarded, marks, over_limit=over_limit),
        "option_states": _option_states(options or [], expected, submitted),
        "max_selections": (
            marks if kind == "checkbox-set" else len(expected) if kind == "checkbox-exact" else None
        ),
        "selection_error": "too_many" if over_limit else None,
    }


def _grade_selection(
    answer,
    value,
    *,
    kind: str,
    marks: int,
    options: list[dict] | None = None,
) -> dict:
    expected = split_letters(answer)
    submitted = split_letters(value)
    if kind == "checkbox-set":
        over_limit = len(submitted) > marks
        awarded = 0 if over_limit else min(marks, len(set(submitted) & set(expected)))
        return _result_feedback(
            answer=answer,
            value=value,
            marks=marks,
            awarded=awarded,
            options=options,
            expected=expected,
            submitted=submitted,
            over_limit=over_limit,
            kind=kind,
        )

    exact = len(submitted) == len(expected) and set(submitted) == set(expected)
    awarded = marks if expected and exact else 0
    return _result_feedback(
        answer=answer,
        value=value,
        marks=marks,
        awarded=awarded,
        options=options,
        expected=expected,
        submitted=submitted,
        kind=kind,
    )


def grade_answer(
    answer,
    value,
    *,
    kind: str = "question",
    marks: int = 1,
    options: list[dict] | None = None,
) -> dict:
    marks = max(1, int(marks or 1))
    if kind in {"checkbox-set", "checkbox-exact"}:
        return _grade_selection(
            answer,
            value,
            kind=kind,
            marks=marks,
            options=options,
        )

    expected_letters = split_letters(answer) if is_letter_answer(answer) else []
    submitted_letters = split_letters(value)
    if expected_letters:
        if kind == "radio" or len(submitted_letters) <= 1:
            is_correct = str(value or "").strip().upper() in expected_letters
        elif len(submitted_letters) > 1:
            is_correct = bool(expected_letters) and set(submitted_letters) == set(expected_letters)
        else:
            is_correct = str(value or "").strip().upper() in expected_letters
        awarded = marks if is_correct else 0
        return _result_feedback(
            answer=answer,
            value=value,
            marks=marks,
            awarded=awarded,
            options=options,
            expected=expected_letters,
            submitted=submitted_letters,
            kind=kind,
        )

    is_correct = clean_answer(value) in split_alternatives(answer)
    awarded = marks if is_correct else 0
    return _result_feedback(
        answer=answer,
        value=value,
        marks=marks,
        awarded=awarded,
        options=options,
        kind=kind,
    )


def _group_options(group: dict) -> list[dict]:
    return (group.get("collect_option") or group.get("collect_options") or {}).get("list") or []


def _group_questions(group: dict) -> list[dict]:
    return group.get("questions") or group.get("items") or []


def _is_combined_multi(group: dict) -> bool:
    questions = _group_questions(group)
    if str(group.get("type") or "") != "2" or not questions or not _group_options(group):
        return False
    first_answer = str(questions[0].get("answer") or "")
    return "," in first_answer and all(
        str(question.get("answer") or "") == first_answer for question in questions
    )


def _listening_units(payload: dict, *, section_number: int | None = None) -> list[dict]:
    sections = payload.get("sections") or []
    if not sections and payload.get("groups"):
        sections = [payload]
    selected_section = max(0, int(section_number) - 1) if section_number else None
    units = []
    for section_index, section in enumerate(sections):
        if selected_section is not None and section_index != selected_section:
            continue
        for group in section.get("groups") or []:
            questions = _group_questions(group)
            if _is_combined_multi(group):
                ids = [str(question.get("id") or question.get("number")) for question in questions]
                numbers = [question.get("number") for question in questions]
                units.append(
                    {
                        "ids": ids,
                        "numbers": numbers,
                        "answer": questions[0].get("answer") or "",
                        "marks": len(questions),
                        "kind": "checkbox-set",
                        "section": section_index,
                        "answer_key": str(group.get("answer_key") or ",".join(ids)),
                        "options": _group_options(group),
                    }
                )
                continue
            for question in questions:
                answer = question.get("answer") or ""
                is_exact_multi = bool(question.get("options")) and "," in str(answer)
                units.append(
                    {
                        "ids": [str(question.get("id") or question.get("number"))],
                        "numbers": [question.get("number")],
                        "answer": answer,
                        "marks": 1,
                        "kind": "checkbox-exact" if is_exact_multi else "question",
                        "section": section_index,
                        "answer_key": str(
                            question.get("answer_key")
                            or question.get("id")
                            or question.get("number")
                        ),
                        "options": question.get("options") or _group_options(group),
                    }
                )
    return units


def _answer_for_unit(unit: dict, answers: dict) -> str:
    value = answers.get(unit["answer_key"])
    if value is None and unit["kind"] == "checkbox-set":
        separate_values = [
            str(answers.get(item_id) or "").strip()
            for item_id in unit["ids"]
            if str(answers.get(item_id) or "").strip()
        ]
        if separate_values:
            value = ",".join(separate_values)
    if value is None and unit["ids"]:
        value = answers.get(unit["ids"][0], "")
    return str(value or "")


def _public_result(unit: dict, value: str, feedback: dict) -> dict:
    return {
        "ids": unit["ids"],
        "numbers": unit["numbers"],
        "q": ",".join(str(number) for number in unit["numbers"] if number is not None),
        "answer_key": unit["answer_key"],
        "answer": unit["answer"],
        "value": value,
        "marks": feedback["marks"],
        "awarded": feedback["awarded"],
        "correct": feedback["correct"],
        "status": feedback["status"],
        "status_label": feedback["status_label"],
        "option_states": feedback["option_states"],
        "max_selections": feedback["max_selections"],
        "selection_error": feedback["selection_error"],
        "section": unit.get("section"),
    }


def _grade_units(units: list[dict], answers: dict) -> dict:
    results = []
    total = 0
    correct = 0
    wrong_numbers = []
    for unit in units:
        value = _answer_for_unit(unit, answers)
        feedback = grade_answer(
            unit["answer"],
            value,
            kind=unit["kind"],
            marks=unit["marks"],
            options=unit.get("options") or [],
        )
        total += feedback["marks"]
        correct += feedback["awarded"]
        if feedback["status"] != "correct":
            wrong_numbers.extend(unit["numbers"])
        results.append(_public_result(unit, value, feedback))
    return {
        "correct": correct,
        "total": total,
        "accuracy": round(correct * 100.0 / total, 1) if total else 0.0,
        "results": results,
        "wrong_numbers": wrong_numbers,
    }


def ielts_listening_band(raw_score: int) -> float:
    raw = int(raw_score or 0)
    if raw >= 39:
        return 9.0
    if raw >= 37:
        return 8.5
    if raw >= 35:
        return 8.0
    if raw >= 32:
        return 7.5
    if raw >= 30:
        return 7.0
    if raw >= 26:
        return 6.5
    if raw >= 23:
        return 6.0
    if raw >= 18:
        return 5.5
    if raw >= 16:
        return 5.0
    if raw >= 13:
        return 4.5
    if raw >= 11:
        return 4.0
    if raw >= 8:
        return 3.5
    if raw >= 6:
        return 3.0
    if raw >= 4:
        return 2.5
    if raw >= 2:
        return 2.0
    if raw >= 1:
        return 1.0
    return 0.0


def ielts_reading_band(raw_score: int) -> float:
    raw = int(raw_score or 0)
    if raw >= 39:
        return 9.0
    if raw >= 37:
        return 8.5
    if raw >= 35:
        return 8.0
    if raw >= 33:
        return 7.5
    if raw >= 30:
        return 7.0
    if raw >= 27:
        return 6.5
    if raw >= 23:
        return 6.0
    if raw >= 19:
        return 5.5
    if raw >= 15:
        return 5.0
    if raw >= 13:
        return 4.5
    if raw >= 10:
        return 4.0
    if raw >= 8:
        return 3.5
    if raw >= 6:
        return 3.0
    if raw >= 4:
        return 2.5
    if raw >= 2:
        return 2.0
    if raw >= 1:
        return 1.0
    return 0.0


def grade_listening_test_answers(
    payload: dict,
    answers: dict,
    section_number: int | None = None,
) -> dict:
    answers = answers if isinstance(answers, dict) else {}
    grade = _grade_units(_listening_units(payload, section_number=section_number), answers)
    grade["ielts_score"] = ielts_listening_band(grade["correct"]) if grade["total"] >= 40 else None
    return grade


def grade_listening_jijing_answers(part: dict, answers: dict) -> dict:
    normalized_groups = []
    for group in part.get("groups") or []:
        normalized = dict(group)
        normalized["questions"] = [
            dict(item, answer_key=str(item.get("number") or item.get("id") or ""))
            for item in (group.get("items") or group.get("questions") or [])
        ]
        normalized["collect_option"] = (
            group.get("collect_options") or group.get("collect_option") or {}
        )
        if str(group.get("type") or "") == "2":
            normalized["answer_key"] = group.get("desc") or group.get("question_title") or ""
        normalized_groups.append(normalized)
    grade = _grade_units(
        _listening_units({"groups": normalized_groups}, section_number=None),
        answers if isinstance(answers, dict) else {},
    )
    grade["ielts_score"] = None
    return grade


def _reading_instruction_text(group: dict) -> str:
    return " ".join(str(group.get(key) or "") for key in ("title", "question_title", "desc"))


def _reading_group_has_judgment_instructions(group: dict) -> bool:
    text_value = _reading_instruction_text(group).upper()
    return bool(
        re.search(r"\b(TRUE|FALSE|YES|NO|NOT\s+GIVEN)\s+IF\b", text_value)
        or re.search(r"\bWRITE\s+(TRUE|FALSE|YES|NO|NOT\s+GIVEN)", text_value)
        or "DO THE FOLLOWING STATEMENTS AGREE" in text_value
        or "STATEMENTS AGREE WITH" in text_value
        or "CLAIMS OF THE WRITER" in text_value
        or "VIEWS OF THE WRITER" in text_value
    )


def reading_judgment_key(value) -> str:
    text_value = str(value or "").strip().upper()
    text_value = re.sub(r"[\s_-]+", " ", text_value)
    compact_value = re.sub(r"[\s_-]+", "", text_value)
    return (
        READING_JUDGMENT_ALIASES.get(text_value)
        or READING_JUDGMENT_ALIASES.get(compact_value)
        or ""
    )


def _reading_judgment_answers(answer, group: dict | None = None) -> list[str]:
    values = []
    group_uses_judgment = _reading_group_has_judgment_instructions(group or {})
    for part in re.split(r"\s*/\s*|\s+or\s+", str(answer or ""), flags=re.I):
        normalized = re.sub(r"[\s_-]+", " ", part.strip().upper())
        compact = re.sub(r"[\s_-]+", "", normalized)
        is_full = normalized in READING_FULL_JUDGMENT_ANSWERS or compact == "NOTGIVEN"
        is_short = compact in READING_SHORT_JUDGMENT_ANSWERS
        if is_full or (is_short and group_uses_judgment):
            values.append(reading_judgment_key(part))
    return list(dict.fromkeys(item for item in values if item))


def _reading_shared_expected(group: dict) -> list[str]:
    questions = group.get("questions") or []
    if len(questions) < 2:
        return []
    first_answer = questions[0].get("answer") or ""
    if "," not in str(first_answer) or not is_letter_answer(first_answer):
        return []
    expected = split_letters(first_answer)
    if len(expected) != len(questions):
        return []
    if not all((question.get("answer") or "") == first_answer for question in questions):
        return []
    return expected


def _reading_options(question: dict, group: dict) -> list[dict]:
    return question.get("options") or _group_options(group)


def _reading_result(question: dict, value: str, feedback: dict, passage_index: int) -> dict:
    qid = str(question.get("id") or question.get("number"))
    number = question.get("number")
    return {
        "ids": [qid],
        "numbers": [number],
        "q": str(number or ""),
        "answer": question.get("answer") or "",
        "value": value,
        "marks": feedback["marks"],
        "awarded": feedback["awarded"],
        "correct": feedback["correct"],
        "status": feedback["status"],
        "status_label": feedback["status_label"],
        "option_states": feedback["option_states"],
        "max_selections": feedback["max_selections"],
        "selection_error": feedback["selection_error"],
        "passage": passage_index,
    }


def grade_reading_test_answers(
    payload: dict,
    answers: dict,
    passage_number: int | None = None,
) -> dict:
    answers = answers if isinstance(answers, dict) else {}
    results = []
    total = 0
    correct = 0
    wrong_numbers = []
    passage_index_filter = max(0, int(passage_number) - 1) if passage_number else None

    for passage_index, passage in enumerate(payload.get("passages") or []):
        if passage_index_filter is not None and passage_index != passage_index_filter:
            continue
        for group in passage.get("groups") or []:
            shared_expected = _reading_shared_expected(group)
            used_letters = set()
            for question in group.get("questions") or []:
                qid = str(question.get("id") or question.get("number"))
                value = str(answers.get(qid, "") or "")
                answer = question.get("answer") or ""
                options = _reading_options(question, group)
                if shared_expected:
                    submitted = split_letters(value)
                    selected = submitted[0] if len(submitted) == 1 else ""
                    is_correct = selected in shared_expected and selected not in used_letters
                    if is_correct:
                        used_letters.add(selected)
                    feedback = _result_feedback(
                        answer=answer,
                        value=value,
                        marks=1,
                        awarded=1 if is_correct else 0,
                        options=options,
                        expected=[selected] if is_correct else [],
                        submitted=submitted,
                        kind="radio",
                    )
                else:
                    judgment_answers = _reading_judgment_answers(answer, group)
                    if judgment_answers:
                        is_correct = reading_judgment_key(value) in judgment_answers
                        feedback = _result_feedback(
                            answer=answer,
                            value=value,
                            marks=1,
                            awarded=1 if is_correct else 0,
                            options=options,
                            expected=judgment_answers,
                            submitted=(
                                [reading_judgment_key(value)] if reading_judgment_key(value) else []
                            ),
                            kind="radio",
                        )
                    elif (
                        "," in str(answer) and is_letter_answer(answer) and question.get("options")
                    ):
                        feedback = grade_answer(
                            answer,
                            value,
                            kind="checkbox-exact",
                            marks=1,
                            options=options,
                        )
                    elif "," in str(answer) and is_letter_answer(answer):
                        feedback = grade_answer(
                            answer, value, kind="checkbox-exact", marks=1, options=options
                        )
                    elif is_letter_answer(answer):
                        feedback = grade_answer(
                            answer,
                            value,
                            kind="radio",
                            marks=1,
                            options=options,
                        )
                    else:
                        feedback = grade_answer(
                            answer, value, kind="question", marks=1, options=options
                        )
                total += 1
                correct += feedback["awarded"]
                if feedback["status"] != "correct":
                    wrong_numbers.append(question.get("number"))
                results.append(_reading_result(question, value, feedback, passage_index))

    return {
        "correct": correct,
        "total": total,
        "accuracy": round(correct * 100.0 / total, 1) if total else 0.0,
        "ielts_score": ielts_reading_band(correct) if total >= 40 else None,
        "wrong_numbers": wrong_numbers,
        "results": results,
    }
