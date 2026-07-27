(() => {
  "use strict";

  const config = window.TOEFL_MOCK;
  const definition = config.definition;
  const elements = {
    welcome: document.getElementById("welcomePanel"),
    panel: document.getElementById("questionPanel"),
    report: document.getElementById("reportPanel"),
    start: document.getElementById("startButton"),
    back: document.getElementById("backButton"),
    next: document.getElementById("nextButton"),
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
  };

  const groupById = new Map(definition.groups.map((item) => [item.id, item]));
  const questionById = new Map(definition.questions.map((item) => [item.id, item]));
  const moduleById = new Map(definition.modules.map((item) => [item.id, item]));
  let attempt = null;
  let state = { phaseIndex: 0, groupIndex: 0 };
  let responses = {};
  let remainingSeconds = null;
  let tickCount = 0;
  let advancing = false;
  const responseSaveTimers = new Map();
  const pendingResponseValues = new Map();

  function phaseGroups(phase) {
    if (phase.group_id) return [groupById.get(phase.group_id)].filter(Boolean);
    return definition.groups
      .filter((item) => item.module_id === phase.module_id)
      .sort((a, b) => (a.order || 0) - (b.order || 0));
  }

  function currentPhase() {
    return definition.phases[state.phaseIndex];
  }

  function currentGroup() {
    return phaseGroups(currentPhase())[state.groupIndex];
  }

  function setSaveState(label, pending = false) {
    elements.save.textContent = label;
    elements.save.style.color = pending ? "#ffe0a8" : "";
  }

  async function api(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
    return payload;
  }

  function updateUrl() {
    if (!attempt) return;
    const url = new URL(window.location.href);
    url.searchParams.set("attemptId", attempt.id);
    if (config.preview) url.searchParams.set("preview", "1");
    history.replaceState({}, "", url);
  }

  function phaseDuration(phase) {
    return phase.duration_seconds == null ? null : Number(phase.duration_seconds);
  }

  function formatTime(seconds) {
    if (seconds == null) return "AUDIO";
    const safe = Math.max(0, seconds);
    const minutes = Math.floor(safe / 60);
    const rest = safe % 60;
    return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
  }

  function updateProgress() {
    const phase = currentPhase();
    document.querySelectorAll(".mock-progress span").forEach((node) => {
      const sectionIndex = definition.sections.indexOf(node.dataset.section);
      const currentIndex = definition.sections.indexOf(phase.section);
      node.classList.toggle("is-active", sectionIndex === currentIndex);
      node.classList.toggle("is-complete", sectionIndex < currentIndex);
    });
  }

  function responseControl(question) {
    const wrapper = document.createElement("article");
    wrapper.className = `mock-question${question.available ? "" : " is-blocked"}`;
    const label = document.createElement("label");
    label.textContent = `${question.number}. ${question.prompt || "Respond to the item."}`;
    wrapper.appendChild(label);

    if (!question.available) {
      const note = document.createElement("p");
      note.className = "mock-blocked-note";
      note.textContent = "该题来源证据不完整，Staging 中禁用，不进入判分分母。";
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
        output.textContent = selected.join(" ");
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
      output.addEventListener("click", () => {
        selected.pop();
        renderOrder();
        saveResponse(question.id, selected);
      });
      wrapper.append(tokenBox, output);
      renderOrder();
      return wrapper;
    }

    if (question.response_type === "recording") {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "mock-secondary";
      button.textContent = value?.recorded ? "重新录音" : "开始录音";
      button.addEventListener("click", () => recordResponse(question.id, button));
      wrapper.appendChild(button);
      return wrapper;
    }

    const input = document.createElement(
      question.response_type === "free_text" ? "textarea" : "input"
    );
    if (input.tagName === "INPUT") input.type = "text";
    input.value = typeof value === "string" ? value : "";
    input.placeholder = question.input_config?.visible_prefix
      ? `可见前缀：${question.input_config.visible_prefix}`
      : "Type your response";
    input.addEventListener("input", () => scheduleResponseSave(question.id, input.value));
    wrapper.appendChild(input);
    return wrapper;
  }

  function renderStimulus(group) {
    elements.stimulus.replaceChildren();
    const stimulus = group.stimulus || {};
    const text = stimulus.display_text || stimulus.text || stimulus.prompt || "";
    if (stimulus.format !== "inline_completion") {
      elements.stimulus.textContent = text;
      return false;
    }
    const questionMap = new Map(
      (group.question_ids || []).map((questionId) => {
        const question = questionById.get(questionId);
        return [String(question?.number || "").padStart(2, "0"), question];
      })
    );
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
      input.ariaLabel = `Question ${question.number}`;
      input.value = typeof responses[question.id] === "string" ? responses[question.id] : "";
      input.addEventListener("input", () => scheduleResponseSave(question.id, input.value));
      inline.appendChild(input);
      elements.stimulus.appendChild(inline);
    });
    return true;
  }

  function render() {
    const phase = currentPhase();
    const groups = phaseGroups(phase);
    const group = groups[state.groupIndex];
    if (!phase || !group) return;
    elements.welcome.hidden = true;
    elements.report.hidden = true;
    elements.panel.hidden = false;
    elements.section.textContent = phase.section;
    elements.phase.textContent = phase.label;
    elements.groupType.textContent = group.task_type.replaceAll("_", " ");
    elements.groupTitle.textContent = group.title || phase.label;
    elements.groupCounter.textContent = `Group ${state.groupIndex + 1} of ${groups.length}`;
    const hasInlineQuestions = renderStimulus(group);
    elements.questions.replaceChildren();
    if (!hasInlineQuestions) {
      (group.question_ids || []).forEach((questionId) => {
        const question = questionById.get(questionId);
        if (question) elements.questions.appendChild(responseControl(question));
      });
    }
    const module = moduleById.get(phase.module_id);
    const previousPhase = definition.phases[state.phaseIndex - 1];
    const canCrossPhase =
      previousPhase && previousPhase.module_id === phase.module_id;
    elements.back.disabled =
      module?.navigation?.back_policy !== "within_module" ||
      (state.groupIndex === 0 && !canCrossPhase);
    elements.next.disabled = false;
    elements.next.textContent =
      state.phaseIndex === definition.phases.length - 1 &&
      state.groupIndex === groups.length - 1
        ? "Complete"
        : "Next";
    elements.timer.textContent = formatTime(remainingSeconds);
    updateProgress();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function saveResponse(questionId, value) {
    responses[questionId] = value;
    setSaveState("保存中…", true);
    try {
      await api("/api/toefl/responses", {
        method: "POST",
        body: JSON.stringify({
          attemptId: attempt.id,
          questionId,
          response: value,
        }),
      });
      setSaveState("已保存");
    } catch (error) {
      setSaveState(`保存失败：${error.message}`, true);
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
      saveResponse(questionId, pendingValue);
    }, 350);
    responseSaveTimers.set(questionId, timer);
  }

  async function flushPendingResponses() {
    const pending = [...pendingResponseValues.entries()];
    pendingResponseValues.clear();
    responseSaveTimers.forEach((timer) => clearTimeout(timer));
    responseSaveTimers.clear();
    await Promise.all(pending.map(([questionId, value]) => saveResponse(questionId, value)));
  }

  async function recordResponse(questionId, button) {
    if (button.activeRecorder?.state === "recording") {
      button.activeRecorder.stop();
      return;
    }
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      alert("当前浏览器不支持录音，请使用 Chrome 或 Safari 最新版。");
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    button.activeRecorder = recorder;
    const chunks = [];
    recorder.addEventListener("dataavailable", (event) => chunks.push(event.data));
    recorder.addEventListener("stop", async () => {
      stream.getTracks().forEach((track) => track.stop());
      button.activeRecorder = null;
      const form = new FormData();
      form.append("attemptId", attempt.id);
      form.append("questionId", questionId);
      form.append("audio", new Blob(chunks, { type: recorder.mimeType }), "response.webm");
      button.textContent = "上传中…";
      const response = await fetch("/api/toefl/recordings", {
        method: "POST",
        credentials: "same-origin",
        body: form,
      });
      if (!response.ok) {
        button.textContent = "上传失败，重试";
        return;
      }
      responses[questionId] = { recorded: true };
      button.textContent = "重新录音";
      setSaveState("录音已保存");
    });
    recorder.start();
    button.textContent = "停止并保存";
  }

  async function persistState() {
    if (!attempt) return;
    await api(`/api/toefl/attempts/${attempt.id}/state`, {
      method: "PUT",
      body: JSON.stringify({
        state,
        currentPhase: currentPhase()?.id,
        remainingSeconds,
      }),
    });
  }

  async function advance() {
    if (advancing) return;
    advancing = true;
    await flushPendingResponses();
    const phase = currentPhase();
    const groups = phaseGroups(phase);
    try {
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
        elements.route.textContent = `${phase.section} M2 route: ${route.route}（未编造分支）`;
      }
      if (state.phaseIndex >= definition.phases.length - 1) {
        await finish();
        return;
      }
      state.phaseIndex += 1;
      state.groupIndex = 0;
      remainingSeconds = phaseDuration(currentPhase());
      await persistState();
      render();
    } finally {
      advancing = false;
    }
  }

  async function goBack() {
    await flushPendingResponses();
    const phase = currentPhase();
    const module = moduleById.get(phase.module_id);
    if (module?.navigation?.back_policy !== "within_module") return;
    if (state.groupIndex > 0) {
      state.groupIndex -= 1;
    } else if (state.phaseIndex > 0) {
      const previousPhase = definition.phases[state.phaseIndex - 1];
      if (previousPhase.module_id !== phase.module_id) return;
      state.phaseIndex -= 1;
      const previousGroups = phaseGroups(previousPhase);
      state.groupIndex = Math.max(0, previousGroups.length - 1);
    }
    remainingSeconds = phaseDuration(currentPhase());
    await persistState();
    render();
  }

  async function finish(alreadyCompleted = false) {
    elements.next.disabled = true;
    await flushPendingResponses();
    if (!alreadyCompleted) {
      await api(`/api/toefl/attempts/${attempt.id}/complete`, {
        method: "POST",
        body: "{}",
      });
    }
    const report = await api(`/api/toefl/attempts/${attempt.id}/report`);
    elements.panel.hidden = true;
    elements.report.hidden = false;
    const accuracy =
      report.objective.accuracy == null
        ? "—"
        : `${Math.round(report.objective.accuracy * 100)}%`;
    elements.report.innerHTML = `
      <p class="mock-kicker">STAGING ATTEMPT REPORT</p>
      <h2>流程已完整结束</h2>
      <p>这是结构和交互验证结果，不是已发布成绩单。</p>
      <div class="report-metrics">
        <div><strong>${report.objective.correct}</strong><span>客观题正确</span></div>
        <div><strong>${accuracy}</strong><span>已判分准确率</span></div>
        <div><strong>${report.manual.submitted}/${report.manual.total}</strong><span>主观题已提交</span></div>
      </div>`;
    const returnLine = document.createElement("p");
    const returnLink = document.createElement("a");
    returnLink.href = attempt.state?.returnTo || config.returnTo || "/toefl/mock";
    returnLink.textContent = "返回";
    returnLine.appendChild(returnLink);
    elements.report.appendChild(returnLine);
    elements.timer.textContent = "--:--";
    elements.next.hidden = true;
    elements.back.hidden = true;
  }

  async function start() {
    elements.start.disabled = true;
    try {
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
      state = { phaseIndex: 0, groupIndex: 0, returnTo: config.returnTo };
      responses = {};
      remainingSeconds = phaseDuration(currentPhase());
      updateUrl();
      render();
      setSaveState("已建立 attempt");
    } catch (error) {
      elements.start.disabled = false;
      elements.start.textContent = `无法开始：${error.message}`;
    }
  }

  async function resume(attemptId) {
    const payload = await api(`/api/toefl/attempts/${attemptId}/resume`);
    attempt = payload.attempt;
    state = { phaseIndex: 0, groupIndex: 0, ...(attempt.state || {}) };
    responses = attempt.responses || {};
    remainingSeconds = attempt.remaining_seconds;
    updateUrl();
    if (attempt.status === "completed") {
      await finish(true);
      return;
    }
    render();
    setSaveState("已恢复");
  }

  function showReview() {
    elements.reviewList.replaceChildren();
    definition.questions.forEach((question) => {
      const row = document.createElement("div");
      row.className = "review-row";
      const value = responses[question.id];
      row.innerHTML = `<span>${question.subject} · Q${question.number}</span><strong>${
        value == null || value === "" ? "未作答" : "已作答"
      }</strong>`;
      elements.reviewList.appendChild(row);
    });
    elements.reviewDialog.showModal();
  }

  elements.start.addEventListener("click", start);
  elements.next.addEventListener("click", advance);
  elements.back.addEventListener("click", goBack);
  elements.review.addEventListener("click", showReview);
  elements.closeReview.addEventListener("click", () => elements.reviewDialog.close());

  setInterval(() => {
    if (!attempt || elements.panel.hidden || remainingSeconds == null) return;
    remainingSeconds = Math.max(0, remainingSeconds - 1);
    elements.timer.textContent = formatTime(remainingSeconds);
    tickCount += 1;
    if (remainingSeconds === 0 && !advancing) {
      advance().catch((error) => setSaveState(`自动推进失败：${error.message}`, true));
      return;
    }
    if (tickCount % 15 === 0) persistState().catch(() => setSaveState("计时同步失败", true));
  }, 1000);

  const attemptId = new URL(window.location.href).searchParams.get("attemptId");
  if (attemptId) {
    resume(attemptId).catch((error) => {
      elements.start.disabled = false;
      elements.start.textContent = `恢复失败，重新开始（${error.message}）`;
    });
  }
})();
