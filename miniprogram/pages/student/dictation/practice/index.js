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

    fetchWords: function (id) {
        if (!this.data.taskId) wx.showLoading({ title: '加载单词...' });

        wx.request({
            url: `${app.globalData.baseUrl}/dictation/books/${id}`,
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
                        currentIndex: 0
                    });

                    this.loadWord(0);
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
        if (this.data.showResult) return;

        const input = this.data.inputValue.trim().toLowerCase();
        const target = this.data.currentWord.word.toLowerCase();
        const isCorrect = input === target;

        if (!input) {
            wx.showToast({ title: '请输入单词', icon: 'none' });
            return;
        }

        if (!isCorrect) {
            const wrongList = this.data.wrongWords;
            wrongList.push(`${this.data.currentWord.word} (写成了: ${input})`);
            this.setData({ wrongWords: wrongList });
        } else {
            this.setData({ correctCount: this.data.correctCount + 1 });
        }

        this.setData({
            showResult: true,
            isCorrect: isCorrect
        });

        if (isCorrect) {
            wx.showToast({ title: '正确!', icon: 'success', duration: 1000 });
        }
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

        let content = `正确率: ${accuracy}%`;
        if (this.data.wrongWords.length > 0) {
            content += `\n错词: ${this.data.wrongWords.length} 个`;
        }

        wx.showModal({
            title: '练习完成',
            content: content,
            confirmText: '提交结果',
            showCancel: !this.data.taskId, // If it's a task, force submit (kind of)
            success: (res) => {
                if (res.confirm && this.data.taskId) {
                    this.submitTaskResult(accuracy, this.data.wrongWords);
                } else if (res.confirm || !this.data.taskId) {
                    wx.navigateBack();
                }
            }
        });
    },

    submitTaskResult: function (accuracy, wrongWords) {
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
                duration_seconds: 0 // Could handle timing later
            },
            success: (res) => {
                wx.hideLoading();
                if (res.data.ok) {
                    wx.showToast({ title: '提交成功', icon: 'success' });
                    setTimeout(() => wx.navigateBack(), 1500);
                } else {
                    wx.showToast({ title: '提交失败', icon: 'none' });
                }
            },
            fail: () => {
                wx.hideLoading();
                wx.showToast({ title: '网络错误', icon: 'none' });
            }
        });
    }
})
