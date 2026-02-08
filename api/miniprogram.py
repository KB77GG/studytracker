import os
import json
import hashlib
from datetime import datetime, date, timedelta
from urllib.parse import quote
import requests
from flask import Blueprint, jsonify, request, current_app, url_for
from werkzeug.utils import secure_filename
from sqlalchemy import func, and_

from models import (
    db, User, StudentProfile, StudyPlan, PlanItem,
    PlanEvidence, ParentStudentLink, TaskCatalog, Task,
    PlanItemSession, ClassFeedback, ScheduleSnapshot,
    MaterialBank, Question
)
from .auth_utils import require_api_user
from .wechat import send_subscribe_message
from .ielts_eval import run_ielts_eval
from .aliyun_asr import transcribe_audio_url

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


@mp_bp.route("/speaking/assigned", methods=["GET"])
@require_api_user(User.ROLE_STUDENT)
def get_speaking_assigned():
    """Get speaking tasks with material questions for a student (default today)."""
    user = request.current_api_user
    student = user.student_profile
    if not student:
        return jsonify({"ok": False, "error": "no_student_profile"}), 404

    date_str = request.args.get("date")
    if date_str:
        try:
            query_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            query_date = date.today()
    else:
        query_date = date.today()

    tasks = Task.query.filter_by(
        student_name=student.full_name,
        date=query_date.isoformat()
    ).all()

    speaking_types = {"speaking_part1", "speaking_part2", "speaking_part2_3"}
    results = []
    for task in tasks:
        if not task.material or task.material.type not in speaking_types:
            continue
        selected_ids = None
        if task.question_ids:
            try:
                loaded = json.loads(task.question_ids)
                if isinstance(loaded, list):
                    selected_ids = {int(x) for x in loaded if str(x).isdigit()}
            except Exception:
                selected_ids = None
        questions = []
        for q in task.material.questions.order_by(Question.sequence).all():
            if selected_ids is not None and q.id not in selected_ids:
                continue
            questions.append({
                "id": q.id,
                "sequence": q.sequence,
                "type": q.question_type,
                "content": q.content,
                "hint": q.hint,
                "reference_answer": q.reference_answer,
            })
        results.append({
            "task_id": task.id,
            "task_name": f"{task.category} - {task.detail}" if task.detail else task.category,
            "material": {
                "id": task.material.id,
                "title": task.material.title,
                "type": task.material.type,
                "description": task.material.description,
                "questions": questions,
            }
        })

    return jsonify({"ok": True, "date": query_date.isoformat(), "tasks": results})


@mp_bp.route("/speaking/random", methods=["GET"])
@require_api_user(User.ROLE_STUDENT)
def get_speaking_random():
    """Get a random speaking question by part."""
    part = (request.args.get("part") or "Part1").strip()
    part = part if part.startswith("Part") else f"Part{part}"

    if part == "Part1":
        types = ["speaking_part1"]
    elif part == "Part2":
        types = ["speaking_part2", "speaking_part2_3"]
    else:
        types = ["speaking_part2_3"]

    question = (
        Question.query.join(MaterialBank)
        .filter(MaterialBank.is_deleted.is_(False))
        .filter(MaterialBank.is_active.is_(True))
        .filter(Question.question_type.in_(types))
        .order_by(func.random())
        .first()
    )

    if not question:
        return jsonify({"ok": False, "error": "no_question_found"}), 404

    return jsonify({
        "ok": True,
        "question": {
            "id": question.id,
            "sequence": question.sequence,
            "type": question.question_type,
            "content": question.content,
            "material_id": question.material_id,
        }
    })


@mp_bp.route("/speaking/evaluate", methods=["POST"])
@require_api_user(User.ROLE_STUDENT)
def evaluate_speaking():
    data = request.get_json(silent=True) or {}
    payload, status = run_ielts_eval(data)
    return jsonify(payload), status


