"""Create the vocabulary answer-appeal review table if it is missing."""

from app import app
from models import DictationAnswerAppeal, db


def create_table():
    with app.app_context():
        DictationAnswerAppeal.__table__.create(bind=db.engine, checkfirst=True)
        print("Table 'dictation_answer_appeal' is ready.")


if __name__ == "__main__":
    create_table()
