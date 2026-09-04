(function () {
  'use strict';

  const root = document.querySelector('[data-mother-topics-index]');
  if (!root) return;
  const cards = Array.from(root.querySelectorAll('[data-mother-topic-card]'));
  const filterButtons = Array.from(root.querySelectorAll('[data-topic-filter]'));
  const search = document.getElementById('motherTopicSearch');
  const count = document.getElementById('motherTopicResultCount');
  const empty = document.getElementById('motherTopicEmpty');
  let activeFilter = 'all';

  function applyFilters() {
    const query = String(search ? search.value : '').trim().toLowerCase();
    let visible = 0;
    cards.forEach(function (card) {
      const familyMatch = activeFilter === 'all' || card.dataset.family === activeFilter;
      const searchMatch = !query || String(card.dataset.search || '').includes(query);
      card.hidden = !(familyMatch && searchMatch);
      if (!card.hidden) visible += 1;
    });
    if (count) count.textContent = '显示 ' + visible + ' 个母题';
    if (empty) empty.hidden = visible !== 0;
  }

  filterButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      activeFilter = button.dataset.topicFilter || 'all';
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

  if (search) search.addEventListener('input', applyFilters);
})();
