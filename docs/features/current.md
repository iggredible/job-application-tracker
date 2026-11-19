# Current Feature: 13 Seed Data

## Status

<!-- Not started | Planned | In progress | Completed -->

Planned

## Goals

<!-- What the spec requires, as bullets. -->

- `python -m scripts.seed`, with a `--reset` flag that truncates all tables first
- A `seed` target in the Makefile
- Refuse to run on a non-empty database unless `--reset` is passed
- Use a fixed random seed so every run produces the same data
- One fictional base resume (`application_id` null, status `approved`). Base-resume snapshots for applications submitted with the base resume are separate rows and are not counted here
- About 40 applications with fictional companies, spread across all sources
- Timeline events backdated over roughly 10 weeks, following only valid transitions
- A spread of current stages, including some stale applications with no activity in 14+ days
- About half the applications get an approved posting analysis and a tailored resume
- Tailored resume outcomes are mixed: approved unchanged, edited then approved, rejected, pending and a few superseded
- A few tailored resumes carry guardrail flags
- `ai_calls` rows for each seeded analysis and resume, with model `seed` and prompt versions `v1` and `v2`
- The `v2` tailoring rows have lower edit ratios and fewer flags than `v1`, so the Insights page shows a prompt improvement
- Applications past Saved (except those withdrawn from Saved) have a submitted resume: some base (each with its snapshot row), some tailored, with a higher response rate for tailored
- A test that seeds an empty database and checks every stage history is valid

## Decisions

<!-- Choices made while planning or building, with the reason. -->

