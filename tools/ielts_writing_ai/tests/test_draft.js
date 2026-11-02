// node --test tools/ielts_writing_ai/tests/test_draft.js
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const Draft = require(path.join(__dirname, '..', 'static', 'draft.js'));

function memoryStorage(initial) {
  const map = new Map(Object.entries(initial || {}));
  return {
    get length() { return map.size; },
    key(i) { return Array.from(map.keys())[i] ?? null; },
    getItem(k) { return map.has(k) ? map.get(k) : null; },
    setItem(k, v) { map.set(k, String(v)); },
    removeItem(k) { map.delete(k); },
    dump() { return Object.fromEntries(map); },
  };
}

const ESSAY = { task_type: 'task2', prompt_text: 'Some prompt here', essay_text: 'A private essay by A.', target_band: '7.0' };

test('a draft saved by A is never loaded by B in the same browser', () => {
  const storage = memoryStorage();
  Draft.create(storage, 'userA').save(ESSAY);
  assert.equal(Draft.create(storage, 'userB').load(), null);
  assert.deepEqual(Draft.create(storage, 'userA').load(), ESSAY);
});

test('the pre-fix global draft is purged and never restored', () => {
  const storage = memoryStorage({ 'iwa:new-draft': JSON.stringify(ESSAY) });
  Draft.purgeLegacy(storage);
  assert.equal(storage.getItem('iwa:new-draft'), null);
  assert.equal(Draft.create(storage, 'userB').load(), null);
});

test('when B signs in, drafts left by other accounts are removed', () => {
  const storage = memoryStorage();
  Draft.create(storage, 'userA').save(ESSAY);
  Draft.create(storage, 'userB').save({ ...ESSAY, essay_text: 'B essay' });
  Draft.purgeOthers(storage, 'userB');
  assert.deepEqual(Object.keys(storage.dump()), [Draft.PREFIX + 'userB']);
});

test('a record copied under another key is rejected by its owner field', () => {
  const storage = memoryStorage();
  Draft.create(storage, 'userA').save(ESSAY);
  storage.setItem(Draft.PREFIX + 'userB', storage.getItem(Draft.PREFIX + 'userA'));
  assert.equal(Draft.create(storage, 'userB').load(), null);
  assert.equal(storage.getItem(Draft.PREFIX + 'userB'), null);
});

test('signed-out pages cannot read or write drafts', () => {
  const storage = memoryStorage();
  const anonymous = Draft.create(storage, '');
  assert.equal(anonymous.save(ESSAY), false);
  assert.equal(anonymous.load(), null);
  assert.equal(storage.length, 0);
});

test('expired, corrupted and empty drafts are dropped', () => {
  let clock = 1000;
  const storage = memoryStorage();
  const store = Draft.create(storage, 'userA', () => clock);
  store.save(ESSAY);
  clock += Draft.MAX_AGE_MS + 1;
  assert.equal(store.load(), null);
  assert.equal(storage.length, 0);

  storage.setItem(Draft.PREFIX + 'userA', '{not json');
  assert.equal(store.load(), null);
  assert.equal(storage.length, 0);

  store.save(ESSAY);
  store.save({ task_type: 'task2', prompt_text: '  ', essay_text: '', target_band: '7.0' });
  assert.equal(storage.length, 0);
  assert.equal(store.hasContent(), false);
});

test('clear removes only the current user draft', () => {
  const storage = memoryStorage();
  Draft.create(storage, 'userA').save(ESSAY);
  Draft.create(storage, 'userB').save(ESSAY);
  Draft.create(storage, 'userA').clear();
  assert.deepEqual(Object.keys(storage.dump()), [Draft.PREFIX + 'userB']);
});

test('storage failures never throw', () => {
  const broken = {
    length: 0, key() { throw new Error('denied'); }, getItem() { throw new Error('denied'); },
    setItem() { throw new Error('quota'); }, removeItem() { throw new Error('denied'); },
  };
  const store = Draft.create(broken, 'userA');
  assert.equal(store.save(ESSAY), false);
  assert.equal(store.load(), null);
  Draft.purgeLegacy(broken);
  Draft.purgeOthers(broken, 'userA');
});
