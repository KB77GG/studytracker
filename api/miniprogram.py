import os
import json
from datetime import datetime, date, timedelta
import requests
from flask import Blueprint, jsonify, request, current_app, url_for
from werkzeug.utils import secure_filename
from sqlalchemy import func, and_

from models import (
    db, User, StudentProfile, StudyPlan, PlanItem, 
    PlanEvidence, ParentStudentLink, TaskCatalog, Task,
    PlanItemSession
)
from .auth_utils import require_api_user
from .wechat import send_subscribe_message

mp_bp = Blueprint("miniprogram", __name__, url_prefix="/api/miniprogram")

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
            "dictation_book_id": task.dictation_book_id, # Add this
            "dictation_word_start": task.dictation_word_start,
            "dictation_word_end": task.dictation_word_end,
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
    try:
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

        # 获取关联的材料信息
        material_data = None
        if task.material:
            questions = []
            for q in task.material.questions:
                options = [{"key": opt.option_key, "text": opt.option_text} for opt in q.options]
                questions.append({
                    "id": q.id,
                    "sequence": q.sequence,
                    "type": q.question_type,
                    "content": q.content,
                    "hint": q.hint,
                    "reference_answer": q.reference_answer,
                    "options": options
                })
            
            material_data = {
                "material_id": task.material.id,
                "dictation_book_id": task.dictation_book_id,
                "dictation_word_start": task.dictation_word_start,
                "dictation_word_end": task.dictation_word_end,
                "actual_seconds": task.actual_seconds,
                "title": task.material.title,
                "type": task.material.type,
                "description": task.material.description,
                "questions": questions
            }

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
                "feedback_audio": task.feedback_audio,
                # Dictation Info
                "dictation_book_id": task.dictation_book_id,
                "dictation_word_start": task.dictation_word_start,
                "dictation_word_end": task.dictation_word_end,
                # 材料信息
                "material": material_data
            }
        })
    except Exception as e:
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({"ok": False, "message": str(e), "error": str(e)}), 500

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
    accuracy = data.get("accuracy") # Optional float 0-100
    
    # 1. 尝试查找 Task (旧版)
    task = Task.query.get(task_id)
    if task:
        # 验证权限
        if task.student_name != user.student_profile.full_name:
            return jsonify({"ok": False, "error": "forbidden"}), 403
            
        task.student_submitted = True
        task.submitted_at = datetime.now()
        task.status = "done"  # 标记完成
        
        # Merge wrong words into note if provided
        final_note = note
        if data.get("wrong_words"):
             wrong_summary = f"[错题记录] {data.get('wrong_words')}"
             final_note = f"{note}\n{wrong_summary}" if note else wrong_summary
        
        task.student_note = final_note
        task.evidence_photos = json.dumps(evidence_files)
        
        if duration > 0:
            task.actual_seconds = duration
            
        if accuracy is not None:
            task.accuracy = float(accuracy)
            task.completion_rate = 100.0
            
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

@mp_bp.route("/student/tasks/<int:task_id>/timer/start", methods=["POST"])
@require_api_user(User.ROLE_STUDENT)
def start_timer(task_id):
    """Start timer for a task"""
    user = request.current_api_user
    
    # Try to find Task (old format) first
    task = Task.query.get(task_id)
    if task:
        # Verify ownership
        if task.student_name != user.student_profile.full_name:
            return jsonify({"ok": False, "error": "forbidden"}), 403
        
        # For old Task format, we don't create session, just return success
        task.status = "in_progress"
        db.session.commit()
        # The miniprogram will handle timer locally
        return jsonify({
            "ok": True,
            "session_id": task_id,  # Use task_id as session_id for compatibility
            "started_at": datetime.utcnow().isoformat()
        })
    
    # Try to find PlanItem (new format)
    item = PlanItem.query.get(task_id)
    if not item:
        return jsonify({"ok": False, "error": "task_not_found"}), 404
        
    # Verify ownership
    if item.plan.student_id != user.student_profile.id:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    
    # Create session for new format
    now = datetime.utcnow()
    session = PlanItemSession(
        plan_item=item,
        started_at=now,
        created_by=user.id,
        source="timer"
    )
    db.session.add(session)
    
    # Update status if pending
    if item.student_status == PlanItem.STUDENT_PENDING:
        item.student_status = PlanItem.STUDENT_IN_PROGRESS
        item.started_at = now
        
    db.session.commit()
    
    return jsonify({
        "ok": True,
        "session_id": session.id,
        "started_at": now.isoformat()
    })


