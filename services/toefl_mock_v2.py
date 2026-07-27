"""Definition and scoring services for source-backed TOEFL v2 mock packages."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

SECTION_ORDER = ("reading", "listening", "speaking", "writing")
PACKAGE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_[A-Z]$")
WRITING_TIMERS = {
    "build_a_sentence": 420,
    "write_email": 420,
    "academic_discussion": 600,
}
MODULE_TIMERS = {
    ("reading", "m1"): 1080,
    ("reading", "m2"): 540,
    ("speaking", "m1"): 420,
    ("speaking", "m2"): 540,
}


class PackageNotFoundError(LookupError):
    """Raised when a requested v2 package does not exist."""


class PackageReleaseBlockedError(ValueError):
    """Raised when a non-preview attempt targets an unreleased package."""


def data_root() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "toefl_practice_v2"


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _package_dirs(root: Path | None = None) -> list[Path]:
    base = root or data_root()
    return sorted(
        path
        for path in base.iterdir()
        if path.is_dir()
        and PACKAGE_PATTERN.fullmatch(path.name)
        and (path / "content.json").is_file()
    )


def resolve_package(test_id: str, root: Path | None = None) -> Path:
    raw = str(test_id or "").strip()
    base = root or data_root()
    direct = base / raw
    if direct.is_dir() and (direct / "content.json").is_file():
        return direct
    lowered = raw.lower()
    for package_dir in _package_dirs(base):
        content = load_json(package_dir / "content.json")
        if content.get("exam", {}).get("id", "").lower() == lowered:
            return package_dir
    raise PackageNotFoundError(f"Unknown TOEFL v2 test: {test_id}")


def _release_blockers(
    content: dict[str, Any], manifest: dict[str, Any]
) -> list[str]:
    counts = manifest.get("counts", {})
    blockers: list[str] = []
    blocked_count = counts.get("blocked", 0)
    if blocked_count:
        blockers.append(f"{blocked_count} question(s) remain source-blocked")
    availability = content.get("exam", {}).get("availability_status")
    if availability not in {"reviewed", "published"}:
        blockers.append(f"availability_status={availability!r}")
    publish_status = manifest.get("quality", {}).get("publish_status")
    if publish_status not in {"ready", "published"}:
        blockers.append(f"publish_status={publish_status!r}")
    reviews = manifest.get("quality", {}).get("subject_reviews", {})
    pending = [
        subject for subject in SECTION_ORDER if reviews.get(subject) != "approved"
    ]
    if pending:
        blockers.append("source review pending: " + ", ".join(pending))
    return blockers


def _validation_status(package_dir: Path) -> str:
    path = package_dir / "validation_result.json"
    if not path.is_file():
        return "not_run"
    return str(load_json(path).get("status", "unknown"))


def catalog(root: Path | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for package_dir in _package_dirs(root):
        content = load_json(package_dir / "content.json")
        manifest = load_json(package_dir / "manifest.json")
        blockers = _release_blockers(content, manifest)
        rows.append(
            {
                "slug": package_dir.name,
                "id": content["exam"]["id"],
                "title": content["exam"]["title"],
                "date": content["exam"]["date"],
                "variant": content["exam"]["variant"],
                "counts": manifest.get("counts", {}),
                "validation_status": _validation_status(package_dir),
                "publish_status": manifest.get("quality", {}).get(
                    "publish_status", "unknown"
                ),
                "subject_reviews": manifest.get("quality", {}).get(
                    "subject_reviews", {}
                ),
                "release_ready": not blockers,
                "release_blockers": blockers,
                "preview_url": f"/toefl/mock/{package_dir.name}?preview=1",
            }
        )
    return rows


def parse_sections(raw_sections: str | list[str] | None) -> list[str]:
    if raw_sections is None:
        return list(SECTION_ORDER)
    values = (
        raw_sections
        if isinstance(raw_sections, list)
        else re.split(r"[|,]", raw_sections)
    )
    requested = {str(value).strip().lower() for value in values}
    sections = [subject for subject in SECTION_ORDER if subject in requested]
    if not sections:
        raise ValueError("No valid TOEFL sections were selected")
    return sections


def _public_asset(asset: dict[str, Any]) -> dict[str, Any]:
    source = asset.get("source", {})
    public = {
        key: deepcopy(asset[key])
        for key in ("id", "kind", "subject", "module_id")
        if key in asset
    }
    delivery = asset.get("delivery", {})
    public["delivery"] = {
        "status": delivery.get("status", "unavailable"),
        "url": delivery.get("url"),
    }
    if source.get("duration_seconds") is not None:
        public["duration_seconds"] = source["duration_seconds"]
    return public


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    public = deepcopy(record)
    public.pop("source_refs", None)
    return public


def _phase_plan(
    modules: list[dict[str, Any]], groups: list[dict[str, Any]], sections: list[str]
) -> list[dict[str, Any]]:
    phases: list[dict[str, Any]] = []
    groups_by_module: dict[str, list[dict[str, Any]]] = {}
    for group in groups:
        groups_by_module.setdefault(group["module_id"], []).append(group)
    for subject in sections:
        subject_modules = sorted(
            (item for item in modules if item["subject"] == subject),
            key=lambda item: item.get("order", 0),
        )
        for module in subject_modules:
            module_key = str(module.get("module", "m1"))
            if subject != "writing":
                phases.append(
                    {
                        "id": f"{subject}:{module_key}",
                        "section": subject,
                        "module": module_key,
                        "module_id": module["id"],
                        "label": module.get("label", f"{subject} {module_key}"),
                        "duration_seconds": MODULE_TIMERS.get(
                            (subject, module_key)
                        ),
                        "timer_mode": (
                            "countdown"
                            if (subject, module_key) in MODULE_TIMERS
                            else "audio_driven"
                        ),
                        "adaptive_checkpoint": (
                            module_key == "m1"
                            and subject in {"reading", "listening"}
                        ),
                    }
                )
                continue
            for group in sorted(
                groups_by_module.get(module["id"], []),
                key=lambda item: item.get("order", 0),
            ):
                task_type = group.get("task_type", "writing")
                phases.append(
                    {
                        "id": f"writing:{task_type}",
                        "section": "writing",
                        "module": module_key,
                        "module_id": module["id"],
                        "group_id": group["id"],
                        "label": group.get("title", task_type.replace("_", " ").title()),
                        "duration_seconds": WRITING_TIMERS.get(task_type),
                        "timer_mode": "countdown",
                        "adaptive_checkpoint": False,
                    }
                )
    return phases


def definition(
    test_id: str,
    sections: str | list[str] | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    package_dir = resolve_package(test_id, root)
    content = load_json(package_dir / "content.json")
    manifest = load_json(package_dir / "manifest.json")
    selected = parse_sections(sections)
    modules = [
        _public_record(item)
        for item in content.get("modules", [])
        if item.get("subject") in selected
    ]
    module_ids = {item["id"] for item in modules}
    groups = [
        _public_record(item)
        for item in content.get("groups", [])
        if item.get("module_id") in module_ids
    ]
    group_ids = {item["id"] for item in groups}
    questions = [
        {
            **_public_record(item),
            "available": item.get("grading_status") != "blocked",
        }
        for item in content.get("questions", [])
        if item.get("group_id") in group_ids
    ]
    blockers = _release_blockers(content, manifest)
    exam = content["exam"]
    return {
        "schema_version": "1.0.0",
        "test": {
            key: deepcopy(exam[key])
            for key in (
                "id",
                "title",
                "date",
                "variant",
                "source_kind",
                "expected_question_count",
                "availability_status",
            )
            if key in exam
        }
        | {
            "slug": package_dir.name,
        },
        "sections": selected,
        "section_order": list(SECTION_ORDER),
        "phases": _phase_plan(modules, groups, selected),
        "modules": modules,
        "groups": groups,
        "questions": questions,
        "assets": [
            _public_asset(item)
            for item in content.get("assets", [])
            if item.get("subject") in selected or item.get("subject") == "exam"
        ],
        "adaptive": {
            subject: {
                "available": False,
                "branches": ["default"],
                "reason": (
                    "This source set contains one verified Module 2 only; "
                    "no easy/hard branch is inferred."
                ),
            }
            for subject in ("reading", "listening")
            if subject in selected
        },
        "release": {
            "ready": not blockers,
            "preview_required": bool(blockers),
            "blockers": blockers,
            "validation_status": _validation_status(package_dir),
        },
    }


def require_attempt_allowed(mock_definition: dict[str, Any], preview: bool) -> None:
    if not preview and not mock_definition["release"]["ready"]:
        raise PackageReleaseBlockedError(
            "This package is available only as an explicitly labelled staging preview"
        )


def load_private_answer_key(test_id: str, root: Path | None = None) -> dict[str, Any]:
    package_dir = resolve_package(test_id, root)
    return load_json(package_dir / "answer_key.json")


def _normalise_scalar(value: Any) -> str:
    return str(value if value is not None else "").strip().casefold()


def answer_is_correct(answer: dict[str, Any], response: Any) -> bool:
    if "correct_option_keys" in answer:
        expected = sorted(_normalise_scalar(item) for item in answer["correct_option_keys"])
        actual_values = response if isinstance(response, list) else [response]
        return sorted(_normalise_scalar(item) for item in actual_values) == expected
    if "ordered_tokens" in answer:
        return list(response or []) == answer["ordered_tokens"]
    accepted = answer.get("accepted_text") or answer.get("accepted_texts")
    if accepted:
        values = accepted if isinstance(accepted, list) else [accepted]
        return _normalise_scalar(response) in {
            _normalise_scalar(value) for value in values
        }
    if "canonical_text" in answer:
        return _normalise_scalar(response) == _normalise_scalar(
            answer["canonical_text"]
        )
    return False


def score_responses(
    test_id: str,
    responses: dict[str, Any],
    *,
    question_ids: set[str] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    answer_key = load_private_answer_key(test_id, root)
    answers = [
        item
        for item in answer_key.get("answers", [])
        if question_ids is None or item.get("question_id") in question_ids
    ]
    results = [
        {
            "question_id": answer["question_id"],
            "answered": answer["question_id"] in responses,
            "correct": answer_is_correct(
                answer, responses.get(answer["question_id"])
            ),
        }
        for answer in answers
    ]
    correct = sum(item["correct"] for item in results)
    return {
        "correct": correct,
        "auto_total": len(results),
        "answered": sum(item["answered"] for item in results),
        "accuracy": round(correct / len(results), 4) if results else None,
        "results": results,
    }


def route_module_two(
    test_id: str,
    subject: str,
    responses: dict[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    mock_definition = definition(test_id, [subject], root=root)
    m1 = next(
        (
            item
            for item in mock_definition["modules"]
            if item["subject"] == subject and item.get("module") == "m1"
        ),
        None,
    )
    if not m1:
        raise ValueError(f"No {subject} Module 1 exists")
    question_ids = {
        item["id"]
        for item in mock_definition["questions"]
        if item["module_id"] == m1["id"]
    }
    score = score_responses(
        test_id, responses, question_ids=question_ids, root=root
    )
    return {
        "subject": subject,
        "route": "default",
        "adaptive_available": False,
        "score": score,
        "reason": (
            "Only one source-verified Module 2 exists; the engine will not "
            "invent easy/hard content."
        ),
    }
