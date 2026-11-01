(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.TaskPlannerWeeklyClient = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  var DAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
  var ACTIVITY_FIELDS = ['id', 'name', 'kind', 'selection', 'source_scope', 'start_group_id', 'source_scopes', 'start_resource_id', 'planned_minutes', 'note'];
  function copy(value) { return JSON.parse(JSON.stringify(value)); }
  function emptyWeeks() { return [0, 1].map(function () { return DAYS.map(function () { return []; }); }); }
  function anchor(start) {
    var day = new Date(start + 'T12:00:00Z');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(start) || !Number.isFinite(day.getTime()) || day.toISOString().slice(0, 10) !== start) throw new Error('请填写有效开始日期。');
    day.setUTCDate(day.getUTCDate() - (day.getUTCDay() + 6) % 7);
    return day.toISOString().slice(0, 10);
  }
  function activityFromPayload(id, name, payload) {
    var result = { id: id, name: String(name || '').trim() };
    if (!result.name || result.name.length > 80) throw new Error('请填写1至80字的练习项名称，例如“听力 P1”。');
    ACTIVITY_FIELDS.forEach(function (key) { if (key !== 'id' && key !== 'name' && payload[key] !== undefined) result[key] = copy(payload[key]); });
    return result;
  }
  function normalizedRules(activities, rules, cycleWeeks) {
    if (![1, 2].includes(Number(cycleWeeks))) throw new Error('请选择每周重复或两周轮换。');
    if (!Array.isArray(activities) || !activities.length || activities.length > 12) throw new Error('请先加入1至12个练习项。');
    var byId = new Map();
    activities.forEach(function (item) { if (!item.id || byId.has(item.id)) throw new Error('练习项标识重复，请重新添加。'); byId.set(item.id, item); });
    if (!Array.isArray(rules) || rules.length < Number(cycleWeeks)) throw new Error('请完整填写每周安排。');
    var used = new Set();
    var normalized = rules.slice(0, Number(cycleWeeks)).map(function (week) {
      if (!Array.isArray(week) || week.length !== 7) throw new Error('每周需要包含周一至周日。');
      return week.map(function (day) {
        if (!Array.isArray(day)) throw new Error('请选择当天练习项。');
        var seen = new Set();
        return day.map(function (item) {
          if (!item || !item.activity_id) throw new Error('还有未选择练习项的日期行，请选择内容或移除该行。');
          var activity = byId.get(item.activity_id), count = Number(item.quantity);
          if (!activity) throw new Error('安排引用了已移除的练习项，请重新选择。');
          if (seen.has(item.activity_id)) throw new Error('同一天的同一练习项只需添加一次，可直接调整数量。');
          seen.add(item.activity_id); used.add(item.activity_id);
          var maximum = activity.kind === 'dictation' ? 1200 : 20;
          if (!['string', 'number'].includes(typeof item.quantity) || !Number.isInteger(count) || count < 1 || count > maximum) throw new Error(activity.name + '的每天数量须为1–' + maximum + '。');
          return { activity_id: item.activity_id, quantity: count };
        });
      });
    });
    activities.forEach(function (item) { if (!used.has(item.id)) throw new Error('练习项“' + item.name + '”尚未安排到任何星期，请配置星期或移除此项。'); });
    return normalized;
  }
  function schedule(start, end, rules) {
    var first = new Date(start + 'T12:00:00Z'), last = new Date(end + 'T12:00:00Z');
    var cycleAnchor = new Date(anchor(start) + 'T12:00:00Z'), rows = [];
    if (!/^\d{4}-\d{2}-\d{2}$/.test(end) || !Number.isFinite(last.getTime()) || last.toISOString().slice(0, 10) !== end) throw new Error('请填写有效结束日期。');
    var length = (last - first) / 86400000 + 1;
    if (length < 1 || length > 31) throw new Error('每次安排为1–31天，结束日期不能早于开始日期。');
    for (var day = new Date(first); day <= last; day.setUTCDate(day.getUTCDate() + 1)) {
      var week = Math.floor((day - cycleAnchor) / (86400000 * 7)) % rules.length;
      rules[week][(day.getUTCDay() + 6) % 7].forEach(function (item) { rows.push({ target_date: day.toISOString().slice(0, 10), activity_id: item.activity_id, quantity: item.quantity }); });
    }
    if (!rows.length) throw new Error('所选日期范围没有练习，请调整日期或每周安排。');
    return rows;
  }
  function buildPayload(fields, activities, rules, cycleWeeks, series) {
    if (!Number.isInteger(Number(fields.student_id)) || Number(fields.student_id) < 1) throw new Error('请选择学生。');
    var name = String(fields.name || '').trim();
    if (!name || name.length > 120) throw new Error('请填写1至120字的安排名称。');
    if (fields.today) series.validateDateWindow(fields.today, fields.start_date, fields.end_date);
    var weeks = normalizedRules(activities, rules, cycleWeeks);
    schedule(fields.start_date, fields.end_date, weeks);
    return { kind: 'weekly', name: name, student_id: Number(fields.student_id), start_date: fields.start_date, end_date: fields.end_date, cycle_weeks: Number(cycleWeeks), activities: activities.map(function (item) { return activityFromPayload(item.id, item.name, item); }), week_rules: weeks, skip_assigned: fields.skip_assigned !== false, wait_for_previous: !!fields.wait_for_previous, planned_minutes: 20, note: '' };
  }
  function removeActivity(activities, rules, id) {
    return { activities: activities.filter(function (item) { return item.id !== id; }), week_rules: rules.map(function (week) { return week.map(function (day) { return day.filter(function (item) { return item.activity_id !== id; }); }); }) };
  }
  function exampleRules(activities) {
    var predicates = [function (item) { return item.kind === 'listening_test' && item.selection.section_number === 1; }, function (item) { return item.kind === 'reading_passage' && item.selection.passage_number === 1; }, function (item) { return item.kind === 'listening_test' && item.selection.section_number === null; }, function (item) { return item.kind === 'reading_test'; }];
    var chosen = predicates.map(function (predicate) { return activities.filter(predicate); });
    if (chosen.some(function (items) { return items.length !== 1; }) || activities.length !== 4) return null;
    var rules = emptyWeeks(), days = [0, 3, 5, 6];
    days.forEach(function (day, index) { rules[0][day] = [{ activity_id: chosen[index][0].id, quantity: 1 }]; rules[1][day] = [{ activity_id: chosen[index % 2 === 0 ? index + 1 : index - 1][0].id, quantity: 1 }]; });
    return rules;
  }
  function summary(series, unit) {
    var byId = new Map((series.activities || []).map(function (item) { return [item.id, item]; }));
    return (series.week_rules || []).map(function (week, index) {
      var days = week.map(function (day, weekday) {
        if (!day.length) return null;
        return DAYS[weekday] + ' ' + day.map(function (item) { var activity = byId.get(item.activity_id); return (activity ? activity.name : '练习') + ' × ' + item.quantity + (activity && unit ? unit(activity.kind, activity.selection) : ''); }).join('、');
      }).filter(Boolean).join('；');
      return (Number(series.cycle_weeks) === 2 ? (index ? 'B周：' : 'A周：') : '') + (days || '休息');
    }).join(' / ');
  }
  function renderSkipped(doc, container, skipped) {
    container.replaceChildren();
    if (!skipped || !skipped.length) return;
    var details = doc.createElement('details'), heading = doc.createElement('summary'), list = doc.createElement('ul');
    details.className = 'tp-skipped'; list.className = 'tp-series-content-labels';
    heading.textContent = '已跳过 ' + skipped.length + ' 份重复内容（展开查看）';
    skipped.forEach(function (item) {
      var row = doc.createElement('li');
      var labels = { assigned: '已布置', planned: '已确认待布置', selected: '本次安排中已选', history: '已有布置记录', reserved: '已有待布置安排', batch: '本次安排中已选' };
      row.textContent = (item.title || item.label || '已安排内容') + (item.reason ? ' · ' + (labels[item.reason] || item.reason) : ''); list.appendChild(row);
    });
    details.appendChild(heading); details.appendChild(list); container.appendChild(details);
  }
  function mount(doc, context) {
    var $ = function (id) { return doc.getElementById(id); }, activities = [], rules = emptyWeeks(), nextId = 1;
    function node(tag, cls, text) { var el = doc.createElement(tag); if (cls) el.className = cls; if (text !== undefined) el.textContent = text; return el; }
    function active() { return $('seriesMode').value === 'weekly'; }
    function cycle() { return Number($('seriesCycleWeeks').value); }
    function changed() { context.invalidate(); }
    function updateAnchor() {
      try { $('seriesCycleHint').textContent = '开始日期所在周（' + anchor($('seriesStart').value) + ' 起）为' + (cycle() === 2 ? ' A 周，下一周为 B 周，依次交替。' : '第一个排课周，每周重复。') + '只安排所选起止日期内的任务。'; } catch (_) { $('seriesCycleHint').textContent = '请先选择开始日期。'; }
    }
    function renderActivities() {
      var list = $('seriesActivities'); list.replaceChildren();
      $('seriesWeeklyExample').disabled = !exampleRules(activities);
      if (!activities.length) list.appendChild(node('p', 'tp-help', '尚未加入练习项。先在上方选择内容与教材，再点击“加入周安排”。'));
      activities.forEach(function (activity) {
        var card = node('div', 'tp-weekly-activity'), body = node('div'), remove = node('button', 'tp-text-button', '移除');
        body.appendChild(node('strong', '', activity.name)); body.appendChild(node('p', 'tp-help', activity._summary || activity.name));
        remove.type = 'button'; remove.setAttribute('aria-label', '移除练习项 ' + activity.name);
        remove.addEventListener('click', function () { var result = removeActivity(activities, rules, activity.id); activities = result.activities; rules = result.week_rules; changed(); render(); });
        card.appendChild(body); card.appendChild(remove); list.appendChild(card);
      });
    }
    function renderRules() {
      var container = $('seriesWeekRules'); container.replaceChildren();
      rules.slice(0, cycle()).forEach(function (week, weekIndex) {
        var block = node('section', 'tp-week-block'); block.appendChild(node('h4', '', cycle() === 2 ? (weekIndex ? 'B 周' : 'A 周') : '每周安排'));
        week.forEach(function (day, dayIndex) {
          var dayBox = node('div', 'tp-week-day'), top = node('div', 'tp-week-day-heading'); top.appendChild(node('strong', '', DAYS[dayIndex]));
          var add = node('button', 'tp-text-button', '＋ 添加'); add.type = 'button'; add.disabled = !activities.length || day.length >= 12;
          add.setAttribute('aria-label', (weekIndex ? 'B周' : 'A周') + DAYS[dayIndex] + '添加练习');
          add.addEventListener('click', function () { day.push({ activity_id: '', quantity: 1 }); changed(); renderRules(); }); top.appendChild(add); dayBox.appendChild(top);
          if (!day.length) dayBox.appendChild(node('p', 'tp-help', '休息'));
          day.forEach(function (entry, entryIndex) {
            var row = node('div', 'tp-week-rule'), choiceLabel = node('label', 'tp-field'), choice = node('select');
            choiceLabel.appendChild(node('span', 'tp-sr-only', DAYS[dayIndex] + '练习项')); var blank = node('option', '', '请选择练习项'); blank.value = ''; choice.appendChild(blank);
            activities.forEach(function (activity) { var option = node('option', '', activity.name); option.value = activity.id; choice.appendChild(option); }); choice.value = entry.activity_id;
            choice.addEventListener('change', function () { var before = activities.find(function (item) { return item.id === entry.activity_id; }); entry.activity_id = choice.value; var after = activities.find(function (item) { return item.id === entry.activity_id; }); if (!before || !after || before.kind !== after.kind) entry.quantity = after && after.kind === 'dictation' ? 20 : 1; changed(); renderRules(); });
            choiceLabel.appendChild(choice); row.appendChild(choiceLabel);
            var activity = activities.find(function (item) { return item.id === entry.activity_id; }), amountLabel = node('label', 'tp-field'), amount = node('input');
            amount.type = 'number'; amount.min = '1'; amount.max = activity && activity.kind === 'dictation' ? '1200' : '20'; amount.step = '1'; amount.value = entry.quantity; amount.disabled = !activity;
            amountLabel.appendChild(node('span', 'tp-sr-only', DAYS[dayIndex] + '数量')); amountLabel.appendChild(amount); row.appendChild(amountLabel);
            amount.addEventListener('input', function () { entry.quantity = amount.value; changed(); });
            row.appendChild(node('span', 'tp-week-unit', activity ? context.series.kindUnit(activity.kind, activity.selection) : '份'));
            var remove = node('button', 'tp-text-button', '移除'); remove.type = 'button'; remove.setAttribute('aria-label', DAYS[dayIndex] + '移除此项'); remove.addEventListener('click', function () { day.splice(entryIndex, 1); changed(); renderRules(); }); row.appendChild(remove); dayBox.appendChild(row);
          });
          block.appendChild(dayBox);
        });
        container.appendChild(block);
      });
    }
    function render() { renderActivities(); renderRules(); updateAnchor(); }
    function modeChanged() {
      var weekly = active(); $('seriesWeeklyFields').hidden = !weekly; $('seriesActivityNameField').hidden = !weekly; $('seriesAddActivity').hidden = !weekly; $('seriesQuotaSection').hidden = weekly;
      $('seriesEditorTitle').textContent = weekly ? '新建每周 / 轮换安排' : '新建连续安排';
      $('seriesActivityHelp').hidden = !weekly;
      $('seriesNote').placeholder = weekly ? '适用于当前练习项的每次任务' : '适用于这条学习线的每次安排';
      render(); changed();
    }
    $('seriesMode').addEventListener('change', modeChanged);
    $('seriesCycleWeeks').addEventListener('change', function () { changed(); render(); });
    $('seriesWeeklyExample').addEventListener('click', function () {
      var example = exampleRules(activities);
      if (!example) return;
      rules = example; context.message(''); changed(); renderRules();
    });
    $('seriesStart').addEventListener('change', updateAnchor);
    $('seriesAddActivity').addEventListener('click', function () {
      try {
        if (activities.length >= 12) throw new Error('每份安排最多加入12个练习项。');
        var item = context.buildActivity('activity-' + nextId, $('seriesActivityName').value); nextId++;
        activities.push(item); $('seriesActivityName').value = ''; context.message(''); changed(); render();
        $('seriesActivities').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } catch (error) { context.message(error.message); }
    });
    return { active: active, updateAnchor: updateAnchor, payload: function (fields) { return buildPayload(fields, activities, rules, cycle(), context.series); }, reset: function () { activities = []; rules = emptyWeeks(); nextId = 1; modeChanged(); }, render: render };
  }
  return { emptyWeeks: emptyWeeks, anchor: anchor, activityFromPayload: activityFromPayload, normalizedRules: normalizedRules, schedule: schedule, buildPayload: buildPayload, removeActivity: removeActivity, exampleRules: exampleRules, summary: summary, renderSkipped: renderSkipped, mount: mount };
});
