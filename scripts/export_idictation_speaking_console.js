// Paste this whole file into the Console on https://www.idictation.cn/main/book
// while logged in. It downloads one JSON file with all visible IELTS speaking
// Part 1 / Part 2 / Part 3 questions.
(async () => {
  const SECRET = "idictation_2024";
  const PAGE_SIZE = 100;
  const MAX_PAGES = 50;
  const SLEEP_MS = 300;
  const BASE_URL = "https://www.idictation.cn";
  const LIST_ENDPOINTS = {
    part1: "/api/study/kouyu-zhenti/v1/part1/list",
    part23: "/api/study/kouyu-zhenti/v1/part2/list",
  };
  const SHOW_ENDPOINT = (id) => `/api/study/kouyu-zhenti/v1/show/${id}`;

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const asObjectList = (value) => Array.isArray(value) ? value.filter((item) => item && typeof item === "object") : [];

  function cleanText(value) {
    let text = value == null ? "" : String(value);
    text = text
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/\s*(p|div|li|tr|h[1-6])\s*>/gi, "\n")
      .replace(/<[^>]+>/g, " ")
      .replace(/&nbsp;/g, " ")
      .replace(/&amp;/g, "&")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .replace(/\u00a0/g, " ")
      .replace(/\u200b/g, "")
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n[ \t]+/g, "\n")
      .replace(/[ \t]{2,}/g, " ")
      .replace(/\n{3,}/g, "\n\n");
    return text.trim();
  }

  function firstValue(item, keys) {
    for (const key of keys) {
      if (Object.prototype.hasOwnProperty.call(item, key) && item[key] !== null && item[key] !== "") {
        return item[key];
      }
    }
    return "";
  }

  function parseJsonish(value) {
    if (typeof value === "string") {
      try {
        return JSON.parse(value);
      } catch {
        return {};
      }
    }
    return value == null ? {} : value;
  }

  function randomNonce() {
    return Math.random().toString(36).slice(2, 12).padEnd(10, "0");
  }

  async function hmacSha256Hex(message) {
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(SECRET),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );
    const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(message));
    return Array.from(new Uint8Array(signature)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
  }

  async function signedBody(path, payload = {}) {
    const body = {};
    for (const [key, value] of Object.entries(payload || {})) {
      if (value !== undefined && value !== null) body[key] = value;
    }
    body.api_key = encodeURIComponent(path);
    body.timestamp = Math.floor(Date.now() / 1000);
    body.nonce = randomNonce();
    const canonical = Object.keys(body).sort().map((key) => {
      const value = typeof body[key] === "object" ? JSON.stringify(body[key]) : body[key];
      return `${key}=${value}`;
    }).join("&");
    body.sign = await hmacSha256Hex(canonical);
    return body;
  }

  async function postJson(path, payload = {}) {
    const response = await fetch(path, {
      method: "POST",
      credentials: "include",
      headers: {
        Accept: "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
      },
      body: JSON.stringify(await signedBody(path, payload)),
    });
    const text = await response.text();
    let decoded;
    try {
      decoded = JSON.parse(text);
    } catch {
      throw new Error(`Non-JSON response from ${path}: ${text.slice(0, 300)}`);
    }
    const status = decoded && decoded.status;
    const okStatuses = new Set([undefined, null, 0, "0", 1, "1", 200, "200", true]);
    if (!okStatuses.has(status)) {
      throw new Error(`${path} failed: ${decoded.message || decoded.msg || status}`);
    }
    return decoded;
  }

  function unwrapValues(response) {
    if (!response || typeof response !== "object") return response;
    for (const key of ["values", "data", "result"]) {
      if (Object.prototype.hasOwnProperty.call(response, key)) return response[key];
    }
    return response;
  }

  function findItems(value) {
    const parsed = parseJsonish(value);
    if (Array.isArray(parsed)) return asObjectList(parsed);
    if (!parsed || typeof parsed !== "object") return [];

    for (const key of ["list", "data", "rows", "records", "items", "values"]) {
      if (Object.prototype.hasOwnProperty.call(parsed, key)) {
        const items = findItems(parsed[key]);
        if (items.length) return items;
      }
    }

    const candidates = [];
    for (const nested of Object.values(parsed)) {
      if (Array.isArray(nested)) candidates.push(...asObjectList(nested));
    }
    return candidates;
  }

  function materialId(item) {
    return String(firstValue(item, [
      "oral_materials_id",
      "mkt_oral_materials_id",
      "materials_id",
      "material_id",
      "id",
    ]));
  }

  function normalizeMaterial(item, sourcePart) {
    return {
      material_id: materialId(item),
      source_part: sourcePart,
      part_type: firstValue(item, ["part_type", "type", "mkt_oral_materials_part_type"]),
      title: cleanText(firstValue(item, [
        "mkt_oral_materials_title",
        "title",
        "name",
        "topic_title",
        "mkt_topic_title",
      ])),
      updated_at: firstValue(item, ["updated_at", "update_time", "mtime", "created_at"]),
    };
  }

  function extractTopic(response) {
    const value = parseJsonish(unwrapValues(response));
    if (value && typeof value === "object" && value.topic && typeof value.topic === "object") {
      return value.topic;
    }
    return value && typeof value === "object" ? value : {};
  }

  function normalizeIssue(raw, part, material) {
    const answerIdeas = parseJsonish(raw.answer_ideas);
    let prompt = cleanText(firstValue(raw, [
      "mkt_topic_issues_title",
      "question_title",
      "topic_problem",
      "problem_prompt",
      "title",
    ]));
    if (!prompt && answerIdeas && typeof answerIdeas === "object") {
      prompt = cleanText(answerIdeas.question);
    }
    return {
      material_id: material.material_id,
      material_title: material.title,
      part,
      issue_id: firstValue(raw, ["topic_issues_id", "id", "issue_id"]),
      question: prompt,
      updated_at: firstValue(raw, ["updated_at", "update_time", "created_at"]) || material.updated_at || "",
      suggested_time: firstValue(raw, ["mkt_topic_issues_time", "prompt_effective_time"]),
    };
  }

  function extractIssues(topic, material) {
    const detail = parseJsonish(topic.detail_text);
    const rows = [];
    if (detail && typeof detail === "object") {
      const listPart = material.source_part === "part23" ? "Part 3" : "Part 1";
      const part2Ids = new Set(asObjectList(detail.tIssuesPart2).map((raw) => String(raw.topic_issues_id || raw.id || "")));
      for (const raw of asObjectList(detail.mktTopicIssuesList)) {
        const rawId = String(raw.topic_issues_id || raw.id || "");
        if (material.source_part === "part23" && (part2Ids.has(rawId) || String(raw.topic_problem || "") === "1")) {
          continue;
        }
        rows.push(normalizeIssue(raw, listPart, material));
      }
      for (const raw of asObjectList(detail.tIssuesPart2)) {
        rows.push(normalizeIssue(raw, "Part 2", material));
      }
    }

    if (!rows.length) {
      const partType = String(topic.part_type || material.part_type || "");
      const fallbackPart = { 1: "Part 1", 2: "Part 2", 3: "Part 3" }[partType] || material.source_part;
      for (const raw of asObjectList(topic.topic_issues)) {
        rows.push(normalizeIssue(raw, fallbackPart, material));
      }
    }
    return rows;
  }

  function dedupe(rows) {
    const seen = new Set();
    const out = [];
    for (const row of rows) {
      const key = [row.material_id, row.part, row.issue_id, row.question].join("\u0001");
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(row);
    }
    return out;
  }

  function stripNumber(text) {
    return cleanText(text).replace(/^\d+\s*[.)、]\s*/, "").trim();
  }

  function organize(questions, materials) {
    const order = new Map(materials.map((material, index) => [String(material.material_id), index]));
    const rows = [...questions].sort((a, b) => {
      const orderA = order.has(String(a.material_id)) ? order.get(String(a.material_id)) : 100000;
      const orderB = order.has(String(b.material_id)) ? order.get(String(b.material_id)) : 100000;
      return orderA - orderB || String(a.part).localeCompare(String(b.part)) || Number(a.issue_id || 0) - Number(b.issue_id || 0);
    });

    const part1 = new Map();
    const part23 = new Map();
    const flat = [];
    for (const row of rows) {
      const date = cleanText(row.suggested_time || row.updated_at);
      const question = row.part === "Part 2" ? cleanText(row.question) : stripNumber(row.question);
      const flatRow = {
        material_id: String(row.material_id),
        topic: cleanText(row.material_title),
        part: cleanText(row.part),
        issue_id: String(row.issue_id || ""),
        question,
        source_date: date,
      };
      flat.push(flatRow);

      if (row.part === "Part 1") {
        if (!part1.has(flatRow.material_id)) {
          part1.set(flatRow.material_id, {
            material_id: flatRow.material_id,
            topic: flatRow.topic,
            source_date: date,
            questions: [],
          });
        }
        const topic = part1.get(flatRow.material_id);
        if (date > topic.source_date) topic.source_date = date;
        topic.questions.push({ issue_id: flatRow.issue_id, question, source_date: date });
      } else {
        if (!part23.has(flatRow.material_id)) {
          part23.set(flatRow.material_id, {
            material_id: flatRow.material_id,
            topic: flatRow.topic,
            source_date: date,
            part2: null,
            part3: [],
          });
        }
        const topic = part23.get(flatRow.material_id);
        if (date > topic.source_date) topic.source_date = date;
        if (row.part === "Part 2") {
          topic.part2 = { issue_id: flatRow.issue_id, card: cleanText(row.question), source_date: date };
        } else if (row.part === "Part 3") {
          topic.part3.push({ issue_id: flatRow.issue_id, question, source_date: date });
        }
      }
    }
    return { part1: Array.from(part1.values()), part23: Array.from(part23.values()), flat };
  }

  function downloadJson(filename, payload) {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function timestampForFilename() {
    const pad = (value) => String(value).padStart(2, "0");
    const now = new Date();
    return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  }

  if (!location.hostname.includes("idictation.cn")) {
    throw new Error("请先打开并登录 https://www.idictation.cn/main/book，再在这个页面的 Console 运行。");
  }

  console.log("[speaking export] fetching lists...");
  const materialsById = new Map();
  const rawLists = {};
  for (const [sourcePart, endpoint] of Object.entries(LIST_ENDPOINTS)) {
    rawLists[sourcePart] = [];
    for (let page = 1; page <= MAX_PAGES; page += 1) {
      const payload = {
        page,
        page_no: page,
        pageNum: page,
        page_size: PAGE_SIZE,
        pageSize: PAGE_SIZE,
        limit: PAGE_SIZE,
      };
      console.log(`[speaking export] ${sourcePart} list page ${page}`);
      const response = await postJson(endpoint, payload);
      rawLists[sourcePart].push({ payload, response });
      const items = findItems(unwrapValues(response));
      for (const item of items) {
        const material = normalizeMaterial(item, sourcePart);
        if (material.material_id && !materialsById.has(material.material_id)) {
          materialsById.set(material.material_id, material);
        }
      }
      if (!items.length || items.length < PAGE_SIZE) break;
      await sleep(SLEEP_MS);
    }
  }

  const materials = Array.from(materialsById.values()).sort((a, b) => {
    const sourceCompare = String(a.source_part).localeCompare(String(b.source_part));
    return sourceCompare || Number(a.material_id) - Number(b.material_id);
  });

  const rawDetails = {};
  let questions = [];
  for (let index = 0; index < materials.length; index += 1) {
    const material = materials[index];
    console.log(`[speaking export] detail ${index + 1}/${materials.length}: ${material.material_id} ${material.title}`);
    const response = await postJson(SHOW_ENDPOINT(material.material_id), {});
    rawDetails[material.material_id] = response;
    const topic = extractTopic(response);
    questions.push(...extractIssues(topic, material));
    await sleep(SLEEP_MS);
  }

  questions = dedupe(questions);
  const organized = organize(questions, materials);
  const sourceDates = organized.flat.map((row) => row.source_date).filter(Boolean).sort();
  const exportPayload = {
    source: "idictation_speaking",
    exported_at: new Date().toISOString(),
    page_url: location.href,
    latest_source_date: sourceDates[sourceDates.length - 1] || "",
    counts: {
      materials: materials.length,
      part1_topics: organized.part1.length,
      part23_topics: organized.part23.length,
      part1_questions: organized.part1.reduce((sum, topic) => sum + topic.questions.length, 0),
      part2_cards: organized.part23.filter((topic) => topic.part2).length,
      part3_questions: organized.part23.reduce((sum, topic) => sum + topic.part3.length, 0),
      total_items: organized.flat.length,
    },
    materials,
    questions: organized.flat,
    part1: organized.part1,
    part23: organized.part23,
    raw: {
      lists: rawLists,
      details: rawDetails,
    },
  };

  const filename = `idictation_speaking_export_${timestampForFilename()}.json`;
  downloadJson(filename, exportPayload);
  console.log(`[speaking export] done: ${filename}`, exportPayload.counts);
})().catch((error) => {
  console.error("[speaking export] failed", error);
});
