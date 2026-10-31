(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.TaskPlannerSeriesClient = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  var API = '/api/task-planner';
  var DAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
  var STATUSES = { draft: '整批草稿', ready: '已确认', cancelled: '已取消', published: '已布置', blocked: '需要处理', failed: '执行失败' };
  var SEQUENCE_KINDS = ['listening_test', 'reading_passage', 'intensive'];

  function dateValue(value) {
    var date = new Date(value + 'T12:00:00Z');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) throw new Error('请填写有效日期。');
    return date;
  }
  function periodEnd(start, days) {
    var date = dateValue(start);
    if (!Number.isInteger(Number(days)) || Number(days) < 1 || Number(days) > 31) throw new Error('每次连续安排为1–31天。');
    date.setUTCDate(date.getUTCDate() + Number(days) - 1);
    return date.toISOString().slice(0, 10);
  }
  function dateBounds(today, start) {
    var limit = dateValue(today);
    limit.setUTCDate(limit.getUTCDate() + 90);
    var max = limit.toISOString().slice(0, 10), lineMax = periodEnd(start, 31);
    return { start_min: today, start_max: max, end_min: start, end_max: lineMax < max ? lineMax : max };
  }
  function validateDateWindow(today, start, end) {
    var bounds = dateBounds(today, start);
    dateValue(end);
    if (start < today || start > bounds.start_max || end < today || end > bounds.start_max) throw new Error('开始和结束日期须在' + today + '至' + bounds.start_max + '内（未来90天）。请提前开始日期或缩短安排时间。');
    return bounds;
  }
  function scheduleDays(start, end, quotas, kind) {
    var from = dateValue(start), to = dateValue(end), max = kind === 'dictation' ? 1200 : 20;
    var count = (to - from) / 86400000 + 1;
    if (count < 1 || count > 31) throw new Error('结束日期须在开始日期之后或当天，每次最多31天。');
    if (!Array.isArray(quotas) || quotas.length !== 7 || quotas.some(function (n) { return n === '' || !Number.isInteger(Number(n)) || Number(n) < 0 || Number(n) > max; })) throw new Error('请填写周一至周日的整数配额（0–' + max + '）。');
    var rows = [];
    for (var index = 0; index < count; index++) {
      var amount = Number(quotas[(from.getUTCDay() + 6) % 7]);
      if (amount > 0) rows.push({ target_date: from.toISOString().slice(0, 10), unit_count: amount });
      from.setUTCDate(from.getUTCDate() + 1);
    }
    if (!rows.length) throw new Error('这个日期范围每天都为0，请至少安排一天的学习量。');
    return rows;
  }
  function kindUnit(kind, selection) {
    if (kind === 'dictation') return '词';
    if (kind === 'question_type') return '组';
    if (kind === 'listening_test' && !(selection || {}).section_number) return '套';
    return '篇';
  }
  function quotaSummary(quotas, kind, unit) {
    return (quotas || []).map(function (n, index) { return DAYS[index] + ' ' + (Number(n) ? n + (unit || kindUnit(kind)) : '休息'); }).join(' · ');
  }
  function previewSummary(preview) {
    return preview.start_date + ' 至 ' + preview.end_date + ' · ' + preview.totals.days + '个学习日 · ' + preview.rows.length + '次任务 · 共' + preview.totals.units + (preview.quota_unit || kindUnit(preview.kind, preview.selection)) + '；休息日不生成任务。';
  }
  function sequenceSelection(fields) {
    var reading = fields.kind === 'reading_passage', field = reading ? 'passage_number' : 'section_number';
    var value = fields[field], number = value === '' || value === null || value === undefined ? null : Number(value);
    if (number !== null && (!Number.isInteger(number) || number < 1 || number > (reading ? 3 : 4))) throw new Error(reading ? '请选择全部篇章或Passage 1–3。' : '请选择全部范围或Part 1–4。');
    var selection = {}; selection[field] = number;
    if (fields.kind === 'intensive') selection.training_mode = fields.training_mode || 'system';
    return selection;
  }
  function selectedScopes(scopes) {
    if (!Array.isArray(scopes) || scopes.some(function (scope) { return typeof scope !== 'string' || !scope.trim(); })) throw new Error('请明确选择教材范围。');
    return Array.from(new Set(scopes)).sort();
  }
  function sequenceQuery(fields) {
    if (SEQUENCE_KINDS.indexOf(fields.kind) < 0) throw new Error('请选择听力、阅读整篇或精听。');
    var selection = sequenceSelection(fields), query = new URLSearchParams({ kind: fields.kind });
    Object.keys(selection).forEach(function (key) { query.set(key, selection[key] === null ? '' : String(selection[key])); });
    selectedScopes(fields.source_scopes || []).forEach(function (scope) { query.append('source_scope', scope); });
    return query.toString();
  }
  function buildPayload(fields) {
    if (!Number.isInteger(Number(fields.student_id)) || Number(fields.student_id) < 1) throw new Error('请选择学生。');
    if (!String(fields.name || '').trim()) throw new Error('请为这条学习线命名。');
    if (['question_type', 'dictation'].concat(SEQUENCE_KINDS).indexOf(fields.kind) < 0) throw new Error('请选择支持连续安排的练习内容。');
    if (fields.today) validateDateWindow(fields.today, fields.start_date, fields.end_date);
    scheduleDays(fields.start_date, fields.end_date, fields.weekday_counts, fields.kind);
    if (!Number.isInteger(Number(fields.planned_minutes)) || Number(fields.planned_minutes) < 1 || Number(fields.planned_minutes) > 180) throw new Error('每天预计用时须为1–180分钟。');
    var selection;
    if (fields.kind === 'question_type') {
      if (!fields.source_scope || !fields.start_group_id) throw new Error('请选择教材 / 试卷范围和起始题组。');
      selection = { subject: fields.subject, standard_type: fields.standard_type || 'all', pace: fields.pace || 'training' };
    } else if (fields.kind === 'dictation') {
      if (!Number.isInteger(Number(fields.book_id)) || Number(fields.book_id) < 1) throw new Error('请选择词书。');
      if (!Number.isInteger(Number(fields.word_start)) || Number(fields.word_start) < 1) throw new Error('开始词序须为正整数。');
      selection = { book_id: Number(fields.book_id), word_start: Number(fields.word_start), vocabulary_goal: fields.vocabulary_goal, dictation_mode: 'audio_to_en', dictation_order: 'sequence' };
    } else {
      if (!selectedScopes(fields.source_scopes || []).length || !String(fields.start_resource_id || '').trim()) throw new Error('请选择至少一本教材和起始内容。');
      selection = sequenceSelection(fields);
    }
    var payload = { name: String(fields.name).trim(), student_id: Number(fields.student_id), kind: fields.kind, start_date: fields.start_date, end_date: fields.end_date, weekday_counts: fields.weekday_counts.map(Number), wait_for_previous: !!fields.wait_for_previous, planned_minutes: Number(fields.planned_minutes), note: fields.note || '', selection: selection };
    if (fields.kind === 'question_type') { payload.source_scope = fields.source_scope; payload.start_group_id = fields.start_group_id; }
    if (SEQUENCE_KINDS.indexOf(fields.kind) >= 0) { payload.source_scopes = selectedScopes(fields.source_scopes); payload.start_resource_id = String(fields.start_resource_id); }
    return payload;
  }
  // A failed write keeps its request key; editing any inputs invalidates its preview.
  function createDraftSession(makeKey) {
    var serial = 0, current = null, accepted = null;
    return {
      invalidate: function () { serial++; accepted = null; },
      reset: function () { serial++; current = null; accepted = null; },
      begin: function (payload) {
        var encoded = JSON.stringify(payload);
        if (!current || current.encoded !== encoded) current = { encoded: encoded, request_key: makeKey() };
        return { serial: serial, encoded: encoded, payload: JSON.parse(encoded) };
      },
      accept: function (ticket, preview) {
        if (ticket.serial !== serial || !current || current.encoded !== ticket.encoded) return false;
        if (current.preview_hash && current.preview_hash !== preview.preview_hash) current.request_key = makeKey();
        current.preview_hash = preview.preview_hash;
        accepted = { payload: ticket.payload, preview_hash: preview.preview_hash, request_key: current.request_key };
        return true;
      },
      writePayload: function (payload) {
        if (!accepted || JSON.stringify(payload) !== JSON.stringify(accepted.payload)) throw new Error('安排已变更，请重新预览后再保存。');
        return Object.assign({}, accepted.payload, { preview_hash: accepted.preview_hash, request_key: accepted.request_key });
      }
    };
  }
  function mount(doc, win, context) {
    var $ = function (id) { return doc.getElementById(id); };
    if (!$('plannerSeriesEditor')) return null;
    var request = context.request, editor = $('plannerSeriesEditor'), details = $('plannerSeriesDetails');
    var state = { loading: 0, sources: 0, sequenceEpoch: 0, sequenceSources: [], scopes: new Set(), books: [], booksRequest: null, editorEpoch: 0, busy: false, list: [], detailEpoch: 0, detail: null };
    var session = createDraftSession(function () { return win.crypto && win.crypto.randomUUID ? win.crypto.randomUUID() : 'series-' + Date.now() + '-' + Math.random().toString(36).slice(2); });
    function node(tag, className, text) { var el = doc.createElement(tag); if (className) el.className = className; if (text !== undefined) el.textContent = String(text); return el; }
    function options(id, items, placeholder, selected) {
      var select = $(id); select.replaceChildren();
      if (placeholder) { var blank = node('option', '', placeholder); blank.value = ''; select.appendChild(blank); }
      (items || []).forEach(function (item) { var option = node('option', '', item.label || item.name); option.value = String(item.id); select.appendChild(option); });
      if (selected !== undefined) select.value = String(selected);
    }
    function message(text) { $('seriesEditorError').textContent = text || ''; $('seriesEditorError').hidden = !text; $('seriesEditorError').classList.add('is-error'); }
    function close(dialog) { if (dialog.close) dialog.close(); else dialog.removeAttribute('open'); }
    function show(dialog) { if (dialog.showModal) { if (!dialog.open) dialog.showModal(); } else dialog.setAttribute('open', ''); }
    function invalidate() {
      session.invalidate(); $('seriesPreview').hidden = true; $('seriesSaveButton').disabled = true;
      $('seriesSaveHint').textContent = '先预览并核对每天内容。保存整批草稿后，还需在学习线中确认。';
    }
    function busy(value, saving) {
      state.busy = value; $('seriesEditorFields').disabled = value; $('seriesPreviewButton').disabled = value;
      $('seriesSaveButton').disabled = true;
      $('seriesPreviewButton').textContent = value && !saving ? '正在预览…' : '预览每天内容';
      $('seriesSaveButton').textContent = value && saving ? '正在保存…' : '保存整批草稿';
    }
    function fields() {
      return { today: context.state.today, student_id: $('seriesStudent').value, name: $('seriesName').value, start_date: $('seriesStart').value, end_date: $('seriesEnd').value, kind: $('seriesKind').value, weekday_counts: DAYS.map(function (_, i) { return $('seriesQuota' + i).value; }), planned_minutes: $('seriesMinutes').value, note: $('seriesNote').value, wait_for_previous: $('seriesWait').value === 'previous', subject: $('seriesSubject').value, standard_type: $('seriesType').value, source_scope: $('seriesSource').value, start_group_id: $('seriesGroup').value, pace: $('seriesPace').value, book_id: $('seriesBook').value, word_start: $('seriesWordStart').value, vocabulary_goal: $('seriesVocabularyGoal').value, source_scopes: Array.from(state.scopes), start_resource_id: $('seriesResource').value, section_number: $('seriesPart').value, passage_number: $('seriesPart').value, training_mode: $('seriesTrainingMode').value };
    }
    function dates() {
      var preset = $('seriesPeriod').value, start = $('seriesStart').value;
      $('seriesEnd').readOnly = preset !== 'custom';
      if (!start) return;
      try {
        var bounds = dateBounds(context.state.today, start);
        $('seriesEnd').min = bounds.end_min; $('seriesEnd').max = bounds.end_max;
        if (preset !== 'custom') $('seriesEnd').value = periodEnd(start, preset);
        if ($('seriesEnd').value) validateDateWindow(context.state.today, start, $('seriesEnd').value);
        message('');
      } catch (error) { message(error.message); }
    }
    async function loadSources(withTypes) {
      var epoch = ++state.sources, subject = $('seriesSubject').value, type = $('seriesType').value || 'all', scope = $('seriesSource').value;
      options('seriesGroup', [], '正在读取起始题组…');
      $('seriesSource').disabled = true; $('seriesGroup').disabled = true;
      try {
        var query = new URLSearchParams({ subject: subject, standard_type: type });
        if (scope) query.set('source_scope', scope);
        var calls = [request(API + '/series-sources?' + query)];
        if (withTypes) calls.push(request(API + '/catalog?kind=question_type&limit=1&subject=' + encodeURIComponent(subject) + '&standard_type=all'));
        var results = await Promise.all(calls);
        if (epoch !== state.sources) return;
        options('seriesSource', results[0].sources, '请选择明确的教材或试卷', scope);
        options('seriesGroup', results[0].groups, scope ? '请选择起始题组' : '先选择教材 / 试卷');
        if (results[1] && results[1].types) options('seriesType', results[1].types, null, type);
      } catch (error) { if (epoch === state.sources) message(error.message); }
      finally { if (epoch === state.sources) { $('seriesSource').disabled = false; $('seriesGroup').disabled = false; } }
    }
    function renderScopes() {
      var container = $('seriesScopes'); container.replaceChildren();
      if (!state.sequenceSources.length) { container.appendChild(node('p', 'tp-help', '没有找到可布置的教材，请调整练习范围。')); return; }
      state.sequenceSources.forEach(function (source) {
        var label = node('label', 'tp-scope-choice'), checkbox = node('input');
        checkbox.type = 'checkbox'; checkbox.value = source.id; checkbox.checked = state.scopes.has(source.id);
        checkbox.addEventListener('change', function () {
          if (checkbox.checked) state.scopes.add(source.id); else state.scopes.delete(source.id);
          invalidate(); loadSequence();
        });
        var text = node('span', '', source.label); text.appendChild(node('small', '', source.count + '份可用内容'));
        label.appendChild(checkbox); label.appendChild(text); container.appendChild(label);
      });
    }
    async function loadSequence() {
      var kind = $('seriesKind').value;
      if (SEQUENCE_KINDS.indexOf(kind) < 0) return;
      var epoch = ++state.sequenceEpoch, scopeCount = state.scopes.size;
      options('seriesResource', [], scopeCount ? '正在读取顺序内容…' : '先选择教材范围'); $('seriesResource').disabled = true;
      $('seriesScopes').setAttribute('aria-busy', 'true'); $('seriesScopesHint').textContent = '正在读取可用内容…';
      try {
        var data = await request(API + '/sequence-sources?' + sequenceQuery(fields()));
        if (epoch !== state.sequenceEpoch || kind !== $('seriesKind').value) return;
        state.sequenceSources = data.sources || []; renderScopes();
        options('seriesResource', data.items, scopeCount ? '请选择起始内容' : '先选择教材范围');
        if (kind === 'intensive' && data.training_modes) options('seriesTrainingMode', data.training_modes, null, $('seriesTrainingMode').value);
        $('seriesScopesHint').textContent = scopeCount ? '已选' + scopeCount + '个范围 · 共' + (data.items || []).length + '份内容；起点之后按自然顺序分配。' : '请选择一本或多本教材，再指定起始内容。';
      } catch (error) {
        if (epoch === state.sequenceEpoch) { message(error.message); $('seriesScopesHint').textContent = '内容读取失败，请调整选择后重试。'; }
      } finally { if (epoch === state.sequenceEpoch) { $('seriesResource').disabled = false; $('seriesScopes').setAttribute('aria-busy', 'false'); } }
    }
    async function loadBooks() {
      if (state.books.length) return;
      if (state.booksRequest) return state.booksRequest;
      state.booksRequest = (async function () {
        var rows = [], offset = 0;
        do {
          var result = await request(API + '/catalog?kind=dictation&limit=100&offset=' + offset);
          rows = rows.concat(result.items || []); offset = rows.length;
        } while (offset < result.total && result.items && result.items.length);
        state.books = rows;
      })();
      try { await state.booksRequest; } finally { state.booksRequest = null; }
    }
    function quotaFields(resetQuotas) {
      var kind = $('seriesKind').value, vocabulary = kind === 'dictation', unit = kindUnit(kind, { section_number: $('seriesPart').value });
      $('seriesQuotaUnit').textContent = '（' + (kind === 'question_type' ? '题组' : unit) + '）';
      $('seriesQuotaHint').textContent = '每天0–' + (vocabulary ? '1200' : '20') + unit + '；填0表示休息。';
      DAYS.forEach(function (_, i) { $('seriesQuota' + i).max = vocabulary ? '1200' : '20'; if (resetQuotas) $('seriesQuota' + i).value = vocabulary ? (i < 5 ? 20 : 40) : (i < 5 ? 1 : 2); });
    }
    function kindFields(resetQuotas) {
      var kind = $('seriesKind').value, vocabulary = kind === 'dictation', question = kind === 'question_type', sequence = SEQUENCE_KINDS.indexOf(kind) >= 0;
      $('seriesQuestionFields').hidden = !question; $('seriesVocabularyFields').hidden = !vocabulary; $('seriesPaceField').hidden = !question; $('seriesSequenceFields').hidden = !sequence;
      $('seriesSource').required = question; $('seriesGroup').required = question; $('seriesBook').required = vocabulary; $('seriesResource').required = sequence;
      $('seriesTrainingField').hidden = kind !== 'intensive';
      if (sequence) {
        var reading = kind === 'reading_passage', first = kind === 'listening_test' ? '整套 Test（全部 Part）' : reading ? '全部 Passage，按篇顺序' : '全部 Part，按篇顺序';
        var parts = [{ id: '', label: first }];
        for (var n = 1; n <= (reading ? 3 : 4); n++) parts.push({ id: n, label: '只练 ' + (reading ? 'Passage ' : 'Part ') + n });
        options('seriesPart', parts, null, ''); $('seriesPartLabel').textContent = reading ? '阅读篇章范围' : '听力范围';
        $('seriesSequenceHint').textContent = '按教材、Test和篇章的自然顺序安排；同一天选多' + (kind === 'listening_test' ? '套 / 篇' : '篇') + '时，每份内容分别生成任务。';
      }
      quotaFields(resetQuotas);
    }
    function changeKind() {
      state.sources++; state.sequenceEpoch++; state.scopes.clear(); state.sequenceSources = [];
      $('seriesScopes').replaceChildren(node('p', 'tp-help', '正在读取教材…')); options('seriesResource', [], '先选择教材范围');
      kindFields(true); message('');
      if (SEQUENCE_KINDS.indexOf($('seriesKind').value) >= 0) loadSequence();
      else if ($('seriesKind').value === 'question_type') loadSources(true);
    }
    async function openEditor() {
      if (state.busy) return;
      var epoch = ++state.editorEpoch;
      state.sources++; state.sequenceEpoch++; state.scopes.clear(); state.sequenceSources = []; session.reset(); $('seriesEditorForm').reset(); message(''); invalidate();
      options('seriesStudent', context.state.students, '请选择学生', $('plannerStudent').value);
      var bounds = dateBounds(context.state.today, context.state.today);
      $('seriesStart').min = bounds.start_min; $('seriesStart').max = bounds.start_max;
      $('seriesStart').value = periodEnd(context.state.today, 2);
      options('seriesType', [{ id: 'all', label: '全部题型' }]); options('seriesSource', [], '请选择明确的教材或试卷'); options('seriesGroup', [], '先选择教材 / 试卷');
      kindFields(true); dates(); show(editor);
      $('seriesWaitHint').textContent = '默认按日期继续布置，未完成的旧任务保留原有状态。';
      $('seriesBookHint').textContent = '按词序连续安排，每天的范围会在预览中列出。';
      await Promise.all([loadSources(true), loadBooks().then(function () { if (epoch === state.editorEpoch) options('seriesBook', state.books, '请选择词书'); }).catch(function (error) { if (epoch === state.editorEpoch) message(error.message); })]);
    }
    function renderRows(container, rows, entries, unit) {
      container.replaceChildren();
      (rows || []).forEach(function (row) {
        var item = node('article', 'tp-series-day');
        var date = dateValue(row.target_date);
        item.appendChild(node('strong', 'tp-series-day-date', row.target_date + ' ' + DAYS[(date.getUTCDay() + 6) % 7]));
        var body = node('div', 'tp-series-day-body'); body.appendChild(node('p', '', row.title));
        var contentLabels = (row.content_labels || []).filter(function (label) { return label !== row.title; });
        if (contentLabels.length) {
          var labels = node('ul', 'tp-series-content-labels');
          contentLabels.forEach(function (label) { labels.appendChild(node('li', '', label)); }); body.appendChild(labels);
        }
        if (entries) {
          body.appendChild(node('span', 'tp-status tp-status-' + row.status, row.status_label || STATUSES[row.status] || row.status));
          if (row.error) body.appendChild(node('p', 'tp-entry-warning', row.error));
        } else body.appendChild(node('small', 'tp-help', row.unit_count + unit + (row.question_count ? ' · ' + row.question_count + '题' : '') + (row.segment_count ? ' · ' + row.segment_count + '句' : '')));
        item.appendChild(body); container.appendChild(item);
      });
    }
    async function preview(event) {
      event.preventDefault(); if (state.busy) return;
      message(''); var payload, ticket;
      try { payload = buildPayload(fields()); ticket = session.begin(payload); } catch (error) { message(error.message); return; }
      invalidate(); ticket = session.begin(payload); busy(true, false);
      var accepted = false;
      try {
        var result = await request(API + '/series/preview', { method: 'POST', body: payload });
        var data = result.preview;
        accepted = session.accept(ticket, data);
        if (!accepted) return;
        renderRows($('seriesPreviewRows'), data.rows, false, data.quota_unit || kindUnit(payload.kind, payload.selection));
        $('seriesPreviewSummary').textContent = previewSummary(data);
        $('seriesPreviewWarnings').replaceChildren();
        (data.warnings || []).forEach(function (warning) { $('seriesPreviewWarnings').appendChild(node('p', 'tp-entry-warning', warning)); });
        $('seriesPreview').hidden = false;
        $('seriesSaveHint').textContent = '请核对下方每天的具体内容。保存后为整批草稿，不会立即出现在学生列表。';
        $('seriesPreview').scrollIntoView({ behavior: 'smooth', block: 'start' });
      } catch (error) { message(error.message); }
      finally { busy(false, false); $('seriesSaveButton').disabled = !accepted; }
    }
    async function save() {
      if (state.busy) return;
      var payload;
      try { payload = session.writePayload(buildPayload(fields())); } catch (error) { message(error.message); return; }
      busy(true, true); message(''); var saved = false;
      try {
        var result = await request(API + '/series', { method: 'POST', body: payload }); saved = true;
        close(editor); session.reset();
        context.showMessage('已保存“' + result.series.name + '”的整批草稿。请在学习线中查看每天内容，再整批确认。');
        await context.refreshEntries();
      } catch (error) { if (saved) context.report(error); else message(error.message + (error.status ? '' : ' 保存结果可能尚未返回；可直接重试保存，系统会避免重复创建。重新预览前请先检查已有学习线。')); }
      finally { busy(false, false); $('seriesSaveButton').disabled = saved; }
    }
    function studentName(series) {
      var student = context.state.students.find(function (item) { return Number(item.id) === Number(series.student_id); });
      return series.student_name || (student && student.name) || '学生';
    }
    function actionButton(label, handler, primary) {
      var button = node('button', 'tp-button' + (primary ? ' tp-button-primary' : ''), label); button.type = 'button';
      button.addEventListener('click', function () { Promise.resolve().then(handler).catch(context.report); }); return button;
    }
    function actions(series, container) {
      if (series.status === 'draft') container.appendChild(actionButton('整批确认', function () { return mutate(series, 'confirm'); }, true));
      var pending = series.entry_count - (series.published_count || 0) - ((series.counts || {}).cancelled || 0);
      if (series.status !== 'cancelled' && pending > 0) container.appendChild(actionButton('取消未布置安排', function () { return mutate(series, 'cancel'); }));
    }
    function renderList() {
      var list = $('plannerSeriesList'); list.replaceChildren();
      if (!state.list.length) { list.appendChild(node('p', 'tp-help tp-series-empty', '还没有连续安排。新建一条学习线，即可按周一至周日设置每天的量。')); return; }
      state.list.forEach(function (series) {
        var card = node('article', 'tp-series-card'), main = node('div', 'tp-series-card-main'), top = node('div', 'tp-entry-top');
        top.appendChild(node('span', 'tp-student-name', studentName(series))); top.appendChild(node('span', 'tp-status tp-status-' + series.status, STATUSES[series.status] || series.status));
        main.appendChild(top); main.appendChild(node('h4', '', series.name));
        main.appendChild(node('p', 'tp-help', series.start_date + ' 至 ' + series.end_date + ' · ' + series.entry_count + '次安排'));
        if (series.counts) main.appendChild(node('p', 'tp-help', '已布置 ' + (series.counts.published || 0) + ' · 草稿 ' + (series.counts.draft || 0) + ' · 待布置 ' + (series.counts.ready || 0) + ' · 需处理 ' + ((series.counts.blocked || 0) + (series.counts.failed || 0))));
        main.appendChild(node('p', 'tp-help', quotaSummary(series.weekday_counts, series.kind, series.quota_unit)));
        if (series.wait_for_previous) main.appendChild(node('p', 'tp-help', '等待上一学习日全部任务有效提交；同日任务互不等待，未完成时由助教处理。'));
        var student = context.state.students.find(function (item) { return Number(item.id) === Number(series.student_id); });
        if (series.status === 'ready' && student && !student.enabled) main.appendChild(node('p', 'tp-entry-warning', '已确认，助教尚未为该学生启用自动布置。'));
        var buttons = node('div', 'tp-entry-actions'); buttons.appendChild(actionButton('查看每天内容', function () { return showDetails(series.id); })); actions(series, buttons);
        card.appendChild(main); card.appendChild(buttons); list.appendChild(card);
      });
    }
    async function refresh() {
      var epoch = ++state.loading, student = $('plannerStudent').value;
      var result = await request(API + '/series' + (student ? '?student_id=' + encodeURIComponent(student) : ''));
      if (epoch !== state.loading) return;
      state.list = result.series || []; renderList(); $('plannerSeriesNew').disabled = false;
    }
    async function showDetails(id) {
      var epoch = ++state.detailEpoch; state.detail = null; $('seriesDetailsRows').replaceChildren(node('p', 'tp-help', '正在读取每天的安排…')); $('seriesDetailsActions').replaceChildren(); show(details);
      try {
        var result = await request(API + '/series/' + id);
        if (epoch !== state.detailEpoch) return;
        state.detail = result.series; $('seriesDetailsTitle').textContent = result.series.name;
        $('seriesDetailsHint').textContent = studentName(result.series) + ' · ' + result.series.start_date + ' 至 ' + result.series.end_date + ' · ' + (STATUSES[result.series.status] || result.series.status);
        renderRows($('seriesDetailsRows'), result.entries, true); actions(result.series, $('seriesDetailsActions'));
      } catch (error) { if (epoch === state.detailEpoch) $('seriesDetailsRows').replaceChildren(node('p', 'tp-entry-warning', error.message)); }
    }
    var mutations = new Set();
    async function mutate(series, action) {
      if (mutations.has(series.id)) return;
      var text = action === 'confirm' ? '确认“' + series.name + '”的整批安排？\n核对每天内容后，将按日期自动布置。助教仍需为该学生启用自动布置。' : '取消“' + series.name + '”中尚未布置的安排？\n已经布置到学生列表的任务会保留。';
      if (!win.confirm(text)) return;
      mutations.add(series.id);
      try {
        await request(API + '/series/' + series.id + '/' + action, { method: 'POST', body: { version: series.version } });
        context.showMessage(action === 'confirm' ? '整条学习线已确认。请确认助教已为该学生启用自动布置。' : '已取消本线尚未布置的安排，已布置任务保留。');
        await context.refreshEntries();
        if (details.open && state.detail && state.detail.id === series.id) await showDetails(series.id);
      } catch (error) {
        if (error.status === 409) { await refresh(); if (details.open) await showDetails(series.id); }
        throw error;
      } finally { mutations.delete(series.id); }
    }
    $('plannerSeriesNew').addEventListener('click', function () { openEditor().catch(context.report); });
    ['seriesEditorClose', 'seriesEditorCancel'].forEach(function (id) { $(id).addEventListener('click', function () { if (!state.busy) { state.editorEpoch++; state.sources++; state.sequenceEpoch++; session.invalidate(); close(editor); } }); });
    editor.addEventListener('cancel', function (event) { if (state.busy) event.preventDefault(); else { state.editorEpoch++; state.sources++; state.sequenceEpoch++; session.invalidate(); } });
    $('seriesEditorFields').addEventListener('input', invalidate); $('seriesEditorFields').addEventListener('change', invalidate);
    $('seriesStart').addEventListener('change', dates); $('seriesPeriod').addEventListener('change', dates);
    $('seriesKind').addEventListener('change', changeKind);
    $('seriesPart').addEventListener('change', function () { state.scopes.clear(); state.sequenceSources = []; $('seriesScopes').replaceChildren(node('p', 'tp-help', '正在读取教材…')); quotaFields(false); loadSequence(); });
    $('seriesSubject').addEventListener('change', function () { options('seriesType', [{ id: 'all', label: '全部题型' }]); $('seriesSource').value = ''; loadSources(true); });
    $('seriesType').addEventListener('change', function () { $('seriesSource').value = ''; loadSources(false); });
    $('seriesSource').addEventListener('change', function () { loadSources(false); });
    $('seriesBook').addEventListener('change', function () { var book = state.books.find(function (row) { return String(row.id) === $('seriesBook').value; }); $('seriesBookHint').textContent = book ? '共' + book.word_count + '词，最大词序' + book.last_sequence + '。每天的连续范围会在预览中列出。' : '按词序连续安排，每天的范围会在预览中列出。'; });
    $('seriesWait').addEventListener('change', function () { $('seriesWaitHint').textContent = $('seriesWait').value === 'previous' ? '本线上一学习日的全部任务有效提交后才继续布置；同日任务互不等待。未完成时进入待处理，日期不会自动顺延，需要助教处理或重建剩余安排。' : '默认按日期继续布置，未完成的旧任务保留原有状态。'; });
    $('seriesEditorForm').addEventListener('submit', preview); $('seriesSaveButton').addEventListener('click', save);
    $('seriesDetailsClose').addEventListener('click', function () { state.detailEpoch++; close(details); });
    details.addEventListener('cancel', function () { state.detailEpoch++; });
    return { refresh: refresh, openEditor: openEditor, showDetails: showDetails };
  }
  return { periodEnd: periodEnd, dateBounds: dateBounds, validateDateWindow: validateDateWindow, scheduleDays: scheduleDays, kindUnit: kindUnit, quotaSummary: quotaSummary, previewSummary: previewSummary, sequenceQuery: sequenceQuery, buildPayload: buildPayload, createDraftSession: createDraftSession, mount: mount };
});
