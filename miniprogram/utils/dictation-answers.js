function normalizeEnglishAnswer(value) {
    return String(value || '')
        .trim()
        .toLowerCase()
        .replace(/[’‘]/g, "'")
        .replace(/\.{3,}|…+/g, ' ')
        .replace(/[，,。.!！？?；;：:()（）]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
}

function parseAnswerVariants(value) {
    let rawItems = []
    if (Array.isArray(value)) {
        rawItems = value
    } else {
        const source = String(value || '').trim()
        if (!source) return []
        if (source[0] === '[') {
            try {
                const decoded = JSON.parse(source)
                if (Array.isArray(decoded)) rawItems = decoded
            } catch (e) {}
        }
        if (!rawItems.length) {
            rawItems = source.split(/\s*(?:[\/≈；;]|,(?=\s*[a-zA-Z]))\s*/)
        }
    }

    const seen = new Set()
    rawItems.forEach(raw => {
        const withoutPartOfSpeech = String(raw || '')
            .trim()
            .replace(/^(?:n|v|vt|vi|adj|adv|prep|conj|pron|phr)\.\s*/i, '')
        const normalized = normalizeEnglishAnswer(withoutPartOfSpeech)
        if (normalized) seen.add(normalized)
    })
    return Array.from(seen)
}

function englishAnswerVariants(word) {
    const canonical = word && typeof word === 'object' ? word.word : word
    const accepted = word && typeof word === 'object' ? word.accepted_answers : null
    let variants = new Set(parseAnswerVariants(canonical))
    parseAnswerVariants(accepted).forEach(item => variants.add(item))
    return Array.from(variants)
}

function isEnglishAnswerCorrect(answer, word) {
    const normalized = normalizeEnglishAnswer(answer)
    return Boolean(normalized) && englishAnswerVariants(word).includes(normalized)
}

module.exports = {
    englishAnswerVariants,
    isEnglishAnswerCorrect,
    normalizeEnglishAnswer,
    parseAnswerVariants
}
