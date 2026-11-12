# Final limited blind-binding recheck — 2026-11-12

**PASS: the remaining measurement-integrity P2 can be closed.** The original seventeen correct-behavior assertions pass without modifying their source or expectations. No additional defect was found in the requested binding, editable-column, resume-preservation and freshness scope.

Target: `/private/tmp/studytracker-iwa-holdout-review-20261111`, branch `codex/iwa-holdout-review-20261111`, HEAD `c0d87c91` (business `fb733279`). Product code and earlier reports were not edited. All inputs were synthetic; no keys, private essays, network or model calls were used. The root task handles the full suite, authorization, handoff and any publishing.

## Confirmed behavior

- **Original `metrics_consistency.py`: 17/17, exit 0, unchanged source.** A separately generated key with another seed is rejected; recalculating that mismatched pair does not make it complete/current. Changing the valid count label to the other valid count label is rejected rather than moving the count. The prior fourteen controls, including staleness and explicit overwrite refusal, remain green.
- **New independent edit contract: 13/13, exit 0.** Each fixed column—ID, position, quote, explanation and suggestion—was changed separately and rejected. Valid judgments and remarks are accepted; one changed judgment counts once; remarks do not change totals. Editing either judgment or remark makes the old tally stale, and recalculating a valid edited sheet restores complete/current status.
- **Actual group resume:** both completed synthetic model runs are skipped, with zero subprocess calls. The filled sheet, reviewer notes, key and saved tally remain unchanged; recalculated results stay complete.
- **Earlier metric regressions remain green:** adapted independent probe **18/18**, baseline probe **6/6**.

The implementation stays within the requested fix: a shared sheet identifier binds the generated row manifest and A/B mapping; fixed-column fingerprints distinguish immutable template content from editable verdicts and remarks; count categories come from the manifest. Existing no-overwrite and post-edit staleness behavior is preserved. This closes a measurement-integrity issue, not a change to request-budget policy or model grading quality.

## Verify adaptation audit

Reviewed the changes to both modified verify files against `f5c3f51d`:

- `metrics_blind_probe_fixed.py` adds a sheet ID, fixed-column fingerprint and category to its handcrafted minimal count row. Its accepted integer and rejected blank/decimal/range/negative cases are unchanged.
- `metrics_independent_adapted.py` adds fingerprints and one matching sheet ID to the handcrafted repeat section, removing the duplicate header identifier. Its first-repeat versus all-repeats requirements, all original cases and eighteen assertions are unchanged.

These changes construct valid examples under the new binding contract; they do not weaken rejection expectations. The prior `metrics_consistency.py` required no adaptation at all.

## Reproduction commands

Run from the target tree:

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-recheck-20261112/metrics_consistency.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-binding-recheck-20261112/metrics_consistency_original.json
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-binding-recheck-20261112/metrics_edit_contract.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-binding-recheck-20261112/metrics_edit_contract.json
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/metrics_independent_adapted.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-binding-recheck-20261112/metrics_independent_adapted.json
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/metrics_resume_adapted.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-binding-recheck-20261112/metrics_resume_adapted.json
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/metrics_blind_probe_fixed.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-binding-recheck-20261112/metrics_blind_probe_fixed.json
```

All five commands exited 0. The resume probe records results rather than asserting all fields; every expected preservation field was independently inspected as true, with `realcheck_subprocess_calls=0`.

New artifacts are local `metrics_*` files only. No commit, push, deployment, paid call or handoff edit was performed by this subtask.
