#!/usr/bin/env python3
"""One-off offline visual audit: real templates/CSS, synthetic data, no app/DB.

Run with the main worktree's .venv Python. Browser requests are fulfilled from
local files; business scripts are removed and the original base drawer script
is retained. This checks rendering and sidebar interactions, not task APIs.
"""
import argparse
import datetime
import json
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

from jinja2 import ChainableUndefined, DictLoader, Environment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--baseline", default="e9d1069a")
    args = parser.parse_args()
    repo = args.repo.resolve()
    report = Path(__file__).resolve().parent
    site = report / "site"
    context = dict(
        current_user=SimpleNamespace(is_authenticated=True, role="admin", username="QA", display_name="验收"),
        config={"VOCABULARY_ERROR_REVIEW_ENABLED": True},
        get_flashed_messages=lambda: [],
        stats={"total": 1, "completed": 0, "total_minutes": 0, "avg_accuracy": 0},
        task_filters={"query": "", "student": "", "category": "", "status": "", "due_date": ""},
        period="week", period_urls={"week": "#", "month": "#", "year": "#"},
        task_page={"total": 1, "start": 1, "end": 1, "page": 1, "pages": [], "page_sizes": [], "page_size": 10},
        start_date=datetime.date(2026, 11, 16), today_obj=datetime.date(2026, 11, 22),
        today="2026-11-22", previous_day="2026-11-21",
        items=[dict(id="QA-1", student_name="示例学员", category="雅思-阅读-整套", detail="Cambridge IELTS 12 Test 5 Reading Passage 2", note="布局验收示例任务", date="2026-11-22", status="pending", completion_rate=0, progress=0, planned_minutes=20, actual_minutes=0, accuracy=0)],
        recent_tasks=[], top_students=[], all_students=[], pending_reviews=[],
    )
    def url_for(endpoint, **kwargs):
        return "/static/" + kwargs["filename"] if endpoint == "static" else "/" + endpoint
    context["url_for"] = url_for
    manifest = {"baseline": args.baseline, "scope": "Real full base/tasks/materials templates and CSS, one synthetic task, business JS removed; original sidebar drawer JS retained; no DB, app import, API or external browser requests."}
    for variant in ("baseline", "current"):
        def source(path, binary=False):
            if variant == "baseline":
                data = subprocess.check_output(["git", "show", f"{args.baseline}:{path}"], cwd=repo)
            else:
                data = (repo / path).read_bytes()
            return data if binary else data.decode()
        templates = {}
        for name in ("base.html", "tasks.html", "materials.html", "_icp_footer.html"):
            text = source("templates/" + name)
            text = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", lambda m: m.group() if name == "base.html" and "// Mobile sidebar drawer" in m.group() else "", text, flags=re.I)
            templates[name] = text
        env = Environment(loader=DictLoader(templates), undefined=ChainableUndefined, autoescape=True)
        output = site / variant
        output.mkdir(parents=True, exist_ok=True)
        for page, template, endpoint in (("tasks", "tasks.html", "tasks_page"), ("materials", "materials.html", "materials_list")):
            rendered = env.get_template(template).render(**context, request=SimpleNamespace(endpoint=endpoint, path="/"+page))
            rendered = rendered.replace("https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/css/bootstrap.min.css", "/vendor/bootstrap.min.css")
            rendered = rendered.replace("https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css", "/vendor/fontawesome.min.css")
            (output / (page + ".html")).write_text(rendered)
        for path in ("static/style.css", "static/admin_suite_v2.css", "static/tasks_workspace.css", "static/tasks_workspace_final.css", "static/brand/sagepath-mark.png", "static/brand/tasks-header-wave.png"):
            dest = output / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(source(path, binary=True))
    (report / "fixture-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    subprocess.run(["node", str(report / "visual_check.cjs")], cwd=repo, check=True)


if __name__ == "__main__":
    main()
