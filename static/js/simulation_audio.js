(function simulationAudioModule(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.SimulationAudio = api;
}(typeof globalThis !== "undefined" ? globalThis : this, function buildSimulationAudio() {
  "use strict";

  function finiteDuration(value) {
    const duration = Number(value);
    return Number.isFinite(duration) && duration > 0 ? duration : 0;
  }

  function waitForMetadata(media, timeoutMs = 15000) {
    return new Promise((resolve, reject) => {
      let settled = false;
      const cleanup = () => {
        media.removeEventListener?.("loadedmetadata", onReady);
        media.removeEventListener?.("error", onError);
        clearTimeout(timer);
      };
      const finish = (callback, value) => {
        if (settled) return;
        settled = true;
        cleanup();
        callback(value);
      };
      const onReady = () => {
        const duration = finiteDuration(media.duration);
        if (!duration) finish(reject, new Error("invalid_audio_duration"));
        else finish(resolve, duration);
      };
      const onError = () => finish(reject, new Error("audio_metadata_failed"));
      const timer = setTimeout(() => finish(reject, new Error("audio_metadata_timeout")), timeoutMs);
      media.addEventListener?.("loadedmetadata", onReady);
      media.addEventListener?.("error", onError);
      if (media.readyState >= 1) onReady();
    });
  }

  async function preflightResources(resources, options = {}) {
    const createMedia = options.createMedia || (() => new Audio());
    const timeoutMs = Number(options.timeoutMs || 15000);
    const rows = [];
    for (const resource of resources) {
      const media = createMedia(resource);
      media.preload = "metadata";
      media.src = resource.url;
      const metadata = waitForMetadata(media, timeoutMs);
      media.load?.();
      const duration = await metadata;
      rows.push({ ...resource, duration });
      media.removeAttribute?.("src");
      media.load?.();
    }
    return rows;
  }

  function timelinePosition(durations, startedAtMs, nowMs = Date.now()) {
    let remaining = Math.max(0, (Number(nowMs) - Number(startedAtMs)) / 1000);
    for (let index = 0; index < durations.length; index += 1) {
      const duration = finiteDuration(durations[index]);
      if (remaining < duration) {
        return { complete: false, sectionIndex: index, offsetSeconds: remaining };
      }
      remaining -= duration;
    }
    return {
      complete: true,
      sectionIndex: Math.max(0, durations.length - 1),
      offsetSeconds: finiteDuration(durations.at(-1))
    };
  }

  function createLockedPlaylist(options) {
    const audio = options.audio;
    const resources = options.resources || [];
    if (!audio) throw new Error("audio_element_required");
    if (!resources.length) throw new Error("audio_resources_required");

    let sectionIndex = -1;
    let lastAllowedTime = 0;
    let transition = false;
    let started = false;
    let complete = false;
    let destroyed = false;

    const emitState = (state, detail = {}) => options.onState?.(state, {
      sectionIndex,
      mediaElementMounts: 1,
      ...detail
    });

    async function loadSection(index, offsetSeconds = 0) {
      if (destroyed || index < 0 || index >= resources.length) return false;
      transition = true;
      sectionIndex = index;
      audio.playbackRate = 1;
      audio.src = resources[index].url;
      audio.load?.();
      try {
        await waitForMetadata(audio, Number(options.timeoutMs || 15000));
        const duration = finiteDuration(audio.duration);
        lastAllowedTime = Math.min(Math.max(0, Number(offsetSeconds || 0)), Math.max(0, duration - .05));
        audio.currentTime = lastAllowedTime;
        options.onSectionChange?.(index, resources[index]);
        transition = false;
        started = true;
        await audio.play();
        emitState("playing", { duration, resumedAt: lastAllowedTime });
        return true;
      } catch (error) {
        transition = false;
        emitState("error", { error });
        options.onError?.(error);
        return false;
      }
    }

    function onTimeUpdate() {
      if (!transition && started) lastAllowedTime = Number(audio.currentTime || 0);
    }

    function onSeeking() {
      if (transition || !started) return;
      if (Math.abs(Number(audio.currentTime || 0) - lastAllowedTime) > .35) {
        transition = true;
        audio.currentTime = lastAllowedTime;
        transition = false;
      }
    }

    function onRateChange() {
      if (audio.playbackRate !== 1) audio.playbackRate = 1;
    }

    function onPause() {
      if (!started || transition || complete || destroyed || audio.ended) return;
      Promise.resolve(audio.play()).catch((error) => options.onError?.(error));
    }

    function onEnded() {
      if (!started || transition || destroyed) return;
      if (sectionIndex + 1 < resources.length) {
        loadSection(sectionIndex + 1, 0);
        return;
      }
      complete = true;
      emitState("complete");
      options.onComplete?.();
    }

    audio.addEventListener?.("timeupdate", onTimeUpdate);
    audio.addEventListener?.("seeking", onSeeking);
    audio.addEventListener?.("ratechange", onRateChange);
    audio.addEventListener?.("pause", onPause);
    audio.addEventListener?.("ended", onEnded);

    return {
      destroy() {
        destroyed = true;
        audio.removeEventListener?.("timeupdate", onTimeUpdate);
        audio.removeEventListener?.("seeking", onSeeking);
        audio.removeEventListener?.("ratechange", onRateChange);
        audio.removeEventListener?.("pause", onPause);
        audio.removeEventListener?.("ended", onEnded);
      },
      loadSection,
      setVolume(value) {
        audio.volume = Math.max(0, Math.min(1, Number(value)));
      },
      snapshot() {
        return { complete, lastAllowedTime, mediaElementMounts: 1, sectionIndex, started, transition };
      }
    };
  }

  return {
    createLockedPlaylist,
    finiteDuration,
    preflightResources,
    timelinePosition,
    waitForMetadata
  };
}));
