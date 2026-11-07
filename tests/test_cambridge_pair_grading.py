"""Two visible blanks -> real browser save contract -> real server grading."""

import copy
import json
import subprocess
import unittest
from pathlib import Path

from services.ielts_exam_payload import build_simulation_payload
from services.ielts_practice_scoring import grade_listening_test_answers, grade_reading_test_answers

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = [
    ("listening", "ielts4_test1", 11, "coal", "firewood"),
    ("listening", "ielts6_test1", 7, "10", "4.30"),
    ("listening", "ielts6_test1", 19, "Monday", "Thursday"),
    ("listening", "ielts6_test1", 32, "metal", "leather"),
    ("listening", "ielts6_test3", 36, "water", "sand"),
    ("listening", "ielts9_test1", 33, "plants", "fish"),
    ("listening", "ielts9_test2", 12, "Friday", "Sunday"),
    ("reading", "ielts4_test1_reading", 21, "bowhead", "humpback"),
    ("reading", "ielts7_test2_reading", 26, "farmers", "consumers"),
    ("reading", "ielts9_test3_reading", 33, "Jupiter", "Saturn"),
    ("reading", "ielts9_test3_reading", 35, "sensors", "circuits"),
    ("reading", "ielts10_test2_reading", 23, "books", "activities"),
]


class CambridgePairGradingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = []
        cls.sources = {}
        for subject, test_id, number, left, right in FIXTURES:
            payload = json.loads(
                (ROOT / "static" / f"{subject}_tests" / f"{test_id}.json").read_text()
            )
            unit_key = "sections" if subject == "listening" else "passages"
            question = next(
                q
                for unit in payload[unit_key]
                for group in unit["groups"]
                for q in group["questions"]
                if q["number"] == number
            )
            cls.sources[(subject, test_id)] = payload
            variants = [
                ("complete", [left, right], 1),
                ("left_only", [left, ""], 0),
                ("right_only", ["", right], 0),
                ("wrong", [left, "incorrect-value"], 0),
                ("blank", ["", ""], 0),
            ]
            if subject == "listening" and (test_id, number) in {
                ("ielts4_test1", 11),
                ("ielts6_test1", 19),
                ("ielts6_test1", 32),
            }:
                variants.append(("reverse", [right, left], 1))
            if subject == "listening" and test_id == "ielts6_test1" and number == 7:
                variants.extend(
                    [("reverse", [right, left], 0), ("explicit_times", ["10 am", "4.30 pm"], 1)]
                )
            for mode in ("ordinary", "simulation"):
                public = (
                    payload if mode == "ordinary" else build_simulation_payload(payload, subject)
                )
                for variant, parts, expected in variants:
                    cls.cases.append(
                        {
                            "name": f"{test_id}:Q{number}:{mode}:{variant}",
                            "subject": subject,
                            "test_id": test_id,
                            "id": str(question["id"]),
                            "number": number,
                            "payload": public,
                            "parts": parts,
                            "expected": expected,
                        }
                    )
        output = subprocess.check_output(
            ["node", str(ROOT / "tests/helpers/cambridge_pair_answers.js")],
            input=json.dumps(cls.cases).encode(),
            cwd=ROOT,
        )
        cls.serialized = {row["name"]: row for row in json.loads(output)}

    def test_actual_saved_values_grade_as_one_mark_and_require_both_parts(self):
        for case in self.cases:
            with self.subTest(case=case["name"]):
                source = self.sources[(case["subject"], case["test_id"])]
                before = copy.deepcopy(source)
                grader = (
                    grade_listening_test_answers
                    if case["subject"] == "listening"
                    else grade_reading_test_answers
                )
                saved = self.serialized[case["name"]]
                result = grader(source, {saved["id"]: saved["value"]})
                row = next(row for row in result["results"] if case["id"] in row["ids"])
                self.assertEqual(row["marks"], 1)
                self.assertEqual(row["awarded"], case["expected"], saved["value"])
                self.assertEqual(source, before)


if __name__ == "__main__":
    unittest.main()
