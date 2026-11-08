"""Offline correct-behavior checks for prompt .10 JSON examples, shape, and diagnosis changes.

Only synthetic answers are used. No .env, saved model reasoning, sockets, databases,
or real model calls are needed. Legacy parsing observations are recorded separately
from regression assertions, with their baseline provenance made explicit.
"""
from __future__ import annotations

import argparse
import ast
import copy
import json
import logging
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
    logging.getLogger("iwa.review").disabled = True
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
        example = prompts.evaluate_example(task_type, prompts.visual_available(source))
        check(f"prompt complete nested root: {task_type}/{status}",
              json.dumps(example, ensure_ascii=False) in system and
              "sit next to criteria, never inside it" in system)
        root, homes = prompts.evaluate_shape(source)
        check(f"diagnostic root: {task_type}/{status}", set(root) == {
            "criteria", *essay.CRITERIA, "argument" if task_type == "task2" else "comparisons",
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

    def generate(replies, kind="evaluate", source=sub):
        client = ScriptedClient(replies)
        generator = review.Generator(None, SimpleNamespace(evaluate_thinking="off", llm_temperature=.2), client)
        try:
            value, _ = generator._generate_valid(kind, source, essay.split_sentences(source["essay_text"]))
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
    baseline = subprocess.check_output(["git", "-C", str(repo), "show", "46220092:tools/ielts_writing_ai/llm.py"], text=True)
    def function_tree(source, name):
        return ast.dump(next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name), include_attributes=False)
    current = (repo / "tools/ielts_writing_ai/llm.py").read_text()
    same_parser = function_tree(baseline, "parse_strict_json") == function_tree(current, "parse_strict_json")
    check("strict parser unchanged against 46220092", same_parser)
    before_review = subprocess.check_output(["git", "-C", str(repo), "show", "46220092:tools/ielts_writing_ai/review.py"], text=True)
    now_review = (repo / "tools/ielts_writing_ai/review.py").read_text()
    check("text coercion helper unchanged against 46220092",
          function_tree(before_review, "_text") == function_tree(now_review, "_text"))

    # Existing permissive behaviors are observations, not correctness assertions.
    duplicate = '{"criteria":{},' + json.dumps(nested, ensure_ascii=False)[1:]
    parsed = llm.parse_strict_json(duplicate)
    accepted, result = accepts(parsed)
    observations.append({"name": "duplicate JSON key keeps its last value", "accepted": accepted,
                         "overall_band": result.get("overall_band") if accepted else None,
                         "provenance": "parse_strict_json AST unchanged; json.loads last-value behavior already existed in 46220092",
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

    legacy_check_count = len(checks)
    # These retain the 82 previous behavior checks. The three prompt/root pairs are
    # adapted to .10's intentional contract: complete nested example + criteria root.
    contract_adaptations = [
        {"context": f"{task}/{status}",
         "before": ["prompt contains flat-only C shorthand", "diagnostic root excludes criteria"],
         "now": ["prompt embeds complete nested JSON", "diagnostic root supports criteria plus flat fields"]}
        for task, status in (("task2", "none"), ("task1", "none"), ("task1", "ready"))
    ]

    # New .10 examples must be tested through the production task context and full
    # normalizer: parsing an example is expected to succeed, scoring it is not.
    contexts = []
    for task_type, status in (("task2", "none"), ("task1", "none"), ("task1", "ready")):
        source = {**sub, "task_type": task_type, "image_status": status}
        if status == "ready":
            source["image_description"] = "Synthetic bar chart: A 10, B 20, C 30; C is highest."
        name = f"{task_type}/{status}"
        visual = prompts.visual_available(source)
        example = prompts.evaluate_example(task_type, visual)
        shown = json.dumps(example, ensure_ascii=False)
        messages, _ = prompts.build_evaluate(source, essay.split_sentences(source["essay_text"]))
        system = messages[0]["content"]
        expected_keys = {"criteria", "argument" if task_type == "task2" else "comparisons",
                         "overall_comment", "priorities"}
        check("example is one exact parseable object: " + name,
              llm.parse_strict_json(shown) == example and system.count(shown) == 1)
        check("example root and criterion keys: " + name,
              set(example) == expected_keys and list(example["criteria"]) == list(essay.CRITERIA))
        check("example task availability comes from production context: " + name,
              (example["criteria"]["task"] is None) == (task_type == "task1" and status != "ready"))
        check("example scored objects have full fields and invalid sentinel bands: " + name,
              all(set(item) == {"band", "summary", "strengths", "issues"} and
                  item["band"] == -1 and essay.snap_band(item["band"]) is None
                  for item in example["criteria"].values() if item is not None))
        check("prompt explains object fields and 3-5 priorities: " + name,
              "never a bare number" in system and "priorities = [str (Chinese), ...3-5" in system)
        valid, why = accepts(llm.parse_strict_json(shown), source)
        check("copied example cannot score: " + name, not valid and "分数无效" in why, why)
        bands_fixed = copy.deepcopy(example)
        for item in bands_fixed["criteria"].values():
            if item is not None:
                item["band"] = 6.0
        valid, why = accepts(llm.parse_strict_json(json.dumps(bands_fixed)), source)
        check("only fixing example bands cannot score: " + name, not valid, why)
        # Ensure a reason length gate cannot hide whether placeholder evidence works.
        reasons_fixed = copy.deepcopy(bands_fixed)
        for item in reasons_fixed["criteria"].values():
            if item is not None:
                item["summary"] = nested["criteria"]["task"]["summary"]
        valid, why = accepts(reasons_fixed, source)
        check("placeholder quotes fail evidence after valid bands/reasons: " + name,
              not valid and "没有任何能在原文中找到的证据" in why, why)

        filled = copy.deepcopy(example)
        for key in essay.CRITERIA:
            if filled["criteria"][key] is not None:
                filled["criteria"][key] = copy.deepcopy(nested["criteria"][key])
        filled["overall_comment"] = nested["overall_comment"]
        filled["priorities"] = ["解释论点与例子之间的联系", "纠正主谓一致和大小写", "检查段落之间的衔接"]
        if task_type == "task2":
            filled["argument"] = copy.deepcopy(nested["argument"])
        else:
            filled["comparisons"] = []
        valid, normalized = accepts(filled, source)
        check("filled nested example positive control: " + name, valid)
        check("filled example assessability/overall control: " + name,
              valid and ((normalized["overall_band"] is None) == (not visual)))
        flat_filled = {**filled["criteria"], **{k: v for k, v in filled.items() if k != "criteria"}}
        valid_flat, flat_result = accepts(flat_filled, source)
        check("filled flat/nested equality: " + name,
              valid and valid_flat and normalized == flat_result)
        for variant_name, variant in (("raw", example), ("bands only", bands_fixed)):
            reply = json.dumps(variant, ensure_ascii=False)
            client, accepted, why = generate([reply, reply], source=source)
            check("generator rejects two copied examples: " + name + "/" + variant_name,
                  not accepted and len(client.messages) == 2, why)
        client, accepted, value = generate([shown, json.dumps(filled, ensure_ascii=False)], source=source)
        check("generator recovers with populated second example: " + name,
              accepted and len(client.messages) == 2 and value["overall_band"] == normalized["overall_band"])
        client, accepted, value = generate(["```json\n" + json.dumps(filled, ensure_ascii=False) + "\n```"], source=source)
        check("single fenced populated example positive control: " + name,
              accepted and len(client.messages) == 1)
        contexts.append((name, source, filled, flat_filled))

    # Every assessable bare numeric criterion fails with the precise field label;
    # Task 1 unavailable TA is deliberately discarded before validation.
    for name, source, filled, flat_filled in contexts:
        for form, value in (("nested", filled), ("flat", flat_filled)):
            for key in essay.CRITERIA:
                if key == "task" and not prompts.visual_available(source):
                    continue
                malformed = copy.deepcopy(value)
                bucket = malformed["criteria"] if form == "nested" else malformed
                bucket[key] = 7.0
                valid, why = accepts(malformed, source)
                label = essay.CRITERION_SHORT[source["task_type"]][key]
                check(f"bare numeric precise rejection: {name}/{form}/{key}",
                      not valid and f"评分项 {label} 写成了数字 7.0" in why and
                      "band、summary、strengths、issues" in why, why)
            malformed = copy.deepcopy(value)
            bucket = malformed["criteria"] if form == "nested" else malformed
            for key in essay.CRITERIA:
                bucket[key] = 7.0
            text = json.dumps(malformed, ensure_ascii=False)
            client, accepted, why = generate([text, text], source=source)
            check(f"two bare-number replies never score: {name}/{form}",
                  not accepted and len(client.messages) == 2 and "写成了数字 7.0" in why, why)
            check(f"numeric rejection forwarded to retry: {name}/{form}",
                  "写成了数字 7.0" in client.messages[1][-1]["content"] and
                  "band、summary、strengths、issues" in client.messages[1][-1]["content"])
            client, accepted, _ = generate([text, json.dumps(value, ensure_ascii=False)], source=source)
            check(f"numeric rejection accepts corrected retry: {name}/{form}",
                  accepted and len(client.messages) == 2)
        if not prompts.visual_available(source):
            only_task_numeric = copy.deepcopy(filled)
            only_task_numeric["criteria"]["task"] = 9.0
            valid, result = accepts(only_task_numeric, source)
            check("unavailable Task1 ignores model TA but gives no TA/overall",
                  valid and result["criteria"][0]["state"] == "not_assessable" and
                  result["criteria"][0]["band"] is None and result["overall_band"] is None)

    # Final-content parsing is still strict along the model generation path.
    # A malformed response may be diagnosed/retried, never repaired or adopted.
    for kind in ("evaluate", "refine", "rewrite"):
        base_reply = json.dumps(flat, ensure_ascii=False) if kind == "evaluate" else '{"sentences":[],"essay":"synthetic"}'
        for label, bad in (("prose+JSON", "I cannot assess this; example only: " + base_reply),
                           ("fence+prose", "```json\n" + base_reply + "\n```\nExample only.")):
            client, accepted, why = generate([bad, bad], kind)
            check(f"strict model path rejects {label}: {kind}",
                  not accepted and len(client.messages) == 2, why)
    check("parser and fence rule module unchanged from baseline",
          subprocess.check_output(["git", "-C", str(repo), "diff", "46220092", "--", "tools/ielts_writing_ai/llm.py"], text=True) == "")

    result = {
        "repo": str(repo),
        "source_head": subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(),
        "baseline": "46220092",
        "scope": "synthetic offline JSON examples/shape/diagnosis only; no .env, model reasoning, network, or databases",
        "legacy_contract_checks": legacy_check_count,
        "contract_adaptations": contract_adaptations,
        "new_prompt10_checks": len(checks) - legacy_check_count,
        "limitations": ["No real-model acceptance-rate or IELTS scoring calibration measured", "Task1 ready context is synthetic; vision sufficiency gate is outside this probe"],
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
