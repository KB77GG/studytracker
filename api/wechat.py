import requests
from flask import Blueprint, current_app, jsonify, request
from models import User, StudentProfile, ParentStudentLink, db
from .auth_utils import issue_token

wechat_bp = Blueprint("wechat", __name__)

# 微信小程序配置
WECHAT_APP_ID = "wx75cdd8fc1ca68c69"
# TODO: 需要用户提供 AppSecret，或者从环境变量/配置中读取
WECHAT_APP_SECRET = "d50cb0a992515238c9807950fed29bf1" 

def get_wechat_session(code):
    """Exchange code for session_key and openid."""
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": WECHAT_APP_ID,
        "secret": current_app.config.get("WECHAT_APP_SECRET", WECHAT_APP_SECRET),
        "js_code": code,
        "grant_type": "authorization_code"
    }
    resp = requests.get(url, params=params)
    return resp.json()

@wechat_bp.route("/login", methods=["POST"])
def wechat_login():
    """
    微信登录接口
    1. 接收 code
    2. 调用微信 API 获取 openid
    3. 查找或创建 User
    4. 返回 JWT token
    """
    data = request.get_json()
    code = data.get("code")
    if not code:
        return jsonify({"ok": False, "error": "missing_code"}), 400

    try:
        # 1. 获取 openid
        wx_data = get_wechat_session(code)
        if "errcode" in wx_data and wx_data["errcode"] != 0:
            return jsonify({"ok": False, "error": "wechat_api_error", "details": wx_data}), 400
        
        openid = wx_data.get("openid")
        unionid = wx_data.get("unionid")
        
        if not openid:
            return jsonify({"ok": False, "error": "no_openid"}), 400

        # 2. 查找用户
        user = User.query.filter_by(wechat_openid=openid).first()
        
        is_new_user = False
        if not user:
            # 如果是新用户，暂时创建一个未绑定的用户
            # 具体的角色绑定（学生/家长）将在后续步骤完成
            is_new_user = True
            
            # 生成一个唯一的 username
            import time
            import random
            base_username = f"wx_{openid[:8]}"
            username = base_username
            
            # 检查用户名是否存在，如果存在则添加随机后缀
            while User.query.filter_by(username=username).first():
                username = f"{base_username}_{int(time.time())}_{random.randint(100, 999)}"
                
            user = User(
                username=username,
                wechat_openid=openid,
                wechat_unionid=unionid,
                role="guest", # 初始角色为 guest，绑定后更新
                password_hash="N/A" # 微信用户无密码
            )
            db.session.add(user)
        
        db.session.commit()
        
        # 重新发放 token (角色已变更)
        _, token = issue_token(user)
        
        return jsonify({
            "ok": True,
            "token": token,
            "user": {
                "id": user.id,
                "role": user.role,
                "is_new": is_new_user,
                "has_profile": _check_profile_exists(user)
            }
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Login error: {str(e)}")
        
        # 自动修复数据库缺失列的问题
        if "no such column: parent_student_link.created_at" in str(e):
            try:
                from sqlalchemy import text
                from models import db
                logger.info("Attempting to auto-fix database schema in login...")
                db.session.rollback()
                db.session.execute(text("ALTER TABLE parent_student_link ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
                db.session.execute(text("ALTER TABLE parent_student_link ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
                db.session.commit()
                return jsonify({"ok": False, "error": "server_error", "message": "系统已自动修复数据库结构，请重新点击登录按钮重试！"}), 500
            except Exception as fix_err:
                logger.error(f"Auto-fix failed: {str(fix_err)}")
                
        return jsonify({"ok": False, "error": "server_error", "message": str(e)}), 500

def _check_profile_exists(user):
    if user.role == User.ROLE_STUDENT:
        return StudentProfile.query.filter_by(user_id=user.id).first() is not None
    elif user.role == User.ROLE_PARENT:
        # 家长可能有多个关联，只要有记录就算有 profile
        return ParentStudentLink.query.filter_by(parent_id=user.id).first() is not None
    return False

@wechat_bp.route("/bind", methods=["POST"])
def bind_role():
    """
    绑定身份接口
    用户选择是"学生"还是"家长"，并提供相应的信息进行验证绑定
    """
    from .auth_utils import require_api_user
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("=== bind_role called ===")
    logger.info(f"Headers: {dict(request.headers)}")
    
    # 获取 token
    auth_header = request.headers.get("Authorization", "")
    logger.info(f"Auth header: {auth_header[:50] if auth_header else 'None'}...")
    
    if not auth_header.startswith("Bearer "):
        logger.error("Missing Bearer token")
        return jsonify({"ok": False, "error": "missing_token"}), 401
    
    token = auth_header.split(" ", 1)[1]
    try:
        import jwt
        payload = jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
        )
    except:
        return jsonify({"ok": False, "error": "invalid_token"}), 401

    user = User.query.get(int(payload.get("sub", 0)))
    if not user or not user.is_active:
        return jsonify({"ok": False, "error": "user_inactive"}), 403
    
    data = request.get_json()
    role = data.get("role") # student / parent
    
    try:
        if role == "student":
            student_name = data.get("name")
            if not student_name:
                return jsonify({"ok": False, "error": "missing_name"}), 400
                
            # 查找学生档案
            profile = StudentProfile.query.filter_by(full_name=student_name).first()
            if not profile:
                return jsonify({"ok": False, "error": "student_not_found"}), 404
                
            # 检查是否已被绑定
            if profile.user_id and profile.user_id != user.id:
                # 检查绑定该学生的用户是否还存在且绑定了微信
                bound_user = User.query.get(profile.user_id)
                if bound_user and bound_user.wechat_openid:
                    return jsonify({"ok": False, "error": "already_bound"}), 400
            
            # 绑定
            profile.user_id = user.id
            profile.wechat_openid = user.wechat_openid
            user.role = User.ROLE_STUDENT
            user.display_name = student_name
            db.session.commit()
            
            return jsonify({"ok": True, "role": "student"})
            
        elif role == "parent":
            # 家长绑定逻辑
            parent_name = data.get("name")
            phone = data.get("phone")
            student_name = data.get("student_name")  # 新增：孩子姓名
            
            if not parent_name:
                return jsonify({"ok": False, "error": "missing_name"}), 400
            
            if not student_name:
                return jsonify({"ok": False, "error": "missing_student_name"}), 400
                
            # 验证学生是否存在
            student_profile = StudentProfile.query.filter_by(full_name=student_name).first()
            if not student_profile:
                return jsonify({"ok": False, "error": "student_not_found", "message": f"未找到学生'{student_name}'，请确认姓名是否正确"}), 404
                
            user.role = User.ROLE_PARENT
            user.display_name = parent_name
            db.session.commit()
            
            # 创建家长-学生关联
            # 先检查是否已存在关联
            existing_link = ParentStudentLink.query.filter_by(
                parent_id=user.id,
                student_name=student_name
            ).first()
            
            if not existing_link:
                link = ParentStudentLink(
                    parent_id=user.id,
                    student_name=student_name,
                    relation="家长",
                    is_active=True
                )
                db.session.add(link)
                db.session.commit()
            
            return jsonify({"ok": True, "role": "parent"})
            
        else:
            return jsonify({"ok": False, "error": "invalid_role"}), 400
            
    except Exception as e:
        logger.error(f"Bind role error: {str(e)}")
        db.session.rollback()
        
        # 自动修复数据库缺失列的问题
        if "no such column: parent_student_link.created_at" in str(e):
            try:
                from sqlalchemy import text
                logger.info("Attempting to auto-fix database schema...")
                db.session.execute(text("ALTER TABLE parent_student_link ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
                db.session.execute(text("ALTER TABLE parent_student_link ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
                db.session.commit()
                return jsonify({"ok": False, "error": "server_error", "message": "系统已自动修复数据库结构，请重新点击绑定按钮重试！"}), 500
            except Exception as fix_err:
                logger.error(f"Auto-fix failed: {str(fix_err)}")
        
        return jsonify({"ok": False, "error": "server_error", "message": str(e)}), 500

@wechat_bp.route("/unbind", methods=["POST"])
def unbind_wechat():
    """
    [Debug] 解除微信绑定
    用于测试时切换账号
    """
    # 手动解析 token（类似 bind_role 的做法）
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        return jsonify({"ok": False, "error": "missing_token"}), 401
    
    token = auth_header.split(" ", 1)[1]
    try:
        import jwt
        payload = jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
        )
        user_id = payload.get("sub")
        if not user_id:
            return jsonify({"ok": False, "error": "invalid_token"}), 401
            
        user = User.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "error": "user_not_found"}), 404
            
    except:
        return jsonify({"ok": False, "error": "invalid_token"}), 401
    
    # 执行解绑
    user.wechat_openid = None
    db.session.commit()
    
    return jsonify({"ok": True, "message": "Unbound successfully"})


