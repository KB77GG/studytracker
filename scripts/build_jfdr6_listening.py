#!/usr/bin/env python3
"""9分达人听力数据流水线：merge（合并+硬校验）与 build（组装 static JSON）。

数据流（详见 data/jfdr{book}/extract/SCHEMA.md）：
  extract/test{N}/part{S}.questions.json   ┐
  extract/test{N}/part{S}.transcript.jsonl ├─ merge ─> merged/test{N}_part{S}.json
  extract/test{N}/part{S}.analysis.json    │          + review/test{N}.md（人工校对单）
  extract/answer_key.json                  ┘
  merged + aligned/ + translations/ ── build ─> static/listening_tests/jfdr{book}_test{N}.json
                                              + static/listening/jfdr{book}_test{N}_s{S}.json + mp3

Usage:
    python scripts/build_jfdr6_listening.py merge [--book B] [--test N]
    python scripts/build_jfdr6_listening.py build [--book B] [--test N]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.listening_series import parse_intensive_id, parse_test_id  # noqa: E402

JFDR_ROOT = PROJECT_ROOT / "data" / "jfdr6"
EXTRACT_DIR = JFDR_ROOT / "extract"
MERGED_DIR = JFDR_ROOT / "merged"
REVIEW_DIR = JFDR_ROOT / "review"
ALIGNED_DIR = JFDR_ROOT / "aligned"
TRANSLATIONS_DIR = JFDR_ROOT / "translations"
AUDIO_DIR = JFDR_ROOT / "audio"
LISTENING_TESTS_DIR = PROJECT_ROOT / "static" / "listening_tests"
LISTENING_DIR = PROJECT_ROOT / "static" / "listening"

PLACEHOLDER_RE = re.compile(r"\$(\d+)\$")


def configure_paths(book: int) -> None:
    global JFDR_ROOT, EXTRACT_DIR, MERGED_DIR, REVIEW_DIR
    global ALIGNED_DIR, TRANSLATIONS_DIR, AUDIO_DIR
    JFDR_ROOT = PROJECT_ROOT / "data" / f"jfdr{book}"
    EXTRACT_DIR = JFDR_ROOT / "extract"
    MERGED_DIR = JFDR_ROOT / "merged"
    REVIEW_DIR = JFDR_ROOT / "review"
    ALIGNED_DIR = JFDR_ROOT / "aligned"
    TRANSLATIONS_DIR = JFDR_ROOT / "translations"
    AUDIO_DIR = JFDR_ROOT / "audio"


def _test_title(book: int, test_no: int) -> str:
    test_id = f"jfdr{book}_test{test_no}"
    info = parse_test_id(test_id)
    if not info:
        raise SystemExit(f"cannot parse listening test id: {test_id}")
    return info["title"]


def _intensive_title(book: int, test_no: int, part_no: int) -> str:
    exercise_id = f"jfdr{book}_test{test_no}_s{part_no}"
    info = parse_intensive_id(exercise_id)
    if not info:
        raise SystemExit(f"cannot parse intensive id: {exercise_id}")
    return info["title"]

# 与 api/text_utils.py 的判分归一化保持一致的宽松比较（仅用于双源答案比对）
def _norm_answer(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[‘’`]", "'", text)
    text = re.sub(r"[“”]", '"', text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^[\W_]+|[\W_]+$", "", text)
    return text


def _part_numbers(part: int) -> list[int]:
    return list(range((part - 1) * 10 + 1, part * 10 + 1))


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _placeholder_numbers(group: dict) -> set[int]:
    found: set[int] = set()
    for text in [group.get("collect") or ""]:
        found.update(int(n) for n in PLACEHOLDER_RE.findall(text))
    table = group.get("table")
    if isinstance(table, dict):
        for row in table.get("content") or []:
            for cell in row:
                found.update(int(n) for n in PLACEHOLDER_RE.findall(str(cell)))
    return found


def merge_part(test_no: int, part_no: int, answer_key: dict) -> tuple[dict | None, list[dict]]:
    """Merge one part's extract files. Returns (merged_payload, issues)."""
    issues: list[dict] = []
    base = EXTRACT_DIR / f"test{test_no}"
    q_path = base / f"part{part_no}.questions.json"
    t_path = base / f"part{part_no}.transcript.jsonl"
    a_path = base / f"part{part_no}.analysis.json"

    missing = [p.name for p in (q_path, t_path, a_path) if not p.exists()]
    if missing:
        issues.append({"level": "error", "q": None, "msg": f"缺提取文件: {', '.join(missing)}"})
        return None, issues

    questions_doc = _load_json(q_path)
    transcript = _load_jsonl(t_path)
    analysis_doc = _load_json(a_path)

    expected = _part_numbers(part_no)
    test_answers = {int(k): v for k, v in (answer_key.get(str(test_no)) or {}).items()}

    # --- 题号完整性 ---
    q_numbers = [
        int(q["number"])
        for group in questions_doc.get("groups") or []
        for q in group.get("questions") or []
    ]
    if sorted(q_numbers) != expected:
        issues.append({
            "level": "error", "q": None,
            "msg": f"题号不完整: 期望 {expected[0]}-{expected[-1]}, 实得 {sorted(q_numbers)}",
        })

    # --- 解析完整性 + 答案双源比对 ---
    analysis_by_number = {int(item["number"]): item for item in analysis_doc.get("items") or []}
    for number in expected:
        key_answer = test_answers.get(number)
        item = analysis_by_number.get(number)
        if key_answer is None:
            issues.append({"level": "error", "q": number, "msg": "答案总表缺该题"})
        if item is None:
            issues.append({"level": "warn", "q": number, "msg": "真题解析缺该题"})
            continue
        if key_answer is not None and _norm_answer(item.get("answer")) != _norm_answer(key_answer):
            issues.append({
                "level": "review", "q": number,
                "msg": f"答案双源不一致: 总表[{key_answer}] vs 解析[{item.get('answer')}]",
            })

    # --- 占位符与题号集合 ---
    for gi, group in enumerate(questions_doc.get("groups") or []):
        group_numbers = {int(q["number"]) for q in group.get("questions") or []}
        placeholders = _placeholder_numbers(group)
        if placeholders and placeholders != group_numbers:
            issues.append({
                "level": "review", "q": None,
                "msg": f"group{gi + 1} 占位符 {sorted(placeholders)} != 题号 {sorted(group_numbers)}",
            })
        gtype = int(group.get("type") or 0)
        if gtype in (1, 9):
            for q in group.get("questions") or []:
                if not q.get("options"):
                    issues.append({"level": "review", "q": int(q["number"]), "msg": "选择题缺 options"})
        if gtype in (2, 8):
            option_list = (group.get("collect_option") or {}).get("list")
            if not option_list:
                issues.append({"level": "review", "q": None, "msg": f"group{gi + 1} (type {gtype}) 缺 collect_option.list"})
        if gtype in (6, 7) and group.get("needs_image"):
            img = group.get("img_local") or ""
            if not img:
                issues.append({"level": "warn", "q": None, "msg": f"group{gi + 1} 地图/图示题待截图 (pages {group.get('image_pages')})"})

    # --- transcript 完整性 + 答案句覆盖 ---
    for i, row in enumerate(transcript):
        if int(row.get("idx", -1)) != i:
            issues.append({"level": "error", "q": None, "msg": f"transcript idx 不连续 (第 {i} 行)"})
            break
    mapped: set[int] = set()
    for row in transcript:
        for n in row.get("q") or []:
            n = int(n)
            if n not in expected:
                issues.append({
                    "level": "review", "q": n,
                    "msg": f"transcript idx {row['idx']} 标注了不属于本 Part 的题号",
                })
            mapped.add(n)
    for number in expected:
        if number not in mapped:
            issues.append({"level": "review", "q": number, "msg": "无答案句标注（需兜底映射）"})

    merged = {
        "test": test_no,
        "part": part_no,
        "title": next(
            (g.get("title") for g in questions_doc.get("groups") or [] if g.get("title")),
            "",
        ),
        "groups": questions_doc.get("groups") or [],
        "transcript": transcript,
        "analysis": {
            str(n): {
                "answer": analysis_by_number[n].get("answer"),
                "analysis": analysis_by_number[n].get("analysis"),
            }
            for n in expected
            if n in analysis_by_number
        },
        "answers": {str(n): test_answers.get(n) for n in expected},
    }
    return merged, issues


