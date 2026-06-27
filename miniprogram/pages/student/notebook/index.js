const app = getApp()
const { request } = require('../../../utils/request.js')

function dictationEntryKey(item) {
    const word = String(item.word || '').toLowerCase().trim()
    if (!word) return ''
    return `${word}::${item.dictationMode || 'audio_to_en'}`
}

function getReadingNotebookCacheKey() {
    const token = app.globalData.token || wx.getStorageSync('token') || ''
    const suffix = token ? String(token).slice(-24) : 'guest'
    return `reading_vocab_notebook:${suffix}`
}

function readReadingNotebookCache() {
    const scoped = wx.getStorageSync(getReadingNotebookCacheKey())
    if (Array.isArray(scoped)) return scoped
    const legacy = wx.getStorageSync('reading_vocab_notebook')
    return Array.isArray(legacy) ? legacy : []
}

function writeReadingNotebookCache(list) {
    const next = Array.isArray(list) ? list : []
    wx.setStorageSync(getReadingNotebookCacheKey(), next)
    wx.setStorageSync('reading_vocab_notebook', next)
}

function sortReadingNotebook(list) {
    return (Array.isArray(list) ? list.slice() : []).sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0))
}

function formatDateTime(value) {
    if (!value) return ''
    const time = new Date(value).getTime()
    if (!time) return ''
    const date = new Date(time)
    const month = `${date.getMonth() + 1}`.padStart(2, '0')
    const day = `${date.getDate()}`.padStart(2, '0')
    const hour = `${date.getHours()}`.padStart(2, '0')
    const minute = `${date.getMinutes()}`.padStart(2, '0')
    return `${month}-${day} ${hour}:${minute}`
}

function savedWordSourceLabel(kind) {
    const labels = {
        listening_test: '听力复盘',
        reading_test: '阅读复盘',
        listening_jijing: '听力机经',
        reading_jijing: '阅读机经',
        manual: '网页收藏'
    }
    return labels[kind] || '网页收藏'
}

function formatDuration(seconds) {
    const total = Math.max(0, Number(seconds) || 0)
    if (!total) return '未计时'
    if (total < 60) return `${total} 秒`
    return `${Math.round(total / 60)} 分钟`
}

function moduleMark(category) {
    const text = String(category || '')
    if (text.includes('听')) return 'L'
    if (text.includes('读')) return 'R'
    if (text.includes('写')) return 'W'
    if (text.includes('口')) return 'S'
    if (text.includes('词') || text.includes('单词')) return 'V'
    return 'T'
}