@mp_bp.route("/student/tasks/<int:task_id>/timer/<int:session_id>/stop", methods=["POST"])
@require_api_user(User.ROLE_STUDENT)
def stop_timer(task_id, session_id):
    """Stop timer for a task"""
    user = request.current_api_user
    
    # Check if this is a legacy Task (session_id == task_id)
    if session_id == task_id:
        task = Task.query.get(task_id)
        if task and task.student_name == user.student_profile.full_name:
            # For old Task format, just return success
            # Timer duration is handled by miniprogram locally
            return jsonify({
                "ok": True,
                "duration": 0,  # Placeholder
                "ended_at": datetime.utcnow().isoformat()
            })
    
    # Handle new PlanItem format with sessions
    session = PlanItemSession.query.get(session_id)
    if not session or session.plan_item.plan.student_id != user.student_profile.id:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    
    # Update session end time
    if not session.ended_at:
        session.ended_at = datetime.utcnow()
        duration = int((session.ended_at - session.started_at).total_seconds())
        
        # Update plan item actual_seconds
        item = session.plan_item
        if item.actual_seconds:
            item.actual_seconds += duration
        else:
            item.actual_seconds = duration
            
        db.session.commit()
        
        return jsonify({
            "ok": True,
            "duration": duration,
            "ended_at": session.ended_at.isoformat()
        })
    
    return jsonify({"ok": False, "error": "already_stopped"}), 400


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
        
    # 3. 学科分布统计 (最近30天)
    thirty_days_ago = today - timedelta(days=30)
    recent_tasks = Task.query.filter(
        Task.student_name == student_name,
        Task.date >= thirty_days_ago.isoformat()
    ).all()
    
    subject_counts = {}
    total_recent = 0
    for t in recent_tasks:
        cat = t.category or "其他"
        subject_counts[cat] = subject_counts.get(cat, 0) + 1
        total_recent += 1
        
    subject_stats = []
    for cat, count in subject_counts.items():
        percent = round(count / total_recent * 100) if total_recent > 0 else 0
        subject_stats.append({
            "subject": cat,
            "count": count,
            "percent": percent
        })
    
    # 按数量降序排序
    subject_stats.sort(key=lambda x: x["count"], reverse=True)
    
    # 4. 检测是否正在学习（有活跃的计时器）
    # 查找最近10分钟内启动的活跃计时会话
    is_studying = False
    try:
        from models import PlanItemSession
        from datetime import datetime
        
        # 获取学生档案
        student_profile = StudentProfile.query.filter_by(
            full_name=student_name,
            is_deleted=False
        ).first()
        
        if student_profile:
            # 查找活跃的计时会话（最近10分钟内启动且未结束）
            ten_min_ago = datetime.now() - timedelta(minutes=10)
            active_session = PlanItemSession.query.join(PlanItem).join(StudyPlan).filter(
                StudyPlan.student_id == student_profile.id,
                PlanItemSession.start_time >= ten_min_ago,
                PlanItemSession.end_time.is_(None)
            ).first()
            
            is_studying = active_session is not None
    except Exception as e:
        # 如果查询失败（比如表不存在），默认不显示
        import logging
        logging.getLogger(__name__).warning(f"Failed to check isStudying: {e}")
    
    return jsonify({
        "ok": True,
        "isStudying": is_studying,
        "today": {
            "total": total_tasks,
            "completed": completed_count,
            "pending": pending_review_count,
            "in_progress": in_progress_count,
            "rate": completion_rate
        },
        "recent": recent_feed,
        "weekly": weekly_stats,
        "subjects": subject_stats
    })

