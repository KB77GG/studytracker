"""Explicit local session and checkpointed collection of official answers.

Read-only by default. New attempts require an explicit flag and an approved list.
The collector never discovers credentials or retries an uncertain submission.
"""

from __future__ import annotations

import fcntl
import hashlib
import http.client
import json
import math
import os
import re
import stat
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path

from services.exam_sprint import content_digest
from services.ninefen_source import API_BASE, verified_https_handler

MAX_BYTES = 8 * 1024 * 1024
APPROVED_COUNT = 123
PUBLIC_WEEKLY_LIMIT = 140
APPROVAL_SCOPES = {"one_time_blank_submission", "weekly_new_or_changed"}
ID_PATTERN = re.compile(r"[0-9]{1,24}\Z")


class CollectionError(ValueError):
    """A safe, credential-free message suitable for command output."""

    def __init__(self, message, *, http_status: int | None = None):
        super().__init__(message)
        # Preserve only the numeric status, never the HTTPError/response/request.
        self.http_status = (
            http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        )


class ReviewMismatch(CollectionError):
    """A valid existing review contains a different version of this unit."""


class NewAttemptRequired(CollectionError):
    """No reusable answers exist; read-only mode cannot create an attempt."""


class UncertainSubmission(CollectionError):
    """A POST may have reached the source; never automatically send it again."""


def _id(value):
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise CollectionError("Invalid source identity")
    return value


def _private_read(path: Path, limit=MAX_BYTES):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1
            ):
                raise CollectionError("Private file must be owned by this user and have mode 600")
            raw = handle.read(limit + 1)
        if len(raw) > limit:
            raise CollectionError("Private file exceeds size limit")
        return json.loads(raw)
    except CollectionError:
        raise
    except (OSError, ValueError):
        raise CollectionError("Cannot read private JSON file") from None


def _private_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise CollectionError("Private directory must be an owned directory, not a symlink")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise CollectionError("Private directory must have mode 700")


def _private_write(path: Path, payload):
    _private_dir(path.parent)
    if path.exists() or path.is_symlink():
        _private_read(path)
    fd, temporary = tempfile.mkstemp(prefix=".collect-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CollectionError("Official API redirected; collection stopped")


class NinefenSession:
    """Only the explicitly supplied mode-600 JSON file's `token` is used."""

    def __init__(
        self, session_file: str | Path, timeout: float = 20, *, allow_new_attempts: bool = False
    ):
        if isinstance(timeout, bool) or not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise CollectionError("Timeout must be between 0 and 60 seconds")
        payload = _private_read(Path(session_file), limit=16384)
        token = payload.get("token") if isinstance(payload, dict) else None
        if (
            not isinstance(token, str)
            or not token.strip()
            or len(token) > 8192
            or any(ord(char) < 33 or ord(char) > 126 for char in token)
        ):
            raise CollectionError("Session file must contain a valid token string")
        self._token = token
        self.allow_new_attempts = allow_new_attempts is True
        self.timeout = timeout
        self._opener = urllib.request.build_opener(_NoRedirect(), verified_https_handler())

    def __repr__(self):
        return "NinefenSession(token=<redacted>)"

    def _request(self, path: str, payload=None):
        is_post = payload is not None
        if is_post and not self.allow_new_attempts:
            raise NewAttemptRequired("Read-only session: new attempts require explicit permission")
        allowed = (
            path == "/practice/v1/attempts"
            if is_post
            else (
                re.fullmatch(r"/practice/v1/unit-status\?unitIds=[0-9]{1,24}", path)
                or re.fullmatch(r"/practice/v1/results/[0-9]{1,24}/review", path)
            )
        )
        if not allowed:
            raise CollectionError("Request is outside the answer collector API scope")
        request = urllib.request.Request(
            API_BASE + path,
            data=json.dumps(payload).encode("utf-8") if is_post else None,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "token": self._token,
                "User-Agent": "StudyTracker-AnswerCollection/1.0",
            },
            method="POST" if is_post else "GET",
        )
        attempts = 1 if is_post else 3
        for attempt in range(attempts):
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    raw = response.read(MAX_BYTES + 1)
            except urllib.error.HTTPError as exc:
                code = exc.code
                exc.close()
                retryable = code == 429 or 500 <= code <= 599
                if not is_post and retryable and attempt + 1 < attempts:
                    time.sleep(attempt + 1)
                    continue
                error = UncertainSubmission if is_post else CollectionError
                raise error(
                    f"Official API returned HTTP {code}; stopped", http_status=code
                ) from None
            except CollectionError:
                # Redirect refusals and other safety checks are never transient.
                raise
            except (OSError, urllib.error.URLError, http.client.HTTPException):
                if not is_post and attempt + 1 < attempts:
                    time.sleep(attempt + 1)
                    continue
                error = UncertainSubmission if is_post else CollectionError
                raise error("Official API network request failed; stopped") from None
            # Decode/schema checks are deliberately outside the retry branches.
            # A POST is never repeated, even if its response cannot be decoded.
            if len(raw) > MAX_BYTES:
                raise CollectionError("Official API response exceeded size limit")
            try:
                result = json.loads(raw)
            except (ValueError, UnicodeError):
                error = UncertainSubmission if is_post else CollectionError
                raise error("Official API response is invalid; stopped without retry") from None
            if not isinstance(result, dict) or result.get("code") not in (200, "200"):
                raise CollectionError("Official API refused the request")
            if not isinstance(result.get("data"), dict):
                raise CollectionError("Official API response has no object data")
            return result["data"]
        raise CollectionError("Official API request did not complete")

    def existing_result(self, unit_id: str) -> str | None:
        data = self._request("/practice/v1/unit-status?unitIds=" + _id(unit_id))
        rows = data.get("list")
        if (
            not isinstance(rows, list)
            or len(rows) != 1
            or not isinstance(rows[0], dict)
            or rows[0].get("unitId") != unit_id
        ):
            raise CollectionError("Unit status did not identify exactly the requested unit")
        result_id = rows[0].get("resultId")
        if result_id is None or result_id == "":
            return None
        return _id(result_id)

    def review(self, result_id: str) -> dict:
        return self._request(f"/practice/v1/results/{_id(result_id)}/review")

    def submit_blank(self, payload: dict) -> str:
        data = self._request("/practice/v1/attempts", payload)
        try:
            return _id(data.get("resultId"))
        except CollectionError:
            raise UncertainSubmission("Submission returned no usable result identity") from None


