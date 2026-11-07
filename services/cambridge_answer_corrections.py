"""Four reviewed listening answer keys for future grading and review copies.

This is deliberately separate from editorial corrections. Callers must copy a
frozen snapshot before applying it; existing results and scores are never read
or recomputed here. Every slash-delimited alternative is a complete answer.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "cambridge_content_corrections"
    / "listening_answers.json"
)
_REVIEWED_TARGETS = {"ielts4_test1": {"11"}, "ielts6_test1": {"7", "19", "32"}}


@lru_cache(maxsize=1)
def _load_answer_corrections() -> dict:
    tests = json.loads(_MANIFEST.read_text(encoding="utf-8"))["tests"]
    if set(tests) != set(_REVIEWED_TARGETS):
        raise ValueError("Unexpected Cambridge answer correction tests")
    for test_id, correction in tests.items():
        questions = correction.get("questions", {})
        if set(correction) != {"questions"} or set(questions) != _REVIEWED_TARGETS[test_id]:
            raise ValueError(f"Unexpected Cambridge answer correction scope: {test_id}")
        for number, patch in questions.items():
            if set(patch) != {"answer"} or not isinstance(patch["answer"], str):
                raise ValueError(f"Invalid Cambridge answer correction: {test_id}/{number}")
            if not all(part.strip() for part in patch["answer"].split("/")):
                raise ValueError(f"Empty Cambridge answer alternative: {test_id}/{number}")
    return tests


def apply_listening_answer_corrections(payload: dict) -> dict:
    """Apply only the four vetted keys in place and derive their alternatives.

    Full papers use payload.id/number. Specialty copies use source_test_id or
    source_meta.test_id and source_number, keeping their rewritten IDs intact.
    The function never writes to storage or changes saved grading results.
    """
    tests = _load_answer_corrections()
    units = payload.get("sections") or ([payload] if payload.get("groups") else [])
    for unit in units:
        test_id = unit.get("source_test_id") or payload.get("id")
        for group in unit.get("groups") or []:
            group_test = (group.get("source_meta") or {}).get("test_id") or test_id
            patches = tests.get(group_test, {}).get("questions", {})
            for question in group.get("questions") or group.get("items") or []:
                number = question.get("source_number", question.get("number"))
                patch = patches.get(str(number))
                if patch:
                    question["answer"] = patch["answer"]
                    question["answers"] = [part.strip() for part in patch["answer"].split("/")]
    return payload
