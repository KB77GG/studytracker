const assert = require('node:assert/strict');
const scoring = require('../static/js/practice_scoring.js');

const options = 'ABCD'.split('').map((key) => ({ key }));

let result = scoring.gradeAnswer('B,C', 'B,D', {
  kind: 'checkbox-set',
  marks: 2,
  options,
});
assert.equal(result.awarded, 1);
assert.equal(result.status, 'partial');
assert.equal(result.status_label, '部分正确 1/2');
assert.equal(result.option_states.find((row) => row.key === 'B').status, 'selected_correct');
assert.equal(result.option_states.find((row) => row.key === 'C').status, 'missed_correct');
assert.equal(result.option_states.find((row) => row.key === 'D').status, 'selected_wrong');

result = scoring.gradeAnswer('B,C', 'B,C', { kind: 'checkbox-set', marks: 2, options });
assert.equal(result.awarded, 2);
assert.equal(result.status, 'correct');

result = scoring.gradeAnswer('B,C', 'A,B,C', { kind: 'checkbox-set', marks: 2, options });
assert.equal(result.awarded, 0);
assert.equal(result.selection_error, 'too_many');

result = scoring.gradeAnswer('B,C', 'B', { kind: 'checkbox-exact', marks: 1, options });
assert.equal(result.awarded, 0);
result = scoring.gradeAnswer('B,C', 'C,B', { kind: 'checkbox-exact', marks: 1, options });
assert.equal(result.awarded, 1);
result = scoring.gradeAnswer('B,C', 'A,B,C', { kind: 'checkbox-exact', marks: 1, options });
assert.equal(result.awarded, 0);

result = scoring.gradeAnswer('A/B', 'A', { kind: 'question', marks: 1, options });
assert.equal(result.awarded, 1);
result = scoring.gradeAnswer('A/B', 'B', { kind: 'question', marks: 1, options });
assert.equal(result.awarded, 1);

const readingPayload = {
  passages: [{
    groups: [{
      desc: 'Questions 10 and 11 Choose TWO letters.',
      collect_option: { list: 'ABCD'.split('').map((key) => ({ key, text: key })) },
      questions: [
        { id: 10, number: 10, answer: 'B,C' },
        { id: 11, number: 11, answer: 'B,C' },
      ],
    }],
  }],
};
const reading = scoring.gradeReadingTestAnswers(readingPayload, { 10: 'B', 11: 'D' });
assert.equal(reading.correct, 1);
assert.equal(reading.results[0].status, 'correct');
assert.equal(reading.results[1].status, 'incorrect');

console.log('practice scoring tests passed');
