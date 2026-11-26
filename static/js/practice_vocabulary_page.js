(function (root) {
  'use strict';
  const C = root.PracticeVocabularyCore,
    T = root.PracticeVocabularyTransport;
  class Page {
    constructor(boot) {
      this.boot = boot;
      this.started = Date.now();
      this.reviewStarted = Date.now();
      this.reviewSessionId = null;
      let storage;
      try {
        storage = sessionStorage;
      } catch (_) {
        storage = null;
      }
      this.storage = new T.Storage(boot.task_id, boot.identity_key, storage);
      this.client = new T.Client(boot, this.storage);
      this.view = new root.PracticeVocabularyView();
      this.player = new T.Player((state) => this.view.audio(state));
      this.seenRetry = new Set();
      this.model = {
        state: 'booting',
        data: boot,
        busy: false,
        q: null,
        draft: '',
        selected: -1,
        familiarIndex: 0,
      };
      this.feedbackUntil = 0;
      this.lastFailed = null;
      this.stale = false;
      this.events = root.PracticeVocabularyEvents.install(this);
      this.shell = root.PracticeShell
        ? root.PracticeShell.init({
            fallbackUrl: '/practice#practiceAssignedTasks',
            initialSaved: true,
          })
        : null;
      document.querySelector('[data-practice-back]').textContent = '← 返回任务列表';
    }
    async start() {
      if (this.boot.stage === 'blocked') {
        this.model.error = this.boot.error;
        this.model.message = this.boot.message;
        this.show('blocked');
        return;
      }
      const pending = this.storage.get('pending');
      const state = await this.request('state', {}, true);
      if (!state) return;
      if (
        C.decideView(state) === 'read_only' ||
        state.stage === 'result' ||
        C.decideView(state) === 'locked_future'
      ) {
        this.storage.remove('pending');
        this.apply(state);
        return;
      }
      if (pending) {
        await this.recover(pending);
        return;
      }
      await this.sync();
    }
    saveDraft() {
      if (this.model.q)
        this.storage.put('draft:' + C.questionKey(this.model.q, this.model.data.review), {
          text: this.model.draft,
          selected: this.model.selected,
        });
    }
    async request(kind, payload, readOnly) {
      if (this.model.busy) return null;
      this.model.busy = true;
      this.view.busy(true);
      this.view.status(readOnly ? '同步中' : '保存中', 'saving');
      const context = {
        q: this.model.q,
        state: this.model.state,
        review: this.model.data.review ? { session_id: this.model.data.review.session_id } : null,
      };
      try {
        const data = await this.client.send(
          kind,
          payload,
          C.position(this.model.data.flow, this.model.data.review),
          readOnly,
          context,
        );
        this.lastFailed = null;
        this.view.status(readOnly ? '已同步' : '已保存', readOnly ? '' : 'saved');
        if (!readOnly && this.broadcast) this.broadcast(C.position(data.flow, data.review));
        return data;
      } catch (error) {
        this.lastFailed = { kind, payload, readOnly };
        this.view.status('保存失败 · 重试', 'error');
        this.pendingError = error;
        return null;
      } finally {
        this.model.busy = false;
        this.view.busy(false);
        if (this.pendingError) {
          const error = this.pendingError;
          this.pendingError = null;
          queueMicrotask(() => this.handleError(error));
        }
      }
    }
    handleError(error) {
      if (error.code === 'request_busy' || error.code === 'stale_response') return;
      if (C.BLOCKED.has(error.code) || error.status === 401) {
        this.model.error = error.code;
        this.model.message = '';
        this.storage.remove('pending');
        this.show('blocked');
        return;
      }
      if (error.code === 'task_expired' || error.code === 'task_not_open') {
        this.model.error = error.code;
        this.storage.remove('pending');
        this.show(error.code === 'task_not_open' ? 'locked_future' : 'read_only');
        return;
      }
      if (C.RESYNC.has(error.code) || error.code === 'task_completed_read_only') {
        if (this.lastFailed && this.lastFailed.kind === 'sync') {
          this.show('save_failed');
          return;
        }
        this.storage.remove('pending');
        this.view.toast('进度已在其他窗口或设备更新，已同步到最新位置');
        this.sync();
        return;
      }
      if (error.status === 400 || error.status === 403 || error.status === 404) {
        this.storage.remove('pending');
        this.model.message =
          error.code === 'csrf'
            ? '页面会话已过期，请返回任务列表重新进入。'
            : '当前请求无法保存，请返回任务列表重新进入。';
        this.show('blocked');
        return;
      }
      this.show(
        this.lastFailed && this.lastFailed.kind.endsWith('settle')
          ? 'settle_failed'
          : 'save_failed',
      );
    }
    async sync(attemptId) {
      const data = await this.request('sync', attemptId ? { attempt_id: attemptId } : {});
      if (data) this.apply(data);
      return data;
    }
    apply(data, skipInterlude, deferAutomatic) {
      const previous = this.model.data.flow,
        oldKey = C.questionKey(this.model.q, this.model.data.review);
      const oldPosition = C.position(this.model.data.flow, this.model.data.review);
      this.saveDraft();
      this.model.data = { ...this.boot, ...data };
      let state = C.decideView(data),
        f = data.flow,
        review = data.stage === 'review' ? data.review : null;
      this.model.q = review ? C.reviewQuestion(review) : f && f.current_question;
      if (this.model.q && f && f.phase === 'retry') this.model.q = { ...this.model.q, retry: true };
      if (!C.sameQuestion(this.model.q, this.model.feedback)) this.model.feedback = null;
      if (
        review &&
        review.session_id != null &&
        String(review.session_id) !== this.reviewSessionId
      ) {
        this.reviewSessionId = String(review.session_id);
        this.reviewStarted = Date.now();
      }
      const key = C.questionKey(this.model.q, review),
        saved = this.storage.get('draft:' + key);
      this.model.draft = (saved && saved.text) || '';
      this.model.selected = saved && Number.isInteger(saved.selected) ? saved.selected : -1;
      if (key !== oldKey) this.model.correctionError = false;
      if (state === 'familiarity') {
        const index = (f.familiarity || []).findIndex((w) => !w.viewed);
        this.model.familiarIndex = Math.max(0, index);
      }
      if (!skipInterlude && f && previous && f.group_index > previous.group_index && !f.completed)
        state = 'group_done';
      else if (!skipInterlude && state === 'question' && f.phase === 'retry') {
        const marker = `${f.group_index}:${f.queue_token}`;
        if (!this.seenRetry.has(marker)) {
          this.seenRetry.add(marker);
          state = 'retry_intro';
        }
      }
      if (this.stale && oldPosition !== C.position(f, review))
        this.view.toast('进度已在其他窗口或设备更新，已同步到最新位置');
      this.stale = false;
      this.show(state);
      if (!deferAutomatic && state === 'settling') this.settle(false);
      else if (!deferAutomatic && state === 'review_settling') this.settle(true);
    }
    show(state) {
      this.events.transition();
      this.player.stop();
      this.model.state = state;
      const familiar = ((this.model.data.flow || {}).familiarity || [])[this.model.familiarIndex];
      this.model.audioUrl = C.audioUrl(this.model.q, state, this.model.feedback, familiar);
      this.view.show(this.model);
      if (state.endsWith('question') && (this.model.draft || this.model.selected >= 0)) {
        this.view.status('答案待提交', '');
      }
      if (
        state.endsWith('question') &&
        ['audio_to_en', 'audio_to_zh'].includes(C.mode(this.model.q))
      )
        this.player.play(this.model.audioUrl, true);
    }
    action(action, target) {
      if (this.model.busy) return;
      if (action === 'back') {
        if (this.shell) this.shell.leave('back');
        else location.assign('/practice#practiceAssignedTasks');
        return;
      }
      if (action === 'audio') {
        this.player.play((target && target.dataset.audio) || this.model.audioUrl, false);
        return;
      }
      if (action === 'wait') return;
      if (action === 'previous') {
        if (this.model.familiarIndex > 0) {
          this.model.familiarIndex--;
          this.show('familiarity');
        }
        return;
      }
      if (action.startsWith('select:') || action.startsWith('option:')) {
        this.select(action);
        return;
      }
      if (action === 'forgot') {
        this.submit('forgot');
        return;
      }
      if (action !== 'primary') return;
      const state = this.model.state;
      if (state.endsWith('question') || state.endsWith('correction')) this.submit('answer');
      else if (state === 'familiarity') this.nextFamiliar();
      else if (state.endsWith('feedback')) {
        if (Date.now() < this.feedbackUntil) return;
        if (state === 'review_feedback') this.apply(this.model.data, true);
        else this.sync();
      } else if (state === 'review_gate') this.claimReview();
      else if (state === 'retry_intro' || state === 'group_done') this.apply(this.model.data, true);
      else if (state === 'save_failed' || state === 'settle_failed') this.retry();
      else if (state === 'not_started') this.sync();
    }
    select(action) {
      const count = C.options(this.model.q).length;
      if (!count) return;
      let index = action.startsWith('select:')
        ? Number(action.split(':')[1])
        : (this.model.selected + (action === 'option:next' ? 1 : -1) + count) % count;
      if (index < 0 || index >= count) return;
      this.model.selected = index;
      this.saveDraft();
      document.querySelectorAll('[data-option]').forEach((node) => {
        const selected = Number(node.dataset.option) === index;
        node.setAttribute('aria-checked', String(selected));
        node.tabIndex = selected ? 0 : -1;
        node.querySelector('.mark').textContent = selected ? '✓' : '';
        if (selected) node.focus({ preventScroll: true });
      });
    }
    async nextFamiliar() {
      const flow = this.model.data.flow,
        items = flow.familiarity || [],
        index = this.model.familiarIndex,
        item = items[index];
      if (!item) return;
      if (item.viewed) {
        this.model.familiarIndex = Math.min(index + 1, items.length - 1);
        this.show('familiarity');
        return;
      }
      const data = await this.request('familiarity', {
        queue_token: flow.queue_token,
        word_id: item.word_id,
      });
      if (data) this.apply(data);
    }
    async submit(kind) {
      const q = this.model.q;
      if (!q) return;
      const review = this.model.data.stage === 'review' ? this.model.data.review : null,
        correction = this.model.state.endsWith('correction');
      const answer = correction
        ? C.correctionValue(q, this.model.draft)
        : C.answerValue(q, this.model.draft, this.model.selected);
      if (kind !== 'forgot' && !answer) {
        this.view.message(
          C.choice(q) && !correction ? '请选择一个答案，或点“忘了”。' : '请输入答案，或点“忘了”。',
        );
        return;
      }
      this.saveDraft();
      const flow = this.model.data.flow || {},
        payload = {
          queue_token: review ? review.queue_token : flow.queue_token,
          attempt_id: C.attemptId(this.boot.task_id, q, review, correction),
          answer: kind === 'forgot' ? '' : answer,
          response_kind: kind,
          learning_question_id: q.learning_question_id,
          queue_item_id: q.queue_item_id,
          question_id: q.question_id,
          word_id: q.word_id,
          sense_id: q.sense_id,
          dimension: q.dimension,
          retry: !!q.retry,
          input_mode: 'native',
          supports_correction: true,
        };
      if (review)
        Object.assign(payload, {
          session_id: review.session_id,
          session_token: review.session_token,
          review_item_id: q.review_item_id,
        });
      const endpoint = (review ? 'review/' : '') + (correction ? 'corrections' : 'answers');
      const data = await this.request(endpoint, payload);
      if (data) await this.acceptWrite(endpoint, data, payload, q);
    }
    async acceptWrite(kind, data, payload, q) {
      if (kind.endsWith('answers')) {
        const feedback = data.feedback || data;
        feedback.local_answer_differs =
          !!feedback.idempotent &&
          String(feedback.student_answer || '') !== String(payload.answer || '');
        this.model.feedback = feedback;
        this.model.q = q || this.model.q;
        if (data.review) this.model.data = { ...this.model.data, ...data, stage: 'review' };
        this.feedbackUntil = feedback.is_correct ? 0 : Date.now() + 500;
        this.show(kind.startsWith('review/') ? 'review_feedback' : 'feedback');
      } else if (kind.endsWith('corrections')) {
        const wrong = (data.feedback || data).correction_is_correct === false;
        this.model.draft = '';
        this.saveDraft();
        if (data.review) this.apply({ ...data, stage: 'review' }, true);
        else await this.sync();
        if (this.model.state.endsWith('correction') && wrong) {
          this.model.correctionError = true;
          this.show(this.model.state);
        }
      } else if (kind === 'review/settle') await this.sync();
      else this.apply(data);
    }
    async claimReview() {
      const data = await this.request('review/claim', {});
      if (data) {
        this.apply(data);
      }
    }
    async settle(review) {
      const r = this.model.data.review || {},
        f = this.model.data.flow || {},
        payload = {
          queue_token: review ? r.queue_token : f.queue_token,
          duration_seconds: Math.max(
            0,
            Math.floor((Date.now() - (review ? this.reviewStarted : this.started)) / 1000),
          ),
          supports_correction: true,
        };
      if (review)
        Object.assign(payload, { session_id: r.session_id, session_token: r.session_token });
      const kind = review ? 'review/settle' : 'settle',
        data = await this.request(kind, payload);
      if (data) await this.acceptWrite(kind, data, payload);
    }
  }
  Object.assign(Page.prototype, root.PracticeVocabularyRecovery);
  root.PracticeVocabularyPage = Page;
  const node = document.getElementById('pv-boot');
  if (node) {
    const page = new Page(JSON.parse(node.textContent));
    page.start();
  }
})(window);
