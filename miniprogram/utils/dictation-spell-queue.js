const CORRECTION_ROUND_FLAG = '_correctionRound'

function wordQueueKey(word) {
    const item = word || {}
    if (item._originIndex != null) return `origin:${item._originIndex}`
    if (item.queue_item_id != null) return `queue:${item.queue_item_id}`
    if (item.word_id != null || item.id != null) return `word:${item.word_id || item.id}`
    return `text:${String(item.word || '')}`
}

function isCorrectionWord(word) {
    return !!(word && word[CORRECTION_ROUND_FLAG])
}

function enqueueCorrectionOnce(queue, currentWord) {
    const items = Array.isArray(queue) ? queue.slice() : []
    if (!currentWord || isCorrectionWord(currentWord)) return items

    const key = wordQueueKey(currentWord)
    const alreadyQueued = items.some(item => (
        isCorrectionWord(item) && wordQueueKey(item) === key
    ))
    if (alreadyQueued) return items

    const correction = Object.assign({}, currentWord, {
        [CORRECTION_ROUND_FLAG]: true,
        _key: `${currentWord._key || key}_correction`
    })
    items.push(correction)
    return items
}

function resolveWrongAnswer(queue, currentWord) {
    const correctionAttempt = isCorrectionWord(currentWord)
    return {
        queue: correctionAttempt
            ? (Array.isArray(queue) ? queue.slice() : [])
            : enqueueCorrectionOnce(queue, currentWord),
        completeCurrent: correctionAttempt
    }
}

module.exports = {
    enqueueCorrectionOnce,
    isCorrectionWord,
    resolveWrongAnswer,
    wordQueueKey
}
