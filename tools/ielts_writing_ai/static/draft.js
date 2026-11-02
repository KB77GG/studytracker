/* Per-user unsent-draft storage for the "新批改" form.
 *
 * Drafts live in localStorage under a key derived from an opaque per-user value
 * (data-user-key, an HMAC computed by the server), so another account in the same
 * browser can never load them. Each record also stores its owner and is ignored if
 * the owner does not match. The pre-fix global key is purged on every page load, and
 * drafts left by other accounts are purged when someone else signs in.
 *
 * UMD: window.IWADraft in the browser, module.exports under node (tests).
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.IWADraft = factory();
})(this, function () {
  'use strict';

  var PREFIX = 'iwa:draft:v2:';
  var LEGACY_KEYS = ['iwa:new-draft'];
  var MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000;
  var FIELDS = ['task_type', 'prompt_text', 'essay_text', 'target_band'];

  function safe(fn, fallback) {
    try { return fn(); } catch (e) { return fallback; }
  }

  function keys(storage) {
    return safe(function () {
      var out = [];
      for (var i = 0; i < storage.length; i++) out.push(storage.key(i));
      return out;
    }, []);
  }

  function purgeLegacy(storage) {
    LEGACY_KEYS.forEach(function (key) { safe(function () { storage.removeItem(key); }); });
  }

  function purgeOthers(storage, userKey) {
    keys(storage).forEach(function (key) {
      if (key && key.indexOf(PREFIX) === 0 && key !== PREFIX + userKey) {
        safe(function () { storage.removeItem(key); });
      }
    });
  }

  function isEmpty(data) {
    return !data || !String(data.prompt_text || '').trim() && !String(data.essay_text || '').trim();
  }

  function create(storage, userKey, now) {
    now = now || function () { return Date.now(); };
    var key = userKey ? PREFIX + userKey : null;

    function clear() {
      if (key) safe(function () { storage.removeItem(key); });
    }

    function load() {
      if (!key) return null;
      var record = safe(function () { return JSON.parse(storage.getItem(key) || 'null'); }, undefined);
      if (record === undefined) { clear(); return null; }
      if (!record) return null;
      if (record.owner !== userKey || typeof record.savedAt !== 'number' ||
          now() - record.savedAt > MAX_AGE_MS || !record.data) {
        clear();
        return null;
      }
      return record.data;
    }

    function save(data) {
      if (!key) return false;
      if (isEmpty(data)) { clear(); return true; }
      var clean = {};
      FIELDS.forEach(function (field) { clean[field] = data[field] === undefined ? '' : String(data[field]); });
      return safe(function () {
        storage.setItem(key, JSON.stringify({ owner: userKey, savedAt: now(), data: clean }));
        return true;
      }, false);
    }

    return { load: load, save: save, clear: clear, hasContent: function () { return !isEmpty(load()); } };
  }

  return { create: create, purgeLegacy: purgeLegacy, purgeOthers: purgeOthers, PREFIX: PREFIX, LEGACY_KEYS: LEGACY_KEYS, MAX_AGE_MS: MAX_AGE_MS };
});
