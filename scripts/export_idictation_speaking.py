#!/usr/bin/env python3
"""Export idictation IELTS speaking question lists and prompts.

This script only uses authenticated HTTP requests for data the supplied account
can access. Pass your own cookie/token from a logged-in browser session.
"""

from __future__ import annotations

import argparse
import csv
import hmac
import html
import hashlib
import json
import os
import re
import ssl
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://www.idictation.cn"
SIGN_SECRET = "idictation_2024"
LIST_ENDPOINTS = {
    "part1": "/api/study/kouyu-zhenti/v1/part1/list",
    "part23": "/api/study/kouyu-zhenti/v1/part2/list",
}
SHOW_ENDPOINT = "/api/study/kouyu-zhenti/v1/show/{id}"


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def first_value(item: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return ""


def parse_jsonish(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    if value is None:
        return {}
    return value


class IdictationClient:
    def __init__(self, cookie: str, token: str, delay: float, verify_ssl: bool) -> None:
        self.cookie = cookie
        self.token = token
        self.delay = delay
        self.ssl_context = None if verify_ssl else ssl._create_unverified_context()

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = BASE_URL + path
        signed_payload = sign_payload(path, payload)
        body = json.dumps(signed_payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Origin": BASE_URL,
            "Referer": BASE_URL + "/main/book",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
            ),
        }
        if self.cookie:
            headers["Cookie"] = self.cookie
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            headers["token"] = self.token

        request = Request(url, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=30, context=self.ssl_context) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} from {path}: {raw[:500]}") from exc
        except URLError as exc:
            raise RuntimeError(f"Request failed for {path}: {exc}") from exc

        if self.delay:
            time.sleep(self.delay)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Non-JSON response from {path}: {raw[:500]}") from exc

        status = data.get("status")
        if status not in (None, 0, 1, 200, "0", "1", "200", True):
            message = data.get("message") or data.get("msg") or ""
            raise RuntimeError(f"API status {status} from {path}: {message}")
        return data


def unwrap_values(response: dict[str, Any]) -> Any:
    for key in ("values", "data", "result"):
        if key in response:
            return response[key]
    return response


def sign_payload(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = {key: value for key, value in payload.items() if value is not None}
    data["api_key"] = quote_api_key(path)
    data["timestamp"] = int(time.time())
    data["nonce"] = random_nonce()
    canonical_parts = []
    for key in sorted(data):
        value = data[key]
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        canonical_parts.append(f"{key}={value}")
    canonical = "&".join(canonical_parts)
    data["sign"] = hmac.new(SIGN_SECRET.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return data


def quote_api_key(path: str) -> str:
    from urllib.parse import quote

    return quote(path, safe="")


def random_nonce() -> str:
    import random
    import string

    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(10))


def find_items(value: Any) -> list[dict[str, Any]]:
    value = parse_jsonish(value)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, dict):
        return []

    for key in ("list", "data", "rows", "records", "items", "values"):
        if key in value:
            items = find_items(value[key])
            if items:
                return items

    candidates: list[dict[str, Any]] = []
    for nested in value.values():
        if isinstance(nested, list):
            candidates.extend(item for item in nested if isinstance(item, dict))
    return candidates


def material_id(item: dict[str, Any]) -> str:
    value = first_value(
        item,
        [
            "oral_materials_id",
            "mkt_oral_materials_id",
            "materials_id",
            "material_id",
            "id",
        ],
    )
    return str(value)


def normalize_material(item: dict[str, Any], source_part: str) -> dict[str, Any]:
    return {
        "material_id": material_id(item),
        "source_part": source_part,
        "part_type": first_value(item, ["part_type", "type", "mkt_oral_materials_part_type"]),
        "title": clean_text(
            first_value(
                item,
                [
                    "mkt_oral_materials_title",
                    "title",
                    "name",
                    "topic_title",
                    "mkt_topic_title",
                ],
            )
        ),
        "updated_at": first_value(item, ["updated_at", "update_time", "mtime", "created_at"]),
        "raw": item,
    }


def extract_topic(response: dict[str, Any]) -> dict[str, Any]:
    value = parse_jsonish(unwrap_values(response))
    if isinstance(value, dict) and isinstance(value.get("topic"), dict):
        return value["topic"]
    if isinstance(value, dict):
        return value
    return {}


def normalize_issue(raw: dict[str, Any], part: str, material: dict[str, Any]) -> dict[str, Any]:
    answer_ideas = parse_jsonish(raw.get("answer_ideas"))
    prompt = clean_text(
        first_value(
            raw,
            [
                "mkt_topic_issues_title",
                "question_title",
                "topic_problem",
                "problem_prompt",
                "title",
            ],
        )
    )
    if not prompt and isinstance(answer_ideas, dict):
        prompt = clean_text(answer_ideas.get("question"))

    return {
        "material_id": material["material_id"],
        "material_title": material["title"],
        "part": part,
        "issue_id": first_value(raw, ["topic_issues_id", "id", "issue_id"]),
        "question": prompt,
        "updated_at": first_value(raw, ["updated_at", "update_time", "created_at"]) or material["updated_at"],
        "suggested_time": first_value(raw, ["mkt_topic_issues_time", "prompt_effective_time"]),
        "raw": raw,
    }


