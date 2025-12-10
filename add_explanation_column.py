#!/usr/bin/env python3
"""Add explanation column to question table for translation exercises."""

import sqlite3
import sys

def add_explanation_column():
    try:
        conn = sqlite3.connect('app.db')
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(question)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'explanation' in columns:
            print("✓ Column 'explanation' already exists")
            return
        
        # Add column
        cursor.execute("ALTER TABLE question ADD COLUMN explanation TEXT")
        conn.commit()
        print("✓ Added 'explanation' column to question table")
        
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("✓ Column already exists (duplicate column name error)")
        else:
            print(f"✗ Error: {e}")
            sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Adding explanation column to question table...")
    add_explanation_column()
    print("Done!")
