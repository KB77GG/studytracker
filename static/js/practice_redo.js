(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.PracticeRedo = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  // A redo is a new local draft. Submitted attempts and notes stay untouched.
  function create(options) {
    const storage = options.storage || window.localStorage;
    const location = options.location || window.location;
    const context = options.practiceContext;
    const allowed = !options.examContext && !context?.read_only && context?.can_write !== false;
    const markerKey = `${options.storageKey}:redo:${options.taskId || 'free'}`;
    const button = options.button;
    let restarting = false;
    let busy = false;

    function updateButton() {
      if (!button) return;
      button.hidden = !allowed;
      button.disabled = !allowed || busy || restarting;
    }

    function skipRestore() {
      if (restarting) return true;
      if (!allowed || options.historyAttemptId) return false;
      try { return storage.getItem(markerKey) === '1'; }
      catch (_error) { return false; }
    }

    function restart() {
      if (!allowed || busy || restarting) return false;
      const confirm = options.confirm || window.confirm.bind(window);
      if (!confirm('重新做本次练习？当前填写的答案会清空，已提交的成绩、错因笔记和划线会保留。')) return false;
      restarting = true;
      updateButton();
      const changes = [[markerKey, '1'], [options.storageKey, '{}'], [options.flagStorageKey, '[]']];
      const previous = [];
      try {
        for (const [key, value] of changes) {
          previous.push([key, storage.getItem(key)]);
          storage.setItem(key, value);
        }
      } catch (_error) {
        for (const [key, value] of previous.reverse()) {
          try {
            if (value === null) storage.removeItem(key);
            else storage.setItem(key, value);
          } catch (_restoreError) { /* Keep the current page intact if storage is unavailable. */ }
        }
        restarting = false;
        updateButton();
        (options.alert || window.alert.bind(window))('无法保存重做状态，请检查浏览器存储后再试。当前页面的答案仍保留。');
        return false;
      }
      // Reload also resets feedback, filters, audio and the elapsed timer.
      const url = new URL(location.href);
      url.searchParams.delete('history_attempt');
      url.hash = '';
      location.replace(url.href);
      return true;
    }

    updateButton();
    button?.addEventListener('click', restart);
    return {
      restart,
      skipRestore,
      suppressDraftWrites: () => restarting || Boolean(options.historyAttemptId),
      setBusy(value) { busy = Boolean(value); updateButton(); },
      submitted() {
        try { storage.removeItem(markerKey); }
        catch (_error) { /* Retain the local draft if browser storage is unavailable. */ }
      }
    };
  }

  return { create };
}));
