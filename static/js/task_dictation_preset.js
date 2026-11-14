/* Preselect an existing word book; the teacher still chooses and submits the task. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    const apply = factory();
    const run = () => apply(root);
    if (root.document.readyState === 'loading') {
      root.document.addEventListener('DOMContentLoaded', run, { once: true });
    } else {
      run();
    }
  }
}(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  function showError(document, message) {
    let notice = document.getElementById('taskDictationPresetNotice');
    if (!notice) {
      notice = document.createElement('p');
      notice.id = 'taskDictationPresetNotice';
      notice.className = 'assignment-duplicate-status is-error';
      notice.setAttribute('role', 'alert');
      const form = document.getElementById('taskForm');
      if (form) form.before(notice);
      else document.body.prepend(notice);
    }
    notice.textContent = message;
    notice.scrollIntoView({ block: 'center' });
    return false;
  }

  return function applyDictationPreset(window) {
    const document = window.document;
    const params = new URLSearchParams(window.location.search);
    if (!params.has('preset_dictation_book')) return false;
    const ids = params.getAll('preset_dictation_book');
    const bookId = ids[0];
    if (ids.length !== 1 || !/^[1-9]\d*$/.test(bookId)) {
      return showError(document, '词表链接无效，请返回材料库重新选择词表。');
    }
    const select = document.getElementById('material_id');
    const option = select && Array.from(select.options).find(
      item => item.value === `dictation-${bookId}` && !item.disabled
    );
    if (!option) {
      return showError(document, '该词表不存在或已停用，请返回材料库重新选择。');
    }
    const radio = document.querySelector('input[name="task_source"][value="material"]');
    const goal = document.getElementById('vocabularyGoalSelect');
    const openButton = document.getElementById('openTaskAssignment');
    if (!radio || !goal || !openButton) {
      return showError(document, '词表预选失败，请刷新页面后重试。');
    }

    // Use the page's real change handlers: source visibility, book-specific
    // defaults, range hints and duplicate-history checks stay in one place.
    select.value = '';
    goal.dataset.autofill = '1';
    radio.checked = true;
    radio.dispatchEvent(new window.Event('change', { bubbles: true }));
    select.value = option.value;
    select.dispatchEvent(new window.Event('change', { bubbles: true }));
    openButton.click();
    return true;
  };
}));
