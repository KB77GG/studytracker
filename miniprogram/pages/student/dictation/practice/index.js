const app = getApp()
const { request } = require('../../../../utils/request.js')
const {
    buildGroupPlans,
    findGroupIndex,
    groupBounds,
    normalizeGroupSizes
} = require('../../../../utils/dictation-groups.js')
const {
    isEnglishAnswerCorrect,
    stripPartOfSpeechPrefix
} = require('../../../../utils/dictation-answers.js')
const {
    buildFirstAttemptId,
    buildRunStorageKey,
    createAttemptRunId,
    ensureAttemptPayload,
    getOrCreateRunId,
    isSuccessfulResponse,
    missingQueueItems,
    summarizeQueue,
    queueMode
} = require('../../../../utils/dictation-review.js')
const {
    INPUT_COMPATIBLE,
    INPUT_NATIVE,
    INPUT_STRICT,
    answerInputLimit,
    chooseInputMode,
    defaultInputPolicy,
    inputModeStorageKey,
    isEnglishSpellingMode,
    normalizeKeyboardKey
} = require('../../../../utils/dictation-input-policy.js')

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

function dictationSpeechText(word) {
    return stripPartOfSpeechPrefix(word)
}

function directYoudaoAudioUrl(word) {
    return `https://dict.youdao.com/dictvoice?audio=${encodeURIComponent(word)}&type=2`
}

