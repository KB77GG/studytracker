Component({
    data: {
        selected: 0,
        color: "#9aa5b1",
        selectedColor: "#3a8c82",
        list: [], // Will be set based on role
        studentList: [],
        parentList: []
    },
    attached() {
        const brand = this.data.selectedColor
        const gray = this.data.color

        const buildIcon = (type, color) => {
            const c = encodeURIComponent(color)
            let path = ''
            if (type === 'task') {
                path = `<circle cx="16" cy="16" r="12" fill="none" stroke="${c}" stroke-width="2.4"/><path d="M11.5 16.5l3.5 3.5 6.5-7.5" fill="none" stroke="${c}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>`
            } else if (type === 'hammer') {
                path = `<path d="M10 13.5l4.8-4.8 2.4 2.4-4.8 4.8z" fill="none" stroke="${c}" stroke-width="2.4" stroke-linejoin="round"/><path d="M17.5 11l4.8 4.8-1.9 1.9-4.8-4.8z" fill="none" stroke="${c}" stroke-width="2.4" stroke-linejoin="round"/><path d="M9.7 22.3l4.9-4.9" stroke="${c}" stroke-width="2.4" stroke-linecap="round"/>`
            } else if (type === 'practice') {
                path = `<rect x="12" y="5" width="8" height="14" rx="4" fill="none" stroke="${c}" stroke-width="2.4"/><path d="M16 19v4.5" stroke="${c}" stroke-width="2.4" stroke-linecap="round"/><path d="M11 23.5h10" stroke="${c}" stroke-width="2.4" stroke-linecap="round"/><path d="M8.5 13.5c0 4.1 3.3 7.5 7.5 7.5s7.5-3.4 7.5-7.5" fill="none" stroke="${c}" stroke-width="2.4" stroke-linecap="round"/>`
            } else if (type === 'note') {
                path = `<rect x="9.5" y="9" width="13" height="14" rx="2.5" fill="none" stroke="${c}" stroke-width="2.4"/><path d="M16 9v14" stroke="${c}" stroke-width="2.4"/><path d="M12 13h4" stroke="${c}" stroke-width="2.2" stroke-linecap="round"/><path d="M12 17h4" stroke="${c}" stroke-width="2.2" stroke-linecap="round"/>`
            } else if (type === 'user') {
                path = `<circle cx="16" cy="12" r="5" fill="none" stroke="${c}" stroke-width="2.4"/><path d="M9 22.5c0-3.3 3.2-6 7-6s7 2.7 7 6" fill="none" stroke="${c}" stroke-width="2.4" stroke-linecap="round"/>`
            } else if (type === 'report') {
                path = `<rect x="10" y="9" width="12" height="14" rx="2" fill="none" stroke="${c}" stroke-width="2.4"/><path d="M12.5 13h7" stroke="${c}" stroke-width="2.2" stroke-linecap="round"/><path d="M12.5 17h6" stroke="${c}" stroke-width="2.2" stroke-linecap="round"/><path d="M12.5 21h4" stroke="${c}" stroke-width="2.2" stroke-linecap="round"/>`
            }
            return `data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'>${path}</svg>`
        }

        const studentList = [
            {
                pagePath: "/pages/student/home/index",
                text: "任务",
                iconPath: buildIcon('task', gray),
                selectedIconPath: buildIcon('task', brand)
            },
            {
                pagePath: "/pages/student/stats/index",
                text: "我的",
                iconPath: buildIcon('user', gray),
                selectedIconPath: buildIcon('user', brand)
            },
            {
                pagePath: "/pages/student/hammer/index",
                text: "对练",
                iconPath: buildIcon('practice', gray),
                selectedIconPath: buildIcon('practice', brand)
            }
        ]

        const parentList = [
            {
                pagePath: "/pages/parent/home/index",
                text: "报告",
                iconPath: buildIcon('report', gray),
                selectedIconPath: buildIcon('report', brand)
            },
            {
                pagePath: "/pages/parent/profile/index",
                text: "我的",
                iconPath: buildIcon('user', gray),
                selectedIconPath: buildIcon('user', brand)
            }
        ]

        const teacherList = [
            {
                pagePath: "/pages/teacher/home/index",
                text: "课表",
                iconPath: buildIcon('task', gray),
                selectedIconPath: buildIcon('task', brand)
            }
        ]

        const role = wx.getStorageSync('role');
        this.setData({
            studentList,
            parentList,
            list: role === 'parent' ? parentList : (role === 'teacher' ? teacherList : studentList)
        });
        this.setSelected();
    },
    methods: {
        setSelected(route) {
            const pages = getCurrentPages();
            const currentRoute = route || (pages[pages.length - 1] && ('/' + pages[pages.length - 1].route));
            const idx = this.data.list.findIndex(item => item.pagePath === currentRoute);
            if (idx !== -1 && idx !== this.data.selected) {
                this.setData({ selected: idx });
            }
        },
        switchTab(e) {
            const data = e.currentTarget.dataset
            const url = data.path
            this.setData({ selected: data.index })
            wx.switchTab({
                url
            })
        }
    }
})
