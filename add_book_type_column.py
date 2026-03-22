#!/usr/bin/env python3
"""Add book_type column to dictation_book table."""

import sqlite3
import sys


def add_book_type_column():
    try:
        conn = sqlite3.connect('app.db')
        cursor = conn.cursor()

        # Check if column exists
        cursor.execute("PRAGMA table_info(dictation_book)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'book_type' in columns:
            print("✓ Column 'book_type' already exists in dictation_book")
        else:
            print("Adding book_type column to dictation_book table...")
            cursor.execute("ALTER TABLE dictation_book ADD COLUMN book_type VARCHAR(20) NOT NULL DEFAULT 'dictation'")
            conn.commit()
            print("✓ Done! book_type column added.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    add_book_type_column()
