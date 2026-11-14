(function (root, factory) {
  'use strict';
  if (typeof module === 'object' && module.exports) module.exports = factory;
  else factory(root.document, root.fetch.bind(root), root.FormData);
})(typeof window !== 'undefined' ? window : globalThis, function mountClassroomVocabulary(doc, fetcher, FormDataClass) {
  'use strict';
  const root = doc.getElementById('classroomVocabulary');
  if (!root) return null;
  const el = id => doc.getElementById(id);
  const state = { rows: [], valid: false, busy: false, saved: false, revision: 0 };
  const sources = Array.from(doc.querySelectorAll('input[name="cvSource"]'));
  const source = () => sources.find(input => input.checked).value;

  function status(message, error) {
    el('cvStatus').textContent = message;
    el('cvStatus').classList.toggle('is-error', Boolean(error));
  }

  function controls() {
    el('cvPreview').disabled = state.busy || state.saved;
    el('cvSave').disabled = state.busy || state.saved || !state.valid || !el('cvTitle').value.trim();
    el('cvTitle').disabled = state.busy || state.saved;
    el('cvText').disabled = state.busy || state.saved;
    el('cvFile').disabled = state.busy || state.saved;
    sources.forEach(input => { input.disabled = state.busy || state.saved; });
    el('cvNew').disabled = state.busy;
  }

  function invalidate() {
    state.revision += 1;
    state.valid = false;
    state.rows = [];
    el('cvPreviewPanel').hidden = true;
    status('');
    controls();
  }

  async function request(path, options) {
    const response = await fetcher(path, Object.assign({ credentials: 'same-origin' }, options, {
      headers: Object.assign({ 'X-CSRF-Token': root.dataset.csrfToken }, options.headers || {})
    }));
    let data;
    try { data = await response.json(); }
    catch (_) { throw new Error('登录可能已过期，请重新登录后重试；当前词表仍保留在页面上。'); }
    if (!response.ok || !data.ok) throw new Error(data.message || '操作失败，请重试。');
    return data;
  }

  function renderPreview(data) {
    const body = el('cvRows');
    body.replaceChildren();
    (data.rows || []).forEach(row => {
      const tr = doc.createElement('tr');
      [row.line, row.word, row.part_of_speech, row.meaning].forEach(value => {
        const td = doc.createElement('td');
        td.textContent = value == null ? '' : String(value);
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
    const issues = el('cvIssues');
    issues.replaceChildren();
    const errors = data.errors || [];
    issues.hidden = errors.length === 0;
    if (errors.length) {
      const list = doc.createElement('ul');
      errors.forEach(error => {
        const li = doc.createElement('li');
        li.textContent = `${error.line ? '第 ' + error.line + ' 行：' : ''}${error.message}`;
        list.appendChild(li);
      });
      issues.appendChild(list);
    }
    const warnings = el('cvWarnings');
    warnings.replaceChildren();
    warnings.hidden = !(data.warnings || []).length;
    if (!warnings.hidden) {
      const list = doc.createElement('ul');
      data.warnings.forEach(warning => {
        const li = doc.createElement('li');
        li.textContent = `${warning.line ? '第 ' + warning.line + ' 行：' : ''}${warning.message}`;
        list.appendChild(li);
      });
      warnings.appendChild(list);
    }
    el('cvWordCount').textContent = `${data.word_count} 词`;
    el('cvPreviewPanel').hidden = false;
    state.rows = data.rows || [];
    state.valid = data.valid === true && errors.length === 0 && state.rows.length > 0;
    status(state.valid ? '预览完成，请核对词性和中文释义后保存。' : '请按提示修正词表，再次预览后保存。', !state.valid);
  }

  async function preview() {
    if (state.busy || state.saved) return;
    invalidate();
    const form = new FormDataClass();
    if (source() === 'file') {
      const file = el('cvFile').files[0];
      if (!file) { status('请先选择 Excel 文件。', true); return; }
      form.append('file', file);
    } else {
      if (!el('cvText').value.trim()) { status('请先粘贴三列词表。', true); return; }
      form.append('text', el('cvText').value);
    }
    const revision = state.revision;
    state.busy = true;
    controls();
    status('正在检查词表…');
    try {
      const data = await request('/api/classroom-vocabulary/preview', { method: 'POST', body: form });
      if (revision === state.revision) renderPreview(data);
    } catch (error) { status(error.message || '网络连接失败，请重试。', true); }
    finally { state.busy = false; controls(); }
  }

  async function save() {
    if (state.busy || state.saved || !state.valid) return;
    const title = el('cvTitle').value.trim();
    if (!title) { status('请填写词表名称。', true); el('cvTitle').focus(); return; }
    state.busy = true;
    controls();
    status('正在保存词表…');
    try {
      const data = await request('/api/classroom-vocabulary/books', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, rows: state.rows })
      });
      state.saved = true;
      el('cvPreviewPanel').hidden = true;
      el('cvSavedSummary').textContent = `${data.book.title} · ${data.book.word_count} 词${data.reused ? '（已保存过，直接使用原词表）' : ''}`;
      // Build the local destination from the ID; never navigate to supplied HTML or URLs.
      el('cvAssign').href = '/tasks?preset_dictation_book=' + encodeURIComponent(data.book.id);
      el('cvSuccess').hidden = false;
      status('词表已保存，尚未布置给学生。');
      el('cvAssign').focus();
    } catch (error) { status(error.message || '网络连接失败，请重试。', true); }
    finally { state.busy = false; controls(); }
  }

  el('cvPreview').addEventListener('click', preview);
  el('cvSave').addEventListener('click', save);
  el('cvTitle').addEventListener('input', controls);
  el('cvText').addEventListener('input', invalidate);
  el('cvFile').addEventListener('change', invalidate);
  sources.forEach(input => input.addEventListener('change', () => {
    el('cvTextArea').hidden = source() !== 'text';
    el('cvFileArea').hidden = source() !== 'file';
    invalidate();
  }));
  el('cvNew').addEventListener('click', () => {
    if (state.busy) return;
    state.saved = false;
    el('cvTitle').value = '';
    el('cvText').value = '';
    el('cvFile').value = '';
    el('cvSuccess').hidden = true;
    invalidate();
    el('cvTitle').focus();
  });
  controls();
  return { state, preview, save, invalidate };
});
