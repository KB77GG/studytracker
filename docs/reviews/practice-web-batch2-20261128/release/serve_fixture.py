"""Local batch-2 navigation fixture; never use this script on production.

Reuse the batch-1 disposable SQLite/users/tasks fixture and the sprint route
unit-test view builder. Only the reading sprint view is synthetic: one visibly
labelled entry points to a real repository Cambridge reading route. This tests
navigation and existing templates/JS, not current rankings or sprint assets.
No tracked seed, runtime sprint state, database model, or product code changes.
"""

import argparse
import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

MARKER = "本机合成导航样例：仅验证导航，不代表真实热榜"
READING_PATH = "/reading/test/ielts10_test1_reading?passage=1"


def load_fixture_app(root, port):
    """Let the existing fixture build only its temporary DB; delay serving."""
    source = root / "docs/reviews/practice-web-batch1-20261126/serve_fixture.py"
    argv = [str(source), str(root), str(port)]
    with patch.object(sys, "argv", argv), patch("flask.Flask.run") as run:
        namespace = runpy.run_path(str(source), run_name="__main__")
    run.assert_called_once()
    return namespace["app"]


def make_sprint_loader():
    from services.exam_sprint import load_sprint_view as real_loader
    from tests.test_exam_sprint_routes import sprint_view

    def navigation_fixture(root, subject, **kwargs):
        if subject != "reading":
            return real_loader(root, subject, **kwargs)
        view = sprint_view("reading")
        entry = view["groups"][0]["items"][0]
        entry.update(
            source_id="local-navigation-fixture",
            title="LOCAL NAVIGATION FIXTURE · Cambridge 10 Test 1",
            title_zh=MARKER,
            heat_label="真实剑雅阅读页；合成冲刺来源",
            practice_url=READING_PATH,
        )
        view["groups"][0]["items"] = [entry]
        view.update(
            total=1,
            ready_count=1,
            updated_at_label="本机临时测试",
            source_updated_at_label="合成导航样例",
            next_update_label="",
        )
        return view

    return navigation_fixture


def self_test(app):
    """Read-only local GETs; no browser, server, credentials, or network."""
    client = app.test_client()
    sprint = client.get("/practice/sprint/reading")
    html = sprint.get_data(as_text=True)
    target = client.get(READING_PATH)
    target_html = target.get_data(as_text=True)
    listening = client.get("/practice/sprint/listening")
    checks = {
        "synthetic_reading_catalog_status_200": sprint.status_code == 200,
        "visible_synthetic_navigation_marker": MARKER in html,
        "one_synthetic_practice_entry": html.count("data-practice-entry") == 1,
        "real_cambridge_reading_href": f'href="{READING_PATH}"' in html,
        "sprint_source_context": "sourceMode: 'exam_sprint'" in html,
        "real_reading_target_status_200": target.status_code == 200,
        "real_reading_target_shell": "practice_shell.js" in target_html,
        "listening_view_not_replaced": (
            listening.status_code == 200
            and MARKER not in listening.get_data(as_text=True)
        ),
    }
    print(json.dumps({"ok": all(checks.values()), "checks": checks}, indent=2))
    return 0 if all(checks.values()) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("port", type=int, nargs="?", default=5116)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / "app.py").is_file():
        parser.error("root must be a local StudyTracker checkout")
    if str(root).startswith("/root/apps/"):
        parser.error("production checkout is forbidden")
    if not 1024 <= args.port <= 65535:
        parser.error("port must be in the local unprivileged range")
    app = load_fixture_app(root, args.port)
    with patch("services.exam_sprint.load_sprint_view", side_effect=make_sprint_loader()):
        if args.self_test:
            return self_test(app)
        print("LOCAL_NAVIGATION_FIXTURE: synthetic reading sprint; not real rankings", flush=True)
        app.run(host="127.0.0.1", port=args.port, threaded=True, use_reloader=False, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
