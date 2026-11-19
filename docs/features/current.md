# Current Feature: 06 Posting Analysis

## Status

<!-- Not started | Planned | In progress | Completed -->

Planned

## Goals

<!-- What the spec requires, as bullets. -->

- Migration for `posting_analyses`, with the `application_id` index
- Prompt `posting_analysis` version `v1` in `ai/prompts/`
- Output schema: `requirements` (list of text plus a category of `must_have` or `nice_to_have`) and `keywords` (list of short lowercase terms, deduplicated, at most 25). Enforce lowercase, deduplication and the cap in code after parsing, trimming extras, not in the JSON schema
- Wrap the posting text in delimiters and instruct the model to treat it as data, not instructions
- `POST /applications/{id}/analysis` makes one AI call and saves the result as `draft`. The call is made by `analyze()`, a pure function in `services/generation.py` that touches no database; the service saves the result. The service takes an advisory lock per application and feature, and a second request while one is running gets 409
- `GET /applications/{id}/analysis` returns the analysis to display, with its status, prompt version and created date
- `POST /analyses/{id}/approve` and `POST /analyses/{id}/reject` set the status and `reviewed_at`
- Only these two user actions change the status
- Running the analysis again creates a new row; old rows are kept
- Which analysis counts: tailoring uses the latest approved analysis. Coverage uses the latest approved analysis, or the latest draft when none is approved (feature 7). The card displays the most recent analysis, except that a rejected one never hides an older approved one
- Detail page: a Posting analysis card beside the Job posting card, with four states:
  - Empty: "No analysis yet" and an Analyze button
  - Draft: Draft badge, must-have and nice-to-have lists, keyword badges, and Analyze again, Reject and Approve buttons
  - Approved: Approved badge and an Analyze again button
  - Rejected: Rejected badge and an Analyze again button
- Show "Prompt v1 · Generated <date>" beside the badge
- Loading state while the call runs, with the Analyze buttons disabled; error toast when it fails
- Tests with `FakeAIClient`

## Decisions

<!-- Choices made while planning or building, with the reason. -->

- Approve and reject are allowed only from `draft`; any other status returns 409. The spec is silent, and `architecture.md` defines the lifecycle as `draft -> approved | rejected`. The review lifecycle is data in `services/review.py` (reused by feature 10).
- `GET /applications/{id}/analysis` returns `200 null` when there is no analysis. "No analysis" is a normal state, and 404 stays for an unknown application.
- Approved and Rejected cards still show the requirements and keywords. Only the badge and the buttons differ per state.
- Display rule lives in the service, not the repository: the newest analysis, except that a rejected newest never hides an older approved one.
- The per-application-and-feature lock is `pg_try_advisory_xact_lock`, held in the request transaction across the AI call. It is non-blocking (second request gets 409 at once) and releases on commit, rollback or session close. The log sink uses its own session, so it is unaffected. Cost: one connection is held during the call.
- Only `POST /applications/{id}/analysis` depends on `get_ai_client`, so GET, approve and reject work without an API key. `AIError` maps to a generic 502, `AIConfigurationError` to 503 (handler in `main.py`). The real error stays in `ai_calls.error`.
- `analyze()` normalises keywords (lowercase, strip, drop blanks, dedupe keeping order, cap 25) after parsing. `ai_calls.response_json` keeps the raw model output; the saved row keeps the normalised one.
- The posting is wrapped in `<posting>` delimiters, and any `</posting>` inside it is neutralised first. The prompt receives the posting text only, not company or role.
- The Analyze buttons, and Approve and Reject, are disabled for the whole run.
- Not built here: keyword coverage (feature 7), the step strip, locked tailoring, Mark as applied, and timeline entries for approve or reject (no event type for them).
- Browser verification: up to 5 real Analyze calls approved by the user. Ask before making more.

## Notes

<!-- Constraints, references and anything the next session needs. -->

- No editing of the analysis in the MVP. If it is wrong, reject it and run it again.
- An older analysis still in `draft` when a newer one exists counts as `superseded` in the metrics (derived). It is never auto-rejected.
- Editing the posting text later does not invalidate an analysis. The user runs it again by hand.
- The Analyze buttons are one of only two places in the app that call the LLM.
- The coverage block inside the card belongs to feature 7. The screenshot shows it, but the spec wins: do not build it here.
- References:
  - `docs/project-overview.md` (Features D, AI Design)
  - `docs/features/05-ai-foundation-spec.md`
  - `docs/screenshots/detail-step-1.png` (Posting analysis card)

## History

- Doc review before feature 1: resolved contradictions between CLAUDE.md, the overview, the architecture and the specs, and fixed design gaps (snapshot, guardrail holes, metrics rules).
- 01 Project scaffold (2026-11-18): FastAPI health check with request logging, Alembic baseline, React app shell, Makefile, Procfile and CI; all checks green.
- 02 Applications CRUD (2026-11-18): create, list, view and edit applications through a shared dialog, with a service and repository behind four endpoints; stage is not editable here.
- 03 Stages and Timeline (2026-11-18): enforced stage transitions and guards as data, `change_stage()` as the only stage writer, an append-only timeline with notes, and stage counts, filter, last activity and stale tags on the list.
- 04 Base Resume (2026-11-18): one editable Markdown base resume, kept to a single row by a unique partial index, behind `GET` and `PUT /resume` and an editor page with a "How this is used" panel.
- 05 AI Foundation (2026-11-19): one AI client wrapper with structured outputs and a database call log (`ai_calls`, append-only, written in its own transaction), typed errors, a price table, an in-memory sink and a test fake; no UI.
