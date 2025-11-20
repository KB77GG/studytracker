from flask import Blueprint

api_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


def init_app(app):
    from . import auth, students, guardians  # noqa: F401

    app.register_blueprint(api_bp)
