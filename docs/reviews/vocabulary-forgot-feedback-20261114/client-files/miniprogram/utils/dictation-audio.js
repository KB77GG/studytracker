function resolveAudioUrl(source, baseUrl) {
    const value = String(source || '').trim()
    if (!value) return ''
    if (/^https?:\/\//i.test(value)) return value

    const base = String(baseUrl || '').replace(/\/$/, '')
    if (!base) return value
    // Uploaded/static assets live at the site root, outside the /api prefix.
    // Backfilled dictionary audio is stored as uploads/tts_cache/... .
    if (/\/api$/i.test(base) && /^\/?(?:uploads|static)\//i.test(value)) {
        const rootBase = base.slice(0, -4)
        return `${rootBase}${value.startsWith('/') ? value : `/${value}`}`
    }
    // Some older snapshots carried /api/... while baseUrl already ends in
    // /api. Keep this helper tolerant during rollout, although v2 now emits
    // the canonical /dictation/... path.
    if (/\/api$/i.test(base) && /^\/api\//i.test(value)) {
        return `${base}${value.slice(4)}`
    }
    return `${base}${value.startsWith('/') ? value : `/${value}`}`
}

function flattenSources(source, baseUrl, output) {
    if (Array.isArray(source)) {
        source.forEach((item) => flattenSources(item, baseUrl, output))
        return output
    }
    if (source && typeof source === 'object') {
        flattenSources(
            source.url || source.src || source.audio_url || source.audio_tts_url,
            baseUrl,
            output
        )
        return output
    }
    const url = resolveAudioUrl(source, baseUrl)
    if (url && output.indexOf(url) < 0) output.push(url)
    return output
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

    let audioCtx = null

    const cache = new Map()
    const inflightDownloads = new Map()
    const activeDownloads = new Map()
    const maxCacheEntries = Math.max(1, Number(options.maxCacheEntries) || 3)
    const loadTimeoutMs = Math.max(1, Number(options.loadTimeoutMs) || 5000)
    const downloadTimeoutMs = Math.max(1, Number(options.downloadTimeoutMs) || 5000)
    const errorGraceMs = Math.max(0, Number(options.errorGraceMs) || 250)
    let destroyed = false
    let playToken = 0
    let state = 'idle'
    let activeRequest = null
    let loadTimer = null
    let errorTimer = null
    let preloadChain = Promise.resolve()
    let maxConcurrentDownloads = 0
    let activePreloadDownloads = 0
    let maxConcurrentPreloadDownloads = 0
    const preferredReplayBySet = new Map()

    function emitEvent(name, detail) {
        if (typeof options.onEvent === 'function') options.onEvent(name, detail || {})
    }

    function sourceType(request) {
        return request && request.index === 0 ? 'primary' : 'fallback'
    }

    function clearLoadTimer() {
        if (loadTimer === null) return
        clearTimeout(loadTimer)
        loadTimer = null
    }

    function clearErrorTimer() {
        if (errorTimer === null) return
        clearTimeout(errorTimer)
        errorTimer = null
    }

    function clearTimers() {
        clearLoadTimer()
        clearErrorTimer()
    }

    function emitState(nextState) {
        if (destroyed || state === nextState) return
        state = nextState
        if (typeof options.onStateChange === 'function') options.onStateChange(nextState)
    }

    function isCurrent(request, generation, context) {
        return !destroyed
            && activeRequest === request
            && request.token === playToken
            && (generation === undefined || request.generation === generation)
            && (!context || audioCtx === context)
    }

    function disposeContext(context) {
        if (!context) return
        try { if (typeof context.stop === 'function') context.stop() } catch (e) {}
        try { if (typeof context.destroy === 'function') context.destroy() } catch (e) {}
    }

    function retireCurrentContext() {
        const context = audioCtx
        audioCtx = null
        disposeContext(context)
    }

    function remember(url, path) {
        if (!url || !path) return
        cache.delete(url)
        cache.set(url, path)
        while (cache.size > maxCacheEntries) {
            const oldest = cache.keys().next().value
            cache.delete(oldest)
        }
    }

    function cachedPath(url) {
        if (!cache.has(url)) return ''
        const path = cache.get(url)
        cache.delete(url)
        cache.set(url, path)
        return path
    }

    function downloadToCache(url, purpose) {
        const cached = cachedPath(url)
        if (cached) return Promise.resolve(cached)
        if (typeof wxApi.downloadFile !== 'function') return Promise.resolve('')
        if (inflightDownloads.has(url)) return inflightDownloads.get(url)

        const promise = new Promise((resolve) => {
            let settled = false
            const record = {
                task: null,
                timerId: null,
                preload: purpose === 'preload'
            }
            const finish = (path) => {
                if (settled) return
                settled = true
                if (record.timerId !== null) {
                    clearTimeout(record.timerId)
                    record.timerId = null
                }
                activeDownloads.delete(url)
                if (record.preload) activePreloadDownloads = Math.max(0, activePreloadDownloads - 1)
                if (path && !destroyed) remember(url, path)
                resolve(path || '')
            }
            record.finish = finish
            activeDownloads.set(url, record)
            maxConcurrentDownloads = Math.max(maxConcurrentDownloads, activeDownloads.size)
            if (record.preload) {
                activePreloadDownloads += 1
                maxConcurrentPreloadDownloads = Math.max(
                    maxConcurrentPreloadDownloads,
                    activePreloadDownloads
                )
            }
            record.timerId = setTimeout(() => {
                if (settled) return
                try {
                    if (record.task && typeof record.task.abort === 'function') record.task.abort()
                } catch (e) {}
                emitEvent('audio_error', {
                    source: url,
                    phase: 'download_timeout',
                    errMsg: 'audio_download_timeout',
                    errCode: 'download_timeout',
                    redirect_info: 'not_available_from_wx_download_api'
                })
                finish('')
            }, downloadTimeoutMs)
            try {
                record.task = wxApi.downloadFile({
                    url,
                    success(result) {
                        if (settled) return
                        const status = Number(result && result.statusCode)
                        const headers = result && result.header
                        const contentType = headers && (headers['Content-Type'] || headers['content-type'])
                        const path = result && (result.tempFilePath || result.filePath)
                        emitEvent('audio_download', {
                            source: url,
                            statusCode: status || undefined,
                            contentType: contentType || undefined,
                            redirect_info: 'not_available_from_wx_download_api'
                        })
                        if (status !== 200 && status !== 206) {
                            emitEvent('audio_error', {
                                source: url,
                                phase: 'download',
                                statusCode: status || undefined,
                                contentType: contentType || undefined,
                                redirect_info: 'not_available_from_wx_download_api'
                            })
                        }
                        finish((status === 200 || status === 206) && path ? path : '')
                    },
                    fail(error) {
                        if (settled) return
                        emitEvent('audio_error', {
                            source: url,
                            phase: 'download',
                            errMsg: error && error.errMsg,
                            errCode: error && error.errCode,
                            redirect_info: 'not_available_from_wx_download_api'
                        })
                        finish('')
                    }
                })
            } catch (error) {
                finish('')
            }
        })
        const tracked = promise.then(
            (path) => {
                inflightDownloads.delete(url)
                return path
            },
            () => {
                inflightDownloads.delete(url)
                return ''
            }
        )
        inflightDownloads.set(url, tracked)
        return tracked
    }

    function failRequest(request, error) {
        if (!isCurrent(request)) return
        clearTimers()
        activeRequest = null
        retireCurrentContext()
        emitState('failed')
        emitEvent('audio_error', {
            source: request && (request.path || request.url),
            source_index: request && request.index,
            source_type: sourceType(request),
            phase: 'playback',
            errMsg: error && error.errMsg
        })
        if (typeof options.onError === 'function') options.onError(error || { errMsg: 'audio_playback_failed' })
    }

    function handleCurrentError(request, generation, context, error) {
        if (!isCurrent(request, generation, context)) return
        if (state === 'playing' || state === 'ended') return
        const message = String((error && error.errMsg) || '')
        if (message.includes('interrupted by a new load request')) return
        const sourceHint = error && (error.src || error.url || error.path)
        if (sourceHint && request.path && String(sourceHint) !== String(request.path)) return
        // Some native callbacks do not include a source URL. The captured
        // context and generation reject callbacks from a replaced attempt.
        let currentContextSource = ''
        try { currentContextSource = String(context.src || '') } catch (e) {}
        if (currentContextSource && request.path && currentContextSource !== String(request.path)) return
        request.lastError = error
        if (request.usingCache) {
            // A broken temporary file must not be retried indefinitely. Remove
            // it and retry the canonical remote source once before fallback.
            cache.delete(request.url)
            request.retryRemote = true
            request.retryRemoteIndex = request.index
        }
        emitEvent('audio_error', {
            source: request.path || request.url,
            source_index: request.index,
            source_type: sourceType(request),
            phase: 'native',
            errMsg: error && error.errMsg,
            errCode: error && error.errCode
        })
        const token = request.token
        clearErrorTimer()
        errorTimer = setTimeout(() => {
            errorTimer = null
            if (!isCurrent(request, generation, context) || token !== playToken) return
            const nextIndex = request.retryRemote ? request.index : request.index + 1
            startCandidate(request, nextIndex, request.retryRemote ? 'remote' : undefined)
        }, errorGraceMs)
    }

    function bindCandidateHandlers(context, request, generation) {
        if (typeof context.onCanplay === 'function') context.onCanplay(() => {
            if (!isCurrent(request, generation, context) || request.started) return
            clearLoadTimer()
            request.started = true
            emitEvent('audio_canplay', {
                source: request.path || request.url,
                source_index: request.index,
                source_type: sourceType(request),
                phase: request.usingCache ? 'cache' : 'remote'
            })
            try { context.play() } catch (error) {
                request.started = false
                handleCurrentError(request, generation, context, error)
            }
        })
        if (typeof context.onPlay === 'function') context.onPlay(() => {
            if (!isCurrent(request, generation, context)) return
            clearTimers()
            request.started = true
            preferredReplayBySet.set(request.sourceKey, request.url)
            emitEvent('audio_play', {
                source: request.path || request.url,
                source_index: request.index,
                source_type: sourceType(request)
            })
            emitState('playing')
        })
        if (typeof context.onEnded === 'function') context.onEnded(() => {
            if (!isCurrent(request, generation, context)) return
            clearTimers()
            emitState('ended')
        })
        if (typeof context.onError === 'function') {
            context.onError((error) => handleCurrentError(request, generation, context, error))
        }
    }

    function createPlaybackContext(request) {
        const context = wxApi.createInnerAudioContext()
        if (!context) throw new Error('inner_audio_unavailable')
        try { context.obeyMuteSwitch = false } catch (e) {}
        try { context.autoplay = false } catch (e) {}
        if (typeof context.onStop === 'function') context.onStop(() => {
            if (
                !destroyed
                && audioCtx === context
                && activeRequest === request
                && state !== 'loading'
                && state !== 'failed'
            ) emitState('idle')
        })
        return context
    }

    function startCandidate(request, index, mode) {
        if (!isCurrent(request) || index >= request.sources.length) {
            failRequest(request, request.lastError)
            return
        }
        clearTimers()
        request.index = index
        request.url = request.sources[index]
        request.generation += 1
        const generation = request.generation
        const forceRemote = mode === 'remote'
            || (request.retryRemote && request.retryRemoteIndex === index)
        request.retryRemote = false
        request.retryRemoteIndex = -1
        // A native context may retain callbacks after a source changes. Retire
        // it before binding the next candidate so every context has exactly
        // one listener set and there is never more than one live context.
        retireCurrentContext()
        try {
            audioCtx = createPlaybackContext(request)
        } catch (error) {
            failRequest(request, error)
            return
        }
        const context = audioCtx
        request.path = ''
        request.started = false
        request.usingCache = false
        request.remoteFallbackStarted = false
        let phase = forceRemote ? 'remote' : 'download'
        bindCandidateHandlers(context, request, generation)

        const launch = (path) => {
            if (!isCurrent(request, generation, context)) return
            phase = path === request.url ? 'remote' : 'local'
            request.usingCache = phase === 'local'
            if (phase === 'remote') request.remoteFallbackStarted = true
            request.path = path || request.url
            try {
                context.src = request.path
            } catch (error) {
                request.lastError = error
                startCandidate(request, index + 1)
                return
            }
            clearLoadTimer()
            loadTimer = setTimeout(() => {
                loadTimer = null
                if (!isCurrent(request, generation, context)) return
                if (phase === 'download') {
                    // A slow download must not strand the UI. Retry the same
                    // URL on a fresh native context; the old download and
                    // context callbacks become harmless through generation.
                    startCandidate(request, index, 'remote')
                    return
                }
                startCandidate(request, index + 1)
            }, loadTimeoutMs)
        }

        if (forceRemote) {
            launch(request.url)
            return
        }
        const cached = cachedPath(request.url)
        if (cached) {
            launch(cached)
            return
        }
        if (typeof wxApi.downloadFile !== 'function') {
            launch(request.url)
            return
        }
        loadTimer = setTimeout(() => {
            loadTimer = null
            if (!isCurrent(request, generation, context)) return
            startCandidate(request, index, 'remote')
        }, loadTimeoutMs)
        downloadToCache(request.url, 'play').then((path) => {
            if (!isCurrent(request, generation, context)) return
            // A remote fallback may already have started while the cache
            // download was still pending. Do not replace a successful native
            // source with that late local callback.
            if (
                request.remoteFallbackStarted
                || request.started
                || state === 'playing'
                || state === 'ended'
            ) return
            clearLoadTimer()
            launch(path || request.url)
        })
    }

    function play(source, baseUrl) {
        const sources = flattenSources(source, baseUrl, [])
        if (!sources.length || destroyed) return false
        clearTimers()
        playToken += 1
        activeRequest = null
        retireCurrentContext()
        const sourceKey = sources.join('\u001f')
        const preferred = preferredReplayBySet.get(sourceKey)
        const orderedSources = preferred && sources.indexOf(preferred) >= 0
            ? [preferred].concat(sources.filter((url) => url !== preferred))
            : sources
        const request = {
            token: playToken,
            sources: orderedSources,
            sourceKey,
            index: -1,
            generation: 0,
            path: '',
            url: '',
            started: false,
            remoteFallbackStarted: false,
            usingCache: false,
            retryRemote: false,
            retryRemoteIndex: -1,
            lastError: null
        }
        activeRequest = request
        emitState('loading')
        startCandidate(request, 0)
        return true
    }

    function preload(source, baseUrl) {
        if (destroyed) return Promise.resolve([])
        const sources = flattenSources(source, baseUrl, []).slice(0, maxCacheEntries)
        const run = () => sources.reduce(
            (chain, url) => chain.then(() => {
                if (destroyed) return undefined
                return downloadToCache(url, 'preload').then((path) => {
                    if (path) loaded.push(url)
                })
            }),
            Promise.resolve()
        ).then(() => loaded)
        const loaded = []
        const result = preloadChain.then(run)
        preloadChain = result.catch(() => [])
        return result
    }

    function destroy() {
        if (destroyed) return
        destroyed = true
        playToken += 1
        activeRequest = null
        clearTimers()
        Array.from(activeDownloads.values()).forEach((record) => {
            try {
                if (record.task && typeof record.task.abort === 'function') record.task.abort()
            } catch (e) {}
            if (typeof record.finish === 'function') record.finish('')
        })
        retireCurrentContext()
    }

    return {
        play,
        preload,
        destroy,
        get context() { return audioCtx },
        getState: () => state,
        cacheSize: () => cache.size,
        maxCacheEntries,
        stats: () => ({
            cacheEntries: cache.size,
            maxCacheEntries,
            inflightDownloads: activeDownloads.size,
            maxConcurrentDownloads,
            activePreloadDownloads,
            maxConcurrentPreloadDownloads,
            downloadTimeoutMs
        })
    }
}

module.exports = { resolveAudioUrl, createReliableAudioPlayer }
