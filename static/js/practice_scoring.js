(function initPracticeScoring(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.PracticeScoring = api;
})(typeof window !== "undefined" ? window : globalThis, function createPracticeScoring() {
  const judgmentAliases = {
    Y: "YES",
    YES: "YES",
    N: "NO",
    NO: "NO",
    NG: "NOT GIVEN",
    NOTGIVEN: "NOT GIVEN",
    "NOT GIVEN": "NOT GIVEN",
    T: "TRUE",
    TRUE: "TRUE",
    F: "FALSE",
    FALSE: "FALSE"
  };
  const fullJudgments = new Set(["YES", "NO", "NOT GIVEN", "TRUE", "FALSE"]);
  const shortJudgments = new Set(["Y", "N", "NG", "T", "F"]);

  function normalizeText(value) {
    return String(value || "")
      .trim()
      .toLowerCase()
      .replace(/[‘’]/g, "'")
      .replace(/[“”]/g, '"')
      .replace(/[：]/g, ":")
      .replace(/[.,!?;:，。！？；：]/g, "")
      .replace(/\s+/g, " ");
  }

  function splitAlternatives(answer) {
    return String(answer || "")
      .split(/\s*\/\s*/)
      .map(normalizeText)
      .filter(Boolean);
  }

  function splitLetters(value) {
    return [...new Set(String(value || "")
      .toUpperCase()
      .split(/[\s,\/]+/)
      .map((item) => item.trim())
      .filter(Boolean))];
  }

  function isLetterAnswer(value) {
    const parts = splitLetters(value);
    return Boolean(parts.length) && parts.every((item) => /^[A-Z]$/.test(item));
  }

  function statusFor(awarded, marks, overLimit = false) {
    if (awarded === marks) return "correct";
    if (awarded > 0) return "partial";
    return "incorrect";
  }

  function statusLabel(status, awarded, marks, overLimit = false) {
    if (status === "correct") return `✓ 选择正确 ${awarded}/${marks}`;
    if (status === "partial") return `部分正确 ${awarded}/${marks}`;
    if (overLimit) return `✕ 超出最多选择 ${marks} 项，0/${marks}`;
    return `✕ 选择错误 0/${marks}`;
  }

  function optionKey(option) {
    return String(option?.key || option?.title || "").trim().toUpperCase();
  }

  function optionStates(options, expected, submitted) {
    const expectedSet = new Set(expected);
    const submittedSet = new Set(submitted);
    return (options || []).map((option) => {
      const key = optionKey(option);
      let status;
      let label;
      if (submittedSet.has(key) && expectedSet.has(key)) {
        status = "selected_correct";
        label = "选择正确";
      } else if (submittedSet.has(key)) {
        status = "selected_wrong";
        label = "选择错误";
      } else if (expectedSet.has(key)) {
        status = "missed_correct";
        label = "正确答案/漏选";
      } else {
        status = "unselected_wrong";
        label = "未选";
      }
      return { key, status, label };
    });
  }

  function feedback(answer, value, marks, awarded, options, expected, submitted, overLimit, kind) {
    const status = statusFor(awarded, marks, overLimit);
    return {
      marks,
      awarded,
      correct: status === "correct",
      status,
      status_label: statusLabel(status, awarded, marks, overLimit),
      option_states: optionStates(options, expected, submitted),
      max_selections: kind === "checkbox-set"
        ? marks
        : kind === "checkbox-exact" ? expected.length : null,
      selection_error: overLimit ? "too_many" : null
    };
  }

  function gradeAnswer(answer, value, config = {}) {
    const kind = config.kind || "question";
    const marks = Math.max(1, Number(config.marks || 1));
    const options = config.options || [];
    if (kind === "checkbox-set" || kind === "checkbox-exact") {
      const expected = splitLetters(answer);
      const submitted = splitLetters(value);
      if (kind === "checkbox-set") {
        const overLimit = submitted.length > marks;
        const matched = submitted.filter((item) => expected.includes(item)).length;
        const awarded = overLimit ? 0 : Math.min(marks, matched);
        return feedback(answer, value, marks, awarded, options, expected, submitted, overLimit, kind);
      }
      const exact = submitted.length === expected.length &&
        expected.every((item) => submitted.includes(item));
      return feedback(answer, value, marks, expected.length && exact ? marks : 0, options, expected, submitted, false, kind);
    }

    const expectedLetters = isLetterAnswer(answer) ? splitLetters(answer) : [];
    const submittedLetters = splitLetters(value);
    let isCorrect;
    if (expectedLetters.length) {
      if (kind === "radio" || submittedLetters.length <= 1) {
        isCorrect = expectedLetters.includes(String(value || "").trim().toUpperCase());
      } else if (submittedLetters.length > 1) {
        isCorrect = submittedLetters.length === expectedLetters.length &&
          expectedLetters.every((item) => submittedLetters.includes(item));
      } else {
        isCorrect = expectedLetters.includes(String(value || "").trim().toUpperCase());
      }
    } else {
      isCorrect = splitAlternatives(answer).includes(normalizeText(value));
    }
    return feedback(
      answer,
      value,
      marks,
      isCorrect ? marks : 0,
      options,
      expectedLetters,
      submittedLetters,
      false,
      kind
    );
  }

  function canonicalJudgment(value) {
    const normalized = String(value || "").trim().toUpperCase().replace(/[\s_-]+/g, " ");
    const compact = normalized.replace(/[\s_-]+/g, "");
    return judgmentAliases[normalized] || judgmentAliases[compact] || "";
  }

  function groupLooksLikeJudgment(group) {
    const text = `${group?.title || ""} ${group?.question_title || ""} ${group?.desc || ""}`.toUpperCase();
    return /\b(TRUE|FALSE|YES|NO|NOT\s+GIVEN)\s+IF\b/.test(text) ||
      /\bWRITE\s+(TRUE|FALSE|YES|NO|NOT\s+GIVEN)/.test(text) ||
      text.includes("DO THE FOLLOWING STATEMENTS AGREE") ||
      text.includes("STATEMENTS AGREE WITH") ||
      text.includes("CLAIMS OF THE WRITER") ||
      text.includes("VIEWS OF THE WRITER");
  }

  function judgmentAnswers(answer, group) {
    const groupUsesJudgment = groupLooksLikeJudgment(group || {});
    return [...new Set(String(answer || "")
      .split(/\s*\/\s*|\s+or\s+/i)
      .map((part) => {
        const normalized = part.trim().toUpperCase().replace(/[\s_-]+/g, " ");
        const compact = normalized.replace(/[\s_-]+/g, "");
        const isFull = fullJudgments.has(normalized) || compact === "NOTGIVEN";
        const isShort = shortJudgments.has(compact);
        return isFull || (isShort && groupUsesJudgment) ? canonicalJudgment(part) : "";
      })
      .filter(Boolean))];
  }

  function groupOptions(group) {
    return group?.collect_option?.list || group?.collect_options?.list || [];
  }

  function sharedReadingExpected(group) {
    const questions = group?.questions || [];
    if (questions.length < 2) return [];
    const first = String(questions[0]?.answer || "");
    if (!first.includes(",") || !isLetterAnswer(first)) return [];
    const expected = splitLetters(first);
    if (expected.length !== questions.length) return [];
    return questions.every((question) => String(question.answer || "") === first) ? expected : [];
  }

  function readingQuestionGrade(question, group, value) {
    const answer = question.answer || "";
    const options = question.options?.length ? question.options : groupOptions(group);
    const judgment = judgmentAnswers(answer, group);
    if (judgment.length) {
      const submitted = canonicalJudgment(value);
      return feedback(answer, value, 1, judgment.includes(submitted) ? 1 : 0, options, judgment, submitted ? [submitted] : [], false, "radio");
    }
    if (String(answer).includes(",") && isLetterAnswer(answer)) {
      return gradeAnswer(answer, value, { kind: "checkbox-exact", marks: 1, options });
    }
    if (isLetterAnswer(answer)) {
      return gradeAnswer(answer, value, { kind: "radio", marks: 1, options });
    }
    return gradeAnswer(answer, value, { kind: "question", marks: 1, options });
  }

  function gradeReadingTestAnswers(payload, answers, passageNumber = null) {
    const result = { correct: 0, total: 0, accuracy: 0, ielts_score: null, wrong_numbers: [], results: [] };
    const passages = payload?.passages || [];
    passages.forEach((passage, passageIndex) => {
      if (passageNumber && passageIndex !== Number(passageNumber) - 1) return;
      (passage.groups || []).forEach((group) => {
        const shared = sharedReadingExpected(group);
        const used = new Set();
        (group.questions || []).forEach((question) => {
          const id = String(question.id ?? question.number);
          const value = String(answers?.[id] || "");
          let graded;
          if (shared.length) {
            const submitted = splitLetters(value);
            const picked = submitted.length === 1 ? submitted[0] : "";
            const ok = shared.includes(picked) && !used.has(picked);
            if (ok) used.add(picked);
            graded = feedback(question.answer || "", value, 1, ok ? 1 : 0, question.options?.length ? question.options : groupOptions(group), ok ? [picked] : [], submitted, false, "radio");
          } else {
            graded = readingQuestionGrade(question, group, value);
          }
          const number = question.number;
          result.total += 1;
          result.correct += graded.awarded;
          if (graded.status !== "correct") result.wrong_numbers.push(number);
          result.results.push({
            ids: [id], numbers: [number], q: String(number || ""), answer: question.answer || "", value,
            ...graded, passage: passageIndex
          });
        });
      });
    });
    result.accuracy = result.total ? Math.round(result.correct / result.total * 1000) / 10 : 0;
    return result;
  }

  function limitSelection(unit, event) {
    const max = Number(unit?.dataset?.maxSelections || 0);
    if (!max || !event?.target?.checked) return true;
    const checked = unit.querySelectorAll("input[type=checkbox]:checked");
    if (checked.length <= max) return true;
    event.target.checked = false;
    return false;
  }

  return {
    normalizeText,
    splitAlternatives,
    splitLetters,
    isLetterAnswer,
    gradeAnswer,
    gradeReadingTestAnswers,
    limitSelection,
    optionStates
  };
});
