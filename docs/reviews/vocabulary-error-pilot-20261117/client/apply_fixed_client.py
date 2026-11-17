"""Apply the reviewed four-page patch only after all 451 source hashes match."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = Path("/Users/zhouxin/Desktop/studytracker-release")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    before = json.loads((HERE / "fixed-source-before-sha256.json").read_text())
    manifest = json.loads((HERE / "manifest.json").read_text())
    assert all(sha(TARGET / name) == value for name, value in before.items()), "source drift"
    assert all(
        sha(HERE / "files" / name) == state["after"] for name, state in manifest.items()
    ), "candidate drift"
    assert all(
        not (TARGET / name).exists() for name, state in manifest.items() if state["before"] is None
    ), "new test path already exists"
    if args.apply:
        backup = Path("/private/tmp/studytracker-error-policy-client-before-20261117")
        for name, state in manifest.items():
            if state["before"] is not None:
                saved = backup / name
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(TARGET / name, saved)
        for name in manifest:
            shutil.copyfile(HERE / "files" / name, TARGET / name)
        assert all(sha(TARGET / name) == state["after"] for name, state in manifest.items())
        assert all(
            sha(TARGET / name) == value for name, value in before.items() if name not in manifest
        )
    print(
        json.dumps(
            {
                "applied": args.apply,
                "checked_before": len(before),
                "changed_product_files": 4 if args.apply else 0,
                "new_test": 1 if args.apply else 0,
                "unchanged_non_targets": len(before) - 4,
                "uploaded": False,
                "published": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
