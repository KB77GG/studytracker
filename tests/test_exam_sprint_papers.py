import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.exam_sprint_papers import (
    SprintPaperError,
    compose_sprint_paper,
    load_sprint_paper,
    save_sprint_paper,
)
from services.ielts_exam_payload import build_simulation_payload
from services.ielts_practice_scoring import grade_listening_test_answers, grade_reading_test_answers


def fixture(subject, counts=None):
    counts = counts or ([10] * 4 if subject == "listening" else [13, 13, 14])
    catalog = {"updated_at_label": "2026-11-26 20:27", "groups": []}
    payloads = {}
    for part, count in enumerate(counts, 1):
        selection = f"entry-{part}"
        # Deliberately repeated IDs between source papers: composition must namespace.
        questions = [
            {
                "id": str(9007199254740993 + i),
                "number": i + 1,
                "answer": "alpha",
                "answers": ["alpha"],
                "analysis": "private explanation",
                "title": "",
                "options": [],
            }
            for i in range(count)
        ]
        group = {
            "type": 1,
            "desc": f"Questions 1-{count}. Write ONE WORD ONLY.",
            "collect": "<table><tr><td>"
            + "".join(f'${q["id"]}$' for q in questions)
            + "</td></tr></table>",
            "items" if subject == "listening" else "questions": questions,
        }
        unit = {"groups": [group], "content": {"text": "Article with the year 1999."}, "passage": 1}
        if subject == "listening":
            unit["audio"] = {"local_path": f"/practice/sprint/assets/{str(part)*64}.mp3"}
            group["collect_options"] = {"list": []}
            payloads[selection] = unit
        else:
            payloads[selection] = {"passages": [unit]}
        item = {
            "source_id": str(part),
            "selection_id": selection,
            "title": f"Paper {part}",
            "passage": 1,
            "mapping": {"target_id": selection},
        }
        catalog["groups"].append({"part": part, "items": [item]})
    return catalog, payloads


class SprintPapersTest(unittest.TestCase):
    def compose(self, subject, counts=None):
        catalog, payloads = fixture(subject, counts)
        with patch(
            "services.exam_sprint_papers._local_target",
            side_effect=lambda root, m: (payloads[m["target_id"]], "/practice"),
        ):
            paper = compose_sprint_paper(".", subject, list(payloads), catalog=catalog)
        return paper, catalog, payloads

    def test_both_subjects_grade_forty_and_preserve_source_ids_and_placeholders(self):
        for subject in ("reading", "listening"):
            paper, _, _ = self.compose(subject)
            units = paper["sections" if subject == "listening" else "passages"]
            questions = [q for u in units for g in u["groups"] for q in g["questions"]]
            self.assertEqual([q["number"] for q in questions], list(range(1, 41)))
            self.assertEqual(len({q["id"] for q in questions}), 40)
            self.assertEqual(questions[0]["source_question_id"], "9007199254740993")
            for unit in units:
                for group in unit["groups"]:
                    for q in group["questions"]:
                        self.assertIn(f'${q["id"]}$', group["collect"])
            answers = {q["id"]: "alpha" for q in questions}
            grader = (
                grade_listening_test_answers
                if subject == "listening"
                else grade_reading_test_answers
            )
            self.assertEqual(grader(paper, answers)["correct"], 40)
            serialized = json.dumps(build_simulation_payload(paper, subject))
            self.assertNotIn("private explanation", serialized)
            self.assertNotIn('"answer":', serialized)
            self.assertNotIn('"answers":', serialized)

    def test_wrong_total_and_wrong_part_or_missing_version_rejected(self):
        with self.assertRaisesRegex(SprintPaperError, "39"):
            self.compose("reading", [13, 13, 13])
        catalog, payloads = fixture("listening")
        with self.assertRaises(SprintPaperError):
            compose_sprint_paper(
                ".", "listening", ["entry-2", "entry-1", "entry-3", "entry-4"], catalog=catalog
            )
        with patch("services.exam_sprint_papers._local_target", return_value=None):
            with self.assertRaisesRegex(SprintPaperError, "校验失败"):
                compose_sprint_paper(".", "listening", list(payloads), catalog=catalog)

    def test_listening_schema_audio_and_teaching_fields(self):
        paper, _, _ = self.compose("listening")
        for index, unit in enumerate(paper["sections"], 1):
            self.assertEqual(unit["section"], index)
            self.assertTrue(unit["audio"].startswith("/practice/sprint/assets/"))
            self.assertNotIn("content", unit)
            self.assertIn("collect_option", unit["groups"][0])
            self.assertNotIn("items", unit["groups"][0])
        safe = build_simulation_payload(paper, "listening")
        self.assertNotIn("transcript", safe["sections"][0])

    def test_original_inputs_unchanged_and_number_references_bounded(self):
        paper, _, sources = self.compose("reading")
        self.assertEqual(
            sources["entry-2"]["passages"][0]["groups"][0]["questions"][0]["number"], 1
        )
        self.assertIn("Questions 14-26", paper["passages"][1]["groups"][0]["desc"])
        self.assertIn("1999", paper["passages"][1]["content"]["text"])

    def test_store_immutable_integrity_and_week_independence(self):
        paper, _, _ = self.compose("reading")
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.dict("os.environ", {"EXAM_SPRINT_STATE_DIR": temp}),
        ):
            test_id = save_sprint_paper(".", paper)
            self.assertEqual(test_id, save_sprint_paper(".", paper))
            loaded, path = load_sprint_paper(".", "reading", test_id)
            self.assertEqual(loaded["question_count"], 40)
            self.assertIsNone(load_sprint_paper(".", "listening", test_id))
            self.assertIsNone(load_sprint_paper(".", "reading", "../" + test_id))
            Path(temp, "current.json").write_text("{}")
            self.assertIsNotNone(load_sprint_paper(".", "reading", test_id))
            path.write_text(path.read_text().replace("alpha", "wrong"))
            self.assertIsNone(load_sprint_paper(".", "reading", test_id))
            with self.assertRaises(ValueError):
                save_sprint_paper(".", paper)

    def test_symlink_not_read_or_overwritten(self):
        paper, _, _ = self.compose("reading")
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.dict("os.environ", {"EXAM_SPRINT_STATE_DIR": temp}),
        ):
            test_id = save_sprint_paper(".", paper)
            _, path = load_sprint_paper(".", "reading", test_id)
            target = Path(temp, "real.json")
            path.rename(target)
            path.symlink_to(target)
            self.assertIsNone(load_sprint_paper(".", "reading", test_id))
            with self.assertRaises(ValueError):
                save_sprint_paper(".", paper)


if __name__ == "__main__":
    unittest.main()
