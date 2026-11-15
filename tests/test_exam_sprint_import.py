"""Whole-week preparation, exact-version reuse and verified media, fully offline."""

import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from services.exam_sprint import _local_target, content_digest, publish_snapshot, validate_snapshot
from services.exam_sprint_import import (
    IncompleteSprintError,
    prepare_complete_snapshot,
    ranked_rows,
)
from services.ninefen_assets import NinefenAssetError, cache_unit_media
from tests.test_exam_sprint import feed
from tests.test_ninefen_assets import mp3_bytes, png_bytes
from tests.test_ninefen_content import paper


class SprintImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "instance/exam_sprint"
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("EXAM_SPRINT_STATE_DIR", None)
        self.feed = feed()
        for _, row in ranked_rows(self.feed):
            row["source_available"] = False
        self.exams, self.answers = {}, {}
        network = patch(
            "services.ninefen_assets._fetch_bytes",
            side_effect=AssertionError("Unexpected network access"),
        )
        self.network = network.start()
        self.addCleanup(network.stop)

    def add_unit(self, subject="reading", *, rank=0, answers=True, media=True):
        row = self.feed["subjects"][subject][1]["items"][rank]
        raw, key = paper(subject)
        unit = row["source_id"]
        raw["data"].update(id=unit, title=row["title"], isCharge=0)
        row.update(source_available=True, source_part_id=raw["data"]["parts"][0]["id"])
        self.exams[unit], self.answers[unit] = raw, key
        if answers:
            self.save_answers(unit)
        if media:
            cache_unit_media(
                raw,
                self.state / "assets",
                self.state / "media",
                fetcher=lambda url, **_: (
                    (mp3_bytes(), "audio/mpeg")
                    if url.endswith(".mp3")
                    else (png_bytes(), "image/png")
                ),
            )
        return unit, row

    def save_answers(self, unit, *, digest=None):
        path = self.state / "answers" / f"{unit}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "unit_id": unit,
                    "source_content_sha256": digest or content_digest(self.exams[unit]),
                    "answers_by_question_id": self.answers[unit],
                }
            )
        )
        return path

    def install_manual(self, unit):
        target = "reading_jijing_verified"
        path = self.root / "static/reading_jijing" / f"{target}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"id": target, "source": "idictation_reading_jijing", "passages": [{"passage": 1}]}
            )
        )
        mapping = {
            "subject": "reading",
            "source_id": unit,
            "source_title": self.exams[unit]["data"]["title"],
            "source_part_id": self.exams[unit]["data"]["parts"][0]["id"],
            "target_id": target,
            "passage": 1,
            "source_content_sha256": content_digest(self.exams[unit]),
            "target_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        manifest = self.root / "data/exam_sprint/mappings.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"schema_version": 1, "mappings": [mapping]}))
        return mapping, path

    def prepare(self, **kwargs):
        return prepare_complete_snapshot(self.root, self.feed, self.exams, **kwargs)

    def save_current(self, snapshot=None):
        publish_snapshot(self.state, snapshot or {**self.feed, "schema_version": 1})
        return (self.state / "current.json").read_bytes()

    @staticmethod
    def mapping(snapshot, unit):
        return next(row["mapping"] for _, row in ranked_rows(snapshot) if row["source_id"] == unit)

    def test_all_open_rows_are_ready_before_return_without_publishing(self):
        self.add_unit("reading")
        self.add_unit("listening")
        progress = Mock()
        candidate = self.prepare(progress=progress)
        validate_snapshot(candidate)
        open_rows = [row for _, row in ranked_rows(candidate) if row["source_available"]]
        self.assertEqual(len(open_rows), 2)
        self.assertTrue(all(not row["unavailable_reason"] for row in open_rows))
        self.assertTrue(all(row["mapping"]["assets"] for row in open_rows))
        self.assertEqual([call.args[-1] for call in progress.call_args_list], ["imported"] * 2)
        self.assertFalse((self.state / "current.json").exists())
        self.network.assert_not_called()

    def test_missing_answer_after_one_import_preserves_current_week(self):
        self.add_unit("reading")
        self.add_unit("listening", answers=False)
        previous = self.save_current()
        with self.assertRaisesRegex(IncompleteSprintError, "Official answers unavailable"):
            self.prepare()
        self.assertEqual((self.state / "current.json").read_bytes(), previous)
        self.assertEqual(len(list((self.state / "content/reading").glob("*.meta.json"))), 1)

    def test_old_manual_exact_version_reuses_without_answers_or_media(self):
        unit, _ = self.add_unit(answers=False, media=False)
        mapping, _ = self.install_manual(unit)
        provider = Mock(side_effect=AssertionError("Must not collect answers"))
        result = self.prepare(answer_provider=provider)
        self.assertEqual(self.mapping(result, unit), mapping)
        provider.assert_not_called()
        self.network.assert_not_called()

    def test_changed_manual_source_version_cannot_reuse_answers(self):
        unit, _ = self.add_unit(answers=False, media=False)
        self.install_manual(unit)
        self.exams[unit]["data"]["parts"][0]["groups"][0]["description"] += " Changed."
        with self.assertRaisesRegex(IncompleteSprintError, "Official answers unavailable"):
            self.prepare()

    def test_modified_manual_local_document_cannot_be_reused(self):
        unit, _ = self.add_unit(answers=False, media=False)
        _, path = self.install_manual(unit)
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(IncompleteSprintError, "Official answers unavailable"):
            self.prepare()

    def test_previous_native_version_is_reused_without_answer_files(self):
        unit, _ = self.add_unit()
        first = self.prepare()
        self.save_current(first)
        (self.state / "answers" / f"{unit}.json").unlink()
        provider, progress = Mock(), Mock()
        second = self.prepare(answer_provider=provider, progress=progress)
        self.assertEqual(self.mapping(second, unit), self.mapping(first, unit))
        provider.assert_not_called()
        self.assertEqual(progress.call_args.args[-1], "reused")

    def test_changed_native_source_cannot_reuse_old_answer_or_document(self):
        unit, _ = self.add_unit()
        previous = self.save_current(self.prepare())
        self.exams[unit]["data"]["parts"][0]["groups"][0]["description"] += " Changed."
        with self.assertRaisesRegex(IncompleteSprintError, "Official answers unavailable"):
            self.prepare()
        self.assertEqual((self.state / "current.json").read_bytes(), previous)

    def test_invalid_previous_native_does_not_hide_valid_manual_mapping(self):
        unit, _ = self.add_unit()
        previous = self.prepare()
        self.mapping(previous, unit)["source_content_sha256"] = "0" * 64
        self.save_current(previous)
        manual, _ = self.install_manual(unit)
        (self.state / "answers" / f"{unit}.json").unlink()
        result = self.prepare()
        self.assertEqual(self.mapping(result, unit), manual)

    def test_provider_must_persist_a_current_version_key(self):
        unit, _ = self.add_unit(answers=False)
        provider = Mock(side_effect=lambda requested, raw: self.save_answers(requested))
        candidate = self.prepare(answer_provider=provider)
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(provider.call_args.args, (unit, self.exams[unit]))
        self.assertTrue(self.mapping(candidate, unit))

    def test_provider_wrong_version_does_not_publish_or_retry_collection(self):
        unit, _ = self.add_unit(answers=False)
        previous = self.save_current()
        provider = Mock(
            side_effect=lambda requested, raw: self.save_answers(requested, digest="0" * 64)
        )
        with self.assertRaisesRegex(IncompleteSprintError, "Official answers unavailable"):
            self.prepare(answer_provider=provider)
        self.assertEqual(provider.call_count, 1)
        self.assertEqual((self.state / "current.json").read_bytes(), previous)

    def test_media_manifest_must_cover_source_and_match_safe_local_urls(self):
        unit, _ = self.add_unit()
        path = self.state / "media" / f"{unit}.json"
        original = json.loads(path.read_text())
        previous = self.save_current()
        mutations = (
            lambda m: m.update(assets=[]),
            lambda m: m.update(unit_id="999"),
            lambda m: m["media_map"].clear(),
            lambda m: m["media_map"].update(
                {next(iter(m["media_map"])): "https://outside.invalid/a.png"}
            ),
            lambda m: m["assets"][0].update(filename="../unsafe.png"),
            lambda m: m["assets"][0].update(byte_count=1),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                damaged = copy.deepcopy(original)
                mutate(damaged)
                path.write_text(json.dumps(damaged))
                with patch(
                    "services.ninefen_assets._fetch_bytes", side_effect=NinefenAssetError("offline")
                ):
                    with self.assertRaisesRegex(NinefenAssetError, "offline"):
                        self.prepare()
                self.assertEqual((self.state / "current.json").read_bytes(), previous)
                self.assertEqual(json.loads(path.read_text()), damaged)

    def test_equal_size_media_corruption_is_not_accepted_for_new_import(self):
        unit, _ = self.add_unit()
        manifest = json.loads((self.state / "media" / f"{unit}.json").read_text())
        path = self.state / "assets" / manifest["assets"][0]["filename"]
        raw = path.read_bytes()
        path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        with patch(
            "services.ninefen_assets._fetch_bytes", side_effect=NinefenAssetError("offline")
        ):
            with self.assertRaisesRegex(NinefenAssetError, "offline"):
                self.prepare()
        self.assertFalse((self.state / "content").exists())

    def test_native_mapping_cannot_omit_referenced_audio_assets(self):
        unit, _ = self.add_unit("listening")
        mapping = self.mapping(self.prepare(), unit)
        self.assertIsNotNone(_local_target(self.root, mapping))
        self.assertIsNone(_local_target(self.root, {**mapping, "assets": []}))
        images_only = [
            asset for asset in mapping["assets"] if not asset["filename"].endswith(".mp3")
        ]
        self.assertIsNone(_local_target(self.root, {**mapping, "assets": images_only}))

    def test_native_mapping_malformed_asset_metadata_fails_closed(self):
        unit, _ = self.add_unit("listening")
        mapping = self.mapping(self.prepare(), unit)
        valid_asset = mapping["assets"][0]
        damaged = (
            None,
            {},
            [None],
            ["broken"],
            [{**valid_asset, "filename": 7}],
            [{**valid_asset, "filename": "../outside.mp3"}],
            [{**valid_asset, "sha256": "0" * 64}],
            [{**valid_asset, "byte_count": True}],
            [{**valid_asset, "byte_count": -1}],
            [valid_asset, valid_asset],
        )
        for metadata in damaged:
            with self.subTest(metadata=metadata):
                self.assertIsNone(_local_target(self.root, {**mapping, "assets": metadata}))

    def test_native_asset_hash_cache_rechecks_equal_size_changes(self):
        unit, _ = self.add_unit("listening")
        mapping = self.mapping(self.prepare(), unit)
        self.assertIsNotNone(_local_target(self.root, mapping))
        asset = next(asset for asset in mapping["assets"] if asset["filename"].endswith(".mp3"))
        path = self.state / "assets" / asset["filename"]
        before = path.stat()
        raw = path.read_bytes()
        path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
        self.assertEqual(path.stat().st_size, before.st_size)
        self.assertIsNone(_local_target(self.root, mapping))

    def test_incomplete_feed_is_rejected_before_provider_or_import(self):
        self.add_unit(answers=False)
        self.feed["subjects"]["listening"].pop()
        provider = Mock(side_effect=AssertionError("Invalid week must not collect answers"))
        with self.assertRaisesRegex(ValueError, "Incomplete part list"):
            self.prepare(answer_provider=provider)
        provider.assert_not_called()

    def test_subject_and_ranked_part_must_match_the_import(self):
        unit, row = self.add_unit()
        self.exams[unit]["data"]["channel"] = "listening"
        with self.assertRaisesRegex(IncompleteSprintError, "Source subject"):
            self.prepare()
        self.exams[unit]["data"]["channel"] = "reading"
        row["source_part_id"] = "999"
        with self.assertRaisesRegex(IncompleteSprintError, "unique practice document"):
            self.prepare()


if __name__ == "__main__":
    unittest.main()
