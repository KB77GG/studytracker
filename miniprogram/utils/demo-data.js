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

const buildStudentTasks = () => []

const buildStudentStats = () => {
    const today = new Date()
    const weeklyActivity = [-6, -5, -4, -3, -2, -1, 0].map((offset, index) => ({
        date: formatDate(addDays(today, offset)),
        day_label: ['一', '二', '三', '四', '五', '六', '日'][index],
        count: [1, 1, 2, 1, 2, 0, 1][index],
        minutes: [24, 36, 72, 18, 44, 0, 28][index]
    }))
    return {
        streak: 1,
        total_hours: 6.5,
        weekly_practice_count: 8,
        average_accuracy: 76,
        level: 1,
        weekly_activity: weeklyActivity,
        badges: [
            { id: 'newbie', icon: '芽', name: '初出茅庐', desc: '开始你的学习之旅' }
        ],
        goal_label: '雅思目标 6.5 · 距考试 38 天'
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
        today: {
            rate: 40,
            total: 5,
            not_started: 1,
            in_progress: 1,
            pending_review: 1,
            pending: 1,
            completed: 2
        },
        today_tasks: [
            { id: 'demo-task-1', category: '雅思听力', task_name: '剑雅听力精听练习', planned_minutes: 30, state: 'completed', state_label: '已完成' },
            { id: 'demo-task-2', category: '词汇', task_name: '核心词汇拼写复习', planned_minutes: 20, state: 'completed', state_label: '已完成' },
            { id: 'demo-task-3', category: '雅思阅读', task_name: '阅读长难句分析', planned_minutes: 25, state: 'not_started', state_label: '待完成' },
            { id: 'demo-task-4', category: '雅思口语', task_name: 'Part 2 录音练习', planned_minutes: 15, state: 'in_progress', state_label: '进行中' },
            { id: 'demo-task-5', category: '写作', task_name: '小作文批改任务', planned_minutes: 30, state: 'pending_review', state_label: '待审核' }
        ],
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
                result_summary: '共 25 题 · 已答 25 · 正确 22 · 错误 3',
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
                result_summary: '应背 12 词 · 已测 12 · 正确 10 · 需复习 2',
                teacher_note: ''
            }
        ]
    }
}

const buildParentDemo = () => ({
    students: [{ id: 'demo-student', name: '演示学生' }],
    stats: buildParentStats()
})

const buildParentTaskDetail = (taskId) => {
    const today = new Date()
    const isVocabulary = String(taskId || '').includes('recent-2') || String(taskId || '').includes('vocabulary')
    if (isVocabulary) {
        return {
            id: taskId || 'demo-recent-2',
            student_name: '演示学生',
            date: formatDate(addDays(today, -1)),
            category: '词汇',
            title: '核心词汇拼写复习',
            state: 'completed',
            state_label: '已完成',
            kind: 'dictation',
            accuracy: 83,
            summary_text: '应背 6 词 · 已测 6 · 正确 5 · 需复习 1',
            summary: { assigned_total: 6, attempted_total: 6, correct_total: 5, wrong_total: 1, pending_total: 0, mastered_total: 2 },
            teacher_note: '错词安排在下一次复习中再次检测。',
            student_note: '',
            evidence: { image: [], audio: [], doc: [], other: [] },
            items: [
                { id: 'word-1', number: 1, prompt: 'achieve', translation: '实现；达到', student_answer: 'achieve', correct_answer: 'achieve', result_status: 'correct', result_label: '正确', attempt_count: 1, mistake_count: 0, mastery_label: '已掌握', review_level: 5 },
                { id: 'word-2', number: 2, prompt: 'accuracy', translation: '准确性', student_answer: 'accurcy', correct_answer: 'accuracy', result_status: 'wrong', result_label: '需复习', attempt_count: 2, mistake_count: 2, mastery_label: '巩固中', review_level: 1, next_review_at: formatDate(addDays(today, 1)) },
                { id: 'word-3', number: 3, prompt: 'heritage', translation: '遗产；传统', student_answer: 'heritage', correct_answer: 'heritage', result_status: 'correct', result_label: '正确', attempt_count: 1, mistake_count: 0, mastery_label: '已掌握', review_level: 5 },
                { id: 'word-4', number: 4, prompt: 'independent', translation: '独立的', student_answer: 'independent', correct_answer: 'independent', result_status: 'correct', result_label: '正确', attempt_count: 1, mistake_count: 1, mastery_label: '巩固中', review_level: 3 },
                { id: 'word-5', number: 5, prompt: 'reputation', translation: '名声；声誉', student_answer: 'reputation', correct_answer: 'reputation', result_status: 'correct', result_label: '正确', attempt_count: 1, mistake_count: 0, mastery_label: '巩固中', review_level: 2 },
                { id: 'word-6', number: 6, prompt: 'realistic', translation: '现实的；实际的', student_answer: 'realistic', correct_answer: 'realistic', result_status: 'correct', result_label: '正确', attempt_count: 1, mistake_count: 0, mastery_label: '巩固中', review_level: 2 }
            ]
        }
    }
    return {
        id: taskId || 'demo-recent-1',
        student_name: '演示学生',
        date: formatDate(today),
        category: '雅思听力',
        title: '剑雅听力精听练习',
        state: 'completed',
        state_label: '已完成',
        kind: 'listening_test',
        accuracy: 88,
        summary_text: '共 4 题 · 已答 4 · 正确 3 · 错误 1',
        summary: { assigned_total: 4, attempted_total: 4, correct_total: 3, wrong_total: 1, pending_total: 0, mastered_total: 0 },
        teacher_note: '注意复数形式和数字信息。',
        student_note: '',
        evidence: { image: [], audio: [], doc: [], other: [] },
        items: [
            { id: 'test-1', number: 1, prompt: 'Complete the notes below. Write ONE WORD ONLY for each answer.', student_answer: 'library', correct_answer: 'library', result_status: 'correct', result_label: '正确' },
            { id: 'test-2', number: 2, prompt: 'What time does the afternoon session begin?', student_answer: '2:15', correct_answer: '2:30', result_status: 'wrong', result_label: '错误' },
            { id: 'test-3', number: 3, prompt: 'Choose the correct letter, A, B or C.', student_answer: 'B', correct_answer: 'B', result_status: 'correct', result_label: '正确' },
            { id: 'test-4', number: 4, prompt: 'Complete the form with the missing information.', student_answer: 'Thursday', correct_answer: 'Thursday', result_status: 'correct', result_label: '正确' }
        ]
    }
}

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
    buildParentTaskDetail,
    buildParentStats,
    buildStudentStats,
    buildStudentTasks,
    buildTeacherMonthlyStats,
    buildTeacherSchedules
}
