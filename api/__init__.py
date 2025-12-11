from flask import Blueprint

api_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


def init_app(app):
    """Register all API blueprints."""
    from api.wechat import wechat_bp
    from api.students import api_bp
    from api.miniprogram import mp_bp
    from api.materials import material_bp  # New material bank API
    from api.tts import tts_bp  # TTS API
    from api.azure_tts import azure_tts_bp  # Azure TTS API
    from api.dictation import dictation_bp  # Dictation API

    app.register_blueprint(wechat_bp, url_prefix="/api/wechat")  # Restore url_prefix
    app.register_blueprint(api_bp)
    app.register_blueprint(mp_bp)
    app.register_blueprint(material_bp)  # Register material bank
    app.register_blueprint(tts_bp)  # Register TTS
    app.register_blueprint(azure_tts_bp)  # Register Azure TTS
    app.register_blueprint(dictation_bp)  # Register Dictation
