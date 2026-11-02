"""The trial tool must stay independent of the main StudyTracker application."""

import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from tools.ielts_writing_ai import __main__ as cli
from tools.ielts_writing_ai import create_app
from tools.ielts_writing_ai.config import ConfigError, load_settings

from .helpers import settings_for

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_DIR = REPO_ROOT / "tools" / "ielts_writing_ai"
MAIN_APP_MODULES = ("app", "models", "config", "api", "services", "toefl_practice")


class IsolationTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="iwa-iso-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def test_creating_the_app_never_imports_main_app_modules(self):
        script = (
            "import json, sys, tempfile\n"
            "from tools.ielts_writing_ai import create_app, load_settings\n"
            "d = tempfile.mkdtemp()\n"
            "create_app(load_settings(env={}, env_file='/nonexistent', data_dir=d, job_mode='inline'))\n"
            f"print(json.dumps([m for m in {MAIN_APP_MODULES!r} if m in sys.modules]))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(json.loads(result.stdout.strip().splitlines()[-1]), [])

    def test_source_has_no_imports_from_the_main_app(self):
        offenders = []
        for path in TOOL_DIR.rglob("*.py"):
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                for module in MAIN_APP_MODULES:
                    if stripped.startswith(
                        (f"import {module}", f"from {module} ", f"from {module}.")
                    ):
                        offenders.append(f"{path.name}: {stripped}")
        self.assertEqual(offenders, [])

    def test_refuses_main_database_names_and_ports(self):
        for name in ("app.db", "studytracker.db"):
            settings = settings_for(self.tmpdir, db_path=str(Path(self.tmpdir) / name))
            with self.assertRaises(ConfigError):
                settings.validate()
        for port in (5000, 5002):
            with self.assertRaises(ConfigError):
                settings_for(self.tmpdir, port=port).validate()

    def test_refuses_a_database_that_has_other_tables(self):
        foreign = Path(self.tmpdir) / "other.sqlite3"
        with sqlite3.connect(foreign) as conn:
            conn.execute("CREATE TABLE mock_exam_session (id INTEGER PRIMARY KEY)")
        with self.assertRaises(ConfigError):
            create_app(settings_for(self.tmpdir, db_path=str(foreign)))

    def test_real_provider_requires_its_own_key(self):
        with self.assertRaises(ConfigError):
            settings_for(self.tmpdir, llm_provider="deepseek").validate()
        settings_for(self.tmpdir, llm_provider="deepseek", llm_api_key="k").validate()

    def test_only_iwa_env_vars_are_read(self):
        env_file = Path(self.tmpdir) / ".env"
        env_file.write_text(
            'IWA_LLM_PROVIDER=qwen\nIWA_LLM_API_KEY="abc"\nIWA_DAILY_LIMIT=7\n', encoding="utf-8"
        )
        settings = load_settings(
            env={"DEEPSEEK_API_KEY": "main-app-key", "IWA_DAILY_LIMIT": "9"}, env_file=env_file
        )
        self.assertEqual(settings.llm_provider, "qwen")
        self.assertEqual(settings.llm_api_key, "abc")
        self.assertEqual(settings.daily_limit, 9)  # process env wins over the file
        self.assertNotIn("main-app-key", json.dumps(settings.public_summary()))
        self.assertTrue(settings.llm_base_url.startswith("https://dashscope"))

    def test_gunicorn_config_does_not_use_main_port(self):
        namespace = {"__file__": str(TOOL_DIR / "gunicorn.conf.py")}
        source = (TOOL_DIR / "gunicorn.conf.py").read_text(encoding="utf-8")
        exec(compile(source, "gunicorn.conf.py", "exec"), namespace)  # noqa: S102 - our own file
        self.assertTrue(namespace["bind"].endswith(":5055"), namespace["bind"])
        self.assertEqual(namespace["workers"], 1)
        self.assertEqual(namespace["wsgi_app"], "tools.ielts_writing_ai.wsgi:app")

    def test_cli_user_lifecycle(self):
        env_file = Path(self.tmpdir) / ".env"
        env_file.write_text(f"IWA_DATA_DIR={self.tmpdir}/data\n", encoding="utf-8")
        out = io.StringIO()
        # Drop any IWA_* variables from the caller's shell: they take precedence over the
        # env file and would point the CLI at a real data directory.
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("IWA_")}
        with mock.patch.dict(os.environ, clean_env, clear=True), redirect_stdout(out):
            self.assertEqual(
                cli.main(
                    ["--env-file", str(env_file), "user-add", "--name", "试用一", "--days", "7"]
                ),
                0,
            )
            self.assertEqual(cli.main(["--env-file", str(env_file), "user-list"]), 0)
            self.assertEqual(cli.main(["--env-file", str(env_file), "user-disable", "1"]), 0)
            self.assertEqual(cli.main(["--env-file", str(env_file), "user-reset-code", "1"]), 0)
            self.assertEqual(cli.main(["--env-file", str(env_file), "check"]), 0)
        text = out.getvalue()
        self.assertIn("试用码（只显示这一次", text)
        self.assertIn("试用一", text)
        self.assertTrue((Path(self.tmpdir) / "data" / "iwa.sqlite3").is_file())
        self.assertNotIn('api_key": "', text)


if __name__ == "__main__":
    unittest.main()
