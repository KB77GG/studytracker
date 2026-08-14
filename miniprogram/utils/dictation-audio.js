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

function createReliableAudioPlayer(wxApi, options) {
    options = options || {}
    if (!wxApi || typeof wxApi.createInnerAudioContext !== 'function') {
        throw new Error('inner_audio_unavailable')
    }

    if (typeof wxApi.setInnerAudioOption === 'function') {
        try {
            wxApi.setInnerAudioOption({
                obeyMuteSwitch: false,
                speakerOn: true,
                mixWithOther: false
            })
        } catch (e) {}
    }

    const audioCtx = wxApi.createInnerAudioContext()
    audioCtx.obeyMuteSwitch = false
    audioCtx.autoplay = false

    const cache = Object.create(null)
    let activePath = ''
    let currentDownloadTask = null
    let destroyed = false
    let playToken = 0
    let pendingToken = 0
    let state = 'idle'

    function emitState(nextState) {
        if (state === nextState) return
        state = nextState
        if (typeof options.onStateChange === 'function') options.onStateChange(nextState)
    }

    function abortDownload() {
        if (currentDownloadTask && typeof currentDownloadTask.abort === 'function') {
            try { currentDownloadTask.abort() } catch (e) {}
        }
        currentDownloadTask = null
    }

    function playPrepared(path, token) {
        if (!path || destroyed || token !== playToken) return
        if (activePath === path) {
            pendingToken = 0
            try { audioCtx.pause() } catch (e) {}
            try { audioCtx.seek(0) } catch (e) {}
            setTimeout(() => {
                if (destroyed || token !== playToken || activePath !== path) return
                try { audioCtx.play() } catch (e) {
                    pendingToken = token
                    activePath = ''
                    audioCtx.src = path
                }
            }, 80)
            return
        }
        pendingToken = token
        activePath = path
        audioCtx.src = path
    }

    function fallBackToRemote(url, token) {
        if (destroyed || token !== playToken) return
        playPrepared(url, token)
    }

    function failPlayback(error, token) {
        if (destroyed || token !== playToken) return
        pendingToken = 0
        activePath = ''
        emitState('error')
        if (typeof options.onError === 'function') options.onError(error)
    }

    if (typeof audioCtx.onCanplay === 'function') {
        audioCtx.onCanplay(() => {
            if (!pendingToken || pendingToken !== playToken || destroyed) return
            pendingToken = 0
            try { audioCtx.play() } catch (e) {
                emitState('error')
                if (typeof options.onError === 'function') options.onError(e)
            }
        })
    }
    if (typeof audioCtx.onPlay === 'function') audioCtx.onPlay(() => emitState('playing'))
    if (typeof audioCtx.onEnded === 'function') audioCtx.onEnded(() => emitState('idle'))
    if (typeof audioCtx.onStop === 'function') audioCtx.onStop(() => {
        if (state !== 'loading') emitState('idle')
    })
    if (typeof audioCtx.onError === 'function') {
        audioCtx.onError((error) => {
            const message = String((error && error.errMsg) || '')
            if (message.includes('interrupted by a new load request')) return
            if (destroyed) return
            pendingToken = 0
            emitState('error')
            if (typeof options.onError === 'function') options.onError(error)
        })
    }

    function play(source, baseUrl) {
        const url = resolveAudioUrl(source, baseUrl)
        if (!url || destroyed) return false
        playToken += 1
        const token = playToken
        emitState('loading')
        abortDownload()
        try { audioCtx.stop() } catch (e) {}

        if (cache[url]) {
            playPrepared(cache[url], token)
            return true
        }
        if (typeof wxApi.downloadFile !== 'function') {
            fallBackToRemote(url, token)
            return true
        }

        let task = null
        task = wxApi.downloadFile({
            url,
            success(result) {
                if (currentDownloadTask === task) currentDownloadTask = null
                if (destroyed || token !== playToken) return
                const status = Number(result && result.statusCode)
                if ((status === 200 || status === 206) && result.tempFilePath) {
                    cache[url] = result.tempFilePath
                    playPrepared(result.tempFilePath, token)
                    return
                }
                // A completed HTTP error will fail identically when assigned
                // to InnerAudioContext and may trigger its internal retries.
                // Surface it once; remote fallback is only useful when the
                // download API itself is unavailable or fails locally.
                failPlayback({
                    errMsg: `audio download HTTP ${status || 'unknown'}`,
                    statusCode: status || 0
                }, token)
            },
            fail() {
                if (currentDownloadTask === task) currentDownloadTask = null
                fallBackToRemote(url, token)
            }
        })
        currentDownloadTask = task
        return true
    }

    function destroy() {
        if (destroyed) return
        destroyed = true
        playToken += 1
        pendingToken = 0
        abortDownload()
        try { audioCtx.stop() } catch (e) {}
        try { audioCtx.destroy() } catch (e) {}
        emitState('idle')
    }

    return { play, destroy, context: audioCtx }
}

module.exports = { resolveAudioUrl, createReliableAudioPlayer }
