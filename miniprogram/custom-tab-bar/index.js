Component({
    data: {
        selected: 0,
        color: "#7A7E83",
        selectedColor: "#667eea",
        list: [], // Will be set based on role
        studentList: [{
            pagePath: "/pages/student/home/index",
            iconPath: "/images/tabbar/task.png",
            selectedIconPath: "/images/tabbar/task_active.png",
            text: "任务"
        }, {
            pagePath: "/pages/student/stats/index",
            iconPath: "/images/tabbar/profile.png",
            selectedIconPath: "/images/tabbar/profile_active.png",
            text: "我的"
        }],
        parentList: [{
            pagePath: "/pages/parent/home/index",
            iconPath: "/images/tabbar/task.png",
            selectedIconPath: "/images/tabbar/task_active.png",
            text: "报告"
        }, {
            pagePath: "/pages/parent/profile/index",
            iconPath: "/images/tabbar/profile.png",
            selectedIconPath: "/images/tabbar/profile_active.png",
            text: "我的"
        }]
    },
    attached() {
        const role = wx.getStorageSync('role');
        if (role === 'parent') {
            this.setData({
                list: this.data.parentList
            });
        } else {
            this.setData({
                list: this.data.studentList
            });
        }
    },
    methods: {
        switchTab(e) {
            const data = e.currentTarget.dataset
            const url = data.path
            wx.switchTab({
                url
            })
        }
    }
})
