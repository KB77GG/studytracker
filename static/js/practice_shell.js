(function practiceShellModule(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.PracticeShell = api;
}(typeof globalThis !== "undefined" ? globalThis : this, function buildPracticeShell() {
  "use strict";

  const CONTEXT_KEY = "practice:return-context:v2";
  const LIST_STATE_PREFIX = "practice:list-state:v2:";
  const LEGACY_CONTEXT_KEY = "practice:return-context:v1";
  const NAVIGATION_PARAMS = ["practice_return", "practice_exit", "practice_source", "practice_identity"];
  const PRACTICE_PAGE_PATH = /^(?:\/practice(?:\/|$)|\/listening(?:\/|$)|\/reading(?:\/|$)|\/exam(?:\/|$)|\/writing(?:\/|$)|\/tasks\/question-types(?:\/|$))/;

  function safeStorage(storage, method, key, value) {
    try {
      if (method === "get") return storage.getItem(key);
      if (method === "remove") storage.removeItem(key);
      else storage.setItem(key, value);
    } catch (_error) {
      return method === "get" ? null : false;
    }
    return method === "get" ? null : true;
  }

  function readJson(storage, key, fallback = null) {
    const raw = safeStorage(storage, "get", key);
    if (!raw) return fallback;
    try {
      return JSON.parse(raw);
    } catch (_error) {
      return fallback;
    }
  }

  function writeJson(storage, key, value) {
    return safeStorage(storage, "set", key, JSON.stringify(value));
  }

  function currentUrl(win) {
    const location = win.location || {};
    const path = `${location.pathname || "/"}${location.search || ""}${location.hash || ""}`;
    return new URL(location.href || path, location.origin || "http://localhost");
  }

  function safeLocalUrl(value, origin, fallback = "") {
    if (!value) return fallback;
    try {
      const url = new URL(String(value), origin);
      if (url.origin !== origin || url.username || url.password || url.pathname.startsWith("//") || url.pathname.includes("\\")) return fallback;
      return url.pathname + url.search + url.hash;
    } catch (_error) {
      return fallback;
    }
  }

  function cleanNavigationUrl(value, origin) {
    const url = new URL(value || "/", origin);
    NAVIGATION_PARAMS.forEach((key) => url.searchParams.delete(key));
    return url;
  }

  function cleanLocalPath(value, origin, fallback = "") {
    const safe = safeLocalUrl(value, origin, fallback);
    if (!safe) return fallback;
    const url = cleanNavigationUrl(safe, origin);
    return url.pathname + url.search + url.hash;
  }

  function sourceModeForPath(pathname) {
    if (/^\/student\/today(?:\/|$)/.test(pathname)) return "student_today";
    if (/^\/tasks\/question-types(?:\/|$)/.test(pathname)) return "question_type_teacher";
    if (/^\/tasks(?:\/|$)/.test(pathname)) return "staff_tasks";
    if (/^\/practice\/question-types(?:\/|$)/.test(pathname)) return "question_type_catalog";
    if (/^\/practice\/mock-exams(?:\/|$)/.test(pathname)) return "mock_exam_review";
    if (/^\/exam\/.+\/session\//.test(pathname)) return "mock_exam_process";
    if (pathname === "/practice") return "practice_library";
    if (/^\/listening\/tests/.test(pathname)) return "listening_tests";
    if (/^\/reading\/tests/.test(pathname)) return "reading_tests";
    if (/^\/listening\/jijing/.test(pathname)) return "listening_jijing";
    if (/^\/reading\/jijing/.test(pathname)) return "reading_jijing";
    if (/^\/writing(?:\/|$)/.test(pathname)) return "writing_library";
    if (/^\/(?:practices|listening)$/.test(pathname)) return "intensive_library";
    return PRACTICE_PAGE_PATH.test(pathname) ? "practice_library" : "external";
  }

  function returnLabel(mode) {
    const labels = {
      student_today: "返回今日计划",
      staff_tasks: "返回任务中心",
      question_type_teacher: "返回任务中心",
      question_type_catalog: "返回题型专项",
      mock_exam_process: "返回模考流程",
      mock_exam_review: "返回模考复盘",
      task_detail: "返回任务详情",
      practice_library: "返回练习中心",
      listening_tests: "返回剑雅听力",
      reading_tests: "返回剑雅阅读",
      listening_jijing: "返回听力机经",
      reading_jijing: "返回阅读机经",
      writing_library: "返回写作题库",
      intensive_library: "返回精听列表"
    };
    return labels[mode] || "返回练习中心";
  }

  function exitLabel(identityMode, exitPath, exitMode, fallbackLabel) {
    if (exitMode !== "external") return returnLabel(exitMode);
    if (identityMode === "classroom" && exitPath === "/login") return "退出课堂刷题";
    if (identityMode === "staff" && exitPath === "/") return "返回工作台";
    if ((identityMode === "guest" || identityMode === "verified_student") && exitPath === "/login") return "退出刷题";
    return fallbackLabel || "退出刷题";
  }

  function mergedOptions(win, options = {}) {
    const defaults = win.PRACTICE_NAVIGATION_DEFAULTS || {};
    return {
      identityMode: options.identityMode || defaults.identityMode || defaults.identity_mode || "guest",
      moduleRootUrl: options.moduleRootUrl || defaults.moduleRootUrl || defaults.module_root_url || "/practice",
      moduleExitUrl: options.moduleExitUrl || defaults.moduleExitUrl || defaults.module_exit_url || "/login",
      moduleExitLabel: options.moduleExitLabel || defaults.moduleExitLabel || defaults.module_exit_label || "退出刷题",
      ...options
    };
  }

  function isPracticeModulePath(pathname) {
    return PRACTICE_PAGE_PATH.test(pathname);
  }

  function collectFilters(doc) {
    const rows = {};
    doc.querySelectorAll("[data-practice-filter], input[type=search], select[data-filter]").forEach((control) => {
      const key = control.dataset.practiceFilter || control.name || control.id;
      if (key) rows[key] = control.value;
    });
    rows.__openTests = Array.from(doc.querySelectorAll("details[data-test-id][open]"))
      .map((details) => details.dataset.testId)
      .filter(Boolean);
    return rows;
  }

  function restoreFilters(doc, filters = {}) {
    doc.querySelectorAll("[data-practice-filter], input[type=search], select[data-filter]").forEach((control) => {
      const key = control.dataset.practiceFilter || control.name || control.id;
      if (key && Object.prototype.hasOwnProperty.call(filters, key)) control.value = filters[key];
    });
    const openTests = new Set(Array.isArray(filters.__openTests) ? filters.__openTests.map(String) : []);
    doc.querySelectorAll("details[data-test-id]").forEach((details) => {
      details.open = openTests.has(String(details.dataset.testId));
    });
  }

  function contextParts(value, origin, fallback = "/practice") {
    const safe = cleanLocalPath(value, origin, fallback);
    const url = new URL(safe, origin);
    return { path: url.pathname, search: url.search, hash: url.hash };
  }

  function storedContext(win) {
    return readJson(win.sessionStorage, CONTEXT_KEY, null)
      || readJson(win.sessionStorage, LEGACY_CONTEXT_KEY, null);
  }

  function captureListState(win, options = {}) {
    const doc = win.document;
    const settings = mergedOptions(win, options);
    const origin = win.location.origin;
    const current = cleanNavigationUrl(currentUrl(win), origin);
    const currentPath = current.pathname + current.search + current.hash;
    const targetPath = cleanLocalPath(options.targetPath || "", origin, "");
    const previous = storedContext(win);
    const previousTargetsCurrent = Boolean(
      previous
      && cleanLocalPath(previous.targetPath || "", origin, "") === currentPath
    );
    const previousSourceIsCurrent = Boolean(
      previous
      && cleanLocalPath(
        `${previous.sourcePath || ""}${previous.sourceSearchParams || ""}${previous.sourceHash || ""}`,
        origin,
        ""
      ) === currentPath
    );

    let moduleExit = contextParts(settings.moduleExitUrl, origin, "/login");
    let moduleExitLabel = settings.moduleExitLabel;
    if (!isPracticeModulePath(current.pathname) && targetPath && isPracticeModulePath(new URL(targetPath, origin).pathname)) {
      moduleExit = { path: current.pathname, search: current.search, hash: current.hash };
      moduleExitLabel = returnLabel(sourceModeForPath(current.pathname));
    } else if ((previousTargetsCurrent || previousSourceIsCurrent) && previous.moduleExitPath) {
      moduleExit = {
        path: previous.moduleExitPath,
        search: previous.moduleExitSearchParams || "",
        hash: previous.moduleExitHash || ""
      };
      moduleExitLabel = previous.moduleExitLabel || moduleExitLabel;
    }

    const context = {
      version: 2,
      sourcePath: current.pathname,
      sourceSearchParams: current.search,
      sourceHash: current.hash,
      studentId: options.studentId || safeStorage(win.localStorage, "get", "listening_student") || "",
      identityMode: settings.identityMode,
      activeTab: options.activeTab || decodeURIComponent(current.hash.replace(/^#/, "")),
      filters: options.filters || collectFilters(doc),
      page: Number(options.page || doc.documentElement.dataset.page || 1),
      scrollPosition: Math.max(0, Math.round(win.scrollY || 0)),
      sourceMode: options.sourceMode || sourceModeForPath(current.pathname),
      targetPath,
      moduleExitPath: moduleExit.path,
      moduleExitSearchParams: moduleExit.search,
      moduleExitHash: moduleExit.hash,
      moduleExitLabel,
      returning: false,
      capturedAt: Date.now()
    };
    writeJson(win.sessionStorage, CONTEXT_KEY, context);
    writeJson(win.sessionStorage, LIST_STATE_PREFIX + current.pathname + current.search, context);
    return context;
  }

  function linkTarget(link, win) {
    try {
      return new URL(link.href || link.dataset.href, currentUrl(win));
    } catch (_error) {
      return null;
    }
  }

  function isPracticeEntry(link, win) {
    if (!link || link.hasAttribute("download")) return false;
    if (link.dataset.practiceEntry !== undefined) return true;
    const url = linkTarget(link, win);
    return Boolean(url && url.origin === win.location.origin && isPracticeModulePath(url.pathname));
  }

  function contextUrl(context, origin) {
    const fallbackHash = context.activeTab ? `#${encodeURIComponent(context.activeTab)}` : "";
    const path = `${context.sourcePath || "/practice"}${context.sourceSearchParams || ""}${context.sourceHash || fallbackHash}`;
    return cleanLocalPath(path, origin, "/practice");
  }

  function moduleExitUrl(context, origin) {
    const path = `${context.moduleExitPath || "/login"}${context.moduleExitSearchParams || ""}${context.moduleExitHash || ""}`;
    return cleanLocalPath(path, origin, "/login");
  }

  function decorateTarget(target, context, win) {
    if (!target || target.origin !== win.location.origin) return target;
    NAVIGATION_PARAMS.forEach((key) => target.searchParams.delete(key));
    target.searchParams.set("practice_return", contextUrl(context, win.location.origin));
    target.searchParams.set("practice_exit", moduleExitUrl(context, win.location.origin));
    target.searchParams.set("practice_source", context.sourceMode || "practice_library");
    target.searchParams.set("practice_identity", context.identityMode || "guest");
    return target;
  }

  function installListContext(options = {}, win = window) {
    if (win.__practiceListContextInstalled) return;
    win.__practiceListContextInstalled = true;
    const settings = mergedOptions(win, options);
    const current = cleanNavigationUrl(currentUrl(win), win.location.origin);
    const restoreKey = LIST_STATE_PREFIX + current.pathname + current.search;
    const saved = readJson(win.sessionStorage, restoreKey, null);
    if (saved && saved.returning) {
      if (saved.activeTab && !win.location.hash) win.history.replaceState(win.history.state, "", `#${encodeURIComponent(saved.activeTab)}`);
      restoreFilters(win.document, saved.filters);
      win.requestAnimationFrame(() => win.requestAnimationFrame(() => {
        restoreFilters(win.document, saved.filters);
        win.scrollTo(0, Number(saved.scrollPosition || 0));
      }));
      saved.returning = false;
      writeJson(win.sessionStorage, restoreKey, saved);
      writeJson(win.sessionStorage, CONTEXT_KEY, saved);
    }

    win.document.addEventListener("click", (event) => {
      const link = event.target.closest("a[href], [data-href]");
      if (!isPracticeEntry(link, win) || event.defaultPrevented) return;
      const target = linkTarget(link, win);
      const cleanTarget = target ? cleanNavigationUrl(target, win.location.origin) : null;
      const context = captureListState(win, {
        ...settings,
        activeTab: settings.activeTab || decodeURIComponent(win.location.hash.replace(/^#/, "")),
        targetPath: cleanTarget ? cleanTarget.pathname + cleanTarget.search + cleanTarget.hash : ""
      });
      if (target && target.origin === win.location.origin) {
        const decorated = decorateTarget(target, context, win);
        if (link.href !== undefined) link.href = decorated.href;
        else link.dataset.href = decorated.href;
      }
    }, true);

    const hasPracticeEntries = Array.from(win.document.querySelectorAll("a[href], [data-href]"))
      .some((entry) => isPracticeEntry(entry, win));
    if (hasPracticeEntries) {
      let scrollTimer = 0;
      win.addEventListener("scroll", () => {
        win.clearTimeout(scrollTimer);
        scrollTimer = win.setTimeout(() => captureListState(win, settings), 120);
      }, { passive: true });
    }
  }

  function samePracticeFlow(targetPath, currentPath) {
    const patterns = [
      /^(\/practice\/question-types\/task\/\d+)/,
      /^(\/exam\/\d+\/session\/[^/]+)/,
      /^(\/listening\/test\/[^/?#]+)/,
      /^(\/reading\/test\/[^/?#]+)/
    ];
    return patterns.some((pattern) => {
      const target = String(targetPath || "").match(pattern);
      const current = String(currentPath || "").match(pattern);
      return target && current && target[1] === current[1];
    });
  }

  function resolveContext(win, fallbackUrl, fallbackMode, options = {}) {
    const settings = mergedOptions(win, options);
    const origin = win.location.origin;
    const browserUrl = currentUrl(win);
    const current = cleanNavigationUrl(browserUrl, origin);
    const currentPath = current.pathname + current.search + current.hash;
    const explicitReturn = safeLocalUrl(browserUrl.searchParams.get("practice_return"), origin, "");
    const explicitExit = safeLocalUrl(browserUrl.searchParams.get("practice_exit"), origin, "");
    if (explicitReturn) {
      const source = contextParts(explicitReturn, origin, fallbackUrl || settings.moduleRootUrl);
      const exit = contextParts(explicitExit || settings.moduleExitUrl, origin, settings.moduleExitUrl);
      const exitMode = sourceModeForPath(exit.path);
      const identityMode = browserUrl.searchParams.get("practice_identity") || settings.identityMode;
      return {
        version: 2,
        sourcePath: source.path,
        sourceSearchParams: source.search,
        sourceHash: source.hash,
        sourceMode: browserUrl.searchParams.get("practice_source") || fallbackMode || sourceModeForPath(source.path),
        studentId: safeStorage(win.localStorage, "get", "listening_student") || "",
        identityMode,
        activeTab: source.hash.replace(/^#/, ""),
        filters: {},
        page: 1,
        scrollPosition: 0,
        targetPath: currentPath,
        moduleExitPath: exit.path,
        moduleExitSearchParams: exit.search,
        moduleExitHash: exit.hash,
        moduleExitLabel: exitLabel(identityMode, exit.path, exitMode, settings.moduleExitLabel),
        returning: false,
        capturedAt: Date.now()
      };
    }

    const stored = storedContext(win);
    const storedTarget = stored ? cleanLocalPath(stored.targetPath || "", origin, "") : "";
    const isFresh = stored && (Date.now() - Number(stored.capturedAt || 0)) < 4 * 60 * 60 * 1000;
    if (isFresh && (!storedTarget || storedTarget === currentPath || samePracticeFlow(storedTarget, currentPath))) return stored;

    const fallback = contextParts(fallbackUrl || settings.moduleRootUrl, origin, settings.moduleRootUrl);
    const exit = contextParts(settings.moduleExitUrl, origin, "/login");
    return {
      version: 2,
      sourcePath: fallback.path,
      sourceSearchParams: fallback.search,
      sourceHash: fallback.hash,
      studentId: safeStorage(win.localStorage, "get", "listening_student") || "",
      identityMode: settings.identityMode,
      activeTab: fallback.hash.replace(/^#/, ""),
      filters: {},
      page: 1,
      scrollPosition: 0,
      sourceMode: fallbackMode || sourceModeForPath(fallback.path),
      targetPath: currentPath,
      moduleExitPath: exit.path,
      moduleExitSearchParams: exit.search,
      moduleExitHash: exit.hash,
      moduleExitLabel: settings.moduleExitLabel,
      returning: false,
      capturedAt: Date.now()
    };
  }

  function assign(win, target) {
    if (typeof win.location.assign === "function") win.location.assign(target);
    else win.location.href = target;
  }

  function navigate(targetUrl, options = {}, win = window) {
    const settings = mergedOptions(win, options);
    const target = new URL(targetUrl, currentUrl(win));
    const cleanTarget = cleanNavigationUrl(target, win.location.origin);
    const context = captureListState(win, {
      ...settings,
      targetPath: cleanTarget.pathname + cleanTarget.search + cleanTarget.hash
    });
    assign(win, decorateTarget(target, context, win).href);
    return context;
  }

  function installHub(options = {}, win = window) {
    const marker = win.document.querySelector("[data-practice-hub]");
    if (!marker || win.__practiceHubInstalled) return null;
    win.__practiceHubInstalled = true;
    const settings = mergedOptions(win, options);
    const isRoot = marker.dataset.practiceHub === "root" || win.location.pathname === new URL(settings.moduleRootUrl, win.location.origin).pathname;
    const context = resolveContext(win, settings.moduleRootUrl, "practice_library", settings);
    let bypassPopState = false;

    function go(target) {
      bypassPopState = true;
      assign(win, target);
    }

    win.document.querySelectorAll("[data-practice-module-back]").forEach((button) => {
      button.textContent = "← 返回练习中心";
      button.addEventListener("click", (event) => {
        event.preventDefault();
        go(cleanLocalPath(settings.moduleRootUrl, win.location.origin, "/practice"));
      });
    });
    win.document.querySelectorAll("[data-practice-module-exit]").forEach((button) => {
      button.textContent = context.moduleExitLabel || settings.moduleExitLabel;
      button.addEventListener("click", (event) => {
        event.preventDefault();
        go(moduleExitUrl(context, win.location.origin));
      });
    });

    win.history.replaceState({ ...(win.history.state || {}), practiceHubBase: true }, "", win.location.href);
    win.history.pushState({ practiceHubGuard: true }, "", win.location.href);
    win.addEventListener("popstate", () => {
      if (bypassPopState) return;
      go(isRoot ? moduleExitUrl(context, win.location.origin) : contextUrl(context, win.location.origin));
    });
    return { context };
  }

  function init(options = {}, win = window) {
    const doc = win.document;
    const settings = mergedOptions(win, options);
    const backButtons = Array.from(doc.querySelectorAll("[data-practice-back]"));
    const examExitButtons = Array.from(doc.querySelectorAll("[data-practice-exam-exit]"));
    const moduleExitButtons = Array.from(doc.querySelectorAll("[data-practice-module-exit]"));
    const saveStatus = doc.querySelector("[data-practice-save-status]");
    const retryButton = doc.querySelector("[data-practice-save-retry]");
    const dialog = doc.getElementById("practiceExitDialog");
    const context = resolveContext(win, options.fallbackUrl || settings.moduleRootUrl, options.fallbackMode, settings);
    let dirty = false;
    let saveTimer = 0;
    let saving = null;
    let bypassPopState = false;
    let pendingTarget = "back";

    doc.addEventListener("click", (event) => {
      const link = event.target.closest("a[data-practice-entry], [data-href][data-practice-entry]");
      if (!link || event.defaultPrevented) return;
      const target = linkTarget(link, win);
      if (!target || target.origin !== win.location.origin) return;
      const cleanTarget = cleanNavigationUrl(target, win.location.origin);
      const nextContext = captureListState(win, {
        ...settings,
        targetPath: cleanTarget.pathname + cleanTarget.search + cleanTarget.hash
      });
      const decorated = decorateTarget(target, nextContext, win);
      if (link.href !== undefined) link.href = decorated.href;
      else link.dataset.href = decorated.href;
    }, true);

    function setStatus(label, tone = "") {
      if (!saveStatus) return;
      saveStatus.textContent = label;
      saveStatus.dataset.tone = tone;
      saveStatus.setAttribute("aria-label", `自动保存状态：${label}`);
      if (retryButton) retryButton.hidden = tone !== "error";
    }

    async function flush(reason = "manual") {
      win.clearTimeout(saveTimer);
      if (!dirty && reason !== "force") return true;
      if (saving) return saving;
      setStatus("保存中", "saving");
      saving = Promise.resolve()
        .then(() => (typeof options.save === "function" ? options.save(reason) : true))
        .then((result) => {
          if (result === false) throw new Error("save_failed");
          dirty = false;
          setStatus("已保存", "saved");
          return true;
        })
        .catch(() => {
          setStatus("保存失败，点击重试", "error");
          return false;
        })
        .finally(() => { saving = null; });
      return saving;
    }

    function markDirty() {
      dirty = true;
      setStatus("保存中", "saving");
      win.clearTimeout(saveTimer);
      saveTimer = win.setTimeout(() => flush("debounce"), Number(options.debounceMs || 450));
    }

    function markSaved() {
      dirty = false;
      setStatus("已保存", "saved");
    }

    async function leave(targetKind = "back") {
      const saved = await flush("exit");
      if (!saved) return false;
      const returning = targetKind === "back";
      context.returning = returning;
      writeJson(win.sessionStorage, CONTEXT_KEY, context);
      if (returning) {
        writeJson(win.sessionStorage, LIST_STATE_PREFIX + context.sourcePath + (context.sourceSearchParams || ""), context);
      }
      bypassPopState = true;
      assign(win, targetKind === "module" ? moduleExitUrl(context, win.location.origin) : contextUrl(context, win.location.origin));
      return true;
    }

    function requestExit(targetKind = "back") {
      pendingTarget = targetKind;
      if (options.confirmExit && dialog && typeof dialog.showModal === "function") {
        dialog.showModal();
        return;
      }
      leave(targetKind);
    }

    backButtons.forEach((button) => {
      button.textContent = `← ${returnLabel(context.sourceMode)}`;
      button.addEventListener("click", (event) => {
        event.preventDefault();
        requestExit("back");
      });
    });
    examExitButtons.forEach((button) => button.addEventListener("click", (event) => {
      event.preventDefault();
      requestExit("back");
    }));
    moduleExitButtons.forEach((button) => {
      button.textContent = context.moduleExitLabel || settings.moduleExitLabel;
      button.addEventListener("click", (event) => {
        event.preventDefault();
        requestExit("module");
      });
    });
    if (retryButton) retryButton.addEventListener("click", () => flush("force"));
    if (dialog) {
      dialog.querySelector("[data-practice-exit-cancel]")?.addEventListener("click", () => dialog.close());
      dialog.querySelector("[data-practice-exit-confirm]")?.addEventListener("click", () => {
        dialog.close();
        leave(pendingTarget);
      });
    }

    win.history.replaceState({ ...(win.history.state || {}), practiceBase: true }, "", win.location.href);
    win.history.pushState({ practiceGuard: true }, "", win.location.href);
    win.addEventListener("popstate", () => {
      if (bypassPopState) return;
      requestExit("back");
    });
    win.addEventListener("pagehide", () => { flush("pagehide"); });
    doc.addEventListener("visibilitychange", () => {
      if (doc.visibilityState === "hidden") flush("visibilitychange");
    });

    setStatus(options.initialSaved === false ? "尚未保存" : "已保存", options.initialSaved === false ? "" : "saved");
    return { context, flush, leave, markDirty, markSaved, setStatus };
  }

  return {
    CONTEXT_KEY,
    LIST_STATE_PREFIX,
    captureListState,
    cleanLocalPath,
    contextUrl,
    init,
    installHub,
    installListContext,
    isPracticeModulePath,
    moduleExitUrl,
    navigate,
    resolveContext,
    returnLabel,
    safeLocalUrl,
    sourceModeForPath
  };
}));
