const MODE_AUDIO_TO_EN = 'audio_to_en'
const MODE_ZH_TO_EN = 'zh_to_en'
const MODE_SPELLING_DRILL = 'spelling_drill'
const MODE_EN_TO_ZH = 'en_to_zh'
const MODE_CONTEXT_FILL = 'context_fill'

// This module is page-scoped to vocabulary/dictation answer pages.
// Do not import it from listening, reading, or global mini-program code.
const WORD_TASK_ENGLISH_MODES = new Set([
    MODE_AUDIO_TO_EN,
    MODE_ZH_TO_EN,
    MODE_SPELLING_DRILL,
    MODE_CONTEXT_FILL
])

function isEnglishSpellingMode(mode) {
    return WORD_TASK_ENGLISH_MODES.has(String(mode || '').trim().toLowerCase())
}

module.exports = {
    MODE_AUDIO_TO_EN,
    MODE_EN_TO_ZH,
    MODE_SPELLING_DRILL,
    MODE_CONTEXT_FILL,
    MODE_ZH_TO_EN,
    isEnglishSpellingMode
}
