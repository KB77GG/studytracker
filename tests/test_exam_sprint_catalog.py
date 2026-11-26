"""Real snapshot/content/media verification for the answer-free staff catalog."""

import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api.teacher_practice_catalog import build_listening_jijing_assignment
from services.exam_sprint import content_digest, publish_snapshot
from services.exam_sprint_catalog import (
    load_sprint_catalog,
    sprint_assignment,
    sprint_assignment_options,
)
from services.exam_sprint_import import prepare_complete_snapshot
from services.exam_sprint_store import load_ninefen_document
from services.ninefen_assets import cache_unit_media
from tests.test_exam_sprint import feed
from tests.test_ninefen_assets import mp3_bytes, png_bytes
from tests.test_ninefen_content import paper


class SprintCatalogFixture:
    def __init__(self, root):
        self.root = Path(root)
        self.state = self.root / "instance/exam_sprint"
        self.feed = feed()
        self.exams = {}
        for groups in self.feed["subjects"].values():
            for group in groups:
                for row in group["items"]:
                    row["source_available"] = False
        for subject in ("reading", "listening"):
            row = self.feed["subjects"][subject][1]["items"][0]
            raw, answers = paper(subject)
            raw["data"].update(id=row["source_id"], title=row["title"], isCharge=0)
            row.update(source_available=True, source_part_id=raw["data"]["parts"][0]["id"])
            self.exams[row["source_id"]] = raw
            path = self.state / "answers" / f"{row['source_id']}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "unit_id": row["source_id"],
                        "source_content_sha256": content_digest(raw),
                        "answers_by_question_id": answers,
                    }
                )
            )
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
        self.snapshot = prepare_complete_snapshot(self.root, self.feed, self.exams)
        publish_snapshot(self.state, self.snapshot)

    def item(self, subject):
        return load_sprint_catalog(self.root, subject)["groups"][1]["items"][0]


class SprintCatalogTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("EXAM_SPRINT_STATE_DIR", None)
        self.fixture = SprintCatalogFixture(temp.name)
        self.root = self.fixture.root

    def test_only_ready_entries_with_fixed_versions_and_no_answers(self):
        for subject in ("reading", "listening"):
            catalog = load_sprint_catalog(self.root, subject)
            self.assertEqual(catalog["total"], 1)
            item = self.fixture.item(subject)
            self.assertEqual(item["question_count"], 4)
            self.assertEqual(item["part"], 2)
            self.assertEqual(item["target_kind"], "ninefen")
            self.assertIn(item["mapping"]["source_content_sha256"][:12], item["target_id"])
            self.assertNotIn('"answer"', json.dumps(catalog))
            self.assertNotIn("drum", json.dumps(catalog))
        reading = self.fixture.item("reading")
        self.assertEqual(reading["passage"], 1)
        self.assertEqual(reading["selection_id"], reading["target_id"] + "@1")

    def test_missing_media_or_tampered_content_disables_new_assignments(self):
        item = self.fixture.item("listening")
        audio = next(
            asset for asset in item["mapping"]["assets"] if asset["filename"].endswith(".mp3")
        )
        (self.fixture.state / "assets" / audio["filename"]).unlink()
        self.assertEqual(load_sprint_catalog(self.root, "listening")["total"], 0)
        self.assertIsNone(sprint_assignment(self.root, "listening", item["selection_id"]))
        reading = self.fixture.item("reading")
        path = self.fixture.state / "content/reading" / f"{reading['target_id']}.json"
        path.write_bytes(path.read_bytes() + b" ")
        self.assertEqual(load_sprint_catalog(self.root, "reading")["total"], 0)

    def test_latest_snapshot_refresh_does_not_erase_old_version(self):
        item = self.fixture.item("reading")
        newer = copy.deepcopy(self.fixture.snapshot)
        newer["fetched_at"] = "2026-11-23T02:00:00+00:00"
        newer["subjects"]["reading"][1]["items"][0]["source_available"] = False
        publish_snapshot(self.fixture.state, newer)
        catalog = load_sprint_catalog(self.root, "reading")
        self.assertEqual(catalog["total"], 0)
        self.assertEqual(catalog["updated_at_label"], "2026-11-23 10:00")
        self.assertIsNone(sprint_assignment(self.root, "reading", item["selection_id"]))
        self.assertIsNotNone(load_ninefen_document(self.root, "reading", item["target_id"]))

    def test_selection_validation_rejects_wrong_subject_scope_and_traversal(self):
        reading, listening = self.fixture.item("reading"), self.fixture.item("listening")
        for value in (
            reading["target_id"],
            reading["target_id"] + "@2",
            listening["selection_id"],
            "../x@1",
        ):
            self.assertIsNone(sprint_assignment(self.root, "reading", value))
        self.assertIsNone(sprint_assignment(self.root, "listening", reading["selection_id"]))
        assignment = sprint_assignment(self.root, "reading", reading["selection_id"])
        self.assertEqual(assignment["id"], reading["target_id"])
        self.assertEqual(assignment["passage"], 1)
        self.assertEqual(assignment["planned_minutes"], 20)

    def test_options_do_not_confuse_legacy_and_sprint_values(self):
        options = sprint_assignment_options(self.root)
        listening = options["listening"][0]
        self.assertEqual(listening["resource_type"], "jijing")
        self.assertEqual(listening["id"], "sprint:" + listening["target_id"])
        assignment = build_listening_jijing_assignment(
            self.root / "static/listening_jijing", listening["id"], app_root=self.root
        )
        self.assertEqual(assignment["id"], listening["target_id"])
        self.assertEqual(assignment["category"], "雅思-听力-7天热榜")
        self.assertIsNone(build_listening_jijing_assignment(self.root, listening["id"]))
        reading = options["reading"][0]
        self.assertEqual(len(options["reading_passages"][reading["id"]]), 1)

    def test_existing_manual_exact_mapping_is_eligible_and_rechecked(self):
        row = self.fixture.snapshot["subjects"]["reading"][0]["items"][0]
        target = "reading_jijing_fixture"
        path = self.root / "static/reading_jijing" / f"{target}.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "id": target,
                    "source": "idictation_reading_jijing",
                    "passages": [
                        {
                            "passage": 3,
                            "groups": [{"questions": [{"id": "x", "answer": "private"}]}],
                        }
                    ],
                }
            )
        )
        mapping = {
            "subject": "reading",
            "source_id": row["source_id"],
            "source_title": row["title"],
            "target_id": target,
            "passage": 3,
            "source_content_sha256": "a" * 64,
            "target_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        manifest = self.root / "data/exam_sprint/mappings.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"schema_version": 1, "mappings": [mapping]}))
        row.update(source_available=True, mapping=mapping)
        publish_snapshot(self.fixture.state, self.fixture.snapshot)
        item = load_sprint_catalog(self.root, "reading")["groups"][0]["items"][0]
        self.assertEqual(
            (item["target_kind"], item["passage"], item["question_count"]), ("legacy", 3, 1)
        )
        self.assertEqual(sprint_assignment(self.root, "reading", target + "@3")["id"], target)
        manifest.write_text('{"schema_version":1,"mappings":[]}')
        self.assertIsNone(sprint_assignment(self.root, "reading", target + "@3"))


if __name__ == "__main__":
    unittest.main()
