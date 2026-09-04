"""Versioned IELTS writing content and typing-practice scoring."""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "writing_library"
    / "pilot_40.json"
)
MOTHER_TOPICS_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "writing_library"
    / "mother_topics.json"
)
BANDS = ("6.0", "6.5", "7.0+")
_WORD_RE = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*|\d+(?:\.\d+)?")
_CHAR_REPLACEMENTS = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "…": "...",
        "\u00a0": " ",
    }
)


def word_count(text: str) -> int:
    value = unicodedata.normalize("NFKC", str(text or "")).translate(
        _CHAR_REPLACEMENTS
    )
    return len(_WORD_RE.findall(value))


def normalize_typing_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).translate(
        _CHAR_REPLACEMENTS
    )
    return " ".join(value.lower().split())


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for row_index, left_char in enumerate(left, start=1):
        current = [row_index]
        for column_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column_index] + 1,
                    previous[column_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def typing_metrics(target: str, typed: str, duration_seconds: int | float) -> dict:
    target_normalized = normalize_typing_text(target)
    typed_normalized = normalize_typing_text(typed)
    distance = _levenshtein_distance(target_normalized, typed_normalized)
    denominator = max(len(target_normalized), len(typed_normalized), 1)
    seconds = max(1, int(duration_seconds or 0))
    typed_words = word_count(typed)
    return {
        "typed_word_count": typed_words,
        "target_word_count": word_count(target),
        "duration_seconds": seconds,
        "speed_wpm": round(typed_words * 60 / seconds, 1),
        "accuracy": round(max(0.0, (1 - distance / denominator) * 100), 1),
    }


def _task2_paragraphs(item: dict, band: str) -> list[str]:
    first, second = item["arguments"]
    if band == "6.0":
        intro = (
            f"{item['intro']} This essay explains the two main reasons for this view."
        )
        body_one = " ".join(
            [
                f"First, {first['claim']}",
                first["why"],
                f"For example, {first['example']}",
                f"As a result, {first['result']}",
                "This is a practical effect that should be considered when decisions are made.",
                first["nuance"],
                "Together, these points show how the main benefit can work in ordinary life rather than only in theory.",
            ]
        )
        body_two = " ".join(
            [
                f"Second, {second['claim']}",
                second["why"],
                f"For instance, {second['example']}",
                f"Therefore, {second['result']}",
                "This point shows why a simple one-sided answer would not be sufficient.",
                second["nuance"],
                "It is therefore important to keep this limit in mind when applying the argument more widely.",
            ]
        )
        conclusion = (
            f"In conclusion, {item['conclusion']} For this reason, the policy or choice "
            "should follow the balanced position explained above."
        )
    elif band == "6.5":
        intro = (
            f"{item['intro']} The issue should be judged by both its immediate effects "
            "and its longer-term consequences."
        )
        body_one = " ".join(
            [
                f"The first important consideration is that {first['claim'][0].lower() + first['claim'][1:]}",
                first["why"],
                f"A clear example is that {first['example'][0].lower() + first['example'][1:]}",
                first["result"],
                first["nuance"],
                "The wider significance is that a workable response must influence everyday incentives as well as formal rules.",
            ]
        )
        body_two = " ".join(
            [
                f"A further consideration is that {second['claim'][0].lower() + second['claim'][1:]}",
                second["why"],
                f"For example, {second['example']}",
                second["result"],
                second["nuance"],
                "This qualification keeps the position realistic while preserving its central direction.",
            ]
        )
        conclusion = (
            f"To conclude, {item['conclusion']} This approach recognises the strongest "
            "concern on each side while still reaching a clear position. It also offers "
            "a realistic basis for action rather than an absolute claim."
        )
    else:
        intro = (
            f"{item['intro']} A balanced judgement requires attention not only to visible "
            "short-term outcomes, but also to incentives and distributional effects. "
            "Those dimensions often determine whether an apparent benefit can be sustained."
        )
        body_one = " ".join(
            [
                f"Most importantly, {first['claim'][0].lower() + first['claim'][1:]}",
                first["why"],
                f"To illustrate, {first['example'][0].lower() + first['example'][1:]}",
                first["result"],
                first["nuance"],
                "This matters because durable policy changes behaviour and opportunity rather than merely treating a visible symptom.",
                "It also identifies the mechanism linking an individual decision to the wider outcome described in the question.",
            ]
        )
        body_two = " ".join(
            [
                f"Equally, {second['claim'][0].lower() + second['claim'][1:]}",
                second["why"],
                f"For example, {second['example'][0].lower() + second['example'][1:]}",
                second["result"],
                second["nuance"],
                "Acknowledging this qualification strengthens the argument because it avoids presenting a complex choice as an absolute one.",
                "The boundary is therefore part of the position itself, rather than an afterthought added to appear balanced.",
            ]
        )
        conclusion = (
            f"Overall, {item['conclusion'][0].lower() + item['conclusion'][1:]} The most defensible response is therefore one "
            "that secures the principal benefit while deliberately limiting predictable harm."
        )
    return [intro, body_one, body_two, conclusion]


def _task1_paragraphs(item: dict, band: str) -> list[str]:
    first, second = item["details"]
    topic = item["title_en"].lower()
    intro = (
        f"The provided visual material illustrates {topic} and its principal features. "
        "The information is organised below according to its most relevant groups."
    )
    overview = item["overview"]
    if band == "6.0":
        body_one = " ".join(
            [first["claim"], first["why"], first["example"], first["result"], first["nuance"]]
        )
        body_two = " ".join(
            [second["claim"], second["why"], second["example"], second["result"], second["nuance"]]
        )
    elif band == "6.5":
        intro = (
            f"The supplied diagram or chart presents information about {topic}. "
            "The principal patterns and comparisons are summarised in the following paragraphs."
        )
        body_one = " ".join(
            [
                first["claim"],
                first["why"],
                first["example"],
                first["result"],
                first["nuance"],
            ]
        )
        body_two = " ".join(
            [
                second["claim"],
                second["why"],
                second["example"],
                second["result"],
                second["nuance"],
            ]
        )
    else:
        intro = (
            f"The visual information compares the main features and changes associated with {topic}. "
            "The account focuses on the dominant pattern before grouping the supporting detail."
        )
        overview = f"{item['overview']} The most notable contrasts are described below."
        body_one = " ".join(
            [
                first["claim"],
                first["why"],
                f"More specifically, {first['example'][0].lower() + first['example'][1:]}",
                first["result"],
                first["nuance"],
            ]
        )
        body_two = " ".join(
            [
                second["claim"],
                second["why"],
                f"In comparison, {second['example'][0].lower() + second['example'][1:]}",
                second["result"],
                second["nuance"],
            ]
        )
    return [intro, overview, body_one, body_two]


def _essay(item: dict, band: str) -> dict:
    paragraphs = (
        _task1_paragraphs(item, band)
        if item["task"] == "task1"
        else _task2_paragraphs(item, band)
    )
    text = "\n\n".join(paragraphs)
    return {"band": band, "paragraphs": paragraphs, "text": text, "word_count": word_count(text)}


def _mother_topic_paragraphs(topic: dict, band: str) -> list[str]:
    """Build a levelled model for the topic's representative prompt.

    The mother-topic data owns the teaching ideas. These templates turn those
    ideas into complete essays without claiming that one answer fits every
    prompt assigned to the topic.
    """
    first, second, third, _fourth = topic["logic_chains"]
    subject = topic["title_en"].lower()
    if band == "6.0":
        intro = (
            f"Questions about {subject} often create strong disagreement because they affect both individuals and society. "
            f"In my view, {topic['thesis_en'][0].lower() + topic['thesis_en'][1:]} "
            "This position is mainly supported by two practical reasons."
        )
        body_one = " ".join(
            [
                f"The first reason is that {first['claim_en'][0].lower() + first['claim_en'][1:]}",
                "This changes the choices available to ordinary people and influences what they are likely to do in daily life.",
                f"For example, {first['example_en'][0].lower() + first['example_en'][1:]}",
                first["result_en"],
                "Therefore, this point is not only an ideal principle; it can lead to a clear and useful outcome.",
                "However, the measure should be applied carefully because the same approach may not suit every person or situation.",
            ]
        )
        body_two = " ".join(
            [
                f"Another important point is that {second['claim_en'][0].lower() + second['claim_en'][1:]}",
                "When a policy changes resources, opportunities or responsibilities, its effects can continue long after the first decision.",
                f"For instance, {second['example_en'][0].lower() + second['example_en'][1:]}",
                second["result_en"],
                "This shows why a one-sided answer is not enough and why implementation matters as much as the original aim.",
                "A reasonable limit is needed so that the main benefit is achieved without creating a new unfairness.",
            ]
        )
        conclusion = (
            f"In conclusion, {topic['conclusion_en'][0].lower() + topic['conclusion_en'][1:]} "
            "A balanced version of this approach is more convincing than either a complete ban or an unrestricted policy."
        )
        return [intro, body_one, body_two, conclusion]

    if band == "6.5":
        intro = (
            f"Debates concerning {subject} are difficult because an apparent short-term advantage may create wider costs. "
            f"I would argue that {topic['thesis_en'][0].lower() + topic['thesis_en'][1:]} "
            "The strongest case rests on the way the proposal changes incentives and distributes opportunity."
        )
        body_one = " ".join(
            [
                f"Most importantly, {first['claim_en'][0].lower() + first['claim_en'][1:]}",
                "The mechanism is important: when people receive clearer opportunities and feedback, their everyday decisions begin to support the intended outcome.",
                f"A useful illustration is that {first['example_en'][0].lower() + first['example_en'][1:]}",
                first["result_en"],
                "The broader significance is that durable improvement comes from changing capability and behaviour, rather than treating one visible symptom.",
            ]
        )
        body_two = " ".join(
            [
                f"A second consideration is that {second['claim_en'][0].lower() + second['claim_en'][1:]}",
                "This matters because costs and benefits rarely fall on the same group or appear at the same time.",
                f"For example, {second['example_en'][0].lower() + second['example_en'][1:]}",
                second["result_en"],
                "Provided that responsibility is clearly assigned and outcomes are monitored, this advantage can be sustained instead of disappearing after an initial intervention.",
            ]
        )
        conclusion = (
            f"To conclude, {topic['conclusion_en'][0].lower() + topic['conclusion_en'][1:]} "
            "Recognising limits does not weaken this position; it identifies the conditions under which the central argument is most likely to work."
        )
        return [intro, body_one, body_two, conclusion]

    intro = (
        f"Arguments about {subject} are often framed as a choice between two absolute positions. "
        f"A more defensible judgement is that {topic['thesis_en'][0].lower() + topic['thesis_en'][1:]} "
        "This view follows from the interaction between individual incentives, institutional capacity and the distribution of long-term risk."
    )
    body_one = " ".join(
        [
            f"The primary mechanism is that {first['claim_en'][0].lower() + first['claim_en'][1:]}",
            "Once the relevant incentives and constraints change, people can make choices that were previously impractical, costly or unavailable.",
            f"To illustrate, {first['example_en'][0].lower() + first['example_en'][1:]}",
            first["result_en"],
            "This causal link is stronger than a simple claim of correlation because it explains who changes their behaviour, why they do so and what follows.",
        ]
    )
    body_two = " ".join(
        [
            f"The distributional case is equally important: {second['claim_en'][0].lower() + second['claim_en'][1:]}",
            "Benefits that appear efficient in aggregate can still be fragile if the financial burden, loss of time or exposure to risk is concentrated on one group.",
            f"For instance, {second['example_en'][0].lower() + second['example_en'][1:]}",
            second["result_en"],
            "A credible response must therefore specify both the responsible institution and the people who require additional protection.",
        ]
    )
    qualification = " ".join(
        [
            f"Nevertheless, the argument should not be treated as universal. {third['claim_en']}",
            f"Consider the case in which {third['example_en'][0].lower() + third['example_en'][1:]}",
            third["result_en"],
            "This qualification sets a boundary rather than reversing the main position: implementation should be proportionate, transparent and responsive to evidence.",
            "Such safeguards preserve the principal benefit while reducing the most predictable unintended consequence.",
        ]
    )
    conclusion = (
        f"Overall, {topic['conclusion_en'][0].lower() + topic['conclusion_en'][1:]} "
        "The preferable course is consequently neither automatic expansion nor outright rejection, but a targeted approach with clear responsibility and reviewable limits."
    )
    return [intro, body_one, body_two, qualification, conclusion]


def _prepare_mother_topic(raw: dict) -> dict:
    topic = dict(raw)
    topic["prompt_count"] = len(topic.get("prompts", []))
    topic["model_essays"] = {}
    for band in BANDS:
        paragraphs = _mother_topic_paragraphs(topic, band)
        text = "\n\n".join(paragraphs)
        topic["model_essays"][band] = {
            "band": band,
            "paragraphs": paragraphs,
            "text": text,
            "word_count": word_count(text),
        }
    return topic


def _structures(item: dict) -> dict:
    argument_key = "details" if item["task"] == "task1" else "arguments"
    first, second = item[argument_key]
    if item["task"] == "task1":
        four = [
            {"label": "P1 改写题目", "function_zh": "说明图表或流程展示什么，不抄原题。", "content_zh": item["topic_zh"]},
            {"label": "P2 总览", "function_zh": "只写最显著趋势、阶段或差异，不堆细节数字。", "content_zh": item["position_zh"]},
            {"label": "P3 细节组一", "function_zh": "按时间、类别或流程关系组织第一组关键信息。", "content_zh": first["title_zh"]},
            {"label": "P4 细节组二", "function_zh": "补充第二组信息，并主动形成比较或衔接。", "content_zh": second["title_zh"]},
        ]
        five = [
            four[0],
            four[1],
            four[2],
            four[3],
            {"label": "P5 对比收束（可选）", "function_zh": "数据特别密集时单列交叉比较；普通题不要为了五段而五段。", "content_zh": "只保留最有区分度的对比，不写观点。"},
        ]
    else:
        four = [
            {"label": "P1 引言与立场", "function_zh": "改写题干并给出清晰、可贯穿全文的回答。", "content_zh": item["position_zh"]},
            {"label": "P2 主体一", "function_zh": "提出主论点，解释因果，再用具体情境落地。", "content_zh": first["title_zh"]},
            {"label": "P3 主体二", "function_zh": "发展第二个维度，并回应题目中的限制或另一面。", "content_zh": second["title_zh"]},
            {"label": "P4 结论", "function_zh": "换一种表达重申答案，不添加新论点。", "content_zh": item["conclusion"]},
        ]
        five = [
            four[0],
            four[1],
            four[2],
            {"label": "P4 让步与边界（可选）", "function_zh": "单独承认反方最强点，再说明为何不改变最终判断。", "content_zh": second["nuance"]},
            {"label": "P5 结论", "function_zh": "综合主张与条件，直接回答题目。", "content_zh": item["conclusion"]},
        ]
    return {"four": four, "five": five}


def _prepare_item(raw: dict) -> dict:
    item = dict(raw)
    item["task_label"] = "Task 1 小作文" if item["task"] == "task1" else "Task 2 大作文"
    item["essays"] = {band: _essay(item, band) for band in BANDS}
    item["structures"] = _structures(item)
    return item


@lru_cache(maxsize=1)
def load_mother_topics() -> dict:
    payload = json.loads(MOTHER_TOPICS_PATH.read_text(encoding="utf-8"))
    topics = [_prepare_mother_topic(row) for row in payload.get("topics", [])]
    identifiers = [row["id"] for row in topics]
    prompt_sequences = [
        prompt["sequence"] for topic in topics for prompt in topic.get("prompts", [])
    ]
    if len(topics) != 27 or len(set(identifiers)) != len(identifiers):
        raise ValueError("writing mother-topic library must contain 27 unique topics")
    if len(prompt_sequences) != 252 or len(set(prompt_sequences)) != 252:
        raise ValueError("writing mother topics must classify 252 unique Task 2 prompts")
    if any(len(row.get("logic_chains", [])) != 4 for row in topics):
        raise ValueError("every writing mother topic must contain four logic chains")
    if any(len(row.get("expressions", [])) < 8 for row in topics):
        raise ValueError("every writing mother topic must contain at least eight expressions")
    if any(
        set(row["model_essays"]) != set(BANDS)
        or any(model["word_count"] < 250 for model in row["model_essays"].values())
        for row in topics
    ):
        raise ValueError("every writing mother topic must contain three complete model essays")
    return {
        **payload,
        "topics": topics,
        "by_id": {row["id"]: row for row in topics},
        "by_sequence": {
            prompt["sequence"]: {
                "id": topic["id"],
                "code": topic["code"],
                "title_zh": topic["title_zh"],
                "title_en": topic["title_en"],
            }
            for topic in topics
            for prompt in topic["prompts"]
        },
    }


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    exercises = [_prepare_item(row) for row in payload.get("exercises", [])]
    mother_topics = load_mother_topics()["by_sequence"]
    for exercise in exercises:
        if exercise["task"] == "task2":
            exercise["mother_topic"] = mother_topics.get(exercise["sequence"])
    identifiers = [row["id"] for row in exercises]
    if len(exercises) != 40 or len(set(identifiers)) != len(identifiers):
        raise ValueError("writing pilot must contain 40 uniquely identified exercises")
    if sum(row["task"] == "task1" for row in exercises) != 10:
        raise ValueError("writing pilot must contain exactly 10 Task 1 exercises")
    if any(set(row["essays"]) != set(BANDS) for row in exercises):
        raise ValueError("every writing exercise must contain all three model bands")
    return {
        **payload,
        "exercises": exercises,
        "by_id": {row["id"]: row for row in exercises},
    }


def get_exercise(exercise_id: str) -> dict | None:
    return load_catalog()["by_id"].get(str(exercise_id or ""))


def get_mother_topic(topic_id: str) -> dict | None:
    return load_mother_topics()["by_id"].get(str(topic_id or "").lower())


def mother_topic_summary() -> dict:
    topics = load_mother_topics()["topics"]
    families = []
    for topic in topics:
        if topic["family"] not in families:
            families.append(topic["family"])
    return {
        "total": len(topics),
        "prompts": sum(row["prompt_count"] for row in topics),
        "expressions": sum(len(row["expressions"]) for row in topics),
        "logic_chains": sum(len(row["logic_chains"]) for row in topics),
        "families": families,
        "bands": list(BANDS),
    }


def catalog_summary() -> dict:
    exercises = load_catalog()["exercises"]
    return {
        "total": len(exercises),
        "task1": sum(row["task"] == "task1" for row in exercises),
        "task2": sum(row["task"] == "task2" for row in exercises),
        "mother_topics": len(load_mother_topics()["topics"]),
        "bands": list(BANDS),
    }
