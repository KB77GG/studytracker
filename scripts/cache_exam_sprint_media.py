#!/usr/bin/env python3
"""Cache a bounded set of public exam media with per-unit version manifests.

No session, account API, answer submission or publication is involved. Successful
units may be resumed; a failed unit never replaces its previous complete manifest.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.ninefen_assets import (  # noqa: E402
    UNIT_ID,
    NinefenAssetError,
    _atomic_manifest,
    cache_unit_media,
    collect_exam_media,
    verified_media_manifest,  # noqa: F401 (backwards-compatible import)
)


def _read_exam(path: Path) -> dict:
    if not UNIT_ID.fullmatch(path.stem) or path.stat().st_size > 8 * 1024 * 1024:
        raise NinefenAssetError("Invalid public exam file")
    payload = json.loads(path.read_text(encoding="utf-8"))
    data = payload.get("data") if isinstance(payload, dict) else None
    if (
        payload.get("code") not in (200, "200")
        or not isinstance(data, dict)
        or data.get("id") != path.stem
        or data.get("channel") not in ("reading", "listening")
        or not (
            (type(data.get("isCharge")) is int and data["isCharge"] == 0)
            or data.get("isCharge") == "0"
        )
    ):
        raise NinefenAssetError("Exam is outside the public media scope")
    collect_exam_media(payload)
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    state = ROOT / "instance/exam_sprint"
    parser.add_argument("--exam-dir", type=Path, default=state / "exams")
    parser.add_argument("--cache-dir", type=Path, default=state / "assets")
    parser.add_argument("--manifest-dir", type=Path, default=state / "media")
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--unit-id", action="append", help="Retry only specified public unit IDs")
    parser.add_argument("--refresh", action="store_true", help="Re-download even verified units")
    args = parser.parse_args(argv)
    try:
        if args.unit_id and not all(UNIT_ID.fullmatch(value) for value in args.unit_id):
            raise NinefenAssetError("Invalid requested unit ID")
        paths = (
            [args.exam_dir / f"{unit_id}.json" for unit_id in dict.fromkeys(args.unit_id)]
            if args.unit_id
            else sorted(args.exam_dir.glob("*.json"))
        )
        if not 1 <= len(paths) <= 140:
            raise NinefenAssetError("Expected 1 to 140 public exam files")
        # Validate all public identities and media URLs before starting network reads.
        exams = [(path.stem, _read_exam(path)) for path in paths]
        args.manifest_dir.mkdir(parents=True, exist_ok=True)
        with (args.manifest_dir / ".cache.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise NinefenAssetError("Another media cache run is active") from exc
            succeeded = reused = 0
            failures = []
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                jobs = {
                    pool.submit(
                        cache_unit_media,
                        payload,
                        args.cache_dir,
                        args.manifest_dir,
                        refresh=args.refresh,
                    ): unit_id
                    for unit_id, payload in exams
                }
                for index, future in enumerate(as_completed(jobs), 1):
                    unit_id = jobs[future]
                    try:
                        manifest, was_reused = future.result()
                        succeeded += 1
                        reused += int(was_reused)
                        event = {
                            "unit_id": unit_id,
                            "ok": True,
                            "reused": was_reused,
                            "assets": len(manifest["assets"]),
                        }
                    except (OSError, ValueError, KeyError, TypeError) as exc:
                        reason = (
                            str(exc)[:200]
                            if isinstance(exc, NinefenAssetError)
                            else type(exc).__name__
                        )
                        event = {"unit_id": unit_id, "ok": False, "reason": reason}
                        failures.append(event)
                    print(
                        json.dumps({"completed": index, "total": len(exams), **event}), flush=True
                    )
            summary = {
                "ok": not failures,
                "total": len(exams),
                "succeeded": succeeded,
                "reused": reused,
                "failures": failures,
            }
            _atomic_manifest(args.manifest_dir / "run-summary.json", summary)
            print(json.dumps(summary), flush=True)
            return 0 if not failures else 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        reason = str(exc)[:200] if isinstance(exc, NinefenAssetError) else type(exc).__name__
        print(json.dumps({"ok": False, "reason": reason}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
