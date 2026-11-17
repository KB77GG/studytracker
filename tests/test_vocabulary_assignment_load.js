const assert = require('node:assert/strict');
const {test} = require('node:test');
const {loadMessage, createLoader} = require('../static/js/vocabulary_assignment_load.js');

test('only enabled overload or paused queues produce task warnings', () => {
  assert.equal(loadMessage(null), '');
  assert.equal(loadMessage({enabled: false, overloaded: true}), '');
  assert.equal(loadMessage({enabled: true, overloaded: false}), '');
  assert.match(loadMessage({enabled: true, overloaded: true, overload_count: 5}), /5 题.*减少本次新词量/);
  assert.match(loadMessage({enabled: true, paused_count: 2}), /2 项暂停待讲解/);
});

test('late previous student response never replaces current student warning', async () => {
  let name = 'synthetic-one';
  const pending = [];
  const renders = [];
  const refresh = createLoader({
    name: () => name,
    fetch: (url, options) => {
      assert.equal(options.credentials, 'same-origin');
      return new Promise(resolve => pending.push({url, resolve}));
    },
    render: (...args) => renders.push(args),
  });
  const first = refresh();
  name = 'synthetic-two';
  const second = refresh();
  pending[1].resolve({ok: true, json: async () => ({ok: true, enabled: true, student: {profile_id: 2, enabled: true, paused_count: 2}})});
  await second;
  pending[0].resolve({ok: true, json: async () => ({ok: true, enabled: true, student: {profile_id: 1, enabled: true, paused_count: 99}})});
  await first;
  assert.equal(renders.at(-1)[1].profile_id, 2);
  assert.equal(renders.length, 3);
});

test('cleared selection and URL metacharacters are handled safely', async () => {
  let name = 'x&profile_id=999';
  let resolve;
  const renders = [];
  const refresh = createLoader({
    name: () => name,
    fetch: url => {
      assert.match(url, /student_name=x%26profile_id%3D999$/);
      return new Promise(r => { resolve = r; });
    },
    render: (...args) => renders.push(args),
  });
  const running = refresh();
  name = '';
  await refresh();
  resolve({ok: true, json: async () => ({ok: true, enabled: true, student: {enabled: true, paused_count: 5}})});
  await running;
  assert.deepEqual(renders, [['', null], ['', null]]);
});

test('authorization failure displays generic notice without server data', async () => {
  const renders = [];
  const refresh = createLoader({
    name: () => 'synthetic',
    fetch: async () => ({ok: false, json: async () => ({ok: false, student: {name: 'private'}})}),
    render: (...args) => renders.push(args),
  });
  await refresh();
  assert.match(renders.at(-1)[0], /无法核对/);
  assert.equal(renders.at(-1)[1], null);
});

test('network failure does not throw into task assignment flow', async () => {
  const renders = [];
  await createLoader({
    name: () => 'synthetic', fetch: async () => { throw new Error('network'); },
    render: (...args) => renders.push(args),
  })();
  assert.match(renders.at(-1)[0], /暂时读取失败/);
});

test('disabled server response clears warning', async () => {
  const renders = [];
  await createLoader({
    name: () => 'synthetic',
    fetch: async () => ({ok: true, json: async () => ({ok: true, enabled: false, student: null})}),
    render: (...args) => renders.push(args),
  })();
  assert.deepEqual(renders.at(-1), ['', null]);
});
