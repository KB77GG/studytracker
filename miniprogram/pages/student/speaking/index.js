const app = getApp();

Page({
    data: {
        books: [],
        loading: true
    },

    onShow() {
        this.fetchBooks();
    },

    fetchBooks() {
        wx.showLoading({ title: '加载中...' });
        wx.request({
            url: `${app.globalData.baseUrl}/speaking/books`,
            method: 'GET',
            header: {
                'Cookie': wx.getStorageSync('cookie'),
                'Authorization': `Bearer ${wx.getStorageSync('token')}`
            },
            success: (res) => {
                wx.hideLoading();
                if (res.data.ok) {
                    this.setData({ books: res.data.books, loading: false });
                }
            },
            fail: () => {
                wx.hideLoading();
                this.setData({ loading: false });
            }
        });
    },

    startPractice(e) {
        const { id, title } = e.currentTarget.dataset;
        wx.navigateTo({
            url: `/pages/student/speaking/practice/index?id=${id}&title=${encodeURIComponent(title)}`
        });
    }
})
