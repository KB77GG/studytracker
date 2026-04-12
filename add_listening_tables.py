"""Migration: add listening fields to Task + create ListeningSegmentResult table."""

import secrets

from app import app, db
from sqlalchemy import text

with app.app_context():
    with db.engine.connect() as conn:
        # 1. Add Task columns
        for column_sql, label in [
            ("ALTER TABLE task ADD COLUMN listening_exercise_id VARCHAR(120)", "listening_exercise_id"),
            ("ALTER TABLE task ADD COLUMN listening_access_token VARCHAR(64)", "listening_access_token"),
        ]:
            print(f"Adding {label} column to task table...")
            try:
                conn.execute(text(column_sql))
                conn.commit()
                print("  Done!")
            except Exception as e:
                print(f"  Skipped (maybe exists): {e}")

        # 2. Create indexes
        for idx_sql, label in [
            ("CREATE INDEX ix_task_listening_exercise_id ON task (listening_exercise_id)", "ix_task_listening_exercise_id"),
            ("CREATE INDEX ix_task_listening_access_token ON task (listening_access_token)", "ix_task_listening_access_token"),
        ]:
            try:
                conn.execute(text(idx_sql))
                conn.commit()
                print(f"  Index created: {label}")
            except Exception as e:
                print(f"  Index skipped: {e}")

        # 3. Backfill missing listening_access_token for existing listening tasks
        rows = conn.execute(text("""
            SELECT id
            FROM task
            WHERE listening_exercise_id IS NOT NULL
              AND (listening_access_token IS NULL OR listening_access_token = '')
        """)).fetchall()
        for row in rows:
            conn.execute(
                text("UPDATE task SET listening_access_token = :token WHERE id = :task_id"),
                {"token": secrets.token_urlsafe(16), "task_id": row[0]},
            )
        if rows:
            conn.commit()
            print(f"  Backfilled tokens for {len(rows)} listening tasks.")

        # 4. Create ListeningSegmentResult table
        print("Creating listening_segment_result table...")
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS listening_segment_result (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    student_name VARCHAR(64) NOT NULL,
                    segment_index INTEGER NOT NULL,
                    segment_text TEXT,
                    hidden_word_indices TEXT,
                    answers_json TEXT,
                    correct_words INTEGER NOT NULL DEFAULT 0,
                    total_words INTEGER NOT NULL DEFAULT 0,
                    accuracy FLOAT NOT NULL DEFAULT 0.0,
                    is_completed BOOLEAN NOT NULL DEFAULT 0,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES task(id),
                    UNIQUE (task_id, segment_index)
                )
            """))
            conn.commit()
            print("  Done!")
        except Exception as e:
            print(f"  Skipped: {e}")

        # 5. Create indexes
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS ix_lsr_task_id ON listening_segment_result (task_id)",
            "CREATE INDEX IF NOT EXISTS ix_lsr_student_name ON listening_segment_result (student_name)",
        ]:
            try:
                conn.execute(text(idx_sql))
                conn.commit()
            except Exception:
                pass

    print("Migration complete.")
