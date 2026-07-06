(function () {
  const API = '/api/entrance';
  const params = new URLSearchParams(location.search);
  const token = params.get('token');

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

  async function fetchJson(url, opts) {
    const r = await fetch(url, opts);
    const data = await r.json().catch(() => ({}));
    if (!r.ok || data.ok === false) {
      throw new Error(data.error || data.message || `HTTP ${r.status}`);
    }
    return data;
  }

  async function init() {
    try {
      const inv = await fetchJson(`${API}/invitation/${token}`);
      if (inv.invitation.status === 'submitted' || inv.invitation.status === 'graded') {
        hide('loading');
        show('error-box');
        $('error-box').textContent = '本次测试已提交，如需重新测试请联系老师。';
        return;
      }
      renderWelcome(inv);
    } catch (e) {
      hide('loading');
      show('error-box');
      $('error-box').textContent = '加载失败：' + e.message + '（请确认链接是否正确）';
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
      <div>👤 <b>${i.student_name || '—'}</b>　${i.student_grade || ''}　${i.student_age ? i.student_age + ' 岁' : ''}</div>
      <div>🎯 目标考试：<b>${examLabel}</b>　${i.has_studied_target ? '（已系统学习）' : '（未系统学习）'}</div>
      <div>📄 试卷：<b>${inv.paper ? inv.paper.title : '—'}</b></div>
    `;
    show('welcome');
    $('btn-start').addEventListener('click', startExam);
  }

  async function startExam() {
    hide('welcome');
    show('loading');
    try {
      const data = await fetchJson(`${API}/paper/${token}`);
      paperData = data.paper;
      renderPaper(paperData);
    } catch (e) {
      hide('loading');
      show('error-box');
      $('error-box').textContent = '加载试卷失败：' + e.message;
    }
  }

  function renderPaper(paper) {
    hide('loading');
    const form = $('exam-form');
    form.innerHTML = '';

    let totalMin = 0;
    const typeLabel = { listening: '🎧 听力', reading: '📖 阅读', writing: '✍️ 写作' };

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
        secDiv.appendChild(buildOncePlayer(sec));
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

    $('duration-total').textContent = totalMin;
    $('duration-note').textContent = totalMin;
    show('timer');
    show('exam-form');
    show('exam-footer');

    // Word count for essay
    form.querySelectorAll('textarea').forEach(ta => {
      ta.addEventListener('input', () => {
        const counter = form.querySelector(`.word-count[data-for="${ta.name}"]`);
        if (counter) counter.textContent = ta.value.trim().split(/\s+/).filter(Boolean).length;
      });
    });

    $('btn-submit').addEventListener('click', submitExam);
  }

  async function submitExam() {
    if (!confirm('确认提交？提交后无法修改。')) return;
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
    $('btn-submit').disabled = true;
    $('btn-submit').textContent = '提交中...';
    try {
      await fetchJson(`${API}/submit/${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers }),
      });
      hide('exam-form');
      hide('exam-footer');
      hide('timer');
      show('done');
      window.scrollTo(0, 0);
    } catch (e) {
      alert('提交失败：' + e.message);
      $('btn-submit').disabled = false;
      $('btn-submit').textContent = '提交测试';
    }
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

  // 听力音频只允许播放一次：无原生 controls（不可拖动/回放），
  // 已播放状态按 token+section 记在 localStorage，刷新页面也不能重播。
  function buildOncePlayer(sec) {
    const playedKey = `entrance_audio_played_${token}_${sec.id}`;
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

    if (localStorage.getItem(playedKey)) {
      setDone('本段音频已播放过。如因故障未能完整收听，请联系老师重置测试。');
    } else {
      btn.textContent = '▶️ 播放听力音频（仅一次）';
      hint.textContent = '注意：音频只能播放一次，不能暂停、回放或拖动进度，请准备好后再点击。';
      btn.addEventListener('click', () => {
        btn.disabled = true;
        audio.play().then(() => {
          started = true;
          try { localStorage.setItem(playedKey, '1'); } catch (e) { /* 隐私模式降级：仅本页生效 */ }
          btn.textContent = '🎧 正在播放…';
        }).catch(() => {
          btn.disabled = false;
          hint.textContent = '播放失败，请检查网络后重试。';
        });
      });
    }

    audio.addEventListener('timeupdate', () => {
      if (started && !audio.ended) {
        hint.textContent = `正在播放 ${formatSeconds(audio.currentTime)} / ${formatSeconds(audio.duration)}`;
      }
    });
    audio.addEventListener('ended', () => {
      setDone('音频播放完毕，请继续作答。');
    });
    // 播放中途出错（如网络中断）：允许从断点继续，但不能回放
    audio.addEventListener('error', () => {
      if (!started) return;
      btn.disabled = false;
      btn.textContent = '▶️ 继续播放（从中断处）';
      hint.textContent = '播放中断，点击按钮从中断位置继续。';
      btn.onclick = () => {
        btn.disabled = true;
        audio.play().then(() => { btn.textContent = '🎧 正在播放…'; }).catch(() => {
          btn.disabled = false;
          hint.textContent = '仍然无法播放，请联系老师。';
        });
      };
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
