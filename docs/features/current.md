# Current Feature: 04 Base Resume

## Status

<!-- Not started | In progress | Completed -->

Not started

## Goals

<!-- What the spec requires, as bullets. -->

- Migration for the `resumes` table and the `review_status` enum with these columns only: `id`, `application_id` (nullable), `content_markdown`, `status`, `created_at`, `updated_at`, `reviewed_at`, plus the `application_id` index
- Exactly one base resume: the row where `application_id` is null, enforced with a unique partial index
- `GET /resume` returns the base resume or 404 if none exists
- `PUT /resume` creates or replaces it and sets `updated_at`
- The base resume always has status `approved`
- Page at `/resume`: title, a "Last saved" time, a Save button, and a large monospace textarea labeled "Resume in Markdown"
- A static "How this is used" panel beside the editor with the four points shown in the screenshot
- Empty state when no base resume exists yet: the empty editor and the same panel
- Tests for create, replace and the single-row rule

## Decisions

<!-- Choices made while planning or building, with the reason. -->

## Notes

<!-- Constraints, references and anything the next session needs. -->

- Plain textarea only. No Markdown preview library.
- `PUT /resume` replaces the text in place. Editing it never changes what an application already sent: marking an application as applied saves a snapshot of the base resume (feature 11).
- The columns for tailored resumes (`ai_call_id`, `content_json`, `draft_markdown`, `guardrail_flags`) are added by features 8 and 9. `ai_calls` does not exist until feature 5, so they cannot be created here.
- Frontend feature: verify in the browser with the Playwright MCP against `docs/screenshots/base-resume.png` (CLAUDE.md step 4a).
- References:
  - Spec: `docs/features/04-base-resume-spec.md`
  - `docs/project-overview.md` (Feature C, Schema)
  - `docs/screenshots/base-resume.png`

## History

- Doc review before feature 1: resolved contradictions between CLAUDE.md, the overview, the architecture and the specs, and fixed design gaps (snapshot, guardrail holes, metrics rules).
- 01 Project scaffold (2026-11-18): FastAPI health check with request logging, Alembic baseline, React app shell, Makefile, Procfile and CI; all checks green.
- 02 Applications CRUD (2026-11-18): create, list, view and edit applications through a shared dialog, with a service and repository behind four endpoints; stage is not editable here.
- 03 Stages and Timeline (2026-11-18): enforced stage transitions and guards as data, `change_stage()` as the only stage writer, an append-only timeline with notes, and stage counts, filter, last activity and stale tags on the list.
