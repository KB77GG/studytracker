"""Add vocabulary-enrichment columns to dictation_word if missing."""

from sqlalchemy import inspect, text

from app import app
from models import db


WORD_ENRICHMENT_COLUMNS = {
    "core_meaning_zh": "TEXT",
    "usage_pattern": "TEXT",
    "example_en": "TEXT",
    "example_zh": "TEXT",
    "usage_note": "TEXT",
    "vocab_ai_status": "VARCHAR(20) NOT NULL DEFAULT 'empty'",
    "vocab_ai_model": "VARCHAR(100)",
    "vocab_ai_generated_at": "DATETIME",
    "vocab_reviewed_at": "DATETIME",
    "vocab_report_count": "INTEGER NOT NULL DEFAULT 0",
}

WORD_ENRICHMENT_INDEXES = {
    "ix_dictation_word_vocab_ai_status": "vocab_ai_status",
    "ix_dictation_word_vocab_reviewed_at": "vocab_reviewed_at",
    "ix_dictation_word_vocab_report_count": "vocab_report_count",
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
            for column_name, column_type in WORD_ENRICHMENT_COLUMNS.items():
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

            for index_name, column_name in WORD_ENRICHMENT_INDEXES.items():
                print(f"Ensuring index '{index_name}'...")
                conn.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS {index_name} "
                        f"ON dictation_word ({column_name})"
                    )
                )

        print("Word enrichment migration completed successfully.")


if __name__ == "__main__":
    add_columns()
