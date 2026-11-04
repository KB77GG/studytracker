"""Prompt builders.  Bump PROMPT_VERSION whenever any prompt text changes."""

from __future__ import annotations

import json

from . import essay as essay_lib

PROMPT_VERSION = "iwa-2026-11-04.3"

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
        else:
            context["visual_note"] = (
                "The task visual is NOT available (no image, or it could not be read). You "
                "cannot know the real data: never state, check or invent figures, trends or "
                "chart features beyond what the question text itself says."
            )
    return context


def visual_available(submission: dict) -> bool:
    return submission["task_type"] != "task1" or submission.get("image_status") == "ready"


def with_retry_note(messages: list, problem: str) -> list:
    """Re-ask after a rejected output, telling the model exactly what was wrong."""
    updated = [dict(m) for m in messages]
    note = (
        f"\n\nIMPORTANT: your previous answer was rejected by validation ({problem}). "
        "Return the COMPLETE JSON again, following the schema and evidence rules exactly."
    )
    updated[-1]["content"] = str(updated[-1]["content"]) + note
    return updated


def _numbered(sentences: list[essay_lib.Sentence]) -> list[dict]:
    return [{"i": s.index, "paragraph": s.paragraph, "text": s.text} for s in sentences]


def build_evaluate(submission: dict, sentences: list[essay_lib.Sentence]) -> tuple[list, dict]:
    task_type = submission["task_type"]
    visual = visual_available(submission)
    rules = [
        EXAMINER_ROLE,
        "Assess the ORIGINAL essay exactly as written.",
        DESCRIPTOR_NOTES[task_type] + COMMON_DESCRIPTORS,
        CALIBRATION,
        "Evidence rules: every band must be justified. 'summary' explains why this band "
        "(2-4 sentences). Every strength and every issue carries a 'quote' copied VERBATIM "
        "from the essay (a short span, max 25 words) so it can be located automatically; "
        "never paraphrase, translate or correct inside 'quote'. A criterion with no "
        "verifiable quote will be rejected.",
        'Output schema: {"criteria": {"task": C, "coherence": C, "lexical": C, '
        '"grammar": C}, "overall_comment": str, "priorities": [str, ...3-5]} where C = '
        '{"band": number, "summary": str, "strengths": [{"quote": str, "comment": str}, '
        '...1-3], "issues": [{"quote": str, "comment": str, "suggestion": str}, ...1-4]}. '
        "Do not output an overall band; it is computed from the criteria.",
    ]
    if task_type == "task1":
        rules.append(
            'Also return "consistency_issues": [{"quote": str, "comment": str}] listing places '
            "where the essay contradicts ITSELF. Check every superlative or comparison "
            "(highest, lowest, most, more than, overtook, doubled, in both years) against the "
            "figures the essay itself gives elsewhere, e.g. it calls A the highest in both years "
            "but gives C a larger figure in one year. Quote the contradicted claim verbatim. "
            "This is about internal consistency only, not about the chart. Use [] if none."
        )
    if not visual:
        rules.append(
            "The task visual is unavailable, so Task Achievement CANNOT be assessed: set "
            '"task": null. Assess only coherence, lexical and grammar from the text itself; '
            "overall_comment and priorities must address language and organisation only, "
            "never data accuracy or coverage of the chart."
        )
    system = " ".join(rules)
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
            f"Length: at least {minimum} words, ideally {minimum + 20}-{upper}; count before "
            "answering. One paragraph per line, separated by a blank line.",
            "If the student's essay does not answer the question that was asked (off-topic), do "
            "NOT polish the off-topic content: write an answer to the actual question, reusing "
            "the student's language only where relevant, and set original_addresses_question "
            "to false.",
            'key_changes are structured: each item is {"before": text copied EXACTLY from the '
            'student\'s essay, "after": text copied EXACTLY from your essay, "why": Chinese '
            'explanation}. Use a short phrase or sentence that pinpoints the change; use "" for '
            "before when text is added and for after when text is removed. List only changes "
            "that are really in your essay, never identical before/after, never word counts. "
            "If the student's essay already meets the target and you keep it unchanged, return "
            "it unchanged with key_changes [] and explain in unchanged_reason - do not invent "
            "changes.",
            "answers maps the question to your essay: list each requirement of the question "
            "(e.g. the position asked for, each side or part to discuss; for Task 1 the "
            "overview and the key comparisons), at least two, each with one sentence quoted "
            "EXACTLY from your essay that addresses it.",
            "band_rationale explains, criterion by criterion, what you changed TOWARDS the "
            f"Band {target:g} target. It must not claim that the essay reaches, meets or achieves "
            "any band - the rewrite has not been scored.",
            (
                (
                    "Task 1: include an overview and accurate key figures; no opinion."
                    if visual_available(submission)
                    else "Task 1: include an overview; no opinion. The visual is unavailable: use "
                    "ONLY figures already stated in the student's essay or the question, never add "
                    "or change data, and never claim the figures are accurate or verified. If the "
                    "student's own figures and comparisons contradict each other, do not repeat "
                    "the contradictory claim: keep the figures, word the comparison so it agrees "
                    "with them, and mention the contradiction in key_changes."
                )
                if task_type == "task1"
                else "Task 2: answer every part of the question with a clear position."
            ),
            'Output schema: {"essay": str, "original_addresses_question": bool, '
            '"answers": [{"part": str (Chinese), "quote": str (exact sentence from essay)}, '
            '...2-6], "key_changes": [{"before": str, "after": str, "why": str}, ...1-6], '
            '"unchanged_reason": str (only if the essay is unchanged), '
            '"band_rationale": str (Chinese, what was changed towards the target band; never '
            "claim a band or score was reached)}.",
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
        "This image should be the visual for an IELTS Academic Writing Task 1 question:\n"
        f"{submission['prompt_text']}\n\n"
        "Read ONLY what the image actually shows. Never guess or estimate a value you cannot "
        "read; list it under 'unclear' instead. Return ONLY one JSON object:\n"
        '{"readability": "sufficient" | "partial" | "unreadable", '
        '"visual_type": "bar_chart" | "line_graph" | "pie_chart" | "table" | "mixed_chart" | '
        '"map" | "process" | "other" | "none", '
        '"title": str, "units": str, "categories": [str], "periods": [str], '
        '"data_points": [{"label": str, "value": str}], '
        '"main_features": [str], "unclear": [str], "summary": str}\n'
        "- readability: 'sufficient' only if you can read enough exact labels and values to "
        "check an essay's figures and main trends; 'partial' if some key values or labels are "
        "illegible; 'unreadable' if the image is blank, blurry, not a chart/table/map/process, "
        "or otherwise cannot be read.\n"
        "- data_points: values exactly as printed or read off the axis, with units, e.g. "
        '{"label": "Museum A, 2020", "value": "140,000 visitors"}.\n'
        "- main_features: main trends, highest/lowest, comparisons; for maps the changes; for "
        "processes the stages in order.\n"
        "- summary: max 120 English words, factual, no essay advice."
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