def cmd_merge(tests: list[int]) -> int:
    answer_key_path = EXTRACT_DIR / "answer_key.json"
    if not answer_key_path.exists():
        raise SystemExit(f"missing {answer_key_path}")
    answer_key = _load_json(answer_key_path)

    MERGED_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    exit_code = 0
    for test_no in tests:
        review_lines = [
            f"# Test {test_no} 校对单（merge 生成，人工只看下面列出的行）",
            "",
            "| Part | 题号 | 级别 | 问题 |",
            "|---|---|---|---|",
        ]
        flagged = 0
        for part_no in (1, 2, 3, 4):
            merged, issues = merge_part(test_no, part_no, answer_key)
            errors = [i for i in issues if i["level"] == "error"]
            for issue in issues:
                review_lines.append(
                    f"| {part_no} | {issue['q'] or '-'} | {issue['level']} | {issue['msg']} |"
                )
                flagged += 1
            if errors:
                exit_code = 1
                print(f"test{test_no} part{part_no}: {len(errors)} 个 error，未产出 merged")
                continue
            if merged is None:
                exit_code = 1
                continue
            out = MERGED_DIR / f"test{test_no}_part{part_no}.json"
            out.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"test{test_no} part{part_no}: merged -> {out.relative_to(PROJECT_ROOT)}"
                  f"（{len(issues)} 条待复核）" if issues else
                  f"test{test_no} part{part_no}: merged 全绿 -> {out.relative_to(PROJECT_ROOT)}")
        if flagged == 0:
            review_lines.append("| - | - | - | 无，全绿 |")
        review_path = REVIEW_DIR / f"test{test_no}.md"
        review_path.write_text("\n".join(review_lines) + "\n", encoding="utf-8")
        print(f"review: {review_path.relative_to(PROJECT_ROOT)}")
    return exit_code


