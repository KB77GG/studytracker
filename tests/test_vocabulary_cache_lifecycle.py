"""Independent concurrency, metadata lifetime and SQL scope acceptance tests.

Only temporary synthetic in-memory SQLite fixtures are used. No production I/O.
Run with python -m unittest tests.test_vocabulary_cache_lifecycle.
"""

import threading
import unittest
from datetime import datetime
from unittest.mock import Mock

from sqlalchemy import delete, update

from models import DictationWord, StudentVocabularyMastery, db
from services.vocabulary_due_cache import BULK_USERS_OPTION, _cache, _DueCache
from tests import test_vocabulary_due_cache as cache_fixtures


class ConcurrentPublicationTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 17, 4)

    def launch(self, cache, key, entered, release, errors):
        def loader():
            entered.set()
            if not release.wait(3):
                raise TimeoutError("synthetic loader release timed out")
            return [10]

        def run():
            try:
                cache.read(key, self.now, loader, lambda: True)
            except BaseException as error:
                errors.append(error)

        worker = threading.Thread(target=run)
        worker.start()
        self.assertTrue(entered.wait(3))
        self.addCleanup(lambda: worker.join(4))
        self.addCleanup(release.set)
        return worker

    def test_other_user_write_between_start_and_publish_keeps_result(self):
        cache = _DueCache()
        entered, release, errors = threading.Event(), threading.Event(), []
        key = ("db", 1, "day")
        worker = self.launch(cache, key, entered, release, errors)
        cache.invalidate({2})
        release.set()
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        loader = Mock(return_value=[20])
        self.assertEqual(cache.read(key, self.now, loader, lambda: True), frozenset({10}))
        loader.assert_not_called()

    def test_same_user_two_keys_retain_invalidation_until_both_loaders_finish(self):
        # A new local day/database key can overlap with an earlier request.
        # Finishing the first request must not reset the second request's epoch.
        cache = _DueCache()
        entered_a, release_a = threading.Event(), threading.Event()
        entered_b, release_b = threading.Event(), threading.Event()
        errors = []
        key_a, key_b = ("db1", 1, "day1"), ("db2", 1, "day2")
        worker_a = self.launch(cache, key_a, entered_a, release_a, errors)
        worker_b = self.launch(cache, key_b, entered_b, release_b, errors)
        cache.invalidate({1})
        release_a.set()
        worker_a.join(3)
        self.assertFalse(worker_a.is_alive())
        self.assertNotIn(key_a, cache.entries)
        release_b.set()
        worker_b.join(3)
        self.assertFalse(worker_b.is_alive())
        self.assertEqual(errors, [])
        self.assertNotIn(key_b, cache.entries)
        self.assertEqual(cache.user_versions, {})

    def test_global_clear_then_user_epoch_reuse_never_publishes_old_loader(self):
        cache = _DueCache()
        entered, release, errors = threading.Event(), threading.Event(), []
        key = ("db", 1, "day")
        worker = self.launch(cache, key, entered, release, errors)
        cache.invalidate({1})
        cache.invalidate()
        release.set()
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertNotIn(key, cache.entries)
        self.assertEqual(cache.user_versions, {})

    def test_idle_invalidations_do_not_accumulate_per_user_metadata(self):
        cache = _DueCache()
        for user_id in range(10_000):
            cache.invalidate({user_id})
        self.assertEqual(cache.user_versions, {})
        self.assertEqual(cache.inflight, {})


class ScopedTransactionTest(unittest.TestCase):
    setUp = cache_fixtures.VocabularyDueCacheTest.setUp
    tearDown = cache_fixtures.VocabularyDueCacheTest.tearDown
    load = cache_fixtures.VocabularyDueCacheTest.load

    def warm_both(self):
        first, second = Mock(return_value=[1]), Mock(return_value=[2])
        self.load(first)
        self.load(second, self.other)
        return first, second

    def test_scoped_delete_rollback_invalidates_owner_and_preserves_other(self):
        first, second = self.warm_both()
        statement = delete(StudentVocabularyMastery).where(
            StudentVocabularyMastery.student_id == self.user.id
        )
        db.session.execute(statement, execution_options={BULK_USERS_OPTION: (self.user.id,)})
        db.session.rollback()
        self.load(first)
        self.load(second, self.other)
        self.assertEqual(first.call_count, 2)
        self.assertEqual(second.call_count, 1)

    def test_nested_scoped_update_bypasses_cache_until_outer_rollback(self):
        first, second = self.warm_both()
        statement = (
            update(StudentVocabularyMastery)
            .where(StudentVocabularyMastery.student_id == self.user.id)
            .values(meaning_recall_stage=2)
        )
        with db.session.begin_nested():
            db.session.execute(statement, execution_options={BULK_USERS_OPTION: (self.user.id,)})
        self.load(first)
        self.load(first)
        self.assertEqual(first.call_count, 3)
        self.assertTrue(any(key[1] == self.other.id for key in _cache().entries))
        db.session.rollback()
        self.load(first)
        self.load(second, self.other)
        self.assertEqual(first.call_count, 4)
        self.assertEqual(second.call_count, 1)

    def test_catalog_bulk_write_ignores_student_scope_and_invalidates_everyone(self):
        first, second = self.warm_both()
        statement = (
            update(DictationWord)
            .where(DictationWord.id == self.word.id)
            .values(translation="synthetic new definition")
        )
        db.session.execute(statement, execution_options={BULK_USERS_OPTION: (self.user.id,)})
        db.session.commit()
        self.load(first)
        self.load(second, self.other)
        self.assertEqual(first.call_count, 2)
        self.assertEqual(second.call_count, 2)

    def test_empty_scope_is_conservative_global_invalidation(self):
        first, second = self.warm_both()
        statement = update(StudentVocabularyMastery).values(meaning_recall_stage=3)
        db.session.execute(statement, execution_options={BULK_USERS_OPTION: ()})
        db.session.commit()
        self.load(first)
        self.load(second, self.other)
        self.assertEqual(first.call_count, 2)
        self.assertEqual(second.call_count, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
