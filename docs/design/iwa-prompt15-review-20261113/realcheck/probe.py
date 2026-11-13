"""Offline .15 reading-confirmation probe. Synthetic inputs only, no network/keys.
Run: MAIN/.venv/bin/python -B probe.py --source SOURCE --out evidence.json
Exit 1 means a correctness expectation is not met; baseline controls must pass.
"""

import argparse
import contextlib
import copy
import hashlib
import io
import json
import os
import socket
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args()
sys.path.insert(0, str(Path(args.source).resolve()))
from tools.ielts_writing_ai import __main__ as cli
from tools.ielts_writing_ai import imagecheck, realcheck, realcheck_compare
from tools.ielts_writing_ai.llm import FakeClient
from tools.ielts_writing_ai.tests.helpers import PNG_BYTES

ESSAY = (
    "The chart shows the proportions of residents using two services in two years.\n"
    "Overall, service A became more popular while service B became less popular.\n"
    "Service A rose from 20% to 40%, whereas service B fell from 70% to 50%.\n"
    "These opposite changes suggest a shift in residents preferences over the period."
)
DESCRIPTION = "A line chart. Data: Service A 2010 = 20%; Service A 2020 = 40%; Service B 2010 = 70%; Service B 2020 = 50%. Trends: A rises while B falls."
CHANGED = DESCRIPTION.replace("40%", "90%")


class Recording(FakeClient):
    def __init__(self):
        super().__init__()
        self.messages = []

    def complete(self, messages, **kwargs):
        self.messages.append(json.dumps(messages, ensure_ascii=False))
        return super().complete(messages, **kwargs)


checks = []
observations = {}


def check(name, passed):
    checks.append({"name": name, "passed": bool(passed)})


def no_network(*args, **kwargs):
    raise AssertionError("Network prohibited in offline probe")


