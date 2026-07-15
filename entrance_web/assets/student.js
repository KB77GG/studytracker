(function () {
  const API = '/api/entrance';
  const params = new URLSearchParams(location.search);
  const token = params.get('token');
  const DEVICE_KEY = 'entrance_device_id';
  const SAVE_DELAY_MS = 900;
  const HEARTBEAT_MS = 30000;

  const $ = (id) => document.getElementById(id);
  const show = (id) => $(id).classList.remove('hidden');
  const hide = (id) => $(id).classList.add('hidden');

  if (!token) {
    hide('loading');
    show('error-box');
    $('error-box').textContent = '缺少测试链接参数（token），请联系老师重新获取链接。';
    return;
  }

  let paperData = null;
  let sessionData = null;
  let saveTimer = null;
  let countdownTimer = null;
  let heartbeatTimer = null;
  let submitting = false;
  let sessionStarted = false;

  const deviceId = getOrCreateDeviceId();

  class ApiError extends Error {
    constructor(code, status, data) {
      super(code || `HTTP ${status}`);
      this.code = code;
      this.status = status;
      this.data = data || {};
    }
  }

  function getOrCreateDeviceId() {
    try {
      let value = localStorage.getItem(DEVICE_KEY);
      if (!value) {
        value = (self.crypto && crypto.randomUUID)
          ? crypto.randomUUID()
          : `device-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        localStorage.setItem(DEVICE_KEY, value);
      }
      return value;
    } catch (e) {
      return `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    }
  }

  async function fetchJson(url, opts = {}) {
    const headers = { 'X-Entrance-Device': deviceId, ...(opts.headers || {}) };
    const response = await fetch(url, { ...opts, headers });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.ok === false) {
      throw new ApiError(data.error || data.message, response.status, data);
    }
    return data;
  }

  async function init() {
    try {
      const inv = await fetchJson(`${API}/invitation/${token}`);
      if (inv.invitation.status === 'submitted' || inv.invitation.status === 'graded') {
        showFatal('本次测试已提交，如需重新测试请联系老师。');
        return;
      }
      renderWelcome(inv);
    } catch (e) {
      showFatal('加载失败：' + errorMessage(e) + '（请确认链接是否正确）');
    }
  }

  function renderWelcome(inv) {
    hide('loading');
    const i = inv.invitation;
    const examLabel = {
      ielts: 'IELTS 雅思',
      toefl: 'TOEFL 托福',
      toefl_junior: 'TOEFL Junior 小托福',
      general: '通用英语',
    }[i.target_exam] || '—';
    $('welcome-info').innerHTML = `
      <div>👤 <b>${escapeHtml(i.student_name || '—')}</b>　${escapeHtml(i.student_grade || '')}　${i.student_age ? i.student_age + ' 岁' : ''}</div>
      <div>🎯 目标考试：<b>${escapeHtml(examLabel)}</b>　${i.has_studied_target ? '（已系统学习）' : '（未系统学习）'}</div>
      <div>📄 试卷：<b>${escapeHtml(inv.paper ? inv.paper.title : '—')}</b></div>
    `;
    $('duration-note').textContent = inv.paper ? inv.paper.duration_minutes : '—';
    show('welcome');
    $('btn-start').textContent = i.status === 'in_progress' ? '恢复测试' : '开始测试';
    $('btn-start').addEventListener('click', startExam, { once: true });
  }

  async function startExam() {
    hide('welcome');
    show('loading');
    try {
      const data = await fetchJson(`${API}/session/${token}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: deviceId }),
      });
      paperData = data.paper;
      sessionData = data.session;
      sessionStarted = true;
      renderPaper(paperData, sessionData);
      installSessionLifecycle();
    } catch (e) {
      if (!handleSessionError(e, '加载试卷失败')) {
        showFatal('加载试卷失败：' + errorMessage(e) + '（请联系老师）');
      }
    }
  }

  function renderPaper(paper, session) {
    hide('loading');
    const form = $('exam-form');
    form.innerHTML = '';

    let totalMin = 0;
    const typeLabel = { listening: '🎧 听力', reading: '📖 阅读', writing: '✍️ 写作' };
    const savedAnswers = session.answers || {};

    paper.sections.forEach((sec, si) => {
      totalMin += sec.duration_minutes || 0;
      const secDiv = document.createElement('div');
      secDiv.className = 'bg-white rounded-2xl shadow p-6';
      secDiv.innerHTML = `
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-xl font-bold text-teal-700">${escapeHtml(typeLabel[sec.section_type] || sec.section_type)} · ${escapeHtml(sec.title)}</h2>
          <span class="text-xs text-gray-500">建议 ${sec.duration_minutes || '—'} 分钟</span>
        </div>
        ${sec.instructions ? `<p class="text-sm text-gray-600 mb-3 question-stem">${formatMultiline(sec.instructions)}</p>` : ''}
      `;

      if (sec.section_type === 'listening' && sec.audio_url) {
        secDiv.appendChild(buildOncePlayer(sec, session.audio_state || {}));
      } else if (sec.section_type === 'listening') {
        const note = document.createElement('div');
        note.className = 'bg-yellow-50 border-l-4 border-yellow-400 p-3 text-sm text-gray-700 mb-4';
        note.textContent = '（本节音频尚未上传，请根据题目直接作答或联系老师）';
        secDiv.appendChild(note);
      }

      if (sec.section_type === 'reading' && sec.passage) {
        const p = document.createElement('div');
        p.className = 'bg-gray-50 rounded p-4 mb-4 whitespace-pre-wrap text-sm leading-relaxed reading-passage';
        p.textContent = sec.passage;
        secDiv.appendChild(p);
      }

      sec.questions.forEach((q, qi) => {
        const qDiv = document.createElement('div');
        qDiv.className = 'q-card border border-gray-200 rounded-lg p-4 mb-3';
        const qNum = `${si + 1}.${qi + 1}`;
        const options = Array.isArray(q.options) ? q.options : [];
        let body = `<div class="font-semibold mb-2 leading-relaxed question-stem">${escapeHtml(qNum)}　${formatMultiline(q.stem)}</div>`;
        if (q.question_type === 'single_choice' && options.length) {
          body += options.map(opt => `
            <label class="flex items-start gap-2 py-1 cursor-pointer hover:bg-teal-50 rounded px-2">
              <input type="radio" name="q_${q.id}" value="${escapeHtml(optionKey(opt))}" class="mt-1">
              <span class="option-label">${formatOptionLabel(opt)}</span>
            </label>
          `).join('');
        } else if (q.question_type === 'short_answer') {
          body += `<input type="text" name="q_${q.id}" class="w-full border border-gray-300 rounded px-3 py-2 focus:border-teal-500 focus:ring-1 focus:ring-teal-500" placeholder="请输入答案">`;
        } else if (q.question_type === 'essay') {
          body += `<textarea name="q_${q.id}" rows="8" class="w-full border border-gray-300 rounded px-3 py-2 focus:border-teal-500 focus:ring-1 focus:ring-teal-500" placeholder="请在此作答..."></textarea>
            <div class="text-xs text-gray-500 mt-1">字数：<span class="word-count" data-for="q_${q.id}">0</span></div>`;
        }
        qDiv.innerHTML = body;
        secDiv.appendChild(qDiv);
      });

      form.appendChild(secDiv);
    });

    restoreAnswers(savedAnswers);
    $('duration-note').textContent = totalMin;
    show('timer');
    show('exam-form');
    show('exam-footer');
    updateSaveStatus(session.last_saved_at ? '已恢复上次答案' : '答案将自动保存', 'text-teal-700');
    startCountdown(session.remaining_seconds);

    form.addEventListener('input', onAnswerChanged);
    form.addEventListener('change', onAnswerChanged);
    updateWordCounts();
    $('btn-submit').addEventListener('click', () => submitExam(false));
  }

  function collectAnswers() {
    if (!paperData) return [];
    const form = $('exam-form');
    const answers = [];
    paperData.sections.forEach(sec => {
      sec.questions.forEach(q => {
        let val = '';
        if (q.question_type === 'single_choice') {
          const checked = form.querySelector(`input[name="q_${q.id}"]:checked`);
          val = checked ? checked.value : '';
        } else {
          const el = form.querySelector(`[name="q_${q.id}"]`);
          val = el ? el.value.trim() : '';
        }
        answers.push({ question_id: q.id, answer_text: val });
      });
    });
    return answers;
  }

  function restoreAnswers(savedAnswers) {
    const form = $('exam-form');
    Object.entries(savedAnswers || {}).forEach(([questionId, answer]) => {
      const name = `q_${questionId}`;
      const radios = form.querySelectorAll(`input[type="radio"][name="${name}"]`);
      if (radios.length) {
        radios.forEach(radio => { radio.checked = radio.value === String(answer); });
        return;
      }
      const field = form.querySelector(`[name="${name}"]`);
      if (field) field.value = String(answer || '');
    });
  }

  function onAnswerChanged() {
    updateWordCounts();
    updateSaveStatus('保存中...', 'text-gray-500');
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => saveDraft(false), SAVE_DELAY_MS);
  }

  async function saveDraft(useBeacon) {
    if (!sessionStarted || submitting) return;
    clearTimeout(saveTimer);
    const body = JSON.stringify({ device_id: deviceId, answers: collectAnswers() });
    if (useBeacon && navigator.sendBeacon) {
      navigator.sendBeacon(
        `${API}/session/${token}/save`,
        new Blob([body], { type: 'application/json' }),
      );
      return;
    }
    try {
      const data = await fetchJson(`${API}/session/${token}/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
      });
      sessionData = data.session;
      updateSaveStatus('已自动保存', 'text-teal-700');
    } catch (e) {
      if (!handleSessionError(e, '自动保存失败', true)) {
        updateSaveStatus('保存失败，请检查网络', 'text-red-600');
      }
    }
  }

  async function submitExam(autoSubmit) {
    if (submitting) return;
    if (!autoSubmit && !confirm('确认提交？提交后无法修改。')) return;
    submitting = true;
    clearTimeout(saveTimer);
    $('btn-submit').disabled = true;
    $('btn-submit').textContent = autoSubmit ? '时间到，正在提交...' : '提交中...';
    try {
      await fetchJson(`${API}/submit/${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: deviceId, answers: collectAnswers() }),
      });
      finishUi(autoSubmit ? '考试时间已结束，答案已自动提交。' : null);
    } catch (e) {
      if (e.code === 'time_expired' && e.data && e.data.attempt_id) {
        finishUi('考试时间已结束，已保存的答案已自动提交。');
        return;
      }
      submitting = false;
      if (!handleSessionError(e, '提交失败', true)) alert('提交失败：' + errorMessage(e));
      $('btn-submit').disabled = false;
      $('btn-submit').textContent = '提交测试';
    }
  }

  function finishUi(message) {
    submitting = true;
    sessionStarted = false;
    clearInterval(countdownTimer);
    clearInterval(heartbeatTimer);
    hide('exam-form');
    hide('exam-footer');
    hide('timer');
    if (message && $('done-message')) $('done-message').textContent = message;
    show('done');
    window.scrollTo(0, 0);
  }

  function installSessionLifecycle() {
    document.addEventListener('visibilitychange', async () => {
      if (!sessionStarted || submitting) return;
      if (document.hidden) {
        saveDraft(true);
        sendSessionEvent('hidden', true);
        return;
      }
      try {
        const data = await sendSessionEvent('visible', false);
        if (data && data.session) {
          sessionData = data.session;
          startCountdown(data.session.remaining_seconds);
        }
      } catch (e) {
        handleSessionError(e, '无法恢复测试');
      }
    });

    window.addEventListener('pagehide', () => {
      if (!sessionStarted || submitting) return;
      saveDraft(true);
      sendSessionEvent('hidden', true);
    });

    heartbeatTimer = setInterval(async () => {
      if (!sessionStarted || submitting || document.hidden) return;
      try {
        const data = await sendSessionEvent('heartbeat', false);
        if (data && data.session) sessionData = data.session;
      } catch (e) {
        handleSessionError(e, '会话连接异常', true);
      }
    }, HEARTBEAT_MS);
  }

  async function sendSessionEvent(event, useBeacon) {
    const body = JSON.stringify({ device_id: deviceId, event });
    if (useBeacon && navigator.sendBeacon) {
      navigator.sendBeacon(
        `${API}/session/${token}/event`,
        new Blob([body], { type: 'application/json' }),
      );
      return null;
    }
    return fetchJson(`${API}/session/${token}/event`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });
  }

  function startCountdown(initialSeconds) {
    let remaining = Math.max(0, Number(initialSeconds || 0));
    clearInterval(countdownTimer);
    renderCountdown(remaining);
    countdownTimer = setInterval(() => {
      remaining = Math.max(0, remaining - 1);
      renderCountdown(remaining);
      if (remaining <= 0) {
        clearInterval(countdownTimer);
        submitExam(true);
      }
    }, 1000);
  }

  function renderCountdown(seconds) {
    if (!$('remaining-time')) return;
    $('remaining-time').textContent = formatSeconds(seconds);
    $('remaining-time').className = seconds <= 300 ? 'font-bold text-red-600' : 'font-bold text-teal-700';
  }

  function updateSaveStatus(text, cls) {
    if (!$('save-status')) return;
    $('save-status').textContent = text;
    $('save-status').className = `text-xs ${cls || 'text-gray-500'}`;
  }

  function updateWordCounts() {
    const form = $('exam-form');
    form.querySelectorAll('textarea').forEach(ta => {
      const counter = form.querySelector(`.word-count[data-for="${ta.name}"]`);
      if (counter) counter.textContent = ta.value.trim().split(/\s+/).filter(Boolean).length;
    });
  }

  function handleSessionError(error, prefix, quiet) {
    const messages = {
      device_changed: '检测到更换设备，测试已锁定。请联系老师解锁后继续。',
      left_too_long: '离开测试页面超过2分钟，测试已锁定。请联系老师解锁后继续。',
      session_interrupted: '测试连接中断超过2分钟，测试已锁定。请联系老师解锁后继续。',
      session_locked: '测试已锁定，请联系老师解锁后继续。',
      time_expired: '考试时间已结束，已保存答案将自动提交。',
      audio_already_started: '本段音频已经播放过，不能重复播放。',
    };
    const message = messages[error.code];
    if (!message) return false;
    if (error.code === 'time_expired' && error.data && error.data.attempt_id) {
      finishUi(message);
      return true;
    }
    if (['device_changed', 'left_too_long', 'session_interrupted', 'session_locked'].includes(error.code)) {
      lockUi(message);
      return true;
    }
    if (!quiet) alert(`${prefix}：${message}`);
    return true;
  }

  function lockUi(message) {
    sessionStarted = false;
    clearInterval(countdownTimer);
    clearInterval(heartbeatTimer);
    hide('loading');
    hide('welcome');
    hide('exam-form');
    hide('exam-footer');
    hide('timer');
    show('session-locked');
    $('session-locked-message').textContent = message;
  }

  function showFatal(message) {
    hide('loading');
    hide('welcome');
    hide('exam-form');
    hide('exam-footer');
    hide('timer');
    show('error-box');
    $('error-box').textContent = message;
  }

  function errorMessage(error) {
    return error && (error.code || error.message) ? (error.code || error.message) : '未知错误';
  }

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  function formatMultiline(s) {
    return String(s || '').split('\n').map(line => {
      const match = line.match(/^\[image:(.+)\]$/);
      if (match) {
        const src = match[1].trim();
        return `<img src="${escapeHtml(src)}" alt="" class="mt-2 mb-2 max-w-full rounded border border-gray-200">`;
      }
      return escapeHtml(line);
    }).join('<br>');
  }

  function formatSeconds(sec) {
    if (!isFinite(sec) || sec < 0) return '--:--';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  function buildOncePlayer(sec, audioState) {
    const wrap = document.createElement('div');
    wrap.className = 'bg-teal-50 border border-teal-100 rounded-lg p-3 mb-4';

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'w-full bg-teal-600 hover:bg-teal-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-2 rounded';

    const hint = document.createElement('div');
    hint.className = 'text-xs text-gray-500 mt-2 text-center';

    const audio = document.createElement('audio');
    audio.src = sec.audio_url;
    audio.preload = 'auto';
    let started = false;

    function setDone(text) {
      btn.disabled = true;
      btn.textContent = '🎧 音频已播放';
      hint.textContent = text || '每段音频只能播放一次。';
    }

    if (audioState[String(sec.id)]) {
      setDone('服务端记录显示本段音频已播放。如遇技术故障，请联系老师处理。');
    } else {
      btn.textContent = '▶️ 播放听力音频（仅一次）';
      hint.textContent = '音频播放状态由服务端记录，换设备也不能重播。';
      btn.addEventListener('click', async () => {
        btn.disabled = true;
        try {
          await fetchJson(`${API}/session/${token}/audio/${sec.id}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_id: deviceId }),
          });
          await audio.play();
          started = true;
          btn.textContent = '🎧 正在播放…';
        } catch (e) {
          if (e.code === 'audio_already_started') {
            setDone('本段音频已经播放过。');
          } else if (!handleSessionError(e, '音频播放失败', true)) {
            setDone('播放授权或播放失败，请联系老师处理。');
          }
        }
      }, { once: true });
    }

    audio.addEventListener('timeupdate', () => {
      if (started && !audio.ended) {
        hint.textContent = `正在播放 ${formatSeconds(audio.currentTime)} / ${formatSeconds(audio.duration)}`;
      }
    });
    audio.addEventListener('ended', () => setDone('音频播放完毕，请继续作答。'));
    audio.addEventListener('error', () => {
      if (started) setDone('播放中断，服务端已记录为播放过，请联系老师处理。');
    });

    wrap.appendChild(btn);
    wrap.appendChild(hint);
    wrap.appendChild(audio);
    return wrap;
  }

  function optionKey(opt) {
    return String((opt && (opt.key || opt.title)) || '');
  }

  function optionText(opt) {
    return String((opt && (opt.text || opt.content)) || '');
  }

  function formatOptionLabel(opt) {
    const rawKey = optionKey(opt);
    const key = escapeHtml(rawKey);
    const text = escapeHtml(stripOptionKeyPrefix(rawKey, optionText(opt)));
    return text ? `<b>${key}.</b> ${text}` : `<b>${key}</b>`;
  }

  function stripOptionKeyPrefix(key, text) {
    const escapedKey = String(key || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return String(text || '').trim().replace(new RegExp(`^\\s*${escapedKey}\\s*[.．、)]\\s*`, 'i'), '');
  }

  init();
})();
