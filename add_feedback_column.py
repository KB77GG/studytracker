from app import app, db
from sqlalchemy import text

with app.app_context():
    print("Adding feedback_text column to task table...")
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE task ADD COLUMN feedback_text TEXT"))
            conn.commit()
        print("Done!")
    except Exception as e:
        print(f"Error (maybe column exists): {e}")
