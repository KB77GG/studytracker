# Independent optional scalar-selection review

Worktree `/private/tmp/studytracker-vocabulary-error-pilot-20261117`, baseline `513c732f`; integration agent owns the selector and performance changes. This review did not modify product code or access production. At integration's explicit request it added one focused regression method to `tests/test_vocabulary_policy_performance.py` (listed below). That method detected the equivalence gap before the owner corrected it and now passes unchanged.

## Finding

**A missing word-book relationship loses the old mastery-book fallback.** The previous `_goal_for_dimension()` checks `word.book`, then falls back to `mastery.representative_book` when it is absent. The initial scalar projection always built `ScalarBook(None)` for an outer-join miss, and `_simple_eligible()` passes `mastery=None`. As a result a numeric/non-English `meaning_recall` word with a missing original book but a listening representative book was eligible before and became ineligible.

This is reproducible in a real synthetic SQLite fixture (where historical foreign keys are not necessarily enforced): set the first word's text to `123`, keep its Chinese meaning, set `word.book_id=999999`, leave its mastery representative book intact and mark that book `listening`, commit and expire ORM state. The old iterator returns 22 candidates including that ability; the scalar iterator returns 21 without it. Normal complete book relationships are not affected by this counterexample.

**Resolved locally:** the integration owner added a missing-book-only bulk fallback: project whether the word's book exists; for those rows obtain the mastery representative book goal in one scalar query and use it in the effective immutable cache key. This preserves the complete-book fast path and avoids per-candidate ORM/N+1 queries. Independent reread confirmed the implementation and the unchanged regression passes. Current selector SHA-256: `d403b602057bf66accdc2cbeedab6fa891e3769e27c8dcc9221c25005f6e490d`.

## Fields, ordering and cache audit

- Synonym eligibility uses the word text/ID plus sense `canonical_key`, `lemma`, `part_of_speech`, and `definition_en`; the scalar projection and immutable key include them all. Valid and malformed synonym markers preserve the old decision.
- Meaning/form/audio eligibility uses meaning/translation, word text and accepted variants, numeric classification, and effective book goal. All current direct fields are included; the missing-book fallback above is the one identified omission.
- Non-context eligibility does not inspect examples or usage patterns. Replacing those three fields with `None` before the pure cache is safe for the current predicate. The cache contains a boolean decision keyed by the immutable word/sense/book source values plus dimension; it contains no student, mastery progress, pending work, answer text or request context.
- Context is intentionally not cached in that process-wide LRU. It gets the original example/usage fields, a proxy with `context_use_stage`, and a request-scoped catalog/context-choice cache. The old predicate remains authoritative.
- Dictionary changes to projected source text, accepted variants, meanings, effective book goal or synonym metadata produce a different key. Reuse of IDs across databases does not itself make a stale hit because the full relevant immutable values are also compared. Deploying different predicate code still requires process restart as usual.
- Metadata ordering still comes from the same `due_metadata_pages` query. `seen` is added after eligibility and before checking policy blocking, preserving the legacy rule that a blocked first eligible ability does not let a later ability of that sense jump ahead. Pages do not truncate the scan; later bounded pages only change fetch size. ORM word/mastery hydration is deferred until an eligible unblocked candidate can be returned, while the caller imposes the final optional capacity.
- The LRU maximum is 16,384 decisions. This is a bounded source-data cache, not evidence of constant database work; the optional path may still scan many scalar candidates or load a book catalog. Performance acceptance belongs to the separate multi-user matrix.

## Local evidence before the fallback fix

Independent predicate checks on Python 3.13:

| Matrix | Checks | Result |
| --- | ---: | --- |
| Normal/empty/numeric/Chinese/multiword source text × accepted variants × meaning × reading/listening/default goals × three non-context dimensions | 1,152 | all equal |
| Valid/broken/ordinary synonym keys × POS/left/right source variants × three non-context dimensions | 486 | all equal |
| Context stage/example/usage/meaning combinations, original object vs scalar proxy with identical request catalog | 96 | all equal |
| Missing word book with listening mastery book, numeric meaning item | 1 | old True / scalar False (finding) |

These are predicate/source-key checks, not a full request/latency or concurrent-edit proof. The current formal source-edit and partial-blocking tests were also run directly:

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_vocabulary_policy_performance.PolicyPerformanceTest.test_scalar_optional_eligibility_matches_orm_and_source_edits_invalidate_cache tests.test_vocabulary_policy_performance.PolicyPerformanceTest.test_optional_excludes_fully_blocked_senses_without_changing_partial_selection -q
```

Result: **2 tests passed**, 0.378 seconds.

New independent regression (added to the existing performance test class, owner to format/retain in CI):

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_vocabulary_policy_performance.PolicyPerformanceTest.test_scalar_optional_preserves_missing_book_mastery_goal_fallback -q
```

Before fix: **1 expected failure**, 0.198 seconds, old 22/new 21 candidate signatures. This demonstrates that the test detects the actual missing fallback; it must pass against the final owner patch. No assertion was changed to accept the mismatch.

After fix, this same regression plus `tests.test_vocabulary_pilot_selection` passed: **4 tests**, 0.215 seconds on Python 3.13. The integration owner separately reported the then-current full performance module (12 tests) green; that is owner evidence, not a second independent run here. Subsequent transaction audit adds three separate regressions documented in `final-transaction-selection-review.md`.

Source SHA at this finding snapshot: `825ff0885cd0adac0a0dbe85f8194adcbfcccc8ebacd7a991d12d92013e7675b` for `services/vocabulary_optional_selection.py`. The integration owner is still changing the selector; this hash is not a release freeze or final performance-validation hash.

## Reproduce the minimal predicate counterexample

Run from the worktree using the project Python before/after the owner's correction. The iterator regression above is authoritative after correction because the fix belongs in effective book resolution before `_simple_eligible` is called.

```python
from types import SimpleNamespace
from services import vocabulary_autonomous_review as old
from services import vocabulary_optional_selection as new

word = SimpleNamespace(id=1, book_id=999, sense_id=1, word="123",
    accepted_answers=None, core_meaning_zh="数字", translation=None,
    example_en=None, example_zh=None, usage_pattern=None, book=None, sense=None)
mastery = SimpleNamespace(representative_book=new.ScalarBook("listening"))
scalar = new.ScalarWord(1, 999, 1, "123", None, "数字", None,
    None, None, None, new.ScalarBook(None), None)
assert old._candidate_is_eligible(word, mastery, "meaning_recall", {}, {}) is True
assert new._simple_eligible(scalar, "meaning_recall") is False
```

No commit, push, deployment or production action was performed by this review. Product changes remain with the integration owner; root owns final full-suite/SHA verification and pilot activation.
