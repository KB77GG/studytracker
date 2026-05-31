/* Shared helpers for StudyTracker admin UI v2 pages.
   The file avoids dependencies and can be used alongside Bootstrap/jQuery. */

(function (window) {
  'use strict';

  const toneByType = {
    grammar: 'info',
    translation: 'primary',
    reading_vocab_choice: 'warning',
    ielts_reading_practice: 'info',
    speaking: 'warning',
    speaking_part1: 'warning',
    speaking_part2_3: 'warning',
    speaking_reading: 'warning',
    writing: 'neutral',
    pending: 'warning',
    progress: 'primary',
    submitted: 'info',
    done: 'success',
    completed: 'success',
    rejected: 'danger'
  };

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, function (char) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[char];
    });
  }

  function formatDate(value) {
    if (!value) return '-';
    return escapeHtml(String(value).split('T')[0]);
  }

  function debounce(fn, delay) {
    let timer = null;
    return function debounced(...args) {
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        fn.apply(this, args);
      }.bind(this), delay);
    };
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function badge(label, tone) {
    const safeTone = tone || toneByType[String(label || '').toLowerCase()] || 'neutral';
    return `<span class="admin-v2-badge admin-v2-badge--${escapeHtml(safeTone)}">${escapeHtml(label || '-')}</span>`;
  }

  function titleCell(title, description) {
    return `
      <div class="admin-v2-title">${escapeHtml(title || '-')}</div>
      <div class="admin-v2-description">${escapeHtml(description || '暂无说明')}</div>
    `;
  }

  function rowAction(label, options) {
    const opts = options || {};
    const toneClass = opts.tone === 'primary'
      ? ' admin-v2-row-action--primary'
      : opts.tone === 'danger'
        ? ' admin-v2-row-action--danger'
        : '';
    const icon = opts.icon ? `<i class="${escapeHtml(opts.icon)}"></i>` : '';
    const attrs = opts.attrs ? ` ${opts.attrs}` : '';
    return `<button type="button" class="admin-v2-row-action${toneClass}"${attrs}>${icon}${escapeHtml(label)}</button>`;
  }

  function table(headers, rows) {
    const th = headers.map(function (header) {
      const width = header.width ? ` style="width: ${escapeHtml(header.width)};"` : '';
      return `<th${width}>${escapeHtml(header.label)}</th>`;
    }).join('');

    const body = rows.map(function (cells) {
      return `<tr>${cells.map(function (cell) { return `<td>${cell}</td>`; }).join('')}</tr>`;
    }).join('');

    return `
      <div class="admin-v2-table-wrap">
        <table class="admin-v2-table">
          <thead><tr>${th}</tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    `;
  }

  function empty(title, desc, iconClass) {
    return `
      <div class="admin-v2-empty">
        <div><i class="${escapeHtml(iconClass || 'fas fa-inbox')}"></i></div>
        <h3>${escapeHtml(title)}</h3>
        ${desc ? `<p>${escapeHtml(desc)}</p>` : ''}
      </div>
    `;
  }

  function loading(label) {
    return `
      <div class="admin-v2-loading">
        <span class="spinner-border spinner-border-sm"></span>${escapeHtml(label || '加载中')}
      </div>
    `;
  }

  function error(message) {
    return `<div class="admin-v2-error">${escapeHtml(message || '加载失败')}</div>`;
  }

  async function fetchJson(url, options) {
    const response = await window.fetch(url, Object.assign({ credentials: 'include' }, options || {}));
    const data = await response.json();
    if (!data.ok) {
      throw new Error(data.message || data.error || '未知错误');
    }
    return data;
  }

  window.AdminUIV2 = {
    badge,
    debounce,
    empty,
    error,
    escapeHtml,
    fetchJson,
    formatDate,
    loading,
    rowAction,
    setText,
    table,
    titleCell,
    toneByType
  };
})(window);
