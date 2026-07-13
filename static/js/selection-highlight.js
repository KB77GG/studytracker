(function() {
  'use strict';

  var STORE_PREFIX = 'exhl:v1:';
  var STORE_KEY = STORE_PREFIX + window.location.pathname;
  var MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000;
  var EXCLUDE_SELECTOR = [
    'input',
    'select',
    'textarea',
    'button',
    'audio',
    '.inline-answer',
    '.result-pill',
    '.answer-pill',
    '.analysis',
    '.sel-tx-popover',
    '.ex-hl-toolbar',
    '.note-box'
  ].join(',');

  var toolbar = null;
  var observerPaused = false;
  var observers = [];
  var refreshTimers = new WeakMap();
  var memoryStore = null;
  var selectionTimer = 0;

  // ---------- Storage ----------
  function emptyStore() {
    return { updatedAt: Date.now(), blocks: {} };
  }

  function loadStore() {
    if (memoryStore) return memoryStore;
    try {
      var raw = window.localStorage.getItem(STORE_KEY);
      var data = raw ? JSON.parse(raw) : null;
      if (data && typeof data === 'object' && data.blocks &&
          typeof data.blocks === 'object' && !Array.isArray(data.blocks)) {
        return data;
      }
    } catch (error) {
      // localStorage may be unavailable in private browsing or a restricted webview.
    }
    return emptyStore();
  }

  function saveStore(store) {
    store.updatedAt = Date.now();
    try {
      window.localStorage.setItem(STORE_KEY, JSON.stringify(store));
      memoryStore = null;
    } catch (error) {
      memoryStore = store;
    }
  }

  function pruneOldStores() {
    try {
      var doomed = [];
      for (var i = 0; i < window.localStorage.length; i++) {
        var key = window.localStorage.key(i);
        if (!key || key.indexOf(STORE_PREFIX) !== 0) continue;
        try {
          var data = JSON.parse(window.localStorage.getItem(key));
          if (!data || !data.updatedAt || Date.now() - data.updatedAt > MAX_AGE_MS) {
            doomed.push(key);
          }
        } catch (error) {
          doomed.push(key);
        }
      }
      doomed.forEach(function(key) {
        window.localStorage.removeItem(key);
      });
    } catch (error) {
      // Cleanup is best-effort only.
    }
  }

  function blockList(store, key) {
    return Array.isArray(store.blocks[key]) ? store.blocks[key] : [];
  }

  // ---------- Filtered text coordinates ----------
  function highlightRoots() {
    return Array.prototype.slice.call(document.querySelectorAll('[data-hl-root]'));
  }

  function textSegments(root) {
    var segments = [];
    var offset = 0;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function(node) {
        var parent = node.parentElement;
        if (!parent || (parent.closest && parent.closest(EXCLUDE_SELECTOR))) {
          return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var node;
    while ((node = walker.nextNode())) {
      var length = node.nodeValue.length;
      segments.push({ node: node, start: offset, end: offset + length });
      offset += length;
    }
    return segments;
  }

  function fingerprint(root) {
    var hash = 5381;
    var segments = textSegments(root);
    for (var i = 0; i < segments.length; i++) {
      var text = segments[i].node.nodeValue;
      for (var j = 0; j < text.length; j++) {
        hash = (((hash << 5) + hash) + text.charCodeAt(j)) >>> 0;
      }
    }
    return hash.toString(36);
  }

  function blockKey(root) {
    return root.getAttribute('data-hl-root') + ':' + fingerprint(root);
  }

  function rangeToSpan(root, range) {
    var segments = textSegments(root);
    var start = Infinity;
    var end = -Infinity;

    for (var i = 0; i < segments.length; i++) {
      var segment = segments[i];
      try {
        if (!range.intersectsNode(segment.node)) continue;
      } catch (error) {
        continue;
      }

      var length = segment.node.nodeValue.length;
      var localStart = 0;
      var localEnd = length;
      if (segment.node === range.startContainer) {
        localStart = Math.min(range.startOffset, length);
      }
      if (segment.node === range.endContainer) {
        localEnd = Math.min(range.endOffset, length);
      }
      if (localStart >= localEnd) continue;
      start = Math.min(start, segment.start + localStart);
      end = Math.max(end, segment.start + localEnd);
    }

    return end > start ? { s: start, e: end } : null;
  }

  // ---------- Paint and restore ----------
  function unwrapAll(root) {
    var marks = root.querySelectorAll('span.ex-hl');
    for (var i = 0; i < marks.length; i++) {
      var mark = marks[i];
      var parent = mark.parentNode;
      while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
      parent.removeChild(mark);
    }
    root.normalize();
  }

  function paintOne(root, highlight) {
    if (!highlight || !Number.isFinite(highlight.s) || !Number.isFinite(highlight.e) ||
        highlight.e <= highlight.s) {
      return;
    }
    var segments = textSegments(root);
    for (var i = 0; i < segments.length; i++) {
      var segment = segments[i];
      var start = Math.max(highlight.s, segment.start);
      var end = Math.min(highlight.e, segment.end);
      if (start >= end) continue;

      var node = segment.node;
      if (start > segment.start) node = node.splitText(start - segment.start);
      if (end < segment.end) node.splitText(end - start);

      var mark = document.createElement('span');
      mark.className = 'ex-hl';
      mark.setAttribute('data-hl-id', highlight.id);
      node.parentNode.insertBefore(mark, node);
      mark.appendChild(node);
    }
  }

  function withObserverPaused(callback) {
    observerPaused = true;
    try {
      callback();
    } finally {
      observers.forEach(function(observer) {
        observer.takeRecords();
      });
      observerPaused = false;
    }
  }

  function refreshRoot(root) {
    withObserverPaused(function() {
      unwrapAll(root);
      var store = loadStore();
      blockList(store, blockKey(root)).forEach(function(highlight) {
        paintOne(root, highlight);
      });
    });
  }

  function refreshAll() {
    highlightRoots().forEach(refreshRoot);
  }

  // ---------- Add and remove ----------
  function generateId() {
    return 'h' + Math.random().toString(36).slice(2, 8) + Date.now().toString(36).slice(-4);
  }

  function mergeInto(list, span) {
    var start = span.s;
    var end = span.e;
    var kept = list.filter(function(item) {
      var isApart = item.e < start || item.s > end;
      if (!isApart) {
        start = Math.min(start, item.s);
        end = Math.max(end, item.e);
      }
      return isApart;
    });
    kept.push({ id: generateId(), s: start, e: end });
    kept.sort(function(a, b) { return a.s - b.s; });
    return kept;
  }

  function applyHighlight(spans) {
    var store = loadStore();
    spans.forEach(function(item) {
      var key = blockKey(item.root);
      store.blocks[key] = mergeInto(blockList(store, key), item.span);
    });
    saveStore(store);
    spans.forEach(function(item) { refreshRoot(item.root); });
  }

  function removeOverlapping(spans) {
    var store = loadStore();
    spans.forEach(function(item) {
      var key = blockKey(item.root);
      store.blocks[key] = blockList(store, key).filter(function(highlight) {
        return highlight.e <= item.span.s || highlight.s >= item.span.e;
      });
    });
    saveStore(store);
    spans.forEach(function(item) { refreshRoot(item.root); });
  }

  function removeById(root, id) {
    var store = loadStore();
    var key = blockKey(root);
    store.blocks[key] = blockList(store, key).filter(function(highlight) {
      return highlight.id !== id;
    });
    saveStore(store);
    refreshRoot(root);
  }

  function clearPage() {
    var store = loadStore();
    store.blocks = {};
    saveStore(store);
    refreshAll();
  }

  // ---------- Styles and toolbar ----------
  function ensureStyles() {
    if (document.getElementById('exHlStyles')) return;
    var style = document.createElement('style');
    style.id = 'exHlStyles';
    style.textContent = [
      '.ex-hl { background: #ffe75e; border-radius: 2px; cursor: pointer; }',
      '.ex-hl:hover { background: #ffd83b; }',
      '.ex-hl-toolbar {',
      '  position: absolute; z-index: 100000; display: flex; gap: 6px;',
      '  padding: 6px; border: 1px solid rgba(15,23,42,.12); border-radius: 8px;',
      '  background: #fff; box-shadow: 0 14px 36px rgba(15,23,42,.18);',
      '  font: 13px/1 -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif;',
      '}',
      '.ex-hl-toolbar button {',
      '  min-height: 34px; padding: 0 12px; border: 1px solid #dedbd0; border-radius: 6px;',
      '  background: #fff; color: #1d1615; font: inherit; font-weight: 700; cursor: pointer;',
      '  white-space: nowrap;',
      '}',
      '.ex-hl-toolbar button:hover { border-color: #2F8E87; }',
      '.ex-hl-toolbar button.ex-hl-primary { background: #ffe75e; border-color: #e8c93a; }'
    ].join('\n');
    document.head.appendChild(style);
  }

  function hideToolbar() {
    if (!toolbar) return;
    toolbar.remove();
    toolbar = null;
  }

  function showToolbar(anchor, buttons) {
    ensureStyles();
    hideToolbar();
    toolbar = document.createElement('div');
    toolbar.className = 'ex-hl-toolbar';
    toolbar.setAttribute('role', 'toolbar');
    toolbar.setAttribute('aria-label', '划词高亮');
    toolbar.addEventListener('mousedown', function(event) {
      event.preventDefault();
      event.stopPropagation();
    });
    toolbar.addEventListener('touchstart', function(event) {
      event.stopPropagation();
    }, { passive: true });

    buttons.forEach(function(button) {
      var element = document.createElement('button');
      element.type = 'button';
      element.textContent = button.label;
      if (button.primary) element.className = 'ex-hl-primary';
      element.addEventListener('click', function(event) {
        event.preventDefault();
        event.stopPropagation();
        button.onClick();
        hideToolbar();
      });
      toolbar.appendChild(element);
    });

    document.body.appendChild(toolbar);
    var margin = 8;
    var scrollX = window.scrollX || window.pageXOffset;
    var scrollY = window.scrollY || window.pageYOffset;
    var viewportWidth = document.documentElement.clientWidth || window.innerWidth;
    var width = toolbar.offsetWidth;
    var height = toolbar.offsetHeight;
    var left = Math.min(
      Math.max(anchor.x - width / 2, margin),
      Math.max(margin, viewportWidth - width - margin)
    );
    var top = anchor.top - height - margin;
    if (top < scrollY + margin) top = anchor.bottom + margin;
    toolbar.style.left = (left + scrollX) + 'px';
    toolbar.style.top = top + 'px';
  }

  function collectSelectionSpans() {
    var selection = window.getSelection();
    if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
    var range = selection.getRangeAt(0);
    var spans = [];
    highlightRoots().forEach(function(root) {
      var span = rangeToSpan(root, range);
      if (span) spans.push({ root: root, span: span });
    });
    return spans.length ? spans : null;
  }

  function selectionOverlapsHighlight(spans) {
    var store = loadStore();
    return spans.some(function(item) {
      return blockList(store, blockKey(item.root)).some(function(highlight) {
        return highlight.s < item.span.e && highlight.e > item.span.s;
      });
    });
  }

  function toolbarForSelection(anchor) {
    var spans = collectSelectionSpans();
    if (!spans) {
      hideToolbar();
      return false;
    }
    var buttons = [{
      label: '🖍 高亮',
      primary: true,
      onClick: function() {
        applyHighlight(spans);
        var selection = window.getSelection();
        if (selection) selection.removeAllRanges();
      }
    }];
    if (selectionOverlapsHighlight(spans)) {
      buttons.push({
        label: '取消高亮',
        onClick: function() { removeOverlapping(spans); }
      });
    }
    showToolbar(anchor, buttons);
    return true;
  }

  // ---------- Events ----------
  function scheduleSelectionToolbar(delay) {
    window.clearTimeout(selectionTimer);
    selectionTimer = window.setTimeout(function() {
      var selection = window.getSelection();
      if (!selection || selection.isCollapsed || selection.rangeCount === 0) return;
      var rect = selection.getRangeAt(0).getBoundingClientRect();
      if (!rect || (!rect.width && !rect.height)) return;
      var scrollY = window.scrollY || window.pageYOffset;
      toolbarForSelection({
        x: rect.left + rect.width / 2,
        top: rect.top + scrollY,
        bottom: rect.bottom + scrollY
      });
    }, delay);
  }

  document.addEventListener('mouseup', function(event) {
    if (toolbar && toolbar.contains(event.target)) return;
    scheduleSelectionToolbar(80);
  });

  document.addEventListener('touchend', function() {
    scheduleSelectionToolbar(200);
  }, { passive: true });

  document.addEventListener('contextmenu', function(event) {
    var selection = window.getSelection();
    if (!selection || selection.isCollapsed) return;
    var spans = collectSelectionSpans();
    if (!spans) return;
    event.preventDefault();
    var scrollY = window.scrollY || window.pageYOffset;
    toolbarForSelection({
      x: event.clientX,
      top: event.clientY + scrollY,
      bottom: event.clientY + scrollY
    });
  });

  document.addEventListener('click', function(event) {
    var mark = event.target && event.target.closest ? event.target.closest('.ex-hl') : null;
    if (!mark) return;
    var selection = window.getSelection();
    if (selection && !selection.isCollapsed) return;

    event.preventDefault();
    event.stopPropagation();
    var root = mark.closest('[data-hl-root]');
    var id = mark.getAttribute('data-hl-id');
    var rect = mark.getBoundingClientRect();
    var scrollY = window.scrollY || window.pageYOffset;
    showToolbar({
      x: rect.left + rect.width / 2,
      top: rect.top + scrollY,
      bottom: rect.bottom + scrollY
    }, [
      {
        label: '取消高亮',
        primary: true,
        onClick: function() { removeById(root, id); }
      },
      { label: '清除本页全部', onClick: clearPage }
    ]);
  }, true);

  document.addEventListener('mousedown', function(event) {
    if (toolbar && !toolbar.contains(event.target)) hideToolbar();
  });

  document.addEventListener('touchstart', function(event) {
    if (toolbar && !toolbar.contains(event.target)) hideToolbar();
  }, { passive: true });

  document.addEventListener('keyup', function(event) {
    if (event.key === 'Escape') hideToolbar();
  });

  document.addEventListener('scroll', hideToolbar, true);

  // ---------- Restore after page redraws ----------
  function observeRoot(root) {
    var observer = new MutationObserver(function() {
      if (observerPaused) return;
      window.clearTimeout(refreshTimers.get(root));
      refreshTimers.set(root, window.setTimeout(function() {
        refreshRoot(root);
      }, 80));
    });
    observer.observe(root, { childList: true, subtree: true, characterData: true });
    observers.push(observer);
  }

  ensureStyles();
  pruneOldStores();
  highlightRoots().forEach(observeRoot);
  refreshAll();
})();
