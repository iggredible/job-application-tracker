# Current Feature: 07 Keyword Coverage

## Status

<!-- Not started | Planned | In progress | Completed -->

Not started

## Goals

<!-- What the spec requires, as bullets. -->

- A pure function `keyword_coverage(keywords, resume_text)` returning covered keywords, missing keywords and a ratio
- Matching is case-insensitive and whitespace-normalized
- Match on word boundaries so `java` does not match `javascript`
- Handle terms with punctuation: `c++`, `ci/cd`, `.net`, `node.js`
- Multi-word keywords match as a phrase
- `GET /applications/{id}/coverage` with an optional `resume_id` (defaults to the base resume). The response always has `covered`, `missing` and `ratio`. When `resume_id` is given it also has `base` (the same fields for the base resume), `newly_covered` and `still_missing`, so feature 10 needs no change to the endpoint
- Use the latest approved analysis, or the latest draft if none is approved. A rejected analysis is never used
- Coverage is calculated on request and never stored
- In the Posting analysis card: "Keyword coverage, base resume" with the percentage, the count (for example "6 of 10"), a progress bar, and Covered and Missing keyword badges
- When no base resume exists, show a link to the Resume page in place of the numbers
- Unit tests for boundaries, punctuation, phrases and empty input

## Decisions

<!-- Choices made while planning or building, with the reason. -->

## Notes

<!-- Constraints, references and anything the next session needs. -->

- Do not call this an "ATS score" anywhere in code or UI.
- This function is reused by the review flow and the eval.
- Spec: `docs/features/07-keyword-coverage-spec.md`
- References: `docs/project-overview.md` (Features D, Derived Values), `docs/screenshots/detail-step-1.png` (coverage block in the Posting analysis card)
- Architecture: coverage lives in `services/coverage.py` (`docs/architecture.md`); pure logic is covered by unit tests.
- Builds on feature 06: `posting_analyses.keywords` (JSONB list of strings) and `status`; the base resume is the `resumes` row with `application_id` null.

## History

- Doc review before feature 1: resolved contradictions between CLAUDE.md, the overview, the architecture and the specs, and fixed design gaps (snapshot, guardrail holes, metrics rules).
- 01 Project scaffold (2026-11-18): FastAPI health check with request logging, Alembic baseline, React app shell, Makefile, Procfile and CI; all checks green.
- 02 Applications CRUD (2026-11-18): create, list, view and edit applications through a shared dialog, with a service and repository behind four endpoints; stage is not editable here.
- 03 Stages and Timeline (2026-11-18): enforced stage transitions and guards as data, `change_stage()` as the only stage writer, an append-only timeline with notes, and stage counts, filter, last activity and stale tags on the list.
- 04 Base Resume (2026-11-18): one editable Markdown base resume, kept to a single row by a unique partial index, behind `GET` and `PUT /resume` and an editor page with a "How this is used" panel.
- 05 AI Foundation (2026-11-19): one AI client wrapper with structured outputs and a database call log (`ai_calls`, append-only, written in its own transaction), typed errors, a price table, an in-memory sink and a test fake; no UI.
- 06 Posting Analysis (2026-11-19): one AI call turns a posting into a draft analysis (requirements and keywords) that the user approves or rejects, behind four endpoints, a lock per application and a card on the detail page.
