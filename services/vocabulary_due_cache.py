"""Short-lived, process-local snapshots for displayed vocabulary debt counts.

Snapshots contain only sense IDs, never ORM objects, questions or credentials.
They are deliberately NOT an authority for gating or selecting review items.
The cold exact count still scans the eligible backlog. Warm reads reuse that
count for at most 30 seconds; local vocabulary writes invalidate it, and
external-process/catalog writes are bounded by the same TTL.
"""

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Event, RLock
from time import monotonic

from flask import current_app, has_app_context
from sqlalchemy import event
from sqlalchemy.orm import Session

from models import db
from services.dictation_review import local_date
from services.vocabulary_mastery import utc_naive

TTL_SECONDS = 30
MAX_ENTRIES = 128
MAX_TOTAL_SENSES = 100_000
_EXTENSION_KEY = "vocabulary_due_display_cache"
_TRANSACTION_KEY = "vocabulary_due_display_writes"
_STUDENT_TABLES = {
    "student_vocabulary_mastery",
    "vocabulary_review_item",
    "vocabulary_review_attempt",
}
_CATALOG_TABLES = {"dictation_word", "dictation_book", "vocabulary_sense"}


@dataclass(frozen=True)
class _Snapshot:
    senses: frozenset[int]
    observed_at: datetime
    expires_at: float


class _DueCache:
    def __init__(self):
        self.lock = RLock()
        self.entries = OrderedDict()
        self.inflight = {}
        self.version = 0
        self.total_senses = 0

    def _remove(self, key):
        entry = self.entries.pop(key, None)
        if entry is not None:
            self.total_senses -= len(entry.senses)

    def invalidate(self, users=None):
        with self.lock:
            self.version += 1
            for key in list(self.entries):
                if users is None or key[1] in users:
                    self._remove(key)

    def read(self, key, now, loader, publish_allowed):
        while True:
            with self.lock:
                clock = monotonic()
                entry = self.entries.get(key)
                if entry is not None:
                    if (
                        clock < entry.expires_at
                        and entry.observed_at <= now
                        and now < entry.observed_at + timedelta(seconds=TTL_SECONDS)
                    ):
                        self.entries.move_to_end(key)
                        return entry.senses
                    self._remove(key)
                pending = self.inflight.get(key)
                if pending is None:
                    pending = Event()
                    self.inflight[key] = pending
                    version = self.version
                    break
            # Coalesce simultaneous cold counts for one student. Other
            # students never wait for this loader or share its result.
            pending.wait()
        try:
            senses = frozenset(int(sense_id) for sense_id in loader())
            with self.lock:
                if (
                    self.version == version
                    and publish_allowed()
                    and len(senses) <= MAX_TOTAL_SENSES
                ):
                    clock = monotonic()
                    for old_key, old_entry in list(self.entries.items()):
                        if old_entry.expires_at <= clock:
                            self._remove(old_key)
                    self.entries[key] = _Snapshot(senses, now, clock + TTL_SECONDS)
                    self.total_senses += len(senses)
                    while len(self.entries) > MAX_ENTRIES or self.total_senses > MAX_TOTAL_SENSES:
                        self._remove(next(iter(self.entries)))
            return senses
        finally:
            with self.lock:
                self.inflight.pop(key, None)
                pending.set()


def _cache():
    # setdefault publishes one instance even when two first requests race.
    return current_app.extensions.setdefault(_EXTENSION_KEY, _DueCache())


def _pending_vocabulary_changes(session):
    if session.info.get(_TRANSACTION_KEY):
        return True
    return any(
        getattr(type(row), "__tablename__", None) in _STUDENT_TABLES | _CATALOG_TABLES
        for row in (*session.new, *session.dirty, *session.deleted)
    )


def cached_due_sense_ids(user, now, loader):
    """Get a numeric-display snapshot, bypassing uncommitted transactions.

    ``loader`` is a zero-argument callable returning eligible sense IDs for
    this user at ``now``. Its result must never decide access or queue order.
    """
    now = utc_naive(now)
    session = db.session()
    if _pending_vocabulary_changes(session):
        return frozenset(int(sense_id) for sense_id in loader())
    key = (db.engine, int(user.id), local_date(now))
    return _cache().read(
        key,
        now,
        loader,
        lambda: not _pending_vocabulary_changes(session),
    )


def _mark_writes(session, users=None):
    if not has_app_context():
        return
    cache = _cache()
    state = session.info.setdefault(
        _TRANSACTION_KEY, {"cache": cache, "users": set(), "all": False}
    )
    if users is None:
        state["all"] = True
    else:
        state["users"].update(users)
    cache.invalidate(None if state["all"] else state["users"])


@event.listens_for(Session, "before_flush")
def _invalidate_flushed_vocabulary(session, _flush_context, _instances):
    users = set()
    all_users = False
    for row in (*session.new, *session.dirty, *session.deleted):
        table = getattr(type(row), "__tablename__", None)
        if table in _CATALOG_TABLES:
            all_users = True
        elif table in _STUDENT_TABLES:
            # A committed instance can have expired attributes; before_flush
            # permits loading its owner without flushing the pending change.
            user_id = getattr(row, "student_id", None)
            if user_id is None:
                all_users = True
            else:
                users.add(int(user_id))
    if all_users or users:
        _mark_writes(session, None if all_users else users)


@event.listens_for(Session, "do_orm_execute")
def _invalidate_bulk_vocabulary(execute_state):
    if not (execute_state.is_update or execute_state.is_delete or execute_state.is_insert):
        return
    table = getattr(getattr(execute_state.statement, "table", None), "name", None)
    if table in _STUDENT_TABLES | _CATALOG_TABLES:
        # A bulk statement need not contain loaded per-student instances.
        # Conservatively invalidate the display cache, never rewrite its SQL.
        _mark_writes(execute_state.session)


@event.listens_for(Session, "after_transaction_end")
def _invalidate_finished_vocabulary(session, transaction):
    if transaction.parent is not None:
        return
    state = session.info.pop(_TRANSACTION_KEY, None)
    if state:
        # Invalidate again after commit OR rollback: another reader may have
        # cached the pre-commit database while the writer was in flight.
        state["cache"].invalidate(None if state["all"] else state["users"])
