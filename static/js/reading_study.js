(() => {
  "use strict";

  const config = window.READING_STUDY_CONFIG || {};
  const passages = Array.isArray(config.passages) ? config.passages : [];
  const passageCache = new Map();
  const savedTexts = new Set();
  let glossary = { camps: {}, concepts: {} };
  let activePassageId = "";
  let activeSentenceIndex = 0;

  const $ = (selector) => document.querySelector(selector);

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[character]);
  }

  function normalizeText(value) {
    return String(value ?? "").trim().replace(/\s+/g, " ").toLowerCase();
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, { credentials: "same-origin", ...options });
    let data = null;
    try {
      data = await response.json();
    } catch (_error) {
      data = null;
    }
    if (!response.ok) {
      const error = new Error(data?.error || `HTTP ${response.status}`);
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  function setActiveTab(passageId) {
    document.querySelectorAll("[data-passage-id]").forEach((node) => {
      const active = node.dataset.passageId === passageId;
      node.classList.toggle("active", active);
      node.setAttribute("aria-current", active ? "true" : "false");
    });
  }

  async function loadSavedExpressions(passageId) {
    const params = new URLSearchParams({ passage_id: passageId });
    const data = await fetchJson(`/api/reading-study/expressions?${params}`);
    return new Set((data.saved || []).map((text) => normalizeText(text)));
  }

  async function loadPassage(passageId) {
    activePassageId = passageId;
    activeSentenceIndex = 0;
    setActiveTab(passageId);
    $("#articleBody").innerHTML = `<div class="loading">正在加载 ${escapeHtml(passageId)}…</div>`;
    $("#analysisBody").innerHTML = '<div class="loading">正在加载句子解析…</div>';

    try {
      let data = passageCache.get(passageId);
      if (!data) {
        data = await fetchJson(`/api/reading-study/passage/${encodeURIComponent(passageId)}`);
        passageCache.set(passageId, data);
      }
      let passageSavedTexts = new Set();
      try {
        passageSavedTexts = await loadSavedExpressions(passageId);
      } catch (_error) {
        // 收藏状态加载失败不应阻断只读的句子解析。
      }
      if (activePassageId !== passageId) return;
      savedTexts.clear();
      passageSavedTexts.forEach((text) => savedTexts.add(text));
      renderArticle(data);
      selectSentence(0);
    } catch (error) {
      if (activePassageId !== passageId) return;
      $("#articleBody").innerHTML = `<div class="loading">加载失败：${escapeHtml(error.message)}</div>`;
      $("#analysisBody").innerHTML = '<div class="loading">请稍后重试</div>';
    }
  }

  function renderArticle(data) {
    const level = { simple: "Simple", medium: "Medium", complex: "Complex" }[data.difficulty] || data.difficulty || "";
    $("#difficultyLabel").textContent = `${config.testId || data.test_id || "Reading"} · ${level}`;
    $("#articleTitle").textContent = data.passage_title || "Reading Passage";
    $("#articleMeta").textContent = `${(data.sentences || []).length} sentences · 点击句子查看解析`;

    const groups = new Map();
    (data.sentences || []).forEach((sentence, index) => {
      const label = sentence.paragraph_label || "";
      if (!groups.has(label)) groups.set(label, []);
      groups.get(label).push({ sentence, index });
    });
    $("#articleBody").innerHTML = Array.from(groups.entries()).map(([label, rows]) => `
      <div class="paragraph-group">
        <div class="paragraph-label">${escapeHtml(label)}</div>
        ${rows.map(({ sentence, index }) => `
          <button class="sentence-block" type="button" data-sentence-index="${index}">
            ${escapeHtml(sentence.sentence)}
          </button>
        `).join("")}
      </div>
    `).join("");
    document.querySelectorAll("[data-sentence-index]").forEach((button) => {
      button.addEventListener("click", () => selectSentence(Number(button.dataset.sentenceIndex)));
    });
  }

  function selectSentence(index) {
    const data = passageCache.get(activePassageId);
    const sentence = data?.sentences?.[index];
    if (!sentence) return;
    activeSentenceIndex = index;
    document.querySelectorAll("[data-sentence-index]").forEach((node) => {
      const active = Number(node.dataset.sentenceIndex) === index;
      node.classList.toggle("active", active);
      node.setAttribute("aria-pressed", active ? "true" : "false");
    });
    $("#sentenceCounter").textContent = `${index + 1} / ${data.sentences.length}`;
    renderAnalysis(sentence);
  }

  function expressionMarkup(expressions) {
    if (!expressions.length) {
      return '<div class="empty-expression">本句没有需要额外积累的表达。</div>';
    }
    return expressions.map((item, index) => {
      const saved = savedTexts.has(normalizeText(item.text));
      return `
        <div class="expression-row">
          <div>
            <div class="expression-text">${escapeHtml(item.text)}</div>
            <div class="expression-meaning">${escapeHtml(item.meaning_zh)}</div>
          </div>
          <button class="save-expression${saved ? " saved" : ""}" type="button" data-expression-index="${index}">
            ${saved ? "✓ 已加入" : "＋ 加入表达库"}
          </button>
        </div>
      `;
    }).join("");
  }

  function renderAnalysis(sentence) {
    const structure = Array.isArray(sentence.structure) ? sentence.structure : [];
    const difficultPoints = Array.isArray(sentence.difficult_points) ? sentence.difficult_points : [];
    const expressions = Array.isArray(sentence.expressions) ? sentence.expressions : [];
    $("#analysisBody").innerHTML = `
      <section class="module">
        <div class="module-label"><span class="module-index">1</span> Original Sentence</div>
        <div class="original">${escapeHtml(sentence.sentence)}</div>
      </section>
      <section class="module">
        <div class="module-label"><span class="module-index">2</span> Sentence Breakdown · 句子拆解 <span class="module-hint">点击语法标签看讲解</span></div>
        <div class="breakdown">
          ${structure.map((part, index) => `
            <div class="breakdown-row" data-level="${Math.min(Number(part.level) || 1, 4)}">
              <div class="breakdown-text">${escapeHtml(part.text)}</div>
              <button class="role" type="button" data-structure-index="${index}" title="点击查看讲解">
                ${escapeHtml(part.label_en || part.role)} · ${escapeHtml(part.label_zh || "语法成分")}
              </button>
            </div>
          `).join("")}
        </div>
      </section>
      <section class="module">
        <div class="module-label"><span class="module-index">3</span> Chinese Translation · 中文翻译</div>
        <div class="translation">${escapeHtml(sentence.translation)}</div>
      </section>
      <section class="module">
        <div class="module-label"><span class="module-index">4</span> Difficult Points · 难点说明</div>
        <ul class="point-list">${difficultPoints.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul>
      </section>
      <section class="module">
        <div class="module-label"><span class="module-index">5</span> Key Expressions · 重点表达</div>
        <div class="expression-list">${expressionMarkup(expressions)}</div>
      </section>
    `;

    document.querySelectorAll("[data-structure-index]").forEach((button) => {
      button.addEventListener("click", () => openGlossary(structure[Number(button.dataset.structureIndex)]));
    });
    document.querySelectorAll("[data-expression-index]").forEach((button) => {
      button.addEventListener("click", () => toggleExpression(expressions[Number(button.dataset.expressionIndex)], sentence, button));
    });
    $(".analysis-panel").scrollTo({ top: 0, behavior: "smooth" });
  }

  function openGlossary(part) {
    const concept = glossary.concepts?.[part.concept] || glossary.concepts?.generic_phrase || {};
    const camp = concept.camp || part.camp || "structure";
    $("#gCamp").textContent = glossary.camps?.[camp] || glossary.camps?.structure || "结构标记";
    $("#gCamp").dataset.camp = camp;
    $("#gTitle").textContent = `${part.label_zh || concept.zh || "语法成分"} · ${part.label_en || concept.en || part.role || "Structure"}`;
    $("#gDesc").textContent = concept.desc || "这是句子结构中的一个语法成分。";
    $("#gEx").textContent = concept.ex ? `例：${concept.ex}` : "";
    $("#gOverlay").hidden = false;
  }

  function closeOverlay(selector) {
    $(selector).hidden = true;
  }

  function showIdentityPrompt() {
    $("#identityOverlay").hidden = false;
  }

  async function toggleExpression(expression, sentence, button) {
    const normalized = normalizeText(expression.text);
    const removing = savedTexts.has(normalized);
    button.disabled = true;
    try {
      const options = {
        method: removing ? "DELETE" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(removing ? { text: expression.text } : {
          text: expression.text,
          meaning_zh: expression.meaning_zh || "",
          passage_id: activePassageId,
          sentence_id: sentence.id || String(activeSentenceIndex + 1),
          source_kind: config.sourceKind || ""
        })
      };
      await fetchJson("/api/reading-study/expressions", options);
      if (removing) savedTexts.delete(normalized);
      else savedTexts.add(normalized);
      button.classList.toggle("saved", !removing);
      button.textContent = removing ? "＋ 加入表达库" : "✓ 已加入";
    } catch (error) {
      if (error.status === 401 || error.data?.error === "need_student") {
        showIdentityPrompt();
      } else {
        window.alert(`收藏操作失败：${error.message}`);
      }
    } finally {
      button.disabled = false;
    }
  }

  function bindOverlays() {
    $("#gOverlay").addEventListener("click", (event) => {
      if (event.target === event.currentTarget) closeOverlay("#gOverlay");
    });
    $("#identityOverlay").addEventListener("click", (event) => {
      if (event.target === event.currentTarget) closeOverlay("#identityOverlay");
    });
    $("#gOverlay .g-close").addEventListener("click", () => closeOverlay("#gOverlay"));
    $("#identityOverlay .identity-close").addEventListener("click", () => closeOverlay("#identityOverlay"));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeOverlay("#gOverlay");
        closeOverlay("#identityOverlay");
      }
    });
  }

  async function init() {
    bindOverlays();
    document.querySelectorAll("[data-passage-id]").forEach((button) => {
      button.addEventListener("click", () => loadPassage(button.dataset.passageId));
    });
    if (!passages.length) {
      $("#articleBody").innerHTML = '<div class="loading">当前 Test 暂无可用解析。</div>';
      return;
    }
    try {
      glossary = await fetchJson("/api/reading-study/glossary");
      $("#toolbarNote").textContent = `共 ${passages.length} 篇 Passage · 点击左侧句子查看解析`;
      await loadPassage(passages[0].passage_id);
    } catch (error) {
      $("#articleBody").innerHTML = `<div class="loading">初始化失败：${escapeHtml(error.message)}</div>`;
    }
  }

  init();
})();
