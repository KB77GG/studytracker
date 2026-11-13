"""Run the e3901a0c prompt15 final recheck tests with fake settings and local-only sockets."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--repo",
    type=Path,
    default=Path("/private/tmp/studytracker-iwa-prompt15-final-recheck-20261113"),
)
parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
args = parser.parse_args()
REPO = args.repo.resolve()
OUTPUT = args.out.resolve()
OUTPUT.mkdir(parents=True, exist_ok=True)
env = {
    key: value
    for key, value in os.environ.items()
    if not key.startswith("IWA_")
    and key.lower() not in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}
    and key not in {"PYTHONPATH", "PYTHONSTARTUP"}
}
report = {
    "repo": str(REPO),
    "python": sys.version.split()[0],
    "source_head": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
    ).strip(),
    "commands": [],
}
with tempfile.TemporaryDirectory(prefix="iwa-realcheck-offline-") as temp:
    directory = Path(temp)
    guard = directory / "guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(
        """import ipaddress
import socket
import sys
def local_only(event, args):
    if event != "socket.connect":
        return
    sock, address = args
    if sock.family == socket.AF_UNIX:
        return
    host = address[0]
    try:
        allowed = ipaddress.ip_address(host).is_loopback
    except ValueError:
        allowed = host == "localhost"
    if not allowed:
        raise RuntimeError("Offline test guard blocked a non-loopback connection")
sys.addaudithook(local_only)
""",
        encoding="utf-8",
    )
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(guard),
        NO_PROXY="127.0.0.1,localhost",
        no_proxy="127.0.0.1,localhost",
        IWA_DATA_DIR=str(directory / "unused-trial-data"),
        IWA_ENV_FILE=str(directory / "absent.env"),
        IWA_LLM_PROVIDER="fake",
        IWA_VISION_PROVIDER="none",  # regression: CLI tests must isolate this override
        IWA_PORT="5055",
    )
    with (OUTPUT / "offline-tests.log").open("w", encoding="utf-8") as log:
        for command in (
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-v",
                "-s",
                "tools/ielts_writing_ai/tests",
                "-t",
                ".",
            ],
            ["node", "--test", "tools/ielts_writing_ai/tests/test_draft.js"],
        ):
            log.write("COMMAND: " + " ".join(command) + "\n")
            log.flush()
            started = time.monotonic()
            result = subprocess.run(
                command, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=300
            )
            record = {
                "command": command,
                "cwd": str(REPO),
                "returncode": result.returncode,
                "elapsed_seconds": round(time.monotonic() - started, 2),
            }
            report["commands"].append(record)
            log.write("\nRESULT: " + json.dumps(record) + "\n\n")
            log.flush()
    report["test_data_directory_untouched"] = not (directory / "unused-trial-data").exists()
report["source_status"] = subprocess.check_output(
    ["git", "status", "--short", "--branch"], cwd=REPO, text=True
)
(OUTPUT / "offline-tests.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(0 if all(row["returncode"] == 0 for row in report["commands"]) else 1)
