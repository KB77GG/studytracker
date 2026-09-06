#!/usr/bin/env python3
"""Read-only audit of markup that reaches the IELTS web practice renderers.

The audit follows the same catalogs/routes as the web application instead of
blindly globbing every JSON file.  It intentionally treats ``collect`` and
``table`` as one active question surface: a placeholder is valid only when its
numeric token matches an id in that *same* group.  This avoids interpreting
currency such as ``US$90-$100`` as question placeholders.

Examples::

    python3 scripts/audit_practice_markup.py
    python3 scripts/audit_practice_markup.py --json
    python3 scripts/audit_practice_markup.py --strict

The command never writes source data.  ``--strict`` only changes the exit code
when the report contains catalog, unsafe-markup, or placeholder-integrity
findings.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.question_type_practice import canonical_type  # noqa: E402

CAMBRIDGE_LISTENING_RE = re.compile(r"^ielts\d+_test\d+$")
JFDR_LISTENING_RE = re.compile(r"^jfdr(?P<book>\d+)_test\d+$")
PLACEHOLDER_RE = re.compile(r"\$(\d+)\$")
TAG_RE = re.compile(r"<\s*(?P<closing>/?)\s*(?P<name>[A-Za-z][\w:-]*)\b(?P<body>[^>]*)>", re.S)
ATTRIBUTE_RE = re.compile(
    r"(?P<name>[A-Za-z_:][\w:.-]*)\s*=\s*"
    r'(?:"(?P<double>[^"]*)"|\'(?P<single>[^\']*)\'|(?P<bare>[^\s>]+))'
)
ENTITY_RE = re.compile(r"&(?:#\d+|#x[0-9a-f]+|[a-z][a-z0-9]+);", re.I)
ESCAPED_TAG_RE = re.compile(r"&lt;\s*/?\s*[A-Za-z][^&]*?&gt;", re.I)

# This mirrors the two allowlists in static/js/practice_table.js.  The audit is
# deliberately stricter than a browser HTML parser: unknown tags are surfaced
# even though the renderer escapes them safely.
INLINE_TAGS = {"b", "i", "bc", "iu", "br", "divider"}
STRUCTURAL_TAGS = {
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "th",
    "td",
    "caption",
    "colgroup",
    "col",
    "p",
    "div",
    "ul",
    "ol",
    "li",
}
SUPPORTED_TAGS = INLINE_TAGS | STRUCTURAL_TAGS
SAFE_ATTRIBUTES = {
    "td": {"rowspan", "colspan"},
    "th": {"rowspan", "colspan", "scope"},
    "col": {"span"},
}
URL_ATTRIBUTES = {"action", "formaction", "href", "poster", "src", "xlink:href"}
COMPLETION_TYPES = {
    "form_completion",
    "note_completion",
    "table_completion",
    "flow_chart_completion",
    "sentence_completion",
    "summary_completion",
    "diagram_labelling",
    "short_answer",
}


@dataclass(frozen=True)
class Corpus:
    name: str
    subject: str
    catalog_source: str
    expected_ids: tuple[str, ...]
    paths: tuple[Path, ...]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _catalog_ids(path: Path) -> list[str]:
    payload = _read_json(path)
    return [
        str(test.get("id") or "").strip()
        for book in payload.get("books") or []
        for test in book.get("tests") or []
        if isinstance(test, dict) and str(test.get("id") or "").strip()
    ]


def _listening_jijing_ids(path: Path) -> list[str]:
    payload = _read_json(path)
    return [
        str(part.get("id") or "").strip()
        for book in payload.get("books") or []
        for test in book.get("tests") or []
        for part in test.get("parts") or []
        if isinstance(part, dict) and str(part.get("id") or "").strip()
    ]


def _offline_reading_ids(path: Path) -> list[str]:
    payload = _read_json(path)
    return [
        str(entry.get("id") or "").strip()
        for entry in payload.get("tests") or []
        if isinstance(entry, dict)
        and entry.get("status") == "offline"
        and str(entry.get("id") or "").strip()
    ]


def discover_corpora(project_root: Path = PROJECT_ROOT) -> tuple[list[Corpus], list[dict]]:
    """Resolve every web-reachable practice corpus and catalog mismatch."""

    static_root = project_root / "static"
    listening_root = static_root / "listening_tests"
    listening_jijing_root = static_root / "listening_jijing"
    reading_root = static_root / "reading_tests"
    reading_jijing_root = static_root / "reading_jijing"
    findings: list[dict] = []

    listening_files = sorted(listening_root.glob("*.json"))
    cambridge_listening = [
        path for path in listening_files if CAMBRIDGE_LISTENING_RE.fullmatch(path.stem)
    ]
    jfdr_by_book: dict[int, list[Path]] = {}
    classified_listening = set(cambridge_listening)
    for path in listening_files:
        match = JFDR_LISTENING_RE.fullmatch(path.stem)
        if not match:
            continue
        jfdr_by_book.setdefault(int(match.group("book")), []).append(path)
        classified_listening.add(path)
    for path in sorted(set(listening_files) - classified_listening):
        findings.append(
            {
                "code": "unclassified_listening_test_file",
                "path": str(path.relative_to(project_root)),
            }
        )

    listening_jijing_catalog = listening_jijing_root / "catalog.json"
    all_listening_jijing_ids = _listening_jijing_ids(listening_jijing_catalog)
    legacy_ids = [
        test_id for test_id in all_listening_jijing_ids if not test_id.startswith("xiahuar_")
    ]
    xiahuar_ids = [
        test_id for test_id in all_listening_jijing_ids if test_id.startswith("xiahuar_")
    ]

    reading_catalog = reading_root / "catalog.json"
    cambridge_reading_ids = _catalog_ids(reading_catalog)
    reading_jijing_catalog = reading_jijing_root / "catalog.json"
    online_reading_jijing_ids = _catalog_ids(reading_jijing_catalog)
    offline_manifest = reading_jijing_root / "offline_tests.json"
    offline_reading_jijing_ids = _offline_reading_ids(offline_manifest)

    def catalog_corpus(
        name: str,
        subject: str,
        catalog_source: str,
        directory: Path,
        expected_ids: list[str],
    ) -> Corpus:
        paths: list[Path] = []
        for test_id in expected_ids:
            path = directory / f"{test_id}.json"
            if path.is_file():
                paths.append(path)
            else:
                findings.append(
                    {
                        "code": "catalog_file_missing",
                        "corpus": name,
                        "path": str(path.relative_to(project_root)),
                    }
                )
        return Corpus(name, subject, catalog_source, tuple(expected_ids), tuple(paths))

    corpora = [
        Corpus(
            "listening_cambridge",
            "listening",
            "dynamic_route_glob",
            tuple(path.stem for path in cambridge_listening),
            tuple(cambridge_listening),
        )
    ]
    for book in sorted(jfdr_by_book):
        paths = tuple(sorted(jfdr_by_book[book]))
        corpora.append(
            Corpus(
                f"listening_jfdr{book}",
                "listening",
                "dynamic_route_glob",
                tuple(path.stem for path in paths),
                paths,
            )
        )
    corpora.extend(
        [
            catalog_corpus(
                "listening_jijing_legacy",
                "listening",
                str(listening_jijing_catalog.relative_to(project_root)),
                listening_jijing_root / "parts",
                legacy_ids,
            ),
            catalog_corpus(
                "listening_jijing_xiahuar",
                "listening",
                str(listening_jijing_catalog.relative_to(project_root)),
                listening_jijing_root / "parts",
                xiahuar_ids,
            ),
            catalog_corpus(
                "reading_cambridge",
                "reading",
                str(reading_catalog.relative_to(project_root)),
                reading_root,
                cambridge_reading_ids,
            ),
            catalog_corpus(
                "reading_jijing_online",
                "reading",
                str(reading_jijing_catalog.relative_to(project_root)),
                reading_jijing_root,
                online_reading_jijing_ids,
            ),
            catalog_corpus(
                "reading_jijing_offline_direct",
                "reading",
                str(offline_manifest.relative_to(project_root)),
                reading_jijing_root,
                offline_reading_jijing_ids,
            ),
        ]
    )

    catalogued_jijing = set(online_reading_jijing_ids) | set(offline_reading_jijing_ids)
    disk_jijing = {path.stem for path in reading_jijing_root.glob("reading_jijing_*.json")}
    for test_id in sorted(disk_jijing - catalogued_jijing):
        findings.append(
            {
                "code": "unlisted_reading_jijing_file",
                "path": str((reading_jijing_root / f"{test_id}.json").relative_to(project_root)),
            }
        )

    disk_listening_jijing = {path.stem for path in (listening_jijing_root / "parts").glob("*.json")}
    for test_id in sorted(disk_listening_jijing - set(all_listening_jijing_ids)):
        findings.append(
            {
                "code": "unlisted_listening_jijing_file",
                "path": str(
                    (listening_jijing_root / "parts" / f"{test_id}.json").relative_to(project_root)
                ),
            }
        )
    return corpora, findings


def _units(payload: dict) -> list[dict]:
    for key in ("sections", "passages"):
        value = payload.get(key)
        if isinstance(value, list):
            return [unit for unit in value if isinstance(unit, dict)]
    return [payload] if isinstance(payload.get("groups"), list) else []


def _questions(group: dict) -> list[dict]:
    for key in ("questions", "items"):
        value = group.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def _active_markup_strings(group: dict) -> list[str]:
    values: list[str] = []
    collect = group.get("collect")
    if isinstance(collect, str) and collect:
        values.append(collect)
    table = group.get("table")
    if table:
        values.extend(_walk_strings(table))
    return values


def _option_list(group: dict) -> list:
    for key in ("collect_option", "collect_options"):
        value = group.get(key)
        options = value.get("list") if isinstance(value, dict) else None
        if isinstance(options, list):
            return options
    return []


def audit_group_placeholders(group: dict) -> dict:
    """Return collect/table coverage using only ids declared by this group."""

    question_ids = [
        str(question.get("id")) for question in _questions(group) if question.get("id") is not None
    ]
    active_strings = _active_markup_strings(group)
    source = "\n".join(active_strings)
    raw_tokens = PLACEHOLDER_RE.findall(source)

    # Counting the exact token for each declared id is the key safety property.
    # A broad ``$...$`` split can span the hyphen in US$90-$100 and invent a
    # blank; these counters cannot.
    counts = Counter(token for token in raw_tokens if token in set(question_ids))
    exact_ids = sorted(question_id for question_id in question_ids if counts[question_id] == 1)
    duplicate_ids = sorted(question_id for question_id in question_ids if counts[question_id] > 1)
    missing_ids = sorted(question_id for question_id in question_ids if counts[question_id] == 0)
    orphan_tokens = sorted(token for token in raw_tokens if token not in set(question_ids))
    return {
        "active": bool(active_strings),
        "question_ids": question_ids,
        "recognized_occurrences": sum(counts.values()),
        "covered_question_ids": len(exact_ids) + len(duplicate_ids),
        "exact_ids": exact_ids,
        "duplicate_ids": duplicate_ids,
        "duplicate_extra_occurrences": sum(counts[key] - 1 for key in duplicate_ids),
        "missing_ids": missing_ids,
        "orphan_tokens": orphan_tokens,
    }


def _attribute_value(match: re.Match) -> str:
    return next(
        (
            value
            for value in (match.group("double"), match.group("single"), match.group("bare"))
            if value is not None
        ),
        "",
    )


def _dangerous_attribute(name: str, value: str) -> bool:
    lowered_name = name.lower()
    lowered_value = re.sub(r"[\x00-\x20]+", "", value).lower()
    if lowered_name.startswith("on") or lowered_name in {"srcdoc", "style"}:
        return True
    if lowered_name in URL_ATTRIBUTES and lowered_value.startswith(
        ("javascript:", "vbscript:", "data:text/html")
    ):
        return True
    return False


def audit_markup_text(text: str) -> dict:
    """Inventory tags/entities/attributes in one renderer-bound string."""

    tags: Counter[str] = Counter()
    attributes: Counter[str] = Counter()
    discarded_attributes: Counter[str] = Counter()
    dangerous: list[dict] = []
    invalid_safe_attributes: list[dict] = []
    rowspan_zero_occurrences = 0
    optional_end_tag_closures = 0
    structural_whitespace_segments = 0
    stack: list[str] = []
    previous_tag: re.Match | None = None
    for tag_match in TAG_RE.finditer(text):
        tag = tag_match.group("name").lower()
        tags[tag] += 1
        if previous_tag is not None:
            between = text[previous_tag.end() : tag_match.start()]
            previous_name = previous_tag.group("name").lower()
            if (
                previous_name in STRUCTURAL_TAGS
                and tag in STRUCTURAL_TAGS
                and "\n" in between
                and not between.strip()
            ):
                structural_whitespace_segments += 1
        previous_tag = tag_match
        if tag_match.group("closing"):
            if tag == "tr" and stack and stack[-1] in {"td", "th"}:
                stack.pop()
                optional_end_tag_closures += 1
            if tag == "table":
                while stack and stack[-1] in {"td", "th", "tr", "thead", "tbody", "tfoot"}:
                    stack.pop()
                    optional_end_tag_closures += 1
            if tag in {"ul", "ol"} and stack and stack[-1] == "li":
                stack.pop()
                optional_end_tag_closures += 1
            if stack and stack[-1] == tag:
                stack.pop()
            continue
        if tag in {"td", "th"} and stack and stack[-1] in {"td", "th"}:
            stack.pop()
            optional_end_tag_closures += 1
        if tag == "tr" and stack and stack[-1] == "tr":
            stack.pop()
            optional_end_tag_closures += 1
        if tag == "li" and stack and stack[-1] == "li":
            stack.pop()
            optional_end_tag_closures += 1
        if tag == "p" and stack and stack[-1] == "p":
            stack.pop()
            optional_end_tag_closures += 1
        for attribute_match in ATTRIBUTE_RE.finditer(tag_match.group("body")):
            name = attribute_match.group("name").lower()
            value = _attribute_value(attribute_match)
            attributes[f"{tag}.{name}"] += 1
            if name not in SAFE_ATTRIBUTES.get(tag, set()):
                discarded_attributes[f"{tag}.{name}"] += 1
            if _dangerous_attribute(name, value):
                dangerous.append({"tag": tag, "attribute": name, "value": value})
            if name in SAFE_ATTRIBUTES.get(tag, set()):
                valid = False
                if name == "scope":
                    valid = tag == "th" and value.lower() in {
                        "col",
                        "row",
                        "colgroup",
                        "rowgroup",
                    }
                elif value.isdigit():
                    numeric = int(value)
                    valid = (name == "rowspan" and numeric == 0) or 1 <= numeric <= 100
                    if name == "rowspan" and numeric == 0:
                        rowspan_zero_occurrences += 1
                if not valid:
                    invalid_safe_attributes.append(
                        {"tag": tag, "attribute": name, "value": value}
                    )
        if tag not in {"br", "divider", "col"} and not tag_match.group("body").rstrip().endswith("/"):
            stack.append(tag)
    entities = Counter(entity.lower() for entity in ENTITY_RE.findall(text))
    return {
        "tags": tags,
        "entities": entities,
        "attributes": attributes,
        "discarded_attributes": discarded_attributes,
        "dangerous_attributes": dangerous,
        "invalid_safe_attributes": invalid_safe_attributes,
        "rowspan_zero_occurrences": rowspan_zero_occurrences,
        "optional_end_tag_closures": optional_end_tag_closures,
        "structural_whitespace_segments": structural_whitespace_segments,
        "escaped_tag_entities": len(ESCAPED_TAG_RE.findall(text)),
    }


def _relative(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def _empty_corpus_report(corpus: Corpus) -> dict:
    return {
        "name": corpus.name,
        "subject": corpus.subject,
        "catalog_source": corpus.catalog_source,
        "counts": {
            "catalog_entries": len(corpus.expected_ids),
            "files": 0,
            "units": 0,
            "groups": 0,
            "questions": 0,
        },
        "placeholders": {
            "active_groups": 0,
            "recognized_occurrences": 0,
            "covered_question_ids": 0,
            "exact_once_question_ids": 0,
            "duplicate_question_ids": 0,
            "duplicate_extra_occurrences": 0,
            "missing_question_ids": 0,
            "orphan_marker_occurrences": 0,
            "findings": [],
        },
        "renderer_dispatch": {
            "complete_placeholder_with_options_groups": 0,
            "complete_placeholder_with_options_questions": 0,
            "completion_type_groups": 0,
            "completion_type_questions": 0,
            "risk_groups": 0,
            "risk_questions": 0,
            "canonical_breakdown": {},
            "findings": [],
        },
        "markup": {
            "tag_occurrences": {},
            "entity_occurrences": {},
            "attribute_occurrences": {},
            "discarded_attribute_occurrences": {},
            "dangerous_attribute_occurrences": 0,
            "dangerous_attributes": [],
            "invalid_safe_attribute_occurrences": 0,
            "invalid_safe_attributes": [],
            "rowspan_zero_occurrences": 0,
            "optional_end_tag_closures": 0,
            "structural_whitespace_segments": 0,
            "unsupported_tag_occurrences": {},
            "escaped_tag_entities": 0,
            "object_table_groups": 0,
            "raw_html_table_groups": 0,
            "raw_structured_html_groups": 0,
            "raw_structured_html_findings": [],
        },
    }


def _audit_corpus(corpus: Corpus, project_root: Path) -> dict:
    report = _empty_corpus_report(corpus)
    counts = report["counts"]
    placeholder_summary = report["placeholders"]
    dispatch = report["renderer_dispatch"]
    markup = report["markup"]
    tag_counter: Counter[str] = Counter()
    entity_counter: Counter[str] = Counter()
    attribute_counter: Counter[str] = Counter()
    discarded_attribute_counter: Counter[str] = Counter()
    canonical_breakdown: Counter[str] = Counter()

    for path in corpus.paths:
        payload = _read_json(path)
        counts["files"] += 1
        units = _units(payload)
        counts["units"] += len(units)
        for unit in units:
            groups = [group for group in unit.get("groups") or [] if isinstance(group, dict)]
            counts["groups"] += len(groups)
            for group in groups:
                questions = _questions(group)
                counts["questions"] += len(questions)
                coverage = audit_group_placeholders(group)
                location = {
                    "path": _relative(path, project_root),
                    "unit_id": unit.get("id"),
                    "group_id": group.get("group_id"),
                }
                if coverage["active"]:
                    placeholder_summary["active_groups"] += 1
                    placeholder_summary["recognized_occurrences"] += coverage[
                        "recognized_occurrences"
                    ]
                    placeholder_summary["covered_question_ids"] += coverage["covered_question_ids"]
                    placeholder_summary["exact_once_question_ids"] += len(coverage["exact_ids"])
                    placeholder_summary["duplicate_question_ids"] += len(coverage["duplicate_ids"])
                    placeholder_summary["duplicate_extra_occurrences"] += coverage[
                        "duplicate_extra_occurrences"
                    ]
                    placeholder_summary["missing_question_ids"] += len(coverage["missing_ids"])
                    placeholder_summary["orphan_marker_occurrences"] += len(
                        coverage["orphan_tokens"]
                    )
                    if (
                        coverage["duplicate_ids"]
                        or coverage["missing_ids"]
                        or coverage["orphan_tokens"]
                    ):
                        placeholder_summary["findings"].append(
                            {
                                **location,
                                "duplicate_ids": coverage["duplicate_ids"],
                                "missing_ids": coverage["missing_ids"],
                                "orphan_tokens": coverage["orphan_tokens"],
                            }
                        )

                options = _option_list(group)
                complete_option_layout = bool(
                    coverage["active"]
                    and coverage["question_ids"]
                    and coverage["covered_question_ids"] == len(coverage["question_ids"])
                    and len(options) >= 3
                )
                if complete_option_layout:
                    canonical, subtype = canonical_type(group, corpus.subject)
                    dispatch["complete_placeholder_with_options_groups"] += 1
                    dispatch["complete_placeholder_with_options_questions"] += len(questions)
                    canonical_breakdown[f"{canonical}/{subtype}"] += len(questions)
                    is_completion = canonical in COMPLETION_TYPES
                    if is_completion:
                        dispatch["completion_type_groups"] += 1
                        dispatch["completion_type_questions"] += len(questions)

                    # Cambridge specialty snapshots historically sent every one
                    # of these complete inline layouts to the generic matching
                    # renderer.  In ZYZ, canonical matching groups are expected;
                    # only completion types are a dispatch risk.
                    is_risk = (
                        corpus.name == "reading_cambridge"
                        or corpus.name.startswith("reading_jijing")
                        and is_completion
                    )
                    if is_risk:
                        dispatch["risk_groups"] += 1
                        dispatch["risk_questions"] += len(questions)
                    dispatch["findings"].append(
                        {
                            **location,
                            "questions": len(questions),
                            "options": len(options),
                            "canonical_type": canonical,
                            "subtype": subtype,
                            "renderer_risk": is_risk,
                        }
                    )

                table = group.get("table")
                if table:
                    markup["object_table_groups"] += 1
                collect = group.get("collect")
                raw_tags_in_group: set[str] = set()
                if isinstance(collect, str) and re.search(r"<\s*table\b", collect, re.I):
                    markup["raw_html_table_groups"] += 1
                for text in _active_markup_strings(group):
                    text_audit = audit_markup_text(text)
                    tag_counter.update(text_audit["tags"])
                    entity_counter.update(text_audit["entities"])
                    attribute_counter.update(text_audit["attributes"])
                    discarded_attribute_counter.update(text_audit["discarded_attributes"])
                    markup["escaped_tag_entities"] += text_audit["escaped_tag_entities"]
                    markup["dangerous_attributes"].extend(
                        {**location, **attribute}
                        for attribute in text_audit["dangerous_attributes"]
                    )
                    markup["invalid_safe_attributes"].extend(
                        {**location, **attribute}
                        for attribute in text_audit["invalid_safe_attributes"]
                    )
                    markup["rowspan_zero_occurrences"] += text_audit[
                        "rowspan_zero_occurrences"
                    ]
                    markup["optional_end_tag_closures"] += text_audit[
                        "optional_end_tag_closures"
                    ]
                    markup["structural_whitespace_segments"] += text_audit[
                        "structural_whitespace_segments"
                    ]
                    raw_tags_in_group.update(text_audit["tags"])
                structural = raw_tags_in_group & STRUCTURAL_TAGS
                if structural:
                    markup["raw_structured_html_groups"] += 1
                    markup["raw_structured_html_findings"].append(
                        {**location, "tags": sorted(structural)}
                    )

    dispatch["canonical_breakdown"] = dict(sorted(canonical_breakdown.items()))
    markup["tag_occurrences"] = dict(sorted(tag_counter.items()))
    markup["entity_occurrences"] = dict(sorted(entity_counter.items()))
    markup["attribute_occurrences"] = dict(sorted(attribute_counter.items()))
    markup["discarded_attribute_occurrences"] = dict(sorted(discarded_attribute_counter.items()))
    markup["dangerous_attribute_occurrences"] = len(markup["dangerous_attributes"])
    markup["invalid_safe_attribute_occurrences"] = len(markup["invalid_safe_attributes"])
    markup["unsupported_tag_occurrences"] = {
        tag: count for tag, count in sorted(tag_counter.items()) if tag not in SUPPORTED_TAGS
    }
    return report


def _sum_nested(corpora: list[dict], section: str, fields: Iterable[str]) -> dict:
    return {field: sum(int(corpus[section][field]) for corpus in corpora) for field in fields}


def audit_repository(project_root: Path = PROJECT_ROOT) -> dict:
    project_root = project_root.resolve()
    corpora, discovery_findings = discover_corpora(project_root)
    corpus_reports = [_audit_corpus(corpus, project_root) for corpus in corpora]

    count_fields = ("catalog_entries", "files", "units", "groups", "questions")
    placeholder_fields = (
        "active_groups",
        "recognized_occurrences",
        "covered_question_ids",
        "exact_once_question_ids",
        "duplicate_question_ids",
        "duplicate_extra_occurrences",
        "missing_question_ids",
        "orphan_marker_occurrences",
    )
    dispatch_fields = (
        "complete_placeholder_with_options_groups",
        "complete_placeholder_with_options_questions",
        "completion_type_groups",
        "completion_type_questions",
        "risk_groups",
        "risk_questions",
    )
    table_fields = (
        "object_table_groups",
        "raw_html_table_groups",
        "raw_structured_html_groups",
        "dangerous_attribute_occurrences",
        "escaped_tag_entities",
        "invalid_safe_attribute_occurrences",
        "rowspan_zero_occurrences",
        "optional_end_tag_closures",
        "structural_whitespace_segments",
    )

    totals = _sum_nested(corpus_reports, "counts", count_fields)
    subject_totals = {
        subject: _sum_nested(
            [corpus for corpus in corpus_reports if corpus["subject"] == subject],
            "counts",
            count_fields,
        )
        for subject in ("listening", "reading")
    }
    placeholder_totals = _sum_nested(corpus_reports, "placeholders", placeholder_fields)
    dispatch_totals = _sum_nested(corpus_reports, "renderer_dispatch", dispatch_fields)
    markup_totals = _sum_nested(corpus_reports, "markup", table_fields)
    for field in (
        "tag_occurrences",
        "entity_occurrences",
        "attribute_occurrences",
        "discarded_attribute_occurrences",
        "unsupported_tag_occurrences",
    ):
        combined: Counter[str] = Counter()
        for corpus in corpus_reports:
            combined.update(corpus["markup"][field])
        markup_totals[field] = dict(sorted(combined.items()))

    integrity_findings = list(discovery_findings)
    for corpus in corpus_reports:
        for finding in corpus["placeholders"]["findings"]:
            integrity_findings.append(
                {"code": "placeholder_coverage", "corpus": corpus["name"], **finding}
            )
        for finding in corpus["markup"]["dangerous_attributes"]:
            integrity_findings.append(
                {"code": "dangerous_attribute", "corpus": corpus["name"], **finding}
            )
        for finding in corpus["markup"]["invalid_safe_attributes"]:
            integrity_findings.append(
                {"code": "invalid_safe_attribute", "corpus": corpus["name"], **finding}
            )
        if corpus["markup"]["unsupported_tag_occurrences"]:
            integrity_findings.append(
                {
                    "code": "unsupported_tags",
                    "corpus": corpus["name"],
                    "tags": corpus["markup"]["unsupported_tag_occurrences"],
                }
            )

    return {
        "project_root": str(project_root),
        "scope": {
            "placeholder_fields": ["collect", "table"],
            "catalog_policy": (
                "dynamic Listening routes; Reading catalogs; Listening jijing catalog; "
                "Reading jijing catalog plus offline direct-route manifest"
            ),
            "placeholder_policy": "exact $numeric_id$ token matched within the same group",
        },
        "ok": not integrity_findings,
        "totals": totals,
        "subject_totals": subject_totals,
        "placeholders": placeholder_totals,
        "renderer_dispatch": dispatch_totals,
        "markup": markup_totals,
        "corpora": corpus_reports,
        "findings": integrity_findings,
    }


def _format_summary(report: dict) -> str:
    lines = ["Web practice markup corpus audit"]
    lines.append(
        "corpus                          catalog files units groups questions  exact dup missing orphan"
    )
    for corpus in report["corpora"]:
        counts = corpus["counts"]
        placeholders = corpus["placeholders"]
        lines.append(
            f"{corpus['name']:<31} "
            f"{counts['catalog_entries']:>7} {counts['files']:>5} {counts['units']:>5} "
            f"{counts['groups']:>6} {counts['questions']:>9}  "
            f"{placeholders['exact_once_question_ids']:>5} "
            f"{placeholders['duplicate_question_ids']:>3} "
            f"{placeholders['missing_question_ids']:>7} "
            f"{placeholders['orphan_marker_occurrences']:>6}"
        )
    totals = report["totals"]
    placeholders = report["placeholders"]
    lines.append(
        f"TOTAL                           {totals['catalog_entries']:>7} {totals['files']:>5} "
        f"{totals['units']:>5} {totals['groups']:>6} {totals['questions']:>9}  "
        f"{placeholders['exact_once_question_ids']:>5} "
        f"{placeholders['duplicate_question_ids']:>3} "
        f"{placeholders['missing_question_ids']:>7} "
        f"{placeholders['orphan_marker_occurrences']:>6}"
    )
    lines.append("")
    for corpus in report["corpora"]:
        dispatch = corpus["renderer_dispatch"]
        if dispatch["complete_placeholder_with_options_groups"]:
            lines.append(
                f"{corpus['name']}: complete placeholders + options "
                f"{dispatch['complete_placeholder_with_options_groups']} groups / "
                f"{dispatch['complete_placeholder_with_options_questions']} questions; "
                f"renderer risk {dispatch['risk_groups']} / {dispatch['risk_questions']}"
            )
    markup = report["markup"]
    lines.extend(
        [
            "",
            "Markup: "
            f"{markup['object_table_groups']} object tables, "
            f"{markup['raw_html_table_groups']} raw HTML tables, "
            f"{markup['raw_structured_html_groups']} raw structured groups, "
            f"{markup['dangerous_attribute_occurrences']} dangerous attributes.",
            "HTML compatibility forms: "
            f"{markup['optional_end_tag_closures']} optional end-tag closures, "
            f"{markup['structural_whitespace_segments']} structural newline segments, "
            f"{markup['rowspan_zero_occurrences']} rowspan=0, "
            f"{markup['invalid_safe_attribute_occurrences']} invalid safe-attribute values.",
            f"Tags: {json.dumps(markup['tag_occurrences'], ensure_ascii=False, sort_keys=True)}",
            f"Entities: {json.dumps(markup['entity_occurrences'], ensure_ascii=False, sort_keys=True)}",
            f"Findings: {len(report['findings'])} (PASS means none; --strict makes findings fatal)",
        ]
    )
    if report["findings"]:
        lines.append("Placeholder/catalog/security findings:")
        for finding in report["findings"]:
            detail = []
            for key in ("duplicate_ids", "missing_ids", "orphan_tokens", "tags", "attribute"):
                if finding.get(key):
                    detail.append(f"{key}={finding[key]}")
            lines.append(
                "- "
                + " ".join(
                    str(value)
                    for value in (
                        finding.get("code"),
                        finding.get("corpus"),
                        finding.get("path"),
                        (
                            f"group={finding.get('group_id')}"
                            if finding.get("group_id") is not None
                            else None
                        ),
                        *detail,
                    )
                    if value
                )
            )
    structured_findings = [
        (corpus["name"], finding)
        for corpus in report["corpora"]
        for finding in corpus["markup"]["raw_structured_html_findings"]
    ]
    if structured_findings:
        lines.append("Raw structured HTML groups:")
        for corpus_name, finding in structured_findings:
            lines.append(
                f"- {corpus_name} {finding['path']} group={finding['group_id']} "
                f"tags={','.join(finding['tags'])}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--json", action="store_true", help="print the complete machine-readable report"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return status 1 for catalog, unsafe markup, or placeholder findings",
    )
    args = parser.parse_args(argv)
    report = audit_repository(args.project_root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(_format_summary(report))
    return 1 if args.strict and not report["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
