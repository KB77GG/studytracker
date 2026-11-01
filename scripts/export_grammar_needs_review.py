#!/usr/bin/env python3
"""Export every needs_review grammar candidate for an outside cross-check.

Reads output/grammar_items/candidates_v0_2.jsonl (run generate_grammar_candidates.py first)
and writes, for Cambridge and jijing separately, into output/grammar_items/needs_review/:

- a workbook with one sheet per template: the item, why it was held back (in Chinese) and
  empty verdict columns using the teacher sheet's four verdicts;
- CSV batches of 100 items (no verdict columns) to hand to a chat model one at a time.

Needs only the standard library and openpyxl.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.grammar_items.review_batch import (  # noqa: E402
    SHEET_NAMES,
    VERDICTS,
    highlighted,
    stable_xlsx,
    style_sheet,
)
from scripts.grammar_items.templates import TEMPLATES  # noqa: E402

BATCH_SIZE = 100
SOURCES = (("cambridge", "剑桥", True), ("jijing", "机经", False))
# What each reason code means for someone checking the item by hand.
REASONS_ZH = {
    "boundary_mismatch": "标注的范围与句法分析的从句边界不一致，答案的起止位置可能不对",
    "clause_type_mismatch": "标注的从句类型与句法分析不一致，题干所说的类别可能不对",
    "ambiguous_span_location": "标注的文字在原句里出现不止一次，答案位置可能取错",
    "span_not_constituent": "标注的范围不是一个完整的句法单位",
    "source_quality": "阅读解析说明原句本身有问题（语病、残缺、截断等）",
    "verb_unit_outside_span": "动词单位有一部分（助动词、否定词等）在标注范围外",
    "subject_mismatch": "标注的主语与句法分析的主语不一致",
    "parser_root_outside_verb_span": "句法分析的主句谓语不在标注的谓语范围内",
    "parser_root_inside_subordinate_span": "句法分析的主句谓语落在一个从句的标注里",
    "finiteness_mismatch": "标注的谓语 / 非谓语身份与句法分析不一致",
    "another_clause_same_type": "句中还有另一个同类从句，“划出句中的……从句”不止一个答案",
    "subordinator_unknown": "引导词不在已知列表里，无法核对关系类别",
    "subordinator_ambiguous": "引导词可以表示多种关系（如 as、since、while），关系需人工确认",
    "subordinator_mismatch": "引导词的常见关系与标注的关系不一致",
    "coordinate_cue_missing": "并列分句前没有 and / but / or 等连词，题干没法写明是哪一个",
    "coordinate_function_overlap": "这个并列分句同时属于一个从句，“并列分句”不是唯一答案",
    "nested_coordination": "并列分句目标本身又连着两个分句，边界不唯一",
    "possible_relative_adverb": "when / where / why 紧跟名词，可能是定语从句而不是状语从句",
    "noun_attached_clause": "状语从句被解析为修饰前面的名词，可能是定语从句",
    "prepositional_target": "目标可能是介词结构、复合连词或非限定结构，不一定是状语从句",
    "particle_outside_unit": "动词后的小品词（如 wrote down 的 down）没有并入动词单位",
    "participle_after_be": "be 后面的过去分词没有并入动词单位",
    "linking_verb_as_auxiliary": "become / remain 等系动词被当成了助动词，判分中心可能不对",
    "shared_auxiliary": "过去分词与前面带助动词的谓语并列、共用助动词，不一定是非谓语",
    "lexical_conjunction": "provided / given 等加 that 作连词用，不是动词",
    "hyphenated_word_split": "答案或干扰项切在连字符词中间（如 re-entered 的 re）",
    "multiple_independent_clauses": "冒号或分号两边各有一个完整分句，主句谓语 / 主语不唯一",
    "list_item": "句子是一个列表项",
}
HEADERS = (
    "序号",
    "题目编号",
    "题型",
    "篇章",
    "句子编号",
    "题干",
    "句子（【】标出目标）",
    "选项",
    "机器答案",
    "判分说明",
    "干扰项",
    "待复核原因",
    "原因码",
)
REVIEW_HEADERS = ("判定", "正确答案应为（选填）", "说明")
WIDTHS = (6, 21, 10, 26, 9, 34, 70, 24, 40, 24, 24, 48, 26, 14, 30, 36)


def review_row(index, item):
    sentence = item["source"]["sentence"]
    target, answer = item["target"], item["answer"]
    root = (item.get("grading") or {}).get("required_root")
    return (
        index,
        item["item_id"],
        SHEET_NAMES[item["template"]],
        item["source"]["passage_id"],
        item["source"]["sentence_id"],
        item["prompt_zh"],
        highlighted(sentence, target.get("parts") or [target]) if target else sentence,
        "\n".join(item["options"] or []),
        answer["option"] if answer["kind"] == "option" else highlighted(sentence, answer["spans"]),
        f"点出的词须包含 {root['text']}" if root else "",
        "\n".join(d["text"] for d in item.get("distractors") or []),
        "\n".join(REASONS_ZH.get(code, code) for code in item["reasons"]),
        ", ".join(item["reasons"]),
    )


def instruction_rows(label, count):
    rows = [
        (f"语法候选题待复核（{label}）", f"共 {count} 题，都是出题器没有把握、没有自动通过的题。"),
        ("怎么判", "逐题看题干、句子和机器答案，在“判定”列选一项；“待复核原因”是机器起疑的地方。"),
        ("正确", "题目清楚，机器答案对，可以直接用。"),
        ("答案错", "机器答案不对，请在“正确答案应为”里写出正确答案。"),
        ("题目有歧义", "不止一个合理答案，或者题干说不清。"),
        ("句子不适合出题", "原句残缺、太偏，或者和这个知识点无关。"),
        (
            "标记说明",
            "【】标出分类题的目标，或点选题、划边界题的机器答案；动词连同助动词、否定词一起标出。",
        ),
        ("主句谓语题", "学生点出动词；点出的词包含“判分说明”里的那个词就算对。"),
    ]
    return rows


def write_workbook(items, label, path):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.worksheet.datavalidation import DataValidation

    workbook = Workbook()
    intro = workbook.active
    intro.title = "说明"
    for row in instruction_rows(label, len(items)):
        intro.append(row)
    style_sheet(intro, (24, 105), header=False)
    intro["A1"].font = Font(name="Arial", size=15, bold=True, color="30445C")
    for template in TEMPLATES:
        sheet = workbook.create_sheet(SHEET_NAMES[template])
        sheet.append(HEADERS + REVIEW_HEADERS)
        rows = [item for item in items if item["template"] == template]
        for index, item in enumerate(rows, 1):
            sheet.append(review_row(index, item) + ("", "", ""))
        style_sheet(sheet, WIDTHS)
        validation = DataValidation(
            type="list", formula1='"' + ",".join(VERDICTS) + '"', allow_blank=True
        )
        sheet.add_data_validation(validation)
        if sheet.max_row >= 2:
            column = chr(ord("A") + len(HEADERS))
            validation.add(f"{column}2:{column}{sheet.max_row}")
    stable_xlsx(workbook, path)


def write_batches(items, name, directory):
    directory.mkdir(parents=True, exist_ok=True)
    for old in directory.glob(f"{name}_*.csv"):
        old.unlink()
    for start in range(0, len(items), BATCH_SIZE):
        path = directory / f"{name}_{start // BATCH_SIZE + 1:03d}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADERS)
            for index, item in enumerate(items[start : start + BATCH_SIZE], start + 1):
                writer.writerow(review_row(index, item))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--candidates", type=Path, default=ROOT / "output/grammar_items/candidates_v0_2.jsonl"
    )
    parser.add_argument("--out", type=Path, default=ROOT / "output/grammar_items/needs_review")
    args = parser.parse_args(argv)
    candidates = [json.loads(line) for line in args.candidates.open(encoding="utf-8")]
    order = {template: index for index, template in enumerate(TEMPLATES)}
    needs = sorted(
        (item for item in candidates if item["status"] == "needs_review"),
        key=lambda item: (
            order[item["template"]],
            item["source"]["passage_id"],
            item["source"]["sentence_id"],
            item["item_id"],
        ),
    )
    unknown = {code for item in needs for code in item["reasons"]} - set(REASONS_ZH)
    if unknown:
        raise SystemExit(f"Reason codes without a Chinese note: {sorted(unknown)}")
    for name, label, cambridge in SOURCES:
        items = [i for i in needs if i["source"]["passage_id"].startswith("ielts") == cambridge]
        write_workbook(items, label, args.out / f"needs_review_{name}.xlsx")
        write_batches(items, name, args.out / "batches")
        print(f"{label}: {len(items)} items")


if __name__ == "__main__":
    main()
