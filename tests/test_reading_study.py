"""Tests for the Reading Study backend (Phase A).

Four groups per docs/reading_study_phase1_implementation_plan.md §4.5:
  1. glossary role normalization (exact / flavor / fallback)
  2. import script (insert / skip / update / bad-file tolerance)
  3. read-only API (catalog / passage 404+200 / glossary)
  4. saved expressions (401 / save / dedupe / list / delete)

Run standalone:
    .venv/bin/python -m unittest tests.test_reading_study -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
for _path in (str(ROOT), str(SCRIPTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import import_reading_study  # noqa: E402  (scripts/import_reading_study.py)
from flask import Flask  # noqa: E402
from flask_login import LoginManager  # noqa: E402

from api.reading_study import reading_study_bp  # noqa: E402
from api.reading_study_glossary import (  # noqa: E402
    CONCEPTS,
    glossary_payload,
    resolve_role,
)
from models import (  # noqa: E402
    ReadingPassageAnalysis,
    StudentProfile,
    StudentSavedExpression,
    User,
    db,
)

# --------------------------------------------------------------------------- #
# Mini fixture: an internally consistent passage (sentences reproduce source).
# --------------------------------------------------------------------------- #
MINI_PASSAGE_ID = "mini_test_p1"
MINI_TEST_ID = "mini_test_reading"


def _mini_source_passages() -> dict[str, dict]:
    return {
        MINI_PASSAGE_ID: {
            "passage": {
                "id": MINI_PASSAGE_ID,
                "content": {
                    "title": "Mini Passage",
                    "paragraphs": [
                        {"label": "A", "text": "The cat sat. The dog ran."},
                    ],
                },
            },
            "source_kind": "reading_test",
            "test_id": MINI_TEST_ID,
            "source_path": Path("mini_test.json"),
        }
    }


def _mini_sample() -> dict:
    return {
        "schema_version": 1,
        "generation_standard": "reading_study_v1",
        "source_kind": "reading_test",
        "test_id": MINI_TEST_ID,
        "passage_id": MINI_PASSAGE_ID,
        "passage_title": "Mini Passage",
        "difficulty": "simple",
        "sentences": [
            {
                "id": "A-01",
                "paragraph_label": "A",
                "sentence_index": 1,
                "sentence": "The cat sat.",
                "translation": "猫坐着。",
                "structure": [
                    {"text": "The cat", "role": "subject", "level": 1},
                    {"text": "sat", "role": "verb_phrase", "level": 1},
                ],
                "difficult_points": ["主语是 The cat。", "sat 是过去式谓语。"],
                "expressions": [{"text": "sat", "meaning_zh": "坐"}],
            },
            {
                "id": "A-02",
                "paragraph_label": "A",
                "sentence_index": 2,
                "sentence": "The dog ran.",
                "translation": "狗跑了。",
                "structure": [
                    {"text": "The dog", "role": "subject", "level": 1},
                    {"text": "ran", "role": "verb_phrase", "level": 1},
                ],
                "difficult_points": ["主语是 The dog。", "ran 是过去式谓语。"],
                "expressions": [],
            },
        ],
    }


# --------------------------------------------------------------------------- #
# 1. Glossary
# --------------------------------------------------------------------------- #
class GlossaryTest(unittest.TestCase):
    def test_exact_mappings(self):
        self.assertEqual(resolve_role("subject")["concept"], "subject")
        self.assertEqual(resolve_role("relative_clause")["concept"], "relative_clause")
        self.assertEqual(resolve_role("passive_verb")["concept"], "passive_predicate")
        # array-form EXACT entry carries zh/en overrides but keeps base concept
        subject_clause = resolve_role("subject_clause")
        self.assertEqual(subject_clause["concept"], "noun_clause")
        self.assertEqual(subject_clause["zh"], "主语从句")
        self.assertEqual(subject_clause["en"], "Subject Clause")

    def test_flavor_combination(self):
        purpose = resolve_role("purpose_clause")
        self.assertEqual(purpose["concept"], "adverbial_clause")
        self.assertEqual(purpose["zh"], "目的状语从句")
        self.assertEqual(purpose["en"], "Purpose Clause")
        self.assertEqual(purpose["camp"], "adv")
        time_adv = resolve_role("time_adverbial")
        self.assertEqual(time_adv["concept"], "adverbial")
        self.assertEqual(time_adv["zh"], "时间状语")

    def test_attribution_roles_are_not_generic_grammar_fallbacks(self):
        speaker = resolve_role("speaker_attribution")
        self.assertEqual(speaker["concept"], "attribution")
        self.assertEqual(speaker["zh"], "引语署名")
        self.assertEqual(speaker["en"], "Speaker Attribution")

        expected_labels = {
            "attribution_phrase": "来源短语",
            "attribution_adverbial": "来源状语",
            "attribution_clause": "来源说明从句",
        }
        for role, expected_zh in expected_labels.items():
            with self.subTest(role=role):
                resolved = resolve_role(role)
                self.assertEqual(resolved["concept"], "attribution")
                self.assertEqual(resolved["zh"], expected_zh)
                self.assertNotEqual(resolved["zh"], "语法成分")

        concept = glossary_payload()["concepts"]["attribution"]
        self.assertIn("不属于被引内容本身", concept["desc"])

    def test_unknown_fallback_is_renderable(self):
        out = resolve_role("totally_made_up_role_xyz")
        self.assertEqual(out["zh"], "语法成分")
        self.assertEqual(out["camp"], "structure")
        # fallback concept MUST exist in the glossary so the UI never dead-clicks
        payload = glossary_payload()
        self.assertIn(out["concept"], payload["concepts"])

    def test_glossary_payload_covers_every_resolved_concept(self):
        payload = glossary_payload()
        self.assertEqual(set(payload["camps"]), {"noun", "verb", "adj", "adv", "structure"})
        # closed concepts + 1 fallback
        self.assertEqual(len(payload["concepts"]), len(CONCEPTS) + 1)
        for role in ["subject", "object_clause", "purpose_clause", "weird_unknown_tag"]:
            self.assertIn(resolve_role(role)["concept"], payload["concepts"])


# --------------------------------------------------------------------------- #
# 2. Import script
# --------------------------------------------------------------------------- #
class ImportTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        self.data_dir = tmp / "data"
        self.data_dir.mkdir()
        self.sample_path = self.data_dir / f"{MINI_PASSAGE_ID}.json"
        self._write_sample(_mini_sample())

        self.app = import_reading_study.make_app(f"sqlite:///{tmp / 'test.db'}")
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)
        self.addCleanup(db.engine.dispose)
        self.addCleanup(db.session.remove)
        db.create_all()
        self.source_passages = _mini_source_passages()

    def _write_sample(self, sample: dict):
        self.sample_path.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")

    def _run(self, dry_run=False):
        return import_reading_study.run_import(
            self.data_dir, self.source_passages, dry_run=dry_run, verbose=False
        )

    def test_first_run_inserts_and_normalizes(self):
        summary = self._run()
        self.assertEqual(summary["created"], 1)
        row = ReadingPassageAnalysis.query.filter_by(passage_id=MINI_PASSAGE_ID).one()
        self.assertEqual(row.status, "ready")
        self.assertEqual(row.sentence_count, 2)
        self.assertEqual(row.test_id, MINI_TEST_ID)
        # structure items gained concept/label fields, original role preserved
        payload = json.loads(row.payload_json)
        first = payload["sentences"][0]["structure"][0]
        self.assertEqual(first["role"], "subject")
        self.assertEqual(first["concept"], "subject")
        self.assertEqual(first["label_zh"], "主语")
        self.assertEqual(first["label_en"], "Subject")

    def test_second_run_skips_unchanged(self):
        self._run()
        summary = self._run()
        self.assertEqual(summary["skipped"], 1)
        self.assertEqual(summary["created"], 0)
        self.assertEqual(summary["updated"], 0)

    def test_changed_payload_triggers_update(self):
        self._run()
        changed = _mini_sample()
        changed["sentences"][0]["translation"] = "猫坐下了。（改动）"
        self._write_sample(changed)
        summary = self._run()
        self.assertEqual(summary["updated"], 1)
        row = ReadingPassageAnalysis.query.filter_by(passage_id=MINI_PASSAGE_ID).one()
        self.assertIn("改动", row.payload_json)

    def test_bad_and_non_analysis_files_are_ignored_not_fatal(self):
        (self.data_dir / "broken.json").write_text("{not valid json", encoding="utf-8")
        (self.data_dir / "other.json").write_text(json.dumps({"hello": "world"}), encoding="utf-8")
        summary = self._run()
        self.assertEqual(summary["created"], 1)
        self.assertEqual(summary["ignored"], 2)
        self.assertEqual(summary["failed"], 0)

    def test_invalid_analysis_counts_as_failed(self):
        bad = _mini_sample()
        # break the source-reproduction invariant -> validation failure
        bad["sentences"][1]["sentence"] = "The dog jumped."
        self._write_sample(bad)
        summary = self._run()
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["created"], 0)
        self.assertEqual(ReadingPassageAnalysis.query.count(), 0)

    def test_dry_run_writes_nothing(self):
        summary = self._run(dry_run=True)
        self.assertEqual(summary["created"], 1)
        self.assertEqual(ReadingPassageAnalysis.query.count(), 0)


# --------------------------------------------------------------------------- #
# API test base (shared app / seeding)
# --------------------------------------------------------------------------- #
class _ApiTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        db_path = Path(self._tmp.name) / "api.db"

        app = Flask(__name__)
        app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret",
            SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(app)

        login_manager = LoginManager()
        login_manager.init_app(app)

        @login_manager.user_loader
        def load_user(user_id):  # pragma: no cover - anonymous in these tests
            return db.session.get(User, int(user_id))

        app.register_blueprint(reading_study_bp)
        self.app = app
        self.ctx = app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)
        self.addCleanup(db.engine.dispose)
        self.addCleanup(db.session.remove)
        db.create_all()
        self._seed()
        self.client = app.test_client()

    def _seed(self):
        self.student = StudentProfile(full_name="Mini Student")
        db.session.add(self.student)
        db.session.add(
            ReadingPassageAnalysis(
                passage_id=MINI_PASSAGE_ID,
                test_id=MINI_TEST_ID,
                source_kind="reading_test",
                passage_title="Mini Passage",
                difficulty="simple",
                content_hash="deadbeef",
                sentence_count=2,
                status="ready",
                payload_json=json.dumps(
                    {"passage_id": MINI_PASSAGE_ID, "sentences": []},
                    ensure_ascii=False,
                ),
            )
        )
        db.session.commit()

    def _login_student(self):
        with self.client.session_transaction() as sess:
            sess["practice_student_name"] = "Mini Student"


# --------------------------------------------------------------------------- #
# 3. Read-only API
# --------------------------------------------------------------------------- #
class ReadOnlyApiTest(_ApiTestBase):
    def test_catalog_by_test_id(self):
        resp = self.client.get(f"/api/reading-study/catalog?test_id={MINI_TEST_ID}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["test_id"], MINI_TEST_ID)
        self.assertEqual(len(data["passages"]), 1)
        self.assertEqual(data["passages"][0]["passage_id"], MINI_PASSAGE_ID)

    def test_catalog_unknown_test_id_is_empty(self):
        resp = self.client.get("/api/reading-study/catalog?test_id=nope")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["passages"], [])

    def test_catalog_all_grouped_by_source_kind(self):
        resp = self.client.get("/api/reading-study/catalog")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("reading_test", data["sources"])
        self.assertEqual(data["sources"]["reading_test"][0]["test_id"], MINI_TEST_ID)

    def test_passage_200_and_404(self):
        ok = self.client.get(f"/api/reading-study/passage/{MINI_PASSAGE_ID}")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.get_json()["passage_id"], MINI_PASSAGE_ID)
        missing = self.client.get("/api/reading-study/passage/does_not_exist")
        self.assertEqual(missing.status_code, 404)

    def test_glossary_endpoint(self):
        resp = self.client.get("/api/reading-study/glossary")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("concepts", data)
        self.assertIn("subject", data["concepts"])

    def test_page_route_404_without_ready_passages(self):
        resp = self.client.get("/reading/study/no_such_test")
        self.assertEqual(resp.status_code, 404)

    def test_page_route_falls_back_when_template_missing(self):
        resp = self.client.get(f"/reading/study/{MINI_TEST_ID}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["test_id"], MINI_TEST_ID)
        self.assertEqual(data["practice_url"], f"/reading/test/{MINI_TEST_ID}")


# --------------------------------------------------------------------------- #
# 4. Saved expressions
# --------------------------------------------------------------------------- #
class ExpressionApiTest(_ApiTestBase):
    def test_requires_student_identity(self):
        resp = self.client.post("/api/reading-study/expressions", json={"text": "take place"})
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json()["error"], "need_student")

    def test_list_without_student_returns_empty(self):
        resp = self.client.get("/api/reading-study/expressions")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsNone(data["student"])
        self.assertEqual(data["saved"], [])

    def test_save_dedupe_list_delete_roundtrip(self):
        self._login_student()
        payload = {
            "text": "Take Place",
            "meaning_zh": "发生",
            "passage_id": MINI_PASSAGE_ID,
            "sentence_id": "A-01",
            "source_kind": "reading_test",
        }
        first = self.client.post("/api/reading-study/expressions", json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.get_json()["saved"])

        # duplicate (different casing/spacing) must not create a second row
        dup = self.client.post("/api/reading-study/expressions", json={"text": "take   place"})
        self.assertEqual(dup.status_code, 200)
        self.assertEqual(
            StudentSavedExpression.query.filter_by(student_id=self.student.id).count(),
            1,
        )

        listed = self.client.get(
            f"/api/reading-study/expressions?passage_id={MINI_PASSAGE_ID}"
        ).get_json()
        self.assertEqual(listed["student"]["name"], "Mini Student")
        self.assertIn("take place", listed["saved"])

        deleted = self.client.delete("/api/reading-study/expressions", json={"text": "take place"})
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(deleted.get_json()["saved"])
        self.assertEqual(
            StudentSavedExpression.query.filter_by(student_id=self.student.id).count(),
            0,
        )

    def test_delete_requires_student(self):
        resp = self.client.delete("/api/reading-study/expressions", json={"text": "x"})
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
