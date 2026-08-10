function text(value) {
    return String(value || '').trim()
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

module.exports = { buildMeaningChoiceOptions, selectedOptionLabel }
