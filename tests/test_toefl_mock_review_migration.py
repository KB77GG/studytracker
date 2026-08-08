import sqlite3

from scripts import migrate_toefl_mock_review


def test_toefl_review_migration_is_idempotent_and_backfills_statuses(tmp_path):
    database = tmp_path / "review.sqlite"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE toefl_mock_attempt (
            id VARCHAR(36) PRIMARY KEY,
            exam_id VARCHAR(80) NOT NULL,
            status VARCHAR(24) NOT NULL
        );
        CREATE TABLE toefl_mock_response (
            id INTEGER PRIMARY KEY,
            attempt_id VARCHAR(36) NOT NULL,
            question_id VARCHAR(120) NOT NULL,
            response_json TEXT NOT NULL
        );
        INSERT INTO toefl_mock_attempt (id, exam_id, status)
        VALUES ('a1', 'toefl:ets-practice-1', 'completed');
        INSERT INTO toefl_mock_response (id, attempt_id, question_id, response_json)
        VALUES
          (1, 'a1', 'toefl:ets-practice-1:writing:m1:g02:q11', '"answer"'),
          (2, 'a1', 'toefl:ets-practice-1:reading:m1:g01:q01', '"answer"');
        """
    )
    connection.commit()
    connection.close()

    assert migrate_toefl_mock_review.migrate(database) == 1
    assert migrate_toefl_mock_review.migrate(
        database, migrate_toefl_mock_review.PACKAGE_ROOT
    ) == 0

    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE toefl_mock_attempt SET review_status = 'published' WHERE id = 'a1'"
    )
    connection.execute(
        "UPDATE toefl_mock_response SET review_status = 'reviewed' WHERE id = 1"
    )
    connection.commit()
    connection.close()
    assert migrate_toefl_mock_review.migrate(
        database, migrate_toefl_mock_review.PACKAGE_ROOT
    ) == 0

    connection = sqlite3.connect(database)
    attempt_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(toefl_mock_attempt)")
    }
    response_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(toefl_mock_response)")
    }
    assert {"review_status", "review_version", "review_published_at"}.issubset(attempt_columns)
    assert {"review_status", "teacher_score", "teacher_feedback"}.issubset(response_columns)
    assert connection.execute(
        "SELECT review_status FROM toefl_mock_attempt WHERE id = 'a1'"
    ).fetchone()[0] == "published"
    assert connection.execute(
        "SELECT review_status FROM toefl_mock_response WHERE id = 1"
    ).fetchone()[0] == "reviewed"
    assert connection.execute(
        "SELECT review_status FROM toefl_mock_response WHERE id = 2"
    ).fetchone()[0] == "not_required"
    indexes = {
        row[1]
        for row in connection.execute("PRAGMA index_list(toefl_mock_attempt)")
    }
    assert "ix_toefl_mock_attempt_review_status" in indexes
    connection.close()