def load_approval(path: Path) -> tuple[list[str], str, str]:
    """Read a bounded explicit list; weekly scope still has no wildcard authority."""
    try:
        raw = path.read_bytes()
        if len(raw) > 65536:
            raise ValueError
        payload = json.loads(raw)
        ids = payload["unit_ids"]
        scope = payload.get("scope")
        if (
            payload.get("schema_version") != 1
            or scope not in APPROVAL_SCOPES
            or not isinstance(ids, list)
            or not 1 <= len(ids) <= PUBLIC_WEEKLY_LIMIT
            or len(set(ids)) != len(ids)
            or (scope == "one_time_blank_submission" and len(ids) != APPROVED_COUNT)
        ):
            raise ValueError
        ids = [_id(value) for value in ids]
    except (OSError, ValueError, KeyError, TypeError):
        raise CollectionError(
            "Approval needs a recognized scope and bounded unique unit IDs"
        ) from None
    digest = hashlib.sha256(
        json.dumps({"scope": scope, "unit_ids": sorted(ids)}, sort_keys=True).encode()
    ).hexdigest()
    return ids, digest, scope


def _exam_questions(exam: dict, unit_id: str):
    if not isinstance(exam, dict) or exam.get("code") not in (200, "200"):
        raise CollectionError("Invalid public exam envelope")
    data = exam.get("data")
    if not isinstance(data, dict) or data.get("id") != unit_id:
        raise CollectionError("Public exam identity mismatch")
    if data.get("channel") not in ("reading", "listening"):
        raise CollectionError("Unsupported exam channel")
    charge = data.get("isCharge")
    if not ((type(charge) is int and charge == 0) or (type(charge) is str and charge == "0")):
        raise CollectionError("Exam is outside the public collection scope")
    parts = data.get("parts")
    if not isinstance(parts, list) or not parts:
        raise CollectionError("Public exam has no parts")
    result = {}
    seen_numbers = set()
    for part in parts:
        if not isinstance(part, dict):
            raise CollectionError("Invalid public exam part")
        part_id = _id(part.get("id"))
        groups = part.get("groups")
        if not isinstance(groups, list) or not groups:
            raise CollectionError("Public exam has no groups")
        for group in groups:
            if not isinstance(group, dict):
                raise CollectionError("Invalid public exam group")
            group_id = _id(group.get("id"))
            questions = group.get("questions")
            if not isinstance(questions, list) or not questions or not group.get("type"):
                raise CollectionError("Public exam has incomplete questions")
            for question in questions:
                if not isinstance(question, dict):
                    raise CollectionError("Invalid public exam question")
                question_id = _id(question.get("id"))
                number = question.get("qNumber")
                if not isinstance(number, str) or not re.fullmatch(r"[0-9]{1,3}", number):
                    raise CollectionError("Public exam has an invalid question number")
                if question_id in result or (part_id, number) in seen_numbers:
                    raise CollectionError("Public exam repeats a question identity")
                seen_numbers.add((part_id, number))
                result[question_id] = (part_id, group_id, number)
    return result


