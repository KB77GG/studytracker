function resolveAudioUrl(source, baseUrl) {
    const value = String(source || '').trim()
    if (!value) return ''
    if (/^https?:\/\//i.test(value)) return value

    const base = String(baseUrl || '').replace(/\/$/, '')
    if (!base) return value
    // Some older snapshots carried /api/... while baseUrl already ends in
    // /api. Keep this helper tolerant during rollout, although v2 now emits
    // the canonical /dictation/... path.
    if (/\/api$/i.test(base) && /^\/api\//i.test(value)) {
        return `${base}${value.slice(4)}`
    }
    return `${base}${value.startsWith('/') ? value : `/${value}`}`
}

module.exports = { resolveAudioUrl }
