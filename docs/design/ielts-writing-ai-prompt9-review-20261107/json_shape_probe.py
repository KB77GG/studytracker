"""Offline correct-behavior checks for prompt .9 JSON shape/diagnosis changes.

Only synthetic answers are used. No .env, saved model reasoning, sockets, databases,
or real model calls are needed. Legacy parsing observations are recorded separately
from .9 regression assertions, with their baseline provenance made explicit.
"""
from __future__ import annotations

import argparse
import ast
import copy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    output = Path(args.output).resolve()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(repo))

    from tools.ielts_writing_ai import essay, jsonshape, llm, prompts, review
    from tools.ielts_writing_ai.tests.test_review import evaluation, submission

    sub = submission(prompt_text="Should governments invest in public services?")
    nested = evaluation()
    flat = {**nested["criteria"], **{k: v for k, v in nested.items() if k != "criteria"}}
    checks: list[dict] = []
    observations: list[dict] = []

    def check(name: str, condition: bool, detail=None):
        checks.append({"name": name, "passed": bool(condition), "detail": detail})

    def accepts(value, source=sub):
        try:
            result = review.checked(review.normalize_evaluation, value, source)
            return True, result
        except review.InvalidOutput as error:
            return False, str(error)

    text_cases = [
        ("object", '{"a": 1}', True),
        ("json fence", '```json\n{"a": 1}\n```', True),
        ("bare fence", '```\n{"a": 1}\n```', True),
        ("prefix disclaimer", 'Example only: {"a": 1}', False),
        ("suffix disclaimer", '{"a": 1} example only', False),
        ("two objects", '{"a": 1}{"a": 2}', False),
        ("two fences", '```json\n{"a":1}\n```\n```json\n{"b":2}\n```', False),
        ("array", '[{"a":1}]', False),
        ("trailing comma", '{"a":1,}', False),
        ("missing brace", '{"a":{"b":1}', False),
        ("mismatched bracket", '{"a":[1,2}', False),
    ]
    for name, text, expected in text_cases:
        parsed = llm.parse_strict_json(text)
        check("strict: " + name, (parsed is not None) is expected)
        diagnosed = jsonshape.diagnose(text)
        check("diagnosis does not alter acceptance: " + name,
              (llm.parse_strict_json(text) is not None) is expected, diagnosed)

    for task_type, status in (("task2", "none"), ("task1", "none"), ("task1", "ready")):
        source = {**sub, "task_type": task_type, "image_status": status}
        a, b = accepts(nested, source), accepts(flat, source)
        check(f"flat/nested equivalent: {task_type}/{status}", a[0] and b[0] and a[1] == b[1])
        messages, _ = prompts.build_evaluate(source, essay.split_sentences(source["essay_text"]))
        system = messages[0]["content"]
        check(f"prompt flat root: {task_type}/{status}", '"criteria":' not in system and
              '"coherence": C, "lexical": C, "grammar": C' in system)
        root, homes = prompts.evaluate_shape(source)
        check(f"diagnostic root: {task_type}/{status}", set(root) == {
            *essay.CRITERIA, "argument" if task_type == "task2" else "comparisons",
            "overall_comment", "priorities"} and
            all(homes[k] == "criteria" for k in essay.CRITERIA))

    mixed = copy.deepcopy(flat)
    mixed["criteria"] = copy.deepcopy(nested["criteria"])
    valid, detail = accepts(mixed)
    check("reject two real groups of criteria", not valid, detail)
    mixed["criteria"] = {}
    check("reject flat with empty nested object", not accepts(mixed)[0])
    mixed = {"grammar": flat["grammar"], **nested}
    check("reject one flat criterion with complete legacy", not accepts(mixed)[0])
    for key in essay.CRITERIA:
        missing = copy.deepcopy(flat)
        del missing[key]
        check("reject missing scored criterion: " + key, not accepts(missing)[0])
        for wrong in (None, True, 6, "six", []):
            malformed = copy.deepcopy(flat)
            malformed[key] = wrong
            check(f"reject malformed criterion: {key}/{type(wrong).__name__}", not accepts(malformed)[0])
    for key in ("overall_comment", "priorities", "argument", "comparisons"):
        wrong_home = copy.deepcopy(flat)
        wrong_home["grammar"][key] = wrong_home.pop(key, [])
        valid, detail = accepts(wrong_home)
        check("reject misplaced root key: " + key, not valid and "放错了位置" in detail, detail)
    for wrong in (None, [], True, "not an object"):
        check("reject malformed root: " + type(wrong).__name__, not accepts(wrong)[0])

    root, homes = prompts.evaluate_shape(sub)
    invalids = [
        ('{"task":{"band":6,"argument":{}},"coherence":{}', "argument 被写进了 task 里面"),
        ('{"overall_comment":"x"},"priorities":["y"]}', "priorities 落在了 JSON 之外"),
        ('{"task":[1,2}', "括号不配对"),
        ('{"task":"unfinished', "字符串没有结束"),
    ]
    for index, (text, fragment) in enumerate(invalids):
        diagnosis = review.json_problem("evaluate", text, sub)
        check(f"specific diagnosis {index}", fragment in diagnosis, diagnosis)
        check(f"diagnosed answer stays rejected {index}", llm.parse_strict_json(text) is None)
    # Use json.dumps for exact escapes rather than hand-written malformed string syntax.
    escaped = json.dumps({"task": {"summary": 'text "argument": {', "band": 6}})[:-1]
    check("quoted key text not mistaken for a structural key",
          "argument 被写进" not in jsonshape.diagnose(escaped, root, homes))

    class ScriptedClient:
        provider, model = "offline_probe", "synthetic"

        def __init__(self, replies):
            self.replies = list(replies)
            self.messages = []

        def complete(self, messages, **_kwargs):
            self.messages.append(copy.deepcopy(messages))
            return llm.LLMResult(self.replies.pop(0), self.model, 0)

    def generate(replies, kind="evaluate"):
        client = ScriptedClient(replies)
        generator = review.Generator(None, SimpleNamespace(evaluate_thinking="off", llm_temperature=.2), client)
        try:
            value, _ = generator._generate_valid(kind, sub, essay.split_sentences(sub["essay_text"]))
            return client, True, value
        except review.InvalidOutput as error:
            return client, False, str(error)

    malformed = json.dumps(flat, ensure_ascii=False)[:-1]
    client, accepted, detail = generate([malformed, malformed])
    check("two malformed replies remain failed without repair", not accepted and len(client.messages) == 2, detail)
    check("retry receives structural diagnosis", "JSON 结构错误" in client.messages[1][-1]["content"])
    client, accepted, result = generate([malformed, json.dumps(flat, ensure_ascii=False)])
    check("clean second reply can succeed", accepted and result["overall_band"] == accepts(flat)[1]["overall_band"])
    original_diagnose = jsonshape.diagnose
    try:
        jsonshape.diagnose = lambda *_args, **_kw: json.dumps(flat, ensure_ascii=False)
        client, accepted, _ = generate([malformed, malformed])
        check("even valid JSON in diagnosis is not adopted", not accepted and len(client.messages) == 2)
    finally:
        jsonshape.diagnose = original_diagnose
    client, accepted, detail = generate(['{"essay": "incomplete', '{"essay": "incomplete'], "rewrite")
    check("rewrite diagnosis never repairs two malformed replies", not accepted and len(client.messages) == 2, detail)

    # Prove the strict parser itself did not change relative to the named baseline.
    baseline = subprocess.check_output(["git", "-C", str(repo), "show", "76214fe2:tools/ielts_writing_ai/llm.py"], text=True)
    def function_tree(source, name):
        return ast.dump(next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name), include_attributes=False)
    current = (repo / "tools/ielts_writing_ai/llm.py").read_text()
    same_parser = function_tree(baseline, "parse_strict_json") == function_tree(current, "parse_strict_json")
    check("strict parser unchanged against 76214fe2", same_parser)
    before_review = subprocess.check_output(["git", "-C", str(repo), "show", "76214fe2:tools/ielts_writing_ai/review.py"], text=True)
    now_review = (repo / "tools/ielts_writing_ai/review.py").read_text()
    check("text coercion helper unchanged against 76214fe2",
          function_tree(before_review, "_text") == function_tree(now_review, "_text"))

    # Existing permissive behaviors are observations, not correctness assertions.
    duplicate = '{"criteria":{},' + json.dumps(nested, ensure_ascii=False)[1:]
    parsed = llm.parse_strict_json(duplicate)
    accepted, result = accepts(parsed)
    observations.append({"name": "duplicate JSON key keeps its last value", "accepted": accepted,
                         "overall_band": result.get("overall_band") if accepted else None,
                         "provenance": "parse_strict_json AST unchanged; json.loads last-value behavior already existed in 76214fe2",
                         "new_regression": False})
    malformed_reason = copy.deepcopy(nested)
    malformed_reason["criteria"]["grammar"]["summary"] = {"reason": "论点清楚但展开不足，例子与观点之间缺少解释。"}
    accepted, result = accepts(malformed_reason)
    observations.append({"name": "mapping reason stringified by existing _text", "accepted": accepted,
                         "provenance": "_text and criterion summary path predate .9", "new_regression": False})
    null_legacy = copy.deepcopy(flat)
    null_legacy["criteria"] = None
    accepted, _ = accepts(null_legacy)
    observations.append({"name": "flat with null legacy marker", "accepted": accepted,
                         "impact": "no second set of criterion scores; null treated like absent marker", "new_shape_only": True})

    result = {
        "repo": str(repo),
        "source_head": subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(),
        "baseline": "76214fe2",
        "scope": "synthetic offline JSON shape/diagnosis only; no .env, model reasoning, network, or databases",
        "passed": sum(item["passed"] for item in checks), "total": len(checks),
        "checks": checks, "non_regression_observations": observations,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "total": result["total"], "output": str(output),
                      "failed_checks": [c for c in checks if not c["passed"]]}, ensure_ascii=False))
    return 0 if all(item["passed"] for item in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
