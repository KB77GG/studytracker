# Source / shared-image recheck, 2026-11-11

Reviewed `/private/tmp/studytracker-iwa-holdout-review-20261111`, branch
`codex/iwa-holdout-review-20261111`, HEAD `d84c412a` (business `50d557fd`).
The review tree remained clean. Evidence is in the main materials tree only;
this reviewer changed no product code, branch, configuration, or deployment.

All inputs are newly generated synthetic prose and fake image bytes. A Python
audit hook denies network connections and DNS. No API key, private dataset or
paid request was used. The batch test runs its real batch/CLI/ledger/report paths
with the child process transport replaced by an in-process fake client. It does
not claim to test process lifetime; the runner reviewer covers that separately.

## P2: Resume does not pin the source dataset before spending further calls

`batch.py:341` records code, prompt, models, mode and prices, but no source-data
fingerprint. `batch.py:133` / `244` trusts `.done` by existence alone; `plan()`
reloads the current source files. This is reproducible with an ordinary source
correction between an interruption and a resume:

1. One synthetic Task 1 chart, two repeats per model. Images and Flash finish;
   Pro is interrupted before dispatch. The ledger has 1 image + 2 text calls.
2. Add one sentence to that same sample in its JSONL, keeping its ID and path.
3. Resume the same stage and output directory.
4. The stage sends 2 Pro evaluations, then exits 6 because comparison detects
   changed source/message fingerprints. The expected behavior is rejection
   before those evaluations (exit 2, zero further calls).

An already completed stage is worse for visibility: after the same source edit,
resume returns 0 without dispatching anything and reuses its old reports.
The record therefore says “complete” for data no longer matching the supplied
source. Changing `--data` to another same-sized dataset has the same underlying
missing guard; this probe demonstrates an edit at the same path.

Recommended repair: record a canonical per-group sample manifest (including
sample IDs, all evaluation input fields, reference metadata used for scoring,
and image-content hashes) before the first request. Compare it before trusting
any `.done` or launching any child. Require a new output directory for changed
data. Pin the actual frozen image-result artifact too. Never silently replace
old completed outputs.

Evidence: `source_probe.json`, checks
`completed_resume_refuses_changed_source` and
`partial_resume_refuses_changed_source_before_calls`. This does not exceed the
existing numeric cap: the issue is incompatible/stale inputs and wasted calls.

## P3: Standalone failed-image reuse falsely rejects a valid comparison

This is outside the new batch success path, which correctly stops on unusable
images. In standalone `realcheck`, an unreadable, non-JSON visual response saves
the diagnostic description on the first sample. `_run_sample()` at
`realcheck.py:520–526` drops that description to `None` for frozen failures.
Repeats and the second model see the same failed status and exactly the same
evaluation messages, but `realcheck_compare.INPUT_FIELDS` includes the exported
description, so comparison rejects the first sample as different.

Observed descriptions: first = “识图模型原始输出：The uploaded image is unreadable.”;
repeat/Pro = `null`. Actual evaluation-message hashes are equal. Preserve the
same frozen description, or canonicalize unavailable image inputs identically
at creation/export/comparison. No extra vision calls occur and no false TA score
is produced; this is a reporting/comparison failure, not the original image bug.

## Confirmed fixes and unchanged protections

- The old unreadable-then-readable scenario makes exactly 1 vision request;
  both repeats remain `failed`, and the second model reuses that failure.
- Batch images-only failure exits 5 before either text model starts. The ledger
  records vision 1 / text 0, no `.done` exists, and version-2 outcomes include the
  failure. Resuming refuses before dispatch (exit 2), keeping the image cap.
- Successful batch: exactly 1 image + 4 text requests for one essay, two repeats
  and two models; unchanged resume adds zero calls. Successful chart readings
  are shared exactly and compare successfully.
- Text cap 1 blocks the second actual dispatch; vision cap 0 blocks even the
  first image dispatch. Ledger categories remain separate from `max_calls`.
- Repeats and both models receive byte-equivalent serialized messages;
  teacher scores/comments/findings, rater names and group/condition labels do
  not enter the messages or fake-client context. References remain in the local
  review data.
- Both models use high / 32000 / 300 seconds, JSON mode and transport retries 0.
  Poisoned inherited `IWA_*` values do not affect child configuration. Paid-path
  configuration forces the official endpoint and expected Pro model, tested
  without constructing a paid client or sending a request.
- Explicit cap changes are recorded as history; a changed price condition is
  rejected. The missing dataset pin is distinct from these working guards.

## Reproduce

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python \
  docs/design/iwa-batch-recheck-20261111/source_probe.py \
  --repo /private/tmp/studytracker-iwa-holdout-review-20261111 \
  --output docs/design/iwa-batch-recheck-20261111/source_probe.json
```

Run from `/Users/zhouxin/Desktop/studytracker`. Result: **34 / 37** correct-behavior
checks, exit 1: two assertions cover the P2 above, one covers the P3. The
`ledger_cap` warnings are the two intentional cap-refusal tests. No tests are
counted as passing merely because they reproduce a defect.

Project handoff updates are consolidated by the parent reviewer. These three
`source_*` artifacts are new local evidence, not committed/pushed/deployed by
this reviewer; previous review artifacts are unchanged.
