from flask import jsonify, request
from werkzeug.security import check_password_hash

from models import User

from . import api_bp
from .auth_utils import issue_token, require_api_user, revoke_token


@api_bp.post("/auth/login")
def api_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"ok": False, "error": "missing_credentials"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.is_active:
        return jsonify({"ok": False, "error": "invalid_credentials"}), 401

    if not check_password_hash(user.password_hash, password):
        return jsonify({"ok": False, "error": "invalid_credentials"}), 401

    raw_token, jwt_token = issue_token(user)
    return jsonify(
        {
            "ok": True,
            "data": {
                "access_token": jwt_token,
                "refresh_hint": f"{raw_token[:6]}…",
                "role": user.role,
                "display_name": user.display_name or user.username,
            },
        }
    )


@api_bp.post("/auth/logout")
@require_api_user()
def api_logout():
    user = request.current_api_user
    revoke_token(user)
    return jsonify({"ok": True})
