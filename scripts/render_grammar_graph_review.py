#!/usr/bin/env python3
"""Render the teacher-review document for the grammar knowledge graph draft.

The JSON graph is the single source of truth; this script turns it into a
Markdown checklist (with a Mermaid diagram of the phase-1 scope) and adds live
counts of how many tagged Reading Study sentences can feed each knowledge point.

Usage:
    python scripts/render_grammar_graph_review.py            # write docs file
    python scripts/render_grammar_graph_review.py --stdout   # print instead
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.reading_study_glossary import CONCEPTS, resolve_role  # noqa: E402

GRAPH_PATH = ROOT / "data" / "grammar_graph" / "grammar_graph_v0.json"
READING_STUDY_DIR = ROOT / "data" / "reading_study"
OUTPUT_PATH = ROOT / "docs" / "GRAMMAR_GRAPH_V0_REVIEW.md"

AUTO_LABELS = {"auto": "可自动出题", "partial": "部分可自动", "none": "需人工出题"}
SPARSE_SENTENCE_THRESHOLD = 100
# be + optional adverb + past participle; a rough probe for untagged passives.
PASSIVE_LIKE = re.compile(
    r"\b(is|are|was|were|be|been|being)\s+(\w+ly\s+)?\w+(ed|en|wn|lt|ht)\b", re.I
)


def load_graph(path: Path = GRAPH_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_tag_stats(reading_dir: Path = READING_STUDY_DIR) -> dict:
    """Count sentences per normalized concept, plus the data-quality probes."""
    sentences_by_concept: Counter = Counter()
    sentence_concepts: list[set[str]] = []
    stats = Counter()
    for path in sorted(reading_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        stats["passages"] += 1
        for sentence in payload.get("sentences", []):
            stats["sentences"] += 1
            spans = sentence.get("structure", [])
            concepts = set()
            level_one_texts = []
            for span in spans:
                concept = resolve_role(span.get("role") or "")["concept"]
                level = span.get("level")
                concepts.add(concept)
                if concept == "unknown":
                    stats["unknown_spans"] += 1
                if level == 1:
                    level_one_texts.append(span.get("text", ""))
                    if concept == "verb_phrase" and PASSIVE_LIKE.search(span.get("text", "")):
                        stats["untagged_passive_like"] += 1
                    if concept == "passive_predicate":
                        stats["tagged_passive"] += 1
                    if concept in {"relative_clause", "noun_clause"}:
                        stats[f"level_one_{concept}"] += 1
            for span in spans:
                if span.get("level") == 2:
                    stats["level_two_spans"] += 1
                    if any(span.get("text", "") in text for text in level_one_texts):
                        stats["level_two_contained"] += 1
            if any((span.get("level") or 0) >= 3 for span in spans):
                stats["nested_three_plus"] += 1
            sentences_by_concept.update(concepts)
            sentence_concepts.append(concepts)
    return {"by_concept": sentences_by_concept, "sentences": sentence_concepts, "stats": stats}


def _pct(part: int, whole: int) -> str:
    return f"{part * 100 / whole:.1f}%" if whole else "—"


def _node_label(node: dict) -> str:
    return f"{node['id']} {node['name_zh']}"


def _render_overview(graph: dict) -> list[str]:
    nodes = graph["nodes"]
    edges = graph["edges"]
    phase_counts = Counter(node["phase"] for node in nodes)
    strength_counts = Counter(edge["strength"] for edge in edges)
    lines = [
        "## 总览",
        "",
        f"- 知识点 **{len(nodes)}** 个：第一阶段 {phase_counts[1]} 个，第二阶段 {phase_counts[2]} 个",
        f"- 依赖 **{len(edges)}** 条：硬依赖 {strength_counts['hard']} 条，软依赖 "
        f"{strength_counts['soft']} 条",
        "",
        "| 模块 | 知识点数 | 第一阶段 |",
        "|---|---:|---:|",
    ]
    for module in graph["modules"]:
        members = [node for node in nodes if node["module"] == module["id"]]
        first = sum(1 for node in members if node["phase"] == 1)
        lines.append(f"| {module['id']} {module['name_zh']} | {len(members)} | {first} |")
    lines.append("")
    return lines


def _render_mermaid(graph: dict) -> list[str]:
    phase_one = {node["id"] for node in graph["nodes"] if node["phase"] == 1}
    lines = [
        "## 第一阶段依赖图",
        "",
        "实线为硬依赖，虚线为软依赖；箭头从前置知识点指向后续知识点。",
        "",
        "```mermaid",
        "flowchart TD",
    ]
    for module in graph["modules"]:
        members = [
            node
            for node in graph["nodes"]
            if node["module"] == module["id"] and node["id"] in phase_one
        ]
        if not members:
            continue
        lines.append(f'  subgraph {module["id"]}["{module["name_zh"]}"]')
        for node in members:
            lines.append(f'    {node["id"].replace("-", "")}["{_node_label(node)}"]')
        lines.append("  end")
    for edge in graph["edges"]:
        if edge["node"] in phase_one and edge["requires"] in phase_one:
            arrow = "-->" if edge["strength"] == "hard" else "-.->"
            lines.append(
                f'  {edge["requires"].replace("-", "")} {arrow} {edge["node"].replace("-", "")}'
            )
    lines.extend(["```", ""])
    return lines


def _render_nodes(graph: dict, sentence_concepts: list[set[str]]) -> list[str]:
    by_id = {node["id"]: node for node in graph["nodes"]}
    requires = defaultdict(list)
    unlocks = defaultdict(list)
    for edge in graph["edges"]:
        requires[edge["node"]].append(edge)
        unlocks[edge["requires"]].append(edge["node"])
    task_labels = {key: text.split("：")[0] for key, text in graph["task_types"].items()}
    lines = ["## 知识点清单", ""]
    for module in graph["modules"]:
        lines.extend([f"### {module['id']} {module['name_zh']}（{module['name_en']}）", ""])
        for node in (n for n in graph["nodes"] if n["module"] == module["id"]):
            if node["concepts"]:
                wanted = set(node["concepts"])
                count = sum(1 for concepts in sentence_concepts if concepts & wanted)
                source = f"{count:,} 句真题（标注概念：{'、'.join(node['concepts'])}）"
            else:
                source = "派生能力，无直接标注"
            lines.extend(
                [
                    f"#### {_node_label(node)}（{node['name_en']}）",
                    "",
                    f"- **阶段**：第{'一' if node['phase'] == 1 else '二'}阶段 · "
                    f"**题源**：{AUTO_LABELS[node['auto_items']]}，{source}",
                    f"- **学习目标**：{node['objective']}",
                    "- **掌握证据**：" + "；".join(node["evidence"]),
                    "- **常见错误**：" + "；".join(node["common_errors"]),
                    "- **题型**：" + "、".join(task_labels[t] for t in node["task_types"]),
                ]
            )
            if node["grammar_60_units"]:
                lines.append("- **语法 60 题包**：" + "、".join(node["grammar_60_units"]))
            if requires[node["id"]]:
                lines.append("- **前置**：")
                for edge in requires[node["id"]]:
                    kind = "硬" if edge["strength"] == "hard" else "软"
                    if edge.get("confirmed_by") == "teacher":
                        kind += "·老师已确认"
                    prereq = by_id[edge["requires"]]
                    lines.append(f"  - [{kind}] {_node_label(prereq)}：{edge['reason']}")
            else:
                lines.append("- **前置**：无（起点）")
            if unlocks[node["id"]]:
                lines.append(
                    "- **后续**：" + "、".join(_node_label(by_id[i]) for i in unlocks[node["id"]])
                )
            lines.append("")
    return lines


def _render_concept_map(graph: dict, by_concept: Counter, total: int) -> list[str]:
    owners = defaultdict(list)
    for node in graph["nodes"]:
        for concept in node["concepts"]:
            owners[concept].append(_node_label(node))
    lines = [
        "## 句子解析概念与知识点对照",
        "",
        "词表共 36 个 key：35 个语法概念加 1 个小标题。",
        "",
        "| 概念 | 中文 | 含该概念的句子 | 对应知识点 |",
        "|---|---|---:|---|",
    ]
    for key, concept in CONCEPTS.items():
        target = "、".join(owners[key]) or f"不纳入：{graph['excluded_concepts'].get(key, '—')}"
        count = by_concept[key]
        lines.append(
            f"| `{key}` | {concept['zh']} | {count:,}（{_pct(count, total)}） | {target} |"
        )
    lines.append("")
    return lines


def _render_data_caveats(graph: dict, stats: Counter, by_concept: Counter) -> list[str]:
    total = stats["sentences"]
    sparse = sorted(
        (
            key
            for key in CONCEPTS
            if key not in graph["excluded_concepts"]
            and 0 < by_concept[key] < SPARSE_SENTENCE_THRESHOLD
        ),
        key=lambda key: by_concept[key],
    )
    sparse_text = "、".join(f"{CONCEPTS[k]['zh']} {by_concept[k]} 句" for k in sparse)
    return [
        "## 自动出题前要处理的标注问题",
        "",
        f"统计范围：{stats['passages']} 篇文章、{total:,} 句。",
        "",
        f"1. **被动漏标。** 第 1 层谓语中有 {stats['untagged_passive_like']} 条形如"
        f"“be + 过去分词”却只标成普通谓语，正式标为被动的只有 {stats['tagged_passive']} 条"
        "（粗略规则估计，含少量“系动词 + 形容词”）。只能用已标注的句子出正例题，"
        "不能用“没标被动”推断“没有被动”。",
        f"2. **层级不是严格包含关系。** 第 2 层成分中只有 {stats['level_two_contained']:,} / "
        f"{stats['level_two_spans']:,} 是某个第 1 层成分的子串；多数是按顺序排列、用层级表示依附深度。"
        "划边界和找先行词的题需要先把标注整理成树。",
        f"3. **主句标注覆盖率低。** 只有 {_pct(by_concept['main_clause'], total)} 的句子带主句标注，"
        "提取主干的题应由第 1 层的主语、谓语、宾语或表语拼出，不要依赖主句标注。",
        f"4. **疑似异常。** 有 {stats['level_one_relative_clause']} 个定语从句和 "
        f"{stats['level_one_noun_clause']} 个名词性从句标在第 1 层，"
        f"另有 {stats['unknown_spans']} 个成分无法归类，上线前需要抽检。",
        f"5. **题源稀少的概念。** {sparse_text}，需要人工补题。",
        f"6. **多层嵌套题源。** 含第 3 层及以上成分的句子有 {stats['nested_three_plus']:,} 句，"
        "可作为“拆解多层嵌套”的题源。",
        "",
    ]


def render(graph: dict, tag_stats: dict) -> str:
    by_concept = tag_stats["by_concept"]
    stats = tag_stats["stats"]
    not_covered = "；".join(
        item["topic"]
        + (
            f"（语法 60 题包单元 {'、'.join(item['grammar_60_units'])}）"
            if item["grammar_60_units"]
            else ""
        )
        for item in graph["not_covered"]
    )
    lines = [
        "# 语法知识图谱 v0（草稿）",
        "",
        "> 本文件由 `scripts/render_grammar_graph_review.py` 从 "
        "`data/grammar_graph/grammar_graph_v0.json` 生成，请勿手改；改 JSON 后重新运行脚本。",
        "",
        graph["status_note"],
        "",
        graph["scope"],
        graph["format_note"],
        "",
        "**审核要点：**",
        "",
        "1. 每个知识点的粒度是否合适：太粗的拆开，太细的合并。",
        "2. 每条硬依赖是否真的是“不会前者就学不会后者”；拿不准的改成软依赖。",
        "3. 第一阶段范围是否合适。",
        "4. 常见错误是否符合学生的实际情况。",
        "5. 是否缺了重要的知识点。",
        "",
    ]
    if graph.get("review_log"):
        by_label = {"teacher": "老师", "claude": "Claude"}
        lines += ["## 审核记录", ""]
        lines += [
            f"- {item['date']} · {by_label.get(item['by'], item['by'])}：{item['decision']}"
            for item in graph["review_log"]
        ]
        lines.append("")
    lines += _render_overview(graph)
    lines += _render_mermaid(graph)
    lines += _render_nodes(graph, tag_stats["sentences"])
    lines += _render_concept_map(graph, by_concept, stats["sentences"])
    lines += _render_data_caveats(graph, stats, by_concept)
    lines += [
        "## 35 个概念未覆盖的语法",
        "",
        f"{not_covered}。句子解析标注无法为这些内容出题，后续可作为第三阶段知识点，"
        "题目来自语法 60 题包或人工出题。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stdout", action="store_true", help="print instead of writing the file")
    args = parser.parse_args()
    text = render(load_graph(), collect_tag_stats())
    if args.stdout:
        print(text)
    else:
        OUTPUT_PATH.write_text(text, encoding="utf-8")
        print(f"wrote {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
