# Current Feature: 10 Tailored Resume Review

## Status

<!-- Not started | Planned | In progress | Completed -->

Not started

## Goals

<!-- What the spec requires, as bullets. -->

- In the Tailored resume section: the base resume (read-only) and the draft side by side
- The draft is an editable textarea while its status is `draft`, with a Save edits button
- `PATCH /resumes/{id}` saves edits to `content_markdown` only, and only while the status is `draft`
- `draft_markdown` never changes after creation
- `POST /resumes/{id}/approve` and `POST /resumes/{id}/reject` set the status and `reviewed_at`
- Approve saves any unsaved edits first
- Approved and rejected resumes are read-only
- An approved resume shows an Approved badge, "Approved <date>" (with "after your edits" when it was edited), and a Copy Markdown button that copies its text to the clipboard
- Below the panes: "Keyword coverage X% → Y%" comparing the base resume with the current draft text, with "Newly covered" and "Still missing" keyword lists
- The coverage endpoint returns both lists when given a `resume_id`
- Which resume the section displays: the newest draft if one is awaiting review; otherwise the latest approved; otherwise the latest rejected. The API makes this choice: `GET /applications/{id}/tailored-resumes` marks one resume as `displayed`, and the frontend renders it
- Saving edits returns the updated coverage and current guardrail flags. They update on save, not while typing, because the frontend holds no rules
- A service helper that derives the outcome: pending, superseded, approved, edited then approved, or rejected. A draft that is still `draft` but has a newer draft for the same application and feature is superseded, not pending
- A service helper that derives the edit ratio from `draft_markdown` and `content_markdown` as 1 − `difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()`, so 0 means unedited
- Outcome and edit ratio are calculated, never stored
- Tests for edit rules, status changes and both helpers, including a draft that becomes superseded and an edit ratio on text longer than 200 characters

## Decisions

<!-- Choices made while planning or building, with the reason. -->

## Notes

<!-- Constraints, references and anything the next session needs. -->

- Spec: `docs/features/10-review-flow-spec.md`
- No diff highlighting and no "regenerate with feedback". To try again, reject and tailor again.
- "2 past examples used" in the screenshot belongs to feature 12.
- Spec wins over screenshots where they disagree.
- Coverage endpoint already accepts `resume_id` and returns `base`, `newly_covered` and `still_missing` (feature 7), so it needs no change.
- References:
  - `docs/project-overview.md` (Features E, Derived Values)
  - `docs/features/07-keyword-coverage-spec.md`
  - `docs/screenshots/detail-step-2.png` (draft in review)
  - `docs/screenshots/detail-step-3.png` (approved, read-only state)

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
