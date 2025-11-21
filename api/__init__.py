from flask import Blueprint

api_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


def init_app(app):
    from . import auth, students, guardians  # noqa: F401
    from .wechat import wechat_bp
    from .miniprogram import mp_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(wechat_bp, url_prefix="/api/wechat")
    app.register_blueprint(mp_bp, url_prefix="/api/miniprogram")
