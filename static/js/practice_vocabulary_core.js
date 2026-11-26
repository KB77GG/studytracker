(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.PracticeVocabularyCore = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const PHASES = [
    'familiarity',
    'active_recall',
    'context_discrimination',
    'context_production',
    'retry',
  ];
  const LABELS = {
    familiarity: '熟悉材料',
    active_recall: '主动提取',
    context_discrimination: '语境辨析',
    context_production: '语境产出',
    retry: '错题再测',
  };
  const MODE_LABELS = {
    en_to_zh: '看词写义',
    zh_to_en: '看义写词',
    audio_to_en: '听音拼写',
    audio_to_zh: '听音选义',
    context_choice: '语境选择',
    context_fill: '语境填空',
  };
  const BLOCKED = new Set([
    'identity_missing',
    'identity_changed',
    'staff_mode',
    'ambiguous_student_name',
    'student_account_missing',
    'student_account_unlinked',
    'task_not_found',
    'task_not_vocabulary_v2',
    'feature_disabled',
  ]);
  const RESYNC = new Set([
    'state_conflict',
    'question_not_current',
    'queue_changed',
    'correction_not_current',
    'correction_required',
    'correction_not_required',
    'task_already_completed',
    'retry_incomplete',
    'group_flow_incomplete',
    'correction_incomplete',
    'familiarity_phase_complete',
    'familiarity_order_violation',
    'review_item_already_answered',
    'review_session_not_active',
    'review_question_changed',
    'review_item_not_in_session',
    'vocabulary_review_required',
  ]);
  function mode(q) {
    return (q && (q.mode || q.dictation_mode || (q.question || {}).mode)) || '';
  }
  function choice(q) {
    return ['audio_to_zh', 'context_choice'].includes(mode(q));
  }
  function options(q) {
    return (q && q.question && q.question.options) || [];
  }
  function answerValue(q, text, selected) {
    if (!choice(q)) return String(text || '').trim();
    const item = options(q)[selected];
    return item ? String(mode(q) === 'audio_to_zh' ? item.label : item.id) : '';
  }
  function correctionValue(q, text) {
    const value = String(text || '').trim();
    if (mode(q) !== 'context_choice') return value;
    const option = options(q).find((item) => String(item.label).trim() === value);
    return option ? String(option.id) : value;
  }
  function sameQuestion(q, feedback) {
    if (!q || !feedback) return false;
    const key = q.review_item_id != null ? 'review_item_id' : 'learning_question_id';
    return q[key] != null && feedback[key] != null && String(q[key]) === String(feedback[key]);
  }
  function position(flow, review) {
    if (review) {
      const q = reviewQuestion(review);
      return [
        'review',
        review.session_id,
        review.queue_token,
        q && q.review_item_id,
        q && q.correction_count,
        !!(q && q.correction_required),
      ].join(':');
    }
    const f = flow || {},
      q = f.current_question || {};
    return [
      f.queue_token,
      f.group_index,
      f.phase,
      f.phase_index,
      q.learning_question_id,
      q.correction_count,
      !!f.correction_required,
    ].join(':');
  }
  function reviewQuestion(review) {
    return ((review || {}).items || []).find((q) => q.correction_required || !q.answered) || null;
  }
  function reviewCount(review) {
    if (review.total_count != null) return Number(review.total_count);
    if (review.required_count != null) return Number(review.required_count);
    return Math.min(Number(review.due_count || 0), Number(review.batch_limit || 20));
  }
  function questionKey(q, review) {
    return q
      ? `${review ? 'review' : 'group'}:${q.review_item_id || q.learning_question_id}:${q.retry ? 'retry' : 'first'}:${q.correction_required ? q.correction_count || 0 : ''}`
      : '';
  }
  function attemptId(taskId, q, review, correction) {
    const count = Number(q.correction_count || 0) + 1;
    if (review)
      return correction
        ? `web-vocabulary-review-correction:${review.session_id}:${q.review_item_id}:${count}`
        : `web-vocabulary-review:${review.session_id}:${q.review_item_id}`;
    const slot = q.retry || q.correction_phase === 'retry' ? 'retry' : 'first';
    return correction
      ? `vocabulary-group:${taskId}:correction:${q.learning_question_id}:${slot}:${count}`
      : `vocabulary-group:${taskId}:${slot}:${q.learning_question_id}`;
  }
  function resolveAudioUrl(url) {
    if (!url || typeof url !== 'string') return '';
    if (/^https?:\/\//i.test(url)) return url;
    if (url.startsWith('/dictation/')) return '/api' + url;
    if (/^(?:uploads|static)\//.test(url)) return '/' + url;
    if (url.startsWith('/') && !url.startsWith('//')) return url;
    return '';
  }
  function audioUrl(q, state, feedback, familiar) {
    if (state === 'familiarity')
      return resolveAudioUrl((familiar || {}).audio_tts_url || (familiar || {}).audio_url);
    if (['feedback', 'review_feedback'].includes(state))
      return resolveAudioUrl(((feedback || {}).answer_feedback || {}).audio_tts_url);
    if (['correction', 'review_correction'].includes(state)) {
      if (!q || !(q.correction_required || q.correction) || q.revealed_answer == null) return '';
      const current =
        (q.answer_feedback || {}).audio_tts_url || ((q.question || {}).prompt || {}).audio_tts_url;
      const saved = sameQuestion(q, feedback)
        ? ((feedback || {}).answer_feedback || {}).audio_tts_url
        : '';
      const fallback =
        Number.isInteger(Number(q.word_id)) && Number(q.word_id) > 0
          ? `/dictation/words/${q.word_id}/tts`
          : '';
      return resolveAudioUrl(current || saved || fallback);
    }
    if (!['en_to_zh', 'audio_to_en', 'audio_to_zh'].includes(mode(q))) return '';
    return resolveAudioUrl((((q || {}).question || {}).prompt || {}).audio_tts_url);
  }
  function routeKey(state, event, ctx) {
    if (
      event.isComposing ||
      event.keyCode === 229 ||
      ctx.composing ||
      ctx.compositionGuard ||
      event.repeat
    )
      return null;
    if (event.key === 'Escape') return 'escape';
    if (ctx.inFlight || ctx.dialogOpen || event.ctrlKey || event.metaKey) return null;
    const key = event.key;
    if (
      (key.toLowerCase() === 'r' && event.altKey) ||
      (key.toLowerCase() === 'r' && !ctx.inInput && !event.altKey)
    )
      return ctx.canAudio ? 'audio' : null;
    if (event.altKey) return null;
    if (ctx.nativeControl && key === 'Enter') return null;
    if (key === 'Enter') {
      if (!ctx.enterArmed) return null;
      if (state.endsWith('feedback') && ctx.feedbackWait) return 'wait';
      if (
        [
          'question',
          'review_question',
          'correction',
          'review_correction',
          'familiarity',
          'feedback',
          'review_feedback',
          'retry_intro',
          'group_done',
          'review_gate',
          'not_started',
          'save_failed',
          'settle_failed',
        ].includes(state)
      )
        return 'primary';
    }
    if (state === 'familiarity' && !ctx.inInput) {
      if (key === 'ArrowLeft') return 'previous';
      if (key === 'ArrowRight') return 'primary';
    }
    if (['question', 'review_question'].includes(state) && ctx.isChoice && !ctx.inInput) {
      if (/^[1-4]$/.test(key)) return `select:${Number(key) - 1}`;
      if (['ArrowDown', 'ArrowRight'].includes(key)) return 'option:next';
      if (['ArrowUp', 'ArrowLeft'].includes(key)) return 'option:previous';
    }
    return null;
  }
  // Both strings are public after an answer. Return text operations, never HTML.
  function spellingDiff(actual, expected) {
    const a = Array.from(String(actual || '').slice(0, 200));
    const b = Array.from(String(expected || '').slice(0, 200));
    const dp = Array.from({ length: a.length + 1 }, () => new Uint16Array(b.length + 1));
    for (let i = a.length - 1; i >= 0; i--)
      for (let j = b.length - 1; j >= 0; j--)
        dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const result = [];
    let i = 0,
      j = 0;
    function add(kind, text) {
      const last = result[result.length - 1];
      if (last && last.kind === kind) last.text += text;
      else result.push({ kind, text });
    }
    while (i < a.length || j < b.length) {
      if (i < a.length && j < b.length && a[i] === b[j]) {
        add('same', a[i++]);
        j++;
      } else if (j < b.length && (i === a.length || dp[i][j + 1] >= dp[i + 1][j]))
        add('ins', b[j++]);
      else add('del', a[i++]);
    }
    return result;
  }
  function decideView(data) {
    if (data.stage === 'blocked') return 'blocked';
    const access = data.access || {};
    if (access.task_date_state === 'future' || access.state === 'future') return 'locked_future';
    if (data.settlement || (data.flow || {}).settlement) return 'result';
    if (data.stage === 'read_only' || access.read_only) return 'read_only';
    if (data.stage === 'review_gate') return 'review_gate';
    if (data.stage === 'review') {
      const q = reviewQuestion(data.review);
      return q
        ? q.correction_required
          ? 'review_correction'
          : 'review_question'
        : 'review_settling';
    }
    const f = data.flow;
    if (!f) return 'not_started';
    if (f.completed) return 'settling';
    if (f.correction_required || (f.current_question || {}).correction_required)
      return 'correction';
    if (f.phase === 'familiarity') return 'familiarity';
    return f.current_question ? 'question' : 'not_started';
  }
  return {
    PHASES,
    LABELS,
    MODE_LABELS,
    BLOCKED,
    RESYNC,
    mode,
    choice,
    options,
    answerValue,
    correctionValue,
    sameQuestion,
    position,
    reviewQuestion,
    reviewCount,
    questionKey,
    attemptId,
    resolveAudioUrl,
    audioUrl,
    routeKey,
    spellingDiff,
    decideView,
  };
});
