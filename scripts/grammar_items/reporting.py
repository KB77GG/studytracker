"""Deterministic audit reports; regression IDs here never influence generation."""

import json
import platform
import re
from collections import Counter
from hashlib import sha256
from importlib.metadata import version

from .checks import Reason as R
from .templates import GENERATOR_VERSION, TEMPLATES

REGRESSION_CASES = (
    ("bad", "ielts7_test3_p1", "K-03"),
    ("bad", "ielts8_test4_p1", "C-04"),
    ("bad", "reading_jijing_76_test_43_p2", "H-02"),
    ("bad", "reading_jijing_73_test_5_p2", "F-05"),
    ("bad", "reading_jijing_56_test_64_p2", "C-01"),
    ("bad", "ielts13_test2_p2", "C-04"),
    ("positive", "reading_jijing_91_test_49_p3", "D-02"),
    ("positive", "ielts11_test3_p2", "A-04"),
    ("positive", "ielts15_test2_p3", "D-05"),
    # Plan v0.2 section B5.
    ("bad", "ielts4_test2_p2", "G-31"),
    ("positive", "ielts6_test3_p1", "C-06"),
    ("positive", "reading_jijing_88_test_98_p2", "G-04"),
    ("positive", "reading_jijing_88_test_98_p2", "G-04b"),
)
# Expected whole-sentence hits; None means "report only" (plan v0.2 B1).
INDEPENDENT_FILTERS = (
    # 36 in plan v0.1; +1 after the v0.2 review marked 71_1_p2 E-01 as predicate_fragment (F4);
    # -1 after the 2026-10-19 re-split joined ielts4_test4_p1 C-14's cut "that U.S." to C-15.
    (R.TAGGED_FRAGMENT, 36),
    (R.CLAUSE_ATTACHED_TO_CONJUNCTION, 2),
    (R.GLUED_SENTENCE_BOUNDARY, 0),
    # 51 in plan v0.2; after the 2026-10-19 re-split only an embedded quotation of three
    # sentences remains (9_81_p1 F-02), which cannot be split without breaking its sentence.
    (R.MULTI_SENTENCE_UNIT, 1),
    (R.SUSPECTED_SPLIT_WORD, None),
    # 14 units before the 2026-10-19 source fixes removed the stray leading periods.
    (R.LEADING_STRAY_PUNCTUATION, 0),
    (R.CONTROL_CHARACTER, None),
)
RESPLIT_ID = re.compile(r"^[A-Z]-\d+[b-z]$")
NODE_IDS = (
    "G-S01",
    "G-S02",
    "G-C02",
    "G-C03",
    "G-C04",
    "G-C08",
    "G-C10",
    "G-C11",
    "G-N01",
    "G-N04",
    "G-L01",
)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in records:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def template_counts(candidates, rejections):
    result = {t: {"auto_pass": 0, "needs_review": 0, "rejected": 0} for t in TEMPLATES}
    for item in candidates:
        result[item["template"]][item["status"]] += 1
    for row in rejections:
        for template in TEMPLATES if row["scope"] == "sentence" else [row["template"]]:
            result[template]["rejected"] += 1
    return result


def benchmark_results(candidates, rejections, sources):
    result = []
    for kind, passage, sid in REGRESSION_CASES:
        key = (passage, sid)
        items = [
            i for i in candidates if (i["source"]["passage_id"], i["source"]["sentence_id"]) == key
        ]
        rejects = [
            r for r in rejections if (r["source"]["passage_id"], r["source"]["sentence_id"]) == key
        ]
        templates = {}
        for template in TEMPLATES:
            questions = [
                {
                    k: i[k]
                    for k in (
                        "item_id",
                        "node_id",
                        "target",
                        "answer",
                        "distractors",
                        "status",
                        "reasons",
                        "evidence",
                    )
                }
                for i in items
                if i["template"] == template
            ]
            failures = [
                r["reasons"]
                for r in rejects
                if r["scope"] == "sentence" or r["template"] == template
            ]
            templates[template] = {
                "candidates": questions,
                "rejections": failures,
                "not_applicable": not questions and not failures,
            }
        result.append({"kind": kind, "source": sources.get(key), "templates": templates})
    return result


def independent_hits(rows):
    result = {}
    for reason, expected in INDEPENDENT_FILTERS:
        hits = [source for source, reasons in rows if reason in reasons]
        result[reason] = {
            "expected": expected,
            "actual": len(hits),
            "matches_expected": None if expected is None else len(hits) == expected,
            "sentences": hits,
        }
    return result


