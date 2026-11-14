"""Synthetic tests for trusted small-class recipient resolution."""

import copy
import time
import unittest
from unittest.mock import patch

import jwt
from flask import Flask

from models import StudentProfile, User, db
from services.teacher_homework_recipients import (
    HomeworkRecipientsError,
    legacy_homework_is_group,
    preview_recipients,
    validate_recipients,
)


class TeacherHomeworkRecipientsTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="recipient-test-secret",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.teacher = User(
            username="teacher", password_hash="x", role="teacher", scheduler_teacher_id=17
        )
        student_user = User(
            username="member-a", password_hash="x", role="student", wechat_openid="synthetic-a"
        )
        db.session.add_all([self.teacher, student_user])
        db.session.flush()
        self.profiles = [
            StudentProfile(full_name="合成甲", user_id=student_user.id),
            StudentProfile(full_name="合成乙"),
            StudentProfile(full_name="合成丙"),
        ]
        db.session.add_all(self.profiles)
        db.session.commit()
        self.raw = {
            "id": 99,
            "teacher_id": 17,
            "student_id": 701,
            "student_name": "合成甲/合成乙/合成丙",
            "schedule_date": "2026-11-14",
            "course_name": "雅思听力",
            "start_time": "13:00",
            "end_time": "14:00",
        }
        self.data = {
            "schedule_id": 99,
            "schedule_uid": "id:99",
            "schedule_date": "2026-11-14",
            "teacher_id": 17,
        }
        self.fetch = patch(
            "services.teacher_homework_recipients.fetch_range_schedules_by_dates",
            side_effect=lambda *_args, **_kwargs: ({"schedules": [copy.deepcopy(self.raw)]}, None),
        ).start()
        self.addCleanup(patch.stopall)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def confirmed(self):
        preview = preview_recipients(self.teacher, self.data)
        return {
            **self.data,
            "roster_token": preview["roster_token"],
            "recipient_profile_ids": [row["profile_id"] for row in preview["members"]],
        }

    def assert_error(self, code, fn, *args, **kwargs):
        with self.assertRaises(HomeworkRecipientsError) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_three_individuals_and_wechat_status(self):
        preview = preview_recipients(self.teacher, self.data)
        self.assertTrue(preview["can_assign"])
        self.assertTrue(preview["is_group"])
        self.assertEqual(
            [row["profile_id"] for row in preview["members"]], [p.id for p in self.profiles]
        )
        self.assertEqual(
            [row["has_wechat_binding"] for row in preview["members"]], [True, False, False]
        )
        self.assertEqual(self.fetch.call_args.kwargs["teacher_id"], 17)
        self.assertEqual(StudentProfile.query.count(), 3)

    def test_legacy_group_guard_precedes_bound_first_member_resolution(self):
        self.profiles[0].scheduler_student_id = 701
        db.session.commit()
        self.assertTrue(
            legacy_homework_is_group({"student_id": 701, "student_name": "合成甲/合成乙/合成丙"})
        )
        self.assertTrue(legacy_homework_is_group({"student_name": "合成甲／合成乙"}))
        self.assertFalse(legacy_homework_is_group({"student_name": "Synthetic Alice"}))
        self.fetch.assert_not_called()

    def test_legacy_quick_guard_uses_verified_roster_not_overridden_profile_name(self):
        quick_context = {
            "student_name": "合成甲",
            "schedule": {"student_name": "合成甲 / 合成乙 / 合成丙"},
        }
        self.assertTrue(legacy_homework_is_group({"student_name": "合成甲"}, quick_context))
        self.assertTrue(legacy_homework_is_group({}, quick_context))
        self.assertFalse(
            legacy_homework_is_group(
                {"student_name": "合成甲"}, {"schedule": {"student_name": "合成甲"}}
            )
        )

    def test_missing_member_blocks_all_and_is_not_created(self):
        self.profiles[1].is_deleted = True
        db.session.commit()
        result = preview_recipients(self.teacher, self.data)
        self.assertFalse(result["can_assign"])
        self.assertIsNone(result["roster_token"])
        self.assertEqual(
            [row["status"] for row in result["members"]], ["ready", "missing", "ready"]
        )
        self.assertIn("合成乙", result["message"])
        self.assertEqual(StudentProfile.query.count(), 3)

    def test_same_name_profiles_are_ambiguous(self):
        db.session.add(StudentProfile(full_name="合成乙"))
        db.session.commit()
        preview = preview_recipients(self.teacher, self.data)
        self.assertFalse(preview["can_assign"])
        self.assertEqual(preview["members"][1]["status"], "ambiguous")

    def test_combined_record_binding_never_replaces_group_members(self):
        self.profiles[0].scheduler_student_id = 701
        db.session.commit()
        self.assertEqual(len(preview_recipients(self.teacher, self.data)["members"]), 3)
        self.assertEqual(self.profiles[0].scheduler_student_id, 701)

    def test_structured_profiles_bind_individual_scheduler_ids(self):
        self.raw["student_name"] = "合成班级"
        self.raw["student_profiles"] = [
            {"id": 11, "name": "排课甲"},
            {"student_id": 12, "student_name": "合成乙"},
            {"scheduler_student_id": 13, "full_name": "合成丙"},
        ]
        self.profiles[0].scheduler_student_id = 11
        db.session.commit()
        result = preview_recipients(self.teacher, self.data)
        self.assertTrue(result["can_assign"])
        self.assertEqual(result["members"][0]["student_name"], "合成甲")

    def test_partial_profile_array_does_not_hide_missing_member(self):
        self.raw["student_profiles"] = [{"name": "合成甲"}, {"name": "合成丙"}]
        self.profiles[1].is_deleted = True
        db.session.commit()
        result = preview_recipients(self.teacher, self.data)
        self.assertEqual(len(result["members"]), 3)
        self.assertFalse(result["can_assign"])
        self.assertEqual(result["members"][-1]["status"], "missing")

    def test_conflicting_structured_roster_is_rejected(self):
        self.raw["student_profiles"] = [{"name": "合成丁"}]
        self.assert_error("invalid_roster", preview_recipients, self.teacher, self.data)

    def test_duplicate_roster_name_is_not_silently_deduplicated(self):
        self.raw["student_name"] = "合成甲/合成甲/合成丙"
        result = preview_recipients(self.teacher, self.data)
        self.assertFalse(result["can_assign"])
        self.assertEqual(result["members"][0]["status"], "ambiguous")

    def test_spaces_in_english_names_are_preserved(self):
        self.raw["student_name"] = "Synthetic Alice／Synthetic Bob"
        db.session.add_all(
            [StudentProfile(full_name="Synthetic Alice"), StudentProfile(full_name="Synthetic Bob")]
        )
        db.session.commit()
        result = preview_recipients(self.teacher, self.data)
        self.assertTrue(result["can_assign"])
        self.assertEqual(
            [row["student_name"] for row in result["members"]], ["Synthetic Alice", "Synthetic Bob"]
        )

    def test_client_name_and_members_cannot_override_real_roster(self):
        forged = {**self.data, "student_name": "合成丁", "student_profiles": [{"name": "合成丁"}]}
        result = preview_recipients(self.teacher, forged)
        self.assertEqual(len(result["members"]), 3)
        self.assertEqual(result["members"][0]["student_name"], "合成甲")

    def test_unowned_returned_schedule_is_rejected_even_if_id_matches(self):
        self.raw["teacher_id"] = 18
        self.assert_error("forbidden_schedule", preview_recipients, self.teacher, self.data)

    def test_missing_authoritative_teacher_is_not_filled_from_client(self):
        del self.raw["teacher_id"]
        self.assert_error("forbidden_schedule", preview_recipients, self.teacher, self.data)

    def test_client_teacher_tampering_rejected_without_network(self):
        self.assert_error(
            "forbidden_schedule", preview_recipients, self.teacher, {**self.data, "teacher_id": 18}
        )
        self.fetch.assert_not_called()

    def test_wrong_date_or_schedule_uid_is_rejected(self):
        self.assert_error(
            "forbidden_schedule",
            preview_recipients,
            self.teacher,
            {**self.data, "schedule_uid": "id:100"},
        )
        self.assert_error(
            "forbidden_schedule",
            preview_recipients,
            self.teacher,
            {**self.data, "schedule_date": "2026-11-15"},
        )
        self.assert_error(
            "invalid_schedule_date",
            preview_recipients,
            self.teacher,
            {**self.data, "schedule_date": "not-a-date"},
        )

    def test_ambiguous_scheduler_rows_are_rejected(self):
        self.fetch.side_effect = lambda *_args, **_kwargs: ([self.raw, self.raw], None)
        self.assert_error("forbidden_schedule", preview_recipients, self.teacher, self.data)

    def test_scheduler_failure_fails_closed(self):
        self.fetch.side_effect = lambda *_args, **_kwargs: (None, "network_error")
        self.assert_error(
            "scheduler_verification_failed", preview_recipients, self.teacher, self.data
        )

    def test_no_teacher_binding_is_rejected(self):
        self.teacher.scheduler_teacher_id = None
        self.assert_error(
            "missing_scheduler_teacher_id", preview_recipients, self.teacher, self.data
        )

    def test_unbound_admin_can_confirm_an_explicit_teacher_roster(self):
        admin = User(username="group-admin", password_hash="x", role=User.ROLE_ADMIN)
        db.session.add(admin)
        db.session.commit()
        preview = preview_recipients(admin, self.data)
        self.assertTrue(preview["can_assign"])
        self.assertEqual(self.fetch.call_args.kwargs["teacher_id"], 17)
        confirmed = {
            **self.data,
            "roster_token": preview["roster_token"],
            "recipient_profile_ids": [member["profile_id"] for member in preview["members"]],
        }
        profiles, context = validate_recipients(admin, confirmed)
        self.assertEqual(len(profiles), 3)
        self.assertEqual(context["schedule"]["teacher_id"], 17)
        self.assert_error("invalid_roster_token", validate_recipients, self.teacher, confirmed)

    def test_admin_explicit_teacher_must_match_authoritative_schedule(self):
        admin = User(username="group-admin", password_hash="x", role=User.ROLE_ADMIN)
        db.session.add(admin)
        db.session.commit()
        self.assert_error(
            "forbidden_schedule", preview_recipients, admin, {**self.data, "teacher_id": 18}
        )
        self.assertEqual(self.fetch.call_args.kwargs["teacher_id"], 18)
        self.assert_error(
            "missing_scheduler_teacher_id",
            preview_recipients,
            admin,
            {**self.data, "teacher_id": ""},
        )

    def test_admin_can_use_own_binding_when_teacher_not_supplied(self):
        self.teacher.role = User.ROLE_ADMIN
        db.session.commit()
        preview = preview_recipients(self.teacher, {**self.data, "teacher_id": ""})
        self.assertTrue(preview["can_assign"])
        self.assertEqual(self.fetch.call_args.kwargs["teacher_id"], 17)

    def test_view_all_schedule_whitelist_does_not_grant_assignment_scope(self):
        self.app.config["ALL_SCHEDULE_TEACHER_ACCOUNTS"] = self.teacher.username
        self.assert_error(
            "forbidden_schedule", preview_recipients, self.teacher, {**self.data, "teacher_id": 18}
        )
        self.teacher.scheduler_teacher_id = None
        self.assert_error(
            "missing_scheduler_teacher_id", preview_recipients, self.teacher, self.data
        )

    def test_confirmed_full_roster_revalidates_and_read_does_not_need_selection(self):
        confirmed = self.confirmed()
        profiles, context = validate_recipients(self.teacher, confirmed)
        self.assertEqual([row.id for row in profiles], [p.id for p in self.profiles])
        self.assertTrue(context["fingerprint"])
        confirmed.pop("recipient_profile_ids")
        self.assertEqual(
            len(validate_recipients(self.teacher, confirmed, require_selection=False)[0]), 3
        )
        self.assert_error("recipient_mismatch", validate_recipients, self.teacher, confirmed)

    def test_subset_extra_duplicate_and_boolean_selection_rejected(self):
        confirmed = self.confirmed()
        ids = confirmed["recipient_profile_ids"]
        for value in [
            ids[:2],
            ids + [999],
            ids + [ids[0]],
            [True, ids[1], ids[2]],
            [str(i) for i in ids],
        ]:
            with self.subTest(value=value):
                self.assert_error(
                    "recipient_mismatch",
                    validate_recipients,
                    self.teacher,
                    {**confirmed, "recipient_profile_ids": value},
                )

    def test_roster_change_after_preview_requires_new_confirmation(self):
        confirmed = self.confirmed()
        self.raw["student_name"] = "合成甲/合成乙"
        self.assert_error("roster_changed", validate_recipients, self.teacher, confirmed)

    def test_deleted_member_after_preview_blocks_publishing(self):
        confirmed = self.confirmed()
        self.profiles[1].is_deleted = True
        db.session.commit()
        self.assert_error("roster_incomplete", validate_recipients, self.teacher, confirmed)

    def test_signed_token_is_bound_to_teacher_and_has_expiry(self):
        confirmed = self.confirmed()
        token = jwt.decode(
            confirmed["roster_token"], self.app.config["SECRET_KEY"], algorithms=["HS256"]
        )
        for key, value in [("sub", "999"), ("teacher_id", "18"), ("typ", "unrelated")]:
            altered = jwt.encode(
                {**token, key: value}, self.app.config["SECRET_KEY"], algorithm="HS256"
            )
            self.assert_error(
                "invalid_roster_token",
                validate_recipients,
                self.teacher,
                {**confirmed, "roster_token": altered},
            )
        expired = jwt.encode(
            {**token, "exp": int(time.time()) - 1}, self.app.config["SECRET_KEY"], algorithm="HS256"
        )
        self.assert_error(
            "roster_expired",
            validate_recipients,
            self.teacher,
            {**confirmed, "roster_token": expired},
        )
        self.assert_error(
            "invalid_roster_token",
            validate_recipients,
            self.teacher,
            {**confirmed, "roster_token": "forged"},
        )


if __name__ == "__main__":
    unittest.main()
