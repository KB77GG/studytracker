"""Exercise the real ordinary listening route bodies without importing app/DB."""

import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename

from practice_tables import normalize_practice_tables
from services.ielts_exam_payload import build_simulation_payload
from services.question_type_review import derive_listening_payload

ROOT = Path(__file__).resolve().parents[1]


class CambridgeReviewDeliveryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.static = self.root / "static"
        self.audio = self.static / "listening"
        self.audio.mkdir(parents=True)
        (self.static / "listening_tests").mkdir()
        (self.root / "data").mkdir()
        self.payload = {
            "id": "fixture",
            "sections": [
                {
                    "section": 1,
                    "audio": "fixture.mp3",
                    "transcript": [{"start": 100, "end": 105, "en": "Verified answer sentence."}],
                    "groups": [
                        {
                            "questions": [
                                {
                                    "id": 1,
                                    "number": 1,
                                    "answer": "safe",
                                    "analysis": "Verified explanation.",
                                    "start": 100,
                                    "end": 105,
                                }
                            ]
                        }
                    ],
                }
            ],
        }
        self.source = self.static / "listening_tests/fixture.json"
        self.source.write_text(json.dumps(self.payload))
        self.source_before = self.source.read_bytes()
        sidecar = self.audio / "fixture.json"
        sidecar.write_text(
            json.dumps(
                {
                    "id": "fixture",
                    "audio": "fixture.mp3",
                    "parts": [
                        {
                            "segments": [
                                {
                                    "start": 20,
                                    "end": 25,
                                    "text": "Verified answer sentence.",
                                    "source_start_time": 100000,
                                    "source_end_time": 105000,
                                }
                            ]
                        }
                    ],
                }
            )
        )
        versions = []
        for name, content, basis, duration in (
            ("original", b"original-media", "source_original", 110),
            ("cut", b"cut-media", "sidecar_current", 30),
        ):
            versions.append(
                {
                    "id": name,
                    "timeline_basis": basis,
                    "media_sha256": hashlib.sha256(content).hexdigest(),
                    "media_size_bytes": len(content),
                    "media_duration_seconds": duration,
                }
            )
        (self.root / "data/listening_audio_timeline_overrides.json").write_text(
            json.dumps(
                {
                    "assets": {
                        "fixture.mp3": {
                            "sidecar": "fixture.json",
                            "sidecar_sha256": hashlib.sha256(sidecar.read_bytes()).hexdigest(),
                            "default_media_version": "cut",
                            "media_versions": versions,
                        }
                    },
                }
            )
        )
        self.app = Flask(__name__, static_folder=str(self.static))
        self.app.config["TESTING"] = True
        self.namespace = {
            "app": self.app,
            "Path": Path,
            "json": json,
            "request": request,
            "jsonify": jsonify,
            "secure_filename": secure_filename,
            "normalize_practice_tables": normalize_practice_tables,
            "derive_listening_payload": derive_listening_payload,
            "_web_assigned_practice_context": lambda *_args, **_kwargs: None,
            "render_template": lambda _name, **values: jsonify(values["test"]),
        }
        names = {
            "_listening_root",
            "_listening_test_root",
            "_load_listening_test_payload",
            "listening_test_practice",
            "api_listening_test_practice",
        }
        tree = ast.parse((ROOT / "app.py").read_text())
        selected = ast.Module(
            body=[
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name in names
            ],
            type_ignores=[],
        )
        exec(compile(selected, str(ROOT / "app.py"), "exec"), self.namespace)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_page_and_api_choose_the_actual_original_or_cut_media(self):
        for media, basis, answer_start in (
            (b"original-media", "source_original", 100),
            (b"cut-media", "sidecar_current", 20),
        ):
            (self.audio / "fixture.mp3").write_bytes(media)
            for url in ("/listening/test/fixture", "/api/listening/test/fixture"):
                with self.subTest(media=media, url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    section = response.get_json()["sections"][0]
                    question = section["groups"][0]["questions"][0]
                    self.assertEqual(section["audio_timeline"]["basis"], basis)
                    self.assertEqual(question["audio_review"]["answer_start"], answer_start)
                    self.assertEqual(
                        question["audio_review"]["evidence"][0]["text"], "Verified answer sentence."
                    )
                    self.assertEqual(section["transcript"][0]["start"], answer_start)
        self.assertEqual(self.source.read_bytes(), self.source_before)

    def test_unknown_same_name_media_disables_clip_instead_of_guessing(self):
        (self.audio / "fixture.mp3").write_bytes(b"unrecognized-media")
        response = self.client.get("/api/listening/test/fixture")
        section = response.get_json()["sections"][0]
        self.assertFalse(section["audio_timeline"]["available"])
        question = section["groups"][0]["questions"][0]
        self.assertFalse(question["audio_review"]["available"])
        self.assertEqual(question["analysis"], "Verified explanation.")

    def test_grading_loader_stays_raw_and_simulation_remains_answer_free(self):
        (self.audio / "fixture.mp3").write_bytes(b"original-media")
        self.client.get("/listening/test/fixture")
        raw, _, _ = self.namespace["_load_listening_test_payload"]("fixture")
        question = raw["sections"][0]["groups"][0]["questions"][0]
        self.assertNotIn("audio_review", question)
        self.assertEqual(raw["sections"][0]["transcript"][0]["start"], 100)
        safe = json.dumps(build_simulation_payload(raw, "listening"))
        self.assertNotIn("Verified answer sentence", safe)
        self.assertNotIn("Verified explanation", safe)
        self.assertNotIn('"answer"', safe)


if __name__ == "__main__":
    unittest.main()
