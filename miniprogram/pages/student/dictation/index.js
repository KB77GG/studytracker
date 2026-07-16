// 听写词库列表页面
const { request } = require('../../../utils/request.js');
const { legacyWrongItemBelongsToBook } = require('../../../utils/dictation-review.js');

Page({
    data: {
        books: [],
        loading: true,
        serverWrongCount: 0
    },

    onShow() {
        this.fetchBooks();
        this.loadServerWrongCount();
    },

    fetchBooks() {
        wx.showLoading({ title: '加载词库...' });

        request('/dictation/books')
            .then((res) => {
                wx.hideLoading();
                if (res && res.ok) {
                    this.setData({ books: this.decorateLegacyCounts(res.books || []), loading: false });
                    return;
                }
                this.setData({ loading: false });
            })
            .catch(() => {
                wx.hideLoading();
                this.setData({ loading: false });
            });
    },

    loadServerWrongCount() {
        request('/miniprogram/student/dictation-wrongs')
            .then((res) => {
                if (res && res.ok) this.setData({ serverWrongCount: res.count || 0 });
            })
            .catch(() => {});
    },

    loadLegacyWrongWords() {
        const last = wx.getStorageSync('dictation_last_wrong') || [];
        const notebook = wx.getStorageSync('dictation_notebook') || [];
        const all = (Array.isArray(last) ? last : []).concat(Array.isArray(notebook) ? notebook : []);
        const seen = {};
        return all.filter(item => {
            const label = item.word || item.name;
            const key = `${item.book_id || item.dictation_book_id || ''}:${String(label || '').toLowerCase()}`;
            if (!label || seen[key]) return false;
            seen[key] = true;
            return true;
        });
    },

    decorateLegacyCounts(books) {
        const wrong = this.loadLegacyWrongWords();
        return (books || []).map(book => Object.assign({}, book, {
            local_wrong_count: wrong.filter(item => Number(item.book_id || item.dictation_book_id) === Number(book.id)).length
        }));
    },

    confirmImportLegacyWrongWords(e) {
        const bookId = Number(e.currentTarget.dataset.id);
        const localItems = this.loadLegacyWrongWords();
        Promise.all([
            request(`/dictation/books/${bookId}`),
            request('/miniprogram/student/dictation-wrongs')
        ]).then(([bookResult, identity]) => {
                if (!identity || !identity.ok || !identity.student) throw new Error('identity_failed');
                const bookWords = (bookResult && bookResult.words) || [];
                const items = localItems.filter(item => {
                    return legacyWrongItemBelongsToBook(item, bookId, bookWords);
                });
                if (!items.length) {
                    wx.showToast({ title: '本机没有属于这本词书的错词', icon: 'none' });
                    return;
                }
                wx.showModal({
                    title: '确认导入错词',
                    content: `当前账号：${identity.student.name || identity.student.username}\n将导入 ${items.length} 个“${e.currentTarget.dataset.title}”错词。`,
                    confirmText: '确认导入',
                    success: (modal) => {
                        if (!modal.confirm) return;
                        request('/miniprogram/student/dictation-wrongs/import', {
                            method: 'POST',
                            data: {
                                book_id: bookId,
                                words: items.map(item => ({ word: item.word || item.name })),
                                confirmed: true,
                                confirmed_student_id: identity.student.id
                            }
                        }).then((result) => {
                            if (!result || !result.ok) {
                                wx.showToast({ title: '导入失败', icon: 'none' });
                                return;
                            }
                            wx.showToast({ title: `已导入 ${result.imported_count} 词`, icon: 'success' });
                            this.fetchBooks();
                            this.loadServerWrongCount();
                        }).catch(() => wx.showToast({ title: '网络错误', icon: 'none' }));
                    }
                });
            })
            .catch(() => wx.showToast({ title: '无法确认当前账号', icon: 'none' }));
    },

    startPractice(e) {
        const { id, title } = e.currentTarget.dataset;
        wx.navigateTo({
            url: `/pages/student/dictation/practice/index?id=${id}&title=${encodeURIComponent(title)}`
        });
    },

    startSpell(e) {
        const { id, title } = e.currentTarget.dataset;
        wx.navigateTo({
            url: `/pages/student/dictation/spell/index?id=${id}&title=${encodeURIComponent(title)}`
        });
    }
})
