import requests
import time
from flask import Blueprint, current_app, jsonify, request
from models import User, StudentProfile, ParentStudentLink, db
from .auth_utils import issue_token

wechat_bp = Blueprint("wechat", __name__)

# Token cache for subscribe message
_token_cache = {"value": None, "expires_at": 0}

def _get_wechat_config():
    appid = current_app.config.get("WECHAT_APPID") or current_app.config.get("WECHAT_APP_ID")
    secret = current_app.config.get("WECHAT_SECRET") or current_app.config.get("WECHAT_APP_SECRET")
    # Fallback to previous constants if present in config (avoid hardcoding secrets)
    return appid, secret

def _get_access_token():
    now = time.time()
    if _token_cache["value"] and now < _token_cache["expires_at"]:
        return _token_cache["value"]

    appid, secret = _get_wechat_config()
    if not appid or not secret:
        current_app.logger.warning("WECHAT_APPID/WECHAT_SECRET not configured")
        return None

    resp = requests.get(
        "https://api.weixin.qq.com/cgi-bin/token",
        params={
            "grant_type": "client_credential",
            "appid": appid,
            "secret": secret,
        },
        timeout=5,
    )
    data = resp.json()
    if "access_token" in data:
        _token_cache["value"] = data["access_token"]
        _token_cache["expires_at"] = now + int(data.get("expires_in", 7200)) - 200
        return _token_cache["value"]
    current_app.logger.error("Failed to fetch access_token: %s", data)
    return None

def send_subscribe_message(openid: str, template_id: str, data: dict, page: str = "pages/student/home/index") -> bool:
    token = _get_access_token()
    if not token:
        return False
    payload = {
        "touser": openid,
        "template_id": template_id,
        "page": page,
        "data": data,
    }
    resp = requests.post(
        f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={token}",
        json=payload,
        timeout=5,
    )
    res = resp.json()
    if res.get("errcode") == 0:
        return True
    current_app.logger.error("Send subscribe fail: %s", res)
    return False

