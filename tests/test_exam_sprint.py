"""Fail-closed source matching and atomic weekly update checks."""

import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from services.exam_sprint import (
    content_digest,
    load_sprint_view,
    prepare_snapshot,
    publish_snapshot,
    validate_snapshot,
)


def feed():
    return {
        "source": "ninefen",
        "fetched_at": "2026-11-15T03:00:00+00:00",
        "source_updated_at": None,
        "subjects": {
            subject: [
                {
                    "part": part,
                    "items": [
                        {
                            "source_id": f"{prefix}{part}{rank:02d}",
                            "rank": rank,
                            "title": f"Title {part}-{rank}",
                            "title_zh": "题目",
                            "source_available": True,
                            "entry_mode": "exam",
                        }
                        for rank in range(1, 21)
                    ],
                }
                for part in range(1, count + 1)
            ]
            for subject, count, prefix in (("reading", 3, "1"), ("listening", 4, "2"))
        },
    }


class SprintSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "instance" / "exam_sprint"
        self.now = datetime(2026, 11, 15, 4, tzinfo=timezone.utc)  # noqa: UP017 (Python 3.10)
        self.exam = {"data": {"id": "1101", "parts": [{"questions": ["one"]}]}}
        self.mapping_file = self.root / "data" / "exam_sprint" / "mappings.json"
        self.mapping_file.parent.mkdir(parents=True)

    def install_mapping(self, subject="reading"):
        target = "reading_jijing_1_test_1" if subject == "reading" else "xiahuar_001_p1"
        folder = self.root / "static" / f"{subject}_jijing"
        path = (
            folder / f"{target}.json"
            if subject == "reading"
            else folder / "parts" / f"{target}.json"
        )
        path.parent.mkdir(parents=True)
        data = {
            "id": target,
            "source": "idictation_reading_jijing",
            "passages": [{"passage": 1}],
            "audio": {"local_path": "audio/example.mp3"},
        }
        path.write_text(json.dumps(data))
        if subject == "listening":
            audio = folder / "audio" / "example.mp3"
            audio.parent.mkdir()
            audio.write_bytes(b"test fixture audio")
        row = {
            "source_id": "1101" if subject == "reading" else "2101",
            "source_title": "Title 1-1",
            "subject": subject,
            "target_id": target,
            "passage": 1,
            "source_content_sha256": content_digest(self.exam),
            "target_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        self.mapping_file.write_text(json.dumps({"schema_version": 1, "mappings": [row]}))
        return row, path

    def capture(self, payload=None, fetcher=None):
        result = prepare_snapshot(self.root, payload or feed(), fetcher)
        publish_snapshot(self.state, result)
        return result

    def test_complete_feed_renders_real_count_without_guessed_links(self):
        self.capture()
        result = load_sprint_view(self.root, "reading", now=self.now)
        self.assertEqual((result["total"], result["ready_count"]), (60, 0))
        self.assertFalse(result["stale"])
        self.assertEqual(result["source_updated_at_label"], "")
        self.assertIn("11月16日", result["next_update_label"])

    def test_missing_snapshot_and_invalid_subject(self):
        self.assertFalse(load_sprint_view(self.root, "reading")["available"])
        with self.assertRaises(ValueError):
            load_sprint_view(self.root, "writing")

    def test_partial_duplicate_and_wrong_rank_rejected(self):
        original = self.capture()
        for mutate in (
            lambda f: f["subjects"].pop("reading"),
            lambda f: f["subjects"]["reading"][0]["items"].pop(),
            lambda f: f["subjects"]["reading"][0]["items"][1].update(source_id="1101"),
            lambda f: f["subjects"]["listening"][0]["items"][0].update(rank=5),
        ):
            candidate = copy.deepcopy(original)
            mutate(candidate)
            with self.assertRaises(ValueError):
                publish_snapshot(self.state, candidate)
        self.assertEqual(json.loads((self.state / "current.json").read_text()), original)

    def test_failed_swap_retains_current_and_cleans_temporary(self):
        original = self.capture()
        candidate = copy.deepcopy(original)
        candidate["fetched_at"] = "2026-11-16T00:00:00+00:00"
        real_replace = __import__("os").replace

        def fail_current(src, dst):
            if Path(dst).name == "current.json":
                raise OSError("disk write failed")
            return real_replace(src, dst)

        with patch("services.exam_sprint.os.replace", side_effect=fail_current):
            with self.assertRaises(OSError):
                publish_snapshot(self.state, candidate)
        self.assertEqual(json.loads((self.state / "current.json").read_text()), original)
        self.assertEqual(list(self.state.glob(".current.json.*")), [])

    def test_correct_mapping_opens_only_its_reading_passage(self):
        self.install_mapping()
        self.capture(fetcher=lambda _: self.exam)
        result = load_sprint_view(self.root, "reading", now=self.now)
        self.assertEqual(result["ready_count"], 1)
        self.assertEqual(
            result["groups"][0]["items"][0]["practice_url"],
            "/reading/jijing/reading_jijing_1_test_1?passage=1",
        )
        self.assertIsNone(result["groups"][0]["items"][1]["practice_url"])

    def test_source_content_change_retires_mapping(self):
        self.install_mapping()
        self.capture(fetcher=lambda _: {"data": {"parts": [{"questions": ["changed"]}]}})
        self.assertEqual(load_sprint_view(self.root, "reading", now=self.now)["ready_count"], 0)

    def test_fetch_failure_does_not_replace_previous(self):
        self.install_mapping()
        previous = self.capture()
        with self.assertRaises(TimeoutError):
            self.capture(fetcher=lambda _: (_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(json.loads((self.state / "current.json").read_text()), previous)

    def test_offline_import_does_not_claim_reverified_mapping(self):
        self.install_mapping()
        self.capture()
        self.assertEqual(load_sprint_view(self.root, "reading", now=self.now)["ready_count"], 0)

    def test_local_edits_and_offline_manifest_disable_existing_link(self):
        row, path = self.install_mapping()
        self.capture(fetcher=lambda _: self.exam)
        offline = path.parent / "offline_tests.json"
        offline.write_text(json.dumps({"tests": [{"id": row["target_id"], "status": "offline"}]}))
        self.assertEqual(load_sprint_view(self.root, "reading", now=self.now)["ready_count"], 0)
        offline.write_text('{"tests": []}')
        path.write_text(path.read_text() + " ")
        self.assertEqual(load_sprint_view(self.root, "reading", now=self.now)["ready_count"], 0)

    def test_revoked_mapping_is_disabled_before_the_next_weekly_sync(self):
        self.install_mapping()
        self.capture(fetcher=lambda _: self.exam)
        self.mapping_file.write_text('{"schema_version": 1, "mappings": []}')
        self.assertEqual(load_sprint_view(self.root, "reading", now=self.now)["ready_count"], 0)

    def test_malformed_mapping_does_not_crash_the_public_page(self):
        snapshot = self.capture()
        snapshot["subjects"]["reading"][0]["items"][0]["mapping"] = ["broken"]
        (self.state / "current.json").write_text(json.dumps(snapshot))
        self.assertFalse(load_sprint_view(self.root, "reading", now=self.now)["available"])

    def test_listening_missing_audio_is_not_playable(self):
        _, path = self.install_mapping("listening")
        self.capture(fetcher=lambda _: self.exam)
        self.assertEqual(load_sprint_view(self.root, "listening", now=self.now)["ready_count"], 1)
        (path.parent.parent / "audio" / "example.mp3").unlink()
        self.assertEqual(load_sprint_view(self.root, "listening", now=self.now)["ready_count"], 0)

    def test_locked_rows_are_not_fetched_or_linked(self):
        self.install_mapping()
        source = feed()
        source["subjects"]["reading"][0]["items"][0]["source_available"] = False
        with patch("builtins.print"):
            self.capture(source, lambda _: self.fail("Must not fetch a locked item"))
        self.assertEqual(load_sprint_view(self.root, "reading", now=self.now)["ready_count"], 0)

    def test_missed_weekly_run_marks_snapshot_stale(self):
        self.capture()
        # Monday 07:01 China time, after the one-hour update allowance.
        now = datetime(2026, 11, 15, 23, 1, tzinfo=timezone.utc)  # noqa: UP017 (Python 3.10)
        self.assertTrue(load_sprint_view(self.root, "reading", now=now)["stale"])

    def test_invalid_timestamp_cannot_be_published(self):
        snapshot = self.capture()
        snapshot["fetched_at"] = "2026-11-15T03:00:00"
        with self.assertRaises(ValueError):
            validate_snapshot(snapshot)

    def test_seed_fallback_is_read_only_and_does_not_fake_update_time(self):
        snapshot = self.capture()
        (self.mapping_file.parent / "latest.json").write_text(json.dumps(snapshot))
        (self.state / "current.json").write_text("broken")
        result = load_sprint_view(self.root, "reading", now=self.now)
        self.assertTrue(result["available"])
        self.assertEqual(result["updated_at_label"], "2026-11-15 11:00")


if __name__ == "__main__":
    unittest.main()