def relative_adverb_stats(candidates):
    """Plan v0.2 B4: counts plus one row per flagged target (review finding F5)."""
    flagged = [i for i in candidates if R.POSSIBLE_RELATIVE_ADVERB in i["reasons"]]
    targets = {}
    for item in flagged:
        source, tag = item["source"], item["evidence"]["tag_span"]
        key = (source["passage_id"], source["sentence_id"], tag["start"], tag["end"])
        row = targets.setdefault(
            key,
            {
                "passage_id": source["passage_id"],
                "sentence_id": source["sentence_id"],
                "target": source["sentence"][tag["start"] : tag["end"]],
                "templates": [],
                "item_ids": [],
            },
        )
        row["templates"] = sorted({*row["templates"], item["template"]})
        row["item_ids"] = sorted({*row["item_ids"], item["item_id"]})
    return {
        "items_by_template": dict(sorted(Counter(i["template"] for i in flagged).items())),
        "distinct_targets": len(targets),
        "targets": [targets[key] for key in sorted(targets)],
    }


def resplit_stats(all_results):
    """Sentences before/after the v0.2 re-split; splitting only adds <id>b, <id>c ... rows."""
    ids = sorted(
        f"{s['passage_id']} {s['sentence_id']}"
        for s, _ in all_results
        if RESPLIT_ID.match(s["sentence_id"])
    )
    return {
        "sentences_before": len(all_results) - len(ids),
        "sentences_after": len(all_results),
        "added": len(ids),
        "new_sentence_ids": ids,
    }


def build_report(root, environment, seed, candidates, rejections, all_results, batch_stats):
    data_dir = root / "data/reading_study"
    fingerprint = sha256()
    for path in sorted(p for p in data_dir.rglob("*") if p.is_file()):
        fingerprint.update(path.read_bytes())
    reasons = Counter(r for item in [*candidates, *rejections] for r in item["reasons"])
    sources = {(s["passage_id"], s["sentence_id"]): s for s, _ in all_results}
    node_counts = {
        node: dict(Counter(i["status"] for i in candidates if i["node_id"] == node))
        for node in NODE_IDS
    }
    row_count = sum(value["rows"] for value in batch_stats.values())
    return {
        "generator_version": GENERATOR_VERSION,
        "plan_version": "v0.2",
        "corpus": {
            "passages": len({s["passage_id"] for s, _ in all_results}),
            "sentences": len(all_results),
            "candidates": len(candidates),
            "sentence_rejections": sum(r["scope"] == "sentence" for r in rejections),
            "template_rejections": sum(r["scope"] == "template" for r in rejections),
        },
        "environment": {
            **environment,
            "python": platform.python_version(),
            "torch": version("torch"),
            "openpyxl": version("openpyxl"),
            "seed": seed,
            "reading_study_sha256": fingerprint.hexdigest(),
            "grammar_graph_sha256": sha256(
                (root / "data/grammar_graph/grammar_graph_v0.json").read_bytes()
            ).hexdigest(),
        },
        "counts_by_template": template_counts(candidates, rejections),
        "counts_by_node": node_counts,
        "reason_counts": dict(sorted(reasons.items(), key=lambda pair: (-pair[1], pair[0]))),
        "candidate_source_kind": dict(
            sorted(Counter(i["source"]["source_kind"] for i in candidates).items())
        ),
        "candidate_difficulty": dict(sorted(Counter(i["difficulty"] for i in candidates).items())),
        "independent_sentence_filters": independent_hits(all_results),
        "possible_relative_adverb": relative_adverb_stats(candidates),
        "resplit": resplit_stats(all_results),
        "regression_cases": benchmark_results(candidates, rejections, sources),
        "review_batch": {
            "rows": row_count,
            "estimated_minutes": row_count / 2,
            "templates": batch_stats,
        },
        "counting_notes": [
            "候选题按 item_id 计数；模板 rejected 含每个整句拒绝一次，以及该模板的目标/选句拒绝记录。",
            "原因码按候选题及拒绝记录计数；整句拒绝在 JSONL 中只记录一条，保留全部原因。",
            "整句规则在全库独立统计，不受其他过滤顺序影响；multi_sentence_unit 在 2026-10-19 重新拆句后预期为 1（一处无法拆开的嵌入引语）。",
            "v0.2：动词目标和干扰项都显示完整动词单位（含助动词、否定词、小品词），target.parts 为连续片段。",
            "v0.2：when/where/why 状语从句紧跟名词时，T2/T3/T4 一律 needs_review（possible_relative_adverb）。",
            "v0.2：动词单位不受原标注范围截断；有成分落在标注范围外时，T1/T6 一律 needs_review（verb_unit_outside_span），T1 答案按计划保持不变。",
            "v0.2：suspected_split_word 以全库词频判断（两个相邻词都极少见、拼起来是语料里出现过的词），只报告不设预期。",
            "v0.2：leading_stray_punctuation 排除以孤立标点开头的句子（段落标号被删后残留的句点），原文修复后预期为 0。",
            "v0.2：control_character 排除含控制字符的句子（原文转码时丢失的字符，如 $ 变成 NUL），只报告不设预期。",
            "拆句前句数 = 拆句后句数 − 新增 ID 数：重新拆句只新增 <原ID>b 等句子，不删除句子。",
            "无白名单目标的 T2/T3/T4 不生成题，也不虚构拒绝原因。T6(a) 单独记录主句选句拒绝。",
            "字符偏移均为原句 [start,end)；evidence 中的 token 范围也是左闭右开。",
            "分类答案使用固定选项文字；抽样 JSONL 的 pool_status 不写入工作簿。",
            "同一模板完全相同的 item_id 和内容去重，ID 相同但内容不同则报错停止。",
            "XLSX 使用固定元数据和不压缩 ZIP，避免时间及压缩库版本影响字节复现。",
        ],
    }


