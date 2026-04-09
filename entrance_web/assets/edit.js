/* Paper edit page — full CRUD for paper/sections/questions + audio upload */

let PAPER = null;
const paperId = new URLSearchParams(location.search).get('paper_id');

async function initEditPage() {
  if (!paperId) {
    $('loading').classList.add('hidden');
    $('error-box').classList.remove('hidden');
    $('error-box').textContent = '缺少 paper_id 参数';
    return;
  }
  await loadPaper();
  $('btn-save-paper').addEventListener('click', savePaperMeta);
  $('btn-toggle-active').addEventListener('click', toggleActive);
}

async function loadPaper() {
  try {
    const res = await apiFetch(`${API}/admin/papers/${paperId}`);
    PAPER = res.paper;
    renderPaper();
  } catch (e) {
    $('loading').classList.add('hidden');
    $('error-box').classList.remove('hidden');
    $('error-box').textContent = '加载失败：' + e.message;
  }
}

function renderPaper() {
  $('loading').classList.add('hidden');
  $('content').classList.remove('hidden');
  $('paper-brief').textContent = `${PAPER.title} · ${EXAM_LABELS[PAPER.exam_type] || ''} · ${PAPER.level || ''}`;

  const f = $('paper-form');
  f.elements.title.value = PAPER.title || '';
  f.elements.exam_type.value = PAPER.exam_type || 'general';
  f.elements.level.value = PAPER.level || '';
  f.elements.description.value = PAPER.description || '';

  const btn = $('btn-toggle-active');
  btn.textContent = PAPER.is_active ? '✓ 已启用（点击停用）' : '⊘ 未启用（点击启用）';
  btn.className = PAPER.is_active
    ? 'bg-green-100 hover:bg-green-200 text-green-800 px-4 py-1.5 rounded text-sm'
    : 'bg-gray-100 hover:bg-gray-200 px-4 py-1.5 rounded text-sm';

  renderSections();
}

function renderSections() {
  const list = $('sections-list');
  if (!PAPER.sections || !PAPER.sections.length) {
    list.innerHTML = '<div class="text-center py-8 text-gray-400 text-sm">暂无分节，点击上方按钮添加。</div>';
    return;
  }
  const typeLabel = { listening: '🎧 听力', reading: '📖 阅读', writing: '✍️ 写作' };
  list.innerHTML = PAPER.sections.map((sec, si) => `
    <details class="border border-gray-200 rounded-lg" ${si === 0 ? 'open' : ''}>
      <summary class="bg-gray-50 hover:bg-gray-100 p-3 rounded-t-lg flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="arrow text-gray-500">▶</span>
          <span class="font-semibold">${typeLabel[sec.section_type] || sec.section_type}</span>
          <span class="text-gray-600 text-sm">${esc(sec.title || '(未命名)')}</span>
          <span class="text-xs text-gray-400">· ${(sec.questions || []).length} 题</span>
        </div>
        <button onclick="event.preventDefault(); deleteSection(${sec.id})" class="text-red-500 hover:text-red-700 text-xs">删除分节</button>
      </summary>
      <div class="p-4 space-y-3">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          <div>
            <label class="block text-xs text-gray-600 mb-1">标题</label>
            <input id="sec-title-${sec.id}" value="${esc(sec.title || '')}" class="w-full border rounded px-2 py-1">
          </div>
          <div>
            <label class="block text-xs text-gray-600 mb-1">建议时长 (分钟)</label>
            <input id="sec-dur-${sec.id}" type="number" value="${sec.duration_minutes || ''}" class="w-full border rounded px-2 py-1">
          </div>
          <div class="md:col-span-2">
            <label class="block text-xs text-gray-600 mb-1">答题说明</label>
            <textarea id="sec-inst-${sec.id}" rows="2" class="w-full border rounded px-2 py-1">${esc(sec.instructions || '')}</textarea>
          </div>
          ${sec.section_type === 'reading' ? `
          <div class="md:col-span-2">
            <label class="block text-xs text-gray-600 mb-1">阅读短文</label>
            <textarea id="sec-passage-${sec.id}" rows="5" class="w-full border rounded px-2 py-1 font-mono text-xs">${esc(sec.passage || '')}</textarea>
          </div>` : ''}
          ${sec.section_type === 'listening' ? `
          <div class="md:col-span-2">
            <label class="block text-xs text-gray-600 mb-1">听力音频</label>
            <div class="flex items-center gap-2">
              <input id="sec-audio-${sec.id}" value="${esc(sec.audio_url || '')}" placeholder="/uploads/entrance/audio/xxx.mp3" class="flex-1 border rounded px-2 py-1 text-xs">
              <label class="bg-teal-50 hover:bg-teal-100 text-teal-700 px-3 py-1 rounded text-xs cursor-pointer">
                上传音频
                <input type="file" accept=".mp3,.m4a,.wav,.ogg,.aac" class="hidden" onchange="uploadAudio(event, ${sec.id})">
              </label>
            </div>
            ${sec.audio_url ? `<audio controls src="${esc(sec.audio_url)}" class="w-full mt-2"></audio>` : ''}
          </div>` : ''}
        </div>
        <div class="flex gap-2 pt-2 border-t">
          <button onclick="saveSection(${sec.id})" class="bg-teal-600 hover:bg-teal-700 text-white px-3 py-1 rounded text-xs">保存分节信息</button>
          <button onclick="createQuestion(${sec.id})" class="bg-gray-100 hover:bg-gray-200 px-3 py-1 rounded text-xs">+ 添加题目</button>
        </div>

        <!-- Questions -->
        <div class="space-y-2 pt-2">
          ${(sec.questions || []).map((q, qi) => renderQuestionCard(q, qi)).join('')}
        </div>
      </div>
    </details>
  `).join('');
}

