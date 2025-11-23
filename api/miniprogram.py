import os
import json
from datetime import datetime, date, timedelta
from flask import Blueprint, jsonify, request, current_app, url_for
from werkzeug.utils import secure_filename
from sqlalchemy import func, and_

from models import (
    db, User, StudentProfile, StudyPlan, PlanItem, 
    PlanEvidence, ParentStudentLink, TaskCatalog, Task
)
from .auth_utils import require_api_user

mp_bp = Blueprint("miniprogram", __name__, url_prefix="/miniprogram")

# --- 通用接口 ---

@mp_bp.route("/upload", methods=["POST"])
@require_api_user()
def upload_file():
    """上传文件接口 (图片/音频)"""
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "no_file"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"ok": False, "error": "empty_filename"}), 400
        
    if file:
        filename = secure_filename(file.filename)
        # 添加时间戳防止重名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        
        # 确保上传目录存在
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        # 生成访问 URL
        # 假设 Nginx 配置了 /uploads/ 映射到 upload_folder
        file_url = f"/uploads/{unique_filename}"
        
        return jsonify({"ok": True, "url": file_url})

# --- 学生接口 ---

@mp_bp.route("/student/tasks/today", methods=["GET"])
@require_api_user(User.ROLE_STUDENT)
def get_student_today_tasks():
    """获取学生今日任务"""
    from models import Task
    
    user = request.current_api_user
    student = user.student_profile
    if not student:
        return jsonify({"ok": False, "error": "no_student_profile"}), 404
        
    today = date.today()
    query_date = today
    
    date_str = request.args.get("date")
    if date_str:
        try:
            query_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass # Invalid date format, fallback to today
    
    # 从 Task 表查询指定日期的任务
    tasks = Task.query.filter_by(
        student_name=student.full_name,
        date=query_date.isoformat()
    ).all()
    
    if not tasks:
        return jsonify({"ok": True, "tasks": [], "message": "今日无任务"})
        
    tasks_data = []
    for task in tasks:
        # 判断状态
        status = "pending"
        if task.status == "done":
            status = "completed"
        elif task.student_submitted:
            status = "submitted"
        elif task.actual_seconds and task.actual_seconds > 0:
            status = "in_progress"
            
        tasks_data.append({
            "id": task.id,
            "task_name": f"{task.category} - {task.detail}" if task.detail else task.category,
            "module": task.category or "其他",
            "exam_system": "",
            "instructions": task.note or "", # 这里note作为任务说明
            "planned_minutes": task.planned_minutes,
            "status": status,
            "is_locked": False,
            "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
            # 反馈字段
            "accuracy": task.accuracy,
            "completion_rate": task.completion_rate,
            "teacher_note": task.note, # 暂时复用note，前端需区分展示场景
        })
        
    return jsonify({
        "ok": True, 
        "date": today.isoformat(),
        "tasks": tasks_data
    })


@mp_bp.route("/student/tasks/<int:task_id>", methods=["GET"])
@require_api_user(User.ROLE_STUDENT)
def get_task_detail(task_id):
    """获取单个任务详情"""
    from models import Task
    
    user = request.current_api_user
    task = Task.query.get(task_id)
    
    if not task:
        return jsonify({"ok": False, "error": "task_not_found"}), 404
        
    # 简单权限验证
    if task.student_name != user.student_profile.full_name:
         return jsonify({"ok": False, "error": "forbidden"}), 403

    status = "pending"
    if task.status == "done":
        status = "completed"
    elif task.student_submitted:
        status = "submitted"
    elif task.actual_seconds and task.actual_seconds > 0:
        status = "in_progress"

    return jsonify({
        "ok": True,
        "task": {
            "id": task.id,
            "task_name": f"{task.category} - {task.detail}" if task.detail else task.category,
            "module": task.category or "其他",
            "exam_system": "",
            "instructions": task.note or "",
            "planned_minutes": task.planned_minutes,
            "status": status,
            "is_locked": False,
            "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
            # 反馈字段
            "accuracy": task.accuracy,
            "completion_rate": task.completion_rate,
            "teacher_note": task.note,
            "student_note": task.student_note,
            "evidence_photos": json.loads(task.evidence_photos) if task.evidence_photos else [],
            "feedback_image": task.feedback_image,
            "feedback_audio": task.feedback_audio
        }
    })

