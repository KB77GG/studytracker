"""Reproducible local acceptance, isolated from production and student databases."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from config import Config  # noqa: E402

Config.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

MODULES = [
    "tests.test_exam_sprint",
    "tests.test_ninefen_source",
    "tests.test_exam_sprint_routes",
    "tests.test_exam_sprint_matching",
    "tests.test_ninefen_content",
    "tests.test_ninefen_assets",
    "tests.test_ninefen_session",
    "tests.test_exam_sprint_store",
    "tests.test_exam_sprint_import",
    "tests.test_exam_sprint_publish",
    "tests.test_exam_sprint_weekly",
    "tests.test_practice_catalog",
    "tests.test_practice_workspace_regression",
    "tests.test_listening_jijing_index_workspace",
    "tests.test_reading_jijing_index_workspace",
    "tests.test_practice_portal_catalog_grouping",
    "tests.test_jijing_scoring",
]


def main():
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromNames(MODULES)
    )
    if not result.wasSuccessful():
        return 1
    from app import app

    client = app.test_client()
    rows = json.loads((ROOT / "data/exam_sprint/mappings.json").read_text())["mappings"]
    checks = []
    for row in rows:
        target = row["target_id"]
        part = json.loads((ROOT / f"static/listening_jijing/parts/{target}.json").read_text())
        assert client.get(f"/listening/jijing/{target}").status_code == 200
        audio_path = part["audio"]["local_path"]
        assert client.head(f"/static/listening_jijing/{audio_path}").status_code == 200
        answers = {
            str(item["number"]): item["answer"].split("/")[0]
            for group in part["groups"]
            for item in group["items"]
        }
        response = client.post(f"/api/listening/jijing/{target}/submit", json={"answers": answers})
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["result"]["correct"] == payload["result"]["total"] == 10
        assert payload["synced"] is False  # Guest acceptance creates no learner record.
        checks.append({"target_id": target, "render_status": 200, "audio_head": 200, "correct": 10})
    for subject in ("reading", "listening"):
        assert client.get(f"/practice/sprint/{subject}").status_code == 200
    evidence = {"python_tests": result.testsRun, "passed": True, "real_guest_routes": checks}
    (Path(__file__).parent / "local-acceptance.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({"python_tests": result.testsRun, "guest_practices": len(checks), "ok": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