@mp_bp.route("/speaking/transcribe", methods=["POST"])
@require_api_user(User.ROLE_STUDENT)
def transcribe_speaking_audio():
    data = request.get_json(silent=True) or {}
    file_url = (data.get("audio_url") or data.get("file_url") or "").strip()
    if not file_url:
        return jsonify({"ok": False, "error": "missing_audio_url"}), 400

    if not file_url.startswith("http"):
        base_url = request.host_url.rstrip("/")
        file_url = f"{base_url}{file_url if file_url.startswith('/') else '/' + file_url}"

    ok, payload = transcribe_audio_url(file_url)
    if not ok:
        return jsonify({"ok": False, **payload}), 500
    return jsonify({"ok": True, **payload})

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
            selected_ids = None
            if task.question_ids:
                try:
                    loaded = json.loads(task.question_ids)
                    if isinstance(loaded, list):
                        selected_ids = {int(x) for x in loaded if str(x).isdigit()}
                except Exception:
                    selected_ids = None

            questions = []
            for q in task.material.questions:
                if selected_ids is not None and q.id not in selected_ids:
                    continue
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

    feedback_list = []
    feedback_total = 0
    try:
        feedback_query = ClassFeedback.query.filter_by(student_name=student_name)
        feedback_total = feedback_query.count()
        feedback_items = feedback_query.order_by(ClassFeedback.created_at.desc()).limit(3).all()
        feedback_list = [_serialize_class_feedback(item) for item in feedback_items]
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to load class feedback: {e}")
    
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
        "subjects": subject_stats,
        "feedback": feedback_list,
        "feedback_total": feedback_total
    })


@mp_bp.route("/parent/feedback", methods=["GET"])
@require_api_user(User.ROLE_PARENT)
def get_parent_feedback():
    """获取指定学生的课堂反馈列表"""
    user = request.current_api_user
    student_name = (request.args.get("student_name") or "").strip()
    if not student_name:
        return jsonify({"ok": False, "error": "missing_student_name"}), 400

    link = ParentStudentLink.query.filter_by(
        parent_id=user.id,
        student_name=student_name,
        is_active=True
    ).first()
    if not link:
        return jsonify({"ok": False, "error": "student_not_bound"}), 403

    limit = request.args.get("limit", 30)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 30
    limit = max(1, min(limit, 100))

    try:
        query = ClassFeedback.query.filter_by(student_name=student_name)
        total = query.count()
        items = query.order_by(ClassFeedback.created_at.desc()).limit(limit).all()
        feedback_list = [_serialize_class_feedback(item) for item in items]
        return jsonify({"ok": True, "total": total, "feedback": feedback_list})
    except Exception as exc:
        msg = str(exc).lower()
        if "no such table" in msg and "class_feedback" in msg:
            return jsonify({"ok": False, "error": "feedback_table_missing"}), 500
        current_app.logger.error("Failed to load parent feedback: %s", exc)
        return jsonify({"ok": False, "error": "load_failed"}), 500


@mp_bp.route("/parent/feedback/detail", methods=["GET"])
@require_api_user(User.ROLE_PARENT)
def get_parent_feedback_detail():
    """获取单条课堂反馈详情"""
    user = request.current_api_user
    feedback_id = request.args.get("feedback_id")
    try:
        feedback_id = int(feedback_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "missing_feedback_id"}), 400

    try:
        feedback = ClassFeedback.query.get(feedback_id)
        if not feedback:
            return jsonify({"ok": False, "error": "feedback_not_found"}), 404

        link = ParentStudentLink.query.filter_by(
            parent_id=user.id,
            student_name=feedback.student_name,
            is_active=True
        ).first()
        if not link:
            return jsonify({"ok": False, "error": "student_not_bound"}), 403

        return jsonify({"ok": True, "feedback": _serialize_class_feedback(feedback)})
    except Exception as exc:
        msg = str(exc).lower()
        if "no such table" in msg and "class_feedback" in msg:
            return jsonify({"ok": False, "error": "feedback_table_missing"}), 500
        current_app.logger.error("Failed to load feedback detail: %s", exc)
        return jsonify({"ok": False, "error": "load_failed"}), 500
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


def _fetch_range_schedules_by_dates(start: date, end: date, teacher_id=None):
    """调用排课系统 range 接口，返回指定日期范围内的课表。"""
    base_url = current_app.config.get("SCHEDULER_BASE_URL")
    token = current_app.config.get("SCHEDULER_PUSH_TOKEN")
    if not base_url or not token:
        return None, "scheduler_config_missing"

    params = {"start": start.isoformat(), "end": end.isoformat()}
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


def _fetch_range_schedules(days=7, teacher_id=None):
    """调用排课系统 range 接口，返回指定天数内的课表。"""
    today = date.today()
    start = today
    end = today + timedelta(days=days)
    return _fetch_range_schedules_by_dates(start, end, teacher_id=teacher_id)


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


def _infer_subject(course_name: str):
    name = (course_name or "").strip()
    if not name:
        return "其他"
    if "雅思听力" in name:
        return "雅思听力"
    return name


