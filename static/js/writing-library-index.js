(function () {
  'use strict';

  const root = document.querySelector('[data-writing-index]');
  if (!root) return;
  const cards = Array.from(root.querySelectorAll('[data-writing-card]'));
  const filterButtons = Array.from(root.querySelectorAll('[data-writing-filter]'));
  const search = document.getElementById('writingSearch');
  const count = document.getElementById('writingResultCount');
  const empty = document.getElementById('writingEmpty');
  let activeFilter = 'all';

  function applyFilters() {
    const query = String(search.value || '').trim().toLowerCase();
    let visible = 0;
    cards.forEach(function (card) {
      const filterMatch = activeFilter === 'all'
        || card.dataset.task === activeFilter
        || card.dataset.type === activeFilter;
      const searchMatch = !query || String(card.dataset.search || '').includes(query);
      card.hidden = !(filterMatch && searchMatch);
      if (!card.hidden) visible += 1;
    });
    count.textContent = '显示 ' + visible + ' 道题';
    empty.hidden = visible !== 0;
  }

  filterButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      activeFilter = button.dataset.writingFilter || 'all';
      filterButtons.forEach(function (candidate) {
        const isActive = candidate === button;
        candidate.classList.toggle('is-active', isActive);
        candidate.classList.toggle('is-selected', isActive);
        candidate.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      });
      applyFilters();
      const sidebar = document.getElementById('practice-catalog');
      const scrim = root.querySelector('[data-catalog-scrim]');
      if (window.innerWidth <= 860 && sidebar) {
        sidebar.classList.remove('is-open');
        if (scrim) scrim.hidden = true;
      }
    });
  });
  search.addEventListener('input', applyFilters);
})();
