(function (root) {
  'use strict';
  const C = root.PracticeVocabularyCore;
  function install(app) {
    const dialog = document.getElementById('pv-help-dialog');
    const keyState = {
      composing: false,
      compositionGuard: false,
      enterDown: false,
      enterArmed: true,
    };
    app.keyState = keyState;
    // User input, including IME and wheel scrolling, renews the idle window.
    // Programmatic scrolling, focus refreshes and repeated keys do not.
    const activity = (event) => {
      if (event.isTrusted && !event.repeat) app.timing?.activity();
    };
    ['pointerdown', 'pointermove', 'wheel', 'keydown', 'input', 'compositionstart', 'compositionend'].forEach(type =>
      document.addEventListener(type, activity, { capture: true, passive: true }));
    app.timing?.visibility(document.visibilityState === 'visible');
    if (app.timing) window.setInterval(() => app.timing.tick(), 5000);
    document.addEventListener('compositionstart', () => {
      keyState.composing = true;
    });
    document.addEventListener('compositionend', () => {
      keyState.composing = false;
      keyState.compositionGuard = true;
      setTimeout(() => {
        keyState.compositionGuard = false;
      }, 0);
    });
    document.addEventListener('keyup', (event) => {
      if (event.key === 'Enter') {
        keyState.enterDown = false;
        keyState.enterArmed = true;
      }
    });
    window.addEventListener('blur', () => {
      keyState.enterDown = false;
      keyState.enterArmed = true;
    });
    document.addEventListener('keydown', (event) => {
      app.player.interacted = true;
      if (event.repeat && ['Enter', ' '].includes(event.key) && event.target.closest('button')) {
        event.preventDefault();
        return;
      }
      if (event.key === 'Enter') keyState.enterDown = true;
      const target = event.target,
        inInput = !!target.closest('input,textarea,[contenteditable="true"]');
      const action = C.routeKey(app.model.state, event, {
        ...keyState,
        inInput,
        nativeControl: !!target.closest('button,a,select') && !target.closest('[role="radio"]'),
        inFlight: app.model.busy,
        dialogOpen: dialog.open,
        canAudio: !!app.model.audioUrl,
        isChoice: C.choice(app.model.q),
        feedbackWait: Date.now() < app.feedbackUntil,
      });
      if (!action) return;
      event.preventDefault();
      if (action === 'escape') {
        if (dialog.open) dialog.close();
        return;
      }
      app.action(action);
    });
    document.addEventListener('input', (event) => {
      if (event.target.id !== 'pv-answer') return;
      app.model.draft = event.target.value;
      app.saveDraft();
      app.view.status('答案待提交', '');
    });
    document.addEventListener('click', (event) => {
      app.player.interacted = true;
      const target = event.target.closest('[data-action]');
      if (target) {
        event.preventDefault();
        if (
          target.dataset.action === 'primary' &&
          event.detail === 0 &&
          keyState.enterDown &&
          !keyState.enterArmed
        )
          return;
        app.action(target.dataset.action, target);
      }
    });
    document.getElementById('pv-help').addEventListener('click', () => dialog.showModal());
    dialog.querySelector('[data-help-close]').addEventListener('click', () => dialog.close());
    let channel;
    try {
      channel = new BroadcastChannel(`pv-task-${app.boot.task_id}`);
      channel.onmessage = (event) => {
        if (event.data && event.data.type === 'advanced') app.stale = true;
      };
    } catch (_) {
      /* Visibility sync also works without BroadcastChannel. */
    }
    app.broadcast = (position) => {
      if (channel) channel.postMessage({ type: 'advanced', position });
    };
    function refresh() {
      if (document.visibilityState === 'visible' && !app.model.busy && !dialog.open) app.refresh();
    }
    document.addEventListener('visibilitychange', () => {
      app.timing?.visibility(document.visibilityState === 'visible');
      refresh();
    });
    window.addEventListener('pageshow', () => app.timing?.visibility(document.visibilityState === 'visible'));
    window.addEventListener('focus', refresh);
    window.addEventListener('pagehide', () => {
      app.timing?.visibility(false);
      app.saveDraft();
      app.player.stop();
    });
    return {
      state: keyState,
      transition() {
        if (keyState.enterDown) keyState.enterArmed = false;
      },
    };
  }
  root.PracticeVocabularyEvents = { install };
})(window);
