#!/usr/bin/env python3
"""Create student_saved_word table for web-saved vocabulary."""

from sqlalchemy import inspect, text

from app import app, db
from models import StudentSavedWord


def add_student_saved_word_table():
    with app.app_context():
        inspector = inspect(db.engine)
        existed = "student_saved_word" in inspector.get_table_names()
        if existed:
            print("student_saved_word table already exists.")
        else:
            print("Creating student_saved_word table...")
            db.create_all()

        with db.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_student_saved_word_student_archived
                    ON student_saved_word (student_id, archived_at)
                    """
                )
            )

        inspector = inspect(db.engine)
        if "student_saved_word" in inspector.get_table_names():
            print("  ✓ student_saved_word exists")
        else:
            print("  ✗ student_saved_word NOT FOUND")


if __name__ == "__main__":
    add_student_saved_word_table()
