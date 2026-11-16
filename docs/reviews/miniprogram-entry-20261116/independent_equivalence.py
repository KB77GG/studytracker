"""Independent deterministic, synthetic context-eligibility comparison."""

import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from services.vocabulary_context import (  # noqa: E402
    ContextChoiceAvailability,
    _collocation_fill,
    _example_fill,
    build_context_question,
)
from services.vocabulary_mastery import _question_for  # noqa: E402
from services.vocabulary_synonyms import SYNONYM_SENSE_PREFIX, is_synonym_word  # noqa: E402


def main():
    rng = random.Random(614116)
    checks = 0
    for catalog in range(450):
        rows = []
        for i in range(rng.randrange(0, 26)):
            lemma = rng.choice([
                "depend", "focus", "help", "assist", "work", "long-term",
                "o’clock", "can't", "", "word / term", "词汇", "value2", "N/A", None,
            ])
            rows.append(SimpleNamespace(
                id=i + 1,
                sense_id=100 + i,
                word=lemma,
                accepted_answers=rng.choice([
                    None, '["assist", "help"]', ["aid", "help"],
                    "support;assist", "bad[json",
                ]),
                core_meaning_zh=rng.choice(["", "甲", "乙", "丙", "丁", "\t甲  ", None, 0]),
                translation=rng.choice(["", "后备", None]),
                example_en=rng.choice([
                    "", None, "short",
                    "An unrelated target in a sufficiently long sentence.",
                    f"We {lemma} and {lemma} together.",
                ]),
                example_zh=rng.choice(["", None, "例句中文"]),
                usage_pattern=rng.choice([
                    "", None, f"{lemma} on", f"{lemma} to", f"{lemma} a goal",
                    f"{lemma} with help", f"{lemma} of", f"{lemma} through",
                    f"{lemma} 中文", "x" * 110,
                ]),
                sense=None,
            ))
            if rng.randrange(15) == 0:
                rows[-1].sense = SimpleNamespace(
                    part_of_speech="synonym", canonical_key=SYNONYM_SENSE_PREFIX + "broken",
                )
            if rng.randrange(12) == 0:
                rows.append(rows[-1])
        index = ContextChoiceAvailability(rows)
        for target in rows[::2]:
            for goal in ["reading", "listening", "writing", "comprehensive"]:
                for stage in [0, 1, 3, 9]:
                    seed = f"v2:{target.id}:{target.sense_id}:context_use:{goal}:{stage}"
                    result = index.has_question(target, seed=seed)
                    expected = bool(build_context_question(
                        target, rows, seed=seed, rotation=stage,
                        allowed_kinds={"meaning_choice", "collocation_choice"},
                    ))
                    assert result == expected, (catalog, target.id, seed, result, expected)
                    if not is_synonym_word(target):
                        eligible = bool(
                            _example_fill(target, "eligibility")
                            or _collocation_fill(target, "eligibility")
                            or result
                        )
                        expected_full = bool(_question_for(
                            target, "context_use", goal, stage, rows,
                        ))
                        assert eligible == expected_full, (
                            catalog, target.id, seed, "full", eligible, expected_full,
                        )
                    checks += 1
    report = {
        "random_seed": 614116,
        "catalogs": 450,
        "independent_equivalence_checks": checks,
        "mismatches": 0,
        "synthetic_only": True,
        "database_or_network_used": False,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
