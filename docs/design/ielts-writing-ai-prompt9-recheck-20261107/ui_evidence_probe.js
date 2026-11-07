#!/usr/bin/env node
'use strict';
// DOM test double, not a real browser. Input: JSON cases emitted by companion Python.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
let repo = '/private/tmp/studytracker-iwa-realcheck-review-20261103';
for (let i = 2; i < process.argv.length; i++) {
  if (process.argv[i] !== '--repo' || !process.argv[i + 1]) throw new Error('Expected --repo PATH');
  repo = process.argv[++i];
}
const source = fs.readFileSync(path.join(repo, 'tools/ielts_writing_ai/static/iwa.js'), 'utf8');
function piece(start, end) {
  const a = source.indexOf(start), b = source.indexOf(end, a);
  if (a < 0 || b < 0) throw new Error('Source extraction marker missing: ' + start);
  return source.slice(a, b);
}
const code = [
  piece('  function el(', '  function clear('),
  piece('  function copyText(', '  function countWords('),
  piece('  function band(', '  function paragraphs('),
  piece('    function regenButton(', '    function provenance('),
  piece('    function copyButton(', '    function quoteButton('),
  piece('    function quoteButton(', '    var REMOVED_NOTE'),
  piece('    function verified(', '    function argumentNode('),
  piece('    function renderEvaluation(', '    // -- refine'),
].join('\n');
function escapeText(value) {
  return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
}
class NodeDouble {
  constructor(tag = null, text = '') { this.tag = tag; this.children = []; this.attrs = {}; this.events = {}; this.value = text; }
  set textContent(value) { this.children = []; this.value = String(value); }
  get textContent() { return this.value + this.children.map(c => c.textContent).join(''); }
  set innerHTML(_) { throw new Error('HTML parsing sink used'); }
  set className(value) { this.attrs.class = value; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  addEventListener(event, handler) { this.events[event] = handler; }
  appendChild(child) { if (!(child instanceof NodeDouble)) throw new Error('Invalid node'); this.children.push(child); return child; }
  toHTML() {
    if (!this.tag) return escapeText(this.value);
    const attrs = Object.entries(this.attrs).map(([k, v]) => ` ${k}="${escapeText(v)}"`).join('');
    return `<${this.tag}${attrs}>${escapeText(this.value)}${this.children.map(n => n.toHTML()).join('')}</${this.tag}>`;
  }
}
function descendants(node) { return [node, ...node.children.flatMap(descendants)]; }
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const checks = [], cases = [];
function check(name, label, ok) { checks.push({ case: name, check: label, ok: Boolean(ok) }); }
for (const fixture of input.cases) {
  const clipboard = [];
  const document = { createElement: tag => new NodeDouble(tag), createTextNode: text => new NodeDouble(null, String(text)) };
  const context = { document, navigator: { clipboard: { writeText(text) { clipboard.push(text); return { then(done) { done(); } }; } } },
                    window: { isSecureContext: true }, toast() {}, state: {},
                    REMOVED_NOTE: 'probe-unused', regenerate() { throw new Error('Unexpected regeneration'); } };
  vm.createContext(context);
  vm.runInContext(code, context, { filename: 'iwa.js extracted original function bodies' });
  const panel = new NodeDouble('section');
  context.renderEvaluation(panel, fixture.generation);
  const all = descendants(panel);
  const contrasts = all.filter(n => n.tag === 'p' && n.attrs.class === 'argument__conflict');
  const contrast = contrasts[0];
  const buttons = contrast ? contrast.children.filter(n => n.tag === 'button') : [];
  const shown = buttons.map(n => n.textContent);
  const suffix = fixture.expected_omitted ? `（另有 ${fixture.expected_omitted} 个数字未列出）` : '';
  check(fixture.name, 'dom_exact_figure_buttons_order', JSON.stringify(shown) === JSON.stringify(fixture.expected_figures.map(f => '“' + f + '”')));
  check(fixture.name, 'dom_contrast_present_iff_has_evidence', contrasts.length === (fixture.expected_figures.length ? 1 : 0));
  check(fixture.name, 'dom_omission_count_and_position', !contrast || contrast.textContent === '对照：' + shown.join('') + suffix);
  check(fixture.name, 'dom_omission_notice_iff_truncated', panel.textContent.includes('未列出') === Boolean(fixture.expected_omitted));
  check(fixture.name, 'dom_comment_retained', !fixture.expected_figures.length || panel.textContent.includes(fixture.expected_comment));
  check(fixture.name, 'dom_no_markup_nodes_from_data', all.every(n => !['img', 'script'].includes(n.tag)) && all.filter(n => n.tag === 'b').length === fixture.generation.result.criteria.length);
  const copyButton = all.find(n => n.tag === 'button' && n.textContent === '复制评价');
  copyButton.events.click();
  check(fixture.name, 'copy_click_passes_exact_server_copy', clipboard.length === 1 && clipboard[0] === fixture.generation.copy.evaluation);
  if (fixture.name === 'html_as_text') {
    check(fixture.name, 'dom_figure_html_kept_literal', shown[0].includes('<img src=x onerror="alert(1)">'));
    check(fixture.name, 'dom_serialization_escapes_figure_html', panel.toHTML().includes('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;'));
    check(fixture.name, 'plain_copy_keeps_literal_markup', clipboard[0].includes('<img src=x onerror="alert(1)">'));
  }
  cases.push({ name: fixture.name, figure_button_count: buttons.length, contrast_text: contrast ? contrast.textContent : null,
               contrast_html_from_dom_double: contrast ? contrast.toHTML() : null, copied_server_text_exact: clipboard[0] === fixture.generation.copy.evaluation });
}
console.log(JSON.stringify({ cases, checks }));
