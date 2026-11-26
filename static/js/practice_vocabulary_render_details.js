(function (root) {
  'use strict';
  const C = root.PracticeVocabularyCore;
  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }
  function button(text, action, cls) {
    const node = el('button', cls || 'pv-btn pv-btn--secondary', text);
    node.type = 'button';
    node.dataset.action = action;
    return node;
  }
  function audio(url, large) {
    const node = button('', 'audio', 'pv-audio' + (large ? ' pv-audio--lg' : ''));
    node.dataset.audio = C.resolveAudioUrl(url);
    node.setAttribute('aria-label', '播放音频');
    node.append(el('span', 'ic', '▶'), el('span', 'pv-audio-label', '播放音频'));
    return node;
  }
  function material(data, target) {
    const panel = el('aside', 'pv-card pv-material');
    if (data.example_en) {
      const block = el('div');
      block.append(el('div', 'pv-label', '例句'));
      const sentence = el('p', 'pv-example');
      highlight(sentence, data.example_en, target || data.word);
      block.append(sentence);
      if (data.example_zh) block.append(el('p', 'pv-trans', data.example_zh));
      panel.append(block);
    }
    [
      ['usage_pattern', '搭配'],
      ['usage_note', '用法'],
    ].forEach(([key, label]) => {
      if (data[key]) {
        const block = el('div');
        block.append(
          el('div', 'pv-label', label),
          el('p', key === 'usage_pattern' ? 'pv-colloc' : 'pv-note', data[key]),
        );
        panel.append(block);
      }
    });
    return panel;
  }
  function highlight(node, value, word) {
    const text = String(value || ''),
      needle = String(word || '');
    const index = needle ? text.toLowerCase().indexOf(needle.toLowerCase()) : -1;
    if (index < 0) {
      node.textContent = text;
      return;
    }
    node.append(
      document.createTextNode(text.slice(0, index)),
      el('b', '', text.slice(index, index + needle.length)),
      document.createTextNode(text.slice(index + needle.length)),
    );
  }
  function stats(items) {
    const node = el('div', 'pv-stats');
    items.forEach(([value, label]) => {
      const item = el('div', 'pv-stat');
      item.append(el('b', '', value), el('span', '', label));
      node.append(item);
    });
    return node;
  }
  function studentAnswer(q, value) {
    if (C.mode(q) !== 'context_choice') return value || '—';
    const answer = String(value == null ? '' : value);
    if (!answer) return '—';
    const option = C.options(q).find(
      (item) => String(item.id) === answer || String(item.label) === answer,
    );
    // A recovered snapshot may no longer contain the saved option. Do not
    // print internal IDs or infer a choice from the revealed correct answer.
    return option ? option.label : '已保存的选项（当前选项不可用）';
  }
  function feedbackCard(feedback, q) {
    const f = feedback || {},
      card = el('section', 'pv-card pv-q');
    const forgot = f.response_kind === 'forgot',
      correct = f.is_correct === true;
    const label = forgot
      ? '已标记为忘了 · 按未掌握记录'
      : correct
        ? '回答正确'
        : q && q.retry
          ? '仍需巩固'
          : '首答错误 · 已记录';
    const verdict = el(
      'div',
      `pv-verdict pv-verdict--${forgot ? 'forgot' : correct ? 'ok' : 'bad'}`,
    );
    verdict.append(el('span', 'ic', correct ? '✓' : forgot ? '—' : '×'), el('span', '', label));
    card.append(verdict);
    if (f.idempotent && f.local_answer_differs)
      card.append(el('p', 'pv-alert', '这道题已在其他窗口或设备提交，以下是已保存的结果。'));
    const answers = el('dl', 'pv-answers');
    if (f.revealed_answer != null)
      answers.append(el('dt', '', '正确答案'), el('dd', 'correct', f.revealed_answer));
    answers.append(
      el('dt', '', '你的答案'),
      el('dd', '', forgot ? '忘了' : studentAnswer(q, f.student_answer)),
    );
    if (
      !forgot &&
      !correct &&
      ['zh_to_en', 'audio_to_en', 'context_fill'].includes(C.mode(q)) &&
      f.revealed_answer != null
    ) {
      answers.append(el('dt', '', '拼写比对'));
      const proof = el('dd', 'pv-proof');
      C.spellingDiff(f.student_answer, f.revealed_answer).forEach((part) =>
        proof.append(
          el(
            part.kind === 'same' ? 'span' : part.kind,
            part.kind === 'same' ? '' : 'pd-' + part.kind,
            part.text,
          ),
        ),
      );
      answers.append(proof);
    }
    card.append(answers);
    const d = f.answer_feedback || {};
    if (Object.values(d).some(Boolean)) {
      const panel = el('div', 'pv-fb'),
        top = el('div', 'pv-fb-top');
      if (d.word) top.append(el('span', 'pv-fb-word', d.word));
      if (d.phonetic) top.append(el('span', 'pv-ipa', d.phonetic));
      if (d.audio_tts_url) top.append(audio(d.audio_tts_url));
      if (top.childNodes.length) panel.append(top);
      if (d.core_meaning_zh || d.translation)
        panel.append(el('p', '', d.core_meaning_zh || d.translation));
      if (d.usage_pattern) panel.append(el('p', 'pv-colloc', d.usage_pattern));
      if (d.example_en) {
        const sentence = el('p', 'pv-example');
        highlight(sentence, d.example_en, d.word);
        panel.append(sentence);
      }
      if (d.example_zh) panel.append(el('p', 'pv-trans', d.example_zh));
      if (d.usage_note) panel.append(el('p', 'pv-note', d.usage_note));
      card.append(panel);
    }
    return card;
  }
  function result(data) {
    const r = data.settlement || (data.flow || {}).settlement || {},
      wrap = el('div', 'pv-result');
    const card = el('section', 'pv-card pv-score');
    card.append(
      el('div', 'pv-eyebrow', '✓ 本次任务已完成'),
      el('h2', '', '首答正确率'),
      el(
        'p',
        'big',
        `${Number(r.accuracy || 0)
          .toFixed(1)
          .replace(/\.0$/, '')}%`,
      ),
      el(
        'p',
        'frac',
        `${r.correct_count || 0} / ${r.total_count || r.scorable_count || 0} 首答正确`,
      ),
    );
    card.append(
      stats([
        [r.retry_count || 0, '再测完成'],
        [r.deferred_review_count || r.needs_review_count || 0, '仍待复习'],
        [r.skipped_count || 0, '资料不足跳过'],
      ]),
    );
    card.append(
      el('p', 'note', '首答成绩已记录；再测用于巩固，不改变首答成绩；仍待复习的词会进入后续复习。'),
    );
    wrap.append(card);
    if ((r.forgot_items || []).length) {
      const list = el('aside', 'pv-card pv-list');
      list.append(el('h3', '', '这次忘了的词'));
      r.forgot_items.forEach((item) => {
        const row = el('div', 'pv-row'),
          text = el('div');
        text.append(
          el('b', '', item.word || item.revealed_answer),
          el('p', '', item.meaning || item.revealed_answer),
        );
        row.append(text);
        if (item.audio_tts_url) row.append(audio(item.audio_tts_url));
        list.append(row);
      });
      wrap.append(list);
    }
    return wrap;
  }
  function rail(data, state) {
    const node = document.getElementById('pv-rail'),
      steps = el('div', 'pv-steps'),
      f = data.flow || {};
    node.replaceChildren();
    let done = 0,
      total = 0;
    if (state.startsWith('review')) {
      const r = data.review || data.preflight || {};
      done = Number(r.answered_count || 0);
      total = C.reviewCount(r);
      steps.append(
        el('span', 'pv-step pv-step--current', `↻ 今日复习 ${done} / ${total}`),
        el('span', 'pv-step', '→ 回到本任务'),
      );
    } else {
      const counts = f.phase_counts || {},
        phases = C.PHASES.filter((p) => Number(counts[p]) > 0 || p === f.phase);
      phases.forEach((phase, index) => {
        const current = phase === f.phase,
          passed = state === 'result' || C.PHASES.indexOf(phase) < C.PHASES.indexOf(f.phase);
        const step = el(
          'span',
          `pv-step${current ? ' pv-step--current' : passed ? ' pv-step--done' : ''}`,
        );
        step.append(el('i', '', passed ? '✓' : index + 1), el('span', '', C.LABELS[phase]));
        if (current) {
          done =
            phase === 'familiarity'
              ? (f.familiarity || []).filter((w) => w.viewed).length
              : Number(f.phase_index || 0);
          total = Number(counts[phase] || f.group_size || 0);
          step.append(el('small', '', `${done} / ${total}`));
          step.setAttribute('aria-current', 'step');
        }
        steps.append(step);
      });
    }
    if (!steps.childNodes.length) {
      node.hidden = true;
      return;
    }
    node.hidden = false;
    node.append(steps);
    const bar = el('div', 'pv-railbar'),
      value =
        state === 'result' ? 100 : Math.min(100, total ? Math.round((done / total) * 100) : 0),
      fill = el('span');
    bar.setAttribute('role', 'progressbar');
    bar.setAttribute('aria-label', '当前阶段进度');
    bar.setAttribute('aria-valuemin', '0');
    bar.setAttribute('aria-valuemax', '100');
    bar.setAttribute('aria-valuenow', value);
    fill.style.width = value + '%';
    bar.append(fill);
    node.append(bar);
  }
  root.PracticeVocabularyDetails = {
    el,
    button,
    audio,
    material,
    highlight,
    stats,
    feedbackCard,
    result,
    rail,
  };
})(window);
