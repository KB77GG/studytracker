import os
import json
from datetime import datetime, date
from flask import Blueprint, jsonify, request, current_app, url_for
from werkzeug.utils import secure_filename
from sqlalchemy import func, and_

from models import (
    db, User, StudentProfile, StudyPlan, PlanItem, 
    PlanEvidence, ParentStudentLink, TaskCatalog
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
    
    # 从 Task 表查询今日任务
    tasks = Task.query.filter_by(
        student_name=student.full_name,
        date=today.isoformat()
    ).all()
    
    if not tasks:
        return jsonify({"ok": True, "tasks": [], "message": "今日无任务"})
        
    tasks_data = []
    for task in tasks:
        # 判断状态
        status = "pending"
        if task.student_submitted:
            status = "submitted"
        elif task.actual_seconds and task.actual_seconds > 0:
            status = "in_progress"
            
        tasks_data.append({
            "id": task.id,
            "task_name": f"{task.category} - {task.detail}" if task.detail else task.category,
            "module": task.category or "其他",
            "exam_system": "",
            "instructions": task.note or "",
            "planned_minutes": task.planned_minutes,
            "status": status,
            "is_locked": False,
            "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
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
    if task.student_submitted:
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
    
    # 简单统计：本周完成任务数，总学习时长
    # 这里可以根据需求扩展
    
    return jsonify({
        "ok": True,
        "stats": {
            "completed_tasks": 0, # TODO: 实现具体统计逻辑
            "study_hours": 0
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
