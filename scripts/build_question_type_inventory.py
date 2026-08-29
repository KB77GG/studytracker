#!/usr/bin/env python3
"""Build the reviewable IELTS question-type inventory and safety audit."""

from __future__ import annotations

import argparse
import html
import json
from datetime import UTC, datetime
from pathlib import Path

from services.question_type_practice import LibraryRoots, build_group_index, summarize_inventory

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--audio-root",
        type=Path,
        help="Directory containing Cambridge section MP3s (defaults to static/listening).",
    )
    parser.add_argument("--include-reading-jijing", action="store_true")
    parser.add_argument(
        "--json-output",
        type=Path,
        default=PROJECT_ROOT / "QUESTION_TYPE_INVENTORY.json",
    )
    parser.add_argument(
        "--html-output",
        type=Path,
        default=PROJECT_ROOT / "QUESTION_TYPE_AUDIT.html",
    )
    return parser.parse_args()


def _portable(inventory: dict) -> dict:
    result = json.loads(json.dumps(inventory, ensure_ascii=False))
    for row in result["groups"]:
        path = Path(row["source_file"])
        try:
            row["source_file"] = str(path.relative_to(PROJECT_ROOT))
        except ValueError:
            row["source_file"] = path.name
    result["generated_at"] = datetime.now(UTC).isoformat()
    result["scope"] = "Cambridge IELTS Listening and Reading source libraries"
    return result


def _pill(status: str) -> str:
    labels = {
        "publishable": "可发布",
        "manual_review": "需人工校验",
        "blocked": "阻断",
    }
    return f'<span class="pill {html.escape(status)}">{labels.get(status, status)}</span>'


def _audit_html(inventory: dict) -> str:
    summary = inventory["summary"]
    type_rows = "".join(
        "<tr>"
        f"<td>{html.escape(row['subject'])}</td>"
        f"<td>{html.escape(row['standard_type_display_label'])}<small>{html.escape(row['standard_type_label'])} · {html.escape(row['subtype'])}</small></td>"
        f"<td>{row['group_count']}</td><td>{row['question_count']}</td>"
        f"<td>{html.escape(row['renderer'])}</td>"
        f"<td>{'是' if row['supports_specialty_practice'] else '否'}</td>"
        f"<td>{row['blocked_group_count']}</td><td>{row['manual_review_group_count']}</td>"
        "</tr>"
        for row in inventory["types"]
    )
    group_rows = "".join(
        "<tr>"
        f"<td><code>{html.escape(row['question_group_id'])}</code></td>"
        f"<td>{html.escape(row['test_title'])}<small>{html.escape(row['unit_label'])} {row['unit_number']} · Q{html.escape(row['original_question_range'])}</small></td>"
        f"<td>{html.escape(row['standard_type_display_label'])}<small>{html.escape(row['standard_type_label'])} · {html.escape(row['subtype'])}</small></td>"
        f"<td>{row['question_count']}</td><td>{html.escape(row['renderer'])}</td>"
        f"<td>{_pill(row['safety_status'])}</td>"
        f"<td>{html.escape('；'.join(row['blockers'] + row['warnings']) or '—')}</td>"
        "</tr>"
        for row in inventory["groups"]
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>IELTS Question Type Audit</title>
<style>
:root{{--green:#277c78;--paper:#fffdf8;--line:#d8ddd9;--ink:#182321}}*{{box-sizing:border-box}}
body{{margin:0;background:#f4f5f1;color:var(--ink);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1500px;margin:auto;padding:28px}}h1{{margin:0 0 6px;font-size:28px}}h2{{margin-top:32px}}
.meta,small{{display:block;color:#64706d}}.stats{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:22px 0}}
.stat{{padding:18px;border:1px solid var(--line);border-radius:14px;background:var(--paper)}}.stat strong{{display:block;font-size:28px;color:var(--green)}}
.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:14px;background:white}}table{{width:100%;border-collapse:collapse;min-width:1050px}}
th,td{{padding:11px 12px;border-bottom:1px solid #e6eae7;text-align:left;vertical-align:top}}th{{position:sticky;top:0;background:#eef5f3;z-index:1}}
code{{font-size:12px}}.pill{{display:inline-flex;padding:3px 8px;border-radius:999px;font-weight:700;white-space:nowrap}}.publishable{{background:#dcfce7;color:#166534}}.manual_review{{background:#fef3c7;color:#92400e}}.blocked{{background:#fee2e2;color:#991b1b}}
@media(max-width:760px){{main{{padding:16px}}.stats{{grid-template-columns:1fr 1fr}}}}
</style></head><body><main>
<h1>IELTS 题型与发布安全审计</h1><p class="meta">生成时间 {html.escape(inventory["generated_at"])} · 最小单位为完整 Question Group</p>
<section class="stats"><div class="stat"><strong>{summary["group_count"]}</strong>题组</div><div class="stat"><strong>{summary["question_count"]}</strong>题目</div><div class="stat"><strong>{summary["publishable_group_count"]}</strong>可发布</div><div class="stat"><strong>{summary["blocked_group_count"]}</strong>阻断</div></section>
<p>“可发布”表示题型已确认且当前题面、答案、共享资源和 Section/Passage 关联通过自动门禁；“需人工校验”和“阻断”均不会进入默认发布候选。</p>
<h2>题型能力矩阵</h2><div class="table-wrap"><table><thead><tr><th>科目</th><th>标准题型 / 子类型</th><th>题组</th><th>题目</th><th>实际渲染器</th><th>专项支持</th><th>阻断</th><th>人工校验</th></tr></thead><tbody>{type_rows}</tbody></table></div>
<h2>逐题组安全清单</h2><div class="table-wrap"><table><thead><tr><th>questionGroupId</th><th>来源</th><th>题型</th><th>题数</th><th>渲染器</th><th>状态</th><th>原因</th></tr></thead><tbody>{group_rows}</tbody></table></div>
</main></body></html>"""


def main() -> int:
    args = _args()
    roots = LibraryRoots(
        listening=PROJECT_ROOT / "static/listening_tests",
        reading=PROJECT_ROOT / "static/reading_tests",
        reading_jijing=(
            (PROJECT_ROOT / "static/reading_jijing") if args.include_reading_jijing else None
        ),
        static=PROJECT_ROOT / "static",
        audio=args.audio_root,
    )
    inventory = _portable(summarize_inventory(build_group_index(roots)))
    args.json_output.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.html_output.write_text(_audit_html(inventory), encoding="utf-8")
    print(json.dumps(inventory["summary"], ensure_ascii=False))
    return 1 if inventory["summary"]["blocked_group_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
