"""Offline adjacent checks for the .15 confirmation repair; synthetic data only."""

import argparse
import copy
import hashlib
import json
import socket
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

p = argparse.ArgumentParser()
p.add_argument("--source", required=True)
p.add_argument("--out", required=True)
args = p.parse_args()
sys.path.insert(0, str(Path(args.source).resolve()))
from tools.ielts_writing_ai import imagecheck, prompts, realcheck, realcheck_compare
from tools.ielts_writing_ai.llm import FakeClient
from tools.ielts_writing_ai.tests.helpers import PNG_BYTES, settings_for

checks = []


def check(name, value):
    checks.append({"name": name, "passed": bool(value)})


def blocked(*a, **k):
    raise AssertionError("Network prohibited")


class Client(FakeClient):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def complete(self, *a, **k):
        self.calls += 1
        return super().complete(*a, **k)


with (
    tempfile.TemporaryDirectory(prefix="iwa15-recheck-adjacent-") as tmp,
    patch.object(socket.socket, "connect", blocked),
):
    root = Path(tmp)
    img = root / "chart.png"
    img.write_bytes(PNG_BYTES)
    desc = "Data: A in 2010 = 20%; A in 2020 = 40%; B in 2010 = 70%; B in 2020 = 50%. A rises, B falls."
    item = {
        "id": "s1",
        "task_type": "task1",
        "prompt": "The chart compares services A and B in two years.",
        "essay": "The chart shows the shares of two services. Overall, A rose while B fell. A rose from 20% to 40%, while B fell from 70% to 50%.",
        "image": str(img),
    }
    raw = {"version": 2, "images": {"s1": {"status": "ready", "description": desc, "error": None}}}
    confirmed = imagecheck.confirm(
        raw, [item], ["s1"], by="Reviewer", now=datetime(2026, 11, 13, tzinfo=UTC)
    )
    record = confirmed["images"]["s1"]["check"]
    check("raw_unmodified", raw["images"]["s1"].get("check") is None)
    check("unchanged_reading_not_marked_edited", not record["edited"])
    check(
        "reading_hash_exact_utf8",
        record["reading_sha256"] == hashlib.sha256(desc.encode()).hexdigest(),
    )
    corrected = desc.replace("40%", "41%")
    fixed = imagecheck.confirm(raw, [item], ["s1"], by="Reviewer", corrections={"s1": corrected})
    fc = fixed["images"]["s1"]["check"]
    check(
        "corrected_hash_matches_final_text",
        fc["reading_sha256"] == hashlib.sha256(corrected.encode()).hexdigest(),
    )
    check("correction_preserves_raw", fc["model_description"] == desc and fc["edited"])
    checkedfile = root / "checked.json"
    checkedfile.write_text(json.dumps(confirmed))
    loaded = [copy.deepcopy(item)]
    check(
        "apply_good_confirmed_count",
        realcheck.apply_image_descriptions(loaded, checkedfile, require_checked=True) == 1,
    )
    good = loaded[0]
    settings = settings_for(tmp)

    def reject_before_calls(name, rows):
        client = Client()
        try:
            realcheck.run(settings, rows, client=client, kinds=("evaluate",))
        except realcheck.RealCheckError:
            rejected = True
        else:
            rejected = False
        check(name, rejected and client.calls == 0)

    missing = copy.deepcopy(good)
    missing["image_check"].pop("reading_sha256")
    reject_before_calls("run_missing_hash_zero_calls", [missing])
    changed = copy.deepcopy(good)
    changed["image_description"] = corrected
    reject_before_calls("run_text_changed_after_load_zero_calls", [changed])
    invalid_second = copy.deepcopy(changed)
    invalid_second["id"] = "s2"
    reject_before_calls(
        "later_bad_item_rejects_entire_run_before_first_call", [copy.deepcopy(good), invalid_second]
    )
    img.write_bytes(PNG_BYTES + b"changed")
    reject_before_calls("run_image_changed_after_load_zero_calls", [copy.deepcopy(good)])
    img.write_bytes(PNG_BYTES)
    # Prompt safety remains conservative if stored description is later changed.
    sub = {
        "task_type": "task1",
        "prompt_text": item["prompt"],
        "essay_text": item["essay"],
        "word_count": 35,
        "target_band": 7.0,
        "image_status": "ready",
        "image_description": desc,
        "image_check": json.dumps(record),
    }
    check("valid_prompt_gate", prompts.visual_available(sub))
    check(
        "changed_text_prompt_gate_closed",
        not prompts.visual_available(dict(sub, image_description=corrected)),
    )
    check(
        "missing_hash_prompt_gate_closed",
        not prompts.visual_available(
            dict(
                sub,
                image_check=json.dumps({k: v for k, v in record.items() if k != "reading_sha256"}),
            )
        ),
    )
    # Audit metadata is excluded; actual final reading and valid/invalid state still differ.
    a = {"submission": sub}
    other = copy.deepcopy(record)
    other.update(by="Other", at="2026-11-15T00:00:00Z")
    b = {"submission": dict(sub, image_check=json.dumps(other))}
    check(
        "audit_metadata_does_not_change_fingerprint",
        realcheck_compare._fingerprint(a) == realcheck_compare._fingerprint(b),
    )
    c = {"submission": dict(sub, image_description=corrected, image_check=json.dumps(fc))}
    check(
        "changed_final_reading_changes_fingerprint",
        realcheck_compare._fingerprint(a) != realcheck_compare._fingerprint(c),
    )
    d = {"submission": dict(sub, image_check=None)}
    check(
        "confirmed_vs_unconfirmed_changes_fingerprint",
        realcheck_compare._fingerprint(a) != realcheck_compare._fingerprint(d),
    )
    # No-image task1 must be rejected when explicitly requiring checked images.
    noimg = dict(item)
    noimg.pop("image")
    try:
        realcheck.apply_image_descriptions([noimg], checkedfile, require_checked=True)
    except realcheck.RealCheckError:
        noimg_rejected = True
    else:
        noimg_rejected = False
    check("require_checked_missing_image_rejected", noimg_rejected)

out = Path(args.out)
out.parent.mkdir(parents=True, exist_ok=True)
report = {
    "source": str(Path(args.source).resolve()),
    "passed": sum(c["passed"] for c in checks),
    "total": len(checks),
    "checks": checks,
    "network_calls": 0,
    "scope": "Temporary synthetic image/essay, fake text model, no private files or keys.",
}
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(
    json.dumps(
        {
            "passed": report["passed"],
            "total": report["total"],
            "failed": [c["name"] for c in checks if not c["passed"]],
        }
    )
)
raise SystemExit(any(not c["passed"] for c in checks))
