const app = getApp()

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

        // UI State
        inputValue: '',
        showResult: false,
        isCorrect: false,
        inputFocus: true,
        showHint: false,
        attemptCount: 0
    },

    onLoad: function (options) {
        if (options.taskId) {
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
        this.playTokenCounter = 0;
        this.pendingPlayToken = null;
        this.currentDownloadTask = null;
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
                const direct = `https://dict.youdao.com/dictvoice?audio=${encodeURIComponent(trimmed)}&type=2`;
                this.downloadAndPlay(direct, trimmed, this.playTokenCounter, true);
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
        this.startTicker();
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

                    // Read from root task object
                    this.setData({
                        bookTitle: task.task_name,
                        rangeStart: task.dictation_word_start,
                        rangeEnd: task.dictation_word_end
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

                    this.setData({
                        // Only update title if not set by task
                        bookTitle: this.data.taskId ? this.data.bookTitle : res.data.book.title,
                        words: words,
                        totalWords: words.length,
                        currentIndex: 0,
                        practiceStart: Date.now(),
                        accumulatedSeconds: 0
                    });

                    const resumeIndex = this.loadProgress(words.length);
                    this.loadWord(resumeIndex);
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
        this.setData({
            currentWord: word,
            currentIndex: index,
            inputValue: '',
            showResult: false,
            isCorrect: false,
            inputFocus: true,
            inputError: false,
            userAnswer: '',
            showHint: false,
            attemptCount: 0
        });
        this.saveProgress(index);

        setTimeout(() => {
            this.playCurrentWord();
        }, 500);
    },

    playCurrentWord: function () {
        const word = this.data.currentWord.word;
        if (!word) return;

        const trimmed = word.trim();
        this.fallbackTried = false;
        this.playTokenCounter = (this.playTokenCounter || 0) + 1;
        const token = this.playTokenCounter;
        this.pendingPlayToken = token;
        this.setData({ isLoadingAudio: true, playToken: token });

        this.abortAudioDownload();
        if (this.audioCtx && this.audioCtx.src) {
            try {
                this.audioCtx.stop();
            } catch (e) {}
        }

        const proxyUrl = `${app.globalData.baseUrl}/dictation/tts?word=${encodeURIComponent(trimmed)}`;
        this.downloadAndPlay(proxyUrl, trimmed, token, false);
    },

    abortAudioDownload() {
        if (this.currentDownloadTask && this.currentDownloadTask.abort) {
            try {
                this.currentDownloadTask.abort();
            } catch (e) {}
        }
        this.currentDownloadTask = null;
    },

    downloadAndPlay(url, word, token, isFallback) {
        this.abortAudioDownload();
        this.currentDownloadTask = wx.downloadFile({
            url: url,
            success: (res) => {
                this.currentDownloadTask = null;
                if (token !== this.playTokenCounter) return;
                if (res.statusCode === 200 && res.tempFilePath) {
                    this.pendingPlayToken = token;
                    this.audioCtx.src = res.tempFilePath;
                } else if (!isFallback) {
                    const direct = `https://dict.youdao.com/dictvoice?audio=${encodeURIComponent(word)}&type=2`;
                    this.downloadAndPlay(direct, word, token, true);
                } else {
                    this.setData({ isLoadingAudio: false });
                    wx.showToast({ title: '音频获取失败', icon: 'none' });
                }
            },
            fail: () => {
                this.currentDownloadTask = null;
                if (token !== this.playTokenCounter) return;
                if (!isFallback) {
                    const direct = `https://dict.youdao.com/dictvoice?audio=${encodeURIComponent(word)}&type=2`;
                    this.downloadAndPlay(direct, word, token, true);
                } else {
                    this.setData({ isLoadingAudio: false });
                    wx.showToast({ title: '音频获取失败', icon: 'none' });
                }
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

        const input = this.data.inputValue.trim().toLowerCase();
        const target = this.data.currentWord.word.toLowerCase();
        const isCorrect = input === target;
        const attempts = this.data.attemptCount || 0;

        if (!input) {
            wx.showToast({ title: '请输入单词', icon: 'none' });
            return;
        }

        if (isCorrect) {
            if (attempts === 0) {
                this.setData({ correctCount: this.data.correctCount + 1 });
            }
            this.setData({
                showResult: true,
                isCorrect: true,
                userAnswer: input,
                inputError: false,
                attemptCount: attempts + 1
            });
            wx.showToast({ title: '正确!', icon: 'success', duration: 1000 });
            return;
        }

        if (attempts === 0) {
            const wrongList = this.data.wrongWords;
            const wrongDetail = this.data.wrongWordsDetail;
            wrongList.push(`${this.data.currentWord.word} (写成了: ${input})`);
            wrongDetail.push({
                word: this.data.currentWord.word,
                translation: this.data.currentWord.translation,
                phonetic: this.data.currentWord.phonetic,
                wrong: input
            });
            this.setData({
                wrongWords: wrongList,
                wrongWordsDetail: wrongDetail,
                showHint: true,
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
            userAnswer: input,
            inputError: true,
            attemptCount: attempts + 1
        });
    },

    nextWord: function () {
        const nextIndex = this.data.currentIndex + 1;
        if (nextIndex < this.data.totalWords) {
            this.loadWord(nextIndex);
        } else {
            this.finishPractice();
        }
    },

    finishPractice: function () {
        const total = this.data.totalWords;
        const correct = this.data.correctCount;
        const accuracy = total > 0 ? ((correct / total) * 100).toFixed(1) : 0;
        const durationSeconds = this.computeDurationSeconds();

        if (this.data.reviewingWrongWords) {
            wx.showModal({
                title: '错词练习完成',
                content: '已完成错词复习。',
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

    saveProgress(index) {
        if (!this.data.progressKey) return;
        wx.setStorageSync(this.data.progressKey, { index });
    },

    loadProgress(totalWords) {
        if (!this.data.progressKey) return 0;
        const saved = wx.getStorageSync(this.data.progressKey);
        if (saved && typeof saved.index === 'number') {
            const idx = Math.max(0, Math.min(saved.index, totalWords - 1));
            return idx;
        }
        return 0;
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
    },

    onUnload() {
        this.pauseTimer();
        this.stopTicker();
        this.abortAudioDownload();
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
            id: idx + 1,
            word: w.word,
            translation: w.translation,
            phonetic: w.phonetic
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
            inputError: false
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

    appendToNotebook(words) {
        try {
            const list = wx.getStorageSync('dictation_notebook') || [];
            const map = new Map();
            if (Array.isArray(list)) {
                list.forEach(item => map.set((item.word || '').toLowerCase(), item));
            }
            (words || []).forEach(w => {
                const key = (w.word || '').toLowerCase();
                if (!key) return;
                map.set(key, {
                    word: w.word,
                    translation: w.translation,
                    phonetic: w.phonetic,
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
