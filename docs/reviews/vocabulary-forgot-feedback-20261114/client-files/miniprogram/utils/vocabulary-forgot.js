const { safeAnswerDisplay } = require('./vocabulary-interaction.js')

function isForgotResponse(value) {
    if (!value) return false
    if (value.response_kind) return value.response_kind === 'forgot'
    return value.first_response_kind === 'forgot'
}

function matchesAnswerEvent(event, item, idKey, itemId, renderEpoch) {
    // Direct calls from page logic do not carry an event. UI events always
    // carry the identity of the question that rendered their control.
    if (!event) return true
    const dataset = event.currentTarget && event.currentTarget.dataset
    if (!dataset || dataset[idKey] === undefined || dataset.questionId === undefined) return false
    if (String(dataset[idKey]) !== String(itemId)) return false
    if (String(dataset.questionId) !== String(item && item.question_id || '')) return false
    // Older injected events may have question identity only. They can match
    // the first render, but never a repeated render of the same question.
    // Real buttons and keyboard confirm controls always carry this epoch.
    if (dataset.renderEpoch === undefined) return Number(renderEpoch) <= 1
    return String(dataset.renderEpoch) === String(renderEpoch)
}

function forgotCountFromResponse(response, countKey, rows) {
    const count = response && response[countKey]
    if (count !== undefined && count !== null) {
        const number = Number(count)
        return Number.isFinite(number) ? Math.max(0, number) : 0
    }
    return Array.isArray(rows) ? rows.length : 0
}

function forgotItemsForDisplay(rows) {
    if (!Array.isArray(rows)) return []
    const seen = new Set()
    return rows.reduce((items, row) => {
        if (!row || typeof row !== 'object') return items
        const feedback = row.answer_feedback || {}
        const prompt = (row.question && row.question.prompt) || {}
        const word = String(row.correct_spelling || row.word || feedback.word || prompt.word || prompt.target_word || '').trim()
        const meaning = String(row.meaning || feedback.core_meaning_zh || prompt.meaning || '').trim()
        const answer = safeAnswerDisplay(
            row.revealed_answer || row.revealed_answer_option_id,
            (row.question && row.question.options) || [],
            '暂无法显示正确答案'
        )
        const key = String(row.word_id || row.learning_question_id || row.review_item_id || `${word}|${answer}`)
        if (seen.has(key)) return items
        seen.add(key)
        items.push({
            key,
            word: word || '本题单词',
            meaning: meaning || '暂无释义',
            answer,
            audioSources: [
                row.audio_tts_url,
                row.audio_url,
                feedback.audio_tts_url,
                feedback.audio_url
            ].filter(Boolean)
        })
        return items
    }, [])
}

function shouldRecoverLearningAnswer(error) {
    const code = String((error && (error.error || error.message || error.errMsg)) || '').toLowerCase()
    const status = Number(error && error.statusCode) || 0
    return status >= 500 || status === 409 || !!(error && error.deadline)
        || /timeout|request:fail|network|socket|abort|state_conflict|question_not_current|queue_changed|attempt_id_conflict/.test(code)
}

module.exports = {
    forgotCountFromResponse,
    forgotItemsForDisplay,
    isForgotResponse,
    matchesAnswerEvent,
    shouldRecoverLearningAnswer
}
