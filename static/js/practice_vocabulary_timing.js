(function (root) {
  'use strict';
  const IDLE_MS = 5 * 60 * 1000;
  const SAVE_MS = 5000;
  const stamp = (value) => Number.isSafeInteger(value) && value >= 0;
  function union(ranges) {
    const result = [];
    ranges.slice().sort((a, b) => a[0] - b[0]).forEach(([start, end]) => {
      const last = result[result.length - 1];
      if (last && start <= last[1]) last[1] = Math.max(last[1], end);
      else result.push([start, end]);
    });
    return result;
  }
  class Timing {
    // Each page writes its own intervals; their union counts overlapping tabs
    // once without a shared read/modify/write total. Never store future credit.
    constructor(taskId, identity, now = () => Date.now()) {
      this.now = now;
      this.lastTick = this.lastActivity = this.lastFlush = now();
      this.visible = true;
      this.enabled = false;
      this.scopes = [];
      this.memory = new Map();
      this.own = new Map();
      this.dirty = new Set();
      this.owner = root.crypto?.randomUUID?.() || `${now()}-${Math.random().toString(36).slice(2)}`;
      let local;
      try { local = taskId && identity ? root.localStorage : null; } catch (_) { local = null; }
      this.store = new root.PracticeVocabularyTransport.Storage(taskId, identity, local);
    }
    key(sessionId) {
      return sessionId == null ? 'active:v2:task' : `active:v2:review:${sessionId}`;
    }
    valid(record, now) {
      if (!record || record.version !== 2 || typeof record.complete !== 'boolean'
          || !Array.isArray(record.windows) || !record.windows.length || record.windows.length > 10000
          || record.generation !== record.windows.length - 1
          || !(record.seconds === null ? !record.complete : stamp(record.seconds))) return false;
      let previous = 0, duration = 0;
      const valid = record.windows.every((span, index) => {
        if (!Array.isArray(span) || span.length !== 2 || !stamp(span[0]) || span[0] < previous || span[0] > now) return false;
        const open = index === record.windows.length - 1 && record.seconds === null;
        if (open ? span[1] !== null : !stamp(span[1]) || span[1] < span[0] || span[1] > now) return false;
        if (!open) duration += span[1] - span[0];
        previous = span[1];
        return true;
      });
      return valid && (record.seconds === null || record.seconds <= Math.floor(duration / 1000));
    }
    entry(sessionId, create = true) {
      const key = this.key(sessionId), now = this.now();
      const candidates = [this.store.get(key), this.memory.get(key)].filter(r => this.valid(r, now));
      if (!candidates.length) {
        if (!create) return null;
        const fresh = { version: 2, generation: 0, windows: [[now, null]], seconds: null, complete: false };
        this.save(sessionId, fresh);
        return fresh;
      }
      const generation = Math.max(...candidates.map(r => r.generation));
      const current = candidates.filter(r => r.generation === generation);
      const frozen = current.filter(r => r.seconds !== null).sort((a, b) => a.seconds - b.seconds);
      const selected = frozen[0] || current[0];
      const record = { ...selected, windows: selected.windows.map(span => span.slice()), complete: current.some(r => r.complete) };
      this.memory.set(key, record);
      return record;
    }
    save(sessionId, record) {
      this.memory.set(this.key(sessionId), record);
      this.store.put(this.key(sessionId), record);
    }
    validRanges(value, now) {
      return value?.version === 2 && Array.isArray(value.ranges) && value.ranges.length <= 10000
        && value.ranges.every(r => Array.isArray(r) && r.length === 2 && stamp(r[0]) && stamp(r[1]) && r[0] <= r[1] && r[1] <= now);
    }
    flush() {
      const now = this.now();
      this.dirty.forEach(key => {
        const ranges = this.own.get(key);
        const saved = this.store.get(key);
        const merged = union([...ranges, ...(this.validRanges(saved, now) ? saved.ranges : [])]);
        this.own.set(key, merged);
        if (this.store.put(key, { version: 2, ranges: merged })) this.dirty.delete(key);
      });
      this.lastFlush = now;
    }
    tick(force = false) {
      const now = this.now();
      if (now < this.lastTick) {
        // A clock rollback never creates a negative or compensating interval.
        this.lastTick = now;
        this.lastActivity = Math.min(this.lastActivity, now);
      }
      const end = Math.min(now, this.lastActivity + IDLE_MS);
      if (this.enabled && this.visible && end > this.lastTick) this.scopes.forEach(sessionId => {
        const record = this.entry(sessionId);
        if (record.seconds !== null || record.complete) return;
        const start = Math.max(this.lastTick, record.windows[record.windows.length - 1][0]);
        if (end <= start) return;
        const key = `${this.key(sessionId)}:page:${this.owner}`;
        this.own.set(key, union([...(this.own.get(key) || []), [start, end]]));
        this.dirty.add(key);
      });
      this.lastTick = now;
      if (force || now - this.lastFlush >= SAVE_MS) this.flush();
    }
    activity() {
      this.tick();
      if (this.visible) this.lastActivity = this.now();
    }
    visibility(visible) {
      this.tick(true);
      const returning = visible && !this.visible;
      this.visible = visible;
      this.lastTick = this.now();
      if (returning) this.lastActivity = this.lastTick;
    }
    setState(state) {
      this.tick(true);
      this.enabled = ['not_started', 'familiarity', 'question', 'correction', 'feedback',
        'review_question', 'review_correction', 'review_feedback', 'review_gate', 'retry_intro', 'group_done'].includes(state);
    }
    observe(data) {
      this.tick(true);
      const access = data.access || {};
      this.scopes = [];
      if (data.settlement || data.flow?.settlement) {
        if (this.entry(null, false)) this.finish(null);
        return;
      }
      if (access.read_only || access.can_write === false || data.stage === 'blocked'
          || ['future', 'expired', 'completed'].includes(access.task_date_state || access.state)) return;
      if (['learning', 'in_progress', 'not_started', 'review', 'review_gate'].includes(data.stage)) {
        this.scopes = [null];
        if (data.stage === 'review' && data.review?.session_id != null) this.scopes.push(data.review.session_id);
        this.scopes.forEach(id => this.entry(id));
      }
    }
    elapsed(sessionId, record) {
      const now = this.now(), prefix = `${this.store.prefix}${this.key(sessionId)}:page:`;
      let ranges = [];
      try {
        const local = this.store.storage;
        for (let i = 0; i < local.length; i++) {
          const key = local.key(i);
          if (!key?.startsWith(prefix)) continue;
          try {
            const value = JSON.parse(local.getItem(key));
            if (this.validRanges(value, now)) ranges.push(...value.ranges);
          } catch (_) { /* One damaged page must not discard other pages. */ }
        }
      } catch (_) { /* Denied storage retains this page's in-memory intervals. */ }
      this.own.forEach((value, key) => {
        if (`${this.store.prefix}${key}`.startsWith(prefix)) ranges.push(...value);
      });
      const allowed = [];
      // Freeze/resume windows also exclude another offline tab's late buffered
      // intervals during settlement waits, even after storage becomes available.
      union(ranges).forEach(([start, end]) => record.windows.forEach(([from, to]) => {
        const left = Math.max(start, from), right = Math.min(end, to === null ? now : to);
        if (right > left) allowed.push([left, right]);
      }));
      return Math.floor(union(allowed).reduce((total, [start, end]) => total + end - start, 0) / 1000);
    }
    snapshot(sessionId) {
      this.tick(true);
      const record = this.entry(sessionId);
      if (record.seconds === null) {
        record.windows[record.windows.length - 1][1] = this.now();
        record.seconds = this.elapsed(sessionId, record);
        this.save(sessionId, record);
      }
      return record.seconds;
    }
    finish(sessionId) {
      this.snapshot(sessionId);
      const record = this.entry(sessionId);
      if (record.complete) return;
      // Recovery sends its original journaled payload unchanged. A legacy
      // wall-clock value is not imported into this active-time record; the
      // server remains the source of the saved settlement and displayed result.
      record.complete = true;
      this.save(sessionId, record);
    }
    resume(sessionId) {
      this.tick(true);
      const record = this.entry(sessionId, false);
      if (!record || record.complete || record.seconds === null) return;
      record.windows.push([this.now(), null]);
      record.generation++;
      record.seconds = null;
      this.save(sessionId, record);
    }
  }
  Timing.IDLE_MS = IDLE_MS;
  Timing.SAVE_MS = SAVE_MS;
  root.PracticeVocabularyTransport.Timing = Timing;
})(window);
