from flask import Blueprint

api_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


def init_app(app):
    """Register all API blueprints."""
    from api.azure_tts import azure_tts_bp  # Azure TTS API
    from api.dictation import dictation_bp  # Dictation API
    from api.dictation_input import dictation_input_bp  # Strict spelling input policy
    from api.entrance import entrance_bp  # Entrance test API (新生入学测试)
    from api.ielts_eval import eval_bp  # IELTS speaking eval API
    from api.listening_training import listening_training_bp
    from api.materials import material_bp  # New material bank API
    from api.miniprogram import mp_bp
    from api.mock_exam_admin import mock_exam_admin_bp  # 模考成绩 / 逐题复盘（教师后台）
    from api.mock_exam_review import mock_exam_review_bp  # 模考写作批改 / 学生复盘
    from api.mock_exam_student import mock_exam_student_bp  # 学生模考逐题复盘
    from api.practice_history import practice_history_bp
    from api.question_type_practice import question_type_practice_bp
    from api.reading_study import reading_study_bp  # Reading Study (阅读句子解析)
    from api.speaking_practice import speaking_bp  # Speaking listen & repeat API
    from api.students import api_bp
    from api.task_assignments import task_assignments_bp
    from api.teacher_practice_access import teacher_practice_bp
    from api.toefl_mock import toefl_mock_bp
    from api.tts import tts_bp  # TTS API
    from api.vocab_review import vocab_review_bp
    from api.wechat import wechat_bp
    from api.writing_library import writing_library_bp
    from models import QuestionTypePracticeAttempt, WritingTypingAttempt, db

    app.register_blueprint(wechat_bp, url_prefix="/api/wechat")  # Restore url_prefix
    app.register_blueprint(api_bp)
    app.register_blueprint(mp_bp)
    app.register_blueprint(practice_history_bp)
    app.register_blueprint(question_type_practice_bp)
    app.register_blueprint(task_assignments_bp)
    app.register_blueprint(material_bp)  # Register material bank
    app.register_blueprint(tts_bp)  # Register TTS
    app.register_blueprint(azure_tts_bp)  # Register Azure TTS
    app.register_blueprint(dictation_bp)  # Register Dictation
    app.register_blueprint(dictation_input_bp)
    app.register_blueprint(vocab_review_bp)  # Server-owned vocabulary review queue
    app.register_blueprint(eval_bp)  # Register IELTS eval
    app.register_blueprint(listening_training_bp)
    app.register_blueprint(speaking_bp)  # Register Speaking practice
    app.register_blueprint(entrance_bp)  # Register Entrance test
    app.register_blueprint(reading_study_bp)  # Register Reading Study
    app.register_blueprint(teacher_practice_bp)
    app.register_blueprint(toefl_mock_bp)
    app.register_blueprint(mock_exam_admin_bp)  # Register mock exam review console
    app.register_blueprint(mock_exam_student_bp)  # Register student mock exam review
    app.register_blueprint(mock_exam_review_bp)
    app.register_blueprint(writing_library_bp)

    # The project still uses check-first schema creation for additive SQLite
    # tables in production. Keep this local to the feature instead of adding
    # more migration logic to the legacy app.py monolith.
    with app.app_context():
        WritingTypingAttempt.__table__.create(bind=db.engine, checkfirst=True)
        QuestionTypePracticeAttempt.__table__.create(bind=db.engine, checkfirst=True)
