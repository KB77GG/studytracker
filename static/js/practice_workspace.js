(function () {
  "use strict";

  var root = document.querySelector("[data-practice-workspace]");
  if (!root) return;

  var sidebar = root.querySelector("#practice-catalog");
  var openCatalogButton = root.querySelector("[data-open-catalog]");
  var closeCatalogButton = root.querySelector("[data-close-catalog]");
  var scrim = root.querySelector("[data-catalog-scrim]");
  var bookButtons = Array.from(root.querySelectorAll("[data-book-target]"));
  var bookPanels = Array.from(root.querySelectorAll("[data-book-panel]"));

  function setCatalogOpen(open) {
    if (!sidebar || !openCatalogButton || !scrim) return;
    sidebar.classList.toggle("is-open", open);
    openCatalogButton.setAttribute("aria-expanded", String(open));
    scrim.hidden = !open;
    document.body.style.overflow = open && window.matchMedia("(max-width: 860px)").matches ? "hidden" : "";
    if (open && closeCatalogButton) closeCatalogButton.focus();
  }

  function setGroupExpanded(group, expanded) {
    var toggle = group.querySelector("[data-source-toggle]");
    var items = group.querySelector(".practice-workspace__source-items");
    if (!toggle || !items) return;
    toggle.setAttribute("aria-expanded", String(expanded));
    toggle.classList.toggle("is-active", expanded);
    items.hidden = !expanded;
  }

  function setOlderBooksExpanded(group, expanded) {
    var toggle = group.querySelector("[data-older-toggle]");
    if (!toggle) return;
    group.querySelectorAll("[data-older-book]").forEach(function (button) {
      button.hidden = !expanded;
    });
    toggle.setAttribute("aria-expanded", String(expanded));
    var label = toggle.querySelector("[data-older-label]");
    if (label) {
      var collapsedLabel = toggle.getAttribute("data-collapsed-label") || "剑15 – 剑4";
      var expandedLabel = toggle.getAttribute("data-expanded-label") || "收起剑15 – 剑4";
      label.textContent = expanded ? expandedLabel : collapsedLabel;
    }
  }

  function selectBook(button, updateHash) {
    if (!button) return;
    var targetKey = button.getAttribute("data-book-target");
    var targetPanel = document.getElementById("book-" + targetKey);
    if (!targetPanel) return;

    bookButtons.forEach(function (item) {
      var selected = item === button;
      item.classList.toggle("is-selected", selected);
      if (selected) item.setAttribute("aria-current", "page");
      else item.removeAttribute("aria-current");
    });
    bookPanels.forEach(function (panel) {
      panel.hidden = panel !== targetPanel;
    });

    var group = button.closest("[data-source-group]");
    if (group) {
      root.querySelectorAll("[data-source-group]").forEach(function (item) {
        setGroupExpanded(item, item === group);
      });
      if (button.hasAttribute("data-older-book")) setOlderBooksExpanded(group, true);
    }

    if (updateHash) history.replaceState(null, "", "#" + targetKey);
    setCatalogOpen(false);
  }

  root.querySelectorAll("[data-source-toggle]").forEach(function (toggle) {
    toggle.addEventListener("click", function () {
      var group = toggle.closest("[data-source-group]");
      if (!group) return;
      setGroupExpanded(group, toggle.getAttribute("aria-expanded") !== "true");
    });
  });

  root.querySelectorAll("[data-older-toggle]").forEach(function (toggle) {
    toggle.addEventListener("click", function () {
      var group = toggle.closest("[data-source-group]");
      if (!group) return;
      setOlderBooksExpanded(group, toggle.getAttribute("aria-expanded") !== "true");
    });
  });

  bookButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      selectBook(button, true);
    });
  });

  root.querySelectorAll(".practice-workspace__test-card").forEach(function (details) {
    details.addEventListener("toggle", function () {
      var label = details.querySelector("[data-closed-label]");
      if (!label) return;
      label.textContent = details.open ? "收起选项" : label.getAttribute("data-closed-label");
    });
  });

  if (openCatalogButton) openCatalogButton.addEventListener("click", function () { setCatalogOpen(true); });
  if (closeCatalogButton) closeCatalogButton.addEventListener("click", function () { setCatalogOpen(false); });
  if (scrim) scrim.addEventListener("click", function () { setCatalogOpen(false); });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && sidebar && sidebar.classList.contains("is-open")) setCatalogOpen(false);
  });
  window.addEventListener("resize", function () {
    if (!window.matchMedia("(max-width: 860px)").matches) setCatalogOpen(false);
  });
  window.addEventListener("hashchange", function () {
    var requestedKey = decodeURIComponent(window.location.hash.replace(/^#/, ""));
    var requestedButton = bookButtons.find(function (button) {
      return button.getAttribute("data-book-target") === requestedKey;
    });
    if (requestedButton) selectBook(requestedButton, false);
  });

  var requestedKey = decodeURIComponent(window.location.hash.replace(/^#/, ""));
  var requestedButton = bookButtons.find(function (button) {
    return button.getAttribute("data-book-target") === requestedKey;
  });
  selectBook(requestedButton || root.querySelector("[data-default-book]") || bookButtons[0], false);
}());
