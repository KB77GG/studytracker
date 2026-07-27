from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_student_workbench_has_preflight_audio_and_recording_contracts():
    template = (ROOT / "templates/toefl/mock_exam.html").read_text(encoding="utf-8")
    script = (ROOT / "static/js/toefl_mock.js").read_text(encoding="utf-8")
    api = (ROOT / "api/toefl_mock.py").read_text(encoding="utf-8")

    for marker in (
        "sectionPicker",
        "micCheckButton",
        "deviceCheck",
        "returnTo",
        "attemptId",
        "route-m2",
    ):
        assert marker in template or marker in script
    for marker in (
        "local_source",
        "once in test mode",
        "controlsList",
        "seeking",
        "getUserMedia",
        "MediaRecorder",
        "durationMs",
        "preparation_seconds",
        "response_seconds",
        "recordingId",
    ):
        assert marker in script or marker in api
    assert "recordingToken" not in script


def test_fast_text_input_flush_waits_for_pending_and_inflight_saves():
    script = (ROOT / "static/js/toefl_mock.js").read_text(encoding="utf-8")

    assert "pendingResponseValues" in script
    assert "inFlightResponseSaves" in script
    assert "Promise.allSettled" in script
    assert "await flushPendingResponses()" in script
    assert "responseSaveChains" in script


def test_report_and_blocked_copy_are_explicitly_staging_safe():
    template = (ROOT / "templates/toefl/mock_exam.html").read_text(encoding="utf-8")
    script = (ROOT / "static/js/toefl_mock.js").read_text(encoding="utf-8")

    assert "STAGING PREVIEW" in template
    assert "blocked 题只展示缺口" in template
    assert "不是正式成绩单" in script
    assert "pending teacher review" in script
    assert "blocked 题不进入分母" in script
