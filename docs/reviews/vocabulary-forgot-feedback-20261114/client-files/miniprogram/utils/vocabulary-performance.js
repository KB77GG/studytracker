/* Lightweight, anonymous vocabulary-review performance tracing.
 *
 * The tracker is intentionally independent from wx.request and Page so it can
 * be unit-tested in Node. Development builds retain marks and counters;
 * release builds retain only an anonymous trace id and error events.
 */

const TRACE_EVENTS = new Set([
    'navigation_start',
    'page_onLoad',
    'request_start',
    'request_end',
    'response_parse_end',
    'normalize_end',
    'scheduler_end',
    'first_setData_end',
    'first_visible',
    'first_interactive',
    'next_word_start',
    'next_word_visible',
    'audio_click',
    'audio_download',
    'audio_canplay',
    'audio_play',
    'audio_error'
])

function clock() {
    return Date.now()
}

function makeTraceId() {
    const random = Math.floor(Math.random() * 0x100000000).toString(16).padStart(8, '0')
    return `vocab-${clock().toString(36)}-${random}`
}

function estimateBytes(value) {
    if (value === undefined || value === null) return 0
    try {
        return JSON.stringify(value).length
    } catch (error) {
        return 0
    }
}

function safeAudioSource(value) {
    const raw = String(value || '').trim()
    if (!raw) return ''
    const withoutQuery = raw.split(/[?#]/, 1)[0]
    const absolute = withoutQuery.match(/^(https?:\/\/[^/]+)(\/.*)?$/i)
    return absolute ? `${absolute[1]}${absolute[2] || '/'}` : withoutQuery
}

function safeErrorMessage(value) {
    const raw = String(value || '')
    const sanitized = raw
        .replace(/https?:\/\/[^\s"'<>]+/gi, (url) => safeAudioSource(url))
        .replace(/(\/[^\s"'<>?]+)\?[^\s"'<>]*/g, '$1')
    return sanitized.slice(0, 240)
}

function isDevelopment(wxApi, explicit) {
    if (explicit !== undefined) return explicit !== false
    try {
        const envVersion = wxApi
            && typeof wxApi.getAccountInfoSync === 'function'
            && wxApi.getAccountInfoSync().miniProgram.envVersion
        return envVersion !== 'release'
    } catch (error) {
        return true
    }
}

function createVocabularyPerformanceTracker(wxApi, options) {
    options = options || {}
    const development = isDevelopment(wxApi, options.development)
    const startedAt = clock()
    const traceId = makeTraceId()
    const marks = {}
    const events = []
    const metrics = {}
    let lastSnapshotLogAt = 0

    function mark(name, detail) {
        if (!TRACE_EVENTS.has(name)) return
        const at = clock()
        // Keep the production record to actionable failures only. It never
        // receives a name, answer, signed URL, or raw request payload.
        if (!development && name !== 'audio_error' && name !== 'request_end') return
        if (!development && name === 'request_end' && (!detail || detail.ok !== false)) return
        if (development) marks[name] = at
        const event = { name, at_ms: Math.max(0, at - startedAt) }
        const productionKeys = name === 'request_end'
            ? new Set(['endpoint', 'ok', 'error', 'errMsg', 'errCode'])
            : new Set([
                'source',
                'path',
                'source_index',
                'source_type',
                'phase',
                'statusCode',
                'contentType',
                'errMsg',
                'errCode',
                'redirect_info'
            ])
        if (detail && typeof detail === 'object') {
            Object.keys(detail).forEach((key) => {
                if (!development && !productionKeys.has(key)) return
                if (key === 'url' || key === 'source' || key === 'path') {
                    const safe = safeAudioSource(detail[key])
                    if (safe) event[key] = safe
                } else if (key === 'errMsg' || key === 'error' || key === 'message') {
                    event[key] = safeErrorMessage(detail[key])
                } else if (key !== 'answer' && key !== 'student_name' && key !== 'account') {
                    event[key] = detail[key]
                }
            })
        }
        events.push(event)
    }

    function setMetric(name, value) {
        if (!development && !/^error/.test(name)) return
        if (typeof value === 'number' && Number.isFinite(value)) metrics[name] = value
        else if (typeof value === 'string' && value.length <= 80) metrics[name] = value
    }

    function addMetric(name, amount) {
        const numeric = Number(amount)
        if (!Number.isFinite(numeric)) return
        setMetric(name, Number(metrics[name] || 0) + numeric)
    }

    function snapshot() {
        return {
            trace_id: traceId,
            development,
            marks: Object.assign({}, marks),
            metrics: Object.assign({}, metrics),
            events: events.slice()
        }
    }

    function logSnapshot(label) {
        const current = clock()
        if (!development || current - lastSnapshotLogAt < 750) return snapshot()
        lastSnapshotLogAt = current
        const value = snapshot()
        if (typeof console !== 'undefined' && typeof console.info === 'function') {
            console.info('[vocabulary-performance]', label || 'snapshot', value)
        }
        return value
    }

    return {
        traceId,
        development,
        mark,
        setMetric,
        addMetric,
        estimateBytes,
        safeAudioSource,
        snapshot,
        logSnapshot
    }
}

module.exports = {
    createVocabularyPerformanceTracker,
    estimateBytes,
    safeAudioSource
}
