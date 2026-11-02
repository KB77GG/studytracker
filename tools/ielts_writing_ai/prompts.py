"""Prompt builders.  Bump PROMPT_VERSION whenever any prompt text changes."""

from __future__ import annotations

import json

from . import essay as essay_lib

PROMPT_VERSION = "iwa-2026-11-02.1"

EXAMINER_ROLE = (
    "You are a senior IELTS Writing examiner and writing coach for Chinese learners. "
    "You apply the public IELTS Writing band descriptors strictly and consistently. "
    "Write every explanation for the student in Simplified Chinese; keep English quotations, "
    "corrections and model sentences in English. Return only one JSON object, no markdown."
)

DESCRIPTOR_NOTES = {
    "task1": (
        "Task Achievement (task): a clear overview of main trends/differences is essential; key "
        "features must be selected and supported with accurate data; no personal opinion; "
        "under 150 words limits TA. "
    ),
    "task2": (
        "Task Response (task): address all parts of the question, keep a clear position "
        "throughout, extend and support main ideas with relevant explanation/examples; "
        "under 250 words or partly off-topic limits TR. "
    ),
}
COMMON_DESCRIPTORS = (
    "Coherence & Cohesion (coherence): logical progression, paragraphing, referencing, "
    "range and accuracy of cohesive devices without mechanical overuse. "
    "Lexical Resource (lexical): range, precision, collocation, less common items, "
    "spelling and word formation errors. "
    "Grammatical Range & Accuracy (grammar): range of complex structures, proportion of "
    "error-free sentences, punctuation."
)

CALIBRATION = (
    "Calibration rules: do not inflate. Most essays by Chinese candidates at this stage sit "
    "between 5.0 and 6.5. Award 7.0+ in a criterion only when its higher-band features are "
    "clearly and consistently present; award 8.0+ only for near-error-free, sophisticated "
    "writing. Each criterion band is independent; use 0.5 steps between 0 and 9."
)


def _task_context(submission: dict) -> dict:
    task_type = submission["task_type"]
    context = {
        "task_type": essay_lib.TASK_LABELS[task_type],
        "question": submission["prompt_text"],
        "word_count": submission["word_count"],
        "minimum_words": essay_lib.MIN_WORDS[task_type],
    }
    if task_type == "task1":
        status = submission.get("image_status") or "none"
        if status == "ready" and submission.get("image_description"):
            context["visual_summary"] = submission["image_description"]
            context["visual_note"] = (
                "visual_summary was extracted from the task image by a vision model; use it to "
                "check data accuracy, but say so if a mismatch might come from extraction."
            )
        elif status in {"failed", "skipped", "pending"}:
            context["visual_note"] = (
                "A task image was provided but could not be read. Do not invent data; treat "
                "data accuracy as unverified and mention this in the task criterion summary."
            )
        else:
            context["visual_note"] = (
                "No task image was provided. Judge data accuracy only against the question text."
            )
    return context


def _numbered(sentences: list[essay_lib.Sentence]) -> list[dict]:
    return [{"i": s.index, "paragraph": s.paragraph, "text": s.text} for s in sentences]


def build_evaluate(submission: dict, sentences: list[essay_lib.Sentence]) -> tuple[list, dict]:
    task_type = submission["task_type"]
    system = " ".join(
        [
            EXAMINER_ROLE,
            "Assess the ORIGINAL essay exactly as written.",
            DESCRIPTOR_NOTES[task_type] + COMMON_DESCRIPTORS,
            CALIBRATION,
            "For every issue, 'quote' must be copied verbatim from the essay (a short span, "
            "max 25 words) so it can be located; never paraphrase inside 'quote'.",
            'Output schema: {"criteria": {"task": C, "coherence": C, "lexical": C, '
            '"grammar": C}, "overall_comment": str, "priorities": [str, ...3-5]} where C = '
            '{"band": number, "summary": str (2-4 sentences, why this band), '
            '"strengths": [str, ...1-3], "issues": [{"quote": str, "comment": str, '
            '"suggestion": str}, ...1-4]}. Do not output an overall band; it is computed '
            "from the four criteria.",
        ]
    )
    payload = {**_task_context(submission), "essay": submission["essay_text"]}
    user = "Evaluate this IELTS essay.\n" + json.dumps(payload, ensure_ascii=False, indent=1)
    context = {
        "kind": "evaluate",
        "word_count": submission["word_count"],
        "minimum_words": essay_lib.MIN_WORDS[task_type],
        "sentences": _numbered(sentences),
    }
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], context


