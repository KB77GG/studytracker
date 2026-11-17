"""Loopback-only synthetic UI fixture; never loads app.py or production config."""

from datetime import timedelta

from flask_login import login_user

from models import User, VocabularySense, db
from tests.test_vocabulary_error_reports import NOW, ROOT, VocabularyErrorReportsTest


def main():
    fixture = VocabularyErrorReportsTest()
    fixture.setUp()
    try:
        fixture.app.static_folder = str(ROOT / "static")
        fixture.profiles["student"].full_name = "合成学生甲"
        fixture.profiles["linked"].full_name = "合成学生乙"
        fixture.profiles["unrelated"].full_name = "合成学生丙"
        first = fixture._queue(status="paused")
        fixture._event(first, "paused")
        second = fixture._queue("linked", dimension="form_recall", status="maintenance")
        fixture._event(second, "overdue_overload")
        fixture._event(second, "unanswerable")
        fixture._event(first, "reopened", day=NOW.date() - timedelta(days=1))
        for index in range(25):
            sense = VocabularySense(canonical_key=f"visual-{index}", lemma=f"synthetic{index}", meaning_zh="合成词义")
            db.session.add(sense)
            db.session.flush()
            fixture._queue(sense=sense)
        db.session.commit()
        teacher_id = fixture.users["teacher"].id

        @fixture.app.before_request
        def synthetic_staff_session():
            login_user(db.session.get(User, teacher_id))

        fixture.app.run(host="127.0.0.1", port=5096, debug=False, use_reloader=False)
    finally:
        fixture.tearDown()


if __name__ == "__main__":
    main()
