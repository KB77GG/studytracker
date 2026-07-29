#!/usr/bin/env python3
"""Validate a StudyTracker TOEFL practice v2 package.

The validator intentionally checks more than JSON Schema: answer leakage,
cross-file references, grading coverage, and source traceability are release
gates for regenerated real-exam content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc  # noqa: UP017  # Python 3.10 production compatibility.

FORBIDDEN_PUBLIC_KEYS = {
    "answer",
    "answers",
    "answer_key",
    "correct_answer",
    "correct_option_keys",
    "canonical_text",
    "accepted_text",
    "canonical_full_word",
    "ordered_tokens",
}
SPEAKING_RESPONSE_SECONDS = {
    "listen_and_repeat": 12,
    "take_an_interview": 45,
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_forbidden_keys(value: Any, location: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in FORBIDDEN_PUBLIC_KEYS:
                errors.append(f"{location}.{key}: answer material leaked into content.json")
            errors.extend(find_forbidden_keys(child, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(find_forbidden_keys(child, f"{location}[{index}]"))
    return errors


def schema_errors(content: dict[str, Any], schema_path: Path) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return []

    schema = load_json(schema_path)
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    return [
        f"schema {'.'.join(str(p) for p in error.absolute_path) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(content), key=lambda item: list(item.absolute_path))
    ]


def validate_package(package_dir: Path, schema_path: Path, source_root: Path | None = None) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    required = ["content.json", "answer_key.json", "manifest.json", "qa_report.json"]
    missing = [name for name in required if not (package_dir / name).is_file()]
    if missing:
        return [f"missing package file: {name}" for name in missing], {}

    content = load_json(package_dir / "content.json")
    answer_key = load_json(package_dir / "answer_key.json")
    manifest = load_json(package_dir / "manifest.json")

    errors.extend(schema_errors(content, schema_path))
    errors.extend(find_forbidden_keys(content))

    modules = content.get("modules", [])
    groups = content.get("groups", [])
    questions = content.get("questions", [])
    assets = content.get("assets", [])
    answers = answer_key.get("answers", [])

    def unique_ids(items: list[dict[str, Any]], label: str) -> set[str]:
        ids = [item.get("id") for item in items]
        duplicates = sorted(key for key, count in Counter(ids).items() if count > 1)
        errors.extend(f"duplicate {label} id: {key}" for key in duplicates)
        if any(not key for key in ids):
            errors.append(f"blank {label} id")
        return {key for key in ids if key}

    module_ids = unique_ids(modules, "module")
    group_ids = unique_ids(groups, "group")
    question_ids = unique_ids(questions, "question")
    asset_ids = unique_ids(assets, "asset")
    answer_ids = unique_ids([{"id": item.get("question_id")} for item in answers], "answer")

    for module in modules:
        for group_id in module.get("group_ids", []):
            if group_id not in group_ids:
                errors.append(f"module {module['id']} references unknown group {group_id}")
        for asset_id in module.get("asset_ids", []):
            if asset_id not in asset_ids:
                errors.append(f"module {module['id']} references unknown asset {asset_id}")

    for group in groups:
        if group.get("module_id") not in module_ids:
            errors.append(f"group {group['id']} references unknown module {group.get('module_id')}")
        for question_id in group.get("question_ids", []):
            if question_id not in question_ids:
                errors.append(f"group {group['id']} references unknown question {question_id}")

    for question in questions:
        qid = question["id"]
        if question.get("module_id") not in module_ids:
            errors.append(f"question {qid} references unknown module {question.get('module_id')}")
        if question.get("group_id") not in group_ids:
            errors.append(f"question {qid} references unknown group {question.get('group_id')}")
        if question.get("response_type") == "mc" and question.get("content_status") != "missing_options":
            options = question.get("options", [])
            keys = [option.get("key") for option in options]
            if len(options) != 4 or len(set(keys)) != 4:
                errors.append(f"question {qid}: ready multiple-choice item must have four unique options")
        if question.get("grading_status") == "auto" and qid not in answer_ids:
            errors.append(f"question {qid}: auto grading has no answer entry")
        if question.get("grading_status") == "blocked" and qid in answer_ids:
            errors.append(f"question {qid}: blocked question must not expose a usable answer entry")

    group_by_id = {item["id"]: item for item in groups}
    asset_by_id = {item["id"]: item for item in assets}
    speaking_questions = [
        item for item in questions if item.get("subject") == "speaking"
    ]
    release_authorization = (
        manifest.get("quality", {}).get("release_authorization") or {}
    )
    speaking_contract_required = (
        release_authorization.get("status") == "owner_authorized"
    )
    if speaking_questions and speaking_contract_required:
        if len(speaking_questions) != 11:
            errors.append(
                f"speaking must contain 11 atomic questions, found {len(speaking_questions)}"
            )
        speaking_duration = sum(
            int(module.get("duration_seconds") or 0)
            for module in modules
            if module.get("subject") == "speaking"
        )
        if speaking_duration != 480:
            errors.append(
                f"speaking module durations must total 480 seconds, found {speaking_duration}"
            )
        for question in speaking_questions:
            qid = question["id"]
            group = group_by_id.get(question.get("group_id")) or {}
            config = question.get("input_config") or {}
            expected_response = SPEAKING_RESPONSE_SECONDS.get(
                group.get("task_type")
            )
            if config.get("preparation_seconds") != 0:
                errors.append(f"question {qid}: speaking preparation must be 0 seconds")
            if config.get("response_seconds") != expected_response:
                errors.append(
                    f"question {qid}: response_seconds does not match its task type"
                )
            if group.get("question_ids") != [qid]:
                errors.append(
                    f"question {qid}: speaking group must contain exactly this question"
                )
            stimulus = group.get("stimulus") or {}
            cue_start = stimulus.get("cue_start_seconds")
            cue_end = stimulus.get("cue_end_seconds")
            confidence = stimulus.get("alignment_confidence")
            asset = asset_by_id.get(stimulus.get("asset_id")) or {}
            asset_duration = asset.get("source", {}).get("duration_seconds")
            if (
                stimulus.get("format") != "audio_cue"
                or not isinstance(cue_start, (int, float))
                or not isinstance(cue_end, (int, float))
                or cue_start < 0
                or cue_end <= cue_start
                or not isinstance(asset_duration, (int, float))
                or cue_end > asset_duration + 0.05
                or not isinstance(confidence, (int, float))
                or confidence < 0.96
            ):
                errors.append(f"question {qid}: speaking audio cue is invalid")

    unknown_answers = sorted(answer_ids - question_ids)
    errors.extend(f"answer references unknown question: {qid}" for qid in unknown_answers)

    question_by_id = {item["id"]: item for item in questions}
    for answer in answers:
        qid = answer["question_id"]
        question = question_by_id.get(qid)
        if not question:
            continue
        response_type = question.get("response_type")
        if response_type == "mc" and not answer.get("correct_option_keys"):
            errors.append(f"answer {qid}: missing correct_option_keys")
        if response_type == "mc" and answer.get("correct_option_keys"):
            option_keys = {option.get("key") for option in question.get("options", [])}
            unknown_keys = sorted(set(answer.get("correct_option_keys", [])) - option_keys)
            if unknown_keys:
                errors.append(f"answer {qid}: correct option key not present in public options: {', '.join(unknown_keys)}")
        if response_type == "text" and not answer.get("canonical_text"):
            errors.append(f"answer {qid}: missing canonical_text")
        if response_type == "order":
            ordered = answer.get("ordered_tokens", [])
            scrambled = question.get("input_config", {}).get("scramble_tokens", [])
            if not ordered or Counter(ordered) != Counter(scrambled):
                errors.append(f"answer {qid}: scramble tokens do not match ordered tokens")

    expected = content.get("exam", {}).get("expected_question_count")
    if expected != len(questions):
        errors.append(f"expected_question_count={expected}, actual={len(questions)}")

    if manifest.get("exam_id") != content.get("exam", {}).get("id"):
        errors.append("manifest exam_id does not match content exam id")

    if source_root:
        checked: set[tuple[str, str]] = set()
        refs: list[dict[str, Any]] = []
        refs.extend(asset.get("source", {}) for asset in assets)
        for item in groups + questions:
            refs.extend(item.get("source_refs", []))
        for ref in refs:
            path_value = ref.get("path")
            expected_hash = ref.get("sha256")
            if not path_value or not expected_hash or (path_value, expected_hash) in checked:
                continue
            checked.add((path_value, expected_hash))
            source_path = source_root / path_value
            if not source_path.is_file():
                errors.append(f"source missing: {path_value}")
            elif sha256(source_path) != expected_hash:
                errors.append(f"source hash mismatch: {path_value}")

    summary = {
        "exam_id": content.get("exam", {}).get("id"),
        "questions": len(questions),
        "auto": sum(item.get("grading_status") == "auto" for item in questions),
        "manual": sum(item.get("grading_status") == "manual" for item in questions),
        "blocked": sum(item.get("grading_status") == "blocked" for item in questions),
        "validation_errors": len(errors),
    }
    return errors, summary


def release_blockers(
    content: dict[str, Any],
    answer_key: dict[str, Any],
    manifest: dict[str, Any],
    summary: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    blocked_count = summary.get("blocked", 0)
    if blocked_count:
        blockers.append(f"{blocked_count} question(s) remain blocked")

    availability = content.get("exam", {}).get("availability_status")
    if availability not in {"reviewed", "published"}:
        blockers.append(
            f"exam availability_status is {availability!r}; expected 'reviewed' or 'published'"
        )

    publish_status = manifest.get("quality", {}).get("publish_status")
    if publish_status not in {"ready", "published"}:
        blockers.append(
            f"manifest quality.publish_status is {publish_status!r}; expected 'ready' or 'published'"
        )

    required_subjects = {"reading", "listening", "writing", "speaking"}
    subject_reviews = manifest.get("quality", {}).get("subject_reviews", {})
    pending_subjects = sorted(
        subject
        for subject in required_subjects
        if subject_reviews.get(subject) != "approved"
    )
    authorization = manifest.get("quality", {}).get("release_authorization") or {}
    authorized_scope = set(authorization.get("scope") or [])
    owner_authorized = (
        authorization.get("status") == "owner_authorized"
        and required_subjects.issubset(authorized_scope)
    )
    if pending_subjects and not owner_authorized:
        blockers.append(
            "subject source review is not approved: " + ", ".join(pending_subjects)
        )

    public_audio = [
        asset
        for asset in content.get("assets", [])
        if asset.get("kind") == "audio"
        and asset.get("subject") in {"listening", "speaking"}
    ]
    unavailable_audio = [
        asset.get("id", "unknown")
        for asset in public_audio
        if asset.get("delivery", {}).get("status") != "published"
        or not str(asset.get("delivery", {}).get("url") or "").startswith(
            "/static/toefl/v2/"
        )
    ]
    if unavailable_audio:
        blockers.append(
            "required audio is not published: " + ", ".join(unavailable_audio)
        )

    groups = {
        item.get("id"): item
        for item in content.get("groups", [])
        if item.get("subject") == "speaking"
    }
    assets = {
        item.get("id"): item
        for item in content.get("assets", [])
        if item.get("subject") == "speaking" and item.get("kind") == "audio"
    }
    speaking_questions = [
        item
        for item in content.get("questions", [])
        if item.get("subject") == "speaking"
    ]
    speaking_duration = sum(
        int(module.get("duration_seconds") or 0)
        for module in content.get("modules", [])
        if module.get("subject") == "speaking"
    )

    def speaking_question_ready(question: dict[str, Any]) -> bool:
        group = groups.get(question.get("group_id")) or {}
        stimulus = group.get("stimulus") or {}
        config = question.get("input_config") or {}
        cue_start = stimulus.get("cue_start_seconds")
        cue_end = stimulus.get("cue_end_seconds")
        confidence = stimulus.get("alignment_confidence")
        asset_duration = (
            assets.get(stimulus.get("asset_id")) or {}
        ).get("source", {}).get("duration_seconds")
        return (
            config.get("preparation_seconds") == 0
            and config.get("response_seconds")
            == SPEAKING_RESPONSE_SECONDS.get(group.get("task_type"))
            and group.get("question_ids") == [question.get("id")]
            and stimulus.get("format") == "audio_cue"
            and isinstance(cue_start, (int, float))
            and isinstance(cue_end, (int, float))
            and cue_end > cue_start >= 0
            and isinstance(confidence, (int, float))
            and confidence >= 0.96
            and isinstance(asset_duration, (int, float))
            and cue_end <= asset_duration + 0.05
        )

    speaking_contract_ready = (
        len(speaking_questions) == 11
        and speaking_duration == 480
        and all(speaking_question_ready(question) for question in speaking_questions)
    )
    if not speaking_contract_ready:
        blockers.append("speaking 2026 per-question audio/timing contract is incomplete")

    blocked_entries = answer_key.get("blocked", [])
    if len(blocked_entries) != blocked_count:
        blockers.append(
            "answer_key blocked-entry count does not match blocked questions "
            f"({len(blocked_entries)} != {blocked_count})"
        )
    return blockers


def portable_package_path(package_dir: Path) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        return str(package_dir.relative_to(repo_root))
    except ValueError:
        return str(package_dir)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("--schema", type=Path, default=Path(__file__).resolve().parents[1] / "schemas/toefl_practice_v2.schema.json")
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--report", type=Path, help="Write a machine-readable validation result.")
    parser.add_argument(
        "--require-release-ready",
        action="store_true",
        help="Exit 1 unless the package is valid, reviewed, publishable, and has zero blocked questions.",
    )
    args = parser.parse_args()

    package_dir = args.package_dir.resolve()
    errors, summary = validate_package(
        package_dir,
        args.schema.resolve(),
        args.source_root.resolve() if args.source_root else None,
    )
    blockers: list[str] = []
    if not errors:
        blockers = release_blockers(
            load_json(package_dir / "content.json"),
            load_json(package_dir / "answer_key.json"),
            load_json(package_dir / "manifest.json"),
            summary,
        )
    if args.report:
        report = {
            "schema_version": "1.0.0",
            "validated_at": datetime.now(UTC).isoformat(),
            "package_dir": portable_package_path(package_dir),
            "source_root_checked": bool(args.source_root),
            "status": (
                "fail"
                if errors
                else (
                    "blocked"
                    if args.require_release_ready and blockers
                    else "pass"
                )
            ),
            "summary": summary,
            "errors": errors,
            "release_gate_checked": args.require_release_ready,
            "release_ready": not errors and not blockers,
            "release_blockers": blockers,
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.require_release_ready and blockers:
        for blocker in blockers:
            print(f"BLOCKED: {blocker}", file=sys.stderr)
        return 1
    suffix = "release-ready" if args.require_release_ready else "source-traceable"
    print(f"PASS: TOEFL practice v2 package is internally consistent and {suffix}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
