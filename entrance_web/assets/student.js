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
          <h2 class="text-xl font-bold text-teal-700">${typeLabel[sec.section_type] || sec.section_type} · ${sec.title}</h2>
          <span class="text-xs text-gray-500">建议 ${sec.duration_minutes || '—'} 分钟</span>
        </div>
        ${sec.instructions ? `<p class="text-sm text-gray-600 mb-3">${sec.instructions}</p>` : ''}
      `;

      if (sec.section_type === 'listening' && sec.audio_url) {
        const audio = document.createElement('audio');
        audio.src = sec.audio_url;
        audio.controls = true;
        audio.className = 'w-full mb-4';
        secDiv.appendChild(audio);
      } else if (sec.section_type === 'listening') {
        const note = document.createElement('div');
        note.className = 'bg-yellow-50 border-l-4 border-yellow-400 p-3 text-sm text-gray-700 mb-4';
        note.textContent = '（本节音频尚未上传，请根据题目直接作答或联系老师）';
        secDiv.appendChild(note);
      }

      if (sec.section_type === 'reading' && sec.passage) {
        const p = document.createElement('div');
        p.className = 'bg-gray-50 rounded p-4 mb-4 whitespace-pre-wrap text-sm leading-relaxed';
        p.textContent = sec.passage;
        secDiv.appendChild(p);
      }

      sec.questions.forEach((q, qi) => {
        const qDiv = document.createElement('div');
        qDiv.className = 'q-card border border-gray-200 rounded-lg p-4 mb-3';
        const qNum = `${si + 1}.${qi + 1}`;
        let body = `<div class="font-semibold mb-2">${qNum}　${escapeHtml(q.stem)}</div>`;
        if (q.question_type === 'single_choice' && q.options) {
          body += q.options.map(opt => `
            <label class="flex items-start gap-2 py-1 cursor-pointer hover:bg-teal-50 rounded px-2">
              <input type="radio" name="q_${q.id}" value="${opt.key}" class="mt-1">
              <span><b>${opt.key}.</b> ${escapeHtml(opt.text)}</span>
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

  init();
})();
