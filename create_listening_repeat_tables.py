"""Create listening repeat result table."""

import os
from sqlalchemy import create_engine, text


DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "app.db")


def main():
    engine = create_engine(f"sqlite:///{DB_PATH}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS listening_repeat_result (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    student_name VARCHAR(64) NOT NULL,
                    segment_index INTEGER NOT NULL,
                    segment_text TEXT,
                    audio_url VARCHAR(500),
                    overall_score FLOAT NOT NULL DEFAULT 0.0,
                    pron_accuracy FLOAT NOT NULL DEFAULT 0.0,
                    pron_fluency FLOAT NOT NULL DEFAULT 0.0,
                    pron_completion FLOAT NOT NULL DEFAULT 0.0,
                    suggested_score_100 FLOAT NOT NULL DEFAULT 0.0,
                    words_json TEXT,
                    is_passed BOOLEAN NOT NULL DEFAULT 0,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(task_id) REFERENCES task(id),
                    CONSTRAINT uq_task_repeat_segment UNIQUE (task_id, segment_index)
                );
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_lrr_task_id ON listening_repeat_result (task_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_lrr_student_name ON listening_repeat_result (student_name)"
            )
        )


if __name__ == "__main__":
    main()
