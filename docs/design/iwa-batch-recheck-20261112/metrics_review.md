# Blind-review and metric recheck — 2026-11-12

Audited `/private/tmp/studytracker-iwa-holdout-review-20261111`, branch `codex/iwa-holdout-review-20261111`, HEAD `f5c3f51d` (business `45072df9`). The target tree remained clean. All evidence here is synthetic; no keys, private essays, network access, paid calls or product edits. These new review artifacts are only in the main local materials tree; the root task handles handoff and publishing.

## Prior three P2 findings: fixed

1. **Missing blind rows:** empty sheets, a missing entire side, count/judgment rows changed to `参考`, duplicate IDs, unknown IDs and old keys without a manifest are rejected as incomplete.
2. **Reclassification duplication:** a reclassified improvement now has one judged row, retaining the explanation and same-paragraph support. The original A/B example now counts the same bad suggestion once per model: **1 vs 1**.
3. **Resume overwriting manual work:** actual `Batch.run_group` with two completed synthetic runs preserves the filled sheet, key and tally byte for byte. Zero model subprocesses run. Explicit `compare.write` to an existing blind folder is also refused before altering any files.

The new tally hashes correctly mark the summary stale after either its sheet or key changes. Restoring the exact files restores freshness. This is a successful fix for **changes made after the last tally**.

## Remaining P2: the row manifest does not bind a sheet to its original mapping or fixed labels

`realcheck_compare.py:842` stores only `id/sample/side/kind` in the key, with row IDs generated from sample ID, displayed side and ordinal. `blindtally.py:90` trusts an ID match and takes model attribution from the supplied key at line 99. No generated template identity or fixed-column fingerprint connects the particular sheet to its corresponding key.

Independent minimal reproduction, using two legitimately generated keys rather than hand-inventing a mapping:

- Generate the same two-model, one-sample comparison with seeds **0** and **1**. Both have identical row manifests and IDs. Seed 0 maps 甲→A; seed 1 maps 甲→B.
- Fill the seed-0 sheet: the synthetic bad comment appears under A and receives `②`; B's comment is correct. With the matching key, the counts are **A=1 / B=0**.
- Supply the separately generated seed-1 key to that filled sheet. The tally accepts the sheet as complete and reverses the result to **A=0 / B=1**.
- Save/recalculate using that mismatched pair: the new file hashes naturally match the wrong pair, so both `current()` and the batch summary report **complete and current**.

This requires mixing a sheet and key from separate generated comparisons; ordinary fixed-seed batch resume without mixed files is now safe. It nevertheless means the new complete/current status cannot detect an accidentally mismatched mapping, and can silently reverse the model conclusion. This P2 affects measurement integrity only; it is not a budget or request-limit regression.

A second minimal case shows the same missing binding at row level. The manifest marks both omission rows simply `kind=count`. At `blindtally.py:104` the category is chosen from the editable sheet label. Changing the first row's label from `④ 漏掉评委都指出的明确错误` to the other valid label `其他漏报` moves **2** from the former category to the latter while still reporting complete. The check catches unknown labels, but not substitution between the two valid labels.

Suggested scoped fix: bind the generated sheet and key using a comparison/template identifier and fingerprint of non-editable columns, and store the exact count category in each manifest row. Judge only the editable verdict/remark columns; do not determine model attribution or count category from a mismatched or relabeled template. This is a measurement-integrity finding, not a request to harden against intentional alteration of every local file.

## Supplied adaptation review

`metrics_independent_adapted.py` retains all original examples. Its meaningful adaptation is the new ID column and manifest entries for repeated samples; it also turns the prior recorded findings into explicit fixed-behavior assertions. None of the failed-side, non-integer, reclassified-advice or privacy examples was removed or weakened. Result: **18/18**.

`metrics_resume_adapted.py` changes the constructor to supply the lock FD, adds required data stamps and shifts the edited column indices. It still calls the actual group resume path, fills the original judgments/notes, reruns the same group and compares bytes. All expected preservation fields are true and subprocess count is zero. It remains a result-recording probe, so exit 0 alone is not its acceptance criterion; the JSON fields were inspected.

## Independent checks and commands

The new `metrics_consistency.py` retains the fourteen positive controls and now asserts the correct behavior for the remaining P2 as well: reject the mismatched generated key, do not mark the recalculated mismatched pair complete/current, and reject substitution between valid count labels. It currently passes **14/17**, exits **1**, and preserves the observed counterexamples under `findings`. After a fix, these same expectations should pass without reversing assertions.

Run from the target tree:

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/metrics_independent_adapted.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-recheck-20261112/metrics_independent_adapted.json
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/metrics_resume_adapted.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-recheck-20261112/metrics_resume_adapted.json
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-recheck-20261112/metrics_consistency.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-batch-recheck-20261112/metrics_consistency.json
```

The two supplied adapted probes exited **0**; the independent consistency probe exited **1** with **14/17** correct-behavior assertions passing. Earlier probes, reports and private source files were not modified. No model-quality conclusion follows from these synthetic bookkeeping checks.
