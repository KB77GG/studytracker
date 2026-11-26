"""Local browser acceptance server. All identities and records are invented.

Run from the implementation tree with .venv/bin/python; never deploy this file.
The in-memory database resets on restart. TTS is a local synthetic tone, with
no network call or heavyweight inference. /__qa/ routes exist only here.
"""

import io
import math
import struct
import sys
import types
import wave
from datetime import datetime, timedelta
from pathlib import Path

from flask import redirect, request, send_file, session

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
config = types.ModuleType("config")
config.Config = type("FixtureConfig", (), {
    "SECRET_KEY": "synthetic-local-vocabulary-acceptance",
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    "UPLOAD_FOLDER": "/private/tmp/studytracker-vocabulary-synthetic-uploads",
    "PRACTICE_VOCABULARY_WEB_ENABLED": True,
    "TESTING": True,
})
sys.modules["config"] = config

from app import app  # noqa: E402
from models import DictationBook, DictationWord, StudentProfile, Task, User, db  # noqa: E402
from services.task_date_gate import beijing_today  # noqa: E402
from services.vocabulary_mastery import ensure_mastery, ensure_word_sense  # noqa: E402

with app.app_context():
    db.create_all()
    teacher = User(username="qa-teacher", role=User.ROLE_TEACHER, password_hash="synthetic")
    student = User(username="qa-student", role=User.ROLE_STUDENT, password_hash="synthetic")
    db.session.add_all([teacher, student])
    db.session.flush()
    db.session.add(StudentProfile(full_name="合成验收学生", user_id=student.id))
    book = DictationBook(title="网页背词 · 合成验收词书", created_by=teacher.id, word_count=4)
    db.session.add(book)
    db.session.flush()
    fixtures = [
        ("depend", "依赖", "/dɪˈpend/", "depend on", "Students depend on clear feedback.", "学生依赖清晰的反馈。"),
        ("focus", "集中", "/ˈfəʊkəs/", "focus on", "Students focus on the main idea.", "学生专注于主要观点。"),
        ("contribute", "贡献", "/kənˈtrɪbjuːt/", "contribute to", "Students contribute to discussion.", "学生为讨论作出贡献。"),
        ("achieve", "实现", "/əˈtʃiːv/", "achieve a goal", "Students achieve a useful goal.", "学生实现了有益的目标。"),
    ]
    for index, (word, meaning, phonetic, pattern, example, translation) in enumerate(fixtures, 1):
        db.session.add(DictationWord(
            book_id=book.id, sequence=index, word=word, translation=meaning,
            core_meaning_zh=meaning, phonetic=phonetic, usage_pattern=pattern,
            example_en=example, example_zh=translation,
            usage_note="常用搭配，请结合句子理解。",
        ))
    task_ids = {}
    for goal in ("reading", "writing", "listening", "comprehensive", "future", "expired"):
        task = Task(
            student_name="合成验收学生", category="词汇", created_by=teacher.id,
            date=(beijing_today() + timedelta(days=1 if goal == "future" else -2 if goal == "expired" else 0)).isoformat(),
            dictation_book_id=book.id, vocabulary_goal=goal if goal not in {"future", "expired"} else "reading",
            dictation_word_start=1, dictation_word_end=2,
        )
        db.session.add(task)
        db.session.flush()
        task_ids[goal] = task.id
    db.session.commit()


@app.get("/__qa/start/<goal>")
def qa_start(goal):
    session.clear()
    session["practice_student_name"] = "合成验收学生"
    session["qa_fault"] = request.args.get("fault", "")
    return redirect(f"/practice/vocabulary/tasks/{task_ids[goal]}")


@app.get("/__qa/review")
def qa_review():
    learner = User.query.filter_by(username="qa-student").one()
    word = DictationWord.query.filter_by(word="contribute").one()
    mastery = ensure_mastery(learner, word, ensure_word_sense(word))
    mastery.meaning_recall_stage = 1
    mastery.meaning_recall_next_due_at = datetime.utcnow() - timedelta(days=1)
    db.session.commit()
    session["practice_student_name"] = "合成验收学生"
    return redirect(f"/practice/vocabulary/tasks/{task_ids['reading']}")


@app.get("/__qa/control/<fault>")
def qa_control(fault):
    session["qa_fault"] = fault
    return f"合成验收故障状态：{fault}"


@app.before_request
def qa_audio():
    if session.get("qa_fault") == "answers" and request.path.endswith("/answers"):
        return {"ok": False, "error": "synthetic_save_failure"}, 503
    if session.get("qa_fault") == "settle" and request.path.endswith("/settle"):
        return {"ok": False, "error": "synthetic_settle_failure"}, 503
    if request.path.startswith("/api/dictation/words/") and request.path.endswith("/tts"):
        if session.get("qa_fault") == "audio":
            return "Synthetic audio failure", 503
        out = io.BytesIO()
        with wave.open(out, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            wav.writeframes(b"".join(struct.pack("<h", int(2500 * math.sin(n * math.tau * 440 / 8000))) for n in range(4000)))
        out.seek(0)
        return send_file(out, mimetype="audio/wav")


@app.after_request
def qa_lost_response(response):
    if request.path.endswith("/answers") and response.status_code == 200 and session.get("qa_fault") == "response_lost":
        session.pop("qa_fault", None)
        return app.make_response(({"ok": False, "error": "synthetic_lost_response"}, 503))
    return response


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5111, debug=False, use_reloader=False)
