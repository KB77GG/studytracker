# StudyTracker DESIGN.md

## Purpose

StudyTracker is a working education product, not a marketing site. The interface should help teachers assign, inspect, correct, and follow up on study tasks quickly. Student pages should make practice feel clear and focused, with stable controls and low visual noise.

This document is the UI contract for future agent work. Before changing any teacher-admin, entrance web, or student mini-program UI, read this file and preserve the existing product identity unless the task explicitly asks for a redesign.

## Migration Strategy

New UI code should follow this document. Existing UI should migrate only when the touched feature is already being changed for product reasons. Do not open broad visual-only refactor PRs just to chase these rules.

When editing an existing page:

- Preserve local behavior first.
- Fix obvious component instability in the touched area.
- Prefer replacing one-off colors with the canonical tokens below when the surrounding code is already being edited.
- Do not churn unrelated pages, generated assets, PDFs, or historical templates.

## Design Direction

### Teacher Admin

The teacher admin should feel like a light Linear/Airtable hybrid:

- Linear influence: restrained, precise, compact, status-forward, minimal decoration.
- Airtable influence: structured data, filters, grouped records, readable tables, lightweight colored labels.
- StudyTracker identity: warm academic focus with a teal primary color and quiet surfaces.

Do not copy any external brand. Borrow the discipline, density, and component logic, not the skin.

### Entrance Web

The `entrance_web` directory is a third surface. It should reuse Teacher Admin rules for admin flows and Student Mini Program rules for student-facing practice flows. If a page mixes both, prioritize task clarity and compact data entry over decorative brand expression.

### Student Mini Program

The student mini program should feel calm, guided, and practice-focused:

- Clear progress and immediate task context.
- Large enough touch targets for phone use.
- Stable audio and answer controls.
- No marketing layout, no decorative hero composition, no feature explanation text inside the app.

## Color Tokens

### Shared Semantic Colors

| Token | Hex | Use |
|---|---:|---|
| `--color-primary` | `#20756F` | Main actions, active states, key links |
| `--color-primary-strong` | `#145C57` | Pressed/strong primary states |
| `--color-primary-soft` | `#E6F5F2` | Selected rows, soft active backgrounds |
| `--color-success` | `#16A34A` | Completed/pass states |
| `--color-success-soft` | `#DCFCE7` | Completed badge background |
| `--color-warning` | `#D97706` | Pending review, partial completion |
| `--color-warning-soft` | `#FEF3C7` | Warning badge background |
| `--color-danger` | `#DC2626` | Delete, reject, destructive actions |
| `--color-danger-soft` | `#FEE2E2` | Destructive warning backgrounds |
| `--color-info` | `#2563EB` | Informational state, links when teal is ambiguous |

### Teacher Admin Palette

| Token | Hex | Use |
|---|---:|---|
| `--admin-canvas` | `#F7F8FA` | Page background |
| `--admin-surface` | `#FFFFFF` | Tables, forms, primary panels |
| `--admin-surface-subtle` | `#F9FAFB` | Table header, muted strips |
| `--admin-border` | `#E5E7EB` | Default border |
| `--admin-border-strong` | `#D0D5DD` | Active/focused border |
| `--admin-ink` | `#111827` | Primary text |
| `--admin-ink-muted` | `#667085` | Secondary text, metadata |
| `--admin-ink-subtle` | `#98A2B3` | Placeholders, disabled text |

### Teal Migration Notes

`#20756F` is the canonical StudyTracker primary teal. Existing code also contains `#0F766E` and `#087F77`; keep them when untouched, but prefer `#20756F` for new components and when modernizing a touched block. Use `#36A59D` or `#58C7BB` only as a secondary gradient/highlight color, not as the main identity color.

### Student Mini Program Palette

