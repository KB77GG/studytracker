#!/usr/bin/env python3
"""Run actual practice routes in a loopback-only, anonymous memory-DB preview.

The real local snapshot, questions and media are used. Guest submissions execute
the real server grader and return synced=false; no learner is provisioned. The
database disappears when the preview process stops.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from config import Config  # noqa: E402

PREVIEW_SECRET = "exam-sprint-local-preview-only"
Config.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
Config.SECRET_KEY = PREVIEW_SECRET


def create_preview():
    existing = sys.modules.get("app")
    if (
        existing is not None
        and existing.app.config.get("SQLALCHEMY_DATABASE_URI") != "sqlite:///:memory:"
    ):
        raise RuntimeError("Preview refuses an existing non-memory application")
    from app import app
    from models import db

    app.config.update(
        SECRET_KEY=PREVIEW_SECRET,
        SESSION_COOKIE_NAME="exam_sprint_preview_session",
        SESSION_COOKIE_SECURE=False,
        TEMPLATES_AUTO_RELOAD=True,
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )
    with app.app_context():
        if str(db.engine.url) != "sqlite:///:memory:":
            raise RuntimeError("Preview refuses a non-memory database")
        db.create_all()
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5096)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    create_preview().run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
