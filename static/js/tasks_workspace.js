/* Direction 2 task workspace behavior. The legacy task script owns the
   server-backed controls; this module only coordinates the new shell. */
(function () {
  'use strict';

  const strip = document.getElementById('taskDateStrip');
  const choices = document.getElementById('taskDateChoices');

  function setupStudentFilterAutocomplete() {
    const input = document.getElementById('filterStudent');
    const listbox = document.getElementById('filterStudentSuggestions');
    const clearButton = document.getElementById('filterClear');
    const options = Array.isArray(window.taskStudentFilterOptions)
      ? window.taskStudentFilterOptions
      : [];
    if (!input || !listbox) return;

    const normalize = value => String(value || '').trim().toLowerCase();
    const optionMatches = (option, query) => normalize(option?.search || option?.name).includes(query);
    let matches = [];
    let activeIndex = -1;

    window.taskStudentFilterMatchesName = (studentName, query) => {
      const normalizedName = normalize(studentName);
      const normalizedQuery = normalize(query);
      if (!normalizedQuery) return true;
      if (normalizedName.includes(normalizedQuery)) return true;
      const option = options.find(item => normalize(item?.name) === normalizedName);
      return Boolean(option && optionMatches(option, normalizedQuery));
    };

    function setExpanded(expanded) {
      listbox.hidden = !expanded;
      input.setAttribute('aria-expanded', String(expanded));
      if (!expanded) {
        activeIndex = -1;
        input.removeAttribute('aria-activedescendant');
      }
    }

    function setActive(index) {
      const optionButtons = Array.from(listbox.querySelectorAll('[role="option"]'));
      if (!optionButtons.length) return;
      activeIndex = Math.max(0, Math.min(index, optionButtons.length - 1));
      optionButtons.forEach((button, buttonIndex) => {
        const selected = buttonIndex === activeIndex;
        button.classList.toggle('is-active', selected);
        button.setAttribute('aria-selected', String(selected));
      });
      const activeButton = optionButtons[activeIndex];
      input.setAttribute('aria-activedescendant', activeButton.id);
      activeButton.scrollIntoView({ block: 'nearest' });
    }

    function choose(option) {
      input.value = option.name;
      setExpanded(false);
      window.applyTaskFilters?.();
      input.blur();
    }

    function render() {
      const query = normalize(input.value);
      listbox.replaceChildren();
      activeIndex = -1;
      input.removeAttribute('aria-activedescendant');
      if (!query) {
        matches = [];
        setExpanded(false);
        return;
      }

      matches = options.filter(option => optionMatches(option, query)).slice(0, 12);
      if (!matches.length) {
        const empty = document.createElement('div');
        empty.className = 'filter-student-suggestion-empty';
        empty.textContent = '没有匹配的学生';
        listbox.appendChild(empty);
        setExpanded(true);
        return;
      }

      matches.forEach((option, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.id = `filter-student-option-${index}`;
        button.className = 'student-suggestion filter-student-suggestion';
        button.setAttribute('role', 'option');
        button.setAttribute('aria-selected', 'false');

        const name = document.createElement('span');
        name.textContent = option.name;
        const hint = document.createElement('small');
        hint.textContent = '选择筛选';
        button.append(name, hint);
        button.addEventListener('mousedown', event => event.preventDefault());
        button.addEventListener('click', event => {
          event.preventDefault();
          choose(option);
        });
        listbox.appendChild(button);
      });
      setExpanded(true);
    }

    input.addEventListener('input', render);
    input.addEventListener('focus', () => {
      if (normalize(input.value)) render();
    });
    input.addEventListener('blur', () => window.setTimeout(() => setExpanded(false), 120));
    input.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        setExpanded(false);
        return;
      }
      if (!['ArrowDown', 'ArrowUp', 'Enter'].includes(event.key)) return;
      if (listbox.hidden) render();
      if (!matches.length) return;
      if (event.key === 'Enter') {
        if (activeIndex >= 0) {
          event.preventDefault();
          choose(matches[activeIndex]);
        }
        return;
      }
      event.preventDefault();
      const delta = event.key === 'ArrowDown' ? 1 : -1;
      const nextIndex = activeIndex < 0
        ? (delta > 0 ? 0 : matches.length - 1)
        : (activeIndex + delta + matches.length) % matches.length;
      setActive(nextIndex);
    });
    clearButton?.addEventListener('click', () => setExpanded(false));
  }

  setupStudentFilterAutocomplete();
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
  window.taskSelectedDate = strip.dataset.selectedDate || '';

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
        const dueDate = document.getElementById('filterDueDate');
        if (dueDate) dueDate.value = window.taskSelectedDate;
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

  window.taskWorkspaceRevealRow = targetRow => {
    if (!targetRow) return;
    targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };
  document.getElementById('taskPageSize')?.addEventListener('change', event => {
    const targetUrl = event.target.selectedOptions[0]?.dataset.url;
    if (targetUrl) window.location.assign(targetUrl);
  });

  renderDates();

  window.addEventListener('resize', () => {
    if (!window.matchMedia('(max-width: 900px)').matches) document.body.classList.remove('task-inspector-mobile-open');
  });
})();
