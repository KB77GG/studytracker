# Metrics and blind-review recheck — 2026-11-11

Target: `/private/tmp/studytracker-iwa-holdout-review-20261111`, branch `codex/iwa-holdout-review-20261111`, HEAD `d84c412a8513a049d4b3dfc6e6f29a170f741236` (business change `50d557fd`). Product tree remained clean. This audit read no private samples or keys and made no network/model calls. Only the new `metrics_*` review artifacts in the main tree were written; no commit, push or deployment was performed. The parent task maintains the canonical handoff.

The supplied six regression checks pass. The independent probe passes fifteen positive contracts but records **two further blind-review counting findings**; its exit 0 means those fifteen contracts passed, not that the findings below are cleared. A focused follow-up using the real group-resume path confirms a third P2: completed manual review is overwritten on resume.

## P2 — An absent part of the blind sheet can be reported as complete

`tools/ielts_writing_ai/blindtally.py:64` only iterates rows present in the edited Markdown. At line 104, `complete = not problems` is therefore true when expected material never appears. No comparison is made with the samples/sides in the key or an expected row manifest.

Independent synthetic reproduction:

- Empty sheet + a key declaring one sample with both sides: `complete=true`, both models have `filled=0`.
- Generate and fill the full sheet, then truncate it before `### 乙`: `complete=true`; one model has no judgments at all.
- Replace a required `其他漏报` count with `参考`: `complete=true`; line 81 skips it before checking the required count-row type.

An accidentally truncated or partially copied review can consequently be exported as finished, with omitted errors represented as zero. Require the expected sample/side/row identities and both omission count rows; only generator-designated context rows should accept `参考`. A missing row is different from a deliberately excluded repeat. Blank rows that remain in place and non-integer counts already work correctly.

## P2 — A reclassified improvement has two independently counted copies of the same advice

`tools/ielts_writing_ai/realcheck_compare.py:210` includes every improvement in `optional`. Line 234 also includes improvements carrying `from_type` in `reclassified`. `feedback_rows` emits both as `JUDGED` at lines 720 and 731, repeating the same quote and suggestion.

Minimal synthetic case: each model produces one identical optional suggestion. Model A's item has `from_type` and verified support because the program reclassified it; Model B supplies it directly as an improvement. The blind sheet contains the advice twice for A, once for B. Marking that identical advice `②` wherever shown yields `changed_meaning: A=2, B=1`, despite one source advice item on each side.

The reclassification status and supporting quote need to remain visible, but should be merged into the improvement's single judged row, or displayed as non-counted context without repeating a separately judged suggestion. Otherwise error counts depend on the program's reclassification path as well as model output quality.

## P2 — Resuming an already-completed group erases filled blind judgments

`tools/ielts_writing_ai/batch.py:308` calls the two model runs, which correctly skip directories carrying `.done`, but still unconditionally calls `realcheck_compare.write` at line 337. `tools/ielts_writing_ai/realcheck_compare.py:836` writes a newly blank `blind_review.md`; line 838 rewrites its key. The old `blind_tally.json` is left behind.

`metrics_resume.py` exercises the actual `Batch.run_group`, `compare`, `write` and `blindtally.run` with two wholly synthetic completed report directories. The model subprocess is guarded to fail if invoked and is never called:

1. Run the completed group once to create its sheet; fill every judgment, both count rows and a synthetic reviewer note. The tally correctly reports `complete=true`.
2. Run the same completed group with the same seed again. Both model directories are skipped, but the filled sheet is overwritten by an empty one. All reviewer notes and decisions disappear.
3. Recalculating the new sheet yields `complete=false`, while the saved `blind_tally.json` is byte-for-byte unchanged and still says `complete=true`. The key's bytes remain unchanged with this identical seed, although the file is rewritten.

This is actual loss of manual review on the documented resume path, not merely regenerating an as-yet-empty template. Preserve existing review artifacts when their underlying comparison is unchanged. If inputs change, create a new version or require an explicit regeneration action; do not silently combine a new blank sheet with a stale completed tally.

## Confirmed fixes and boundaries

- Human disagreement and AI deviation use the same scored essays; all-failed data leaves conditional gaps null. Two-model comparison uses the common successfully scored IDs.
- Ranking spread is null when either planned endpoint is missing. A failed repeat remains in the missing count; an available repeat at each endpoint may still provide the displayed spread.
- Ledger totals include failed and unknown requests across attempts. Unknown cost is marked as a lower bound, and unfinished runs do not contribute final quality.
- Teacher score exports use the numeric field whitelist; attached comments, sample details in repeat statistics, and ranking row identifiers are removed in the synthetic privacy checks.
- The blind sheet now includes the contradiction partner, support quote, position verdict, program qualifiers, paragraph number and count corrections. Model condition names are not displayed; the separate key retains the mapping.
- Blank judgment cells and decimal, signed, ranged or textual omission counts are rejected. Unfilled later repeats are allowed only under the default first-repeat policy; `all_repeats=True` makes them incomplete.
- These checks validate computation and export behavior, not model accuracy or the authenticity of external calibration data. Persistent-ledger concurrency and runner authorization limits belong to the separate runner audit.

## Reproduction

Run from the target tree with the shared interpreter:

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/metrics_blind_probe_fixed.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-recheck-20261111/metrics_supplied.json
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-recheck-20261111/metrics_independent.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-recheck-20261111/metrics_independent.json
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-recheck-20261111/metrics_resume.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-recheck-20261111/metrics_resume.json
```

All commands exited 0: supplied 6/6 and independent 15/15 positive checks; the follow-up records the observed resume overwrite without treating the defect as a passing contract. The independent JSON's `findings` object preserves the first two counterexamples and resulting counts; `metrics_resume.json` preserves the lost-review and stale-tally evidence. Prior review artifacts and supplied probes were not changed.
