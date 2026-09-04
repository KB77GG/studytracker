"""Content integrity and typing-score tests for the IELTS writing pilot."""

from pathlib import Path

from services.writing_library import (
    get_mother_topic,
    load_catalog,
    load_mother_topics,
    mother_topic_summary,
    normalize_typing_text,
    typing_metrics,
)


def test_pilot_contains_expected_tasks_and_complete_learning_content():
    catalog = load_catalog()
    exercises = catalog["exercises"]

    assert len(exercises) == 40
    assert sum(row["task"] == "task1" for row in exercises) == 10
    assert sum(row["task"] == "task2" for row in exercises) == 30
    assert {row["batch"] for row in exercises} == {"A", "B", "C"}

    for row in exercises:
        assert set(row["essays"]) == {"6.0", "6.5", "7.0+"}
        assert len(row["structures"]["four"]) == 4
        assert len(row["structures"]["five"]) == 5
        assert len(row["expressions"]) >= 3
        minimum = 150 if row["task"] == "task1" else 250
        assert all(model["word_count"] >= minimum for model in row["essays"].values())


def test_all_task1_images_are_versioned_static_assets():
    static_root = Path(__file__).resolve().parents[1] / "static"
    task1_rows = [row for row in load_catalog()["exercises"] if row["task"] == "task1"]

    assert len(task1_rows) == 10
    for row in task1_rows:
        assert row["image"].startswith("writing_library/images/")
        assert (static_root / row["image"]).is_file()


def test_mother_topics_cover_the_full_task2_source_with_rich_teaching_content():
    catalog = load_mother_topics()
    topics = catalog["topics"]
    prompts = [prompt for topic in topics for prompt in topic["prompts"]]

    assert len(topics) == 27
    assert len(prompts) == 252
    assert len({prompt["sequence"] for prompt in prompts}) == 252
    assert sum(prompt["source_normalized"] for prompt in prompts) == 4
    assert mother_topic_summary()["logic_chains"] == 108
    assert mother_topic_summary()["expressions"] == 216

    for topic in topics:
        assert len(topic["logic_chains"]) == 4
        assert len(topic["expressions"]) >= 8
        assert len(topic["pitfalls_zh"]) >= 3
        assert len(topic["guiding_questions_zh"]) >= 4
        assert len(topic["transfer_drills_zh"]) >= 3
        assert set(topic["model_essays"]) == {"6.0", "6.5", "7.0+"}
        assert all(
            essay["word_count"] >= 250
            for essay in topic["model_essays"].values()
        )


def test_every_pilot_task2_links_back_to_its_mother_topic():
    task2_rows = [row for row in load_catalog()["exercises"] if row["task"] == "task2"]

    assert len(task2_rows) == 30
    assert all(row["mother_topic"] for row in task2_rows)
    for row in task2_rows:
        topic = get_mother_topic(row["mother_topic"]["id"])
        assert any(prompt["exercise_id"] == row["id"] for prompt in topic["prompts"])


def test_typing_metrics_are_server_reproducible_and_normalized():
    target = "A clear plan—when followed—works well."
    exact = typing_metrics(target, "A  clear plan-when followed-works well.", 60)
    partial = typing_metrics(target, "A plan works.", 60)

    assert exact == {
        "typed_word_count": 5,
        "target_word_count": 5,
        "duration_seconds": 60,
        "speed_wpm": 5.0,
        "accuracy": 100.0,
    }
    assert partial["accuracy"] < exact["accuracy"]
    assert normalize_typing_text("  Smart ‘quotes’  ") == "smart 'quotes'"
