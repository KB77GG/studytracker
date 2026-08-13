import hashlib
import json
import unittest
from pathlib import Path

from api.listening_intensive import (
    build_intensive_catalog,
    load_registered_intensive_exercise,
)
from scripts.build_xdf_ielts20 import REGION_OFFSETS_SECONDS, SECTIONS
from scripts.build_xdf_intensive_pilot import normalized_tokens

ROOT = Path(__file__).resolve().parents[1]
LISTENING_DIR = ROOT / "static/listening"
EXPECTED = {
    "ielts20_test1_s1": (
        1817,
        45,
        742,
        "9a89273c77bcc39d7ec545e9c6cb2691292878ce96d2bd963e3b8e48d6780ba9",
    ),
    "ielts20_test1_s2": (
        1819,
        34,
        799,
        "5c1912eda7075cea80689b0ca1c50f07d618c37d603817a96868cdb0ab928a73",
    ),
    "ielts20_test1_s3": (
        1820,
        38,
        793,
        "9038c220e95061805d1c573ae01f58ec77fcac1344c6403e95434b2f1db51ede",
    ),
    "ielts20_test1_s4": (
        1821,
        36,
        810,
        "455683171aef859cc595719ce8b53c01b545fd0dbc95e4be6eb7e0e568058612",
    ),
    "ielts20_test2_s1": (
        1834,
        29,
        585,
        "f61019ba081455d2c8757bf476bf8c937847eff9208ee98b8e15cb5f17d4c81f",
    ),
    "ielts20_test2_s2": (
        1823,
        36,
        735,
        "d6c11a29edba40aa0aa52e3c062e01f2def695e0747b492cc025bf2450318601",
    ),
    "ielts20_test2_s3": (
        1824,
        40,
        748,
        "97432a04eb60f13b8cbad58bf3a871f0c94ec4665bcac4a22a26b3221e3efcf1",
    ),
    "ielts20_test2_s4": (
        1825,
        36,
        714,
        "34a9f61639913358f3dfe4b5d63d0c274634f6eef3bba8cf531848ab650954e4",
    ),
    "ielts20_test3_s1": (
        1826,
        40,
        631,
        "010884d8dc1b4651ed6dfffcc51444e0bb6195cab204832862cfc8ac7a690d6e",
    ),
    "ielts20_test3_s2": (
        1827,
        43,
        763,
        "9e024151ff5f993d650f0a80ce3d08dc545f2a2b0d8b83fafe6f1bf6222ad07d",
    ),
    "ielts20_test3_s3": (
        1828,
        42,
        791,
        "69f9013ff3add067893137d8b6e4219acad446dc1c5ae55030152d260006213b",
    ),
    "ielts20_test3_s4": (
        1829,
        31,
        745,
        "e5e95dd326ccd5cb9f97f72d4e0dde8631746d4b3f701414fd1ad02ba92b694a",
    ),
    "ielts20_test4_s1": (
        1830,
        44,
        731,
        "0b69d8488489f6bac0d82d7b8ba6f78205c99b2a712e5dba7ada514df03807e7",
    ),
    "ielts20_test4_s2": (
        1831,
        33,
        752,
        "1322a8e20000084bd237398c7cad8a2107284568bfc71254d1f03bf805f4df53",
    ),
    "ielts20_test4_s3": (
        1832,
        38,
        854,
        "7e3f7f59d6eea991e0a3cce667de5219ccf2ef99f71e3f2f2c2f2cb1327eefa6",
    ),
    "ielts20_test4_s4": (
        1833,
        29,
        749,
        "f6baa53c31e4a1e0d91a194ff3ae5db606e58bd5f55a2c376fc2901c8a54aa95",
    ),
}


