/* Shared admin JS for entrance test pages (invitations, grade, papers) */
const API = '/api/entrance';
const $ = (id) => document.getElementById(id);

async function apiFetch(url, opts = {}) {
  const r = await fetch(url, { credentials: 'same-origin', ...opts });
  if (r.status === 401 || r.status === 302) {
    throw new Error('未登录或登录已过期，请先登录 studytracker 后台');
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok || data.ok === false) {
    throw new Error(data.error || data.message || `HTTP ${r.status}`);
  }
  return data;
}

function showAuthError(msg) {
  const box = $('auth-error') || $('error-box');
  if (box) {
    box.classList.remove('hidden');
    box.textContent = msg;
  }
}

const STATUS_LABELS = {
  pending: { text: '待开始', cls: 'bg-gray-100 text-gray-700' },
  in_progress: { text: '答题中', cls: 'bg-blue-100 text-blue-700' },
  submitted: { text: '待批改', cls: 'bg-yellow-100 text-yellow-700' },
  graded: { text: '已批改', cls: 'bg-green-100 text-green-700' },
};

const EXAM_LABELS = {
  ielts: 'IELTS', toefl: 'TOEFL', toefl_junior: 'TOEFL Junior', general: '通用英语',
};

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

// ============================================================================
// Invitations page
// ============================================================================
async function initInvitationsPage() {
  try {
    const papers = await apiFetch(`${API}/admin/papers`);
    const sel = $('paper-select');
    sel.innerHTML = '<option value="">请选择试卷</option>' +
      papers.papers.filter(p => p.is_active).map(p =>
        `<option value="${p.id}">${esc(p.title)}（${EXAM_LABELS[p.exam_type] || p.exam_type}）</option>`
      ).join('');
  } catch (e) {
    showAuthError(e.message);
    return;
  }

  $('create-form').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    const body = Object.fromEntries(fd.entries());
    body.has_studied_target = body.has_studied_target === 'true';
    if (body.student_age) body.student_age = parseInt(body.student_age, 10);
    if (body.paper_id) body.paper_id = parseInt(body.paper_id, 10);
    try {
      const res = await apiFetch(`${API}/admin/invitations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const link = `${location.origin}/entrance/student.html?token=${res.invitation.token}`;
      $('result-link').value = link;
      $('create-result').classList.remove('hidden');
      ev.target.reset();
      loadInvitations();
    } catch (e) {
      alert('创建失败：' + e.message);
    }
  });

  $('copy-btn').addEventListener('click', () => {
    const inp = $('result-link');
    inp.select();
    document.execCommand('copy');
    $('copy-btn').textContent = '已复制';
    setTimeout(() => ($('copy-btn').textContent = '复制'), 1500);
  });

  $('filter-status').addEventListener('change', loadInvitations);
  loadInvitations();
}

async function loadInvitations() {
  const status = $('filter-status').value;
  const url = status ? `${API}/admin/invitations?status=${status}` : `${API}/admin/invitations`;
  try {
    const res = await apiFetch(url);
    const tbody = $('invite-list');
    if (!res.invitations.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="p-8 text-center text-gray-400">暂无邀请</td></tr>';
      return;
    }
    tbody.innerHTML = res.invitations.map(inv => {
      const s = STATUS_LABELS[inv.status] || { text: inv.status, cls: 'bg-gray-100' };
      const link = `${location.origin}/entrance/student.html?token=${inv.token}`;
      let action = `<button class="text-teal-600 hover:underline text-xs" onclick="copyLink('${inv.token}')">复制链接</button>`;
      if (inv.attempt_id && (inv.status === 'submitted' || inv.status === 'graded')) {
        action += ` · <a href="grade.html?attempt_id=${inv.attempt_id}" class="text-teal-600 hover:underline text-xs">批改 / 查看</a>`;
      }
      return `
        <tr class="border-t hover:bg-gray-50">
          <td class="p-3">
            <div class="font-semibold">${esc(inv.student_name)}</div>
            <div class="text-xs text-gray-500">${esc(inv.student_grade || '')} ${inv.student_age ? inv.student_age + '岁' : ''}</div>
          </td>
          <td class="p-3 text-xs">${esc(inv.paper_title || '—')}<br><span class="text-gray-500">${EXAM_LABELS[inv.target_exam] || ''}</span></td>
          <td class="p-3"><span class="px-2 py-1 rounded text-xs ${s.cls}">${s.text}</span></td>
          <td class="p-3 text-xs text-gray-500">${(inv.created_at || '').slice(0, 16).replace('T', ' ')}</td>
          <td class="p-3 text-xs text-gray-500">${(inv.submitted_at || '').slice(0, 16).replace('T', ' ')}</td>
          <td class="p-3">${action}</td>
        </tr>`;
    }).join('');
  } catch (e) {
    $('invite-list').innerHTML = `<tr><td colspan="6" class="p-8 text-center text-red-500">加载失败：${esc(e.message)}</td></tr>`;
  }
}

function copyLink(token) {
  const link = `${location.origin}/entrance/student.html?token=${token}`;
  navigator.clipboard.writeText(link).then(() => alert('已复制：\n' + link));
}

// ============================================================================
// Grade page
// ============================================================================
async function initGradePage() {
  const params = new URLSearchParams(location.search);
  const attemptId = params.get('attempt_id');
  if (!attemptId) {
    $('loading').classList.add('hidden');
    $('error-box').classList.remove('hidden');
    $('error-box').textContent = '缺少 attempt_id 参数';
    return;
  }

  try {
    const res = await apiFetch(`${API}/admin/attempts/${attemptId}`);
    renderAttempt(res);
    $('pdf-link').href = `${API}/admin/attempts/${attemptId}/report.pdf`;
  } catch (e) {
    $('loading').classList.add('hidden');
    $('error-box').classList.remove('hidden');
    $('error-box').textContent = '加载失败：' + e.message;
    return;
  }

  $('grade-form').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    const body = {};
    for (const [k, v] of fd.entries()) {
      if (v === '') continue;
      body[k] = (k.endsWith('_score')) ? parseFloat(v) : v;
    }
    try {
      await apiFetch(`${API}/admin/attempts/${attemptId}/grade`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      alert('评分已保存');
    } catch (e) {
      alert('保存失败：' + e.message);
    }
  });
}

function renderAttempt(res) {
  $('loading').classList.add('hidden');
  $('content').classList.remove('hidden');

  const { invitation, attempt, paper, sections } = res;
  $('student-brief').textContent = `${invitation.student_name} · ${EXAM_LABELS[invitation.target_exam] || ''} · ${paper.title}`;

  $('auto-summary').innerHTML = `
    <div class="grid grid-cols-3 gap-2 text-center">
      <div><div class="text-xs text-gray-600">听力客观</div><div class="text-xl font-bold text-teal-700">${attempt.auto_score_listening || 0}</div></div>
      <div><div class="text-xs text-gray-600">阅读客观</div><div class="text-xl font-bold text-teal-700">${attempt.auto_score_reading || 0}</div></div>
      <div><div class="text-xs text-gray-600">客观总分</div><div class="text-xl font-bold text-teal-700">${attempt.auto_score_total_max || 0}</div></div>
    </div>
  `;

  // Prefill
  const f = $('grade-form');
  ['writing_score', 'writing_comment', 'speaking_score', 'speaking_comment', 'overall_level', 'overall_comment'].forEach(k => {
    if (attempt[k] != null) f.elements[k].value = attempt[k];
  });

  const listDiv = $('answers-list');
  listDiv.innerHTML = '';
  const typeLabel = { listening: '🎧 听力', reading: '📖 阅读', writing: '✍️ 写作' };

  sections.forEach((sec) => {
    const secHeader = document.createElement('h3');
    secHeader.className = 'font-bold text-teal-700 mt-4 border-l-4 border-teal-500 pl-3';
    secHeader.textContent = `${typeLabel[sec.section_type] || sec.section_type} · ${sec.title}`;
    listDiv.appendChild(secHeader);

    sec.questions.forEach((q, idx) => {
      const ans = { answer_text: q.student_answer, is_correct: q.is_correct };
      const card = document.createElement('div');
      card.className = 'border border-gray-200 rounded p-3 text-sm';
      let status = '';
      if (q.question_type !== 'essay') {
        status = ans.is_correct
          ? '<span class="text-green-600 font-bold">✓ 正确</span>'
          : '<span class="text-red-600 font-bold">✗ 错误</span>';
      } else {
        status = '<span class="text-yellow-600 font-bold">主观题</span>';
      }
      card.innerHTML = `
        <div class="font-semibold mb-1">${idx + 1}. ${esc(q.stem)}</div>
        ${q.options ? `<div class="text-xs text-gray-500 mb-1">${q.options.map(o => `${o.key}. ${esc(o.text)}`).join('　')}</div>` : ''}
        <div>学生作答：<b>${esc(ans.answer_text || '（未作答）')}</b>　${status}</div>
        ${q.question_type !== 'essay' ? `<div class="text-xs text-gray-500">标准答案：${esc(q.correct_answer || '')}</div>` : ''}
        ${q.reference_answer ? `<div class="text-xs text-gray-500 mt-1">参考：${esc(q.reference_answer)}</div>` : ''}
      `;
      listDiv.appendChild(card);
    });
  });
}

// ============================================================================
// Papers page (simple list + toggle)
// ============================================================================
async function initPapersPage() {
  try {
    const res = await apiFetch(`${API}/admin/papers`);
    const tbody = $('paper-list');
    if (!res.papers.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-gray-400">暂无试卷</td></tr>';
      return;
    }
    tbody.innerHTML = res.papers.map(p => `
      <tr class="border-t">
        <td class="p-3">${esc(p.title)}</td>
        <td class="p-3 text-xs">${EXAM_LABELS[p.exam_type] || p.exam_type}</td>
        <td class="p-3 text-xs">${esc(p.level || '')}</td>
        <td class="p-3">${p.is_active
          ? '<span class="px-2 py-1 rounded bg-green-100 text-green-700 text-xs">已启用</span>'
          : '<span class="px-2 py-1 rounded bg-gray-100 text-gray-700 text-xs">草稿</span>'}</td>
        <td class="p-3"><button onclick="togglePaper(${p.id})" class="text-teal-600 hover:underline text-xs">${p.is_active ? '停用' : '启用'}</button></td>
      </tr>
    `).join('');
  } catch (e) {
    showAuthError(e.message);
  }
}

async function togglePaper(id) {
  try {
    await apiFetch(`${API}/admin/papers/${id}/toggle`, { method: 'POST' });
    initPapersPage();
  } catch (e) {
    alert('操作失败：' + e.message);
  }
}
