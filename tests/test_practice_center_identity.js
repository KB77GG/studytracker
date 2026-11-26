'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const template = fs.readFileSync(path.join(__dirname, '../templates/practice/index_content.html'), 'utf8');
const script = template.match(/<script>\s*([\s\S]*?)<\/script>/)[1];

function storage() {
  const values = new Map();
  return {
    getItem: key => values.get(key) || null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key),
  };
}

function runtime({ identity = 'guest', serverIdentity = { ok: true, verified: false }, valid = true } = {}) {
  const nodes = new Map();
  const listeners = {};
  const windowListeners = {};
  const requests = [];
  function node(id) {
    if (!nodes.has(id)) nodes.set(id, {
      value: '', hidden: false, style: {}, dataset: {}, textContent: '', innerHTML: '', listeners: {},
      addEventListener(name, callback) { this.listeners[name] = callback; },
      focus() { this.focused = true; },
    });
    return nodes.get(id);
  }
  node('identity').dataset = { practiceStaffMode: identity === 'staff' ? '1' : '0' };
  const window = {
    PRACTICE_NAVIGATION_DEFAULTS: { identity_mode: identity, module_exit_url: '/login' },
    addEventListener(name, callback) { windowListeners[name] = callback; },
  };
  const context = {
    window, localStorage: storage(), sessionStorage: storage(),
    document: {
      getElementById: node,
      querySelector: selector => selector === '.practice-identity' ? node('identity') : null,
      querySelectorAll: () => [],
      addEventListener: (name, callback) => { listeners[name] = callback; },
    },
    PracticeTaskLists: require('../static/js/practice_task_lists.js'),
    fetch: async (url, options) => {
      requests.push({ url, options });
      const data = url === '/api/practice/identity' ? serverIdentity
        : url === '/api/listening/verify' ? (valid ? { ok: true, name: 'Synthetic Student' } : { ok: false, error: 'student_not_found' })
          : { ok: true, groups: {}, sessions: [] };
      return { ok: true, json: async () => data };
    },
  };
  vm.runInNewContext(script, context);
  return { ...context, node, listeners, windowListeners, requests };
}

const flush = () => new Promise(resolve => setImmediate(resolve));

test('successful name confirmation hides form, updates navigation, and switch restores guest', async () => {
  const env = runtime();
  env.node('practiceStudentName').value = 'Synthetic Student';
  env.node('practiceIdentityForm').listeners.submit({ preventDefault() {} });
  await flush();
  assert.equal(env.window.PRACTICE_NAVIGATION_DEFAULTS.identityMode, 'verified_student');
  assert.equal(env.node('practiceIdentityForm').hidden, true);
  assert.equal(env.node('practiceIdentitySwitch').hidden, false);
  assert.equal(env.localStorage.getItem('listening_student'), 'Synthetic Student');
  env.node('practiceIdentitySwitch').listeners.click();
  assert.equal(env.window.PRACTICE_NAVIGATION_DEFAULTS.identityMode, 'guest');
  assert.equal(env.window.PRACTICE_NAVIGATION_DEFAULTS.identity_mode, 'guest');
  assert.equal(env.node('practiceIdentityForm').hidden, false);
  assert.equal(env.node('practiceIdentitySwitch').hidden, true);
  assert.equal(env.localStorage.getItem('listening_student'), null);
});

test('restored server identity updates navigation before entering a resource', async () => {
  const env = runtime({ serverIdentity: { ok: true, verified: true, name: 'Synthetic Student' } });
  await env.listeners.DOMContentLoaded();
  assert.equal(env.window.PRACTICE_NAVIGATION_DEFAULTS.identityMode, 'verified_student');
  assert.equal(env.node('practiceIdentityForm').hidden, true);
});

test('cached return refreshes assigned tasks only while the student is verified', async () => {
  const env = runtime({ serverIdentity: { ok: true, verified: true, name: 'Synthetic Student' } });
  await env.listeners.DOMContentLoaded();
  await flush();
  const taskRequests = () => env.requests.filter(request => request.url === '/api/practice/tasks').length;
  const before = taskRequests();
  env.windowListeners.pageshow({ persisted: false });
  await flush();
  assert.equal(taskRequests(), before);
  env.windowListeners.pageshow({ persisted: true });
  await flush();
  assert.equal(taskRequests(), before + 1);
  env.node('practiceIdentitySwitch').listeners.click();
  env.windowListeners.pageshow({ persisted: true });
  await flush();
  assert.equal(taskRequests(), before + 1);
  assert.equal(env.window.PRACTICE_NAVIGATION_DEFAULTS.identityMode, 'guest');
});

test('account identity is preserved when the identity endpoint reports verified', async () => {
  const env = runtime({ identity: 'student_account', serverIdentity: { ok: true, verified: true, name: 'Synthetic Student' } });
  await env.listeners.DOMContentLoaded();
  assert.equal(env.window.PRACTICE_NAVIGATION_DEFAULTS.identity_mode, 'student_account');
  assert.equal(env.window.PRACTICE_NAVIGATION_DEFAULTS.identityMode, undefined);
});

test('staff bypass retains staff navigation and does not fetch student data', async () => {
  const env = runtime({ identity: 'staff' });
  await env.listeners.DOMContentLoaded();
  assert.equal(env.window.PRACTICE_NAVIGATION_DEFAULTS.identity_mode, 'staff');
  assert.equal(env.node('practiceIdentityForm').hidden, true);
  assert.equal(env.node('practiceIdentitySwitch').hidden, true);
  assert.equal(env.requests.length, 0);
});

test('failed confirmation keeps guest navigation and visible form', async () => {
  const env = runtime({ valid: false });
  env.node('practiceStudentName').value = 'Unknown';
  env.node('practiceIdentityForm').listeners.submit({ preventDefault() {} });
  await flush();
  assert.equal(env.window.PRACTICE_NAVIGATION_DEFAULTS.identityMode, 'guest');
  assert.equal(env.node('practiceIdentityForm').hidden, false);
  assert.equal(env.node('practiceIdentityError').textContent, '未找到该学生，请确认姓名。');
});
