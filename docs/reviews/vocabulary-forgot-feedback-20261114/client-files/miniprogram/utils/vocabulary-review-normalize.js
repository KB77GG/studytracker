const VALID_DIMENSIONS = new Set([
    'meaning_recall',
    'form_recall',
    'audio_form_recall',
    'context_use'
])

const VALID_MODES = new Set([
    'en_to_zh',
    'zh_to_en',
    'audio_to_en',
    'audio_to_zh',
    'context_choice',
    'context_fill'
])

const MAX_TEXT_LENGTH = 2000

function clean(value, max = MAX_TEXT_LENGTH) {
    if (value === undefined || value === null) return ''
    const result = String(value).trim()
    return result.length > max ? '' : result
}

function identity(value, max = 96) {
    if (typeof value === 'number') return Number.isFinite(value) ? value : null
    const result = clean(value, max)
    return result || null
}

function normalizeOptions(options) {
    if (!Array.isArray(options)) return []
    const seenIds = new Set()
    const seenLabels = new Set()
    return options.reduce((result, option) => {
        if (!option || typeof option !== 'object') return result
        const id = clean(option.id, 200)
        const label = clean(option.label || option.text, 500)
        if (!id || !label || seenIds.has(id) || seenLabels.has(label)) return result
        seenIds.add(id)
        seenLabels.add(label)
        result.push({ id, label })
        return result
    }, [])
}

function normalizeReviewItem(raw) {
    if (!raw || typeof raw !== 'object') return { item: null, reason: 'invalid_item' }
    const reviewItemId = identity(raw.review_item_id || raw.queue_item_id)
    const wordId = identity(raw.word_id)
    const senseId = identity(raw.sense_id)
    const dimension = clean(raw.dimension, 64).toLowerCase()
    const questionId = clean(raw.question_id, 96)
    const question = raw.question && typeof raw.question === 'object' ? raw.question : null
    const mode = clean(raw.mode || (question && question.mode), 64).toLowerCase()
    // Keep skip reasons in the server's small, stable vocabulary. A client
    // cannot make a valid row optional; these distinctions only describe why
    // this renderer could not safely use the frozen row it received.
    if (!reviewItemId) return { item: null, reason: 'invalid_item' }
    if (!wordId) return { item: null, reason: 'missing_word' }
    if (!senseId) return { item: null, reason: 'invalid_item' }
    if (!questionId) return { item: null, reason: 'invalid_question' }
    if (typeof raw.first_answer === 'string' && raw.first_answer.length > 200) return { item: null, reason: 'long_text' }
    if (typeof raw.correction_answer === 'string' && raw.correction_answer.length > 200) return { item: null, reason: 'long_text' }
    if (raw.due_at && !Number.isFinite(Date.parse(String(raw.due_at)))) return { item: null, reason: 'invalid_time' }
    if (!VALID_DIMENSIONS.has(dimension)) return { item: null, reason: 'invalid_dimension' }
    if (!VALID_MODES.has(mode) || !question) return { item: null, reason: 'invalid_question' }

    const prompt = question.prompt && typeof question.prompt === 'object'
        ? question.prompt
        : {}
    const promptText = [
        prompt.word,
        prompt.meaning,
        prompt.sentence,
        prompt.translation,
        prompt.instruction,
        prompt.audio_url,
        prompt.audio_tts_url
    ]
    if (promptText.some((value) => typeof value === 'string' && value.length > MAX_TEXT_LENGTH)) {
        return { item: null, reason: 'long_text' }
    }
    const safeQuestion = Object.assign({}, question, {
        mode,
        options: normalizeOptions(question.options),
        prompt: Object.assign({}, prompt)
    })
    if (mode === 'context_fill' && !clean(prompt.sentence, MAX_TEXT_LENGTH)) {
        return { item: null, reason: 'missing_context' }
    }
    if (mode === 'context_choice' && safeQuestion.options.length === 0) {
        return { item: null, reason: 'missing_options' }
    }
    if (mode === 'context_choice'
        && !clean(prompt.sentence, MAX_TEXT_LENGTH)
        && !clean(prompt.target_word, MAX_TEXT_LENGTH)) {
        return { item: null, reason: 'missing_context' }
    }
    if (mode === 'en_to_zh' && !clean(prompt.word, MAX_TEXT_LENGTH)) {
        return { item: null, reason: 'missing_meaning_prompt' }
    }
    if (mode === 'zh_to_en' && !clean(prompt.meaning, MAX_TEXT_LENGTH)) {
        return { item: null, reason: 'missing_meaning_prompt' }
    }
    if (mode === 'audio_to_zh' && safeQuestion.options.length === 0) {
        return { item: null, reason: 'missing_options' }
    }
    if ((mode === 'audio_to_en' || mode === 'audio_to_zh')
        && !clean(prompt.audio_url || prompt.audio_tts_url || raw.audio_url || raw.audio_tts_url, MAX_TEXT_LENGTH)) {
        return { item: null, reason: 'missing_audio' }
    }

    const item = Object.assign({}, raw, {
        review_item_id: reviewItemId,
        queue_item_id: reviewItemId,
        word_id: wordId,
        sense_id: senseId,
        question_id: questionId,
        dimension,
        mode,
        question: safeQuestion,
        first_answer: clean(raw.first_answer, 200),
        correction_answer: clean(raw.correction_answer, 200)
    })
    return { item, reason: '' }
}

function skippedIdentity(raw) {
    if (!raw || typeof raw !== 'object') return null
    return identity(raw.review_item_id || raw.queue_item_id)
}

function normalizeReviewQueue(rawItems) {
    const items = []
    const reasons = {}
    const skippedItems = []
    const seen = new Set()
    ;(Array.isArray(rawItems) ? rawItems : []).forEach((raw) => {
        const rawId = skippedIdentity(raw)
        const rawDimension = raw && typeof raw === 'object'
            ? clean(raw.dimension, 64).toLowerCase()
            : ''
        const rawKey = rawId !== null && rawDimension ? `${rawId}|${rawDimension}` : ''
        if (rawKey && seen.has(rawKey)) {
            reasons.duplicate = Number(reasons.duplicate || 0) + 1
            return
        }
        const result = normalizeReviewItem(raw)
        if (!result.item) {
            reasons[result.reason] = Number(reasons[result.reason] || 0) + 1
            const reviewItemId = skippedIdentity(raw)
            if (reviewItemId !== null) {
                skippedItems.push({ review_item_id: reviewItemId, reason: result.reason })
            }
            return
        }
        const key = `${result.item.review_item_id}|${result.item.dimension}`
        if (seen.has(key)) {
            reasons.duplicate = Number(reasons.duplicate || 0) + 1
            return
        }
        seen.add(key)
        items.push(result.item)
    })
    return {
        items,
        skipped: Object.values(reasons).reduce((sum, value) => sum + value, 0),
        reasons,
        skipped_items: skippedItems
    }
}

module.exports = {
    MAX_TEXT_LENGTH,
    normalizeReviewItem,
    normalizeReviewQueue
}
