# UI Optimization Backlog

## Goal

Make the StudyTracker web admin interface clearer, calmer, and consistent. Backend pages should have effective sectioning, concise hierarchy, consistent controls, and task-first usability.

## Current Evidence

- `studytracker.xin/materials` has real production data, not the empty local development dataset.
- The current material list renders as stacked list items with long descriptions, repeated full-text action buttons, emoji/type labels, and large row height.
- Production material types include the existing API values plus speaking variants such as `speaking_part1`, `speaking_part2_3`, and `speaking_reading`.
- Some grammar material descriptions are long enough to dominate the page; list rows need truncation and predictable expansion behavior.

## Current Assets

- `templates/materials_v2.html` is a complete replacement candidate for the material library page. It is intentionally not wired to the `/materials` route yet because the current environment cannot read or modify existing protected files such as `templates/materials.html` and `app.py`.
- `static/admin_ui_v2.css` contains reusable admin primitives for tabs, toolbars, filters, tables, badges, row actions, and empty/loading/error states. It should be included from `base.html` once existing files are editable.
- `static/admin_ui_v2.js` contains dependency-free helpers for safe HTML escaping, date formatting, debounced search, fetch JSON handling, badges, title cells, row actions, tables, empty/loading/error states.
- `static/admin_ui_v2_preview.html` is a standalone preview of the shared admin language using production-like material/task data, long descriptions, task status, stat cards, detail layout, and form sections.
- `templates/_admin_v2_macros.html` contains server-rendered Jinja macros for the same admin primitives when pages do not need API-side rendering, including list controls, stat cards, detail panels, metadata lists, form sections, and fields.
- `scripts/apply_materials_v2.py` is a guarded integration helper for the material library: it backs up the current template, applies `materials_v2.html`, and links `admin_ui_v2.css` / `admin_ui_v2.js` from `base.html`.
- `scripts/validate_admin_ui_v2_preview.cjs` validates the standalone preview and writes desktop/mobile screenshots to `tmp/admin-ui-v2-preview-desktop.png` and `tmp/admin-ui-v2-preview-mobile.png`.
- `scripts/audit_ui_v2_assets.py` audits the whole UI v2 asset set: Jinja parsing, CSS selectors, JS syntax/helpers, cross-file references, and optional preview rendering.
## Global UI Direction

- Use a restrained admin style: light canvas, white surfaces, compact tables, soft borders, limited shadows, teal as the primary action color.
- Prefer dense but readable tables for management lists.
- Keep page structure predictable: page title, primary action, tabs or filters, then content.
- Use badges for type/status metadata, not large colored blocks.
- Keep destructive actions visually quiet until the user is about to commit them.
- Avoid emoji as structural UI. Use Font Awesome already present in the project or text-only labels.
- Keep descriptions to 1-2 visible lines in list views. Full text belongs in details or edit pages.

## Web Admin Page Groups

1. **Management Lists**
   - Materials
   - Tasks
   - Grading list
   - Users
   - Course plans
   - Stage reports
   - Mock exam list

   Standard layout: toolbar, filters, compact table, fixed-width action column, empty/loading states.

2. **Creation And Edit Forms**
   - Material form
   - Task creation
   - Course plan creation
   - Stage report creation
   - Mock exam form
   - Bulk add

   Standard layout: compact form sections, clear labels, related controls grouped together, sticky/save footer only when useful.

3. **Detail And Review Pages**
   - Material detail
   - Grading detail
   - Reports
   - Listening/reading practice review pages

   Standard layout: summary header, metadata badges, primary content area, side actions only when they reduce scanning.

4. **Practice / Student-Facing Web**
   - Practice library
   - Listening and reading test pages
   - Student today
   - Exam login/process/result

   Standard layout: task context first, stable controls, minimal admin chrome, clear progress.

## Material Library Acceptance Criteria

- Header uses the shared dashboard page title and a single primary create button.
- Tabs show actual counts after API load.
- The main materials tab renders production data in a compact table.
- Descriptions are clamped to 2 lines in list view.
- Material type labels cover:
  - `grammar`
  - `translation`
  - `reading_vocab_choice`
  - `ielts_reading_practice`
  - `speaking`
  - `speaking_part1`
  - `speaking_part2_3`
  - `speaking_reading`
  - `writing`
- Unknown material types render as neutral badges and do not break layout.
- Row actions remain available: view, publish task, edit, delete.
- Search/filter/refresh remain wired to the existing API.
- Dictation tab preserves: list books, view book modal, publish task, delete book, upload vocabulary PDF.
- Empty, loading, and error states are visually consistent.
- Mobile layout keeps controls readable and table scrolls horizontally rather than squeezing columns.

## Rollout Order

1. Restore reliable read/write access to existing files in the project.
2. Run or manually apply `scripts/apply_materials_v2.py` after reviewing the current `templates/materials.html` and `templates/base.html`.
3. Render material library with production-like long descriptions and full material type coverage.
4. Include `static/admin_ui_v2.css` and `static/admin_ui_v2.js` from `templates/base.html` for future migrated pages if the integration helper is not used.
5. Migrate task management and grading list next because they are high-frequency teacher workflows.
6. Migrate creation/edit forms after list pages so form controls inherit the same visual language.
7. Migrate report/detail pages.

## Verification

- Run `python3 scripts/audit_ui_v2_assets.py` after editing UI v2 assets.
- Run `python3 scripts/audit_ui_v2_assets.py --render-preview` before wiring a migrated page or after any layout-affecting changes. This also refreshes desktop/mobile screenshots.
- Before wiring into production pages, run `scripts/validate_admin_ui_v2_preview.cjs` with Playwright available. It should confirm desktop/mobile page width, sample row rendering, and long-description clamping.
- The preview validator also checks stat cards, detail panels, and form sections so list, report/detail, and creation/edit patterns stay covered.
- Render each touched page at desktop width and mobile width.
- Use production-like data or API fixtures containing long titles, long descriptions, empty states, and unknown labels.
- Confirm no button text wraps awkwardly.
- Confirm long descriptions do not push action buttons off screen.
- Confirm primary workflows still navigate to the same routes.
- Confirm console has no JavaScript errors after switching tabs and using filters.
