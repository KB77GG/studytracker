// Execute the actual old/new heading prompt functions against all source targets.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { execFileSync } = require('node:child_process');

const root = path.resolve(__dirname, '../../..');
const audit = JSON.parse(fs.readFileSync(path.join(__dirname, 'reading-stems.json'), 'utf8'));
const gitText = name => execFileSync('git', ['show', `${audit.baseline}:${name}`], { cwd: root, encoding: 'utf8' });
const sources = [gitText('templates/reading/test_practice.html'), fs.readFileSync(path.join(root, 'templates/reading/test_practice.html'), 'utf8')];
const counts = { correct: 0, wrong_paragraph: 0, blank_prompt: 0, current_verified: 0 };
const cache = new Map();
for (const row of audit.headings) {
  const relative = `static/reading_tests/${row.test}.json`;
  if (!cache.has(relative)) cache.set(relative, [JSON.parse(gitText(relative)), JSON.parse(fs.readFileSync(path.join(root, relative), 'utf8'))]);
  cache.get(relative).forEach((payload, version) => {
    const group = payload.passages.flatMap(passage => passage.groups).find(item => item.questions.some(question => question.number === row.number));
    const question = group.questions.find(item => item.number === row.number);
    const context = { testData: payload };
    vm.createContext(context);
    for (const name of ['passageForQuestion', 'groupInstruction', 'displayQuestionPrompt']) {
      const start = sources[version].indexOf(`function ${name}(`);
      const end = sources[version].indexOf('\nfunction ', start + 1);
      assert.ok(start >= 0 && end > start, name);
      vm.runInContext(sources[version].slice(start, end), context);
    }
    const rendered = context.displayQuestionPrompt(question, group);
    if (version === 0) {
      const target = rendered.match(/(?:Paragraph|Section) ([A-Z])/);
      counts[target ? target[1] === row.source_code ? 'correct' : 'wrong_paragraph' : 'blank_prompt'] += 1;
    } else {
      assert.equal(rendered, row.title, `${row.test}/Q${row.number}`);
      counts.current_verified += 1;
    }
  });
}
assert.equal(counts.current_verified, 200);
fs.writeFileSync(path.join(__dirname, 'reading-stems-render.json'), JSON.stringify(counts, null, 2) + '\n');
console.log(JSON.stringify(counts, null, 2));
