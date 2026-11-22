// 任务列表：显示学生作答过程（每题作答时刻、离开页面）与异常提示。
// 数据来自 /api/staff/answer-integrity/*，只读；提示仅供老师参考，不改变成绩。
(function () {
  'use strict';

  const SUMMARY_BATCH = 200;
  const MODE_LABELS = { practice: '正常作答', redo_wrong: '错题重做', redo_all: '全部重做' };
  const BADGE_TEXT = { high: '高度可疑', medium: '需关注' };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function fmtClock(seconds) {
    const value = Math.max(0, Math.round(Number(seconds) || 0));
    const minutes = Math.floor(value / 60);
    return `${minutes}:${String(value % 60).padStart(2, '0')}`;
  }

  function fmtSubmitted(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
  }

  const summaryCache = new Map();

  function attachBadge(row) {
    const item = summaryCache.get(row.dataset.id);
    const cell = row.querySelector('td.task-time');
    if (!item || !cell || cell.querySelector('.answer-integrity-badge')) return;
    cell.appendChild(badgeFor(row.dataset.id, item));
  }

  function taskRows() {
    return Array.from(document.querySelectorAll('tr[data-id]')).filter(row => row.querySelector('td.task-time'));
  }

  function badgeFor(taskId, item) {
    const level = item.level || 'none';
    const text = BADGE_TEXT[level] || (item.has_timeline ? '作答过程' : '无过程记录');
    const button = el('button', `answer-integrity-badge is-${level}${item.has_timeline ? '' : ' is-missing'}`, text);
    button.type = 'button';
    button.title = '查看本次作业的作答过程';
    button.addEventListener('click', () => openModal(taskId));
    return button;
  }

  async function loadBadges() {
    const rows = taskRows();
    if (!rows.length) return;
    const ids = rows.map(row => row.dataset.id).filter(id => /^\d+$/.test(id || ''));
    for (let start = 0; start < ids.length; start += SUMMARY_BATCH) {
      const batch = ids.slice(start, start + SUMMARY_BATCH);
      let payload;
      try {
        const response = await fetch(`/api/staff/answer-integrity/summary?task_ids=${batch.join(',')}`, {
          headers: { Accept: 'application/json' },
        });
        payload = await response.json();
        if (!response.ok || !payload.ok) continue;
      } catch (error) {
        console.warn('answer integrity summary failed', error);
        continue;
      }
      Object.entries(payload.items || {}).forEach(([taskId, item]) => summaryCache.set(taskId, item));
      rows.forEach(attachBadge);
    }
    watchRows(rows);
  }

  // Editing a task rewrites the whole time cell (textContent), which drops the
  // badge; put it back from the cache instead of touching that legacy code.
  function watchRows(rows) {
    if (!summaryCache.size || typeof MutationObserver === 'undefined') return;
    const observer = new MutationObserver(mutations => {
      mutations.forEach(mutation => {
        const row = mutation.target.closest && mutation.target.closest('tr[data-id]');
        if (row) attachBadge(row);
      });
    });
    rows.forEach(row => {
      const cell = row.querySelector('td.task-time');
      if (cell && summaryCache.has(row.dataset.id)) observer.observe(cell, { childList: true });
    });
  }

  // ---- modal ----

  let modal = null;
  let requestSeq = 0;

  function ensureModal() {
    if (modal) return modal;
    modal = el('div', 'modal hidden answer-integrity-modal');
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    const backdrop = el('div', 'backdrop');
    const card = el('div', 'card');
    const header = el('div', 'attempt-history-modal__header');
    const titles = el('div');
    titles.appendChild(el('h3', '', '作答过程'));
    const subtitle = el('p', 'attempt-history-modal__subtitle', '');
    titles.appendChild(subtitle);
    const close = el('button', 'attempt-history-modal__close', '关闭');
    close.type = 'button';
    header.append(titles, close);
    const content = el('div', 'attempt-history-modal__content');
    card.append(header, content);
    modal.append(backdrop, card);
    document.body.appendChild(modal);
    backdrop.addEventListener('click', closeModal);
    close.addEventListener('click', closeModal);
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') closeModal();
    });
    modal.subtitleNode = subtitle;
    modal.contentNode = content;
    return modal;
  }

  function closeModal() {
    requestSeq += 1; // responses for a closed modal are ignored
    if (modal) modal.classList.add('hidden');
  }

  async function openModal(taskId) {
    const seq = ++requestSeq;
    const node = ensureModal();
    node.classList.remove('hidden');
    node.subtitleNode.textContent = '正在读取作答过程';
    node.contentNode.replaceChildren(el('div', 'attempt-history-state', '正在加载...'));
    try {
      const response = await fetch(`/api/staff/tasks/${encodeURIComponent(taskId)}/answer-integrity`, {
        headers: { Accept: 'application/json' },
      });
      const payload = await response.json();
      if (seq !== requestSeq) return;
      if (!response.ok || !payload.ok) throw new Error(payload.error || 'request_failed');
      node.subtitleNode.textContent = `${payload.task.student_name || ''} · ${payload.task.title || ''}`;
      renderLogs(node.contentNode, payload.logs || []);
    } catch (error) {
      if (seq !== requestSeq) return;
      const message = error && error.message === 'forbidden_task'
        ? '当前账号无权查看该学生的作答过程。'
        : '作答过程加载失败，请刷新页面后重试。';
      node.contentNode.replaceChildren(el('div', 'attempt-history-state', message));
    }
  }

  function renderLogs(container, logs) {
    container.replaceChildren();
    if (!logs.length) {
      container.appendChild(el('div', 'attempt-history-state', '暂无作答过程记录。'));
      return;
    }
    container.appendChild(el(
      'p',
      'answer-integrity-note',
      '提示由作答节奏自动生成，只作参考：建议结合课上抽问或限时练习再下结论。',
    ));
    logs.forEach((log, index) => container.appendChild(renderLog(log, logs.length - index)));
  }

  function renderLog(log, number) {
    const section = el('section', `answer-integrity-log is-${log.level || 'none'}`);
    const head = el('div', 'answer-integrity-log__head');
    head.appendChild(el('strong', '', `第 ${number} 次提交 · ${log.source_label || ''} · ${MODE_LABELS[log.mode] || log.mode || ''}`));
    head.appendChild(el('span', `answer-integrity-pill is-${log.level || 'none'}`, log.level_label || ''));
    section.appendChild(head);

    const facts = [
      fmtSubmitted(log.submitted_at),
      log.correct_count !== null && log.correct_count !== undefined ? `答对 ${log.correct_count}/${log.question_count}` : '',
      log.accuracy !== null && log.accuracy !== undefined ? `正确率 ${Math.round(log.accuracy)}%` : '',
      `用时 ${fmtClock(log.duration_seconds)}`,
    ].filter(Boolean);
    section.appendChild(el('p', 'answer-integrity-log__facts', facts.join(' · ')));

    if (log.flags && log.flags.length) {
      const list = el('ul', 'answer-integrity-flags');
      log.flags.forEach(flag => list.appendChild(el('li', `is-${flag.level}`, flag.message)));
      section.appendChild(list);
    }

    if (log.has_timeline && log.metrics) {
      const m = log.metrics;
      const answeredAt = m.first_answer_seconds === null || m.first_answer_seconds === undefined
        ? ['本次没有作答记录']
        : [`第一次作答在 ${fmtClock(m.first_answer_seconds)}`, `最后一道新题在 ${fmtClock(m.last_answer_seconds)}`];
      const stats = answeredAt.concat([
        `离开页面 ${m.leave_count} 次（共 ${fmtClock(m.hidden_seconds)}）`,
        `改答案 ${m.revisit_count} 次`,
      ]);
      section.appendChild(el('p', 'answer-integrity-log__facts', stats.join(' · ')));
      section.appendChild(renderTimeline(log.events || [], m.duration_seconds));
    }
    return section;
  }

  function renderTimeline(events, durationSeconds) {
    const wrap = el('div', 'answer-timeline');
    const track = el('div', 'answer-timeline__track');
    const totalMs = Math.max(1000, (Number(durationSeconds) || 0) * 1000);
    const pct = offset => `${Math.min(100, Math.max(0, (offset / totalMs) * 100)).toFixed(2)}%`;

    let hiddenAt = null;
    const addHidden = (start, stop) => {
      const span = el('span', 'answer-timeline__hidden');
      span.style.left = pct(start);
      span.style.width = `${Math.max(0.4, ((stop - start) / totalMs) * 100).toFixed(2)}%`;
      span.title = `离开页面 ${fmtClock(start / 1000)}–${fmtClock(stop / 1000)}`;
      track.appendChild(span);
    };
    const seen = new Set();
    events.forEach(event => {
      const [offset, type, key] = event;
      if (type === 'h' && hiddenAt === null) hiddenAt = offset;
      if (type === 's' && hiddenAt !== null) {
        addHidden(hiddenAt, offset);
        hiddenAt = null;
      }
      if (type === 'a') {
        const tick = el('span', `answer-timeline__tick${seen.has(key) ? ' is-revisit' : ''}`);
        tick.style.left = pct(offset);
        tick.title = `${seen.has(key) ? '修改' : '作答'} 第 ${key} 题 · ${fmtClock(offset / 1000)}`;
        seen.add(key);
        track.appendChild(tick);
      }
    });
    if (hiddenAt !== null) addHidden(hiddenAt, totalMs);

    const axis = el('div', 'answer-timeline__axis');
    axis.append(el('span', '', '0:00'), el('span', '', fmtClock(totalMs / 2000)), el('span', '', fmtClock(totalMs / 1000)));
    const legend = el('div', 'answer-timeline__legend');
    legend.append(
      el('span', 'is-tick', '作答'),
      el('span', 'is-revisit', '改答案'),
      el('span', 'is-hidden', '离开页面'),
    );
    wrap.append(track, axis, legend);
    return wrap;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadBadges);
  } else {
    loadBadges();
  }
})();
