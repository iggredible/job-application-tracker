# Base Resume

## Overview

Store one base resume as an editable Markdown document. Every tailored resume is derived from it.

## Requirements

- Migration for the `resumes` table and the `review_status` enum with these columns only: `id`, `application_id` (nullable), `content_markdown`, `status`, `created_at`, `updated_at`, `reviewed_at`, plus the `application_id` index
- Exactly one base resume: the row where `application_id` is null, enforced with a unique partial index
- `GET /resume` returns the base resume or 404 if none exists
- `PUT /resume` creates or replaces it and sets `updated_at`
- The base resume always has status `approved`
- Page at `/resume`: title, a "Last saved" time, a Save button, and a large monospace textarea labeled "Resume in Markdown"
- A static "How this is used" panel beside the editor with the four points shown in the screenshot
- Empty state when no base resume exists yet: the empty editor and the same panel
- Tests for create, replace and the single-row rule

## References

- `@docs/project-overview.md` (Features C, Schema)
- `@docs/screenshots/base-resume.png`

## Notes

- Plain textarea only. No Markdown preview library.
- `PUT /resume` replaces the text in place. Editing it never changes what an application already sent: marking an application as applied saves a snapshot of the base resume (feature 11).
- The columns for tailored resumes (`ai_call_id`, `content_json`, `draft_markdown`, `guardrail_flags`) are added by features 8 and 9. `ai_calls` does not exist until feature 5, so they cannot be created here.
