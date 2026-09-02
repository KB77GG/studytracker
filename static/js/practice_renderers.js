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

  function isPureLabelCell(cell) {
    if (!cell || !cell.labels.length) return false;
    const residual = cell.raw
      .replace(/\[\[LABEL:[^\]]+\]\]/g, "")
      .replace(/[\s·•\-–—]+/g, "");
    return !residual;
  }

  function isDecoratedLabelCell(cell) {
    return isPureLabelCell(cell) && /^[\s·•\-–—]+\[\[LABEL:/.test(cell.raw);
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
          if (candidate.column !== target.column || !isPureLabelCell(candidate)) continue;
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

  function sharedStemKey(question) {
    const title = String(question && question.title || "").trim();
    const blankCount = (title.match(/【\s*】|\[\s*\]/g) || []).length;
    return blankCount > 1 ? title.replace(/\s+/g, " ") : "";
  }

  function sharedFormClusters(fields) {
    const clusters = [];
    for (let start = 0; start < (fields || []).length;) {
      const key = sharedStemKey(fields[start].question);
      let end = start + 1;
      while (key && end < fields.length && sharedStemKey(fields[end].question) === key) end += 1;
      const blankCount = key ? (key.match(/【\s*】|\[\s*\]/g) || []).length : 0;
      if (key && end - start > 1 && end - start === blankCount) {
        clusters.push({ startIndex: start, fields: fields.slice(start, end), key });
        start = end;
      } else {
        start += 1;
      }
    }
    return clusters;
  }

  function sharedQuestionTemplate(title, cluster, renderControl) {
    const parts = String(title || "").split(/【\s*】|\[\s*\]/g);
    const renderPart = (part, field) => {
      let cleanPart = part;
      const questionNumber = String(field && field.question && field.question.number || "").replace(/\D/g, "");
      if (questionNumber) cleanPart = cleanPart.replace(new RegExp(`\\s+${questionNumber}\\s*$`), "");
      const anchor = field ? `<span class="practice-form__shared-anchor practice-question-anchor" data-question-id="${escapeHtml(field.question.id || field.question.number)}" data-question-number="${escapeHtml(field.question.number)}">${renderControl(field.question, true)}</span>` : "";
      return `${escapeHtml(cleanPart)}${anchor}`;
    };
    const sourceGroups = [];
    let groupStart = 0;
    for (let index = 1; index <= cluster.length; index += 1) {
      const previous = cluster[index - 1];
      const next = cluster[index];
      const changedSourceCell = index === cluster.length || previous.targetIndex < 0 || next.targetIndex < 0 || previous.targetIndex !== next.targetIndex;
      if (!changedSourceCell) continue;

      let groupContent = "";
      for (let partIndex = groupStart; partIndex < index; partIndex += 1) {
        groupContent += renderPart(parts[partIndex], cluster[partIndex]);
      }
      // The text after the last marker belongs to the next source cell when
      // the marker groups are split across cells. Keep it with that next
      // group, and append it only once at the end of the final group.
      if (index === cluster.length) groupContent += escapeHtml(parts[index] || "");
      sourceGroups.push(`<div class="practice-form__shared-source">${groupContent}</div>`);
      groupStart = index;
    }
    return {
      content: sourceGroups.join(""),
      sourceGroupCount: sourceGroups.length,
      extras: cluster.map((field) => field.question).filter(Boolean)
    };
  }

  function duplicateQuestionPrefixIndexes(fields) {
    const duplicateIndexes = new Set();
    (fields || []).forEach((field) => {
      const questionTitle = usefulTitle(field && field.question);
      const prompt = normalizedPrompt(questionTitle);
      if (!prompt || !field || !field.target) return;

      targetPrefixIndexes(field).forEach((index) => {
        const fact = field.cells[index] && field.cells[index].text;
        if (/^[·•\-–—]/.test(String(fact || "").trim())) return;
        const normalizedFact = normalizedPrompt(fact);
        if (!normalizedFact) return;
        // A paper form may split one question across left/right cells while
        // the normalized item title already contains the complete stem. In
        // that case the left cell is not a separate fact; rendering it again
        // (usually after the final field) duplicates the question prompt.
        if (
          prompt === normalizedFact ||
          prompt.startsWith(`${normalizedFact} `) ||
          prompt.startsWith(`${normalizedFact}:`)
        ) {
          duplicateIndexes.add(index);
        }
      });
    });
    return duplicateIndexes;
  }

  function staticFactEntries(group, fields) {
    const normalizeLabel = (value) => String(value || "").replace(/:\s*$/, "").trim().toLowerCase();
    const usedLabels = new Set(fields.map((field) => normalizeLabel(field.label)).filter(Boolean));
    const questionMarkers = new Set((group.questions || []).map((question) => `$${question.id}$`));
    const promptCellIndexes = new Set(
      fields.filter((field) => !usefulTitle(field.question)).flatMap(targetPrefixIndexes)
    );
    const duplicateIndexes = duplicateQuestionPrefixIndexes(fields);
    const facts = [];
    visualCells(group.collect || "").forEach((cell, index) => {
      if (duplicateIndexes.has(index)) return;
      if (promptCellIndexes.has(index)) return;
      if (Array.from(questionMarkers).some((marker) => cell.raw.includes(marker))) return;
      let text = cell.text.replace(/\[\[LABEL:([^\]]+)\]\]/g, "$1").trim();
      if (!text || /^[-–—]+$/.test(text) || /^(?:Example|Answer)$/i.test(text)) return;
      if (usedLabels.has(normalizeLabel(text)) || /:\s*$/.test(text)) return;
      if (text.length > 150) return;
      facts.push({ index, text });
    });
    return facts;
  }

  function staticFacts(group, fields) {
    return staticFactEntries(group, fields).map(({ text }) => text);
  }

  function formFields(group) {
    const cells = visualCells(group.collect || "");
    const fields = (group.questions || [])
      .slice()
      .sort((left, right) => Number(left.number || 0) - Number(right.number || 0))
      .map((question) => ({ question, ...fieldMeta(group, question, cells) }));
    const duplicateIndexes = duplicateQuestionPrefixIndexes(fields);
    fields.forEach((field) => {
      const duplicateContextIndexes = field.contextIndexes.filter((index) => duplicateIndexes.has(index));
      if (!duplicateContextIndexes.length) return;
      const isFallbackContext = field.labelIndex >= 0 && field.contextIndexes.every((index) => index < field.labelIndex);
      if (isFallbackContext) {
        // If a later section inherits a source fragment that is already part
        // of an earlier titled question, release the whole fallback context.
        // The section heading then returns to its source position via
        // beforeFacts instead of being rendered after that question.
        field.contextIndexes = [];
        field.context = [];
        return;
      }
      field.contextIndexes = field.contextIndexes.filter((index) => !duplicateIndexes.has(index));
      field.context = field.contextIndexes.map((index) => cells[index].text).filter(Boolean);
    });
    const reserved = new Set(fields.flatMap((field) => [field.labelIndex, ...field.contextIndexes]).filter((index) => index >= 0));
    const usedLabels = new Set(fields.map((field) => String(field.label || "").replace(/:\s*$/, "").trim().toLowerCase()).filter(Boolean));
    let maxQuestionLine = -1;
    fields.forEach((field) => {
      const currentLine = Number(field.target?.line ?? maxQuestionLine);
      const beforeFacts = cells
        .map((cell, index) => ({ cell, index }))
        .filter(({ cell, index }) => index !== field.targetIndex && !reserved.has(index) && cell.line > maxQuestionLine && cell.line < currentLine)
        .filter(({ cell }) => {
          const text = cell.text.trim();
          return text && !/^(?:Example|Answer)$/i.test(text) && !usedLabels.has(text.replace(/:\s*$/, "").toLowerCase());
        });
      field.beforeFactIndexes = beforeFacts.map(({ index }) => index);
      field.beforeFacts = beforeFacts.map(({ cell }) => cell.text.trim());
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

  function directLabelText(field, isSectionLabel) {
    if (
      isSectionLabel ||
      !field ||
      !field.label ||
      /^q(?:uestion)?$/i.test(field.label.trim()) ||
      titleContainsLabel(field.question, field.label) ||
      targetContainsLabel(field, field.label)
    ) return "";
    return field.label;
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
    const facts = staticFactEntries(group, fields);
    const duplicateIndexes = duplicateQuestionPrefixIndexes(fields);
    const sharedClusters = new Map(sharedFormClusters(fields).map((cluster) => [cluster.startIndex, cluster]));
    const hasPaperColumns = fields.some((field) => field.cells.some((cell) => cell.column === "right"));
    let activeSection = "";
    const emittedSourceIndexes = new Set();
    const claimSourceIndex = (index) => {
      if (index < 0) return true;
      if (emittedSourceIndexes.has(index)) return false;
      emittedSourceIndexes.add(index);
      return true;
    };
    const renderPrelude = (field, sharedPrompt = "") => {
      const labelCell = field.labelIndex >= 0 ? field.cells[field.labelIndex] : null;
      const isSectionLabel = Boolean(
        field.label &&
        labelCell &&
        field.labelIndex < field.targetIndex &&
        (!/[:：]\s*$/.test(labelCell.text) || isDecoratedLabelCell(labelCell))
      );
      const sectionKey = isSectionLabel ? normalizedPrompt(field.label) : "";
      const contextEntries = field.context
        .map((text, index) => ({ index: field.contextIndexes[index], text }))
        .filter(({ index }) => !duplicateIndexes.has(index));
      const beforeEntries = field.beforeFacts
        .map((text, index) => ({ index: field.beforeFactIndexes[index], text }))
        .filter(({ index }) => !duplicateIndexes.has(index));
      const visibleBeforeEntries = beforeEntries.filter((entry) => {
        if (sharedPrompt && sharedPrompt.includes(normalizedPrompt(entry.text))) {
          claimSourceIndex(entry.index);
          return false;
        }
        return claimSourceIndex(entry.index);
      });
      let prelude = visibleBeforeEntries.map((entry) => flowFact(entry.text)).join("");
      if (isSectionLabel && sectionKey !== activeSection) {
        if (sharedPrompt && sharedPrompt.includes(sectionKey)) {
          claimSourceIndex(field.labelIndex);
        } else if (claimSourceIndex(field.labelIndex)) {
          prelude += `<div class="practice-form__section">${escapeHtml(field.label)}</div>`;
        }
        activeSection = sectionKey;
      }
      const visibleContextEntries = contextEntries.filter((entry) => {
        if (sharedPrompt && sharedPrompt.includes(normalizedPrompt(entry.text))) {
          claimSourceIndex(entry.index);
          return false;
        }
        return entry.index < 0 || !emittedSourceIndexes.has(entry.index);
      });
      if (isSectionLabel && visibleContextEntries.length) {
        prelude += visibleContextEntries
          .filter((entry) => claimSourceIndex(entry.index))
          .map((entry) => flowFact(entry.text))
          .join("");
      }
      return { prelude, isSectionLabel, contextEntries: visibleContextEntries };
    };
    const renderField = (field) => {
      const number = escapeHtml(field.question.number);
      const id = escapeHtml(field.question.id || field.question.number);
      const control = renderControl(field.question, true);
      const { prelude, isSectionLabel, contextEntries } = renderPrelude(field);
      const context = contextEntries.filter((entry) => claimSourceIndex(entry.index)).map(({ text }) => text);
      const directLabelTextValue = directLabelText(field, isSectionLabel);
      const directLabel = directLabelTextValue && claimSourceIndex(field.labelIndex)
        ? `<span class="practice-form__prompt">${escapeHtml(directLabelTextValue)}:</span> `
        : "";
      if (!directLabelTextValue && !isSectionLabel && field.labelIndex >= 0) claimSourceIndex(field.labelIndex);
      const questionContent = usefulTitle(field.question)
        ? questionTemplate(field.question, control)
        : targetTemplate(field, control);
      return `
        ${prelude}
        <div class="practice-form__field practice-question-anchor" data-question-id="${id}" data-question-number="${number}">
          ${!isSectionLabel && context.length ? `<div class="practice-form__context">${context.map(escapeHtml).join(" · ")}</div>` : ""}
          <div class="practice-form__content">${directLabel}${questionContent}</div>
          ${typeof renderExtras === "function" ? renderExtras(field.question) : ""}
        </div>`;
    };
    const renderSharedCluster = (cluster) => {
      const first = cluster.fields[0];
      const sharedPrompt = normalizedPrompt(first.question.title);
      const preludes = [];
      const contextEntries = [];
      const directLabels = [];
      const directLabelKeys = new Set();
      cluster.fields.forEach((field) => {
        const result = renderPrelude(field, sharedPrompt);
        preludes.push(result.prelude);
        if (!result.isSectionLabel) contextEntries.push(...result.contextEntries);
        const labelText = directLabelText(field, result.isSectionLabel);
        if (labelText && claimSourceIndex(field.labelIndex)) {
          const key = normalizedPrompt(labelText);
          if (!directLabelKeys.has(key)) {
            directLabelKeys.add(key);
            directLabels.push(labelText);
          }
        } else if (!labelText && !result.isSectionLabel && field.labelIndex >= 0) {
          claimSourceIndex(field.labelIndex);
        }
      });
      const context = contextEntries
        .filter((entry) => claimSourceIndex(entry.index))
        .map(({ text }) => text);
      const shared = sharedQuestionTemplate(first.question.title, cluster.fields, renderControl);
      const directLabelHtml = directLabels
        .map((label) => `<span class="practice-form__prompt">${escapeHtml(label)}:</span> `)
        .join("");
      const extras = typeof renderExtras === "function"
        ? shared.extras.map((question) => renderExtras(question)).join("")
        : "";
      return `
        ${preludes.join("")}
        <div class="practice-form__field practice-form__shared-field" data-shared-question-count="${cluster.fields.length}" data-shared-source-group-count="${shared.sourceGroupCount}">
          ${context.length ? `<div class="practice-form__context">${context.map(escapeHtml).join(" · ")}</div>` : ""}
          <div class="practice-form__content">${directLabelHtml}${shared.content}</div>
          ${extras}
        </div>`;
    };
    const rows = [];
    for (let index = 0; index < fields.length;) {
      const cluster = sharedClusters.get(index);
      if (cluster) {
        rows.push(renderSharedCluster(cluster));
        index += cluster.fields.length;
      } else {
        rows.push(renderField(fields[index]));
        index += 1;
      }
    }
    const factHtml = facts
      .filter((entry) => claimSourceIndex(entry.index))
      .map((entry) => flowFact(entry.text))
      .join("");
    return `<div class="practice-form" data-renderer="form-completion" data-layout="${hasPaperColumns ? "columns" : "flow"}">${rows.join("")}${factHtml}</div>`;
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
    sharedFormClusters,
    staticFacts,
    targetSource,
    visualCells
  };
}));