def markdown_report(report):
    lines = [
        "# 语法候选题生成报告 v0.2",
        "",
        "按执行计划 v0.2（在 v0.1 基础上的增量）生成；候选题尚未通过教师审核、未入库。",
        "",
        "## 题型数量",
        "",
        "| 题型 | auto_pass | needs_review | rejected |",
        "|---|---:|---:|---:|",
    ]
    for template, counts in report["counts_by_template"].items():
        lines.append(
            f"| {template} | {counts['auto_pass']} | {counts['needs_review']} | {counts['rejected']} |"
        )
    for key, title in (
        ("corpus", "范围"),
        ("environment", "环境与输入指纹"),
        ("counts_by_node", "知识点数量"),
        ("reason_counts", "原因码数量"),
        ("candidate_source_kind", "来源分布"),
        ("candidate_difficulty", "难度分布"),
        ("review_batch", "抽查清单"),
        ("possible_relative_adverb", "关系副词风险"),
        ("resplit", "重新拆句"),
    ):
        lines.extend(
            [
                "",
                f"## {title}",
                "",
                "```json",
                json.dumps(report[key], ensure_ascii=False, indent=2),
                "```",
            ]
        )
    lines.extend(["", "## 独立整句过滤命中", ""])
    for reason, result in report["independent_sentence_filters"].items():
        lines.extend(
            [
                f"### {reason}",
                "",
                f"实际 {result['actual']} 句；"
                + (
                    "计划未设预期，只报告。"
                    if result["expected"] is None
                    else f"计划预期 {result['expected']} 句。"
                ),
                "",
            ]
        )
        for source in result["sentences"]:
            lines.append(
                f"- `{source['passage_id']}` {source['sentence_id']}：{source['sentence']}"
            )
    lines.extend(["", "## 回归例句逐模板结果", ""])
    for case in report["regression_cases"]:
        source = case["source"]
        lines.extend(
            [
                f"### {source['passage_id']} {source['sentence_id']} ({case['kind']})",
                "",
                source["sentence"],
                "",
            ]
        )
        for template, result in case["templates"].items():
            lines.append(f"- **{template}**：" + describe_result(result))
    lines.extend(["", "## 计数和复现约定", "", *[f"- {note}" for note in report["counting_notes"]]])
    return "\n".join(lines) + "\n"


def describe_result(result):
    if result["not_applicable"]:
        return "无适用白名单目标。"
    parts = []
    for question in result["candidates"]:
        answer = question["answer"]["option"] or " / ".join(
            s["text"] for s in question["answer"]["spans"]
        )
        reasons = ", ".join(question["reasons"]) or "标注与解析器一致"
        target = question["target"]["text"] if question["target"] else ""
        parts.append(f"{question['status']}；目标 `{target}`；答案 `{answer}`；{reasons}")
    parts.extend("rejected：" + ", ".join(reasons) for reasons in result["rejections"])
    return "；".join(parts)
