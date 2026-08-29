(function practiceModesModule(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.PracticeModes = api;
}(typeof globalThis !== "undefined" ? globalThis : this, function buildPracticeModes() {
  "use strict";

  const MODES = Object.freeze({
    SIMULATION: "simulation",
    PRACTICE: "practice",
    INTENSIVE_LISTENING: "intensiveListening",
    REVIEW: "review"
  });

  const MODE_FLAG_NAMES = Object.freeze({
    simulationMode: MODES.SIMULATION,
    practiceMode: MODES.PRACTICE,
    intensiveListeningMode: MODES.INTENSIVE_LISTENING,
    reviewMode: MODES.REVIEW
  });

  const BASE = Object.freeze({
    canFlagQuestions: false,
    canPauseAudio: false,
    canSeekAudio: false,
    canReplayAudio: false,
    canChangePlaybackRate: false,
    canShowTranscript: false,
    canShowAnalysis: false,
    canShowCorrectness: false,
    canUseQuestionNotes: false,
    canUseMapZoom: false,
    canUseReadingStudy: false,
    canUseTrainingViews: false,
    canSubmitForScoring: false,
    canResetAnswers: false,
    canShowPracticeBack: false,
    canShowPracticeNavigation: false,
    showAnsweredSummary: false,
    showElapsedTimer: false,
    showPracticeScorePanel: false,
    showPracticeSyncStatus: false,
    showPersistentSubmit: false,
    requiresAudioPreflight: false,
    usesServerDeadline: false,
    confirmExit: false
  });

  const DEFINITIONS = Object.freeze({
    [MODES.SIMULATION]: Object.freeze({
      ...BASE,
      canFlagQuestions: true,
      confirmExit: true,
      requiresAudioPreflight: true,
      usesServerDeadline: true
    }),
    [MODES.PRACTICE]: Object.freeze({
      ...BASE,
      canFlagQuestions: true,
      canPauseAudio: true,
      canSeekAudio: true,
      canReplayAudio: true,
      canUseMapZoom: true,
      canUseReadingStudy: true,
      canSubmitForScoring: true,
      canResetAnswers: true,
      canShowPracticeBack: true,
      canShowPracticeNavigation: true,
      showAnsweredSummary: true,
      showElapsedTimer: true,
      showPracticeScorePanel: true,
      showPracticeSyncStatus: true,
      showPersistentSubmit: true
    }),
    [MODES.INTENSIVE_LISTENING]: Object.freeze({
      ...BASE,
      canPauseAudio: true,
      canSeekAudio: true,
      canReplayAudio: true,
      canChangePlaybackRate: true,
      canShowTranscript: true,
      canShowAnalysis: true,
      canShowCorrectness: true,
      canUseQuestionNotes: true,
      canShowPracticeBack: true,
      canShowPracticeNavigation: true,
      showPracticeSyncStatus: true
    }),
    [MODES.REVIEW]: Object.freeze({
      ...BASE,
      canPauseAudio: true,
      canSeekAudio: true,
      canReplayAudio: true,
      canShowTranscript: true,
      canShowAnalysis: true,
      canShowCorrectness: true,
      canUseQuestionNotes: true,
      canUseMapZoom: true,
      canUseReadingStudy: true,
      canShowPracticeBack: true,
      canShowPracticeNavigation: true,
      showAnsweredSummary: true,
      showPracticeScorePanel: true,
      showPracticeSyncStatus: true
    })
  });

  function normalizeMode(value) {
    const mode = String(value || "").trim();
    if (!Object.values(MODES).includes(mode)) throw new Error(`Unknown practice mode: ${mode || "empty"}`);
    return mode;
  }

  function resolve(input = MODES.PRACTICE) {
    if (typeof input === "string") return normalizeMode(input);
    const active = Object.entries(MODE_FLAG_NAMES)
      .filter(([flag]) => Boolean(input && input[flag]))
      .map(([, mode]) => mode);
    if (active.length !== 1) {
      throw new Error(`Exactly one practice mode must be active; received ${active.length}`);
    }
    return active[0];
  }

  function modeFlags(input) {
    const mode = resolve(input);
    return Object.freeze(Object.fromEntries(
      Object.entries(MODE_FLAG_NAMES).map(([flag, target]) => [flag, target === mode])
    ));
  }

  function capabilities(input) {
    const mode = resolve(input);
    return Object.freeze({ mode, ...modeFlags(mode), ...DEFINITIONS[mode] });
  }

  function apply(rootNode, input) {
    const caps = capabilities(input);
    const doc = rootNode && rootNode.nodeType === 9 ? rootNode : rootNode?.ownerDocument;
    const scope = rootNode || doc;
    if (!scope || typeof scope.querySelectorAll !== "function") return caps;
    if (doc?.documentElement) doc.documentElement.dataset.experienceMode = caps.mode;
    if (doc?.body) doc.body.dataset.experienceMode = caps.mode;
    scope.querySelectorAll("[data-capability]").forEach((node) => {
      const capability = node.dataset.capability;
      const available = Boolean(caps[capability]);
      node.hidden = !available;
      node.setAttribute("aria-hidden", String(!available));
      if ("disabled" in node && !available) node.disabled = true;
      if ("disabled" in node && available && node.dataset.capabilityDisabled !== "true") node.disabled = false;
    });
    return caps;
  }

  return {
    DEFINITIONS,
    MODES,
    apply,
    capabilities,
    modeFlags,
    resolve
  };
}));
