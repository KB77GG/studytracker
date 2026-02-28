const app = getApp()

Page({
    data: {
        list: [],
        isLoading: false,
        lastWrongCount: 0
    },

    onShow() {
        this.loadNotebook();
        this.loadLastWrongCount();
    },

    loadNotebook() {
        this.setData({ isLoading: true });
        try {
            const list = wx.getStorageSync('dictation_notebook') || [];
            if (Array.isArray(list)) {
                // sort by updatedAt desc
                list.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
                this.setData({ list });
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

    // 重练上次练习的错词
    retryLastWrong() {
        wx.navigateTo({
            url: '/pages/student/dictation/practice/index?mode=retry_wrong&source=last'
        });
    },

    // 重练错词本全部错词
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
            content: '确认清空本地错词本吗？',
            success: (res) => {
                if (res.confirm) {
                    try {
                        wx.removeStorageSync('dictation_notebook');
                    } catch (e) {}
                    this.setData({ list: [] });
                }
            }
        });
    },

    deleteItem(e) {
        const word = e.currentTarget.dataset.word;
        if (!word) return;
        const list = (this.data.list || []).filter(item => (item.word || '').toLowerCase() !== String(word).toLowerCase());
        this.setData({ list });
        try {
            wx.setStorageSync('dictation_notebook', list);
        } catch (err) {
            console.warn('deleteItem error', err);
        }
    }
})
