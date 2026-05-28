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

Page({
    data: {
        activeTab: 'dictation',          // 'dictation' | 'reading' | 'vocab'
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
        this.loadNotebook();
        this.loadLastWrongCount();
        this.loadReadingNotebook();
        if (this.data.activeTab === 'vocab') {
            this.loadVocab();
        }
    },

    switchTab(e) {
        const tab = e.currentTarget.dataset.tab
        if (!tab || tab === this.data.activeTab) return
        this.setData({ activeTab: tab })
        if (tab === 'vocab' && !this.data.vocabList.length) {
            this.loadVocab()
        }
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
                this.setData({ list: displayList });
            } else {
                this.setData({ list: [] });
            }
        } catch (e) {
            console.warn('loadNotebook error', e);
            this.setData({ list: [] });
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
                this.setData({ readingList: list });
                try { writeReadingNotebookCache(list); }
                catch (cacheErr) { console.warn('cache reading notebook error', cacheErr); }
                return;
            }

            const list = sortReadingNotebook(readReadingNotebookCache());
            this.setData({ readingList: list });
        } catch (e) {
            console.warn('loadReadingNotebook error', e);
            this.setData({ readingList: sortReadingNotebook(readReadingNotebookCache()) });
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
                this.setData({ vocabList: list });
            } else {
                this.setData({ vocabList: [] });
            }
        } catch (e) {
            console.warn('loadVocab error', e);
            this.setData({ vocabList: [] });
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
                    this.setData({ list: [] });
                }
            }
        });
    },

    deleteItem(e) {
        const entryKey = e.currentTarget.dataset.entrykey;
        if (!entryKey) return;
        const list = (this.data.list || []).filter(item => item.entryKey !== entryKey);
        this.setData({ list });
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
                    this.setData({ readingList: [] });
                }
            }
        });
    },

    async deleteVocab(e) {
        const id = e.currentTarget.dataset.id;
        if (!id) return;
        const previous = this.data.vocabList || [];
        this.setData({ vocabList: previous.filter(item => String(item.id) !== String(id)) });
        try {
            const res = await request(`/miniprogram/student/saved-words/${id}`, {
                method: 'DELETE'
            });
            if (!res.ok) {
                this.setData({ vocabList: previous });
                wx.showToast({ title: '删除失败', icon: 'none' });
            }
        } catch (err) {
            this.setData({ vocabList: previous });
            wx.showToast({ title: '删除失败', icon: 'none' });
        }
    }
})