| Token | Hex | Use |
|---|---:|---|
| `--student-canvas` | `#F4F1EA` | Calm page background |
| `--student-surface` | `#FFFEFA` | Main practice cards |
| `--student-surface-cool` | `#F7FAF9` | Exercise panels, answer areas |
| `--student-border` | `#E3E8EE` | Card and control borders |
| `--student-ink` | `#18243A` | Primary text |
| `--student-ink-muted` | `#667085` | Metadata, secondary labels |

## Typography

Use system fonts. Do not introduce external font loading unless the user explicitly requests it.

### Teacher Admin Type Scale

| Role | Size | Weight | Line Height | Use |
|---|---:|---:|---:|---|
| Page title | 24px | 700 | 1.25 | Main admin page heading |
| Section title | 18px | 700 | 1.3 | Form/table group headings |
| Table header | 13px | 700 | 1.3 | Column labels |
| Body | 14px | 400-500 | 1.45 | Normal admin text |
| Cell dense | 13px | 400-500 | 1.4 | Dense table cells |
| Caption | 12px | 500 | 1.35 | Metadata, helper text, badges |

### Student Mini Program Type Scale

Use `rpx` in mini-program pages.

| Role | Size | Weight | Use |
|---|---:|---:|---|
| Page/card title | 32-36rpx | 750 | Task title, practice title |
| Section title | 28-30rpx | 750 | Current section, group heading |
| Body | 26-28rpx | 400-500 | Question text, instructions |
| Caption | 21-24rpx | 600 | Badges, metadata, tabs |
| Button | 25-30rpx | 750-800 | Primary actions |

Letter spacing should normally be `0`. Do not use viewport-scaled font sizes.

## Spacing And Shape

### Teacher Admin

- Base spacing: 4px.
- Dense gaps: 8px.
- Form/control gaps: 12px.
- Panel padding: 16-20px.
- Table cell horizontal padding: 10-14px.
- Border radius: 6-8px for controls and panels.
- Large rounded cards are discouraged in admin pages.
- Shadows should be rare and subtle. Prefer borders and background contrast.

### Student Mini Program

- Base spacing: 8rpx.
- Card padding: 24-32rpx.
- Section gaps: 20-28rpx.
- Control height: 68-88rpx.
- Border radius: 16-24rpx on major practice cards, 14-18rpx on controls.
- Do not nest cards inside cards unless the inner element is a repeated item or a modal.

## Teacher Admin Layout

Admin pages are tools for scanning and repeated action.

### Page Structure

- No landing-page hero sections.
- No decorative illustration-first layouts.
- Put filters and primary actions near the top.
- Keep forms compact but readable.
- Tables should remain the primary layout for task lists, submissions, and student records.
- Group records by student/date only when it improves scanning.

### Tables

- Default row height: 44-56px.
- Header background: `--admin-surface-subtle`.
- Use sticky headers only when the table is long and the page benefits from it.
- Numeric fields should align consistently.
- Long task titles should wrap predictably, not stretch action columns.
- Operation columns should have fixed width where practical.
- Avoid huge blank cards around tables.

### Buttons

Use compact buttons:

- Small button height: 30-32px.
- Default button height: 34-36px.
- Radius: 6-8px.
- Primary: teal background, white text.
- Secondary: white or subtle surface, border, dark text.
- Destructive: red background only for final destructive action. For less severe actions, use red text on a light background.
- Keep operation buttons consistent in width within a row when possible.

Do not use oversized pill buttons in dense admin tables.

### Status Badges

Badges should be compact, text-first, and semantically colored.

- Pending: neutral or warning soft background.
- In progress: teal soft background.
- Completed: success soft background.
- Submitted/review: info or warning soft background.
- Rejected/delete: danger soft background.

Badge height should usually be 22-26px. Avoid large colorful blocks.

### Forms

- Labels above fields for task creation and editing.
- Helper text should be short and placed directly below the relevant control.
- Radio and checkbox groups should wrap cleanly.
- Section/task range selectors should be visible only when relevant.
- Do not hide critical task-binding data behind ambiguous copy.

