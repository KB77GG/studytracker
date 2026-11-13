"""Prompt builders.  Bump PROMPT_VERSION whenever any prompt text changes."""

from __future__ import annotations

import json

from . import argument as argument_lib
from . import essay as essay_lib

PROMPT_VERSION = "iwa-2026-11-13.15"

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

ARGUMENT_CHECKLIST = (
    "Argument check (Task 2): a diagnosis whose findings explain Task Response or Coherence "
    "& Cohesion, whichever each one evidences; it is NOT a separate score. Judge the WHOLE essay and report only real faults. "
    "(0) Question type: identify what the question requires (discuss both views AND give "
    "an opinion; to what extent agree; whether advantages outweigh disadvantages; two "
    "questions) and check every required part is answered in that form; a missing part "
    "(no own opinion, no verdict on 'outweigh') is a Task Response issue. "
    "(1) Position. A qualified position is ONE position, e.g. 'mostly X, but Y where "
    "necessary' or 'partly agree': naming exceptions or admitting the other side "
    "is sometimes needed is neither unclear nor inconsistent. Vague wording that the body or "
    "conclusion makes clear is at most an improvement. unclear_position = after reading the "
    "whole essay a reader still cannot tell what the writer thinks. inconsistent_position / "
    "conclusion_inconsistent = two passages that genuinely cannot both be true; quote BOTH "
    "('quote' and 'conflicts_with'). A conclusion that restates the main side without "
    "repeating the exceptions is consistent. "
    "(2) Relevance. off_position only when a paragraph argues something that serves neither "
    "the position nor the question; a paragraph explaining an exception the qualified "
    "position already allows, or a concession, is not off_position. "
    "(3) Support takes several valid forms: a causal explanation (because / so / which "
    "means / therefore), a comparison, consequences, or a personal or hypothetical example. "
    "A named city, study or statistic is NEVER required. unsupported only when a point is "
    "merely asserted with no reason at all; a reason that is present but brief is an "
    "improvement, not a problem. example_not_linked only when an example is given and "
    "nothing connects it to the point. Before reporting either, read the WHOLE paragraph "
    "and list in 'support_found' every span that gives a reason, mechanism or example for "
    "the point, or states the claim the example illustrates: a clause (because / so / "
    "where / which / if ... then) or a neighbouring sentence counts, and an example right "
    "after the claim it illustrates is linked without any closing 'this shows' sentence. "
    "If you find any, the point is supported: put the advice in 'improvements' instead. "
    "(4) Concession. A concession that sets the scope of the position needs no rebuttal. "
    "concession_unanswered only when an opposing argument that weakens the position is "
    "raised and the essay never returns to its position; concession_undermines only when "
    "the concession outweighs the essay's own argument. "
    "(5) Your map must agree with itself: if position.consistent is true, report no "
    "inconsistent_position or conclusion_inconsistent; a paragraph whose verdict is "
    "'supports' cannot also be off_position. "
    "Optional ways to make a sound argument stronger (more detail, a sharper topic sentence, "
    "an extra example) go in 'improvements', never in 'problems'. Never invent facts: no "
    "statistic, percentage, year, study or named real-world case that is not in the essay; "
    "use the essay's own reasoning or a hypothetical example described in words only - no "
    "number, count, percentage, year or multiplier the essay does not give. Reflect each "
    "real problem in the summary of the criterion it evidences; improvements do not lower "
    "bands."
)

CRITERION_SCHEMA = (
    'C = {"band": number, "strengths": [{"quote": str, "comment": str (Chinese)}, ...1-3], '
    '"issues": [{"quote": str, "comment": str (Chinese), "suggestion": str}, ...0-4; [] '
    'when there is no clear error or weakness], "summary": str (Chinese)}'
)


