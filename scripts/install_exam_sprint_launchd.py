#!/usr/bin/env python3
"""Plan or install the local, isolated exam-sprint launchd runtime."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_exam_sprint_weekly import (  # noqa: E402
    LABEL,
    ZONE,
    due_week,
    read_private_json,
    system_timezone_is_shanghai,
    write_private_json,
)

SOURCE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME = Path.home() / "Library" / "Application Support" / "StudyTrackerExamSprint"
CODE_FILES = (
    "services/__init__.py",
    "services/exam_sprint.py",
    "services/exam_sprint_import.py",
    "services/exam_sprint_store.py",
    "services/practice_library_offline.py",
    "services/ninefen_source.py",
    "services/ninefen_session.py",
    "services/ninefen_content.py",
    "services/ninefen_assets.py",
    "scripts/sync_exam_sprint.py",
    "scripts/publish_exam_sprint.py",
    "scripts/activate_exam_sprint.py",
    "scripts/run_exam_sprint_weekly.py",
)


def _owned_directory(path: Path):
    missing = []
    ancestor = path
    while not ancestor.exists() and not ancestor.is_symlink():
        missing.append(ancestor)
        ancestor = ancestor.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise ValueError("Destination must be an owned mode-700 directory")


def _copy_file(source: Path, destination: Path):
    info = source.lstat()
    if not stat.S_ISREG(info.st_mode) or source.is_symlink():
        raise ValueError("Only regular source files may enter the runtime")
    _owned_directory(destination.parent)
    fd, temporary = tempfile.mkstemp(prefix=".install-", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as incoming:
            shutil.copyfileobj(incoming, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _copy_tree(source: Path, destination: Path):
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Expected a real source directory")
    _owned_directory(destination)
    for item in source.iterdir():
        if item.name in ("__pycache__", ".DS_Store") or item.name.endswith(".lock"):
            continue
        if item.is_symlink():
            raise ValueError("Source trees may not contain symlinks")
        if item.is_dir():
            _copy_tree(item, destination / item.name)
        else:
            _copy_file(item, destination / item.name)


def _copy_legacy_dependencies(source: Path, runtime: Path, state: Path, asset_root: Path):
    """Copy only reviewed legacy dependencies referenced by the active snapshot."""
    snapshot = json.loads((state / "current.json").read_text(encoding="utf-8"))
    manifest = json.loads((source / "data" / "exam_sprint" / "mappings.json").read_text())
    reviewed = {(m["subject"], m["source_id"]): m for m in manifest["mappings"]}
    copied = set()
    for subject, groups in snapshot["subjects"].items():
        if subject not in ("reading", "listening"):
            raise ValueError("Unsupported mapped subject")
        for group in groups:
            for row in group["items"]:
                mapping = row.get("mapping")
                if not mapping or mapping.get("target_kind") == "ninefen":
                    continue
                if mapping != reviewed.get((subject, row["source_id"])):
                    raise ValueError("Legacy mapping is not the reviewed release mapping")
                target = mapping.get("target_id")
                if not isinstance(target, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", target):
                    raise ValueError("Invalid legacy identity")
                folder = Path("static") / f"{subject}_jijing"
                relative = (
                    folder / "parts" / f"{target}.json"
                    if subject == "listening"
                    else folder / f"{target}.json"
                )
                item = source / relative
                if item.is_symlink() or not item.is_file():
                    raise ValueError("Reviewed legacy document is missing")
                raw = item.read_bytes()
                if hashlib.sha256(raw).hexdigest() != mapping.get("target_sha256"):
                    raise ValueError("Reviewed legacy document hash changed")
                if relative not in copied:
                    _copy_file(item, runtime / relative)
                    copied.add(relative)
                offline = source / folder / "offline_tests.json"
                if offline.is_file() and folder / "offline_tests.json" not in copied:
                    _copy_file(offline, runtime / folder / "offline_tests.json")
                    copied.add(folder / "offline_tests.json")
                if subject == "listening":
                    audio = json.loads(raw).get("audio", {}).get("local_path")
                    if (
                        not isinstance(audio, str)
                        or not audio
                        or Path(audio).is_absolute()
                        or ".." in Path(audio).parts
                    ):
                        raise ValueError("Legacy audio must be an explicit relative path")
                    relative_audio = folder / audio
                    source_audio = asset_root / relative_audio
                    if not source_audio.resolve().is_relative_to(asset_root.resolve()):
                        raise ValueError("Legacy audio escapes the explicitly supplied asset root")
                    if relative_audio not in copied:
                        _copy_file(source_audio, runtime / relative_audio)
                        copied.add(relative_audio)
    return len(copied)


def build_plist(runtime: Path, python: str) -> dict:
    return {
        "Label": LABEL,
        "ProgramArguments": [python, str(runtime / "scripts" / "run_exam_sprint_weekly.py")],
        "WorkingDirectory": str(runtime),
        "RunAtLoad": True,
        "StartCalendarInterval": {"Weekday": 1, "Hour": 6, "Minute": 0},
        "StartInterval": 1800,
        "ProcessType": "Background",
        "LowPriorityIO": True,
        "Nice": 10,
        "Umask": 0o077,
        "EnvironmentVariables": {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"},
        "StandardOutPath": str(runtime / "logs" / "weekly.log"),
        "StandardErrorPath": str(runtime / "logs" / "weekly-error.log"),
    }


def _validate_initial_snapshot(source: Path):
    payload = json.loads((source / "current.json").read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("source") != "ninefen":
        raise ValueError("A complete previously published snapshot is required")
    expected_parts = {"reading": 3, "listening": 4}
    subjects = payload.get("subjects")
    if not isinstance(subjects, dict) or set(subjects) != set(expected_parts):
        raise ValueError("Both ranked subjects are required")
    for subject, count in expected_parts.items():
        groups = subjects[subject]
        if not isinstance(groups, list) or [g.get("part") for g in groups] != list(
            range(1, count + 1)
        ):
            raise ValueError("Incomplete initial snapshot")
        for group in groups:
            rows = group.get("items")
            if not isinstance(rows, list) or [r.get("rank") for r in rows] != list(range(1, 21)):
                raise ValueError("Incomplete public ranking")
            for row in rows:
                if row.get("source_available") is True and row.get("entry_mode") == "exam":
                    if not row.get("mapping") or row.get("unavailable_reason"):
                        raise ValueError("Initial snapshot has an unavailable open exercise")
    private = source / "private"
    private_info = private.lstat()
    if (
        not stat.S_ISDIR(private_info.st_mode)
        or private_info.st_uid != os.getuid()
        or stat.S_IMODE(private_info.st_mode) != 0o700
    ):
        raise ValueError("Source private root must be an owned mode-700 directory")
    session = private / "session.json"
    info = session.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
    ):
        raise ValueError("A local owned mode-600 source session is required")


def install(args) -> None:
    if sys.platform != "darwin" or not system_timezone_is_shanghai():
        raise ValueError("macOS with system timezone Asia/Shanghai is required")
    source = args.source_root.absolute()
    runtime = args.runtime_dir.absolute()
    if (
        runtime.resolve().is_relative_to(source.resolve())
        or source.resolve().is_relative_to(runtime.resolve())
        or runtime.resolve().is_relative_to(args.state_source.resolve())
        or str(runtime.resolve()).startswith(("/tmp/", "/private/tmp/"))
    ):
        raise ValueError("A separate permanent runtime is required")
    python = str(args.python.absolute())
    if python.startswith(("/tmp/", "/private/tmp/")) or not Path(python).is_file():
        raise ValueError("A permanent Python executable is required")
    for relative in CODE_FILES:
        if (source / relative).is_symlink() or not (source / relative).is_file():
            raise ValueError("Source runtime code is incomplete")
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    checked = subprocess.run(
        [python, "-c", "import certifi, werkzeug"],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=False,
    )
    if checked.returncode:
        raise ValueError("The selected Python requires installed certifi and Werkzeug")
    fresh = not runtime.exists() or (runtime.is_dir() and not any(runtime.iterdir()))
    if fresh:
        if not args.initial_publish_confirmed:
            raise ValueError("Initial remote publication must be confirmed before activation")
        _validate_initial_snapshot(args.state_source)
    _owned_directory(runtime)
    fd = os.open(runtime / ".weekly.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a") as lock:
        info = os.fstat(lock.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise ValueError("Invalid runtime lock")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("A weekly run is active; install later") from None
        if not fresh:
            previous = read_private_json(runtime / "weekly-state.json")
            if previous.get("initialized_after_publish") is not True:
                raise ValueError("Existing runtime needs explicit recovery before activation")
        for relative in CODE_FILES:
            _copy_file(source / relative, runtime / relative)
        _owned_directory(runtime / "data")
        _copy_tree(source / "data" / "exam_sprint", runtime / "data" / "exam_sprint")
        if fresh:
            _owned_directory(runtime / "instance")
            _copy_tree(args.state_source, runtime / "instance" / "exam_sprint")
        _owned_directory(runtime / "static")
        _copy_legacy_dependencies(
            source,
            runtime,
            runtime / "instance" / "exam_sprint",
            (args.legacy_assets_root or source).absolute(),
        )
        # This is local validation only. It never invokes ssh/rsync in dry-run mode.
        validated = subprocess.run(
            [
                python,
                str(runtime / "scripts" / "publish_exam_sprint.py"),
                "--state-dir",
                str(runtime / "instance" / "exam_sprint"),
                "--dry-run",
            ],
            cwd=runtime,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=300,
            check=False,
        )
        if validated.returncode:
            raise ValueError("Isolated runtime did not validate its complete public snapshot")
        if fresh:
            write_private_json(
                runtime / "weekly-state.json",
                {
                    "schema_version": 1,
                    "initialized_after_publish": True,
                    "last_success_week": due_week(datetime.now(ZONE)),
                    "last_success_at": datetime.now(ZONE).isoformat(),
                    "attempts": {},
                },
            )
        _owned_directory(runtime / "logs")
        for name in ("weekly.log", "weekly-error.log"):
            path = runtime / "logs" / name
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
            os.close(fd)
        write_private_json(
            runtime / "weekly-config.json",
            {
                "schema_version": 1,
                "enabled": True,
                "timezone": "Asia/Shanghai",
                "python": python,
                "host": "root@47.110.45.193",
                "remote_root": "/root/apps/studytracker",
            },
        )
        launch_agents = Path.home() / "Library" / "LaunchAgents"
        launch_agents.mkdir(parents=True, exist_ok=True)
        plist_path = launch_agents / f"{LABEL}.plist"
        fd, temporary = tempfile.mkstemp(prefix=".exam-sprint-", dir=launch_agents)
        try:
            with os.fdopen(fd, "wb") as handle:
                plistlib.dump(build_plist(runtime, python), handle)
            os.replace(temporary, plist_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        domain = f"gui/{os.getuid()}"
        # Hold the lock through registration so a launchd wake cannot start work
        # between replacing the code and replacing the job registration.
        subprocess.run(
            ["/bin/launchctl", "bootout", f"{domain}/{LABEL}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
        result = subprocess.run(
            ["/bin/launchctl", "bootstrap", domain, str(plist_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
        if result.returncode:
            raise ValueError("Runtime copied; launchd registration failed")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument(
        "--state-source", type=Path, default=SOURCE_ROOT / "instance" / "exam_sprint"
    )
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument(
        "--legacy-assets-root",
        type=Path,
        help="Explicit project root for only the reviewed legacy audio files; defaults to source root",
    )
    parser.add_argument(
        "--install", action="store_true", help="Copy local runtime and register launchd"
    )
    parser.add_argument(
        "--initial-publish-confirmed",
        action="store_true",
        help="Initial complete snapshot has already been published and verified",
    )
    args = parser.parse_args(argv)
    if not args.install:
        print(
            json.dumps(
                {
                    "action": "plan",
                    "runtime": str(args.runtime_dir),
                    "schedule": "Monday 06:00 Asia/Shanghai; 30-minute catch-up checks",
                    "activation_requires": "--install --initial-publish-confirmed",
                }
            )
        )
        return 0
    try:
        install(args)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
        print(
            "Installation stopped: local runtime validation or registration failed.",
            file=sys.stderr,
        )
        return 2
    print(json.dumps({"action": "installed", "label": LABEL, "runtime": str(args.runtime_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