## Student Mini Program Layout

Student pages are practice surfaces. They should be touch-safe, stable, and calm.

### Practice Page Structure

- Summary card at top: task title, status, progress.
- Navigation strip when there are many sections/sentences/questions.
- Main practice card with current mode, audio, question/answer area.
- Fixed bottom submit/action bar only when it saves scrolling effort.
- Add bottom padding so fixed bars never cover content.

### Audio Controls

Audio controls must be layout-stable.

- Do not use native `button` for complex audio-control layout.
- Use `view` controls with explicit dimensions.
- Use CSS grid for multi-button audio controls.
- Define responsive fallback for very narrow screens.
- Text inside controls must not overflow or overlap.
- Play/pause state should not change button size.

### Answer Controls

- Radio for single choice.
- Checkbox for multi-choice.
- Picker/select style for option-bank matching.
- Input for fill-in blanks.
- Inline blanks must have fixed responsive widths.
- Table questions should scroll horizontally rather than compress into unreadable columns.

### Feedback And Results

- Show score/result in a concise card.
- Wrong question numbers should be clear and compact.
- Do not show `IELTS None`; hide IELTS band when unavailable, such as Section-only listening scores.
- Use modal confirmation before partial submission.

## Component Rules

### Cards

Use cards for:

- A task summary.
- A repeated record item.
- A modal/dialog.
- A contained practice area.

Do not use cards as generic page sections inside other cards.

### Tabs And Chips

- Tabs should have stable width or predictable scroll behavior.
- Active state should use teal background or soft teal surface.
- Chips should not resize when selected.

### Fixed Bars

- Fixed bottom bars must use `env(safe-area-inset-bottom)` in mini-program pages.
- Content must have enough bottom padding.
- Fixed bars should contain only primary current-step actions.

## Responsive Behavior

### Teacher Admin

- Desktop first, but tables must not break on narrow laptop widths.
- Use horizontal scroll for very wide tables.
- Collapse filter groups before hiding important columns.
- Operation columns should remain accessible.

### Student Mini Program

- Phone first.
- Touch targets should be at least 44px equivalent.
- On small screens, reduce gaps before reducing font size.
- Never let button text overlap.
- Question tables may scroll horizontally.

## Accessibility And Readability

- Color must not be the only signal for status.
- Use clear text labels for status and actions.
- Keep contrast high enough for classroom lighting and mobile screens.
- Avoid long center-aligned paragraphs in tools.
- Use concise Chinese labels in the product UI; avoid explanatory feature copy inside app surfaces.

## Do

- Preserve existing StudyTracker teal identity.
- Prefer dense, organized, low-decoration admin interfaces.
- Use tables, filters, badges, and compact controls for teacher workflows.
- Use stable dimensions for audio controls, question tabs, and fixed bars.
- Keep mini-program pages touch-friendly.
- Verify changed UI on narrow mobile widths.
- Keep unrelated UI surfaces unchanged when making a focused fix.

## Don't

- Do not turn admin pages into marketing pages.
- Do not add oversized hero sections to tools.
- Do not introduce decorative gradient orbs, bokeh blobs, or atmospheric backgrounds.
- Do not make one-off button/card styles when an existing pattern fits.
- Do not use large rounded pills in dense admin tables.
- Do not let task titles or operation buttons stretch table rows unpredictably.
- Do not use raw external brand styles directly.
- Do not rely on CSS order to resolve conflicting duplicate component rules.

## Agent Implementation Notes

When editing UI:

1. Inspect the existing page and nearby styles first.
2. Choose the smallest change that satisfies the task.
3. Reuse the local component vocabulary before adding new abstractions.
4. For teacher admin, optimize scan speed and data clarity.
5. For student mini-program pages, optimize touch safety and stable controls.
6. If adding a new page, state which side it belongs to: Teacher Admin or Student Mini Program.
7. If a rule here conflicts with an explicit user request, follow the user request and mention the tradeoff.
