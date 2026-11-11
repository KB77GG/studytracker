(function () {
  'use strict';

  var frames = Array.prototype.slice.call(document.querySelectorAll('iframe[data-review-paper]'));
  var wrongOnly = document.getElementById('wrongOnly');

  function sendFilter(frame) {
    if (!frame.contentWindow) return;
    frame.contentWindow.postMessage({
      type: 'mock-review-filter',
      wrongOnly: Boolean(wrongOnly && wrongOnly.checked)
    }, window.location.origin);
  }

  function showStatus(frame, message) {
    var status = frame.parentElement.querySelector('[data-review-paper-status]');
    if (!status) return;
    status.hidden = !message;
    if (message) status.textContent = message;
  }

  window.addEventListener('message', function (event) {
    if (event.origin !== window.location.origin || !event.data || typeof event.data !== 'object') return;
    var frame = frames.find(function (item) { return item.contentWindow === event.source; });
    if (!frame) return;
    if (event.data.type === 'mock-review-ready') {
      showStatus(frame, '');
      sendFilter(frame);
    } else if (event.data.type === 'mock-review-height') {
      var height = event.data.height;
      if (typeof height !== 'number' || !Number.isFinite(height) || height <= 0 || height > 100000) return;
      frame.style.height = Math.max(200, Math.ceil(height)) + 'px';
    }
  });

  frames.forEach(function (frame) {
    frame.addEventListener('load', function () {
      try {
        if (!frame.contentDocument || !frame.contentDocument.querySelector('[data-review-paper-embed="true"]')) {
          frame.hidden = true;
          showStatus(frame, '复盘内容暂时加载失败，请刷新页面重试。');
          return;
        }
        frame.hidden = false;
        showStatus(frame, '');
        sendFilter(frame);
      } catch (_error) {
        showStatus(frame, '复盘内容暂时加载失败，请刷新页面重试。');
      }
    });
    frame.addEventListener('error', function () {
      frame.hidden = true;
      showStatus(frame, '复盘内容暂时加载失败，请刷新页面重试。');
    });
    // A cached child may finish before this deferred parent script runs.
    try {
      if (frame.contentDocument && frame.contentDocument.readyState === 'complete' &&
          frame.contentDocument.querySelector('[data-review-paper-embed="true"]')) {
        showStatus(frame, '');
        sendFilter(frame);
      }
    } catch (_error) { /* The load handler reports unavailable child pages. */ }
  });
  if (wrongOnly) wrongOnly.addEventListener('change', function () { frames.forEach(sendFilter); });
}());
