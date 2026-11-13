"""Independent .15 copied-token property and .14 migration checks, all synthetic.

Run with the project's venv; no credentials, private inputs or network.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for name in tuple(os.environ):
        if name.startswith("IWA_"):
            del os.environ[name]

    def denied(*_args, **_kwargs):
        raise RuntimeError("network forbidden during offline probe")

    socket.socket.connect = denied
    socket.create_connection = denied
    socket.getaddrinfo = denied
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.repo))
    from tools.ielts_writing_ai import essay, prompts, realcheck, storage

    checks = {}
    details = {}

    def check(name, value):
        checks[name] = bool(value)

    phrases = [
        "alpha don't beta.",
        "alpha don’t beta.",
        "alpha cost-effective beta.",
        "one state-of-the-art option.",
        "one x-12-y option.",
        "[alpha] (beta), gamma!",
        "a 2020/21 report.",
        "two x--y choices.",
        "[café] naïve façade.",
        "甲word乙 and test.",
        "before\r\n  don't cost-effective!\r\n after",
        "before\r  don’t 9-to-5!\r after",
    ]
    candidates = accepted = rejected = pair_accepted = 0
    boundary_errors = count_errors = overlap_errors = crashes = 0
    for raw in phrases:
        text = essay.normalize_newlines(raw)
        tokens = list(essay.WORD_RE.finditer(text))
        valid = {}
        for start in range(len(text)):
            for end in range(start + 1, len(text) + 1):
                quote = text[start:end].strip()
                if not quote or "\n" in quote or text.count(quote) != 1:
                    continue
                candidates += 1
                try:
                    result = essay.resolve_copied(raw, [{"quote": quote}])
                except ValueError:
                    rejected += 1
                    continue
                except Exception:
                    crashes += 1
                    continue
                accepted += 1
                begin = text.index(result[0]["text"])
                finish = begin + len(result[0]["text"])
                whole = {i for i, m in enumerate(tokens) if begin <= m.start() < m.end() <= finish}
                partial = any(
                    m.start() < begin < m.end() or m.start() < finish < m.end() for m in tokens
                )
                boundary_errors += int(partial)
                count_errors += int(essay.count_words(result[0]["text"]) != len(whole))
                valid[(begin, finish)] = (quote, whole)
        intervals = list(valid.items())
        for i, ((a, b), (qa, ta)) in enumerate(intervals):
            for (c, d), (qb, tb) in intervals[i + 1 :]:
                if a < d and c < b:
                    continue
                result = essay.resolve_copied(raw, [{"quote": qa}, {"quote": qb}])
                pair_accepted += 1
                overlap_errors += int(bool(ta & tb))
                count_errors += int(
                    sum(essay.count_words(v["text"]) for v in result) != len(ta | tb)
                )
    check("accepted_spans_never_split_word_tokens", boundary_errors == 0)
    check("accepted_counts_match_whole_original_tokens", count_errors == 0)
    check("disjoint_spans_never_count_same_token_twice", overlap_errors == 0)
    check("all_candidate_failures_are_value_errors", crashes == 0)
    check("exercise_accept_and_reject_paths", accepted > 0 and rejected > 0 and pair_accepted > 0)
    details["token_property"] = {
        "synthetic_essays": len(phrases),
        "candidate_spans": candidates,
        "accepted_spans": accepted,
        "rejected_spans": rejected,
        "accepted_disjoint_pairs": pair_accepted,
        "boundary_errors": boundary_errors,
        "count_errors": count_errors,
        "overlap_errors": overlap_errors,
        "unexpected_exceptions": crashes,
    }

    threshold_rows = []
    with tempfile.TemporaryDirectory(prefix="iwa-p15-whole-token-") as temp:
        for index, word in enumerate(["cost-effective", "don't", "don’t"], 1):
            text = f"A {word} plan works. " + " ".join(["item"] * 147)
            sample = {
                "id": "synthetic-whole-token",
                "task_type": "task1",
                "prompt": "Describe the synthetic chart.",
                "essay": text,
                "copied_from_question": [{"quote": word}],
                "copied_source": "Synthetic confirmed annotation",
            }
            path = Path(temp) / f"{index}.jsonl"
            path.write_text(json.dumps(sample) + "\n")
            loaded = realcheck.load_samples(str(path))[0]
            submission = {
                "task_type": "task1",
                "prompt_text": loaded["prompt"],
                "essay_text": loaded["essay"],
                "word_count": essay.count_words(loaded["essay"]),
                "target_band": 7.0,
                "image_status": "none",
                "image_description": None,
                "copied_spans": realcheck._copied_spans(loaded, loaded["essay"]),
            }
            messages, _ = prompts.build_evaluate(submission, essay.split_sentences(text))
            payload = json.JSONDecoder().raw_decode(messages[-1]["content"].split("\n", 1)[1])[0]
            counted = essay.confirmed_copies(submission)["words"]
            check(
                f"whole_token_{index}_151_to_150",
                submission["word_count"] == 151
                and counted == 1
                and payload["word_count_without_copied"] == 150,
            )
            check(
                f"whole_token_{index}_source_not_in_messages",
                sample["copied_source"] not in json.dumps(messages),
            )
            threshold_rows.append(
                {
                    "case": index,
                    "original_words": submission["word_count"],
                    "deducted": counted,
                    "payload_remaining": payload["word_count_without_copied"],
                }
            )
    details["whole_token_threshold"] = threshold_rows

    old_source = subprocess.check_output(
        ["git", "show", "cd82fc1b:tools/ielts_writing_ai/storage.py"], cwd=args.repo, text=True
    )
    schema = next(
        ast.literal_eval(node.value)
        for node in ast.parse(old_source).body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "SCHEMA" for t in node.targets)
    )
    with tempfile.TemporaryDirectory(prefix="iwa-p15-copy-") as temp:
        path = Path(temp) / "probe.sqlite3"
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            conn.executescript(schema)
            conn.execute("INSERT INTO iwa_meta VALUES ('schema_version','1')")
            conn.execute("INSERT INTO iwa_meta VALUES ('synthetic-marker','preserve')")
            conn.execute(
                "INSERT INTO trial_user VALUES (1,'synthetic','hash','hint',7,30,NULL,NULL,'2026-11-01',NULL)"
            )
            confirmed = json.dumps(
                {"spans": [{"p": 1, "text": "cost-effective"}], "source": "Synthetic source"}
            )
            conn.execute(
                "INSERT INTO submission VALUES (1,'synthetic',1,'task1','question',"
                "'cost-effective essay','digest',2,7.0,'x.png','image/png','ready',"
                "'chart values','keep diagnostic',?,'2026-11-01')",
                (confirmed,),
            )
            conn.execute(
                "INSERT INTO generation VALUES (1,1,'evaluate','ready','fake','fake',"
                "'old-version','{}',NULL,NULL,123,'{}','2026-11-01','2026-11-01','2026-11-01')"
            )
            conn.execute(
                "INSERT INTO usage_event VALUES (1,1,'2026-11-01','evaluate','2026-11-01')"
            )
            before = {
                table: [dict(row) for row in conn.execute("SELECT * FROM " + table)]
                for table in sorted(storage.OWN_TABLES)
            }
            old_columns = [dict(row) for row in conn.execute("PRAGMA table_info(submission)")]
        current = storage.Storage(path)
        current.init_schema()
        current.init_schema()
        with current.connect() as conn:
            after = {
                table: [dict(row) for row in conn.execute("SELECT * FROM " + table)]
                for table in sorted(storage.OWN_TABLES)
            }
            columns = [dict(row) for row in conn.execute("PRAGMA table_info(submission)")]
            foreign_keys = list(conn.execute("PRAGMA foreign_key_check"))
        new_columns = [v for v in columns if v["name"] not in {v["name"] for v in old_columns}]
        check(
            "migration_14_adds_only_image_check",
            len(new_columns) == 1 and new_columns[0]["name"] == "image_check",
        )
        check("migration_new_column_nullable", new_columns[0]["notnull"] == 0)
        check(
            "migration_old_column_contracts_unchanged",
            [v for v in columns if v["name"] != "image_check"] == old_columns,
        )
        check("migration_existing_row_unchecked", after["submission"][0].pop("image_check") is None)
        for table in before:
            check("migration_14_all_old_fields_unchanged_" + table, after[table] == before[table])
        check(
            "migration_preserves_confirmed_copy_count",
            essay.confirmed_copies(after["submission"][0])["words"] == 1,
        )
        check("migration_foreign_keys_valid", not foreign_keys)
        details["migration"] = {
            "baseline": "cd82fc1b",
            "starts": 2,
            "tables": len(before),
            "rows": sum(map(len, before.values())),
        }

    sources = ["essay.py", "storage.py", "prompts.py", "realcheck.py"]
    result = {
        "repo": str(args.repo),
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=args.repo, text=True
        ).strip(),
        "checks": checks,
        "details": details,
        "passed": sum(checks.values()),
        "total": len(checks),
        "failed": [k for k, v in checks.items() if not v],
        "source_sha256": {
            name: hashlib.sha256(
                (args.repo / "tools/ielts_writing_ai" / name).read_bytes()
            ).hexdigest()
            for name in sources
        },
        "scope": {
            "paid_calls": 0,
            "network_calls": 0,
            "env_files_read": 0,
            "private_inputs": 0,
            "product_modified": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: result[k] for k in ["passed", "total", "failed", "details"]}, ensure_ascii=False
        )
    )
    return int(bool(result["failed"]))


if __name__ == "__main__":
    raise SystemExit(main())
