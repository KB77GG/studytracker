# StudyTracker TOEFL practice v2 contract

Status: pilot contract, 2026-07-20

## Goal

Rebuild every local TOEFL real-exam set into a source-traceable, renderer-friendly package that can later enter StudyTracker without repeating the legacy catalog's false-completeness and detached-question problems.

The contract follows the mature IELTS practice model—catalog readiness, module navigation, progress, grading and review—but keeps TOEFL-specific task types and timing.

## Package boundary

Each exam lives at `data/toefl_practice_v2/<exam_key>/`:

- `content.json`: public-safe exam content. It must never contain answer keys.
- `answer_key.json`: private server-side answers, manual-grading list and blocked-item reasons.
- `manifest.json`: counts, generator, source portability and release status.
- `qa_report.json`: human-readable build/recovery checks.

The JSON Schema for `content.json` is `schemas/toefl_practice_v2.schema.json`.

## Stable hierarchy

`exam → subject module → stimulus group → atomic question`

- A question ID is stable and encodes exam, subject, module, group and question number.
- Shared passages, notices, conversations and lectures belong to a group; they are not duplicated into every question.
- Range questions such as “1–10 Complete the Words” become ten atomic questions under one group.
- Every question has exactly one content state and one grading state.

## Content states

- `ready`: source content is complete and directly usable.
- `reviewed_repair`: source OCR/layout required a documented human repair.
- `missing_options`: the source does not contain the options; the item is blocked.
- `needs_review`: content exists but has not met the verification gate.

No set may be labeled fully complete when any expected atomic question is absent or blocked.

## Grading states

- `auto`: a private answer entry exists and the response format is deterministic.
- `manual`: a human or rubric-based grader is required.
- `blocked`: the content is insufficient to present or grade safely.

For the pilot, speaking and extended writing are manual. Complete-the-words, multiple choice and sentence ordering are auto-graded only after cross-file validation.

## Source evidence

Every group and question records:

- a path relative to the configured raw-source root;
- SHA-256 of the source file;
- source page/module/question when applicable;
- confidence: `source_exact`, `visually_recovered`, `reviewed_repair` or `source_missing`.

Relative paths are mandatory so the package can move from this Mac to another Mac without rewriting every record.

## Renderer requirements

### Complete the Words

Missing-letter fields render inline inside the paragraph. The renderer must not put a passage on the left and ten unrelated text boxes in a separate side panel.

Practice mode may accept either the missing suffix or the full word. Test mode shows the source prefix and records one answer per inline blank.

### Listening

- Test mode: one-pass playback, no scrubbing, no replay unless the source task explicitly permits it.
- Practice mode: replay may be enabled by a separate policy.
- Transcripts are review-only and must not be returned by the active-test content endpoint.
- A multiple-choice item without four recoverable options is blocked.

### Build a Sentence

The situation/context sentence is distinct from the target response. `scramble_tokens` and the private `ordered_tokens` must have the same multiset.

### Speaking

Prompts and recording behavior belong to content; model answers and grading notes remain private. Test mode supports a one-take policy; practice mode may allow local preview.

The 2026 formal contract requires 11 atomic one-question groups:

- Listen and Repeat Q1–Q7: `preparation_seconds=0`, `response_seconds=12`.
- Take an Interview Q8–Q11: `preparation_seconds=0`, `response_seconds=45`.
- The two Speaking module timers must total 480 seconds.
- Every group must reference a published source audio asset and a bounded
  `audio_cue` with alignment confidence of at least 0.96.
- Formal uploads are one-take, current-question only, and bounded by the
  question response time plus the transport tolerance enforced by the API.

## Release gate

Run:

```bash
.venv/bin/python scripts/validate_toefl_practice_v2.py \
  data/toefl_practice_v2/<exam_key> \
  --source-root "/path/to/新托福资料"
```

Publication requires zero validator errors and zero blocked questions. A package with blocked questions can be used for schema/renderer integration only and must remain visibly labeled `pilot` or `blocked` in the catalog.

The structural validator can pass a blocked pilot so renderer work can continue. The publication gate is stricter and must be run explicitly:

```bash
.venv/bin/python scripts/validate_toefl_practice_v2.py \
  data/toefl_practice_v2/<exam_key> \
  --source-root "/path/to/新托福资料" \
  --require-release-ready
```

This command exits nonzero unless the package has zero structural errors, zero blocked questions, the availability state is reviewed/published, the manifest state is ready/published, and the 2026 Speaking contract is complete. Source review may be satisfied either by four approved subject reviews or by an explicit repository-owner release authorization recorded in the manifest.

## Pilot result

`2026-01-21_A` contains 120 atomic questions:

- Reading: 50 auto-graded.
- Listening: 47 total; 43 auto-graded and 4 blocked because the supplied paper omits options.
- Writing: 10 auto-graded sentence builds and 2 manual tasks.
- Speaking: 11 manual recording tasks.

This pilot passes structural and source-traceability validation, but the exam is not publishable as fully complete until the four missing listening option sets are recovered.
