import copy
import hashlib
import json
import re
import tempfile
import unicodedata
import unittest
from difflib import SequenceMatcher
from pathlib import Path

from services.question_type_practice import public_snapshot
from services.question_type_review import (
    derive_listening_payload,
    reading_evidence,
    review_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
_SPEAKER_RE = re.compile(r"^\s*[A-Za-z][A-Za-z .’'\-]{0,30}:\s*")


def _evidence_coverage(frozen, current):
    def tokens(value):
        text = _SPEAKER_RE.sub("", str(value or ""))
        return re.findall(
            r"[a-z0-9]+",
            unicodedata.normalize("NFKC", text).lower(),
        )

    frozen_tokens = tokens(frozen)
    if not frozen_tokens:
        return 0.0
    matcher = SequenceMatcher(
        None,
        frozen_tokens,
        tokens(current),
        autojunk=False,
    )
    return sum(block.size for block in matcher.get_matching_blocks()) / len(
        frozen_tokens
    )


def _snapshot(payload, pace="training"):
    return {
        "schema_version": 1,
        "task_type": "question_type_practice",
        "subject": "listening",
        "pace": pace,
        "standard_type": "completion",
        "group_ids": ["listening:fixture:1:g1"],
        "group_refs": [],
        "question_count": 1,
        "snapshot_hash": "frozen-hash",
        "payload": payload,
    }


def _payload(audio="fixture.mp3"):
    return {
        "id": "fixture",
        "sections": [
            {
                "id": "fixture",
                "section": 1,
                "audio": audio,
                "transcript": [
                    {"start": 100, "end": 105, "en": "Mapped answer sentence."}
                ],
                "groups": [
                    {
                        "question_group_id": "listening:fixture:1:g1",
                        "questions": [
                            {
                                "id": 9_000_000_001,
                                "number": 1,
                                "source_question_id": "7",
                                "source_number": 7,
                                "answer": "safe",
                                "analysis": "Use the mapped answer sentence.",
                                "answer_sentences": {"start_time": 100000, "end_time": 105000},
                                "start": 100.0,
                                "end": 105.0,
                            }
                        ],
                    }
                ],
            }
        ],
    }


class QuestionTypeReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp.name)
        self.static_root = self.project_root / "static"
        self.audio_root = self.static_root / "listening"
        self.audio_root.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def _write_sidecar(self, *, sidecar_id="fixture", audio="fixture.mp3"):
        payload = {
            "id": sidecar_id,
            "audio": audio,
            "parts": [
                {
                    "segments": [
                        {
                            "start": 20.0,
                            "end": 25.0,
                            "text": "Mapped answer sentence.",
                            "translation": "映射后的答案句。",
                            "source_start_time": 100000,
                            "source_end_time": 105000,
                        }
                    ]
                }
            ],
        }
        path = self.audio_root / "fixture.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_review_is_derived_without_mutating_frozen_snapshot(self):
        self._write_sidecar()
        frozen = _snapshot(_payload())
        before = json.dumps(frozen, sort_keys=True)

        review = review_snapshot(
            frozen,
            static_root=self.static_root,
            audio_root=self.audio_root,
            project_root=self.project_root,
        )

        question = review["payload"]["sections"][0]["groups"][0]["questions"][0]
        self.assertEqual((question["audio_review"]["start"], question["audio_review"]["end"]), (17.0, 25.0))
        self.assertEqual(question["audio_review"]["evidence"][0]["text"], "Mapped answer sentence.")
        self.assertEqual(review["payload"]["sections"][0]["transcript"][0]["start"], 20.0)
        self.assertEqual(json.dumps(frozen, sort_keys=True), before)
        self.assertEqual(frozen["snapshot_hash"], "frozen-hash")

    def test_training_public_payload_has_group_range_but_no_review_leak(self):
        self._write_sidecar()
        frozen = _snapshot(_payload(), pace="training")
        public = public_snapshot(
            frozen,
            static_root=self.static_root,
            audio_root=self.audio_root,
            project_root=self.project_root,
        )
        text = json.dumps(public["payload"], ensure_ascii=False)
        group = public["payload"]["sections"][0]["groups"][0]

        self.assertTrue(group["practice_audio"]["available"])
        self.assertNotIn('"answer"', text)
        self.assertNotIn('"analysis"', text)
        self.assertNotIn('"audio_review"', text)
        self.assertNotIn('"transcript"', text)
        self.assertNotIn("Mapped answer sentence", text)

    def test_exam_public_payload_does_not_expose_group_or_question_windows(self):
        self._write_sidecar()
        public = public_snapshot(
            _snapshot(_payload(), pace="exam"),
            static_root=self.static_root,
            audio_root=self.audio_root,
            project_root=self.project_root,
        )
        text = json.dumps(public["payload"], ensure_ascii=False)
        self.assertNotIn('"practice_audio"', text)
        self.assertNotIn('"audio_timeline"', text)
        self.assertNotIn('"audio_review"', text)

    def test_missing_or_mismatched_sidecar_falls_back_to_section(self):
        mismatch = derive_listening_payload(
            _payload(),
            static_root=self.static_root,
            audio_root=self.audio_root,
            project_root=self.project_root,
        )
        self.assertFalse(mismatch["sections"][0]["groups"][0]["practice_audio"]["available"])

        self._write_sidecar(sidecar_id="another-section")
        mismatch = derive_listening_payload(
            _payload(),
            static_root=self.static_root,
            audio_root=self.audio_root,
            project_root=self.project_root,
        )
        question = mismatch["sections"][0]["groups"][0]["questions"][0]
        self.assertFalse(question["audio_review"]["available"])
        self.assertIn("匹配", question["audio_review"]["reason"])
        self.assertEqual(
            mismatch["sections"][0]["transcript"][0]["en"],
            "Mapped answer sentence.",
        )

    def test_override_rejects_changed_sidecar_version(self):
        sidecar = self._write_sidecar(audio="dialogue.mp3")
        (self.project_root / "data").mkdir()
        (self.project_root / "data/listening_audio_timeline_overrides.json").write_text(
            json.dumps(
                {
                    "assets": {
                        "fixture.mp3": {
                            "timeline_basis": "sidecar_current",
                            "sidecar": "fixture.json",
                            "sidecar_sha256": "outdated",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        self.assertNotEqual(hashlib.sha256(sidecar.read_bytes()).hexdigest(), "outdated")
        result = derive_listening_payload(
            _payload(),
            static_root=self.static_root,
            audio_root=self.audio_root,
            project_root=self.project_root,
        )
        timeline = result["sections"][0]["audio_timeline"]
        self.assertFalse(timeline["available"])
        self.assertIn("版本", timeline["reason"])

    def test_override_rejects_changed_media_with_the_same_declared_name(self):
        sidecar = self._write_sidecar(audio="dialogue.mp3")
        media = self.audio_root / "fixture.mp3"
        media.write_bytes(b"different-media-version")
        (self.project_root / "data").mkdir()
        (self.project_root / "data/listening_audio_timeline_overrides.json").write_text(
            json.dumps(
                {
                    "assets": {
                        "fixture.mp3": {
                            "timeline_basis": "sidecar_current",
                            "sidecar": "fixture.json",
                            "sidecar_sha256": hashlib.sha256(sidecar.read_bytes()).hexdigest(),
                            "media_size_bytes": media.stat().st_size,
                            "media_sha256": "outdated",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        result = derive_listening_payload(
            _payload(),
            static_root=self.static_root,
            audio_root=self.audio_root,
            project_root=self.project_root,
        )

        timeline = result["sections"][0]["audio_timeline"]
        self.assertFalse(timeline["available"])
        self.assertIn("音频文件版本", timeline["reason"])

    def test_multi_version_override_selects_timeline_basis_from_exact_media(self):
        sidecar = self._write_sidecar(audio="dialogue.mp3")
        media = self.audio_root / "fixture.mp3"
        media.write_bytes(b"full-section-production-version")
        (self.project_root / "data").mkdir()
        (self.project_root / "data/listening_audio_timeline_overrides.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "assets": {
                        "fixture.mp3": {
                            "sidecar": "fixture.json",
                            "sidecar_sha256": hashlib.sha256(
                                sidecar.read_bytes()
                            ).hexdigest(),
                            "default_media_version": "dialogue",
                            "media_versions": [
                                {
                                    "id": "dialogue",
                                    "timeline_basis": "sidecar_current",
                                    "media_size_bytes": 3,
                                    "media_sha256": hashlib.sha256(b"new").hexdigest(),
                                    "media_duration_seconds": 25.0,
                                },
                                {
                                    "id": "production-original",
                                    "timeline_basis": "source_original",
                                    "media_size_bytes": media.stat().st_size,
                                    "media_sha256": hashlib.sha256(
                                        media.read_bytes()
                                    ).hexdigest(),
                                    "media_duration_seconds": 120.0,
                                },
                            ],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        result = derive_listening_payload(
            _payload(),
            static_root=self.static_root,
            audio_root=self.audio_root,
            project_root=self.project_root,
        )

        section = result["sections"][0]
        timeline = section["audio_timeline"]
        question = section["groups"][0]["questions"][0]["audio_review"]
        self.assertTrue(timeline["available"])
        self.assertEqual(timeline["basis"], "source_original")
        self.assertEqual(timeline["media_version"], "production-original")
        self.assertEqual(timeline["expected_duration"], 120.0)
        self.assertEqual((question["answer_start"], question["answer_end"]), (100.0, 105.0))

    def test_multi_version_override_rejects_unknown_concrete_media(self):
        sidecar = self._write_sidecar(audio="dialogue.mp3")
        media = self.audio_root / "fixture.mp3"
        media.write_bytes(b"unknown-version")
        (self.project_root / "data").mkdir()
        (self.project_root / "data/listening_audio_timeline_overrides.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "assets": {
                        "fixture.mp3": {
                            "sidecar": "fixture.json",
                            "sidecar_sha256": hashlib.sha256(
                                sidecar.read_bytes()
                            ).hexdigest(),
                            "default_media_version": "known",
                            "media_versions": [
                                {
                                    "id": "known",
                                    "timeline_basis": "sidecar_current",
                                    "media_size_bytes": 5,
                                    "media_sha256": hashlib.sha256(b"known").hexdigest(),
                                    "media_duration_seconds": 25.0,
                                }
                            ],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        result = derive_listening_payload(
            _payload(),
            static_root=self.static_root,
            audio_root=self.audio_root,
            project_root=self.project_root,
        )

        timeline = result["sections"][0]["audio_timeline"]
        self.assertFalse(timeline["available"])
        self.assertIn("音频文件版本", timeline["reason"])

    def test_real_dialogue_override_and_invalid_source_window(self):
        mapped_payload = json.loads(
            (ROOT / "static/listening_tests/ielts20_test1.json").read_text(encoding="utf-8")
        )
        mapped_payload["sections"] = [mapped_payload["sections"][0]]
        mapped_snapshot = _snapshot(mapped_payload)
        frozen = copy.deepcopy(mapped_snapshot)
        mapped_review = review_snapshot(
            mapped_snapshot,
            static_root=ROOT / "static",
            audio_root=ROOT / "static/listening",
            project_root=ROOT,
        )
        mapped_question = next(
            question
            for group in mapped_review["payload"]["sections"][0]["groups"]
            for question in group["questions"]
            if question["number"] == 6
        )
        self.assertAlmostEqual(mapped_question["audio_review"]["answer_start"], 189.24, places=2)
        self.assertIn("Baxter Bridge", mapped_question["audio_review"]["evidence"][-1]["text"])
        self.assertEqual(mapped_snapshot, frozen)

        split_question = next(
            question
            for group in mapped_review["payload"]["sections"][0]["groups"]
            for question in group["questions"]
            if question["number"] == 2
        )
        split_evidence = " ".join(
            row["text"] for row in split_question["audio_review"]["evidence"]
        )
        self.assertTrue(split_question["audio_review"]["available"])
        self.assertIn("roof", split_evidence)
        self.assertIn("need to book", split_evidence)
        self.assertAlmostEqual(
            split_question["audio_review"]["answer_start"], 66.84, places=2
        )
        self.assertAlmostEqual(
            split_question["audio_review"]["answer_end"], 81.48, places=2
        )

        invalid_payload = json.loads(
            (ROOT / "static/listening_tests/ielts4_test3.json").read_text(encoding="utf-8")
        )
        invalid_payload["sections"] = [invalid_payload["sections"][0]]
        invalid_snapshot = _snapshot(invalid_payload)
        invalid_review = review_snapshot(
            invalid_snapshot,
            static_root=ROOT / "static",
            audio_root=ROOT / "static/listening",
            project_root=ROOT,
        )
        invalid_question = next(
            question
            for group in invalid_review["payload"]["sections"][0]["groups"]
            for question in group["questions"]
            if question["number"] == 4
        )
        self.assertFalse(invalid_question["audio_review"]["available"])
        invalid_group = next(
            group
            for group in invalid_review["payload"]["sections"][0]["groups"]
            if any(question["number"] == 4 for question in group["questions"])
        )
        self.assertFalse(invalid_group["practice_audio"]["available"])

    def test_ielts21_shifted_tracks_bind_by_frozen_evidence_text(self):
        expected = {
            ("ielts21_test3", 1): "Northern Ferries",
            ("ielts21_test3", 2): "seven days a week",
            ("ielts21_test2", 1): "13th of January",
            ("ielts21_test2", 6): "on the 6th",
            ("ielts21_test2", 7): "natural products",
        }
        for test_id in ("ielts21_test2", "ielts21_test3"):
            payload = json.loads(
                (ROOT / f"static/listening_tests/{test_id}.json").read_text(
                    encoding="utf-8"
                )
            )
            payload["sections"] = [payload["sections"][0]]
            result = derive_listening_payload(
                payload,
                static_root=ROOT / "static",
                audio_root=ROOT / "static/listening",
                project_root=ROOT,
            )
            questions = [
                question
                for group in result["sections"][0]["groups"]
                for question in group["questions"]
            ]
            for question in questions:
                marker = expected.get((test_id, question["number"]))
                if not marker:
                    continue
                evidence = " ".join(
                    row["text"] for row in question["audio_review"]["evidence"]
                )
                self.assertTrue(question["audio_review"]["available"])
                self.assertIn(marker, evidence)
                self.assertNotIn("look at questions", evidence)

    def test_full_corpus_available_clips_correspond_to_frozen_evidence(self):
        counts = {
            "sections": 0,
            "questions": 0,
            "available_questions": 0,
            "groups": 0,
            "available_groups": 0,
        }
        for path in sorted((ROOT / "static/listening_tests").glob("*.json")):
            frozen = json.loads(path.read_text(encoding="utf-8"))
            derived = derive_listening_payload(
                frozen,
                static_root=ROOT / "static",
                audio_root=ROOT / "static/listening",
                project_root=ROOT,
            )
            for frozen_section, current_section in zip(
                frozen["sections"], derived["sections"], strict=True
            ):
                counts["sections"] += 1
                self.assertTrue(current_section["audio_timeline"]["available"])
                frozen_rows = frozen_section.get("transcript") or []
                for frozen_group, current_group in zip(
                    frozen_section["groups"], current_section["groups"], strict=True
                ):
                    counts["groups"] += 1
                    counts["available_groups"] += bool(
                        current_group["practice_audio"]["available"]
                    )
                    for frozen_question, current_question in zip(
                        frozen_group["questions"],
                        current_group["questions"],
                        strict=True,
                    ):
                        counts["questions"] += 1
                        review = current_question["audio_review"]
                        if not review["available"]:
                            continue
                        counts["available_questions"] += 1
                        source_rows = [
                            row["en"]
                            for row in frozen_rows
                            if max(frozen_question["start"], row["start"])
                            < min(frozen_question["end"], row["end"])
                        ]
                        evidence = " ".join(row["text"] for row in review["evidence"])
                        self.assertTrue(evidence)
                        self.assertTrue(
                            all(
                                _evidence_coverage(source, evidence) == 1.0
                                for source in source_rows
                            ),
                            (
                                path.name,
                                frozen_section["id"],
                                frozen_question["number"],
                                [round(_evidence_coverage(source, evidence), 3) for source in source_rows],
                            ),
                        )
        self.assertEqual(
            counts,
            {
                "sections": 336,
                "questions": 3360,
                "available_questions": 3358,
                "groups": 658,
                "available_groups": 656,
            },
        )

    def test_real_jfdr_question_uses_source_time_overlap_not_index_conventions(self):
        payload = json.loads(
            (ROOT / "static/listening_tests/jfdr6_test1.json").read_text(
                encoding="utf-8"
            )
        )
        payload["sections"] = [payload["sections"][0]]

        review = review_snapshot(
            _snapshot(payload),
            static_root=ROOT / "static",
            audio_root=ROOT / "static/listening",
            project_root=ROOT,
        )
        question = next(
            question
            for group in review["payload"]["sections"][0]["groups"]
            for question in group["questions"]
            if question["number"] == 1
        )

        self.assertTrue(question["audio_review"]["available"])
        self.assertAlmostEqual(question["audio_review"]["answer_start"], 126.3, places=2)
        self.assertIn("Saturday", question["audio_review"]["evidence"][0]["text"])

    def test_group_range_uses_min_and_max_when_question_order_is_not_chronological(self):
        sidecar = {
            "id": "fixture",
            "audio": "fixture.mp3",
            "parts": [
                {
                    "segments": [
                        {
                            "start": 10.0,
                            "end": 12.0,
                            "text": "Earlier answer.",
                            "source_start_time": 10000,
                            "source_end_time": 12000,
                        },
                        {
                            "start": 40.0,
                            "end": 43.0,
                            "text": "Later answer.",
                            "source_start_time": 40000,
                            "source_end_time": 43000,
                        },
                    ]
                }
            ],
        }
        (self.audio_root / "fixture.json").write_text(
            json.dumps(sidecar), encoding="utf-8"
        )
        payload = _payload()
        payload["sections"][0]["transcript"] = [
            {"start": 10.0, "end": 12.0, "en": "Earlier answer."},
            {"start": 40.0, "end": 43.0, "en": "Later answer."},
        ]
        questions = payload["sections"][0]["groups"][0]["questions"]
        questions[:] = [
            {**questions[0], "number": 2, "start": 40.0, "end": 43.0},
            {**questions[0], "number": 1, "start": 10.0, "end": 12.0},
        ]

        result = derive_listening_payload(
            payload,
            static_root=self.static_root,
            audio_root=self.audio_root,
            project_root=self.project_root,
        )
        group_audio = result["sections"][0]["groups"][0]["practice_audio"]

        self.assertEqual((group_audio["start"], group_audio["end"]), (2.0, 43.0))

    def test_one_frozen_row_can_map_to_multiple_current_segments(self):
        sidecar = {
            "id": "fixture",
            "audio": "fixture.mp3",
            "parts": [
                {
                    "segments": [
                        {
                            "start": 20.0,
                            "end": 23.0,
                            "text": "The answer starts on the rooftop terrace",
                            "source_order": 4,
                            "source_start_time": 100000,
                            "source_end_time": 102000,
                        },
                        {
                            "start": 23.0,
                            "end": 26.0,
                            "text": "where guests have a drink before dinner.",
                            "source_order": 5,
                            "source_start_time": 102000,
                            "source_end_time": 105000,
                        },
                    ]
                }
            ],
        }
        (self.audio_root / "fixture.json").write_text(
            json.dumps(sidecar), encoding="utf-8"
        )
        payload = _payload()
        payload["sections"][0]["transcript"] = [
            {
                "order": 5,
                "start": 100.0,
                "end": 105.0,
                "en": "The answer starts on the rooftop terrace where guests have a drink before dinner.",
            }
        ]
        question = payload["sections"][0]["groups"][0]["questions"][0]
        question["start"] = 100.0
        question["end"] = 105.0

        result = derive_listening_payload(
            payload,
            static_root=self.static_root,
            audio_root=self.audio_root,
            project_root=self.project_root,
        )
        review = result["sections"][0]["groups"][0]["questions"][0][
            "audio_review"
        ]

        self.assertTrue(review["available"])
        self.assertEqual((review["answer_start"], review["answer_end"]), (20.0, 26.0))
        self.assertEqual(len(review["evidence"]), 2)

    def test_partial_frozen_evidence_does_not_create_a_trusted_clip(self):
        sidecar = {
            "id": "fixture",
            "audio": "fixture.mp3",
            "parts": [
                {
                    "segments": [
                        {
                            "start": 20.0,
                            "end": 23.0,
                            "text": "The answer starts on the rooftop terrace.",
                            "source_order": 5,
                            "source_start_time": 100000,
                            "source_end_time": 102000,
                        }
                    ]
                }
            ],
        }
        (self.audio_root / "fixture.json").write_text(
            json.dumps(sidecar), encoding="utf-8"
        )
        payload = _payload()
        payload["sections"][0]["transcript"] = [
            {
                "order": 5,
                "start": 100.0,
                "end": 105.0,
                "en": "The answer starts on the rooftop terrace and continues with essential booking details for every guest.",
            }
        ]

        result = derive_listening_payload(
            payload,
            static_root=self.static_root,
            audio_root=self.audio_root,
            project_root=self.project_root,
        )
        group = result["sections"][0]["groups"][0]

        self.assertFalse(group["questions"][0]["audio_review"]["available"])
        self.assertFalse(group["practice_audio"]["available"])

    def test_short_answer_tail_is_not_dropped_after_long_context_reaches_threshold(self):
        long_context = (
            "Our visitors often enjoy dinner in the main restaurant because the "
            "service is friendly and the atmosphere is pleasant and the menu "
            "offers many interesting choices for families and groups."
        )
        short_answer = "The answer is roof."
        sidecar = {
            "id": "fixture",
            "audio": "fixture.mp3",
            "parts": [
                {
                    "segments": [
                        {
                            "start": 20.0,
                            "end": 28.0,
                            "text": long_context,
                            "source_order": 4,
                            "source_start_time": 100000,
                            "source_end_time": 104000,
                        },
                        {
                            "start": 28.0,
                            "end": 30.0,
                            "text": short_answer,
                            "source_order": 5,
                            "source_start_time": 104000,
                            "source_end_time": 105000,
                        },
                    ]
                }
            ],
        }
        (self.audio_root / "fixture.json").write_text(
            json.dumps(sidecar), encoding="utf-8"
        )
        payload = _payload()
        payload["sections"][0]["transcript"] = [
            {
                "order": 5,
                "start": 100.0,
                "end": 105.0,
                "en": f"{long_context} {short_answer}",
            }
        ]

        result = derive_listening_payload(
            payload,
            static_root=self.static_root,
            audio_root=self.audio_root,
            project_root=self.project_root,
        )
        review = result["sections"][0]["groups"][0]["questions"][0][
            "audio_review"
        ]

        self.assertTrue(review["available"])
        self.assertEqual((review["answer_start"], review["answer_end"]), (20.0, 30.0))
        self.assertIn("roof", " ".join(row["text"] for row in review["evidence"]))

    def test_missing_one_of_multiple_frozen_evidence_rows_falls_back(self):
        sidecar = {
            "id": "fixture",
            "audio": "fixture.mp3",
            "parts": [
                {
                    "segments": [
                        {
                            "start": 20.0,
                            "end": 23.0,
                            "text": "The first evidence row is present.",
                            "source_order": 4,
                            "source_start_time": 100000,
                            "source_end_time": 102000,
                        }
                    ]
                }
            ],
        }
        (self.audio_root / "fixture.json").write_text(
            json.dumps(sidecar), encoding="utf-8"
        )
        payload = _payload()
        payload["sections"][0]["transcript"] = [
            {
                "order": 4,
                "start": 100.0,
                "end": 102.0,
                "en": "The first evidence row is present.",
            },
            {
                "order": 5,
                "start": 102.0,
                "end": 105.0,
                "en": "The second evidence row contains the missing answer roof.",
            },
        ]

        result = derive_listening_payload(
            payload,
            static_root=self.static_root,
            audio_root=self.audio_root,
            project_root=self.project_root,
        )
        group = result["sections"][0]["groups"][0]

        self.assertFalse(group["questions"][0]["audio_review"]["available"])
        self.assertFalse(group["practice_audio"]["available"])

    def test_reading_evidence_prefers_frozen_central_sentences(self):
        question = {
            "central_sentences": {
                "sentences": [
                    "The source sentence.",
                    {"sentence": "A second source sentence."},
                    "The source sentence.",
                ]
            }
        }
        self.assertEqual(
            reading_evidence(question),
            ["The source sentence.", "A second source sentence."],
        )

        real = json.loads(
            (ROOT / "static/reading_tests/ielts10_test1_reading.json").read_text(
                encoding="utf-8"
            )
        )
        real_question = real["passages"][0]["groups"][0]["questions"][0]
        self.assertEqual(
            reading_evidence(real_question),
            [
                "Unique to this region, stepwells are often architecturally complex "
                "and vary widely in size and shape."
            ],
        )


if __name__ == "__main__":
    unittest.main()
