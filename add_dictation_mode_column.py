from app import app
import sqlite3


def add_column():
    with app.app_context():
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        print(f"Connecting to database at {db_path}...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT dictation_mode FROM task LIMIT 1")
            print("Column 'dictation_mode' already exists.")
        except sqlite3.OperationalError:
            print("Adding column 'dictation_mode'...")
            cursor.execute(
                "ALTER TABLE task ADD COLUMN dictation_mode VARCHAR(20) DEFAULT 'audio_to_en'"
            )
            print("Done.")

        conn.commit()
        conn.close()
        print("Migration completed successfully.")


if __name__ == "__main__":
    add_column()
