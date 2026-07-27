"use strict";

(function exposeResponseQueue(root, factory) {
  const queue = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = queue;
  if (root) root.ToeflResponseQueue = queue;
})(typeof window === "undefined" ? globalThis : window, () => {
  async function flushResponseSaves({ pendingEntries = [], inFlightEntries = [], save }) {
    const pendingPromises = pendingEntries.map(([questionId, value]) =>
      Promise.resolve().then(() => save(questionId, value))
    );
    const inFlightPromises = inFlightEntries.map((entry) => entry.promise);
    const results = await Promise.allSettled([
      ...pendingPromises,
      ...inFlightPromises,
    ]);
    const retry = new Map();
    pendingEntries.forEach(([questionId, value], index) => {
      if (results[index].status === "rejected") retry.set(questionId, value);
    });
    inFlightEntries.forEach((entry, index) => {
      if (results[pendingPromises.length + index].status === "rejected") {
        retry.set(entry.questionId, entry.value);
      }
    });
    return {
      ok: !results.some((result) => result.status === "rejected"),
      results,
      retry,
    };
  }

  return { flushResponseSaves };
});
