# Source and frozen-input recheck — 2026-11-12

Review tree: `/private/tmp/studytracker-iwa-holdout-review-20261111`, branch
`codex/iwa-holdout-review-20261111`, clean HEAD **f5c3f51d**, business **45072df9**.
No product changes, private samples, API keys, network or paid requests were used.
Evidence is new under the main materials tree; old reports remain untouched.

**The prior source-manifest P2 and failed-image comparison P3 are fixed in the
reviewed scenarios. No new finding in this assigned scope.**

## Existing probe: expectations preserved, 37 / 37

Ran the author's `verify/source_probe_adapted.py`. Compared its parsed Python AST
with the original `source_probe.py`: only three calls to the former
`_record_batch` helper changed to `check_batch` followed by `record_batch`.
The test inputs, control flow, all 37 check names and all expected values are
unchanged. `source_adaptation.json` records the hashes and exact AST diff.
The original correct-behavior result was 34 / 37; this revision is **37 / 37**.

This closes the previous counterexamples:

- Same-ID essay changes during a partial resume are rejected before any new
  model request; completed runs no longer silently serve stale reports.
- Unreadable visual responses preserve their diagnostic description in frozen
  repeats and the other model's run. The actual input and exported input now
  agree, so the standalone comparison succeeds.
- Successful/failed vision freezing, one image call per essay, images-only
  failure cutoff, separate text/image caps, teacher-label isolation, exact
  repeated/model messages and inherited-IWA isolation remain passing.

## Independent additional cases: 30 / 30

`source_manifest_probe.py` uses synthetic essays, fake PNG bytes and fake clients.
The batch, CLI, ledger, output and comparison code are real; the child transport
is replaced in-process. It intentionally does not test process lifetime, which
the runner review handles independently.

After the image step and Flash finish, with Pro interrupted before dispatch:

| Changed input | Observed result |
|---|---|
| Prompt or essay | Exit 2, no launched child, no dispatch, ledger unchanged |
| Single teacher score or separate rater score | Same |
| Teacher annotation text or its valid source quote | Same |
| Target band or group label | Same |
| Image bytes at the same path | Same |
| Frozen image description | Exit 2, no dispatch, ledger unchanged |
| Missing or incorrect completed-run input stamp | Exit 2, no dispatch, ledger unchanged |

For all eight JSONL mutations, rejection also leaves the pinned batch manifest
unchanged. Thus rejected data is not silently adopted as the new baseline.
Moving the same image bytes to a different path keeps the manifest identical;
resumption finishes only Pro's two evaluations. A subsequent unchanged resume
adds zero requests.

Optional-group behavior is consistent with existing-input immutability:

- With the official group absent, only the synthetic teacher group runs.
- Adding official data while also changing the prior teacher data is rejected
  before any new request.
- Adding official data with the prior data unchanged runs only that new group
  (four fake calls, two repeats per model), and pins it.
- Once pinned, changing or removing official data is refused with no new call.
  Restoring its exact content permits a zero-call resume.

These optional-group tests use two small groups and an explicit cap of 16;
they do not purport to be the full private package rehearsal.

## Commands and evidence

Run from the review tree:

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python \
  docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/source_probe_adapted.py \
  --repo /private/tmp/studytracker-iwa-holdout-review-20261111 \
  --output /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-recheck-20261112/source_adapted.json
```

Run from `/Users/zhouxin/Desktop/studytracker`:

```sh
.venv/bin/python docs/design/iwa-batch-recheck-20261112/source_manifest_probe.py \
  --repo /private/tmp/studytracker-iwa-holdout-review-20261111 \
  --output docs/design/iwa-batch-recheck-20261112/source_manifest.json
```

Both exit 0. The adapted probe's two `ledger_cap` warnings are its intentional
refusal checks. Assertions use desired behavior, not “defect reproduced” as a
success condition.

Prepared but did not execute the ignored wrapper
`tmp/iwa-batch-recheck-20261112/dry_run.py` (syntax checked; `.gitignore:22`).
It retains the preceding wrapper's full fake-model, absent-env, proxy/IWA
removal, child network guard, refusal-to-overwrite and metadata-only export
protections. Only its default output paths changed to
`~/iwa-compare-dry-20261112-review/` and this review's `dryrun_metadata.json`.
The parent reviewer will approve and run it separately; this report does not
claim the private-data rehearsal has been executed.

All new `source_*` evidence remains local until the parent consolidates delivery.
No commit/push/deploy or handoff edits were made by this reviewer.
