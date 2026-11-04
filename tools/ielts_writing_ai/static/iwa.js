/* IELTS writing AI trial tool — page scripts (no framework, no innerHTML for data). */
(function () {
  'use strict';

  var body = document.body;
  var ROOT = body.getAttribute('data-root') || '/';
  var CSRF = body.getAttribute('data-csrf') || '';

  // ---------------------------------------------------------------- helpers
  function url(path) { return ROOT.replace(/\/$/, '') + '/' + path.replace(/^\//, ''); }

  function api(method, path, payload) {
    var options = { method: method, headers: { 'X-IWA-CSRF': CSRF, Accept: 'application/json' }, credentials: 'same-origin' };
    if (payload instanceof FormData) {
      options.body = payload;
    } else if (payload !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(payload);
    }
    return fetch(url(path), options).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (response.status === 401 && body.getAttribute('data-page') !== 'login') {
          window.location.href = url('login');
        }
        data.httpStatus = response.status;
        data.ok = response.ok && data.ok !== false;
        return data;
      });
    }, function () {
      return { ok: false, message: '网络连接失败，请检查网络后重试' };
    });
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      var value = attrs[key];
      if (value === null || value === undefined || value === false) return;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else if (key.indexOf('on') === 0) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? '' : value);
    });
    (children || []).forEach(function (child) {
      if (child === null || child === undefined || child === false) return;
      node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
    });
    return node;
  }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  var toastTimer = null;
  function toast(message) {
    var node = document.getElementById('toast');
    if (!node) return;
    node.textContent = message;
    node.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { node.classList.remove('is-visible'); }, 2200);
  }

  function copyText(text, label) {
    var done = function () { toast((label || '内容') + '已复制'); };
    var fallback = function () {
      var area = el('textarea', { readonly: true });
      // CSSOM properties, not a style attribute, so the strict CSP allows it.
      area.style.position = 'fixed';
      area.style.top = '-1000px';
      area.style.opacity = '0';
      area.value = text;
      document.body.appendChild(area);
      area.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      document.body.removeChild(area);
      if (ok) done(); else toast('复制失败，请手动选择文本复制');
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else {
      fallback();
    }
  }

  function countWords(text) {
    var matches = (text || '').match(/[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*/g);
    return matches ? matches.length : 0;
  }

  function formatTime(iso) {
    if (!iso) return '';
    var date = new Date(iso);
    if (isNaN(date.getTime())) return iso;
    return date.toLocaleString('zh-CN', { hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  }

  function band(value) { return value === null || value === undefined ? '—' : Number(value).toFixed(1); }

  function paragraphs(text) {
    return (text || '').split(/\n+/).map(function (p) { return p.trim(); }).filter(Boolean);
  }

  function essayNode(text, highlight) {
    var wrap = el('div', { class: 'essay' });
    var needle = (highlight || '').trim().toLowerCase();
    paragraphs(text).forEach(function (paragraph) {
      var p = el('p');
      var at = needle ? paragraph.toLowerCase().indexOf(needle) : -1;
      if (at >= 0) {
        p.appendChild(document.createTextNode(paragraph.slice(0, at)));
        p.appendChild(el('mark', { text: paragraph.slice(at, at + needle.length) }));
        p.appendChild(document.createTextNode(paragraph.slice(at + needle.length)));
      } else {
        p.textContent = paragraph;
      }
      wrap.appendChild(p);
    });
    return wrap;
  }

  function updateQuota(quota) {
    var badge = document.getElementById('quotaBadge');
    if (!badge || !quota) return;
    clear(badge);
    badge.appendChild(document.createTextNode('今日剩余 '));
    badge.appendChild(el('strong', { text: String(quota.remaining) }));
    badge.appendChild(document.createTextNode('/' + quota.limit));
  }

  // Word-level diff (LCS) for the sentence comparison view.
  function tokens(text) { return (text || '').match(/[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*|[^\sA-Za-z0-9]/g) || []; }

  function diffTokens(a, b) {
    var n = a.length, m = b.length, i, j;
    var dp = [];
    for (i = 0; i <= n; i++) { dp.push(new Array(m + 1).fill(0)); }
    for (i = n - 1; i >= 0; i--) {
      for (j = m - 1; j >= 0; j--) {
        dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
    var ops = [];
    i = 0; j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) { ops.push(['eq', a[i]]); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) { ops.push(['del', a[i]]); i++; }
      else { ops.push(['ins', b[j]]); j++; }
    }
    while (i < n) { ops.push(['del', a[i++]]); }
    while (j < m) { ops.push(['ins', b[j++]]); }
    return ops;
  }

  function diffNode(original, revised) {
    var p = el('p', { class: 'sentence__diff' });
    var prev = '';
    diffTokens(tokens(original), tokens(revised)).forEach(function (op, index) {
      var token = op[1];
      var tight = /^[.,;:!?%)\]’”'"]$/.test(token) || /^[(\[“‘]$/.test(prev);
      if (index > 0 && !tight) p.appendChild(document.createTextNode(' '));
      if (op[0] === 'eq') p.appendChild(document.createTextNode(token));
      else p.appendChild(el(op[0] === 'del' ? 'del' : 'ins', { text: token }));
      prev = token;
    });
    return p;
  }

  // ------------------------------------------------------------------ pages
  // Per-user draft store (see draft.js). Null when signed out or storage is unavailable.
  function storage() {
    try { return window.localStorage; } catch (e) { return null; }
  }
  function drafts() {
    var store = storage();
    var userKey = body.getAttribute('data-user-key') || '';
    return store && window.IWADraft && userKey ? window.IWADraft.create(store, userKey) : null;
  }
  function initDraftHygiene() {
    var store = storage();
    if (!store || !window.IWADraft) return;
    window.IWADraft.purgeLegacy(store);  // pre-fix global draft key
    var userKey = body.getAttribute('data-user-key') || '';
    if (userKey) window.IWADraft.purgeOthers(store, userKey);  // another account used this browser
  }

  function initLogout() {
    var button = document.getElementById('logoutBtn');
    if (!button) return;
    button.addEventListener('click', function () {
      var store = drafts();
      if (store && store.hasContent() && !window.confirm('退出后，本机保存的未提交草稿会被清除。确定退出吗？')) return;
      if (store) store.clear();
      api('POST', 'api/logout', {}).then(function () { window.location.replace(url('login')); });
    });
  }

  // A page restored from the back/forward cache after logout must not show stale content.
  window.addEventListener('pageshow', function (event) {
    if (event.persisted && body.getAttribute('data-page') !== 'login') window.location.reload();
  });

  function initLogin() {
    var form = document.getElementById('loginForm');
    var error = document.getElementById('loginError');
    var input = document.getElementById('loginCode');
    input.focus();
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      error.hidden = true;
      var button = form.querySelector('button[type=submit]');
      button.disabled = true;
      api('POST', 'api/login', { code: input.value }).then(function (data) {
        button.disabled = false;
        if (!data.ok) {
          error.textContent = data.message || '登录失败';
          error.hidden = false;
          return;
        }
        var next = new URLSearchParams(window.location.search).get('next');
        window.location.href = next && next.charAt(0) === '/' && next.charAt(1) !== '/' ? next : url('');
      });
    });
  }

  function initNew() {
    var form = document.getElementById('newForm');
    var essay = document.getElementById('essayInput');
    var wordCount = document.getElementById('wordCount');
    var wordHint = document.getElementById('wordHint');
    var imageField = document.getElementById('imageField');
    var imageInput = document.getElementById('imageInput');
    var preview = document.getElementById('imagePreview');
    var hint = document.getElementById('dropzoneHint');
    var clearBtn = document.getElementById('clearImage');
    var dropzone = document.getElementById('dropzone');
    var formError = document.getElementById('formError');
    var submitBtn = document.getElementById('submitBtn');
    var draftStore = drafts();

    function taskType() { return form.querySelector('input[name=task_type]:checked').value; }
    function refreshWords() {
      var n = countWords(essay.value);
      var min = taskType() === 'task1' ? 150 : 250;
      wordCount.textContent = n;
      wordHint.textContent = (taskType() === 'task1' ? 'Task 1' : 'Task 2') + ' 要求至少 ' + min + ' 词' + (n && n < min ? '（当前不足）' : '');
    }
    function refreshTask() {
      imageField.hidden = taskType() !== 'task1';
      refreshWords();
    }
    function saveDraft() {
      if (!draftStore) return;
      draftStore.save({
        task_type: taskType(), prompt_text: form.prompt_text.value, essay_text: essay.value, target_band: form.target_band.value
      });
    }
    function restoreDraft() {
      var draft = draftStore && draftStore.load();
      if (!draft) return;
      var radio = form.querySelector('input[name=task_type][value="' + draft.task_type + '"]');
      if (radio) radio.checked = true;
      form.prompt_text.value = draft.prompt_text || '';
      essay.value = draft.essay_text || '';
      if (draft.target_band) form.target_band.value = draft.target_band;
    }
    function showImage(file) {
      if (!file) { preview.hidden = true; hint.hidden = false; clearBtn.hidden = true; return; }
      preview.src = URL.createObjectURL(file);
      preview.hidden = false;
      hint.hidden = true;
      clearBtn.hidden = false;
    }

    restoreDraft();
    refreshTask();
    form.querySelectorAll('input[name=task_type]').forEach(function (radio) { radio.addEventListener('change', function () { refreshTask(); saveDraft(); }); });
    essay.addEventListener('input', function () { refreshWords(); saveDraft(); });
    form.prompt_text.addEventListener('input', saveDraft);
    form.target_band.addEventListener('change', saveDraft);
    imageInput.addEventListener('change', function () { showImage(imageInput.files[0]); });
    clearBtn.addEventListener('click', function () { imageInput.value = ''; showImage(null); });
    ['dragenter', 'dragover'].forEach(function (name) { dropzone.addEventListener(name, function () { dropzone.classList.add('is-over'); }); });
    ['dragleave', 'drop'].forEach(function (name) { dropzone.addEventListener(name, function () { dropzone.classList.remove('is-over'); }); });

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      formError.hidden = true;
      form.querySelectorAll('[data-error-for]').forEach(function (node) { node.textContent = ''; });
      var data = new FormData(form);
      if (taskType() !== 'task1' || !imageInput.files.length) data.delete('image');
      submitBtn.disabled = true;
      submitBtn.textContent = '提交中…';
      api('POST', 'api/submissions', data).then(function (result) {
        if (result.ok) {
          if (draftStore) draftStore.clear();
          window.location.href = result.url;
          return;
        }
        submitBtn.disabled = false;
        submitBtn.textContent = '开始批改';
        var fields = result.fields || {};
        Object.keys(fields).forEach(function (key) {
          var node = form.querySelector('[data-error-for="' + key + '"]');
          if (node) node.textContent = fields[key];
        });
        if (!Object.keys(fields).length) {
          formError.textContent = result.message || '提交失败，请稍后重试';
          formError.hidden = false;
        }
      });
    });
  }

  // ----------------------------------------------------------- submission
  function initSubmission() {
    var publicId = body.getAttribute('data-submission');
    var state = { data: null, tab: 'evaluate', onlyChanged: true, highlight: '' };
    var pollTimer = null;
    var rendered = {};

    var panels = {};
    document.querySelectorAll('[data-panel]').forEach(function (node) { panels[node.getAttribute('data-panel')] = node; });

    document.querySelectorAll('.tab').forEach(function (tab) {
      tab.addEventListener('click', function () { selectTab(tab.getAttribute('data-tab')); });
    });
    document.querySelector('[data-copy="original"]').addEventListener('click', function () {
      if (state.data) copyText(state.data.essay_text, '原稿');
    });

    function selectTab(name) {
      state.tab = name;
      document.querySelectorAll('.tab').forEach(function (tab) {
        var active = tab.getAttribute('data-tab') === name;
        tab.classList.toggle('is-active', active);
        tab.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      Object.keys(panels).forEach(function (key) { panels[key].hidden = key !== name; });
    }

    function load() {
      api('GET', 'api/submissions/' + encodeURIComponent(publicId)).then(function (result) {
        if (!result.ok) {
          if (result.httpStatus === 404) window.location.reload();
          schedule(5000);
          return;
        }
        state.data = result.submission;
        updateQuota(result.quota);
        render();
        var active = Object.keys(state.data.generations).some(function (kind) {
          var g = state.data.generations[kind];
          return g && (g.status === 'queued' || g.status === 'running');
        }) || (state.data.image && state.data.image.status === 'pending');
        if (active) schedule(2500);
      });
    }

    function schedule(ms) { clearTimeout(pollTimer); pollTimer = setTimeout(load, ms); }

    function renderSource() {
      var d = state.data;
      document.getElementById('sourceMeta').textContent =
        d.task_label + ' · ' + d.word_count + ' 词（要求 ≥ ' + d.minimum_words + '）· 改写目标 Band ' + band(d.target_band) + ' · ' + formatTime(d.created_at);
      document.getElementById('promptText').textContent = d.prompt_text;
      var original = document.getElementById('originalEssay');
      var replacement = essayNode(d.essay_text, state.highlight);
      replacement.id = 'originalEssay';
      original.parentNode.replaceChild(replacement, original);
      var imageBlock = document.getElementById('imageBlock');
      if (d.image) {
        imageBlock.hidden = false;
        var img = document.getElementById('taskImage');
        if (img.getAttribute('src') !== d.image.url) img.src = d.image.url;
        var note = document.getElementById('imageNote');
        note.classList.remove('is-warn');
        if (d.image.status === 'pending') note.textContent = '正在识别题图…';
        else if (d.image.status === 'ready') note.textContent = '识图模型读到的图表信息（请核对是否与题图一致）：\n' + d.image.description;
        else {
          note.textContent = (d.image.unusable_reason || '题图不可用') + '：本次不评 Task Achievement，也不给总分。' +
            (d.image.description ? '\n\n' + d.image.description : '');
          note.classList.add('is-warn');
        }
      } else {
        imageBlock.hidden = true;
      }
    }

    function regenerate(kind) {
      api('POST', 'api/submissions/' + encodeURIComponent(publicId) + '/generations/' + kind, {}).then(function (result) {
        if (!result.ok) { toast(result.message || '无法重新生成'); return; }
        toast('已开始重新生成');
        rendered[kind] = null;
        load();
      });
    }

    function regenButton(kind) {
      return el('button', {
        type: 'button', class: 'btn btn--ghost btn--sm', text: '重新生成',
        onclick: function () {
          if (window.confirm('重新生成会消耗 1 次额度，并替换当前结果。继续吗？')) regenerate(kind);
        }
      });
    }

    function provenance(g) {
      var parts = [];
      if (g.model) parts.push('模型 ' + g.model);
      if (g.prompt_version) parts.push('提示词 ' + g.prompt_version);
      if (g.finished_at) parts.push('生成于 ' + formatTime(g.finished_at));
      parts.push('AI 结果仅供参考');
      return el('p', { class: 'provenance', text: parts.join(' · ') });
    }

    function renderPanel(kind) {
      var g = state.data.generations[kind];
      var panel = panels[kind];
      var dot = document.querySelector('[data-dot="' + kind + '"]');
      dot.setAttribute('data-status', g ? g.status : '');
      var signature = g ? g.id + ':' + g.status + ':' + (kind === 'refine' ? state.onlyChanged : '') : 'none';
      if (rendered[kind] === signature) return;
      rendered[kind] = signature;
      clear(panel);
      if (!g) { panel.appendChild(el('div', { class: 'state', text: '暂无结果' })); return; }
      if (g.status === 'queued' || g.status === 'running') {
        var waiting = state.data.image && state.data.image.status === 'pending' ? '正在识别题图，随后开始生成…' : 'AI 正在生成，通常需要 20–60 秒。可以先查看其他标签。';
        panel.appendChild(el('div', { class: 'state' }, [el('div', { class: 'spinner', 'aria-hidden': 'true' }), el('p', { text: waiting })]));
        return;
      }
      if (g.status === 'failed') {
        panel.appendChild(el('div', { class: 'state state--error' }, [
          el('p', { text: (g.error && g.error.message) || '生成失败' }),
          el('button', { type: 'button', class: 'btn btn--primary', text: '重新生成（消耗 1 次）', onclick: function () { regenerate(kind); } })
        ]));
        return;
      }
      if (kind === 'evaluate') renderEvaluation(panel, g);
      else if (kind === 'refine') renderRefine(panel, g);
      else renderRewrite(panel, g);
      panel.appendChild(provenance(g));
    }

    // Copy texts come from the server so they always carry the result's limits.
    function copyButton(label, text, toastLabel) {
      return el('button', {
        type: 'button', class: 'btn btn--ghost btn--sm', text: label, disabled: !text,
        onclick: function () { copyText(text, toastLabel); }
      });
    }

    function quoteButton(entry) {
      if (!entry.quote) return null;
      return el('button', {
        type: 'button', class: 'issue__quote' + (entry.quote_found ? '' : ' is-missing'),
        title: entry.quote_found ? '在左侧原文中标出' : '',
        onclick: function () {
          if (!entry.quote_found) return;
          state.highlight = entry.quote;
          renderSource();
          var mark = document.querySelector('#originalEssay mark');
          if (mark) mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, ['“' + entry.quote + '”', entry.quote_found ? null : el('span', { class: 'issue__flag', text: '（未在原文中找到，不作为评分依据）' })]);
    }

    // -- Task 2 argument map (every quote was verified on the server)
    function verified(quote) { return quoteButton({ quote: quote, quote_found: true }); }

    function argumentNode(a) {
      var box = el('section', { class: 'block argument' }, [
        el('h3', { text: '论证结构检查' }),
        el('p', { class: 'muted small', text: 'AI 标注，引文均已在原文中核实；不单独计分，用来解释 TR / CC 的分数。点击引文可在左侧原文中定位。' })
      ]);
      var p = a.position;
      var consistent = p && p.consistent === true ? '前后一致' : p && p.consistent === false ? '前后不一致' : '';
      box.appendChild(el('div', { class: 'argument__position' }, p ? [
        el('span', { class: 'argument__label', text: '立场' }),
        verified(p.quote),
        consistent ? el('span', { class: 'tag' + (p.consistent ? ' tag--ok' : ' tag--bad'), text: consistent }) : null,
        p.comment ? el('p', { class: 'issue__comment', text: p.comment }) : null
      ] : [
        el('span', { class: 'argument__label', text: '立场' }),
        el('span', { class: 'muted', text: '没有找到可核实的立场句。' })
      ]));
      box.appendChild(el('p', { class: 'subhead', text: '各段中心句' }));
      box.appendChild(el('ol', { class: 'argument__flow' }, (a.paragraphs || []).map(function (item) {
        return el('li', { class: 'argument__step is-' + item.verdict }, [
          el('div', { class: 'argument__step-head' }, [
            el('span', { class: 'tag', text: item.role_label || item.role }),
            el('span', { class: 'tag tag--' + ({ supports: 'ok', weak: 'warn', off_position: 'bad' }[item.verdict] || 'warn'), text: item.verdict_label || item.verdict })
          ]),
          verified(item.main_point),
          item.comment ? el('p', { class: 'issue__comment', text: item.comment }) : null
        ]);
      })));
      var problems = a.problems || [];
      box.appendChild(el('p', { class: 'subhead', text: '论证问题' + (problems.length ? '（' + problems.length + '）' : '') }));
      if (!problems.length) {
        box.appendChild(el('p', { class: 'muted small', text: 'AI 没有标出明显的论证问题（不代表论证没有可改进之处）。' }));
      }
      problems.forEach(function (item) {
        box.appendChild(el('div', { class: 'issue issue--argument' }, [
          el('span', { class: 'tag tag--bad', text: item.label || item.type }),
          ' ',
          verified(item.quote),
          item.comment ? el('p', { class: 'issue__comment', text: item.comment }) : null,
          item.suggestion ? el('p', { class: 'issue__suggestion', text: '建议：' + item.suggestion }) : null
        ]));
      });
      return box;
    }

    // -- evaluation
    function renderEvaluation(panel, g) {
      var r = g.result;
      var copies = g.copy || {};
      var notAssessable = r.overall_band === null || r.overall_band === undefined;
      panel.appendChild(el('div', { class: 'panel-actions' }, [
        copyButton('复制评价', copies.evaluation, '评价'),
        el('span', { class: 'spacer' }),
        regenButton('evaluate')
      ]));
      panel.appendChild(el('div', { class: 'score-hero' + (notAssessable ? ' is-limited' : '') }, [
        el('div', {}, [
          el('div', { class: 'score-hero__band' + (notAssessable ? ' is-text' : ''), text: notAssessable ? '不可评' : band(r.overall_band) }),
          el('div', { class: 'score-hero__label', text: notAssessable ? '总分不可评 · 只保留有依据的语言反馈' : 'AI 预估总分 · 四项平均 · 仅供参考' })
        ]),
        el('div', { class: 'score-chips' }, r.criteria.map(function (c) {
          var off = c.band === null || c.band === undefined;
          return el('div', { class: 'score-chip' + (off ? ' is-off' : ''), title: off ? (c.reason || '不可评') : c.label }, [
            el('b', { text: off ? '—' : band(c.band) }),
            el('span', { text: c.short + (off ? ' 不可评' : '') })
          ]);
        }))
      ]));
      (r.warnings || []).forEach(function (w) { panel.appendChild(el('p', { class: 'notice notice--warn', text: w })); });
      var consistency = (r.consistency_issues || []).filter(function (c) { return c.comment; });
      if (consistency.length) {
        var box = el('div', { class: 'block' }, [
          el('h3', { text: '文内数据自洽检查' }),
          el('p', { class: 'muted small', text: '只检查作文内部的数字和比较是否前后矛盾，不代表数据与题图一致。' })
        ]);
        consistency.forEach(function (c) {
          box.appendChild(el('div', { class: 'issue' }, [quoteButton(c), el('p', { class: 'issue__comment', text: c.comment })]));
        });
        panel.appendChild(box);
      }
      if (r.overall_comment) panel.appendChild(el('div', { class: 'block' }, [el('h3', { text: '总评' }), el('p', { text: r.overall_comment })]));
      if (r.priorities && r.priorities.length) {
        panel.appendChild(el('div', { class: 'block' }, [
          el('h3', { text: '下一步提升重点' }),
          el('ol', { class: 'priorities' }, r.priorities.map(function (p) { return el('li', { text: p }); }))
        ]));
      }
      if (r.argument) panel.appendChild(argumentNode(r.argument));
      r.criteria.forEach(function (c) {
        var off = c.band === null || c.band === undefined;
        var card = el('article', { class: 'criterion' + (off ? ' is-off' : '') }, [
          el('div', { class: 'criterion__head' }, [
            el('h3', { text: c.label + '（' + c.short + '）' }),
            el('span', { class: 'criterion__band', text: off ? '不可评' : 'Band ' + band(c.band) })
          ]),
          off ? el('p', { class: 'criterion__reason', text: c.reason || '缺少评分依据，不评分。' }) : null,
          c.summary ? el('p', {}, [el('strong', { text: '评分理由：' }), c.summary]) : null
        ]);
        var strengths = c.strengths || [];
        if (strengths.length) {
          card.appendChild(el('ul', { class: 'strengths' }, strengths.map(function (s) {
            if (typeof s === 'string') return el('li', { text: s });  // results stored before evidence rules
            return el('li', {}, [quoteButton(s), s.comment ? el('span', { class: 'strength__comment', text: ' ' + s.comment }) : null]);
          })));
        }
        (c.issues || []).forEach(function (issue) {
          card.appendChild(el('div', { class: 'issue' }, [
            quoteButton(issue),
            issue.comment ? el('p', { class: 'issue__comment', text: issue.comment }) : null,
            issue.suggestion ? el('p', { class: 'issue__suggestion', text: '建议：' + issue.suggestion }) : null
          ]));
        });
        panel.appendChild(card);
      });
    }

    // -- refine
    function renderRefine(panel, g) {
      var r = g.result;
      var copies = g.copy || {};
      panel.appendChild(el('div', { class: 'panel-actions' }, [
        copyButton('复制精修全文', copies.full, '精修全文'),
        copyButton('复制修改清单', copies.changes, '修改清单'),
        el('span', { class: 'spacer' }),
        regenButton('refine')
      ]));
      var toggle = el('input', { type: 'checkbox' });
      toggle.checked = state.onlyChanged;
      toggle.addEventListener('change', function () { state.onlyChanged = toggle.checked; renderPanel('refine'); });
      panel.appendChild(el('div', { class: 'refine-summary' }, [
        el('span', { class: 'pill', text: '共 ' + r.sentences.length + ' 句 · 修改 ' + r.changed_count + ' 句' }),
        el('label', { class: 'toggle' }, [toggle, '只看有修改的句子'])
      ]));
      (r.warnings || []).forEach(function (w) { panel.appendChild(el('p', { class: 'notice notice--warn', text: w })); });
      if (r.missing_count) panel.appendChild(el('p', { class: 'notice notice--warn', text: '有 ' + r.missing_count + ' 句 AI 没有返回结果，已按原句保留。' }));
      if (r.summary) panel.appendChild(el('div', { class: 'block' }, [el('h3', { text: '主要问题' }), el('p', { text: r.summary })]));
      var list = el('div', { class: 'sentences' });
      var shown = r.sentences.filter(function (s) { return !state.onlyChanged || s.changed; });
      if (!shown.length) list.appendChild(el('div', { class: 'state', text: r.changed_count ? '' : 'AI 认为没有需要修改的句子。' }));
      shown.forEach(function (s) {
        list.appendChild(el('article', { class: 'sentence' + (s.changed ? '' : ' is-unchanged') }, [
          el('span', { class: 'sentence__no', text: '#' + (s.i + 1) }),
          el('div', { class: 'sentence__body' }, [
            s.changed ? diffNode(s.original, s.revised) : el('p', { class: 'sentence__diff', text: s.original }),
            s.changed && s.tags.length ? el('div', { class: 'tags' }, s.tags.map(function (t) { return el('span', { class: 'tag', text: TAG_LABELS[t] || t }); })) : null,
            s.explanation ? el('p', { class: 'sentence__explain', text: s.explanation }) : null
          ]),
          s.changed ? el('button', { type: 'button', class: 'btn btn--ghost btn--sm', text: '复制', title: '只复制这一句改句', onclick: function () { copyText(s.revised, '改句'); } }) : el('span')
        ]));
      });
      panel.appendChild(list);
      panel.appendChild(el('details', { class: 'full-text' }, [
        el('summary', { text: '精修后全文（' + r.refined_word_count + ' 词）' }),
        essayNode(r.refined_essay)
      ]));
    }

    // -- rewrite
    function renderRewrite(panel, g) {
      var r = g.result;
      var copies = g.copy || {};
      panel.appendChild(el('div', { class: 'panel-actions' }, [
        copyButton('复制改写全文', copies.essay, '改写全文'),
        copyButton('复制改写+说明', copies.with_notes, '改写和说明'),
        el('span', { class: 'spacer' }),
        regenButton('rewrite')
      ]));
      panel.appendChild(el('div', { class: 'rewrite-meta' }, [
        el('span', { class: 'pill', text: '目标 Band ' + band(r.target_band) + '（未经评分验证）' }),
        el('span', { class: 'pill', text: r.word_count + ' 词（服务端计数）' }),
        r.quality_passed === false ? el('span', { class: 'pill pill--warn', text: '质量检查未通过' }) : null
      ]));
      (r.warnings || []).forEach(function (w) { panel.appendChild(el('p', { class: 'notice notice--warn', text: w })); });
      var essayBox = essayNode(r.essay);
      essayBox.classList.add('rewrite-essay');
      panel.appendChild(essayBox);
      if (r.answers && r.answers.length) {
        panel.appendChild(el('div', { class: 'block' }, [
          el('h3', { text: '题目回应对照' }),
          el('p', { class: 'muted small', text: 'AI 标注每个题目要求对应的句子；服务端只核实这些句子确实在改写稿中，是否真正切题请人工判断。' }),
          el('ul', { class: 'answers' }, r.answers.map(function (a) {
            return el('li', {}, [el('strong', { text: a.part + '：' }), el('span', { class: 'answers__quote', text: '“' + a.quote + '”' })]);
          }))
        ]));
      }
      if (r.key_changes.length) {
        panel.appendChild(el('div', { class: 'block' }, [
          el('h3', { text: '关键改动' }),
          el('p', { class: 'muted small', text: '每条改动都已核对：原文在原稿中、改后在改写稿中，并且确实发生了变化。' }),
          el('ol', { class: 'priorities' }, r.key_changes.map(function (c) {
            if (typeof c === 'string') return el('li', { text: c });  // results stored before structured notes
            var body = c.before && c.after ? diffNode(c.before, c.after)
              : el('p', { class: 'sentence__diff', text: (c.after ? '新增：' + c.after : '删除：' + c.before) });
            return el('li', {}, [body, c.why ? el('p', { class: 'sentence__explain', text: c.why }) : null]);
          }))
        ]));
      }
      if (r.band_rationale) panel.appendChild(el('div', { class: 'block' }, [el('h3', { text: 'AI 对目标分数段的说明（自述，未经评分验证）' }), el('p', { text: r.band_rationale })]));
    }

    function render() {
      renderSource();
      ['evaluate', 'refine', 'rewrite'].forEach(renderPanel);
    }

    load();
  }

  var TAG_LABELS = {
    grammar: '语法', vocabulary: '词汇', collocation: '搭配', cohesion: '衔接',
    punctuation: '标点', spelling: '拼写', clarity: '清晰度', task: '切题'
  };

  // ---------------------------------------------------------------- history
  function initHistory() {
    var list = document.getElementById('historyList');
    var more = document.getElementById('loadMore');
    var cursor = null;

    function statusText(statuses) {
      var values = Object.keys(statuses).map(function (k) { return statuses[k]; });
      if (values.some(function (s) { return s === 'queued' || s === 'running'; })) return '生成中';
      if (values.some(function (s) { return s === 'failed'; })) return '部分失败';
      return '';
    }

    function item(entry) {
      var bandBox = entry.overall_band !== null && entry.overall_band !== undefined
        ? el('div', { class: 'history-item__band' }, [el('span', {}, [band(entry.overall_band), el('small', { text: '预估' })])])
        : entry.overall_state === 'not_assessable'
          ? el('div', { class: 'history-item__band is-pending', title: '有评分项缺少依据，总分不可评', text: '不可评' })
          : el('div', { class: 'history-item__band is-pending', text: statusText(entry.statuses) || '—' });
      var node = el('article', { class: 'card history-item' }, [
        bandBox,
        el('div', {}, [
          el('p', { class: 'history-item__title', text: entry.prompt_excerpt }),
          el('div', { class: 'history-item__meta' }, [
            el('span', { text: entry.task_label }),
            el('span', { text: entry.word_count + ' 词' }),
            el('span', { text: '目标 ' + band(entry.target_band) }),
            entry.has_image ? el('span', { text: '含题图' }) : null,
            statusText(entry.statuses) && entry.overall_band !== null ? el('span', { text: statusText(entry.statuses) }) : null,
            el('span', { text: formatTime(entry.created_at) })
          ])
        ]),
        el('div', { class: 'history-item__actions' }, [
          el('a', { class: 'btn btn--ghost btn--sm', href: entry.url, text: '查看' }),
          el('button', {
            type: 'button', class: 'btn btn--danger btn--sm', text: '删除',
            onclick: function () {
              if (!window.confirm('删除后原稿、题图和 AI 结果都无法恢复。确定删除吗？')) return;
              api('DELETE', 'api/submissions/' + encodeURIComponent(entry.public_id)).then(function (result) {
                if (!result.ok) { toast(result.message || '删除失败'); return; }
                node.parentNode.removeChild(node);
                toast('已删除');
                if (!list.children.length) empty();
              });
            }
          })
        ])
      ]);
      return node;
    }

    function empty() {
      list.appendChild(el('div', { class: 'card empty' }, [
        el('p', { class: 'muted', text: '还没有批改记录。' }),
        el('a', { class: 'btn btn--primary', href: url(''), text: '新建第一次批改' })
      ]));
    }

    function load() {
      more.disabled = true;
      api('GET', 'api/submissions' + (cursor ? '?before=' + cursor : '')).then(function (result) {
        more.disabled = false;
        if (!result.ok) { toast(result.message || '加载失败'); return; }
        if (!cursor && !result.items.length) empty();
        result.items.forEach(function (entry) { list.appendChild(item(entry)); cursor = entry.cursor; });
        more.hidden = !result.has_more;
      });
    }

    more.addEventListener('click', load);
    load();
  }

  initDraftHygiene();
  initLogout();
  var page = body.getAttribute('data-page');
  if (page === 'login') initLogin();
  else if (page === 'new') initNew();
  else if (page === 'submission') initSubmission();
  else if (page === 'history') initHistory();
})();
