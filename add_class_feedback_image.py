from app import app, db
from sqlalchemy import text

with app.app_context():
    print("Adding feedback_image column to class_feedback table...")
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE class_feedback ADD COLUMN feedback_image VARCHAR(200)"))
            conn.commit()
        print("Done!")
    except Exception as e:
        print(f"Error (maybe column exists): {e}")
