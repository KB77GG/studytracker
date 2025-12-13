from app import app, db
from sqlalchemy import text
import sqlite3

def add_columns():
    with app.app_context():
        # Get database path from config
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        
        print(f"Connecting to database at {db_path}...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check and add dictation_word_start
        try:
            cursor.execute("SELECT dictation_word_start FROM task LIMIT 1")
            print("Column 'dictation_word_start' already exists.")
        except sqlite3.OperationalError:
            print("Adding column 'dictation_word_start'...")
            cursor.execute("ALTER TABLE task ADD COLUMN dictation_word_start INTEGER DEFAULT 1")
            print("Done.")

        # Check and add dictation_word_end
        try:
            cursor.execute("SELECT dictation_word_end FROM task LIMIT 1")
            print("Column 'dictation_word_end' already exists.")
        except sqlite3.OperationalError:
            print("Adding column 'dictation_word_end'...")
            cursor.execute("ALTER TABLE task ADD COLUMN dictation_word_end INTEGER")
            print("Done.")
            
        conn.commit()
        conn.close()
        print("Migration completed successfully.")

if __name__ == "__main__":
    add_columns()
