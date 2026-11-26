'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const { findForty } = require('../static/js/mock_sprint_picker.js');
test('suggestion respects part order and searches beyond hottest wrong total', () => {
  const result = findForty([[{value:'p1',count:13}], [{value:'wrong',count:14},{value:'p2',count:13}], [{value:'p3',count:14}]]);
  assert.deepEqual(result,['p1','p2','p3']);
});
test('incomplete or incompatible feed cannot suggest a fake complete paper', () => {
  assert.equal(findForty([[],[{value:'p2',count:40}]]),null);
  assert.equal(findForty([[{value:'p1',count:13}],[{value:'p2',count:13}],[{value:'p3',count:13}]]),null);
});
