// 听写练习页面
const app = getApp();

Page({
    data: {
        loading: true,
        completed: false,
        showResult: false,

        // 词书信息
        bookId: null,
        bookTitle: '',
        taskId: null,  // 可选：关联任务

        // 单词列表
        words: [],
        currentIndex: 0,
        totalWords: 0,

        // 当前练习
        currentWord: null,
        userAnswer: '',
        isCorrect: false,
        inputFocus: false,

        // 发音选择
        accent: 'uk',  // uk 或 us
        isPlaying: false,

        // 统计
        correctCount: 0,
        progress: 0,
        accuracy: 0,

        // 音频
        audioContext: null
    },

    onLoad(options) {
        const bookId = options.book_id || options.bookId;
        const taskId = options.task_id || options.taskId;

        if (!bookId) {
            wx.showToast({ title: '参数错误', icon: 'none' });
            setTimeout(() => wx.navigateBack(), 1500);
            return;
        }

        this.setData({ bookId, taskId });
        this.loadBook();

        // 创建音频上下文
        this.audioContext = wx.createInnerAudioContext();
        this.audioContext.onEnded(() => {
            this.setData({ isPlaying: false });
        });
        this.audioContext.onError((err) => {
            console.error('Audio error:', err);
            this.setData({ isPlaying: false });
        });
    },

    onUnload() {
        if (this.audioContext) {
            this.audioContext.destroy();
        }
    },

    // 加载词书数据
    async loadBook() {
        const { bookId } = this.data;

        try {
            const res = await new Promise((resolve, reject) => {
                wx.request({
                    url: `${app.globalData.baseUrl}/api/dictation/books/${bookId}`,
                    header: { 'Authorization': `Bearer ${app.globalData.token}` },
                    success: resolve,
                    fail: reject
                });
            });

            if (res.data.ok) {
                const words = res.data.words || [];
                if (words.length === 0) {
                    wx.showToast({ title: '词库为空', icon: 'none' });
                    setTimeout(() => wx.navigateBack(), 1500);
                    return;
                }

                this.setData({
                    loading: false,
                    bookTitle: res.data.book.title,
                    words: words,
                    totalWords: words.length,
                    currentWord: words[0],
                    inputFocus: true
                });

                // 页面加载后自动播放第一个单词
                setTimeout(() => this.playAudio(), 500);
            } else {
                throw new Error(res.data.error || '加载失败');
            }
        } catch (err) {
            console.error('Load book error:', err);
            wx.showToast({ title: '加载失败', icon: 'none' });
            setTimeout(() => wx.navigateBack(), 1500);
        }
    },

    // 切换发音口音
    switchAccent(e) {
        const accent = e.currentTarget.dataset.accent;
        this.setData({ accent });
        // 切换后自动播放
        this.playAudio();
    },

    // 播放音频
    playAudio() {
        const { currentWord, accent, isPlaying } = this.data;
        if (!currentWord || isPlaying) return;

        const audioPath = accent === 'uk' ? currentWord.audio_uk : currentWord.audio_us;
        if (!audioPath) {
            wx.showToast({ title: '音频不可用', icon: 'none' });
            return;
        }

        const audioUrl = `${app.globalData.baseUrl}/${audioPath}`;

        this.setData({ isPlaying: true });
        this.audioContext.src = audioUrl;
        this.audioContext.play();
    },

    // 输入处理
    onInput(e) {
        this.setData({ userAnswer: e.detail.value });
    },

    // 提交答案
    async submitAnswer() {
        const { currentWord, userAnswer, bookId, taskId } = this.data;

        if (!userAnswer.trim()) {
            wx.showToast({ title: '请输入答案', icon: 'none' });
            return;
        }

        try {
            const res = await new Promise((resolve, reject) => {
                wx.request({
                    url: `${app.globalData.baseUrl}/api/dictation/submit`,
                    method: 'POST',
                    header: {
                        'Authorization': `Bearer ${app.globalData.token}`,
                        'Content-Type': 'application/json'
                    },
                    data: {
                        word_id: currentWord.id,
                        answer: userAnswer.trim(),
                        book_id: bookId,
                        task_id: taskId
                    },
                    success: resolve,
                    fail: reject
                });
            });

            if (res.data.ok) {
                const isCorrect = res.data.is_correct;
                let correctCount = this.data.correctCount;
                if (isCorrect) {
                    correctCount++;
                }

                this.setData({
                    showResult: true,
                    isCorrect: isCorrect,
                    correctCount: correctCount,
                    currentWord: {
                        ...currentWord,
                        phonetic: res.data.phonetic,
                        translation: res.data.translation
                    }
                });
            }
        } catch (err) {
            console.error('Submit error:', err);
            wx.showToast({ title: '提交失败', icon: 'none' });
        }
    },

    // 下一题
    nextWord() {
        const { currentIndex, words, totalWords, correctCount } = this.data;
        const nextIndex = currentIndex + 1;

        if (nextIndex >= totalWords) {
            // 练习完成
            const accuracy = Math.round(correctCount / totalWords * 100);
            this.setData({
                completed: true,
                showResult: false,
                accuracy: accuracy
            });
            return;
        }

        // 进入下一题
        const progress = Math.round((nextIndex / totalWords) * 100);
        this.setData({
            showResult: false,
            currentIndex: nextIndex,
            currentWord: words[nextIndex],
            userAnswer: '',
            progress: progress,
            inputFocus: true
        });

        // 自动播放下一个单词
        setTimeout(() => this.playAudio(), 300);
    },

    // 重新练习
    restartPractice() {
        this.setData({
            completed: false,
            showResult: false,
            currentIndex: 0,
            currentWord: this.data.words[0],
            userAnswer: '',
            correctCount: 0,
            progress: 0,
            inputFocus: true
        });

        setTimeout(() => this.playAudio(), 500);
    },

    // 返回
    goBack() {
        wx.navigateBack();
    },

    // 阻止事件冒泡
    stopPropagation() {
        // Do nothing, just stop propagation
    }
});
