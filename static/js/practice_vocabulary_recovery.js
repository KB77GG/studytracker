(function (root) {
  'use strict';
  const C = root.PracticeVocabularyCore;
  // Recovery uses the exact journaled write, while visibility sync only reads
  // the current domain position. Keep both paths separate from new answers.
  class Recovery {
    async retry() {
      const pending = this.storage.get('pending') || this.lastFailed;
      if (!pending) {
        await this.sync();
        return;
      }
      const data = await this.request(pending.kind, pending.payload || {}, pending.readOnly);
      if (data)
        await this.acceptWrite(
          pending.kind,
          data,
          pending.payload || {},
          pending.context && pending.context.q,
        );
    }
    async recover(pending) {
      const review = pending.kind.startsWith('review/');
      const data = await this.request(
        review ? 'review/claim' : 'sync',
        review ? {} : { attempt_id: pending.attempt_id || '' },
      );
      if (!data) return;
      const recovered = (data.flow || {}).saved_response || data.saved_response;
      if (recovered && pending.kind.endsWith('answers')) {
        this.apply(data, true, true);
        this.storage.remove('pending');
        this.model.feedback = recovered;
        this.model.q = pending.context && pending.context.q;
        this.feedbackUntil = recovered.is_correct ? 0 : Date.now() + 500;
        this.show('feedback');
        return;
      }
      const savedItem =
        review &&
        ((data.review || {}).items || []).find(
          (item) => item.review_item_id === pending.payload.review_item_id && item.answered,
        );
      if (savedItem && pending.kind === 'review/answers') {
        this.apply(data, true, true);
        this.storage.remove('pending');
        this.model.q = pending.context && pending.context.q;
        this.model.feedback = {
          ...savedItem,
          is_correct: savedItem.first_is_correct,
          student_answer: savedItem.first_answer,
          response_kind: savedItem.first_response_kind,
        };
        this.feedbackUntil = savedItem.first_is_correct ? 0 : Date.now() + 500;
        this.show('review_feedback');
        return;
      }
      this.apply(data, true, true);
      const current = C.position(data.flow, data.review);
      if (current === pending.position || pending.kind.endsWith('settle')) {
        const result = await this.request(pending.kind, pending.payload);
        if (result)
          await this.acceptWrite(
            pending.kind,
            result,
            pending.payload,
            pending.context && pending.context.q,
          );
      } else {
        this.storage.remove('pending');
        this.view.toast('已同步到最新进度，未重复提交旧答案。');
        if (this.model.state === 'settling') this.settle(false);
        else if (this.model.state === 'review_settling') this.settle(true);
      }
    }
    async refresh() {
      if (
        this.model.busy ||
        [
          'booting',
          'blocked',
          'save_failed',
          'settle_failed',
          'feedback',
          'review_feedback',
          'result',
          'read_only',
          'locked_future',
        ].includes(this.model.state)
      )
        return;
      this.saveDraft();
      this.stale = true;
      if (this.model.data.stage === 'review') await this.claimReview();
      else await this.sync();
    }
  }
  root.PracticeVocabularyRecovery = {
    retry: Recovery.prototype.retry,
    recover: Recovery.prototype.recover,
    refresh: Recovery.prototype.refresh,
  };
})(window);
