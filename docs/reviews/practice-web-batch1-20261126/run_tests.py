"""Run selected unittest modules with private SQLite/config and networking denied.

The real app is imported only after injecting config, so this runner never loads
the repository .env or its configured app.db. It does not alter product modules
or add interpreter compatibility aliases.
"""

import argparse
import importlib
import os
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modules", nargs="+", help="Fully qualified unittest modules")
    args = parser.parse_args()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    with tempfile.TemporaryDirectory(prefix="practice-batch1-tests-") as temporary, ExitStack() as stack:
        blocked = [
            stack.enter_context(patch(target, side_effect=AssertionError("Network forbidden in practice regression")))
            for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.getaddrinfo")
        ]
        config = types.ModuleType("config")
        config.Config = type("PrivatePracticeTestConfig", (), {
            "TESTING": True,
            "SECRET_KEY": "synthetic-practice-regression-only",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{temporary}/practice.db",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "UPLOAD_FOLDER": temporary,
            "SESSION_COOKIE_SECURE": False,
            "CLASSROOM_PASSCODE": "synthetic-practice-only",
        })
        sys.modules["config"] = config
        module = importlib.import_module("app")
        from models import db

        with module.app.app_context():
            assert Path(db.engine.url.database).is_relative_to(temporary)
            db.create_all()
        try:
            suite = unittest.defaultTestLoader.loadTestsFromNames(args.modules)
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            for mock in blocked:
                mock.assert_not_called()
            print("PRIVATE_CONFIG_OK: temporary SQLite, no .env/app.db, network calls=0")
            return 0 if result.wasSuccessful() else 1
        finally:
            with module.app.app_context():
                db.session.remove()
                db.engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())

