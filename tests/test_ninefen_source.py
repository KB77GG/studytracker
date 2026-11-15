"""No-network tests for public ranking integrity and bounded source requests."""

import copy
import io
import json
import unittest
import urllib.error
from datetime import datetime, timezone
from unittest.mock import patch

from services import ninefen_source as source


def public_payload():
    albums = []
    item_id = 2100000000000000000
    for channel, part_count in source.SUBJECT_PARTS.items():
        slots = []
        for part in range(1, part_count + 1):
            rows = []
            for rank in range(1, 21):
                item_id += 1
                rows.append(
                    {
                        "id": str(item_id),
                        "channel": channel,
                        "partId": str(item_id + 1000),
                        "partCode": f"PT-TEST-{item_id}",
                        "entryMode": "exam",
                        "available": True,
                        "lockedForOrdinaryUsers": False,
                        "title": f"Example {part} {rank}",
                        "titleZh": "示例",
                        "rank": rank,
                        "sevenDayReportTotal": 300 - rank,
                    }
                )
            slots.append(
                {
                    "key": f"part:Part {part}",
                    "label": f"Part {part}",
                    "channel": channel,
                    "count": 20,
                    "publicRowLimit": 20,
                    "list": rows,
                    "hasMore": True,
                }
            )
        albums.append(
            {
                "channel": channel,
                "groupCode": "weekly_dynamic",
                "publicRowLimit": 20,
                "slots": slots,
            }
        )
    return {"code": "200", "data": {"list": albums}, "msg": "OK"}


class PublicRankingTests(unittest.TestCase):
    def test_complete_snapshot_preserves_large_string_ids_and_actual_fetch_time(self):
        now = datetime(2026, 11, 15, 1, 2, tzinfo=timezone.utc)  # noqa: UP017
        result = source.parse_public_hotlist(public_payload(), fetched_at=now)
        self.assertEqual(result["fetched_at"], now.isoformat())
        self.assertIsNone(result["source_updated_at"])
        self.assertEqual([len(v) for v in result["subjects"].values()], [3, 4])
        rows = [r for groups in result["subjects"].values() for g in groups for r in g["items"]]
        self.assertEqual(len(rows), 140)
        self.assertEqual(rows[0]["source_id"], "2100000000000000001")
        self.assertEqual(rows[0]["heat_label"], "近7天上报 299 次")
        self.assertEqual(rows[0]["source_part_id"], "2100000000000001001")
        self.assertEqual(rows[0]["source_version_title"], rows[0]["title"])
        self.assertTrue(rows[0]["source_available"])

    def test_partial_subject_section_or_row_rejected(self):
        payload = public_payload()
        for location in [
            payload["data"]["list"],
            payload["data"]["list"][0]["slots"],
            payload["data"]["list"][0]["slots"][0]["list"],
        ]:
            removed = location.pop()
            with self.assertRaises(source.NinefenSourceError):
                source.parse_public_hotlist(payload)
            location.append(removed)

    def test_duplicate_or_wrong_rank_and_identity_rejected(self):
        mutations = [
            ("id", "2100000000000000002"),
            ("id", 2100000000000000001),
            ("id", "../../other"),
            ("rank", 2),
            ("rank", True),
            ("rank", 21),
            ("channel", "writing"),
            ("sevenDayReportTotal", -1),
            ("sevenDayReportTotal", True),
            ("title", ""),
        ]
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                payload = public_payload()
                payload["data"]["list"][0]["slots"][0]["list"][0][key] = value
                with self.assertRaises(source.NinefenSourceError):
                    source.parse_public_hotlist(payload)

    def test_extra_rows_scope_change_and_duplicate_section_rejected(self):
        for kind in ["extra", "scope", "duplicate"]:
            with self.subTest(kind=kind):
                payload = public_payload()
                slots = payload["data"]["list"][0]["slots"]
                if kind == "extra":
                    slots[0]["list"].append(copy.deepcopy(slots[0]["list"][0]))
                elif kind == "scope":
                    slots[0]["publicRowLimit"] = 50
                else:
                    slots[1] = copy.deepcopy(slots[0])
                with self.assertRaises(source.NinefenSourceError):
                    source.parse_public_hotlist(payload)

    def test_failed_business_response_rejected(self):
        for payload in [{"code": "401"}, [], {"code": 200, "data": {"list": []}}]:
            with self.assertRaises(source.NinefenSourceError):
                source.parse_public_hotlist(payload)

    def test_naive_time_rejected(self):
        with self.assertRaises(source.NinefenSourceError):
            source.parse_public_hotlist(public_payload(), fetched_at=datetime(2026, 11, 15))


