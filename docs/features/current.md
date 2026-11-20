# Current Feature

## Status

<!-- Not started | Planned | In progress | Completed -->

Not started

## Goals

<!-- What the spec requires, as bullets. -->

## Decisions

<!-- Choices made while planning or building, with the reason. -->

## Notes

<!-- Constraints, references and anything the next session needs. -->

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
- 13 Seed Data (2026-11-19): `python -m scripts.seed` (`make seed`, `--reset` to wipe) fills an empty database in one transaction with about 40 fictional applications, valid backdated timelines, analyses, tailored resumes and `seed`-model `ai_calls` rows shaped to the Insights screenshot, from a pure fixed-seed planner.
- 14 Metrics Endpoints (2026-11-19): `GET /metrics/pipeline` and `GET /metrics/ai` return the funnel, time in stage, response rates, stale count and per-prompt-version AI outcomes, edit ratio, flags, tokens, cost and latency, all calculated on request from the logs and read-only.
- 15 Insights Page (2026-11-19): `/insights` shows stat tiles, a Recharts funnel and tables for time in stage, tailored vs base resume and AI calls by feature, prompt version and model, from the two metrics endpoints, with loading, empty and error states per section and a wide AI table that scrolls inside its card.
- 16 Prompt Eval (2026-11-19): `make eval` runs the real model on four fixtures through `analyze()` and `tailor()`, scores each draft with the guardrail and keyword coverage (no employer, title, dates or number flags, no forbidden skill, coverage not lower than the base resume) and writes a results file named with the prompt versions and model, with no database session.
