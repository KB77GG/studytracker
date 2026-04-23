"""Add is_uncertain column to student_answer table if missing."""

from sqlalchemy import inspect, text

from app import app
from models import db


def add_column():
    with app.app_context():
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())
        if "student_answer" not in tables:
            print("Table 'student_answer' does not exist.")
            return

        columns = {col["name"] for col in inspector.get_columns("student_answer")}
        if "is_uncertain" in columns:
            print("Column 'is_uncertain' already exists.")
            return

        print("Adding column 'is_uncertain'...")
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE student_answer "
                    "ADD COLUMN is_uncertain BOOLEAN NOT NULL DEFAULT 0"
                )
            )
        print("Column 'is_uncertain' added.")


if __name__ == "__main__":
    add_column()
