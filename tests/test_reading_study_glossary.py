"""Role → grammar-concept labels for Reading Study (needs only Flask, for api/__init__).

Run standalone:
    python -m unittest tests.test_reading_study_glossary -v
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.reading_study_glossary import glossary_payload, resolve_role  # noqa: E402


def label(role):
    resolved = resolve_role(role)
    return resolved["concept"], resolved["zh"]


class UnflavoredClauseTest(unittest.TestCase):
    """*_clause roles that used to fall back to 状语从句 (2026-10-19)."""

    def test_sentence_types(self):
        self.assertEqual(label("interrogative_clause"), ("main_clause", "疑问句"))
        self.assertEqual(label("question_clause"), ("main_clause", "疑问句"))
        self.assertEqual(label("second_interrogative_clause"), ("main_clause", "疑问句"))
        self.assertEqual(label("imperative_clause"), ("main_clause", "祈使句"))
        self.assertEqual(label("exclamatory_clause"), ("main_clause", "感叹句"))

    def test_elliptical(self):
        self.assertEqual(label("elliptical_clause"), ("generic_phrase", "省略结构"))
        self.assertEqual(label("elliptical_time_clause"), ("adverbial_clause", "时间状语从句"))
        self.assertEqual(label("elliptical_adverbial_clause"), ("adverbial_clause", "状语从句"))
        # Other elliptical_* roles used to fall back to 语法成分.
        self.assertEqual(label("elliptical_question"), ("generic_phrase", "省略结构"))
        self.assertEqual(label("ellipsis"), ("generic_phrase", "省略结构"))
        self.assertEqual(label("elliptical_predicate"), ("verb_phrase", "谓语"))

    def test_non_finite_and_noun_clauses(self):
        self.assertEqual(label("infinitive_clause")[0], "infinitive_phrase")
        self.assertEqual(label("participle_clause")[0], "participial_phrase")
        self.assertEqual(label("gerund_clause")[0], "gerund_phrase")
        self.assertEqual(label("prepositional_participial_clause")[0], "prepositional_phrase")
        self.assertEqual(label("nominal_clause")[0], "noun_clause")
        self.assertEqual(label("whether_clause")[0], "noun_clause")

    def test_flavor_inside_the_name(self):
        self.assertEqual(label("reduced_time_clause"), ("adverbial_clause", "时间状语从句"))
        self.assertEqual(label("temporal_clause"), ("adverbial_clause", "时间状语从句"))
        self.assertEqual(label("causal_clause"), ("adverbial_clause", "原因状语从句"))
        self.assertEqual(label("reduced_concessive_clause"), ("adverbial_clause", "让步状语从句"))

    def test_main_clauses(self):
        self.assertEqual(label("independent_clause"), ("main_clause", "主句"))
        self.assertEqual(label("clause"), ("main_clause", "分句"))

    def test_existing_labels_unchanged(self):
        self.assertEqual(label("time_clause"), ("adverbial_clause", "时间状语从句"))
        self.assertEqual(label("purpose_infinitive_clause"), ("adverbial_clause", "目的状语从句"))
        self.assertEqual(label("relative_clause"), ("relative_clause", "定语从句"))
        self.assertEqual(label("subject_clause")[0], "noun_clause")
        self.assertEqual(label("reporting_clause")[0], "reporting_clause")
        # Mixed in the data ("whilst ..." and "but ..."), so the name alone cannot decide.
        self.assertEqual(label("contrastive_clause"), ("adverbial_clause", "状语从句"))
        self.assertEqual(label("comment_clause"), ("adverbial_clause", "状语从句"))

    def test_every_corpus_role_has_a_glossary_entry(self):
        concepts = glossary_payload()["concepts"]
        for path in sorted((ROOT / "data" / "reading_study").glob("*.json")):
            for sentence in json.loads(path.read_text(encoding="utf-8"))["sentences"]:
                for span in sentence["structure"]:
                    with self.subTest(role=span["role"]):
                        self.assertIn(resolve_role(span["role"])["concept"], concepts)


if __name__ == "__main__":
    unittest.main()
