import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, jsonify, request

from models import User, db

TOKEN_TTL_HOURS = 168


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_token(user: User) -> tuple[str, str]:
    """Create a random token hash and a JWT for the client."""

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)

    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    }
    jwt_token = jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")

    user.set_api_token(token_hash)
    db.session.commit()
    return raw_token, jwt_token


def revoke_token(user: User) -> None:
    user.clear_api_token()
    db.session.commit()


def can_view_all_schedules(user: User) -> bool:
    """判断某账号是否可以查看全部老师的课表。

    admin 角色始终允许；其余老师需在 ALL_SCHEDULE_TEACHER_ACCOUNTS 白名单内
    （按 username 或 wechat_openid 匹配）。
    """
    if not user:
        return False
    if user.role == User.ROLE_ADMIN:
        return True
    raw = current_app.config.get("ALL_SCHEDULE_TEACHER_ACCOUNTS") or ""
    allow = {item.strip() for item in str(raw).split(",") if item.strip()}
    if not allow:
        return False
    return bool(
        (user.username and user.username in allow)
        or (user.wechat_openid and user.wechat_openid in allow)
    )


def require_api_user(*roles):
    """Decorator enforcing API bearer auth and optional role filtering."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"ok": False, "error": "missing_token"}), 401
            token = auth_header.split(" ", 1)[1]
            try:
                payload = jwt.decode(
                    token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
                )
            except jwt.PyJWTError:
                return jsonify({"ok": False, "error": "invalid_token"}), 401

            user = User.query.get(int(payload.get("sub", 0)))
            if not user or not user.is_active:
                return jsonify({"ok": False, "error": "user_inactive"}), 403

            if roles and user.role not in roles and user.role != User.ROLE_ADMIN:
                return jsonify({"ok": False, "error": "forbidden"}), 403

            request.current_api_user = user
            return fn(*args, **kwargs)

        return wrapper

    return decorator