def _parse_time_minutes(value):
    if not value:
        return None
    time_str = str(value)
    if " " in time_str:
        time_str = time_str.split(" ")[1]
    parts = time_str.split(":")
    if not parts or len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour * 60 + minute


def _build_schedule_uid(schedule_id, teacher_id, student_id, course_name, start_time):
    if schedule_id:
        return f"id:{schedule_id}"
    raw = f"{teacher_id or ''}|{student_id or ''}|{course_name or ''}|{start_time or ''}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]
    return f"hash:{digest}"


def _serialize_class_feedback(feedback: ClassFeedback):
    return {
        "id": feedback.id,
        "schedule_uid": feedback.schedule_uid,
        "schedule_id": feedback.schedule_id,
        "student_name": feedback.student_name,
        "teacher_name": feedback.teacher_name,
        "course_name": feedback.course_name,
        "start_time": feedback.start_time,
        "end_time": feedback.end_time,
        "schedule_date": feedback.schedule_date,
        "feedback_text": feedback.feedback_text,
        "feedback_image": feedback.feedback_image,
        "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
    }


def _collect_student_openids(student_id, student_name):
    openids = []
    profile = None
    if student_id:
        profile = StudentProfile.query.filter_by(scheduler_student_id=student_id).first()
    if not profile and student_name:
        profile = StudentProfile.query.filter_by(full_name=student_name).first()
    if profile:
        if profile.user and profile.user.wechat_openid:
            openids.append(profile.user.wechat_openid)
        links = ParentStudentLink.query.filter_by(student_name=profile.full_name, is_active=True).all()
        for link in links:
            parent = User.query.get(link.parent_id)
            if parent and parent.wechat_openid:
                openids.append(parent.wechat_openid)
    return list(dict.fromkeys(openids))


def _collect_teacher_openid(scheduler_teacher_id):
    if not scheduler_teacher_id:
        return None
    teacher = User.query.filter_by(scheduler_teacher_id=scheduler_teacher_id, role=User.ROLE_TEACHER).first()
    if teacher and teacher.wechat_openid:
        return teacher.wechat_openid
    return None


@mp_bp.route("/send_tomorrow_class_reminders", methods=["POST"])
@require_api_user(User.ROLE_ADMIN, User.ROLE_TEACHER)
def send_tomorrow_class_reminders():
    """向绑定了 scheduler_student_id 的学生/家长推送明日课程提醒"""
    result = send_tomorrow_class_reminders_internal()
    if result.get("ok"):
        return jsonify(result)
    return jsonify(result), 400


def send_tomorrow_class_reminders_internal():
    template_id = current_app.config.get("WECHAT_TASK_TEMPLATE_ID")
    if not template_id:
        return {"ok": False, "error": "missing_template_id"}

    schedules, err = _fetch_tomorrow_schedules()
    if err:
        return {"ok": False, "error": err}
    if not schedules:
        return {"ok": True, "sent": 0, "total": 0}

    if isinstance(schedules, dict):
        schedules_list = schedules.get("schedules") or schedules.get("data") or []
    else:
        schedules_list = schedules

    sent = 0
    dedupe = set()
    for item in schedules_list:
        schedule_id, student_id, teacher_id, course_name, start_time, end_time, teacher_name, student_name = _extract_schedule_fields(item)
        if schedule_id and schedule_id in dedupe:
            continue
        if schedule_id:
            dedupe.add(schedule_id)
        # 学生+家长
        openids = _collect_student_openids(student_id, student_name)
        if openids:
            data = {
                "thing27": {"value": (course_name or "课程")[:20]},
                "time6": {"value": str(start_time)[:32]},
                "time38": {"value": str(end_time or start_time)[:32]},
                "thing15": {"value": (teacher_name or "")[:20]},
            }
            for oid in openids:
                if send_subscribe_message(oid, template_id, data, page="pages/student/home/index"):
                    sent += 1

        # 老师
        teacher_openid = _collect_teacher_openid(teacher_id)
        if teacher_openid:
            data_t = {
                "thing27": {"value": (course_name or "课程")[:20]},
                "time6": {"value": str(start_time)[:32]},
                "time38": {"value": str(end_time or start_time)[:32]},
                "thing15": {"value": (teacher_name or "")[:20]},
            }
            if send_subscribe_message(teacher_openid, template_id, data_t, page="pages/teacher/home/index"):
                sent += 1

    return {"ok": True, "sent": sent, "total": len(schedules_list)}


