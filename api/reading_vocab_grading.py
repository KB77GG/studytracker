"""阅读词汇练习（reading vocab choice）判分纯核心。

从 api/miniprogram.py 的 submit_reading_vocab_practice() 抽出。
本模块不碰 DB / Flask：输入是普通 dict（由 handler 把 ORM 解析好），
输出是「待入库记录 + 聚合指标 + 错题 + 备注后缀」，便于零依赖单测钉住行为。

判分逻辑与原 handler 逐字一致（三分支 writing / auto_text / choice +
redo_wrong 复用分支），只是把 db.session.add(...) 换成 append 到 records。
"""

from dataclasses import dataclass, field

from .text_utils import _normalize_objective_answer, _objective_answer_alternatives


@dataclass
class GradeResult:
    """grade_reading_vocab_submission 的结构化返回。"""

    records: list = field(default_factory=list)  # 待入库 StudentAnswer 字段(不含 task_id/student_id/submitted_at)
    correct_count: int = 0
    objective_total: int = 0  # 客观题(choice + auto_text)数量；accuracy 分母
    answered_count: int = 0  # 所有已作答(含 writing)数量；completion_rate 分子
    writing_total: int = 0
    writing_answered: int = 0
    total: int = 0  # 题目总数；completion_rate 分母
    accuracy: float = 0.0
    completion_rate: float = 0.0
    wrong_items: list = field(default_factory=list)
    note_suffix: str = ""  # 形如 "[阅读词汇待复习] …"，无错题时为空串


def _wrong_item(qv, *, selected_key, selected_text, correct_key, correct_text, is_uncertain):
    return {
        "task_id": qv["task_id"],
        "task_title": qv["task_title"],
        "question_id": qv["question_id"],
        "word": qv["word"],
        "selected_key": selected_key,
        "selected_text": selected_text,
        "correct_key": correct_key,
        "correct_text": correct_text,
        "hint": qv["hint"] or "",
        "is_uncertain": is_uncertain,
    }


def grade_reading_vocab_submission(
    question_views,
    *,
    answer_map,
    text_answer_map,
    uncertain_ids,
    prior_by_qid,
    resubmit_qids,
):
    """对一次阅读词汇练习提交判分（纯函数）。

    question_views: list[dict]，每题含
        question_id / input_mode(choice|auto_text|writing) /
        options([{key,text}]) / reference_answer / hint / word / task_id / task_title
    answer_map:        {qid: 选项KEY}
    text_answer_map:   {qid: 文本答案}
    uncertain_ids:     set[int]
    prior_by_qid:      {qid: {"text_answer","is_correct","is_uncertain"}}  redo_wrong 复用旧记录
    resubmit_qids:     set[int]  本次重新提交的题目
    """
    result = GradeResult()
    result.total = len(question_views)

    for qv in question_views:
        qid = qv["question_id"]
        input_mode = qv["input_mode"]
        opts = qv["options"]
        ref = qv["reference_answer"]
        is_auto_text = input_mode == "auto_text"
        is_writing = input_mode == "writing"
        if is_writing:
            result.writing_total += 1
        else:
            result.objective_total += 1

        # redo_wrong：本题不在本次提交、但有旧记录 → 复用旧结果，不重新入库
        if qid not in resubmit_qids and qid in prior_by_qid:
            prior = prior_by_qid[qid]
            prior_text = prior.get("text_answer")
            prior_correct = prior.get("is_correct")
            prior_uncertain = bool(prior.get("is_uncertain"))
            if prior_text:
                result.answered_count += 1
                if is_writing:
                    result.writing_answered += 1
            if not is_writing:
                if prior_correct:
                    result.correct_count += 1
                if (not prior_correct) or prior_uncertain:
                    options = {opt["key"]: opt["text"] for opt in opts}
                    correct_key = str(ref or "").strip().upper() if input_mode == "choice" else (ref or "")
                    correct_text = options.get(correct_key, ref or qv["hint"] or "")
                    selected_text = (
                        (prior_text or "未作答")
                        if input_mode == "auto_text"
                        else options.get(prior_text or "", "未作答")
                    )
                    result.wrong_items.append(_wrong_item(
                        qv,
                        selected_key=prior_text or "未作答",
                        selected_text=selected_text,
                        correct_key=correct_key,
                        correct_text=correct_text,
                        is_uncertain=prior_uncertain,
                    ))
            continue

        if is_writing:
            # 写作题：原样保存，不判分，待老师批改
            text_val = text_answer_map.get(qid, "")
            if text_val:
                result.answered_count += 1
                result.writing_answered += 1
            result.records.append({
                "question_id": qid,
                "answer_type": "text",
                "text_answer": text_val,
                "reviewed": False,
                "is_correct": None,
                "is_uncertain": False,
            })
            continue

        if is_auto_text:
            text_val = text_answer_map.get(qid, "")
            expected = _objective_answer_alternatives(ref or "")
            normalized = _normalize_objective_answer(text_val)
            is_correct = bool(normalized) and normalized in expected
            is_uncertain = qid in uncertain_ids
            if text_val:
                result.answered_count += 1
            if is_correct:
                result.correct_count += 1
            if (not is_correct) or is_uncertain:
                result.wrong_items.append(_wrong_item(
                    qv,
                    selected_key=text_val or "未作答",
                    selected_text=text_val or "未作答",
                    correct_key=ref or "",
                    correct_text=ref or "",
                    is_uncertain=is_uncertain,
                ))
            result.records.append({
                "question_id": qid,
                "answer_type": "text",
                "text_answer": text_val,
                "reviewed": True,
                "is_correct": is_correct,
                "is_uncertain": is_uncertain,
            })
            continue

        # choice：单选题
        selected_key = answer_map.get(qid, "")
        options = {opt["key"]: opt["text"] for opt in opts}
        if selected_key and selected_key not in options:
            selected_key = ""
        correct_key = str(ref or "").strip().upper()
        is_correct = bool(selected_key) and selected_key == correct_key
        is_uncertain = qid in uncertain_ids
        if selected_key:
            result.answered_count += 1
        if is_correct:
            result.correct_count += 1
        if (not is_correct) or is_uncertain:
            result.wrong_items.append(_wrong_item(
                qv,
                selected_key=selected_key or "未作答",
                selected_text=options.get(selected_key, "未作答"),
                correct_key=correct_key,
                correct_text=options.get(correct_key, qv["hint"] or ""),
                is_uncertain=is_uncertain,
            ))
        result.records.append({
            "question_id": qid,
            "answer_type": "choice",
            "text_answer": selected_key,
            "reviewed": True,
            "is_correct": is_correct,
            "is_uncertain": is_uncertain,
        })

    # 聚合：accuracy 只按客观题；completion_rate 按全部题目
    result.accuracy = (
        round((result.correct_count / result.objective_total) * 100, 1)
        if result.objective_total
        else 0.0
    )
    result.completion_rate = (
        round((result.answered_count / result.total) * 100, 1) if result.total else 0.0
    )

    if result.wrong_items:
        wrong_summary = "；".join(
            (
                f"{item['word']}（已标记不清楚，你选{item['selected_key']}:{item['selected_text']}，"
                f"正确{item['correct_key']}:{item['correct_text']}）"
                if item.get("is_uncertain")
                else f"{item['word']}（你选{item['selected_key']}:{item['selected_text']}，"
                f"正确{item['correct_key']}:{item['correct_text']}）"
            )
            for item in result.wrong_items
        )
        result.note_suffix = f"[阅读词汇待复习] {wrong_summary}"

    return result
