'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { templateRuntime } = require('./helpers/practice_template_runtime');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/listening/test_practice.html'), 'utf8');
const css = `${template.match(/<style>([\s\S]*?)<\/style>/)[1]}\n${fs.readFileSync(path.join(root, 'static/css/practice_shell.css'), 'utf8')}`;

// Evaluate width conditions, selector specificity and source order for the
// known selectors of these controls. This catches the old mobile override
// losing to [data-layout], which a mere declaration-presence assertion misses.
function rulesAtWidth(source, width) {
  const rules = [];
  const clean = source.replace(/\/\*[\s\S]*?\*\//g, '');
  let cursor = 0;
  while (cursor < clean.length) {
    const open = clean.indexOf('{', cursor);
    if (open < 0) break;
    const selector = clean.slice(cursor, open).trim();
    let close = open + 1, depth = 1;
    while (close < clean.length && depth) {
      if (clean[close] === '{') depth += 1;
      if (clean[close] === '}') depth -= 1;
      close += 1;
    }
    const body = clean.slice(open + 1, close - 1);
    if (selector.startsWith('@media')) {
      const conditions = [...selector.matchAll(/(min|max)-width:\s*(\d+)px/g)];
      if (conditions.length && conditions.every(([, kind, bound]) => kind === 'min' ? width >= +bound : width <= +bound)) {
        rules.push(...rulesAtWidth(body, width));
      }
    } else if (!selector.startsWith('@')) {
      const declarations = Object.fromEntries(body.split(';').filter(part => part.includes(':')).map(part => {
        const colon = part.indexOf(':');
        return [part.slice(0, colon).trim(), part.slice(colon + 1).trim()];
      }));
      selector.split(',').forEach(value => rules.push({ selector: value.trim(), declarations }));
    }
    cursor = close;
  }
  return rules;
}

function computed(width, matchingSelectors) {
  const values = {}, priorities = {};
  for (const rule of rulesAtWidth(css, width)) {
    if (!matchingSelectors.includes(rule.selector)) continue;
    const weight = (rule.selector.match(/#[\w-]+/g) || []).length * 100
      + (rule.selector.match(/\.[\w-]+|\[[^\]]+\]/g) || []).length * 10
      + (rule.selector.match(/(?:^|\s)(?:body|input|span)(?=[.#\s[]|$)/g) || []).length;
    for (const [property, value] of Object.entries(rule.declarations)) {
      if (weight >= (priorities[property] ?? -1)) {
        values[property] = value;
        priorities[property] = weight;
      }
    }
  }
  return values;
}

test('legacy paper-column forms become a full-width single column at narrow viewports', () => {
  for (const width of [390, 768, 980]) {
    assert.equal(computed(width, ['.practice-form', '.practice-form[data-layout="columns"]'])['grid-template-columns'], '1fr', `${width}px`);
  }
  assert.equal(computed(1280, ['.practice-form', '.practice-form[data-layout="columns"]'])['grid-template-columns'], 'repeat(2, minmax(0, 1fr))');
});

test('real Cambridge 18 form controls can shrink within their prompt without overflow', () => {
  const payload = JSON.parse(fs.readFileSync(path.join(root, 'static/listening_tests/ielts18_test1.json')));
  const html = templateRuntime('listening', payload).renderGroup(payload.sections[0].groups[0], 0);
  assert.equal((html.match(/class="answer-input answer-unit"/g) || []).length, 10);
  assert.equal((html.match(/class="inline-answer"/g) || []).length, 10);
  assert.equal(computed(390, ['.inline-answer', '.practice-form__content .inline-answer'])['max-width'], '100%');
  const input = computed(390, ['.answer-input', '.practice-form__content .answer-input', '.practice-form__content .inline-answer .answer-input']);
  assert.equal(input['min-width'], '0');
  assert.equal(input['max-width'], '100%');
});

test('compound listening blanks align vertically with their surrounding text', () => {
  const input = computed(1280, ['.answer-input', 'body.practice-listening-page [data-kind="text-parts"] .answer-input']);
  assert.equal(input['vertical-align'], 'middle');
  assert.equal(computed(1280, ['.inline-answer'])['vertical-align'], 'middle');
});
