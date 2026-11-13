"""Adapted copy (2026-11-13, .15): the reviewer's original compares migrated rows after
removing only the copied_spans column; .15 adds a second nullable column, image_check,
which must also be present once and empty on old rows. Everything else is unchanged.

Offline .14 confirmed-copy review; no credentials, network or real model.

Private official text is read only in memory, and only counts/check outcomes leave
that section. All persisted test databases contain synthetic text. Exit 1 means an
expected validation/property check failed, not that a paid/model request failed.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--private-sample", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))
    from tools.ielts_writing_ai import (
        access,
        create_app,
        essay,
        prompts,
        realcheck,
        review,
        storage,
    )
    from tools.ielts_writing_ai.llm import FakeClient
    from tools.ielts_writing_ai.tests.helpers import settings_for
    from tools.ielts_writing_ai.tests.test_copied_question_20261113 import FULL_T1, QUESTION_T1

    checks, detail, findings = [], {}, []

    def check(name, passed, **extra):
        checks.append({"name": name, "passed": bool(passed), **extra})

    def sub(text, *, task="task2", question="Discuss the benefits of city parks.", copied=None):
        return {
            "task_type": task,
            "prompt_text": question,
            "essay_text": text,
            "word_count": essay.count_words(text),
            "target_band": 7.0,
            "image_status": "none",
            "copied_spans": copied,
        }

    def payload(record):
        messages, context = prompts.build_evaluate(
            record, essay.split_sentences(record["essay_text"])
        )
        data = json.JSONDecoder().raw_decode(messages[1]["content"].split("\n", 1)[1])[0]
        return data, messages, context

    def stored(text, entries, source="Synthetic reviewer confirmed this passage."):
        return json.dumps({"spans": essay.resolve_copied(text, entries), "source": source})

    class Recording(FakeClient):
        def __init__(self):
            super().__init__()
            self.messages = []

        def complete(self, messages, **kwargs):
            self.messages.append(messages)
            return super().complete(messages, **kwargs)

    def deny_network(*_a, **_k):
        raise AssertionError("offline probe: network forbidden")

    with (
        patch.object(socket.socket, "connect", deny_network),
        patch.object(socket, "create_connection", deny_network),
        tempfile.TemporaryDirectory(prefix="iwa-confirmed-review-") as temporary,
    ):
        tmp = Path(temporary)
        original = sub(FULL_T1, task="task1", question=QUESTION_T1)
        data, messages, context = payload(original)
        normalized = review.normalize_evaluation(FakeClient._evaluate(context), original)
        check(
            "152_word_false_positive_no_longer_deducted",
            original["word_count"] == 152 and "word_count_without_copied" not in data,
        )
        check(
            "similarity_not_sent_as_confirmed",
            "copied_from_question" not in data and "copied_note" not in data,
        )
        check(
            "similarity_is_page_hint_only",
            normalized["copied_from_question"] == []
            and normalized["similar_to_question"] == [{"p": 2, "words": 14}],
        )
        check(
            "152_word_page_no_below_150_warning",
            all("低于 150" not in w for w in normalized["warnings"]),
        )
        check(
            "152_word_page_explicit_no_deduction",
            any("本工具没有因此扣字数" in w for w in normalized["warnings"]),
        )
        detail["prior_false_positive"] = {
            "words": original["word_count"],
            "confirmed_words": 0,
            "similar_words": 14,
            "payload_has_deducted_count": "word_count_without_copied" in data,
        }

        text = "First paragraph has original words.\r\n\r\n  Second paragraph contains a chosen passage.\rThird paragraph ends here."
        entries = [{"paragraph": 3}, {"quote": "chosen passage."}]
        resolved = essay.resolve_copied(text, entries)
        check(
            "normalized_line_endings_and_sorted_spans",
            resolved
            == [
                {"p": 2, "text": "chosen passage."},
                {"p": 3, "text": "Third paragraph ends here."},
            ],
        )
        invalid = {
            "empty": [],
            "not_list": {"paragraph": 1},
            "negative": [{"paragraph": -1}],
            "zero": [{"paragraph": 0}],
            "beyond_end": [{"paragraph": 4}],
            "bool": [{"paragraph": True}],
            "float": [{"paragraph": 1.0}],
            "string": [{"paragraph": "1"}],
            "absent": [{"quote": "not present"}],
            "duplicate_quote": [{"quote": "paragraph"}],
            "cross_paragraph": [{"quote": "words.\n\n  Second"}],
            "midword_start": [{"quote": "econd"}],
            "midword_end": [{"quote": "Secon"}],
            "space": [{"quote": " "}],
            "duplicate_paragraph": [{"paragraph": 1}, {"paragraph": 1}],
            "paragraph_quote_overlap": [{"paragraph": 2}, {"quote": "chosen passage."}],
            "quote_quote_overlap": [{"quote": "Second paragraph"}, {"quote": "paragraph contains"}],
            "ambiguous_entry": [{"paragraph": 1, "quote": "First"}],
            "extra_key": [{"paragraph": 1, "irrelevant": 0}],
            "nondict": [1],
            "unknown_key": [{"span": [0, 20]}],
            "quote_nonstr": [{"quote": 1}],
        }
        for name, value in invalid.items():
            try:
                essay.resolve_copied(text, value)
            except ValueError:
                check("resolve_reject_" + name, True)
            else:
                check("resolve_reject_" + name, False)

        sample = {
            "id": "synthetic",
            "task_type": "task2",
            "prompt": "Discuss city park funding.",
            "essay": essay.normalize_newlines(text),
        }
        sample_path = tmp / "sample.jsonl"

        def load_extra(extra):
            sample_path.write_text("\n" + json.dumps({**sample, **extra}) + "\n", encoding="utf-8")
            return realcheck.load_samples(str(sample_path))

        invalid_metadata = {
            "missing_basis": {"copied_from_question": [{"paragraph": 1}]},
            "missing_span": {"copied_source": "reviewer"},
            "empty_basis": {"copied_from_question": [{"paragraph": 1}], "copied_source": " \t"},
            "long_basis": {"copied_from_question": [{"paragraph": 1}], "copied_source": "x" * 201},
            "nonstr_basis": {"copied_from_question": [{"paragraph": 1}], "copied_source": 5},
            "bad_span": {"copied_from_question": [{"paragraph": 4}], "copied_source": "reviewer"},
            "mismatched_quote": {
                "copied_from_question": [{"quote": "missing"}],
                "copied_source": "reviewer",
            },
            "overlap": {
                "copied_from_question": [{"paragraph": 1}, {"quote": "First"}],
                "copied_source": "reviewer",
            },
        }
        for name, extra in invalid_metadata.items():
            try:
                load_extra(extra)
            except realcheck.RealCheckError as exc:
                check("load_reject_" + name, "第 2 行" in str(exc))
            else:
                check("load_reject_" + name, False)
        for basis_length in (1, 200):
            check(
                "basis_length_" + str(basis_length),
                len(
                    load_extra(
                        {
                            "copied_from_question": [{"paragraph": 1}],
                            "copied_source": "x" * basis_length,
                        }
                    )
                )
                == 1,
            )

        basis = "LOCAL CONFIRMATION BASIS NEVER SENT"
        valid = load_extra(
            {
                "copied_from_question": [{"paragraph": 1}, {"quote": "chosen passage."}],
                "copied_source": basis,
            }
        )
        client = Recording()
        result = realcheck.run(
            settings_for(str(tmp / "fake-run")), valid, client=client, kinds=("evaluate",)
        )
        saved = result["samples"][0]["submission"]
        resolved_data = json.loads(saved["copied_spans"])
        sent = json.JSONDecoder().raw_decode(client.messages[0][1]["content"].split("\n", 1)[1])[0]
        check(
            "realcheck_confirmed_spans_persist_and_export",
            resolved_data["source"] == basis and len(resolved_data["spans"]) == 2,
        )
        check(
            "realcheck_confirmed_text_reaches_payload",
            sent["copied_from_question"] == resolved_data["spans"],
        )
        check(
            "realcheck_count_matches_selected_words",
            sent["word_count_without_copied"] == saved["word_count"] - 7,
        )
        check("confirmation_basis_does_not_reach_model", basis not in json.dumps(client.messages))
        detail["realcheck"] = {
            "fake_calls": len(client.calls),
            "confirmed_words": 7,
            "original_words": saved["word_count"],
            "remaining_words": sent["word_count_without_copied"],
        }

        private_bytes = args.private_sample.read_bytes()
        official_rows = [
            json.loads(line) for line in private_bytes.decode("utf-8").splitlines() if line.strip()
        ]
        official = next(r for r in official_rows if r["id"] == "official-2B-A")
        official_text = essay.normalize_newlines(official["essay"]).strip()
        official_spans = [{"paragraph": 1}, {"paragraph": 2}]
        official_record = sub(
            official_text,
            question=official["prompt"],
            copied=stored(official_text, official_spans, "Official examiner comment, local audit."),
        )
        official_data, _, _ = payload(official_record)
        confirmed = essay.confirmed_copies(official_record)
        check("official_original_is_228_words", official_record["word_count"] == 228)
        check("official_first_two_paragraphs_are_34_words", confirmed["words"] == 34)
        check("official_payload_own_words_194", official_data["word_count_without_copied"] == 194)
        check(
            "official_payload_contains_exact_two_confirmed_paragraphs",
            [x["p"] for x in official_data["copied_from_question"]] == [1, 2]
            and [x["text"] for x in official_data["copied_from_question"]]
            == essay.split_paragraphs(official_text)[:2],
        )
        check("private_sample_unchanged", args.private_sample.read_bytes() == private_bytes)
        detail["official"] = {
            "sample_id": "official-2B-A",
            "input_sha256": hashlib.sha256(private_bytes).hexdigest(),
            "original_words": official_record["word_count"],
            "confirmed_paragraphs": [1, 2],
            "confirmed_words": confirmed["words"],
            "remaining_words": official_data["word_count_without_copied"],
            "metadata_added_in_memory_only": True,
        }

        web_client = Recording()
        app = create_app(settings_for(str(tmp / "web")), client=web_client)
        try:
            store = app.extensions["iwa"].storage
            uid = store.create_user(
                name="Synthetic probe user",
                code_hash=access.hash_code("probe-only-code"),
                code_hint="probe",
                daily_limit=100,
            )
            browser = app.test_client()
            page = browser.get("/login").get_data(as_text=True)
            csrf = re.search(r'data-csrf="([^"]+)"', page).group(1)
            login = browser.post(
                "/api/login", json={"code": "probe-only-code"}, headers={"X-IWA-CSRF": csrf}
            )
            csrf = login.get_json()["csrf"]
            fake_confirm = stored(FULL_T1, [{"paragraph": 2}], "Forged web source")
            response = browser.post(
                "/api/submissions",
                data={
                    "task_type": "task1",
                    "prompt_text": QUESTION_T1,
                    "essay_text": FULL_T1,
                    "target_band": "7.0",
                    "copied_spans": fake_confirm,
                    "copied_from_question": json.dumps([{"paragraph": 2}]),
                    "copied_source": "Forged web source",
                },
                headers={"X-IWA-CSRF": csrf},
                content_type="multipart/form-data",
            )
            check("forged_web_submission_accepted_as_plain_text", response.status_code == 201)
            with store.connect() as conn:
                record = dict(
                    conn.execute("SELECT * FROM submission WHERE user_id=?", (uid,)).fetchone()
                )
            check("web_does_not_store_forged_confirmation", record["copied_spans"] is None)
            check(
                "web_does_not_send_forged_confirmation",
                all(
                    "Forged web source" not in json.dumps(m)
                    and '"copied_from_question"'
                    not in json.dumps(m, ensure_ascii=False).replace('\\"', '"')
                    for m in web_client.messages
                ),
            )
            check("web_original_word_count_retained", record["word_count"] == 152)
        finally:
            app.extensions["iwa"].close()

        old_source = subprocess.check_output(
            ["git", "show", "f46756f8:tools/ielts_writing_ai/storage.py"], cwd=repo, text=True
        )
        old_schema = next(
            ast.literal_eval(node.value)
            for node in ast.parse(old_source).body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "SCHEMA" for t in node.targets)
        )
        db = tmp / "legacy.sqlite3"
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        conn.executescript(old_schema)
        conn.execute("INSERT INTO iwa_meta VALUES ('schema_version','1')")
        conn.execute("INSERT INTO iwa_meta VALUES ('probe-marker','keep')")
        conn.execute(
            "INSERT INTO trial_user VALUES (1,'synthetic','hash','hint',3,30,'2027-01-01',NULL,'2026-11-01','2026-11-02')"
        )
        conn.execute(
            "INSERT INTO submission VALUES (1,'legacy',1,'task1','synthetic question','synthetic essay','digest',2,7.0,'synthetic.png','image/png','ready','synthetic description','retained error','2026-11-01')"
        )
        conn.execute(
            "INSERT INTO generation VALUES (1,1,'evaluate','ready','fake','fake','legacy','{\"result\":1}',NULL,NULL,123,'{\"tokens\":8}','2026-11-01','2026-11-01','2026-11-01')"
        )
        conn.execute("INSERT INTO usage_event VALUES (1,1,'2026-11-01','evaluate','2026-11-01')")
        conn.commit()
        before = {
            t: [dict(r) for r in conn.execute("SELECT * FROM " + t)]
            for t in sorted(storage.OWN_TABLES)
        }
        conn.close()
        migrated = storage.Storage(db)
        migrated.init_schema()
        migrated.init_schema()
        with migrated.connect() as conn:
            after = {
                t: [dict(r) for r in conn.execute("SELECT * FROM " + t)]
                for t in sorted(storage.OWN_TABLES)
            }
            columns = [r["name"] for r in conn.execute("PRAGMA table_info(submission)")]
            fk = list(conn.execute("PRAGMA foreign_key_check"))
        check(
            "migration_adds_one_nullable_column",
            columns.count("copied_spans") == 1
            and after["submission"][0].pop("copied_spans") is None
            # .15 adds a second nullable column; old rows must have it empty too.
            and columns.count("image_check") == 1
            and after["submission"][0].pop("image_check") is None,
        )
        for table in before:
            check("migration_preserves_every_field_" + table, before[table] == after[table])
        check("migration_foreign_keys_intact", not fk)
        detail["migration"] = {
            "source_revision": "f46756f8",
            "tables_compared": len(before),
            "seeded_rows": sum(map(len, before.values())),
            "starts": 2,
            "old_fields_equal": before == after,
        }

        # Whole-word validation must agree with WORD_RE, which treats these as one
        # word. Otherwise disjoint character spans silently double-count that word.
        boundary_cases = {
            "ascii_apostrophe": ("don't", ["don", "t"]),
            "curly_apostrophe": ("don’t", ["don", "t"]),
            "hyphenated_word": ("cost-effective", ["cost", "effective"]),
        }
        boundary = []
        for name, (compound, fragments) in boundary_cases.items():
            probe_essay = "The " + compound + " approach is useful."
            check(
                "whole_compound_valid_" + name,
                essay.resolve_copied(probe_essay, [{"quote": compound}])
                == [{"p": 1, "text": compound}],
            )
            for fragment in fragments:
                try:
                    essay.resolve_copied(probe_essay, [{"quote": fragment}])
                except ValueError:
                    check("reject_partial_word_" + name + "_" + fragment, True)
                else:
                    check("reject_partial_word_" + name + "_" + fragment, False)
            malformed = {
                "id": name,
                "task_type": "task2",
                "prompt": "Discuss whether this is useful.",
                "essay": probe_essay,
                "copied_from_question": [{"quote": f} for f in fragments],
                "copied_source": "Synthetic reviewer annotation",
            }
            sample_path.write_text(json.dumps(malformed) + "\n", encoding="utf-8")
            try:
                loaded = realcheck.load_samples(str(sample_path))
            except realcheck.RealCheckError:
                check("loader_rejects_split_token_" + name, True)
                boundary.append({"case": name, "rejected": True})
            else:
                check("loader_rejects_split_token_" + name, False)
                stored_spans = realcheck._copied_spans(loaded[0], probe_essay)
                bad_record = sub(probe_essay, copied=stored_spans)
                bad_payload, _, _ = payload(bad_record)
                counted = essay.confirmed_copies(bad_record)["words"]
                boundary.append(
                    {
                        "case": name,
                        "rejected": False,
                        "synthetic_essay": probe_essay,
                        "submitted_fragments": fragments,
                        "whole_compound_word_count": essay.count_words(compound),
                        "deducted_word_count": counted,
                        "original_words": bad_record["word_count"],
                        "payload_remaining_words": bad_payload["word_count_without_copied"],
                    }
                )
        detail["token_boundary"] = boundary
        if any(not row["rejected"] for row in boundary):
            threshold_text = "A cost-effective plan works. " + " ".join(["item"] * 147)
            threshold_sample = {
                "id": "split-token-threshold",
                "task_type": "task1",
                "prompt": "The chart compares spending on a cost-effective plan over time.",
                "essay": threshold_text,
                "copied_from_question": [{"quote": "cost"}, {"quote": "effective"}],
                "copied_source": "Synthetic annotation for boundary regression",
            }
            sample_path.write_text(json.dumps(threshold_sample) + "\n", encoding="utf-8")
            threshold_client = Recording()
            threshold_run = realcheck.run(
                settings_for(str(tmp / "threshold-run")),
                realcheck.load_samples(str(sample_path)),
                client=threshold_client,
                kinds=("evaluate",),
            )
            threshold_sub = threshold_run["samples"][0]
            threshold_payload = json.JSONDecoder().raw_decode(
                threshold_client.messages[0][1]["content"].split("\n", 1)[1]
            )[0]
            threshold_result = threshold_sub["generations"]["evaluate"]["result"]
            check(
                "malformed_split_token_cannot_trigger_false_below_minimum",
                not any("低于 150" in warning for warning in threshold_result["warnings"]),
            )
            detail["boundary_threshold_end_to_end"] = {
                "original_words": threshold_sub["submission"]["word_count"],
                "one_original_compound_word": 1,
                "selected_fragments": 2,
                "payload_remaining_words": threshold_payload["word_count_without_copied"],
                "fake_calls": len(threshold_client.calls),
                "stored_span_count": len(
                    json.loads(threshold_sub["submission"]["copied_spans"])["spans"]
                ),
                "below_150_warning": any(
                    "低于 150" in warning for warning in threshold_result["warnings"]
                ),
                "warnings": threshold_result["warnings"],
            }
            findings.append(
                {
                    "id": "confirmed-token-boundary",
                    "severity": "P2",
                    "location": "tools/ielts_writing_ai/essay.py:279-280",
                    "summary": "Whole-word check accepts halves of apostrophe/hyphen words; loader accepts disjoint halves and confirmed word deduction double-counts one original word.",
                    "scope": "Confirmed quote annotations only; official two-whole-paragraph annotation is unaffected.",
                    "reproduced_cases": sum(not row["rejected"] for row in boundary),
                }
            )

    output = {
        "repo": str(repo),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
        "offline": True,
        "real_calls": 0,
        "private_text_in_output": False,
        "checks": checks,
        "summary": {"passed": sum(c["passed"] for c in checks), "total": len(checks)},
        "details": detail,
        "findings": findings,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "summary": output["summary"],
                "failed_checks": [c["name"] for c in checks if not c["passed"]],
                "findings": findings,
            },
            ensure_ascii=False,
        )
    )
    return int(any(not c["passed"] for c in checks))


if __name__ == "__main__":
    raise SystemExit(main())
