import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_listening_test_practice as builder
from services import cambridge_answer_corrections as corrections
from services.ielts_practice_scoring import grade_listening_test_answers
from services.question_type_review import review_snapshot

ROOT = Path(__file__).resolve().parents[1]
OLD_KEYS = {
    ("ielts4_test1", 11): "coal and firewood",
    ("ielts6_test1", 7): "10 am / 10 / 4.30 pm / 4.30 / 4:30 / 4:30 pm",
    ("ielts6_test1", 19): "Monday / Thursday / Monday and Thursday / Thursday and Monday",
    ("ielts6_test1", 32): "metal / leather",
}


def old_paper(test_id):
    data = json.loads((ROOT / "static/listening_tests" / f"{test_id}.json").read_text())
    for section in data["sections"]:
        for group in section["groups"]:
            for q in group["questions"]:
                old = OLD_KEYS.get((test_id, q["number"]))
                if old:
                    q["answer"] = old
                    q["answers"] = [part.strip() for part in old.split("/")]
    return data


def question_by_number(data, number):
    return next(
        q
        for section in data["sections"]
        for group in section["groups"]
        for q in group["questions"]
        if q["number"] == number
    )


class CambridgeAnswerCorrectionsTest(unittest.TestCase):
    def assert_grade(self, test_id, number, value, awarded):
        data = old_paper(test_id)
        before = copy.deepcopy(data)
        q = question_by_number(data, number)
        result = grade_listening_test_answers(data, {str(q["id"]): value})
        row = next(row for row in result["results"] if number in row["numbers"])
        self.assertEqual((row["awarded"], row["marks"]), (awarded, 1))
        self.assertEqual(data, before)
        return row

    def test_both_parts_required_for_four_reviewed_questions(self):
        for test_id, number, accepted, rejected in [
            (
                "ielts4_test1",
                11,
                ["coal and firewood", "firewood and coal", "coal firewood", "firewood, coal"],
                ["coal", "firewood", "coal and", "and firewood", "coal and coal"],
            ),
            (
                "ielts6_test1",
                7,
                [
                    "10 to 4.30",
                    "10 am to 4:30 pm",
                    "10 a.m. to 4.30 p.m.",
                    "10, 4:30",
                    "10 and 4.30",
                ],
                ["10", "4.30", "10 to", "to 4.30", "4.30 to 10", "4.30 pm to 10 am", "10 to 10"],
            ),
            (
                "ielts6_test1",
                19,
                ["Monday and Thursday", "Thursday and Monday", "Monday Thursday"],
                ["Monday", "Thursday", "Monday and", "and Thursday", "Monday and Monday"],
            ),
            (
                "ielts6_test1",
                32,
                ["metal and leather", "leather and metal", "metal leather"],
                ["metal", "leather", "metal and", "and leather", "metal and metal"],
            ),
        ]:
            for value in accepted + rejected:
                with self.subTest(test=test_id, question=number, value=value):
                    self.assert_grade(test_id, number, value, int(value in accepted))

    def test_renumbered_old_snapshot_grades_future_submission_without_rewriting_it(self):
        payload = {"id": "historical-specialty-snapshot", "sections": []}
        answers = {}
        for index, ((test_id, number), _) in enumerate(OLD_KEYS.items(), 1):
            question = copy.deepcopy(question_by_number(old_paper(test_id), number))
            question.update(source_number=number, number=index, id=9_000_000_000 + index)
            payload["sections"].append(
                {
                    "source_test_id": test_id,
                    "groups": [{"type": 5, "questions": [question]}],
                }
            )
            answers[str(question["id"])] = {
                1: "firewood and coal",
                2: "10 to 4.30",
                3: "Monday and Thursday",
                4: "metal and leather",
            }[index]
        original = copy.deepcopy(payload)
        grade = grade_listening_test_answers(payload, answers)
        self.assertEqual((grade["correct"], grade["total"]), (4, 4))
        self.assertEqual(payload, original)
        self.assertEqual(grade["results"][0]["numbers"], [1])
        self.assertEqual(grade["results"][0]["ids"], ["9000000001"])

    def test_group_source_metadata_and_section_filter_use_the_same_keys(self):
        payload = old_paper("ielts6_test1")
        payload["id"] = "custom-specialty"
        for section in payload["sections"]:
            for group in section["groups"]:
                group["source_meta"] = {"test_id": "ielts6_test1"}
        q = question_by_number(payload, 7)
        grade = grade_listening_test_answers(payload, {str(q["id"]): "10 to 4.30"}, 1)
        self.assertEqual((grade["correct"], grade["total"]), (1, 10))

    def test_only_four_answer_fields_and_derived_alternatives_can_change(self):
        seen = set()
        for test_id in {test_id for test_id, _ in OLD_KEYS}:
            original = old_paper(test_id)
            corrected = corrections.apply_listening_answer_corrections(copy.deepcopy(original))
            for number in range(1, 41):
                before = question_by_number(original, number)
                after = question_by_number(corrected, number)
                if before != after:
                    seen.add((test_id, number))
                    self.assertEqual(
                        {
                            key
                            for key in set(before) | set(after)
                            if before.get(key) != after.get(key)
                        },
                        {"answer", "answers"},
                    )
                    self.assertEqual(
                        after["answers"], [v.strip() for v in after["answer"].split("/")]
                    )
            self.assertEqual(
                corrections.apply_listening_answer_corrections(copy.deepcopy(corrected)), corrected
            )
        self.assertEqual(seen, set(OLD_KEYS))
        unrelated = {
            "id": "ielts18_test1",
            "sections": [{"groups": [{"questions": [{"number": 7, "answer": "unchanged"}]}]}],
        }
        self.assertEqual(
            corrections.apply_listening_answer_corrections(copy.deepcopy(unrelated)), unrelated
        )

    def test_authorized_review_copy_changes_key_without_regrading_saved_results(self):
        saved = {
            "subject": "listening",
            "payload": old_paper("ielts6_test1"),
            "results": [
                {"numbers": [32], "answer": "metal / leather", "value": "metal", "awarded": 1}
            ],
            "correct": 1,
        }
        original = copy.deepcopy(saved)
        reviewed = review_snapshot(saved, static_root=ROOT / "static")
        self.assertIn("metal and leather", question_by_number(reviewed["payload"], 32)["answer"])
        self.assertEqual(reviewed["results"], original["results"])
        self.assertEqual(reviewed["correct"], 1)
        self.assertEqual(saved, original)

    def test_builder_persists_reviewed_keys_after_raw_import(self):
        raw = {
            "parts": {
                "1": {
                    "values": {
                        "question": [
                            {"list": [{"id": 1578, "number": 7, "display_answer": "10 / 4.30"}]}
                        ]
                    }
                }
            }
        }
        report = [{"exercise_id": "ielts6_test1_s1", "part_id": 1}]
        with tempfile.TemporaryDirectory() as temp:
            raw_path, report_path = Path(temp) / "raw.json", Path(temp) / "report.json"
            raw_path.write_text(json.dumps(raw))
            report_path.write_text(json.dumps(report))
            with (
                patch.object(builder, "RAW_PATH", raw_path),
                patch.object(builder, "REPORT_PATH", report_path),
            ):
                question = question_by_number(builder.build_test("ielts6_test1"), 7)
        self.assertIn("10 to 4.30", question["answers"])
        self.assertNotIn("10", question["answers"])

    def test_manifest_rejects_non_answer_fields(self):
        original = json.loads(corrections._MANIFEST.read_text())
        original["tests"]["ielts6_test1"]["questions"]["7"]["number"] = 8
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "invalid.json"
            path.write_text(json.dumps(original))
            corrections._load_answer_corrections.cache_clear()
            try:
                with patch.object(corrections, "_MANIFEST", path), self.assertRaises(ValueError):
                    corrections._load_answer_corrections()
            finally:
                corrections._load_answer_corrections.cache_clear()


if __name__ == "__main__":
    unittest.main()
