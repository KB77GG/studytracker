(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root.document) api.mount(root);
}(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  function loadMessage(student) {
    if (!student || !student.enabled) return '';
    if (student.overloaded) {
      return `错词队列过载，超出今日安排 ${Number(student.overload_count) || 0} 题。建议减少本次新词量，先安排困难词讲解。`;
    }
    if (student.paused_count > 0) {
      return `有 ${Number(student.paused_count) || 0} 项暂停待讲解，请结合周清单安排新词量。`;
    }
    return '';
  }

  function createLoader(options) {
    let revision = 0;
    return async function refresh() {
      const current = ++revision;
      const name = options.name().trim();
      options.render('', null);
      if (!name) return;
      try {
        const response = await options.fetch(`/api/teacher/vocabulary-review/assignment-load?student_name=${encodeURIComponent(name)}`, {credentials: 'same-origin'});
        const payload = await response.json();
        if (current !== revision || name !== options.name().trim()) return;
        if (!response.ok || !payload.ok) {
          options.render('暂时无法核对该学生的复习负担，请确认学生档案和查看权限。', null);
          return;
        }
        const student = payload.student;
        options.render(payload.enabled ? loadMessage(student) : '', student);
      } catch (_) {
        if (current === revision && name === options.name().trim()) {
          options.render('复习负担暂时读取失败，可打开周清单查看。', null);
        }
      }
    };
  }

  function mount(win) {
    const input = win.document.getElementById('taskStudent');
    const box = win.document.getElementById('vocabularyAssignmentLoad');
    if (!input || !box) return;
    let timer;
    const refresh = createLoader({
      name: () => input.value,
      fetch: (...args) => win.fetch(...args),
      render(message, student) {
        box.replaceChildren();
        box.hidden = !message;
        if (!message) return;
        const text = win.document.createElement('span');
        text.textContent = message + ' ';
        const link = win.document.createElement('a');
        const id = Number(student && student.profile_id);
        link.href = Number.isSafeInteger(id) && id > 0
          ? `/teacher/vocabulary-review?profile_id=${id}` : '/teacher/vocabulary-review';
        link.textContent = '查看词汇周清单';
        box.append(text, link);
      }
    });
    const schedule = () => {
      win.clearTimeout(timer);
      timer = win.setTimeout(refresh, 250);
    };
    input.addEventListener('input', schedule);
    input.addEventListener('change', schedule);
    input.addEventListener('blur', schedule);
    win.refreshVocabularyAssignmentLoad = schedule;
    schedule();
  }

  return {loadMessage, createLoader, mount};
}));
