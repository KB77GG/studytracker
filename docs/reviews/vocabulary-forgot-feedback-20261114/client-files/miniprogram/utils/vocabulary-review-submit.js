const RECOVERABLE_CODES = {
    attempt_id_conflict: true,
    review_answer_in_progress: true,
    review_item_already_answered: true,
    review_question_changed: true
}

const ACTIONABLE_MESSAGES = {
    attempt_id_conflict: '本题提交状态已变化，正在恢复',
    invalid_input_mode: '当前输入方式不可用，请刷新后重试',
    missing_answer: '请先填写答案',
    review_answer_in_progress: '本题正在保存，正在恢复',
    review_item_already_answered: '本题已保存，正在恢复',
    review_item_invalid: '题目资料异常，请稍后重试',
    review_item_not_in_session: '复习题目已变化，正在恢复',
    review_question_changed: '题目已更新，正在恢复',
    review_session_not_found: '复习会话已失效，请重新进入',
    review_session_token_invalid: '复习会话已失效，请重新进入',
    review_session_token_required: '复习会话已失效，请重新进入'
}

function buildReviewAttemptId(sessionId, reviewItemId) {
    return `wx-vocabulary-review:${sessionId}:${reviewItemId}`
}

function buildReviewCorrectionAttemptId(sessionId, reviewItemId, correctionNumber) {
    return `wx-vocabulary-review-correction:${sessionId}:${reviewItemId}:${Number(correctionNumber) || 1}`
}

function errorCode(value) {
    if (!value) return ''
    return String(value.error || value.message || value.errMsg || '').trim()
}

function isUncertainSubmitError(value) {
    const code = errorCode(value).toLowerCase()
    const statusCode = Number(value && value.statusCode) || 0
    if (statusCode >= 500) return true
    if (!code) return statusCode === 0
    return (
        code.includes('timeout')
        || code.includes('request:fail')
        || code.includes('network')
        || code.includes('socket')
        || code.includes('abort')
    )
}

function classifyReviewAnswerFailure(value) {
    const code = errorCode(value)
    const statusCode = Number(value && value.statusCode) || 0
    const uncertain = isUncertainSubmitError(value)
    return {
        code,
        statusCode,
        uncertain,
        recoverable: uncertain || !!RECOVERABLE_CODES[code],
        message: ACTIONABLE_MESSAGES[code] || (
            uncertain ? '提交结果未确认，正在恢复' : '提交失败，请重试'
        )
    }
}

function findReviewItem(items, reviewItemId) {
    const target = String(reviewItemId)
    return (Array.isArray(items) ? items : []).find(
        (item) => String(item && item.review_item_id) === target
    ) || null
}

function answeredReviewItem(items, reviewItemId) {
    const item = findReviewItem(items, reviewItemId)
    return item && item.first_attempt_id ? item : null
}

function correctedReviewItem(items, reviewItemId, attemptId) {
    const item = findReviewItem(items, reviewItemId)
    if (!item || !item.correction_attempt_id) return null
    if (attemptId && String(item.correction_attempt_id) !== String(attemptId)) return null
    return item
}

function mergeAnswerResult(item, result, fallbackAnswer) {
    return Object.assign({}, item, {
        first_attempt_id: result.attempt_id || item.first_attempt_id || '',
        first_is_correct: !!result.is_correct,
        first_answer: result.student_answer !== undefined ? result.student_answer : (fallbackAnswer || ''),
        first_response_kind: result.first_response_kind || result.response_kind || item.first_response_kind || 'answer',
        revealed_answer: result.revealed_answer || '',
        revealed_answer_option_id: result.revealed_answer_option_id || '',
        answer_feedback: result.answer_feedback || null,
        correction_required: !!result.correction_required,
        correction_attempt_id: result.correction_attempt_id || item.correction_attempt_id || '',
        correction_is_correct: result.correction_is_correct,
        correction_answer: result.correction_answer || item.correction_answer || '',
        correction_count: Number(result.correction_count || item.correction_count || 0),
        correction_max_attempts: Number(result.correction_max_attempts || item.correction_max_attempts || 2),
        correction_retry_allowed: !!result.correction_retry_allowed,
        correction_exhausted: !!result.correction_exhausted,
        answered: true
    })
}

module.exports = {
    buildReviewAttemptId,
    buildReviewCorrectionAttemptId,
    classifyReviewAnswerFailure,
    answeredReviewItem,
    correctedReviewItem,
    findReviewItem,
    isUncertainSubmitError,
    mergeAnswerResult
}
