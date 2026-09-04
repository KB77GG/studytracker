(function () {
  'use strict';

  const root = document.querySelector('[data-mother-topic-detail]');
  if (!root) return;
  const tabs = Array.from(root.querySelectorAll('[data-topic-model-band]'));
  const panels = Array.from(root.querySelectorAll('[data-topic-model-panel]'));
  const copyStatus = document.getElementById('writingCopyStatus');
  const assignedTaskId = root.dataset.assignedTaskId || '';
  const topicId = root.dataset.topicId || '';
  const topicCompleteButton = document.getElementById('writingTopicComplete');
  const topicAssignment = document.getElementById('writingTopicAssignment');
  const openedAt = Date.now();

  function selectBand(selected) {
    const band = selected.dataset.topicModelBand;
    tabs.forEach(function (tab) {
      const active = tab === selected;
      tab.classList.toggle('is-active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
      tab.tabIndex = active ? 0 : -1;
    });
    panels.forEach(function (panel) {
      panel.hidden = panel.dataset.topicModelPanel !== band;
    });
  }

  tabs.forEach(function (tab, index) {
    tab.addEventListener('click', function () { selectBand(tab); });
    tab.addEventListener('keydown', function (event) {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
      event.preventDefault();
      const offset = event.key === 'ArrowRight' ? 1 : -1;
      const next = tabs[(index + offset + tabs.length) % tabs.length];
      selectBand(next);
      next.focus();
    });
  });

  function fallbackCopy(text) {
    const field = document.createElement('textarea');
    field.value = text;
    field.setAttribute('readonly', '');
    field.style.position = 'fixed';
    field.style.opacity = '0';
    document.body.appendChild(field);
    field.select();
    const copied = document.execCommand('copy');
    field.remove();
    return copied;
  }

  root.querySelectorAll('[data-copy-expression]').forEach(function (button) {
    button.addEventListener('click', async function () {
      const text = button.dataset.copyExpression || '';
      let copied = false;
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(text);
          copied = true;
        } else {
          copied = fallbackCopy(text);
        }
      } catch (_error) {
        copied = fallbackCopy(text);
      }
      if (copyStatus) copyStatus.textContent = copied ? '已复制：' + text : '复制失败，请手动选择文本。';
    });
  });

  if (assignedTaskId && topicId && topicCompleteButton && root.dataset.assignedComplete !== '1') {
    topicCompleteButton.addEventListener('click', async function () {
      topicCompleteButton.disabled = true;
      topicCompleteButton.textContent = '正在提交…';
      try {
        const response = await fetch('/writing/api/topics/' + encodeURIComponent(topicId) + '/tasks/' + encodeURIComponent(assignedTaskId) + '/complete', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ duration_seconds: Math.floor((Date.now() - openedAt) / 1000) })
        });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || 'complete_failed');
        topicCompleteButton.textContent = '已完成';
        topicAssignment?.classList.add('is-complete');
        const description = topicAssignment?.querySelector('strong');
        if (description) description.textContent = '母题学习已完成，可继续复习';
      } catch (_error) {
        topicCompleteButton.disabled = false;
        topicCompleteButton.textContent = '重试确认完成';
      }
    });
  }

  const navLinks = Array.from(root.querySelectorAll('.writing-detail-nav a[href^="#"]'));
  const sections = navLinks.map(function (link) {
    return document.querySelector(link.getAttribute('href'));
  }).filter(Boolean);
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(function (entries) {
      const visible = entries.filter(function (entry) { return entry.isIntersecting; })
        .sort(function (left, right) { return right.intersectionRatio - left.intersectionRatio; });
      if (!visible.length) return;
      const id = '#' + visible[0].target.id;
      navLinks.forEach(function (link) {
        link.classList.toggle('is-active', link.getAttribute('href') === id);
      });
    }, { rootMargin: '-18% 0px -68% 0px', threshold: [0, 0.15, 0.4] });
    sections.forEach(function (section) { observer.observe(section); });
  }
})();
