"""Add usage_note_audited column to dictation_word if missing."""

from sqlalchemy import inspect, text

from app import app
from models import db


COLUMNS = {
    "usage_note_audited": "BOOLEAN NOT NULL DEFAULT 0",
}

INDEXES = {
    "ix_dictation_word_usage_note_audited": "usage_note_audited",
}


def add_columns():
    with app.app_context():
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())
        if "dictation_word" not in tables:
            print("Table 'dictation_word' does not exist.")
            return

        columns = {col["name"] for col in inspector.get_columns("dictation_word")}
        with db.engine.begin() as conn:
            for column_name, column_type in COLUMNS.items():
                if column_name in columns:
                    print(f"Column '{column_name}' already exists.")
                    continue
                print(f"Adding column '{column_name}'...")
                conn.execute(
                    text(
                        f"ALTER TABLE dictation_word "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )
                print(f"Column '{column_name}' added.")

            for index_name, column_name in INDEXES.items():
                print(f"Ensuring index '{index_name}'...")
                conn.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS {index_name} "
                        f"ON dictation_word ({column_name})"
                    )
                )

        print("usage_note_audited migration completed successfully.")


if __name__ == "__main__":
    add_columns()
