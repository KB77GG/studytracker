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
  root.PracticeVocabularyTransport = { Storage, Client, Player, RequestError };
})(window);
