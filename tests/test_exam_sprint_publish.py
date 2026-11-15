"""Public-only transfer plans and activation failures retain the previous week."""

import copy
import fcntl
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from scripts.activate_exam_sprint import (
    activate,
    prepare_public_directories,
    using_state_directory,
    validate_candidate,
)
from scripts.publish_exam_sprint import (
    ALLOWED_HOST,
    ALLOWED_REMOTE_ROOT,
    build_commands,
    public_files,
    publish,
)
from services.exam_sprint_store import save_converted_documents
from tests.test_exam_sprint import feed
from tests.test_ninefen_content import IMAGE, convert, paper


class SprintPublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "instance/exam_sprint"
        prepare_public_directories(self.root)
        mappings = self.root / "data/exam_sprint/mappings.json"
        mappings.parent.mkdir(parents=True)
        mappings.write_text('{"schema_version":1,"mappings":[]}')
        self.mapping_file = mappings
        self.snapshot = {**feed(), "schema_version": 1}
        for groups in self.snapshot["subjects"].values():
            for group in groups:
                for row in group["items"]:
                    row["source_available"] = False
        raw, answers = paper()
        asset_bytes = b"synthetic media checksum fixture"
        digest = hashlib.sha256(asset_bytes).hexdigest()
        self.asset = self.state / "assets" / f"{digest}.png"
        self.asset.write_bytes(asset_bytes)
        converted = convert(
            raw, answers, media_map={IMAGE: f"/practice/sprint/assets/{digest}.png"}
        )
        with using_state_directory(self.state):
            self.mapping = save_converted_documents(self.root, converted)[0]
        self.mapping["assets"] = [
            {"filename": self.asset.name, "sha256": digest, "byte_count": len(asset_bytes)}
        ]
        self.row = self.snapshot["subjects"]["reading"][1]["items"][0]
        self.row.update(
            {
                "source_available": True,
                "source_id": self.mapping["source_id"],
                "source_part_id": self.mapping["source_part_id"],
                "title": self.mapping["source_title"],
                "mapping": self.mapping,
                "unavailable_reason": "",
            }
        )
        self.current = self.state / "current.json"
        self.current.write_text(json.dumps(self.snapshot))
        self.old = self.current.read_bytes()

    def stage(self, snapshot=None):
        raw = json.dumps(snapshot or self.snapshot).encode()
        digest = hashlib.sha256(raw).hexdigest()
        path = self.state / "incoming" / f"{digest}.json"
        path.write_bytes(raw)
        return path, digest

    def test_dry_run_is_public_only_and_never_invokes_subprocess(self):
        for directory in ("private", "exams", "answers", "media"):
            path = self.state / directory
            path.mkdir()
            (path / "session.json").write_text("MUST NEVER UPLOAD")
        run = Mock()
        result = publish(
            self.state, ALLOWED_HOST, ALLOWED_REMOTE_ROOT, root=self.root, dry_run=True, runner=run
        )
        run.assert_not_called()
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["public_files"], 3)
        self.assertEqual(
            result["validation"], {"total": 140, "ready": 1, "imported": 1, "reviewed_legacy": 0}
        )
        names = public_files(self.state)
        self.assertTrue(all(name.startswith(("assets/", "content/reading/")) for name in names))
        self.assertNotIn("MUST NEVER UPLOAD", json.dumps(result))
        self.assertEqual(self.current.read_bytes(), self.old)

    def test_execution_plan_uploads_allowlist_then_hash_named_snapshot_then_activation(self):
        calls = []

        def run(command, *, input, check):
            self.assertTrue(check)
            calls.append((command, input))
            if len(calls) == 4:
                staged = Path(command[-2])
                self.assertTrue(staged.is_file())
                self.assertEqual(staged.read_bytes(), self.old)

        result = publish(self.state, ALLOWED_HOST, ALLOWED_REMOTE_ROOT, root=self.root, runner=run)
        self.assertEqual(len(calls), 5)
        self.assertIn("--prepare-directories", calls[0][0][-1])
        self.assertIn("--files-from=-", calls[1][0])
        for index, prefix in ((1, "assets/"), (2, "content/")):
            names = [
                name[len(prefix) :] for name in public_files(self.state) if name.startswith(prefix)
            ]
            self.assertEqual(calls[index][1].decode().split("\0")[:-1], names)
            self.assertEqual(calls[index][0][-2], str((self.state / prefix).resolve()) + "/")
        for command, _stdin in calls[1:4]:
            self.assertIn("--ignore-existing", command)
            self.assertNotIn("--delete", command)
        self.assertIn(f"/incoming/{result['snapshot_sha256']}.json", calls[3][0][-1])
        self.assertIn("/root/apps/studytracker/.venv/bin/python", calls[4][0][-1])
        self.assertIn("--expected-sha256", calls[4][0][-1])

    def test_remote_arguments_reject_injection_and_other_destinations(self):
        for host, root in (
            ("root@other", ALLOWED_REMOTE_ROOT),
            (ALLOWED_HOST + ";id", ALLOWED_REMOTE_ROOT),
            (ALLOWED_HOST, "/tmp/elsewhere"),
            (ALLOWED_HOST, ALLOWED_REMOTE_ROOT + "/../elsewhere"),
            (ALLOWED_HOST, ALLOWED_REMOTE_ROOT + "$(id)"),
        ):
            with self.subTest(host=host, root=root), self.assertRaises(ValueError):
                build_commands(self.state, host, root, "0" * 64)

    @unittest.skipUnless(shutil.which("rsync"), "Local rsync is not installed")
    def test_actual_local_rsync_copies_only_allowlist_and_preserves_existing_bytes(self):
        private = self.state / "private"
        private.mkdir()
        (private / "session.json").write_text("never transfer this fixture")
        destination = self.root / "local-transfer-target"
        destination.mkdir()
        commands = build_commands(self.state, ALLOWED_HOST, ALLOWED_REMOTE_ROOT, "0" * 64)
        transfers = []
        for index, folder in ((1, "assets"), (2, "content")):
            command = commands[index]
            (destination / folder).mkdir()
            command[-1] = str(destination / folder) + "/"
            prefix = folder + "/"
            names = [
                name[len(prefix) :] for name in public_files(self.state) if name.startswith(prefix)
            ]
            manifest = ("\0".join(names) + "\0").encode()
            subprocess.run(command, input=manifest, capture_output=True, check=True)
            transfers.append((command, manifest))
        self.assertEqual(
            sorted(
                p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()
            ),
            public_files(self.state),
        )
        copied = destination / "assets" / self.asset.name
        copied.write_bytes(b"existing remote bytes must not change")
        for command, manifest in transfers:
            subprocess.run(command, input=manifest, capture_output=True, check=True)
        self.assertEqual(copied.read_bytes(), b"existing remote bytes must not change")
        self.assertFalse((destination / "private").exists())

    def test_extra_or_symlink_public_inputs_are_rejected(self):
        bad = self.state / "assets/session.json"
        bad.write_text("not an asset")
        with self.assertRaises(ValueError):
            public_files(self.state)
        bad.unlink()
        bad.symlink_to(self.asset)
        with self.assertRaises(ValueError):
            public_files(self.state)
        bad.unlink()
        directory = self.state / "content/extra"
        directory.mkdir()
        with self.assertRaises(ValueError):
            public_files(self.state)

    def test_activation_validates_then_atomically_replaces_only_current(self):
        newer = copy.deepcopy(self.snapshot)
        newer["fetched_at"] = "2026-11-16T22:00:00+00:00"
        path, digest = self.stage(newer)
        result = activate(self.root, path, digest)
        self.assertTrue(result["activated"])
        self.assertEqual(json.loads(self.current.read_bytes()), newer)
        self.assertEqual(len(list((self.state / "history").glob("*.json"))), 1)
        self.assertTrue(path.exists())

    def test_media_corruption_rejects_activation_and_keeps_old_week(self):
        path, digest = self.stage()
        self.asset.write_bytes(b"corrupted media")
        with self.assertRaises(ValueError):
            activate(self.root, path, digest)
        self.assertEqual(self.current.read_bytes(), self.old)
        self.assertFalse((self.state / "history").exists())

    def test_wrong_source_or_content_metadata_rejects_before_publication(self):
        for field, value in (
            ("source_id", "999"),
            ("source_part_id", "999"),
            ("source_content_sha256", "0" * 64),
            ("target_sha256", "0" * 64),
            ("part_number", 3),
        ):
            candidate = copy.deepcopy(self.snapshot)
            candidate["subjects"]["reading"][1]["items"][0]["mapping"][field] = value
            path, digest = self.stage(candidate)
            with self.subTest(field=field), self.assertRaises(ValueError):
                activate(self.root, path, digest)
            self.assertEqual(self.current.read_bytes(), self.old)

    def test_incomplete_or_closed_source_mapping_cannot_activate(self):
        candidate = copy.deepcopy(self.snapshot)
        candidate["subjects"]["reading"][0]["items"].pop()
        with self.assertRaises(ValueError):
            validate_candidate(self.root, candidate, self.state)
        candidate = copy.deepcopy(self.snapshot)
        candidate["subjects"]["reading"][1]["items"][0]["source_available"] = False
        with self.assertRaises(ValueError):
            validate_candidate(self.root, candidate, self.state)

    def test_snapshot_hash_location_symlink_and_dry_run(self):
        path, digest = self.stage()
        with self.assertRaises(ValueError):
            activate(self.root, path, "0" * 64)
        wrong = self.state / f"{digest}.json"
        wrong.write_bytes(path.read_bytes())
        with self.assertRaises(ValueError):
            activate(self.root, wrong, digest)
        result = activate(self.root, path, digest, dry_run=True)
        self.assertFalse(result["activated"])
        self.assertFalse((self.state / ".sync.lock").exists())
        self.assertEqual(self.current.read_bytes(), self.old)
        path.unlink()
        path.symlink_to(wrong)
        with self.assertRaises(ValueError):
            activate(self.root, path, digest)

    def test_legacy_mapping_must_equal_current_repository_mapping(self):
        legacy = self.root / "static/listening_jijing"
        (legacy / "parts").mkdir(parents=True)
        (legacy / "audio").mkdir()
        (legacy / "audio/sample.mp3").write_bytes(b"existing legacy fixture")
        payload = {"id": "legacy_p1", "audio": {"local_path": "audio/sample.mp3"}}
        target = legacy / "parts/legacy_p1.json"
        target.write_text(json.dumps(payload))
        row = self.snapshot["subjects"]["listening"][0]["items"][0]
        mapping = {
            "subject": "listening",
            "source_id": row["source_id"],
            "source_part_id": "123",
            "source_title": row["title"],
            "source_content_sha256": "a" * 64,
            "target_id": "legacy_p1",
            "target_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        }
        row.update(
            {
                "source_available": True,
                "source_part_id": "123",
                "mapping": mapping,
                "unavailable_reason": "",
            }
        )
        self.mapping_file.write_text(json.dumps({"schema_version": 1, "mappings": [mapping]}))
        self.assertEqual(
            validate_candidate(self.root, self.snapshot, self.state)["reviewed_legacy"], 1
        )
        self.mapping_file.write_text('{"schema_version":1,"mappings":[]}')
        with self.assertRaisesRegex(ValueError, "current code release"):
            validate_candidate(self.root, self.snapshot, self.state)

    def test_active_sync_lock_prevents_replacement(self):
        path, digest = self.stage()
        with (self.state / ".sync.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                activate(self.root, path, digest)
        self.assertEqual(self.current.read_bytes(), self.old)

    def test_remote_destination_preparation_rejects_symlinks(self):
        folder = self.state / "assets"
        backup = self.state / "saved-assets"
        folder.rename(backup)
        folder.symlink_to(backup, target_is_directory=True)
        with self.assertRaises(ValueError):
            prepare_public_directories(self.root)


if __name__ == "__main__":
    unittest.main()
