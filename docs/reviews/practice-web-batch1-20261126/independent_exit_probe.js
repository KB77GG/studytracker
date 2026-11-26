// The nine cases run during the independent exit review, saved for reproduction.
// Only path resolution differs from the original `node -` invocation.
// Run from the repository root:
//   node docs/reviews/practice-web-batch1-20261126/independent_exit_probe.js
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../..');
const cloze = require(path.join(root, 'static/js/listening-cloze.js'));
const source = fs.readFileSync(path.join(root, 'templates/listening/player.html'), 'utf8');
const helpers = source.slice(
  source.indexOf('  function hasUnconfirmedFirstAttempt()'),
  source.indexOf('  practiceShellController = PracticeShell.init(')
);
const guardExpr = source.match(/confirmExit:\s*([\s\S]*?),\n\s*initialSaved:/)[1];
const beforeExpr = source.match(/beforeLeave:\s*([\s\S]*?),\n\s*save:/)[1];
const progress = {};
const context = {
  data: {}, taskReadOnly: false, errorSummaryDirty: false,
  pendingFirstAttempts: new Map(), firstAttemptGates: new Map(),
  dictationDrafts: new Map(), correctionSegments: new Set(),
  getActiveProgressMap: () => progress,
  getSegmentLocations: () => [{ globalIndex: 3, seg: { text: 'synthetic' } }],
  getPracticeText: s => s.text,
  getEffectiveProgress: (p, i) => p[i],
  dictationStateKey: i => String(i),
  practiceShellController: { setStatus() {} }
};
vm.createContext(context);
vm.runInContext(helpers, context);
const guard = vm.runInContext('(' + guardExpr + ')', context);
const before = vm.runInContext('(' + beforeExpr + ')', context);
const clean = { dirty: false, saving: false };
let count = 0;
function check(label, wantPrompt, wantLeave) {
  assert.equal(Boolean(guard(clean)), wantPrompt, label);
  assert.equal(before(), wantLeave, label);
  count++;
  console.log(label, JSON.stringify({ prompt: wantPrompt, canLeave: wantLeave }));
}
check('untouched', false, true);
context.dictationDrafts.set('3:challenge', ['some answer']);
check('typed-before-submit', true, true);
const gate = cloze.createFirstAttemptGate(false);
context.firstAttemptGates.set('3', gate);
gate.beginFirstAttempt();
check('first-submit-inflight', true, false);
context.pendingFirstAttempts.set('3', { answers: ['some answer'] });
check('first-submit-failed', true, false);
context.pendingFirstAttempts.clear();
progress[3] = { is_completed: true };
check('first-submit-success', false, true);
context.correctionSegments.add('3');
check('correction-draft', true, true);
context.pendingFirstAttempts.set('3', { answers: ['uncertain'] });
check('uncertain-response-before-refresh', true, false);
context.pendingFirstAttempts.clear();
context.firstAttemptGates.clear();
context.dictationDrafts.clear();
context.correctionSegments.clear();
check('refresh-server-confirms-save', false, true);
delete progress[3];
check('refresh-server-has-no-save-can-retry', false, true);
console.log('independent cases passed:', count);
