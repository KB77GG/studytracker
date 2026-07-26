#!/usr/bin/env python3
"""Audit the file-backed TOEFL practice bank and produce review artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.toefl_bank_quality import (  # noqa: E402
    analyze_bank,
    blocking_issues,
    load_source_profiles,
)

DEFAULT_DATA_ROOT = REPO_ROOT / "data" / "toefl_practice"
DEFAULT_PROFILE = REPO_ROOT / "data" / "toefl_quality" / "source_profiles.json"
DEFAULT_JSON = REPO_ROOT / "data" / "toefl_quality" / "latest_audit.json"
DEFAULT_MARKDOWN = REPO_ROOT / "docs" / "toefl_quality_audit.md"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _percent(value: int, denominator: int) -> str:
    return f"{value / denominator * 100:.1f}%" if denominator else "0.0%"


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    published = int(summary.get("published_exam_count") or 0)
    partial = int(summary.get("published_partial_count") or 0)
    subject_count = int(summary.get("subject_count") or 0)
    ready_subjects = int(summary.get("release_ready_subject_count") or 0)
    issue_counts = summary.get("issue_counts") or {}
    code_counts = Counter(summary.get("issue_code_counts") or {})

    lines = [
        "# TOEFL 题库质量审计",
        "",
        "## 技术摘要",
        "",
        (
            f"- 当前扫描 {summary.get('exam_count', 0)} 套卷、{subject_count} 个科目、"
            f"{summary.get('question_object_count', 0)} 个题目对象。"
        ),
        (
            f"- {published} 套处于发布状态，其中 {partial} 套仍标记为不完整"
            f"（{_percent(partial, published)}）。"
        ),
        (
            f"- 严格门禁下可直接发布的科目为 {ready_subjects}/{subject_count}"
            f"（{_percent(ready_subjects, subject_count)}）。未通过来源审阅的科目不会被视为可发布。"
        ),
        (
            f"- 发现 critical {issue_counts.get('critical', 0)}、"
            f"high {issue_counts.get('high', 0)}、"
            f"medium {issue_counts.get('medium', 0)}、"
            f"low {issue_counts.get('low', 0)} 项。"
        ),
        "",
        "## 最高风险发现",
        "",
        "| 检查项 | 数量 | 发布风险 |",
        "|---|---:|---|",
        (
            f"| 已发布但题卷不完整 | {summary.get('published_partial_count', 0)}"
            " | 学生会直接遇到缺题或缺科目 |"
        ),
        (
            f"| 四选项结构不完整 | {summary.get('invalid_mc_option_count', 0)}"
            " | 题干与选项无法可靠作答或判分 |"
        ),
        (
            f"| 自动题缺少可靠答案 | {summary.get('missing_answer_count', 0)}"
            " | 成绩分母与错题报告不可信 |"
        ),
        (
            f"| 听力模块复用同一整段音频 | {summary.get('duplicate_audio_binding_count', 0)}"
            " | Module 2 会从错误位置播放 |"
        ),
        "",
        "## 主要问题分布",
        "",
        "| 问题代码 | 数量 |",
        "|---|---:|",
    ]
    for code, count in code_counts.most_common(15):
        lines.append(f"| `{code}` | {count} |")

    lines.extend([
        "",
        "## 套卷级发布状态",
        "",
        "| 套卷 | 当前发布 | 内容状态 | 严格门禁 | Critical | High | Medium |",
        "|---|---|---|---|---:|---:|---:|",
    ])
    for exam in report.get("exams") or []:
        counts = exam.get("issue_counts") or {}
        lines.append(
            f"| {exam['exam_id']} | {'是' if exam['published'] else '否'} | "
            f"{exam.get('content_status') or '-'} | {exam['release_status']} | "
            f"{counts.get('critical', 0)} | {counts.get('high', 0)} | "
            f"{counts.get('medium', 0)} |"
        )

    first_exam = next(
        (exam for exam in report.get("exams") or [] if exam["exam_id"] == "2026-01-21_A"),
        None,
    )
    if first_exam:
        lines.extend([
            "",
            "## 第一套：2026-01-21_A",
            "",
            (
                "该套已建立页级来源结构档案，但四科仍处于人工审阅前状态。"
                "以下数量是导入后的题目覆盖，不代表内容语义已经核准。"
            ),
            "",
            "| 科目 | 题目对象 | 计分项 | 门禁状态 | Critical | High | Medium |",
            "|---|---:|---:|---|---:|---:|---:|",
        ])
        for subject in first_exam.get("subjects") or []:
            counts = subject.get("issue_counts") or {}
            lines.append(
                f"| {subject['subject']} | {subject['question_objects']} | "
                f"{subject['item_count']} | {subject['release_status']} | "
                f"{counts.get('critical', 0)} | {counts.get('high', 0)} | "
                f"{counts.get('medium', 0)} |"
            )

    lines.extend([
        "",
        "## 门禁方法",
        "",
        "- 题目 ID、Module 和题号范围必须唯一且可解析。",
        "- 选择题必须恰好四个非空选项，答案必须属于可见选项。",
        "- 填空答案数量必须与题号范围一致；组句答案必须可由展示词块构造。",
        "- 听力与口语题必须解析到实际存在的静态音频；不同听力 Module 不得共用同一整段音频。",
        "- 每套上线前必须建立带 SHA-256 的来源档案，并由人工将对应科目标记为 `approved`。",
        "",
        "## 限制与下一步",
        "",
        "- 本报告验证结构、覆盖率、来源哈希和媒体绑定，不自动判断题干与选项的语义匹配。",
        "- 第一套需逐题对照原始 PDF，并对听力进行时间轴/题组抽验后才可批准。",
        "- 任何无法从来源确定的内容保持 `review_required`，不得由模型猜测补全。",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument(
        "--require-release-ready",
        action="append",
        default=[],
        metavar="EXAM_ID",
        help="Exit non-zero when the named exam still has critical/high issues.",
    )
    args = parser.parse_args()

    report = analyze_bank(
        args.data_root,
        REPO_ROOT,
        profiles=load_source_profiles(args.profile),
        source_root=args.source_root,
    )
    _write_json(args.output_json, report)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.write_text(render_markdown(report), encoding="utf-8")

    summary = report["summary"]
    print(
        f"Audited {summary.get('exam_count', 0)} exams; "
        f"critical={summary.get('issue_counts', {}).get('critical', 0)}, "
        f"high={summary.get('issue_counts', {}).get('high', 0)}."
    )
    if args.require_release_ready:
        blockers = blocking_issues(report, args.require_release_ready)
        if blockers:
            print(
                f"Release blocked for {', '.join(args.require_release_ready)}: "
                f"{len(blockers)} critical/high issue(s).",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