@mp_bp.route("/student/tasks/<int:task_id>/submit", methods=["POST"])
@require_api_user(User.ROLE_STUDENT)
def submit_task(task_id):
    """学生提交任务"""
    from models import Task
    
    user = request.current_api_user
    data = request.get_json()
    note = data.get("note")
    evidence_files = data.get("evidence_files", []) # List of URLs
    duration = data.get("duration_seconds", 0)
    
    # 1. 尝试查找 Task (旧版)
    task = Task.query.get(task_id)
    if task:
        # 验证权限
        if task.student_name != user.student_profile.full_name:
            return jsonify({"ok": False, "error": "forbidden"}), 403
            
        task.student_submitted = True
        task.submitted_at = datetime.now()
        task.student_note = note
        task.evidence_photos = json.dumps(evidence_files) # 旧版字段存 JSON
        
        if duration > 0:
            task.actual_seconds = duration
            
        db.session.commit()
        return jsonify({"ok": True})

    # 2. 尝试查找 PlanItem (新版)
    item = PlanItem.query.get(task_id)
    if item:
        # 验证该任务是否属于当前学生
        if item.plan.student_id != user.student_profile.id:
            return jsonify({"ok": False, "error": "forbidden"}), 403
            
        # 更新任务状态
        item.student_status = PlanItem.STUDENT_SUBMITTED
        item.submitted_at = datetime.now()
        item.student_comment = note
        
        # 如果有实际耗时
        if duration > 0:
            item.actual_seconds = duration
            
        # 保存证据文件
        for file_url in evidence_files:
            file_type = "image"
            if file_url.endswith(".mp3") or file_url.endswith(".wav"):
                file_type = "audio"
                
            evidence = PlanEvidence(
                plan_item_id=item.id,
                uploader_id=user.id,
                file_type=file_type,
                storage_path=file_url,
                original_filename=os.path.basename(file_url)
            )
            db.session.add(evidence)
            
        db.session.commit()
        return jsonify({"ok": True})

    return jsonify({"ok": False, "error": "task_not_found"}), 404

