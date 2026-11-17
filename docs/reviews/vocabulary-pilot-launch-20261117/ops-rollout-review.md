# One-time activation wrapper review

Reviewed root's `activate_and_restart.py` for the first four-person pilot after migration and OFF readback. No real service commands, SSH, production files or databases were touched by this review. All subprocess calls in tests are mocks; `.env` files are temporary synthetic fixtures.

Two concrete issues were corrected before freezing: a stop command outside `try/finally` could leave the service stopped after a partial stop/timeout; checking HEAD without tracked working-tree status could stop the service against changed source. Stop is now inside the guaranteed-start region, and both expected HEAD and tracked source cleanliness are checked before any stop or private backup write.

Additional safeguards preserve the original `.env` non-target bytes, mode and owner through atomic replacement, reject a symlink backup or an unexpected existing backup, redact top-level exception text, and bound subprocess calls. An enrollment failure leaves the original flag unchanged and still attempts service start. If enrollment/flag change succeeds but start fails, the result explicitly says `ok=false`, `service_start_command_succeeded=false`, and accurately retains `feature_flag_written=true`; it does not pretend to have rolled back the successfully committed enrollment or flag. Root must then perform the documented recovery/readback rather than treat the failed run as an untouched OFF state.

Validation from `/private/tmp/studytracker-vocabulary-error-pilot-20261117`:

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest discover \
  -s docs/reviews/vocabulary-pilot-launch-20261117 -p test_activate_and_restart.py -q
/private/tmp/studytracker-stage2-py310/bin/python -m unittest discover \
  -s docs/reviews/vocabulary-pilot-launch-20261117 -p test_activate_and_restart.py -q
```

**6 tests passed on each runtime**, each 0.005s. They cover failed enrollment, exact non-target bytes including CRLF/UTF-8/no final newline, permissions/owner/private backup, wrong HEAD and dirty tracked source, partial-stop timeout recovery, start error/timeout, write failure and sanitized top-level failure. Black, targeted Ruff and `git diff --check` passed. The ops script and tests were frozen and handed to root before manifest generation; this review performed no commit/push/deployment. Root owns canonical handoff and actual rollout.
