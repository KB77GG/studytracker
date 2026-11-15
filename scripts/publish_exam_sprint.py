#!/usr/bin/env python3
"""Upload only immutable public assets/content, then validate a staged snapshot.

Private source sessions, answers, raw exams and the rest of the local state tree
are never transfer inputs. Existing remote immutable files are never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.activate_exam_sprint import read_candidate, validate_candidate  # noqa: E402
from services.exam_sprint_store import VERSIONED_ID  # noqa: E402

ALLOWED_HOST = "root@47.110.45.193"
ALLOWED_REMOTE_ROOT = "/root/apps/studytracker"
ASSET_FILENAME = re.compile(r"[0-9a-f]{64}\.(mp3|png|jpg|jpeg|webp|gif)\Z")


def public_files(state_dir: Path) -> list[str]:
    """Build an explicit relative-file allowlist; never recursively send state/."""
    state = Path(state_dir)
    if state.is_symlink() or not state.is_dir():
        raise ValueError("Invalid local runtime directory")
    files = []
    for folder in (state / "assets", state / "content"):
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("Public asset/content directories are required")
        for path in sorted(folder.rglob("*")):
            if path.is_symlink():
                raise ValueError("Symlinks are not public transfer inputs")
            relative = path.relative_to(state)
            if path.is_dir():
                if relative.parts not in (("content", "reading"), ("content", "listening")):
                    raise ValueError("Unexpected directory in public transfer inputs")
                continue
            if not path.is_file():
                raise ValueError("Only regular files may be uploaded")
            if relative.parts[0] == "assets":
                valid = len(relative.parts) == 2 and ASSET_FILENAME.fullmatch(path.name)
            else:
                filename = path.name
                suffix = ".meta.json" if filename.endswith(".meta.json") else ".json"
                identifier = filename[: -len(suffix)] if filename.endswith(suffix) else ""
                match = VERSIONED_ID.fullmatch(identifier)
                valid = (
                    len(relative.parts) == 3
                    and relative.parts[1] in {"reading", "listening"}
                    and match
                )
                if valid:
                    valid = (relative.parts[1] == "listening") == bool(match.group(3))
            if not valid:
                raise ValueError("Unexpected filename in public transfer inputs")
            files.append(relative.as_posix())
    return files


def build_commands(
    state_dir: Path, host: str, remote_root: str, digest: str, *, snapshot_path=None
):
    if host != ALLOWED_HOST or remote_root != ALLOWED_REMOTE_ROOT:
        raise ValueError("Remote host/root is outside the configured StudyTracker deployment")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid snapshot fingerprint")
    remote_state = f"{remote_root}/instance/exam_sprint"
    incoming = f"{remote_state}/incoming/{digest}.json"
    ssh = ["ssh", "-o", "BatchMode=yes", host]
    prepare = [
        f"{remote_root}/.venv/bin/python",
        f"{remote_root}/scripts/activate_exam_sprint.py",
        "--root",
        remote_root,
        "--prepare-directories",
    ]
    rsync = [
        "rsync",
        "--recursive",
        "--times",
        "--ignore-existing",
        "--safe-links",
        "--chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r",
        "-e",
        "ssh -o BatchMode=yes",
    ]
    return [
        [*ssh, shlex.join(prepare)],
        *[
            [
                *rsync,
                "--relative",
                "--from0",
                "--files-from=-",
                "--",
                f"{state_dir.resolve() / folder}/",
                f"{host}:{remote_state}/{folder}/",
            ]
            for folder in ("assets", "content")
        ],
        [
            *rsync,
            "--",
            str(snapshot_path or state_dir.resolve() / "current.json"),
            f"{host}:{incoming}",
        ],
        [
            *ssh,
            shlex.join(
                [
                    f"{remote_root}/.venv/bin/python",
                    f"{remote_root}/scripts/activate_exam_sprint.py",
                    "--root",
                    remote_root,
                    "--snapshot",
                    incoming,
                    "--expected-sha256",
                    digest,
                ]
            ),
        ],
    ]


def publish(state_dir: Path, host: str, remote_root: str, *, root=ROOT, dry_run=False, runner=None):
    state = Path(state_dir).absolute()
    # Validate the fixed target before reading data or invoking any external command.
    build_commands(state, host, remote_root, "0" * 64)
    files = public_files(state)
    current = state / "current.json"
    if current.is_symlink() or not current.is_file():
        raise ValueError("A public current snapshot is required")
    digest = hashlib.sha256(current.read_bytes()).hexdigest()
    snapshot, raw = read_candidate(current, digest)
    summary = validate_candidate(Path(root), snapshot, state)
    commands = build_commands(state, host, remote_root, digest)
    report = {
        "ok": True,
        "dry_run": dry_run,
        "public_files": len(files),
        "snapshot_sha256": digest,
        "validation": summary,
        "commands": [shlex.join(command) for command in commands],
    }
    if dry_run:
        return report
    run = runner or subprocess.run
    # Freeze only public snapshot bytes so a concurrent local sync cannot change
    # the capture between its filename hash and the actual upload.
    with tempfile.TemporaryDirectory(prefix="exam-sprint-publish-") as temporary:
        staged = Path(temporary) / f"{digest}.json"
        staged.write_bytes(raw)
        commands = build_commands(state, host, remote_root, digest, snapshot_path=staged)
        for index, command in enumerate(commands):
            manifest = b""
            if index in (1, 2):
                prefix = "assets/" if index == 1 else "content/"
                names = [name[len(prefix) :] for name in files if name.startswith(prefix)]
                manifest = ("\0".join(names) + ("\0" if names else "")).encode("utf-8")
            run(command, input=manifest, check=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--host", default=ALLOWED_HOST)
    parser.add_argument("--remote-root", default=ALLOWED_REMOTE_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = publish(args.state_dir, args.host, args.remote_root, dry_run=args.dry_run)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        subprocess.CalledProcessError,
    ):
        print(
            "Sprint publish failed; active remote capture was not replaced without validation.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
