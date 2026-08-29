import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_ielts_practice_library import scan_library


class IeltsLibraryGateTest(unittest.TestCase):
    def test_gate_detects_missing_question_and_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            static = Path(directory)
            (static / "listening_tests").mkdir()
            (static / "reading_tests").mkdir()
            (static / "reading_jijing").mkdir()
            (static / "listening").mkdir()
            payload = {
                "sections": [{
                    "audio": "missing.mp3",
                    "groups": [{"questions": [{"id": index, "number": index} for index in range(1, 40)]}],
                }]
            }
            (static / "listening_tests/test.json").write_text(json.dumps(payload), encoding="utf-8")
            report = scan_library(static, static / "listening", verify_duration=False)
            codes = {problem["code"] for problem in report["problems"]}
            self.assertFalse(report["ok"])
            self.assertIn("audio_missing", codes)
            self.assertIn("not_full_40_question_test", codes)

    def test_gate_accepts_a_structurally_complete_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            static = Path(directory)
            for name in ("listening_tests", "reading_tests", "reading_jijing", "listening"):
                (static / name).mkdir()
            audio = static / "listening/test.mp3"
            audio.write_bytes(b"fixture")
            payload = {
                "sections": [{
                    "audio": "test.mp3",
                    "groups": [{"questions": [{"id": index, "number": index} for index in range(1, 41)]}],
                }]
            }
            (static / "listening_tests/test.json").write_text(json.dumps(payload), encoding="utf-8")
            report = scan_library(static, static / "listening", verify_duration=False)
            self.assertTrue(report["ok"], report["problems"])

    def test_gate_accepts_a_hash_locked_offline_test_outside_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            static = Path(directory)
            for name in ("listening_tests", "reading_tests", "reading_jijing", "listening"):
                (static / name).mkdir()
            source_path = static / "reading_jijing/reading_jijing_83_test_95.json"
            source_path.write_text(json.dumps({
                "passages": [{
                    "groups": [{
                        "questions": [{"id": index, "number": index} for index in range(1, 40)]
                    }]
                }]
            }), encoding="utf-8")
            source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
            (static / "reading_jijing/catalog.json").write_text(
                json.dumps({"books": []}), encoding="utf-8"
            )
            (static / "reading_jijing/offline_tests.json").write_text(json.dumps({
                "tests": [{
                    "id": source_path.stem,
                    "status": "offline",
                    "question_count": 39,
                    "source_sha256": source_hash,
                }]
            }), encoding="utf-8")

            report = scan_library(static, static / "listening", verify_duration=False)

            self.assertTrue(report["ok"], report["problems"])
            self.assertEqual(report["counts"]["offline_reading_tests"], 1)
            self.assertEqual(report["counts"]["reading_tests"], 0)

    def test_gate_rejects_an_offline_test_still_present_in_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            static = Path(directory)
            for name in ("listening_tests", "reading_tests", "reading_jijing", "listening"):
                (static / name).mkdir()
            source_path = static / "reading_jijing/offline_test.json"
            source_path.write_text(json.dumps({"passages": []}), encoding="utf-8")
            source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
            (static / "reading_jijing/catalog.json").write_text(json.dumps({
                "books": [{"book": 1, "tests": [{"id": source_path.stem}]}]
            }), encoding="utf-8")
            (static / "reading_jijing/offline_tests.json").write_text(json.dumps({
                "tests": [{
                    "id": source_path.stem,
                    "status": "offline",
                    "question_count": 0,
                    "source_sha256": source_hash,
                }]
            }), encoding="utf-8")

            report = scan_library(static, static / "listening", verify_duration=False)

            self.assertFalse(report["ok"])
            self.assertIn(
                "offline_test_still_catalogued",
                {problem["code"] for problem in report["problems"]},
            )


if __name__ == "__main__":
    unittest.main()
