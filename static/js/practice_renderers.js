(function practiceRendererModule(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.PracticeRenderers = api;
}(typeof globalThis !== "undefined" ? globalThis : this, function buildPracticeRenderers() {
  "use strict";

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[char]);
  }

  function decodeEntities(value) {
    return String(value == null ? "" : value)
      .replace(/&nbsp;|&#160;/gi, "\u00a0")
      .replace(/&lt;/gi, "<")
      .replace(/&gt;/gi, ">")
      .replace(/&quot;/gi, '"')
      .replace(/&#39;|&apos;/gi, "'")
      .replace(/&amp;/gi, "&");
  }

  function plainText(value) {
    return decodeEntities(value)
      .replace(/<\s*(?:br|divider)\s*\/?\s*>/gi, "\n")
      .replace(/<[^>]+>/g, "")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+/g, " ")
      .replace(/\s*\n\s*/g, "\n")
      .trim();
  }

  function visualCells(value) {
    const normalized = decodeEntities(value)
      .replace(/<\s*b\s*>([\s\S]*?)<\s*\/\s*b\s*>/gi, (_match, label) => `[[LABEL:${plainText(label)}]]`)
      .replace(/<\s*(?:br|divider)\s*\/?\s*>/gi, "\n")
      .replace(/<[^>]+>/g, "");
    const cells = [];
    normalized.split(/\r?\n/).forEach((line, lineIndex) => {
      const searchableLine = line.replace(/[ \t\u00a0]+$/g, "");
      const matcher = /[^ \t\u00a0](?:[\s\S]*?[^ \t\u00a0])?(?=[ \t\u00a0]{8,}|$)/g;
      let match;
      while ((match = matcher.exec(searchableLine))) {
        const raw = match[0];
        const start = match.index;
        cells.push({
          line: lineIndex,
          start,
          column: start >= 24 ? "right" : "left",
          raw,
          text: raw.replace(/\[\[LABEL:([^\]]+)\]\]/g, "$1").replace(/[\u00a0 \t]+/g, " ").trim(),
          labels: Array.from(raw.matchAll(/\[\[LABEL:([^\]]+)\]\]/g)).map((item) => item[1].trim())
        });
      }
    });
    return cells;
  }

  function usefulTitle(question) {
    return String(question && question.title || "")
      .replace(/【\s*】/g, "")
      .replace(/\[\s*\]/g, "")
      .trim()
      .replace(/^[-–—]\s*$/, "");
  }

  function fieldMeta(group, question, sharedCells) {
    const marker = `$${question.id}$`;
    const cells = sharedCells || visualCells(group.collect || "");
    const targetIndex = cells.findIndex((cell) => cell.raw.includes(marker));
    const target = targetIndex >= 0 ? cells[targetIndex] : null;
    let label = "";
    let labelIndex = -1;
    if (target) {
      const before = target.raw.slice(0, target.raw.indexOf(marker));
      const ownLabels = Array.from(before.matchAll(/\[\[LABEL:([^\]]+)\]\]/g)).map((item) => item[1].trim());
      label = ownLabels.at(-1) || "";
      if (label) labelIndex = targetIndex;
      if (!label && /:\s*$/.test(before.replace(/\[\[LABEL:[^\]]+\]\]/g, "").trim())) {
        label = plainText(before).replace(/:\s*$/, "");
      }
      if (!label) {
        for (let index = targetIndex - 1; index >= 0 && target.line - cells[index].line <= 4; index -= 1) {
          const candidate = cells[index];
          if (candidate.column !== target.column || !candidate.labels.length) continue;
          label = candidate.labels.at(-1);
          labelIndex = index;
          break;
        }
      }
    }
    if (!label) {
      const title = usefulTitle(question);
      const colon = title.match(/^([^:]{2,80}):/);
      label = colon ? colon[1].trim() : "";
    }
    const contextIndexes = [];
    if (target && labelIndex >= 0 && labelIndex < targetIndex) {
      for (let index = labelIndex + 1; index < targetIndex; index += 1) {
        const candidate = cells[index];
        if (candidate.column === target.column && !/\$\d+\$/.test(candidate.raw)) contextIndexes.push(index);
      }
      if (!contextIndexes.length) {
        for (let index = labelIndex - 1; index >= 0; index -= 1) {
          const candidate = cells[index];
          if (candidate.column !== target.column || !candidate.labels.length) continue;
          if (cells[labelIndex].line - candidate.line > 3) break;
          const segment = cells.slice(index, labelIndex).map((_cell, offset) => index + offset)
            .filter((cellIndex) => cells[cellIndex].column === target.column);
          if (!segment.some((cellIndex) => /\$\d+\$/.test(cells[cellIndex].raw))) contextIndexes.push(...segment);
          break;
        }
      }
    }
    return {
      label: label.replace(/:\s*$/, "").trim(),
      target,
      targetIndex,
      labelIndex,
      contextIndexes,
      context: contextIndexes.map((index) => cells[index].text).filter(Boolean),
      cells
    };
  }

  function targetPrefixIndexes(field) {
    if (!field || !field.target || field.targetIndex < 0) return [];
    return field.cells
      .map((cell, index) => ({ cell, index }))
      .filter(({ cell, index }) => (
        index < field.targetIndex &&
        cell.line === field.target.line &&
        !/\$\d+\$/.test(cell.raw)
      ))
      .map(({ index }) => index);
  }

  function targetSource(field) {
    if (!field || !field.target) return "";
    const prefix = targetPrefixIndexes(field).map((index) => field.cells[index].raw);
    return [...prefix, field.target.raw]
      .join(" ")
      .replace(/\[\[LABEL:([^\]]+)\]\]/g, "$1");
  }

  function questionTemplate(question, controlHtml) {
    const title = String(question && question.title || "");
    const questionNumber = String(question && question.number || "").replace(/\D/g, "");
    const cleanNumberBeforeBlank = (value) => questionNumber
      ? value.replace(new RegExp(`\\s+${questionNumber}\\s*$`), "")
      : value;
    if (/【\s*】/.test(title)) {
      const [before, after] = title.split(/【\s*】/, 2);
      return `${escapeHtml(cleanNumberBeforeBlank(before))}${controlHtml}${escapeHtml(after || "")}`;
    }
    if (/\[\s*\]/.test(title)) {
      const [before, after] = title.split(/\[\s*\]/, 2);
      return `${escapeHtml(cleanNumberBeforeBlank(before))}${controlHtml}${escapeHtml(after || "")}`;
    }
    return title.trim() ? `${escapeHtml(title)} ${controlHtml}` : controlHtml;
  }

  function targetTemplate(field, controlHtml) {
    const question = field && field.question || {};
    const marker = `$${question.id}$`;
    const raw = targetSource(field);
    const markerIndex = raw.indexOf(marker);
    if (markerIndex < 0) return controlHtml;
    const questionNumber = String(question.number || "").replace(/\D/g, "");
    let before = raw.slice(0, markerIndex);
    if (questionNumber) before = before.replace(new RegExp(`\\s+${questionNumber}\\s*$`), "");
    return `${escapeHtml(before)}${controlHtml}${escapeHtml(raw.slice(markerIndex + marker.length))}`;
  }

  function staticFacts(group, fields) {
    const normalizeLabel = (value) => String(value || "").replace(/:\s*$/, "").trim().toLowerCase();
    const usedLabels = new Set(fields.map((field) => normalizeLabel(field.label)).filter(Boolean));
    const questionMarkers = new Set((group.questions || []).map((question) => `$${question.id}$`));
    const promptCellIndexes = new Set(
      fields.filter((field) => !usefulTitle(field.question)).flatMap(targetPrefixIndexes)
    );
    const facts = [];
    visualCells(group.collect || "").forEach((cell, index) => {
      if (promptCellIndexes.has(index)) return;
      if (Array.from(questionMarkers).some((marker) => cell.raw.includes(marker))) return;
      let text = cell.text.replace(/\[\[LABEL:([^\]]+)\]\]/g, "$1").trim();
      if (!text || /^[-–—]+$/.test(text) || /^(?:Example|Answer)$/i.test(text)) return;
      if (usedLabels.has(normalizeLabel(text)) || /:\s*$/.test(text)) return;
      if (text.length > 150) return;
      if (!facts.includes(text)) facts.push(text);
    });
    return facts;
  }

  function formFields(group) {
    const cells = visualCells(group.collect || "");
    const fields = (group.questions || [])
      .slice()
      .sort((left, right) => Number(left.number || 0) - Number(right.number || 0))
      .map((question) => ({ question, ...fieldMeta(group, question, cells) }));
    const reserved = new Set(fields.flatMap((field) => [field.labelIndex, ...field.contextIndexes]).filter((index) => index >= 0));
    const usedLabels = new Set(fields.map((field) => String(field.label || "").replace(/:\s*$/, "").trim().toLowerCase()).filter(Boolean));
    let maxQuestionLine = -1;
    fields.forEach((field) => {
      const currentLine = Number(field.target?.line ?? maxQuestionLine);
      field.beforeFacts = cells
        .map((cell, index) => ({ cell, index }))
        .filter(({ cell, index }) => index !== field.targetIndex && !reserved.has(index) && cell.line > maxQuestionLine && cell.line < currentLine)
        .map(({ cell }) => cell.text.trim())
        .filter((text) => text && !/^(?:Example|Answer)$/i.test(text) && !usedLabels.has(text.replace(/:\s*$/, "").toLowerCase()));
      maxQuestionLine = Math.max(maxQuestionLine, currentLine);
    });
    return fields;
  }

  function normalizedPrompt(value) {
    return String(value || "")
      .replace(/【\s*】|\[\s*\]/g, "")
      .replace(/^[\s·•\-–—]+/, "")
      .replace(/[:：?？\s]+$/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function titleContainsLabel(question, label) {
    const title = normalizedPrompt(usefulTitle(question));
    const prompt = normalizedPrompt(label);
    return Boolean(title && prompt && (title.startsWith(prompt) || prompt.startsWith(title)));
  }

  function targetContainsLabel(field, label) {
    if (!field || !field.target) return false;
    const marker = `$${field.question && field.question.id}$`;
    const target = normalizedPrompt(
      targetSource(field).replace(marker, " ")
    );
    const prompt = normalizedPrompt(label);
    return Boolean(target && prompt && target.includes(prompt));
  }

  function flowFact(text) {
    const value = String(text || "").trim();
    if (!value) return "";
    const isBullet = /^[·•\-–—]/.test(value);
    const isSubheading = !isBullet && !/[:：?？]/.test(value) && value.length <= 64;
    const className = isSubheading ? "practice-form__subheading" : "practice-form__line";
    return `<div class="${className}">${escapeHtml(value)}</div>`;
  }

  function renderForm(group, renderControl, renderExtras) {
    const fields = formFields(group);
    const facts = staticFacts(group, fields);
    const hasPaperColumns = fields.some((field) => field.cells.some((cell) => cell.column === "right"));
    let activeSection = "";
    let activeSectionContext = "";
    const rows = fields.map((field) => {
      const number = escapeHtml(field.question.number);
      const id = escapeHtml(field.question.id || field.question.number);
      const control = renderControl(field.question, true);
      const labelCell = field.labelIndex >= 0 ? field.cells[field.labelIndex] : null;
      const isSectionLabel = Boolean(
        field.label &&
        labelCell &&
        field.labelIndex < field.targetIndex &&
        !/[:：]\s*$/.test(labelCell.text)
      );
      const sectionKey = isSectionLabel ? normalizedPrompt(field.label) : "";
      const contextKey = field.context.map(normalizedPrompt).join("|");
      let prelude = field.beforeFacts.map(flowFact).join("");
      if (isSectionLabel && sectionKey !== activeSection) {
        prelude += `<div class="practice-form__section">${escapeHtml(field.label)}</div>`;
        activeSection = sectionKey;
        activeSectionContext = "";
      }
      if (isSectionLabel && field.context.length && contextKey !== activeSectionContext) {
        prelude += field.context.map(flowFact).join("");
        activeSectionContext = contextKey;
      }
      const directLabel = !isSectionLabel && field.label && !/^q(?:uestion)?$/i.test(field.label.trim()) && !titleContainsLabel(field.question, field.label) && !targetContainsLabel(field, field.label)
        ? `<span class="practice-form__prompt">${escapeHtml(field.label)}:</span> `
        : "";
      const questionContent = usefulTitle(field.question)
        ? questionTemplate(field.question, control)
        : targetTemplate(field, control);
      return `
        ${prelude}
        <div class="practice-form__field practice-question-anchor" data-question-id="${id}" data-question-number="${number}">
          ${!isSectionLabel && field.context.length ? `<div class="practice-form__context">${field.context.map(escapeHtml).join(" · ")}</div>` : ""}
          <div class="practice-form__content">${directLabel}${questionContent}</div>
          ${typeof renderExtras === "function" ? renderExtras(field.question) : ""}
        </div>`;
    }).join("");
    const usedFacts = new Set(fields.flatMap((field) => [...field.beforeFacts, ...field.context]));
    const remainingFacts = facts.filter((fact) => !usedFacts.has(fact));
    const factHtml = remainingFacts.map(flowFact).join("");
    return `<div class="practice-form" data-renderer="form-completion" data-layout="${hasPaperColumns ? "columns" : "flow"}">${rows}${factHtml}</div>`;
  }

  function isFormGroup(group) {
    return Number(group && group.type) === 5 && Boolean(group && group.collect) && (group.questions || []).length > 0;
  }

  function isMatchingGroup(group) {
    const options = group && group.collect_option && group.collect_option.list;
    return Array.isArray(options) && options.length >= 3 && (
      Number(group && group.type) === 8 || (group.questions || []).length >= 3
    );
  }

  function isMapGroup(group) {
    return Boolean(group && (group.img_local || group.img_url)) && [6, 7].includes(Number(group.type));
  }

  function renderMatching(group, renderOptionBank, renderQuestion) {
    return `
      <div class="matching-workspace" data-renderer="matching">
        ${renderOptionBank(group)}
        <div class="matching-workspace__questions">
          ${(group.questions || []).map((question) => `
            <div class="matching-row practice-question-anchor" data-question-id="${escapeHtml(question.id || question.number)}" data-question-number="${escapeHtml(question.number)}">
              ${renderQuestion(question, group)}
            </div>`).join("")}
        </div>
      </div>`;
  }

  function renderMap(group, imageUrl, renderQuestion) {
    return `
      <div class="map-workspace" data-renderer="map">
        <div class="map-viewer" data-map-viewer>
          <div class="map-toolbar" aria-label="地图工具" data-capability="canUseMapZoom">
            <button type="button" data-map-action="zoom-in">放大</button>
            <button type="button" data-map-action="zoom-out">缩小</button>
            <button type="button" data-map-action="reset">重置</button>
            <button type="button" data-map-action="fullscreen">全屏查看</button>
          </div>
          <div class="map-canvas" data-map-canvas>
            <img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(group.title || group.question_title || "听力地图题")}" draggable="false">
          </div>
        </div>
        <div class="map-workspace__questions">
          ${(group.questions || []).map((question) => renderQuestion(question, group)).join("")}
        </div>
      </div>`;
  }

  function initMapViewers(doc = document, capabilities = { canUseMapZoom: true }) {
    if (!capabilities.canUseMapZoom) return;
    doc.querySelectorAll("[data-map-viewer]").forEach((viewer) => {
      if (viewer.dataset.mapReady === "1") return;
      viewer.dataset.mapReady = "1";
      const canvas = viewer.querySelector("[data-map-canvas]");
      const image = canvas && canvas.querySelector("img");
      if (!canvas || !image) return;
      let scale = 1;
      let x = 0;
      let y = 0;
      let pointer = null;
      let startX = 0;
      let startY = 0;

      function paint() {
        image.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
      }
      function reset() {
        scale = 1;
        x = 0;
        y = 0;
        paint();
      }
      viewer.addEventListener("click", (event) => {
        const action = event.target.closest("[data-map-action]")?.dataset.mapAction;
        if (!action) return;
        if (action === "zoom-in") scale = Math.min(3, scale + .25);
        if (action === "zoom-out") scale = Math.max(1, scale - .25);
        if (action === "reset") reset();
        if (action === "fullscreen") {
          if (doc.fullscreenElement) doc.exitFullscreen?.();
          else viewer.requestFullscreen?.();
        }
        paint();
      });
      canvas.addEventListener("pointerdown", (event) => {
        if (scale <= 1) return;
        pointer = event.pointerId;
        startX = event.clientX - x;
        startY = event.clientY - y;
        canvas.setPointerCapture?.(pointer);
        canvas.classList.add("is-dragging");
      });
      canvas.addEventListener("pointermove", (event) => {
        if (event.pointerId !== pointer) return;
        x = event.clientX - startX;
        y = event.clientY - startY;
        paint();
      });
      canvas.addEventListener("pointerup", (event) => {
        if (event.pointerId !== pointer) return;
        pointer = null;
        canvas.classList.remove("is-dragging");
      });
      canvas.addEventListener("wheel", (event) => {
        if (!event.ctrlKey && !event.metaKey) return;
        event.preventDefault();
        scale = Math.max(1, Math.min(3, scale + (event.deltaY < 0 ? .15 : -.15)));
        if (scale === 1) { x = 0; y = 0; }
        paint();
      }, { passive: false });
    });
  }

  function renderReviewCard(question, result, userAnswer) {
    const status = result && (result.status || (result.correct ? "correct" : "incorrect")) || "unanswered";
    const label = status === "correct" ? "✓ 正确" : status === "unanswered" ? "— 未作答" : "× 错误";
    const correctAnswer = result && result.answer !== undefined ? result.answer : question.answer;
    const analysis = result && result.analysis !== undefined ? result.analysis : question.analysis;
    return `
      <div class="review-card" data-review-question="${escapeHtml(question.id || question.number)}" data-capability="canShowCorrectness">
        <div class="review-card__status" data-status="${escapeHtml(status)}">结果：${label}</div>
        <div class="review-card__answers">
          <span><strong>你的答案</strong><br>${escapeHtml(userAnswer || "未作答")}</span>
          <span><strong>正确答案</strong><br>${escapeHtml(correctAnswer || "—")}</span>
        </div>
        ${analysis ? `<div class="review-card__analysis"><strong>解析</strong><br>${escapeHtml(analysis)}</div>` : ""}
      </div>`;
  }

  return {
    escapeHtml,
    fieldMeta,
    formFields,
    initMapViewers,
    isFormGroup,
    isMapGroup,
    isMatchingGroup,
    plainText,
    renderForm,
    renderMap,
    renderMatching,
    renderReviewCard,
    staticFacts,
    targetSource,
    visualCells
  };
}));
