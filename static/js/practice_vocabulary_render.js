(function (root) {
  'use strict';
  const C = root.PracticeVocabularyCore,
    D = root.PracticeVocabularyDetails;
  const { el, button, audio } = D;
  const ERROR_MESSAGES = {
    identity_missing: '请先前往练习中心确认学生身份。',
    identity_changed: '身份已变化，请返回任务列表重新进入。',
    staff_mode: '教师或课堂模式下不能代学生作答。',
    ambiguous_student_name: '系统中有同名学生，请使用学生账号登录。',
    student_account_missing: '学生账号未开通，请联系老师。',
    student_account_unlinked: '学生账号未关联档案，请联系老师。',
    task_not_found: '未找到可访问的任务，请返回任务列表。',
    task_not_vocabulary_v2: '该词汇任务请在小程序完成。',
    feature_disabled: '网页版背单词暂未开放，请在小程序完成。',
    task_expired: '已过截止时间，结算未完成；作答记录已保存。',
  };
  function input(q, draft, correction) {
    const wrap = el('div', 'pv-line'),
      label = el(
        'label',
        'pv-input-label',
        correction ? '照正确答案输入一次' : C.mode(q) === 'en_to_zh' ? '中文释义' : '你的答案',
      );
    label.htmlFor = 'pv-answer';
    const field = el('input');
    field.id = 'pv-answer';
    field.type = 'text';
    field.value = draft || '';
    const chinese = C.mode(q) === 'en_to_zh' || (correction && C.mode(q) === 'audio_to_zh');
    field.maxLength = chinese || (correction && C.choice(q)) ? 200 : Number(q.answer_length) || 100;
    field.lang = chinese ? 'zh' : 'en';
    field.inputMode = 'text';
    field.autocomplete = 'off';
    field.spellcheck = false;
    field.setAttribute('autocorrect', 'off');
    field.setAttribute('autocapitalize', 'off');
    field.setAttribute('enterkeyhint', 'done');
    field.setAttribute('data-gramm', 'false');
    field.placeholder = chinese ? '输入中文释义' : '在这里输入';
    field.setAttribute('aria-describedby', 'pv-input-message');
    wrap.append(label, field, el('p', 'pv-linehint', 'Enter 提交 · 中文输入法确认候选词不会提交'));
    const message = el('p', 'pv-status-message');
    message.id = 'pv-input-message';
    message.setAttribute('role', 'status');
    wrap.append(message);
    return wrap;
  }
  function familiarity(model) {
    const items = model.data.flow.familiarity || [],
      item = items[model.familiarIndex] || {},
      wrap = el('div', 'pv-cols');
    const entry = el('section', 'pv-card pv-entry'),
      top = el('div', 'pv-eyebrow');
    top.append(
      el('span', '', '熟悉材料'),
      el('span', 'pv-tag', `${model.familiarIndex + 1} / ${items.length}`),
    );
    entry.append(top, el('h2', 'pv-headword', item.word));
    const ipa = el('div', 'pv-ipa-row');
    if (item.phonetic) ipa.append(el('span', 'pv-ipa', item.phonetic));
    if (item.audio_tts_url) ipa.append(audio(item.audio_tts_url));
    entry.append(ipa);
    if (item.meaning || item.core_meaning_zh || item.translation)
      entry.append(el('p', 'pv-meaning', item.meaning || item.core_meaning_zh || item.translation));
    const dots = el('div', 'pv-dots');
    dots.setAttribute(
      'aria-label',
      `已浏览 ${items.filter((w) => w.viewed).length} / ${items.length} 词`,
    );
    items.forEach((word, index) =>
      dots.append(el('span', index === model.familiarIndex ? 'c' : word.viewed ? 'v' : '')),
    );
    dots.append(el('em', '', '看过后进入提取练习'));
    entry.append(dots);
    wrap.append(entry);
    const material = D.material(item);
    if (material.childNodes.length) wrap.append(material);
    return wrap;
  }
  function question(model) {
    const q = model.q || {},
      mode = C.mode(q),
      prompt = (q.question || {}).prompt || {},
      card = el('section', 'pv-card pv-q');
    const kind = el('div', 'pv-qkind');
    kind.append(el('span', '', C.MODE_LABELS[mode] || '词汇练习'));
    if (q.context_role === 'guide') kind.append(el('span', 'pv-badge', '引导练习 · 不计分'));
    card.append(kind);
    if (mode === 'en_to_zh') {
      card.append(el('h2', 'pv-prompt-word', prompt.word));
      if (prompt.phonetic) card.append(el('p', 'pv-ipa', prompt.phonetic));
    } else if (mode === 'zh_to_en') card.append(el('h2', 'pv-prompt-zh', prompt.meaning));
    else if (mode.startsWith('context')) {
      if (prompt.sentence) {
        const sentence = el('p', 'pv-sentence');
        D.highlight(sentence, prompt.sentence, mode === 'context_choice' ? prompt.target_word : '');
        card.append(sentence);
      } else if (mode === 'context_choice' && prompt.target_word)
        card.append(el('p', 'pv-sentence', prompt.target_word));
      if (mode === 'context_fill' && prompt.translation) {
        const translated = el('div', 'pv-transbox');
        translated.append(
          el('span', '', prompt.translation_label || '译文'),
          document.createTextNode(prompt.translation),
        );
        card.append(translated);
      }
    }
    if (model.audioUrl) card.append(audio(model.audioUrl, mode.startsWith('audio')));
    card.append(
      el(
        'p',
        'pv-instr',
        prompt.instruction ||
          (C.choice(q) ? '选择最合适的一项。' : '凭记忆作答；想不起来可以点“忘了”。'),
      ),
    );
    if (prompt.input_hint) card.append(el('p', 'pv-instr', prompt.input_hint));
    if (C.choice(q)) {
      const list = el('div', 'pv-options');
      list.setAttribute('role', 'radiogroup');
      list.setAttribute('aria-label', '答案选项');
      C.options(q).forEach((option, index) => {
        const item = button('', `select:${index}`, 'pv-opt');
        item.dataset.option = index;
        item.setAttribute('role', 'radio');
        item.setAttribute('aria-checked', String(model.selected === index));
        item.tabIndex = index === (model.selected >= 0 ? model.selected : 0) ? 0 : -1;
        item.append(
          el('kbd', '', index + 1),
          el('span', 'pv-option-label', option.label),
          el('span', 'mark', model.selected === index ? '✓' : ''),
        );
        list.append(item);
      });
      card.append(list);
      const message = el('p', 'pv-status-message');
      message.id = 'pv-input-message';
      message.setAttribute('role', 'status');
      card.append(message);
    } else card.append(input(q, model.draft, false));
    return card;
  }
  function correction(model) {
    const q = model.q || {},
      f = model.feedback || {},
      card = el('section', 'pv-card pv-q');
    card.append(
      el('div', 'pv-alert', '订正：照正确答案输入一次（不计分）'),
      el(
        'div',
        'pv-qkind',
        `第 ${Number(q.correction_count || f.correction_count || 0) + 1} / ${q.correction_max_attempts || 2} 次`,
      ),
    );
    card.append(
      el('p', 'pv-input-label', '正确答案'),
      el('h2', 'pv-prompt-zh', q.revealed_answer != null ? q.revealed_answer : f.revealed_answer),
    );
    if (model.correctionError) card.append(el('p', 'pv-status-message', '还不对，再试一次。'));
    if (model.audioUrl) card.append(audio(model.audioUrl));
    card.append(input(q, model.draft, true));
    return card;
  }
  function inter(title, text) {
    const card = el('section', 'pv-card pv-inter');
    card.append(el('h2', '', title), el('p', '', text));
    return card;
  }
  function intermediate(model) {
    const f = model.data.flow || {},
      r = model.data.review || model.data.preflight || {},
      access = model.data.access || {};
    switch (model.state) {
      case 'blocked':
        return inter(
          model.error === 'feature_disabled' ? '暂未开放' : '暂时无法进入',
          model.message || ERROR_MESSAGES[model.error] || '请返回任务列表重新进入。',
        );
      case 'locked_future':
        return inter('尚未开放', `${access.task_date || access.date || ''} 开放后再来学习。`);
      case 'read_only': {
        const card = inter(
          '本次任务已截止',
          model.error === 'task_expired'
            ? ERROR_MESSAGES.task_expired
            : '已于次日 03:00 截止，作答已保存。',
        );
        card.append(
          D.stats([
            [f.group_index || 0, '已完成组'],
            [f.base_progress_completed || 0, '已保存首答'],
            [f.base_progress_total || 0, '首答总题数'],
          ]),
        );
        return card;
      }
      case 'review_gate':
        return inter(
          '先完成今日复习',
          `开始本任务前先完成今日复习${C.reviewCount(r) ? `，本批约 ${C.reviewCount(r)} 题` : ''}。完成后自动回到本任务。`,
        );
      case 'retry_intro':
        return inter(
          '错题再测',
          `${(f.phase_counts || {}).retry || f.remediation_pending_count || 0} 题，只用于巩固，不改变首答成绩。`,
        );
      case 'group_done': {
        const result = (f.group_results || []).slice(-1)[0] || {};
        const card = inter('本组完成', `接下来进入第 ${f.group_number} 组。`);
        card.append(
          D.stats([
            [`${result.correct_count || 0} / ${result.scorable_count || 0}`, '首答正确'],
            [result.retry_count || 0, '再测完成'],
            [(result.weak_word_ids || []).length, '仍待复习'],
          ]),
        );
        return card;
      }
      case 'settle_failed':
        return inter('还差最后一步', '作答都已保存，只差最后一步结算。请重试提交任务结果。');
      case 'settling':
      case 'review_settling':
        return inter('正在提交结果…', '作答记录已保存，请稍候。');
      case 'save_failed':
        return inter('保存失败', '网络暂时不可用，输入已保留。请重试；重试不会重复记分。');
      case 'not_started':
        return inter('准备开始', '先熟悉本组材料，再凭记忆完成练习。学习进度会随作答保存。');
      default:
        return inter('正在同步学习进度…', '请稍候。');
    }
  }
  class View {
    constructor() {
      this.stage = document.getElementById('pv-stage');
      this.bar = document.getElementById('pv-bar');
      this.toastTimer = 0;
    }
    show(model) {
      const active = document.activeElement;
      const keepFocus = active && (active.closest('.pv-head') || active.closest('dialog'));
      const task = model.data.task || {},
        chips = document.getElementById('pv-chips');
      chips.replaceChildren();
      if (task.goal_label) chips.append(el('span', 'pv-chip pv-chip--goal', task.goal_label));
      const flow = model.data.flow;
      if (flow && flow.group_count && !flow.completed)
        chips.append(el('span', 'pv-chip', `第 ${flow.group_number} / ${flow.group_count} 组`));
      const access = model.data.access || {},
        dateLabel = access.task_date_label || access.label;
      if (dateLabel) chips.append(el('span', 'pv-chip', dateLabel));
      document.getElementById('pv-title').textContent = task.title || '背单词';
      D.rail(model.data, model.state);
      let content;
      if (model.state === 'familiarity') content = familiarity(model);
      else if (model.state.endsWith('question')) content = question(model);
      else if (model.state.endsWith('correction')) content = correction(model);
      else if (model.state.endsWith('feedback')) content = D.feedbackCard(model.feedback, model.q);
      else if (model.state === 'result') content = D.result(model.data);
      else content = intermediate(model);
      if (
        [
          'question',
          'review_question',
          'feedback',
          'review_feedback',
          'correction',
          'review_correction',
        ].includes(model.state)
      ) {
        const wrap = el('div', 'pv-qwrap');
        wrap.append(content);
        content = wrap;
      }
      this.stage.replaceChildren(content);
      this.stage.setAttribute('aria-busy', String(model.busy));
      this.controls(model);
      if (!keepFocus && !model.busy) {
        const target =
          this.stage.querySelector('#pv-answer, [role="radio"][tabindex="0"]') ||
          (model.state.endsWith('feedback')
            ? this.bar.querySelector('[data-action="primary"]')
            : null);
        if (target) target.focus({ preventScroll: true });
      }
    }
    controls(model) {
      const left = el('div', 'left'),
        right = el('div', 'right'),
        hint = el(
          'span',
          'hint',
          model.state === 'familiarity' ? '← 回看已浏览的词 · Enter 下一词' : '作答后自动保存',
        );
      if (model.state === 'familiarity') {
        const previous = button('上一词', 'previous', 'pv-btn pv-btn--ghost');
        previous.disabled = model.familiarIndex < 1;
        left.append(previous);
      }
      if (model.state.endsWith('question'))
        left.append(button('忘了', 'forgot', 'pv-btn pv-btn--ghost'));
      const labels = {
        familiarity: '看过 · 下一词',
        question: '提交答案',
        review_question: '提交答案',
        correction: '提交订正',
        review_correction: '提交订正',
        feedback: '继续',
        review_feedback: '继续',
        retry_intro: '开始再测',
        group_done: '开始下一组',
        not_started: '开始学习',
        review_gate: '开始复习',
        save_failed: '重试保存',
        settle_failed: '重试结算',
      };
      if (labels[model.state]) {
        const primary = button('', 'primary', 'pv-btn pv-btn--primary');
        primary.append(el('span', 'pv-primary-label', labels[model.state]), el('kbd', '', '↵'));
        right.append(primary);
      } else if (['result', 'blocked', 'read_only', 'locked_future'].includes(model.state))
        right.append(button('返回任务列表', 'back', 'pv-btn pv-btn--primary'));
      this.bar.replaceChildren(left, hint, right);
      this.busy(model.busy);
    }
    busy(value) {
      [...this.stage.querySelectorAll('button'), ...this.bar.querySelectorAll('button')].forEach(
        (node) => {
          if (!node.dataset.wasDisabled) node.dataset.wasDisabled = String(node.disabled);
          node.disabled = value || node.dataset.wasDisabled === 'true';
          node.setAttribute('aria-busy', String(value));
          const label = node.querySelector('.pv-primary-label');
          if (label) {
            if (!node.dataset.label) node.dataset.label = label.textContent;
            label.textContent = value ? '提交中…' : node.dataset.label;
          }
        },
      );
      const input = document.getElementById('pv-answer');
      if (input) input.readOnly = value;
      this.stage.setAttribute('aria-busy', String(value));
    }
    status(label, tone) {
      const node = document.getElementById('pv-save');
      node.textContent = (tone === 'saved' ? '✓ ' : tone === 'error' ? '! ' : '◦ ') + label;
      node.dataset.tone = tone || '';
    }
    message(text) {
      const node = document.getElementById('pv-input-message');
      if (node) node.textContent = text;
    }
    toast(text) {
      const node = document.getElementById('pv-toast');
      clearTimeout(this.toastTimer);
      node.textContent = text;
      node.hidden = false;
      this.toastTimer = setTimeout(() => {
        node.hidden = true;
      }, 4500);
    }
    audio(state) {
      document.querySelectorAll('[data-audio]').forEach((node) => {
        node.dataset.state = state;
        node.querySelector('.ic').textContent =
          state === 'playing' ? '▥' : state === 'loading' ? '◌' : state === 'error' ? '↻' : '▶';
        node.querySelector('.pv-audio-label').textContent = {
          idle: '播放音频',
          loading: '加载中…',
          playing: '正在播放',
          error: '播放失败 · 重试',
        }[state];
      });
    }
  }
  root.PracticeVocabularyView = View;
})(window);