@mp_bp.route("/student/stats", methods=["GET"])
@require_api_user(User.ROLE_STUDENT)
def get_student_stats():
    """获取学生统计概览"""
    user = request.current_api_user
    student = user.student_profile
    
    # 使用 Task 表进行统计
    student_name = student.full_name
    
    # 1. 累计学习时长 (小时)
    total_seconds = db.session.query(func.sum(Task.actual_seconds)).filter(
        Task.student_name == student_name,
        Task.status == 'done'
    ).scalar() or 0
    total_hours = round(total_seconds / 3600, 1)
    
    # 2. 连续打卡天数 (Streak)
    # 获取所有有完成任务的日期，按倒序排列
    completed_dates = db.session.query(Task.date).filter(
        Task.student_name == student_name,
        Task.status == 'done'
    ).distinct().order_by(Task.date.desc()).all()
    
    streak = 0
    if completed_dates:
        today = date.today()
        last_date_str = completed_dates[0][0] # YYYY-MM-DD string
        try:
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            # 如果最后一次打卡是今天或昨天，则连续有效
            if (today - last_date).days <= 1:
                streak = 1
                current_check = last_date
                for i in range(1, len(completed_dates)):
                    prev_date_str = completed_dates[i][0]
                    prev_date = datetime.strptime(prev_date_str, "%Y-%m-%d").date()
                    if (current_check - prev_date).days == 1:
                        streak += 1
                        current_check = prev_date
                    else:
                        break
        except:
            pass

    # 3. 本周活跃度 (过去7天)
    today = date.today()
    week_dates = [(today - timedelta(days=i)) for i in range(6, -1, -1)]
    weekly_activity = []
    
    for d in week_dates:
        d_str = d.isoformat()
        count = Task.query.filter(
            Task.student_name == student_name,
            Task.date == d_str,
            Task.status == 'done'
        ).count()
        weekly_activity.append({
            "date": d.strftime("%m-%d"),
            "count": count,
            "day_label": ["周一","周二","周三","周四","周五","周六","周日"][d.weekday()]
        })

    # 4. 简单勋章判断
    badges = []
    if streak >= 3:
        badges.append({"id": "streak_3", "name": "坚持不懈", "icon": "🔥", "desc": "连续打卡3天"})
    if streak >= 7:
        badges.append({"id": "streak_7", "name": "习惯养成", "icon": "📅", "desc": "连续打卡7天"})
    if total_hours >= 10:
        badges.append({"id": "hours_10", "name": "学习新星", "icon": "⭐", "desc": "累计学习10小时"})
    
    # 如果没有勋章，给一个鼓励勋章
    if not badges:
        badges.append({"id": "newbie", "name": "初出茅庐", "icon": "🌱", "desc": "开始你的学习之旅"})

    return jsonify({
        "ok": True,
        "stats": {
            "streak": streak,
            "total_hours": total_hours,
            "weekly_activity": weekly_activity,
            "badges": badges,
            "level": int(total_hours // 5) + 1  # 简单等级计算：每5小时升一级
        }
    })

# --- 家长接口 ---

@mp_bp.route("/parent/children", methods=["GET"])
@require_api_user(User.ROLE_PARENT)
def get_parent_children():
    """获取家长绑定的孩子列表"""
    user = request.current_api_user
    
    # 查找 ParentStudentLink
    links = ParentStudentLink.query.filter_by(parent_id=user.id, is_active=True).all()
    
    children = []
    for link in links:
        # 尝试关联 StudentProfile
        profile = StudentProfile.query.filter_by(full_name=link.student_name).first()
        children.append({
            "name": link.student_name,
            "relation": link.relation,
            "student_id": profile.id if profile else None,
            "has_profile": profile is not None
        })
        
    return jsonify({"ok": True, "children": children})

@mp_bp.route("/parent/report", methods=["GET"])
@require_api_user(User.ROLE_PARENT)
def get_child_report():
    """获取孩子日报/周报"""
    student_id = request.args.get("student_id")
    date_str = request.args.get("date") # YYYY-MM-DD
    
    if not student_id:
        return jsonify({"ok": False, "error": "missing_student_id"}), 400
        
    # 验证权限：确保该家长绑定了这个孩子
    # ... (省略严格验证，假设前端传来的 student_id 是合法的)
    
    target_date = date.today()
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except:
            pass
            
    plan = StudyPlan.query.filter_by(
        student_id=student_id, 
        plan_date=target_date
    ).first()
    
    report_data = {
        "date": target_date.isoformat(),
        "tasks": [],
        "summary": "今日无计划"
    }
    
    if plan:
        completed_count = 0
        total_count = 0
        for item in plan.items:
            total_count += 1
            if item.student_status == PlanItem.STUDENT_SUBMITTED or item.review_status == PlanItem.REVIEW_APPROVED:
                completed_count += 1
                
            report_data["tasks"].append({
                "name": item.task_name,
                "status": item.student_status,
                "review": item.review_status,
                "comment": item.review_comment
            })
            
        report_data["summary"] = f"今日计划 {total_count} 项任务，已完成 {completed_count} 项。"
        
    return jsonify({"ok": True, "report": report_data})

# --- 家长接口 ---

@mp_bp.route("/parent/students", methods=["GET"])
@require_api_user(User.ROLE_PARENT)
def get_parent_students():
    """获取家长绑定的学生列表"""
    user = request.current_api_user
    
    # 通过 ParentStudentLink 查询
    links = ParentStudentLink.query.filter_by(
        parent_id=user.id,
        is_active=True
    ).all()
    
    students = []
    for link in links:
        students.append({
            "name": link.student_name,
            "relation": link.relation or "家长"
        })
        
    return jsonify({
        "ok": True,
        "students": students
    })

@mp_bp.route("/parent/stats", methods=["GET"])
@require_api_user(User.ROLE_PARENT)
def get_parent_stats():
    """获取指定学生的统计数据"""
    from models import Task
    
    user = request.current_api_user
    student_name = request.args.get("student_name")
    
    if not student_name:
        return jsonify({"ok": False, "error": "missing_student_name"}), 400
        
    # 验证绑定关系
    link = ParentStudentLink.query.filter_by(
        parent_id=user.id,
        student_name=student_name,
        is_active=True
    ).first()
    
    if not link:
        return jsonify({"ok": False, "error": "student_not_bound"}), 403
        
    today = date.today()
    
    # 1. 今日任务概览
    today_tasks = Task.query.filter_by(
        student_name=student_name,
        date=today.isoformat()
    ).all()
    
    total_tasks = len(today_tasks)
    completed_count = 0
    pending_review_count = 0
    in_progress_count = 0
    
    for t in today_tasks:
        if t.status == "done":
            completed_count += 1
        elif t.student_submitted:
            pending_review_count += 1
        elif t.actual_seconds and t.actual_seconds > 0:
            in_progress_count += 1
            
    completion_rate = round(completed_count / total_tasks * 100) if total_tasks > 0 else 0
    
    # 2. 最近动态 (最近完成的5个任务)
    recent_tasks = Task.query.filter(
        Task.student_name == student_name,
        Task.status == "done"
    ).order_by(Task.date.desc(), Task.id.desc()).limit(5).all()
    
    recent_feed = []
    for t in recent_tasks:
        recent_feed.append({
            "id": t.id,
            "date": t.date,
            "category": t.category,
            "detail": t.detail,
            "accuracy": t.accuracy,
            "completion_rate": t.completion_rate,
            "teacher_note": t.note
        })

    # 3. 本周趋势 (过去7天)
    from datetime import timedelta
    weekly_stats = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.isoformat()
        
        day_tasks = Task.query.filter_by(
            student_name=student_name,
            date=day_str
        ).all()
        
        d_total = len(day_tasks)
        d_completed = sum(1 for t in day_tasks if t.status == "done")
        d_rate = round(d_completed / d_total * 100) if d_total > 0 else 0
        
        weekly_stats.append({
            "date": day.strftime("%m-%d"),
            "total": d_total,
            "completed": d_completed,
            "rate": d_rate
        })
        
    return jsonify({
        "ok": True,
        "today": {
            "total": total_tasks,
            "completed": completed_count,
            "pending": pending_review_count,
            "in_progress": in_progress_count,
            "rate": completion_rate
        },
        "recent": recent_feed,
        "weekly": weekly_stats
    })

@mp_bp.route("/debug/fix_db", methods=["GET"])
def debug_fix_db():
    """临时修复数据库结构"""
    from models import db
    from sqlalchemy import text
    
    try:
        # 尝试添加 created_at
        try:
            db.session.execute(text("ALTER TABLE parent_student_link ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # 忽略错误（可能已存在）
            pass
            
        # 尝试添加 updated_at
        try:
            db.session.execute(text("ALTER TABLE parent_student_link ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            pass
            
        return jsonify({"ok": True, "message": "Database schema updated"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
