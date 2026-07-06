function normalizeOrder(value) {
    return String(value || '').trim().toLowerCase() === 'random' ? 'random' : 'sequence'
}

function hashSeed(value) {
    const text = String(value || '')
    let hash = 2166136261
    for (let i = 0; i < text.length; i += 1) {
        hash ^= text.charCodeAt(i)
        hash = Math.imul(hash, 16777619)
    }
    return hash >>> 0
}

function seededRandom(seedValue) {
    let state = hashSeed(seedValue) || 1
    return function nextRandom() {
        state += 0x6D2B79F5
        let t = state
        t = Math.imul(t ^ (t >>> 15), t | 1)
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296
    }
}

function shuffleCopy(items, seedValue) {
    const result = items.slice()
    const random = seededRandom(seedValue)
    for (let i = result.length - 1; i > 0; i -= 1) {
        const j = Math.floor(random() * (i + 1))
        const temp = result[i]
        result[i] = result[j]
        result[j] = temp
    }
    return result
}

function applyDictationOrder(words, options = {}) {
    const source = Array.isArray(words) ? words : []
    if (normalizeOrder(options.order) !== 'random' || source.length <= 1) {
        return source.slice()
    }
    const seed = [
        options.taskId || '',
        options.bookId || '',
        options.start || '',
        options.end || ''
    ].join(':')
    return shuffleCopy(source, seed)
}

module.exports = {
    applyDictationOrder,
    normalizeOrder
}
