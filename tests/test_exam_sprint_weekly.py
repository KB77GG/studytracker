"""Offline scheduling/install checks; no real sessions, network, or launchd calls."""

import contextlib
import hashlib
import io
import json
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from scripts import install_exam_sprint_launchd as installer
from scripts import run_exam_sprint_weekly as runner

ROOT = Path(__file__).resolve().parents[1]


class WeeklyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        (self.root / "scripts").mkdir()
        for name in ("sync_exam_sprint.py", "publish_exam_sprint.py"):
            (self.root / "scripts" / name).write_text("# test only\n")
        self.state_dir = self.root / "instance" / "exam_sprint"
        (self.state_dir / "private").mkdir(parents=True)
        (self.state_dir / "private" / "session.json").write_text("{}")
        (self.state_dir / "private" / "session.json").chmod(0o600)
        (self.state_dir / "current.json").write_text('{"snapshot":"synthetic"}')
        runner.write_private_json(
            self.root / "weekly-config.json",
            {
                "schema_version": 1,
                "enabled": True,
                "python": sys.executable,
                "host": "root@47.110.45.193",
                "remote_root": "/root/apps/studytracker",
            },
        )
        runner.write_private_json(
            self.root / "weekly-state.json",
            {
                "initialized_after_publish": True,
                "last_success_week": "2026-11-09",
                "attempts": {},
            },
        )
        self.tz = patch.object(runner, "system_timezone_is_shanghai", return_value=True)
        self.tz.start()
        self.addCleanup(self.tz.stop)
        self.log = contextlib.redirect_stdout(io.StringIO())
        self.log.__enter__()
        self.addCleanup(self.log.__exit__, None, None, None)
        self.now = datetime.fromisoformat("2026-11-16T06:00:00+08:00")

    def state(self):
        return runner.read_private_json(self.root / "weekly-state.json")

    def test_due_boundary_and_sleep_catchup(self):
        self.assertEqual(
            runner.due_week(datetime.fromisoformat("2026-11-16T05:59:59+08:00")), "2026-11-09"
        )
        self.assertEqual(runner.due_week(self.now), "2026-11-16")
        self.assertEqual(
            runner.due_week(datetime.fromisoformat("2026-11-19T18:00:00+08:00")), "2026-11-16"
        )

    @patch.object(runner, "_stage")
    def test_first_published_week_does_no_work(self, stage):
        state = self.state()
        state["last_success_week"] = "2026-11-16"
        runner.write_private_json(self.root / "weekly-state.json", state)
        self.assertEqual(runner.run_due(self.root, now=self.now), 0)
        stage.assert_not_called()

    @patch.object(runner, "_stage")
    def test_uninitialized_and_wrong_timezone_refuse(self, stage):
        state = self.state()
        state["initialized_after_publish"] = False
        runner.write_private_json(self.root / "weekly-state.json", state)
        self.assertEqual(runner.run_due(self.root, now=self.now), 2)
        with patch.object(runner, "system_timezone_is_shanghai", return_value=False):
            self.assertEqual(runner.run_due(self.root, now=self.now), 2)
        stage.assert_not_called()

    @patch.object(runner, "_stage", return_value=0)
    def test_only_publish_success_advances_week_and_rerun_is_read_only(self, stage):
        self.assertEqual(runner.run_due(self.root, now=self.now), 0)
        self.assertEqual(stage.call_count, 2)
        self.assertIn("--allow-new-attempts", stage.call_args_list[0].args[0])
        self.assertNotIn("--session-file", stage.call_args_list[1].args[0])
        self.assertEqual(self.state()["last_success_week"], "2026-11-16")
        self.assertEqual(runner.run_due(self.root, now=self.now), 0)
        self.assertEqual(stage.call_count, 2)

    @patch.object(runner, "_stage", return_value=1)
    def test_sync_failure_preserves_week_and_is_bounded(self, stage):
        for _ in range(3):
            self.assertEqual(runner.run_due(self.root, now=self.now), 1)
        self.assertEqual(runner.run_due(self.root, now=self.now), 2)
        self.assertEqual(stage.call_count, 3)
        self.assertEqual(self.state()["last_success_week"], "2026-11-09")

    @patch.object(runner, "_stage", side_effect=[0, 1, 0])
    def test_publish_retry_does_not_sync_or_submit_again(self, stage):
        self.assertEqual(runner.run_due(self.root, now=self.now), 1)
        self.assertEqual(self.state()["last_success_week"], "2026-11-09")
        self.assertEqual(runner.run_due(self.root, now=self.now), 0)
        self.assertEqual(stage.call_count, 3)
        self.assertIn("publish_exam_sprint.py", stage.call_args_list[2].args[0][1])

    @patch.object(runner, "_stage", side_effect=[0, 1])
    def test_changed_pending_candidate_is_never_published(self, stage):
        runner.run_due(self.root, now=self.now)
        (self.state_dir / "current.json").write_text("{}")
        with self.assertRaises(ValueError):
            runner.run_due(self.root, now=self.now)
        self.assertEqual(stage.call_count, 2)

    @patch.object(runner, "_stage")
    def test_check_only_does_no_work(self, stage):
        self.assertEqual(runner.run_due(self.root, now=self.now, check_only=True), 0)
        stage.assert_not_called()
        self.assertEqual(self.state()["attempts"], {})

    def test_private_controls_reject_symlink_and_mode(self):
        target = self.root / "weekly-config.json"
        target.chmod(0o644)
        with self.assertRaises(ValueError):
            runner.read_private_json(target)
        target.chmod(0o600)
        alias = self.root / "alias"
        alias.symlink_to(target)
        with self.assertRaises(OSError):
            runner.read_private_json(alias)

    @patch.object(installer, "install")
    def test_installer_defaults_to_plan(self, install):
        self.assertEqual(installer.main([]), 0)
        install.assert_not_called()

    def test_plist_and_repo_template_match(self):
        expected = installer.build_plist(Path("__RUNTIME_DIR__"), "__PYTHON__")
        actual = plistlib.loads(
            (ROOT / "deploy/exam-sprint/com.sagepath.studytracker-exam-sprint.plist").read_bytes()
        )
        self.assertEqual(expected, actual)
        self.assertEqual(expected["StartInterval"], 1800)
        self.assertEqual(expected["StartCalendarInterval"], {"Weekday": 1, "Hour": 6, "Minute": 0})
        self.assertTrue(expected["RunAtLoad"])

    def test_copy_tree_refuses_symlinks_and_keeps_private_mode(self):
        source = self.root / "source"
        source.mkdir()
        (source / "private").mkdir()
        (source / "private" / "session.json").write_text("{}")
        dest = self.root / "destination"
        installer._copy_tree(source, dest)
        self.assertEqual((dest / "private").stat().st_mode & 0o777, 0o700)
        self.assertEqual((dest / "private" / "session.json").stat().st_mode & 0o777, 0o600)
        (source / "alias").symlink_to(source / "private" / "session.json")
        with self.assertRaises(ValueError):
            installer._copy_tree(source, self.root / "other")


class RuntimeDependencyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.runtime = self.root / "runtime"
        self.state = self.root / "state"
        self.assets = self.root / "asset-source"
        for folder in (self.source, self.runtime, self.state, self.assets):
            folder.mkdir(mode=0o700)
        self.target_id = "synthetic_p1"
        self.folder = Path("static/listening_jijing")
        self.document = self.source / self.folder / "parts" / f"{self.target_id}.json"
        self.document.parent.mkdir(parents=True)
        self.document.write_text(
            json.dumps({"id": self.target_id, "audio": {"local_path": "audio/one.mp3"}})
        )
        (self.source / self.folder / "offline_tests.json").write_text('{"tests":[]}')
        audio = self.assets / self.folder / "audio"
        audio.mkdir(parents=True)
        (audio / "one.mp3").write_bytes(b"synthetic media bytes, not a playable asset")
        (audio / "unrelated.mp3").write_bytes(b"must not copy")
        self.mapping = {
            "subject": "listening",
            "source_id": "123",
            "target_id": self.target_id,
            "target_sha256": hashlib.sha256(self.document.read_bytes()).hexdigest(),
        }
        self._write_manifests()

    def _write_manifests(self, row_mapping=None):
        manifest = self.source / "data/exam_sprint/mappings.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"mappings": [self.mapping]}))
        (self.state / "current.json").write_text(
            json.dumps(
                {
                    "subjects": {
                        "listening": [
                            {
                                "items": [
                                    {"source_id": "123", "mapping": row_mapping or self.mapping}
                                ]
                            }
                        ]
                    }
                }
            )
        )

    def test_only_exact_reviewed_legacy_files_are_copied_privately(self):
        copied = installer._copy_legacy_dependencies(
            self.source, self.runtime, self.state, self.assets
        )
        self.assertEqual(copied, 3)
        paths = {
            p.relative_to(self.runtime).as_posix() for p in self.runtime.rglob("*") if p.is_file()
        }
        self.assertEqual(
            paths,
            {
                "static/listening_jijing/parts/synthetic_p1.json",
                "static/listening_jijing/audio/one.mp3",
                "static/listening_jijing/offline_tests.json",
            },
        )
        for path in self.runtime.rglob("*"):
            self.assertEqual(path.stat().st_mode & 0o777, 0o700 if path.is_dir() else 0o600)
        self.assertFalse((self.runtime / "instance").exists())

    def test_legacy_manifest_mismatch_or_changed_document_refuses_copy(self):
        bad = dict(self.mapping, target_id="different")
        self._write_manifests(bad)
        with self.assertRaises(ValueError):
            installer._copy_legacy_dependencies(self.source, self.runtime, self.state, self.assets)
        self._write_manifests()
        self.document.write_text('{"changed":true}')
        with self.assertRaises(ValueError):
            installer._copy_legacy_dependencies(self.source, self.runtime, self.state, self.assets)
        self.assertFalse(any(self.runtime.iterdir()))

    def test_legacy_audio_cannot_escape_explicit_asset_root(self):
        audio = self.assets / self.folder / "audio/one.mp3"
        audio.unlink()
        outside = self.root / "outside.mp3"
        outside.write_bytes(b"outside")
        audio.symlink_to(outside)
        with self.assertRaises(ValueError):
            installer._copy_legacy_dependencies(self.source, self.runtime, self.state, self.assets)
        self.assertFalse((self.runtime / self.folder / "audio/one.mp3").exists())

    def test_exact_code_copy_imports_without_original_tree_or_real_state(self):
        for relative in installer.CODE_FILES:
            installer._copy_file(ROOT / relative, self.runtime / relative)
        self.assertIn("scripts/activate_exam_sprint.py", installer.CODE_FILES)
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        environment.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
        for script in (
            "sync_exam_sprint.py",
            "publish_exam_sprint.py",
            "run_exam_sprint_weekly.py",
        ):
            result = subprocess.run(
                [sys.executable, str(self.runtime / "scripts" / script), "--help"],
                cwd=self.runtime,
                env=environment,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode()[:500])
        self.assertFalse((self.runtime / "instance").exists())

    def test_initial_private_root_and_session_must_be_owned_and_restricted(self):
        snapshot = {"schema_version": 1, "source": "ninefen", "subjects": {}}
        for subject, count in (("reading", 3), ("listening", 4)):
            snapshot["subjects"][subject] = [
                {
                    "part": part,
                    "items": [{"rank": rank, "source_available": False} for rank in range(1, 21)],
                }
                for part in range(1, count + 1)
            ]
        (self.state / "current.json").write_text(json.dumps(snapshot))
        private = self.state / "private"
        private.mkdir(mode=0o700)
        session = private / "session.json"
        session.write_text("{}")
        session.chmod(0o600)
        installer._validate_initial_snapshot(self.state)
        private.chmod(0o755)
        with self.assertRaises(ValueError):
            installer._validate_initial_snapshot(self.state)
        private.chmod(0o700)
        session.chmod(0o644)
        with self.assertRaises(ValueError):
            installer._validate_initial_snapshot(self.state)
        session.chmod(0o600)
        os.link(session, private / "hardlink.json")
        with self.assertRaises(ValueError):
            installer._validate_initial_snapshot(self.state)


if __name__ == "__main__":
    unittest.main()
