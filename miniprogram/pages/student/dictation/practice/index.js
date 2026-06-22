const app = getApp()
const {
    buildGroupPlans,
    findGroupIndex,
    groupBounds,
    normalizeGroupSizes
} = require('../../../../utils/dictation-groups.js')
const { isEnglishAnswerCorrect } = require('../../../../utils/dictation-answers.js')

const MODE_AUDIO_TO_EN = 'audio_to_en'
const MODE_ZH_TO_EN = 'zh_to_en'
const MODE_EN_TO_ZH = 'en_to_zh'
const MODE_SPELLING_DRILL = 'spelling_drill'
const AUDIO_SLOW_FALLBACK_MS = 3500
const AUDIO_FAMILIARIZE_FALLBACK_MS = 1200
const AUDIO_PREFETCH_AHEAD = 4
const AUDIO_PREWARM_LIMIT = 60

function resolveDictationMode(dictationMode, bookType) {
    const mode = String(dictationMode || '').trim().toLowerCase()
    if ([MODE_AUDIO_TO_EN, MODE_ZH_TO_EN, MODE_EN_TO_ZH].includes(mode)) {
        return mode
    }
    return String(bookType || '').trim().toLowerCase() === 'translation'
        ? MODE_ZH_TO_EN
        : MODE_AUDIO_TO_EN
}

function isAudioMode(mode) {
    return mode === MODE_AUDIO_TO_EN
}

