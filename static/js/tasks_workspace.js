/* Direction 2 task workspace behavior. The legacy task script owns the
   server-backed controls; this module only coordinates the new shell. */
(function () {
  'use strict';

  const strip = document.getElementById('taskDateStrip');
  const choices = document.getElementById('taskDateChoices');
  const rows = () => Array.from(document.querySelectorAll('#taskRows tr[data-id]'));
  if (!strip || !choices) return;

  const parseDate = value => {
    const parts = String(value || '').split('-').map(Number);
    if (parts.length !== 3 || parts.some(Number.isNaN)) return new Date();
    return new Date(parts[0], parts[1] - 1, parts[2]);
  };
  const isoDate = date => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };
  const weekDays = ['日', '一', '二', '三', '四', '五', '六'];
  let dateAnchor = parseDate(strip.dataset.endDate);
  let page = 1;

  function renderDates() {
    choices.replaceChildren();
    const dates = [];
    for (let offset = 6; offset >= 0; offset -= 1) {
      const date = new Date(dateAnchor);
      date.setDate(date.getDate() - offset);
      dates.push(date);
    }
    dates.forEach(date => {
      const value = isoDate(date);
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'task-date-choice';
      button.dataset.date = value;
      if (value === strip.dataset.endDate) button.classList.add('is-today');
      if (window.taskSelectedDate === value) button.classList.add('is-active');
      const weekday = document.createElement('small');
      weekday.textContent = `周${weekDays[date.getDay()]}`;
      const label = document.createElement('strong');
      label.textContent = `${date.getMonth() + 1}/${date.getDate()}`;
      button.append(weekday, label);
      button.addEventListener('click', () => {
        window.taskSelectedDate = window.taskSelectedDate === value ? '' : value;
        renderDates();
        window.applyTaskFilters?.();
      });
      choices.appendChild(button);
    });
  }

  function shiftDates(direction) {
    dateAnchor = new Date(dateAnchor);
    dateAnchor.setDate(dateAnchor.getDate() + (direction * 7));
    renderDates();
  }
  strip.querySelector('[data-date-shift="-1"]')?.addEventListener('click', () => shiftDates(-1));
  strip.querySelector('[data-date-shift="1"]')?.addEventListener('click', () => shiftDates(1));

  function renderPagination() {
    const allRows = rows();
    const filteredRows = allRows.filter(row => row.dataset.filterVisible !== 'false');
    const size = Math.max(1, Number(document.getElementById('taskPageSize')?.value || 10));
    const pageCount = Math.max(1, Math.ceil(filteredRows.length / size));
    page = Math.min(page, pageCount);
    const start = (page - 1) * size;
    allRows.forEach(row => {
      const index = filteredRows.indexOf(row);
      row.style.display = index >= start && index < start + size ? '' : 'none';
    });
    const count = document.getElementById('taskListCount');
    if (count) count.textContent = `显示 ${filteredRows.length} 条任务`;
    const previous = document.getElementById('taskPrevPage');
    const next = document.getElementById('taskNextPage');
    if (previous) previous.disabled = page <= 1;
    if (next) next.disabled = page >= pageCount;
    const numbers = document.getElementById('taskPageNumbers');
    if (numbers) {
      numbers.replaceChildren();
      for (let number = 1; number <= pageCount; number += 1) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = number === page ? 'is-active' : '';
        button.textContent = String(number);
        button.setAttribute('aria-label', `第 ${number} 页`);
        button.addEventListener('click', () => { page = number; renderPagination(); });
        numbers.appendChild(button);
      }
    }
  }
  window.taskWorkspaceApplyPagination = renderPagination;
  document.getElementById('taskPrevPage')?.addEventListener('click', () => { page -= 1; renderPagination(); });
  document.getElementById('taskNextPage')?.addEventListener('click', () => { page += 1; renderPagination(); });
  document.getElementById('taskPageSize')?.addEventListener('change', () => { page = 1; renderPagination(); });

  window.taskSelectedDate = '';
  renderDates();
  window.applyTaskFilters?.();
  renderPagination();

  window.addEventListener('resize', () => {
    if (!window.matchMedia('(max-width: 900px)').matches) document.body.classList.remove('task-inspector-mobile-open');
  });
})();
