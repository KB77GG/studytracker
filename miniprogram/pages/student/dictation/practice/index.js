const app = getApp()

Page({
    data: {
        bookId: null,
        bookTitle: '听写练习',
        words: [],
        currentIndex: 0,
        currentWord: {},
        totalWords: 0,

        // UI State
        inputValue: '',
        showResult: false,
        isCorrect: false,
        inputFocus: true
    },

    onLoad: function (options) {
        if (options.taskId) {
            this.setData({ taskId: options.taskId });
            this.fetchTask(options.taskId);
        } else if (options.id) {
            this.setData({ bookId: options.id });
            this.fetchWords(options.id);
        }

        // Create Audio Context
        this.audioCtx = wx.createInnerAudioContext();
        this.audioCtx.onError((res) => {
            console.error('Audio Error:', res.errMsg);
            wx.showToast({ title: '音频播放失败', icon: 'none' });
        });
    },

    fetchTask: function (taskId) {
        wx.showLoading({ title: '加载任务...' });
        wx.request({
            url: `${app.globalData.baseUrl}/api/miniprogram/student/tasks/${taskId}`,
            method: 'GET',
            header: { 'Cookie': wx.getStorageSync('cookie') },
            success: (res) => {
                if (res.data.ok) {
                    const task = res.data.task;
                    const material = task.material || {};

                    this.setData({
                        bookTitle: task.task_name,
                        rangeStart: material.dictation_word_start,
                        rangeEnd: material.dictation_word_end
                    });

                    if (material.dictation_book_id) {
                        this.setData({ bookId: material.dictation_book_id });
                        this.fetchWords(material.dictation_book_id);
                    }
                }
            }
        });
    },

    fetchWords: function (id) {
        if (!this.data.taskId) wx.showLoading({ title: '加载单词...' });

        wx.request({
            url: `${app.globalData.baseUrl}/api/dictation/books/${id}`,
            method: 'GET',
            header: {
                'Cookie': wx.getStorageSync('cookie')
            },
            success: (res) => {
                wx.hideLoading();
                if (res.data.ok) {
                    let words = res.data.words;

                    // Apply Range Filter if set
                    if (this.data.rangeStart || this.data.rangeEnd) {
                        const start = (this.data.rangeStart || 1) - 1; // 0-based
                        const end = this.data.rangeEnd || words.length;
                        words = words.slice(start, end);
                    }

                    this.setData({
                        // Only update title if not set by task
                        bookTitle: this.data.taskId ? this.data.bookTitle : res.data.book.title,
                        words: words,
                        totalWords: words.length,
                        currentIndex: 0
                    });

                    if (words.length > 0) {
                        this.loadWord(0);
                    } else {
                        wx.showModal({
                            title: '提示',
                            content: '该范围内没有单词',
                            showCancel: false,
                            success: () => wx.navigateBack()
                        });
                    }
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

    onUnload: function () {
        if (this.audioCtx) {
            this.audioCtx.destroy();
        }
    },

    loadWord: function (index) {
        const word = this.data.words[index];
        this.setData({
            currentWord: word,
            currentIndex: index,
            inputValue: '',
            showResult: false,
            isCorrect: false,
            inputFocus: true
        });

        // Auto play
        setTimeout(() => {
            this.playCurrentWord();
        }, 500);
    },

    playCurrentWord: function () {
        const word = this.data.currentWord.word;
        if (!word) return;

        // Use generic TTS API
        // Option 1: Youdao (High quality, widely used)
        const url = `https://dict.youdao.com/dictvoice?audio=${encodeURIComponent(word)}&type=2`;

        this.audioCtx.src = url;
        this.audioCtx.play();
    },

    onInput: function (e) {
        this.setData({
            inputValue: e.detail.value
        });
    },

    checkAnswer: function () {
        if (this.data.showResult) return; // Prevent double submit

        const input = this.data.inputValue.trim().toLowerCase();
        const target = this.data.currentWord.word.toLowerCase();

        if (!input) {
            wx.showToast({ title: '请输入单词', icon: 'none' });
            return;
        }

        const isCorrect = input === target;

        this.setData({
            showResult: true,
            isCorrect: isCorrect
        });

        // Play sound effect (optional) if needed
        if (isCorrect) {
            wx.showToast({ title: '正确!', icon: 'success', duration: 1000 });
            // Logic to record attempt could be added here
        } else {
            // Logic for incorrect
        }
    },

    nextWord: function () {
        const nextIndex = this.data.currentIndex + 1;
        if (nextIndex < this.data.totalWords) {
            this.loadWord(nextIndex);
        } else {
            wx.showModal({
                title: '恭喜',
                content: '本词库练习完成！',
                showCancel: false,
                success: () => {
                    wx.navigateBack();
                }
            });
        }
    }
})
