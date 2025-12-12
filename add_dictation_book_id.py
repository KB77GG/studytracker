#!/usr/bin/env python3
"""Add dictation_book_id column to task table."""

import sqlite3
import sys

def add_dictation_book_id():
    try:
        conn = sqlite3.connect('app.db')
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(task)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'dictation_book_id' in columns:
            print("✓ Column 'dictation_book_id' already exists")
            return
        
        # Add column
        print("Adding dictation_book_id column to task table...")
        cursor.execute("ALTER TABLE task ADD COLUMN dictation_book_id INTEGER REFERENCES dictation_book(id)")
        conn.commit()
        print("Done!")
        
    except Exception as e:
        print(f"Error adding column: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_dictation_book_id()
