"""Contract checks for the additive, repeatable vocabulary migration."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from models import db
from scripts.migrate_vocabulary_forgot_response import COLUMNS, migrate
from services.vocabulary_mastery import ensure_vocabulary_schema


class VocabularyForgotMigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "isolated.db"

    def create_legacy_tables(self, *, missing: str | None = None):
        with sqlite3.connect(self.database) as connection:
            for table in COLUMNS:
                if table != missing:
                    connection.execute(
                        f'CREATE TABLE "{table}" (id INTEGER PRIMARY KEY, '
                        "student_answer VARCHAR(200))"
                    )
                    connection.execute(
                        f'INSERT INTO "{table}" (student_answer) VALUES (?)',
                        ("original answer",),
                    )

    def test_migrates_history_without_changing_answer_and_repeats(self):
        self.create_legacy_tables()
        self.assertEqual(len(migrate(self.database)), 5)
        self.assertEqual(migrate(self.database), [])
        with sqlite3.connect(self.database) as connection:
            for table, columns in COLUMNS.items():
                row = connection.execute(f'SELECT * FROM "{table}"').fetchone()
                names = [item[1] for item in connection.execute(f'PRAGMA table_info("{table}")')]
                data = dict(zip(names, row))
                self.assertEqual(data["student_answer"], "original answer")
                for column in columns:
                    self.assertEqual(data[column], "answer")
                connection.execute(
                    f'INSERT INTO "{table}" (student_answer) VALUES (?)',
                    ("old client",),
                )
                self.assertEqual(
                    connection.execute(
                        f'SELECT "{columns[0]}" FROM "{table}" WHERE student_answer=?',
                        ("old client",),
                    ).fetchone()[0],
                    "answer",
                )

    def test_missing_table_rolls_back_all_columns(self):
        self.create_legacy_tables(missing="vocabulary_review_attempt")
        with self.assertRaisesRegex(ValueError, "required table is missing"):
            migrate(self.database)
        with sqlite3.connect(self.database) as connection:
            for table in COLUMNS:
                if table != "vocabulary_review_attempt":
                    self.assertNotIn(
                        "response_kind",
                        [item[1] for item in connection.execute(f'PRAGMA table_info("{table}")')],
                    )
                    self.assertNotIn(
                        "first_response_kind",
                        [item[1] for item in connection.execute(f'PRAGMA table_info("{table}")')],
                    )

    def test_requires_existing_database(self):
        with self.assertRaisesRegex(ValueError, "database does not exist"):
            migrate(self.database)

    def test_startup_schema_guard_adds_missing_columns_to_legacy_tables(self):
        app = Flask(__name__)
        app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(app)
        with app.app_context():
            db.create_all()
            with db.engine.begin() as connection:
                for table, columns in COLUMNS.items():
                    for column in columns:
                        connection.exec_driver_sql(
                            f'ALTER TABLE "{table}" DROP COLUMN "{column}"'
                        )
            ensure_vocabulary_schema(db.engine)
            with db.engine.connect() as connection:
                for table, columns in COLUMNS.items():
                    names = {
                        row[1]
                        for row in connection.exec_driver_sql(
                            f'PRAGMA table_info("{table}")'
                        )
                    }
                    self.assertTrue(set(columns) <= names)
            db.session.remove()
            db.drop_all()


if __name__ == "__main__":
    unittest.main()
