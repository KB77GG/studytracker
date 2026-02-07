#!/usr/bin/env python3
"""Batch-call an IELTS speaking evaluation API with local JSONL samples."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_AUDIO_METRICS = {
    "wpm": 110,
    "pause_count": 8,
    "avg_pause_ms": 650,
    "filler_rate": 0.04,
    "pronunciation_accuracy": 0.8,
    "stress_variation": 0.4,
    "intonation_variation": 0.42,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch-run IELTS speaking evaluations from JSONL samples."
    )
    parser.add_argument(
        "--input",
        default="data/ielts_part1_samples.jsonl",
        help="Path to input JSONL file.",
    )
    parser.add_argument(
        "--output",
        default="data/ielts_part1_eval_results.jsonl",
        help="Path to output JSONL file.",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("EVAL_API_URL"),
        help="Evaluation endpoint URL. Defaults to env EVAL_API_URL.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("EVAL_API_KEY"),
        help="API key for bearer auth. Defaults to env EVAL_API_KEY.",
    )
    parser.add_argument(
        "--answer-field",
        choices=["base_answer", "upgraded_answer"],
        default="base_answer",
        help="Which answer field from sample JSON to send as transcript.",
    )
    parser.add_argument(
        "--part-override",
        default="",
        help="Override sample part value (for example: Part1).",
    )
    parser.add_argument(
        "--part2-topic",
        default="",
        help="Part2 topic hint: person_place | object_concrete | object_abstract | storyline.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Sleep seconds between requests.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only process first N samples (0 means all).",
    )
    parser.add_argument(
        "--header",
        action="append",
        default=[],
        help="Extra HTTP header in KEY=VALUE form. Can be repeated.",
    )
    parser.add_argument(
        "--no-audio-metrics",
        action="store_true",
        help="Do not include default audio metrics in payload.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build payloads and write output without calling API.",
    )
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_extra_headers(values: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"Invalid --header value: {item!r}. Use KEY=VALUE.")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"Invalid --header key: {item!r}.")
        headers[key] = value
    return headers


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                obj = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_no}: {exc}") from exc
            if not isinstance(obj, dict):
                raise ValueError(f"Expected object at {path}:{line_no}.")
            rows.append(obj)
    return rows


def build_payload(
    sample: dict[str, Any],
    answer_field: str,
    part_override: str,
    include_audio_metrics: bool,
    part2_topic: str,
) -> dict[str, Any]:
    answer = str(sample.get(answer_field) or "").strip()
    payload: dict[str, Any] = {
        "exam": "IELTS",
        "part": part_override or sample.get("part") or "Part1",
        "sample_id": sample.get("id"),
        "question": sample.get("question", ""),
        "transcript": answer,
        "student_answer": answer,
        "metadata": {
            "source": "ielts_part1_samples",
            "base_answer": sample.get("base_answer", ""),
            "upgraded_answer": sample.get("upgraded_answer", ""),
        },
    }
    if include_audio_metrics:
        payload["audio_metrics"] = dict(DEFAULT_AUDIO_METRICS)
    topic_hint = part2_topic.strip() or str(sample.get("part2_topic") or "")
    if topic_hint:
        payload["part2_topic"] = topic_hint
    return payload


def post_json(
    url: str,
    payload: dict[str, Any],
    timeout: float,
    headers: dict[str, str],
) -> tuple[int, Any, str | None]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url=url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        req.add_header(key, value)

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            text = resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    except error.URLError as exc:
        return 0, None, str(exc.reason)
    except TimeoutError:
        return 0, None, "request_timeout"
    except OSError as exc:
        return 0, None, str(exc)

    parsed: Any
    try:
        parsed = json.loads(text) if text else {}
    except json.JSONDecodeError:
        parsed = {"raw_text": text}
    return status, parsed, None


def write_result(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()

    if not args.dry_run and not args.api_url:
        print("Error: --api-url is required (or set EVAL_API_URL).", file=sys.stderr)
        return 2

    try:
        extra_headers = parse_extra_headers(args.header)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("", encoding="utf-8")

    try:
        samples = load_jsonl(input_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.limit > 0:
        samples = samples[: args.limit]

    headers = dict(extra_headers)
    if args.api_key:
        headers.setdefault("Authorization", f"Bearer {args.api_key}")

    total = len(samples)
    success = 0
    failed = 0

    for idx, sample in enumerate(samples, start=1):
        payload = build_payload(
            sample=sample,
            answer_field=args.answer_field,
            part_override=args.part_override.strip(),
            include_audio_metrics=not args.no_audio_metrics,
            part2_topic=args.part2_topic,
        )
        started = time.perf_counter()
        if args.dry_run:
            status = 0
            response_data: Any = {"dry_run": True}
            error_msg = None
        else:
            status, response_data, error_msg = post_json(
                url=args.api_url,
                payload=payload,
                timeout=args.timeout,
                headers=headers,
            )
        latency_ms = int((time.perf_counter() - started) * 1000)

        ok = bool(args.dry_run or (200 <= status < 300 and error_msg is None))
        if ok:
            success += 1
        else:
            failed += 1

        result_row = {
            "index": idx,
            "id": sample.get("id"),
            "part": payload.get("part"),
            "question": payload.get("question"),
            "answer_field": args.answer_field,
            "status_code": status,
            "ok": ok,
            "latency_ms": latency_ms,
            "error": error_msg,
            "request_payload": payload,
            "response": response_data,
            "created_at": utc_now_iso(),
        }
        write_result(output_path, result_row)

        msg = f"[{idx}/{total}] id={sample.get('id')} status={status} ok={ok}"
        if error_msg:
            msg += f" error={error_msg}"
        print(msg)

        if args.sleep > 0 and idx < total:
            time.sleep(args.sleep)

    print(
        f"Done. total={total} success={success} failed={failed} output={output_path}",
        flush=True,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
