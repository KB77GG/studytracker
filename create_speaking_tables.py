import os
from sqlalchemy import create_engine, text


DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "app.db")


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
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES speaking_session(id)
                );
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_speaking_message_session_id ON speaking_message(session_id);"))


if __name__ == "__main__":
    main()
