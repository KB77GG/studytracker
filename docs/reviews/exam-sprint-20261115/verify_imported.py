"""Verify actual imported exercises with an ephemeral database and guest requests.

No source login/network calls, learner accounts, task creation, or real database
writes. Reads local mapping/content/media and writes only this review's evidence.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from config import Config  # noqa: E402

# Must precede app/model import. Do not move this into main after importing app.
Config.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


def canonical_answers(subject, payload, passage):
    """Use the controls' real answer keys, including one selection per shared mark."""
    answers = {}
    parts = payload["passages"] if subject == "reading" else [payload]
    if subject == "reading" and passage:
        parts = [parts[passage - 1]]
    expected_count = 0
    for part in parts:
        for group in part["groups"]:
            questions = group["questions" if subject == "reading" else "items"]
            expected_count += len(questions)
            shared = []
            if len(questions) > 1:
                first = str(questions[0].get("answer") or "")
                candidates = [value.strip() for value in first.split(",")]
                if (
                    len(candidates) == len(questions)
                    and all(re.fullmatch(r"[A-Z]", value) for value in candidates)
                    and all(q.get("answer") == first for q in questions)
                ):
                    shared = candidates
            if subject == "listening" and str(group.get("type")) == "2" and shared:
                answers[group.get("desc") or group.get("question_title")] = ",".join(shared)
                continue
            for index, question in enumerate(questions):
                key = str(question["id"] if subject == "reading" else question["number"])
                answer = str(question.get("answer") or "")
                assert answer, f"Missing canonical answer: {payload['id']} / {key}"
                answers[key] = (
                    shared[index] if subject == "reading" and shared else answer.split("/")[0]
                )
    return answers, expected_count


def embedded_payload(response, subject):
    name = "rawTestData" if subject == "reading" else "part"
    match = re.search(rf"^const {name} = (.+);$", response.get_data(as_text=True), flags=re.M)
    assert match, f"Missing serialized {subject} practice data"
    return json.loads(match[1])


def media_urls(subject, payload):
    urls = set()
    if subject == "listening":
        local = payload["audio"]["local_path"]
        urls.add(local if local.startswith("/") else f"/static/listening_jijing/{local}")
    parts = payload["passages"] if subject == "reading" else [payload]
    for part in parts:
        for group in part["groups"]:
            if group.get("img_local"):
                urls.add(f"/static/{group['img_local']}")
            elif group.get("img_url"):
                urls.add(group["img_url"])
        for figure in (part.get("content") or {}).get("images", []) if subject == "reading" else []:
            value = figure["url"]
            urls.add(value if value.startswith("/") else f"/static/{value}")
    return sorted(urls)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimum-mapped", type=int, default=140)
    args = parser.parse_args()
    from app import app
    from models import (
        ListeningTestSubmission,
        ReadingTestSubmission,
        StudentProfile,
        Task,
        User,
        db,
    )
    from services.exam_sprint import _load_snapshot, _local_target, load_sprint_view

    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    models = (User, StudentProfile, Task, ReadingTestSubmission, ListeningTestSubmission)
    with app.app_context():
        assert str(db.engine.url) == "sqlite:///:memory:", "Refusing a non-ephemeral database"
        db.create_all()
        before = {model.__name__: model.query.count() for model in models}
    client = app.test_client()
    checks, rendered, assets = [], [], {}
    snapshot = _load_snapshot(ROOT)
    assert snapshot is not None, "A valid current sprint snapshot is required"
    mappings = [
        row["mapping"]
        for groups in snapshot["subjects"].values()
        for group in groups
        for row in group["items"]
        if row.get("mapping")
    ]
    assert len(mappings) >= args.minimum_mapped, f"Only {len(mappings)} mappings available"
    for row in mappings:
        resolved = _local_target(ROOT, row)
        assert resolved is not None, f"Unavailable mapping {row['subject']} / {row['source_id']}"
        stored, url = resolved
        subject, target = row["subject"], row["target_id"]
        response = client.get(url)
        assert response.status_code == 200, f"GET {url}: {response.status_code}"
        payload = embedded_payload(response, subject)
        assert payload["id"] == stored["id"] == target
        if row.get("target_kind") == "ninefen":
            assert payload["source"] == "ninefen"
            assert payload["source_id"] == row["source_id"]
            assert payload["source_content_sha256"] == row["source_content_sha256"]
        for media_url in media_urls(subject, payload):
            assert media_url.startswith("/") and not media_url.startswith(
                "//"
            ), f"Nonlocal media: {target}"
            if media_url not in assets:
                head = client.head(media_url)
                assert head.status_code == 200, f"HEAD {media_url}: {head.status_code}"
                assert head.content_length and head.content_length > 0
                expected_type = "audio/" if media_url.endswith(".mp3") else "image/"
                assert head.content_type.startswith(expected_type), f"Wrong media type: {media_url}"
                assets[media_url] = {
                    "status": head.status_code,
                    "bytes": head.content_length,
                    "content_type": head.content_type,
                }
        answers, total = canonical_answers(subject, payload, row.get("passage"))
        endpoint = (
            f"/api/reading/test/{target}/submit"
            if subject == "reading"
            else f"/api/listening/jijing/{target}/submit"
        )
        submission = client.post(
            endpoint, json={"answers": answers, "passage_number": row.get("passage")}
        )
        assert submission.status_code == 200, f"POST {endpoint}: {submission.status_code}"
        result = submission.get_json()
        assert (
            result.get("ok") is True and result.get("synced") is False
        ), f"Unexpected saved submission: {target}"
        grade = result["result"]
        assert (
            grade["correct"] == grade["total"] == total
        ), f"Canonical scoring failed: {target}: {grade['correct']}/{grade['total']} expected {total}"
        checks.append(
            {
                "subject": subject,
                "source_id": row["source_id"],
                "target_id": target,
                "get": 200,
                "submit": 200,
                "correct": total,
                "total": total,
                "synced": False,
            }
        )
        rendered.append({"subject": subject, "payload": payload})
    renderer = subprocess.run(
        ["node", str(Path(__file__).with_name("verify_imported_render.js"))],
        input=json.dumps(rendered),
        text=True,
        capture_output=True,
        check=False,
    )
    assert renderer.returncode == 0, renderer.stderr
    renderer_evidence = json.loads(renderer.stdout)
    readiness = {}
    for subject in ("reading", "listening"):
        view = load_sprint_view(ROOT, subject)
        assert client.get(f"/practice/sprint/{subject}").status_code == 200
        readiness[subject] = {"total": view["total"], "ready": view["ready_count"]}
    assert sum(row["ready"] for row in readiness.values()) >= args.minimum_mapped
    with app.app_context():
        after = {model.__name__: model.query.count() for model in models}
    assert before == after, "Guest acceptance must not create learner or submission records"
    evidence = {
        "captured_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 (Python 3.10)
        "passed": True,
        "database": "ephemeral SQLite memory only",
        "row_counts_unchanged": before == after,
        "mapped_practices": len(checks),
        "questions": sum(row["total"] for row in checks),
        "readiness": readiness,
        "renderer": renderer_evidence,
        "assets": assets,
        "practices": checks,
    }
    evidence["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    Path(__file__).with_name("imported-acceptance.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                key: evidence[key]
                for key in ("passed", "mapped_practices", "questions", "readiness", "renderer")
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
