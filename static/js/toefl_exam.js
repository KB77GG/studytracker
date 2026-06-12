(function () {
  "use strict";

  const exam = window.TOEFL_EXAM;
  const questions = exam.questions || [];
  const storageKey = `toefl:${exam.id}:${exam.subject}`;
  const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
  const moduleIds = questions.reduce((ids, question) => {
    if (!ids.includes(question.module_id)) ids.push(question.module_id);
    return ids;
  }, []);
  const savedIndex = Math.min(Number(saved.index) || 0, Math.max(questions.length - 1, 0));
  const initialModule = questions[savedIndex] ? questions[savedIndex].module_id : "main";
  const initialModuleFloor = Math.max(
    0,
    questions.findIndex((question) => question.module_id === initialModule)
  );
  const defaultModuleDuration = moduleIds.length > 1
    ? Math.floor(exam.duration_seconds / moduleIds.length)
    : exam.duration_seconds;
  const state = {
    index: savedIndex,
    responses: saved.responses || {},
    recordingTokens: saved.recordingTokens || {},
    recordingMeta: saved.recordingMeta || {},
    elapsed: Number(saved.elapsed) || 0,
    remaining: Number(saved.remaining) || Number((exam.module_durations || {})[initialModule]) || defaultModuleDuration,
    timerHidden: false,
    moduleIntro: typeof saved.moduleIntro === "boolean"
      ? saved.moduleIntro
      : (exam.subject === "listening" || moduleIds.length > 1),
    moduleFloor: Object.prototype.hasOwnProperty.call(saved, "moduleFloor")
      ? Math.max(0, Number(saved.moduleFloor) || 0)
      : initialModuleFloor,
    activeModule: null,
    submitted: false,
    timerTransitioning: false
  };

  const stage = document.getElementById("examStage");
  const nextButton = document.getElementById("nextButton");
  const backButton = document.getElementById("backButton");
  const reviewButton = document.getElementById("reviewButton");
  const volumeButton = document.getElementById("volumeButton");
  const helpButton = document.getElementById("helpButton");
  const timerDisplay = document.getElementById("timerDisplay");
  const timerToggle = document.getElementById("timerToggle");
  const questionCounter = document.getElementById("questionCounter");
  const audioDrawer = document.getElementById("audioDrawer");
  const moduleAudio = document.getElementById("moduleAudio");
  const audioModuleLabel = document.getElementById("audioModuleLabel");
  const recordings = new Map();
  let activeRecorder = null;
  let activeRecorderQuestionId = null;

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function persist() {
    localStorage.setItem(storageKey, JSON.stringify({
      index: state.index,
      responses: state.responses,
      recordingTokens: state.recordingTokens,
      recordingMeta: state.recordingMeta,
      elapsed: state.elapsed,
      remaining: state.remaining,
      moduleIntro: state.moduleIntro,
      moduleFloor: state.moduleFloor
    }));
  }

  function formatTime(totalSeconds) {
    const value = Math.max(0, totalSeconds);
    const hours = Math.floor(value / 3600);
    const minutes = Math.floor((value % 3600) / 60);
    const seconds = value % 60;
    return [hours, minutes, seconds].map((item) => String(item).padStart(2, "0")).join(":");
  }

  function currentQuestion() {
    return questions[state.index] || null;
  }

  function moduleDuration(moduleId) {
    return Number((exam.module_durations || {})[moduleId]) || defaultModuleDuration;
  }

  function moduleNumber(moduleId) {
    const index = moduleIds.indexOf(moduleId);
    return index >= 0 ? index + 1 : 1;
  }

  function moduleQuestionIndexes(moduleId) {
    return questions
      .map((question, index) => question.module_id === moduleId ? index : -1)
      .filter((index) => index >= 0);
  }

  function currentResponse(question) {
    return state.responses[question.id];
  }

  function hasResponse(question) {
    const value = currentResponse(question);
    if (question.response_type === "record") {
      return Boolean(state.recordingTokens[question.id]);
    }
    if (question.response_type === "free") {
      return Boolean(String(value || "").trim());
    }
    if (Array.isArray(value)) return value.some((item) => String(item || "").trim());
    return Boolean(String(value || "").trim());
  }

  function setResponse(question, value) {
    state.responses[question.id] = value;
    persist();
  }

  function optionMarkup(question) {
    const selected = String(currentResponse(question) || "");
    return `
      <div class="option-list">
        ${(question.options || []).map((option) => `
          <label class="option">
            <input type="radio" name="answer" value="${escapeHtml(option.key)}" ${selected === String(option.key) ? "checked" : ""}>
            <span><span class="option-key">${escapeHtml(option.key)}.</span>${escapeHtml(option.text)}</span>
          </label>
        `).join("")}
      </div>`;
  }

  function passageText(question) {
    return question.passage && question.passage.text ? question.passage.text : "";
  }

  function renderMultipleChoice(question) {
    if (exam.subject === "reading") {
      stage.innerHTML = `
        <section class="question-shell reading-layout">
          <article class="reading-passage">${escapeHtml(passageText(question))}</article>
          <article class="reading-question">
            <p class="question-source-number">Question ${escapeHtml(question.number || state.index + 1)}</p>
            <h1 class="question-title">${escapeHtml(question.prompt || question.directive || "Choose the best answer.")}</h1>
            ${optionMarkup(question)}
          </article>
        </section>`;
    } else {
      stage.innerHTML = `
        <section class="question-shell listening-question">
          <p class="question-directive">${escapeHtml(question.directive || "Choose the best answer.")}</p>
          <h1 class="question-title">${escapeHtml(question.prompt || "Choose the best response.")}</h1>
          ${optionMarkup(question)}
        </section>`;
    }
    stage.querySelectorAll('input[name="answer"]').forEach((input) => {
      input.addEventListener("change", () => setResponse(question, input.value));
    });
  }

  function renderFill(question) {
    const values = Array.isArray(currentResponse(question)) ? currentResponse(question) : [];
    const count = Math.max(1, Number(question.number_end) - Number(question.number) + 1 || 1);
    stage.innerHTML = `
      <section class="question-shell reading-layout">
        <article class="reading-passage">${escapeHtml(passageText(question))}</article>
        <article class="reading-question">
          <p class="question-source-number">Questions ${escapeHtml(question.number)}-${escapeHtml(question.number_end || question.number)}</p>
          <h1 class="question-title">${escapeHtml(question.directive || "Complete the words.")}</h1>
          <p class="fill-instructions">Type the complete missing words in passage order.</p>
          <div class="fill-grid">
            ${Array.from({ length: count }, (_, index) => `
              <label class="fill-item">
                <span>${Number(question.number) + index}</span>
                <input type="text" data-fill-index="${index}" value="${escapeHtml(values[index] || "")}" autocomplete="off">
              </label>
            `).join("")}
          </div>
        </article>
      </section>`;
    stage.querySelectorAll("[data-fill-index]").forEach((input) => {
      input.addEventListener("input", () => {
        const next = Array.from({ length: count }, (_, index) => {
          const field = stage.querySelector(`[data-fill-index="${index}"]`);
          return field ? field.value : "";
        });
        setResponse(question, next);
      });
    });
  }

  function renderOrder(question) {
    const selectedIndexes = Array.isArray(currentResponse(question)) ? currentResponse(question) : [];
    const words = question.scramble_words || [];
    const selectedWords = selectedIndexes.map((index) => words[index]).filter((word) => word !== undefined);
    stage.innerHTML = `
      <section class="question-shell writing-shell">
        <h1 class="question-title">Make an appropriate sentence.</h1>
        <div class="dialogue-panel">
          <img class="speaker-avatar" src="/static/toefl/assets/speaker-professor.png" alt="Professor">
          <div class="speech-card">${escapeHtml(question.prompt || "")}</div>
        </div>
        <div class="dialogue-panel">
          <img class="speaker-avatar" src="/static/toefl/assets/speaker-student.png" alt="Student">
          <div class="order-answer" id="orderAnswer">
            ${selectedWords.length ? selectedWords.map((word, position) => `<button class="word-token" data-remove-position="${position}" type="button">${escapeHtml(word)}</button>`).join("") : '<span class="order-placeholder">Select words below to build the response.</span>'}
          </div>
        </div>
        <div class="word-bank">
          ${words.map((word, index) => `<button class="word-token" data-word-index="${index}" type="button" ${selectedIndexes.includes(index) ? "disabled" : ""}>${escapeHtml(word)}</button>`).join("")}
        </div>
      </section>`;
    stage.querySelectorAll("[data-word-index]").forEach((button) => {
      button.addEventListener("click", () => {
        setResponse(question, selectedIndexes.concat(Number(button.dataset.wordIndex)));
        render();
      });
    });
    stage.querySelectorAll("[data-remove-position]").forEach((button) => {
      button.addEventListener("click", () => {
        const next = selectedIndexes.slice();
        next.splice(Number(button.dataset.removePosition), 1);
        setResponse(question, next);
        render();
      });
    });
  }

  function renderFree(question) {
    const value = String(currentResponse(question) || "");
    stage.innerHTML = `
      <section class="question-shell free-layout">
        <article class="free-prompt">
          <p class="question-directive">${escapeHtml(question.directive || "Writing Task")}</p>
          ${escapeHtml(question.prompt || "")}
        </article>
        <article class="free-editor">
          <textarea id="freeResponse" aria-label="Writing response">${escapeHtml(value)}</textarea>
          <div class="word-count" id="wordCount"></div>
        </article>
      </section>`;
    const textarea = document.getElementById("freeResponse");
    const wordCount = document.getElementById("wordCount");
    const updateCount = () => {
      const count = textarea.value.trim() ? textarea.value.trim().split(/\s+/).length : 0;
      wordCount.textContent = `Word Count: ${count}`;
      setResponse(question, textarea.value);
    };
    textarea.addEventListener("input", updateCount);
    updateCount();
  }

  function renderRecord(question) {
    const localRecording = recordings.get(question.id);
    const savedRecording = state.recordingMeta[question.id];
    const recording = localRecording || (
      savedRecording && savedRecording.audio_url
        ? { url: savedRecording.audio_url }
        : null
    );
    const hasRecording = hasResponse(question);
    const evaluation = savedRecording && savedRecording.evaluation;
    const scoreMarkup = evaluation
      ? `<div class="recording-score recording-score--${escapeHtml(evaluation.status || "pending_review")}">
          <strong>${evaluation.score == null ? "Pending review" : `${escapeHtml(evaluation.score)} / ${escapeHtml(evaluation.score_max || 5)}`}</strong>
          <span>${escapeHtml(evaluation.feedback_zh || "")}</span>
        </div>`
      : "";
    stage.innerHTML = `
      <section class="question-shell speaking-shell">
        <p class="question-directive">${escapeHtml(question.directive || "Record your response.")}</p>
        ${question.passage && question.passage.text
          ? `<div class="speaking-context">${escapeHtml(question.passage.text)}</div>`
          : ""}
        <h1 class="question-title">${escapeHtml(question.prompt || "Respond after the prompt.")}</h1>
        <div class="recording-panel">
          <div class="recording-status" id="recordingStatus">${hasRecording ? "Response recorded" : "Microphone ready"}</div>
          <div class="recording-actions">
            <button class="record-button" id="recordButton" type="button">Start Recording</button>
            <button class="record-button record-button--stop" id="stopRecordButton" type="button" disabled>Stop</button>
          </div>
          ${recording ? `<audio class="recording-playback" controls src="${recording.url}"></audio>` : ""}
          ${scoreMarkup}
          <p class="recording-note">Stopping the recording uploads it to the student record. Automated scores are practice estimates and remain available for teacher review.</p>
        </div>
      </section>`;
    const recordButton = document.getElementById("recordButton");
    const stopButton = document.getElementById("stopRecordButton");
    const status = document.getElementById("recordingStatus");
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      recordButton.disabled = true;
      status.textContent = "This browser does not support microphone recording.";
      return;
    }
    recordButton.addEventListener("click", async () => {
      try {
        delete state.recordingTokens[question.id];
        delete state.recordingMeta[question.id];
        setResponse(question, "");
        nextButton.disabled = true;
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const chunks = [];
        activeRecorder = new MediaRecorder(stream);
        activeRecorderQuestionId = question.id;
        activeRecorder.addEventListener("dataavailable", (event) => {
          if (event.data.size) chunks.push(event.data);
        });
        activeRecorder.addEventListener("stop", async () => {
          const blob = new Blob(chunks, { type: activeRecorder.mimeType || "audio/webm" });
          const previous = recordings.get(question.id);
          if (previous) URL.revokeObjectURL(previous.url);
          recordings.set(question.id, { blob, url: URL.createObjectURL(blob) });
          stream.getTracks().forEach((track) => track.stop());
          activeRecorder = null;
          activeRecorderQuestionId = null;
          status.textContent = "Uploading and scoring...";
          recordButton.disabled = true;
          stopButton.disabled = true;
          const formData = new FormData();
          formData.append("question_id", question.id);
          formData.append("audio", blob, `response-${question.id}.webm`);
          try {
            const response = await fetch(
              `/api/toefl/test/${encodeURIComponent(exam.id)}/speaking/recording`,
              { method: "POST", body: formData }
            );
            const result = await response.json();
            if (!response.ok || !result.ok) {
              throw new Error(result.message || result.error || "upload_failed");
            }
            state.recordingTokens[question.id] = result.recording_token;
            state.recordingMeta[question.id] = {
              audio_url: result.audio_url,
              transcript: result.transcript || "",
              evaluation: result.evaluation || null
            };
            setResponse(question, "recorded");
            render();
          } catch (error) {
            status.textContent = error.message || "Upload failed. Please record again.";
            recordButton.disabled = false;
            nextButton.disabled = false;
          }
        });
        activeRecorder.start();
        status.textContent = "Recording...";
        recordButton.disabled = true;
        stopButton.disabled = false;
      } catch (_error) {
        status.textContent = "Microphone permission is required.";
        nextButton.disabled = false;
      }
    });
    stopButton.addEventListener("click", () => {
      if (activeRecorder && activeRecorderQuestionId === question.id) {
        activeRecorder.stop();
      }
    });
  }

  function audioModule(moduleId) {
    return (exam.audio_modules || []).find((item) => item.id === moduleId);
  }

  function setAudioModule(moduleId) {
    const module = audioModule(moduleId);
    if (!module || state.activeModule === moduleId) return;
    state.activeModule = moduleId;
    moduleAudio.src = module.url;
    audioModuleLabel.textContent = module.label || "Listening audio";
  }

  function renderModuleIntro(question) {
    const usesAudio = exam.subject === "listening" || exam.subject === "speaking";
    if (usesAudio) setAudioModule(question.module_id);
    const module = audioModule(question.module_id);
    const label = module && module.label
      ? module.label
      : `${exam.subject_label} Module ${moduleNumber(question.module_id)}`;
    stage.innerHTML = `
      <section class="module-intro">
        <p class="module-intro__eyebrow">${escapeHtml(exam.title || "TOEFL Practice")}</p>
        <h1>${escapeHtml(label)}</h1>
        <p>${exam.subject === "listening"
          ? "The audio continues through this module. Once you select Next on a listening question, you cannot return to it."
          : exam.subject === "speaking"
          ? "Listen to the module prompt, record each response, and continue in order."
          : "You may review answers within this module. Once you begin the next module, you cannot return to this one."}</p>
        <button class="start-button" id="startModuleButton" type="button">Start Module</button>
      </section>`;
    document.getElementById("startModuleButton").addEventListener("click", async () => {
      if (usesAudio) {
        audioDrawer.hidden = false;
        try { await moduleAudio.play(); } catch (_error) {}
      }
      state.moduleIntro = false;
      persist();
      render();
    });
  }

  function updateChrome(question) {
    const currentModuleIndexes = moduleQuestionIndexes(question.module_id);
    const modulePosition = currentModuleIndexes.indexOf(state.index) + 1;
    questionCounter.textContent = `Module ${moduleNumber(question.module_id)} | Question ${modulePosition} of ${currentModuleIndexes.length}`;
    document.getElementById("sectionLabel").textContent = exam.subject_label;
    backButton.hidden = exam.subject === "listening" || exam.subject === "speaking";
    reviewButton.hidden = exam.subject === "listening" || exam.subject === "speaking";
    volumeButton.hidden = exam.subject !== "listening" && exam.subject !== "speaking";
    backButton.disabled = state.moduleIntro || state.index <= state.moduleFloor;
    reviewButton.disabled = state.moduleIntro;
    nextButton.disabled = state.moduleIntro;
    nextButton.textContent = state.index === questions.length - 1 ? "Submit" : "Next";
    if (question && (exam.subject === "listening" || exam.subject === "speaking")) {
      setAudioModule(question.module_id);
    }
  }

  function render() {
    const question = currentQuestion();
    if (!question) {
      stage.innerHTML = '<section class="module-intro"><h1>No available questions</h1></section>';
      nextButton.disabled = true;
      return;
    }
    updateChrome(question);
    timerDisplay.textContent = state.timerHidden ? "--:--:--" : formatTime(state.remaining);
    if (state.moduleIntro) {
      renderModuleIntro(question);
      return;
    }
    if (question.response_type === "mc") renderMultipleChoice(question);
    else if (question.response_type === "fill") renderFill(question);
    else if (question.response_type === "order") renderOrder(question);
    else if (question.response_type === "record") renderRecord(question);
    else renderFree(question);
  }

  function openModal(id) {
    document.getElementById(id).hidden = false;
  }

  function closeModal(id) {
    document.getElementById(id).hidden = true;
  }

  function renderReview() {
    const grid = document.getElementById("reviewGrid");
    const current = currentQuestion();
    grid.innerHTML = questions.map((question, index) => {
      if (!current || question.module_id !== current.module_id || index < state.moduleFloor) return "";
      return `
      <button class="review-item ${hasResponse(question) ? "is-answered" : ""} ${index === state.index ? "is-current" : ""}" data-review-index="${index}" type="button">${index + 1}</button>
    `;
    }).join("");
    grid.querySelectorAll("[data-review-index]").forEach((button) => {
      button.addEventListener("click", () => {
        state.index = Number(button.dataset.reviewIndex);
        state.moduleIntro = false;
        persist();
        closeModal("reviewModal");
        render();
      });
    });
  }

  function beginNextModule() {
    const question = currentQuestion();
    if (!question) return false;
    const nextIndex = questions.findIndex(
      (candidate, index) => index > state.index && candidate.module_id !== question.module_id
    );
    if (nextIndex < 0) return false;
    state.index = nextIndex;
    state.moduleFloor = nextIndex;
    state.moduleIntro = true;
    state.remaining = moduleDuration(questions[nextIndex].module_id);
    state.timerTransitioning = false;
    persist();
    render();
    return true;
  }

  async function submitExam() {
    nextButton.disabled = true;
    nextButton.textContent = "Submitting";
    try {
      const submissionResponses = Object.assign({}, state.responses);
      questions.forEach((question) => {
        if (question.response_type !== "order") return;
        const indexes = Array.isArray(state.responses[question.id]) ? state.responses[question.id] : [];
        submissionResponses[question.id] = indexes
          .map((index) => (question.scramble_words || [])[index])
          .filter((word) => word !== undefined);
      });
      const response = await fetch(`/api/toefl/test/${encodeURIComponent(exam.id)}/${encodeURIComponent(exam.subject)}/grade`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          responses: submissionResponses,
          recording_tokens: state.recordingTokens,
          duration_seconds: state.elapsed
        })
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error("submit_failed");
      state.submitted = true;
      localStorage.removeItem(storageKey);
      const resultTitle = document.getElementById("resultTitle");
      if (result.practice_score != null) {
        resultTitle.textContent = `Practice score ${result.practice_score} / ${result.practice_score_max || 5}`;
      } else {
        resultTitle.textContent = `${result.correct} of ${result.auto_total} auto-graded responses correct`;
      }
      const reviewParts = [];
      if (result.auto_total) reviewParts.push(`Objective accuracy ${result.accuracy}%`);
      if (result.pending_review_count) reviewParts.push(`${result.pending_review_count} response(s) require teacher review`);
      if (result.review_only_count) reviewParts.push(`${result.review_only_count} question(s) have no reliable answer key`);
      reviewParts.push(result.synced
        ? `Saved to ${result.student_name || "the student"}'s record`
        : "This attempt was not linked to a verified student");
      if (result.score_note) reviewParts.push(result.score_note);
      document.getElementById("resultSummary").textContent =
        `${reviewParts.join(". ")}.`;
      openModal("resultModal");
    } catch (_error) {
      nextButton.disabled = false;
      nextButton.textContent = "Submit";
      window.alert("Submission failed. Please try again.");
    }
  }

  nextButton.addEventListener("click", () => {
    const question = currentQuestion();
    if (!question || state.moduleIntro) return;
    if ((exam.subject === "listening" || exam.subject === "speaking") && !hasResponse(question)) {
      openModal("requiredModal");
      return;
    }
    if (state.index === questions.length - 1) {
      submitExam();
      return;
    }
    const currentModule = question.module_id;
    state.index += 1;
    const nextQuestion = currentQuestion();
    if (nextQuestion.module_id !== currentModule) {
      state.moduleFloor = state.index;
      state.moduleIntro = true;
      state.remaining = moduleDuration(nextQuestion.module_id);
    }
    persist();
    render();
  });

  backButton.addEventListener("click", () => {
    if (
      state.index <= state.moduleFloor
      || exam.subject === "listening"
      || exam.subject === "speaking"
    ) return;
    state.index -= 1;
    persist();
    render();
  });

  reviewButton.addEventListener("click", () => {
    renderReview();
    openModal("reviewModal");
  });
  helpButton.addEventListener("click", () => openModal("helpModal"));
  volumeButton.addEventListener("click", () => {
    audioDrawer.hidden = !audioDrawer.hidden;
  });
  timerToggle.addEventListener("click", () => {
    state.timerHidden = !state.timerHidden;
    timerDisplay.textContent = state.timerHidden ? "--:--:--" : formatTime(state.remaining);
    timerToggle.textContent = state.timerHidden ? "Show Time" : "Hide Time";
  });
  document.querySelectorAll("[data-close-modal]").forEach((button) => {
    button.addEventListener("click", () => closeModal(button.dataset.closeModal));
  });

  timerDisplay.textContent = formatTime(state.remaining);
  window.setInterval(() => {
    if (state.submitted || state.moduleIntro || state.remaining <= 0 || state.timerTransitioning) return;
    state.remaining -= 1;
    state.elapsed += 1;
    if (!state.timerHidden) timerDisplay.textContent = formatTime(state.remaining);
    if (state.remaining % 5 === 0) persist();
    if (state.remaining === 0) {
      state.timerTransitioning = true;
      if (!beginNextModule()) submitExam();
    }
  }, 1000);

  render();
})();
