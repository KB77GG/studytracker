"""Read-only offline probe; no keys, network, or persistent trial data."""
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from tools.ielts_writing_ai import realcheck, review
from tools.ielts_writing_ai.llm import FakeClient, LLMError, LLMResult
from tools.ielts_writing_ai.tests.helpers import settings_for

fixtures = json.loads((REPO / "tools/ielts_writing_ai/tests/fixtures/realcheck_20261104.json").read_text())
raw_first = fixtures["rewrites"]["t2-mid"]["raw_text"]
raw_clean = json.loads(fixtures["rewrites"]["t2-weak"]["raw_text"])
raw_clean["band_rationale"] = "为了向 Band 7 目标靠近：重组段落，补充例子的解释，修正语法错误。"
raw_clean = json.dumps(raw_clean, ensure_ascii=False)

class SecondAttemptFailure(FakeClient):
    def __init__(self, error):
        super().__init__()
        self.error = error
        self.count = 0
    def complete(self, messages, **kwargs):
        self.count += 1
        if self.count == 1:
            return LLMResult(raw_first, self.model, 1, {})
        raise LLMError(self.error, "offline injected retry failure")

class OneGoodSixFailures(FakeClient):
    def __init__(self):
        super().__init__()
        self.count = 0
    def complete(self, messages, **kwargs):
        self.count += 1
        if self.count == 1:
            return LLMResult(raw_clean, self.model, 1, {})
        raise LLMError("truncated", "offline injected truncation")

result = {}
with tempfile.TemporaryDirectory(prefix="iwa-review-metrics-") as tmp:
    settings = settings_for(tmp)
    items = realcheck.load_samples("builtin")
    # Use t2-mid, matching the first candidate's transport prompt.
    item = next(s for s in items if s["id"] == "t2-mid")
    baseline = review.normalize_rewrite(json.loads(raw_first), fixtures["rewrites"]["t2-mid"]["submission"])
    result["first_candidate"] = {"word_count":baseline["word_count"], "quality_passed":baseline["quality_passed"], "quality_codes":[i["code"] for i in baseline["quality_issues"]]}
    result["retry_failure"] = {}
    for error in ("timeout", "truncated", "http_503"):
        client = SecondAttemptFailure(error)
        data = realcheck.run(settings, [item], client=client, kinds=("rewrite",), max_calls=42)
        generation = data["samples"][0]["generations"]["rewrite"]
        assert client.count == 2 and generation["status"] == "failed" and generation["result"] is None
        result["retry_failure"][error] = {"calls":client.count, "status":generation["status"], "error":generation["error_code"], "first_candidate_retained":False}
    client = SecondAttemptFailure("must_not_call_second")
    data = realcheck.run(settings, [item], client=client, kinds=("rewrite",), max_calls=1)
    generation = data["samples"][0]["generations"]["rewrite"]
    assert client.count == 1 and len(data["calls"]) == 1
    assert generation["status"] == "failed" and generation["error_code"] == "call_budget" and generation["result"] is None
    result["retry_failure"]["call_budget"] = {"actual_client_invocations":1, "recorded_calls":1, "status":generation["status"], "first_candidate_retained":False}
    data = realcheck.run(settings, items, client=OneGoodSixFailures(), kinds=("rewrite",), max_calls=42)
    report = realcheck.build_report(data)
    result["denominator"] = {"samples":len(data["samples"]), "ready":[s["id"] for s in data["samples"] if s["generations"]["rewrite"]["status"]=="ready"], "failed":[s["id"] for s in data["samples"] if s["generations"]["rewrite"]["status"]=="failed"], "final_ready":report["kinds"]["rewrite"]["final_ready"], "rewrite_quality_passed":report["refine_rewrite"]["rewrite_quality_passed"], "rewrites_denominator":report["refine_rewrite"]["rewrites"]}
    assert report["kinds"]["rewrite"]["final_ready"] == 0.143
    assert report["refine_rewrite"]["rewrite_quality_passed"] == 1.0
Path(__file__).with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
print(json.dumps(result, ensure_ascii=False, indent=2))
