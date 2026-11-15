"""Immutable runtime content and actual app loader shims, without importing app."""

import ast
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename

from practice_tables import normalize_practice_tables
from services.exam_sprint_store import (
    SprintStoreError,
    content_directory,
    load_mapping_target,
    load_ninefen_document,
    resolve_listening_part_path,
    resolve_ninefen_document_path,
    save_converted_documents,
)
from services.ielts_practice_scoring import grade_listening_jijing_answers
from tests.test_ninefen_content import convert, paper


class SprintStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop("EXAM_SPRINT_STATE_DIR", None)

    def install(self, subject="reading"):
        raw, answers = paper(subject)
        converted = convert(raw, answers)
        row = save_converted_documents(self.root, converted)[0]
        path = content_directory(self.root) / row["relative_path"]
        return converted, row, path

    def app_function(self, name, **context):
        """Execute only the changed real function; no app init, DB or TTS imports."""
        path = Path(__file__).resolve().parents[1] / "app.py"
        tree = ast.parse(path.read_text())
        function = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name
        )
        function.decorator_list = []
        module = ast.Module(body=[function], type_ignores=[])
        namespace = {
            "Path": Path,
            "json": json,
            "app": SimpleNamespace(root_path=str(self.root)),
            "secure_filename": secure_filename,
            "normalize_practice_tables": normalize_practice_tables,
            "resolve_ninefen_document_path": resolve_ninefen_document_path,
            "resolve_listening_part_path": resolve_listening_part_path,
            **context,
        }
        exec(compile(module, str(path), "exec"), namespace)
        return namespace[name]

    def test_round_trip_metadata_and_current_mapping(self):
        for subject in ("reading", "listening"):
            with self.subTest(subject=subject):
                converted, row, path = self.install(subject)
                payload = converted["documents"][0]["payload"]
                self.assertEqual(
                    load_ninefen_document(self.root, subject, row["target_id"]), payload
                )
                self.assertEqual(
                    resolve_ninefen_document_path(self.root, subject, row["target_id"]), path
                )
                self.assertEqual(load_mapping_target(self.root, row), (payload, path))
                self.assertEqual(
                    row["target_sha256"], hashlib.sha256(path.read_bytes()).hexdigest()
                )
                self.assertEqual(row["source_title"], payload["source_version_title"])
                self.assertEqual(row["part_number"], 2)
                self.assertEqual(row["passage"], 1 if subject == "reading" else None)

    def test_repeat_is_identical_and_old_version_remains_loadable(self):
        converted, row, path = self.install()
        before = path.stat().st_mtime_ns
        self.assertEqual(save_converted_documents(self.root, converted)[0], row)
        self.assertEqual(path.stat().st_mtime_ns, before)
        raw, answers = paper()
        raw["data"]["title"] += " new revision"
        new = save_converted_documents(self.root, convert(raw, answers))[0]
        self.assertNotEqual(new["target_id"], row["target_id"])
        self.assertIsNotNone(load_mapping_target(self.root, new))
        self.assertIsNotNone(load_mapping_target(self.root, row))

    def test_answer_edit_cannot_replace_existing_source_version(self):
        converted, row, path = self.install()
        before = path.read_bytes()
        converted["documents"][0]["payload"]["passages"][0]["groups"][0]["questions"][0][
            "answer"
        ] = "different"
        with self.assertRaisesRegex(SprintStoreError, "Immutable"):
            save_converted_documents(self.root, converted)
        self.assertEqual(path.read_bytes(), before)
        self.assertIsNotNone(load_mapping_target(self.root, row))

    def test_byte_tampering_missing_or_changed_receipt_disables_content(self):
        _converted, row, path = self.install()
        original = path.read_bytes()
        path.write_bytes(original + b" ")
        self.assertIsNone(load_mapping_target(self.root, row))
        self.assertIsNone(resolve_ninefen_document_path(self.root, "reading", row["target_id"]))
        path.write_bytes(original)
        receipt = path.with_suffix(".meta.json")
        original_receipt = receipt.read_bytes()
        receipt.unlink()
        self.assertIsNone(load_ninefen_document(self.root, "reading", row["target_id"]))
        data = json.loads(original_receipt)
        data["source_id"] = "999"
        receipt.write_text(json.dumps(data))
        self.assertIsNone(load_ninefen_document(self.root, "reading", row["target_id"]))

    def test_every_mapping_identity_is_checked(self):
        _converted, row, _path = self.install()
        changes = {
            "target_kind": "idictation",
            "target_id": row["target_id"] + "_p1",
            "subject": "listening",
            "source_id": "999",
            "source_content_sha256": "b" * 64,
            "target_sha256": "c" * 64,
            "source_title": "Different title",
            "source_part_id": "999",
            "passage": 2,
        }
        for key, value in changes.items():
            with self.subTest(key=key):
                self.assertIsNone(load_mapping_target(self.root, {**row, key: value}))
        self.assertIsNone(load_mapping_target(self.root, {**row, "passage": True}))
        self.assertIsNone(load_mapping_target(self.root, {**row, "source_id": None}))
        self.assertIsNone(load_mapping_target(self.root, {**row, "source_part_id": None}))
        self.assertIsNone(load_mapping_target(self.root, {**row, "part_number": 1}))
        self.assertIsNone(
            load_ninefen_document(self.root, "reading", row["target_id"], expected_sha256="bad")
        )

    def test_source_identity_and_version_must_agree_before_writes(self):
        raw, answers = paper()
        converted = convert(raw, answers)
        for key, value in (
            ("id", "ninefen_999_000000000000"),
            ("source", "idictation"),
            ("source_id", "999"),
            ("source_content_sha256", "0" * 64),
        ):
            with self.subTest(key=key):
                changed = copy.deepcopy(converted)
                changed["documents"][0]["payload"][key] = value
                with self.assertRaises(SprintStoreError):
                    save_converted_documents(self.root, changed)
        self.assertFalse(content_directory(self.root).exists())

    def test_untrusted_path_components_and_subjects_are_rejected(self):
        _converted, row, path = self.install()
        for value in (
            "../" + row["target_id"],
            row["target_id"] + ".json",
            " " + row["target_id"],
            row["target_id"].replace("ninefen_", "ninefen_../"),
            "/" + str(path),
            None,
        ):
            with self.subTest(value=value):
                self.assertIsNone(load_ninefen_document(self.root, "reading", value))
        self.assertIsNone(load_ninefen_document(self.root, "../reading", row["target_id"]))
        raw, answers = paper()
        converted = convert(raw, answers)
        converted["documents"][0]["relative_path"] = "../../outside.json"
        with self.assertRaises(SprintStoreError):
            save_converted_documents(self.root, converted)

    def test_symlink_files_receipts_and_directories_are_rejected(self):
        converted, row, path = self.install()
        for candidate in (path, path.with_suffix(".meta.json")):
            with self.subTest(path=candidate.name):
                moved = candidate.with_suffix(candidate.suffix + ".saved")
                candidate.rename(moved)
                candidate.symlink_to(moved)
                self.assertIsNone(load_mapping_target(self.root, row))
                with self.assertRaises(SprintStoreError):
                    save_converted_documents(self.root, converted)
                candidate.unlink()
                moved.rename(candidate)
        folder = path.parent
        moved = folder.with_name("outside-reading")
        folder.rename(moved)
        folder.symlink_to(moved, target_is_directory=True)
        self.assertIsNone(load_mapping_target(self.root, row))

    def test_configured_runtime_root_and_legacy_resolution(self):
        os.environ["EXAM_SPRINT_STATE_DIR"] = str(self.root / "custom-state")
        _converted, row, path = self.install("listening")
        self.assertEqual(path.parent.parent, self.root / "custom-state" / "content")
        legacy = self.root / "static" / "listening_jijing"
        self.assertEqual(resolve_listening_part_path(self.root, legacy, row["target_id"]), path)
        self.assertEqual(
            resolve_listening_part_path(self.root, legacy, "old_001_p1"),
            legacy / "parts" / "old_001_p1.json",
        )
        self.assertIsNone(resolve_listening_part_path(self.root, legacy, "../" + row["target_id"]))

    def test_actual_reading_loader_uses_verified_runtime_and_preserves_legacy(self):
        _converted, row, path = self.install()
        legacy = self.root / "legacy"
        legacy.mkdir()
        (legacy / "old.json").write_text('{"id": "old", "passages": []}')
        loader = self.app_function(
            "_load_reading_test_payload",
            _reading_test_root=lambda: legacy,
            _reading_jijing_root=lambda: self.root / "jijing",
        )
        payload, loaded_path, safe_id = loader(row["target_id"])
        self.assertEqual(
            (payload["id"], loaded_path, safe_id), (row["target_id"], path, row["target_id"])
        )
        self.assertEqual(loader("old")[0]["id"], "old")
        self.assertIsNone(loader("../" + row["target_id"])[0])
        path.write_bytes(path.read_bytes() + b" ")
        self.assertIsNone(loader(row["target_id"])[0])

    def test_actual_listening_get_and_guest_submit_share_verified_runtime(self):
        converted, row, path = self.install("listening")
        legacy = self.root / "legacy"
        get = self.app_function(
            "listening_jijing_part",
            _listening_jijing_root=lambda: legacy,
            render_template=lambda _name, **context: context,
        )
        self.assertEqual(get(row["target_id"])["part"]["source"], "ninefen")
        submit = self.app_function(
            "api_listening_jijing_submit",
            _listening_jijing_root=lambda: legacy,
            _grade_listening_jijing_answers=grade_listening_jijing_answers,
            _upsert_listening_jijing_self_task=lambda *_args: None,
            request=request,
            jsonify=jsonify,
        )
        payload = converted["documents"][0]["payload"]
        answers = {q["id"]: q["answer"] for g in payload["groups"] for q in g["items"]}
        test_app = Flask(__name__)
        with test_app.test_request_context(json={"answers": answers}):
            response = submit(row["target_id"]).get_json()
            self.assertFalse(response["synced"])
            self.assertEqual(response["result"]["correct"], 4)
            self.assertEqual(response["result"]["total"], 4)
        path.write_bytes(path.read_bytes() + b" ")
        self.assertEqual(get(row["target_id"])[1], 404)
        with test_app.test_request_context(json={"answers": answers}):
            self.assertEqual(submit(row["target_id"])[1], 404)


if __name__ == "__main__":
    unittest.main()
