const REGIONAL_SPELLING_PAIRS = [
    ['behavior', 'behaviour'],
    ['color', 'colour'],
    ['favor', 'favour'],
    ['favorite', 'favourite'],
    ['flavor', 'flavour'],
    ['harbor', 'harbour'],
    ['honor', 'honour'],
    ['humor', 'humour'],
    ['labor', 'labour'],
    ['neighbor', 'neighbour'],
    ['rumor', 'rumour'],
    ['center', 'centre'],
    ['fiber', 'fibre'],
    ['liter', 'litre'],
    ['meter', 'metre'],
    ['theater', 'theatre'],
    ['catalog', 'catalogue'],
    ['dialog', 'dialogue'],
    ['gray', 'grey'],
    ['jewelry', 'jewellery'],
    ['license', 'licence'],
    ['practice', 'practise'],
    ['program', 'programme'],
    ['traveling', 'travelling'],
    ['traveled', 'travelled'],
    ['traveler', 'traveller'],
    ['modeling', 'modelling'],
    ['modeled', 'modelled'],
    ['canceled', 'cancelled'],
    ['canceling', 'cancelling'],
    ['analyze', 'analyse'],
    ['organize', 'organise'],
    ['recognize', 'recognise']
]

const COMMON_SYNONYM_GROUPS = [
    ['bike', 'bicycle'],
    ['bikes', 'bicycles']
]

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

function expandGroups(values, groups) {
    const expanded = new Set(values)
    groups.forEach(group => {
        if (group.some(item => expanded.has(item))) {
            group.forEach(item => expanded.add(item))
        }
    })
    return expanded
}

function englishAnswerVariants(word, options = {}) {
    const canonical = word && typeof word === 'object' ? word.word : word
    const accepted = word && typeof word === 'object' ? word.accepted_answers : null
    let variants = new Set(parseAnswerVariants(canonical))
    parseAnswerVariants(accepted).forEach(item => variants.add(item))
    variants = expandGroups(variants, REGIONAL_SPELLING_PAIRS)
    if (options.allowSynonyms) {
        variants = expandGroups(variants, COMMON_SYNONYM_GROUPS)
    }
    return Array.from(variants)
}

function isEnglishAnswerCorrect(answer, word, options = {}) {
    const normalized = normalizeEnglishAnswer(answer)
    return Boolean(normalized) && englishAnswerVariants(word, options).includes(normalized)
}

function englishAnswerLengthHint(word, options = {}) {
    const lengths = new Set()
    englishAnswerVariants(word, options).forEach(answer => {
        const count = (answer.match(/[a-z]/gi) || []).length
        if (count) lengths.add(count)
    })
    const ordered = Array.from(lengths).sort((a, b) => a - b)
    if (!ordered.length) return ''
    return `可接受答案：${ordered.join(' 或 ')} 个字母`
}

module.exports = {
    englishAnswerLengthHint,
    englishAnswerVariants,
    isEnglishAnswerCorrect,
    normalizeEnglishAnswer,
    parseAnswerVariants
}
