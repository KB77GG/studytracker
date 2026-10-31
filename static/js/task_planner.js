(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else {
    root.TaskPlannerClient = api;
    if (root.document) api.mount(root.document, root);
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  var API = '/api/task-planner';
  var MUTABLE = ['draft', 'ready', 'blocked', 'failed'];
  var LABELS = { draft: '草稿', ready: '待布置', blocked: '需要处理', failed: '执行失败', published: '已布置', cancelled: '已取消' };

  function eventLabel(event) {
    var labels = { save_draft: '保存草稿', confirm: '确认安排', cancel: '取消安排', enable: '启用自动布置', disable: '暂停自动布置', blocked: '进入待处理', auto_publish: '自动布置完成', publish: '立即布置完成', failed: '布置失败' };
    var label = labels[event.action] || event.action || '操作记录';
    return label + (event.detail ? ' · ' + event.detail : '');
  }

  function addDays(value, amount) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value))) throw new Error('日期格式不正确');
    var date = new Date(value + 'T12:00:00Z');
    if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) throw new Error('日期格式不正确');
    date.setUTCDate(date.getUTCDate() + amount);
    return date.toISOString().slice(0, 10);
  }
  function canPublish(entry, today) {
    return entry.target_date === today && ['ready', 'failed'].indexOf(entry.status) !== -1;
  }
  function canConfirm(entry, today) {
    return !entry.series_managed && entry.target_date >= today && ['draft', 'blocked', 'failed'].indexOf(entry.status) !== -1;
  }
  function mutationFeedback(action, entry) {
    var expected = { publish: 'published', confirm: 'ready', cancel: 'cancelled' }[action];
    if (entry && entry.status === expected) {
      return { message: { publish: '已布置到学生任务列表。', confirm: '安排已确认。', cancel: '安排已取消。' }[action], error: false };
    }
    var detail = entry && entry.error;
    if (entry && entry.status === 'blocked') return { message: '尚未布置，已进入待处理。' + (detail || '请查看安排详情。'), error: true };
    if (entry && entry.status === 'failed') return { message: '布置未成功。' + (detail || '请查看执行记录后重试。'), error: true };
    return { message: '操作结果需要核对，请查看最新列表。' + (detail || ''), error: true };
  }
  function prerequisiteOptions(tasks, selected) {
    var options = (tasks || []).map(function (task) { return { id: task.id, label: task.date + ' · ' + task.title + ' · ' + task.status_label }; });
    var value = selected === null || selected === undefined ? '' : String(selected);
    var missing = value !== '' && !options.some(function (item) { return String(item.id) === value; });
    if (missing) options.unshift({ id: value, label: '已关联的历史任务（保留当前前置）' });
    return { options: options, selected: value, missing: missing };
  }
  function summary(entries, today) {
    var result = { tomorrow: 0, draft: 0, attention: 0, published: 0 };
    var tomorrow = addDays(today, 1);
    entries.forEach(function (entry) {
      if (entry.status === 'ready' && entry.target_date === tomorrow) result.tomorrow++;
      if (entry.status === 'draft') result.draft++;
      if (['blocked', 'failed'].indexOf(entry.status) !== -1 || (entry.target_date < today && ['draft', 'ready'].indexOf(entry.status) !== -1)) result.attention++;
      if (entry.status === 'published') result.published++;
    });
    return result;
  }
  function createGate() {
    var running = new Set();
    return {
      busy: function (key) { return running.has(key); },
      run: async function (key, action) {
        if (running.has(key)) return { skipped: true };
        running.add(key);
        try { return await action(); } finally { running.delete(key); }
      }
    };
  }
  function createRequest(fetcher, csrf) {
    return async function (path, options) {
      options = options || {};
      var method = options.method || 'GET';
      var headers = { Accept: 'application/json' };
      var init = { method: method, credentials: 'same-origin', headers: headers };
      if (method !== 'GET') {
        headers['Content-Type'] = 'application/json';
        headers['X-CSRF-Token'] = csrf();
        init.body = JSON.stringify(options.body || {});
      }
      var response;
      try { response = await fetcher(path, init); } catch (error) { throw new Error('网络连接失败，请检查网络后重试。'); }
      var data;
      try { data = await response.json(); } catch (error) { throw new Error('登录状态可能已过期，请刷新页面或重新登录。'); }
      if (!response.ok || data.ok === false) {
        var failure = new Error(data.message || data.error || '操作失败，请重试。');
        failure.status = response.status;
        failure.code = data.error;
        throw failure;
      }
      return data;
    };
  }
  function buildSelection(kind, selection, fields) {
    var chosen = Array.from(selection.values());
    if (!chosen.length) throw new Error('请先选择具体学习内容。');
    if (kind === 'question_type') return { subject: fields.subject, standard_type: fields.standard_type, group_ids: Array.from(selection.keys()), pace: fields.pace };
    var base = Object.assign({}, chosen[0].selection || {});
    if (kind === 'dictation') {
      var start = Number(fields.word_start), end = Number(fields.word_end);
      if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < start) throw new Error('请填写有效的开始和结束词序。');
      return Object.assign(base, { book_id: Number(base.book_id || chosen[0].id), word_start: start, word_end: end, vocabulary_goal: fields.vocabulary_goal, dictation_mode: base.dictation_mode || 'audio_to_en', dictation_order: base.dictation_order || 'sequence' });
    }
    if (kind === 'intensive') return Object.assign(base, { exercise_id: base.exercise_id || chosen[0].id, training_mode: fields.training_mode });
    if (kind === 'reading_passage') {
      if (!base.test_id) base.test_id = chosen[0].test_id;
      if (!base.passage_number) base.passage_number = chosen[0].passage_number;
    }
    return base;
  }
  function mount(doc, win) {
    if (!doc.getElementById('taskPlanner')) return null;
    var $ = function (id) { return doc.getElementById(id); };
    var state = { today: '', csrf: '', students: [], kinds: [], entries: [], selected: new Map(), editing: null, catalogRows: [], catalogEpoch: 0, listEpoch: 0, prerequisiteEpoch: 0, catalogTotal: 0, catalogLoading: false, saving: false };
    var gate = createGate();
    var request = createRequest(win.fetch.bind(win), function () { return state.csrf; });
    var dialog = $('plannerEditor');
    var seriesClient = win.TaskPlannerSeriesClient && win.TaskPlannerSeriesClient.mount(doc, win, { request: request, state: state, refreshEntries: loadEntries, showMessage: showMessage, report: report });
    function node(tag, className, text) {
      var item = doc.createElement(tag);
      if (className) item.className = className;
      if (text !== undefined) item.textContent = String(text);
      return item;
    }
    function option(value, label) {
      var item = node('option', '', label); item.value = String(value); return item;
    }
    function setOptions(select, items, placeholder, selected) {
      select.replaceChildren();
      if (placeholder !== null) select.appendChild(option('', placeholder));
      items.forEach(function (item) { select.appendChild(option(item.id, item.label || item.name)); });
      if (selected !== undefined && selected !== null) select.value = String(selected);
    }
    function showMessage(message, error, target) {
      var area = $(target || 'plannerMessage');
      area.textContent = message || '';
      area.hidden = !message;
      area.classList.toggle('is-error', !!error);
    }
    function report(error) { showMessage(error.message || '操作失败，请重试。', true); }
    function kindLabel(kind) {
      var item = state.kinds.find(function (row) { return row.id === kind; });
      return item ? item.label : '学习任务';
    }
    function dateLabel(date) {
      var suffix = date === state.today ? ' · 今天' : date === addDays(state.today, 1) ? ' · 明天' : '';
      return date + suffix;
    }
    function renderEnrollment() {
      var student = state.students.find(function (row) { return String(row.id) === $('plannerStudent').value; });
      $('plannerEnrollment').hidden = !student;
      if (!student) return;
      $('enrollmentTitle').textContent = student.name + ' · 自动布置' + (student.enabled ? '已启用' : '未启用');
      $('enrollmentHint').textContent = student.enabled ? '到时间只布置已确认的安排。关闭后保留草稿和已布置任务。' : '助教尚未为该学生启用自动布置。可以先保存和确认安排；由助教启用后才会自动执行。';
      $('plannerEnable').textContent = student.enabled ? '暂停自动布置' : '启用自动布置';
    }
    async function loadBootstrap() {
      var data = await request(API + '/bootstrap');
      state.today = data.today; state.csrf = data.csrf_token; state.students = data.students || []; state.kinds = data.kinds || [];
      var selected = $('plannerStudent').value;
      setOptions($('plannerStudent'), state.students, '全部学生', selected);
      setOptions($('editorStudent'), state.students, '请选择学生');
      setOptions($('editorKind'), state.kinds, null);
      $('plannerSchedule').textContent = (data.schedule_label || '每天03:05布置') + ' · 北京时间';
      $('plannerNew').disabled = false;
      if (seriesClient) $('plannerSeriesNew').disabled = false;
      $('editorDate').min = state.today;
      $('editorDate').max = addDays(state.today, 90);
      renderEnrollment();
    }
    function renderEntries(attentionCount) {
      var container = $('plannerEntries'); container.replaceChildren();
      var counts = summary(state.entries, state.today);
      $('summaryTomorrow').textContent = counts.tomorrow; $('summaryDraft').textContent = counts.draft;
      $('summaryPublished').textContent = counts.published; $('summaryAttention').textContent = attentionCount === undefined ? counts.attention : attentionCount;
      $('plannerEmpty').hidden = !!state.entries.length;
      var lastDate = '';
      state.entries.forEach(function (entry) {
        if (entry.target_date !== lastDate) {
          lastDate = entry.target_date;
          container.appendChild(node('h3', 'tp-day-heading', dateLabel(lastDate)));
        }
        var card = node('article', 'tp-entry');
        var main = node('div', 'tp-entry-main');
        var top = node('div', 'tp-entry-top');
        top.appendChild(node('span', 'tp-student-name', entry.student_name));
        top.appendChild(node('span', 'tp-kind-label', kindLabel(entry.kind)));
        var status = LABELS[entry.status] ? entry.status : 'draft';
        top.appendChild(node('span', 'tp-status tp-status-' + status, entry.status_label || LABELS[status]));
        main.appendChild(top); main.appendChild(node('h3', '', entry.title));
        main.appendChild(node('p', 'tp-entry-meta', '预计 ' + entry.planned_minutes + ' 分钟' + (entry.series_wait_for_previous ? ' · 等待本线上一项有效提交' : entry.prerequisite_task_id ? ' · 需先完成指定任务' : ' · 按指定日期布置')));
        if (entry.series_managed) {
          var seriesLink = node('button', 'tp-text-button tp-series-link', '所属学习线：' + (entry.series_name || '连续安排'));
          seriesLink.type = 'button'; seriesLink.addEventListener('click', function () { if (seriesClient) seriesClient.showDetails(entry.series_id).catch(report); }); main.appendChild(seriesLink);
          main.appendChild(node('p', 'tp-help', '在学习线中整体确认 / 取消；临时调整可取消未布置安排后重建。'));
        }
        if (entry.note) main.appendChild(node('p', 'tp-entry-note', entry.note));
        if (entry.error) main.appendChild(node('p', 'tp-entry-warning', entry.error));
        else if (entry.status === 'ready' && !entry.student_enabled) main.appendChild(node('p', 'tp-entry-warning', '已确认，助教尚未为该学生启用自动布置。筛选该学生后可以启用。'));
        var actions = node('div', 'tp-entry-actions');
        function action(label, key, className) {
          var button = node('button', 'tp-button ' + (className || ''), label); button.type = 'button';
          button.addEventListener('click', function () { handleEntryAction(entry, key).catch(report); }); actions.appendChild(button);
        }
        if (!entry.series_managed && MUTABLE.indexOf(entry.status) !== -1) action(entry.target_date < state.today ? '改期 / 编辑' : '编辑', 'edit');
        if (canConfirm(entry, state.today)) action('确认安排', 'confirm', 'tp-button-primary');
        if (canPublish(entry, state.today)) action('立即布置', 'publish', 'tp-button-primary');
        if (entry.status === 'published') {
          var link = node('a', 'tp-button', '查看任务'); link.href = '/tasks?student=' + encodeURIComponent(entry.student_name || ''); actions.appendChild(link);
        }
        action('复制安排', 'copy');
        if (!entry.series_managed && MUTABLE.indexOf(entry.status) !== -1) action('取消', 'cancel', 'tp-button-danger');
        action('记录', 'events');
        card.appendChild(main); card.appendChild(actions); container.appendChild(card);
      });
    }
    function listQuery() {
      var params = new URLSearchParams({ from: $('plannerFrom').value, to: $('plannerTo').value });
      if ($('plannerStudent').value) params.set('student_id', $('plannerStudent').value);
      if ($('plannerStatus').value) params.set('status', $('plannerStatus').value);
      return params;
    }
    async function loadEntries() {
      if (!state.today) return;
      var epoch = ++state.listEpoch;
      $('plannerLoading').hidden = false; $('plannerEmpty').hidden = true;
      $('plannerEntries').setAttribute('aria-busy', 'true');
      try {
        var params = listQuery();
        var attentionParams = new URLSearchParams(params); attentionParams.set('status', 'attention');
        var results = await Promise.all([request(API + '/entries?' + params.toString()), request(API + '/entries?' + attentionParams.toString())]);
        if (epoch !== state.listEpoch) return;
        state.entries = results[0].entries || [];
        renderEntries((results[1].entries || []).length);
        $('plannerCount').textContent = results[0].has_more ? '仅显示前500条，请缩小日期或学生范围' : state.entries.length + ' 条安排' + ($('plannerStatus').value === 'attention' ? ' · 包含此前未处理记录' : '');
        if (results[1].has_more) $('summaryAttention').textContent = '500+';
        if (seriesClient) await seriesClient.refresh();
      } finally {
        if (epoch === state.listEpoch) { $('plannerLoading').hidden = true; $('plannerEntries').setAttribute('aria-busy', 'false'); }
      }
    }
    function closeEditor() {
      if (state.saving) return;
      state.catalogEpoch++; state.prerequisiteEpoch++;
      if (dialog.close) dialog.close(); else dialog.removeAttribute('open');
    }
    function restoreSelection(entry) {
      state.selected.clear();
      if (!entry) return;
      var selection = entry.selection || {};
      if (entry.kind === 'question_type') {
        (selection.group_ids || []).forEach(function (id, index) { state.selected.set(String(id), { id: id, label: entry.title + ' · 已选题组 ' + (index + 1) }); });
      } else {
        var id = entry.kind === 'dictation' ? selection.book_id : entry.kind === 'intensive' ? selection.exercise_id : entry.kind === 'listening_test' ? selection.test_id + ':' + (selection.section_number || 'all') : selection.test_id + ':' + selection.passage_number;
        state.selected.set(String(id), { id: id, label: entry.title, selection: Object.assign({}, selection) });
      }
    }
    function updateKindFields() {
      var kind = $('editorKind').value;
      $('questionTypeFields').hidden = kind !== 'question_type'; $('paceField').hidden = kind !== 'question_type';
      $('dictationFields').hidden = kind !== 'dictation'; $('intensiveFields').hidden = kind !== 'intensive';
    }
    async function openEditor(entry, copy) {
      state.catalogEpoch++; state.prerequisiteEpoch++;
      state.editing = copy ? null : entry || null;
      $('plannerEditorForm').reset(); showMessage('', false, 'plannerEditorError');
      setOptions($('editorStudent'), state.students, '请选择学生', entry ? entry.student_id : $('plannerStudent').value);
      setOptions($('editorKind'), state.kinds, null, entry ? entry.kind : state.kinds[0] && state.kinds[0].id);
      var selection = entry && entry.selection || {};
      $('editorDate').value = entry && !copy && entry.target_date >= state.today ? entry.target_date : addDays(state.today, 1);
      $('editorMinutes').value = entry ? entry.planned_minutes : 20; $('editorNote').value = entry ? entry.note || '' : '';
      $('editorSubject').value = selection.subject || 'reading';
      setOptions($('editorType'), [{ id: selection.standard_type || 'all', label: '全部题型' }], null, selection.standard_type || 'all');
      $('editorPace').value = selection.pace || 'training'; $('editorWordStart').value = selection.word_start || 1; $('editorWordEnd').value = selection.word_end || '';
      $('editorVocabularyGoal').value = selection.vocabulary_goal || 'reading'; $('editorTrainingMode').value = selection.training_mode || 'system';
      $('plannerEditorTitle').textContent = copy ? '复制为新草稿' : entry ? '编辑安排' : '新建安排';
      restoreSelection(entry); updateKindFields(); renderSelected();
      if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', '');
      await Promise.all([loadCatalog(false), loadPrerequisites(entry && entry.prerequisite_task_id)]);
    }
    function renderSelected() {
      var container = $('editorSelected'); container.replaceChildren();
      $('editorSelectionCount').textContent = state.selected.size ? '已选 ' + state.selected.size + ($('editorKind').value === 'question_type' ? ' 个题组' : ' 份内容') : '尚未选择内容';
      state.selected.forEach(function (row, id) {
        var chip = node('span', 'tp-selected-chip'); chip.appendChild(node('span', '', row.label));
        var remove = node('button', '', '×'); remove.type = 'button'; remove.setAttribute('aria-label', '移除 ' + row.label);
        remove.addEventListener('click', function () { state.selected.delete(id); renderSelected(); renderCatalog(); });
        chip.appendChild(remove); container.appendChild(chip);
      });
    }
    function normalizeRow(row, kind) {
      var item = Object.assign({}, row); item.id = String(row.id);
      if (!item.selection) {
        if (kind === 'reading_passage') item.selection = { test_id: row.test_id, passage_number: row.passage_number };
        else if (kind === 'listening_test') item.selection = { test_id: row.test_id, section_number: row.section_number || null };
        else if (kind === 'dictation') item.selection = { book_id: Number(row.id), word_start: 1, word_end: row.last_sequence, vocabulary_goal: row.vocabulary_goal || 'reading', dictation_mode: 'audio_to_en', dictation_order: 'sequence' };
        else if (kind === 'intensive') item.selection = { exercise_id: row.id, training_mode: 'system' };
      }
      return item;
    }
    function renderCatalog() {
      var container = $('editorCatalog'); container.replaceChildren();
      if (!state.catalogRows.length) { container.appendChild(node('p', 'tp-catalog-empty', state.catalogLoading ? '正在查找内容…' : '没有找到匹配内容，请换个关键词。')); return; }
      var kind = $('editorKind').value;
      state.catalogRows.forEach(function (row) {
        var label = node('label', 'tp-catalog-row');
        var input = node('input'); input.type = kind === 'question_type' ? 'checkbox' : 'radio'; input.name = 'planner-resource'; input.checked = state.selected.has(String(row.id));
        input.addEventListener('change', function () {
          if (kind !== 'question_type') state.selected.clear();
          if (input.checked) {
            state.selected.set(String(row.id), row);
            if (kind === 'dictation') {
              $('editorWordStart').value = row.selection.word_start || 1; $('editorWordEnd').value = row.selection.word_end || row.last_sequence || '';
              $('editorVocabularyGoal').value = row.selection.vocabulary_goal || 'reading';
              $('editorBookHint').textContent = '共 ' + (row.word_count || '—') + ' 词，最大词序 ' + (row.last_sequence || '—') + '。请核对本次范围。';
            }
          } else state.selected.delete(String(row.id));
          renderSelected(); renderCatalog();
        });
        var text = node('span'); text.appendChild(node('strong', '', row.label));
        var detail = [row.unit_label, row.range, row.question_count ? row.question_count + '题' : '', row.segment_count ? row.segment_count + '句' : ''].filter(Boolean).join(' · ');
        if (detail) text.appendChild(node('small', '', detail));
        label.appendChild(input); label.appendChild(text); container.appendChild(label);
      });
    }
    async function loadCatalog(append) {
      var epoch = ++state.catalogEpoch;
      var kind = $('editorKind').value;
      var offset = append ? state.catalogRows.length : 0;
      if (!append) state.catalogRows = [];
      state.catalogLoading = true; renderCatalog(); $('editorLoadMore').disabled = true;
      var params = new URLSearchParams({ kind: kind, query: $('editorSearch').value.trim(), limit: '50', offset: String(offset) });
      if (kind === 'question_type') { params.set('subject', $('editorSubject').value); params.set('standard_type', $('editorType').value || 'all'); }
      try {
        var data = await request(API + '/catalog?' + params.toString());
        if (epoch !== state.catalogEpoch) return;
        var rows = (data.items || []).map(function (row) { return normalizeRow(row, kind); });
        state.catalogRows = append ? state.catalogRows.concat(rows) : rows; state.catalogTotal = data.total || 0;
        if (kind === 'question_type' && data.types) {
          var current = $('editorType').value || 'all'; setOptions($('editorType'), data.types, null, current);
          if (!$('editorType').value && data.types.length) $('editorType').value = data.types[0].id;
        }
        if (kind === 'intensive' && data.training_modes) setOptions($('editorTrainingMode'), data.training_modes, null, $('editorTrainingMode').value);
        rows.forEach(function (row) { if (state.selected.has(String(row.id))) state.selected.set(String(row.id), Object.assign({}, row, { selection: state.selected.get(String(row.id)).selection || row.selection })); });
        renderSelected(); $('editorLoadMore').hidden = state.catalogRows.length >= state.catalogTotal;
      } catch (error) {
        if (epoch === state.catalogEpoch) showMessage(error.message, true, 'plannerEditorError');
      } finally {
        if (epoch === state.catalogEpoch) { state.catalogLoading = false; renderCatalog(); $('editorLoadMore').disabled = false; }
      }
    }
    async function loadPrerequisites(selected) {
      var epoch = ++state.prerequisiteEpoch; var student = $('editorStudent').value;
      var initial = prerequisiteOptions([], selected);
      setOptions($('editorPrerequisite'), initial.options, '按指定日期布置', initial.selected);
      $('editorPrerequisiteHint').textContent = initial.selected ? '保留原有关联，正在读取任务信息…' : '可选已有任务作为前置；未完成时，这条安排会进入待处理。';
      if (!student) return;
      try {
        var data = await request(API + '/students/' + encodeURIComponent(student) + '/tasks');
        if (epoch !== state.prerequisiteEpoch) return;
        var current = prerequisiteOptions(data.tasks, $('editorPrerequisite').value);
        setOptions($('editorPrerequisite'), current.options, '按指定日期布置', current.selected);
        $('editorPrerequisiteHint').textContent = current.missing ? '当前前置不在最近任务列表中，关联已保留；只有主动改选才会变更。' : '可选已有任务作为前置；未完成时，这条安排会进入待处理。';
      } catch (error) {
        if (epoch === state.prerequisiteEpoch) {
          $('editorPrerequisiteHint').textContent = $('editorPrerequisite').value ? '任务列表读取失败，原有前置关联仍保留。' : '任务列表读取失败。请重选学生重试，或明确使用“按指定日期布置”。';
          showMessage(error.message + ($('editorPrerequisite').value ? ' 原有前置关联已保留，保存不会自动解除。' : ''), true, 'plannerEditorError');
        }
      }
    }
    async function handleEntryAction(entry, action) {
      if (action === 'edit' || action === 'copy') { await openEditor(entry, action === 'copy'); return; }
      if (action === 'events') {
        var log = await request(API + '/entries/' + entry.id + '/events');
        var lines = (log.events || []).map(function (event) { return new Date(event.created_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) + ' · ' + eventLabel(event); });
        win.alert(lines.join('\n') || '暂无执行记录'); return;
      }
      var confirmations = {
        confirm: '确认在 ' + entry.target_date + ' 布置给' + entry.student_name + '？\n' + entry.title + (entry.student_enabled ? '' : '\n助教尚未为该学生启用自动布置，确认后仍需由助教启用。'),
        publish: '现在将这条任务布置到' + entry.student_name + '的今日任务列表？\n' + entry.title,
        cancel: '取消这条尚未布置的安排？\n' + entry.title
      };
      if (!win.confirm(confirmations[action])) return;
      await gate.run('entry-' + entry.id, async function () {
        try {
          var result = await request(API + '/entries/' + entry.id + '/' + action, { method: 'POST', body: { version: entry.version } });
          var feedback = mutationFeedback(action, result.entry);
          showMessage(feedback.message, feedback.error);
        } catch (error) {
          if (error.status === 409) { await loadEntries(); throw new Error(error.message + ' 列表已更新，请重新查看。'); }
          throw error;
        }
        await loadEntries();
      });
    }
    async function saveEditor(event) {
      event.preventDefault();
      if (state.saving) return;
      showMessage('', false, 'plannerEditorError');
      var selection;
      try {
        selection = buildSelection($('editorKind').value, state.selected, { subject: $('editorSubject').value, standard_type: $('editorType').value, pace: $('editorPace').value, word_start: $('editorWordStart').value, word_end: $('editorWordEnd').value, vocabulary_goal: $('editorVocabularyGoal').value, training_mode: $('editorTrainingMode').value });
      } catch (error) { showMessage(error.message, true, 'plannerEditorError'); return; }
      var payload = { student_id: Number($('editorStudent').value), target_date: $('editorDate').value, kind: $('editorKind').value, selection: selection, planned_minutes: Number($('editorMinutes').value), note: $('editorNote').value, prerequisite_task_id: $('editorPrerequisite').value ? Number($('editorPrerequisite').value) : null };
      var editing = state.editing;
      if (editing) payload.version = editing.version;
      state.saving = true; $('plannerEditorFields').disabled = true; $('plannerEditorSave').disabled = true; $('plannerEditorSave').textContent = '正在保存…';
      try {
        var result = await request(API + '/entries' + (editing ? '/' + editing.id : ''), { method: editing ? 'PATCH' : 'POST', body: payload });
        state.saving = false; closeEditor();
        $('plannerFrom').value = result.entry.target_date; $('plannerTo').value = addDays(result.entry.target_date, 6); $('plannerStatus').value = '';
        showMessage('草稿已保存。请核对列表内容，再点击“确认安排”。');
        await loadEntries();
      } catch (error) {
        if (error.status === 409) {
          state.saving = false; closeEditor(); await loadEntries(); report(new Error(error.message + ' 请从最新列表重新打开。'));
        } else showMessage(error.message, true, 'plannerEditorError');
      } finally { state.saving = false; $('plannerEditorFields').disabled = false; $('plannerEditorSave').disabled = false; $('plannerEditorSave').textContent = '保存草稿'; }
    }
    function setRange(which) {
      $('plannerFrom').value = which === 'tomorrow' ? addDays(state.today, 1) : state.today;
      $('plannerTo').value = which === 'week' ? addDays(state.today, 6) : $('plannerFrom').value;
    }
    function resetCatalog() {
      state.selected.clear(); state.catalogRows = []; $('editorSearch').value = ''; renderSelected(); updateKindFields();
      loadCatalog(false);
    }
    $('plannerFilters').addEventListener('submit', function (event) { event.preventDefault(); renderEnrollment(); loadEntries().catch(report); });
    $('plannerStudent').addEventListener('change', function () { renderEnrollment(); loadEntries().catch(report); });
    $('plannerStatus').addEventListener('change', function () { loadEntries().catch(report); });
    $('plannerRefresh').addEventListener('click', function () { gate.run('refresh', async function () { await loadBootstrap(); await loadEntries(); }).catch(report); });
    ['plannerNew', 'plannerEmptyNew'].forEach(function (id) { $(id).addEventListener('click', function () { openEditor(null, false).catch(report); }); });
    ['plannerEditorClose', 'plannerEditorCancel'].forEach(function (id) { $(id).addEventListener('click', closeEditor); });
    dialog.addEventListener('cancel', function (event) { if (state.saving) event.preventDefault(); });
    $('plannerEditorForm').addEventListener('submit', saveEditor);
    $('editorKind').addEventListener('change', resetCatalog);
    $('editorSubject').addEventListener('change', function () { setOptions($('editorType'), [{ id: 'all', label: '全部题型' }], null); resetCatalog(); });
    $('editorType').addEventListener('change', resetCatalog);
    $('editorStudent').addEventListener('change', function () { loadPrerequisites(null); });
    $('editorSearchButton').addEventListener('click', function () { loadCatalog(false); });
    $('editorSearch').addEventListener('keydown', function (event) { if (event.key === 'Enter') { event.preventDefault(); loadCatalog(false); } });
    $('editorLoadMore').addEventListener('click', function () { if (!state.catalogLoading) loadCatalog(true); });
    $('editorClearSelection').addEventListener('click', function () { state.selected.clear(); renderSelected(); renderCatalog(); });
    doc.querySelectorAll('[data-range]').forEach(function (button) { button.addEventListener('click', function () { if (!state.today) return; setRange(button.dataset.range); loadEntries().catch(report); }); });
    doc.querySelectorAll('[data-summary]').forEach(function (button) { button.addEventListener('click', function () { if (!state.today) return; $('plannerStatus').value = button.dataset.summary; if (button.dataset.summary === 'ready') setRange('tomorrow'); loadEntries().catch(report); }); });
    $('plannerEnable').addEventListener('click', function () {
      var student = state.students.find(function (row) { return String(row.id) === $('plannerStudent').value; });
      if (!student) return;
      var enable = !student.enabled;
      if (!win.confirm(enable ? '为' + student.name + '启用自动布置？到时间会将已确认的安排加入学生任务列表。' : '暂停' + student.name + '的自动布置？已布置任务保持不变。')) return;
      gate.run('enable-' + student.id, async function () {
        $('plannerEnable').disabled = true;
        try { await request(API + '/students/' + student.id + '/enable', { method: 'POST', body: { enabled: enable } }); student.enabled = enable; renderEnrollment(); await loadEntries(); showMessage(enable ? '已为选中学生启用自动布置。' : '已暂停选中学生的自动布置。'); }
        finally { $('plannerEnable').disabled = false; }
      }).catch(report);
    });
    var ready = (async function () {
      try {
        await loadBootstrap();
        var params = new URLSearchParams(win.location.search);
        if (params.get('student_id')) $('plannerStudent').value = params.get('student_id');
        setRange('week'); renderEnrollment(); await loadEntries();
      } catch (error) { $('plannerLoading').hidden = true; report(error); }
    })();
    return { state: state, ready: ready, loadEntries: loadEntries, openEditor: openEditor };
  }
  return { eventLabel: eventLabel, addDays: addDays, canPublish: canPublish, canConfirm: canConfirm, mutationFeedback: mutationFeedback, prerequisiteOptions: prerequisiteOptions, summary: summary, createGate: createGate, createRequest: createRequest, buildSelection: buildSelection, mount: mount };
});
