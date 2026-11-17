"""Mutate methods in memory to prove the independent tests detect regressions."""

import importlib.util
import inspect
import io
import json
import textwrap
import unittest
from pathlib import Path

from services import vocabulary_due_cache as product


def run_negative(name, target, method_name, old, new):
    spec = importlib.util.spec_from_file_location(
        "independent_cache_checks",
        Path(__file__).resolve().parents[4] / "tests/test_vocabulary_cache_lifecycle.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = textwrap.dedent(inspect.getsource(getattr(product._DueCache, method_name)))
    if old not in source:
        raise AssertionError("Expected mutation anchor absent")
    namespace = dict(vars(product))
    exec(compile(source.replace(old, new, 1), "<memory-only negative control>", "exec"), namespace)
    broken = type("BrokenCache", (product._DueCache,), {method_name: namespace[method_name]})
    module._DueCache = broken
    suite = unittest.TestSuite([module.ConcurrentPublicationTest(target)])
    result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
    outcome = {
        "negative_control": name,
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "regression_detected": len(result.failures) == 1 and not result.errors,
    }
    if not outcome["regression_detected"]:
        raise AssertionError(outcome)
    return outcome


if __name__ == "__main__":
    outcomes = [
        run_negative(
            "remove_user_epoch_while_another_loader_is_pending",
            "test_same_user_two_keys_retain_invalidation_until_both_loaders_finish",
            "read",
            "if not any(other_key[1] == key[1] for other_key in self.inflight):",
            "if True:",
        ),
        run_negative(
            "ignore_global_epoch_after_catalog_invalidation",
            "test_global_clear_then_user_epoch_reuse_never_publishes_old_loader",
            "_version",
            "return self.global_version, self.user_versions.get(key[1], 0)",
            "return 0, self.user_versions.get(key[1], 0)",
        ),
        run_negative(
            "retain_epoch_for_every_past_writer",
            "test_idle_invalidations_do_not_accumulate_per_user_metadata",
            "invalidate",
            "for user_id in set(users) & inflight_users:",
            "for user_id in users:",
        ),
    ]
    print(json.dumps(outcomes, indent=2))