- Two-part design: a pure planner (`scripts/seed_plan.py`, all randomness from `random.Random(13)`, returns dataclasses) and a persistence step (`scripts/seed.py`, one transaction, repositories only). Static fictional content lives in `scripts/seed_content.py`. The planner needs no database, so the data shape is tuned and tested without one.
- Dates are offsets from an injected `now`. A real run uses the current time, so stale applications are stale whenever you seed; tests pass a fixed `now` so two runs are identical. Absolute timestamps differ between real runs, the relative layout does not.
- `--reset` has no extra guard (no confirmation prompt), as the spec says. It erases real data on whatever `DATABASE_URL` points at.
- `make seed` runs the script; `make seed ARGS=--reset` passes the flag. No separate `seed-reset` target.
- `MaintenanceRepository` (`repositories/maintenance.py`) holds `is_empty()` and `truncate_all()` (`TRUNCATE ... RESTART IDENTITY CASCADE` over `Base.metadata`), so the script has no SQL and ids restart after `--reset`.
- Seed writes `stage`, `submitted_resume_id` and review statuses directly: the documented seed exception. `submitted_resume_id` is set after the resume insert (foreign-key cycle) and `updated_at` is set explicitly so `onupdate=now()` does not overwrite the backdate. The history test proves the data is consistent.
- `draft_markdown`, `content_markdown` and `status` are inserted in one INSERT, so the `draft_markdown` trigger never fires.
- Flags and edit ratios are real: flagged drafts inject an unsupported skill or number into the structured output, then run the real `check()`. Edits apply a seeded number of line changes to the draft so `edit_ratio` lands near the target.
- Cost uses an explicit `seed` price passed to `estimate_cost()`; the real price table in `core/config.py` is not changed.
- Include 2 failed `ai_calls` rows (1 analysis, 1 `v2` tailor) with no artifact, so the Insights Failed column is not all zeros. Not in the spec; approved at planning.
- Flags follow the spec's "a few": about 5 of 12 `v1` drafts flagged, 1 to 2 in `v2`. This lands below the screenshot's 1.8 and 0.4 per draft but keeps `v1` higher. The spec wins over the screenshot.
- `retrieved_example_ids` is `[]` on every seeded call. `request_json` is a minimal `{"system", "messages"}` because `v2` has no real prompt module.
- "Response" means a later stage change other than Withdrawn (Feature 14's definition). Applied to Rejected counts.
- Tests assert ranges, not exact numbers, taken from `insights.png`. No migration, no new dependency, no frontend change (so no Playwright step; run `make seed` and fetch `/applications` by hand instead).

## Notes

<!-- Constraints, references and anything the next session needs. -->

- The seed script makes no AI calls.
- No real personal data.
- This script is the documented exception to the `change_stage()` rule. It inserts stage and timeline rows through repositories with explicit timestamps. The data must still satisfy every rule the services enforce, and the history test replays each timeline against the transition table.
- `--reset` uses `TRUNCATE`, which the append-only triggers allow.
- Spec: `docs/features/13-seed-spec.md`
- References: `docs/project-overview.md` (Seed Data, Schema, Derived Values), `docs/screenshots/insights.png` (the kind of numbers the seed should produce: about 34 of 40 applied, 56% response rate, 5 stale, tailored 67% vs base 44%, posting analysis v1, tailor resume v1 and v2 with edit ratio 31% vs 14% and flags per draft 1.8 vs 0.4)

## History

- Doc review before feature 1: resolved contradictions between CLAUDE.md, the overview, the architecture and the specs, and fixed design gaps (snapshot, guardrail holes, metrics rules).
- 01 Project scaffold (2026-11-18): FastAPI health check with request logging, Alembic baseline, React app shell, Makefile, Procfile and CI; all checks green.
- 02 Applications CRUD (2026-11-18): create, list, view and edit applications through a shared dialog, with a service and repository behind four endpoints; stage is not editable here.
- 03 Stages and Timeline (2026-11-18): enforced stage transitions and guards as data, `change_stage()` as the only stage writer, an append-only timeline with notes, and stage counts, filter, last activity and stale tags on the list.
- 04 Base Resume (2026-11-18): one editable Markdown base resume, kept to a single row by a unique partial index, behind `GET` and `PUT /resume` and an editor page with a "How this is used" panel.
- 05 AI Foundation (2026-11-19): one AI client wrapper with structured outputs and a database call log (`ai_calls`, append-only, written in its own transaction), typed errors, a price table, an in-memory sink and a test fake; no UI.
- 06 Posting Analysis (2026-11-19): one AI call turns a posting into a draft analysis (requirements and keywords) that the user approves or rejects, behind four endpoints, a lock per application and a card on the detail page.
- 07 Keyword Coverage (2026-11-19): a pure `keyword_coverage()` function and `GET /applications/{id}/coverage` that measure the base resume against the posting keywords, shown as a percentage, progress bar and Covered and Missing badges on the Posting analysis card.
- 08 Tailored Resume Draft (2026-11-19): one AI call writes a structured draft from the base resume and the approved keywords, rendered to Markdown by code and saved as a `draft` behind `POST` and `GET /applications/{id}/tailored-resumes`, with two guards, a lock per application, a `draft_markdown` trigger and a Locked, Ready and Draft section on the detail page.
- 09 Guardrail Check (2026-11-19): a pure `check()` flags employers, titles, dates, numbers, skills and keywords that the base resume lacks and stores them as generated in `resumes.guardrail_flags`, and a pure `current_flags()` recalculates what the user sees, shown as a warning box above the draft.
- 10 Tailored Resume Review (2026-11-19): the user edits a draft beside the base resume, then approves or rejects it behind `PATCH /resumes/{id}` and `POST /resumes/{id}/approve` and `/reject`, with outcome, edit ratio and the displayed resume calculated on request, never stored.
- 11 Mark as Applied and Submitted Resume (2026-11-19): `POST /applications/{id}/apply` is the only way from Saved to Applied, saving a snapshot of the base resume (or pointing at an approved tailored resume) in `submitted_resume_id`, and the API returns the three workflow steps, shown as a strip and a Mark as applied section.
- 12 Example Retrieval (2026-11-19): before tailoring, a full-text search over `applications.posting_tsv` finds up to 3 past approved tailored resumes, which fill the prompt's examples section and are logged in `ai_calls.retrieved_example_ids`, and the section header shows "N past examples used".
