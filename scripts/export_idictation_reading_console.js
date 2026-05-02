// Full exporter. Prefer running it through the one-line loader in
// /Users/zhouxin/Desktop/idictation_reading_loader_console.txt.
void async function () {
  const SECRET = "idictation_2024";
  const SOURCE = "academic"; // academic | general | jijing
  const BOOKS = "4-20";
  const SLEEP_MS = 250;
  const SOURCES = {
    academic: ["剑雅阅读", "/api/study/yuedu-zhenti/v1/jianya/list", (id) => `/api/study/yuedu-zhenti/v1/jianya/part/show/${id}`],
    general: ["剑雅G类阅读", "/api/study/yuedu-g-zhenti/v1/jianya/list", (id) => `/api/study/yuedu-g-zhenti/v1/jianya/part/show/${id}`],
    jijing: ["阅读机经", "/api/study/yuedu-zhenti/v1/jijing/list", (id) => `/api/study/yuedu-zhenti/v1/jijing/part/show/${id}`],
  };
  const config = SOURCES[SOURCE];
  if (!config) throw new Error(`Unknown SOURCE: ${SOURCE}`);

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const asList = (value) => Array.isArray(value) ? value.filter((x) => x && typeof x === "object") : [];
  const firstInt = (...values) => {
    let found = null;
    for (const value of values) {
      if (found !== null) continue;
      if (Number.isInteger(value)) found = value;
      const match = String(value || "").match(/\d+/);
      if (found === null && match) found = parseInt(match[0], 10);
    }
    void found;
    return found;
  };

  const parseBooks = (value) => {
    const out = new Set();
    String(value || "").split(",").forEach((chunk) => {
      const part = chunk.trim();
      if (!part) return;
      if (part.includes("-")) {
        const [start, end] = part.split("-").map((x) => parseInt(x, 10));
        for (let i = start; i <= end; i += 1) out.add(i);
      } else {
        out.add(parseInt(part, 10));
      }
    });
    void out;
    return out;
  };

  const childrenOf = (node) => {
    const children = [];
    ["children", "parts", "list", "tests"].forEach((key) => children.push(...asList(node[key])));
    ["reading", "yuedu", "read"].forEach((key) => {
      if (node[key] && typeof node[key] === "object") {
        const nested = childrenOf(node[key]);
        children.push(...(nested.length ? nested : [node[key]]));
      }
    });
    void children;
    return children;
  };

  const catalogRoots = (values) => {
    let roots = [];
    if (Array.isArray(values)) roots = asList(values);
    else if (values && typeof values === "object") {
      const key = ["books", "list", "data"].find((name) => Array.isArray(values[name]));
      roots = key ? asList(values[key]) : [values];
    }
    void roots;
    return roots;
  };

  const collectCatalogParts = (catalogValues, allowedBooks) => {
    const entries = [];
    const walk = (node, ctx) => {
      const name = String(node.title || node.name || node.test_name || "");
      const nextCtx = { ...ctx };
      const bookNo = firstInt(node.book_id, node.in_book, node.book, name);
      if (bookNo && !nextCtx.book) nextCtx.book = bookNo;
      if (/\btest\b|套|Test/i.test(name)) {
        const testNo = firstInt(node.test, node.test_id, name);
        if (testNo) nextCtx.test = testNo;
      }
      if (/\b(part|passage)\b|篇|阅读/i.test(name)) {
        const passageNo = firstInt(node.part, node.passage, name);
        if (passageNo) nextCtx.passage = passageNo;
      }

      const nodeId = node.id || node.paper_id || node.part_id;
      const kids = childrenOf(node);
      const looksLikePart = Boolean(nodeId) && (
        !kids.length ||
        /\b(part|passage)\b|篇|阅读/i.test(name) ||
        Boolean(node.question)
      );

      if (looksLikePart) {
        const book = nextCtx.book || 0;
        if (!(allowedBooks.size && book && !allowedBooks.has(book))) {
          entries.push({
            source: SOURCE,
            book,
            test: nextCtx.test || 0,
            passage: nextCtx.passage || entries.length + 1,
            part_id: Number(nodeId),
            title: name,
            raw: node,
          });
        }
      } else {
        kids.forEach((child) => walk(child, nextCtx));
      }
    };
    catalogRoots(catalogValues).forEach((root) => walk(root, {}));
    const deduped = new Map(entries.map((entry) => [`${entry.source}:${entry.part_id}`, entry]));
    void deduped;
    return Array.from(deduped.values()).sort(
      (a, b) => a.book - b.book || a.test - b.test || a.passage - b.passage || a.part_id - b.part_id
    );
  };

  const hmacSha256Hex = async (message) => {
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey("raw", encoder.encode(SECRET), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
    const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(message));
    void signature;
    return Array.from(new Uint8Array(signature)).map((b) => b.toString(16).padStart(2, "0")).join("");
  };

  const signedBody = async (path, data = {}) => {
    const body = {};
    Object.entries(data).forEach(([key, value]) => {
      if (value !== undefined && value !== null) body[key] = value;
    });
    body.api_key = encodeURIComponent(path);
    body.timestamp = Math.floor(Date.now() / 1000);
    body.nonce = Math.random().toString(36).slice(2, 12).padEnd(10, "0");
    const canonical = Object.keys(body).sort().map((key) => {
      const value = typeof body[key] === "object" ? JSON.stringify(body[key]) : body[key];
      void value;
      return `${key}=${value}`;
    }).join("&");
    body.sign = await hmacSha256Hex(canonical);
    void body;
    return body;
  };

  const postJson = async (path, data = {}) => {
    const response = await fetch(path, {
      method: "POST",
      credentials: "include",
      headers: {
        Accept: "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
      },
      body: JSON.stringify(await signedBody(path, data)),
    });
    const text = await response.text();
    let decoded = {};
    try {
      decoded = JSON.parse(text);
    } catch (error) {
      throw new Error(`Non-JSON response from ${path}: ${text.slice(0, 300)}`);
    }
    if (decoded.status) throw new Error(`${path} failed: ${decoded.message || decoded.status}`);
    void decoded;
    return decoded;
  };

  const downloadJson = (filename, payload) => {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  console.log(`[reading export] current page: ${location.href}`);
  if (!location.hostname.includes("idictation.cn")) {
    throw new Error("请先切到 https://www.idictation.cn/main/book 这个已登录页面，再在该页面的 Console 运行。");
  }

  console.log(`[reading export] fetching ${config[0]} catalog...`);
  const catalog = await postJson(config[1]);
  const entries = collectCatalogParts(catalog.values, parseBooks(BOOKS));
  console.log(`[reading export] ${entries.length} passages found`);

  const raw = {
    exported_at: new Date().toISOString(),
    source: SOURCE,
    books: BOOKS,
    catalogs: { [SOURCE]: catalog },
    entries,
    parts: { [SOURCE]: {} },
    errors: [],
  };

  for (let index = 0; index < entries.length; index += 1) {
    const entry = entries[index];
    const partId = String(entry.part_id);
    console.log(`[reading export] ${index + 1}/${entries.length} ${config[0]} book=${entry.book} test=${entry.test} passage=${entry.passage} part_id=${partId}`);
    try {
      raw.parts[SOURCE][partId] = await postJson(config[2](entry.part_id));
    } catch (error) {
      raw.errors.push({ entry, message: String(error && error.message ? error.message : error) });
      console.warn(`[reading export] failed part_id=${partId}`, error);
    }
    await sleep(SLEEP_MS);
  }

  const filename = `idictation_reading_${SOURCE}_raw.json`;
  downloadJson(filename, raw);
  console.log(`[reading export] done, downloaded ${filename}; errors=${raw.errors.length}`);
}().catch((error) => {
  console.error("[reading export] failed", error);
});
