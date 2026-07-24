function buildFirstAttemptId(taskId, bookId, wordId, sessionId) {
    const scope = taskId
        ? `task-${taskId}`
        : `book-${bookId || 'unknown'}-${sessionId || 'session'}`
    return `dictation:first:${scope}:word-${wordId}`
}

function summarizeQueue(queue) {
    const items = Array.isArray(queue) ? queue : []
    return {
        assignedCount: items.filter(item => item && item.source === 'assigned').length,
        reviewCount: items.filter(item => item && item.source === 'auto_review').length,
        totalCount: items.length
    }
}

function queueMode(item, fallback) {
    return String((item && (item.mode || item.dictation_mode)) || fallback || 'audio_to_en')
        .trim()
        .toLowerCase()
}

function buildRunStorageKey(scope) {
    return `dictation:attempt-run:${scope || 'default'}`
}

function createAttemptRunId(prefix) {
    const safePrefix = String(prefix || 'run').replace(/[^a-zA-Z0-9_-]/g, '_')
    return `${safePrefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function getOrCreateRunId(storage, key, factory) {
    const read = storage && typeof storage.get === 'function' ? storage.get() : null
    if (read) return String(read)
    const value = String((factory || createAttemptRunId)(key))
    if (storage && typeof storage.set === 'function') storage.set(value)
    return value
}

function ensureAttemptPayload(payloads, key, payload) {
    if (!payloads[key]) payloads[key] = Object.assign({}, payload)
    return payloads[key]
}

function isSuccessfulResponse(response) {
    return !!(response && response.ok === true)
}

function firstAttemptStateFromResponse(response, submittedAnswer) {
    if (!isSuccessfulResponse(response)) return null
    const isFirstAttempt = response.first_attempt !== false
    const historicalAnswer = isFirstAttempt
        ? response.student_answer
        : response.first_attempt_answer
    const hasRecordedAnswer = historicalAnswer !== undefined
        && historicalAnswer !== null
    return {
        correct: isFirstAttempt
            ? !!response.is_correct
            : response.first_attempt_is_correct === true,
        // An idempotent response is a replay of an existing database row.  Do
        // not fall back to the current input when an old server omits the
        // answer: that would pair a historical verdict with a new answer.
        answer: hasRecordedAnswer
            ? String(historicalAnswer)
            : (response.idempotent || !isFirstAttempt ? '' : String(submittedAnswer || '')),
        attemptId: (isFirstAttempt ? response.attempt_id : response.first_attempt_id) || '',
        idempotent: !!response.idempotent,
        recovered: !isFirstAttempt || !!response.idempotent
    }
}

function firstAttemptStateFromQueueItem(item) {
    if (!item || !item.first_attempt_id) return null
    return {
        correct: item.first_is_correct === true,
        answer: item.first_answer == null ? '' : String(item.first_answer),
        attemptId: String(item.first_attempt_id),
        idempotent: true,
        recovered: true
    }
}

function hydrateQueueFirstAttempts(words) {
    const states = {}
    ;(words || []).forEach((item, index) => {
        const state = firstAttemptStateFromQueueItem(item)
        if (!state) return
        const wordId = item.word_id || item.id
        if (wordId != null) states[String(wordId)] = state
        states[`index:${index}`] = state
    })
    return states
}

function firstAttemptForWord(states, word) {
    if (!states || !word) return null
    const wordId = word.word_id || word.id
    return states[String(wordId)] || states[`index:${word._originIndex}`] || null
}

function missingQueueItems(response, queue) {
    if (!response || response.error !== 'queue_incomplete') return []
    const missingIds = Array.isArray(response.missing_word_ids)
        ? response.missing_word_ids
        : []
    const items = Array.isArray(queue) ? queue : []
    const byWordId = new Map(items.map(item => [
        String(item && (item.word_id || item.id) || ''),
        item
    ]))
    const seen = new Set()
    return missingIds.reduce((result, wordId) => {
        const key = String(wordId || '')
        const item = byWordId.get(key)
        if (item && !seen.has(key)) {
            seen.add(key)
            result.push(item)
        }
        return result
    }, [])
}

function legacyWrongItemBelongsToBook(item, bookId, bookWords) {
    const source = item || {}
    const explicitBookId = source.book_id != null && source.book_id !== ''
        ? source.book_id
        : (source.dictation_book_id != null && source.dictation_book_id !== ''
            ? source.dictation_book_id
            : null)
    if (explicitBookId != null) return Number(explicitBookId) === Number(bookId)

    const words = Array.isArray(bookWords) ? bookWords : []
    const wordIds = new Set(words.map(word => Number(word && word.id)))
    const wordNames = new Set(words.map(word => String(word && (word.word || word.name) || '').trim().toLowerCase()))
    const itemWordId = Number(source.word_id || source.id || 0)
    const itemWord = String(source.word || source.name || '').trim().toLowerCase()
    return (itemWordId > 0 && wordIds.has(itemWordId))
        || (!!itemWord && wordNames.has(itemWord))
}

module.exports = {
    buildFirstAttemptId,
    buildRunStorageKey,
    createAttemptRunId,
    ensureAttemptPayload,
    firstAttemptForWord,
    firstAttemptStateFromQueueItem,
    firstAttemptStateFromResponse,
    getOrCreateRunId,
    hydrateQueueFirstAttempts,
    isSuccessfulResponse,
    legacyWrongItemBelongsToBook,
    missingQueueItems,
    summarizeQueue,
    queueMode
}
