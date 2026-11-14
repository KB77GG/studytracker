"""Loopback-only synthetic QA: in-memory SQLite, real import and task templates.

Never import app.py or production config. /tasks is GET-only: this fixture
verifies preselection, while student learning is covered by integration tests.
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from flask import Flask, jsonify, render_template  # noqa: E402
from flask_login import LoginManager, login_user  # noqa: E402

from api.classroom_vocabulary import classroom_vocabulary_bp  # noqa: E402
from models import DictationBook, User, db  # noqa: E402


def create_preview_app():
    app = Flask(
        __name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static")
    )
    app.config.update(
        SECRET_KEY="synthetic-classroom-preview-only",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TEMPLATES_AUTO_RELOAD=True,
    )
    db.init_app(app)
    manager = LoginManager(app)

    @manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    with app.app_context():
        db.create_all()
        teacher = User(
            username="synthetic_classroom_teacher", display_name="合成教师", role="teacher"
        )
        teacher.set_password("preview-only-not-an-account")
        db.session.add(teacher)
        db.session.commit()
        teacher_id = teacher.id

    @app.before_request
    def synthetic_login():
        login_user(db.session.get(User, teacher_id))

    app.register_blueprint(classroom_vocabulary_bp)

    @app.get("/materials", endpoint="materials_list")
    def materials():
        return render_template("materials.html")

    @app.get("/tasks", endpoint="tasks_page")
    def tasks():
        today = date.today()
        books = DictationBook.query.filter_by(is_deleted=False).all()
        return render_template(
            "tasks.html",
            all_materials=[
                dict(
                    id=f"dictation-{b.id}",
                    title=b.title,
                    type="dictation",
                    book_type=b.book_type,
                    vocabulary_goal=b.default_vocabulary_goal,
                    course_system=b.course_system,
                    question_count=b.word_count,
                )
                for b in books
            ],
            all_students=["合成学生"],
            student_picker_options=[],
            student_memos={},
            items=[],
            pending_reviews=[],
            previous_day_tasks=[],
            recent_tasks=[],
            top_students=[],
            listening_exercises=[],
            listening_training_modes=[],
            reading_exercises=[],
            reading_exercise_passages={},
            question_type_summaries={},
            writing_resources=[],
            dictation_range_hints={},
            today=today.isoformat(),
            today_obj=today,
            start_date=today,
            previous_day=today.isoformat(),
            period="week",
            period_urls=dict(week="/tasks", month="/tasks", year="/tasks"),
            task_filters=dict(query="", category="", status="", student="", due_date=""),
            task_page=dict(
                total=0,
                start=0,
                end=0,
                page=1,
                pages=[],
                page_size=20,
                page_sizes=[20, 50],
                previous_url=None,
                next_url=None,
            ),
        )

    @app.get("/api/materials")
    def empty_materials():
        return jsonify(ok=True, materials=[])

    @app.get("/api/dictation/books")
    def books():
        return jsonify(
            ok=True,
            books=[
                dict(
                    id=b.id,
                    title=b.title,
                    description=b.description,
                    word_count=b.word_count,
                    book_type=b.book_type,
                )
                for b in DictationBook.query.all()
            ],
        )

    @app.get("/synthetic-state")
    def state():
        return jsonify(book_count=DictationBook.query.count())

    # Only URL destinations used in the shared shell are stubbed; the feature
    # page, import routes, task template and all local assets are the real files.
    for template in ("base.html", "tasks.html"):
        for endpoint in re.findall(
            r"url_for\('([^']+)'", (ROOT / "templates" / template).read_text()
        ):
            if endpoint not in app.view_functions:
                app.add_url_rule(
                    "/synthetic-nav/" + endpoint, endpoint, lambda: "Synthetic navigation"
                )
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5099)
    args = parser.parse_args()
    create_preview_app().run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
