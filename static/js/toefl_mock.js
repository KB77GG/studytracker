(() => {
  "use strict";

  const config = window.TOEFL_MOCK;
  let definition = config.definition;
  const elements = {
    welcome: document.getElementById("welcomePanel"),
    intro: document.getElementById("phaseIntroPanel"),
    introKicker: document.getElementById("phaseIntroKicker"),
    introTitle: document.getElementById("phaseIntroTitle"),
    introDescription: document.getElementById("phaseIntroDescription"),
    introTimer: document.getElementById("phaseIntroTimer"),
    phaseMicCheck: document.getElementById("phaseMicCheck"),
    phaseMicCheckButton: document.getElementById("phaseMicCheckButton"),
    phaseMicCheckStatus: document.getElementById("phaseMicCheckStatus"),
    beginPhase: document.getElementById("beginPhaseButton"),
    panel: document.getElementById("questionPanel"),
    report: document.getElementById("reportPanel"),
    start: document.getElementById("startButton"),
    back: document.getElementById("backButton"),
    next: document.getElementById("nextButton"),
    footer: document.getElementById("mockFooter"),
    section: document.getElementById("sectionLabel"),
    phase: document.getElementById("phaseLabel"),
    groupType: document.getElementById("groupType"),
    groupTitle: document.getElementById("groupTitle"),
    groupCounter: document.getElementById("groupCounter"),
    stimulus: document.getElementById("stimulus"),
    questions: document.getElementById("questions"),
    timer: document.getElementById("timerDisplay"),
    save: document.getElementById("saveState"),
    route: document.getElementById("routeNotice"),
    review: document.getElementById("reviewButton"),
    reviewDialog: document.getElementById("reviewDialog"),
    reviewList: document.getElementById("reviewList"),
    closeReview: document.getElementById("closeReview"),
    sectionPicker: document.getElementById("sectionPicker"),
    selectionNotice: document.getElementById("selectionNotice"),
  };

  let groupById = new Map();
  let questionById = new Map();
  let moduleById = new Map();
  let assetById = new Map();
  let attempt = null;
  let state = { phaseIndex: 0, groupIndex: 0 };
  let responses = {};
  let remainingSeconds = null;
  let tickCount = 0;
  let advancing = false;
  let activeRecording = null;
  let activeListeningAudio = null;
  const responseSaveTimers = new Map();
  const pendingResponseValues = new Map();
  const responseSaveChains = new Map();
  const inFlightResponseSaves = new Set();
  const inFlightResponseValues = new Map();
  const audioStates = new Map();

  function rebuildDefinitionMaps() {
    groupById = new Map((definition.groups || []).map((item) => [item.id, item]));
    questionById = new Map((definition.questions || []).map((item) => [item.id, item]));
    moduleById = new Map((definition.modules || []).map((item) => [item.id, item]));
    assetById = new Map((definition.assets || []).map((item) => [item.id, item]));
  }

  function setSaveState(label, pending = false) {
    elements.save.textContent = label;
    elements.save.classList.toggle("is-pending", pending);
  }

  async function api(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(payload.message || payload.error || `HTTP ${response.status}`);
      error.code = payload.error;
      throw error;
    }
    return payload;
  }

  function currentPhase() {
    return definition.phases[state.phaseIndex];
  }

  function phaseGroups(phase) {
    if (!phase) return [];
    if (phase.group_ids) return phase.group_ids.map((id) => groupById.get(id)).filter(Boolean);
    if (phase.group_id) return [groupById.get(phase.group_id)].filter(Boolean);
    return definition.groups
      .filter((item) => item.module_id === phase.module_id)
      .sort((a, b) => (a.order || 0) - (b.order || 0));
  }

  function currentGroup() {
    return phaseGroups(currentPhase())[state.groupIndex];
  }

  function phaseDuration(phase) {
    if (!phase || phase.duration_seconds == null) return null;
    return Number(phase.duration_seconds);
  }

  function formatTime(seconds) {
    if (seconds == null) return "AUDIO";
    const safe = Math.max(0, seconds);
    return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
  }

  function selectedSections() {
    return [...elements.sectionPicker.querySelectorAll("input:checked")].map((input) => input.value);
  }

  function updatePreflight() {
    const sections = selectedSections();
    const invalidSelection = sections.length === 0;
    elements.start.disabled = invalidSelection;
    if (invalidSelection) {
      elements.selectionNotice.textContent = "至少选择一个科目。";
    } else {
      elements.selectionNotice.textContent = "说明页和设备检查不计时；进入每个阶段后再启动服务端倒计时。";
    }
  }

  function updateUrl() {
    if (!attempt) return;
    const url = new URL(window.location.href);
    url.searchParams.set("attemptId", attempt.id);
    if (config.preview) url.searchParams.set("preview", "1");
    history.replaceState({}, "", url);
  }

  function updateProgress() {
    const phase = currentPhase();
    if (!phase) return;
    document.querySelectorAll(".mock-progress span").forEach((node) => {
      const sectionIndex = definition.sections.indexOf(node.dataset.section);
      const currentIndex = definition.sections.indexOf(phase.section);
      node.classList.toggle("is-active", sectionIndex === currentIndex);
      node.classList.toggle("is-complete", sectionIndex < currentIndex);
    });
  }

  function isFirstSpeakingPhase() {
    return currentPhase()?.section === "speaking"
      && definition.phases.findIndex((phase) => phase.section === "speaking") === state.phaseIndex;
  }

  function phaseDirections(phase) {
    if (phase.section === "reading") {
      return "本 Module 内可以前后检查答案；进入下一个 Module 后不能返回。倒计时归零会立即封闭本 Module。";
    }
    if (phase.section === "listening") {
      return "题目必须按顺序完成，音频只播放一次，不能拖动、重播或返回上一题。倒计时归零会立即封闭本 Module。";
    }
    if (phase.section === "writing") {
      return "本任务使用独立倒计时；进入下一项写作任务后不能返回。系统会持续保存当前输入。";
    }
    return "题目播放结束后立即录音，无准备时间；录音到时自动停止、上传并进入下一题。";
  }

  function renderPhaseIntro() {
    const phase = currentPhase();
    if (!phase) return;
    elements.welcome.hidden = true;
    elements.panel.hidden = true;
    elements.report.hidden = true;
    elements.footer.hidden = true;
    elements.intro.hidden = false;
    elements.review.hidden = true;
    elements.section.textContent = phase.section;
    elements.phase.textContent = `${phase.label} · Directions`;
    elements.timer.textContent = "--:--";
    elements.introKicker.textContent = `${phase.section.toUpperCase()} · ${phase.module.toUpperCase()}`;
    elements.introTitle.textContent = phase.label;
    elements.introDescription.textContent = phaseDirections(phase);
    elements.introTimer.textContent = formatTime(phaseDuration(phase));
    const needsMic = isFirstSpeakingPhase();
    const micPassed = state.deviceCheck?.microphone === "passed";
    elements.phaseMicCheck.hidden = !needsMic;
    elements.phaseMicCheckStatus.textContent = micPassed ? "测试通过 · 麦克风可用" : "未测试";
    elements.phaseMicCheckStatus.className = `mock-check-status${micPassed ? " is-success" : ""}`;
    elements.beginPhase.disabled = needsMic && !micPassed;
    elements.beginPhase.textContent = `开始 ${phase.label}`;
    updateProgress();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function renderCurrentStep() {
    if (state.phaseRunning === false) renderPhaseIntro();
    else render();
  }

  async function beginPhase() {
    if (isFirstSpeakingPhase() && state.deviceCheck?.microphone !== "passed") return;
    elements.beginPhase.disabled = true;
    state.phaseRunning = true;
    remainingSeconds = phaseDuration(currentPhase());
    try {
      await persistState();
      elements.intro.hidden = true;
      render();
      setSaveState("本阶段计时已开始");
    } catch (error) {
      state.phaseRunning = false;
      elements.beginPhase.disabled = false;
      setSaveState(`无法开始本阶段：${error.message}`, true);
    }
  }

  function questionIsRecording(question) {
    return question && question.response_type === "recording";
  }

  function questionTiming(question) {
    const input = question.input_config || {};
    const preparation = Number(input.preparation_seconds);
    const response = Number(input.response_seconds);
    if (!Number.isFinite(preparation) || preparation < 0 || !Number.isFinite(response) || response <= 0) {
      return null;
    }
    return { preparation, response };
  }

  function audioStateKey(phase, group) {
    return group?.stimulus?.playback_scope === "group" ? group.id : phase.id;
  }

  function renderAudioGate(phase, group) {
    if (phase.section !== "listening" || !group || group.stimulus?.format !== "audio") return false;
    const asset = assetById.get(group.stimulus.asset_id);
    const stateKey = audioStateKey(phase, group);
    const groupScoped = stateKey === group.id;
    const audioState = audioStates.get(stateKey) || { ready: false, skipped: false, played: false };
    audioStates.set(stateKey, audioState);
    const card = document.createElement("div");
    card.className = "mock-audio-card";
    const title = document.createElement("strong");
    title.textContent = "Listening audio · once in test mode";
    card.appendChild(title);
    if (!asset || asset.delivery?.status !== "published" || !asset.delivery?.url) {
      card.classList.add("is-unavailable");
      const note = document.createElement("p");
      note.textContent = "当前音频仍是 local_source，尚未进入发布存储；没有使用错误音频，也不会静默标记为已播放。";
      card.appendChild(note);
      if (config.preview) {
        const skip = document.createElement("button");
        skip.type = "button";
        skip.className = "mock-secondary";
        skip.textContent = audioState.skipped ? "已明确跳过音频缺口" : "仅在 Staging 明确跳过音频缺口";
        skip.disabled = audioState.skipped;
        skip.addEventListener("click", async () => {
          audioState.skipped = true;
          audioState.ready = true;
          await persistState();
          render();
        });
        card.appendChild(skip);
      }
      elements.stimulus.appendChild(card);
      return true;
    }
    if ((!groupScoped && state.groupIndex !== 0) || audioState.ready) {
      const note = document.createElement("p");
      note.textContent = audioState.ready
        ? "音频已播放；测试模式禁止重播和拖动。"
        : "音频将在本 Module 的第一组加载。";
      card.appendChild(note);
      elements.stimulus.appendChild(card);
      return true;
    }
    const audio = document.createElement("audio");
    audio.controls = false;
    audio.preload = "metadata";
    audio.src = asset.delivery.url;
    audio.setAttribute("aria-label", "Listening audio");
    const playbackStatus = document.createElement("p");
    playbackStatus.className = "mock-audio-status";
    playbackStatus.textContent = "正在准备音频…";
    const playFallback = document.createElement("button");
    playFallback.type = "button";
    playFallback.className = "mock-secondary";
    playFallback.textContent = "继续并播放音频";
    playFallback.hidden = true;
    let lastTime = 0;
    let playbackBlocked = false;
    let startedHere = false;
    audio.addEventListener("play", () => {
      if (audioState.played && !startedHere && audio.currentTime < 0.5) {
        playbackBlocked = true;
        activeListeningAudio = null;
        audio.pause();
        playbackStatus.textContent = "本段音频已开始过 · 正式模式不允许刷新后重播";
        setSaveState("测试模式禁止重新播放听力音频", true);
        return;
      }
      activeListeningAudio = audio;
      startedHere = true;
      audioState.played = true;
      playbackStatus.textContent = "音频正在播放 · 不可暂停、拖动或倍速";
      playFallback.hidden = true;
      persistState().catch(() => setSaveState("音频播放状态同步失败", true));
      updateNextState();
    });
    audio.addEventListener("pause", () => {
      if (!playbackBlocked && activeListeningAudio === audio && audioState.played && !audioState.ready && !audio.ended) {
        audio.play().catch(() => setSaveState("听力音频播放中断，请检查设备", true));
      }
    });
    audio.addEventListener("ratechange", () => {
      if (audio.playbackRate !== 1) audio.playbackRate = 1;
    });
    audio.addEventListener("timeupdate", () => {
      if (audio.currentTime >= lastTime) lastTime = audio.currentTime;
    });
    audio.addEventListener("seeking", () => {
      if (audio.currentTime > lastTime + 0.4 || audio.currentTime < lastTime - 0.4) {
        audio.currentTime = lastTime;
      }
    });
    audio.addEventListener("ended", async () => {
      activeListeningAudio = null;
      audioState.ready = true;
      playbackStatus.textContent = "音频播放完毕 · 可以继续答题";
      await persistState();
      render();
    });
    audio.addEventListener("error", () => {
      playbackBlocked = true;
      activeListeningAudio = null;
      playbackStatus.textContent = "音频加载失败 · 请检查网络后重新进入本次模考";
      playFallback.hidden = true;
      setSaveState("听力音频加载失败", true);
    });
    const startPlayback = async () => {
      try {
        await audio.play();
      } catch (error) {
        if (audioState.played) return;
        playbackStatus.textContent = "浏览器等待确认；点击下方按钮后音频将连续播放一次。";
        playFallback.hidden = false;
      }
    };
    playFallback.addEventListener("click", startPlayback);
    card.append(audio, playbackStatus, playFallback);
    const note = document.createElement("p");
    note.textContent = "与正式考试一致：音频自动连续播放一次，播放结束后才能继续。";
    card.appendChild(note);
    elements.stimulus.appendChild(card);
    startPlayback();
    return true;
  }

  function renderStimulus(phase, group) {
    elements.stimulus.replaceChildren();
    if (renderAudioGate(phase, group)) return false;
    const stimulus = group.stimulus || {};
    const text = stimulus.display_text || stimulus.text || stimulus.prompt || "";
    if (stimulus.format !== "inline_completion") {
      if (text) elements.stimulus.textContent = text;
      return false;
    }
    const questionMap = new Map((group.question_ids || []).map((questionId) => {
      const question = questionById.get(questionId);
      return [String(question?.number || "").padStart(2, "0"), question];
    }));
    text.split(/(\{q\d+:[^}]*\})/g).forEach((part) => {
      const match = part.match(/^\{q(\d+):([^}]*)\}$/);
      if (!match) {
        elements.stimulus.appendChild(document.createTextNode(part));
        return;
      }
      const question = questionMap.get(match[1]);
      if (!question) {
        elements.stimulus.appendChild(document.createTextNode(part));
        return;
      }
      const inline = document.createElement("span");
      inline.className = "inline-completion";
      inline.appendChild(document.createTextNode(match[2]));
      const input = document.createElement("input");
      input.type = "text";
      input.disabled = !question.available;
      input.setAttribute("aria-label", `Question ${question.number}`);
      input.value = typeof responses[question.id] === "string" ? responses[question.id] : "";
      input.addEventListener("input", () => scheduleResponseSave(question.id, input.value));
      inline.appendChild(input);
      elements.stimulus.appendChild(inline);
    });
    return true;
  }

  function responseControl(question) {
    const wrapper = document.createElement("article");
    wrapper.className = `mock-question${question.available ? "" : " is-blocked"}`;
    const recordingQuestion = questionIsRecording(question);
    const label = document.createElement("label");
    const spokenPrompt = currentPhase()?.section === "listening"
      && currentGroup()?.task_type === "listen_response";
    label.textContent = recordingQuestion
      ? `${question.number}. 听完题目后，系统会立即开始录音。`
      : spokenPrompt
        ? `${question.number}. Choose the best response.`
        : `${question.number}. ${question.prompt || "Respond to the item."}`;
    wrapper.appendChild(label);
    if (question.context_sentence && !recordingQuestion) {
      const context = document.createElement("p");
      context.className = "mock-context";
      context.textContent = question.context_sentence;
      wrapper.appendChild(context);
    }
    if (!question.available) {
      const note = document.createElement("p");
      note.className = "mock-blocked-note";
      note.textContent = "该题来源证据不完整，Staging 中禁用，不进入客观题判分分母。";
      wrapper.appendChild(note);
      return wrapper;
    }
    const value = responses[question.id];
    if (question.response_type === "mc") {
      (question.options || []).forEach((option) => {
        const optionLabel = document.createElement("label");
        optionLabel.className = "mock-option";
        const input = document.createElement("input");
        input.type = "radio";
        input.name = question.id;
        input.value = option.key;
        input.checked = value === option.key;
        input.addEventListener("change", () => saveResponse(question.id, option.key));
        const text = document.createElement("span");
        text.textContent = `${option.key}. ${option.text}`;
        optionLabel.append(input, text);
        wrapper.appendChild(optionLabel);
      });
      return wrapper;
    }
    if (question.response_type === "order") {
      const selected = Array.isArray(value) ? [...value] : [];
      const output = document.createElement("div");
      output.className = "mock-order-output";
      const tokenBox = document.createElement("div");
      tokenBox.className = "mock-order-tokens";
      const renderOrder = () => {
        output.replaceChildren();
        selected.forEach((token, index) => {
          const chosen = document.createElement("button");
          chosen.type = "button";
          chosen.className = "mock-order-chip";
          chosen.textContent = token;
          chosen.title = "点击移除这个 token";
          chosen.addEventListener("click", () => {
            selected.splice(index, 1);
            renderOrder();
            saveResponse(question.id, selected);
          });
          output.appendChild(chosen);
        });
        if (!selected.length) output.textContent = "点击下方 token 组成句子；重复 token 可分别选择。";
        const used = selected.reduce((counts, token) => {
          counts.set(token, (counts.get(token) || 0) + 1);
          return counts;
        }, new Map());
        tokenBox.querySelectorAll("button").forEach((button) => {
          const count = used.get(button.dataset.token) || 0;
          button.disabled = count > 0;
          if (count > 0) used.set(button.dataset.token, count - 1);
        });
      };
      (question.input_config?.scramble_tokens || []).forEach((token) => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.token = token;
        button.textContent = token;
        button.addEventListener("click", () => {
          selected.push(token);
          renderOrder();
          saveResponse(question.id, selected);
        });
        tokenBox.appendChild(button);
      });
      wrapper.append(tokenBox, output);
      renderOrder();
      return wrapper;
    }
    if (recordingQuestion) {
      const timing = questionTiming(question);
      const timingNote = document.createElement("p");
      timingNote.className = `mock-timing-note${timing ? "" : " is-warning"}`;
      timingNote.textContent = timing
        ? `无单独准备时间 · 作答 ${timing.response}s · 到时自动停止并上传`
        : "逐题时长不可用，本题不能开始。";
      wrapper.appendChild(timingNote);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "mock-secondary mock-record-button";
      button.textContent = value?.recorded
        ? (attempt?.preview ? "重新完成本题" : "本题已完成")
        : "播放题目并开始录音";
      button.disabled = Boolean(value?.recorded && !attempt?.preview);
      button.addEventListener("click", () => recordResponse(question, button));
      wrapper.appendChild(button);
      return wrapper;
    }
    const input = document.createElement(question.response_type === "free_text" ? "textarea" : "input");
    if (input.tagName === "INPUT") input.type = "text";
    input.value = typeof value === "string" ? value : "";
    input.placeholder = question.input_config?.visible_prefix
      ? `可见前缀：${question.input_config.visible_prefix}`
      : "Type your response";
    input.addEventListener("input", () => scheduleResponseSave(question.id, input.value));
    wrapper.appendChild(input);
    return wrapper;
  }

  function render() {
    const phase = currentPhase();
    const groups = phaseGroups(phase);
    const group = groups[state.groupIndex];
    if (!phase || !group) return;
    elements.welcome.hidden = true;
    elements.intro.hidden = true;
    elements.report.hidden = true;
    elements.panel.hidden = false;
    elements.footer.hidden = false;
    elements.review.hidden = phase.section !== "reading";
    elements.section.textContent = phase.section;
    elements.phase.textContent = phase.label;
    elements.groupType.textContent = (group.task_type || "task").replaceAll("_", " ");
    elements.groupTitle.textContent = group.title || phase.label;
    elements.groupCounter.textContent = `Group ${state.groupIndex + 1} of ${groups.length}`;
    const hasInlineQuestions = renderStimulus(phase, group);
    elements.questions.replaceChildren();
    const waitingForListeningAudio = phase.section === "listening" && !audioReadyForCurrentGroup();
    if (waitingForListeningAudio) {
      const waiting = document.createElement("p");
      waiting.className = "mock-timing-note";
      waiting.textContent = "请先听完音频；题目将在音频结束后显示。";
      elements.questions.appendChild(waiting);
    } else if (!hasInlineQuestions) {
      (group.question_ids || []).forEach((questionId) => {
        const question = questionById.get(questionId);
        if (question) elements.questions.appendChild(responseControl(question));
      });
    }
    const module = moduleById.get(phase.module_id);
    elements.back.disabled = module?.navigation?.back_policy !== "within_module"
      || state.groupIndex === 0;
    elements.timer.textContent = formatTime(remainingSeconds);
    updateProgress();
    updateNextState();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function saveResponse(questionId, value) {
    responses[questionId] = value;
    setSaveState("保存中…", true);
    const previous = responseSaveChains.get(questionId) || Promise.resolve();
    const operation = previous.catch(() => undefined).then(() => api("/api/toefl/responses", {
      method: "POST",
      body: JSON.stringify({ attemptId: attempt.id, questionId, response: value }),
    }));
    let tracked;
    tracked = operation.finally(() => {
      inFlightResponseSaves.delete(tracked);
      inFlightResponseValues.delete(tracked);
      if (responseSaveChains.get(questionId) === tracked) responseSaveChains.delete(questionId);
    });
    responseSaveChains.set(questionId, tracked);
    inFlightResponseSaves.add(tracked);
    inFlightResponseValues.set(tracked, { questionId, value });
    try {
      await tracked;
      setSaveState("已保存");
    } catch (error) {
      if (!pendingResponseValues.has(questionId)) pendingResponseValues.set(questionId, value);
      setSaveState(`保存失败：${error.message}`, true);
      throw error;
    }
  }

  function scheduleResponseSave(questionId, value) {
    responses[questionId] = value;
    pendingResponseValues.set(questionId, value);
    clearTimeout(responseSaveTimers.get(questionId));
    const timer = setTimeout(() => {
      responseSaveTimers.delete(questionId);
      const pendingValue = pendingResponseValues.get(questionId);
      pendingResponseValues.delete(questionId);
      saveResponse(questionId, pendingValue).catch(() => undefined);
    }, 350);
    responseSaveTimers.set(questionId, timer);
  }

  async function flushPendingResponses() {
    const pending = [...pendingResponseValues.entries()];
    pendingResponseValues.clear();
    responseSaveTimers.forEach((timer) => clearTimeout(timer));
    responseSaveTimers.clear();
    const inFlight = [...inFlightResponseSaves].map((promise) => ({
      promise,
      ...(inFlightResponseValues.get(promise) || {}),
    }));
    const queueResult = await window.ToeflResponseQueue.flushResponseSaves({
      pendingEntries: pending,
      inFlightEntries: inFlight,
      save: saveResponse,
    });
    queueResult.retry.forEach((value, questionId) => {
      pendingResponseValues.set(questionId, value);
    });
    if (!queueResult.ok) {
      const failed = queueResult.results.find((result) => result.status === "rejected");
      throw failed.reason;
    }
  }

  function stopActiveRecording(manual = true) {
    if (!activeRecording) return;
    const record = activeRecording;
    if (record.phase === "prompting") {
      record.audio?.pause();
      record.stream.getTracks().forEach((track) => track.stop());
      activeRecording = null;
      record.button.disabled = false;
      record.button.textContent = "播放题目并开始录音";
      setSaveState(manual ? "本题已取消，可重新开始" : "本题录音未开始", true);
      record.resolve(false);
      return;
    }
    if (record.recorder && record.recorder.state === "recording") record.recorder.stop();
  }

  async function recordResponse(question, button) {
    if (activeRecording || (responses[question.id]?.recorded && !attempt?.preview)) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      button.textContent = "浏览器不支持录音，重试";
      setSaveState("录音失败：请使用最新版 Chrome 或 Safari", true);
      return;
    }
    const group = currentGroup();
    const stimulus = group?.stimulus || {};
    const asset = assetById.get(stimulus.asset_id);
    const cueStart = Number(stimulus.cue_start_seconds);
    const cueEnd = Number(stimulus.cue_end_seconds);
    const timing = questionTiming(question);
    if (
      stimulus.format !== "audio_cue"
      || !asset?.delivery?.url
      || asset.delivery.status !== "published"
      || !Number.isFinite(cueStart)
      || !Number.isFinite(cueEnd)
      || cueEnd <= cueStart
      || !timing
    ) {
      button.textContent = "题目音频不可用";
      button.disabled = true;
      setSaveState("本题音频或计时定义未通过门禁", true);
      return;
    }
    let stream;
    button.disabled = true;
    button.textContent = "正在连接麦克风…";
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      button.disabled = false;
      button.textContent = "权限失败，重试";
      setSaveState("录音失败：麦克风权限未开启，可重试", true);
      return;
    }
    const mimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find((type) => MediaRecorder.isTypeSupported(type)) || "";
    let recorder;
    try {
      recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    } catch (error) {
      stream.getTracks().forEach((track) => track.stop());
      button.disabled = false;
      button.textContent = "录音失败，重试";
      setSaveState("录音失败：无法创建录音器，可重试", true);
      return;
    }
    const chunks = [];
    const audio = new Audio();
    audio.preload = "auto";
    audio.src = asset.delivery.url;
    activeRecording = {
      questionId: question.id,
      recorder,
      stream,
      audio,
      button,
      chunks,
      phase: "prompting",
      startedAt: null,
      stopAt: null,
    };
    activeRecording.done = new Promise((resolve) => { activeRecording.resolve = resolve; });
    const record = activeRecording;
    let cueFinished = false;
    const failCue = (message) => {
      if (activeRecording !== record) return;
      audio.pause();
      stream.getTracks().forEach((track) => track.stop());
      activeRecording = null;
      button.disabled = false;
      button.textContent = "播放失败，重试";
      setSaveState(message, true);
      record.resolve(false);
    };
    const beginRecording = () => {
      if (cueFinished || activeRecording !== record) return;
      cueFinished = true;
      audio.pause();
      record.phase = "recording";
      record.startedAt = Date.now();
      record.stopAt = record.startedAt + timing.response * 1000;
      try {
        recorder.start(250);
      } catch (error) {
        failCue("录音失败：无法启动录音器，可重试");
        return;
      }
      button.textContent = `录音中 · ${timing.response}s 后自动停止`;
      elements.route.textContent = "正在录音，请持续作答；到时会自动上传并进入下一题。";
      updateNextState();
    };
    recorder.addEventListener("dataavailable", (event) => {
      if (event.data.size) chunks.push(event.data);
    });
    recorder.addEventListener("error", () => {
      stream.getTracks().forEach((track) => track.stop());
      activeRecording = null;
      button.disabled = false;
      button.textContent = "录音失败，重试";
      setSaveState("录音失败，可重试；没有提交损坏文件", true);
      record.resolve(false);
    });
    recorder.addEventListener("stop", async () => {
      const finished = activeRecording;
      activeRecording = null;
      stream.getTracks().forEach((track) => track.stop());
      if (!finished || !finished.startedAt || !chunks.length) {
        button.disabled = false;
        button.textContent = "录音失败，重试";
        setSaveState("录音失败：没有可验证的音频，可重试", true);
        record.resolve(false);
        return;
      }
      const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      const form = new FormData();
      form.append("attemptId", attempt.id);
      form.append("questionId", question.id);
      form.append("durationMs", String(Math.max(1, Date.now() - finished.startedAt)));
      form.append("audio", blob, "response.webm");
      button.textContent = "上传中…";
      let saved = false;
      try {
        const response = await fetch("/api/toefl/recordings", {
          method: "POST",
          credentials: "same-origin",
          body: form,
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
        responses[question.id] = { recorded: true, durationMs: payload.durationMs };
        saved = true;
        button.textContent = attempt?.preview ? "重新完成本题" : "本题已完成";
        setSaveState("录音已保存");
      } catch (error) {
        button.textContent = "上传失败，重试";
        setSaveState(`录音上传失败：${error.message}`, true);
      } finally {
        button.disabled = Boolean(saved && !attempt?.preview);
        updateNextState();
        record.resolve(saved);
        if (saved) {
          window.setTimeout(() => {
            advance().catch((error) => setSaveState(`自动推进失败：${error.message}`, true));
          }, 250);
        }
      }
    });
    audio.addEventListener("loadedmetadata", () => {
      if (activeRecording !== record) return;
      audio.currentTime = cueStart;
      button.textContent = "题目播放中 · 播放后自动录音";
      elements.route.textContent = "请仔细听；题目只播放一次，结束后立即录音。";
      audio.play().catch(() => failCue("浏览器阻止了题目音频播放，请点击重试"));
    }, { once: true });
    audio.addEventListener("timeupdate", () => {
      if (audio.currentTime >= cueEnd - 0.04) beginRecording();
    });
    audio.addEventListener("ended", beginRecording, { once: true });
    audio.addEventListener("error", () => failCue("题目音频加载失败，请检查网络后重试"), { once: true });
    audio.load();
    updateNextState();
  }

  async function persistState() {
    if (!attempt || attempt.status !== "in_progress") return;
    const audio = {};
    audioStates.forEach((value, key) => { audio[key] = value; });
    const statePayload = { ...state, audio, returnTo: attempt.state?.returnTo || config.returnTo };
    if (statePayload.deviceCheck?.microphone !== "passed") delete statePayload.deviceCheck;
    const payload = {
      state: statePayload,
      currentPhase: currentPhase()?.id,
      remainingSeconds,
    };
    const result = await api(`/api/toefl/attempts/${attempt.id}/state`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    attempt = result.attempt;
    remainingSeconds = attempt.remaining_seconds;
  }

  function audioReadyForCurrentGroup() {
    const phase = currentPhase();
    if (phase?.section !== "listening") return true;
    const group = currentGroup();
    if (group?.stimulus?.format !== "audio") return true;
    return Boolean(audioStates.get(audioStateKey(phase, group))?.ready);
  }

  function currentGroupRecordingsReady() {
    const group = currentGroup();
    if (!group || currentPhase()?.section !== "speaking") return true;
    return (group.question_ids || []).every((id) => {
      const question = questionById.get(id);
      return !question?.available || responses[id]?.recorded;
    });
  }

  function updateNextState() {
    if (!attempt || elements.panel.hidden) return;
    const phase = currentPhase();
    const groups = phaseGroups(phase);
    const lastGroup = state.groupIndex >= groups.length - 1;
    const canProceed = audioReadyForCurrentGroup() && currentGroupRecordingsReady();
    elements.next.disabled = !canProceed || advancing;
    elements.next.textContent = lastGroup && state.phaseIndex === definition.phases.length - 1 ? "Complete" : "Next";
    if (phase?.section === "listening" && !audioReadyForCurrentGroup()) {
      const asset = assetById.get(currentGroup()?.stimulus?.asset_id);
      const published = asset?.delivery?.status === "published" && asset?.delivery?.url;
      elements.route.textContent = published
        ? "请先完整听完当前音频；播放结束后题目会自动显示。"
        : "当前音频未进入发布存储；只可在 Staging 明确跳过缺口。";
    } else if (phase?.section === "speaking" && !currentGroupRecordingsReady()) {
      if (!activeRecording) {
        elements.route.textContent = "点击“播放题目并开始录音”；播放结束后会自动录音、上传并进入下一题。";
      }
    }
  }

  async function advance() {
    if (advancing) return;
    advancing = true;
    try {
      await flushPendingResponses();
      const phase = currentPhase();
      const groups = phaseGroups(phase);
      if (!audioReadyForCurrentGroup() || !currentGroupRecordingsReady()) return;
      if (state.groupIndex < groups.length - 1) {
        state.groupIndex += 1;
        await persistState();
        render();
        return;
      }
      if (phase.adaptive_checkpoint) {
        const route = await api(`/api/toefl/attempts/${attempt.id}/route-m2`, {
          method: "POST",
          body: JSON.stringify({ subject: phase.section }),
        });
        elements.route.textContent = `${phase.section} M2 route: ${route.route}（adaptive_available=false）`;
      }
      if (state.phaseIndex >= definition.phases.length - 1) {
        await finish();
        return;
      }
      state.phaseIndex += 1;
      state.groupIndex = 0;
      state.phaseRunning = false;
      const nextPhase = currentPhase();
      remainingSeconds = phaseDuration(nextPhase);
      await persistState();
      renderCurrentStep();
      setSaveState("等待开始下一阶段");
    } catch (error) {
      setSaveState(`无法继续：${error.message}`, true);
    } finally {
      advancing = false;
      updateNextState();
    }
  }

  async function expirePhase() {
    if (advancing) return;
    advancing = true;
    try {
      if (activeListeningAudio) {
        const audio = activeListeningAudio;
        activeListeningAudio = null;
        audio.pause();
      }
      if (activeRecording) {
        const recording = activeRecording;
        stopActiveRecording(false);
        await recording.done;
      }
      await flushPendingResponses();
      remainingSeconds = 0;
      await persistState();
      const phase = currentPhase();
      if (phase.adaptive_checkpoint) {
        await api(`/api/toefl/attempts/${attempt.id}/route-m2`, {
          method: "POST",
          body: JSON.stringify({ subject: phase.section }),
        });
      }
      if (state.phaseIndex >= definition.phases.length - 1) {
        await finish();
        return;
      }
      state.phaseIndex += 1;
      state.groupIndex = 0;
      state.phaseRunning = false;
      remainingSeconds = phaseDuration(currentPhase());
      await persistState();
      renderCurrentStep();
      setSaveState("上一阶段时间到，已自动封闭");
    } catch (error) {
      setSaveState(`到时提交失败：${error.message}`, true);
    } finally {
      advancing = false;
      updateNextState();
    }
  }

  async function goBack() {
    if (!attempt || advancing) return;
    try {
      await flushPendingResponses();
      const phase = currentPhase();
      const module = moduleById.get(phase.module_id);
      if (module?.navigation?.back_policy !== "within_module") return;
      if (state.groupIndex === 0) return;
      state.groupIndex -= 1;
      await persistState();
      render();
    } catch (error) {
      setSaveState(`无法返回：${error.message}`, true);
    }
  }

  function appendMetric(parent, value, label) {
    const metric = document.createElement("div");
    const strong = document.createElement("strong");
    strong.textContent = value;
    const span = document.createElement("span");
    span.textContent = label;
    metric.append(strong, span);
    parent.appendChild(metric);
  }

  async function finish(alreadyCompleted = false) {
    elements.next.disabled = true;
    if (activeRecording) {
      const recording = activeRecording;
      stopActiveRecording(false);
      const recorded = await recording.done;
      if (!recorded) throw new Error("录音未成功保存，无法完成 attempt");
    }
    await flushPendingResponses();
    if (!alreadyCompleted) {
      const completed = await api(`/api/toefl/attempts/${attempt.id}/complete`, { method: "POST", body: "{}" });
      attempt = completed.attempt;
    }
    const report = await api(`/api/toefl/attempts/${attempt.id}/report`);
    elements.intro.hidden = true;
    elements.panel.hidden = true;
    elements.report.hidden = false;
    elements.back.hidden = true;
    elements.next.hidden = true;
    elements.review.hidden = true;
    elements.timer.textContent = "--:--";
    elements.report.replaceChildren();
    const kicker = document.createElement("p");
    kicker.className = "mock-kicker";
    kicker.textContent = attempt.preview ? "PREVIEW ATTEMPT REPORT" : "TOEFL ATTEMPT REPORT";
    const heading = document.createElement("h2");
    heading.textContent = "流程已完整结束";
    const note = document.createElement("p");
    const manualStatus = {
      pending: "pending teacher review（待老师批改）",
      draft: "老师批改中",
      published: "老师已发布",
      not_required: "无需人工批改",
    }[report.manual.status] || report.manual.status;
    note.textContent = `这是本站练习报告，不是正式成绩单，也不是 ETS 官方成绩单；人工题状态：${manualStatus}。`;
    const metrics = document.createElement("div");
    metrics.className = "report-metrics";
    appendMetric(metrics, `${report.objective.correct}/${report.objective.auto_total}`, "本站练习客观题合计答对");
    appendMetric(metrics, report.objective.accuracy == null ? "—" : `${Math.round(report.objective.accuracy * 100)}%`, "本站练习客观题准确率");
    appendMetric(metrics, `${report.manual.submitted}/${report.manual.total}`, "主观题已提交");
    const bySubject = report.practice_breakdown?.by_subject || {};
    ["reading", "listening"].forEach((subject) => {
      const section = bySubject[subject];
      if (section) appendMetric(metrics, `${section.correct}/${section.eligible_total}`, `${subject === "reading" ? "Reading" : "Listening"} · 本站练习答对数`);
    });
    ["writing", "speaking"].forEach((subject) => {
      const section = bySubject[subject];
      if (section?.practice_raw != null) appendMetric(metrics, `${section.practice_raw}/${section.practice_max}`, `${subject === "writing" ? "Writing" : "Speaking"} · 练习原始累计分`);
    });
    const blocked = document.createElement("p");
    blocked.className = "mock-report-note";
    blocked.textContent = `${report.practice_breakdown?.notice || "本站统计不生成 ETS 官方 1–6 分数。"} blocked 题不进入分母或可判题数。`;
    const returnLine = document.createElement("p");
    const returnLink = document.createElement("a");
    returnLink.href = attempt.state?.returnTo || config.returnTo || "/toefl/mock";
    returnLink.textContent = "返回模考目录";
    returnLine.appendChild(returnLink);
    const reviewLine = document.createElement("p");
    const reviewLink = document.createElement("a");
    reviewLink.href = `/toefl/mock/attempts/${encodeURIComponent(attempt.id)}/review`;
    reviewLink.textContent = "进入错题复盘";
    reviewLine.appendChild(reviewLink);
    elements.report.append(kicker, heading, note, metrics, blocked, reviewLine, returnLine);
  }

  async function start() {
    const sections = selectedSections();
    if (!sections.length) {
      updatePreflight();
      return;
    }
    elements.start.disabled = true;
    try {
      if (sections.join(",") !== definition.sections.join(",")) {
        const loaded = await api(`/api/toefl/tests/${encodeURIComponent(definition.test.id)}/definition?sections=${encodeURIComponent(sections.join(","))}`);
        definition = loaded;
        rebuildDefinitionMaps();
      }
      const payload = await api("/api/toefl/attempts/start", {
        method: "POST",
        body: JSON.stringify({
          testId: definition.test.id,
          sections: definition.sections,
          preview: config.preview,
          returnTo: config.returnTo,
        }),
      });
      attempt = payload.attempt;
      state = { phaseIndex: 0, groupIndex: 0, ...(attempt.state || {}) };
      responses = {};
      remainingSeconds = attempt.remaining_seconds;
      updateUrl();
      elements.sectionPicker.closest(".mock-preflight-grid")?.setAttribute("hidden", "hidden");
      renderCurrentStep();
      setSaveState("已建立 attempt");
    } catch (error) {
      elements.start.disabled = false;
      elements.start.textContent = `无法开始：${error.message}`;
      updatePreflight();
    }
  }

  async function resume(attemptId) {
    const payload = await api(`/api/toefl/attempts/${encodeURIComponent(attemptId)}/resume`);
    attempt = payload.attempt;
    definition = payload.definition;
    rebuildDefinitionMaps();
    state = { phaseIndex: 0, groupIndex: 0, ...(attempt.state || {}) };
    responses = attempt.responses || {};
    remainingSeconds = attempt.remaining_seconds;
    Object.entries(attempt.state?.audio || {}).forEach(([key, value]) => audioStates.set(key, value));
    updateUrl();
    if (attempt.status === "completed") {
      await finish(true);
      return;
    }
    elements.welcome.hidden = true;
    renderCurrentStep();
    setSaveState("已恢复");
  }

  function showReview() {
    elements.reviewList.replaceChildren();
    const visibleQuestionIds = new Set(currentPhase()?.question_ids || []);
    definition.questions.filter((question) => visibleQuestionIds.has(question.id)).forEach((question) => {
      const row = document.createElement("div");
      row.className = "review-row";
      const label = document.createElement("span");
      label.textContent = `${question.subject} · Q${question.number}`;
      const value = document.createElement("strong");
      value.textContent = responses[question.id] == null || responses[question.id] === "" ? "未作答" : "已作答";
      row.append(label, value);
      elements.reviewList.appendChild(row);
    });
    elements.reviewDialog.showModal();
  }

  async function runMicCheck() {
    if (!isFirstSpeakingPhase()) return;
    elements.phaseMicCheckButton.disabled = true;
    elements.phaseMicCheckStatus.textContent = "请对麦克风说话，正在检测音量…";
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("browser_media_unavailable");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      let passed = true;
      if (window.AudioContext || window.webkitAudioContext) {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        const context = new AudioContextClass();
        const analyser = context.createAnalyser();
        const source = context.createMediaStreamSource(stream);
        const data = new Uint8Array(analyser.fftSize);
        source.connect(analyser);
        await new Promise((resolve) => setTimeout(resolve, 450));
        analyser.getByteTimeDomainData(data);
        const rms = Math.sqrt(data.reduce((total, value) => total + ((value - 128) / 128) ** 2, 0) / data.length);
        passed = rms > 0.004;
        source.disconnect();
        await context.close();
      }
      stream.getTracks().forEach((track) => track.stop());
      state.deviceCheck = passed ? { microphone: "passed" } : {};
      elements.phaseMicCheckStatus.textContent = passed ? "测试通过 · 麦克风可用" : "未检测到足够音量，请重试并说话";
      elements.phaseMicCheckStatus.className = `mock-check-status ${passed ? "is-success" : "is-warning"}`;
      elements.beginPhase.disabled = !passed;
    } catch (error) {
      state.deviceCheck = {};
      elements.phaseMicCheckStatus.textContent = "测试失败 · 请允许浏览器使用麦克风后重试";
      elements.phaseMicCheckStatus.className = "mock-check-status is-warning";
      elements.beginPhase.disabled = true;
    } finally {
      elements.phaseMicCheckButton.disabled = false;
    }
  }

  elements.sectionPicker.querySelectorAll("input").forEach((input) => input.addEventListener("change", updatePreflight));
  elements.phaseMicCheckButton.addEventListener("click", runMicCheck);
  elements.beginPhase.addEventListener("click", beginPhase);
  elements.start.addEventListener("click", start);
  elements.next.addEventListener("click", advance);
  elements.back.addEventListener("click", goBack);
  elements.review.addEventListener("click", showReview);
  elements.closeReview.addEventListener("click", () => elements.reviewDialog.close());

  setInterval(() => {
    if (!attempt || elements.panel.hidden) return;
    const now = Date.now();
    if (activeRecording) {
      if (activeRecording.phase === "recording" && activeRecording.stopAt) {
        const seconds = Math.max(0, Math.ceil((activeRecording.stopAt - now) / 1000));
        activeRecording.button.textContent = `录音中 · ${seconds}s 后自动停止`;
        if (now >= activeRecording.stopAt) stopActiveRecording(false);
      }
    }
    if (remainingSeconds != null && state.phaseRunning !== false) {
      remainingSeconds = Math.max(0, remainingSeconds - 1);
      elements.timer.textContent = formatTime(remainingSeconds);
      tickCount += 1;
      if (remainingSeconds === 0 && !advancing) {
        expirePhase().catch((error) => setSaveState(`到时提交失败：${error.message}`, true));
      } else if (tickCount % 15 === 0) {
        persistState().catch(() => setSaveState("状态同步失败，正在保留本地显示", true));
      }
    }
  }, 1000);

  rebuildDefinitionMaps();
  updatePreflight();
  const attemptId = new URL(window.location.href).searchParams.get("attemptId");
  if (attemptId) {
    resume(attemptId).catch((error) => {
      elements.start.disabled = false;
      elements.start.textContent = `恢复失败，请重新开始（${error.message}）`;
    });
  }
})();
