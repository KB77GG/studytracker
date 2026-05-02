#!/usr/bin/env python3
"""Import idictation IELTS reading passages into MaterialBank questions.

Authentication is supplied at runtime via --cookie or IDICTATION_COOKIE.
The imported material type is ielts_reading_practice, which the miniprogram
routes to the existing material-choice practice page.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import html
import json
import os
import random
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE_URL = "https://www.idictation.cn"
SECRET = "idictation_2024"
DEFAULT_BOOKS = "4-20"
MATERIAL_TYPE = "ielts_reading_practice"

SOURCE_CONFIG = {
    "academic": {
        "label": "剑雅阅读",
        "list_path": "/api/study/yuedu-zhenti/v1/jianya/list",
        "part_path": "/api/study/yuedu-zhenti/v1/jianya/part/show/{id}",
    },
    "general": {
        "label": "剑雅G类阅读",
        "list_path": "/api/study/yuedu-g-zhenti/v1/jianya/list",
        "part_path": "/api/study/yuedu-g-zhenti/v1/jianya/part/show/{id}",
    },
    "jijing": {
        "label": "阅读机经",
        "list_path": "/api/study/yuedu-zhenti/v1/jijing/list",
        "part_path": "/api/study/yuedu-zhenti/v1/jijing/part/show/{id}",
    },
}


def parse_books(value: str) -> set[int]:
    books: set[int] = set()
    for chunk in (value or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start, end = chunk.split("-", 1)
            books.update(range(int(start), int(end) + 1))
        else:
            books.add(int(chunk))
    return books


def signed_body(path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    body = {k: v for k, v in (data or {}).items() if v is not None}
    body["api_key"] = urllib.parse.quote(path, safe="")
    body["timestamp"] = int(time.time())
    body["nonce"] = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(10))

    canonical_parts: list[str] = []
    for key in sorted(body):
        value = body[key]
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        canonical_parts.append(f"{key}={value}")
    canonical = "&".join(canonical_parts)
    body["sign"] = hmac.new(SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return body


def post_json(
    path: str,
    data: dict[str, Any] | None,
    cookie: str,
    timeout: int,
    insecure: bool = False,
) -> dict[str, Any]:
    payload = json.dumps(signed_body(path, data), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Cookie": cookie,
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/main/book",
            "User-Agent": "Mozilla/5.0",
        },
    )
    context = ssl._create_unverified_context() if insecure else None
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        raw = response.read().decode("utf-8")
    decoded = json.loads(raw)
    if decoded.get("status"):
        raise RuntimeError(f"{path} failed: {decoded.get('message') or decoded.get('status')}")
    return decoded


def values_of(response: dict[str, Any]) -> Any:
    return response.get("values") if isinstance(response, dict) else None


def read_raw(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"catalogs": {}, "parts": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    text = html.unescape(str(value))
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.I)
    text = re.sub(r"</\s*(p|div|li|tr|h[1-6])\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def first_int(*values: Any) -> int | None:
    for value in values:
        if isinstance(value, int):
            return value
        match = re.search(r"\d+", str(value or ""))
        if match:
            return int(match.group())
    return None


def children_of(node: dict[str, Any]) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = []
    for key in ("children", "parts", "list", "tests"):
        value = node.get(key)
        if isinstance(value, list):
            children.extend(item for item in value if isinstance(item, dict))
    for key in ("reading", "yuedu", "read"):
        value = node.get(key)
        if isinstance(value, dict):
            children.extend(children_of(value) or [value])
    return children


def catalog_roots(values: Any) -> list[dict[str, Any]]:
    if isinstance(values, dict):
        for key in ("books", "list", "data"):
            if isinstance(values.get(key), list):
                return [item for item in values[key] if isinstance(item, dict)]
        return [values]
    if isinstance(values, list):
        return [item for item in values if isinstance(item, dict)]
    return []


def collect_catalog_parts(catalog_values: Any, allowed_books: set[int], source: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    def walk(node: dict[str, Any], ctx: dict[str, Any]) -> None:
        name = str(node.get("title") or node.get("name") or node.get("test_name") or "")
        next_ctx = dict(ctx)
        book_no = first_int(node.get("book_id"), node.get("in_book"), node.get("book"), name)
        if book_no:
            next_ctx.setdefault("book", book_no)
        if re.search(r"\btest\b|套|Test", name, re.I):
            test_no = first_int(node.get("test"), node.get("test_id"), name)
            if test_no:
                next_ctx["test"] = test_no
        if re.search(r"\b(part|passage)\b|篇|阅读", name, re.I):
            passage_no = first_int(node.get("part"), node.get("passage"), name)
            if passage_no:
                next_ctx["passage"] = passage_no

        node_id = node.get("id") or node.get("paper_id") or node.get("part_id")
        kids = children_of(node)
        looks_like_part = bool(node_id) and (
            not kids
            or re.search(r"\b(part|passage)\b|篇|阅读", name, re.I)
            or node.get("question")
        )
        if looks_like_part:
            book = next_ctx.get("book")
            if allowed_books and book and int(book) not in allowed_books:
                return
            entries.append(
                {
                    "source": source,
                    "book": int(book or 0),
                    "test": int(next_ctx.get("test") or 0),
                    "passage": int(next_ctx.get("passage") or len(entries) + 1),
                    "part_id": int(node_id),
                    "title": name,
                    "raw": node,
                }
            )
            return

        for child in kids:
            walk(child, next_ctx)

    for root in catalog_roots(catalog_values):
        walk(root, {})

    unique: dict[tuple[str, int], dict[str, Any]] = {}
    for entry in entries:
        unique[(entry["source"], entry["part_id"])] = entry
    return sorted(unique.values(), key=lambda item: (item["book"], item["test"], item["passage"], item["part_id"]))


def unwrap_part(raw_parts: dict[str, Any], source: str, part_id: int) -> dict[str, Any]:
    row = raw_parts.get(source, {}).get(str(part_id)) or {}
    return row.get("values") or row.get("data") or row


def option_key(value: Any, fallback_index: int) -> str:
    raw = clean_text(value)
    match = re.match(r"^([A-Z])(?:[.)、:]|\s|$)", raw, re.I)
    if match:
        return match.group(1).upper()
    return chr(ord("A") + fallback_index)


def option_text(value: dict[str, Any], fallback_key: str) -> str:
    text = clean_text(value.get("content") or value.get("text") or value.get("title") or "")
    text = re.sub(rf"^{re.escape(fallback_key)}[.)、:\s]+", "", text, flags=re.I).strip()
    return text


def truth_options(answer: str) -> list[dict[str, str]]:
    upper = answer.strip().upper()
    if upper in {"TRUE", "FALSE", "NOT GIVEN", "T", "F", "NG"}:
        return [
            {"key": "T", "text": "TRUE"},
            {"key": "F", "text": "FALSE"},
            {"key": "NG", "text": "NOT GIVEN"},
        ]
    if upper in {"YES", "NO", "NOT GIVEN", "Y", "N", "NG"}:
        return [
            {"key": "Y", "text": "YES"},
            {"key": "N", "text": "NO"},
            {"key": "NG", "text": "NOT GIVEN"},
        ]
    return []


def choice_answer_for_options(answer: str, options: list[dict[str, str]]) -> str:
    upper = answer.strip().upper()
    if upper in {option["key"].strip().upper() for option in options}:
        return upper
    for option in options:
        if option["text"].strip().upper() == upper:
            return option["key"]
    return ""


def analysis_text(value: Any) -> str:
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        chunks = []
        for row in value:
            if isinstance(row, dict):
                chunks.append(clean_text(row.get("content") or row.get("analysis") or row.get("text")))
            else:
                chunks.append(clean_text(row))
        return "\n".join(chunk for chunk in chunks if chunk)
    if isinstance(value, dict):
        return clean_text(value.get("content") or value.get("analysis") or value.get("text") or "")
    return ""


def render_table(table: Any) -> str:
    if not table:
        return ""
    content = table.get("content") if isinstance(table, dict) else table
    if not isinstance(content, list):
        return clean_text(content)
    lines = []
    for row in content:
        if isinstance(row, list):
            lines.append(" | ".join(clean_text(cell) for cell in row if clean_text(cell)))
        else:
            lines.append(clean_text(row))
    return "\n".join(line for line in lines if line)


def question_content(group: dict[str, Any], item: dict[str, Any]) -> str:
    number = item.get("number") or item.get("serialNumber") or item.get("index")
    title = clean_text(item.get("title") or item.get("question") or item.get("stem"))
    group_title = clean_text(group.get("question_title") or group.get("title") or group.get("desc"))
    table_text = render_table(group.get("table"))
    collect = clean_text(group.get("collect") or "")
    pieces = []
    if number:
        pieces.append(f"Q{number}")
    if title:
        pieces.append(title)
    elif group_title:
        pieces.append(group_title)
    if table_text and "$" in table_text:
        pieces.append(table_text)
    elif collect and "$" in collect:
        pieces.append(collect)
    content = ". ".join(pieces)
    return content or group_title or f"Question {number or item.get('id') or ''}".strip()


def build_question(group: dict[str, Any], item: dict[str, Any], sequence: int) -> dict[str, Any] | None:
    answer = clean_text(item.get("display_answer") or item.get("answer") or item.get("correct_answer"))
    if not answer:
        return None

    raw_options = item.get("option") or []
    options: list[dict[str, str]] = []
    if isinstance(raw_options, list):
        for index, raw in enumerate(raw_options):
            if not isinstance(raw, dict):
                raw = {"title": raw}
            key = option_key(raw.get("title") or raw.get("key") or raw.get("label"), index)
            text = option_text(raw, key)
            if text:
                options.append({"key": key, "text": text})

    if not options:
        options = truth_options(answer)

    choice_answer = choice_answer_for_options(answer, options)
    content = question_content(group, item)
    explanation = clean_text(item.get("ai_analyze")) or analysis_text(item.get("analyze"))

    if options and choice_answer:
        return {
            "sequence": sequence,
            "question_type": "choice",
            "content": content,
            "reference_answer": choice_answer,
            "hint": answer,
            "explanation": explanation,
            "points": 1,
            "options": options,
        }

    if options:
        option_lines = "\n".join(f"{opt['key']}. {opt['text']}" for opt in options)
        content = f"{content}\n\nOptions:\n{option_lines}"

    return {
        "sequence": sequence,
        "question_type": "reading_text",
        "content": content,
        "reference_answer": answer,
        "hint": clean_text(group.get("question_title") or group.get("title") or ""),
        "explanation": explanation,
        "points": 1,
        "options": [],
    }


def passage_text(part: dict[str, Any]) -> str:
    content = part.get("content")
    if isinstance(content, str):
        return clean_text(content)
    if isinstance(content, list):
        rows = []
        for item in sorted(
            (row for row in content if isinstance(row, dict)),
            key=lambda row: row.get("order") or row.get("sequence") or 0,
        ):
            text = clean_text(
                item.get("en_text")
                or item.get("content")
                or item.get("text")
                or item.get("paragraph")
                or ""
            )
            if text:
                rows.append(text)
        if rows:
            return "\n\n".join(rows)
    for key in ("article", "passage", "text", "desc"):
        if part.get(key):
            return clean_text(part.get(key))
    return ""


def build_material_payload(entry: dict[str, Any], part: dict[str, Any]) -> dict[str, Any]:
    source_label = SOURCE_CONFIG[entry["source"]]["label"]
    book = part.get("in_book") or entry.get("book") or ""
    test_name = clean_text(part.get("test_name") or "")
    title = clean_text(part.get("title") or entry.get("title") or f"Passage {entry.get('passage')}")
    if entry["source"] == "jijing":
        material_title = f"{source_label} {book} {title}".strip()
    else:
        material_title = f"{source_label} Cambridge IELTS {book} {test_name} {title}".strip()

    questions = []
    for group in part.get("question") or part.get("questions") or []:
        if not isinstance(group, dict):
            continue
        for item in group.get("list") or group.get("questions") or []:
            if not isinstance(item, dict):
                continue
            built = build_question(group, item, len(questions) + 1)
            if built:
                questions.append(built)

    source_note = (
        f"来源：idictation {source_label}；part_id={entry['part_id']}；"
        f"book={book or '-'}；test={test_name or entry.get('test') or '-'}。"
    )
    passage = passage_text(part)
    description = f"{source_note}\n\n{passage}".strip()
    return {
        "title": material_title,
        "type": MATERIAL_TYPE,
        "description": description,
        "questions": questions,
    }


def import_materials(payloads: list[dict[str, Any]], creator_id: int | None, replace: bool) -> list[dict[str, Any]]:
    from app import app
    from models import MaterialBank, Question, QuestionOption, User, db

    imported: list[dict[str, Any]] = []
    with app.app_context():
        if creator_id is None:
            creator = (
                User.query.filter(User.role.in_(["admin", "teacher", "assistant"]))
                .order_by(User.id)
                .first()
            )
            creator_id = creator.id if creator else None

        for payload in payloads:
            material = (
                MaterialBank.query.filter_by(
                    title=payload["title"],
                    type=MATERIAL_TYPE,
                    is_deleted=False,
                )
                .order_by(MaterialBank.id)
                .first()
            )
            if material and not replace:
                imported.append({"title": payload["title"], "material_id": material.id, "status": "skipped"})
                continue
            existed = material is not None
            if not material:
                material = MaterialBank(
                    title=payload["title"],
                    type=MATERIAL_TYPE,
                    created_by=creator_id,
                    is_active=True,
                )
                db.session.add(material)
                db.session.flush()
            else:
                for question in material.questions.all():
                    db.session.delete(question)
                db.session.flush()

            material.description = payload.get("description") or ""
            material.is_active = True

            for q_data in payload.get("questions") or []:
                question = Question(
                    material_id=material.id,
                    sequence=q_data["sequence"],
                    question_type=q_data.get("question_type", "choice"),
                    content=q_data["content"],
                    reference_answer=q_data.get("reference_answer"),
                    hint=q_data.get("hint"),
                    explanation=q_data.get("explanation"),
                    points=q_data.get("points", 1),
                )
                db.session.add(question)
                db.session.flush()
                for opt in q_data.get("options") or []:
                    db.session.add(
                        QuestionOption(
                            question_id=question.id,
                            option_key=opt["key"],
                            option_text=opt["text"],
                        )
                    )

            imported.append(
                {
                    "title": payload["title"],
                    "material_id": material.id,
                    "questions": len(payload.get("questions") or []),
                    "status": "updated" if existed else "imported",
                }
            )
        db.session.commit()
    return imported


def main() -> int:
    parser = argparse.ArgumentParser(description="Import idictation IELTS reading materials.")
    parser.add_argument("--cookie", default=os.environ.get("IDICTATION_COOKIE", ""), help="Login cookie; defaults to IDICTATION_COOKIE.")
    parser.add_argument("--source", choices=sorted(SOURCE_CONFIG), default="academic")
    parser.add_argument("--books", default=DEFAULT_BOOKS, help="Book range/list, e.g. 4-20 or 11,12.")
    parser.add_argument("--raw", default="data/idictation_reading/raw.json")
    parser.add_argument("--report", default="data/idictation_reading/import_report.json")
    parser.add_argument("--normalized", default="data/idictation_reading/normalized.json")
    parser.add_argument("--only", default="", help="Comma-separated part ids to import.")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of parts for smoke tests.")
    parser.add_argument("--no-fetch", action="store_true", help="Use existing --raw without calling idictation APIs.")
    parser.add_argument("--no-db", action="store_true", help="Fetch and normalize only; do not write MaterialBank rows.")
    parser.add_argument("--replace", action="store_true", help="Replace questions for existing materials with the same title.")
    parser.add_argument("--creator-id", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--sleep", type=float, default=0.25)
    parser.add_argument("--insecure", action="store_true", help="Skip TLS verification for idictation calls.")
    args = parser.parse_args()

    raw_path = Path(args.raw)
    raw = read_raw(raw_path)
    raw.setdefault("catalogs", {})
    raw.setdefault("parts", {})
    raw["parts"].setdefault(args.source, {})
    allowed_books = parse_books(args.books)

    config = SOURCE_CONFIG[args.source]
    if not args.no_fetch:
        if not args.cookie:
            raise SystemExit("Missing cookie. Pass --cookie or set IDICTATION_COOKIE.")
        catalog = post_json(config["list_path"], {}, args.cookie, args.timeout, args.insecure)
        raw["catalogs"][args.source] = catalog
    else:
        catalog = raw["catalogs"].get(args.source) or {}

    catalog_values = values_of(catalog)
    entries = collect_catalog_parts(catalog_values, allowed_books, args.source)
    only_ids = {int(item.strip()) for item in args.only.split(",") if item.strip().isdigit()}
    if only_ids:
        entries = [entry for entry in entries if entry["part_id"] in only_ids]
    if args.limit > 0:
        entries = entries[: args.limit]

    payloads: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, 1):
        part_key = str(entry["part_id"])
        print(f"[{index}/{len(entries)}] {args.source} part_id={part_key}")
        if not args.no_fetch and part_key not in raw["parts"][args.source]:
            path = config["part_path"].format(id=entry["part_id"])
            raw["parts"][args.source][part_key] = post_json(path, {}, args.cookie, args.timeout, args.insecure)
            time.sleep(args.sleep)
        part = unwrap_part(raw.get("parts") or {}, args.source, entry["part_id"])
        if not part:
            print("  skip: missing part values")
            continue
        payload = build_material_payload(entry, part)
        if not payload["questions"]:
            print("  skip: no questions recognized")
            continue
        payloads.append(payload)

    write_json(raw_path, raw)
    write_json(Path(args.normalized), payloads)
    if args.no_db:
        report = [
            {"title": payload["title"], "questions": len(payload.get("questions") or []), "status": "normalized"}
            for payload in payloads
        ]
    else:
        report = import_materials(payloads, args.creator_id, args.replace)
    write_json(Path(args.report), report)
    print(f"processed {len(report)} materials")
    print(f"raw: {raw_path}")
    print(f"normalized: {args.normalized}")
    print(f"report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
