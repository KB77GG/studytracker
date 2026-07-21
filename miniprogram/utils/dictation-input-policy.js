const MODE_AUDIO_TO_EN = 'audio_to_en'
const MODE_ZH_TO_EN = 'zh_to_en'
const MODE_SPELLING_DRILL = 'spelling_drill'
const MODE_EN_TO_ZH = 'en_to_zh'

const INPUT_STRICT = 'strict'
const INPUT_COMPATIBLE = 'compatible'
const INPUT_NATIVE = 'native'

// This module is page-scoped to the three vocabulary/dictation task pages.
// Do not import it from listening, reading, or global mini-program code.
const WORD_TASK_ENGLISH_MODES = new Set([
    MODE_AUDIO_TO_EN,
    MODE_ZH_TO_EN,
    MODE_SPELLING_DRILL
])

function isEnglishSpellingMode(mode) {
    return WORD_TASK_ENGLISH_MODES.has(String(mode || '').trim().toLowerCase())
}

function defaultInputPolicy(mode) {
    const normalizedMode = String(mode || '').trim().toLowerCase()
    const isEnglish = isEnglishSpellingMode(normalizedMode)
    return {
        mode: normalizedMode || MODE_EN_TO_ZH,
        isEnglishSpelling: isEnglish,
        defaultInputMode: isEnglish ? INPUT_STRICT : INPUT_NATIVE,
        compatibleAllowed: false,
        grant: null
    }
}

function normalizeServerPolicy(response, mode) {
    const fallback = defaultInputPolicy(mode)
    const raw = response && response.policy ? response.policy : {}
    return {
        mode: raw.mode || fallback.mode,
        isEnglishSpelling: raw.is_english_spelling != null
            ? !!raw.is_english_spelling
            : fallback.isEnglishSpelling,
        defaultInputMode: raw.default_input_mode || fallback.defaultInputMode,
        compatibleAllowed: !!raw.compatible_allowed,
        grant: raw.grant || null
    }
}

function chooseInputMode(policy, storedMode) {
    if (!policy || !policy.isEnglishSpelling) return INPUT_NATIVE
    if (policy.compatibleAllowed && storedMode === INPUT_COMPATIBLE) {
        return INPUT_COMPATIBLE
    }
    return INPUT_STRICT
}

function inputModeStorageKey({ taskId, bookId, mode } = {}) {
    const scope = taskId ? `task-${taskId}` : `book-${bookId || 'unknown'}`
    return `dictation_input_mode:${scope}:${String(mode || '').trim().toLowerCase() || 'unknown'}`
}

function normalizeKeyboardKey(key) {
    if (key === '’' || key === '‘') return "'"
    if (key === ' ') return ' '
    return String(key || '').toLowerCase()
}

function answerSeparators(answer) {
    const text = String(answer || '')
    const separators = []
    if (text.includes(' ')) separators.push({ key: ' ', label: '空格', ariaLabel: '空格' })
    if (text.includes('-') || text.includes('‐') || text.includes('‑') || text.includes('–') || text.includes('—')) {
        separators.push({ key: '-', label: '-', ariaLabel: '连字符' })
    }
    if (text.includes("'") || text.includes('’') || text.includes('‘') || text.includes('`') || text.includes('´')) {
        separators.push({ key: "'", label: "'", ariaLabel: '撇号' })
    }
    return separators
}

function answerInputLimit(answer, acceptedAnswers) {
    const values = [String(answer || '')]
    if (Array.isArray(acceptedAnswers)) {
        values.push(...acceptedAnswers)
    } else if (acceptedAnswers) {
        const raw = String(acceptedAnswers).trim()
        if (raw[0] === '[') {
            try {
                const parsed = JSON.parse(raw)
                if (Array.isArray(parsed)) values.push(...parsed)
            } catch (e) {}
        } else {
            values.push(...raw.split(/\s*(?:[\/／;；]|,(?=\s*[a-zA-Z]))\s*/))
        }
    }
    return Math.max(1, ...values.map(value => Array.from(String(value || '')).length))
}

module.exports = {
    INPUT_COMPATIBLE,
    INPUT_NATIVE,
    INPUT_STRICT,
    MODE_AUDIO_TO_EN,
    MODE_EN_TO_ZH,
    MODE_SPELLING_DRILL,
    MODE_ZH_TO_EN,
    answerSeparators,
    answerInputLimit,
    chooseInputMode,
    defaultInputPolicy,
    inputModeStorageKey,
    isEnglishSpellingMode,
    normalizeKeyboardKey
}
