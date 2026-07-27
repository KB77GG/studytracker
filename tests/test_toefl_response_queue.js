const assert = require('node:assert/strict');
const test = require('node:test');

const { flushResponseSaves } = require('../static/js/toefl_response_queue.js');

test('flush propagates a failed in-flight save and returns its value for retry', async () => {
  const inFlight = Promise.reject(new Error('network down'));
  const result = await flushResponseSaves({
    inFlightEntries: [{ promise: inFlight, questionId: 'q1', value: 'draft' }],
    save: async () => undefined,
  });

  assert.equal(result.ok, false);
  assert.equal(result.results[0].reason.message, 'network down');
  assert.equal(result.retry.get('q1'), 'draft');
});

test('flush waits for pending and in-flight saves before allowing navigation', async () => {
  const events = [];
  let release;
  const inFlight = new Promise((resolve) => { release = resolve; });
  const flushing = flushResponseSaves({
    pendingEntries: [['q2', 'new value']],
    inFlightEntries: [{ promise: inFlight, questionId: 'q1', value: 'old value' }],
    save: async (questionId, value) => events.push(`${questionId}:${value}`),
  });

  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(events, ['q2:new value']);
  let settled = false;
  flushing.then(() => { settled = true; });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(settled, false);
  release();
  const result = await flushing;
  assert.equal(result.ok, true);
});
