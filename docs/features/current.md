# Current Feature: 04 Base Resume

## Status

<!-- Not started | In progress | Completed -->

Planned

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

- Migration `0004_create_resumes` creates the `review_status` enum and `resumes` with only the spec's columns, plus `resumes_application_idx` and the unique partial index `resumes_one_base_idx`. The tailored-resume columns, the `draft_markdown` trigger and `applications.submitted_resume_id` wait for features 5, 8, 9 and 11, because their dependencies do not exist yet.
- Layers: `api/resume.py`, `schemas/resume.py`, `services/resumes.py` (`ResumeService` with an injected clock, `ResumeNotFound`), `repositories/resumes.py`, `models/resume.py`. The service sets `status=approved` and `application_id=null`, so the API cannot send either (`ResumeWrite` forbids extra fields).
- `PUT /resume` returns 200 whether it creates or replaces, because the spec treats it as one operation. A concurrent create that hits the unique index rolls back and retries as a replace.
- Blank or whitespace-only content is rejected with 422, because a blank base resume would make tailoring meaningless. The text is otherwise stored exactly as typed.
- `reviewed_at` stays null for the base resume, because no review happens.
- "Last saved" is `updated_at`, and is hidden in the empty state.
- Save is disabled only while saving or when the text is blank. No dirty tracking or unsaved-changes warning, because the spec does not list them.
- The frontend treats a 404 from `GET /resume` as "no resume yet", not as an error.
- No "tailored" or "snapshot" repository predicates yet, because nothing in this feature uses them.
- `docs/architecture.md` is updated for the new service and endpoints.
- No new dependencies.

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
