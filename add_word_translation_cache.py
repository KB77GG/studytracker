"""Create the word translation cache table for review-page selection lookup."""

from sqlalchemy import text

from app import app
from models import db


def add_word_translation_cache_table():
    with app.app_context():
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS word_translation_cache (
                        word TEXT PRIMARY KEY,
                        translation TEXT NOT NULL,
                        source TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
        print("Word translation cache table is ready.")


if __name__ == "__main__":
    add_word_translation_cache_table()
