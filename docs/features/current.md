# Current Feature: 14 Metrics Endpoints

## Status

<!-- Not started | Planned | In progress | Completed -->

Not started

## Goals

<!-- What the spec requires, as bullets. -->

- Expose process and AI telemetry as two read-only endpoints. Every number is a query over the event logs; nothing is stored
- `GET /metrics/pipeline` returns:
  - Total applications tracked and how many reached Applied
  - Funnel: how many applications reached Applied, Screening, Interviewing and Offer, with the share that moved on from the previous step. Reaching a later stage counts as having passed the earlier funnel stages, so Applied → Interviewing still counts at Screening
  - Median time in each stage, with the sample size for each. Only completed intervals count: a stage an application is still in, and the terminal stages, are excluded
  - Response rate: share of applied applications with any later stage change other than Withdrawn, with both counts
  - Count of stale applications, using the stale rule from feature 3
  - Response rate for tailored vs base resume: applied count, response count and rate for each
- `GET /metrics/ai` returns, per feature, prompt version and model (so seeded rows with model `seed` stay separate from real calls):
  - Total calls and failed calls
  - Counts for approved as is, edited then approved, rejected, pending and superseded
  - Average edit ratio
  - Average guardrail flags per draft
  - Input and output tokens, and estimated cost
  - Median latency
- Edit ratio, edited-then-approved and flags are null for posting analysis
- "Reached a stage" is read from `timeline_events`, not from the current stage
- Metric logic lives in `services/metrics.py` with queries in repositories
- Response schemas appear correctly in `/docs`
- Tests using small hand-built datasets with known answers

## Decisions

<!-- Choices made while planning or building, with the reason. -->

## Notes

<!-- Constraints, references and anything the next session needs. -->

- Spec: `docs/features/14-metrics-endpoints-spec.md`
- References: `docs/project-overview.md` (Telemetry, Derived Values), `docs/features/10-review-flow-spec.md` (outcome and edit ratio helpers), `docs/screenshots/insights.png` (every number shown must be available from these endpoints)
- Also relevant: `docs/features/03-stages-timeline-spec.md` (stale rule, `services/staleness.py`), `docs/architecture.md` (snapshots vs tailored resumes, metrics row)
- These endpoints never write
- Reuse the outcome and edit ratio helpers and the stale rule. Do not reimplement them in SQL
- Guardrail flags are read from `guardrail_flags` as generated, not from the current flags
- Base-resume snapshots (`application_id` set, `ai_call_id` null) are excluded from the AI metrics (use the "tailored" predicate). In the tailored vs base comparison, a submitted snapshot counts as base
- The tailored vs base comparison is confounded, because the user may tailor for better-fit jobs. The endpoint returns the counts as they are, and the page says so (feature 15)
- The screenshot's Time in stage table includes Saved, so the interval table covers every non-terminal stage; the spec's rule decides edge cases

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