class XdfIelts20ReplacementTests(unittest.TestCase):
    def test_manifest_covers_all_16_sections_once(self):
        self.assertEqual(len(SECTIONS), 16)
        self.assertEqual(len({spec.asset_id for spec in SECTIONS}), 16)
        self.assertEqual(len({spec.qid for spec in SECTIONS}), 16)
        self.assertEqual({spec.asset_id for spec in SECTIONS}, set(EXPECTED))

    def test_all_canonical_assets_have_verified_xdf_transcripts(self):
        for asset_id, (qid, sentence_count, token_count, transcript_hash) in EXPECTED.items():
            with self.subTest(asset_id=asset_id):
                payload = json.loads(
                    (LISTENING_DIR / f"{asset_id}.json").read_text(encoding="utf-8")
                )
                segments = payload["parts"][0]["segments"]
                tokens = [
                    token for segment in segments for token in normalized_tokens(segment["text"])
                ]

                self.assertEqual(payload["id"], asset_id)
                self.assertEqual(payload["audio"], f"{asset_id}_xdf_20260813.mp3")
                self.assertEqual(payload["source"]["provider"], "xdf_ieltscat_mapped")
                self.assertEqual(payload["source"]["q_id"], qid)
                self.assertEqual(len(segments), sentence_count)
                self.assertEqual(len(tokens), token_count)
                self.assertEqual(
                    hashlib.sha256(" ".join(tokens).encode()).hexdigest(),
                    transcript_hash,
                )
                self.assertTrue(all(segment["translation"].strip() for segment in segments))

    def test_all_timelines_are_contiguous_and_use_audio_calibration(self):
        for asset_id, (qid, *_unused) in EXPECTED.items():
            with self.subTest(asset_id=asset_id):
                payload = json.loads(
                    (LISTENING_DIR / f"{asset_id}.json").read_text(encoding="utf-8")
                )
                segments = payload["parts"][0]["segments"]
                mapping = payload["source"]["mapping"]

                self.assertEqual(segments[0]["start"], 0)
                self.assertEqual(
                    [segment["id"] for segment in segments],
                    list(range(1, len(segments) + 1)),
                )
                for previous, current in zip(segments, segments[1:], strict=False):
                    self.assertAlmostEqual(previous["end"], current["start"], places=2)
                self.assertTrue(all(segment["end"] > segment["start"] for segment in segments))
                self.assertEqual(
                    mapping["region_offset_method"],
                    "xdf_reference_audio_cross_correlation",
                )
                self.assertEqual(
                    mapping["region_offsets_seconds"], list(REGION_OFFSETS_SECONDS[qid])
                )
                self.assertEqual(mapping["clip_edge_margin_seconds"], 0.2)
                self.assertEqual(len(mapping["clips"]), len(REGION_OFFSETS_SECONDS[qid]))
                self.assertEqual(len(mapping["removed_gaps_seconds"]), len(mapping["clips"]) - 1)
                self.assertTrue(all(gap > 30 for gap in mapping["removed_gaps_seconds"]))

    def test_known_source_ocr_defects_do_not_break_word_alignment(self):
        self.assertEqual(
            normalized_tokens("companywas ffnished fft fgure"),
            [
                "company",
                "was",
                "finished",
                "fit",
                "figure",
            ],
        )
        self.assertEqual(
            normalized_tokens("DEV: Example sentence.DEV:"),
            [
                "example",
                "sentence",
            ],
        )

    def test_existing_tasks_can_keep_using_hidden_legacy_snapshots(self):
        expected_legacy = {
            "ielts20_test2_s2_legacy_20260813": ("ielts20_test2_s2.mp3", 35),
            "ielts20_test4_s4_legacy_20260813": ("ielts20_test4_s4.mp3", 29),
        }
        for exercise_id, (audio_name, segment_count) in expected_legacy.items():
            with self.subTest(exercise_id=exercise_id):
                payload, info, loaded_id = load_registered_intensive_exercise(
                    LISTENING_DIR,
                    exercise_id,
                )
                self.assertEqual(loaded_id, exercise_id)
                self.assertEqual(info["book"], 20)
                self.assertTrue(payload["hidden_from_catalog"])
                self.assertEqual(payload["audio"], audio_name)
                self.assertEqual(
                    sum(len(part["segments"]) for part in payload["parts"]),
                    segment_count,
                )

        catalog = build_intensive_catalog(LISTENING_DIR)
        cambridge_20 = next(
            book for book in catalog if book["series"] == "cambridge" and book["book"] == 20
        )
        self.assertEqual(len(cambridge_20["tests"]), 4)
        self.assertTrue(all(len(test["parts"]) == 4 for test in cambridge_20["tests"]))
        catalog_ids = {part["id"] for test in cambridge_20["tests"] for part in test["parts"]}
        self.assertTrue(catalog_ids.isdisjoint(expected_legacy))


if __name__ == "__main__":
    unittest.main()
