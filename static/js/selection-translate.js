(function() {
  'use strict';

  const WORD_RE = /^[A-Za-z][A-Za-z'-]{0,39}$/;
  const LOOKUP_URL = '/api/practice/word-lookup';
  const ME_URL = '/api/practice/me';
  const SAVE_URL = '/api/practice/save-word';
  const IGNORE_SELECTOR = [
    'input',
    'textarea',
    'select',
    'button',
    'a',
    '[contenteditable="true"]',
    '[data-no-translate]',
    '.question-no',
    '.blank-number',
    '.q-number',
    '.answer-pill',
    '.transcript-time',
    '.sel-tx-popover'
  ].join(',');

  let popover = null;
  let activeWord = '';
  let activeLookupData = null;
  let activeController = null;
  let triggerTimer = 0;
  let isPracticeStudent = false;

  function isReviewMode() {
    return document.body.classList.contains('result-mode') ||
      document.body.classList.contains('show-answers');
  }

  function ensureStyles() {
    if (document.getElementById('selTxStyles')) return;
    const style = document.createElement('style');
    style.id = 'selTxStyles';
    style.textContent = `
      .sel-tx-popover {
        position: absolute;
        z-index: 99999;
        width: min(280px, calc(100vw - 24px));
        max-width: calc(100vw - 24px);
        padding: 12px 14px;
        border: 1px solid rgba(15, 23, 42, 0.12);
        border-radius: 8px;
        background: #fff;
        box-shadow: 0 14px 36px rgba(15, 23, 42, 0.18);
        color: #111827;
        font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      .sel-tx-popover::before {
        content: "";
        position: absolute;
        top: -7px;
        left: var(--arrow-left, 24px);
        width: 12px;
        height: 12px;
        border-left: 1px solid rgba(15, 23, 42, 0.12);
        border-top: 1px solid rgba(15, 23, 42, 0.12);
        background: #fff;
        transform: rotate(45deg);
      }
      .sel-tx-word {
        font-weight: 700;
        font-size: 15px;
        color: #0f172a;
        word-break: break-word;
      }
      .sel-tx-phonetic {
        margin-left: 6px;
        color: #64748b;
        font-weight: 500;
      }
      .sel-tx-translation {
        margin-top: 6px;
        color: #1f2937;
        word-break: break-word;
      }
      .sel-tx-meta {
        margin-top: 7px;
        color: #6b7280;
        font-size: 12px;
      }
      .sel-tx-status {
        color: #475569;
      }
      .sel-tx-error {
        color: #b91c1c;
      }
      .sel-tx-save {
        margin-top: 10px;
        width: 100%;
        min-height: 34px;
        border: 1px solid #2F8E87;
        border-radius: 8px;
        background: #2F8E87;
        color: #fff;
        font: 700 13px/1 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        cursor: pointer;
      }
      .sel-tx-save:disabled {
        cursor: default;
        opacity: 0.76;
      }
      .sel-tx-save.is-error {
        border-color: #fecaca;
        background: #fff1f2;
        color: #b91c1c;
      }
    `;
    document.head.appendChild(style);
  }

  function escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, function(ch) {
      return ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      })[ch];
    });
  }

  function normalizeWord(value) {
    const word = String(value || '')
      .trim()
      .replace(/[‘’`]/g, "'")
      .replace(/^[\s"'“”‘’.,;:!?()[\]{}<>…-]+|[\s"'“”‘’.,;:!?()[\]{}<>…-]+$/g, '');
    return WORD_RE.test(word) ? word : '';
  }

  function isIgnoredNode(node) {
    const element = node && node.nodeType === Node.TEXT_NODE ? node.parentElement : node;
    return Boolean(element && element.closest && element.closest(IGNORE_SELECTOR));
  }

  function getSelectionPayload() {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
    if (isIgnoredNode(selection.anchorNode) || isIgnoredNode(selection.focusNode)) return null;

    const range = selection.getRangeAt(0);
    if (isIgnoredNode(range.commonAncestorContainer)) return null;

    const word = normalizeWord(selection.toString());
    if (!word) return null;

    let rect = range.getBoundingClientRect();
    if (!rect || (!rect.width && !rect.height)) {
      const rects = range.getClientRects();
      rect = rects.length ? rects[0] : null;
    }
    if (!rect) return null;
    return { word, rect };
  }

  function closePopover() {
    if (activeController) {
      activeController.abort();
      activeController = null;
    }
    activeWord = '';
    activeLookupData = null;
    if (popover) {
      popover.remove();
      popover = null;
    }
  }

  function placePopover(rect) {
    if (!popover) return;
    const margin = 12;
    const pageX = window.scrollX || window.pageXOffset;
    const pageY = window.scrollY || window.pageYOffset;
    const viewportWidth = document.documentElement.clientWidth || window.innerWidth;

    popover.style.visibility = 'hidden';
    popover.style.left = '0px';
    popover.style.top = '0px';

    const popoverWidth = popover.offsetWidth || 280;
    const targetCenter = rect.left + rect.width / 2;
    const minLeft = margin;
    const maxLeft = Math.max(margin, viewportWidth - popoverWidth - margin);
    const left = Math.min(Math.max(targetCenter - popoverWidth / 2, minLeft), maxLeft);
    const top = Math.max(pageY + rect.bottom + 8, pageY + margin);
    const arrowLeft = Math.min(
      Math.max(targetCenter - left - 6, 14),
      Math.max(14, popoverWidth - 26)
    );

    popover.style.left = `${left + pageX}px`;
    popover.style.top = `${top}px`;
    popover.style.setProperty('--arrow-left', `${arrowLeft}px`);
    popover.style.visibility = 'visible';
  }

  function showPopover(rect, html) {
    ensureStyles();
    if (!popover) {
      popover = document.createElement('div');
      popover.className = 'sel-tx-popover';
      popover.setAttribute('role', 'status');
      popover.setAttribute('aria-live', 'polite');
      popover.addEventListener('mousedown', function(event) {
        event.stopPropagation();
      });
      popover.addEventListener('click', handlePopoverClick);
      document.body.appendChild(popover);
    }
    popover.innerHTML = html;
    placePopover(rect);
  }

  function loadingHtml(word) {
    return `
      <div class="sel-tx-word">${escapeHtml(word)}</div>
      <div class="sel-tx-translation sel-tx-status">查询中...</div>
    `;
  }

  function resultHtml(data) {
    const sourceLabels = {
      cache: '本地缓存',
      dictation: '本地词库',
      google: 'Google 免费翻译',
      youdao: '有道词典'
    };
    const source = sourceLabels[data.source] || '查词服务';
    const phonetic = data.phonetic ? `<span class="sel-tx-phonetic">${escapeHtml(data.phonetic)}</span>` : '';
    const saveButton = isPracticeStudent
      ? '<button type="button" class="sel-tx-save" data-sel-tx-save>加入生词本</button>'
      : '';
    return `
      <div class="sel-tx-word">${escapeHtml(data.word || activeWord)}${phonetic}</div>
      <div class="sel-tx-translation">${escapeHtml(data.translation)}</div>
      ${saveButton}
      <div class="sel-tx-meta">来源：${escapeHtml(source)}</div>
    `;
  }

  function missHtml(word) {
    return `
      <div class="sel-tx-word">${escapeHtml(word)}</div>
      <div class="sel-tx-translation sel-tx-status">未查询到释义</div>
    `;
  }

  function errorHtml(word, error) {
    const message = error === 'rate_limited'
      ? '请求过于频繁，请稍后再试'
      : '查询失败，请稍后重试';
    return `
      <div class="sel-tx-word">${escapeHtml(word)}</div>
      <div class="sel-tx-translation sel-tx-error">${message}</div>
    `;
  }

  async function lookupWord(word, rect) {
    if (activeController) activeController.abort();
    const controller = new AbortController();
    activeController = controller;
    activeWord = word;
    activeLookupData = null;
    showPopover(rect, loadingHtml(word));

    try {
      const response = await fetch(LOOKUP_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        signal: controller.signal,
        body: JSON.stringify({ word })
      });
      const data = await response.json().catch(function() { return {}; });
      if (!popover || activeWord !== word) return;
      if (response.ok && data.ok && data.found && data.translation) {
        activeLookupData = data;
        showPopover(rect, resultHtml(data));
      } else if (response.ok && data.ok && data.found === false) {
        showPopover(rect, missHtml(word));
      } else {
        showPopover(rect, errorHtml(word, data.error));
      }
    } catch (err) {
      if (err && err.name === 'AbortError') return;
      if (popover && activeWord === word) {
        showPopover(rect, errorHtml(word));
      }
    } finally {
      if (activeController === controller) activeController = null;
    }
  }

  function handleSelection() {
    if (!isReviewMode()) {
      closePopover();
      return;
    }
    const payload = getSelectionPayload();
    if (!payload) {
      closePopover();
      return;
    }
    if (payload.word === activeWord && popover) {
      placePopover(payload.rect);
      return;
    }
    lookupWord(payload.word, payload.rect);
  }

  function scheduleSelectionCheck(delay) {
    window.clearTimeout(triggerTimer);
    triggerTimer = window.setTimeout(handleSelection, delay);
  }

  function getPracticeSourceKind() {
    return String(window.__PRACTICE_SOURCE__ || 'manual').slice(0, 32) || 'manual';
  }

  function getPracticeSourceRef() {
    return String(window.__PRACTICE_SOURCE_REF__ || window.location.pathname || '').slice(0, 80);
  }

  function setSaveButton(button, text, disabled, isError) {
    if (!button) return;
    button.textContent = text;
    button.disabled = Boolean(disabled);
    button.classList.toggle('is-error', Boolean(isError));
  }

  async function saveActiveWord(button) {
    if (!activeLookupData || !activeLookupData.translation) return;
    setSaveButton(button, '保存中...', true, false);
    try {
      const response = await fetch(SAVE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({
          word: activeLookupData.word || activeWord,
          translation: activeLookupData.translation,
          source_kind: getPracticeSourceKind(),
          source_ref: getPracticeSourceRef()
        })
      });
      const data = await response.json().catch(function() { return {}; });
      if (response.ok && data.ok) {
        setSaveButton(button, '✓ 已加入', true, false);
      } else {
        setSaveButton(button, '保存失败，点我重试', false, true);
      }
    } catch (err) {
      setSaveButton(button, '保存失败，点我重试', false, true);
    }
  }

  function handlePopoverClick(event) {
    const saveButton = event.target && event.target.closest
      ? event.target.closest('[data-sel-tx-save]')
      : null;
    if (!saveButton) return;
    event.preventDefault();
    event.stopPropagation();
    saveActiveWord(saveButton);
  }

  async function loadPracticeUser() {
    try {
      const response = await fetch(ME_URL, { credentials: 'same-origin' });
      const data = await response.json();
      isPracticeStudent = Boolean(response.ok && data && data.is_student);
    } catch (err) {
      isPracticeStudent = false;
    }
    window.__IS_STUDENT__ = isPracticeStudent;
  }

  document.addEventListener('mouseup', function() {
    scheduleSelectionCheck(80);
  });
  document.addEventListener('touchend', function() {
    scheduleSelectionCheck(180);
  }, { passive: true });
  document.addEventListener('keyup', function(event) {
    if (event.key === 'Escape') {
      closePopover();
      return;
    }
    scheduleSelectionCheck(80);
  });
  document.addEventListener('mousedown', function(event) {
    if (popover && !popover.contains(event.target)) closePopover();
  });
  document.addEventListener('scroll', closePopover, true);
  loadPracticeUser();
})();