with (
    tempfile.TemporaryDirectory(prefix="iwa15-confirmation-review-") as scratch,
    patch.dict(
        os.environ, {k: v for k, v in os.environ.items() if not k.startswith("IWA_")}, clear=True
    ),
    patch.object(socket.socket, "connect", no_network),
):
    root = Path(scratch)
    image = root / "chart.png"
    image.write_bytes(PNG_BYTES)
    sample = {
        "id": "synthetic-t1",
        "task_type": "task1",
        "prompt": "The chart shows the proportions of residents using service A and service B in 2010 and 2020. Summarise the information.",
        "essay": ESSAY,
        "image": "chart.png",
    }
    samplefile = root / "samples.jsonl"

    def save_samples(row=sample):
        samplefile.write_text(json.dumps(row) + "\n")

    save_samples()
    items = realcheck.load_samples(str(samplefile))
    raw = {
        "version": 2,
        "images": {"synthetic-t1": {"status": "ready", "description": DESCRIPTION, "error": None}},
    }
    rawfile = root / "raw.json"
    rawfile.write_text(json.dumps(raw))
    checked = imagecheck.confirm(
        raw,
        items,
        ["synthetic-t1"],
        by="Reviewer",
        corrections={"synthetic-t1": DESCRIPTION.replace("50%", "51%")},
    )
    checkedfile = root / "checked.json"
    checkedfile.write_text(json.dumps(checked))
    check(
        "confirmed_record_keeps_original",
        checked["images"]["synthetic-t1"]["check"]["model_description"] == DESCRIPTION,
    )
    check(
        "confirmed_record_binds_original_image",
        checked["images"]["synthetic-t1"]["check"]["image_sha256"]
        == imagecheck.image_sha256(image),
    )
    envfile = root / "demo.env"
    envfile.write_text(
        f'IWA_DATA_DIR={root / "data"}\nIWA_LLM_PROVIDER=fake\nIWA_VISION_PROVIDER=none\n'
    )
    runs = {}

    def run(name, readings=None, require=False, repeat=1):
        client = Recording()
        outdir = root / name
        stdout = io.StringIO()
        stderr = io.StringIO()
        argv = [
            "--env-file",
            str(envfile),
            "realcheck",
            "--samples",
            str(samplefile),
            "--kinds",
            "evaluate",
            "--max-calls",
            "4",
            "--repeat",
            str(repeat),
            "--out",
            str(outdir),
        ]
        if readings:
            argv += ["--image-descriptions", str(readings)]
        if require:
            argv += ["--require-checked-images"]
        with (
            patch.object(
                realcheck,
                "build_client",
                side_effect=lambda settings, vision=False: None if vision else client,
            ),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = cli.main(argv)
        data = (
            json.loads((outdir / "run_data.json").read_text())
            if (outdir / "run_data.json").exists()
            else None
        )
        ta = [realcheck._scores(s)["task"] for s in data["samples"]] if data else []
        result = {
            "exit_code": code,
            "calls": len(client.messages),
            "task_bands": ta,
            "has_human_checked_note": any(
                "checked against the image by a person" in m for m in client.messages
            ),
            "has_changed_90_percent": any("90%" in m for m in client.messages),
            "message_hashes": [hashlib.sha256(m.encode()).hexdigest() for m in client.messages],
        }
        runs[name] = (outdir, data, client.messages)
        observations[name] = result
        return result

    unchecked = run("unchecked", rawfile)
    check(
        "unchecked_no_ta",
        unchecked["task_bands"] == [None] and not unchecked["has_human_checked_note"],
    )
    reject = run("require_unchecked", rawfile, True)
    check("require_checked_rejects_before_calls", reject["exit_code"] == 2 and reject["calls"] == 0)
    good = run("confirmed_repeat", checkedfile, True, repeat=2)
    check(
        "corrected_confirmed_scores_twice",
        good["exit_code"] == 0
        and len(good["task_bands"]) == 2
        and all(x is not None for x in good["task_bands"]),
    )
    check("repeats_same_prompt", len(set(good["message_hashes"])) == 1)
    check("confirm_does_not_mutate_raw", rawfile.read_text() == json.dumps(raw))
    image.write_bytes(PNG_BYTES + b"changed")
    stale = run("changed_image_file", checkedfile, True)
    check("changed_image_file_rejected", stale["exit_code"] == 2 and stale["calls"] == 0)
    # Supported JSONL image_description path: carry the same legitimate check metadata
    # with the reading, but keep the changed image above. It must not evade SHA checks.
    inline = dict(
        sample,
        image_description=checked["images"]["synthetic-t1"]["description"],
        image_check=checked["images"]["synthetic-t1"]["check"],
    )
    save_samples(inline)
    bypass = run("inline_stale_check")
    check("inline_check_same_image_required", bypass["exit_code"] == 2 and bypass["calls"] == 0)
    # Missing all audit fields should not count as a confirmed reading either.
    inline["image_check"] = {"status": "confirmed"}
    save_samples(inline)
    bare = run("inline_bare_status")
    check("inline_check_metadata_validated", bare["exit_code"] == 2 and bare["calls"] == 0)
    no_image = dict(inline)
    no_image.pop("image")
    save_samples(no_image)
    emptyfile = root / "empty-outcomes.json"
    emptyfile.write_text(json.dumps({"version": 2, "images": {}}))
    no_image_run = run("require_checked_inline_without_image", emptyfile, True)
    check(
        "require_checked_no_image_cannot_score_ta",
        no_image_run["exit_code"] == 2 or no_image_run["task_bands"] == [None],
    )
    save_samples()
    image.write_bytes(PNG_BYTES)
    # An already-confirmed readings file changes after the check. The check record is
    # byte-identical: no new user confirmation is performed.
    edited = copy.deepcopy(checked)
    edited["images"]["synthetic-t1"]["description"] = CHANGED
    editedfile = root / "edited-after-check.json"
    editedfile.write_text(json.dumps(edited))
    editedrun = run("edited_after_confirmation", editedfile, True)
    check(
        "post_check_reading_change_requires_reconfirmation",
        editedrun["exit_code"] == 2 and editedrun["calls"] == 0,
    )
    # Metadata alone is not model input; use two independently confirmed equal readings.
    second = copy.deepcopy(checked)
    second["images"]["synthetic-t1"]["check"].update(
        by="Second reviewer", at="2026-11-14T00:00:00Z"
    )
    secondfile = root / "second-checker.json"
    secondfile.write_text(json.dumps(second))
    first = run("compare_first", checkedfile, True)
    other = run("compare_second", secondfile, True)
    check("metadata_only_has_same_model_input", first["message_hashes"] == other["message_hashes"])
    a = realcheck_compare.conditions(realcheck_compare.load_run(runs["compare_first"][0]))
    b = realcheck_compare.conditions(realcheck_compare.load_run(runs["compare_second"][0]))
    errors, warnings = realcheck_compare.check_same_conditions(a, b)
    observations["metadata_only_comparison"] = {"errors": errors, "warnings": warnings}
    check("metadata_only_allows_same_input_comparison", not errors)
    # Confirm CLI must refuse overwriting an existing different file.
    before = checkedfile.read_bytes()
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli.main(
            [
                "--env-file",
                str(envfile),
                "realcheck-check-images",
                "--samples",
                str(samplefile),
                "--descriptions",
                str(rawfile),
                "--confirm",
                "synthetic-t1",
                "--by",
                "Another reviewer",
                "--out",
                str(checkedfile),
            ]
        )
    check(
        "existing_confirmed_output_not_overwritten",
        code == 2 and checkedfile.read_bytes() == before,
    )

report = {
    "source": str(Path(args.source).resolve()),
    "source_head": __import__("subprocess")
    .check_output(["git", "rev-parse", "HEAD"], cwd=args.source, text=True)
    .strip(),
    "checks": checks,
    "passed": sum(c["passed"] for c in checks),
    "total": len(checks),
    "observations": observations,
    "network_calls": 0,
    "scope": "Synthetic fake-client CLI and comparison; no private inputs or keys; all files except this report temporary.",
}
out = Path(args.out)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(
    json.dumps(
        {
            "passed": report["passed"],
            "total": report["total"],
            "failed": [c["name"] for c in checks if not c["passed"]],
            "out": str(out),
        },
        ensure_ascii=False,
    )
)
raise SystemExit(any(not c["passed"] for c in checks))
