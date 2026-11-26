"""Offline session-renewal tests with synthetic identities and fake HTTP only."""

import fcntl
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from services import ninefen_auth as auth

OLD_TOKEN = "synthetic-old-token"
NEW_TOKEN = "synthetic-new-token"
OWNER = "synthetic-owner"
NOW = 1800000000


def success_fixture():
    return {
        "code": 200,
        "data": {"token": NEW_TOKEN, "user": {"id": OWNER, "displayName": "not-to-be-saved"}},
    }


class Response(io.BytesIO):
    def __init__(self, payload=None, *, raw=None, status=200, content_type="application/json"):
        super().__init__(raw if raw is not None else json.dumps(payload).encode())
        self.status = status
        self.headers = {"Content-Type": content_type}

    def geturl(self):
        return auth.RENEW_URL


class NinefenAuthTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.session = self.root / "session.json"
        self.write_session()
        self.build = patch.object(auth.urllib.request, "build_opener").start()
        self.addCleanup(patch.stopall)
        self.opener = self.build.return_value
        self.opener.open.return_value = Response(success_fixture())

    def write_session(self, **changes):
        payload = {"token": OLD_TOKEN, "owner": OWNER, **changes}
        self.session.write_text(json.dumps(payload), encoding="utf-8")
        self.session.chmod(0o600)
        return self.session.read_bytes()

    def assert_failure_preserves_session(self, exception=auth.RenewalError):
        original = self.session.read_bytes()
        with self.assertRaises(exception) as caught:
            auth.renew_session_file(self.session, now=NOW)
        self.assertEqual(self.session.read_bytes(), original)
        for secret in (OLD_TOKEN, NEW_TOKEN, OWNER, "not-to-be-saved"):
            self.assertNotIn(secret, str(caught.exception))
            self.assertNotIn(secret, repr(caught.exception))
            self.assertNotIn(secret, repr(vars(caught.exception)))
        self.assertEqual(list(self.root.glob(".renew-*.tmp")), [])
        return caught.exception

    def test_exact_official_request_and_atomic_private_save(self):
        self.write_session(local_metadata="preserved")
        before_inode = self.session.stat().st_ino
        result = auth.renew_session_file(self.session, now=NOW)
        self.assertEqual(
            result, {"status": "renewed", "renewed_at": NOW, "durability_confirmed": True}
        )
        self.assertEqual(self.opener.open.call_count, 1)
        request = self.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, auth.RENEW_URL)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.data, b"{}")
        self.assertEqual(request.get_header("Token"), OLD_TOKEN)
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertIsNone(request.get_header("Cookie"))
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(self.opener.open.call_args.kwargs, {"timeout": 10})
        self.assertEqual(self.build.call_args.args[0].proxies, {})
        self.assertTrue(
            any(isinstance(item, auth._NoRedirect) for item in self.build.call_args.args)
        )
        self.assertEqual(
            json.loads(self.session.read_bytes()),
            {"token": NEW_TOKEN, "owner": OWNER, "local_metadata": "preserved", "renewed_at": NOW},
        )
        self.assertNotEqual(self.session.stat().st_ino, before_inode)
        self.assertEqual(self.session.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(self.root.glob(".renew-*.tmp")), [])

    def test_source_confirmed_aliases_nested_data_and_numeric_owner(self):
        for index, token_key in enumerate(auth.TOKEN_FIELDS):
            for user_key in auth.USER_FIELDS:
                with self.subTest(token_key=token_key, user_key=user_key):
                    self.write_session(owner="1234567890123456789")
                    data = {
                        token_key: NEW_TOKEN,
                        user_key: {"id": 1234567890123456789, "userId": "1234567890123456789"},
                    }
                    self.opener.open.return_value = Response(
                        {"code": "200", "data": {"data": data} if index == 1 else data}
                    )
                    self.assertEqual(
                        auth.renew_session_file(self.session, now=NOW)["status"], "renewed"
                    )

    def test_equal_aliases_are_supported_without_saving_user_details(self):
        payload = success_fixture()
        payload["data"].update(accessToken=NEW_TOKEN, student={"userId": OWNER})
        self.opener.open.return_value = Response(payload)
        auth.renew_session_file(self.session, now=NOW)
        saved = json.loads(self.session.read_bytes())
        self.assertEqual(set(saved), {"token", "owner", "renewed_at"})

    def test_incomplete_conflicting_or_unknown_response_fails_closed(self):
        bad_data = [
            {},
            {"token": NEW_TOKEN},
            {"user": {"id": OWNER}},
            {"refreshToken": NEW_TOKEN, "user": {"id": OWNER}},
            {"token": NEW_TOKEN, "user": {"id": "different-owner"}},
            {"token": NEW_TOKEN, "user": {}},
            {"token": NEW_TOKEN, "user": {"id": OWNER, "userId": "conflicting-owner"}},
            {"token": NEW_TOKEN, "user": {"id": True}},
            {"token": NEW_TOKEN, "user": {"id": 1.5}},
            {"token": NEW_TOKEN, "user": {"id": OWNER}, "accessToken": "conflicting-token"},
            {"token": NEW_TOKEN, "user": {"id": OWNER}, "student": {"id": "another-owner"}},
            {"token": NEW_TOKEN, "user": {"id": OWNER}, "data": {}},
            {"data": []},
            [],
        ]
        for data in bad_data:
            with self.subTest(data_shape=type(data).__name__):
                self.opener.open.reset_mock()
                self.opener.open.return_value = Response({"code": 200, "data": data})
                self.assert_failure_preserves_session()
                self.assertEqual(self.opener.open.call_count, 1)

    def test_returned_token_is_strictly_bounded_header_safe_text(self):
        for token in (None, "", " ", "abc\r\nHeader:value", "a b", "中文", 123, "a" * 8193):
            with self.subTest(token_type=type(token).__name__):
                fixture = success_fixture()
                fixture["data"]["token"] = token
                self.opener.open.return_value = Response(fixture)
                self.assert_failure_preserves_session()

    def test_authentication_rejection_has_distinct_type_and_never_retries(self):
        for status in (401, 403):
            with self.subTest(http_status=status):
                self.opener.open.reset_mock()
                self.opener.open.side_effect = urllib.error.HTTPError(
                    "https://invalid/" + OLD_TOKEN,
                    status,
                    OWNER,
                    {},
                    io.BytesIO(NEW_TOKEN.encode()),
                )
                failure = self.assert_failure_preserves_session(auth.AuthenticationRejected)
                self.assertEqual(failure.http_status, status)
                self.assertEqual(self.opener.open.call_count, 1)
        self.opener.open.side_effect = None
        for code in (401, 403, 10401, 10403, "401", "403", "10401", "10403"):
            with self.subTest(business_code=code):
                self.opener.open.reset_mock()
                self.opener.open.return_value = Response(
                    {"code": code, "msg": OLD_TOKEN, "data": {}}
                )
                self.assert_failure_preserves_session(auth.AuthenticationRejected)
                self.assertEqual(self.opener.open.call_count, 1)

    def test_transient_http_or_network_errors_are_never_retried(self):
        failures = [urllib.error.URLError(OLD_TOKEN), TimeoutError(OLD_TOKEN)]
        failures += [
            urllib.error.HTTPError("", code, NEW_TOKEN, {}, io.BytesIO(OWNER.encode()))
            for code in (301, 302, 307, 308, 429, 500, 503)
        ]
        for failure in failures:
            with self.subTest(failure_type=type(failure).__name__):
                self.opener.open.reset_mock()
                self.opener.open.side_effect = failure
                self.assert_failure_preserves_session()
                self.assertEqual(self.opener.open.call_count, 1)

    def test_redirect_handler_never_returns_a_followup_request(self):
        with self.assertRaises(auth.RenewalError):
            auth._NoRedirect().redirect_request(
                None, None, 302, OLD_TOKEN, {}, "https://other.invalid"
            )

    def test_status_content_type_and_json_schema_are_enforced(self):
        responses = [
            Response(success_fixture(), status=201),
            Response(success_fixture(), content_type="text/html"),
            Response(raw=b"not-json"),
            Response(raw=b'{"code":200,"code":401,"data":{}}'),
            Response(raw=b'{"code":200,"data":{},"extra":NaN}'),
            Response(raw=b"[]"),
            Response(raw=b" " * (auth.MAX_RESPONSE_BYTES + 1)),
            Response({"code": True, "data": success_fixture()["data"]}),
            Response({"code": 200.0, "data": success_fixture()["data"]}),
            Response({"code": "0200", "data": success_fixture()["data"]}),
            Response({"code": 500, "msg": OLD_TOKEN, "data": {}}),
        ]
        for response in responses:
            self.opener.open.return_value = response
            self.assert_failure_preserves_session()

    def test_only_explicit_private_owned_regular_file_is_read(self):
        self.session.chmod(0o644)
        self.assert_failure_preserves_session()
        self.session.chmod(0o600)
        self.root.chmod(0o755)
        self.assert_failure_preserves_session()
        self.root.chmod(0o700)
        with patch.object(auth.os, "getuid", return_value=os.getuid() + 1):
            self.assert_failure_preserves_session()
        self.build.assert_not_called()

    def test_session_and_directory_symlinks_and_hardlinks_are_rejected(self):
        linked = self.root / "linked.json"
        linked.symlink_to(self.session)
        with self.assertRaises(auth.RenewalError):
            auth.renew_session_file(linked, now=NOW)
        os.link(self.session, self.root / "hardlink.json")
        self.assert_failure_preserves_session()
        with tempfile.TemporaryDirectory() as elsewhere:
            directory = Path(elsewhere) / "alias"
            directory.symlink_to(self.root, target_is_directory=True)
            with self.assertRaises(auth.RenewalError):
                auth.renew_session_file(directory / "session.json", now=NOW)
        self.build.assert_not_called()

    def test_named_pipe_does_not_block_or_make_network_request(self):
        fifo = self.root / "fifo.json"
        os.mkfifo(fifo, 0o600)
        with self.assertRaises(auth.RenewalError):
            auth.renew_session_file(fifo, now=NOW)
        self.build.assert_not_called()

    def test_missing_owner_bad_token_and_malformed_files_do_not_make_a_request(self):
        fixtures = [
            {"token": OLD_TOKEN},
            {"token": OLD_TOKEN, "owner": 123},
            {"token": OLD_TOKEN, "owner": ""},
            {"token": "a b", "owner": OWNER},
            {"token": OLD_TOKEN, "owner": OWNER, "extra": "x" * auth.MAX_SESSION_BYTES},
        ]
        for fixture in fixtures:
            self.session.write_text(json.dumps(fixture))
            self.assert_failure_preserves_session()
        self.session.write_text('{"token":"first","token":"second"}')
        self.assert_failure_preserves_session()
        self.build.assert_not_called()

    def test_reason_codes_are_a_safe_fixed_enum(self):
        for value in (OLD_TOKEN, {}, [], None, True):
            error = auth.RenewalError("safe", reason_code=value, http_status=OWNER)
            self.assertEqual(error.reason_code, "renewal_failed")
            self.assertIsNone(error.http_status)
        self.session.write_text(json.dumps({"token": OLD_TOKEN}))
        self.assertEqual(self.assert_failure_preserves_session().reason_code, "owner_missing")
        self.build.assert_not_called()
        self.write_session()
        fixture = success_fixture()
        fixture["data"]["user"]["id"] = "different-owner"
        self.opener.open.return_value = Response(fixture)
        self.assertEqual(self.assert_failure_preserves_session().reason_code, "owner_mismatch")

    def test_concurrent_refresh_cannot_overwrite_the_newer_session(self):
        replacement = {"token": "synthetic-concurrent-token", "owner": OWNER}

        def update_while_renewing(*args, **kwargs):
            self.session.write_text(json.dumps(replacement))
            return Response(success_fixture())

        self.opener.open.side_effect = update_while_renewing
        with self.assertRaisesRegex(auth.RenewalError, "Session changed"):
            auth.renew_session_file(self.session, now=NOW)
        self.assertEqual(json.loads(self.session.read_bytes()), replacement)
        self.assertEqual(list(self.root.glob(".renew-*.tmp")), [])

    def test_inode_change_is_detected_even_if_bytes_are_unchanged(self):
        original = self.session.read_bytes()

        def replace_while_renewing(*args, **kwargs):
            temporary = self.root / "new-session.json"
            temporary.write_bytes(original)
            temporary.chmod(0o600)
            os.replace(temporary, self.session)
            return Response(success_fixture())

        self.opener.open.side_effect = replace_while_renewing
        self.assert_failure_preserves_session()

    def test_exclusive_lock_prevents_overlapping_renewals(self):
        lock = self.root / ".session.json.renew.lock"
        lock.write_text("")
        lock.chmod(0o600)
        with lock.open("rb") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assert_failure_preserves_session()
        self.build.assert_not_called()

    def test_unsafe_lock_file_is_rejected_before_network(self):
        lock = self.root / ".session.json.renew.lock"
        lock.symlink_to(self.session)
        self.assert_failure_preserves_session()
        self.build.assert_not_called()

    def test_write_and_rename_failure_preserve_original(self):
        for function in ("fsync", "replace"):
            with self.subTest(failing_function=function):
                self.opener.open.return_value = Response(success_fixture())
                with patch.object(auth.os, function, side_effect=OSError(OLD_TOKEN)):
                    self.assert_failure_preserves_session()

    def test_directory_fsync_failure_reports_committed_renewal_without_rollback(self):
        with patch.object(auth.os, "fsync", side_effect=[None, OSError(OLD_TOKEN)]):
            result = auth.renew_session_file(self.session, now=NOW)
        self.assertEqual(
            result, {"status": "renewed", "renewed_at": NOW, "durability_confirmed": False}
        )
        self.assertEqual(json.loads(self.session.read_bytes())["token"], NEW_TOKEN)
        self.assertEqual(self.opener.open.call_count, 1)
        self.assertEqual(auth.renew_session_file(self.session, now=NOW)["status"], "skipped_recent")
        self.assertEqual(self.opener.open.call_count, 1)

    def test_success_is_rate_limited_for_one_day(self):
        original = self.write_session(renewed_at=NOW - 86399)
        self.assertEqual(
            auth.renew_session_file(self.session, now=NOW),
            {"status": "skipped_recent", "renewed_at": NOW - 86399},
        )
        self.assertEqual(self.session.read_bytes(), original)
        self.build.assert_not_called()
        self.write_session(renewed_at=NOW - 86400)
        self.assertEqual(auth.renew_session_file(self.session, now=NOW)["status"], "renewed")
        self.assertEqual(self.opener.open.call_count, 1)

    def test_bad_timestamps_fail_without_network(self):
        for previous in (True, NOW + 1, 0, -1, str(NOW), 1.5):
            self.write_session(renewed_at=previous)
            self.assert_failure_preserves_session()
        self.write_session()
        for now in (True, 0, -1, 1.5, "invalid"):
            with self.assertRaises(auth.RenewalError):
                auth.renew_session_file(self.session, now=now)
        self.build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
