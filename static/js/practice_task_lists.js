(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PracticeTaskLists = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  function availability(task) {
    return task.task_date_state || task.availability_status || '';
  }

  function workflow(task) {
    return task.task_status || task.status || '';
  }

  function completed(task) {
    return availability(task) === 'completed'
      || ['done', 'completed', 'finished'].includes(workflow(task));
  }

  function isLocked(task) {
    if (completed(task)) return false;
    return ['expired', 'future'].includes(availability(task))
      || task.read_only === true || task.can_start === false || task.can_write === false;
  }

  function bucket(task) {
    const state = availability(task);
    if (completed(task) || workflow(task) === 'submitted') return 'history';
    if (state === 'future') return 'upcoming';
    if (state === 'expired') return 'expired';
    // The server owns the date window, including the next-day 03:00 grace period.
    // Missing availability must not turn an unknown task into something actionable.
    if (!isLocked(task) && (state === 'today' || task.can_start === true || task.can_write === true)) {
      return 'current';
    }
    return 'history';
  }

  function dateOrder(a, b) {
    return String(a.task_date || a.date || '').localeCompare(String(b.task_date || b.date || ''))
      || Number(a.id || 0) - Number(b.id || 0);
  }

  function partition(tasks) {
    const result = { current: [], upcoming: [], history: [], expired: [] };
    (Array.isArray(tasks) ? tasks : []).forEach(function (task) {
      if (task && typeof task === 'object') result[bucket(task)].push(task);
    });
    result.current.sort(function (a, b) {
      return Number(workflow(b) === 'in_progress') - Number(workflow(a) === 'in_progress')
        || dateOrder(b, a);
    });
    result.upcoming.sort(dateOrder);
    result.history.sort((a, b) => dateOrder(b, a));
    result.expired.sort((a, b) => dateOrder(b, a));
    return result;
  }

  function fromGroups(groups) {
    groups = groups || {};
    return partition(['assistant', 'teacher'].flatMap(function (key) {
      return Array.isArray(groups[key]) ? groups[key] : [];
    }));
  }

  return { partition, fromGroups, isLocked };
});
