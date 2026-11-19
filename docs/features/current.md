# Current Feature: 09 Guardrail Check

## Status

<!-- Not started | Planned | In progress | Completed -->

Planned

## Goals

<!-- What the spec requires, as bullets. -->

- Migration adding `guardrail_flags` (JSON, default empty list) to `resumes`
- A pure function `check(tailored, base_text, keywords)` returning a list of flags, each with a field, a value and a message
- Flag an employer or title value that is not found in the base resume
- Flag a dates value when a year or month in it is not in the base resume. Years are whole tokens, months are compared by their first three letters, and "Present" and "Current" are ignored
- Flag a skill that is not found in the base resume
- Flag any number in the summary or a bullet whose token is not in the base resume. A number token is digits with optional `,` `.` `$` `%` and a trailing `k`, `m` or `x`
- Flag an approved analysis keyword that appears in the draft (summary, bullets or skills) but not in the base resume
- Normalize before comparing: lowercase, collapse whitespace, treat en and em dashes as hyphens
- Match whole tokens or phrases on word boundaries, never raw substrings: `Go` does not match `Google`, and `5` does not pass because `2025` exists
- Run the check in the same service call as generation and store the result in `guardrail_flags`. The stored flags are as generated and never change
- A pure function `current_flags(flags, content_markdown, base_text, keywords)` that recalculates what the user sees. A structural flag (employer, title, dates, skill) stays only while its value still appears in the text. Number and keyword flags are recalculated from the text. The API returns the current flags with each resume
- Flags never block approval and are never auto-fixed
- In the Tailored resume section, above the draft: a warning box titled "N things in this draft are not in your base resume", listing each flag, for example `Skill "Kubernetes"`, with the line "Edit or remove them, or keep them if they are true. Flags do not block approval."
- The box lists the current flags, so it updates when the user edits and saves
- No box when there are no current flags
- Unit tests: one per flag type, a clean draft with zero flags, the number-token case, the `Go` / `Google` case, a reformatted date that must pass, a number in the summary, a keyword in the draft but not in the base, and `current_flags` after a flagged skill is removed

## Decisions

<!-- Choices made while planning or building, with the reason. -->

- Migration 0008 adds only `resumes.guardrail_flags` (JSONB, NOT NULL, default `'[]'`), with no trigger: the spec lists none and `CLAUDE.md` names triggers only for `draft_markdown`. Feature 8 drafts keep `[]` (dev data, no backfill).
- `services/guardrail.py` is pure. It copies coverage's whole-word pattern `(?<!\w)phrase(?!\w)` and adds dash normalization, because coverage documents that it normalizes nothing else.
- Dates: years are `(19|20)\d\d` tokens; months are matched only as month words (so "Market" is not "mar") and compared by their first three letters; both are read from the whole base resume.
- Numbers: one flag per distinct token with the first line as context; tokens glued to letters (`S3`, `1st`) are not tokens. In `current_flags` numbers come from the Summary body and bullet lines, keywords also from the Skills body, and headings are excluded so a flagged year in a heading is not flagged twice.
- Flags are ordered by field (employer, title, dates, number, skill, keyword), so `check` and `current_flags` agree on a fresh draft.
- Flag messages are the display line: `Skill "Kubernetes"`, and `Number "40%" in "Cut report run time by 40%…"` as in the screenshot. One flag reads "1 thing … is not in your base resume".
- `rendering._headings` becomes public (`find_headings`), behavior unchanged, so `current_flags` can find the Summary and Skills sections.
- `TailoredResumeService.run()` and `list_for_application()` return `TailoredDraft(resume, flags)`. The API exposes only the current flags; the stored snapshot is read by metrics in feature 14.
- At read time the keywords come from the latest approved analysis and the text from the current base resume, so displayed flags can drift if either changed after generation.
- Known gap, to note in `AI_WORKFLOW.md`: a structural fact the user adds while editing (for example a new skill) is not re-checked, because the spec recalculates only numbers and keywords.
- Browser check: there is no seed (feature 13), so the draft row and its flags are inserted by SQL for the Playwright check.

## Notes

<!-- Constraints, references and anything the next session needs. -->

- `check` runs once, on the model's structured output. `guardrail_flags` keeps those flags as generated, and metrics read them so prompt versions are compared fairly. `current_flags` follows the user's edits, and the user sees those.
- A flag is about the draft. A keyword the posting wants and the resume lacks is a missing keyword, which belongs to coverage.
- Spec: `docs/features/09-guardrail-spec.md`
- References: `docs/project-overview.md` (AI Design: Guardrail Check), `docs/screenshots/detail-step-2.png` (warning box), `docs/architecture.md` (guardrail lives in `services/guardrail.py`)
- Builds on feature 8: `tailor()` in `services/generation.py` and the `resumes` table (`content_json`, `content_markdown`).

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
