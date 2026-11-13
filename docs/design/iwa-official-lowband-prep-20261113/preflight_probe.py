"""No-network preflight of the new official transcript workflow."""

import json
import socket
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path("/private/tmp/studytracker-iwa-holdout-review-20261111")
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.ielts_writing_ai import ledger, realcheck
from tools.ielts_writing_ai.config import load_settings
from tools.ielts_writing_ai.llm import FakeClient, LLMResult

source = subprocess.check_output(
    [
        "git",
        "show",
        "5134fdc3:docs/design/ielts-writing-ai-model-comparison-plan-20261110/fill_transcripts.py",
    ],
    cwd=ROOT,
    text=True,
)
mod = types.ModuleType("fill_review")
exec(compile(source, "remote-fill-transcripts.py", "exec"), mod.__dict__)
records = [
    ("1A", "A", 5, 9),
    ("1A", "B", 6, 10),
    ("1B", "A", 6, 11),
    ("1C", "A", 5, 13),
    ("2B", "A", 5.5, 23),
]
text = "前面的说明\n" + "\n\n".join(
    f"Task {task} · Script {script} · {score} 分（第 {page} 页）\n中文说明行\nThis sticy earth are [seilmens?] and 48–[77?] hours.\n\nIt’s impaction stays."
    for task, script, score, page in records
)
parsed = mod.parse(text)
assert list(parsed) == [f"official-{a}-{b}" for a, b, _, _ in records]
assert all(
    row["essay"] == "This sticy earth are seilmens and 48–77 hours.\nIt’s impaction stays."
    and len(row["notes"]) == 2
    for row in parsed.values()
)
try:
    mod.parse(text + "\nTask 1A · Script A · 5.0 分（第 9 页）\nBody")
except SystemExit:
    duplicate_rejected = True
else:
    duplicate_rejected = False
assert duplicate_rejected


class AlwaysInvalid(FakeClient):
    def complete(self, messages, **kwargs):
        return LLMResult("invalid", kwargs.get("model") or self.model, 1)


result = {
    "parser": {
        "five_ids_match": True,
        "chinese_notes_skipped": True,
        "uncertain_words_only_changed": True,
        "grammar_typography_kept": True,
        "duplicate_heading_rejected": True,
    },
    "paid_calls": 0,
}
with (
    tempfile.TemporaryDirectory(prefix="iwa-official-cap-") as tmp,
    patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")),
):
    p = Path(tmp)
    settings = load_settings(
        env={}, env_file="/nonexistent", data_dir=p / "unused", llm_provider="fake"
    )
    samples = realcheck.expand_repeats(realcheck.load_samples("builtin")[:1], 2)
    book = ledger.Ledger(
        p / "wide.jsonl",
        text_cap=20,
        vision_cap=0,
        run="official-t2",
        code_sha256=realcheck.code_fingerprint(),
        prompt_version=realcheck.review.prompts.PROMPT_VERSION,
    )
    per_run = []
    for _ in range(2):
        data = realcheck.run(
            settings, samples, kinds=("evaluate",), max_calls=4, client=AlwaysInvalid(), ledger=book
        )
        per_run.append(len(data["calls"]))
    total = book.check()["text"]["reserved"]
    assert per_run == [4, 4] and total == 8
    result["documented_a_command"] = {
        "process_cap": 4,
        "ledger_cap": 20,
        "per_run_calls": per_run,
        "cumulative_calls": total,
        "exceeds_authorized_4": True,
    }
    bounded = ledger.Ledger(
        p / "bounded.jsonl",
        text_cap=4,
        vision_cap=0,
        run="official-t2",
        code_sha256=realcheck.code_fingerprint(),
        prompt_version=realcheck.review.prompts.PROMPT_VERSION,
    )
    realcheck.run(
        settings, samples, kinds=("evaluate",), max_calls=4, client=AlwaysInvalid(), ledger=bounded
    )
    before = bounded.check()["text"]["reserved"]
    data = realcheck.run(
        settings, samples, kinds=("evaluate",), max_calls=4, client=AlwaysInvalid(), ledger=bounded
    )
    after = bounded.check()["text"]["reserved"]
    assert before == after == 4
    result["bounded_a"] = {
        "ledger_cap": 4,
        "before_retry": before,
        "after_retry": after,
        "new_calls": 0,
    }
    vpath = p / "vision-switch.jsonl"
    common = {
        "path": vpath,
        "text_cap": 20,
        "run": "probe",
        "code_sha256": "fixed",
        "prompt_version": "fixed",
    }
    ledger.Ledger(**common, vision_cap=0).check()
    enabled = ledger.Ledger(**common, vision_cap=4)
    enabled.reserve(sample="image", kind="describe_image", model="fake", attempt=1)
    disabled = ledger.Ledger(**common, vision_cap=0)
    disabled.reserve(sample="text", kind="evaluate", model="fake", attempt=1)
    result["vision_cap_0_4_0"] = {
        "works": True,
        "counts": {
            "vision": disabled.check()["vision"]["reserved"],
            "text": disabled.check()["text"]["reserved"],
        },
    }
(OUT / "preflight-evidence.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