def check_schedule_changes_internal(days=7):
    """检查课表变化并推送新增/取消提醒。"""
    template_id = current_app.config.get("WECHAT_TASK_TEMPLATE_ID")
    if not template_id:
        return {"ok": False, "error": "missing_template_id"}

    teachers = User.query.filter(
        User.role == User.ROLE_TEACHER,
        User.scheduler_teacher_id.isnot(None)
    ).all()

    start_date = date.today()
    end_date = start_date + timedelta(days=days)
    added = 0
    removed = 0
    sent = 0

    for teacher in teachers:
        data, err = _fetch_range_schedules_by_dates(start_date, end_date, teacher_id=teacher.scheduler_teacher_id)
        if err:
            continue
        schedules = data.get("schedules") if isinstance(data, dict) else data
        schedules = schedules or []

        current_uids = set()
        for item in schedules:
            schedule_id, student_id, teacher_id, course_name, start_time, end_time, teacher_name, student_name = _extract_schedule_fields(item)
            schedule_date = item.get("schedule_date") or item.get("date")
            if not schedule_date and start_time and " " in str(start_time):
                schedule_date = str(start_time).split(" ")[0]

            uid = _build_schedule_uid(schedule_id, teacher.scheduler_teacher_id, student_id, course_name, start_time)
            current_uids.add(uid)
            snapshot = ScheduleSnapshot.query.filter_by(schedule_uid=uid).first()
            if not snapshot:
                snapshot = ScheduleSnapshot(
                    schedule_uid=uid,
                    teacher_id=teacher.id,
                    scheduler_teacher_id=teacher.scheduler_teacher_id,
                )
                db.session.add(snapshot)
                is_new = True
            else:
                is_new = snapshot.status != "active"

            snapshot.schedule_id = str(schedule_id) if schedule_id is not None else None
            snapshot.student_id = student_id
            snapshot.student_name = student_name
            snapshot.course_name = course_name
            snapshot.start_time = start_time
            snapshot.end_time = end_time
            snapshot.schedule_date = schedule_date
            snapshot.status = "active"
            snapshot.last_seen = datetime.now()

            if is_new:
                added += 1
                change_label = "新增"
                openids = _collect_student_openids(student_id, student_name)
                teacher_openid = _collect_teacher_openid(teacher.scheduler_teacher_id)
                if teacher_openid:
                    openids.append(teacher_openid)
                openids = list(dict.fromkeys(openids))
                data_msg = {
                    "thing27": {"value": f"[{change_label}]{(course_name or '课程')}"[:20]},
                    "time6": {"value": str(start_time)[:32]},
                    "time38": {"value": str(end_time or start_time)[:32]},
                    "thing15": {"value": (teacher_name or "")[:20]},
                }
                for oid in openids:
                    if send_subscribe_message(oid, template_id, data_msg, page="pages/teacher/home/index"):
                        sent += 1

        # 检测取消的课程
        existing = ScheduleSnapshot.query.filter(
            ScheduleSnapshot.teacher_id == teacher.id,
            ScheduleSnapshot.status == "active",
            ScheduleSnapshot.schedule_date >= start_date.isoformat(),
            ScheduleSnapshot.schedule_date <= end_date.isoformat(),
        ).all()
        for snapshot in existing:
            if snapshot.schedule_uid not in current_uids:
                snapshot.status = "removed"
                removed += 1
                change_label = "取消"
                openids = _collect_student_openids(snapshot.student_id, snapshot.student_name)
                teacher_openid = _collect_teacher_openid(teacher.scheduler_teacher_id)
                if teacher_openid:
                    openids.append(teacher_openid)
                openids = list(dict.fromkeys(openids))
                data_msg = {
                    "thing27": {"value": f"[{change_label}]{(snapshot.course_name or '课程')}"[:20]},
                    "time6": {"value": str(snapshot.start_time)[:32]},
                    "time38": {"value": str(snapshot.end_time or snapshot.start_time)[:32]},
                    "thing15": {"value": ""[:20]},
                }
                for oid in openids:
                    if send_subscribe_message(oid, template_id, data_msg, page="pages/teacher/home/index"):
                        sent += 1

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.warning("Schedule snapshot commit failed: %s", exc)

    return {"ok": True, "added": added, "removed": removed, "sent": sent}

