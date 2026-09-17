(function listeningClipPlayerModule(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.ListeningClipPlayer = api;
}(typeof globalThis !== "undefined" ? globalThis : this, function buildListeningClipPlayer() {
  "use strict";

  function finite(value) {
    return typeof value === "number" && Number.isFinite(value);
  }

  function validateWindow({ start, end, duration, expectedDuration = null }) {
    const numericStart = Number(start);
    const numericEnd = Number(end);
    const numericDuration = Number(duration);
    const numericExpected = expectedDuration === null || expectedDuration === undefined
      ? null
      : Number(expectedDuration);
    if (!finite(numericDuration) || numericDuration <= 0) {
      return { ok: false, reason: "metadata_unavailable" };
    }
    if (finite(numericExpected) && Math.abs(numericDuration - numericExpected) > 0.75) {
      return { ok: false, reason: "audio_version_mismatch" };
    }
    if (!finite(numericStart) || !finite(numericEnd) || numericStart < 0 || numericEnd <= numericStart) {
      return { ok: false, reason: "invalid_window" };
    }
    if (numericStart >= numericDuration || numericEnd > numericDuration + 0.25) {
      return { ok: false, reason: "window_out_of_range" };
    }
    return {
      ok: true,
      start: numericStart,
      end: Math.min(numericEnd, numericDuration)
    };
  }

  function create({ audio, selectSection, onStatus = () => {} }) {
    if (!audio || typeof audio.addEventListener !== "function") {
      throw new Error("audio_element_required");
    }
    let revision = 0;
    let boundary = null;

    function report(message, tone = "") {
      onStatus(message, tone);
    }

    function pause() {
      try { audio.pause(); } catch (_error) { /* no-op */ }
    }

    function play(token) {
      if (token !== revision) return;
      const promise = audio.play();
      if (promise && typeof promise.catch === "function") {
        promise.catch(() => {
          if (token === revision) report("音频播放失败，请重试完整 Section。", "error");
        });
      }
    }

    function playFullSection(sectionIndex, { fallback = false } = {}) {
      const token = ++revision;
      boundary = null;
      pause();
      selectSection(sectionIndex, true);
      const apply = () => {
        if (token !== revision) return;
        try { audio.currentTime = 0; } catch (_error) { /* metadata may still be settling */ }
        report(
          fallback ? "题目定位不可用，已回退播放完整 Section。" : "正在播放完整 Section。",
          fallback ? "warn" : ""
        );
        play(token);
      };
      if (audio.readyState >= 1) apply();
      else audio.addEventListener("loadedmetadata", apply, { once: true });
      return token;
    }

    function playWindow({ sectionIndex, start, end, expectedDuration = null, label = "定位片段" }) {
      const token = ++revision;
      boundary = null;
      pause();
      selectSection(sectionIndex, true);
      const apply = () => {
        if (token !== revision) return;
        const window = validateWindow({ start, end, duration: audio.duration, expectedDuration });
        if (!window.ok) {
          playFullSection(sectionIndex, { fallback: true });
          return;
        }
        try { audio.currentTime = window.start; } catch (_error) {
          playFullSection(sectionIndex, { fallback: true });
          return;
        }
        boundary = { token, end: window.end };
        report(`正在播放${label}。`, "ok");
        play(token);
      };
      if (audio.readyState >= 1) apply();
      else audio.addEventListener("loadedmetadata", apply, { once: true });
      return token;
    }

    function playFrom({ sectionIndex, start, expectedDuration = null, label = "定位位置" }) {
      const token = ++revision;
      boundary = null;
      pause();
      selectSection(sectionIndex, true);
      const apply = () => {
        if (token !== revision) return;
        const numericStart = Number(start);
        if (
          !finite(numericStart)
          || numericStart < 0
          || !finite(Number(audio.duration))
          || (
            expectedDuration !== null
            && expectedDuration !== undefined
            && finite(Number(expectedDuration))
            && Math.abs(Number(audio.duration) - Number(expectedDuration)) > 0.75
          )
          || numericStart >= Number(audio.duration)
        ) {
          playFullSection(sectionIndex, { fallback: true });
          return;
        }
        try { audio.currentTime = numericStart; } catch (_error) {
          playFullSection(sectionIndex, { fallback: true });
          return;
        }
        report(`正在播放${label}。`, "ok");
        play(token);
      };
      if (audio.readyState >= 1) apply();
      else audio.addEventListener("loadedmetadata", apply, { once: true });
      return token;
    }

    function cancel({ pauseAudio = true } = {}) {
      revision += 1;
      boundary = null;
      if (pauseAudio) pause();
    }

    audio.addEventListener("timeupdate", () => {
      if (!boundary || boundary.token !== revision) return;
      if (Number(audio.currentTime) < boundary.end) return;
      pause();
      boundary = null;
      report("定位片段播放完毕。", "ok");
    });
    audio.addEventListener("ended", () => {
      boundary = null;
      report("音频播放完毕。", "ok");
    });
    audio.addEventListener("error", () => {
      boundary = null;
      report("音频加载失败，请检查网络后重试。", "error");
    });

    return {
      cancel,
      playFullSection,
      playFrom,
      playWindow,
      state: () => ({ revision, boundary: boundary ? { ...boundary } : null })
    };
  }

  return { create, validateWindow };
}));
