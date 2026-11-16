import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.vocabulary_context import (
    ContextChoiceAvailability,
    _collocation_fill,
    _example_fill,
    build_context_question,
)
from services.vocabulary_synonyms import SYNONYM_SENSE_PREFIX


def word(index, **overrides):
    fields = dict(
        id=index,
        word=f"word{index}",
        accepted_answers=None,
        core_meaning_zh=f"释义{index}",
        translation="",
        example_en="An example sentence without the requested target.",
        example_zh="例句翻译",
        usage_pattern="",
        sense=None,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


class ContextChoiceAvailabilityTest(unittest.TestCase):
    def assert_equivalent(self, target, candidates, seed):
        index = ContextChoiceAvailability(candidates)
        expected = bool(
            build_context_question(
                target,
                candidates,
                seed=seed,
                allowed_kinds={"meaning_choice", "collocation_choice"},
            )
        )
        self.assertEqual(index.has_question(target, seed=seed), expected)

    def test_duplicate_first_three_remain_ineligible(self):
        target = word(1)
        candidates = [target] + [
            word(index, core_meaning_zh="重复" if index < 9 else f"释义{index}")
            for index in range(2, 13)
        ]
        results = []
        index = ContextChoiceAvailability(candidates)
        for attempt in range(40):
            seed = f"duplicate:{attempt}"
            expected = bool(build_context_question(target, candidates, seed=seed))
            self.assertEqual(index.has_question(target, seed=seed), expected)
            results.append(expected)
        self.assertIn(False, results)
        self.assertIn(True, results)

    def test_collocations_need_three_distinct_real_frames(self):
        target = word(
            1,
            word="depend",
            core_meaning_zh="",
            example_en="",
            usage_pattern="depend on",
        )
        candidates = [
            target,
            word(2, word="focus", usage_pattern="focus on"),
            word(3, word="contribute", usage_pattern="contribute to"),
            word(4, word="achieve", usage_pattern="achieve a goal"),
            word(5, word="support", usage_pattern="support a plan"),
        ]
        self.assertFalse(
            ContextChoiceAvailability(candidates[:4]).has_question(target, seed="x")
        )
        self.assertTrue(
            ContextChoiceAvailability(candidates).has_question(target, seed="x")
        )
        self.assert_equivalent(target, candidates, "x")
        candidates[-1].sense = SimpleNamespace(
            part_of_speech="synonym", canonical_key=""
        )
        self.assertFalse(
            ContextChoiceAvailability(candidates).has_question(target, seed="x")
        )

    def test_hash_ties_keep_original_catalog_order(self):
        target = word(1)
        candidates = [
            target,
            word(2),
            word(3, core_meaning_zh="释义2"),
            word(4),
            word(5),
        ]
        digest = SimpleNamespace(digest=lambda: b"same", hexdigest=lambda: "same")
        with patch("services.vocabulary_context.hashlib.sha256", return_value=digest):
            self.assert_equivalent(target, candidates, "collision")

    def test_new_request_index_observes_catalog_edits(self):
        target = word(1)
        candidates = [target, word(2), word(3), word(4)]
        self.assertTrue(
            ContextChoiceAvailability(candidates).has_question(target, seed="x")
        )
        candidates[-1].core_meaning_zh = "释义2"
        self.assertFalse(
            ContextChoiceAvailability(candidates).has_question(target, seed="x")
        )

    def test_randomized_choices_and_full_builder_eligibility_match(self):
        rng = random.Random(20261116)
        for catalog_id in range(100):
            candidates = []
            for _position in range(rng.randrange(0, 18)):
                lemma = rng.choice(
                    [
                        "depend",
                        "focus",
                        "achieve",
                        "can't",
                        "o’clock",
                        "n. work",
                        "a/b",
                        "",
                        "词",
                        "mp3 player",
                    ]
                )
                candidate = word(
                    rng.randrange(1, 20),
                    word=lemma,
                    accepted_answers=rng.choice(
                        [
                            None,
                            '["support", "help"]',
                            ["support", "help"],
                            "assist; aid",
                        ]
                    ),
                    core_meaning_zh=rng.choice(["", "甲", "乙", "丙", "丁", "  甲  "]),
                    translation=rng.choice(["", "戊"]),
                    example_en=rng.choice(
                        [
                            "",
                            "short",
                            f"We {lemma} in a useful example.",
                            "This sentence has another target.",
                        ]
                    ),
                    example_zh=rng.choice(["", "翻译"]),
                    usage_pattern=rng.choice(
                        [
                            "",
                            f"{lemma} on",
                            f"{lemma} a plan",
                            f"{lemma} to",
                            f"{lemma} with help",
                            "已经填好中文",
                            "x" * 101,
                        ]
                    ),
                )
                if rng.randrange(8) == 0:
                    candidate.sense = SimpleNamespace(
                        part_of_speech="", canonical_key=SYNONYM_SENSE_PREFIX + "broken"
                    )
                candidates.append(candidate)
                if rng.randrange(10) == 0:
                    candidates.append(candidate)
            index = ContextChoiceAvailability(candidates)
            for target in candidates + [word(999)]:
                for rotation in (0, 1, 3):
                    seed = f"random:{catalog_id}:{rotation}"
                    expected_choice = bool(
                        build_context_question(
                            target,
                            candidates,
                            seed=seed,
                            rotation=rotation,
                            allowed_kinds={"meaning_choice", "collocation_choice"},
                        )
                    )
                    with self.subTest(
                        catalog=catalog_id, target=target.id, rotation=rotation
                    ):
                        self.assertEqual(
                            index.has_question(target, seed=seed), expected_choice
                        )
                        if target.sense is None:
                            available = bool(
                                _example_fill(target, seed)
                                or _collocation_fill(target, seed)
                                or index.has_question(target, seed=seed)
                            )
                            self.assertEqual(
                                available,
                                bool(
                                    build_context_question(
                                        target, candidates, seed=seed, rotation=rotation
                                    )
                                ),
                            )


if __name__ == "__main__":
    unittest.main()
