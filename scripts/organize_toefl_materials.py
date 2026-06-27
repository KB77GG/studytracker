#!/usr/bin/env python3
"""Build a non-destructive, deduplicated TOEFL material library.

The generated library contains symbolic links to the original material files.
Source files are never moved, renamed, deleted, or copied.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


DEFAULT_SOURCE = Path.home() / "Desktop" / "新托福资料"
DEFAULT_OUTPUT = Path.home() / "Desktop" / "新托福资料_整理"
DEFAULT_REAL_INVENTORY = Path("data") / "toefl_real_inventory" / "inventory.json"
DEFAULT_OFFICIAL_AUDIT = Path("data") / "toefl_official_audit" / "inventory.json"
DEFAULT_CROSSWALK = (
    Path("data")
    / "toefl_answer_keys"
    / "practice_crosswalk"
    / "exam_crosswalk.csv"
)
MARKER = ".toefl_material_library"
NOTICE = "内部学习资料，禁止外传或用于商业用途"

SECTION_DIRS = {
    "reading": "01_阅读",
    "listening": "02_听力",
    "speaking": "03_口语",
    "writing": "04_写作",
}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".md", ".markdown"}
MEDIA_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".wav",
    ".ogg",
    ".aiff",
    ".aac",
    ".flac",
    ".mp4",
    ".mov",
    ".m4v",
    ".webm",
}
TEMP_TOPS = {
    ".claude",
    "__pycache__",
    "output",
    "sagepath_vocab",
    "tmp",
    "tmp_pdfs",
}
OFFICIAL_UNASSIGNED_TOPS = {"test 3", "test 4", "test 5", "test 6", "test 7", "测试2"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_rank(relative_path: str) -> tuple[int, int, int, str]:
    normalized = relative_path.lower()
    penalty = 0
    penalty += 8 if "1.21新托福真题c卷/" in normalized and normalized.count("/") > 1 else 0
    penalty += 4 if re.search(r"\s\(1\)(?=\.)|副本|备份|copy", normalized) else 0
    penalty += 2 if " files 2" in normalized else 0
    parts = Path(relative_path).parts
    return penalty, len(parts), len(relative_path), relative_path


def choose_canonical(rows: list[dict]) -> dict:
    return min(rows, key=lambda row: canonical_rank(row["path"]))


def prepare_output(output: Path, force: bool) -> None:
    if output.exists():
        marker = output / MARKER
        if not force:
            raise RuntimeError(f"Output already exists: {output}; rerun with --force")
        if not marker.is_file():
            raise RuntimeError(f"Refusing to replace unowned directory: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / MARKER).write_text(
        f"{NOTICE}\ngenerated={datetime.now().astimezone().isoformat(timespec='seconds')}\n",
        encoding="utf-8",
    )


def available_destination(destination: Path, digest: str) -> Path:
    if not destination.exists() and not destination.is_symlink():
        return destination
    return destination.with_name(f"{destination.stem}__{digest[:8]}{destination.suffix}")


def create_link(source: Path, destination: Path, digest: str) -> Path:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination = available_destination(destination, digest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(source)
    return destination


def exam_file_category(row: dict) -> str:
    if row.get("is_answer"):
        return "05_答案"
    if row.get("is_transcript"):
        return "06_听力原文"
    if row.get("is_full_paper"):
        return "00_整套题"
    if row.get("kind") == "archive":
        sections = row.get("sections") or []
        return SECTION_DIRS.get(sections[0], "90_其他") if len(sections) == 1 else "90_其他"
    sections = row.get("sections") or []
    if len(sections) == 1:
        return SECTION_DIRS.get(sections[0], "90_其他")
    if len(sections) > 1:
        return "00_整套题"
    return "90_其他"


def official_file_category(row: dict) -> str:
    extension = row.get("extension") or Path(row["path"]).suffix.lower()
    if extension == ".pdf":
        return "00_试题PDF"
    if extension == ".zip":
        return "90_原始压缩包"
    if extension in {".mp4", ".mov", ".m4v", ".webm"}:
        return "02_视频"
    if extension in MEDIA_EXTENSIONS:
        return "01_音频"
    return "99_其他"


def support_category(relative_path: str) -> tuple[str, str]:
    parts = Path(relative_path).parts
    top = parts[0] if parts else ""
    lower = relative_path.lower()
    if top in TEMP_TOPS or (
        top == "新托福分科刷题材料"
        and len(parts) > 1
        and parts[1] in {"data", "output"}
    ):
        return "excluded", "临时目录、程序目录或中间产物"
    if top in OFFICIAL_UNASSIGNED_TOPS:
        return "07_官方待对应素材", "官方音频/压缩包尚未绑定到确定 PDF"
    if top == "新版托福考试官方指南（OG）":
        return "08_官方指南章节素材", "OG 非 Chapter 6 章节配套音频"
    if top == "新托福分科刷题材料":
        return "01_分科刷题材料", ""
    if top in {"SagePath词册", "输出词册"} or "词汇" in lower:
        return "02_词汇", ""
    if top == "评分标准" or "rubric" in lower or "test-overview" in lower:
        return "03_评分标准", ""
    if top == "课件输出" or "教案" in relative_path or "【作业】" in relative_path:
        return "04_课程课件", ""
    if top == "课程安排":
        return "05_课程安排", ""
    if top in {"lacircle_archive", "wechat_toefl"}:
        return "06_采集归档", ""
    if top.startswith("tmp") or Path(relative_path).name.startswith("tmp_"):
        return "excluded", "临时文件"
    return "99_其他待归类", "未命中已知辅助资料分类"


def load_crosswalk(path: Path) -> dict[str, dict]:
    return {
        row["practice_id"].strip().lower(): row
        for row in read_csv(path)
        if row.get("practice_id")
    }


def crosswalk_for_exam(exam_key: str, crosswalk: dict[str, dict]) -> dict:
    key = exam_key.lower()
    if key in crosswalk:
        return crosswalk[key]
    aliases = {
        "2026-03-16-s1": "2026-03-16",
        "2026-03-25-s1": "2026-03-25",
    }
    return crosswalk.get(aliases.get(key, ""), {})


def normalize_exam_key(value: str) -> str:
    return value.strip().replace("_", "-").upper()


def import_priority(exam: dict, answer_map: dict, imported_ids: set[str]) -> tuple[str, str]:
    if normalize_exam_key(exam["exam_key"]) in imported_ids:
        return "P0_已导入", "当前本地题库已有结构化版本"
    answer_status = answer_map.get("status") or "not_mapped"
    statuses = {
        section: detail["status"]
        for section, detail in (exam.get("sections") or {}).items()
    }
    if (
        exam.get("variant") == "MIXED"
        or exam.get("partial_markers")
        or answer_status in {"no_answer_file", "unsupported_answer_layout", "not_mapped"}
        or "missing" in statuses.values()
    ):
        return "P4_待补资料", "存在缺科、部分资料、混合卷别或答案阻塞"
    if exam.get("import_candidate"):
        return "P1_可直接导入", "四科、答案、媒体和文本层均通过基础门禁"
    if exam.get("asset_complete") and answer_status in {"mapped", "mapped_with_warnings"}:
        return "P2_OCR后导入", "素材齐备，需 OCR、题面校对或答案警告复核"
    if any(
        status in {"archive_only", "content_only", "media_only", "archive_only_no_content"}
        for status in statuses.values()
    ):
        return "P3_先解压配对", "媒体仍在压缩包内或题面/媒体尚未配齐"
    return "P4_待人工复核", "未达到自动导入条件"


def imported_exam_ids(practice_root: Path) -> set[str]:
    ids = set()
    if not practice_root.is_dir():
        return ids
    for manifest_path in practice_root.glob("*/manifest.json"):
        manifest = read_json(manifest_path)
        if manifest.get("source_kind") == "real_exam":
            ids.add(
                normalize_exam_key(
                    str(
                        manifest.get("inventory_exam_key")
                        or manifest.get("id")
                        or manifest_path.parent.name
                    )
                )
            )
    return ids


def write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def relative_output_path(path: Path, output: Path) -> str:
    return str(path.relative_to(output))


def build_exam_readme(exam: dict, answer_map: dict, priority: str, reason: str) -> str:
    sections = exam.get("sections") or {}
    lines = [
        f"# {exam['exam_key']}",
        "",
        f"> {NOTICE}",
        "",
        f"- 日期：{exam['exam_date']}",
        f"- 卷别：{exam['variant']}",
        f"- 来源目录：{'；'.join(exam.get('source_dirs') or [])}",
        f"- 导入优先级：{priority}",
        f"- 说明：{reason}",
        f"- 答案对应状态：{answer_map.get('status') or '未对应'}",
        f"- OCR 阻塞：{'是' if exam.get('has_ocr_blocker') else '否'}",
        "",
        "## 科目状态",
        "",
    ]
    for section, label in (
        ("reading", "阅读"),
        ("listening", "听力"),
        ("speaking", "口语"),
        ("writing", "写作"),
    ):
        lines.append(f"- {label}：{(sections.get(section) or {}).get('status', 'missing')}")
    if exam.get("partial_markers"):
        lines.extend(["", "## 部分/缺失标记", ""])
        lines.extend(f"- `{path}`" for path in exam["partial_markers"])
    if answer_map.get("warnings"):
        lines.extend(["", "## 答案警告", "", answer_map["warnings"]])
    return "\n".join(lines) + "\n"


def build_library(
    source: Path,
    output: Path,
    real_inventory: dict,
    official_audit: dict,
    crosswalk: dict[str, dict],
    imported_ids: set[str],
    force: bool = False,
    workers: int = 4,
) -> dict:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    prepare_output(output, force)
    index_dir = output / "00_索引"
    index_dir.mkdir()
    dispositions: dict[str, dict] = {}
    duplicate_rows: list[dict] = []
    import_queue: list[dict] = []
    catalog = {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "notice": NOTICE,
        "source_root": str(source),
        "library_root": str(output),
        "real_exams": [],
        "official_sources": [],
    }

    exam_by_key = {exam["exam_key"]: exam for exam in real_inventory.get("exams") or []}
    files_by_exam: dict[str, list[dict]] = defaultdict(list)
    for row in real_inventory.get("files") or []:
        files_by_exam[row["exam_key"]].append(row)

    real_duplicate_lookup = {}
    for group_id, group in enumerate(real_inventory.get("duplicates") or [], start=1):
        for path in group["paths"]:
            real_duplicate_lookup[path] = (group_id, group)

    for exam in sorted(exam_by_key.values(), key=lambda item: item["exam_key"]):
        exam_key = exam["exam_key"]
        answer_map = crosswalk_for_exam(exam_key, crosswalk)
        priority, reason = import_priority(exam, answer_map, imported_ids)
        exam_dir = output / "01_真题套卷" / exam_key
        exam_dir.mkdir(parents=True)
        linked_files = []
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in files_by_exam[exam_key]:
            grouped[row["sha256"]].append(row)
        for digest, rows in grouped.items():
            canonical = choose_canonical(rows)
            category = exam_file_category(canonical)
            source_path = source / canonical["path"]
            link_path = create_link(source_path, exam_dir / category / canonical["name"], digest)
            linked_files.append({
                "source_path": canonical["path"],
                "library_path": relative_output_path(link_path, output),
                "sha256": digest,
                "category": category,
            })
            dispositions[canonical["path"]] = {
                "source_path": canonical["path"],
                "sha256": digest,
                "status": "linked_real_exam",
                "area": exam_key,
                "library_path": relative_output_path(link_path, output),
                "canonical_source": canonical["path"],
                "notes": "",
            }
            for duplicate in rows:
                if duplicate["path"] == canonical["path"]:
                    continue
                dispositions[duplicate["path"]] = {
                    "source_path": duplicate["path"],
                    "sha256": digest,
                    "status": "duplicate_omitted",
                    "area": exam_key,
                    "library_path": relative_output_path(link_path, output),
                    "canonical_source": canonical["path"],
                    "notes": "同套卷精确重复副本",
                }
        (exam_dir / "README.md").write_text(
            build_exam_readme(exam, answer_map, priority, reason),
            encoding="utf-8",
        )
        exam_manifest = {
            "exam": exam,
            "answer_crosswalk": answer_map,
            "import_priority": priority,
            "priority_reason": reason,
            "files": linked_files,
        }
        (exam_dir / "manifest.json").write_text(
            json.dumps(exam_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        catalog["real_exams"].append({
            "exam_key": exam_key,
            "library_path": relative_output_path(exam_dir, output),
            "priority": priority,
            "answer_status": answer_map.get("status") or "not_mapped",
            "linked_file_count": len(linked_files),
        })
        import_queue.append({
            "exam_key": exam_key,
            "priority": priority,
            "reason": reason,
            "answer_status": answer_map.get("status") or "not_mapped",
            "asset_complete": exam.get("asset_complete"),
            "ocr_blocker": exam.get("has_ocr_blocker"),
            "reading": exam["sections"]["reading"]["status"],
            "listening": exam["sections"]["listening"]["status"],
            "speaking": exam["sections"]["speaking"]["status"],
            "writing": exam["sections"]["writing"]["status"],
            "source_dirs": " | ".join(exam.get("source_dirs") or []),
        })

    official_sources = {
        row["source_id"]: row
        for row in official_audit.get("sources") or []
    }
    official_files: dict[str, list[dict]] = defaultdict(list)
    for row in official_audit.get("file_records") or []:
        official_files[row["source_id"]].append(row)

    for source_id, metadata in sorted(official_sources.items()):
        source_dir = output / "02_官方样题" / source_id
        source_dir.mkdir(parents=True)
        linked_files = []
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in official_files[source_id]:
            grouped[row["sha256"]].append(row)
        for digest, rows in grouped.items():
            canonical = choose_canonical(rows)
            category = official_file_category(canonical)
            source_path = source / canonical["path"]
            link_path = create_link(
                source_path,
                source_dir / category / Path(canonical["path"]).name,
                digest,
            )
            linked_files.append({
                "source_path": canonical["path"],
                "library_path": relative_output_path(link_path, output),
                "sha256": digest,
                "category": category,
            })
            dispositions[canonical["path"]] = {
                "source_path": canonical["path"],
                "sha256": digest,
                "status": "linked_official",
                "area": source_id,
                "library_path": relative_output_path(link_path, output),
                "canonical_source": canonical["path"],
                "notes": "",
            }
            for duplicate in rows:
                if duplicate["path"] == canonical["path"]:
                    continue
                dispositions[duplicate["path"]] = {
                    "source_path": duplicate["path"],
                    "sha256": digest,
                    "status": "duplicate_omitted",
                    "area": source_id,
                    "library_path": relative_output_path(link_path, output),
                    "canonical_source": canonical["path"],
                    "notes": "官方同来源精确重复副本",
                }
        source_manifest = {
            **metadata,
            "duplicate_status": "clear",
            "files": linked_files,
        }
        (source_dir / "manifest.json").write_text(
            json.dumps(source_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (source_dir / "README.md").write_text(
            "\n".join([
                f"# {metadata.get('label') or source_id}",
                "",
                f"> {NOTICE}",
                "",
                f"- 来源 ID：{source_id}",
                f"- 类型：{metadata.get('kind')}",
                f"- PDF SHA-256：`{metadata.get('pdf_sha256')}`",
                f"- 题目块：{metadata.get('question_block_count')}",
                "- 重复状态：clear",
                "",
            ]),
            encoding="utf-8",
        )
        catalog["official_sources"].append({
            "source_id": source_id,
            "label": metadata.get("label"),
            "library_path": relative_output_path(source_dir, output),
            "linked_file_count": len(linked_files),
        })

    known_exam_keys = set(exam_by_key)
    for collection in real_inventory.get("unclassified_dated_collections") or []:
        candidate = collection["candidate_key"]
        manual_dir = output / "04_待人工确认" / candidate
        for relative_path in collection["files"]:
            row = next(
                (
                    item for item in real_inventory.get("files") or []
                    if item["path"] == relative_path
                ),
                None,
            )
            digest = (row or {}).get("sha256") or sha256_file(source / relative_path)
            link_path = create_link(
                source / relative_path,
                manual_dir / Path(relative_path).name,
                digest,
            )
            dispositions[relative_path] = {
                "source_path": relative_path,
                "sha256": digest,
                "status": "manual_review",
                "area": candidate,
                "library_path": relative_output_path(link_path, output),
                "canonical_source": relative_path,
                "notes": "有日期但未识别科目",
            }

    unmatched = [
        path
        for path in real_inventory.get("unmatched_relevant_files") or []
        if path not in dispositions
    ]
    support_candidates = []
    for relative_path in unmatched:
        category, note = support_category(relative_path)
        path = source / relative_path
        if category == "excluded":
            dispositions[relative_path] = {
                "source_path": relative_path,
                "sha256": "",
                "status": "excluded_generated",
                "area": "",
                "library_path": "",
                "canonical_source": "",
                "notes": note,
            }
        elif path.is_file():
            support_candidates.append((relative_path, category, note))
        else:
            dispositions[relative_path] = {
                "source_path": relative_path,
                "sha256": "",
                "status": "missing_source",
                "area": category,
                "library_path": "",
                "canonical_source": "",
                "notes": "盘点后源文件已不存在",
            }

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        hashes = list(
            pool.map(
                sha256_file,
                [source / relative_path for relative_path, _category, _note in support_candidates],
            )
        )
    support_by_hash: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for item, digest in zip(support_candidates, hashes):
        support_by_hash[digest].append(item)

    for digest, items in support_by_hash.items():
        canonical_path, category, note = min(items, key=lambda item: canonical_rank(item[0]))
        link_path = create_link(
            source / canonical_path,
            output / "03_辅助资料" / category / canonical_path,
            digest,
        )
        dispositions[canonical_path] = {
            "source_path": canonical_path,
            "sha256": digest,
            "status": "linked_support",
            "area": category,
            "library_path": relative_output_path(link_path, output),
            "canonical_source": canonical_path,
            "notes": note,
        }
        for duplicate_path, duplicate_category, duplicate_note in items:
            if duplicate_path == canonical_path:
                continue
            dispositions[duplicate_path] = {
                "source_path": duplicate_path,
                "sha256": digest,
                "status": "duplicate_omitted",
                "area": duplicate_category,
                "library_path": relative_output_path(link_path, output),
                "canonical_source": canonical_path,
                "notes": duplicate_note or "辅助资料精确重复副本",
            }

    for group_id, group in enumerate(real_inventory.get("duplicates") or [], start=1):
        canonical = min(group["paths"], key=canonical_rank)
        for path in group["paths"]:
            duplicate_rows.append({
                "scope": "real_exam",
                "group_id": group_id,
                "classification": (
                    "cross_set_content_duplicate"
                    if len(group.get("exam_keys") or []) > 1
                    else "duplicate_copy"
                ),
                "sha256": group["sha256"],
                "copy_count": group["copy_count"],
                "exam_or_source_ids": " | ".join(group.get("exam_keys") or []),
                "canonical_source": canonical,
                "source_path": path,
                "reclaimable_bytes": group["reclaimable_bytes"],
            })
    for group_id, group in enumerate(
        official_audit.get("file_duplicate_groups") or [],
        start=1,
    ):
        for path in group["paths"]:
            duplicate_rows.append({
                "scope": "official",
                "group_id": group_id,
                "classification": group["classification"],
                "sha256": group["sha256"],
                "copy_count": group["copy_count"],
                "exam_or_source_ids": " | ".join(group.get("source_ids") or []),
                "canonical_source": group["canonical_path"],
                "source_path": path,
                "reclaimable_bytes": group["reclaimable_bytes"],
            })
    support_group_id = 0
    for digest, items in support_by_hash.items():
        if len(items) < 2:
            continue
        support_group_id += 1
        canonical = min((item[0] for item in items), key=canonical_rank)
        size = (source / canonical).stat().st_size
        for path, category, _note in items:
            duplicate_rows.append({
                "scope": "support",
                "group_id": support_group_id,
                "classification": "duplicate_copy",
                "sha256": digest,
                "copy_count": len(items),
                "exam_or_source_ids": category,
                "canonical_source": canonical,
                "source_path": path,
                "reclaimable_bytes": size * (len(items) - 1),
            })

    disposition_rows = sorted(dispositions.values(), key=lambda row: row["source_path"])
    write_csv(
        index_dir / "文件去向.csv",
        disposition_rows,
        [
            "source_path",
            "sha256",
            "status",
            "area",
            "library_path",
            "canonical_source",
            "notes",
        ],
    )
    write_csv(
        index_dir / "重复文件.csv",
        duplicate_rows,
        [
            "scope",
            "group_id",
            "classification",
            "sha256",
            "copy_count",
            "exam_or_source_ids",
            "canonical_source",
            "source_path",
            "reclaimable_bytes",
        ],
    )
    priority_order = {
        "P0_已导入": 0,
        "P1_可直接导入": 1,
        "P2_OCR后导入": 2,
        "P3_先解压配对": 3,
        "P4_待补资料": 4,
        "P4_待人工复核": 5,
    }
    import_queue.sort(key=lambda row: (priority_order.get(row["priority"], 99), row["exam_key"]))
    write_csv(
        index_dir / "导入队列.csv",
        import_queue,
        [
            "exam_key",
            "priority",
            "reason",
            "answer_status",
            "asset_complete",
            "ocr_blocker",
            "reading",
            "listening",
            "speaking",
            "writing",
            "source_dirs",
        ],
    )
    status_counts = Counter(row["status"] for row in disposition_rows)
    category_counts = Counter(
        row["area"]
        for row in disposition_rows
        if row["status"] in {"linked_support", "linked_official", "linked_real_exam"}
    )
    summary = {
        "source_file_count": len(disposition_rows),
        "linked_file_count": sum(status.startswith("linked_") for status in (row["status"] for row in disposition_rows)),
        "duplicate_omitted_count": status_counts["duplicate_omitted"],
        "excluded_generated_count": status_counts["excluded_generated"],
        "manual_review_count": status_counts["manual_review"],
        "missing_source_count": status_counts["missing_source"],
        "real_exam_count": len(catalog["real_exams"]),
        "official_source_count": len(catalog["official_sources"]),
        "status_counts": dict(sorted(status_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
    }
    catalog["summary"] = summary
    (index_dir / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    priority_counts = Counter(row["priority"] for row in import_queue)
    overview = [
        "# 新托福素材整理总览",
        "",
        f"> {NOTICE}",
        "",
        "此目录是非破坏性素材库。所有素材文件均为指向原目录的符号链接；",
        "原文件没有被移动、重命名或删除。",
        "",
        f"- 生成时间：{catalog['generated_at']}",
        f"- 原始目录：`{source}`",
        f"- 真题套卷：**{summary['real_exam_count']}**",
        f"- 官方 Practice / OG：**{summary['official_source_count']}**",
        f"- 建立素材链接：**{summary['linked_file_count']}**",
        f"- 省略精确重复副本：**{summary['duplicate_omitted_count']}**",
        f"- 排除临时/程序产物：**{summary['excluded_generated_count']}**",
        f"- 待人工确认：**{summary['manual_review_count']}**",
        "",
        "## 导入优先级",
        "",
    ]
    for priority in sorted(priority_counts, key=lambda key: priority_order.get(key, 99)):
        overview.append(f"- {priority}：{priority_counts[priority]} 套")
    overview.extend([
        "",
        "## 目录说明",
        "",
        "- `01_真题套卷`：按规范套卷 ID 整理，每套含 README、manifest 和分科素材。",
        "- `02_官方样题`：ETS Practice 1–5 与 OG Chapter 6，已按哈希去除纯副本。",
        "- `03_辅助资料`：分科汇编、词汇、评分标准、课件、课程安排和采集归档。",
        "- `04_待人工确认`：有日期但无法自动识别科目的素材。",
        "- `00_索引/文件去向.csv`：每个相关原文件的最终处理结果。",
        "- `00_索引/重复文件.csv`：真题、官方资料和辅助资料的重复明细。",
        "- `00_索引/导入队列.csv`：后续结构化导入顺序。",
        "",
    ])
    (output / "README.md").write_text("\n".join(overview), encoding="utf-8")
    (index_dir / "总览.md").write_text("\n".join(overview), encoding="utf-8")
    return {"catalog": catalog, "dispositions": disposition_rows, "duplicates": duplicate_rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Organize TOEFL materials with symlinks.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--real-inventory", type=Path, default=DEFAULT_REAL_INVENTORY)
    parser.add_argument("--official-audit", type=Path, default=DEFAULT_OFFICIAL_AUDIT)
    parser.add_argument("--crosswalk", type=Path, default=DEFAULT_CROSSWALK)
    parser.add_argument("--practice-root", type=Path, default=Path("data") / "toefl_practice")
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    result = build_library(
        args.source,
        args.output,
        read_json(args.real_inventory),
        read_json(args.official_audit),
        load_crosswalk(args.crosswalk),
        imported_exam_ids(args.practice_root),
        force=args.force,
        workers=args.workers,
    )
    print(
        json.dumps(
            {
                "output": str(args.output.expanduser().resolve()),
                **result["catalog"]["summary"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
