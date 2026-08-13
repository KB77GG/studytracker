import hashlib
import json
import unittest
from pathlib import Path

from scripts.build_xdf_intensive_pilot import (
    ORIGINAL_AUDIO_BACKUP,
    _infer_regions,
    _token_spans,
    normalized_tokens,
)

ROOT = Path(__file__).resolve().parents[1]
EXERCISE_PATH = ROOT / "static/listening/ielts20_test1_s1.json"
EXPECTED_TRANSCRIPT_SHA256 = "9a89273c77bcc39d7ec545e9c6cb2691292878ce96d2bd963e3b8e48d6780ba9"


def _segments(payload):
    return [
        segment for part in payload.get("parts") or [] for segment in part.get("segments") or []
    ]


class XdfIntensiveReplacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exercise = json.loads(EXERCISE_PATH.read_text(encoding="utf-8"))
        cls.segments = _segments(cls.exercise)

    def test_canonical_exercise_uses_the_verified_45_sentence_transcript(self):
        tokens = [
            token for segment in self.segments for token in normalized_tokens(segment["text"])
        ]
        transcript_hash = hashlib.sha256(" ".join(tokens).encode()).hexdigest()

        self.assertEqual(self.exercise["id"], "ielts20_test1_s1")
        self.assertEqual(self.exercise["audio"], "ielts20_test1_s1_xdf_20260813.mp3")
        self.assertEqual(self.exercise["source"]["provider"], "xdf_ieltscat_mapped")
        self.assertEqual(len(self.segments), 45)
        self.assertEqual(len(tokens), 742)
        self.assertEqual(transcript_hash, EXPECTED_TRANSCRIPT_SHA256)

    def test_dialogue_only_timeline_is_contiguous_and_removes_instruction_gap(self):
        self.assertEqual(self.segments[0]["start"], 0)
        for previous, current in zip(self.segments, self.segments[1:], strict=False):
            self.assertAlmostEqual(previous["end"], current["start"], places=2)

        mapping = self.exercise["source"]["mapping"]
        self.assertEqual(mapping["original_dialogue_segment_count"], 58)
        self.assertEqual(mapping["shared_internal_boundaries"], 42)
        self.assertEqual(len(mapping["removed_gaps_seconds"]), 1)
        self.assertGreater(mapping["removed_gaps_seconds"][0], 46)
        self.assertLess(mapping["removed_gaps_seconds"][0], 47)
        self.assertLess(self.segments[-1]["end"], 281)

    def test_cut_happens_between_dialogue_sentences_not_inside_speech(self):
        before_cut = self.segments[26]
        after_cut = self.segments[27]

        self.assertIn("selection of those", before_cut["text"])
        self.assertIn("another idea", after_cut["text"])
        self.assertLess(before_cut["original_end"], 206)
        self.assertGreater(after_cut["original_start"], 251)
        self.assertAlmostEqual(before_cut["end"], after_cut["start"], places=2)

    def test_miniprogram_stops_at_the_declared_end_without_early_margin(self):
        source = (ROOT / "miniprogram/pages/student/listening/practice/index.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("currentTime >= Math.max(segment.start, segment.end)", source)
        self.assertNotIn("segment.end - 0.05", source)

    def test_generator_recovers_original_timeline_after_replacement(self):
        _, local_spans = _token_spans(self.segments, "text")
        xdf_rows = [
            {
                "entext": segment["text"],
                "start": segment["source_start_time"] / 1000,
                "end": segment["source_end_time"] / 1000,
            }
            for segment in self.segments
        ]
        _, xdf_spans = _token_spans(xdf_rows, "entext")
        regions = _infer_regions(xdf_spans, local_spans)

        self.assertEqual(
            ORIGINAL_AUDIO_BACKUP,
            "ielts20_test1_s1_pre_45sentence_20260813.mp3",
        )
        self.assertEqual(len(regions), 2)
        self.assertAlmostEqual(regions[0]["offset"], 40.645, places=3)
        self.assertAlmostEqual(regions[1]["offset"], 87.412, places=3)


if __name__ == "__main__":
    unittest.main()
