const app = getApp()
const { buildStudentStats } = require('../../../utils/demo-data.js')

function toNumber(value, fallback = 0) {
    const number = Number(value)
    return Number.isFinite(number) ? number : fallback
}

function formatPercent(value) {
    if (value === null || value === undefined || value === '') return '—'
    const number = Number(value)
    if (!Number.isFinite(number)) return '—'
    return `${number.toFixed(0)}%`
}

Page({
    data: {
        stats: {
            streak: 0,
            total_hours: 0,
            level: 1,
            weekly_activity: [],
            badges: [],
            average_accuracy: null
        },
        loading: true,
        isGuest: false,
        userInfo: null,
        displayName: '同学',
        avatarText: '学',
        weeklyPracticeCount: 0,
        accuracyLabel: '—',
        weeklyBars: [],
        badgeGrid: [],
        unlockedBadgeCount: 0,
        nextBadgeTip: '完成一次练习即可解锁「初出茅庐」'
    },

    onShow() {
        if (typeof this.getTabBar === 'function' && this.getTabBar()) {
            this.getTabBar().setData({
                selected: 2
            })
        }
        // Guest mode detection
        const isGuest = !!getApp().globalData.guestMode
        const userInfo = isGuest
            ? { nickName: '演示学生' }
            : (app.globalData.userInfo || { nickName: '同学' })
        this.setData({
            isGuest,
            userInfo,
            displayName: userInfo.nickName || '同学',
            avatarText: this.buildAvatarText(userInfo.nickName || '同学')
        })
        if (!isGuest) {
            this.fetchStats()
        } else {
            this.applyStats(buildStudentStats())
        }
    },

    onPullDownRefresh() {
        if (this.data.isGuest) {
            wx.stopPullDownRefresh()
            return
        }
        this.fetchStats().then(() => {
            wx.stopPullDownRefresh()
        })
    },

    goLogin() {
        getApp().globalData.guestMode = false
        getApp().globalData.guestRole = ''
        wx.reLaunch({ url: '/pages/index/index?action=login' })
    },

    buildAvatarText(name) {
        const text = String(name || '同学').trim()
        return text ? text.slice(0, 1) : '学'
    },

    applyStats(rawStats) {
        const stats = rawStats || {}
        const weeklyActivity = Array.isArray(stats.weekly_activity) ? stats.weekly_activity : []
        const values = weeklyActivity.map(item => (
            toNumber(item.minutes, toNumber(item.count, 0) * 20)
        ))
        const maxValue = Math.max(1, ...values)
        const weeklyBars = weeklyActivity.map((item, index) => {
            const value = values[index]
            const rawLabel = String(item.day_label || '')
            const dayLabel = rawLabel.replace(/^周/, '') || ['一', '二', '三', '四', '五', '六', '日'][index] || ''
            return {
                ...item,
                dayLabel,
                value,
                height: Math.max(18, Math.round((value / maxValue) * 100)),
                active: index === weeklyActivity.length - 1
            }
        })
        const weeklyPracticeCount = stats.weekly_practice_count !== undefined
            ? toNumber(stats.weekly_practice_count)
            : weeklyActivity.reduce((total, item) => total + toNumber(item.count), 0)
        const badges = Array.isArray(stats.badges) ? stats.badges : []
        const badgeSlots = [
            { id: 'newbie', name: '初出茅庐', icon: '芽', desc: '开始学习' },
            { id: 'streak_3', name: '坚持不懈', icon: '3', desc: '连续打卡 3 天' },
            { id: 'streak_7', name: '习惯养成', icon: '7', desc: '连续打卡 7 天' },
            { id: 'hours_10', name: '学习新星', icon: '10', desc: '累计学习 10 小时' },
            { id: 'accuracy_90', name: '满分达人', icon: 'A', desc: '高正确率练习' },
            { id: 'review_clear', name: '清空错题', icon: '✓', desc: '完成复盘' }
        ]
        const badgeGrid = badgeSlots.map(slot => {
            const earned = badges.find(item => item.id === slot.id || item.name === slot.name)
            if (earned) {
                return {
                    ...slot,
                    ...earned,
                    icon: earned.icon || slot.icon,
                    unlocked: true
                }
            }
            return {
                ...slot,
                icon: '锁',
                unlocked: false
            }
        })
        const unlockedBadgeCount = badgeGrid.filter(item => item.unlocked).length

        this.setData({
            stats: {
                ...this.data.stats,
                ...stats,
                weekly_activity: weeklyActivity,
                badges
            },
            weeklyPracticeCount,
            accuracyLabel: formatPercent(stats.average_accuracy),
            weeklyBars,
            badgeGrid,
            unlockedBadgeCount,
            nextBadgeTip: this.buildNextBadgeTip(stats),
            loading: false
        })
    },

    buildNextBadgeTip(stats) {
        const streak = toNumber(stats && stats.streak)
        const totalHours = toNumber(stats && stats.total_hours)
        const accuracy = toNumber(stats && stats.average_accuracy, 0)
        if (streak < 3) return `再连续打卡 ${3 - streak} 天解锁「坚持不懈」`
        if (streak < 7) return `再连续打卡 ${7 - streak} 天解锁「习惯养成」`
        if (totalHours < 10) return `再学习 ${Math.max(1, Math.ceil(10 - totalHours))} 小时解锁「学习新星」`
        if (accuracy < 90) return '单次练习正确率达到 90% 可解锁「满分达人」'
        return '继续保持节奏，新的勋章会自动点亮'
    },

    fetchStats() {
        return new Promise((resolve, reject) => {
            wx.request({
                url: `${app.globalData.baseUrl}/miniprogram/student/stats`,
                method: 'GET',
                header: {
                    'Authorization': `Bearer ${app.globalData.token}`
                },
                success: (res) => {
                    if (res.data.ok) {
                        this.applyStats(res.data.stats)
                        resolve()
                    } else {
                        console.error('Fetch stats failed:', res.data.error)
                        this.setData({ loading: false })
                        reject()
                    }
                },
                fail: (err) => {
                    console.error('Request failed:', err)
                    this.setData({ loading: false })
                    reject()
                }
            })
        })
    },

    handleUnbind() {
        wx.showModal({
            title: '提示',
            content: '确定要解除绑定并退出吗？',
            confirmText: '解绑',
            success: async (res) => {
                if (res.confirm) {
                    wx.showLoading({ title: '处理中...' })
                    try {
                        // 尝试调用后端解绑
                        await new Promise((resolve) => {
                            wx.request({
                                url: `${app.globalData.baseUrl}/wechat/unbind`,
                                method: 'POST',
                                header: { 'Authorization': `Bearer ${app.globalData.token}` },
                                complete: resolve // 无论成功失败都继续
                            })
                        })

                        // 强制登出逻辑
                        wx.clearStorageSync()
                        app.globalData.token = null
                        app.globalData.userInfo = null
                        app.globalData.role = null

                        wx.showToast({ title: '已解绑', icon: 'success' })
                        setTimeout(() => {
                            wx.reLaunch({ url: '/pages/index/index' })
                        }, 1500)

                    } catch (err) {
                        console.error('Unbind error:', err)
                        // 异常保底
                        wx.clearStorageSync()
                        wx.reLaunch({ url: '/pages/index/index' })
                    } finally {
                        wx.hideLoading()
                    }
                }
            }
        })
    },

    handleLogout() {
        wx.showModal({
            title: '提示',
            content: '确定要退出登录吗？',
            success: (res) => {
                if (res.confirm) {
                    wx.clearStorageSync()
                    app.globalData.token = null
                    app.globalData.userInfo = null
                    app.globalData.role = null

                    wx.reLaunch({
                        url: '/pages/index/index'
                    })
                }
            }
        })
    }
})