def _argument_schema() -> str:
    types = " | ".join(f'"{key}"' for key in argument_lib.PROBLEM_TYPES)
    return (
        'A = {"paragraphs": [{"p": int '
        '(the paragraph number in essay_paragraphs), "role": "introduction" | "body" | '
        '"concession" | "conclusion", "main_point": str (that paragraph\'s central sentence, '
        'verbatim), "verdict": "supports" | "weak" | "off_position", "comment": str '
        "(Chinese)}, ...exactly one per paragraph of essay_paragraphs, in order], "
        f'"problems": [{{"type": {types}, "quote": str (verbatim), "conflicts_with": str '
        "(verbatim; REQUIRED for inconsistent_position and conclusion_inconsistent: the other "
        'passage it contradicts), "support_found": [str (verbatim)] (REQUIRED for unsupported '
        "and example_not_linked: what the same paragraph already offers for the point; [] "
        'only if nothing), "comment": str (Chinese), "suggestion": str (Chinese)}, '
        '...0-6], "improvements": [{"quote": str (verbatim), "suggestion": str (Chinese: what '
        "to add or sharpen; the key is 'suggestion', not 'comment')}, ...0-3], "
        '"position": {"quote": str (the sentence that states the position, verbatim), '
        '"consistent": bool, "comment": str (Chinese)} or null}. If there is '
        "no clear position, set position to null and add an "
        "unclear_position problem quoting the closest sentence. Do not invent problems: a "
        "well-argued essay may have no problems."
    )


COMPARISON_SCHEMA = (
    'K = {"claim": str (verbatim: a sentence or clause that ranks or compares, e.g. highest, '
    'lowest, most, more/less than, overtook, doubled, throughout, all), "figures": [str '
    "(verbatim figures from the essay that decide the claim - for holds=false the ones that "
    'contradict it, first; at most 4, not every figure in the essay)], "holds": bool, '
    '"comment": str (Chinese)}'
)
COMPARISON_RULE = (
    'Internal consistency (Task 1): in "comparisons" list EVERY ranking or comparison claim '
    "in the essay and check it against the figures the essay itself gives elsewhere; "
    "holds=false when the essay's own figures contradict it (e.g. it calls one item the "
    "highest throughout but gives another a larger figure at some point). This is about the "
    "essay agreeing "
    "with itself only, not about the chart."
)


ROOT_TEXT_RULES = (
    "overall_comment = str (Chinese); priorities = [str (Chinese), ...3-5, the most useful "
    "first]."
)
# Placeholders in the example can never pass validation if copied: no band is -1 and
# no quote is "<...>", so a copied example is rejected, never scored.
EXAMPLE_BAND = -1


def _example_criterion() -> dict:
    # Ends with a plain field (summary), not a list - see _root_schema.
    return {
        "band": EXAMPLE_BAND,
        "strengths": [{"quote": "<原文逐字引文>", "comment": "<中文说明>"}],
        "issues": [{"quote": "<原文逐字引文>", "comment": "<中文说明>", "suggestion": "<改法>"}],
        "summary": "<中文评分理由，2-4 句>",
    }


def evaluate_example(task_type: str, visual: bool) -> dict:
    """A complete, parseable answer with placeholders: the exact nesting to copy."""
    criteria = {key: _example_criterion() for key in essay_lib.CRITERIA}
    if not visual:
        criteria["task"] = None
    example: dict = {"criteria": criteria}
    if task_type == "task2":
        example["argument"] = {
            "paragraphs": [
                {
                    "p": 1,
                    "role": "introduction",
                    "main_point": "<该段中心句，逐字>",
                    "verdict": "supports",
                    "comment": "<中文>",
                }
            ],
            "problems": [
                {
                    "type": "<上面列出的问题类型之一>",
                    "quote": "<原文逐字引文>",
                    "comment": "<中文>",
                    "suggestion": "<中文>",
                }
            ],
            "improvements": [{"quote": "<原文逐字引文>", "suggestion": "<中文>"}],
            # Ends with a plain field (position), not a list - see _root_schema.
            "position": {"quote": "<立场句，逐字>", "consistent": True, "comment": "<中文>"},
        }
    else:
        example["comparisons"] = [
            {
                "claim": "<比较或排序说法，逐字>",
                "figures": ["<原文数字，逐字>"],
                "holds": True,
                "comment": "<中文>",
            }
        ]
    example["overall_comment"] = "<中文总评>"
    example["priorities"] = ["<中文提升重点>", "<中文提升重点>", "<中文提升重点>"]
    return example