function normalizeChineseAnswer(value) {
    return String(value || '')
        .trim()
        .replace(/^(?:n|v|vt|vi|adj|adv|prep|conj|pron|phr)\.\s*/ig, '')
        .replace(/[()（）【】\[\]「」『』"'`]/g, '')
        .replace(/\s+/g, '')
        .replace(/[，,。.!！？?：:]/g, '')
        .toLowerCase()
}

function chineseVariants(value) {
    const source = String(value || '')
        .replace(/\r?\n/g, '；')
        .replace(/^(?:n|v|vt|vi|adj|adv|prep|conj|pron|phr)\.\s*/ig, '')
    const variants = new Set()
    source.split(/\s*(?:[；;、/]|,(?=[\u4e00-\u9fff]))\s*/).forEach(part => {
        const item = normalizeChineseAnswer(part)
        if (item) variants.add(item)
    })
    const full = normalizeChineseAnswer(source)
    if (full) variants.add(full)
    return Array.from(variants)
}

function notebookEntryKey(item) {
    const word = String(item.word || '').toLowerCase().trim()
    if (!word) return ''
    return `${word}::${item.dictationMode || MODE_AUDIO_TO_EN}`
}

function audioCacheKey(word) {
    return String(word || '').trim().toLowerCase()
}

function directYoudaoAudioUrl(word) {
    return `https://dict.youdao.com/dictvoice?audio=${encodeURIComponent(word)}&type=2`
}

Page({
    data: {
        bookId: null,
        bookTitle: '听写练习',
        words: [],
        currentIndex: 0,
        currentWord: {},
        totalWords: 0,
        progressKey: null,
        wrongWords: [],
        wrongWordsDetail: [],
        correctCount: 0,
        userAnswer: '',
        inputError: false,
        autoPlay: false,
        practiceStart: null,
        accumulatedSeconds: 0,
        isSubmitting: false,
        displayTime: '00:00',
        ticker: null,
        isLoadingAudio: false,
        playToken: 0,
        reviewingWrongWords: false,
        finished: false,
        summaryInfo: null,

        // Familiarization phase
        phase: 'loading',       // loading | group_select | familiarize | test | group_summary
        famIndex: 0,
        famRevealed: false,
        famTimerSeconds: 1200,  // 20 minutes
        famTimerDisplay: '20:00',

        // Optional grouping for a single assigned task.
        groupPlans: [],
        selectedGroupPlanKey: '',
        groupSizes: [],
        currentGroupIndex: 0,
        groupCount: 1,
        groupStart: 0,
        groupEnd: 0,
        groupWordCount: 0,
        hasMoreGroups: false,
        groupCorrectStart: 0,
        groupWrongStart: 0,
        groupSummaryInfo: null,

        // UI State
        inputValue: '',
        showResult: false,
        isCorrect: false,
        inputFocus: true,
        showHint: false,
        attemptCount: 0,
        dictationMode: MODE_AUDIO_TO_EN,
        currentMode: MODE_AUDIO_TO_EN,
        appealSubmitted: false
    },

    onLoad: function (options) {
        if (options.mode === 'retry_wrong') {
            // Launched from notebook or home for wrong-word practice
            this._initRetryWrongWords(options.source || 'last');
        } else if (options.taskId) {
            this.setData({ taskId: options.taskId });
            this.fetchTask(options.taskId);
        } else if (options.id) {
            this.setData({ bookId: options.id });
            this.fetchWords(options.id);
        }

        // Prepare progress key once we know taskId/bookId later
        if (options.taskId || options.id) {
            this.setData({ progressKey: this.buildProgressKey(options.taskId, options.id) });
        }

        // Load notebook count
        this.loadNotebookCount();
        this.loadLastWrong();

        // Create Audio Context
        wx.setInnerAudioOption({
            obeyMuteSwitch: false,
            speakerOn: true
        });
        wx.setInnerAudioOption({
            obeyMuteSwitch: false,
            speakerOn: true
        });
        this.audioCtx = wx.createInnerAudioContext();
        this.audioCtx.obeyMuteSwitch = false;
        this.audioCtx.autoplay = false;
        this.audioFileCache = {};
        this.playTokenCounter = 0;
        this.pendingPlayToken = null;
        this.currentDownloadTask = null;
        this.audioFallbackTimer = null;
        this.currentAudioCacheKey = null;
        this.activeAudioPath = null;
        this.audioCtx.onCanplay(() => {
            if (this.pendingPlayToken && this.pendingPlayToken === this.playTokenCounter) {
                this.pendingPlayToken = null;
                this.audioCtx.play();
            }
        });
        this.audioCtx.onPlay(() => {
            this.setData({ isLoadingAudio: false });
        });
        this.audioCtx.onStop(() => {
            this.setData({ isLoadingAudio: false });
        });
        this.audioCtx.onError((res) => {
            const errMsg = res && res.errMsg ? String(res.errMsg) : '';
            if (errMsg.includes('interrupted by a new load request')) {
                return;
            }
            if (this.pendingPlayToken !== this.playTokenCounter) {
                return;
            }
            console.error('Audio Error:', errMsg);
            if (!this.fallbackTried && this.data.currentWord.word) {
                this.fallbackTried = true;
                const trimmed = this.data.currentWord.word.trim();
                this.downloadAndPlay(directYoudaoAudioUrl(trimmed), trimmed, this.playTokenCounter, true, {
                    cacheKey: this.currentAudioCacheKey
                });
                return;
            }
            this.setData({ isLoadingAudio: false });
            wx.showToast({ title: '音频播放失败', icon: 'none' });
        });
        this.audioCtx.onEnded(() => {
            if (this.data.autoPlay && this.data.showResult) {
                this.nextWord();
            }
        });
    },

    fetchTask: function (taskId) {
        wx.showLoading({ title: '加载任务...' });
        this.startBackendTimer(taskId);
        wx.request({
            url: `${app.globalData.baseUrl}/miniprogram/student/tasks/${taskId}`,
            method: 'GET',
            header: {
                'Cookie': wx.getStorageSync('cookie'),
                'Authorization': `Bearer ${wx.getStorageSync('token')}`
            },
            success: (res) => {
                if (res.data.ok) {
                    const task = res.data.task;
                    const rawMode = String(task.dictation_mode || '').trim().toLowerCase();
                    if (rawMode === MODE_SPELLING_DRILL) {
                        wx.hideLoading();
                        wx.redirectTo({
                            url: `/pages/student/dictation/spell/index?taskId=${taskId}`
                        });
                        return;
                    }
                    const dictationMode = resolveDictationMode(task.dictation_mode, task.dictation_book_type);

                    // Read from root task object
                    this.setData({
                        bookTitle: task.task_name,
                        rangeStart: task.dictation_word_start,
                        rangeEnd: task.dictation_word_end,
                        dictationMode: dictationMode,
                        currentMode: dictationMode
                    });
                    this.setData({ progressKey: this.buildProgressKey(taskId, task.dictation_book_id, task.dictation_word_start, task.dictation_word_end) });

                    if (task.dictation_book_id) {
                        this.setData({ bookId: task.dictation_book_id });
                        this.fetchWords(task.dictation_book_id);
                    } else {
                        wx.hideLoading();
                        wx.showToast({ title: '任务配置错误: dictation_book_id missing', icon: 'none' });
                    }
                } else {
                    wx.hideLoading();
                    console.log('API Error Data:', res.data);
                    let msg = '';
                    if (typeof res.data === 'string') {
                        msg = 'Server Error (HTML/String)';
                    } else {
                        msg = res.data.message || res.data.error || 'Unknown Error';
                    }
                    wx.showToast({ title: 'Err: ' + msg, icon: 'none' });
                }
            },
            fail: (err) => {
                wx.hideLoading();
                console.error(err);
                wx.showToast({ title: 'Network Error', icon: 'none' });
            }
        });
    },

    startBackendTimer(taskId) {
        if (!taskId) return;
        wx.request({
            url: `${app.globalData.baseUrl}/miniprogram/student/tasks/${taskId}/timer/start`,
            method: 'POST',
            header: {
                'Cookie': wx.getStorageSync('cookie'),
                'Authorization': `Bearer ${wx.getStorageSync('token')}`
            },
            fail: (err) => {
                console.warn('start timer failed', err);
            }
        });
    },

    fetchWords: function (id) {
        if (!this.data.taskId) wx.showLoading({ title: '加载单词...' });

        const url = `${app.globalData.baseUrl}/dictation/books/${id}`;
        console.log("fetchWords Requesting:", url);
        console.log("Authorization:", `Bearer ${wx.getStorageSync('token')}`);

        wx.request({
            url: url,
            method: 'GET',
            header: {
                'Cookie': wx.getStorageSync('cookie'),
                'Authorization': `Bearer ${wx.getStorageSync('token')}`
            },
            success: (res) => {
                wx.hideLoading();
                if (res.data.ok) {
                    let words = res.data.words;
                    console.log('Fetched words:', words.length);

                    // Apply Range Filter if set
                    if (this.data.rangeStart || this.data.rangeEnd) {
                        const start = (this.data.rangeStart || 1) - 1; // 0-based
                        const end = this.data.rangeEnd || words.length;
                        console.log('Filtering range:', start, end);
                        words = words.slice(start, end);
                    }
                    console.log('Final words:', words.length);

                    if (words.length === 0) {
                        wx.showModal({
                            title: '提示',
                            content: '该范围内没有单词 (或加载失败)',
                            showCancel: false,
                            success: () => wx.navigateBack()
                        });
                        return;
                    }

                    const bookType = res.data.book.book_type || 'dictation';
                    const dictationMode = this.data.taskId
                        ? resolveDictationMode(this.data.dictationMode, bookType)
                        : resolveDictationMode('', bookType);
                    words = words.map(word => ({
                        ...word,
                        dictationMode
                    }))

                    this.setData({
                        // Only update title if not set by task
                        bookTitle: this.data.taskId ? this.data.bookTitle : res.data.book.title,
                        words: words,
                        totalWords: words.length,
                        currentIndex: 0,
                        practiceStart: null,
                        accumulatedSeconds: 0,
                        dictationMode,
                        currentMode: dictationMode
                    });

                    if (isAudioMode(dictationMode)) {
                        this.requestServerTtsPrewarm(words);
                        this.prefetchAudioWindow(0);
                    }

                    const groupPlans = buildGroupPlans(words.length);
                    const selectedPlan = groupPlans.find(plan => plan.recommended) || groupPlans[0];
                    this.setData({
                        groupPlans,
                        selectedGroupPlanKey: selectedPlan ? selectedPlan.key : ''
                    });

                    const saved = this.loadProgress(words.length);
                    if (!saved) {
                        this.setData({ phase: 'group_select' });
                        return;
                    }

                    const savedSizes = normalizeGroupSizes(saved.groupSizes, words.length);
                    const savedIndex = Math.max(0, Math.min(Number(saved.index) || 0, words.length - 1));
                    let savedGroupIndex = Number.isInteger(saved.groupIndex)
                        ? saved.groupIndex
                        : findGroupIndex(savedSizes, savedIndex);
                    if (saved.awaitingNextGroup && savedGroupIndex < savedSizes.length - 1) {
                        savedGroupIndex += 1;
                    }
                    this.activateGroup(savedSizes, savedGroupIndex, {
                        correctStart: saved.awaitingNextGroup ? this.data.correctCount : saved.groupCorrectStart,
                        wrongStart: saved.awaitingNextGroup ? this.data.wrongWordsDetail.length : saved.groupWrongStart
                    }, () => {
                        if (saved.awaitingNextGroup || saved.resumePhase === 'familiarize') {
                            this.enterFamiliarization();
                            return;
                        }
                        this.setData({ phase: 'test', practiceStart: Date.now() });
                        this.loadWord(savedIndex);
                        this.startTicker();
                    });
                } else {
                    wx.showToast({ title: '加载失败', icon: 'none' });
                }
            },
            fail: () => {
                wx.hideLoading();
                wx.showToast({ title: '网络错误', icon: 'none' });
            }
        });
    },

    loadWord: function (index) {
        const word = this.data.words[index];
        const currentMode = resolveDictationMode(word && word.dictationMode, this.data.dictationMode);
        this.setData({
            currentWord: word,
            currentIndex: index,
            currentMode: currentMode,
            inputValue: '',
            showResult: false,
            isCorrect: false,
            inputFocus: true,
            inputError: false,
            userAnswer: '',
            showHint: false,
            attemptCount: 0,
            appealSubmitted: false
        });
        this.saveProgress(index);

        if (isAudioMode(currentMode)) {
            setTimeout(() => {
                this.playCurrentWord();
            }, 500);
            this.prefetchAudioWindow(index + 1);
        }
    },

    playCurrentWord: function (force) {
        if (!force && !isAudioMode(this.data.currentMode)) return;
        const word = this.data.currentWord.word;
        if (!word) return;

        const trimmed = word.trim();
        this.fallbackTried = false;
        this.playTokenCounter = (this.playTokenCounter || 0) + 1;
        const token = this.playTokenCounter;
        const cacheKey = audioCacheKey(trimmed);
        this.pendingPlayToken = token;
        this.currentAudioCacheKey = cacheKey;
        this.setData({ isLoadingAudio: true, playToken: token });

        this.abortAudioDownload();
        if (this.audioCtx && this.audioCtx.src) {
            try {
                this.audioCtx.stop();
            } catch (e) {}
        }

        const cached = this.audioFileCache && this.audioFileCache[cacheKey];
        if (cached && cached.status === 'ready' && cached.tempFilePath) {
            this.playPreparedAudio(cached.tempFilePath, token);
            this.prefetchAudioWindow(this.nextAudioPrefetchIndex());
            return;
        }

        const proxyUrl = `${app.globalData.baseUrl}/dictation/tts?word=${encodeURIComponent(trimmed)}`;
        this.downloadAndPlay(proxyUrl, trimmed, token, false, {
            cacheKey,
            allowSlowFallback: true,
            fallbackDelayMs: this.data.phase === 'familiarize'
                ? AUDIO_FAMILIARIZE_FALLBACK_MS
                : AUDIO_SLOW_FALLBACK_MS
        });
        this.prefetchAudioWindow(this.nextAudioPrefetchIndex());
    },

    abortAudioDownload() {
        this.clearAudioFallbackTimer();
        if (this.currentDownloadTask && this.currentDownloadTask.abort) {
            try {
                this.currentDownloadTask.abort();
            } catch (e) {}
        }
        this.currentDownloadTask = null;
    },

    clearAudioFallbackTimer() {
        if (this.audioFallbackTimer) {
            clearTimeout(this.audioFallbackTimer);
            this.audioFallbackTimer = null;
        }
    },

    startSlowFallbackTimer(word, token, cacheKey, delayMs = AUDIO_SLOW_FALLBACK_MS) {
        this.clearAudioFallbackTimer();
        this.audioFallbackTimer = setTimeout(() => {
            this.audioFallbackTimer = null;
            if (token !== this.playTokenCounter || this.fallbackTried) return;
            this.fallbackTried = true;
            this.downloadAndPlay(directYoudaoAudioUrl(word), word, token, true, { cacheKey });
        }, delayMs);
    },

    playPreparedAudio(tempFilePath, token) {
        if (!tempFilePath || !this.audioCtx || token !== this.playTokenCounter) {
            return;
        }

        if (this.activeAudioPath === tempFilePath) {
            this.pendingPlayToken = null;
            try {
                this.audioCtx.pause();
            } catch (e) {}
            try {
                this.audioCtx.seek(0);
            } catch (e) {}
            setTimeout(() => {
                if (
                    !this.audioCtx
                    || token !== this.playTokenCounter
                    || this.activeAudioPath !== tempFilePath
                ) {
                    return;
                }
                try {
                    this.audioCtx.play();
                } catch (e) {
                    this.pendingPlayToken = token;
                    this.activeAudioPath = null;
                    this.audioCtx.src = tempFilePath;
                }
            }, 120);
            return;
        }

        this.pendingPlayToken = token;
        this.activeAudioPath = tempFilePath;
        this.audioCtx.src = tempFilePath;
    },

    downloadAndPlay(url, word, token, isFallback, options = {}) {
        this.abortAudioDownload();
        let downloadTask = null;
        downloadTask = wx.downloadFile({
            url: url,
            success: (res) => {
                if (this.currentDownloadTask === downloadTask) {
                    this.currentDownloadTask = null;
                }
                if (token !== this.playTokenCounter) return;
                this.clearAudioFallbackTimer();
                if (res.statusCode === 200 && res.tempFilePath) {
                    if (options.cacheKey) {
                        this.audioFileCache[options.cacheKey] = {
                            status: 'ready',
                            tempFilePath: res.tempFilePath
                        };
                    }
                    this.playPreparedAudio(res.tempFilePath, token);
                } else if (!isFallback && !this.fallbackTried) {
                    this.fallbackTried = true;
                    this.downloadAndPlay(directYoudaoAudioUrl(word), word, token, true, options);
                } else if (!isFallback) {
                    return;
                } else {
                    this.setData({ isLoadingAudio: false });
                    wx.showToast({ title: '音频获取失败', icon: 'none' });
                }
            },
            fail: () => {
                if (this.currentDownloadTask === downloadTask) {
                    this.currentDownloadTask = null;
                }
                if (token !== this.playTokenCounter) return;
                this.clearAudioFallbackTimer();
                if (!isFallback && !this.fallbackTried) {
                    this.fallbackTried = true;
                    this.downloadAndPlay(directYoudaoAudioUrl(word), word, token, true, options);
                } else if (!isFallback) {
                    return;
                } else {
                    this.setData({ isLoadingAudio: false });
                    wx.showToast({ title: '音频获取失败', icon: 'none' });
                }
            }
        });
        this.currentDownloadTask = downloadTask;
        if (options.allowSlowFallback && !isFallback) {
            this.startSlowFallbackTimer(
                word,
                token,
                options.cacheKey,
                options.fallbackDelayMs || AUDIO_SLOW_FALLBACK_MS
            );
        }
    },

    prefetchAudioWindow(startIndex) {
        const words = this.data.words || [];
        if (!words.length) return;
        for (let offset = 0; offset < AUDIO_PREFETCH_AHEAD; offset++) {
            const item = words[startIndex + offset];
            if (!item) break;
            const mode = resolveDictationMode(item.dictationMode, this.data.dictationMode);
            if (isAudioMode(mode)) {
                this.prefetchAudioForWord(item.word);
            }
        }
    },

    nextAudioPrefetchIndex() {
        if (this.data.phase === 'familiarize') {
            return (this.data.famIndex || 0) + 1;
        }
        return (this.data.currentIndex || 0) + 1;
    },

    prefetchAudioForWord(word) {
        const trimmed = String(word || '').trim();
        if (!trimmed) return;
        const cacheKey = audioCacheKey(trimmed);
        const existing = this.audioFileCache && this.audioFileCache[cacheKey];
        if (existing && (existing.status === 'ready' || existing.status === 'loading')) {
            return;
        }
        const cacheRecord = { status: 'loading' };
        this.audioFileCache[cacheKey] = cacheRecord;
        const url = `${app.globalData.baseUrl}/dictation/tts?word=${encodeURIComponent(trimmed)}`;
        const task = wx.downloadFile({
            url,
            success: (res) => {
                if (res.statusCode === 200 && res.tempFilePath) {
                    this.audioFileCache[cacheKey] = {
                        status: 'ready',
                        tempFilePath: res.tempFilePath
                    };
                } else {
                    delete this.audioFileCache[cacheKey];
                }
            },
            fail: () => {
                delete this.audioFileCache[cacheKey];
            }
        });
        cacheRecord.task = task;
    },

    abortAudioPrefetches() {
        const cache = this.audioFileCache || {};
        Object.keys(cache).forEach(key => {
            const item = cache[key];
            if (item && item.status === 'loading' && item.task && item.task.abort) {
                try {
                    item.task.abort();
                } catch (e) {}
                delete cache[key];
            }
        });
    },

    requestServerTtsPrewarm(words) {
        const targets = [];
        const seen = {};
        (words || []).forEach(item => {
            const mode = resolveDictationMode(item && item.dictationMode, this.data.dictationMode);
            const word = String(item && item.word || '').trim();
            const key = audioCacheKey(word);
            if (!word || (mode !== MODE_AUDIO_TO_EN && mode !== MODE_ZH_TO_EN) || seen[key]) return;
            seen[key] = true;
            targets.push(word);
        });
        if (!targets.length) return;
        wx.request({
            url: `${app.globalData.baseUrl}/dictation/tts/prewarm`,
            method: 'POST',
            header: {
                'Cookie': wx.getStorageSync('cookie'),
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${wx.getStorageSync('token')}`
            },
            data: {
                words: targets.slice(0, AUDIO_PREWARM_LIMIT)
            },
            fail: (err) => {
                console.warn('dictation tts prewarm failed', err);
            }
        });
    },

    onToggleAutoPlay(e) {
        this.setData({ autoPlay: e.detail.value });
    },

    onInput: function (e) {
        this.setData({
            inputValue: e.detail.value,
            inputError: false
        });
    },

    checkAnswer: function () {
        if (this.data.showResult) return;

        const inputRaw = this.data.inputValue.trim();
        const mode = this.data.currentMode || MODE_AUDIO_TO_EN;
        let isCorrect = false;
        if (mode === MODE_AUDIO_TO_EN) {
            isCorrect = isEnglishAnswerCorrect(inputRaw, this.data.currentWord);
        } else if (mode === MODE_ZH_TO_EN) {
            isCorrect = isEnglishAnswerCorrect(inputRaw, this.data.currentWord);
        } else {
            const input = normalizeChineseAnswer(inputRaw);
            isCorrect = chineseVariants(this.data.currentWord.translation).some(variant => (
                input === variant
                || (input.length >= 2 && (variant.includes(input) || input.includes(variant)))
            ));
        }
        const attempts = this.data.attemptCount || 0;

        if (!inputRaw) {
            wx.showToast({ title: '请输入答案', icon: 'none' });
            return;
        }

        if (isCorrect) {
            if (attempts === 0) {
                this.setData({ correctCount: this.data.correctCount + 1 });
            }
            this.setData({
                showResult: true,
                isCorrect: true,
                userAnswer: inputRaw,
                inputError: false,
                attemptCount: attempts + 1
            });
            wx.showToast({ title: '正确!', icon: 'success', duration: 1000 });
            if (mode === MODE_ZH_TO_EN) this.playCurrentWord(true);
            return;
        }

        if (attempts === 0) {
            const wrongList = this.data.wrongWords;
            const wrongDetail = this.data.wrongWordsDetail;
            wrongList.push(`${this.data.currentWord.word} (写成了: ${inputRaw})`);
            wrongDetail.push({
                id: this.data.currentWord.id,
                word_id: this.data.currentWord.word_id,
                word: this.data.currentWord.word,
                translation: this.data.currentWord.translation,
                phonetic: this.data.currentWord.phonetic,
                core_meaning_zh: this.data.currentWord.core_meaning_zh,
                usage_pattern: this.data.currentWord.usage_pattern,
                example_en: this.data.currentWord.example_en,
                example_zh: this.data.currentWord.example_zh,
                usage_note: this.data.currentWord.usage_note,
                accepted_answers: this.data.currentWord.accepted_answers || [],
                wrong: inputRaw,
                dictationMode: mode
            });
            this.setData({
                wrongWords: wrongList,
                wrongWordsDetail: wrongDetail,
                showHint: mode === MODE_AUDIO_TO_EN,
                inputValue: '',
                inputError: true,
                attemptCount: attempts + 1,
                inputFocus: true
            });
            wx.showToast({ title: '再试一次', icon: 'none' });
            return;
        }

        this.setData({
            showResult: true,
            isCorrect: false,
            userAnswer: inputRaw,
            inputError: true,
            attemptCount: attempts + 1
        });
        if (mode === MODE_ZH_TO_EN) this.playCurrentWord(true);
    },

    reportExample: function (e) {
        const wordId = e.currentTarget.dataset.id;
        if (!wordId) return;
        wx.request({
            url: `${app.globalData.baseUrl}/dictation/example/report/${wordId}`,
            method: 'POST',
            header: {
                'Cookie': wx.getStorageSync('cookie'),
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${wx.getStorageSync('token')}`
            },
            success: (res) => {
                if (res.data && res.data.ok) {
                    wx.showToast({ title: '已反馈，助教会复审', icon: 'none' });
                } else {
                    wx.showToast({ title: '反馈失败', icon: 'none' });
                }
            },
            fail: () => {
                wx.showToast({ title: '网络错误', icon: 'none' });
            }
        });
    },

    submitAnswerAppeal: function () {
        if (this.data.appealSubmitted || this.data.isCorrect) return;
        const word = this.data.currentWord || {};
        const answer = String(this.data.userAnswer || '').trim();
        if (!word.id || !answer) return;
        wx.showModal({
            title: '申请人工复核',
            content: `你的答案“${answer}”将提交给老师审核。`,
            confirmText: '提交申诉',
            success: (modalRes) => {
                if (!modalRes.confirm) return;
                wx.request({
                    url: `${app.globalData.baseUrl}/dictation/appeals`,
                    method: 'POST',
                    header: {
                        'Cookie': wx.getStorageSync('cookie'),
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${wx.getStorageSync('token')}`
                    },
                    data: {
                        word_id: word.id,
                        task_id: this.data.taskId,
                        answer: answer,
                        mode: this.data.currentMode
                    },
                    success: (res) => {
                        if (res.data && res.data.ok) {
                            this.setData({ appealSubmitted: true });
                            wx.showToast({ title: '已提交人工审核', icon: 'none' });
                            return;
                        }
                        const title = res.data && res.data.error === 'answer_already_accepted'
                            ? '该答案现已可接受'
                            : '申诉提交失败';
                        wx.showToast({ title, icon: 'none' });
                    },
                    fail: () => wx.showToast({ title: '网络错误', icon: 'none' })
                });
            }
        });
    },

    nextWord: function () {
        const nextIndex = this.data.currentIndex + 1;
        const groupEnd = this.data.groupEnd || this.data.totalWords;
        if (nextIndex < groupEnd) {
            this.loadWord(nextIndex);
        } else if (this.data.hasMoreGroups) {
            this.finishCurrentGroup();
        } else {
            this.finishPractice();
        }
    },

    finishCurrentGroup() {
        this.pauseTimer();
        this.stopTicker();
        const total = this.data.groupWordCount;
        const correct = Math.max(0, this.data.correctCount - this.data.groupCorrectStart);
        const wrongCount = Math.max(0, this.data.wrongWordsDetail.length - this.data.groupWrongStart);
        const accuracy = total > 0 ? ((correct / total) * 100).toFixed(1) : 0;
        this.setData({
            phase: 'group_summary',
            groupSummaryInfo: {
                groupNumber: this.data.currentGroupIndex + 1,
                groupCount: this.data.groupCount,
                total,
                correct,
                wrongCount,
                accuracy,
                nextCount: this.data.groupSizes[this.data.currentGroupIndex + 1] || 0
            }
        });
        this.saveProgress(Math.max(this.data.groupStart, this.data.groupEnd - 1), {
            awaitingNextGroup: true,
            resumePhase: 'group_summary'
        });
    },

    continueNextGroup() {
        const nextGroupIndex = this.data.currentGroupIndex + 1;
        if (nextGroupIndex >= this.data.groupCount) {
            this.finishPractice();
            return;
        }
        this.activateGroup(this.data.groupSizes, nextGroupIndex, {
            correctStart: this.data.correctCount,
            wrongStart: this.data.wrongWordsDetail.length
        }, () => {
            this.saveProgress(this.data.groupStart, {
                awaitingNextGroup: false,
                resumePhase: 'familiarize'
            });
            this.enterFamiliarization();
        });
    },

    leaveBetweenGroups() {
        wx.navigateBack();
    },

    finishPractice: function () {
        const total = this.data.totalWords;
        const correct = this.data.correctCount;
        const accuracy = total > 0 ? ((correct / total) * 100).toFixed(1) : 0;
        const durationSeconds = this.computeDurationSeconds();

        if (this.data.reviewingWrongWords) {
            // 从错词本中移除本次答对的单词
            this._removeCorrectWordsFromNotebook();
            const stillWrong = this.data.wrongWordsDetail.length;
            const msg = stillWrong > 0
                ? `答对 ${correct}/${total}，仍有 ${stillWrong} 词待巩固`
                : `全部答对！已从错词本移除`;
            wx.showModal({
                title: '错词练习完成',
                content: msg,
                showCancel: false,
                success: () => wx.navigateBack()
            });
            return;
        }

        const summaryInfo = {
            accuracy,
            correct,
            total,
            wrongCount: this.data.wrongWordsDetail.length
        };
        // 保存最后一次错词列表，便于离开页面后再重练
        if (this.data.wrongWordsDetail.length > 0) {
            try {
                wx.setStorageSync('dictation_last_wrong', this.data.wrongWordsDetail);
            } catch (e) {
                console.warn('save last wrong failed', e);
            }
        }

        // 如果有任务，先提交，再展示摘要
        if (this.data.taskId) {
            this.submitTaskResult(accuracy, this.data.wrongWords, durationSeconds, {
                keepOpen: true,
                onSuccess: () => {
                    if (this.data.wrongWordsDetail.length > 0) {
                        this.appendToNotebook(this.data.wrongWordsDetail);
                    }
                    this.setData({
                        finished: true,
                        summaryInfo
                    });
                    wx.showToast({ title: '提交成功', icon: 'success' });
                }
            });
        } else {
            if (this.data.wrongWordsDetail.length > 0) {
                this.appendToNotebook(this.data.wrongWordsDetail);
            }
            this.setData({
                finished: true,
                summaryInfo
            });
            wx.showToast({ title: '练习结束', icon: 'success' });
        }
    },

    computeDurationSeconds() {
        let elapsed = this.data.accumulatedSeconds;
        if (this.data.practiceStart) {
            elapsed += Math.floor((Date.now() - this.data.practiceStart) / 1000);
        }
        return elapsed;
    },

    submitTaskResult: function (accuracy, wrongWords, durationSeconds = 0, options = {}) {
        if (this.data.isSubmitting) return;
        this.setData({ isSubmitting: true });
        wx.showLoading({ title: '提交中...' });
        wx.request({
            url: `${app.globalData.baseUrl}/miniprogram/student/tasks/${this.data.taskId}/submit`,
            method: 'POST',
            header: {
                'Cookie': wx.getStorageSync('cookie'),
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${wx.getStorageSync('token')}`
            },
            data: {
                accuracy: accuracy,
                wrong_words: wrongWords.join(', '),
                duration_seconds: durationSeconds
            },
            success: (res) => {
                wx.hideLoading();
                if (res.data.ok) {
                    this.clearProgress();
                    if (options.onSuccess) {
                        options.onSuccess();
                    }
                    if (!options.keepOpen) {
                        setTimeout(() => wx.navigateBack(), 1500);
                    }
                } else {
                    wx.showToast({ title: '提交失败', icon: 'none' });
                }
            },
            fail: () => {
                wx.hideLoading();
                wx.showToast({ title: '网络错误', icon: 'none' });
            },
            complete: () => {
                this.setData({ isSubmitting: false });
            }
        });
    },

    // --- Progress Persistence ---
    buildProgressKey(taskId, bookId, start, end) {
        const startVal = start || this.data.rangeStart || '';
        const endVal = end || this.data.rangeEnd || '';
        if (taskId) return `dictation_progress_task_${taskId}_${startVal}_${endVal}`;
        if (bookId) return `dictation_progress_book_${bookId}_${startVal}_${endVal}`;
        return null;
    },

    saveProgress(index, extraData = {}) {
        if (!this.data.progressKey) return;
        let elapsed = this.data.accumulatedSeconds || 0;
        if (this.data.practiceStart) {
            elapsed += Math.floor((Date.now() - this.data.practiceStart) / 1000);
        }
        wx.setStorageSync(this.data.progressKey, Object.assign({
            index,
            correctCount: this.data.correctCount,
            wrongWords: this.data.wrongWords,
            wrongWordsDetail: this.data.wrongWordsDetail,
            accumulatedSeconds: elapsed,
            groupSizes: this.data.groupSizes,
            groupIndex: this.data.currentGroupIndex,
            groupCorrectStart: this.data.groupCorrectStart,
            groupWrongStart: this.data.groupWrongStart,
            awaitingNextGroup: false,
            resumePhase: 'test'
        }, extraData));
    },

    loadProgress(totalWords) {
        if (!this.data.progressKey) return null;
        const saved = wx.getStorageSync(this.data.progressKey);
        if (saved && typeof saved.index === 'number') {
            const idx = Math.max(0, Math.min(saved.index, totalWords - 1));
            // Restore accumulated results from previous sessions
            if (saved.correctCount != null) {
                this.setData({
                    correctCount: saved.correctCount,
                    wrongWords: saved.wrongWords || [],
                    wrongWordsDetail: saved.wrongWordsDetail || []
                });
            }
            if (saved.accumulatedSeconds) {
                this.setData({ accumulatedSeconds: saved.accumulatedSeconds });
            }
            return Object.assign({}, saved, { index: idx });
        }
        return null;
    },

    clearProgress() {
        if (!this.data.progressKey) return;
        try {
            wx.removeStorageSync(this.data.progressKey);
        } catch (e) {
            console.warn('Failed to clear progress', e);
        }
        this.stopTicker();
    },

    // 生命周期：隐藏/卸载时累计时间
    onHide() {
        this.pauseTimer();
        this.stopTicker();
        this.stopFamTimer();
    },

    onShow() {
        if (this.data.phase === 'familiarize' && this.data.famTimerSeconds > 0) {
            this.startFamTimer();
        } else if (this.data.phase === 'test') {
            this.resumeTimer();
        }
    },

    onUnload() {
        this.pauseTimer();
        this.stopTicker();
        this.stopFamTimer();
        this.abortAudioDownload();
        this.abortAudioPrefetches();
        if (this.audioCtx) {
            this.audioCtx.destroy();
            this.audioCtx = null;
        }
    },

    pauseTimer() {
        if (this.data.practiceStart) {
            const elapsed = Math.floor((Date.now() - this.data.practiceStart) / 1000);
            this.setData({
                accumulatedSeconds: this.data.accumulatedSeconds + elapsed,
                practiceStart: null
            });
        }
    },

    resumeTimer() {
        if (!this.data.practiceStart) {
            this.setData({ practiceStart: Date.now() });
        }
        this.startTicker();
    },

    // 从 onLoad 启动错词重练（由错词本或首页发起）
    _initRetryWrongWords(source) {
        let wrongDetail = [];
        const storageKey = source === 'notebook' ? 'dictation_notebook' : 'dictation_last_wrong';
        try {
            const saved = wx.getStorageSync(storageKey) || [];
            if (Array.isArray(saved) && saved.length) {
                wrongDetail = saved;
            }
        } catch (e) {
            console.warn('load wrong words failed', e);
        }
        if (!wrongDetail.length) {
            wx.showToast({ title: '没有错词可重练', icon: 'none' });
            setTimeout(() => wx.navigateBack(), 1200);
            return;
        }
        const wrongOnly = wrongDetail.map((w, idx) => ({
            id: w.id || w.word_id || null,
            word: w.word,
            translation: w.translation,
            phonetic: w.phonetic,
            core_meaning_zh: w.core_meaning_zh,
            usage_pattern: w.usage_pattern,
            example_en: w.example_en,
            example_zh: w.example_zh,
            usage_note: w.usage_note,
            accepted_answers: w.accepted_answers || [],
            dictationMode: resolveDictationMode(w.dictationMode)
        }));
        this.setData({
            phase: 'test',
            bookTitle: source === 'notebook' ? '错词本重练' : '上次错词重练',
            words: wrongOnly,
            totalWords: wrongOnly.length,
            currentIndex: 0,
            wrongWords: [],
            wrongWordsDetail: [],
            correctCount: 0,
            showResult: false,
            inputValue: '',
            userAnswer: '',
            practiceStart: Date.now(),
            reviewingWrongWords: true,
            retrySource: source,
            finished: false,
            showHint: false,
            attemptCount: 0,
            inputError: false,
            dictationMode: wrongOnly[0] ? wrongOnly[0].dictationMode : MODE_AUDIO_TO_EN,
            currentMode: wrongOnly[0] ? wrongOnly[0].dictationMode : MODE_AUDIO_TO_EN
        });
        this.loadWord(0);
        this.startTicker();
    },

    // 重练错词
    restartWrongWords() {
        let wrongDetail = this.data.wrongWordsDetail;
        if (!wrongDetail.length) {
            try {
                const saved = wx.getStorageSync('dictation_last_wrong') || [];
                if (Array.isArray(saved) && saved.length) {
                    wrongDetail = saved;
                    this.setData({ wrongWordsDetail: saved });
                }
            } catch (e) {
                console.warn('load last wrong failed', e);
            }
        }
        if (!wrongDetail.length) {
            wx.showToast({ title: '没有错词可重练', icon: 'none' });
            return;
        }
        const wrongOnly = wrongDetail.map((w, idx) => ({
            id: w.id || w.word_id || null,
            word: w.word,
            translation: w.translation,
            phonetic: w.phonetic,
            core_meaning_zh: w.core_meaning_zh,
            usage_pattern: w.usage_pattern,
            example_en: w.example_en,
            example_zh: w.example_zh,
            usage_note: w.usage_note,
            accepted_answers: w.accepted_answers || [],
            dictationMode: resolveDictationMode(w.dictationMode)
        }));
        this.setData({
            words: wrongOnly,
            totalWords: wrongOnly.length,
            currentIndex: 0,
            wrongWords: [],
            wrongWordsDetail: [],
            correctCount: 0,
            showResult: false,
            inputValue: '',
            userAnswer: '',
            practiceStart: Date.now(),
            reviewingWrongWords: true,
            finished: false,
            showHint: false,
            attemptCount: 0,
            inputError: false,
            dictationMode: wrongOnly[0] ? wrongOnly[0].dictationMode : MODE_AUDIO_TO_EN,
            currentMode: wrongOnly[0] ? wrongOnly[0].dictationMode : MODE_AUDIO_TO_EN
        });
        this.loadWord(0);
        this.startTicker();
    },

    returnAfterFinish() {
        this.clearProgress();
        wx.navigateBack();
    },

    // ---------- Notebook (local) ----------
    loadLastWrong() {
        try {
            const saved = wx.getStorageSync('dictation_last_wrong') || [];
            if (Array.isArray(saved) && saved.length) {
                this.setData({ wrongWordsDetail: saved });
            }
        } catch (e) {
            console.warn('loadLastWrong error', e);
        }
    },

    loadNotebookCount() {
        try {
            const list = wx.getStorageSync('dictation_notebook') || [];
            this.setData({ notebookCount: Array.isArray(list) ? list.length : 0 });
        } catch (e) {
            console.warn('loadNotebookCount error', e);
            this.setData({ notebookCount: 0 });
        }
    },

    // 错词重练后，从错词本中移除本次答对的词
    _removeCorrectWordsFromNotebook() {
        try {
            // 本次练习的所有单词
            const allWords = this.data.words || [];
            // 本次仍然答错的单词
            const stillWrongSet = new Set(
                (this.data.wrongWordsDetail || []).map(w => notebookEntryKey(w))
            );
            // 答对的单词 = 全部 - 仍然答错的
            const correctWords = allWords
                .map(w => notebookEntryKey(w))
                .filter(w => w && !stillWrongSet.has(w));

            if (!correctWords.length) return;

            const correctSet = new Set(correctWords);
            const notebook = wx.getStorageSync('dictation_notebook') || [];
            if (!Array.isArray(notebook)) return;
            const updated = notebook.filter(
                item => !correctSet.has(notebookEntryKey(item))
            );
            wx.setStorageSync('dictation_notebook', updated);

            // 同时清理 dictation_last_wrong 中答对的词
            const lastWrong = wx.getStorageSync('dictation_last_wrong') || [];
            if (Array.isArray(lastWrong) && lastWrong.length) {
                const updatedLast = lastWrong.filter(
                    item => !correctSet.has(notebookEntryKey(item))
                );
                wx.setStorageSync('dictation_last_wrong', updatedLast);
            }
        } catch (e) {
            console.warn('_removeCorrectWordsFromNotebook error', e);
        }
    },

    appendToNotebook(words) {
        try {
            const list = wx.getStorageSync('dictation_notebook') || [];
            const map = new Map();
            if (Array.isArray(list)) {
                list.forEach(item => map.set(notebookEntryKey(item), item));
            }
            (words || []).forEach(w => {
                const key = notebookEntryKey(w);
                if (!key) return;
                map.set(key, {
                    id: w.id || w.word_id || null,
                    word: w.word,
                    translation: w.translation,
                    phonetic: w.phonetic,
                    core_meaning_zh: w.core_meaning_zh,
                    usage_pattern: w.usage_pattern,
                    example_en: w.example_en,
                    example_zh: w.example_zh,
                    usage_note: w.usage_note,
                    dictationMode: resolveDictationMode(w.dictationMode || this.data.currentMode),
                    updatedAt: Date.now()
                });
            });
            const newList = Array.from(map.values());
            wx.setStorageSync('dictation_notebook', newList);
            this.setData({ notebookCount: newList.length });
        } catch (e) {
            console.warn('appendToNotebook error', e);
        }
    },

    // ========== Group Selection ==========
    selectGroupPlan(e) {
        const key = e.currentTarget.dataset.key;
        if (!key) return;
        this.setData({ selectedGroupPlanKey: key });
    },

    startSelectedGroupPlan() {
        const plans = this.data.groupPlans || [];
        const plan = plans.find(item => item.key === this.data.selectedGroupPlanKey) || plans[0];
        if (!plan || !plan.sizes || !plan.sizes.length) {
            wx.showToast({ title: '暂无可用分组', icon: 'none' });
            return;
        }
        this.activateGroup(plan.sizes, 0, { correctStart: 0, wrongStart: 0 }, () => {
            this.enterFamiliarization();
        });
    },

    activateGroup(sizesValue, groupIndex, baseline, callback) {
        const sizes = normalizeGroupSizes(sizesValue, this.data.totalWords);
        const bounds = groupBounds(sizes, groupIndex);
        const correctStart = baseline && baseline.correctStart != null
            ? Number(baseline.correctStart) || 0
            : this.data.correctCount;
        const wrongStart = baseline && baseline.wrongStart != null
            ? Number(baseline.wrongStart) || 0
            : this.data.wrongWordsDetail.length;
        this.setData({
            groupSizes: sizes,
            currentGroupIndex: bounds.groupIndex,
            groupCount: sizes.length,
            groupStart: bounds.start,
            groupEnd: bounds.end,
            groupWordCount: bounds.size,
            hasMoreGroups: bounds.groupIndex < sizes.length - 1,
            groupCorrectStart: correctStart,
            groupWrongStart: wrongStart,
            groupSummaryInfo: null,
            finished: false
        }, callback);
    },

    // ========== Familiarization Phase ==========
    enterFamiliarization() {
        const firstIndex = this.data.groupStart || 0;
        const firstWord = this.data.words[firstIndex] || {};
        const firstMode = resolveDictationMode(firstWord.dictationMode, this.data.dictationMode);
        const timerSeconds = Math.max(300, Math.min(1200, (this.data.groupWordCount || this.data.totalWords) * 24));
        const timerMinutes = String(Math.floor(timerSeconds / 60)).padStart(2, '0');
        const timerRemainder = String(timerSeconds % 60).padStart(2, '0');
        this.setData({
            phase: 'familiarize',
            famIndex: firstIndex,
            famRevealed: false,
            famTimerSeconds: timerSeconds,
            famTimerDisplay: `${timerMinutes}:${timerRemainder}`,
            currentWord: firstWord,
            currentMode: firstMode
        });
        this.startFamTimer();
        if (isAudioMode(firstMode)) {
            this.prefetchAudioWindow(firstIndex);
            setTimeout(() => this.playCurrentWord(), 500);
        }
    },

    startFamTimer() {
        this.stopFamTimer();
        this.famTimerInterval = setInterval(() => {
            let seconds = this.data.famTimerSeconds - 1;
            if (seconds <= 0) {
                this.stopFamTimer();
                wx.showToast({ title: '熟悉时间到，开始练习', icon: 'none', duration: 2000 });
                setTimeout(() => this.startTest(), 1500);
                return;
            }
            const m = String(Math.floor(seconds / 60)).padStart(2, '0');
            const s = String(seconds % 60).padStart(2, '0');
            this.setData({
                famTimerSeconds: seconds,
                famTimerDisplay: `${m}:${s}`
            });
        }, 1000);
    },

    stopFamTimer() {
        if (this.famTimerInterval) {
            clearInterval(this.famTimerInterval);
            this.famTimerInterval = null;
        }
    },

    playFamWord() {
        const word = this.data.words[this.data.famIndex];
        if (!word) return;
        this.setData({
            currentWord: word,
            currentMode: resolveDictationMode(word.dictationMode, this.data.dictationMode)
        });
        this.playCurrentWord();
    },

    revealFamWord() {
        this.setData({ famRevealed: true });
    },

    nextFamWord() {
        const nextIdx = this.data.famIndex + 1;
        let targetIndex = nextIdx;
        if (nextIdx >= this.data.groupEnd) {
            targetIndex = this.data.groupStart;
        }
        const targetWord = this.data.words[targetIndex] || {};
        const targetMode = resolveDictationMode(targetWord.dictationMode, this.data.dictationMode);
        this.setData({
            famIndex: targetIndex,
            famRevealed: false,
            currentWord: targetWord,
            currentMode: targetMode
        });
        if (isAudioMode(targetMode)) {
            this.prefetchAudioWindow(targetIndex);
            setTimeout(() => this.playCurrentWord(), 300);
        }
    },

    prevFamWord() {
        const prevIdx = this.data.famIndex - 1;
        let targetIndex = prevIdx;
        if (prevIdx < this.data.groupStart) {
            targetIndex = this.data.groupEnd - 1;
        }
        const targetWord = this.data.words[targetIndex] || {};
        const targetMode = resolveDictationMode(targetWord.dictationMode, this.data.dictationMode);
        this.setData({
            famIndex: targetIndex,
            famRevealed: false,
            currentWord: targetWord,
            currentMode: targetMode
        });
        if (isAudioMode(targetMode)) {
            this.prefetchAudioWindow(targetIndex);
            setTimeout(() => this.playCurrentWord(), 300);
        }
    },

    startTest() {
        this.stopFamTimer();
        this.setData({
            phase: 'test',
            practiceStart: Date.now()
        });
        this.loadWord(this.data.groupStart || 0);
        this.startTicker();
    },

    startTicker() {
        if (this.data.ticker) return;
        this.data.ticker = setInterval(() => {
            const seconds = this.computeDurationSeconds();
            const m = String(Math.floor(seconds / 60)).padStart(2, '0');
            const s = String(seconds % 60).padStart(2, '0');
            this.setData({ displayTime: `${m}:${s}` });
        }, 1000);
    },

    stopTicker() {
        if (this.data.ticker) {
            clearInterval(this.data.ticker);
            this.data.ticker = null;
        }
    }
})