def build_rewrite_notes(submission: dict, rewrite_essay: str, problems: str) -> tuple[list, dict]:
    """Ask only for corrected notes about an existing rewrite (the essay is kept)."""
    target = submission["target_band"]
    system = " ".join(
        [
            EXAMINER_ROLE,
            "You are given a student's essay and a rewritten version of it. The rewritten "
            "essay is FINAL: do not change it and do not return it.",
            "Return only the notes about it, as one JSON object: "
            '{"original_addresses_question": bool, "answers": [{"part": str (Chinese), '
            '"quote": str (exact sentence from the rewritten essay)}, ...2-6], '
            '"key_changes": [{"before": str (exact text from the student\'s essay), '
            '"after": str (exact text from the rewritten essay), "why": str (Chinese)}, ...0-6], '
            '"unchanged_reason": str (only if the two essays are identical), '
            '"band_rationale": str (Chinese)}.',
            "Copy before/after/quote text exactly. List only changes that really happened "
            "between the two essays. Never state word counts. Never claim the rewrite reaches, "
            f"meets or achieves Band {target:g} or any score.",
            f"Problems found in the previous notes: {problems}",
        ]
    )
    payload = {
        **_task_context(submission),
        "student_essay": submission["essay_text"],
        "rewritten_essay": rewrite_essay,
    }
    user = "Write the notes for this rewrite.\n" + json.dumps(payload, ensure_ascii=False, indent=1)
    context = {
        "kind": "rewrite",
        "mode": "notes",
        "original_essay": submission["essay_text"],
        "rewrite_essay": rewrite_essay,
    }
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], context


BUILDERS = {"evaluate": build_evaluate, "refine": build_refine, "rewrite": build_rewrite}
MAX_TOKENS = {
    "evaluate": 3000,
    "refine": 6000,
    "rewrite": 2400,
    "rewrite_notes": 1500,
    "describe_image": 700,
}
