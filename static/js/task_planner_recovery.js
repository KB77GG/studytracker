(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.TaskPlannerRecoveryClient = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  var API = '/api/task-planner/inbox';
  var ACTIONS = {
    makeup: { title: '补做并顺延', confirm: '确认补做并顺延', description: '今天只安排这次补做；当前学习线从今天起尚未发布的新任务整体按天后移。星期可能变化，请核对下面的新日期。其他学习线、已发布任务和旧成绩保留。' },
    continue: { title: '忽略本次，继续原计划', confirm: '确认忽略本次', description: '只放过本次未完成，后续继续原日期计划。旧任务不会被标为已完成，成绩不变，也不会永久关闭这条学习线的等待条件。' }
  };
  function inboxQuery(studentId, view) {
    if (!['pending', 'resolved'].includes(view)) throw new Error('请选择待处理或已处理记录。');
    var query = new URLSearchParams({ view: view });
    if (studentId !== '' && studentId !== undefined && studentId !== null) {
      if (!/^\d+$/.test(String(studentId)) || !Number.isSafeInteger(Number(studentId)) || Number(studentId) < 1) throw new Error('学生筛选无效，请刷新。');
      query.set('student_id', String(studentId));
    }
    return query.toString();
  }
  function actionPayload(item, action) {
    if (!Object.prototype.hasOwnProperty.call(ACTIONS, action)) throw new Error('请选择补做或忽略本次。');
    if (!item || !Number.isSafeInteger(Number(item.series_id)) || Number(item.series_id) < 1) throw new Error('学习线信息已失效，请刷新。');
    var sourceDate = String(item.source_date || ''), day = new Date(sourceDate + 'T12:00:00Z');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(sourceDate) || !Number.isFinite(day.getTime()) || day.toISOString().slice(0, 10) !== sourceDate) throw new Error('原任务日期无效，请刷新。');
    return { series_id: Number(item.series_id), source_date: sourceDate, action: action };
  }
  function counts(items) {
    var students = new Set(), lines = new Set(), tasks = new Set();
    (items || []).forEach(function (item) {
      students.add(String(item.student_id)); lines.add(String(item.series_id));
      (item.tasks || []).forEach(function (task) { tasks.add(String(item.student_id) + ':' + String(task.id)); });
    });
    return { students: students.size, lines: lines.size, tasks: tasks.size, cases: (items || []).length };
  }
  function groupByStudent(items) {
    var groups = new Map();
    (items || []).forEach(function (item) {
      var key = String(item.student_id);
      if (!groups.has(key)) groups.set(key, { student_id: item.student_id, student_name: item.student_name || '学生', items: [] });
      groups.get(key).items.push(item);
    });
    return Array.from(groups.values());
  }
  function canApply(preview) {
    return !!(preview && preview.can_apply === true && typeof preview.preview_hash === 'string' && preview.preview_hash && Array.isArray(preview.tasks) && Array.isArray(preview.changes) && Array.isArray(preview.blockers) && preview.blockers.length === 0);
  }
  function decisionLabel(item) {
    var decision = item.decision || {};
    var label = decision.action_label || (decision.action === 'makeup' ? '已安排补做并顺延' : decision.action === 'continue' ? '已忽略本次' : '已处理');
    return label + (decision.makeup_date ? ' · 补做日期 ' + decision.makeup_date : '') + (decision.decided_at ? ' · ' + decision.decided_at : '');
  }
  function resultMessage(response, action) {
    if (!response || response.ok !== true || !response.result) throw new Error('处理结果未确认，请保留当前预览并重试；系统会避免重复操作。');
    return response.message || (action === 'makeup' ? '已安排补做，并顺延当前学习线的未发布任务。' : '已忽略本次未完成，继续原计划。');
  }
  function mount(doc, win, context) {
    var $ = function (id) { return doc.getElementById(id); };
    if (!$('plannerRecovery') || !$('plannerRecoveryDialog')) return null;
    var dialog = $('plannerRecoveryDialog'), request = context.request;
    var sessionFactory = context.createDraftSession || (win.TaskPlannerSeriesClient && win.TaskPlannerSeriesClient.createDraftSession);
    if (!sessionFactory) return null;
    var session = sessionFactory(function () { return win.crypto && win.crypto.randomUUID ? win.crypto.randomUUID() : 'recovery-' + Date.now() + '-' + Math.random().toString(36).slice(2); });
    var gate = context.createGate();
    var state = { view: 'pending', items: [], listEpoch: 0, previewEpoch: 0, selection: null, item: null, preview: null, loading: false, applying: false };
    function node(tag, cls, text) { var el = doc.createElement(tag); if (cls) el.className = cls; if (text !== undefined) el.textContent = String(text); return el; }
    function show(dialogNode) { if (dialogNode.showModal) { if (!dialogNode.open) dialogNode.showModal(); } else dialogNode.setAttribute('open', ''); }
    function close() {
      if (state.applying) return;
      state.previewEpoch++; session.reset(); state.selection = null; state.preview = null; state.loading = false; busy(false);
      if (dialog.close) dialog.close(); else dialog.removeAttribute('open');
    }
    function dialogMessage(text, error) {
      $('recoveryDialogMessage').textContent = text || ''; $('recoveryDialogMessage').hidden = !text;
      $('recoveryDialogMessage').classList.toggle('is-error', !!error);
    }
    function busy(value) {
      state.applying = value; $('recoveryDialogClose').disabled = value; $('recoveryDialogCancel').disabled = value;
      $('recoveryRepreview').disabled = value || state.loading;
      $('recoveryApply').disabled = value || state.loading || !canApply(state.preview);
      $('recoveryApply').textContent = value ? '正在处理…' : state.selection ? ACTIONS[state.selection.action].confirm : '确认处理';
    }
    function renderTasks(container, tasks) {
      container.replaceChildren();
      (tasks || []).forEach(function (task) {
        var item = node('li', 'tp-recovery-task'), title = node('span', '', task.title || '学习任务'); item.appendChild(title);
        if (task.status_label) item.appendChild(node('small', 'tp-status', task.status_label));
        container.appendChild(item);
      });
    }
    function renderInbox() {
      var list = $('recoveryInboxList'); list.replaceChildren();
      var summary = counts(state.items), resolved = state.view === 'resolved';
      $('recoveryInboxSummary').textContent = summary.students + ' 位学生 · ' + summary.lines + ' 条学习线 · ' + summary.tasks + ' 项任务' + (resolved ? '（已处理记录）' : '待处理');
      if (!state.items.length) { list.appendChild(node('p', 'tp-help tp-recovery-empty', resolved ? '当前筛选下还没有处理记录。' : '当前没有需要处理的未完成任务。')); return; }
      groupByStudent(state.items).forEach(function (student) {
        var group = node('section', 'tp-recovery-student'); group.appendChild(node('h4', '', student.student_name));
        student.items.forEach(function (item) {
          var card = node('article', 'tp-recovery-case'), main = node('div', 'tp-recovery-case-main');
          main.appendChild(node('strong', '', item.series_name || '学习线'));
          main.appendChild(node('p', 'tp-help', '原任务日期 ' + item.source_date + ' · ' + (item.tasks || []).length + ' 项任务'));
          var tasks = node('ul', 'tp-recovery-tasks'); renderTasks(tasks, item.tasks); main.appendChild(tasks);
          if (resolved) main.appendChild(node('p', 'tp-recovery-decision', decisionLabel(item)));
          else if (item.reason || item.message) main.appendChild(node('p', 'tp-entry-warning', item.reason || item.message));
          card.appendChild(main);
          if (!resolved) {
            var buttons = node('div', 'tp-entry-actions tp-recovery-actions');
            ['makeup', 'continue'].forEach(function (action) {
              var button = node('button', 'tp-button' + (action === 'makeup' ? ' tp-button-primary' : ''), ACTIONS[action].title); button.type = 'button';
              button.addEventListener('click', function () { openPreview(item, action).catch(context.report); }); buttons.appendChild(button);
            }); card.appendChild(buttons);
          }
          group.appendChild(card);
        }); list.appendChild(group);
      });
    }
    async function refresh() {
      if (!context.state.today) return;
      var epoch = ++state.listEpoch, view = state.view;
      var student = $('plannerStudent') ? $('plannerStudent').value : '';
      state.items = [];
      $('recoveryInboxList').replaceChildren(node('p', 'tp-help tp-recovery-empty', '正在读取未完成作业…'));
      $('recoveryInboxSummary').textContent = '正在读取…';
      $('recoveryInboxError').hidden = true; $('recoveryInboxList').setAttribute('aria-busy', 'true'); $('recoveryInboxRefresh').disabled = true;
      try {
        var result = await request(API + '?' + inboxQuery(student, view));
        if (epoch !== state.listEpoch || view !== state.view) return;
        state.items = result.items || []; renderInbox();
      } catch (error) {
        if (epoch !== state.listEpoch) return;
        state.items = []; $('recoveryInboxList').replaceChildren(); $('recoveryInboxSummary').textContent = '暂时无法读取';
        $('recoveryInboxError').textContent = error.message || '读取失败，请重试。'; $('recoveryInboxError').hidden = false;
      } finally {
        if (epoch === state.listEpoch) { $('recoveryInboxList').setAttribute('aria-busy', 'false'); $('recoveryInboxRefresh').disabled = false; }
      }
    }
    function renderPreview(preview) {
      var action = ACTIONS[state.selection.action];
      $('recoveryDialogTitle').textContent = action.title;
      $('recoveryDialogContext').textContent = (state.item.student_name || '学生') + ' · ' + (state.item.series_name || '学习线') + ' · 原任务日期 ' + state.selection.source_date;
      $('recoveryDialogScope').textContent = action.description;
      $('recoveryPreviewSummary').textContent = typeof preview.summary === 'string' ? preview.summary : '请核对本次处理的任务和日期变化。';
      $('recoveryTaskHeading').textContent = state.selection.action === 'makeup' ? '今天补做的内容（' + preview.today + '）' : '本次忽略的未完成内容';
      renderTasks($('recoveryPreviewTasks'), preview.tasks);
      var changes = $('recoveryPreviewChanges'); changes.replaceChildren();
      (preview.changes || []).forEach(function (change) {
        var row = node('li', 'tp-recovery-date-change'); row.appendChild(node('span', '', change.title || '学习任务'));
        var dates = node('span', 'tp-recovery-dates'); dates.appendChild(node('time', '', change.from)); dates.appendChild(node('span', 'tp-recovery-arrow', '→')); dates.appendChild(node('time', '', change.to)); row.appendChild(dates); changes.appendChild(row);
      });
      $('recoveryChangesSection').hidden = !(preview.changes || []).length;
      var skipped = $('recoveryPreviewSkipped'); skipped.replaceChildren();
      (preview.skipped_entries || []).forEach(function (entry) { skipped.appendChild(node('li', '', entry.date + ' · ' + (entry.title || '学习任务'))); });
      $('recoverySkippedSection').hidden = !(preview.skipped_entries || []).length;
      var warnings = $('recoveryPreviewWarnings'); warnings.replaceChildren();
      (preview.warnings || []).forEach(function (warning) { warnings.appendChild(node('p', 'tp-entry-warning', warning)); });
      var blockers = $('recoveryPreviewBlockers'); blockers.replaceChildren();
      (preview.blockers || []).forEach(function (blocker) { blockers.appendChild(node('p', 'tp-recovery-blocker', blocker)); });
      if (!canApply(preview) && !(preview.blockers || []).length) blockers.appendChild(node('p', 'tp-recovery-blocker', '当前状态不允许执行，请重新预览或刷新收件箱。'));
      $('recoveryPreviewContent').hidden = false;
    }
    async function loadPreview() {
      if (!state.selection || state.applying) return;
      var epoch = ++state.previewEpoch, payload = state.selection;
      session.invalidate(); var ticket = session.begin(payload);
      state.preview = null; state.loading = true; busy(false); dialogMessage('正在核对补做内容和受影响日期…'); $('recoveryPreviewContent').hidden = true;
      try {
        var response = await request(API + '/preview', { method: 'POST', body: payload });
        if (epoch !== state.previewEpoch || state.selection !== payload) return;
        var preview = response.preview;
        if (!preview || preview.action !== payload.action || !preview.preview_hash) throw new Error('预览结果不完整，请重新预览。');
        if (!session.accept(ticket, preview)) return;
        state.preview = preview; renderPreview(preview); dialogMessage('');
      } catch (error) { if (epoch === state.previewEpoch) { session.invalidate(); state.preview = null; dialogMessage(error.message || '预览失败，请重试。', true); } }
      finally { if (epoch === state.previewEpoch) { state.loading = false; busy(false); } }
    }
    async function openPreview(item, action) {
      if (state.applying) return;
      state.selection = actionPayload(item, action); state.item = item; state.preview = null; session.reset();
      $('recoveryDialogTitle').textContent = ACTIONS[action].title;
      $('recoveryDialogContext').textContent = (item.student_name || '学生') + ' · ' + (item.series_name || '学习线');
      $('recoveryDialogScope').textContent = ACTIONS[action].description;
      show(dialog); await loadPreview();
    }
    async function apply() {
      if (state.applying || state.loading || !canApply(state.preview)) return;
      var selection = state.selection, payload;
      try { payload = session.writePayload(selection); } catch (error) { dialogMessage(error.message, true); return; }
      await gate.run('apply', async function () {
        busy(true); dialogMessage('');
        var applied = false;
        try {
          var response = await request(API + '/apply', { method: 'POST', body: payload });
          var message = resultMessage(response, selection.action); applied = true;
          busy(false); close(); context.showMessage(message);
          await context.refreshEntries();
        } catch (error) {
          if (applied) { context.report(error); return; }
          if (error.status === 409) {
            session.reset(); state.preview = null;
            dialogMessage('安排已变化，原预览不能继续执行。请点击“重新预览”后再次核对。' + (error.message ? ' ' + error.message : ''), true);
          } else dialogMessage((error.message || '请求失败。') + ' 可重试确认；系统会使用同一请求标识，避免重复补做或重复顺延。', true);
        } finally { busy(false); }
      });
    }
    ['pending', 'resolved'].forEach(function (view) {
      $('recoveryView' + (view === 'pending' ? 'Pending' : 'Resolved')).addEventListener('click', function () {
        state.view = view;
        $('recoveryViewPending').setAttribute('aria-pressed', String(view === 'pending')); $('recoveryViewResolved').setAttribute('aria-pressed', String(view === 'resolved'));
        refresh();
      });
    });
    $('recoveryInboxRefresh').addEventListener('click', refresh);
    $('recoveryRepreview').addEventListener('click', loadPreview);
    $('recoveryApply').addEventListener('click', function () { apply().catch(context.report); });
    $('recoveryDialogClose').addEventListener('click', close); $('recoveryDialogCancel').addEventListener('click', close);
    dialog.addEventListener('cancel', function (event) { event.preventDefault(); if (!state.applying) close(); });
    return { refresh: refresh, openPreview: openPreview, apply: apply };
  }
  return { inboxQuery: inboxQuery, actionPayload: actionPayload, counts: counts, groupByStudent: groupByStudent, canApply: canApply, decisionLabel: decisionLabel, resultMessage: resultMessage, mount: mount };
});
