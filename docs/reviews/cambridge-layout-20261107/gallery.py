"""Loopback-only geometry gallery using real listening rendering; no app/DB.

Run with the project's Python environment, then open /layout-corpus.
Each GET reloads source CSS, JSON and Node renderer code; nothing is persisted.
"""

import argparse
import html
import importlib.util
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PREVIEW = ROOT / "docs/reviews/cambridge-fix-20261107/preview.py"
spec = importlib.util.spec_from_file_location("cambridge_layout_preview", PREVIEW)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)
app = preview.app

from flask import Response  # noqa: E402

NODE_SOURCE = r"""
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const root = process.cwd();
const { templateRuntime } = require(path.join(root, 'tests/helpers/practice_template_runtime.js'));
const R = require(path.join(root, 'static/js/practice_renderers.js'));
const cases = [];
const files = fs.readdirSync(path.join(root, 'static/listening_tests'))
  .filter(file => /^ielts\d+_test\d+\.json$/.test(file))
  .sort((a, b) => a.localeCompare(b, 'en', { numeric: true }));
for (const file of files) {
  const payload = JSON.parse(fs.readFileSync(path.join(root, 'static/listening_tests', file), 'utf8'));
  const runtime = templateRuntime('listening', payload);
  payload.sections.forEach((section, sectionIndex) => (section.groups || []).forEach((group, groupIndex) => {
    if (!R.isFormGroup(group)) return;
    const numbers = group.questions.map(question => question.number);
    cases.push({
      key: `${payload.id}:s${sectionIndex + 1}:g${groupIndex + 1}`,
      test: payload.id, section: sectionIndex + 1, group: groupIndex + 1,
      numbers, html: runtime.renderGroup(group, sectionIndex)
    });
  }));
}
process.stdout.write(JSON.stringify({ test_count: files.length, cases }));
"""


@app.get("/layout-corpus")
def layout_corpus():
    rendered = subprocess.run(
        ["node", "-"], input=NODE_SOURCE, cwd=ROOT,
        text=True, capture_output=True, check=True, timeout=30,
    )
    corpus = json.loads(rendered.stdout)
    template = (ROOT / "templates/listening/test_practice.html").read_text(encoding="utf-8")
    template_css = re.search(r"<style>(.*?)</style>", template, re.DOTALL).group(1)
    shell_css = (ROOT / "static/css/practice_shell.css").read_text(encoding="utf-8")
    cases = []
    for case in corpus["cases"]:
        key = html.escape(case["key"], quote=True)
        test_id = html.escape(case["test"], quote=True)
        question_range = f'{min(case["numbers"])}–{max(case["numbers"])}'
        cases.append(
            f'<section class="layout-audit-case" data-audit-case="{key}" '
            f'data-audit-test="{test_id}" data-audit-section="{case["section"]}" '
            f'data-audit-group="{case["group"]}" data-audit-questions="{question_range}">'
            f'<h2 class="layout-audit-label">{key} · Q{question_range}</h2>'
            f'{case["html"]}</section>'
        )
    document = (
        '<!doctype html><html lang="zh"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Cambridge listening form layout audit</title>'
        f'<style>{template_css}\n{shell_css}</style>'
        '<style>.layout-audit-label { font-size: 14px; margin: 20px 0 8px; color: #64748b; }</style>'
        '</head><body class="practice-shell-page practice-listening-page">'
        f'<main class="page" data-audit-cases="{len(cases)}" data-audit-tests="{corpus["test_count"]}">'
        '<p>本机排版检查：真实题库与渲染函数；无提交、计时或保存。</p>'
        '<div class="view-panel active" id="practiceView"><div class="layout">'
        '<div id="sectionsRoot" data-hl-root="listening-questions">'
        + "".join(cases)
        + '</div></div></div></main></body></html>'
    )
    return Response(document, mimetype="text/html", headers={
        "Cache-Control": "no-store",
        "Content-Security-Policy": (
            "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; "
            "form-action 'none'; base-uri 'none'"
        ),
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5099)
    args = parser.parse_args()
    app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
