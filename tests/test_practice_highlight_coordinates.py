"""Check real practice renderers keep the source text coordinates used by highlights."""

import json
import re
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

from services.ielts_exam_payload import build_review_payload, build_simulation_payload

ROOT = Path(__file__).resolve().parents[1]


class SourceText(HTMLParser):
    """Extract source text with the production highlighter's explicit exclusions."""

    def __init__(self, selectors):
        super().__init__(convert_charrefs=True)
        self.selectors = selectors
        self.stack = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        excluded = tag in self.selectors or any("." + name in self.selectors for name in classes)
        if tag not in {"input", "br", "img", "hr", "meta", "link", "source", "wbr"}:
            self.stack.append((tag, excluded))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, data):
        if not any(excluded for _, excluded in self.stack):
            self.parts.append(data)


NODE_RENDER = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const { templateRuntime } = require('./tests/helpers/practice_template_runtime.js');
const results = [];
for (const entry of JSON.parse(fs.readFileSync(0, 'utf8'))) {
  const elements = {};
  const document = { getElementById(id) { return elements[id] ||= { innerHTML: '' }; } };
  const c = templateRuntime(entry.subject, entry.payload, {
    document, getNotes: () => ({}),
    isMockExamReview: entry.mode === 'mock-review',
    experienceCapabilities: { simulationMode: entry.mode === 'simulation', canShowCorrectness: entry.mode.includes('review') },
    resultMode: false, experienceMode: entry.mode,
    requestAnimationFrame() {}, setExperienceMode() {}, window: {}
  });
  const template = fs.readFileSync(`templates/${entry.subject}/test_practice.html`, 'utf8');
  const functionName = entry.subject === 'listening' ? 'renderSection' : 'renderPassage';
  const start = template.indexOf(`function ${functionName}(`);
  vm.runInContext(template.slice(start, template.indexOf('\n}', start) + 2), c);
  c.bindInputs = () => {};
  const units = entry.payload[entry.subject === 'listening' ? 'sections' : 'passages'];
  const roots = [];
  if (entry.subject === 'listening') roots.push(units.map((unit, i) => c.renderSection(unit, i)).join(''));
  else for (const unit of units) {
    c.renderPassage(unit);
    roots.push(elements.passagePanel.innerHTML, elements.questionPanel.innerHTML);
  }
  results.push({ name: entry.name, subject: entry.subject, mode: entry.mode, roots });
}
process.stdout.write(JSON.stringify(results));
"""


class PracticeHighlightCoordinateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "static/js/selection-highlight.js").read_text()
        match = re.search(r"var EXCLUDE_SELECTOR = \[(.*?)\]\.join\(','\);", source, re.S)
        cls.selectors = set(re.findall(r"'([^']+)'", match.group(1)))
        entries = []
        for subject in ("listening", "reading"):
            for path in sorted((ROOT / f"static/{subject}_tests").glob("ielts*_test*.json")):
                if not re.fullmatch(r"ielts\d+_test\d+(?:_reading)?\.json", path.name):
                    continue
                payload = json.loads(path.read_text())
                for mode, data in (
                    ("practice", payload),
                    ("review", payload),
                    ("simulation", build_simulation_payload(payload, subject)),
                    ("mock-review", build_review_payload(payload, subject)),
                ):
                    entries.append(dict(name=path.name, subject=subject, mode=mode, payload=data))
        result = subprocess.run(
            ["node", "-e", NODE_RENDER],
            input=json.dumps(entries),
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=True,
        )
        cls.rendered = {}
        for entry in json.loads(result.stdout):
            roots = []
            for markup in entry["roots"]:
                parser = SourceText(cls.selectors)
                parser.feed(markup)
                roots.append("".join(parser.parts))
            cls.rendered[entry["name"], entry["mode"]] = roots

    def assert_subject_coordinates(self, subject, before, after):
        names = sorted(
            name
            for name, mode in self.rendered
            if mode == before and ("_reading" in name) == (subject == "reading")
        )
        self.assertEqual(len(names), 72)
        for name in names:
            for index, (source, review) in enumerate(
                zip(self.rendered[name, before], self.rendered[name, after], strict=True)
            ):
                self.assertTrue(
                    source == review,
                    f"{name} root {index}: {before} ({len(source)} chars) != {after} ({len(review)} chars)",
                )

    def test_reading_submit_and_refresh_keep_source_coordinates(self):
        self.assert_subject_coordinates("reading", "practice", "review")

    def test_listening_review_render_keeps_source_coordinates(self):
        self.assert_subject_coordinates("listening", "practice", "review")

    def test_reading_original_mock_review_keeps_exam_source_coordinates(self):
        self.assert_subject_coordinates("reading", "simulation", "mock-review")

    def test_listening_original_mock_review_keeps_exam_source_coordinates(self):
        self.assert_subject_coordinates("listening", "simulation", "mock-review")


if __name__ == "__main__":
    unittest.main()