Page({
    data: {
        activeTab: 'history',
        isGuest: false,
        historyList: [],
        historyLoading: false,
        historySummary: {
            total: 0,
            completed: 0,
            total_minutes: 0,
            average_accuracy: null,
            wrong_tasks: 0
        },
        pendingReviewCount: 0,
        wrongQuestionCount: 0,
        savedWordCount: 0,
        // Dictation tab
        list: [],
        isLoading: false,
        lastWrongCount: 0,
        // Reading-vocab tab
        readingList: [],
        readingLoading: false,
        // Saved web vocabulary tab
        vocabList: [],
        vocabLoading: false
    },

    onShow() {
        if (typeof this.getTabBar === 'function' && this.getTabBar()) {
            this.getTabBar().setData({ selected: 1 })
        }
        const isGuest = !!app.globalData.guestMode
        this.setData({ isGuest })
        this.loadHistory()
        this.loadNotebook();
        this.loadLastWrongCount();
        this.loadReadingNotebook();
        this.loadVocab();
    },

    switchTab(e) {
        const tab = e.currentTarget.dataset.tab
        if (!tab || tab === this.data.activeTab) return
        this.setData({ activeTab: tab })
        if (tab === 'history' && !this.data.historyList.length) {
            this.loadHistory()
        }
        if (tab === 'vocab' && !this.data.vocabList.length) {
            this.loadVocab()
        }
    },

    onPullDownRefresh() {
        Promise.all([
            this.loadHistory(),
            this.loadReadingNotebook(),
            this.loadVocab()
        ]).finally(() => wx.stopPullDownRefresh())
    },

    refreshReviewCounts() {
        const historyList = this.data.historyList || []
        const summary = this.data.historySummary || {}
        const wrongFromHistory = historyList.reduce((total, item) => (
            total + Number(item.wrongCount || 0)
        ), 0)
        const wrongFromNotebooks = (this.data.list || []).length + (this.data.readingList || []).length
        const pendingReviewCount = Number(summary.wrong_tasks || 0) || historyList.filter(item => (
            Number(item.wrongCount || 0) > 0 || item.state === 'pending_review'
        )).length

        this.setData({
            pendingReviewCount,
            wrongQuestionCount: wrongFromHistory || wrongFromNotebooks,
            savedWordCount: (this.data.vocabList || []).length
        })
    },

    loadHistory() {
        if (this.data.isGuest || app.globalData.guestMode) {
            const today = new Date()
            const yesterday = new Date(today)
            yesterday.setDate(today.getDate() - 1)
            const dateText = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, '0')}-${String(yesterday.getDate()).padStart(2, '0')}`
            this.setData({
                historyLoading: false,
                historySummary: { total: 3, completed: 3, total_minutes: 68, average_accuracy: 88.7, wrong_tasks: 2 },
                historyList: [
                    { id: 'demo-review-1', date: dateText, category: '雅思听力', title: '剑雅听力精听练习', state: 'completed', stateLabel: '已完成', durationLabel: '28 分钟', accuracyLabel: '92%', moduleMark: 'L', wrongCount: 3, wrongLabel: '错题 3 题', needsReview: true, hasFeedback: true },
                    { id: 'demo-review-2', date: dateText, category: '词汇', title: '核心词汇拼写复习', state: 'completed', stateLabel: '已完成', durationLabel: '20 分钟', accuracyLabel: '86%', moduleMark: 'V', wrongCount: 1, wrongLabel: '错题 1 题', needsReview: true, hasFeedback: false },
                    { id: 'demo-review-3', date: dateText, category: '雅思阅读', title: '阅读词汇选择练习', state: 'completed', stateLabel: '已完成', durationLabel: '20 分钟', accuracyLabel: '88%', moduleMark: 'R', wrongCount: 0, wrongLabel: '', needsReview: false, hasFeedback: true }
                ]
            }, () => {
                this.refreshReviewCounts()
            })
            return Promise.resolve()
        }

        this.setData({ historyLoading: true })
        return request('/miniprogram/student/task-history')
            .then((res) => {
                if (!res || !res.ok) throw new Error((res && res.error) || 'load_failed')
                const historyList = (res.items || []).map(item => {
                    const wrongCount = Number(item.wrong_count || 0)
                    return {
                        ...item,
                        stateLabel: item.state_label || '已完成',
                        durationLabel: formatDuration(item.actual_seconds),
                        accuracyLabel: item.accuracy === null || item.accuracy === undefined
                            ? ''
                            : `${Number(item.accuracy).toFixed(1).replace(/\.0$/, '')}%`,
                        moduleMark: moduleMark(item.category),
                        wrongCount,
                        wrongLabel: wrongCount > 0 ? `错题 ${wrongCount} 题` : '',
                        needsReview: wrongCount > 0 || item.state === 'pending_review'
                    }
                })
                this.setData({
                    historyList,
                    historySummary: res.summary || this.data.historySummary
                }, () => {
                    this.refreshReviewCounts()
                })
            })
            .catch((err) => {
                console.warn('load task history failed', err)
                this.setData({ historyList: [] })
            })
            .finally(() => this.setData({ historyLoading: false }))
    },

    openHistoryTask(e) {
        if (this.data.isGuest) {
            wx.showModal({
                title: '练习记录示例',
                content: '登录后可查看真实答题记录、错题和老师反馈。',
                showCancel: false
            })
            return
        }
        const taskId = e.currentTarget.dataset.id
        if (!taskId) return
        wx.navigateTo({ url: `/pages/student/task/index?id=${taskId}` })
    },

    loadNotebook() {
        this.setData({ isLoading: true });
        try {
            const list = wx.getStorageSync('dictation_notebook') || [];
            if (Array.isArray(list)) {
                const displayList = list.map(item => ({
                    ...item,
                    entryKey: dictationEntryKey(item)
                }));
                displayList.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
                this.setData({ list: displayList }, () => this.refreshReviewCounts());
            } else {
                this.setData({ list: [] }, () => this.refreshReviewCounts());
            }
        } catch (e) {
            console.warn('loadNotebook error', e);
            this.setData({ list: [] }, () => this.refreshReviewCounts());
        } finally {
            this.setData({ isLoading: false });
        }
    },

    loadLastWrongCount() {
        try {
            const saved = wx.getStorageSync('dictation_last_wrong') || [];
            this.setData({
                lastWrongCount: Array.isArray(saved) ? saved.length : 0
            });
        } catch (e) {
            this.setData({ lastWrongCount: 0 });
        }
    },

    async loadReadingNotebook() {
        this.setData({ readingLoading: true });
        try {
            const res = await request('/miniprogram/student/reading-vocab-wrongs');
            if (res.ok && Array.isArray(res.items)) {
                const list = sortReadingNotebook(res.items.map(item => ({
                    entryKey: `${item.task_id}:${item.question_id}`,
                    taskId: item.task_id,
                    taskTitle: item.task_title || '',
                    questionId: item.question_id,
                    word: item.word,
                    isUncertain: !!item.is_uncertain,
                    correctKey: item.correct_key,
                    correctText: item.correct_text,
                    yourKey: item.your_key || '',
                    yourText: item.your_text || '未作答',
                    hint: item.hint || '',
                    updatedAt: item.submitted_at ? new Date(item.submitted_at).getTime() : 0
                })));
                this.setData({ readingList: list }, () => this.refreshReviewCounts());
                try { writeReadingNotebookCache(list); }
                catch (cacheErr) { console.warn('cache reading notebook error', cacheErr); }
                return;
            }

            const list = sortReadingNotebook(readReadingNotebookCache());
            this.setData({ readingList: list }, () => this.refreshReviewCounts());
        } catch (e) {
            console.warn('loadReadingNotebook error', e);
            this.setData({ readingList: sortReadingNotebook(readReadingNotebookCache()) }, () => this.refreshReviewCounts());
        } finally {
            this.setData({ readingLoading: false });
        }
    },

    async loadVocab() {
        this.setData({ vocabLoading: true });
        try {
            const res = await request('/miniprogram/student/saved-words');
            if (res.ok && Array.isArray(res.items)) {
                const list = res.items.map(item => ({
                    id: item.id,
                    word: item.word || '',
                    translation: item.translation || '暂无释义',
                    sourceKind: item.source_kind || 'manual',
                    sourceLabel: savedWordSourceLabel(item.source_kind || 'manual'),
                    sourceRef: item.source_ref || '',
                    updatedAt: item.updated_at ? new Date(item.updated_at).getTime() : 0,
                    updatedText: formatDateTime(item.updated_at)
                }));
                this.setData({ vocabList: list }, () => this.refreshReviewCounts());
            } else {
                this.setData({ vocabList: [] }, () => this.refreshReviewCounts());
            }
        } catch (e) {
            console.warn('loadVocab error', e);
            this.setData({ vocabList: [] }, () => this.refreshReviewCounts());
        } finally {
            this.setData({ vocabLoading: false });
        }
    },

    // ── Dictation actions ──
    retryLastWrong() {
        wx.navigateTo({
            url: '/pages/student/dictation/practice/index?mode=retry_wrong&source=last'
        });
    },

    retryAllNotebook() {
        if (!this.data.list.length) {
            wx.showToast({ title: '错词本是空的', icon: 'none' });
            return;
        }
        wx.navigateTo({
            url: '/pages/student/dictation/practice/index?mode=retry_wrong&source=notebook'
        });
    },

    playWord(e) {
        const word = e.currentTarget.dataset.word;
        if (!word) return;
        if (this.audioCtx) {
            try { this.audioCtx.stop(); } catch (err) {}
        } else {
            this.audioCtx = wx.createInnerAudioContext();
            this.audioCtx.obeyMuteSwitch = false;
            this.audioCtx.autoplay = false;
        }
        const url = `${app.globalData.baseUrl}/dictation/tts?word=${encodeURIComponent(word)}`;
        wx.downloadFile({
            url,
            success: (res) => {
                if (res.statusCode === 200 && res.tempFilePath) {
                    this.audioCtx.src = res.tempFilePath;
                    this.audioCtx.play();
                } else {
                    wx.showToast({ title: '播放失败', icon: 'none' });
                }
            },
            fail: () => wx.showToast({ title: '播放失败', icon: 'none' })
        });
    },

    clearAll() {
        wx.showModal({
            title: '清空错词本',
            content: '确认清空本地听写错词本吗？',
            success: (res) => {
                if (res.confirm) {
                    try { wx.removeStorageSync('dictation_notebook'); } catch (e) {}
                    this.setData({ list: [] }, () => this.refreshReviewCounts());
                }
            }
        });
    },

    deleteItem(e) {
        const entryKey = e.currentTarget.dataset.entrykey;
        if (!entryKey) return;
        const list = (this.data.list || []).filter(item => item.entryKey !== entryKey);
        this.setData({ list }, () => this.refreshReviewCounts());
        try {
            wx.setStorageSync('dictation_notebook', list.map(item => {
                const next = { ...item }
                delete next.entryKey
                return next
            }));
        }
        catch (err) { console.warn('deleteItem error', err); }
    },

    // ── Reading-vocab actions ──
    // Tap a wrong word → jump into that task's redo-wrong flow
    retryReadingItem(e) {
        const taskId = e.currentTarget.dataset.taskid;
        if (!taskId) {
            wx.showToast({ title: '任务信息缺失', icon: 'none' });
            return;
        }
        wx.navigateTo({
            url: `/pages/student/material-choice/practice/index?taskId=${taskId}&mode=redo_wrong`
        });
    },

    deleteReadingItem(e) {
        const entryKey = e.currentTarget.dataset.entrykey;
        if (!entryKey) return;
        const list = (this.data.readingList || []).filter(
            item => item.entryKey !== entryKey
        );
        this.setData({ readingList: list });
        try { writeReadingNotebookCache(list); }
        catch (err) { console.warn('deleteReadingItem error', err); }
    },

    clearReadingAll() {
        wx.showModal({
            title: '清空阅读错词',
            content: '确认清空本地阅读词汇错题吗？',
            success: (res) => {
                if (res.confirm) {
                    try {
                        wx.removeStorageSync(getReadingNotebookCacheKey());
                        wx.removeStorageSync('reading_vocab_notebook');
                    } catch (e) {}
                    this.setData({ readingList: [] }, () => this.refreshReviewCounts());
                }
            }
        });
    },

    async deleteVocab(e) {
        const id = e.currentTarget.dataset.id;
        if (!id) return;
        const previous = this.data.vocabList || [];
        this.setData({ vocabList: previous.filter(item => String(item.id) !== String(id)) }, () => this.refreshReviewCounts());
        try {
            const res = await request(`/miniprogram/student/saved-words/${id}`, {
                method: 'DELETE'
            });
            if (!res.ok) {
                this.setData({ vocabList: previous }, () => this.refreshReviewCounts());
                wx.showToast({ title: '删除失败', icon: 'none' });
            }
        } catch (err) {
            this.setData({ vocabList: previous }, () => this.refreshReviewCounts());
            wx.showToast({ title: '删除失败', icon: 'none' });
        }
    }
})