Page({
    data: {
        bookId: null,
        taskId: null,
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
        isCheckingFirstAnswer: false,
        isAdvancingWord: false,
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
        resultRevealed: false,
        inputFocus: true,
        showHint: false,
        attemptCount: 0,
        dictationMode: MODE_AUDIO_TO_EN,
        currentMode: MODE_AUDIO_TO_EN,
        dictationOrder: 'sequence',
        queueToken: '',
        assignedCount: 0,
        reviewCount: 0,
        recoveryMissingWordIds: [],
        appealSubmitted: false,
        inputMode: INPUT_NATIVE,
        inputPolicy: defaultInputPolicy(MODE_AUDIO_TO_EN),
        isEnglishSpelling: true
    },

    onLoad: function (options) {
        options = options || {};
        this.firstAttempts = {};
        this.firstAttemptPayloads = {};
        this.firstAttemptConfirmed = {};
        this.firstAttemptResults = {};
        this.firstAttemptPromises = {};
        this.firstAttemptSent = {};
        this.firstAnswerInFlightKey = null;
        this.wordAdvanceLocked = false;
        this.taskSubmitLocked = false;
        this.attemptRunStorageKey = options.taskId
            ? null
            : buildRunStorageKey(options.mode === 'retry_wrong'
                ? `wrong-${options.source || 'last'}`
                : `book-${options.id || 'unknown'}`);
        this.attemptSessionId = options.taskId
            ? ''
            : this.getOrCreateAttemptRunId();

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
            const fallbackWord = dictationSpeechText(this.data.currentWord.word);
            if (!this.fallbackTried && fallbackWord) {
                this.fallbackTried = true;
                this.downloadAndPlay(directYoudaoAudioUrl(fallbackWord), fallbackWord, this.playTokenCounter, true, {
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
        request(`/miniprogram/student/tasks/${taskId}`)
            .then((res) => {
                if (!res || !res.ok || !res.task) {
                    wx.hideLoading();
                    wx.showToast({ title: '任务加载失败', icon: 'none' });
                    return;
                }
                const task = res.task;
                const rawMode = String(task.dictation_mode || '').trim().toLowerCase();
                if (rawMode === MODE_SPELLING_DRILL) {
                    wx.hideLoading();
                    wx.redirectTo({ url: `/pages/student/dictation/spell/index?taskId=${taskId}` });
                    return;
                }
                const dictationMode = resolveDictationMode(task.dictation_mode, task.dictation_book_type);
                this.setData({
                    bookTitle: task.task_name,
                    rangeStart: task.dictation_word_start,
                    rangeEnd: task.dictation_word_end,
                    dictationOrder: task.dictation_order || 'sequence',
                    dictationMode,
                    currentMode: dictationMode,
                    bookId: task.dictation_book_id,
                    progressKey: this.buildProgressKey(taskId, task.dictation_book_id, task.dictation_word_start, task.dictation_word_end)
                });
                if (task.dictation_book_id) {
                    this.fetchTaskQueue(taskId);
                } else {
                    wx.hideLoading();
                    wx.showToast({ title: '任务配置错误: dictation_book_id missing', icon: 'none' });
                }
            })
            .catch((err) => {
                wx.hideLoading();
                console.error(err);
                wx.showToast({ title: '网络错误', icon: 'none' });
            });
    },

    startBackendTimer(taskId) {
        if (!taskId) return;
        request(`/miniprogram/student/tasks/${taskId}/timer/start`, { method: 'POST' })
            .catch((err) => console.warn('start timer failed', err));
    },

    fetchTaskQueue(taskId) {
        request(`/miniprogram/student/tasks/${taskId}/dictation-queue`)
            .then((res) => {
                wx.hideLoading();
                if (!res || !res.ok) {
                    wx.showToast({ title: '加载合并队列失败', icon: 'none' });
                    return;
                }
                const words = (res.words || []).map(item => Object.assign({}, item, {
                    dictationMode: queueMode(item, res.task_mode)
                }));
                const counts = summarizeQueue(words);
                if (!words.length) {
                    wx.showToast({ title: '当前任务没有可练单词', icon: 'none' });
                    return;
                }
                this.setData({
                    words,
                    totalWords: words.length,
                    currentIndex: 0,
                    practiceStart: null,
                    accumulatedSeconds: 0,
                    dictationMode: res.task_mode,
                    currentMode: res.task_mode,
                    dictationOrder: res.dictation_order || 'sequence',
                    queueToken: res.queue_token || '',
                    assignedCount: res.assigned_count != null ? res.assigned_count : counts.assignedCount,
                    reviewCount: res.auto_review_count != null ? res.auto_review_count : counts.reviewCount
                });
                if (res.task_mode === MODE_AUDIO_TO_EN || res.task_mode === MODE_ZH_TO_EN) {
                    this.requestServerTtsPrewarm(words);
                    this.prefetchAudioWindow(0);
                }
                this.prepareLoadedWords(words);
            })
            .catch(() => {
                wx.hideLoading();
                wx.showToast({ title: '网络错误', icon: 'none' });
            });
    },

    prepareLoadedWords(words) {
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
        if (saved.awaitingNextGroup && savedGroupIndex < savedSizes.length - 1) savedGroupIndex += 1;
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
    },

    fetchWords: function (id) {
        wx.showLoading({ title: '加载单词...' });
        request(`/dictation/books/${id}`)
            .then((res) => {
                wx.hideLoading();
                if (!res || !res.ok) {
                    wx.showToast({ title: '加载失败', icon: 'none' });
                    return;
                }
                let words = res.words || [];
                if (this.data.rangeStart || this.data.rangeEnd) {
                    const start = Math.max(0, (this.data.rangeStart || 1) - 1);
                    const end = this.data.rangeEnd || words.length;
                    words = words.slice(start, end);
                }
                if (!words.length) {
                    wx.showModal({ title: '提示', content: '该范围内没有单词', showCancel: false });
                    return;
                }
                const bookType = (res.book && res.book.book_type) || 'dictation';
                const dictationMode = resolveDictationMode('', bookType);
                words = words.map(word => Object.assign({}, word, { dictationMode }));
                const counts = summarizeQueue(words.map(item => Object.assign({}, item, { source: 'assigned' })));
                this.setData({
                    bookTitle: res.book && res.book.title ? res.book.title : this.data.bookTitle,
                    words,
                    totalWords: words.length,
                    currentIndex: 0,
                    practiceStart: null,
                    accumulatedSeconds: 0,
                    dictationMode,
                    currentMode: dictationMode,
                    assignedCount: counts.assignedCount,
                    reviewCount: 0
                });
                if (isAudioMode(dictationMode) || dictationMode === MODE_ZH_TO_EN) {
                    this.requestServerTtsPrewarm(words);
                    this.prefetchAudioWindow(0);
                }
                this.prepareLoadedWords(words);
            })
            .catch(() => {
                wx.hideLoading();
                wx.showToast({ title: '网络错误', icon: 'none' });
            });
    },

    refocusAnswerInput(delay = 50) {
        if (this.data.inputMode === INPUT_STRICT) return;
        this.setData({ inputFocus: false });
        setTimeout(() => {
            if (this.data.phase !== 'test' || this.data.showResult || this.data.finished) return;
            this.setData({ inputFocus: true });
        }, delay);
    },

    loadInputPolicy(mode) {
        this.inputPolicyRequestToken = (this.inputPolicyRequestToken || 0) + 1;
        const requestToken = this.inputPolicyRequestToken;
        const fallback = defaultInputPolicy(mode);
        const storageKey = inputModeStorageKey({
            taskId: this.data.taskId,
            bookId: this.data.bookId,
            mode
        });
        this.setData({
            inputPolicy: fallback,
            inputMode: fallback.defaultInputMode,
            isEnglishSpelling: fallback.isEnglishSpelling
        });
        if (!fallback.isEnglishSpelling) return;
        request('/dictation/input-policy', {
            data: {
                mode,
                task_id: this.data.taskId || undefined
            }
        }).then((res) => {
            if (requestToken !== this.inputPolicyRequestToken) return;
            const raw = res && res.policy;
            const policy = raw ? {
                mode: raw.mode || mode,
                isEnglishSpelling: !!raw.is_english_spelling,
                defaultInputMode: raw.default_input_mode || INPUT_STRICT,
                compatibleAllowed: !!raw.compatible_allowed,
                grant: raw.grant || null
            } : fallback;
            this.setData({
                inputPolicy: policy,
                inputMode: chooseInputMode(policy, wx.getStorageSync(storageKey))
            }, () => this.refocusAnswerInput());
        }).catch(() => {
            if (requestToken !== this.inputPolicyRequestToken) return;
            this.setData({ inputPolicy: fallback, inputMode: INPUT_STRICT });
        });
    },

    onInputModeChange(e) {
        const nextMode = e && e.detail && e.detail.mode;
        if (!this.data.inputPolicy.compatibleAllowed || !nextMode || nextMode === this.data.inputMode) return;
        const change = () => {
            const storageKey = inputModeStorageKey({
                taskId: this.data.taskId,
                bookId: this.data.bookId,
                mode: this.data.currentMode
            });
            wx.setStorageSync(storageKey, nextMode);
            this.setData({
                inputMode: nextMode,
                inputValue: '',
                inputError: false,
                resultRevealed: false
            }, () => this.refocusAnswerInput());
        };
        if (this.data.inputValue) {
            wx.showModal({
                title: '切换输入方式',
                content: '切换后会清空当前答案，是否继续？',
                confirmText: '清空并切换',
                success: res => { if (res.confirm) change(); }
            });
            return;
        }
        change();
    },

    onKeyboardKey(e) {
        if (this.data.inputMode !== INPUT_STRICT || this.data.showResult) return;
        const key = normalizeKeyboardKey(e && e.detail && e.detail.key);
        const answer = String(this.data.currentWord.word || '');
        const limit = answerInputLimit(answer, this.data.currentWord.accepted_answers);
        if (!key || this.data.inputValue.length >= limit) return;
        this.setData({ inputValue: `${this.data.inputValue}${key}`, inputError: false });
    },

    onKeyboardBackspace() {
        if (this.data.inputMode !== INPUT_STRICT || this.data.showResult) return;
        this.setData({
            inputValue: String(this.data.inputValue || '').slice(0, -1),
            inputError: false
        });
    },

    retrySpelling() {
        if (!this.data.showResult || this.data.isCorrect || this.data.resultRevealed) return;
        this.setData({
            showResult: false,
            resultRevealed: false,
            inputValue: '',
            userAnswer: '',
            inputError: false
        }, () => this.refocusAnswerInput());
    },

    skipSpelling() {
        if (!this.data.showResult || this.data.isCorrect || this.data.resultRevealed) return;
        this.setData({
            resultRevealed: true,
            userAnswer: this.data.userAnswer || this.data.inputValue
        });
    },

    loadWord: function (index, onReady) {
        const word = this.data.words[index];
        const currentMode = resolveDictationMode(word && word.dictationMode, this.data.dictationMode);
        this.setData({
            currentWord: word,
            currentIndex: index,
            currentMode: currentMode,
            inputValue: '',
            showResult: false,
            isCorrect: false,
            resultRevealed: false,
            inputFocus: false,
            inputError: false,
            userAnswer: '',
            showHint: false,
            attemptCount: 0,
            appealSubmitted: false,
            inputMode: defaultInputPolicy(currentMode).defaultInputMode,
            inputPolicy: defaultInputPolicy(currentMode),
            isEnglishSpelling: isEnglishSpellingMode(currentMode)
        }, () => {
            this.loadInputPolicy(currentMode);
            this.refocusAnswerInput();
            if (onReady) onReady();
        });
        this.saveProgress(index);

        // 强化记忆（看中文写英文）默写时也播发音；错词重练一律播发音
        if (isAudioMode(currentMode) || currentMode === MODE_ZH_TO_EN || this.data.reviewingWrongWords) {
            setTimeout(() => {
                this.playCurrentWord(true);
            }, 500);
            this.prefetchAudioWindow(index + 1);
        }
    },

    playCurrentWord: function (force) {
        if (!force && !isAudioMode(this.data.currentMode)) return;
        const word = this.data.currentWord.word;
        if (!word) return;

        const trimmed = dictationSpeechText(word);
        if (!trimmed) return;
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

    replayCurrentWord() {
        this.playCurrentWord(true);
        wx.showToast({ title: '已重播', icon: 'none', duration: 800 });
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
            if (isAudioMode(mode) || mode === MODE_ZH_TO_EN || this.data.reviewingWrongWords) {
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
        const trimmed = dictationSpeechText(word);
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
            const word = dictationSpeechText(item && item.word);
            const key = audioCacheKey(word);
            if (!word || seen[key]) return;
            if (!this.data.reviewingWrongWords && mode !== MODE_AUDIO_TO_EN && mode !== MODE_ZH_TO_EN) return;
            seen[key] = true;
            targets.push(word);
        });
        if (!targets.length) return;
        request('/dictation/tts/prewarm', {
            method: 'POST',
            data: {
                words: targets.slice(0, AUDIO_PREWARM_LIMIT)
            },
        }).catch((err) => console.warn('dictation tts prewarm failed', err));
    },

    onToggleAutoPlay(e) {
        this.setData({ autoPlay: e.detail.value });
    },

    onInput: function (e) {
        if (this.data.inputMode === INPUT_STRICT) return;
        this.setData({
            inputValue: e.detail.value,
            inputError: false
        });
    },

    checkAnswer: function () {
        if (this.data.showResult || this.data.isCheckingFirstAnswer) return;

        const inputRaw = this.data.inputValue.trim();
        const mode = this.data.currentMode || MODE_AUDIO_TO_EN;
        const attempts = this.data.attemptCount || 0;

        if (!inputRaw) {
            wx.showToast({ title: '请输入答案', icon: 'none' });
            return;
        }

        if (attempts === 0) {
            const word = this.data.currentWord;
            const key = String(word.word_id || word.id);
            if (this.firstAnswerInFlightKey === key) return;
            this.firstAnswerInFlightKey = key;
            this.setData({ isCheckingFirstAnswer: true, inputFocus: false });
            this.submitFirstAttempt(word, inputRaw)
                .then((res) => {
                    if (!isSuccessfulResponse(res)) {
                        throw new Error('first_attempt_not_acknowledged');
                    }
                    this.firstAttempts[key] = {
                        correct: !!res.is_correct,
                        answer: inputRaw
                    };
                    this.firstAnswerInFlightKey = null;
                    this.persistAttemptState();
                    this.setData({ isCheckingFirstAnswer: false }, () => {
                        this.applyAnswerResult(inputRaw, !!res.is_correct, 0);
                    });
                })
                .catch((err) => {
                    this.firstAnswerInFlightKey = null;
                    this.setData({ isCheckingFirstAnswer: false, inputValue: inputRaw, inputFocus: true });
                    wx.showToast({ title: '首答同步失败，请重试', icon: 'none' });
                    console.warn('submit first attempt failed', err);
                });
            return;
        }

        this.applyAnswerResult(inputRaw, this.isAnswerCorrectLocally(inputRaw, mode), attempts);
    },

    isAnswerCorrectLocally(inputRaw, mode) {
        if (mode === MODE_AUDIO_TO_EN || mode === MODE_ZH_TO_EN) {
            return isEnglishAnswerCorrect(inputRaw, this.data.currentWord);
        }
        const input = normalizeChineseAnswer(inputRaw);
        return chineseVariants(this.data.currentWord.translation).some(variant => (
            input === variant
            || (input.length >= 2 && (variant.includes(input) || input.includes(variant)))
        ));
    },

    applyAnswerResult(inputRaw, isCorrect, attempts) {
        const mode = this.data.currentMode || MODE_AUDIO_TO_EN;
        if (isCorrect) {
            if (attempts === 0) {
                this.setData({ correctCount: this.data.correctCount + 1 });
            }
            this.setData({
                showResult: true,
                isCorrect: true,
                resultRevealed: false,
                userAnswer: inputRaw,
                inputError: false,
                attemptCount: attempts + 1
            }, () => {
                if (!this.isFinalPracticeWord()) return;
                setTimeout(() => {
                    if (this.data.showResult && this.data.isCorrect && !this.data.finished) {
                        this.finishPractice();
                    }
                }, 600);
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
                book_id: this.data.currentWord.book_id || this.data.bookId,
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
            const nextState = {
                wrongWords: wrongList,
                wrongWordsDetail: wrongDetail,
                showHint: mode === MODE_AUDIO_TO_EN,
                inputError: true,
                attemptCount: attempts + 1
            };
            if (isEnglishSpellingMode(mode)) {
                Object.assign(nextState, {
                    showResult: true,
                    resultRevealed: false,
                    userAnswer: inputRaw
                });
                this.setData(nextState);
            } else {
                Object.assign(nextState, {
                    inputValue: '',
                    showResult: false,
                    resultRevealed: false,
                    inputFocus: false
                });
                this.setData(nextState, () => this.refocusAnswerInput(30));
            }
            wx.showToast({ title: isEnglishSpellingMode(mode) ? '拼写不正确' : '再试一次', icon: 'none' });
            return;
        }

        this.setData({
            showResult: true,
            isCorrect: false,
            resultRevealed: false,
            userAnswer: inputRaw,
            inputError: true,
            attemptCount: attempts + 1
        });
        if (mode === MODE_ZH_TO_EN) this.playCurrentWord(true);
    },

    submitFirstAttempt(word, answer) {
        const wordId = word && (word.word_id || word.id);
        if (!wordId) return Promise.resolve(null);
        const key = String(wordId);
        ensureAttemptPayload(this.firstAttemptPayloads, key, {
            word_id: wordId,
            book_id: word.book_id || this.data.bookId,
            task_id: this.data.taskId || null,
            answer,
            mode: this.data.currentMode,
            input_mode: this.data.inputMode,
            input_grant_id: this.data.inputPolicy.grant && this.data.inputPolicy.grant.id,
            attempt_id: buildFirstAttemptId(this.data.taskId, this.data.bookId, wordId, this.attemptSessionId),
            is_first_attempt: true,
            strict_queue: !!this.data.taskId,
            enroll: true
        });
        this.persistAttemptState();
        return this.sendFirstAttempt(key);
    },

    sendFirstAttempt(key) {
        if (this.firstAttemptConfirmed[key]) {
            return Promise.resolve(this.firstAttemptResults[key] || {
                ok: true,
                is_correct: !!(this.firstAttempts[key] && this.firstAttempts[key].correct)
            });
        }
        if (this.firstAttemptPromises[key]) return this.firstAttemptPromises[key];
        const payload = this.firstAttemptPayloads[key];
        if (!payload) return Promise.reject(new Error('missing_first_attempt_payload'));
        this.firstAttemptSent[key] = true;
        const promise = request('/dictation/submit', {
            method: 'POST',
            data: payload
        }).then((res) => {
            if (!isSuccessfulResponse(res)) {
                const error = new Error((res && res.error) || 'first_attempt_rejected');
                error.response = res;
                throw error;
            }
            this.firstAttemptConfirmed[key] = true;
            this.firstAttemptResults[key] = res;
            delete this.firstAttemptSent[key];
            delete this.firstAttemptPromises[key];
            this.persistAttemptState();
            return res;
        }).catch((err) => {
            delete this.firstAttemptSent[key];
            delete this.firstAttemptPromises[key];
            this.persistAttemptState();
            throw err;
        });
        this.firstAttemptPromises[key] = promise;
        return promise;
    },

    retryPendingFirstAttempts() {
        const keys = Object.keys(this.firstAttemptPayloads || {})
            .filter(key => !this.firstAttemptConfirmed[key]);
        return Promise.all(keys.map(key => this.sendFirstAttempt(key)));
    },

    reportExample: function (e) {
        const wordId = e.currentTarget.dataset.id;
        if (!wordId) return;
        request(`/dictation/example/report/${wordId}`, { method: 'POST' })
            .then((res) => {
                wx.showToast({
                    title: res && res.ok ? '已反馈，助教会复审' : '反馈失败',
                    icon: 'none'
                });
            })
            .catch(() => wx.showToast({ title: '网络错误', icon: 'none' }));
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
                request('/dictation/appeals', {
                    method: 'POST',
                    data: {
                        word_id: word.id,
                        task_id: this.data.taskId,
                        answer: answer,
                        mode: this.data.currentMode
                    },
                }).then((res) => {
                        if (res && res.ok) {
                            this.setData({ appealSubmitted: true });
                            wx.showToast({ title: '已提交人工审核', icon: 'none' });
                            return;
                        }
                        const title = res && res.error === 'answer_already_accepted'
                            ? '该答案现已可接受'
                            : '申诉提交失败';
                        wx.showToast({ title, icon: 'none' });
                }).catch(() => wx.showToast({ title: '网络错误', icon: 'none' }));
            }
        });
    },

    nextWord: function () {
        if (
            this.wordAdvanceLocked
            || this.data.isAdvancingWord
            || this.data.isCheckingFirstAnswer
            || !this.data.showResult
        ) return;
        this.wordAdvanceLocked = true;
        this.setData({ isAdvancingWord: true });

        const recoveryIds = this.data.recoveryMissingWordIds || [];
        if (recoveryIds.length) {
            const currentId = String(this.data.currentWord.word_id || this.data.currentWord.id || '');
            const remainingIds = recoveryIds.filter(wordId => String(wordId) !== currentId);
            this.setData({ recoveryMissingWordIds: remainingIds });
            if (remainingIds.length) {
                const nextRecoveryIndex = this.data.words.findIndex(item => (
                    String(item.word_id || item.id) === String(remainingIds[0])
                ));
                if (nextRecoveryIndex >= 0) {
                    this.loadWord(nextRecoveryIndex, () => this.releaseWordAdvance());
                    return;
                }
            }
            this.releaseWordAdvance();
            this.finishPractice();
            return;
        }

        const nextIndex = this.data.currentIndex + 1;
        const groupEnd = this.data.groupEnd || this.data.totalWords;
        if (nextIndex < groupEnd) {
            this.loadWord(nextIndex, () => this.releaseWordAdvance());
        } else if (this.data.hasMoreGroups) {
            this.finishCurrentGroup(() => this.releaseWordAdvance());
        } else {
            this.releaseWordAdvance();
            this.finishPractice();
        }
    },

    releaseWordAdvance() {
        this.wordAdvanceLocked = false;
        this.setData({ isAdvancingWord: false });
    },

    isFinalPracticeWord() {
        const groupEnd = this.data.groupEnd || this.data.totalWords;
        return this.data.currentIndex + 1 >= groupEnd && !this.data.hasMoreGroups;
    },

    finishCurrentGroup(onReady) {
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
        }, () => {
            if (onReady) onReady();
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
        this.pauseTimer();
        this.stopTicker();
        this.setData({ inputFocus: false });

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
                success: () => {
                    this.clearAttemptRun();
                    wx.navigateBack();
                }
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
                onSuccess: (serverResult) => {
                    if (this.data.wrongWordsDetail.length > 0) {
                        this.appendToNotebook(this.data.wrongWordsDetail);
                    }
                    this.setData({
                        finished: true,
                        summaryInfo: this.buildServerSummary(serverResult)
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
        if (this.taskSubmitLocked || this.data.isSubmitting) return;
        this.taskSubmitLocked = true;
        this.setData({ isSubmitting: true });
        wx.showLoading({ title: '提交中...' });
        this.retryPendingFirstAttempts()
            .then(() => request(`/miniprogram/student/tasks/${this.data.taskId}/submit`, {
                method: 'POST',
                data: {
                    strict_queue: true,
                    queue_token: this.data.queueToken,
                    accuracy,
                    wrong_words: wrongWords.join(', '),
                    duration_seconds: durationSeconds
                }
            }))
            .then((res) => {
                wx.hideLoading();
                if (res && res.ok) {
                    this.setData({ recoveryMissingWordIds: [] });
                    this.clearProgress();
                    if (options.onSuccess) {
                        options.onSuccess(res);
                    }
                    if (!options.keepOpen) {
                        setTimeout(() => wx.navigateBack(), 1500);
                    }
                } else if (!this.recoverMissingTaskWords(res)) {
                    wx.showToast({ title: '提交失败', icon: 'none' });
                }
            })
            .catch((err) => {
                wx.hideLoading();
                console.warn('submit dictation task failed', err);
                wx.showToast({ title: '提交失败，请重试', icon: 'none' });
            })
            .finally(() => {
                this.taskSubmitLocked = false;
                this.setData({ isSubmitting: false });
            }
            );
    },

    recoverMissingTaskWords(response) {
        const missingWords = missingQueueItems(response, this.data.words);
        if (!missingWords.length) return false;
        const missingIds = missingWords.map(item => item.word_id || item.id);
        const firstIndex = this.data.words.findIndex(item => (
            String(item.word_id || item.id) === String(missingIds[0])
        ));
        if (firstIndex < 0) return false;

        this.setData({
            finished: false,
            phase: 'test',
            recoveryMissingWordIds: missingIds,
            inputFocus: false
        }, () => {
            this.loadWord(firstIndex);
            this.resumeTimer();
            wx.showModal({
                title: '补答后即可提交',
                content: `检测到 ${missingIds.length} 个单词没有同步，已为你自动定位。`,
                showCancel: false
            });
        });
        return true;
    },

    // --- Progress Persistence ---
    getOrCreateAttemptRunId() {
        const key = this.attemptRunStorageKey;
        return getOrCreateRunId(
            {
                get: () => wx.getStorageSync(key),
                set: value => wx.setStorageSync(key, value)
            },
            key,
            () => createAttemptRunId('dictation')
        );
    },

    beginNewAttemptRun(scope) {
        this.attemptRunStorageKey = buildRunStorageKey(scope);
        this.attemptSessionId = createAttemptRunId('dictation');
        wx.setStorageSync(this.attemptRunStorageKey, this.attemptSessionId);
        this.firstAttempts = {};
        this.firstAttemptPayloads = {};
        this.firstAttemptConfirmed = {};
        this.firstAttemptResults = {};
        this.firstAttemptPromises = {};
        this.firstAttemptSent = {};
        this.firstAnswerInFlightKey = null;
    },

    clearAttemptRun() {
        if (!this.data.taskId && this.attemptRunStorageKey) {
            try { wx.removeStorageSync(this.attemptRunStorageKey); } catch (e) {}
        }
    },

    persistAttemptState() {
        if (this.data.progressKey) this.saveProgress(this.data.currentIndex || 0);
    },

    buildServerSummary(response) {
        const total = Number(response && response.total_count) || 0;
        const correct = Number(response && response.correct_count) || 0;
        return {
            accuracy: response && response.accuracy != null ? response.accuracy : 0,
            correct,
            total,
            wrongCount: Math.max(0, total - correct)
        };
    },

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
            attemptRunId: this.attemptSessionId,
            firstAttempts: this.firstAttempts,
            firstAttemptPayloads: this.firstAttemptPayloads,
            firstAttemptConfirmed: this.firstAttemptConfirmed,
            firstAttemptResults: this.firstAttemptResults,
            recoveryMissingWordIds: this.data.recoveryMissingWordIds || [],
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
                    wrongWordsDetail: saved.wrongWordsDetail || [],
                    recoveryMissingWordIds: saved.recoveryMissingWordIds || []
                });
            }
            if (saved.accumulatedSeconds) {
                this.setData({ accumulatedSeconds: saved.accumulatedSeconds });
            }
            if (saved.attemptRunId) this.attemptSessionId = saved.attemptRunId;
            if (saved.attemptRunId && this.attemptRunStorageKey) {
                try { wx.setStorageSync(this.attemptRunStorageKey, saved.attemptRunId); } catch (e) {}
            }
            this.firstAttempts = saved.firstAttempts || this.firstAttempts || {};
            this.firstAttemptPayloads = saved.firstAttemptPayloads || this.firstAttemptPayloads || {};
            this.firstAttemptConfirmed = saved.firstAttemptConfirmed || this.firstAttemptConfirmed || {};
            this.firstAttemptResults = saved.firstAttemptResults || this.firstAttemptResults || {};
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
        this.clearAttemptRun();
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
        } else if (this.data.phase === 'test' && !this.data.finished) {
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
        this.requestServerTtsPrewarm(wrongOnly);
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
        this.beginNewAttemptRun('wrong-restart');
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
        this.requestServerTtsPrewarm(wrongOnly);
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
