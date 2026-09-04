(function () {
  'use strict';

  const root = document.querySelector('[data-writing-detail]');
  if (!root) return;
  const exerciseId = root.dataset.exerciseId;
  const assignedTaskId = root.dataset.assignedTaskId || '';
  const essayData = JSON.parse(document.getElementById('writingEssayData').textContent);
  const staffMode = document.getElementById('typing').dataset.staffMode === '1';

  const modelButtons = Array.from(document.querySelectorAll('[data-model-band]'));
  const modelPanels = Array.from(document.querySelectorAll('[data-model-panel]'));
  modelButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      modelButtons.forEach(function (candidate) {
        const active = candidate === button;
        candidate.classList.toggle('is-active', active);
        candidate.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      modelPanels.forEach(function (panel) {
        panel.hidden = panel.dataset.modelPanel !== button.dataset.modelBand;
      });
    });
  });

  const structureButtons = Array.from(document.querySelectorAll('[data-structure-tab]'));
  const structurePanels = Array.from(document.querySelectorAll('[data-structure-panel]'));
  structureButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      structureButtons.forEach(function (candidate) {
        const active = candidate === button;
        candidate.classList.toggle('is-active', active);
        candidate.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      structurePanels.forEach(function (panel) {
        panel.hidden = panel.dataset.structurePanel !== button.dataset.structureTab;
      });
    });
  });

  const copyStatus = document.getElementById('writingCopyStatus');
  document.querySelectorAll('[data-copy-expression]').forEach(function (button) {
    button.addEventListener('click', async function () {
      const text = button.dataset.copyExpression || '';
      try {
        await navigator.clipboard.writeText(text);
      } catch (_error) {
        const helper = document.createElement('textarea');
        helper.value = text;
        helper.setAttribute('readonly', '');
        helper.style.position = 'fixed';
        helper.style.opacity = '0';
        document.body.appendChild(helper);
        helper.select();
        document.execCommand('copy');
        helper.remove();
      }
      copyStatus.textContent = '已复制：' + text;
      window.setTimeout(function () { copyStatus.textContent = ''; }, 2400);
    });
  });

  const navLinks = Array.from(document.querySelectorAll('.writing-detail-nav a[href^="#"]'));
  const sections = navLinks.map(function (link) { return document.querySelector(link.getAttribute('href')); }).filter(Boolean);
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(function (entries) {
      const visible = entries.filter(function (entry) { return entry.isIntersecting; })
        .sort(function (a, b) { return b.intersectionRatio - a.intersectionRatio; })[0];
      if (!visible) return;
      navLinks.forEach(function (link) {
        link.classList.toggle('is-active', link.getAttribute('href') === '#' + visible.target.id);
      });
    }, { rootMargin: '-80px 0px -55% 0px', threshold: [0.08, 0.3] });
    sections.forEach(function (section) { observer.observe(section); });
  }

  const bandButtons = Array.from(document.querySelectorAll('[data-typing-band]'));
  const startButton = document.getElementById('typingStart');
  const finishButton = document.getElementById('typingFinish');
  const resetButton = document.getElementById('typingReset');
  const input = document.getElementById('typingInput');
  const targetText = document.getElementById('typingTargetText');
  const targetBand = document.getElementById('typingTargetBand');
  const wordMetric = document.getElementById('typingWords');
  const targetWordMetric = document.getElementById('typingTargetWords');
  const speedMetric = document.getElementById('typingSpeed');
  const accuracyMetric = document.getElementById('typingAccuracy');
  const timerMetric = document.getElementById('typingTimer');
  const saveStatus = document.getElementById('typingSaveStatus');
  let selectedBand = '6.0';
  let attemptId = null;
  let running = false;
  let startedAt = null;
  let timerHandle = null;
  let metricHandle = null;

  function storageKey() {
    return 'writingDraft:' + exerciseId + ':' + selectedBand;
  }

  function normalizeText(value) {
    return String(value || '')
      .normalize('NFKC')
      .replace(/[‘’]/g, "'")
      .replace(/[“”]/g, '"')
      .replace(/[–—]/g, '-')
      .replace(/…/g, '...')
      .replace(/\s+/g, ' ')
      .trim()
      .toLowerCase();
  }

  function countWords(value) {
    const matches = String(value || '').match(/[A-Za-z]+(?:['’-][A-Za-z]+)*|\d+(?:\.\d+)?/g);
    return matches ? matches.length : 0;
  }

  function distance(left, right) {
    if (left === right) return 0;
    if (left.length < right.length) return distance(right, left);
    let previous = Array.from({ length: right.length + 1 }, function (_value, index) { return index; });
    for (let row = 1; row <= left.length; row += 1) {
      const current = [row];
      for (let column = 1; column <= right.length; column += 1) {
        current.push(Math.min(
          current[column - 1] + 1,
          previous[column] + 1,
          previous[column - 1] + (left[row - 1] === right[column - 1] ? 0 : 1)
        ));
      }
      previous = current;
    }
    return previous[previous.length - 1];
  }

  function elapsedSeconds() {
    return startedAt ? Math.max(1, Math.floor((Date.now() - startedAt) / 1000)) : 0;
  }

  function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainder = seconds % 60;
    return String(minutes).padStart(2, '0') + ':' + String(remainder).padStart(2, '0');
  }

  function accuracy(typed, finalMode) {
    const cleanTyped = normalizeText(typed);
    const cleanTarget = normalizeText(essayData[selectedBand].text);
    if (!cleanTyped) return 0;
    const comparisonTarget = finalMode ? cleanTarget : cleanTarget.slice(0, cleanTyped.length);
    const denominator = Math.max(cleanTyped.length, comparisonTarget.length, 1);
    return Math.max(0, (1 - distance(cleanTyped, comparisonTarget) / denominator) * 100);
  }

  function updateMetrics(finalMode) {
    const seconds = elapsedSeconds();
    const words = countWords(input.value);
    wordMetric.textContent = String(words);
    speedMetric.textContent = seconds ? (words * 60 / seconds).toFixed(1) : '0.0';
    accuracyMetric.textContent = accuracy(input.value, Boolean(finalMode)).toFixed(1);
    timerMetric.textContent = formatTime(seconds);
    finishButton.disabled = !running || !input.value.trim();
  }

  function setStatus(message, kind) {
    saveStatus.textContent = message;
    saveStatus.classList.toggle('is-success', kind === 'success');
    saveStatus.classList.toggle('is-error', kind === 'error');
  }

  function setBand(band) {
    selectedBand = band;
    bandButtons.forEach(function (button) {
      const active = button.dataset.typingBand === band;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-checked', active ? 'true' : 'false');
    });
    targetText.textContent = essayData[band].text;
    targetBand.textContent = 'Band ' + band;
    targetWordMetric.textContent = '/ ' + essayData[band].word_count;
    const draft = localStorage.getItem(storageKey()) || '';
    input.value = draft;
    updateMetrics(false);
    if (draft) setStatus('已找到这个档位在当前浏览器的草稿；开始后可继续输入。', 'success');
    else setStatus('选择档位后开始；输入内容会自动保存在当前浏览器。');
  }

  function lockBands(locked) {
    bandButtons.forEach(function (button) { button.disabled = locked; });
  }

  async function beginAttempt(options) {
    const preserveDraft = !options || options.preserveDraft !== false;
    startButton.disabled = true;
    setStatus('正在创建本次练习……');
    try {
      const response = await fetch('/writing/api/' + encodeURIComponent(exerciseId) + '/typing/start', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ band: selectedBand, task_id: assignedTaskId || null })
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'start_failed');
      attemptId = data.attempt_id;
      running = true;
      startedAt = Date.now();
      if (!preserveDraft) input.value = '';
      input.disabled = false;
      resetButton.disabled = false;
      finishButton.disabled = !input.value.trim();
      startButton.textContent = '练习进行中';
      lockBands(true);
      window.clearInterval(timerHandle);
      timerHandle = window.setInterval(function () { updateMetrics(false); }, 1000);
      setStatus(data.client_only ? '课堂模式：实时统计已开始，本次不写入学生记录。' : '已开始，草稿将自动保存在当前浏览器。', 'success');
      input.focus();
      updateMetrics(false);
    } catch (_error) {
      startButton.disabled = false;
      setStatus('开始失败，请检查网络后重试。', 'error');
    }
  }

  function stopAttempt() {
    running = false;
    window.clearInterval(timerHandle);
    timerHandle = null;
    input.disabled = true;
    resetButton.disabled = true;
    finishButton.disabled = true;
    startButton.disabled = false;
    startButton.textContent = '再练一次';
    lockBands(false);
  }

  function addHistoryRow(record) {
    const container = document.getElementById('typingHistory');
    document.getElementById('typingHistoryEmpty')?.remove();
    let table = container.querySelector('.writing-history__table');
    if (!table) {
      table = document.createElement('div');
      table.className = 'writing-history__table';
      table.setAttribute('role', 'table');
      const head = document.createElement('div');
      head.className = 'writing-history__row writing-history__row--head';
      ['时间', '档位', '字数', '速度', '准确率'].forEach(function (label) {
        const cell = document.createElement('span');
        cell.textContent = label;
        head.appendChild(cell);
      });
      table.appendChild(head);
      container.appendChild(table);
    }
    const row = document.createElement('div');
    row.className = 'writing-history__row';
    row.setAttribute('role', 'row');
    const values = [
      record.completed_at || '本次（课堂）',
      record.band,
      record.typed_word_count + '/' + record.target_word_count,
      record.speed_wpm + ' WPM',
      record.accuracy + '%'
    ];
    values.forEach(function (value) {
      const cell = document.createElement('span');
      cell.textContent = value;
      cell.setAttribute('role', 'cell');
      row.appendChild(cell);
    });
    table.insertBefore(row, table.children[1] || null);
  }

  bandButtons.forEach(function (button) {
    button.addEventListener('click', function () { if (!running) setBand(button.dataset.typingBand); });
  });
  startButton.addEventListener('click', function () { beginAttempt({ preserveDraft: true }); });

  input.addEventListener('input', function () {
    localStorage.setItem(storageKey(), input.value);
    setStatus('草稿已自动保存在当前浏览器。', 'success');
    window.clearTimeout(metricHandle);
    metricHandle = window.setTimeout(function () { updateMetrics(false); }, 160);
  });

  resetButton.addEventListener('click', async function () {
    if (input.value && !window.confirm('清空当前输入并重新计时吗？当前浏览器草稿也会被清除。')) return;
    localStorage.removeItem(storageKey());
    stopAttempt();
    attemptId = null;
    startedAt = null;
    timerMetric.textContent = '00:00';
    await beginAttempt({ preserveDraft: false });
  });

  finishButton.addEventListener('click', async function () {
    finishButton.disabled = true;
    setStatus('正在计算并保存本次结果……');
    const seconds = elapsedSeconds();
    if (staffMode && attemptId == null) {
      const words = countWords(input.value);
      const localRecord = {
        completed_at: '本次（课堂）',
        band: selectedBand,
        typed_word_count: words,
        target_word_count: essayData[selectedBand].word_count,
        speed_wpm: (words * 60 / Math.max(1, seconds)).toFixed(1),
        accuracy: accuracy(input.value, true).toFixed(1)
      };
      accuracyMetric.textContent = localRecord.accuracy;
      addHistoryRow(localRecord);
      localStorage.removeItem(storageKey());
      stopAttempt();
      setStatus('本次课堂练习已完成；结果仅显示在本页，不写入学生记录。', 'success');
      return;
    }
    try {
      const response = await fetch('/writing/api/' + encodeURIComponent(exerciseId) + '/typing/' + attemptId + '/finish', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ band: selectedBand, typed_text: input.value, task_id: assignedTaskId || null })
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'finish_failed');
      wordMetric.textContent = data.attempt.typed_word_count;
      targetWordMetric.textContent = '/ ' + data.attempt.target_word_count;
      speedMetric.textContent = Number(data.attempt.speed_wpm || 0).toFixed(1);
      accuracyMetric.textContent = Number(data.attempt.accuracy || 0).toFixed(1);
      timerMetric.textContent = formatTime(data.attempt.duration_seconds || seconds);
      addHistoryRow(data.attempt);
      localStorage.removeItem(storageKey());
      stopAttempt();
      setStatus(data.task_completed ? '本次结果已保存，助教布置的任务已自动提交。' : '本次结果已保存到学生记录。', 'success');
    } catch (_error) {
      finishButton.disabled = false;
      setStatus('保存失败，输入内容仍保留在当前浏览器，请重试。', 'error');
    }
  });

  setBand(selectedBand);
})();