# ---------------------------------------------------------------- build ----

_PAREN_RE = re.compile(r"\(([^)]*)\)")


def _expand_answer_alternatives(raw: str) -> list[str]:
    """答案总表写法 -> 判分可接受的全部写法。

    现有判分（app.py `_grade_listening_test_answers`）只对 `answer` 字符串按
    "/" 拆备选后做清洗全等比较，不理解括号可选成分。书中大量使用
    "5(th) May" / "(the) library" 式写法，必须在组装时展开，否则学生写
    "5th May" 会被判错。
    """
    raw = str(raw or "").strip()
    if not raw:
        return []
    out: list[str] = []
    for part in raw.split("/"):
        part = part.strip()
        if not part:
            continue
        variants = [part]
        if _PAREN_RE.search(part):
            inline = re.sub(r"\s+", " ", _PAREN_RE.sub(lambda m: m.group(1), part)).strip()
            removed = re.sub(r"\s+", " ", _PAREN_RE.sub("", part)).strip()
            variants.extend([inline, removed])
        for v in variants:
            if v and v not in out:
                out.append(v)
    return out or [raw]


def build_test(test_no: int, book: int) -> None:
    sections = []
    for part_no in (1, 2, 3, 4):
        merged = _load_json(MERGED_DIR / f"test{test_no}_part{part_no}.json")
        exercise_id = f"jfdr{book}_test{test_no}_s{part_no}"
        aligned = _load_json(ALIGNED_DIR / f"{exercise_id}.json")
        segments = aligned["segments"]
        translations_path = TRANSLATIONS_DIR / f"test{test_no}_part{part_no}.json"
        translations = _load_json(translations_path) if translations_path.exists() else {}

        transcript_rows = merged["transcript"]
        if len(segments) != len(transcript_rows):
            raise SystemExit(
                f"{exercise_id}: aligned segments ({len(segments)}) != transcript rows ({len(transcript_rows)})"
            )

        # 每题 -> 命中句 idx 列表
        q_to_rows: dict[int, list[int]] = {}
        for row in transcript_rows:
            for n in row.get("q") or []:
                q_to_rows.setdefault(int(n), []).append(int(row["idx"]))

        test_transcript = []
        for row, seg in zip(transcript_rows, segments):
            speaker = (row.get("speaker") or "").strip()
            display = f"{speaker}: {row['en']}" if speaker else row["en"]
            test_transcript.append({
                "order": int(row["idx"]),
                "start": seg["start"],
                "end": seg["end"],
                "en": display,
                "cn": translations.get(str(row["idx"])) or "",
            })

        groups_out = []
        for gi, group in enumerate(merged["groups"]):
            gtype = int(group.get("type") or 0)
            # 多选组（Choose TWO/THREE，组内共享选项、乱序可接受）：现有判分
            # 依赖每题 answer 都等于合并字母串（如 "B,E"）来触发 checkbox-set
            # 乱序判分（app.py `_listening_test_is_combined_multi`）。
            combined_answer = None
            if gtype == 2:
                letters = [
                    str(merged["answers"].get(str(int(q["number"]))) or "").strip()
                    for q in group.get("questions") or []
                ]
                if letters and all(letters):
                    combined_answer = ",".join(letters)
            questions_out = []
            for q in group.get("questions") or []:
                number = int(q["number"])
                answer = combined_answer or merged["answers"].get(str(number)) or ""
                analysis = (merged["analysis"].get(str(number)) or {}).get("analysis") or ""
                row_idxs = sorted(q_to_rows.get(number, []))
                if row_idxs:
                    start = min(segments[i]["start"] for i in row_idxs)
                    end = max(segments[i]["end"] for i in row_idxs)
                    answer_sentences = {
                        "start_time": int(round(start * 1000)),
                        "end_time": int(round(end * 1000)),
                        "lyc_index": row_idxs,
                    }
                else:
                    start = end = 0
                    answer_sentences = None
                alternatives = _expand_answer_alternatives(answer)
                questions_out.append({
                    "id": number,
                    "number": number,
                    "title": q.get("title") or "",
                    "answer": " / ".join(alternatives) if len(alternatives) > 1 else answer,
                    "answers": alternatives,
                    "options": q.get("options") or [],
                    "start": start,
                    "end": end,
                    "analysis": analysis,
                    "answer_sentences": answer_sentences,
                })
            groups_out.append({
                "group_id": gi + 1,
                "type": int(group.get("type") or 0),
                "title": group.get("title") or "",
                "question_title": group.get("question_title") or "",
                "desc": group.get("desc") or "",
                "table": group.get("table"),
                "collect": group.get("collect") or "",
                "img_url": "",
                "img_local": group.get("img_local") or "",
                "collect_option": group.get("collect_option") or {"title": "", "list": None},
                "questions": questions_out,
            })

        sections.append({
            "id": exercise_id,
            "part_id": part_no,
            "section": part_no,
            "title": f"Part {part_no}",
            "audio": f"{exercise_id}.mp3",
            "source_title": merged.get("title") or f"Part {part_no}",
            "question_name": f"Q{(part_no - 1) * 10 + 1}-{part_no * 10}",
            "question_type": sorted({int(g.get("type") or 0) for g in merged["groups"]}),
            "groups": groups_out,
            "transcript": test_transcript,
        })

        # ---- 精听 JSON ----
        intensive_segments = []
        for row, seg in zip(transcript_rows, segments):
            speaker = (row.get("speaker") or "").strip()
            display = f"{speaker}: {row['en']}" if speaker else row["en"]
            intensive_segments.append({
                "id": int(row["idx"]) + 1,
                "start": seg["start"],
                "end": seg["end"],
                "text": display,
                "translation": translations.get(str(row["idx"])) or "",
                "source_order": int(row["idx"]),
                "source_start_time": int(round(seg["start"] * 1000)),
                "source_end_time": int(round(seg["end"] * 1000)),
            })
        intensive_payload = {
            "id": exercise_id,
            "title": _intensive_title(book, test_no, part_no),
            "audio": f"{exercise_id}.mp3",
            "source": {
                "provider": f"jfdr{book}_pipeline",
                "book": f"《9分达人雅思听力真题还原及解析{book}》",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "parts": [{"name": f"Part {part_no}", "segments": intensive_segments}],
        }
        LISTENING_DIR.mkdir(parents=True, exist_ok=True)
        (LISTENING_DIR / f"{exercise_id}.json").write_text(
            json.dumps(intensive_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        src_mp3 = AUDIO_DIR / f"{exercise_id}.mp3"
        dst_mp3 = LISTENING_DIR / f"{exercise_id}.mp3"
        if src_mp3.exists() and not dst_mp3.exists():
            shutil.copy2(src_mp3, dst_mp3)

    test_payload = {
        "id": f"jfdr{book}_test{test_no}",
        "title": _test_title(book, test_no),
        "source": f"《9分达人雅思听力真题还原及解析{book}》",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": sections,
    }
    LISTENING_TESTS_DIR.mkdir(parents=True, exist_ok=True)
    out = LISTENING_TESTS_DIR / f"jfdr{book}_test{test_no}.json"
    out.write_text(json.dumps(test_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"build -> {out.relative_to(PROJECT_ROOT)}")

    _selfcheck_test(test_payload)


def _selfcheck_test(payload: dict) -> None:
    problems = []
    for section in payload["sections"]:
        transcript_len = len(section["transcript"])
        audio_path = LISTENING_DIR / section["audio"]
        for group in section["groups"]:
            for q in group["questions"]:
                if not q["answer"]:
                    problems.append(f"{section['id']} Q{q['number']}: 空答案")
                if q["answer_sentences"]:
                    for idx in q["answer_sentences"]["lyc_index"]:
                        if idx >= transcript_len:
                            problems.append(f"{section['id']} Q{q['number']}: lyc_index {idx} 越界")
                    if q["end"] < q["start"]:
                        problems.append(f"{section['id']} Q{q['number']}: end < start")
                else:
                    problems.append(f"{section['id']} Q{q['number']}: 缺 answer_sentences")
        if not audio_path.exists():
            problems.append(f"{section['id']}: 缺音频 {section['audio']}")
    if problems:
        print("SELFCHECK 未通过:")
        for p in problems:
            print(f"  - {p}")
        raise SystemExit(1)
    print("selfcheck: OK")


def cmd_build(tests: list[int], book: int) -> int:
    for test_no in tests:
        build_test(test_no, book)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["merge", "build"])
    parser.add_argument("--book", type=int, default=6, help="9分达人听力 book number")
    parser.add_argument("--tests", type=int, default=6, help="number of tests to process")
    parser.add_argument("--test", type=int, help="只处理某一套")
    args = parser.parse_args()
    configure_paths(args.book)

    tests = [args.test] if args.test else list(range(1, args.tests + 1))
    if args.command == "merge":
        sys.exit(cmd_merge(tests))
    else:
        sys.exit(cmd_build(tests, args.book))


if __name__ == "__main__":
    main()