def build_refine(submission: dict, sentences: list[essay_lib.Sentence]) -> tuple[list, dict]:
    target = submission["target_band"]
    system = " ".join(
        [
            EXAMINER_ROLE,
            "Task: sentence-by-sentence polishing of the student's essay.",
            f"Revise each sentence so it would fit a Band {target:g} essay: fix every grammar, "
            "spelling, punctuation, collocation and word-choice error, and upgrade expression "
            "where it clearly helps, while KEEPING the student's meaning, argument and "
            "sentence order. Do not add new ideas. Do not merge or split sentences: return "
            "exactly one item per input sentence, with the same 'i'.",
            "If a sentence is already good, return it unchanged with empty tags.",
            "Allowed tags: grammar, vocabulary, collocation, cohesion, punctuation, spelling, "
            "clarity, task.",
            'Output schema: {"sentences": [{"i": int, "revised": str, "tags": [str], '
            '"explanation": str (Chinese, 1-2 sentences, what was wrong and why the revision '
            'is better; empty if unchanged)}], "summary": str (Chinese, the 2-3 most '
            "frequent problems)}.",
        ]
    )
    payload = {
        **_task_context(submission),
        "target_band": target,
        "sentences": [{"i": s.index, "text": s.text} for s in sentences],
    }
    user = "Polish these sentences.\n" + json.dumps(payload, ensure_ascii=False, indent=1)
    context = {"kind": "refine", "sentences": _numbered(sentences)}
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], context


def build_rewrite(submission: dict, sentences: list[essay_lib.Sentence]) -> tuple[list, dict]:
    task_type = submission["task_type"]
    target = submission["target_band"]
    minimum = essay_lib.MIN_WORDS[task_type]
    upper = 220 if task_type == "task1" else 330
    system = " ".join(
        [
            EXAMINER_ROLE,
            f"Task: rewrite the whole essay as a Band {target:g} model answer that the student "
            "can study against their own draft.",
            "Keep the student's position, main ideas and examples wherever they are usable; "
            "repair logic, paragraphing and development; fix all language errors. Use natural "
            f"academic English appropriate to Band {target:g} (not artificially ornate). "
            f"Length: {minimum}-{upper} words. One paragraph per line, separated by a blank line.",
            (
                "Task 1: include an overview and accurate key figures; no opinion."
                if task_type == "task1"
                else "Task 2: answer every part of the question with a clear position."
            ),
            'Output schema: {"essay": str, "key_changes": [str (Chinese), ...3-6], '
            '"band_rationale": str (Chinese, why this version meets the target band)}.',
        ]
    )
    payload = {
        **_task_context(submission),
        "target_band": target,
        "essay": submission["essay_text"],
    }
    user = "Rewrite this essay.\n" + json.dumps(payload, ensure_ascii=False, indent=1)
    context = {"kind": "rewrite", "sentences": _numbered(sentences)}
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], context


def build_describe_image(submission: dict, image_data_url: str) -> tuple[list, dict]:
    instruction = (
        "This image is the visual for an IELTS Academic Writing Task 1 question:\n"
        f"{submission['prompt_text']}\n\n"
        "Describe ONLY what the image shows, in English, max 220 words: chart/diagram type, "
        "title, units, time periods, categories, the key figures (exact values where legible), "
        "the main trends, highest/lowest points and notable comparisons. For maps/processes, "
        "list the stages or changes in order. Mark any value you cannot read clearly as "
        "'unclear'. No opinions, no essay advice."
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_data_url}},
                {"type": "text", "text": instruction},
            ],
        }
    ]
    return messages, {"kind": "describe_image"}


BUILDERS = {"evaluate": build_evaluate, "refine": build_refine, "rewrite": build_rewrite}
MAX_TOKENS = {"evaluate": 3000, "refine": 6000, "rewrite": 2400, "describe_image": 700}
