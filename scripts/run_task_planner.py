#!/usr/bin/env python3
"""Model-only scheduler; never imports app.py or any speech/model runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask  # noqa: E402

from config import Config  # noqa: E402
from models import db  # noqa: E402
from models_task_planner import ensure_schema  # noqa: E402
from services.task_planner import run_due  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report eligible count without writes")
    parser.add_argument("--init-schema", action="store_true", help="Create missing task planner tables without altering existing tables")
    args = parser.parse_args()
    app = Flask("task_planner_runner")
    app.config.from_object(Config)
    db.init_app(app)
    with app.app_context():
        if args.init_schema:
            ensure_schema()
            print(json.dumps({"schema": "ready"}))
            return 0
        result = run_due(dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
