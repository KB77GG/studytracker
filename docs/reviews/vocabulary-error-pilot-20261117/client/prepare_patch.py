"""Archive the narrow student-page change; never overwrite the upload tree."""

import difflib
import hashlib
import json
import shutil
from pathlib import Path

SOURCE = Path("/Users/zhouxin/Desktop/studytracker-release")
CANDIDATE = Path("/private/tmp/studytracker-vocabulary-error-client-20261117")
HERE = Path(__file__).resolve().parent
TARGETS = tuple(
    f"miniprogram/pages/student/{page}/index.{suffix}"
    for page in ("home", "vocabulary-review")
    for suffix in ("js", "wxml")
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    initial = json.loads((HERE / "fixed-source-before-sha256.json").read_text())
    assert all(digest(SOURCE / name) == value for name, value in initial.items()), "source drift"
    changed = [name for name, value in initial.items() if digest(CANDIDATE / name) != value]
    assert set(changed) == set(TARGETS), changed
    patch = []
    for name in TARGETS:
        old, new = SOURCE / name, CANDIDATE / name
        patch.extend(
            difflib.unified_diff(
                old.read_text().splitlines(True),
                new.read_text().splitlines(True),
                fromfile="a/" + name,
                tofile="b/" + name,
            )
        )
        target = HERE / "files" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(new, target)
    test = "tests/test_vocabulary_error_policy_client.js"
    target = HERE / "files" / test
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CANDIDATE / test, target)
    (HERE / "client-increment.patch").write_text("".join(patch))
    manifest = {
        name: {"before": initial[name], "after": digest(CANDIDATE / name)} for name in TARGETS
    }
    manifest[test] = {"before": None, "after": digest(CANDIDATE / test)}
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (HERE / "scope-check.json").write_text(
        json.dumps(
            {
                "existing_files_checked": len(initial),
                "product_files_changed": len(TARGETS),
                "unchanged_files": len(initial) - len(TARGETS),
                "new_tests": 1,
                "fixed_source_changed": False,
            },
            indent=2,
        )
        + "\n"
    )
    shutil.copyfile("/private/tmp/vocabulary-error-client-tests.log", HERE / "client-tests.log")
    print(json.dumps({"checked": len(initial), "changed": len(TARGETS), "patch_ready": True}))


if __name__ == "__main__":
    main()