@mp_bp.route("/teacher/feedback", methods=["POST"])
@require_api_user(User.ROLE_TEACHER)
def submit_class_feedback():
    """老师提交课程反馈并推送给家长。"""
    data = request.get_json() or {}
    feedback_text = (data.get("feedback_text") or "").strip()
    if not feedback_text:
        return jsonify({"ok": False, "error": "missing_feedback_text"}), 400

    user = request.current_api_user
    schedule_id = data.get("schedule_id")
    schedule_date = data.get("schedule_date")
    course_name = data.get("course_name") or ""
    start_time = data.get("start_time") or ""
    end_time = data.get("end_time") or ""
    teacher_name = data.get("teacher_name") or user.display_name or user.username
    feedback_image = data.get("feedback_image")

    scheduler_student_id = data.get("student_id")
    try:
        scheduler_student_id = int(scheduler_student_id) if scheduler_student_id is not None else None
    except (TypeError, ValueError):
        scheduler_student_id = None

    student_name = (data.get("student_name") or "").strip()
    profile = None
    if scheduler_student_id:
        profile = StudentProfile.query.filter_by(scheduler_student_id=scheduler_student_id).first()
        if profile and not student_name:
            student_name = profile.full_name

    if not schedule_date and start_time and " " in start_time:
        schedule_date = start_time.split(" ")[0]

    schedule_uid = data.get("schedule_uid")
    if not schedule_uid:
        schedule_uid = _build_schedule_uid(
            schedule_id,
            user.scheduler_teacher_id,
            scheduler_student_id,
            course_name,
            start_time,
        )

    feedback = ClassFeedback.query.filter_by(schedule_uid=schedule_uid).first()
    if feedback and feedback.teacher_id != user.id:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    is_new = feedback is None
    if is_new:
        feedback = ClassFeedback(schedule_uid=schedule_uid, teacher_id=user.id)
        db.session.add(feedback)

    feedback.schedule_id = str(schedule_id) if schedule_id is not None else None
    feedback.scheduler_student_id = scheduler_student_id
    feedback.student_name = student_name or None
    feedback.teacher_name = teacher_name
    feedback.course_name = course_name
    feedback.start_time = start_time
    feedback.end_time = end_time
    feedback.schedule_date = schedule_date
    feedback.feedback_text = feedback_text
    feedback.feedback_image = feedback_image

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        msg = str(exc).lower()
        if "no such table" in msg and "class_feedback" in msg:
            return jsonify({"ok": False, "error": "feedback_table_missing"}), 500
        current_app.logger.error("Failed to save class feedback: %s", exc)
        return jsonify({"ok": False, "error": "save_failed"}), 500

    template_id = current_app.config.get("WECHAT_FEEDBACK_TEMPLATE_ID")
    push_sent = 0
    push_error = None

    openids = []
    target_name = student_name
    if not target_name and profile:
        target_name = profile.full_name

    if target_name:
        links = ParentStudentLink.query.filter_by(student_name=target_name, is_active=True).all()
        for link in links:
            parent = User.query.get(link.parent_id)
            if parent and parent.wechat_openid:
                openids.append(parent.wechat_openid)

    openids = list(dict.fromkeys(openids))

    if not template_id:
        push_error = "missing_template_id"
    elif not openids:
        push_error = "no_parent_openid"
    else:
        time_value = start_time or schedule_date or ""
        payload = {
            "thing2": {"value": (target_name or "学生")[:20]},
            "thing1": {"value": (course_name or "课程")[:20]},
            "phrase4": {"value": feedback_text[:20]},
            "time3": {"value": str(time_value)[:32]},
        }
        page = f"pages/parent/feedback/index?feedback_id={feedback.id}"
        if target_name:
            page = f"{page}&student={quote(target_name)}"
        for oid in openids:
            if send_subscribe_message(oid, template_id, payload, page=page):
                push_sent += 1

    if push_sent > 0:
        feedback.push_success = True
        feedback.pushed_at = datetime.now()
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            current_app.logger.warning("Failed to update push status: %s", exc)

    return jsonify({
        "ok": True,
        "feedback": _serialize_class_feedback(feedback),
        "push_sent": push_sent,
        "push_error": push_error,
        "created": is_new,
    })


