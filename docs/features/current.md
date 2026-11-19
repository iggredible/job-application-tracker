# Current Feature: 08 Tailored Resume Draft

## Status

<!-- Not started | Planned | In progress | Completed -->

Not started

## Goals

<!-- What the spec requires, as bullets. -->

Use the LLM to write a tailored resume from the base resume and the posting. The output is structured JSON, rendered to Markdown by code and saved as a draft.

- Migration adding to `resumes`: `ai_call_id` (foreign key to `ai_calls`), `content_json` and `draft_markdown`, plus a trigger that rejects any change to `draft_markdown` after insert
- Prompt `tailor_resume` version `v1` in `ai/prompts/`
- Prompt inputs: rules, base resume, posting text, approved analysis keywords, and an examples section. The section is part of v1 from the start and stays empty until feature 12, so filling it later is not a new prompt version
- Rules in the prompt: only rephrase, reorder and emphasize facts from the base resume; never invent experience, skills, employers, titles, dates or metrics; if a required skill is missing from the resume, leave it missing
- Output schema `TailoredResume` from the overview: summary, experiences (employer, title, dates, bullets) and skills
- A deterministic renderer that turns the structured output into Markdown. It splits the base resume by headings. A section headed Summary, Experience or Skills (case-insensitive) is replaced by the model's output, and all other sections, including any text before the first heading, are copied through unchanged. If the base has no such heading, the generated section is added after the header
- `POST /applications/{id}/tailored-resumes` makes one AI call and saves a resume row. The call is made by `tailor()`, a pure function in `services/generation.py` that touches no database. The service takes an advisory lock per application and feature, and a second request while one is running gets 409
- Guard: the application must have an approved posting analysis, otherwise 409 with the reason
- A base resume must exist, otherwise 409 with the reason
- Save `content_json`, `draft_markdown`, `content_markdown` (same as the draft at first), status `draft` and `ai_call_id`
- `GET /applications/{id}/tailored-resumes` lists them, newest first, each with status, prompt version and created date
- Multiple drafts per application are allowed. A new draft does not change the status of older ones. An older draft still in `draft` counts as `superseded` in the metrics (derived, never auto-rejected)
- Detail page: a Tailored resume section below the posting and analysis cards, with these states:
  - Locked: a dashed box with a lock icon, "Approve the posting analysis to unlock tailoring", and a disabled Tailor resume button
  - Ready: the same box without the lock, and an enabled Tailor resume button
  - Draft: Draft badge, "Prompt v1 · Generated <date>", a Tailor again button, and the rendered draft shown read-only
- Loading state while the call runs, with the Tailor buttons disabled; error toast when it fails
- Tests: both guards, the renderer and the persisted fields

## Decisions

<!-- Choices made while planning or building, with the reason. -->

## Notes

<!-- Constraints, references and anything the next session needs. -->

- Register the analysis guard in the guard structure from feature 3 (`GUARDS` in `backend/app/services/transitions.py`), under its own action (the file names `"start_tailoring"` as an example).
- Retrieval fills the examples section in feature 12. Tailoring must work with no examples.
- The Tailor buttons are the second of only two places in the app that call the LLM.
- Flags, editing, the base resume pane, coverage and Approve / Reject come in features 9 and 10. Do not build them here, even though `detail-step-2.png` shows them.
- Where the spec and the screenshots disagree, the spec wins. The screenshots show "2 past examples used" in the draft header; the spec's Draft state is "Prompt v1 · Generated <date>" only.
- The detail page has no step bar yet and the spec does not list one, so the numbered steps in the screenshots are out of scope.
- Reuse from earlier features: `AIClient`, log sinks and `FakeAIClient` (05); the advisory lock in `repositories/locks.py`, `services/review.py` and the `AnalysisInProgress` to 409 mapping (06).
- References:
  - `docs/features/08-tailored-draft-spec.md`
  - `docs/project-overview.md` (Features E, AI Design: Tailored Resume Output Schema)
  - `docs/architecture.md` (AI call path)
  - `docs/features/05-ai-foundation-spec.md`
  - `docs/screenshots/detail-step-1.png` (locked Tailored resume box)
  - `docs/screenshots/detail-step-2.png` (section header and draft pane)

## History

- Doc review before feature 1: resolved contradictions between CLAUDE.md, the overview, the architecture and the specs, and fixed design gaps (snapshot, guardrail holes, metrics rules).
- 01 Project scaffold (2026-11-18): FastAPI health check with request logging, Alembic baseline, React app shell, Makefile, Procfile and CI; all checks green.
- 02 Applications CRUD (2026-11-18): create, list, view and edit applications through a shared dialog, with a service and repository behind four endpoints; stage is not editable here.
- 03 Stages and Timeline (2026-11-18): enforced stage transitions and guards as data, `change_stage()` as the only stage writer, an append-only timeline with notes, and stage counts, filter, last activity and stale tags on the list.
- 04 Base Resume (2026-11-18): one editable Markdown base resume, kept to a single row by a unique partial index, behind `GET` and `PUT /resume` and an editor page with a "How this is used" panel.
- 05 AI Foundation (2026-11-19): one AI client wrapper with structured outputs and a database call log (`ai_calls`, append-only, written in its own transaction), typed errors, a price table, an in-memory sink and a test fake; no UI.
- 06 Posting Analysis (2026-11-19): one AI call turns a posting into a draft analysis (requirements and keywords) that the user approves or rejects, behind four endpoints, a lock per application and a card on the detail page.
- 07 Keyword Coverage (2026-11-19): a pure `keyword_coverage()` function and `GET /applications/{id}/coverage` that measure the base resume against the posting keywords, shown as a percentage, progress bar and Covered and Missing badges on the Posting analysis card.
