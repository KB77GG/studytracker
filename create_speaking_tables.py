import os
from sqlalchemy import create_engine, text


DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "app.db")


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table_name});")).fetchall()
    return any((row[1] if len(row) > 1 else None) == column_name for row in rows)


def _ensure_column(conn, table_name: str, column_name: str, column_type: str) -> None:
    if _column_exists(conn, table_name, column_name):
        return
    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type};"))


def main():
    engine = create_engine(f"sqlite:///{DB_PATH}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS speaking_session (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    part TEXT NOT NULL,
                    question TEXT NOT NULL,
                    question_type TEXT,
                    source TEXT,
                    part2_topic TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    FOREIGN KEY(student_id) REFERENCES student_profile(id)
                );
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_speaking_session_student_id ON speaking_session(student_id);"))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS speaking_message (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    result_json TEXT,
                    audio_url TEXT,
                    meta_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES speaking_session(id)
                );
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_speaking_message_session_id ON speaking_message(session_id);"))
        _ensure_column(conn, "speaking_message", "audio_url", "TEXT")
        _ensure_column(conn, "speaking_message", "meta_json", "TEXT")


if __name__ == "__main__":
    main()
