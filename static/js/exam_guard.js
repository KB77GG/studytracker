/* Optional exam integrity UI. The exam's saving, clock and submission stay independent. */
(function (root, factory) {
  'use strict';
  try {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else if (root && root.document) {
      const node = root.document.getElementById('exam-integrity-config');
      if (node) api.install(root, JSON.parse(node.textContent));
    }
  } catch (_error) { /* A broken optional guard must leave the exam usable. */ }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const ACTIVE_MODES = ['monitor', 'enforce'];
  const DEVICE_KEY = 'exam-integrity-device:v1';
  const SUPPORT = '遇到问题请举手联系老师，答案已保存。计时仍在继续。';

  function viewState(state, section, healthy = true) {
    const enabled = healthy && !!state && ACTIVE_MODES.includes(state.mode);
    const enforce = enabled && state.mode === 'enforce' && !state.exempt;
    // Listening audio cannot be replayed: no blocking layer, including soft signals.
    const canCover = enforce && section !== 'listening' && section !== 'process';
    return {
      enabled,
      enforce,
      locked: canCover && !!state.is_locked,
      conflict: enforce && section !== 'listening' && !!state.device_conflict,
      ackRequired: enabled && section === 'process' && !state.acked && !state.acked_at && !state.exempt,
      warning: enforce && Number(state.leave_count || 0) > 0,
    };
  }

  function allowsInternalPaste(text, copied) {
    return typeof text === 'string' && text.length > 0 && typeof copied === 'string' && text === copied;
  }

  function viewportSignal(width, screenWidth) {
    const ratio = Number(screenWidth) > 0 ? Number(width) / Number(screenWidth) : 1;
    return { ratio: Number.isFinite(ratio) ? ratio : 1, narrow: Number.isFinite(ratio) && ratio > 0 && ratio < 0.7 };
  }

  function visibilityTracker(pageId) {
    let hiddenAt = null;
    return function transition(visibility, now) {
      if (visibility === 'hidden' && hiddenAt === null) {
        hiddenAt = now;
        return { type: 'hidden', page_id: pageId, client_ts: now };
      }
      if (visibility === 'visible' && hiddenAt !== null) {
        const duration = Math.max(0, now - hiddenAt);
        hiddenAt = null;
        return { type: 'visible', page_id: pageId, client_ts: now, client_hidden_ms: duration };
      }
      return null;
    };
  }

  function randomId(win) {
    if (win.crypto && win.crypto.randomUUID) return win.crypto.randomUUID();
    if (win.crypto && win.crypto.getRandomValues) {
      return Array.from(win.crypto.getRandomValues(new Uint32Array(4)), n => n.toString(16).padStart(8, '0')).join('');
    }
    return Date.now().toString(36) + Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
  }

  function install(win, config) {
    const doc = win.document;
    if (!config || !ACTIVE_MODES.includes(config.mode)) return null;
    let stopped = false;
    let healthy = false;
    let state = config;
    let root;
    let overlay;
    let overlayTitle;
    let overlayMessage;
    let continueButton;
    let warning;
    let rules;
    let rulesDescription;
    let ackButton;
    let watermark;
    let softBlur = false;
    let previousFocus = null;
    let wakeLock = null;
    let wakePending = false;
    let deviceId;
    let pageId;
    let transition;
    let requestNumber = 0;
    let appliedNumber = 0;
    let polling = false;
    let sendingHello = false;
    let hasClaimedDevice = false;
    let lastHeartbeat = 0;
    let lastNarrow = null;
    let copied = '';
    let pastePermit = null;
    let lastBlocked = null;
    const timers = [];
    const listeners = [];
    const gatedLinks = new Map();

    function restoreLinks() {
      gatedLinks.forEach((original, link) => {
        if (original.href !== null) link.setAttribute('href', original.href);
        if (original.entry !== null) link.setAttribute('data-practice-entry', original.entry);
        if (original.tabindex === null) link.removeAttribute('tabindex');
        else link.setAttribute('tabindex', original.tabindex);
        link.removeAttribute('data-exam-guard-pending');
      });
      gatedLinks.clear();
    }

    function gateLinks(required) {
      if (!required) { restoreLinks(); return; }
      doc.querySelectorAll('#btnStartListening, #btnStartReading, #btnStartWriting').forEach(link => {
        if (!gatedLinks.has(link)) {
          gatedLinks.set(link, { href: link.getAttribute('href'), entry: link.getAttribute('data-practice-entry'), tabindex: link.getAttribute('tabindex') });
        }
        link.removeAttribute('href');
        link.removeAttribute('data-practice-entry');
        link.setAttribute('tabindex', '-1');
        link.setAttribute('data-exam-guard-pending', 'true');
      });
    }

    function failOpen() {
      healthy = false;
      softBlur = false;
      restoreLinks();
      if (root) root.hidden = true;
      doc.body.classList.remove('exam-integrity-enforce');
      if (previousFocus && previousFocus.isConnected) previousFocus.focus({ preventScroll: true });
      previousFocus = null;
    }

    function safely(fn) {
      return function () {
        if (stopped) return;
        try {
          const result = fn.apply(null, arguments);
          if (result && typeof result.catch === 'function') return result.catch(() => { failOpen(); });
          return result;
        } catch (_error) { failOpen(); }
      };
    }

    function listen(target, type, handler, clipboard = false) {
      const wrapped = safely(handler);
      const options = { passive: !clipboard };
      target.addEventListener(type, wrapped, options);
      listeners.push([target, type, wrapped, options]);
    }

    function stop() {
      stopped = true;
      failOpen();
      timers.forEach(id => win.clearInterval(id));
      listeners.forEach(args => args[0].removeEventListener(args[1], args[2], args[3]));
      try { if (wakeLock) Promise.resolve(wakeLock.release()).catch(() => {}); } catch (_error) { /* Optional API. */ }
      if (root) root.remove();
    }

    function element(tag, className, text) {
      const node = doc.createElement(tag);
      if (className) node.className = className;
      if (text) node.textContent = text;
      return node;
    }

    function buildUI() {
      root = element('div', 'exam-integrity-root');
      root.id = 'exam-integrity-root';
      root.hidden = true;
      warning = element('div', 'exam-integrity-warning');
      warning.setAttribute('role', 'status');
      root.appendChild(warning);
      overlay = element('div', 'exam-integrity-overlay');
      overlay.hidden = true;
      overlay.setAttribute('role', 'dialog');
      overlay.setAttribute('aria-label', '考试状态');
      overlay.setAttribute('tabindex', '0');
      const panel = element('div', 'exam-integrity-panel');
      overlayTitle = element('h2');
      overlayMessage = element('p');
      continueButton = element('button', 'exam-integrity-button', '点击继续答题');
      continueButton.type = 'button';
      panel.appendChild(overlayTitle);
      panel.appendChild(overlayMessage);
      panel.appendChild(element('p', 'exam-integrity-support', SUPPORT));
      panel.appendChild(continueButton);
      overlay.appendChild(panel);
      root.appendChild(overlay);
      listen(continueButton, 'click', () => { softBlur = false; render(); });
      rules = element('section', 'exam-integrity-rules');
      rules.setAttribute('aria-label', '考试规则与设备检查');
      rules.appendChild(element('h2', '', '考试规则与设备检查'));
      rulesDescription = element('p');
      rules.appendChild(rulesDescription);
      rules.appendChild(element('p', '', '考前请开勿扰模式、调长自动锁定时间、关闭其他 App 和标签页，并连接电源。'));
      const guide = element('a', '', '查看 iPad / MacBook 设备指引');
      guide.href = config.guide_url || '/exam/guide';
      guide.target = '_blank';
      guide.rel = 'noopener';
      rules.appendChild(guide);
      ackButton = element('button', 'exam-integrity-button', '我已阅读并承诺遵守');
      ackButton.type = 'button';
      rules.appendChild(ackButton);
      listen(ackButton, 'click', () => {
        ackButton.disabled = true;
        send('ack').finally(() => { ackButton.disabled = false; });
      });
      root.appendChild(rules);
      watermark = element('div', 'exam-integrity-watermark');
      watermark.setAttribute('aria-hidden', 'true');
      const started = config.started_at ? new Date(config.started_at).toLocaleString() : '模考进行中';
      for (let i = 0; i < 20; i += 1) watermark.appendChild(element('span', '', `${config.student_name || ''} · ${started}`));
      root.appendChild(watermark);
      doc.body.appendChild(root);
    }

    function render() {
      const styled = win.getComputedStyle(root).getPropertyValue('--exam-integrity-ready').trim() === '1';
      const view = viewState(state, config.section, healthy && styled);
      if (!view.enabled) { failOpen(); return; }
      root.hidden = false;
      doc.body.classList.toggle('exam-integrity-enforce', view.enforce);
      gateLinks(view.enforce && view.ackRequired);
      rules.hidden = !view.ackRequired;
      rulesDescription.textContent = state.mode === 'monitor'
        ? '本场为仅记录模式：离开页面、复制和粘贴会被记录，不警告、不锁定。'
        : `离开页面会被记录。阅读和写作累计 ${state.max_leaves || config.max_leaves || 3} 次或 ${state.max_hidden_seconds || config.max_hidden_seconds || 60} 秒将锁定；听力只警告。禁止复制题干和粘贴外部作文；计时不暂停。`;
      watermark.hidden = !view.enforce || config.section === 'process';
      const blurCover = view.enforce && config.section !== 'listening' && config.section !== 'process' && softBlur;
      const cover = view.locked || view.conflict || blurCover;
      const wasHidden = overlay.hidden;
      overlay.hidden = !cover;
      continueButton.hidden = !blurCover || view.locked || view.conflict;
      if (view.conflict) {
        overlayTitle.textContent = '需要老师确认设备';
        overlayMessage.textContent = '本场考试已在另一台设备开始，如需更换请联系老师。';
      } else if (view.locked) {
        overlayTitle.textContent = '本场答题已锁定';
        overlayMessage.textContent = `锁定原因：${state.locked_reason || '离开页面达到本场限制'}。请联系老师解锁，无需刷新。`;
      } else if (blurCover) {
        overlayTitle.textContent = '点击继续答题';
        overlayMessage.textContent = '页面暂时失去焦点，本次失焦不会计为离开。';
      }
      if (cover && wasHidden) {
        previousFocus = doc.activeElement;
        overlay.focus({ preventScroll: true });
      } else if (!cover && !wasHidden && previousFocus && previousFocus.isConnected) {
        previousFocus.focus({ preventScroll: true });
        previousFocus = null;
      }
      warning.hidden = !view.warning && !(view.enforce && config.section === 'listening' && state.device_conflict);
      if (!warning.hidden) {
        const limits = Number(state.unlock_count || 0) > 0
          ? '解锁后再离开 1 次或再累计 30 秒将再次锁定'
          : `累计 ${state.max_leaves || config.max_leaves || 3} 次或 ${state.max_hidden_seconds || config.max_hidden_seconds || 60} 秒将锁定`;
        warning.textContent = state.device_conflict && config.section === 'listening'
          ? '检测到另一台设备，请举手联系老师；听力继续播放。'
          : `已记录 ${state.leave_count || 0} 次离开，累计 ${Math.floor(state.hidden_seconds || 0)} 秒。${limits}。${config.section === 'listening' ? '听力阶段只警告，不锁定。' : ''}`;
      }
    }

    async function wake() {
      if (wakePending) return;
      try {
        if (!stopped && healthy && !wakePending && doc.visibilityState === 'visible' && win.navigator.wakeLock && (!wakeLock || wakeLock.released)) {
          wakePending = true;
          wakeLock = await win.navigator.wakeLock.request('screen');
          if (stopped || !healthy) await wakeLock.release();
        }
      } catch (_error) { /* Wake Lock is optional and permission/browser dependent. */ }
      finally { wakePending = false; }
    }

    async function request(url, options) {
      const number = ++requestNumber;
      let timeout;
      let controller;
      try {
        if (win.AbortController) controller = new win.AbortController();
        const timedOut = new Promise((_, reject) => {
          timeout = win.setTimeout(() => { if (controller) controller.abort(); reject(new Error('timeout')); }, 4000);
        });
        const fetchState = win.fetch(url, { ...options, credentials: 'same-origin', cache: 'no-store', ...(controller ? { signal: controller.signal } : {}) })
          .then(async response => { if (!response.ok) throw new Error('integrity unavailable'); return response.json(); });
        const result = await Promise.race([fetchState, timedOut]);
        if (stopped) return result;
        if (!result || result.ok === false || !['off', 'monitor', 'enforce'].includes(result.mode)) throw new Error('invalid state');
        if (result.mode === 'off') { stop(); return result; }
        // A prior hello may have reached the server even if its response timed out.
        if (result.mode === 'enforce' && result.device_bound && !result.device_conflict) hasClaimedDevice = true;
        if (number < appliedNumber) return result;
        appliedNumber = number;
        state = result;
        healthy = true;
        render();
        wake();
        return result;
      } catch (_error) {
        if (!stopped && number >= appliedNumber) { appliedNumber = number; failOpen(); }
        return null;
      } finally { win.clearTimeout(timeout); }
    }

    function payload(type, extra = {}) {
      return { device_id: deviceId, page_id: pageId, type, section: config.section, client_ts: Date.now(), ...extra };
    }

    function send(type, extra = {}) {
      if (stopped) return Promise.resolve(null);
      return request(config.event_url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload(type, extra)) });
    }

    async function hello() {
      if (sendingHello || stopped) return;
      sendingHello = true;
      try {
        const result = await send('hello');
        if (result && result.mode === 'enforce' && result.device_bound && !result.device_conflict) hasClaimedDevice = true;
      }
      finally { sendingHello = false; }
    }

    function beacon(event) {
      const body = JSON.stringify(payload(event.type, event));
      try {
        if (win.navigator.sendBeacon && win.navigator.sendBeacon(config.event_url, new win.Blob([body], { type: 'application/json' }))) return;
      } catch (_error) { /* The visible event carries duration if the beacon was lost. */ }
      // This request is best effort. Failure cannot change the exam's saving logic.
      request(config.event_url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true });
    }

    function elapsedClock() {
      return win.performance && win.performance.now ? win.performance.now() : Date.now();
    }

    async function poll() {
      if (stopped || polling) return;
      polling = true;
      try {
        const query = new win.URLSearchParams({ section: config.section, page_id: pageId });
        const result = await request(config.state_url + '?' + query.toString(), { method: 'GET', headers: { 'X-Exam-Integrity-Device': deviceId } });
        if (result && result.mode === 'enforce' && result.device_bound === false && !hasClaimedDevice) await hello();
        if (!stopped && doc.visibilityState === 'visible' && elapsedClock() - lastHeartbeat >= 15000) {
          lastHeartbeat = elapsedClock();
          await send('heartbeat');
        }
      } catch (_error) { failOpen(); }
      finally { polling = false; }
    }

    // A 15s refresh plus the 4s request timeout stays inside the 20s fail-open budget.
    async function scheduledRefresh() {
      if (stopped || polling) return;
      if (doc.visibilityState === 'visible' && elapsedClock() - lastHeartbeat >= 15000) {
        polling = true;
        lastHeartbeat = elapsedClock();
        try {
          const result = await send('heartbeat');
          if (result && result.mode === 'enforce' && result.device_bound === false && !hasClaimedDevice) await hello();
        } finally { polling = false; }
        return;
      }
      const view = viewState(state, config.section, healthy);
      if (!healthy || view.locked || view.conflict || softBlur || (view.enforce && view.ackRequired)) await poll();
    }

    function editable(target) {
      return !!(target && target.closest && target.closest('input, textarea, [contenteditable="true"], [contenteditable=""]'));
    }

    function writingBox(target) {
      return config.section === 'writing' && target && target.matches && target.matches('textarea[id^="essayTask"]');
    }

    function questionRef(target) {
      if (!target || !target.closest) return '';
      const node = target.closest('[data-question-id], [data-id], [data-task]');
      return node ? String(node.getAttribute('data-question-id') || node.getAttribute('data-id') || node.getAttribute('data-task') || '').slice(0, 80) : '';
    }

    function copy(event) {
      if (!healthy) return;
      if (writingBox(event.target)) {
        copied = event.target.value.slice(event.target.selectionStart, event.target.selectionEnd);
        return;
      }
      if (editable(event.target)) return;
      const enforce = viewState(state, config.section, healthy).enforce;
      if (enforce) event.preventDefault();
      send('copy_blocked', { question: questionRef(event.target), detail: { blocked: enforce, signal: event.type } });
    }

    function paste(event) {
      if (!healthy || !writingBox(event.target)) return;
      const before = event.type === 'beforeinput';
      if (before && !['insertFromPaste', 'insertFromDrop'].includes(event.inputType)) return;
      const transfer = event.clipboardData || event.dataTransfer;
      const text = transfer ? transfer.getData('text/plain') : (typeof event.data === 'string' ? event.data : '');
      const now = Date.now();
      const permitted = allowsInternalPaste(text, copied) || (before && !text && pastePermit && pastePermit.target === event.target && now - pastePermit.at < 1000);
      if (permitted) {
        pastePermit = before ? null : { target: event.target, at: now };
        return;
      }
      pastePermit = null;
      const enforce = viewState(state, config.section, healthy).enforce;
      if (enforce) event.preventDefault();
      if (!lastBlocked || lastBlocked.target !== event.target || now - lastBlocked.at > 100) {
        send('paste_blocked', { question: questionRef(event.target), detail: { length: text.length, blocked: enforce, signal: before ? 'beforeinput' : event.type } });
        lastBlocked = { target: event.target, at: now };
      }
    }

    function viewport() {
      const signal = viewportSignal(win.innerWidth, win.screen && win.screen.width);
      if (lastNarrow === signal.narrow) return;
      lastNarrow = signal.narrow;
      // Split View/Stage Manager is unverified on real iPads: record only, never cover.
      if (healthy) send('viewport', { detail: { ratio: signal.ratio, width: win.innerWidth, screen_width: win.screen && win.screen.width } });
    }

    try {
      if (!config.event_url || !config.state_url) throw new Error('missing URLs');
      pageId = randomId(win);
      deviceId = win.localStorage.getItem(DEVICE_KEY);
      if (!deviceId) { deviceId = randomId(win); win.localStorage.setItem(DEVICE_KEY, deviceId); }
      transition = visibilityTracker(pageId);
      buildUI();
      listen(doc, 'visibilitychange', () => {
        const event = transition(doc.visibilityState, Date.now());
        if (event && event.type === 'hidden') beacon(event);
        else if (doc.visibilityState === 'visible') {
          softBlur = false;
          if (event) send('visible', event);
          else poll();
          wake();
          if (healthy) render();
        }
      });
      listen(win, 'blur', () => {
        if (!healthy) return;
        softBlur = true;
        send('blur');
        render();
      });
      listen(win, 'focus', () => { softBlur = false; if (healthy) render(); poll(); });
      listen(doc, 'focusin', event => {
        if (healthy && !overlay.hidden && !overlay.contains(event.target)) overlay.focus({ preventScroll: true });
      });
      listen(win, 'resize', viewport);
      ['copy', 'cut'].forEach(type => listen(doc, type, copy, true));
      ['paste', 'drop', 'beforeinput'].forEach(type => listen(doc, type, paste, true));
      lastHeartbeat = elapsedClock();
      timers.push(win.setInterval(safely(scheduledRefresh), 5000));
      hello().then(safely(viewport));
    } catch (_error) { stop(); }
    return { stop, failOpen, poll, state: () => state };
  }

  return { install, viewState, allowsInternalPaste, viewportSignal, visibilityTracker };
}));
