"""Structural quality checks for the file-backed TOEFL practice bank.

The checks in this module deliberately avoid repairing or inferring content.
They answer a narrower release question: does every published question have a
stable identity, complete response data, traceable source structure, and a
resolvable media binding?
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SEVERITY_ORDER = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}
AUTO_RESPONSE_TYPES = {"mc", "fill", "order"}
MANUAL_RESPONSE_TYPES = {"free", "record"}
QUESTION_MODULE_RE = re.compile(r"_m(\d+)_")


@dataclass(frozen=True)
class QualityIssue:
    severity: str
    code: str
    message: str
    exam_id: str
    subject: str = ""
    module_id: str = ""
    question_id: str = ""
    evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload["evidence"] is None:
            payload["evidence"] = {}
        return payload


def load_source_profiles(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    exams = payload.get("exams") if isinstance(payload, dict) else None
    return exams if isinstance(exams, dict) else {}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _severity_for_published(published: bool, published_level: str, draft_level: str) -> str:
    return published_level if published else draft_level


def _module_id(question: dict[str, Any]) -> str:
    explicit = str(question.get("module_id") or "").strip()
    if explicit:
        return explicit
    match = QUESTION_MODULE_RE.search(str(question.get("id") or ""))
    return f"m{match.group(1)}" if match else "main"


def _question_numbers(question: dict[str, Any]) -> list[int]:
    try:
        start = int(question.get("number"))
        end = int(question.get("number_end") or start)
    except (TypeError, ValueError):
        return []
    if start < 1 or end < start or end - start > 200:
        return []
    return list(range(start, end + 1))


def _normalized_tokens(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [
        re.sub(r"\s+", " ", str(value or "")).strip().lower()
        for value in values
        if re.sub(r"\s+", " ", str(value or "")).strip()
    ]


def _static_asset_path(repo_root: Path, url: str) -> Path | None:
    if not url.startswith("/static/"):
        return None
    return repo_root / url.lstrip("/")


def _expected_numbers(module_profile: dict[str, Any]) -> set[int]:
    explicit = module_profile.get("question_numbers")
    if isinstance(explicit, list):
        result = set()
        for value in explicit:
            try:
                result.add(int(value))
            except (TypeError, ValueError):
                continue
        return {value for value in result if value > 0}
    try:
        start = int(module_profile.get("question_number_start"))
        end = int(module_profile.get("question_number_end"))
    except (TypeError, ValueError):
        return set()
    return set(range(start, end + 1)) if 1 <= start <= end else set()


def _profile_source_issues(
    exam_id: str,
    profile: dict[str, Any],
    source_root: Path | None,
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    sources = profile.get("sources")
    if not isinstance(sources, list) or not sources:
        issues.append(QualityIssue(
            "high",
            "source_evidence_missing",
            "The source profile has no file evidence.",
            exam_id,
        ))
        return issues
    if source_root is None:
        issues.append(QualityIssue(
            "medium",
            "source_root_not_checked",
            "Source hashes were not checked because no source root was provided.",
            exam_id,
        ))
        return issues
    for source in sources:
        if not isinstance(source, dict):
            continue
        relative = str(source.get("path") or "")
        path = source_root / relative
        role = str(source.get("role") or "source")
        if not path.is_file():
            issues.append(QualityIssue(
                "critical",
                "source_file_missing",
                f"Source file is missing for role {role}.",
                exam_id,
                evidence={"path": relative, "role": role},
            ))
            continue
        expected_hash = str(source.get("sha256") or "").lower()
        if expected_hash and _sha256(path) != expected_hash:
            issues.append(QualityIssue(
                "critical",
                "source_hash_mismatch",
                f"Source file changed for role {role}.",
                exam_id,
                evidence={"path": relative, "role": role},
            ))
    return issues


def _question_issues(
    exam_id: str,
    subject: str,
    question: dict[str, Any],
    published: bool,
    audio_module_ids: set[str],
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    question_id = str(question.get("id") or "")
    module_id = _module_id(question)
    response_type = str(question.get("response_type") or "")
    numbers = _question_numbers(question)
    evidence = {"number": question.get("number"), "number_end": question.get("number_end")}

    if not question_id:
        issues.append(QualityIssue(
            "critical",
            "question_id_missing",
            "Question has no stable ID.",
            exam_id,
            subject,
            module_id,
            evidence=evidence,
        ))
    if not numbers:
        issues.append(QualityIssue(
            "critical",
            "question_number_invalid",
            "Question number or range is invalid.",
            exam_id,
            subject,
            module_id,
            question_id,
            evidence,
        ))
    if response_type not in AUTO_RESPONSE_TYPES | MANUAL_RESPONSE_TYPES:
        issues.append(QualityIssue(
            "critical",
            "response_type_invalid",
            "Question has an unsupported response type.",
            exam_id,
            subject,
            module_id,
            question_id,
            {"response_type": response_type},
        ))
        return issues

    answer = question.get("answer")
    grading_status = str(question.get("grading_status") or "")
    if response_type in AUTO_RESPONSE_TYPES and not isinstance(answer, dict):
        issues.append(QualityIssue(
            _severity_for_published(published, "high", "medium"),
            "answer_missing",
            "Automatically gradable question has no reliable answer.",
            exam_id,
            subject,
            module_id,
            question_id,
        ))
    if response_type in AUTO_RESPONSE_TYPES and grading_status != "auto":
        issues.append(QualityIssue(
            _severity_for_published(published, "high", "medium"),
            "grading_not_ready",
            "Automatically gradable question is not marked ready for grading.",
            exam_id,
            subject,
            module_id,
            question_id,
            {"grading_status": grading_status},
        ))

    if response_type == "mc":
        options = question.get("options") if isinstance(question.get("options"), list) else []
        keys = [str(option.get("key") or "") for option in options if isinstance(option, dict)]
        texts = [str(option.get("text") or "").strip() for option in options if isinstance(option, dict)]
        if len(options) != 4:
            issues.append(QualityIssue(
                _severity_for_published(published, "critical", "high"),
                "mc_option_count_invalid",
                "Multiple-choice question does not have exactly four options.",
                exam_id,
                subject,
                module_id,
                question_id,
                {"option_count": len(options)},
            ))
        if len(keys) != len(set(keys)) or keys != list("ABCD")[: len(keys)]:
            issues.append(QualityIssue(
                "critical",
                "mc_option_keys_invalid",
                "Multiple-choice option keys are duplicated or out of order.",
                exam_id,
                subject,
                module_id,
                question_id,
                {"keys": keys},
            ))
        if len(texts) != len(options) or any(not text for text in texts):
            issues.append(QualityIssue(
                "critical",
                "mc_option_text_missing",
                "Multiple-choice option text is empty.",
                exam_id,
                subject,
                module_id,
                question_id,
            ))
        if isinstance(answer, dict):
            expected_keys = {
                str(value or "").strip()
                for value in answer.get("keys") or []
                if str(value or "").strip()
            }
            if not expected_keys or not expected_keys.issubset(set(keys)):
                issues.append(QualityIssue(
                    "critical",
                    "mc_answer_not_in_options",
                    "Answer key is missing or not present in the visible options.",
                    exam_id,
                    subject,
                    module_id,
                    question_id,
                    {"answer_keys": sorted(expected_keys), "option_keys": keys},
                ))
    elif response_type == "fill":
        passage = question.get("passage") if isinstance(question.get("passage"), dict) else {}
        if not str(passage.get("text") or "").strip():
            issues.append(QualityIssue(
                "critical",
                "fill_passage_missing",
                "Fill question has no passage text.",
                exam_id,
                subject,
                module_id,
                question_id,
            ))
        if isinstance(answer, dict):
            words = _normalized_tokens(answer.get("words"))
            if numbers and len(words) != len(numbers):
                issues.append(QualityIssue(
                    "critical",
                    "fill_answer_count_mismatch",
                    "Fill answer count does not match the question-number range.",
                    exam_id,
                    subject,
                    module_id,
                    question_id,
                    {"item_count": len(numbers), "answer_count": len(words)},
                ))
    elif response_type == "order":
        scramble = _normalized_tokens(question.get("scramble_words"))
        ordered = _normalized_tokens(answer.get("ordered")) if isinstance(answer, dict) else []
        if not scramble:
            issues.append(QualityIssue(
                "critical",
                "order_tokens_missing",
                "Build-a-Sentence question has no scramble tokens.",
                exam_id,
                subject,
                module_id,
                question_id,
            ))
        if ordered and Counter(ordered) - Counter(scramble):
            issues.append(QualityIssue(
                "critical",
                "order_answer_not_buildable",
                "The ordered answer cannot be built from the displayed tokens.",
                exam_id,
                subject,
                module_id,
                question_id,
            ))

    if subject == "reading" and response_type == "mc":
        if not str(question.get("prompt") or "").strip():
            issues.append(QualityIssue(
                _severity_for_published(published, "critical", "high"),
                "reading_prompt_missing",
                "Reading multiple-choice question has no prompt.",
                exam_id,
                subject,
                module_id,
                question_id,
            ))
    if subject in {"listening", "speaking"}:
        audio_ref = str(question.get("audio_ref") or "")
        if not audio_ref:
            issues.append(QualityIssue(
                "critical",
                "question_audio_ref_missing",
                "Audio question has no module media reference.",
                exam_id,
                subject,
                module_id,
                question_id,
            ))
        elif audio_ref not in audio_module_ids:
            issues.append(QualityIssue(
                "critical",
                "question_audio_ref_unresolved",
                "Question media reference does not resolve to an audio module.",
                exam_id,
                subject,
                module_id,
                question_id,
                {"audio_ref": audio_ref},
            ))
    return issues


def _subject_profile_issues(
    exam_id: str,
    subject: str,
    profile: dict[str, Any] | None,
    covered_numbers: dict[str, set[int]],
    published: bool,
) -> list[QualityIssue]:
    if not profile:
        return [QualityIssue(
            _severity_for_published(published, "high", "medium"),
            "source_profile_missing",
            "Subject has not been reconciled against a source-verified structure.",
            exam_id,
            subject,
        )]
    issues: list[QualityIssue] = []
    review_status = str(profile.get("review_status") or "pending")
    if review_status != "approved":
        issues.append(QualityIssue(
            _severity_for_published(published, "high", "medium"),
            "subject_review_pending",
            "Subject has not passed human source review.",
            exam_id,
            subject,
            evidence={"review_status": review_status},
        ))
    modules = profile.get("modules")
    if not isinstance(modules, dict):
        return issues
    for module_id, module_profile in modules.items():
        if not isinstance(module_profile, dict):
            continue
        expected = _expected_numbers(module_profile)
        actual = covered_numbers.get(module_id, set())
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        if missing:
            issues.append(QualityIssue(
                "critical",
                "source_question_coverage_missing",
                "Imported subject is missing source question numbers.",
                exam_id,
                subject,
                module_id,
                evidence={"missing_numbers": missing, "expected_count": len(expected)},
            ))
        if unexpected:
            issues.append(QualityIssue(
                "high",
                "source_question_coverage_unexpected",
                "Imported subject contains question numbers outside the verified source range.",
                exam_id,
                subject,
                module_id,
                evidence={"unexpected_numbers": unexpected, "expected_count": len(expected)},
            ))
    return issues


def analyze_bank(
    data_root: Path,
    repo_root: Path,
    *,
    profiles: dict[str, Any] | None = None,
    source_root: Path | None = None,
) -> dict[str, Any]:
    profiles = profiles or {}
    all_issues: list[QualityIssue] = []
    exam_results: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()

    for exam_dir in sorted(path for path in data_root.iterdir() if path.is_dir()):
        manifest = _read_json(exam_dir / "manifest.json")
        if not manifest:
            continue
        exam_id = exam_dir.name
        published = (
            manifest.get("publish_status") == "published"
            and manifest.get("duplicate_status") == "clear"
        )
        totals["exam_count"] += 1
        totals["published_exam_count"] += int(published)
        exam_issues: list[QualityIssue] = []
        exam_profile = profiles.get(exam_id) if isinstance(profiles.get(exam_id), dict) else None
        if published and manifest.get("content_status") != "complete":
            exam_issues.append(QualityIssue(
                "critical",
                "published_exam_incomplete",
                "Incomplete exam is visible in the published catalog.",
                exam_id,
                evidence={"content_status": manifest.get("content_status")},
            ))
            totals["published_partial_count"] += 1
        if exam_profile:
            exam_issues.extend(_profile_source_issues(exam_id, exam_profile, source_root))

        subject_results = []
        for subject in ("reading", "listening", "writing", "speaking"):
            subject_path = exam_dir / f"{subject}.json"
            if not subject_path.is_file():
                continue
            payload = _read_json(subject_path)
            questions = payload.get("questions")
            if not isinstance(questions, list):
                exam_issues.append(QualityIssue(
                    "critical",
                    "subject_questions_invalid",
                    "Subject file does not contain a question list.",
                    exam_id,
                    subject,
                ))
                continue
            totals["subject_count"] += 1
            totals["question_object_count"] += len(questions)
            subject_issues: list[QualityIssue] = []
            ids = [str(question.get("id") or "") for question in questions if isinstance(question, dict)]
            duplicate_ids = sorted(key for key, count in Counter(ids).items() if key and count > 1)
            if duplicate_ids:
                subject_issues.append(QualityIssue(
                    "critical",
                    "question_id_duplicate",
                    "Subject contains duplicate question IDs.",
                    exam_id,
                    subject,
                    evidence={"question_ids": duplicate_ids},
                ))

            audio_modules = (
                (payload.get("exam") or {}).get("audio_modules")
                if isinstance(payload.get("exam"), dict)
                else []
            )
            audio_modules = audio_modules if isinstance(audio_modules, list) else []
            audio_module_ids = {
                str(module.get("id") or "")
                for module in audio_modules
                if isinstance(module, dict) and str(module.get("id") or "")
            }
            audio_urls = [
                str(module.get("url") or "")
                for module in audio_modules
                if isinstance(module, dict) and str(module.get("url") or "")
            ]
            if subject == "listening" and len(audio_urls) > 1 and len(set(audio_urls)) != len(audio_urls):
                subject_issues.append(QualityIssue(
                    _severity_for_published(published, "critical", "high"),
                    "module_audio_reused",
                    "Multiple listening modules reuse the same full audio asset.",
                    exam_id,
                    subject,
                    evidence={"urls": audio_urls},
                ))
                totals["duplicate_audio_binding_count"] += 1
            for module in audio_modules:
                if not isinstance(module, dict):
                    continue
                url = str(module.get("url") or "")
                asset_path = _static_asset_path(repo_root, url)
                if asset_path is None:
                    subject_issues.append(QualityIssue(
                        "critical",
                        "audio_url_invalid",
                        "Audio module does not use a repository static asset.",
                        exam_id,
                        subject,
                        str(module.get("id") or ""),
                        evidence={"url": url},
                    ))
                elif not asset_path.is_file():
                    subject_issues.append(QualityIssue(
                        "critical",
                        "audio_asset_missing",
                        "Audio module points to a missing static asset.",
                        exam_id,
                        subject,
                        str(module.get("id") or ""),
                        evidence={"url": url},
                    ))

            covered_numbers: dict[str, set[int]] = {}
            module_counts: dict[str, Counter[str]] = {}
            orders = []
            for question in questions:
                if not isinstance(question, dict):
                    subject_issues.append(QualityIssue(
                        "critical",
                        "question_object_invalid",
                        "Question list contains a non-object value.",
                        exam_id,
                        subject,
                    ))
                    continue
                module_id = _module_id(question)
                numbers = _question_numbers(question)
                covered_numbers.setdefault(module_id, set()).update(numbers)
                counts = module_counts.setdefault(module_id, Counter())
                counts["question_objects"] += 1
                counts["item_count"] += len(numbers) if numbers else 1
                totals["item_count"] += len(numbers) if numbers else 1
                response_type = str(question.get("response_type") or "")
                if response_type in AUTO_RESPONSE_TYPES:
                    counts["auto_candidates"] += 1
                    if not isinstance(question.get("answer"), dict):
                        totals["missing_answer_count"] += 1
                    if question.get("grading_status") != "auto":
                        totals["not_auto_count"] += 1
                if response_type == "mc" and len(question.get("options") or []) != 4:
                    totals["invalid_mc_option_count"] += 1
                try:
                    orders.append(int(question.get("order")))
                except (TypeError, ValueError):
                    pass
                subject_issues.extend(_question_issues(
                    exam_id,
                    subject,
                    question,
                    published,
                    audio_module_ids,
                ))
            if orders and orders != list(range(1, len(orders) + 1)):
                subject_issues.append(QualityIssue(
                    "medium",
                    "question_order_noncontiguous",
                    "Question order values are not contiguous after import filtering.",
                    exam_id,
                    subject,
                    evidence={"question_count": len(orders)},
                ))

            subject_profile = None
            if exam_profile and isinstance(exam_profile.get("subjects"), dict):
                candidate = exam_profile["subjects"].get(subject)
                subject_profile = candidate if isinstance(candidate, dict) else None
            subject_issues.extend(_subject_profile_issues(
                exam_id,
                subject,
                subject_profile,
                covered_numbers,
                published,
            ))
            exam_issues.extend(subject_issues)
            severity_counts = Counter(issue.severity for issue in subject_issues)
            release_status = (
                "blocked"
                if severity_counts["critical"] or severity_counts["high"]
                else "review_required"
                if severity_counts["medium"]
                else "ready"
            )
            totals["release_ready_subject_count"] += int(release_status == "ready")
            subject_results.append({
                "subject": subject,
                "question_objects": len(questions),
                "item_count": sum(count["item_count"] for count in module_counts.values()),
                "modules": {
                    module_id: dict(counts)
                    for module_id, counts in sorted(module_counts.items())
                },
                "issue_counts": dict(severity_counts),
                "release_status": release_status,
            })

        all_issues.extend(exam_issues)
        exam_severity_counts = Counter(issue.severity for issue in exam_issues)
        exam_results.append({
            "exam_id": exam_id,
            "title": manifest.get("title") or exam_id,
            "published": published,
            "content_status": manifest.get("content_status") or "",
            "profile_status": (
                str(exam_profile.get("status") or "") if exam_profile else "missing"
            ),
            "subjects": subject_results,
            "issue_counts": dict(exam_severity_counts),
            "release_status": (
                "blocked"
                if exam_severity_counts["critical"] or exam_severity_counts["high"]
                else "review_required"
                if exam_severity_counts["medium"]
                else "ready"
            ),
        })

    issue_counts = Counter(issue.severity for issue in all_issues)
    issue_code_counts = Counter(issue.code for issue in all_issues)
    summary = dict(totals)
    summary["issue_counts"] = dict(issue_counts)
    summary["issue_code_counts"] = dict(issue_code_counts)
    summary["release_ready_exam_count"] = sum(
        exam["release_status"] == "ready" for exam in exam_results
    )
    return {
        "schema_version": "1.0",
        "data_root": data_root.name,
        "summary": summary,
        "exams": exam_results,
        "issues": [
            issue.to_dict()
            for issue in sorted(
                all_issues,
                key=lambda item: (
                    -SEVERITY_ORDER[item.severity],
                    item.exam_id,
                    item.subject,
                    item.module_id,
                    item.question_id,
                    item.code,
                ),
            )
        ],
    }


def blocking_issues(
    report: dict[str, Any],
    exam_ids: Iterable[str],
    minimum_severity: str = "high",
) -> list[dict[str, Any]]:
    wanted = set(exam_ids)
    threshold = SEVERITY_ORDER[minimum_severity]
    return [
        issue
        for issue in report.get("issues") or []
        if issue.get("exam_id") in wanted
        and SEVERITY_ORDER.get(str(issue.get("severity")), 0) >= threshold
    ]