@mp_bp.route("/teacher/schedules", methods=["GET"])
@require_api_user(User.ROLE_TEACHER)
def teacher_schedules():
    """老师查看课表（默认未来7天 + 过去2天，可传 days/past_days），要求已绑定 scheduler_teacher_id。"""
    days = request.args.get("days", 7)
    try:
        days = int(days)
    except Exception:
        days = 7
    days = max(1, min(days, 60))  # 限制 1-60 天

    past_days = request.args.get("past_days", 2)
    try:
        past_days = int(past_days)
    except Exception:
        past_days = 2
    past_days = max(0, min(past_days, 14))  # 限制 0-14 天

    user = request.current_api_user
    if not user.scheduler_teacher_id:
        current_app.logger.warning(
            "teacher_schedules missing scheduler_teacher_id user=%s role=%s",
            user.id, user.role
        )
        return jsonify({"ok": False, "error": "missing_scheduler_teacher_id"}), 400

    start_date = date.today() - timedelta(days=past_days)
    end_date = date.today() + timedelta(days=days)
    data, err = _fetch_range_schedules_by_dates(start_date, end_date, teacher_id=user.scheduler_teacher_id)
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
        schedule_uid = _build_schedule_uid(sid, teacher_id or user.scheduler_teacher_id, student_id, course_name, start_dt)
        normalized.append({
            "schedule_id": sid,
            "schedule_uid": schedule_uid,
            "student_id": student_id,
            "teacher_id": teacher_id,
            "course_name": course_name,
            "start_time": start_dt,
            "end_time": end_dt,
            "teacher_name": teacher_name,
            "student_name": student_name,
            "schedule_date": item.get("schedule_date") or item.get("date"),
        })

    feedback_map = {}
    try:
        schedule_uids = [item["schedule_uid"] for item in normalized if item.get("schedule_uid")]
        if schedule_uids:
            feedbacks = ClassFeedback.query.filter(ClassFeedback.schedule_uid.in_(schedule_uids)).all()
            feedback_map = {feedback.schedule_uid: feedback for feedback in feedbacks}
    except Exception as exc:
        current_app.logger.warning("Class feedback lookup failed: %s", exc)

    for item in normalized:
        feedback = feedback_map.get(item.get("schedule_uid"))
        if feedback:
            item["feedback"] = {
                "id": feedback.id,
                "text": feedback.feedback_text,
                "image": feedback.feedback_image,
                "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
            }
        else:
            item["feedback"] = None

    return jsonify({
        "ok": True,
        "days": days,
        "past_days": past_days,
        "count": len(normalized),
        "schedules": normalized
    })


@mp_bp.route("/teacher/monthly_stats", methods=["GET"])
@require_api_user(User.ROLE_TEACHER)
def teacher_monthly_stats():
    """老师查看当月课时统计（按科目汇总）。"""
    user = request.current_api_user
    if not user.scheduler_teacher_id:
        return jsonify({"ok": False, "error": "missing_scheduler_teacher_id"}), 400

    month_str = request.args.get("month")
    today = date.today()
    if month_str:
        try:
            year, month = month_str.split("-")
            year = int(year)
            month = int(month)
        except Exception:
            year = today.year
            month = today.month
    else:
        year = today.year
        month = today.month

    import calendar

    last_day = calendar.monthrange(year, month)[1]
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)

    data, err = _fetch_range_schedules_by_dates(start_date, end_date, teacher_id=user.scheduler_teacher_id)
    if err:
        return jsonify({"ok": False, "error": err}), 400

    schedules = data.get("schedules") if isinstance(data, dict) else data
    schedules = schedules or []

    stats_map = {}
    total_minutes = 0
    total_sessions = 0

    for item in schedules:
        _sid, _student_id, _teacher_id, course_name, start_dt, end_dt, _teacher_name, _student_name = _extract_schedule_fields(item)
        subject = _infer_subject(course_name)
        start_min = _parse_time_minutes(start_dt)
        end_min = _parse_time_minutes(end_dt)
        if start_min is None:
            duration = 60
        else:
            if end_min is None:
                duration = 60
            else:
                if end_min <= start_min:
                    end_min = start_min + 60
                duration = max(30, end_min - start_min)

        if subject not in stats_map:
            stats_map[subject] = {"subject": subject, "minutes": 0, "sessions": 0}
        stats_map[subject]["minutes"] += duration
        stats_map[subject]["sessions"] += 1
        total_minutes += duration
        total_sessions += 1

    subjects = list(stats_map.values())
    for item in subjects:
        item["hours"] = round(item["minutes"] / 60, 1)

    subjects.sort(key=lambda x: (-x["minutes"], x["subject"]))

    total = {
        "sessions": total_sessions,
        "minutes": total_minutes,
        "hours": round(total_minutes / 60, 1),
    }

    return jsonify({
        "ok": True,
        "month": f"{year:04d}-{month:02d}",
        "subjects": subjects,
        "total": total,
    })