def _root_schema(task_type: str, visual: bool) -> str:
    """The whole answer as one complete, parseable example plus the field rules.

    History: .8 described the shape with C / A placeholders inside "criteria"; real runs
    forgot the brace that closes criteria (2026-11-04 weak, 2026-11-06 under-length x2).
    .9 moved the criteria to the top level: brace errors did not go away and two of
    seven answers wrote the criteria as bare numbers ("task": 7.0). .10 went back to
    "criteria" with the full nesting as real JSON; mid still left argument unclosed
    twice (2026-11-09). Six of the seven brace errors in real runs had the same shape: a
    brace missing right after a list closed (issues / improvements], then the object's
    }); the seventh (2026-11-06 off-topic) closed argument too early. From .11 a criterion
    ends with summary (a string) and argument with position (an object ending in its
    comment, or null), so in the example no more than two brackets close in a row. The
    root object still ends with the priorities list."""
    nested = "argument" if task_type == "task2" else "comparisons"
    example = json.dumps(evaluate_example(task_type, visual), ensure_ascii=False)
    return " ".join(
        [
            "Return exactly ONE JSON object nested exactly like this complete example. "
            "Replace every <...> placeholder and every band -1 with your own content; copy "
            "nothing else from it; lists have as many items as the rules allow (issues may "
            "be [], paragraphs has exactly one entry per paragraph):",
            example,
            "Field rules:",
            ROOT_TEXT_RULES,
            CRITERION_SCHEMA,
            _argument_schema() if task_type == "task2" else COMPARISON_SCHEMA,
            "Inside criteria every criterion is an object with band, strengths, issues and "
            "summary - never a bare number. Keep the key order of the example: a criterion "
            "ends with summary and argument ends with position, after their lists, so close "
            "the list, write that field, then close the object. Close "
            "each criterion object, then the criteria "
            f"object, before {nested}; {nested}, overall_comment and priorities sit next to "
            "criteria, never inside it. Do not output an overall band; it is computed from "
            "the criteria.",
        ]
    )


def evaluate_shape(submission: dict) -> tuple[tuple[str, ...], dict[str, str]]:
    """(top-level keys, key -> where it belongs) of an evaluation, for jsonshape.diagnose."""
    task2 = submission["task_type"] == "task2"
    # The criteria belong in "criteria"; the .9 top-level form is still accepted.
    root = ("criteria", *essay_lib.CRITERIA, "argument" if task2 else "comparisons")
    root += ("overall_comment", "priorities")
    homes = dict.fromkeys(essay_lib.CRITERIA, "criteria")
    homes.update(dict.fromkeys(("band", "summary", "strengths", "issues"), "评分项"))
    if task2:
        homes.update(
            dict.fromkeys(("position", "paragraphs", "problems", "improvements"), "argument")
        )
    else:
        homes.update(dict.fromkeys(("claim", "holds"), "comparisons"))
    return root, homes


CHINESE_REMINDER = (
    "请注意：所有解释（summary、comment、overall_comment、priorities 以及中文 suggestion）"
    "都用简体中文书写；引文和英文改写句保持英文原样。"
)


# No assumed score range for the writer (".7" told the model most candidates sit at
# 5.0-6.5, which can pull strong essays down and push it to find faults).
CALIBRATION = (
    "Calibration rules: judge each essay only on its own evidence against the band "
    "descriptors; do not inflate or deflate, and do not assume a typical score for the "
    "writer. Award 7.0+ in a criterion only when its higher-band features are clearly and "
    "consistently present; award 8.0+ only for near-error-free, sophisticated writing. "
    "Each criterion band is independent; use 0.5 steps between 0 and 9."
)

