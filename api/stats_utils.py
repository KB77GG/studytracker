"""统计聚合纯函数（零 DB / Flask）。

从各 stats handler 抽出，单源化重复了多处的 round(x/y*100) 占比计算与计数聚合，
便于零依赖单测。handler 负责 DB 查询，把原始值传进来。
"""

from datetime import datetime

# 今日任务状态桶；键与前端 data-filter / 后端响应契约一致，顺序固定。
TODAY_STATUS_KEYS = ("not_started", "in_progress", "pending_review", "completed")


def percent(part, whole):
    """占比/完成率：round(part / whole * 100)，whole<=0 返回 0。返回 int。"""
    return round(part / whole * 100) if whole and whole > 0 else 0


def summarize_today_status(states):
    """汇总今日任务状态。

    states: list[str]，每个任务的状态（取自 _parent_task_state 的第一个返回值）。
    返回 dict 含 4 个状态计数键 + total / completed_count / rate。
    """
    counts = {key: 0 for key in TODAY_STATUS_KEYS}
    for state in states:
        if state in counts:
            counts[state] += 1
    total = len(states)
    completed = counts["completed"]
    return {
        **counts,
        "total": total,
        "completed_count": completed,
        "rate": percent(completed, total),
    }


def summarize_weekly(rows):
    """给每天补上完成率。

    rows: list[dict]，每项含 date / total / completed。
    返回新 list（不修改入参），每项追加 rate。
    """
    return [
        {
            "date": row["date"],
            "total": row["total"],
            "completed": row["completed"],
            "rate": percent(row["completed"], row["total"]),
        }
        for row in rows
    ]


def summarize_subjects(categories, *, default="其他"):
    """学科分布：计数 + 占比，按数量降序。

    categories: list[str | None]，每个任务的 category（None/空 归入 default）。
    """
    counts = {}
    total = 0
    for category in categories:
        key = category or default
        counts[key] = counts.get(key, 0) + 1
        total += 1
    stats = [
        {"subject": subject, "count": count, "percent": percent(count, total)}
        for subject, count in counts.items()
    ]
    stats.sort(key=lambda item: item["count"], reverse=True)
    return stats


def average_accuracy(values):
    """近期正确率均值，保留 1 位小数；空列表返回 None。"""
    return round(sum(values) / len(values), 1) if values else None


def study_level(total_hours):
    """简单等级：每 5 小时升一级，从 1 起。"""
    return int(total_hours // 5) + 1


def compute_streak(completed_date_strings, today):
    """连续打卡天数。

    completed_date_strings: 已完成任务的去重日期（"YYYY-MM-DD"），按日期降序。
    today: date。仅当最近一次打卡是今天或昨天才算连续，再向前数连续天。
    """
    parsed = []
    for value in completed_date_strings:
        try:
            parsed.append(datetime.strptime(value, "%Y-%m-%d").date())
        except (ValueError, TypeError):
            break  # 非法日期即止（生产中 Task.date 恒为合法串，不会触发）
    if not parsed:
        return 0
    last_date = parsed[0]
    if (today - last_date).days > 1:
        return 0
    streak = 1
    current = last_date
    for prev in parsed[1:]:
        if (current - prev).days == 1:
            streak += 1
            current = prev
        else:
            break
    return streak


def compute_badges(streak, total_hours, average_accuracy_value):
    """根据 streak / 学习时长 / 近7日正确率给出勋章；无任何勋章时给鼓励勋章。"""
    badges = []
    if streak >= 3:
        badges.append({"id": "streak_3", "name": "坚持不懈", "icon": "🔥", "desc": "连续打卡3天"})
    if streak >= 7:
        badges.append({"id": "streak_7", "name": "习惯养成", "icon": "📅", "desc": "连续打卡7天"})
    if total_hours >= 10:
        badges.append({"id": "hours_10", "name": "学习新星", "icon": "⭐", "desc": "累计学习10小时"})
    if average_accuracy_value is not None and average_accuracy_value >= 90:
        badges.append({"id": "accuracy_90", "name": "满分达人", "icon": "A", "desc": "近7日正确率90%+"})
    if not badges:
        badges.append({"id": "newbie", "name": "初出茅庐", "icon": "🌱", "desc": "开始你的学习之旅"})
    return badges
