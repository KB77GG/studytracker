"""Render the actual staff mock template with public synthetic data, without DB."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, render_template


def main():
    report = Path(__file__).resolve().parent
    repo = report.parents[2]
    app = Flask(__name__, template_folder=str(repo / "templates"))
    app.secret_key = "offline-synthetic-visual-fixture"
    app.jinja_env.globals["url_for"] = lambda endpoint, **kw: (
        "/static/" + kw["filename"] if endpoint == "static" else "/" + endpoint
    )
    catalogs = {}
    for subject, parts in (("listening", 4), ("reading", 3)):
        groups = []
        for part in range(1, parts + 1):
            items = []
            for rank in range(1, 21):
                count = 10 if subject == "listening" else (14 if rank == 1 else 13)
                items.append({
                    "selection_id": f"synthetic-{subject}-{part}-{rank}",
                    "rank": rank,
                    "title": f"Synthetic {subject} topic {part}: public transport in modern cities",
                    "question_count": count,
                })
            groups.append({"part": part, "items": items})
        catalogs[subject] = {
            "groups": groups, "updated_at_label": "2026-11-26 20:27", "stale": False,
        }
    with app.test_request_context("/admin/mock-exams/create"):
        rendered = render_template(
            "admin/mock_exams_form.html",
            current_user=SimpleNamespace(
                is_authenticated=True, role="admin", username="Synthetic QA", display_name="验收",
            ),
            exam=None, sprint_catalogs=catalogs, suggested_pincode="QA123",
            listening_options=[{"id": "synthetic-old-listening", "label": "Synthetic Cambridge Listening Test", "question_count": 40}],
            reading_options=[{"id": "synthetic-old-reading", "label": "Synthetic Cambridge Reading Test", "question_count": 40}],
            writing_options=[],
        )
    rendered = "\n".join(line.rstrip() for line in rendered.splitlines()) + "\n"
    (report / "mock-form-fixture.html").write_text(rendered, encoding="utf-8")
    paths = [
        "templates/base.html", "templates/admin/mock_exams_form.html",
        "templates/admin/_mock_sprint_picker.html", "static/js/mock_sprint_picker.js",
        "static/style.css", "static/admin_suite_v2.css",
    ]
    manifest = {
        "scope": "Real Flask-rendered staff mock template, CSS and first-party JS; synthetic catalog only; no app import, database, server, network or form submission.",
        "synthetic_catalog": {"listening_groups": 4, "reading_groups": 3, "items_per_group": 20},
        "source_sha256": {path: hashlib.sha256((repo / path).read_bytes()).hexdigest() for path in paths},
        "third_party_js": "Planned browser interception only; this renderer does not launch a browser or observe browser requests or screenshots.",
        "status": "fixture_only_browser_not_executed",
    }
    (report / "mock-visual-fixture.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print("Rendered mock-form-fixture.html with 7 synthetic catalog groups; no database opened.")


if __name__ == "__main__":
    main()
