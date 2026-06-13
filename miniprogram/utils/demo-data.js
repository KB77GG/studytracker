const pad = (value) => String(value).padStart(2, '0')

const formatDate = (date) => (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
)

const formatShortDate = (date) => `${date.getMonth() + 1}/${date.getDate()}`

const addDays = (date, days) => {
    const result = new Date(date)
    result.setDate(result.getDate() + days)
    return result
}

const buildStudentTasks = () => ([
    {
        id: 'demo-listening',
        task_name: '剑雅听力精听练习',
        module: '雅思听力',
        planned_minutes: 30,
        status: 'completed',
        actual_seconds: 1680
    },
    {
        id: 'demo-vocabulary',
        task_name: '核心词汇拼写复习',
        module: '词汇',
        planned_minutes: 20,
        status: 'in_progress',
        actual_seconds: 480
    },
    {
        id: 'demo-reading',
        task_name: '阅读长难句分析',
        module: '雅思阅读',
        planned_minutes: 25,
        status: 'pending',
        actual_seconds: 0
    }
])

const buildStudentStats = () => {
    const today = new Date()
    const weeklyActivity = [-6, -5, -4, -3, -2, -1, 0].map((offset, index) => ({
        date: formatDate(addDays(today, offset)),
        day_label: ['一', '二', '三', '四', '五', '六', '日'][index],
        count: [2, 3, 2, 4, 3, 5, 3][index]
    }))
    return {
        streak: 8,
        total_hours: 26.5,
        level: 4,
        weekly_activity: weeklyActivity,
        badges: [
            { id: 'demo-1', icon: '7', name: '坚持一周', desc: '连续完成学习任务' },
            { id: 'demo-2', icon: 'A', name: '词汇进阶', desc: '累计复习 300 个词' },
            { id: 'demo-3', icon: '90', name: '高正确率', desc: '单次练习正确率超过 90%' }
        ]
    }
}

const buildParentStats = () => {
    const today = new Date()
    const rates = [75, 100, 80, 100, 67, 100, 80]
    const weekly = rates.map((rate, index) => {
        const total = index % 2 === 0 ? 5 : 4
        return {
            date: formatShortDate(addDays(today, index - 6)),
            total,
            completed: Math.round(total * rate / 100),
            rate
        }
    })
    const todayText = formatDate(today)
    const yesterdayText = formatDate(addDays(today, -1))
    return {
        ok: true,
        isStudying: true,
        today: { rate: 80, pending: 1, completed: 4, in_progress: 1, total: 5 },
        weekly,
        subjects: [
            { subject: '雅思听力', count: 12, percent: 86 },
            { subject: '雅思阅读', count: 9, percent: 64 },
            { subject: '词汇', count: 7, percent: 50 }
        ],
        feedback_total: 2,
        feedback: [
            {
                id: 'demo-feedback-1',
                course_name: '雅思听力',
                schedule_date: todayText,
                start_time: '16:00',
                end_time: '17:00',
                teacher_name: '李老师',
                feedback_text: '课堂专注度良好，定位关键词的速度有提升。建议课后复盘错题并整理同义替换。'
            },
            {
                id: 'demo-feedback-2',
                course_name: '词汇巩固',
                schedule_date: yesterdayText,
                start_time: '18:30',
                end_time: '19:20',
                teacher_name: '王老师',
                feedback_text: '本次拼写正确率稳定，易错词需要继续按复习计划巩固。'
            }
        ],
        recent: [
            {
                id: 'demo-recent-1',
                category: '雅思听力',
                date: todayText,
                detail: '完成剑雅听力精听练习',
                status: 'done',
                accuracy: 88,
                completion_rate: null,
                teacher_note: '注意复数和数字信息'
            },
            {
                id: 'demo-recent-2',
                category: '词汇',
                date: yesterdayText,
                detail: '完成核心词汇拼写复习',
                status: 'done',
                accuracy: 92,
                completion_rate: null,
                teacher_note: ''
            }
        ]
    }
}

const buildParentDemo = () => ({
    students: [{ id: 'demo-student', name: '演示学生' }],
    stats: buildParentStats()
})

const buildTeacherSchedules = (monthValue) => {
    const now = new Date()
    const currentMonth = `${now.getFullYear()}-${pad(now.getMonth() + 1)}`
    let dates = []
    if (!monthValue || monthValue === currentMonth) {
        dates = [now, addDays(now, 1), addDays(now, 3)]
    } else {
        const [year, month] = monthValue.split('-').map(Number)
        dates = [5, 12, 19].map(day => new Date(year, month - 1, day))
    }
    const courses = [
        { name: '雅思听力', student: '演示学生', start: '10:00', end: '11:00', feedback: null },
        {
            name: '雅思阅读',
            student: '陈同学',
            start: '14:00',
            end: '15:30',
            feedback: { text: '课堂完成情况良好，已记录重点错题。', image: '' }
        },
        { name: '词汇巩固', student: '林同学', start: '18:30', end: '19:20', feedback: null }
    ]
    return dates.map((date, index) => {
        const course = courses[index]
        const dateText = formatDate(date)
        return {
            schedule_uid: `demo-schedule-${index + 1}`,
            schedule_id: `demo-${index + 1}`,
            student_id: `demo-student-${index + 1}`,
            student_name: course.student,
            teacher_id: 'demo-teacher',
            teacher_name: '演示老师',
            course_name: course.name,
            schedule_date: dateText,
            start_time: `${dateText} ${course.start}`,
            end_time: `${dateText} ${course.end}`,
            feedback: course.feedback
        }
    })
}

const buildTeacherMonthlyStats = () => ({
    subjects: [
        { subject: '雅思听力', sessions: 18, hours: 18 },
        { subject: '雅思阅读', sessions: 14, hours: 21 },
        { subject: '词汇巩固', sessions: 10, hours: 8.5 }
    ],
    total: { sessions: 42, hours: 47.5 }
})

module.exports = {
    buildParentDemo,
    buildParentStats,
    buildStudentStats,
    buildStudentTasks,
    buildTeacherMonthlyStats,
    buildTeacherSchedules
}