# What evidences which criterion (IELTS writing assessment criteria, checked 2026-11-09:
# ielts.org writing-test-resources / academic-format-writing). .11 put all argument quality
# under Task Response, which contradicted the argument check feeding Coherence & Cohesion;
# logical progression and the organisation of ideas are Coherence & Cohesion features.
CRITERION_BOUNDARIES = {
    "task2": (
        "Criterion boundaries: assess task fulfilment, position, relevance, and the "
        "development and support of ideas under Task Response; assess the organisation of "
        "ideas, logical progression, paragraphing, cohesive links and referencing under "
        "Coherence & Cohesion. Map each argument finding to the criterion feature it "
        "actually evidences (a point with no reason is Task Response; a paragraph that "
        "breaks the line of reasoning is Coherence & Cohesion), without repeating the same "
        "finding mechanically in both."
    ),
    "task1": (
        "Criterion boundaries: assess the overview, the selection and accuracy of key "
        "features and data under Task Achievement; assess the organisation of information, "
        "logical progression, paragraphing, cohesive links and referencing under "
        "Coherence & Cohesion."
    ),
}
LANGUAGE_BOUNDARY = (
    "Justify Lexical Resource and Grammatical Range & Accuracy with lexical and grammatical "
    "evidence only: never infer a language weakness from off-topic content, missing data or "
    "weak support (an off-topic essay can still use varied, accurate grammar)."
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
        if visual_available(submission) and submission.get("image_description"):
            # Only a reading a person checked against the image (.15): the first real
            # reading was well formed but had wrong values (2026-11-13).
            context["visual_summary"] = submission["image_description"]
            context["visual_note"] = (
                "visual_summary was read from the task image by a vision model and then "
                "checked against the image by a person; use it to check data accuracy."
            )
        else:
            context["visual_note"] = (
                "The task visual is NOT available (no image, or it could not be read). You "
                "cannot know the real data: never state, check or invent figures, trends or "
                "chart features beyond what the question text itself says."
            )
    return context


def image_check(submission: dict) -> dict | None:
    """A person's check of the chart reading: {"status": "confirmed" | "skipped", ...}."""
    raw = submission.get("image_check")
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def awaiting_image_check(submission: dict) -> bool:
    """A well-formed reading nobody has checked or skipped yet."""
    return (
        submission["task_type"] == "task1"
        and submission.get("image_status") == "ready"
        and image_check(submission) is None
    )


def visual_available(submission: dict) -> bool:
    """Task 1 data can be checked only against a reading a person confirmed: a
    well-formed reading ("ready") can still have wrong values."""
    if submission["task_type"] != "task1":
        return True
    return (
        submission.get("image_status") == "ready"
        and (image_check(submission) or {}).get("status") == "confirmed"
    )


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
        CRITERION_BOUNDARIES[task_type] + " " + LANGUAGE_BOUNDARY,
        "Evidence rules: every band must be justified. 'summary' explains why this band "
        "(2-4 sentences). Every strength and every issue carries a 'quote' copied VERBATIM "
        "from the essay (a short span, max 25 words) so it can be located automatically; "
        "never paraphrase, translate or correct inside 'quote'. A criterion with no "
        "verifiable quote will be rejected. An issue must be an error or a clear weakness; "
        "an equally good alternative wording is not an issue. Call development brief when "
        "a point is explained briefly; say it is not explained only when no reason or "
        "example is given at all. Report only issues you are "
        "sure of: a criterion may have no issues at all (then its strengths carry the "
        "evidence) - never invent one to fill the list.",
        "Language feedback has three kinds - say which one it is: an error (wrong form, "
        "word or meaning), wording that is unclear or imprecise, and an optional "
        "alternative (style, register, variety). Accurate, neutral everyday wording is "
        "neither an error nor impolite; a more formal or more varied alternative is "
        "optional, is not an issue, and if mentioned must be called optional. Before "
        "saying the essay lacks a structure (passives, conditionals, relative clauses ...), "
        "check that it does not already use one. "
        "Language advice: read the whole sentence before calling a structure wrong (a "
        "correct relative clause or a natural comparative phrase is not an "
        "error, and accurate, natural wording comes before rarer words). A correction or "
        "model sentence must keep the writer's meaning: never add facts, causes, figures, "
        "multipliers or trends the writer did not state (do not turn a stated fact into a "
        "different cause, or two data points into a continuous trend). Give a "
        "complete, usable sentence, not a fragment, and one that works in place: put back "
        "instead of the quote it must leave a correct sentence - if the surrounding "
        "sentence would still be wrong (e.g. a stand-alone Because-clause), quote the whole "
        "sentence and correct the whole sentence. Call something a grammar error only when "
        "it is one: clauses joined by and/but may have different subjects, and an -ing "
        "clause whose subject is clear from the sentence is not dangling. A more precise "
        "wording (e.g. naming the measured figure instead of the thing it belongs to) "
        "is a precision point: present it as one, in the issue and in priorities, never as "
        "a grammar error. Before describing what a paragraph or the overview says, check "
        "that it really says it.",
        "Counts must match the essay: paragraph_count is given (one paragraph per line); "
        "only say a word is repeated if it really appears several times.",
        "overall_comment and priorities summarise your own findings: never call something "
        "missing or weak there (e.g. calling a point unexplained or barely mentioned) "
        "that your criteria or argument analysis says the essay already does. A priority may "
        "suggest going further, but then say what is already there.",
    ]
    if task_type == "task2":
        rules.append(ARGUMENT_CHECKLIST)
    else:
        rules.append(COMPARISON_RULE)
    rules.append(_root_schema(task_type, visual))
    if not visual:
        rules.append(
            "The task visual is unavailable, so Task Achievement CANNOT be assessed: set "
            '"task": null. Assess only coherence, lexical and grammar from the text itself; '
            "overall_comment and priorities must address language and organisation only, "
            "never data accuracy or coverage of the chart."
        )
    system = " ".join(rules)
    payload = {
        **_task_context(submission),
        "paragraph_count": len(essay_lib.split_paragraphs(submission["essay_text"])),
    }
    if task_type == "task2":
        # Numbered so the argument map is bound to the real paragraphs.
        payload["essay_paragraphs"] = [
            {"p": n, "text": text}
            for n, text in enumerate(essay_lib.split_paragraphs(submission["essay_text"]), 1)
        ]
    else:
        payload["essay"] = submission["essay_text"]
    copied = essay_lib.confirmed_copies(submission)
    if copied:
        # Only copying a person confirmed (.14): a text comparison is never sent, since
        # sentences that reuse the question's words often add the writer's own trend,
        # stance or data (review f46756f). Every other essay's messages are unchanged.
        payload["copied_from_question"] = [
            {"p": s["p"], "text": s["text"]} for s in copied["spans"]
        ]
        payload["word_count_without_copied"] = submission["word_count"] - copied["words"]
        payload["copied_note"] = (
            "A reviewer confirmed that the passages in copied_from_question were copied from "
            "the question. As in the test, words copied from the question do not count "
            "towards the word count and are not the candidate's own ideas or language: judge "
            "length by word_count_without_copied and do not credit those passages for task "
            "response, development, vocabulary or grammar. Everything else in the essay is "
            "the candidate's own and is assessed as usual. You may say in the feedback that "
            "the question was copied."
        )
    user = (
        "Evaluate this IELTS essay.\n"
        + json.dumps(payload, ensure_ascii=False, indent=1)
        + "\n"
        + CHINESE_REMINDER
    )
    context = {
        "kind": "evaluate",
        "task_type": task_type,
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
                else "Task 2: answer every part of the question with one clear position, stated "
                "in the introduction and kept to the conclusion. Fix the argument, not only the "
                "language: every body paragraph's main point must support that position; develop "
                "each point as claim -> why -> example -> result linked back to the claim; a "
                "concession must be followed by a rebuttal that returns to the position. When a "
                "key change fixes the argument, name the problem in its why (e.g. 例子未回扣论点, "
                "分论点偏离立场, 让步后没有反驳)."
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
    "evaluate": 4500,  # Task 2 also returns the argument map (real runs: ~1.6k without it)
    "refine": 6000,
    "rewrite": 2400,
    "rewrite_notes": 1500,
    "describe_image": 2000,  # fallback; Settings.vision_max_tokens (IWA_VISION_MAX_TOKENS) is used
}
