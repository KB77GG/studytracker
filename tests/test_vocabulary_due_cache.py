"""Display-count freshness, transaction isolation and bounded cache behavior."""

import threading
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from flask import Flask
from sqlalchemy import update

from models import DictationBook, DictationWord, User, db
from services.vocabulary_due_cache import (
    _cache,
    _DueCache,
    cached_due_sense_ids,
)
from services.vocabulary_mastery import ensure_mastery, ensure_word_sense


class VocabularyDueCacheTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.user = User(username="cache-student", password_hash="test", role="student")
        self.other = User(username="cache-other", password_hash="test", role="student")
        db.session.add_all([self.user, self.other])
        db.session.flush()
        book = DictationBook(title="cache-test", created_by=self.user.id)
        db.session.add(book)
        db.session.flush()
        self.word = DictationWord(book_id=book.id, sequence=1, word="cache", translation="缓存")
        db.session.add(self.word)
        db.session.flush()
        sense = ensure_word_sense(self.word)
        self.mastery = ensure_mastery(self.user, self.word, sense)
        db.session.commit()
        self.now = datetime(2026, 11, 17, 4, 0)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def load(self, loader, user=None, now=None):
        return cached_due_sense_ids(user or self.user, now or self.now, loader)

    def test_warm_count_is_exact_not_capped_and_user_isolated(self):
        loader = Mock(return_value=range(2400))
        self.assertEqual(len(self.load(loader)), 2400)
        self.assertEqual(len(self.load(loader)), 2400)
        self.assertEqual(loader.call_count, 1)
        other_loader = Mock(return_value=[9999])
        self.assertEqual(self.load(other_loader, self.other), frozenset({9999}))
        self.assertEqual(other_loader.call_count, 1)

    def test_ttl_expiry_and_clock_rewind_reload(self):
        loader = Mock(side_effect=[[1], [2], [3]])
        self.assertEqual(self.load(loader), frozenset({1}))
        self.assertEqual(self.load(loader, now=self.now + timedelta(seconds=30)), frozenset({2}))
        self.assertEqual(self.load(loader, now=self.now), frozenset({3}))

    def test_monotonic_expiry_even_if_supplied_time_does_not_move(self):
        loader = Mock(side_effect=[[1], [2]])
        with patch("services.vocabulary_due_cache.monotonic", return_value=100):
            self.load(loader)
        with patch("services.vocabulary_due_cache.monotonic", return_value=131):
            self.assertEqual(self.load(loader), frozenset({2}))

    def test_beijing_day_boundary_never_reuses_cooldown_snapshot(self):
        loader = Mock(side_effect=[[1], [1, 2]])
        before_midnight = datetime(2026, 11, 17, 15, 59, 59)
        self.load(loader, now=before_midnight)
        self.assertEqual(
            self.load(loader, now=before_midnight + timedelta(seconds=2)),
            frozenset({1, 2}),
        )

    def test_dirty_and_flushed_transactions_bypass_without_publishing(self):
        loader = Mock(side_effect=[[1], [2], [3], [4]])
        self.load(loader)
        self.mastery.meaning_recall_stage = 1
        self.assertEqual(self.load(loader), frozenset({2}))
        db.session.flush()
        self.assertEqual(self.load(loader), frozenset({3}))
        db.session.commit()
        self.assertEqual(self.load(loader), frozenset({4}))
        self.assertEqual(loader.call_count, 4)

    def test_rollback_does_not_publish_speculative_count(self):
        loader = Mock(side_effect=[[1], [], [1]])
        self.load(loader)
        self.mastery.meaning_recall_stage = 2
        db.session.flush()
        self.assertEqual(self.load(loader), frozenset())
        db.session.rollback()
        self.assertEqual(self.load(loader), frozenset({1}))
        self.assertEqual(loader.call_count, 3)

    def test_writing_one_student_keeps_other_students_warm(self):
        loader = Mock(return_value=[1])
        other_loader = Mock(return_value=[2])
        self.load(loader)
        self.load(other_loader, self.other)
        self.mastery.meaning_recall_stage = 1
        db.session.commit()
        self.load(other_loader, self.other)
        self.load(loader)
        self.assertEqual(other_loader.call_count, 1)
        self.assertEqual(loader.call_count, 2)

    def test_catalog_changes_and_bulk_changes_invalidate(self):
        loader = Mock(return_value=[1])
        self.load(loader)
        self.word.translation = "新释义"
        db.session.commit()
        self.load(loader)
        db.session.execute(
            update(DictationWord).where(DictationWord.id == self.word.id).values(word="cached")
        )
        db.session.commit()
        self.load(loader)
        self.assertEqual(loader.call_count, 3)

    def test_nested_commit_cannot_publish_before_outer_transaction_finishes(self):
        loader = Mock(return_value=[1])
        self.load(loader)
        with db.session.begin_nested():
            self.mastery.meaning_recall_stage = 1
            db.session.flush()
        self.load(loader)
        self.load(loader)
        self.assertEqual(loader.call_count, 3)
        db.session.rollback()
        self.load(loader)
        self.assertEqual(loader.call_count, 4)

    def test_failed_loader_is_retried_without_caching_failure(self):
        loader = Mock(side_effect=[RuntimeError("synthetic"), [1]])
        with self.assertRaises(RuntimeError):
            self.load(loader)
        self.assertEqual(self.load(loader), frozenset({1}))

    def test_cache_is_application_scoped(self):
        first = _cache()
        with Flask("other-cache-app").app_context():
            self.assertIsNot(_cache(), first)

    def test_total_memory_is_bounded_by_sense_budget(self):
        cache = _DueCache()
        with patch("services.vocabulary_due_cache.MAX_TOTAL_SENSES", 5):
            cache.read(("db", 1, "day"), self.now, lambda: [1, 2, 3], lambda: True)
            cache.read(("db", 2, "day"), self.now, lambda: [4, 5, 6], lambda: True)
            self.assertEqual(cache.total_senses, 3)
            self.assertEqual(len(cache.entries), 1)
            cache.read(("db", 3, "day"), self.now, lambda: range(6), lambda: True)
            self.assertEqual(cache.total_senses, 3)
            self.assertEqual(len(cache.entries), 1)

    def test_same_student_cold_reads_coalesce(self):
        cache = _DueCache()
        entered = threading.Event()
        release = threading.Event()
        calls = []
        results = []

        def loader():
            calls.append(1)
            entered.set()
            self.assertTrue(release.wait(2))
            return [1, 2]

        def run():
            results.append(cache.read(("db", 1, "day"), self.now, loader, lambda: True))

        first = threading.Thread(target=run)
        second = threading.Thread(target=run)
        first.start()
        self.assertTrue(entered.wait(2))
        second.start()
        release.set()
        first.join(3)
        second.join(3)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertEqual(len(calls), 1)
        self.assertEqual(results, [frozenset({1, 2}), frozenset({1, 2})])

    def test_write_during_load_prevents_stale_snapshot_publication(self):
        cache = _DueCache()

        def loader():
            cache.invalidate({1})
            return [1]

        cache.read(("db", 1, "day"), self.now, loader, lambda: True)
        self.assertFalse(cache.entries)


if __name__ == "__main__":
    unittest.main()