def build_blank_submission(exam: dict, unit_id: str, client_submission_id: str) -> dict:
    _exam_questions(exam, unit_id)
    if str(uuid.UUID(client_submission_id)) != client_submission_id:
        raise CollectionError("Invalid submission UUID")
    data = exam["data"]
    return {
        "unitId": unit_id,
        "channel": data["channel"],
        "clientSubmissionId": client_submission_id,
        "annotationSnapshot": {"version": 1, "annotations": []},
        "parts": [
            {
                "id": part["id"],
                "groups": [
                    {
                        "id": group["id"],
                        "type": group["type"],
                        "questions": [
                            {
                                "id": q["id"],
                                "qNumber": q["qNumber"],
                                "userAnswer": "",
                                "bookmarked": False,
                            }
                            for q in group["questions"]
                        ],
                    }
                    for group in part["groups"]
                ],
            }
            for part in data["parts"]
        ],
    }


def _compare_content(source, review, fields):
    """Compare shared source fields without inferring answers or missing text."""
    for name in fields:
        if name not in source:
            continue
        left = source[name]
        if name not in review or (review[name] is None and left is not None):
            if left not in (None, "", [], {}):
                raise CollectionError("Review lacks content needed to verify the current version")
            continue
        right = review[name]
        if name == "articleJson":
            try:
                left = json.loads(left) if isinstance(left, str) else left
                right = json.loads(right) if isinstance(right, str) else right
            except ValueError:
                pass
        if left != right:
            raise ReviewMismatch("Existing review content differs from the current public exam")


def extract_verified_answers(exam: dict, review: dict, unit_id: str) -> dict:
    """Export official answer fields only, with exact unit/part/group/question bindings."""
    expected = _exam_questions(exam, unit_id)
    if (
        not isinstance(review, dict)
        or not isinstance(review.get("result"), dict)
        or review["result"].get("unitId") != unit_id
    ):
        raise CollectionError("Review belongs to a different unit")
    answers = {}
    source_parts = {part["id"]: part for part in exam["data"]["parts"]}
    parts = review.get("parts")
    if not isinstance(parts, list):
        raise CollectionError("Review has no parts")
    for part in parts:
        if not isinstance(part, dict) or not isinstance(part.get("groups"), list):
            raise CollectionError("Invalid review part")
        source_part = source_parts.get(part.get("id"))
        if source_part is None:
            raise ReviewMismatch("Review part differs from current public exam")
        _compare_content(
            source_part,
            part,
            ("article", "articleJson", "audioUrl", "exAudioUrl", "description", "partDescription"),
        )
        source_groups = {group["id"]: group for group in source_part["groups"]}
        for group in part["groups"]:
            if not isinstance(group, dict) or not isinstance(group.get("questions"), list):
                raise CollectionError("Invalid review group")
            source_group = source_groups.get(group.get("id"))
            if source_group is None:
                raise ReviewMismatch("Review group differs from current public exam")
            _compare_content(
                source_group,
                group,
                (
                    "contentHtml",
                    "options",
                    "type",
                    "questionSubtype",
                    "image",
                    "imageUrl",
                    "description",
                    "qRange",
                    "typeDescription",
                    "title1",
                    "title2",
                ),
            )
            source_questions = {q["id"]: q for q in source_group["questions"]}
            for question in group["questions"]:
                if not isinstance(question, dict):
                    raise CollectionError("Invalid review question")
                question_id = question.get("id") or question.get("questionId")
                if (
                    question.get("id")
                    and question.get("questionId")
                    and question["id"] != question["questionId"]
                ):
                    raise CollectionError("Review question identity aliases disagree")
                identity = (part.get("id"), group.get("id"), question.get("qNumber"))
                if question_id in answers:
                    raise CollectionError("Review repeats a question identity")
                if question_id not in expected or identity != expected[question_id]:
                    raise ReviewMismatch("Review question identities do not match the public exam")
                _compare_content(
                    source_questions[question_id],
                    question,
                    ("question", "options", "type", "headingParagraphIndex"),
                )
                answer = question.get("rightAnswer")
                if answer is None:
                    answer = question.get("correctAnswer")
                valid = isinstance(answer, str) and bool(answer.strip())
                valid = valid or (
                    isinstance(answer, list)
                    and bool(answer)
                    and all(isinstance(value, str) and value.strip() for value in answer)
                )
                if not valid:
                    raise CollectionError("Review is missing an official answer")
                answers[question_id] = {
                    "part_id": identity[0],
                    "group_id": identity[1],
                    "question_id": question_id,
                    "q_number": identity[2],
                    "answer": answer,
                }
    if set(answers) != set(expected):
        raise CollectionError("Review does not contain all public exam questions")
    return {
        "unit_id": unit_id,
        "source_content_sha256": content_digest(exam),
        "answers": [answers[question_id] for question_id in expected],
    }


