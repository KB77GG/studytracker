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
    getOrCreateRunId,
    isSuccessfulResponse,
    legacyWrongItemBelongsToBook,
    summarizeQueue,
    queueMode
}
