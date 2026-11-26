(function (root) {
  'use strict';
  function findForty(groups, index = 0, sum = 0, chosen = []) {
    if (index === groups.length) return sum === 40 ? chosen : null;
    for (const item of groups[index]) {
      const count = Number(item.count);
      if (!Number.isInteger(count) || count <= 0 || sum + count > 40) continue;
      const result = findForty(groups, index + 1, sum + count, [...chosen, item.value]);
      if (result) return result;
    }
    return null;
  }
  function install(container) {
    const source = container.querySelector('[data-sprint-source]');
    const existing = container.querySelector('[data-existing-paper]');
    const panel = container.querySelector('[data-sprint-parts]');
    const parts = [...panel.querySelectorAll('[data-sprint-part]')];
    const status = panel.querySelector('[data-sprint-total]');
    function update() {
      const sprint = source.value === 'sprint';
      existing.hidden = sprint;
      existing.querySelector('select').disabled = sprint;
      panel.hidden = !sprint;
      parts.forEach(select => { select.disabled = !sprint; });
      const count = parts.reduce((sum, select) => sum + Number(select.selectedOptions[0]?.dataset.count || 0), 0);
      const complete = parts.length > 0 && parts.every(select => select.value);
      status.textContent = `已选 ${count} / 40 题${complete && count !== 40 ? '，请调整篇章至40题' : ''}`;
      if (parts.length) parts[0].setCustomValidity(sprint && complete && count !== 40 ? '模考需要40题，请调整篇章。' : '');
    }
    source.addEventListener('change', update);
    parts.forEach(select => select.addEventListener('change', update));
    panel.querySelector('[data-sprint-suggest]').addEventListener('click', () => {
      const choice = findForty(parts.map(select => [...select.options].filter(o => o.value).map(o => ({ value: o.value, count: o.dataset.count }))));
      if (!choice) { status.textContent = '当前可用题目无法组成40题，请选择已有整套题库。'; return; }
      parts.forEach((select, index) => { select.value = choice[index]; });
      update();
    });
    update();
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { findForty, install };
  if (root.document) root.document.querySelectorAll('[data-sprint-picker]').forEach(install);
})(typeof window !== 'undefined' ? window : globalThis);
