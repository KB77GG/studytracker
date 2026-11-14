#!/usr/bin/env python3
"""Offline replay of saved responses; no client, settings, database or model calls.

Public output contains only hashes, IDs, paths, booleans and counts. Complete
normalised responses/diffs stay in --private-out (a separate ignored directory).
Run with the repository venv and -B. See --help for required input paths.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()
    ).hexdigest()


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data, private=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if private:
        path.parent.chmod(0o700)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    if private:
        path.chmod(0o600)


def block_network():
    attempts = []

    def blocked(*args, **kwargs):
        attempts.append(True)
        raise RuntimeError("Network disabled in offline replay")

    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.create_connection = blocked
    socket.getaddrinfo = blocked
    return attempts


def worker(args):
    attempts = block_network()
    sys.path.insert(0, str(args.source.resolve()))
    from tools.ielts_writing_ai import essay, prompts, review

    run = json.loads(args.run_data.read_text())
    calls = [json.loads(line) for line in args.raw_calls.read_text().splitlines()]
    by_id = {c["sample"]: c for c in calls}
    if len(by_id) != len(calls):
        raise ValueError("Replay expects one successful response per sample")
    outputs = []
    diagnostics = []
    for sample in run["samples"]:
        call = by_id[sample["id"]]
        assert call["ok"] and call["attempt"] == 0 and call["kind"] == "evaluate"
        submission = copy.deepcopy(sample["submission"])
        raw = json.loads(call["text"])
        before = digest({"submission": submission, "raw": raw})
        messages, context = prompts.build_evaluate(
            submission, essay.split_sentences(submission["essay_text"])
        )
        normalized = review.checked(review.normalize_evaluation, raw, submission)
        normalized["thinking"] = call["thinking"]
        reading = review.chart_reading_used(submission)
        if reading is not None:
            normalized["chart_reading"] = reading
        outputs.append(
            {
                "sample_id": sample["id"],
                "result": normalized,
                "messages": messages,
                "context": context,
                "input_sha256": digest(messages),
                "recorded_input_sha256": call["input_sha256"],
                "submission_sha256": digest(submission),
                "raw_sha256": digest(raw),
                "raw_and_submission_unchanged": before
                == digest({"submission": submission, "raw": raw}),
            }
        )
        if (
            sample["id"] == "official-1B-A#r2"
            and (args.source / "tools/ielts_writing_ai/conflicts.py").is_file()
        ):
            from tools.ielts_writing_ai import conflicts, figures

            task_raw = raw["criteria"]["task"]["issues"][1]
            task_normalized = normalized["criteria"][0]["issues"][1]
            language = normalized["criteria"][3]["issues"][1]
            sentences = conflicts._Sentences(submission["essay_text"])
            raw_values = conflicts.corrected_values(dict(task_raw, quote_found=True))
            diagnostics.append(
                {
                    "id": "L9",
                    "sample_id": sample["id"],
                    "task_raw_field": "criteria.task.issues[1]",
                    "language_field": "criteria.grammar.issues[1]",
                    "task_raw": task_raw,
                    "task_normalized": task_normalized,
                    "language_normalized": language,
                    "unsourced_in_task_suggestion": figures.for_submission(
                        submission, chart_checked=True
                    ).unsourced(task_raw["suggestion"]),
                    "raw_corrected_values": sorted(raw_values),
                    "normalized_corrected_values": sorted(
                        conflicts.corrected_values(task_normalized)
                    ),
                    "retained_corrected_values": sorted(
                        conflicts._values(language["suggestion"]) & raw_values
                    ),
                    "same_sentence": bool(
                        sentences.of(task_raw["quote"]) & sentences.of(language["quote"])
                    ),
                }
            )
    write_json(
        args.worker_out,
        {
            "prompt_version": prompts.PROMPT_VERSION,
            "network_attempts": len(attempts),
            "samples": outputs,
            "diagnostics_private": diagnostics,
        },
        private=True,
    )


def differences(old, new, path=""):
    if type(old) is not type(new):
        return [{"path": path, "old": old, "new": new}]
    if isinstance(old, dict):
        result = []
        for key in sorted(set(old) | set(new)):
            subpath = f"{path}.{key}" if path else key
            if key not in old or key not in new:
                result.append(
                    {
                        "path": subpath,
                        "old_present": key in old,
                        "new_present": key in new,
                        "old": old.get(key),
                        "new": new.get(key),
                    }
                )
            else:
                result.extend(differences(old[key], new[key], subpath))
        return result
    if isinstance(old, list):
        result = []
        for i in range(max(len(old), len(new))):
            subpath = f"{path}[{i}]"
            if i >= len(old) or i >= len(new):
                result.append(
                    {
                        "path": subpath,
                        "old_present": i < len(old),
                        "new_present": i < len(new),
                        "old": old[i] if i < len(old) else None,
                        "new": new[i] if i < len(new) else None,
                    }
                )
            else:
                result.extend(differences(old[i], new[i], subpath))
        return result
    return [] if old == new else [{"path": path, "old": old, "new": new}]


def tracked_sources(root):
    files = sorted((root / "tools/ielts_writing_ai").rglob("*"))
    return {
        str(p.relative_to(root)): file_sha(p)
        for p in files
        if p.is_file() and p.suffix in {".py", ".js", ".html", ".css"}
    }


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def entry(result, key, kind, index):
    return next(c for c in result["criteria"] if c["key"] == key)[kind][index]


def main(args):
    if args.private_out.resolve() == args.out.parent.resolve():
        raise ValueError("Private artifacts must be separate from public output")
    # Never permit full responses to become untracked public source files.
    ancestor = args.private_out.resolve()
    while not ancestor.exists():
        ancestor = ancestor.parent
    located = subprocess.run(
        ["git", "-C", str(ancestor), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if located.returncode == 0:
        ignored = subprocess.run(
            [
                "git",
                "-C",
                located.stdout.strip(),
                "check-ignore",
                "-q",
                str(args.private_out.resolve() / "private-marker"),
            ],
            check=False,
        )
        if ignored.returncode:
            raise ValueError("Private output inside a repository must be git-ignored")
    for root in (args.baseline, args.candidate):
        assert not git(root, "status", "--porcelain"), "Source tree is dirty"
    source_before = {
        key: tracked_sources(root)
        for key, root in (("baseline", args.baseline), ("candidate", args.candidate))
    }
    run_root = args.run_data.resolve().parent.parent
    input_before = {
        str(p.relative_to(run_root)): file_sha(p)
        for p in sorted(run_root.rglob("*"))
        if p.is_file()
    }
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "en_US.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    replay = {}
    for label, source in (("baseline", args.baseline), ("candidate", args.candidate)):
        output = args.private_out.resolve() / f"{label}.normalized.private.json"
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(Path(__file__).resolve()),
                "--worker",
                "--source",
                str(source.resolve()),
                "--run-data",
                str(args.run_data.resolve()),
                "--raw-calls",
                str(args.raw_calls.resolve()),
                "--worker-out",
                str(output),
            ],
            cwd=source,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        replay[label] = json.loads(output.read_text())
    baseline, candidate = replay["baseline"], replay["candidate"]
    run = json.loads(args.run_data.read_text())
    checks = []

    def check(name, ok):
        checks.append({"check": name, "ok": bool(ok)})

    check("eight_responses", len(run["samples"]) == 8)
    check("prompt_version_unchanged", baseline["prompt_version"] == candidate["prompt_version"])
    check(
        "network_attempts_zero", baseline["network_attempts"] == candidate["network_attempts"] == 0
    )
    rows, full_diffs, removed, retained = [], [], [], []
    for stored, old, new in zip(
        run["samples"], baseline["samples"], candidate["samples"], strict=True
    ):
        sid = stored["id"]
        check(f"{sid}:ids", sid == old["sample_id"] == new["sample_id"])
        check(f"{sid}:baseline_exact", old["result"] == stored["generations"]["evaluate"]["result"])
        check(f"{sid}:input_messages", old["messages"] == new["messages"])
        check(f"{sid}:prompt_context", old["context"] == new["context"])
        check(
            f"{sid}:recorded_message_hash",
            old["input_sha256"]
            == new["input_sha256"]
            == old["recorded_input_sha256"]
            == new["recorded_input_sha256"],
        )
        check(f"{sid}:submission_hash", old["submission_sha256"] == new["submission_sha256"])
        check(f"{sid}:raw_hash", old["raw_sha256"] == new["raw_sha256"])
        check(
            f"{sid}:inputs_not_mutated",
            old["raw_and_submission_unchanged"] and new["raw_and_submission_unchanged"],
        )
        o, n = old["result"], new["result"]
        check(f"{sid}:overall_band", o["overall_band"] == n["overall_band"])
        check(
            f"{sid}:criterion_bands",
            [c["band"] for c in o["criteria"]] == [c["band"] for c in n["criteria"]],
        )
        check(f"{sid}:task_criterion", o["criteria"][0] == n["criteria"][0])
        check(
            f"{sid}:source_number_removed_count",
            o["suggestions_removed"] == n["suggestions_removed"],
        )
        changed = differences(o, n)
        full_diffs.append({"sample_id": sid, "changes": changed})
        expected = copy.deepcopy(o)
        count = 0
        for ci, (oc, nc) in enumerate(zip(o["criteria"], n["criteria"], strict=True)):
            for ii, (oi, ni) in enumerate(zip(oc["issues"], nc["issues"], strict=True)):
                path = f"criteria[{ci}].issues[{ii}]"
                if oi.get("suggestion") and not ni.get("suggestion"):
                    count += 1
                    removed.append(
                        {
                            "sample_id": sid,
                            "path": path,
                            "criterion": oc["key"],
                            "old": oi,
                            "new": ni,
                        }
                    )
                    expected["criteria"][ci]["issues"][ii].update(
                        suggestion="", suggestion_removed=True, removed_reason="task_conflict"
                    )
                    check(
                        f"{sid}:{path}:removal_marked",
                        ni.get("removed_reason") == "task_conflict"
                        and ni.get("suggestion_removed"),
                    )
                    check(f"{sid}:{path}:comment_preserved", oi["comment"] == ni["comment"])
                elif oi.get("suggestion"):
                    retained.append({"sample_id": sid, "path": path})
                    check(f"{sid}:{path}:other_advice_unchanged", oi == ni)
        expected["task_conflicts"] = count
        if count:
            expected["warnings"].append(
                f"有 {count} 条语言方面的建议保留了 {o['criteria'][0]['short']} 部分已指出有误的数据，"
                f"建议已删去，评语保留；改写这些句子时，数据请按 {o['criteria'][0]['short']} 部分的改正修改。"
            )
        check(f"{sid}:only_documented_changes", n == expected)
        rows.append(
            {
                "sample_id": sid,
                "task_conflicts": n["task_conflicts"],
                "difference_paths": [x["path"] for x in changed],
                "old_sha256": digest(o),
                "new_sha256": digest(n),
                "message_sha256": new["input_sha256"],
            }
        )
    # Previously reviewed locations, identified by IDs/paths rather than private text.
    locations = [
        ("H1", 1, "lexical", "issues", 2, "warned_quote"),
        ("H2", 2, "coherence", "issues", 2, "previously_removed"),
        ("H3", 3, "coherence", "issues", 0, "comment_retained"),
        ("H4", 5, "task", "strengths", 2, "comment_retained"),
        ("L1", 0, "coherence", "issues", 0, "trend_retained"),
        ("L4", 3, "coherence", "issues", 1, "trend_retained"),
        ("L5", 3, "lexical", "issues", 0, "trend_retained"),
        ("L7", 5, "coherence", "issues", 0, "trend_retained"),
        ("L9", 5, "grammar", "issues", 1, "newly_removed"),
        ("L11", 6, "lexical", "issues", 3, "newly_removed"),
    ]
    finding_states = []
    for fid, sn, key, kind, ix, state in locations:
        o = entry(baseline["samples"][sn]["result"], key, kind, ix)
        n = entry(candidate["samples"][sn]["result"], key, kind, ix)
        if state == "newly_removed":
            ok = (
                bool(o.get("suggestion"))
                and not n["suggestion"]
                and n.get("removed_reason") == "task_conflict"
            )
        elif state == "warned_quote":
            ok = o == n and not n["quote_found"]
        elif state == "previously_removed":
            ok = o == n and n["suggestion_removed"] and not n["suggestion"]
        elif state == "trend_retained":
            ok = o == n and bool(n["suggestion"])
        else:
            ok = o == n and bool(n["comment"])
        check(f"finding:{fid}:{state}", ok)
        finding_states.append(
            {
                "id": fid,
                "sample_id": candidate["samples"][sn]["sample_id"],
                "field_path": f"criteria.{key}.{kind}[{ix}]",
                "expected_state": state,
                "ok": ok,
            }
        )
    input_after = {
        str(p.relative_to(run_root)): file_sha(p)
        for p in sorted(run_root.rglob("*"))
        if p.is_file()
    }
    check("closed_run_all_file_hashes_unchanged", input_before == input_after)
    for label, root in (("baseline", args.baseline), ("candidate", args.candidate)):
        check(f"{label}:product_hashes_unchanged", source_before[label] == tracked_sources(root))
        check(f"{label}:git_clean_after", not git(root, "status", "--porcelain"))
    private = {"full_diff": full_diffs, "newly_removed": removed, "other_retained_advice": retained}
    write_json(args.private_out / "diff.private.json", private, private=True)
    report = {
        "baseline_head": git(args.baseline, "rev-parse", "HEAD"),
        "candidate_head": git(args.candidate, "rev-parse", "HEAD"),
        "prompt_version": candidate["prompt_version"],
        "model_calls": 0,
        "network_attempts": 0,
        "checks_passed": sum(c["ok"] for c in checks),
        "checks_total": len(checks),
        "responses": rows,
        "new_removals": [{k: r[k] for k in ("sample_id", "path", "criterion")} for r in removed],
        "new_removals_count": len(removed),
        "other_retained_advice_count": len(retained),
        "finding_states": finding_states,
        "l9_diagnostic": [
            {
                "sample_id": x["sample_id"],
                "task_field": x["task_raw_field"],
                "language_field": x["language_field"],
                "raw_task_suggestion_present": bool(x["task_raw"]["suggestion"]),
                "normalized_task_suggestion_present": bool(x["task_normalized"]["suggestion"]),
                "task_suggestion_previously_filtered": x["task_normalized"]["suggestion_removed"],
                "unsourced_tokens_in_task_suggestion_count": len(x["unsourced_in_task_suggestion"]),
                "raw_corrected_value_count": len(x["raw_corrected_values"]),
                "normalized_corrected_value_count": len(x["normalized_corrected_values"]),
                "retained_corrected_value_count": len(x["retained_corrected_values"]),
                "same_sentence": x["same_sentence"],
            }
            for x in candidate["diagnostics_private"]
        ],
        "closed_run_file_count": len(input_before),
        "closed_run_manifest_sha256": digest(input_before),
        "run_data_sha256": file_sha(args.run_data),
        "raw_calls_sha256": file_sha(args.raw_calls),
        "source_manifest_sha256": {k: digest(v) for k, v in source_before.items()},
        "checks": checks,
        "limitations_zh": [
            "只回放本批已有八份回答，不新增模型评分，不代表教师审查或评分校准。",
            "新删除是否合理需结合私有原文、确认读数及完整差异逐项审阅；本脚本记录精确行为。",
            "趋势方向及模型评论判断按设计不在此数字规则覆盖内。",
            "旧已保存结果没有被重写；本次新归一化结果仅保存在本机私有目录。",
        ],
    }
    write_json(args.out, report)
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "checks_passed",
                    "checks_total",
                    "new_removals_count",
                    "other_retained_advice_count",
                    "model_calls",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if all(c["ok"] for c in checks) else 1


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path)
    p.add_argument("--candidate", type=Path)
    p.add_argument("--run-data", type=Path, required=True)
    p.add_argument("--raw-calls", type=Path, required=True)
    p.add_argument("--private-out", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--source", type=Path, help=argparse.SUPPRESS)
    p.add_argument("--worker-out", type=Path, help=argparse.SUPPRESS)
    a = p.parse_args()
    required = (
        ("source", "worker_out") if a.worker else ("baseline", "candidate", "private_out", "out")
    )
    for name in required:
        if getattr(a, name) is None:
            p.error(f"--{name.replace('_', '-')} is required")
    return a


if __name__ == "__main__":
    arguments = parse_args()
    if arguments.worker:
        worker(arguments)
    else:
        raise SystemExit(main(arguments))
