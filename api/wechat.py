import requests
from flask import Blueprint, current_app, jsonify, request
from models import User, StudentProfile, ParentStudentLink, db
from .auth_utils import issue_token

wechat_bp = Blueprint("wechat", __name__, url_prefix="/wechat")

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
        # 生成一个临时的 username
        user = User(
            username=f"wx_{openid[:8]}",
            wechat_openid=openid,
            wechat_unionid=unionid,
            role="guest", # 初始角色为 guest，绑定后更新
            password_hash="N/A" # 微信用户无密码
        )
        db.session.add(user)
        db.session.commit()
    
    # 3. 发放 Token
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
    
    if role == "student":
        # 学生绑定逻辑：通过姓名匹配现有的 StudentProfile
        student_name = data.get("name")
        if not student_name:
            return jsonify({"ok": False, "error": "missing_name"}), 400
        
        profile = StudentProfile.query.filter_by(full_name=student_name).first()
        if not profile:
            return jsonify({"ok": False, "error": "student_not_found"}), 404
        
        if profile.user_id and profile.user_id != user.id:
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
        
        if not parent_name:
            return jsonify({"ok": False, "error": "missing_name"}), 400
            
        user.role = User.ROLE_PARENT
        user.display_name = parent_name
        db.session.commit()
        
        return jsonify({"ok": True, "role": "parent"})
        
    else:
        return jsonify({"ok": False, "error": "invalid_role"}), 400

