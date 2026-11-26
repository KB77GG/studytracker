(function (root) {
  'use strict';
  class Storage {
    constructor(taskId, identity, storage) {
      this.prefix = `pv:${taskId}:${identity}:`;
      this.storage = storage;
    }
    get(key) {
      try {
        return JSON.parse(this.storage.getItem(this.prefix + key));
      } catch (_) {
        return null;
      }
    }
    put(key, value) {
      try {
        this.storage.setItem(this.prefix + key, JSON.stringify(value));
      } catch (_) {
        /* Private browsing can deny storage. */
      }
    }
    remove(key) {
      try {
        this.storage.removeItem(this.prefix + key);
      } catch (_) {
        /* Best effort. */
      }
    }
  }
  class Timing {
    // Wall-clock time on this browser, isolated by task and stable student ID.
    // The first settlement payload is frozen before transmission so a lost
    // response, reload, or second tab cannot add retry time to that payload.
    constructor(taskId, identity, now = () => Date.now()) {
      this.now = now;
      this.enteredAt = now();
      this.memory = new Map();
      let local;
      try {
        local = taskId && identity ? root.localStorage : null;
      } catch (_) {
        local = null;
      }
      this.store = new Storage(taskId, identity, local);
    }
    key(sessionId) {
      return sessionId == null ? 'timer:task' : `timer:review:${sessionId}`;
    }
    valid(record, now) {
      return (
        !!record &&
        record.version === 1 &&
        (record.generation == null ||
          (Number.isSafeInteger(record.generation) && record.generation >= 0)) &&
        typeof record.complete === 'boolean' &&
        Number.isSafeInteger(record.startedAt) &&
        record.startedAt >= 0 &&
        record.startedAt <= now &&
        (record.seconds === null
          ? !record.complete
          : Number.isSafeInteger(record.seconds) &&
            record.seconds >= 0 &&
            record.seconds <= Math.floor((now - record.startedAt) / 1000))
      );
    }
    entry(sessionId, create = true) {
      const key = this.key(sessionId),
        now = this.now();
      const records = [this.store.get(key), this.memory.get(key)].filter((record) =>
        this.valid(record, now),
      );
      if (!records.length && !create) return null;
      const startedAt = records.length
        ? Math.min(...records.map((record) => record.startedAt))
        : sessionId == null && this.enteredAt <= now
          ? this.enteredAt
          : now;
      // A rejected incomplete settlement starts a new generation. An older
      // tab's cached snapshot must not refreeze time after another tab resumes.
      const generation = Math.max(0, ...records.map((record) => record.generation || 0));
      const current = records.filter((record) => (record.generation || 0) === generation);
      const snapshots = current.filter((record) => record.seconds !== null);
      const result = {
        version: 1,
        generation,
        startedAt,
        seconds: snapshots.length ? Math.min(...snapshots.map((record) => record.seconds)) : null,
        complete: current.some((record) => record.complete),
      };
      this.save(sessionId, result);
      return result;
    }
    save(sessionId, record) {
      const key = this.key(sessionId);
      this.memory.set(key, record);
      this.store.put(key, record);
    }
    observe(data) {
      if (data.settlement || (data.flow || {}).settlement) {
        if (this.entry(null, false)) this.finish(null);
        return;
      }
      const access = data.access || {};
      if (
        access.read_only ||
        access.can_write === false ||
        data.stage === 'blocked' ||
        ['future', 'expired', 'completed'].includes(access.task_date_state || access.state)
      )
        return;
      if (
        ['learning', 'in_progress', 'not_started', 'review', 'review_gate'].includes(data.stage)
      ) {
        this.entry(null);
        if (data.stage === 'review' && data.review && data.review.session_id != null)
          this.entry(data.review.session_id);
      }
    }
    snapshot(sessionId) {
      const record = this.entry(sessionId);
      if (record.seconds === null) {
        record.seconds = Math.max(0, Math.floor((this.now() - record.startedAt) / 1000));
        this.save(sessionId, record);
      }
      return record.seconds;
    }
    finish(sessionId, submittedSeconds) {
      const record = this.entry(sessionId);
      if (record.seconds === null) {
        const elapsed = Math.max(0, Math.floor((this.now() - record.startedAt) / 1000));
        record.seconds =
          Number.isSafeInteger(submittedSeconds) && submittedSeconds >= 0
            ? Math.min(elapsed, submittedSeconds)
            : elapsed;
      }
      record.complete = true;
      this.save(sessionId, record);
    }
    resume(sessionId) {
      // A definitive incomplete-flow response means there is more work to do.
      // A completed settlement can never be reopened by a client-side retry.
      const record = this.entry(sessionId, false);
      if (!record || record.complete) return;
      record.seconds = null;
      record.generation++;
      this.save(sessionId, record);
    }
  }
  class RequestError extends Error {
    constructor(code, status, data) {
      super(code);
      this.code = code;
      this.status = status;
      this.data = data || {};
    }
  }
  class Client {
    constructor(boot, storage) {
      this.boot = boot;
      this.storage = storage;
      this.seq = 0;
      this.inFlight = false;
    }
    async send(kind, payload, position, readOnly, context) {
      if (this.inFlight) throw new RequestError('request_busy', 409);
      this.inFlight = true;
      const seq = ++this.seq;
      const preserveJournal =
        ['sync', 'review/claim'].includes(kind) && this.storage.get('pending');
      if (!readOnly && !preserveJournal)
        this.storage.put('pending', {
          kind,
          payload,
          position,
          attempt_id: payload.attempt_id || '',
          context,
        });
      try {
        let result;
        for (let attempt = 0; attempt < 2; attempt++) {
          try {
            result = await this.fetchOnce(kind, payload, readOnly);
            break;
          } catch (error) {
            const retryable =
              !error.status ||
              error.status >= 500 ||
              (error.code === 'state_conflict' && error.data.retryable);
            if (!retryable || attempt) throw error;
            await new Promise((resolve) => setTimeout(resolve, 1000));
          }
        }
        if (seq !== this.seq) throw new RequestError('stale_response', 409);
        if (!readOnly && !preserveJournal) this.storage.remove('pending');
        return result;
      } finally {
        this.inFlight = false;
      }
    }
    async fetchOnce(kind, payload, readOnly) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 15000);
      try {
        const response = await fetch(`${this.boot.api_base}/${kind}`, {
          method: readOnly ? 'GET' : 'POST',
          credentials: 'same-origin',
          cache: 'no-store',
          signal: controller.signal,
          headers: readOnly
            ? { Accept: 'application/json' }
            : {
                Accept: 'application/json',
                'Content-Type': 'application/json',
                'X-CSRF-Token': this.boot.csrf_token,
                'X-Practice-Identity': this.boot.identity_key,
              },
          body: readOnly ? undefined : JSON.stringify(payload || {}),
        });
        let data;
        try {
          data = await response.json();
        } catch (_) {
          throw new RequestError(
            'invalid_response',
            response.status >= 400 ? response.status : 502,
          );
        }
        if (!response.ok || data.ok !== true)
          throw new RequestError(data.error || 'save_failed', response.status, data);
        return data;
      } catch (error) {
        if (error instanceof RequestError) throw error;
        throw new RequestError(
          error.name === 'AbortError' ? 'request_timeout' : 'network_error',
          0,
        );
      } finally {
        clearTimeout(timer);
      }
    }
  }
  class Player {
    constructor(changed) {
      this.audio = null;
      this.changed = changed;
      this.timer = 0;
      this.serial = 0;
      this.url = '';
      this.state = 'idle';
      this.interacted = false;
    }
    set(state) {
      this.state = state;
      this.changed(state);
    }
    stop() {
      this.serial++;
      clearTimeout(this.timer);
      if (this.audio) {
        this.audio.pause();
        this.audio.removeAttribute('src');
        this.audio.load();
      }
      this.audio = null;
      this.url = '';
      this.set('idle');
    }
    async play(url, automatic) {
      if (!url || (automatic && !this.interacted)) return;
      this.stop();
      this.url = url;
      const serial = this.serial,
        audio = (this.audio = new Audio());
      audio.preload = 'auto';
      this.set('loading');
      const current = () => serial === this.serial;
      const fail = () => {
        if (current()) {
          this.serial++;
          clearTimeout(this.timer);
          audio.pause();
          this.set('error');
        }
      };
      audio.addEventListener(
        'canplay',
        () => {
          if (current()) clearTimeout(this.timer);
        },
        { once: true },
      );
      audio.addEventListener('playing', () => {
        if (current()) {
          clearTimeout(this.timer);
          this.set('playing');
        }
      });
      audio.addEventListener('ended', () => {
        if (current()) this.set('idle');
      });
      audio.addEventListener('error', fail);
      this.timer = setTimeout(fail, 8000);
      audio.src = url;
      try {
        await audio.play();
      } catch (error) {
        if (current()) {
          clearTimeout(this.timer);
          this.set(automatic && error.name === 'NotAllowedError' ? 'idle' : 'error');
        }
      }
    }
  }
  root.PracticeVocabularyTransport = { Storage, Timing, Client, Player, RequestError };
})(window);
