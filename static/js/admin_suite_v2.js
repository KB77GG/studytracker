(function () {
  'use strict';

  function text(value) {
    return String(value || '').trim().toLocaleLowerCase('zh-CN');
  }

  function filterCurrentPage(input) {
    const query = text(input.value);
    const scope = document.querySelector('.panel-content');
    if (!scope) return;

    const explicitRows = Array.from(scope.querySelectorAll('[data-suite-search-row]'));
    const rows = explicitRows.length
      ? explicitRows
      : Array.from(scope.querySelectorAll('tbody tr, .practice-resource, .practice-task-row'));

    rows.forEach(function (row) {
      const visible = !query || text(row.getAttribute('data-suite-search') || row.textContent).includes(query);
      row.hidden = !visible;
    });

    document.dispatchEvent(new CustomEvent('admin-suite:search', { detail: { query: query } }));
  }

  document.addEventListener('DOMContentLoaded', function () {
    const search = document.getElementById('suiteGlobalSearch');
    if (search) {
      search.addEventListener('input', function () { filterCurrentPage(search); });
      document.addEventListener('keydown', function (event) {
        if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
          event.preventDefault();
          search.focus();
          search.select();
        }
      });
    }

    document.querySelectorAll('[data-suite-tab-target]').forEach(function (tab) {
      tab.addEventListener('click', function () {
        const group = tab.closest('[data-suite-tabs]');
        if (!group) return;
        const target = tab.getAttribute('data-suite-tab-target');
        group.querySelectorAll('[data-suite-tab-target]').forEach(function (item) {
          item.classList.toggle('is-active', item === tab);
          item.setAttribute('aria-selected', item === tab ? 'true' : 'false');
        });
        document.querySelectorAll('[data-suite-tab-panel]').forEach(function (panel) {
          panel.hidden = panel.getAttribute('data-suite-tab-panel') !== target;
        });
      });
    });
  });
})();
