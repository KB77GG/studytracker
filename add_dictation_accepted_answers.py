"""Add teacher-approved alternative answers to dictation words."""

from sqlalchemy import inspect, text

from app import app
from models import db


def add_column():
    with app.app_context():
        inspector = inspect(db.engine)
        if "dictation_word" not in inspector.get_table_names():
            print("Table 'dictation_word' does not exist.")
            return
        columns = {column["name"] for column in inspector.get_columns("dictation_word")}
        if "accepted_answers" in columns:
            print("Column 'accepted_answers' already exists.")
            return
        with db.engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE dictation_word ADD COLUMN accepted_answers TEXT")
            )
        print("Column 'accepted_answers' added.")


if __name__ == "__main__":
    add_column()
