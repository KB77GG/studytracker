#!/usr/bin/env python3
"""Standalone 40/40 self-check for built jfdr listening tests.

Faithful replica of app.py `_grade_listening_test_answers` (clean/split/letters/
combined-multi logic). Feeds each test's correct answers back as student answers
and asserts a perfect score — WITHOUT the dev server (whose debug reloader crashes
when build writes static files). Use in Phase 6 of docs/jfdr_import_runbook.md.

Usage:
    .venv/bin/python scripts/grade_jfdr_selfcheck.py --book 6
    .venv/bin/python scripts/grade_jfdr_selfcheck.py --book 6 --tests 1,2,3
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _norm(v):
    return (str(v or "").strip().lower()
            .replace("‘", "'").replace("’", "'")
            .replace("“", '"').replace("”", '"'))


def _clean(v):
    t = _norm(v)
    t = re.sub(r"[.,!?;:，。！？；：]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _alts(ans):
    return [_clean(p) for p in re.split(r"\s*/\s*", str(ans or "")) if _clean(p)]


def _letters(ans):
    ls = [p.strip().upper() for p in re.split(r"\s*[,/]\s*", str(ans or "")) if p.strip()]
    return list(dict.fromkeys(ls))


def _is_letters(ans):
    ls = _letters(ans)
    return bool(ls) and all(re.fullmatch(r"[A-Z]", x) for x in ls)


def _is_combined_multi(group):
    if group.get("type") != 2:
        return False
    opts = (group.get("collect_option") or {}).get("list") or []
    qs = group.get("questions") or []
    if not opts or not qs:
        return False
    fa = qs[0].get("answer") or ""
    return "," in fa and all((q.get("answer") or "") == fa for q in qs)


def _units(payload):
    out = []
    for si, s in enumerate(payload.get("sections") or []):
        for g in s.get("groups") or []:
            qs = g.get("questions") or []
            if _is_combined_multi(g):
                out.append({"ids": [str(q.get("id") or q.get("number")) for q in qs],
                            "numbers": [q.get("number") for q in qs],
                            "answer": qs[0].get("answer") or "", "marks": len(qs),
                            "kind": "checkbox-set"})
                continue
            for q in qs:
                a = q.get("answer") or ""
                exact_multi = bool(q.get("options")) and "," in str(a)
                out.append({"ids": [str(q.get("id") or q.get("number"))],
                            "numbers": [q.get("number")], "answer": a, "marks": 1,
                            "kind": "checkbox-exact" if exact_multi else "question"})
    return out


def _grade(payload, answers):
    total = correct = 0
    wrong = []
    for u in _units(payload):
        key = ",".join(u["ids"])
        val = answers.get(key)
        if val is None and u["kind"] == "checkbox-set":
            sep = [str(answers.get(i) or "").strip() for i in u["ids"] if str(answers.get(i) or "").strip()]
            if sep:
                val = ",".join(sep)
        if val is None and u["ids"]:
            val = answers.get(u["ids"][0], "")
        ans = u["answer"]
        marks = int(u["marks"] or 1)
        total += marks
        awarded = 0
        ok = False
        if u["kind"] == "checkbox-set":
            exp = _letters(ans); sub = _letters(val)
            awarded = 0 if len(sub) > marks else min(marks, len([x for x in sub if x in exp]))
            ok = bool(exp) and awarded == marks
        elif u["kind"] == "checkbox-exact":
            exp = _letters(ans); sub = _letters(val)
            ok = bool(exp) and len(sub) == len(exp) and set(sub) == set(exp)
            awarded = marks if ok else 0
        elif _is_letters(ans):
            exp = _letters(ans); sub = _letters(val)
            ok = (len(sub) == len(exp) and set(sub) == set(exp)) if len(sub) > 1 else str(val or "").strip().upper() in exp
            awarded = marks if ok else 0
        else:
            ok = _clean(val) in _alts(ans)
            awarded = marks if ok else 0
        correct += awarded
        if not ok:
            wrong.extend(u["numbers"])
    return correct, total, wrong


def _correct_answers(payload):
    answers = {}
    for s in payload["sections"]:
        for g in s["groups"]:
            qs = g["questions"]
            if _is_combined_multi(g):
                answers[",".join(str(q["id"]) for q in qs)] = qs[0]["answer"]
            else:
                for q in qs:
                    answers[str(q["id"])] = (q.get("answers") or [q["answer"]])[0]
    return answers


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book", type=int, required=True)
    ap.add_argument("--tests", help="comma list e.g. 1,2,3; default = all found")
    args = ap.parse_args()

    if args.tests:
        test_ids = [f"jfdr{args.book}_test{t.strip()}" for t in args.tests.split(",") if t.strip()]
    else:
        files = sorted(glob.glob(str(ROOT / f"static/listening_tests/jfdr{args.book}_test*.json")))
        test_ids = [Path(f).stem for f in files]
    if not test_ids:
        print(f"no built tests for book {args.book}")
        sys.exit(1)

    all_ok = True
    for tid in test_ids:
        f = ROOT / f"static/listening_tests/{tid}.json"
        if not f.exists():
            print(f"{tid}: (not built)"); all_ok = False; continue
        d = json.loads(f.read_text(encoding="utf-8"))
        c, tot, wrong = _grade(d, _correct_answers(d))
        ok = (c == tot and tot == 40)
        all_ok = all_ok and ok
        print(f"{tid}: {c}/{tot} [{'OK' if ok else 'FAIL'}]" + (f" wrong={wrong}" if wrong else ""))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
