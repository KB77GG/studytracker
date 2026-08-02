import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ConfigSecurityTest(unittest.TestCase):
    def _config_probe(self, secure_value: str | None) -> str:
        env = os.environ.copy()
        env["SECRET_KEY"] = "test-only-config-key"
        if secure_value is None:
            env.pop("SESSION_COOKIE_SECURE", None)
        else:
            env["SESSION_COOKIE_SECURE"] = secure_value
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from config import Config; "
                    "print(Config.SECRET_KEY == 'test-only-config-key', "
                    "Config.SESSION_COOKIE_HTTPONLY, "
                    "Config.SESSION_COOKIE_SAMESITE, "
                    "Config.SESSION_COOKIE_SECURE)"
                ),
            ],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def test_secret_key_and_session_cookie_security_settings(self):
        self.assertEqual(self._config_probe("1"), "True True Lax True")
        self.assertEqual(self._config_probe("0"), "True True Lax False")
        self.assertEqual(self._config_probe(None), "True True Lax False")


if __name__ == "__main__":
    unittest.main()