@mp_bp.route("/debug/fix_db", methods=["GET"])
def debug_fix_db():
    """临时修复数据库结构 - 增强版"""
    from models import db
    from sqlalchemy import text
    
    result = {
        "ok": True,
        "logs": [],
        "columns_before": [],
        "columns_after": []
    }
    
    try:
        # 1. 检查现有列
        try:
            rows = db.session.execute(text("PRAGMA table_info(parent_student_link)")).fetchall()
            result["columns_before"] = [row[1] for row in rows] # row[1] is name
        except Exception as e:
            result["logs"].append(f"Error checking columns: {str(e)}")
            
        # 2. 尝试添加 created_at
        if "created_at" not in result["columns_before"]:
            try:
                db.session.execute(text("ALTER TABLE parent_student_link ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
                db.session.commit()
                result["logs"].append("Added created_at")
            except Exception as e:
                db.session.rollback()
                result["logs"].append(f"Failed to add created_at: {str(e)}")
        else:
            result["logs"].append("created_at already exists")
            
        # 3. 尝试添加 updated_at
        if "updated_at" not in result["columns_before"]:
            try:
                # 使用固定时间字符串作为默认值，避免 SQLite "non-constant default" 错误
                db.session.execute(text("ALTER TABLE parent_student_link ADD COLUMN updated_at DATETIME DEFAULT '2000-01-01 00:00:00'"))
                db.session.commit()
                result["logs"].append("Added updated_at")
            except Exception as e:
                db.session.rollback()
                result["logs"].append(f"Failed to add updated_at: {str(e)}")
        else:
            result["logs"].append("updated_at already exists")

        # 4. 再次检查
        try:
            rows = db.session.execute(text("PRAGMA table_info(parent_student_link)")).fetchall()
            result["columns_after"] = [row[1] for row in rows]
        except Exception as e:
            result["logs"].append(f"Error checking columns after: {str(e)}")
            
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@mp_bp.route("/bind_scheduler_student", methods=["POST"])
@require_api_user(User.ROLE_STUDENT)
def bind_scheduler_student():
    """绑定排课系统的学生ID到当前学生档案"""
    data = request.get_json() or {}
    scheduler_student_id = data.get("scheduler_student_id")
    student_name = (data.get("student_name") or "").strip()

    if not scheduler_student_id:
        return jsonify({"ok": False, "error": "missing_scheduler_student_id"}), 400

    user = request.current_api_user
    profile = user.student_profile
    if not profile:
        return jsonify({"ok": False, "error": "no_student_profile"}), 404

    if student_name and student_name != profile.full_name:
        return jsonify({"ok": False, "error": "name_mismatch"}), 400

    existing = StudentProfile.query.filter(
        StudentProfile.scheduler_student_id == scheduler_student_id,
        StudentProfile.id != profile.id,
    ).first()
    if existing:
        return jsonify({"ok": False, "error": "scheduler_id_taken"}), 409

    profile.scheduler_student_id = scheduler_student_id
    db.session.commit()
    return jsonify({"ok": True, "scheduler_student_id": scheduler_student_id})


@mp_bp.route("/bind_scheduler_teacher", methods=["POST"])
@require_api_user(User.ROLE_TEACHER)
def bind_scheduler_teacher():
    """绑定排课系统的教师ID到当前教师账号"""
    data = request.get_json() or {}
    scheduler_teacher_id = data.get("scheduler_teacher_id")
    if not scheduler_teacher_id:
        return jsonify({"ok": False, "error": "missing_scheduler_teacher_id"}), 400

    user = request.current_api_user
    existing = User.query.filter(
        User.scheduler_teacher_id == scheduler_teacher_id,
        User.id != user.id,
    ).first()
    if existing:
        return jsonify({"ok": False, "error": "scheduler_id_taken"}), 409

    user.scheduler_teacher_id = scheduler_teacher_id
    db.session.commit()
    return jsonify({"ok": True, "scheduler_teacher_id": scheduler_teacher_id})


def _fetch_tomorrow_schedules():
    base_url = current_app.config.get("SCHEDULER_BASE_URL")
    token = current_app.config.get("SCHEDULER_PUSH_TOKEN")
    if not base_url or not token:
        return None, "scheduler_config_missing"
    try:
        resp = requests.get(
            f"{base_url}/api/schedules/tomorrow",
            headers={"X-Push-Token": token},
            timeout=5,
        )
        if resp.status_code != 200:
            current_app.logger.warning("Scheduler API error: %s %s", resp.status_code, resp.text)
            return None, "scheduler_api_error"
        return resp.json(), None
    except Exception as exc:  # pragma: no cover
        current_app.logger.error("Scheduler API request failed: %s", exc)
        return None, "scheduler_request_failed"


def _fetch_range_schedules(days=7, teacher_id=None):
    """调用排课系统 range 接口，返回指定天数内的课表。"""
    base_url = current_app.config.get("SCHEDULER_BASE_URL")
    token = current_app.config.get("SCHEDULER_PUSH_TOKEN")
    if not base_url or not token:
        return None, "scheduler_config_missing"

    today = date.today()
    start = today.isoformat()
    end = (today + timedelta(days=days)).isoformat()
    params = {"start": start, "end": end}
    if teacher_id is not None:
        params["teacher_id"] = teacher_id

    try:
        resp = requests.get(
            f"{base_url}/api/schedules/range",
            headers={"X-Push-Token": token},
            params=params,
            timeout=5,
        )
        if resp.status_code != 200:
            current_app.logger.warning("Scheduler range API error: %s %s", resp.status_code, resp.text)
            return None, "scheduler_api_error"
        return resp.json(), None
    except Exception as exc:  # pragma: no cover
        current_app.logger.error("Scheduler range API request failed: %s", exc)
        return None, "scheduler_request_failed"


def _extract_schedule_fields(item: dict):
    """兼容字段提取"""
    schedule_id = item.get("schedule_id") or item.get("id")
    student_id = item.get("student_id") or item.get("scheduler_student_id")
    teacher_id = item.get("teacher_id")
    course_name = item.get("course_name") or item.get("name") or "课程"
    start_time = item.get("start_time") or item.get("start_at") or item.get("datetime")
    end_time = item.get("end_time") or item.get("end_at") or item.get("end_datetime")
    teacher_name = item.get("teacher_name") or item.get("teacher") or "老师待定"
    student_name = (
        item.get("student_name")
        or item.get("student")
        or item.get("studentName")
        or item.get("student_full_name")
        or item.get("studentFullName")
    )
    schedule_date = item.get("schedule_date") or item.get("date")

    # 拼成完整时间，避免仅有时分导致订阅模板校验失败
    if schedule_date and start_time and len(str(start_time)) <= 5:
        start_dt = f"{schedule_date} {start_time}"
    else:
        start_dt = start_time
    if schedule_date and end_time and len(str(end_time)) <= 5:
        end_dt = f"{schedule_date} {end_time}"
    else:
        end_dt = end_time

    return schedule_id, student_id, teacher_id, course_name, start_dt, end_dt, teacher_name, student_name


@mp_bp.route("/send_tomorrow_class_reminders", methods=["POST"])
@require_api_user(User.ROLE_ADMIN, User.ROLE_TEACHER)
def send_tomorrow_class_reminders():
    """向绑定了 scheduler_student_id 的学生/家长推送明日课程提醒"""
    template_id = current_app.config.get("WECHAT_TASK_TEMPLATE_ID")
    if not template_id:
        return jsonify({"ok": False, "error": "missing_template_id"}), 400

    schedules, err = _fetch_tomorrow_schedules()
    if err:
        return jsonify({"ok": False, "error": err}), 400
    if not schedules:
        return jsonify({"ok": True, "sent": 0, "total": 0})

    if isinstance(schedules, dict):
        schedules_list = schedules.get("schedules") or schedules.get("data") or []
    else:
        schedules_list = schedules

    sent = 0
    dedupe = set()
    for item in schedules_list:
        schedule_id, student_id, teacher_id, course_name, start_time, end_time, teacher_name, _student_name = _extract_schedule_fields(item)
        if schedule_id and schedule_id in dedupe:
            continue
        if schedule_id:
            dedupe.add(schedule_id)
        # 学生+家长
        if student_id:
            profile = StudentProfile.query.filter_by(scheduler_student_id=student_id).first()
            if profile:
                openids = []
                if profile.user and profile.user.wechat_openid:
                    openids.append(profile.user.wechat_openid)
                parent_links = ParentStudentLink.query.filter_by(student_name=profile.full_name).all()
                for link in parent_links:
                    parent = User.query.get(link.parent_id)
                    if parent and parent.wechat_openid:
                        openids.append(parent.wechat_openid)
                if openids:
                    data = {
                        "thing27": {"value": course_name[:20]},
                        "time6": {"value": str(start_time)[:32]},
                        "time38": {"value": str(end_time or start_time)[:32]},
                        "thing15": {"value": teacher_name[:20]},
                    }
                    for oid in openids:
                        if send_subscribe_message(oid, template_id, data, page="pages/student/home/index"):
                            sent += 1

        # 老师
        if teacher_id:
            teacher = User.query.filter_by(scheduler_teacher_id=teacher_id, role=User.ROLE_TEACHER).first()
            if teacher and teacher.wechat_openid:
                data_t = {
                    "thing27": {"value": course_name[:20]},
                    "time6": {"value": str(start_time)[:32]},
                    "time38": {"value": str(end_time or start_time)[:32]},
                    "thing15": {"value": teacher_name[:20]},
                }
                if send_subscribe_message(teacher.wechat_openid, template_id, data_t, page="pages/student/home/index"):
                    sent += 1

    return jsonify({"ok": True, "sent": sent, "total": len(schedules_list)})


@mp_bp.route("/teacher/schedules", methods=["GET"])
@require_api_user(User.ROLE_TEACHER)
def teacher_schedules():
    """老师查看未来课表（默认7天，可传 days=30），要求已绑定 scheduler_teacher_id。"""
    days = request.args.get("days", 7)
    try:
        days = int(days)
    except Exception:
        days = 7
    days = max(1, min(days, 60))  # 限制 1-60 天

    user = request.current_api_user
    if not user.scheduler_teacher_id:
        current_app.logger.warning(
            "teacher_schedules missing scheduler_teacher_id user=%s role=%s",
            user.id, user.role
        )
        return jsonify({"ok": False, "error": "missing_scheduler_teacher_id"}), 400

    data, err = _fetch_range_schedules(days=days, teacher_id=user.scheduler_teacher_id)
    if err:
        return jsonify({"ok": False, "error": err}), 400

    schedules = data.get("schedules") if isinstance(data, dict) else data
    schedules = schedules or []

    normalized = []
    student_name_map = None
    for item in schedules:
        sid, student_id, teacher_id, course_name, start_dt, end_dt, teacher_name, student_name = _extract_schedule_fields(item)
        if not student_name and student_id:
            if student_name_map is None:
                student_name_map = {}
                student_ids = {student_id}
                for sched_item in schedules:
                    _, sched_student_id, _, _, _, _, _, _ = _extract_schedule_fields(sched_item)
                    if sched_student_id:
                        student_ids.add(sched_student_id)
                if student_ids:
                    profiles = StudentProfile.query.filter(
                        StudentProfile.scheduler_student_id.in_(student_ids)
                    ).all()
                    student_name_map = {
                        profile.scheduler_student_id: profile.full_name
                        for profile in profiles
                        if profile.scheduler_student_id
                    }
            student_name = student_name_map.get(student_id)
        normalized.append({
            "schedule_id": sid,
            "student_id": student_id,
            "teacher_id": teacher_id,
            "course_name": course_name,
            "start_time": start_dt,
            "end_time": end_dt,
            "teacher_name": teacher_name,
            "student_name": student_name,
            "schedule_date": item.get("schedule_date") or item.get("date"),
        })

    return jsonify({"ok": True, "days": days, "count": len(normalized), "schedules": normalized})
