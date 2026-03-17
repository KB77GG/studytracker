const app = getApp()

Page({
    data: {
        bookId: null,
        taskId: null,
        bookTitle: '跟读练习',
        phrases: [],
        currentIndex: 0,
        currentPhrase: {},
        totalPhrases: 0,
        revealed: false,

        // Timer
        practiceStart: null,
        accumulatedSeconds: 0,
        displayTime: '00:00',
        ticker: null,

        // Audio
        isLoadingAudio: false,
        playToken: 0,

        // Recording
        isRecording: false,
        recordFilePath: null,
        isPlayingRecord: false,

        // Progress
        completedSet: {},
        completedCount: 0,
        finished: false,
        isSubmitting: false
    },

    onLoad(options) {
        if (options.taskId) {
            this.setData({ taskId: options.taskId });
            this.fetchTask(options.taskId);
        } else if (options.id) {
            this.setData({ bookId: options.id });
            if (options.title) {
                this.setData({ bookTitle: decodeURIComponent(options.title) });
            }
            this.fetchPhrases(options.id);
        }

        // Audio context
        wx.setInnerAudioOption({ obeyMuteSwitch: false, speakerOn: true });
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
        this.audioCtx.onPlay(() => this.setData({ isLoadingAudio: false }));
        this.audioCtx.onStop(() => this.setData({ isLoadingAudio: false }));
        this.audioCtx.onError((res) => {
            const errMsg = res && res.errMsg ? String(res.errMsg) : '';
            if (errMsg.includes('interrupted by a new load request')) return;
            if (this.pendingPlayToken !== this.playTokenCounter) return;
            console.error('Audio Error:', errMsg);
            // Fallback to Youdao direct
            if (!this.fallbackTried && this.data.currentPhrase.phrase) {
                this.fallbackTried = true;
                const text = this.data.currentPhrase.phrase.trim();
                const direct = `https://dict.youdao.com/dictvoice?audio=${encodeURIComponent(text)}&type=2`;
                this.downloadAndPlay(direct, this.playTokenCounter, true);
                return;
            }
            this.setData({ isLoadingAudio: false });
            wx.showToast({ title: '音频播放失败', icon: 'none' });
        });

        // Recording manager
        this.recorderManager = wx.getRecorderManager();
        this.recorderManager.onStop((res) => {
            this.setData({ isRecording: false, recordFilePath: res.tempFilePath });
        });
        this.recorderManager.onError(() => {
            this.setData({ isRecording: false });
            wx.showToast({ title: '录音失败', icon: 'none' });
        });

        // Playback for recorded audio
        this.recordAudioCtx = wx.createInnerAudioContext();
        this.recordAudioCtx.onPlay(() => this.setData({ isPlayingRecord: true }));
        this.recordAudioCtx.onEnded(() => this.setData({ isPlayingRecord: false }));
        this.recordAudioCtx.onStop(() => this.setData({ isPlayingRecord: false }));
    },

    fetchTask(taskId) {
        wx.showLoading({ title: '加载任务...' });
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
                    this.setData({
                        bookTitle: task.task_name || '跟读练习',
                        rangeStart: task.speaking_phrase_start,
                        rangeEnd: task.speaking_phrase_end
                    });
                    if (task.speaking_book_id) {
                        this.setData({ bookId: task.speaking_book_id });
                        this.fetchPhrases(task.speaking_book_id);
                    } else {
                        wx.hideLoading();
                        wx.showToast({ title: '任务配置错误', icon: 'none' });
                    }
                } else {
                    wx.hideLoading();
                    wx.showToast({ title: '加载失败', icon: 'none' });
                }
            },
            fail: () => {
                wx.hideLoading();
                wx.showToast({ title: '网络错误', icon: 'none' });
            }
        });
    },

    fetchPhrases(id) {
        if (!this.data.taskId) wx.showLoading({ title: '加载中...' });
        wx.request({
            url: `${app.globalData.baseUrl}/speaking/books/${id}`,
            method: 'GET',
            header: {
                'Cookie': wx.getStorageSync('cookie'),
                'Authorization': `Bearer ${wx.getStorageSync('token')}`
            },
            success: (res) => {
                wx.hideLoading();
                if (res.data.ok) {
                    let phrases = res.data.phrases;
                    // Apply range filter if task-based
                    if (this.data.rangeStart || this.data.rangeEnd) {
                        const start = (this.data.rangeStart || 1) - 1;
                        const end = this.data.rangeEnd || phrases.length;
                        phrases = phrases.slice(start, end);
                    }
                    if (phrases.length === 0) {
                        wx.showModal({
                            title: '提示', content: '该范围内没有句子',
                            showCancel: false, success: () => wx.navigateBack()
                        });
                        return;
                    }
                    this.setData({
                        bookTitle: this.data.taskId ? this.data.bookTitle : res.data.book.title,
                        phrases: phrases,
                        totalPhrases: phrases.length,
                        currentIndex: 0,
                        currentPhrase: phrases[0],
                        practiceStart: Date.now(),
                        accumulatedSeconds: 0
                    });
                    this.startTicker();
                    setTimeout(() => this.playCurrentPhrase(), 500);
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

    // ========== Audio Playback ==========
    playCurrentPhrase() {
        const phrase = this.data.currentPhrase.phrase;
        if (!phrase) return;
        const trimmed = phrase.trim();
        this.fallbackTried = false;
        this.playTokenCounter = (this.playTokenCounter || 0) + 1;
        const token = this.playTokenCounter;
        this.pendingPlayToken = token;
        this.setData({ isLoadingAudio: true, playToken: token });

        this.abortAudioDownload();
        if (this.audioCtx && this.audioCtx.src) {
            try { this.audioCtx.stop(); } catch (e) {}
        }

        const proxyUrl = `${app.globalData.baseUrl}/dictation/tts?word=${encodeURIComponent(trimmed)}`;
        this.downloadAndPlay(proxyUrl, token, false);
    },

    abortAudioDownload() {
        if (this.currentDownloadTask && this.currentDownloadTask.abort) {
            try { this.currentDownloadTask.abort(); } catch (e) {}
        }
        this.currentDownloadTask = null;
    },

    downloadAndPlay(url, token, isFallback) {
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
                    const text = this.data.currentPhrase.phrase.trim();
                    const direct = `https://dict.youdao.com/dictvoice?audio=${encodeURIComponent(text)}&type=2`;
                    this.downloadAndPlay(direct, token, true);
                } else {
                    this.setData({ isLoadingAudio: false });
                    wx.showToast({ title: '音频获取失败', icon: 'none' });
                }
            },
            fail: () => {
                this.currentDownloadTask = null;
                if (token !== this.playTokenCounter) return;
                if (!isFallback) {
                    const text = this.data.currentPhrase.phrase.trim();
                    const direct = `https://dict.youdao.com/dictvoice?audio=${encodeURIComponent(text)}&type=2`;
                    this.downloadAndPlay(direct, token, true);
                } else {
                    this.setData({ isLoadingAudio: false });
                    wx.showToast({ title: '音频获取失败', icon: 'none' });
                }
            }
        });
    },

    // ========== Card Interaction ==========
    revealPhrase() {
        const key = `completedSet.${this.data.currentIndex}`;
        const newCount = this.data.completedSet[this.data.currentIndex]
            ? this.data.completedCount
            : this.data.completedCount + 1;
        this.setData({ revealed: true, [key]: true, completedCount: newCount });
    },

    nextPhrase() {
        const nextIdx = this.data.currentIndex + 1;
        if (nextIdx >= this.data.totalPhrases) {
            this.finishPractice();
            return;
        }
        this.setData({
            currentIndex: nextIdx,
            currentPhrase: this.data.phrases[nextIdx],
            revealed: false,
            recordFilePath: null,
            isPlayingRecord: false
        });
        setTimeout(() => this.playCurrentPhrase(), 400);
    },

    prevPhrase() {
        if (this.data.currentIndex <= 0) return;
        const prevIdx = this.data.currentIndex - 1;
        this.setData({
            currentIndex: prevIdx,
            currentPhrase: this.data.phrases[prevIdx],
            revealed: false,
            recordFilePath: null,
            isPlayingRecord: false
        });
        setTimeout(() => this.playCurrentPhrase(), 400);
    },

    // ========== Recording ==========
    startRecording() {
        this.setData({ isRecording: true, recordFilePath: null });
        this.recorderManager.start({
            format: 'mp3',
            sampleRate: 16000,
            numberOfChannels: 1
        });
    },

    stopRecording() {
        this.recorderManager.stop();
    },

    playRecording() {
        if (!this.data.recordFilePath) return;
        this.recordAudioCtx.src = this.data.recordFilePath;
        this.recordAudioCtx.play();
    },

    // ========== Finish & Submit ==========
    finishPractice() {
        const durationSeconds = this.computeDurationSeconds();
        this.stopTicker();

        if (this.data.taskId) {
            this.submitTaskResult(durationSeconds);
        } else {
            this.setData({ finished: true });
            wx.showToast({ title: '练习完成', icon: 'success' });
        }
    },

    submitTaskResult(durationSeconds) {
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
                accuracy: 100,
                completion_rate: 100,
                duration_seconds: durationSeconds
            },
            success: (res) => {
                wx.hideLoading();
                if (res.data.ok) {
                    this.setData({ finished: true });
                    wx.showToast({ title: '提交成功', icon: 'success' });
                } else {
                    wx.showToast({ title: '提交失败', icon: 'none' });
                }
            },
            fail: () => {
                wx.hideLoading();
                wx.showToast({ title: '网络错误', icon: 'none' });
            },
            complete: () => this.setData({ isSubmitting: false })
        });
    },

    // ========== Timer ==========
    computeDurationSeconds() {
        let elapsed = this.data.accumulatedSeconds;
        if (this.data.practiceStart) {
            elapsed += Math.floor((Date.now() - this.data.practiceStart) / 1000);
        }
        return elapsed;
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

    // ========== Lifecycle ==========
    onHide() {
        this.pauseTimer();
        this.stopTicker();
    },

    onShow() {
        if (this.data.totalPhrases > 0 && !this.data.finished) {
            this.resumeTimer();
        }
    },

    onUnload() {
        this.pauseTimer();
        this.stopTicker();
        this.abortAudioDownload();
        if (this.audioCtx) { this.audioCtx.destroy(); this.audioCtx = null; }
        if (this.recordAudioCtx) { this.recordAudioCtx.destroy(); this.recordAudioCtx = null; }
    },

    returnAfterFinish() {
        wx.navigateBack();
    }
})
