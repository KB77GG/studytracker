"""Synthetic, offline tests; never read a real session or submit a real result."""

import copy
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

from services import ninefen_session as ns

UNIT_ID = "2102715008296194050"
RESULT_ID = "1234567890123456789"


def exam_fixture():
    return {
        "code": "200",
        "data": {
            "id": UNIT_ID,
            "channel": "reading",
            "isCharge": 0,
            "parts": [
                {
                    "id": "2001",
                    "groups": [
                        {
                            "id": "3001",
                            "type": "multiple-choice",
                            "questions": [
                                {"id": "4001", "qNumber": "1", "rightAnswer": None},
                                {"id": "4002", "qNumber": "2", "rightAnswer": None},
                            ],
                        }
                    ],
                }
            ],
        },
    }


def review_fixture():
    return {
        "result": {"unitId": UNIT_ID, "userId": "synthetic-user", "id": RESULT_ID},
        "parts": [
            {
                "id": "2001",
                "groups": [
                    {
                        "id": "3001",
                        "type": "multiple-choice",
                        "questions": [
                            {"id": "4001", "qNumber": "1", "rightAnswer": "A", "userAnswer": ""},
                            {"id": "4002", "qNumber": "2", "rightAnswer": "C", "userAnswer": ""},
                        ],
                    }
                ],
            }
        ],
    }


class PrivateSessionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.session_file = self.root / "session.json"
        self.session_file.write_text('{"token":"synthetic-test-only"}')
        self.session_file.chmod(0o600)

    def test_private_mode_and_symlinks_rejected(self):
        self.session_file.chmod(0o644)
        with self.assertRaises(ns.CollectionError):
            ns.NinefenSession(self.session_file)
        self.session_file.chmod(0o600)
        alias = self.root / "alias.json"
        alias.symlink_to(self.session_file)
        with self.assertRaises(ns.CollectionError):
            ns.NinefenSession(alias)

    @patch.object(ns.urllib.request, "build_opener")
    def test_only_explicit_token_header_and_fixed_endpoint(self, build):
        build.return_value.open.return_value = io.BytesIO(
            json.dumps(
                {
                    "code": "200",
                    "data": {"list": [{"unitId": UNIT_ID, "resultId": RESULT_ID}]},
                }
            ).encode()
        )
        session = ns.NinefenSession(self.session_file)
        self.assertNotIn("synthetic-test-only", repr(session))
        self.assertEqual(session.existing_result(UNIT_ID), RESULT_ID)
        request = build.return_value.open.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(
            request.full_url, ns.API_BASE + "/practice/v1/unit-status?unitIds=" + UNIT_ID
        )
        self.assertEqual(request.get_header("Token"), "synthetic-test-only")
        self.assertIsNone(request.get_header("Cookie"))
        with self.assertRaises(ns.CollectionError):
            session._request("https://other.invalid/")
        with self.assertRaises(ns.CollectionError):
            session.review("../other")
        with self.assertRaises(ns.CollectionError):
            session._request("/practice/v1/unit-status?unitIds=" + UNIT_ID, {})
        with self.assertRaises(ns.CollectionError):
            session._request("/practice/v1/attempts")
        self.assertEqual(build.return_value.open.call_count, 1)

    @patch.object(ns.urllib.request, "build_opener")
    def test_post_timeout_is_uncertain_never_retried_and_sanitized(self, build):
        build.return_value.open.side_effect = urllib.error.URLError("synthetic-test-only")
        session = ns.NinefenSession(self.session_file, allow_new_attempts=True)
        with self.assertRaises(ns.UncertainSubmission) as raised:
            session.submit_blank({"unitId": UNIT_ID})
        self.assertNotIn("synthetic-test-only", str(raised.exception))
        self.assertEqual(build.return_value.open.call_count, 1)

    @patch.object(ns.urllib.request, "build_opener")
    def test_auth_failure_and_unknown_status_stop(self, build):
        session = ns.NinefenSession(self.session_file)
        build.return_value.open.side_effect = urllib.error.HTTPError("", 401, "", {}, None)
        with self.assertRaises(ns.CollectionError):
            session.existing_result(UNIT_ID)
        self.assertEqual(build.return_value.open.call_count, 1)
        build.return_value.open.side_effect = None
        build.return_value.open.return_value = io.BytesIO(b'{"code":200,"data":{"list":[]}}')
        with self.assertRaises(ns.CollectionError):
            session.existing_result(UNIT_ID)

    @patch.object(ns.time, "sleep")
    @patch.object(ns.urllib.request, "build_opener")
    def test_get_retries_only_network_errors_with_one_two_second_delays(self, build, sleep):
        build.return_value.open.side_effect = [
            urllib.error.URLError("synthetic-test-only"),
            TimeoutError("synthetic-test-only"),
            io.BytesIO(
                json.dumps(
                    {"code": 200, "data": {"list": [{"unitId": UNIT_ID, "resultId": RESULT_ID}]}}
                ).encode()
            ),
        ]
        session = ns.NinefenSession(self.session_file)
        self.assertEqual(session.existing_result(UNIT_ID), RESULT_ID)
        self.assertEqual(build.return_value.open.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    @patch.object(ns.time, "sleep")
    @patch.object(ns.urllib.request, "build_opener")
    def test_get_retries_429_and_5xx(self, build, sleep):
        build.return_value.open.side_effect = [
            urllib.error.HTTPError("", 429, "", {}, None),
            urllib.error.HTTPError("", 503, "", {}, None),
            io.BytesIO(b'{"code":200,"data":{"verified":"synthetic"}}'),
        ]
        self.assertEqual(
            ns.NinefenSession(self.session_file).review(RESULT_ID), {"verified": "synthetic"}
        )
        self.assertEqual(build.return_value.open.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    @patch.object(ns.time, "sleep")
    @patch.object(ns.urllib.request, "build_opener")
    def test_get_network_retry_is_bounded_and_sanitized(self, build, sleep):
        build.return_value.open.side_effect = urllib.error.URLError("synthetic-test-only")
        with self.assertRaises(ns.CollectionError) as error:
            ns.NinefenSession(self.session_file).review(RESULT_ID)
        self.assertNotIn("synthetic-test-only", str(error.exception))
        self.assertEqual(build.return_value.open.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch.object(ns.time, "sleep")
    @patch.object(ns.urllib.request, "build_opener")
    def test_get_does_not_retry_auth_schema_identity_or_redirect_errors(self, build, sleep):
        cases = [
            urllib.error.HTTPError("", 401, "", {}, None),
            ns.CollectionError("Official API redirected; collection stopped"),
            io.BytesIO(b"not-json"),
            io.BytesIO(b'{"code":200,"data":[]}'),
            io.BytesIO(b'{"code":401,"data":{}}'),
            io.BytesIO(b'{"code":200,"data":{"list":[{"unitId":"999","resultId":null}]}}'),
        ]
        session = ns.NinefenSession(self.session_file)
        for case in cases:
            build.return_value.open.reset_mock()
            if isinstance(case, Exception):
                build.return_value.open.side_effect = case
            else:
                build.return_value.open.side_effect = None
                build.return_value.open.return_value = case
            with self.assertRaises(ns.CollectionError):
                session.existing_result(UNIT_ID)
            self.assertEqual(build.return_value.open.call_count, 1)
        sleep.assert_not_called()

    @patch.object(ns.time, "sleep")
    @patch.object(ns.urllib.request, "build_opener")
    def test_post_never_retries_even_on_429_or_5xx(self, build, sleep):
        session = ns.NinefenSession(self.session_file, allow_new_attempts=True)
        for status in (429, 500, 503):
            build.return_value.open.reset_mock()
            build.return_value.open.side_effect = urllib.error.HTTPError("", status, "", {}, None)
            with self.assertRaises(ns.UncertainSubmission):
                session.submit_blank({"unitId": UNIT_ID})
            self.assertEqual(build.return_value.open.call_count, 1)
        sleep.assert_not_called()

    def test_no_redirect(self):
        with self.assertRaises(ns.CollectionError):
            ns._NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid")

    def test_approval_is_exact_one_time_123_string_ids(self):
        path = self.root / "approval.json"
        payload = {
            "schema_version": 1,
            "scope": "one_time_blank_submission",
            "unit_ids": [str(2100000000000000000 + index) for index in range(123)],
        }
        path.write_text(json.dumps(payload))
        ids, digest, scope = ns.load_approval(path)
        self.assertEqual(scope, "one_time_blank_submission")
        self.assertEqual(len(ids), 123)
        self.assertEqual(len(digest), 64)
        for mutate in [
            lambda p: p["unit_ids"].pop(),
            lambda p: p.update(scope="weekly_auto_submission"),
            lambda p: p["unit_ids"].__setitem__(0, 123),
            lambda p: p["unit_ids"].__setitem__(0, p["unit_ids"][1]),
        ]:
            bad = copy.deepcopy(payload)
            mutate(bad)
            path.write_text(json.dumps(bad))
            with self.assertRaises(ns.CollectionError):
                ns.load_approval(path)

    @patch.object(ns.urllib.request, "build_opener")
    def test_session_is_read_only_unless_explicitly_enabled(self, build):
        session = ns.NinefenSession(self.session_file)
        with self.assertRaises(ns.NewAttemptRequired):
            session.submit_blank({"unitId": UNIT_ID})
        build.return_value.open.assert_not_called()

    def test_weekly_approval_is_bounded_and_scope_bound(self):
        path = self.root / "approval.json"
        payload = {"schema_version": 1, "scope": "weekly_new_or_changed", "unit_ids": [UNIT_ID]}
        path.write_text(json.dumps(payload))
        ids, digest, scope = ns.load_approval(path)
        self.assertEqual(ids, [UNIT_ID])
        self.assertEqual(scope, "weekly_new_or_changed")
        self.assertEqual(len(digest), 64)
        for ids in [[], [str(i) for i in range(141)], [UNIT_ID, UNIT_ID]]:
            payload["unit_ids"] = ids
            path.write_text(json.dumps(payload))
            with self.assertRaises(ns.CollectionError):
                ns.load_approval(path)


class AnswerBindingTests(unittest.TestCase):
    def test_blank_multi_is_one_answer_per_question_with_stable_uuid(self):
        submission_id = "12345678-1234-4234-8234-123456789abc"
        payload = ns.build_blank_submission(exam_fixture(), UNIT_ID, submission_id)
        self.assertEqual(payload["clientSubmissionId"], submission_id)
        self.assertNotIn("timer", payload)
        self.assertEqual(payload["annotationSnapshot"], {"version": 1, "annotations": []})
        questions = payload["parts"][0]["groups"][0]["questions"]
        self.assertEqual([q["userAnswer"] for q in questions], ["", ""])
        self.assertEqual([q["qNumber"] for q in questions], ["1", "2"])

    def test_answers_export_does_not_leak_result_or_user_and_preserves_multi(self):
        output = ns.extract_verified_answers(exam_fixture(), review_fixture(), UNIT_ID)
        self.assertEqual([q["answer"] for q in output["answers"]], ["A", "C"])
        serialized = json.dumps(output)
        self.assertNotIn(RESULT_ID, serialized)
        self.assertNotIn("synthetic-user", serialized)
        self.assertEqual(set(output), {"unit_id", "source_content_sha256", "answers"})

    def test_wrong_unit_part_group_question_number_or_missing_answer_rejected(self):
        cases = [
            lambda r: r["result"].update(unitId="999"),
            lambda r: r["parts"][0].update(id="999"),
            lambda r: r["parts"][0]["groups"][0].update(id="999"),
            lambda r: r["parts"][0]["groups"][0]["questions"][0].update(id="999"),
            lambda r: r["parts"][0]["groups"][0]["questions"][0].update(qNumber="9"),
            lambda r: r["parts"][0]["groups"][0]["questions"][0].update(rightAnswer=None),
            lambda r: r["parts"][0]["groups"][0]["questions"].pop(),
        ]
        for mutate in cases:
            review = review_fixture()
            mutate(review)
            with self.assertRaises(ns.CollectionError):
                ns.extract_verified_answers(exam_fixture(), review, UNIT_ID)


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.private = Path(self.temporary.name) / "private"
        self.session = Mock()
        self.session.review.return_value = review_fixture()
        self.session.submit_blank.return_value = RESULT_ID
        self.session.existing_result.return_value = None

    def collector(
        self, *, allow=True, scope="one_time_blank_submission", approval="approval-digest"
    ):
        return ns.AnswerCollector(
            self.session,
            self.private,
            [UNIT_ID],
            approval,
            allow_new_attempts=allow,
            scope=scope,
        )

    def test_existing_result_reused_without_post_and_private_files(self):
        self.session.existing_result.return_value = RESULT_ID
        with ns.collection_lock(self.private):
            path = self.collector().collect(UNIT_ID, exam_fixture())
        self.session.submit_blank.assert_not_called()
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.private.stat().st_mode & 0o777, 0o700)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        self.collector().collect(UNIT_ID, exam_fixture())
        self.assertEqual(self.session.review.call_count, 1)

    def test_pending_uuid_persisted_before_only_post(self):
        def submit(payload):
            checkpoint = ns._private_read(self.private / "checkpoint.json")
            entry = checkpoint["units"][UNIT_ID][ns.content_digest(exam_fixture())]
            self.assertEqual(entry["state"], "pending")
            self.assertEqual(entry["clientSubmissionId"], payload["clientSubmissionId"])
            return RESULT_ID

        self.session.submit_blank.side_effect = submit
        self.collector().collect(UNIT_ID, exam_fixture())
        self.session.submit_blank.assert_called_once()

    def test_uncertain_post_reconciles_read_only_then_completes(self):
        self.session.existing_result.side_effect = [None, RESULT_ID]
        self.session.submit_blank.side_effect = ns.UncertainSubmission("timeout")
        self.collector().collect(UNIT_ID, exam_fixture())
        self.session.submit_blank.assert_called_once()
        self.assertEqual(self.session.existing_result.call_count, 2)

    def test_uncertain_post_without_result_stops_and_resume_does_not_resubmit(self):
        self.session.submit_blank.side_effect = ns.UncertainSubmission("timeout")
        with self.assertRaises(ns.UncertainSubmission):
            self.collector().collect(UNIT_ID, exam_fixture())
        with self.assertRaises(ns.UncertainSubmission):
            self.collector().collect(UNIT_ID, exam_fixture())
        self.session.submit_blank.assert_called_once()
        self.session.review.assert_not_called()

    def test_crash_after_intent_cannot_trigger_second_post(self):
        self.session.submit_blank.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.collector().collect(UNIT_ID, exam_fixture())
        with self.assertRaises(ns.UncertainSubmission):
            self.collector().collect(UNIT_ID, exam_fixture())
        self.session.submit_blank.assert_called_once()

    def test_review_failure_retries_only_read_on_resume(self):
        self.session.review.side_effect = [ns.CollectionError("offline"), review_fixture()]
        with self.assertRaises(ns.CollectionError):
            self.collector().collect(UNIT_ID, exam_fixture())
        self.collector().collect(UNIT_ID, exam_fixture())
        self.session.submit_blank.assert_called_once()
        self.assertEqual(self.session.review.call_count, 2)

    def test_changed_exam_unapproved_id_or_approval_stop(self):
        collector = self.collector()
        with self.assertRaises(ns.CollectionError):
            collector.collect("999", exam_fixture())
        self.session.existing_result.assert_not_called()
        collector.collect(UNIT_ID, exam_fixture())
        changed = exam_fixture()
        changed["data"]["title"] = "Changed version"
        with self.assertRaises(ns.CollectionError):
            self.collector().collect(UNIT_ID, changed)
        self.collector(approval="different-approval").collect(UNIT_ID, exam_fixture())
        self.session.submit_blank.assert_called_once()

    def test_default_read_only_collector_never_submits(self):
        collector = ns.AnswerCollector(self.session, self.private, [UNIT_ID], "digest")
        with self.assertRaises(ns.NewAttemptRequired):
            collector.collect(UNIT_ID, exam_fixture())
        self.session.submit_blank.assert_not_called()
        self.session.existing_result.return_value = RESULT_ID
        collector.collect(UNIT_ID, exam_fixture())
        self.session.submit_blank.assert_not_called()

    def test_weekly_changed_version_reuses_matching_existing_review(self):
        self.session.existing_result.return_value = RESULT_ID
        self.collector(scope="weekly_new_or_changed").collect(UNIT_ID, exam_fixture())
        changed = exam_fixture()
        changed["data"]["title"] = "New descriptive title"
        self.collector(scope="weekly_new_or_changed", approval="next-week").collect(
            UNIT_ID, changed
        )
        self.session.submit_blank.assert_not_called()
        checkpoint = ns._private_read(self.private / "checkpoint.json")
        self.assertEqual(len(checkpoint["units"][UNIT_ID]), 2)
        self.collector(scope="weekly_new_or_changed").collect(UNIT_ID, exam_fixture())
        self.assertEqual(self.session.review.call_count, 2)
        cached = ns._private_read(self.private / "answers" / f"{UNIT_ID}.json")
        self.assertEqual(cached["source_content_sha256"], ns.content_digest(exam_fixture()))

    def test_weekly_changed_question_posts_once_after_old_review_mismatch(self):
        self.session.existing_result.return_value = RESULT_ID
        self.collector(scope="weekly_new_or_changed").collect(UNIT_ID, exam_fixture())
        changed = exam_fixture()
        changed["data"]["parts"][0]["groups"][0]["questions"][0]["id"] = "4999"
        changed_review = review_fixture()
        changed_review["parts"][0]["groups"][0]["questions"][0]["id"] = "4999"
        self.session.review.side_effect = [review_fixture(), changed_review]
        self.session.submit_blank.return_value = "9999"
        self.collector(scope="weekly_new_or_changed").collect(UNIT_ID, changed)
        self.collector(scope="weekly_new_or_changed").collect(UNIT_ID, changed)
        self.session.submit_blank.assert_called_once()
        checkpoint = ns._private_read(self.private / "checkpoint.json")
        self.assertEqual(len(checkpoint["units"][UNIT_ID]), 2)

    def test_changed_content_same_ids_can_trigger_one_new_attempt(self):
        changed = exam_fixture()
        changed["data"]["parts"][0]["groups"][0]["contentHtml"] = "new content"
        old_review = review_fixture()
        old_review["parts"][0]["groups"][0]["contentHtml"] = "old content"
        current_review = review_fixture()
        current_review["parts"][0]["groups"][0]["contentHtml"] = "new content"
        self.session.existing_result.return_value = RESULT_ID
        self.session.review.side_effect = [old_review, current_review]
        self.session.submit_blank.return_value = "9999"
        self.collector(scope="weekly_new_or_changed").collect(UNIT_ID, changed)
        self.session.submit_blank.assert_called_once()

    def test_uncertain_changed_version_does_not_mistake_old_result_for_new(self):
        changed = exam_fixture()
        changed["data"]["parts"][0]["groups"][0]["questions"][0]["id"] = "4999"
        self.session.existing_result.return_value = RESULT_ID
        self.session.submit_blank.side_effect = ns.UncertainSubmission("timeout")
        for _ in range(2):
            with self.assertRaises(ns.UncertainSubmission):
                self.collector(scope="weekly_new_or_changed").collect(UNIT_ID, changed)
        self.session.submit_blank.assert_called_once()
        another = copy.deepcopy(changed)
        another["data"]["title"] = "Another change while pending"
        with self.assertRaises(ns.UncertainSubmission):
            self.collector(scope="weekly_new_or_changed").collect(UNIT_ID, another)
        self.session.submit_blank.assert_called_once()

    def test_missing_answer_or_failed_review_does_not_authorize_new_attempt(self):
        self.session.existing_result.return_value = RESULT_ID
        incomplete = review_fixture()
        incomplete["parts"][0]["groups"][0]["questions"][0]["rightAnswer"] = None
        self.session.review.side_effect = [ns.CollectionError("HTTP401"), incomplete]
        for _ in range(2):
            with self.assertRaises(ns.CollectionError):
                self.collector(scope="weekly_new_or_changed").collect(UNIT_ID, exam_fixture())
        self.session.submit_blank.assert_not_called()

    def test_legacy_pending_checkpoint_migrates_without_post(self):
        ns._private_write(
            self.private / "checkpoint.json",
            {
                "schema_version": 1,
                "approval_sha256": "old-approval",
                "units": {
                    UNIT_ID: {
                        "source_content_sha256": ns.content_digest(exam_fixture()),
                        "state": "pending",
                        "clientSubmissionId": "12345678-1234-4234-8234-123456789abc",
                    }
                },
            },
        )
        with self.assertRaises(ns.UncertainSubmission):
            self.collector(scope="weekly_new_or_changed").collect(UNIT_ID, exam_fixture())
        self.session.submit_blank.assert_not_called()
        self.assertEqual(ns._private_read(self.private / "checkpoint.json")["schema_version"], 2)

    def test_invalid_completed_answer_cache_stops_without_post(self):
        self.session.existing_result.return_value = RESULT_ID
        output = self.collector().collect(UNIT_ID, exam_fixture())
        version_output = output.parent / UNIT_ID / f"{ns.content_digest(exam_fixture())}.json"
        cached = ns._private_read(version_output)
        cached["answers"].pop()
        ns._private_write(version_output, cached)
        with self.assertRaises(ns.CollectionError):
            self.collector().collect(UNIT_ID, exam_fixture())
        self.session.submit_blank.assert_not_called()

    def test_missing_review_content_stops_without_binding_or_new_attempt(self):
        changed = exam_fixture()
        changed["data"]["parts"][0]["groups"][0]["contentHtml"] = "Changed question text"
        self.session.existing_result.return_value = RESULT_ID
        with self.assertRaises(ns.CollectionError) as error:
            self.collector(scope="weekly_new_or_changed").collect(UNIT_ID, changed)
        self.assertNotIsInstance(error.exception, ns.ReviewMismatch)
        self.session.submit_blank.assert_not_called()
        self.assertFalse((self.private / "answers" / f"{UNIT_ID}.json").exists())

    def test_changed_group_instructions_require_current_review(self):
        changed = exam_fixture()
        changed["data"]["parts"][0]["groups"][0].update(
            description="Choose TWO letters.", qRange="1-2"
        )
        old_review = review_fixture()
        old_review["parts"][0]["groups"][0].update(description="Choose ONE letter.", qRange="1-2")
        with self.assertRaises(ns.ReviewMismatch):
            ns.extract_verified_answers(changed, old_review, UNIT_ID)
        old_review["parts"][0]["groups"][0].update(description="Choose TWO letters.", qRange="3-4")
        with self.assertRaises(ns.ReviewMismatch):
            ns.extract_verified_answers(changed, old_review, UNIT_ID)

    def test_prepared_version_cannot_submit_while_another_version_is_pending(self):
        changed = exam_fixture()
        changed["data"]["title"] = "A second version prepared earlier"
        for exam in (exam_fixture(), changed):
            with self.assertRaises(ns.NewAttemptRequired):
                self.collector(allow=False, scope="weekly_new_or_changed").collect(UNIT_ID, exam)
        self.session.submit_blank.side_effect = ns.UncertainSubmission("timeout")
        with self.assertRaises(ns.UncertainSubmission):
            self.collector(scope="weekly_new_or_changed").collect(UNIT_ID, exam_fixture())
        with self.assertRaises(ns.UncertainSubmission):
            self.collector(scope="weekly_new_or_changed").collect(UNIT_ID, changed)
        self.session.submit_blank.assert_called_once()

    def test_partial_or_duplicate_review_is_not_permission_for_another_attempt(self):
        self.session.existing_result.return_value = RESULT_ID
        partial = review_fixture()
        partial["parts"][0]["groups"][0]["questions"].pop()
        duplicate = review_fixture()
        duplicate["parts"][0]["groups"][0]["questions"].append(
            duplicate["parts"][0]["groups"][0]["questions"][0].copy()
        )
        for review in (partial, duplicate):
            self.session.review.return_value = review
            with self.assertRaises(ns.CollectionError) as error:
                self.collector(scope="weekly_new_or_changed").collect(UNIT_ID, exam_fixture())
            self.assertNotIsInstance(error.exception, ns.ReviewMismatch)
        self.session.submit_blank.assert_not_called()

    def test_parallel_collectors_are_locked_out(self):
        with ns.collection_lock(self.private):
            with self.assertRaises(ns.CollectionError), ns.collection_lock(self.private):
                pass


class CollectorCommandTests(unittest.TestCase):
    def test_cli_requires_explicit_flag_for_both_submission_layers(self):
        from scripts import collect_ninefen_answers as command

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            approval = root / "approval.json"
            approval.write_text(
                json.dumps(
                    {"schema_version": 1, "scope": "weekly_new_or_changed", "unit_ids": [UNIT_ID]}
                )
            )
            (root / f"{UNIT_ID}.json").write_text(json.dumps(exam_fixture()))
            arguments = [
                "--session-file",
                str(root / "unused-session.json"),
                "--approval-file",
                str(approval),
                "--exam-dir",
                str(root),
            ]
            for enabled in (False, True):
                with (
                    patch.object(command, "ROOT", root),
                    patch.object(command, "NinefenSession") as session,
                    patch.object(command, "AnswerCollector") as collector,
                    patch("sys.stdout", new_callable=io.StringIO),
                ):
                    self.assertEqual(
                        command.main(arguments + (["--allow-new-attempts"] if enabled else [])), 0
                    )
                    self.assertIs(session.call_args.kwargs["allow_new_attempts"], enabled)
                    self.assertIs(collector.call_args.kwargs["allow_new_attempts"], enabled)
                    self.assertEqual(collector.call_args.kwargs["scope"], "weekly_new_or_changed")
                    collector.return_value.collect.assert_called_once()


if __name__ == "__main__":
    unittest.main()
