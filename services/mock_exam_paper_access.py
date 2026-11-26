"""Keep composed answer-bearing papers inside authenticated mock-exam handlers."""

from flask import has_request_context, request

from services.exam_sprint_papers import load_sprint_paper

MOCK_ENDPOINTS = frozenset(
    {
        "admin_mock_exams_create",
        "mock_exam_listening",
        "mock_exam_reading",
        "api_mock_exam_submit_listening",
        "api_mock_exam_submit_reading",
    }
)
MOCK_BLUEPRINTS = frozenset({"mock_exam_admin", "mock_exam_student", "mock_exam_review"})


def load_mock_paper(root, subject, test_id):
    # These existing handlers enforce staff access or the exam session token before
    # loading. Public practice/JSON/grading handlers must not expose this snapshot.
    if (
        has_request_context()
        and request.endpoint not in MOCK_ENDPOINTS
        and request.blueprint not in MOCK_BLUEPRINTS
    ):
        return None
    return load_sprint_paper(root, subject, test_id)