function renderQuestionCard(q, idx) {
  let options = [];
  try { options = q.options ? (Array.isArray(q.options) ? q.options : JSON.parse(q.options)) : []; } catch (_) {}
  const qid = q.id;
  return `
    <div class="q-card border border-gray-200 rounded p-3 bg-gray-50">
      <div class="flex items-center justify-between mb-2">
        <div class="text-xs font-semibold text-gray-600">题目 #${idx + 1}</div>
        <button onclick="deleteQuestion(${qid})" class="text-red-500 hover:text-red-700 text-xs">删除</button>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-4 gap-2 text-xs">
        <div>
          <label class="block text-gray-600 mb-1">题型</label>
          <select id="q-type-${qid}" class="w-full border rounded px-2 py-1">
            <option value="single_choice" ${q.question_type === 'single_choice' ? 'selected' : ''}>单选题</option>
            <option value="short_answer" ${q.question_type === 'short_answer' ? 'selected' : ''}>简答填空</option>
            <option value="essay" ${q.question_type === 'essay' ? 'selected' : ''}>作文 / 主观题</option>
          </select>
        </div>
        <div>
          <label class="block text-gray-600 mb-1">分值</label>
          <input id="q-points-${qid}" type="number" value="${q.points || 1}" class="w-full border rounded px-2 py-1">
        </div>
        <div class="md:col-span-2">
          <label class="block text-gray-600 mb-1">标准答案（简答可用 | 分隔多个可接受答案）</label>
          <input id="q-ans-${qid}" value="${esc(q.correct_answer || '')}" class="w-full border rounded px-2 py-1">
        </div>
        <div class="md:col-span-4">
          <label class="block text-gray-600 mb-1">题干</label>
          <textarea id="q-stem-${qid}" rows="2" class="w-full border rounded px-2 py-1">${esc(q.stem || '')}</textarea>
        </div>
        <div class="md:col-span-4">
          <label class="block text-gray-600 mb-1">选项 (每行一项，格式：<code>A|选项文本</code>，单选题必填)</label>
          <textarea id="q-opts-${qid}" rows="4" class="w-full border rounded px-2 py-1 font-mono">${options.map(o => `${o.key}|${o.text}`).join('\n')}</textarea>
        </div>
        <div class="md:col-span-4">
          <label class="block text-gray-600 mb-1">参考答案 / 批改要点（作文题给老师参考）</label>
          <textarea id="q-ref-${qid}" rows="2" class="w-full border rounded px-2 py-1">${esc(q.reference_answer || '')}</textarea>
        </div>
      </div>
      <div class="mt-2">
        <button onclick="saveQuestion(${qid})" class="bg-teal-600 hover:bg-teal-700 text-white px-3 py-1 rounded text-xs">保存题目</button>
      </div>
    </div>
  `;
}

// ============================================================================
// Actions
// ============================================================================