class PublicRequestTests(unittest.TestCase):
    @patch.object(source.urllib.request, "build_opener")
    def test_one_get_without_auth_even_when_more_rows_exist(self, build):
        build.return_value.open.return_value = io.BytesIO(json.dumps(public_payload()).encode())
        result = source.fetch_public_hotlist(timeout=7)
        request = build.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, source.API_BASE + source.HOTLIST_PATH)
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(build.return_value.open.call_args.kwargs["timeout"], 7)
        self.assertNotIn("Cookie", dict(request.header_items()))
        self.assertNotIn("Token", dict(request.header_items()))
        self.assertEqual(build.return_value.open.call_count, 1)
        self.assertEqual(result["source"], "ninefen")

    @patch.object(source.time, "sleep")
    @patch.object(source.urllib.request, "build_opener")
    def test_transient_failure_retries_are_bounded(self, build, sleep):
        build.return_value.open.side_effect = urllib.error.URLError("offline")
        with self.assertRaises(source.NinefenSourceError):
            source.fetch_public_hotlist()
        self.assertEqual(build.return_value.open.call_count, 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2])

    @patch.object(source.time, "sleep")
    @patch.object(source.urllib.request, "build_opener")
    def test_auth_error_is_not_retried(self, build, sleep):
        build.return_value.open.side_effect = urllib.error.HTTPError("", 401, "", {}, None)
        with self.assertRaisesRegex(source.NinefenSourceError, "401"):
            source.fetch_public_hotlist()
        self.assertEqual(build.return_value.open.call_count, 1)
        sleep.assert_not_called()

    @patch.object(source.urllib.request, "build_opener")
    def test_bad_json_and_oversized_response_rejected(self, build):
        for data in [b"<html>login</html>", b"x" * (source.MAX_RESPONSE_BYTES + 1)]:
            build.return_value.open.return_value = io.BytesIO(data)
            with self.assertRaises(source.NinefenSourceError):
                source.fetch_public_hotlist()

    def test_no_redirects(self):
        with self.assertRaises(source.NinefenSourceError):
            source._NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid")

    @patch.object(source, "_fetch_json")
    def test_exam_limits_ids_and_refuses_charged_content(self, fetch):
        for unit_id in ["../private", "1?token=abc", 123, "https://other.invalid"]:
            with self.assertRaises(source.NinefenSourceError):
                source.fetch_public_exam(unit_id)
        fetch.assert_not_called()
        fetch.return_value = {"code": 200, "data": {"id": "123", "isCharge": 1}}
        with self.assertRaises(source.NinefenSourceError):
            source.fetch_public_exam("123")

    @patch.object(source, "_fetch_json")
    def test_public_exam_accepts_explicit_zero_and_preserves_missing_answers(self, fetch):
        # Match the public reading/listening envelope without copying question text.
        unit_id = "2102715008296194050"
        for charge in (0, "0"):
            with self.subTest(charge=charge):
                sample = {
                    "code": "200",
                    "msg": "OK",
                    "data": {
                        "id": unit_id,
                        "channel": "reading",
                        "isCharge": charge,
                        "parts": [{"groups": [{"questions": [{"rightAnswer": None}]}]}],
                    },
                }
                fetch.return_value = sample
                self.assertIs(source.fetch_public_exam(unit_id), sample)
                fetch.assert_called_with(f"/practice/v1/units/{unit_id}/exam", 20)
                self.assertIsNone(
                    sample["data"]["parts"][0]["groups"][0]["questions"][0]["rightAnswer"]
                )

    @patch.object(source, "_fetch_json")
    def test_exam_charge_unknown_or_coercible_values_are_rejected(self, fetch):
        for charge in (False, True, 0.0, "false", "00", None, "1", 1):
            with self.subTest(charge=charge):
                fetch.return_value = {"code": 200, "data": {"id": "123", "isCharge": charge}}
                with self.assertRaises(source.NinefenSourceError):
                    source.fetch_public_exam("123")

    @patch.object(source.urllib.request, "build_opener")
    def test_timeout_limits(self, build):
        for timeout in [0, -1, 61, float("inf"), float("nan"), True]:
            with self.assertRaises(source.NinefenSourceError):
                source.fetch_public_hotlist(timeout=timeout)
        build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
