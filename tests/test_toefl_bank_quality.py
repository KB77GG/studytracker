import json
import tempfile
import unittest
from pathlib import Path

from services.toefl_bank_quality import (
    analyze_bank,
    blocking_issues,
)


class ToeflBankQualityTest(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _manifest(self, content_status: str = "complete") -> dict:
        return {
            "title": "Fixture",
            "publish_status": "published",
            "duplicate_status": "clear",
            "content_status": content_status,
        }

    def _mc_question(self, number: int = 1) -> dict:
        return {
            "id": f"reading_fixture_m1_q{number}",
            "order": number,
            "number": str(number),
            "number_end": None,
            "response_type": "mc",
            "prompt": "Fixture prompt",
            "options": [
                {"key": "A", "text": "Option A"},
                {"key": "B", "text": "Option B"},
                {"key": "C", "text": "Option C"},
                {"key": "D", "text": "Option D"},
            ],
            "answer": {"keys": ["A"]},
            "grading_status": "auto",
            "task_type": "read_daily",
        }

    def _profiles(self, approved: bool = True) -> dict:
        return {
            "fixture": {
                "status": "structure_verified",
                "sources": [{"role": "exam_pdf", "path": "fixture.pdf"}],
                "subjects": {
                    "reading": {
                        "review_status": "approved" if approved else "pending",
                        "modules": {
                            "m1": {
                                "question_number_start": 1,
                                "question_number_end": 1,
                            }
                        },
                    }
                },
            }
        }

    def test_complete_approved_subject_is_release_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "source"
            source_root.mkdir()
            (source_root / "fixture.pdf").write_bytes(b"fixture")
            self._write_json(root / "data" / "fixture" / "manifest.json", self._manifest())
            self._write_json(
                root / "data" / "fixture" / "reading.json",
                {
                    "exam": {"audio_modules": []},
                    "questions": [self._mc_question()],
                },
            )
            profiles = self._profiles()
            profiles["fixture"]["sources"][0]["sha256"] = (
                "f16d05ec6b29248d2c61adb1e9263f78e4f7bace1b955014a2d17872cfe4064d"
            )
            report = analyze_bank(
                root / "data",
                root,
                profiles=profiles,
                source_root=source_root,
            )
            self.assertEqual(report["exams"][0]["release_status"], "ready")
            self.assertFalse(blocking_issues(report, ["fixture"]))

    def test_published_partial_exam_is_blocked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_json(
                root / "data" / "fixture" / "manifest.json",
                self._manifest("partial"),
            )
            self._write_json(
                root / "data" / "fixture" / "reading.json",
                {
                    "exam": {"audio_modules": []},
                    "questions": [self._mc_question()],
                },
            )
            report = analyze_bank(root / "data", root)
            codes = {issue["code"] for issue in report["issues"]}
            self.assertIn("published_exam_incomplete", codes)
            self.assertTrue(blocking_issues(report, ["fixture"]))

    def test_mc_requires_exactly_four_options(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            question = self._mc_question()
            question["options"].pop()
            self._write_json(root / "data" / "fixture" / "manifest.json", self._manifest())
            self._write_json(
                root / "data" / "fixture" / "reading.json",
                {"exam": {"audio_modules": []}, "questions": [question]},
            )
            report = analyze_bank(root / "data", root)
            issue = next(
                item
                for item in report["issues"]
                if item["code"] == "mc_option_count_invalid"
            )
            self.assertEqual(issue["severity"], "critical")

    def test_source_profile_reports_missing_question_numbers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_json(root / "data" / "fixture" / "manifest.json", self._manifest())
            self._write_json(
                root / "data" / "fixture" / "reading.json",
                {
                    "exam": {"audio_modules": []},
                    "questions": [self._mc_question()],
                },
            )
            profiles = self._profiles()
            profiles["fixture"]["sources"] = []
            profiles["fixture"]["subjects"]["reading"]["modules"]["m1"][
                "question_number_end"
            ] = 2
            report = analyze_bank(root / "data", root, profiles=profiles)
            issue = next(
                item
                for item in report["issues"]
                if item["code"] == "source_question_coverage_missing"
            )
            self.assertEqual(issue["evidence"]["missing_numbers"], [2])

    def test_listening_modules_cannot_share_full_audio(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            asset = root / "static" / "toefl" / "audio" / "full.mp3"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"audio")
            questions = []
            for module in ("m1", "m2"):
                question = self._mc_question()
                question.update({
                    "id": f"listening_fixture_{module}_q1",
                    "audio_ref": module,
                })
                questions.append(question)
            self._write_json(root / "data" / "fixture" / "manifest.json", self._manifest())
            self._write_json(
                root / "data" / "fixture" / "listening.json",
                {
                    "exam": {
                        "audio_modules": [
                            {"id": "m1", "url": "/static/toefl/audio/full.mp3"},
                            {"id": "m2", "url": "/static/toefl/audio/full.mp3"},
                        ]
                    },
                    "questions": questions,
                },
            )
            report = analyze_bank(root / "data", root)
            codes = {issue["code"] for issue in report["issues"]}
            self.assertIn("module_audio_reused", codes)

    def test_pending_human_review_blocks_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_json(root / "data" / "fixture" / "manifest.json", self._manifest())
            self._write_json(
                root / "data" / "fixture" / "reading.json",
                {
                    "exam": {"audio_modules": []},
                    "questions": [self._mc_question()],
                },
            )
            profiles = self._profiles(approved=False)
            profiles["fixture"]["sources"] = []
            report = analyze_bank(root / "data", root, profiles=profiles)
            codes = {issue["code"] for issue in report["issues"]}
            self.assertIn("subject_review_pending", codes)
            self.assertTrue(blocking_issues(report, ["fixture"]))


if __name__ == "__main__":
    unittest.main()