def get_wechat_session(code):
    """Exchange code for session_key and openid."""
    url = "https://api.weixin.qq.com/sns/jscode2session"
    appid, secret = _get_wechat_config()
    params = {
        "appid": appid,
        "secret": secret,
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
        err_str = str(e).lower()
        if "no such column" in err_str and "parent_student_link" in err_str:
            try:
                from sqlalchemy import text
                # db is already imported globally
                logger.info("Attempting to auto-fix database schema in login...")
                db.session.rollback()
                
                try:
                    db.session.execute(text("ALTER TABLE parent_student_link ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
                    db.session.commit()
                except:
                    db.session.rollback()
                    
                try:
                    db.session.execute(text("ALTER TABLE parent_student_link ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
                    db.session.commit()
                except:
                    db.session.rollback()
                    
                return jsonify({"ok": False, "error": "server_error", "message": "系统已自动修复数据库结构，请重新点击登录按钮重试！"}), 500
            except Exception as fix_err:
                logger.error(f"Auto-fix failed: {str(fix_err)}")
                
        return jsonify({"ok": False, "error": "server_error", "message": str(e)}), 500

def _check_profile_exists(user):
    try:
        if user.role in {User.ROLE_TEACHER, User.ROLE_ASSISTANT, User.ROLE_ADMIN, User.ROLE_COURSE_PLANNER}:
            return True
        if user.role == User.ROLE_STUDENT:
            return StudentProfile.query.filter_by(user_id=user.id).first() is not None
        elif user.role == User.ROLE_PARENT:
            # 家长可能有多个关联，只要有记录就算有 profile
            return ParentStudentLink.query.filter_by(parent_id=user.id).first() is not None
        return False
    except Exception as e:
        # 如果查询失败（例如表结构问题），返回 False 而不是抛出异常
        # 这样不会影响登录流程
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error checking profile: {str(e)}")
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
        
        elif role == "teacher":
            teacher_name = data.get("name")
            if not teacher_name:
                return jsonify({"ok": False, "error": "missing_name"}), 400
            # 仅设置角色和显示名，排课ID由后台管理员填入
            user.role = User.ROLE_TEACHER
            user.display_name = teacher_name
            db.session.commit()
            return jsonify({"ok": True, "role": "teacher"})

        else:
            return jsonify({"ok": False, "error": "invalid_role"}), 400
            
    except Exception as e:
        logger.error(f"Bind role error: {str(e)}")
        db.session.rollback()
        
        # 自动修复数据库缺失列的问题
        err_str = str(e).lower()
        if "no such column" in err_str and "parent_student_link" in err_str:
            try:
                from sqlalchemy import text
                # db is already imported globally
                logger.info("Attempting to auto-fix database schema...")
                db.session.rollback()
                
                try:
                    db.session.execute(text("ALTER TABLE parent_student_link ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
                    db.session.commit()
                except:
                    db.session.rollback()
                    
                try:
                    db.session.execute(text("ALTER TABLE parent_student_link ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
                    db.session.commit()
                except:
                    db.session.rollback()
                    
                return jsonify({"ok": False, "error": "server_error", "message": "系统已自动修复数据库结构，请重新点击绑定按钮重试！"}), 500
            except Exception as fix_err:
                logger.error(f"Auto-fix failed: {str(fix_err)}")
        
        return jsonify({"ok": False, "error": "server_error", "message": str(e)}), 500


@wechat_bp.route("/bind_existing", methods=["POST"])
def bind_existing_account():
    """Bind current WeChat user to an existing teacher account (username/password)."""
    import logging
    import jwt

    logger = logging.getLogger(__name__)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"ok": False, "error": "missing_token"}), 401

    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
        )
    except Exception:
        return jsonify({"ok": False, "error": "invalid_token"}), 401

    current_user = User.query.get(int(payload.get("sub", 0)))
    if not current_user or not current_user.is_active:
        return jsonify({"ok": False, "error": "user_inactive"}), 403

    if current_user.role in {User.ROLE_STUDENT, User.ROLE_PARENT}:
        return jsonify({"ok": False, "error": "role_conflict"}), 400

    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"ok": False, "error": "missing_credentials"}), 400

    target = User.query.filter_by(username=username).first()
    if not target or not target.check_password(password):
        return jsonify({"ok": False, "error": "invalid_credentials"}), 400
    if not target.is_active:
        return jsonify({"ok": False, "error": "user_inactive"}), 403
    if target.role != User.ROLE_TEACHER:
        return jsonify({"ok": False, "error": "not_teacher"}), 400

    current_openid = current_user.wechat_openid
    if not current_openid:
        return jsonify({"ok": False, "error": "missing_openid"}), 400

    if target.wechat_openid and target.wechat_openid != current_openid:
        return jsonify({"ok": False, "error": "wechat_already_bound"}), 409

    try:
        if target.id != current_user.id:
            target.wechat_openid = current_openid
            if current_user.wechat_unionid:
                target.wechat_unionid = current_user.wechat_unionid
            if current_user.scheduler_teacher_id and not target.scheduler_teacher_id:
                target.scheduler_teacher_id = current_user.scheduler_teacher_id
                current_user.scheduler_teacher_id = None

            current_user.wechat_openid = None
            current_user.wechat_unionid = None
            current_user.wechat_nickname = None
            if current_user.role == "guest":
                current_user.is_active = False

        if not target.display_name:
            target.display_name = target.username

        _, jwt_token = issue_token(target)
        return jsonify({
            "ok": True,
            "token": jwt_token,
            "user": {
                "id": target.id,
                "role": target.role,
                "display_name": target.display_name,
            }
        })
    except Exception as e:
        logger.error("Bind existing account error: %s", str(e))
        db.session.rollback()
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
