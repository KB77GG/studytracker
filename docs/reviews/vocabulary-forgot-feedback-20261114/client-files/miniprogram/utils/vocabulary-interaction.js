function text(value) {
    return value === undefined || value === null ? '' : String(value).trim()
}

function stableHash(value) {
    let hash = 2166136261
    const source = String(value || '')
    for (let index = 0; index < source.length; index += 1) {
        hash ^= source.charCodeAt(index)
        hash = Math.imul(hash, 16777619)
    }
    return hash >>> 0
}

function buildMeaningChoiceOptions(question, familiarity) {
    question = question || {}
    const snapshot = question.question || {}
    const serverOptions = Array.isArray(snapshot.options) ? snapshot.options : []
    const candidates = []
    const seen = Object.create(null)

    function add(id, label) {
        label = text(label)
        if (!label || seen[label]) return
        seen[label] = true
        candidates.push({ id: text(id) || `meaning-${candidates.length + 1}`, label })
    }

    serverOptions.forEach((option) => add(option && option.id, option && option.label))
    let targetOption = null
    if (!serverOptions.length) {
        const targetId = String(question.word_id || '')
        const rows = Array.isArray(familiarity) ? familiarity : []
        const target = rows.find((item) => String(item && item.word_id) === targetId)
        if (target) {
            add(`meaning-${target.word_id}`, target.meaning)
            targetOption = candidates[0] || null
        }
        rows.forEach((item) => add(`meaning-${item && item.word_id}`, item && item.meaning))
    }

    const seed = question.question_id || question.learning_question_id || question.word_id || ''
    if (targetOption) {
        const distractors = candidates
            .filter((option) => option !== targetOption)
            .sort((left, right) => stableHash(`${seed}|pick|${left.label}`) - stableHash(`${seed}|pick|${right.label}`))
            .slice(0, 3)
        return [targetOption, ...distractors]
            .sort((left, right) => stableHash(`${seed}|order|${left.label}`) - stableHash(`${seed}|order|${right.label}`))
    }
    return candidates
        .sort((left, right) => stableHash(`${seed}|order|${left.label}`) - stableHash(`${seed}|order|${right.label}`))
        .slice(0, 4)
}

function selectedOptionLabel(options, selectedId) {
    const selected = (Array.isArray(options) ? options : []).find(
        (option) => String(option && option.id) === String(selectedId || '')
    )
    return selected ? text(selected.label) : ''
}

const SAFE_UNRESOLVED_OPTION = '未能还原原选项'

function normalizedEnglish(value) {
    return String(value || '')
        .trim()
        .toLowerCase()
        .replace(/[’‘]/g, "'")
        .replace(/\.{3,}|…+/g, ' ')
        .replace(/[，,。.!！？?；;：:()（）]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
}

function optionList(options) {
    return Array.isArray(options) ? options.filter((option) => option && typeof option === 'object') : []
}

function optionLabelForValue(options, value) {
    const rows = optionList(options)
    if (!rows.length) return ''
    if (value && typeof value === 'object') {
        const direct = text(value.label || value.text || value.display_label)
        if (direct && !looksLikeInternalAnswer(direct)) return direct
        const nested = value.id !== undefined
            ? value.id
            : (value.option_id !== undefined
                ? value.option_id
                : (value.index !== undefined ? value.index : value.option_index))
        if (nested !== undefined && nested !== null) return optionLabelForValue(rows, nested)
        return ''
    }
    const raw = text(value)
    if (!raw) return ''
    const byId = rows.find((option) => String(option.id) === raw)
    if (byId) return text(byId.label || byId.text)
    const numeric = /^\d+$/.test(raw) ? Number(raw) : NaN
    if (Number.isInteger(numeric)) {
        if (rows[numeric]) return text(rows[numeric].label || rows[numeric].text)
        // Some historical records used one-based option indexes.
        if (numeric > 0 && rows[numeric - 1]) return text(rows[numeric - 1].label || rows[numeric - 1].text)
    }
    const byLabel = rows.find((option) => text(option.label || option.text) === raw)
    return byLabel ? text(byLabel.label || byLabel.text) : ''
}

function looksLikeInternalAnswer(value) {
    const raw = text(value)
    return /^(?:option[_-]|uuid[_-]|answer[_-]|choice[_-])/i.test(raw)
        || /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(raw)
        || /^[0-9a-f]{32}$/i.test(raw)
}

function safeAnswerDisplay(value, options, fallback = SAFE_UNRESOLVED_OPTION) {
    if (value && typeof value === 'object') {
        const direct = text(value.label || value.text || value.display_label)
        if (direct) return direct
    }
    const mapped = optionLabelForValue(options, value)
    if (mapped) return mapped
    const raw = text(value)
    if (!raw || looksLikeInternalAnswer(raw)) return fallback
    // A numeric answer that did not resolve to an option is still an internal
    // index/key in the historical contract and must not reach the learner.
    if (/^\d+$/.test(raw)) return fallback
    return raw
}

function contextCorrectionSubmissionValue(question, typedAnswer, revealedAnswer) {
    const raw = text(typedAnswer)
    if (!question || question.mode !== 'context_choice' || !raw) return raw
    const prompt = question.question && question.question.prompt
    const target = text(prompt && prompt.target_word)
    if (!target || normalizedEnglish(raw) !== normalizedEnglish(target)) return raw
    const options = question.question && question.question.options
    const explicitId = question.revealed_answer_option_id
    if (explicitId) return String(explicitId)
    const expectedLabel = text(revealedAnswer)
    const option = optionList(options).find(
        (candidate) => text(candidate.label || candidate.text) === expectedLabel
    )
    return option ? String(option.id) : raw
}

module.exports = {
    SAFE_UNRESOLVED_OPTION,
    buildMeaningChoiceOptions,
    contextCorrectionSubmissionValue,
    normalizedEnglish,
    safeAnswerDisplay,
    selectedOptionLabel
}
