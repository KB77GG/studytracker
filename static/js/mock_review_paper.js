(function () {
  'use strict';
  if (!document.body || document.body.dataset.reviewPaperEmbed !== 'true' || window.parent === window) return;

  var main = document.querySelector('main.page');
  var navigation = document.querySelector('.practice-bottom-nav');
  var tabs = document.getElementById('sectionTabs') || document.getElementById('passageTabs');
  if (navigation && tabs) {
    navigation.classList.add('mock-review-navigation');
    tabs.insertAdjacentElement('afterend', navigation);
  }
  var empty = document.createElement('p');
  empty.className = 'mock-review-empty';
  empty.setAttribute('role', 'status');
  empty.textContent = '当前部分没有错题。';
  empty.hidden = true;
  if (main) main.appendChild(empty);

  var wrongOnly = false;
  var pending = false;
  var lastHeight = 0;

  function isCorrect(card) {
    var status = card.querySelector('.review-card__status');
    return Boolean(status && status.dataset.status === 'correct');
  }

  function setFiltered(element, hidden) {
    if (hidden) {
      if (element.getAttribute('data-review-hidden') !== 'true') element.setAttribute('data-review-hidden', 'true');
    } else if (element.hasAttribute('data-review-hidden')) element.removeAttribute('data-review-hidden');
  }

  function applyFilter() {
    var cards = Array.prototype.slice.call(document.querySelectorAll('.review-card[data-review-question]'));
    cards.forEach(function (card) { setFiltered(card, wrongOnly && isCorrect(card)); });
    // Shared forms and combined choices keep their source context whenever any
    // constituent question is wrong; never remove an individual inline blank.
    document.querySelectorAll('.question, .question-row, .matching-row, .practice-form__field, .group').forEach(function (row) {
      var nested = Array.prototype.slice.call(row.querySelectorAll('.review-card[data-review-question]'));
      setFiltered(row, wrongOnly && nested.length > 0 && nested.every(isCorrect));
    });
    var activeCards = cards.filter(function (card) {
      var panel = card.closest('.panel');
      return !panel || panel.classList.contains('active');
    });
    empty.hidden = !(wrongOnly && activeCards.length > 0 && activeCards.every(isCorrect));
  }

  function reportSize() {
    // The body is content-sized by mock_review_paper.css. scrollHeight of the
    // document includes the iframe viewport and would prevent shrinking.
    var height = Math.ceil(document.body.getBoundingClientRect().height);
    if (!Number.isFinite(height) || height <= 0 || height === lastHeight) return;
    lastHeight = height;
    window.parent.postMessage({ type: 'mock-review-height', height: height }, window.location.origin);
  }

  function schedule() {
    if (pending) return;
    pending = true;
    window.requestAnimationFrame(function () {
      pending = false;
      applyFilter();
      reportSize();
    });
  }

  window.addEventListener('message', function (event) {
    if (event.origin !== window.location.origin || event.source !== window.parent) return;
    if (!event.data || event.data.type !== 'mock-review-filter' || typeof event.data.wrongOnly !== 'boolean') return;
    wrongOnly = event.data.wrongOnly;
    // Reply even when the size is unchanged: the parent may have subscribed
    // after a cached iframe sent its initial ready/height handshake.
    lastHeight = 0;
    schedule();
  });
  new MutationObserver(schedule).observe(document.body, {
    subtree: true, childList: true, attributes: true, attributeFilter: ['class']
  });
  if (window.ResizeObserver) new ResizeObserver(schedule).observe(document.body);
  window.addEventListener('resize', schedule);
  document.addEventListener('load', schedule, true);
  window.parent.postMessage({ type: 'mock-review-ready' }, window.location.origin);
  schedule();
}());