@contextmanager
def collection_lock(directory: Path):
    _private_dir(directory)
    fd = os.open(directory / "collector.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise CollectionError("Collector lock is not a private owned file")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CollectionError("Another collector is already running") from None
        yield
    finally:
        os.close(fd)


class AnswerCollector:
    def __init__(
        self,
        session,
        directory: Path,
        approved_ids: list[str],
        approval_digest: str,
        *,
        scope: str = "one_time_blank_submission",
        allow_new_attempts: bool = False,
    ):
        if scope not in APPROVAL_SCOPES:
            raise CollectionError("Unknown approval scope")
        if (
            not isinstance(approved_ids, list)
            or not 1 <= len(approved_ids) <= PUBLIC_WEEKLY_LIMIT
            or any(not isinstance(value, str) for value in approved_ids)
            or len(set(approved_ids)) != len(approved_ids)
        ):
            raise CollectionError("Collector requires a bounded explicit unit list")
        for value in approved_ids:
            _id(value)
        self.session = session
        self.directory = directory
        self.approved_ids = set(approved_ids)
        self.approval_digest = approval_digest
        self.scope = scope
        self.allow_new_attempts = allow_new_attempts is True
        self.checkpoint_path = directory / "checkpoint.json"
        if self.checkpoint_path.exists():
            self.checkpoint = _private_read(self.checkpoint_path)
            if not isinstance(self.checkpoint, dict) or not isinstance(
                self.checkpoint.get("units"), dict
            ):
                raise CollectionError("Invalid collector checkpoint")
            if self.checkpoint.get("schema_version") == 1:
                # Preserve all previous intents, including uncertain POSTs, during migration.
                migrated = {}
                for unit_id, entry in self.checkpoint["units"].items():
                    _id(unit_id)
                    digest = entry.get("source_content_sha256")
                    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                        raise CollectionError("Invalid legacy checkpoint hash")
                    migrated[unit_id] = {digest: entry}
                self.checkpoint = {"schema_version": 2, "units": migrated}
                self._save()
            if self.checkpoint.get("schema_version") != 2:
                raise CollectionError("Unsupported collector checkpoint version")
        else:
            self.checkpoint = {"schema_version": 2, "units": {}}

    def _save(self):
        _private_write(self.checkpoint_path, self.checkpoint)

    def _finish(self, unit_id, digest, entry, answers):
        _private_dir(self.directory / "answers")
        version_output = self.directory / "answers" / unit_id / f"{digest}.json"
        output = self.directory / "answers" / f"{unit_id}.json"
        _private_write(version_output, answers)
        _private_write(output, answers)
        entry["state"] = "complete"
        self._save()
        return output

    def _cached_answers(self, unit_id, digest, exam):
        version_output = self.directory / "answers" / unit_id / f"{digest}.json"
        # Legacy schema-1 caches had only the canonical unit file.
        output = (
            version_output
            if version_output.exists()
            else self.directory / "answers" / f"{unit_id}.json"
        )
        cached = _private_read(output)
        if (
            not isinstance(cached, dict)
            or cached.get("unit_id") != unit_id
            or cached.get("source_content_sha256") != digest
            or not isinstance(cached.get("answers"), list)
        ):
            raise CollectionError("Completed answer cache identity mismatch")
        # The exact content hash was already verified when this private cache was
        # created. Rebuild its source context and recheck every cached answer binding.
        source_parts = {part["id"]: part for part in exam["data"]["parts"]}
        source_groups = {
            group["id"]: group for part in exam["data"]["parts"] for group in part["groups"]
        }
        source_questions = {
            q["id"]: q for group in source_groups.values() for q in group["questions"]
        }
        by_part = {}
        for row in cached["answers"]:
            if not isinstance(row, dict):
                raise CollectionError("Invalid cached answer")
            group = by_part.setdefault(row.get("part_id"), {}).setdefault(row.get("group_id"), [])
            group.append(
                {
                    **source_questions.get(row.get("question_id"), {}),
                    "id": row.get("question_id"),
                    "qNumber": row.get("q_number"),
                    "rightAnswer": row.get("answer"),
                }
            )
        review = {
            "result": {"unitId": unit_id},
            "parts": [
                {
                    **source_parts.get(part_id, {}),
                    "id": part_id,
                    "groups": [
                        {**source_groups.get(group_id, {}), "id": group_id, "questions": questions}
                        for group_id, questions in groups.items()
                    ],
                }
                for part_id, groups in by_part.items()
            ],
        }
        return extract_verified_answers(exam, review, unit_id)

    def collect(self, unit_id: str, exam: dict) -> Path:
        if unit_id not in self.approved_ids:
            raise CollectionError("Unit is absent from the explicit approval list")
        _exam_questions(exam, unit_id)
        digest = content_digest(exam)
        versions = self.checkpoint["units"].setdefault(unit_id, {})
        if not isinstance(versions, dict):
            raise CollectionError("Invalid unit checkpoint")
        entry = versions.get(digest)
        if entry and entry.get("state") == "complete":
            return self._finish(unit_id, digest, entry, self._cached_answers(unit_id, digest, exam))
        if entry is None:
            if self.scope == "one_time_blank_submission" and versions:
                raise CollectionError("Changed source requires explicit weekly approval scope")
            if any(value.get("state") == "pending" for value in versions.values()):
                raise UncertainSubmission("Another version has an unresolved submission; stopped")
            entry = {
                "source_content_sha256": digest,
                "clientSubmissionId": str(uuid.uuid4()),
                "approval_sha256": self.approval_digest,
                "approval_scope": self.scope,
                "state": "prepared",
            }
            versions[digest] = entry
            self._save()
        if entry.get("state") not in ("prepared", "pending", "submitted"):
            raise CollectionError("Invalid checkpoint state")

        # A completed POST is never repeated, even if its later review fails validation.
        if entry["state"] == "submitted":
            result_id = _id(entry.get("resultId"))
            answers = extract_verified_answers(exam, self.session.review(result_id), unit_id)
            return self._finish(unit_id, digest, entry, answers)

        result_id = self.session.existing_result(unit_id)
        if entry["state"] == "pending":
            if result_id is None or result_id == entry.get("previousResultId"):
                raise UncertainSubmission(
                    "Uncertain prior submission has no new recoverable result; stopped"
                )
            entry.update(resultId=result_id, state="submitted")
            self._save()
            answers = extract_verified_answers(exam, self.session.review(result_id), unit_id)
            return self._finish(unit_id, digest, entry, answers)

        if result_id is not None:
            # A valid existing review is preferred. Auth/transport errors and missing
            # formal answer fields stop here; only a proven different question version
            # is eligible for a new attempt.
            review = self.session.review(result_id)
            try:
                answers = extract_verified_answers(exam, review, unit_id)
            except ReviewMismatch:
                pass
            else:
                entry["resultId"] = result_id
                return self._finish(unit_id, digest, entry, answers)
        if not self.allow_new_attempts:
            raise NewAttemptRequired(
                "No reusable answers; rerun with explicit --allow-new-attempts"
            )
        if any(
            version_hash != digest and value.get("state") == "pending"
            for version_hash, value in versions.items()
        ):
            raise UncertainSubmission("Another version has an unresolved submission; stopped")
        payload = build_blank_submission(exam, unit_id, entry["clientSubmissionId"])
        entry.update(state="pending", previousResultId=result_id, post_attempted=True)
        self._save()  # Durable UUID and intent BEFORE the only POST for this unit/hash.
        try:
            new_result_id = self.session.submit_blank(payload)
        except CollectionError:
            # Read-only reconciliation once. Never retry the POST, even with the same UUID.
            new_result_id = self.session.existing_result(unit_id)
            if new_result_id is None or new_result_id == result_id:
                raise UncertainSubmission(
                    "Submission outcome uncertain; checkpoint retained, no retry"
                ) from None
        if new_result_id == result_id:
            raise UncertainSubmission("Submission did not create a distinguishable result; stopped")
        entry.update(resultId=_id(new_result_id), state="submitted")
        self._save()
        answers = extract_verified_answers(exam, self.session.review(new_result_id), unit_id)
        return self._finish(unit_id, digest, entry, answers)
