#!/usr/bin/env python3
"""Recheck the reviewed 2026-11-15 hotlist mappings against saved public exams.

This is an offline audit, not a fuzzy title matcher or answer-key importer.
Titles only nominated candidates; every mapping below was checked against all
ten question stems/options and the existing listening transcript. New candidates
require review before adding them to REVIEWED_MATCHES.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.exam_sprint import content_digest  # noqa: E402

# Source unit IDs stay strings: they exceed JavaScript's safe integer range.
REVIEWED_MATCHES = {
    "2017124496722989058": "xiahuar_017_p1",
    "2072889406625742849": "xiahuar_096_p1",
    "2021494303475990529": "xiahuar_050_p1",
    "2068932085801353218": "xiahuar_064_p1",
    "2017124496806875139": "xiahuar_023_p2",
    "2032409935532883969": "xiahuar_040_p2",
    "2017124496836235265": "xiahuar_019_p3",
    "2017124496899149826": "xiahuar_048_p3",
    "2033420799996166145": "xiahuar_039_p3",
    "2021837800313815041": "xiahuar_020_p4",
    "2047925917235908610": "xiahuar_109_p4",
    "2017124496936898562": "xiahuar_008_p4",
    "2021829152476856322": "xiahuar_024_p4",
    "2021829927332577281": "xiahuar_094_p4",
    "2062075620860411906": "xiahuar_006_p4",
    "2029791132152070146": "xiahuar_084_p4",
}


def comparison_text(value: str | None) -> str:
    """Ignore layout/punctuation, retaining substantive words and numeric data."""
    value = html.unescape(str(value or ""))
    value = re.sub(r"<input\b[^>]*>", " BLANK ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\$\d+\$", " BLANK ", value)
    value = re.sub(r"\b\d+\.?\s*_+", " BLANK ", value)
    value = re.sub(r"_+", " BLANK ", value)
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def options_signature(options: list[dict]) -> list[tuple[str, str]]:
    return [
        (
            comparison_text(option.get("optionNum", option.get("title"))),
            comparison_text(option.get("optionContent", option.get("content"))),
        )
        for option in options
    ]


def source_questions(part: dict) -> list[tuple[str, str, list]]:
    result = []
    for group in part["groups"]:
        if group.get("image") or group.get("imageUrl"):
            raise ValueError("Image-dependent questions require a separate visual review")
        for question in group["questions"]:
            number = str(question["qNumber"])
            title = question.get("question")
            if not title:
                rows = re.findall(
                    r"<tr\b[^>]*>.*?</tr>", group.get("contentHtml") or "", re.S | re.I
                )
                pattern = r'<input\b[^>]*placeholder=["\']' + re.escape(number) + r'["\']'
                matches = [row for row in rows if re.search(pattern, row)]
                if len(matches) != 1:
                    raise ValueError(f"Cannot identify one source stem for Q{number}")
                title = matches[0]
            result.append(
                (
                    number,
                    comparison_text(title),
                    options_signature(question.get("options") or group.get("options") or []),
                )
            )
    return result


def local_questions(part: dict) -> list[tuple[str, str, list]]:
    result = []
    for group in part["groups"]:
        for question in group["items"]:
            if not str(question.get("answer") or "").strip():
                raise ValueError("Local question has no existing answer key")
            result.append(
                (
                    str(question["number"]),
                    comparison_text(question.get("title")),
                    options_signature(
                        question.get("options")
                        or group.get("collect_options", {}).get("list")
                        or []
                    ),
                )
            )
    return result


def transcript_coverage(source: dict, local: dict) -> float:
    transcript = source.get("article")
    if not transcript:
        article = json.loads(source.get("articleJson") or "{}")
        transcript = " ".join(
            " ".join(sentence.get("text", "") for sentence in segment.get("sentences", []))
            or segment.get("text", "")
            for segment in article.get("segments", [])
        )
    source_words = comparison_text(transcript).split()
    target_words = comparison_text(
        " ".join(line.get("en_text", "") for line in local.get("content", []))
    ).split()
    if len(source_words) < 100 or len(target_words) < 100:
        raise ValueError("Transcript evidence is insufficient")
    matcher = difflib.SequenceMatcher(None, source_words, target_words, autojunk=False)
    return sum(block.size for block in matcher.get_matching_blocks()) / len(source_words)


def verify_pair(payload: dict, local: dict, source_id: str) -> dict:
    data = payload["data"]
    if data.get("id") != source_id or data.get("channel") != "listening":
        raise ValueError("Source identity/subject differs")
    if len(data.get("parts", [])) != 1:
        raise ValueError("Expected exactly one source Part")
    part = data["parts"][0]
    if part.get("partNum") != f"Part {local['part_number']}":
        raise ValueError("Part numbers differ")
    source_rows = source_questions(part)
    local_rows = local_questions(local)
    if len(source_rows) != 10 or len(local_rows) != 10 or source_rows != local_rows:
        raise ValueError("The complete question numbers/stems/options are not identical")
    coverage = transcript_coverage(part, local)
    if coverage < 0.92:
        raise ValueError("Transcript version needs additional review")
    return {
        "question_count": 10,
        "identical_question_numbers_stems_options": True,
        "source_transcript_token_coverage": round(coverage, 6),
        "source_part_id": part["id"],
    }


def audit(source_dir: Path, root: Path) -> tuple[dict, dict]:
    mappings, checks = [], []
    for source_id, target_id in REVIEWED_MATCHES.items():
        source_path = source_dir / f"{source_id}.json"
        if not source_path.exists() and source_id == "2017124496722989058":
            source_path = source_dir / "listening-sample.json"
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        target_path = root / "static/listening_jijing/parts" / f"{target_id}.json"
        raw = target_path.read_bytes()
        local = json.loads(raw)
        evidence = verify_pair(payload, local, source_id)
        mapping = {
            "subject": "listening",
            "source_id": source_id,
            "source_title": payload["data"]["title"],
            "target_id": target_id,
            "source_content_sha256": content_digest(payload),
            "target_sha256": hashlib.sha256(raw).hexdigest(),
            "source_part_id": evidence["source_part_id"],
            "review_note": (
                "2026-11-15：10题题号、题干及选项逐题一致；原有录音文字版本已比对。"
                "只链接本地原题、原答案和原音频，不从来源解析生成答案。"
            ),
        }
        mappings.append(mapping)
        checks.append({"source_id": source_id, "target_id": target_id, **evidence})
    return {"schema_version": 1, "mappings": mappings}, {
        "verified_count": len(checks),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--mapping-output", type=Path)
    parser.add_argument("--report-output", type=Path)
    args = parser.parse_args()
    mappings, report = audit(args.source_dir, args.root)
    for path, payload in ((args.mapping_output, mappings), (args.report_output, report)):
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
    print(json.dumps({"verified_count": report["verified_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
