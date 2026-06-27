"""统计聚合纯函数（零 DB / Flask）。

从各 stats handler 抽出，单源化重复了多处的 round(x/y*100) 占比计算与计数聚合，
便于零依赖单测。handler 负责 DB 查询，把原始值传进来。
"""

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
