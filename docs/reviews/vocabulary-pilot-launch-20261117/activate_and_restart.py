"""Explicit first-pilot rollout, after OFF verification/migration; no identity output."""

import argparse
import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path


def atomic_write(path, data, mode):
    owner = path.stat()
    fd, temporary = tempfile.mkstemp(prefix=".pilot-switch-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchown(stream.fileno(), owner.st_uid, owner.st_gid)
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def rollout(root, selection, expected_head):
    dotenv = root / ".env"
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        stderr=subprocess.DEVNULL,
        timeout=10,
    ).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=root,
        text=True,
        stderr=subprocess.DEVNULL,
        timeout=10,
    ).strip()
    if head != expected_head or dirty or dotenv.is_symlink() or not dotenv.is_file():
        raise ValueError("rollout_precondition_failed")
    original = dotenv.read_bytes()
    original.decode("utf-8")  # fail before stopping if config's loader cannot read it
    mode = stat.S_IMODE(dotenv.stat().st_mode)
    backup = selection.parent / "vocabulary-20261117.env-before"
    if backup.is_symlink():
        raise ValueError("unsafe_backup_path")
    if backup.exists():
        info = backup.stat()
        if (
            stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.geteuid()
            or backup.read_bytes() != original
        ):
            raise ValueError("prior_switch_backup_requires_review")
    else:
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
    written = False
    result = {"ok": False, "identities_exported": False}
    try:
        # Even a failed/timed-out stop can have stopped the service already.
        # Start is therefore guaranteed after every stop attempt.
        subprocess.run(
            ["systemctl", "stop", "studytracker"],
            check=True,
            capture_output=True,
            timeout=30,
        )
        enrolled = subprocess.run(
            [
                str(root / ".venv/bin/python"),
                "-B",
                "scripts/activate_vocabulary_pilot.py",
                "--database",
                str(root / "app.db"),
                "--selection",
                str(selection),
                "--apply",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=30,
        )
        details = json.loads(enrolled.stdout)
        if enrolled.returncode or details.get("ok") is not True:
            raise ValueError("enrollment_failed_service_restored_off")
        if dotenv.read_bytes() != original:
            raise ValueError("configuration_changed_during_rollout")
        retained = []
        for line in original.splitlines(keepends=True):
            if line.strip().split(b"=", 1)[0].strip() != b"VOCABULARY_ERROR_REVIEW_ENABLED":
                retained.append(line)
        text = b"".join(retained)
        if text and not text.endswith(b"\n"):
            text += b"\n"
        text += b"VOCABULARY_ERROR_REVIEW_ENABLED=true\n"
        atomic_write(dotenv, text, mode)
        written = True
        result.update(ok=True, enrollment=details, feature_flag_written=True)
    except Exception as error:
        if written:
            atomic_write(dotenv, original, mode)
        result.update(error_type=type(error).__name__, feature_flag_written=False)
    finally:
        try:
            started = subprocess.run(
                ["systemctl", "start", "studytracker"], capture_output=True, timeout=30
            )
            result["service_start_command_succeeded"] = started.returncode == 0
        except Exception as error:
            result.update(
                service_start_command_succeeded=False, start_error_type=type(error).__name__
            )
        if not result["service_start_command_succeeded"]:
            result.update(ok=False, error="service_start_failed")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--apply", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        result = rollout(
            Path("/root/apps/studytracker"),
            Path("/root/.studytracker-pilot/vocabulary-20261117.json"),
            args.expected_head,
        )
    except Exception as error:
        result = {"ok": False, "identities_exported": False, "error_type": type(error).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