async function savePaperMeta() {
  const f = $('paper-form');
  const body = {
    title: f.elements.title.value.trim(),
    exam_type: f.elements.exam_type.value,
    level: f.elements.level.value.trim(),
    description: f.elements.description.value.trim(),
  };
  try {
    await apiFetch(`${API}/admin/papers/${paperId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    await loadPaper();
    flash('已保存');
  } catch (e) { alert('保存失败：' + e.message); }
}

async function toggleActive() {
  try {
    await apiFetch(`${API}/admin/papers/${paperId}/toggle`, { method: 'POST' });
    await loadPaper();
  } catch (e) { alert('切换失败：' + e.message); }
}

async function createSection(type) {
  const title = prompt(`新建${type === 'listening' ? '听力' : type === 'reading' ? '阅读' : '写作'}分节的标题：`, 'Section');
  if (!title) return;
  try {
    await apiFetch(`${API}/admin/papers/${paperId}/sections`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ section_type: type, title, duration_minutes: 10 }),
    });
    await loadPaper();
  } catch (e) { alert('创建失败：' + e.message); }
}

async function saveSection(sid) {
  const body = {
    title: $(`sec-title-${sid}`).value.trim(),
    instructions: $(`sec-inst-${sid}`).value.trim(),
    duration_minutes: $(`sec-dur-${sid}`).value || null,
  };
  const passageEl = $(`sec-passage-${sid}`);
  if (passageEl) body.passage = passageEl.value;
  const audioEl = $(`sec-audio-${sid}`);
  if (audioEl) body.audio_url = audioEl.value.trim();
  try {
    await apiFetch(`${API}/admin/sections/${sid}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    flash('分节已保存');
  } catch (e) { alert('保存失败：' + e.message); }
}

async function deleteSection(sid) {
  if (!confirm('确定删除该分节及其所有题目？')) return;
  try {
    await apiFetch(`${API}/admin/sections/${sid}`, { method: 'DELETE' });
    await loadPaper();
  } catch (e) { alert('删除失败：' + e.message); }
}

async function uploadAudio(ev, sid) {
  const file = ev.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  try {
    const r = await fetch(`${API}/admin/upload/audio`, { method: 'POST', body: fd, credentials: 'same-origin' });
    const d = await r.json();
    if (!d.ok) throw new Error(d.error);
    $(`sec-audio-${sid}`).value = d.url;
    await saveSection(sid);
    await loadPaper();
    flash('音频上传成功');
  } catch (e) { alert('上传失败：' + e.message); }
}

async function createQuestion(sid) {
  try {
    await apiFetch(`${API}/admin/sections/${sid}/questions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question_type: 'single_choice', stem: '新题目', points: 1 }),
    });
    await loadPaper();
  } catch (e) { alert('创建失败：' + e.message); }
}

function parseOptionsText(text) {
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  const opts = [];
  for (const line of lines) {
    const idx = line.indexOf('|');
    if (idx < 0) continue;
    opts.push({ key: line.slice(0, idx).trim(), text: line.slice(idx + 1).trim() });
  }
  return opts;
}

async function saveQuestion(qid) {
  const qtype = $(`q-type-${qid}`).value;
  const body = {
    question_type: qtype,
    stem: $(`q-stem-${qid}`).value.trim(),
    points: parseInt($(`q-points-${qid}`).value, 10) || 1,
    correct_answer: $(`q-ans-${qid}`).value.trim(),
    reference_answer: $(`q-ref-${qid}`).value.trim(),
  };
  if (qtype === 'single_choice') {
    body.options = parseOptionsText($(`q-opts-${qid}`).value);
  } else {
    body.options = [];
  }
  try {
    await apiFetch(`${API}/admin/questions/${qid}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    flash('题目已保存');
  } catch (e) { alert('保存失败：' + e.message); }
}

async function deleteQuestion(qid) {
  if (!confirm('确定删除该题目？')) return;
  try {
    await apiFetch(`${API}/admin/questions/${qid}`, { method: 'DELETE' });
    await loadPaper();
  } catch (e) { alert('删除失败：' + e.message); }
}

// Simple toast
function flash(msg) {
  let t = document.getElementById('__flash');
  if (!t) {
    t = document.createElement('div');
    t.id = '__flash';
    t.className = 'fixed bottom-6 right-6 bg-gray-900 text-white px-4 py-2 rounded shadow-lg text-sm z-50';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.style.opacity = '1';
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity 0.3s'; }, 1800);
}
