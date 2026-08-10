function cleanText(value) {
    return typeof value === 'string' ? value.trim() : ''
}

function cleanSyllables(value) {
    if (Array.isArray(value)) return value.map(cleanText).filter(Boolean).join(' · ')
    return cleanText(value)
}

function normalizeAnswerFeedback(payload, fallback) {
    const outer = payload && typeof payload === 'object' ? payload : {}
    const source = outer.answer_feedback && typeof outer.answer_feedback === 'object'
        ? outer.answer_feedback
        : outer
    const safeFallback = fallback && typeof fallback === 'object' ? fallback : {}
    const feedback = {
        word: cleanText(source.word) || cleanText(safeFallback.word),
        syllables: cleanSyllables(source.syllables) || cleanSyllables(safeFallback.syllables),
        phonetic: cleanText(source.phonetic) || cleanText(safeFallback.phonetic),
        core_meaning_zh: cleanText(source.core_meaning_zh)
            || cleanText(source.meaning)
            || cleanText(safeFallback.core_meaning_zh)
            || cleanText(safeFallback.meaning),
        usage_pattern: cleanText(source.usage_pattern) || cleanText(safeFallback.usage_pattern),
        example_en: cleanText(source.example_en) || cleanText(safeFallback.example_en),
        example_zh: cleanText(source.example_zh) || cleanText(safeFallback.example_zh),
        usage_note: cleanText(source.usage_note) || cleanText(safeFallback.usage_note),
        audio_tts_url: cleanText(source.audio_tts_url) || cleanText(safeFallback.audio_tts_url)
    }
    return Object.values(feedback).some(Boolean) ? feedback : null
}

module.exports = {
    normalizeAnswerFeedback
}