def extract_issues(topic: dict[str, Any], material: dict[str, Any]) -> list[dict[str, Any]]:
    detail = parse_jsonish(topic.get("detail_text"))
    rows: list[dict[str, Any]] = []

    if isinstance(detail, dict):
        list_part = "Part 3" if material.get("source_part") == "part23" else "Part 1"
        part2_ids = {
            str(raw.get("topic_issues_id") or raw.get("id") or "")
            for raw in detail.get("tIssuesPart2") or []
            if isinstance(raw, dict)
        }
        for raw in detail.get("mktTopicIssuesList") or []:
            if isinstance(raw, dict):
                raw_id = str(raw.get("topic_issues_id") or raw.get("id") or "")
                if material.get("source_part") == "part23" and (
                    raw_id in part2_ids or str(raw.get("topic_problem") or "") == "1"
                ):
                    continue
                rows.append(normalize_issue(raw, list_part, material))
        for raw in detail.get("tIssuesPart2") or []:
            if isinstance(raw, dict):
                rows.append(normalize_issue(raw, "Part 2", material))

    if not rows:
        part_type = str(topic.get("part_type") or material.get("part_type") or "")
        fallback_part = {"1": "Part 1", "2": "Part 2", "3": "Part 3"}.get(part_type, material["source_part"])
        for raw in topic.get("topic_issues") or []:
            if isinstance(raw, dict):
                rows.append(normalize_issue(raw, fallback_part, material))

    return rows


def build_payload(page: int, page_size: int, extra: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "page": page,
        "page_no": page,
        "pageNum": page,
        "page_size": page_size,
        "pageSize": page_size,
        "limit": page_size,
    }
    payload.update(extra)
    return payload


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def dedupe_issue_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    unique_rows: list[dict[str, Any]] = []
    for row in rows:
        key = (
            str(row.get("material_id", "")),
            str(row.get("part", "")),
            str(row.get("issue_id", "")),
            str(row.get("question", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    return unique_rows


def read_text_file(path: str) -> str:
    return Path(path).expanduser().read_text(encoding="utf-8").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Export idictation speaking topics visible to your account.")
    parser.add_argument("--cookie", default=os.environ.get("IDICTATION_COOKIE", ""), help="Logged-in Cookie header.")
    parser.add_argument("--cookie-file", default="", help="File containing the logged-in Cookie header.")
    parser.add_argument("--token", default=os.environ.get("IDICTATION_TOKEN", ""), help="Optional auth token.")
    parser.add_argument("--output-dir", default="data/idictation_speaking", help="Directory for CSV/JSON outputs.")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests in seconds.")
    parser.add_argument("--list-payload-json", default="{}", help="Extra JSON merged into list payloads.")
    parser.add_argument("--no-details", action="store_true", help="Only export topic/material lists.")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification if local Python certificates are broken.",
    )
    args = parser.parse_args()

    cookie = args.cookie_file and read_text_file(args.cookie_file) or args.cookie
    extra_payload = json.loads(args.list_payload_json)
    out_dir = Path(args.output_dir)
    client = IdictationClient(cookie=cookie, token=args.token, delay=args.delay, verify_ssl=not args.insecure)

    materials_by_id: dict[str, dict[str, Any]] = {}
    raw_lists: dict[str, list[dict[str, Any]]] = {}

    for source_part, endpoint in LIST_ENDPOINTS.items():
        raw_lists[source_part] = []
        for page in range(1, args.max_pages + 1):
            payload = build_payload(page, args.page_size, extra_payload)
            print(f"Fetching {source_part} list page {page}...", file=sys.stderr)
            response = client.post_json(endpoint, payload)
            raw_lists[source_part].append({"payload": payload, "response": response})
            items = find_items(unwrap_values(response))
            if not items:
                break
            for item in items:
                material = normalize_material(item, source_part)
                if material["material_id"]:
                    materials_by_id.setdefault(material["material_id"], material)
            if len(items) < args.page_size:
                break

    materials = list(materials_by_id.values())
    materials.sort(key=lambda row: (str(row["source_part"]), str(row["material_id"])))

    details: list[dict[str, Any]] = []
    raw_details: dict[str, Any] = {}
    if not args.no_details:
        for index, material in enumerate(materials, start=1):
            mid = material["material_id"]
            print(f"Fetching detail {index}/{len(materials)}: {mid}...", file=sys.stderr)
            response = client.post_json(SHOW_ENDPOINT.format(id=mid), {})
            raw_details[mid] = response
            topic = extract_topic(response)
            details.extend(extract_issues(topic, material))
        details = dedupe_issue_rows(details)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        out_dir / "speaking_materials.csv",
        materials,
        ["material_id", "source_part", "part_type", "title", "updated_at"],
    )
    write_csv(
        out_dir / "speaking_questions.csv",
        details,
        ["material_id", "material_title", "part", "issue_id", "question", "updated_at", "suggested_time"],
    )
    (out_dir / "speaking_materials.raw.json").write_text(
        json.dumps({"lists": raw_lists, "materials": materials}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "speaking_details.raw.json").write_text(
        json.dumps({"details": details, "raw": raw_details}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Exported {len(materials)} materials and {len(details)} questions to {out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
