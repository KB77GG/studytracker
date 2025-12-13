// 听写词库列表页面
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
        wx.showLoading({ title: '加载词库...' });

        wx.request({
            url: `${app.globalData.baseUrl}/api/dictation/books`,
            method: 'GET',
            header: {
                'Cookie': wx.getStorageSync('cookie')
            },
            success: (res) => {
                wx.hideLoading();
                if (res.data.ok) {
                    this.setData({
                        books: res.data.books,
                        loading: false
                    });
                }
            },
            fail: (err) => {
                wx.hideLoading();
                // console.error(err);
                this.setData({ loading: false });
            }
        });
    },

    startPractice(e) {
        const { id, title } = e.currentTarget.dataset;
        wx.navigateTo({
            url: `/pages/student/dictation/practice/index?id=${id}&title=${encodeURIComponent(title)}`
        });
    }
})
