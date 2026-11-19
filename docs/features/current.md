# Current Feature: 15 Insights Page

## Status

<!-- Not started | Planned | In progress | Completed -->

Planned

## Goals

<!-- What the spec requires, as bullets. -->

- `/insights` route, linked from the nav
- Two TanStack Query calls, one per metrics endpoint
- A "Job search" group:
  - Three stat tiles: Applied (of total tracked), Response rate (with both counts) and Stale applications
  - Funnel: one horizontal bar per stage using the shadcn/ui chart component, each labeled with its count and the share that moved on
  - Table: median time in each stage, with the sample size
  - Table: tailored vs base resume with applied, responses and response rate, and a line noting that the samples are small and that tailoring may go to better-fit jobs, so the comparison is not a controlled test
- An "AI performance" group:
  - One table by feature, prompt version and model: calls, failed, approved as is, edited then approved, rejected, pending, superseded, edit ratio, flags per draft, estimated cost and median latency
  - Show "n/a" where a value does not apply
- The wide table scrolls sideways on narrow screens
- Loading and empty states for each section

## Decisions

<!-- Choices made while planning or building, with the reason. -->

- Frontend only: feature 14 already returns every number, so no backend change and no migration.
- The page renders API values and never recomputes a rate, median, share or count. Formatters only round and label. "n/a" follows the API's nulls, so the page does not decide which features a column applies to.
- Funnel: one horizontal `BarChart` through the shadcn chart component (adds `recharts`, already listed in the overview). Labels come from `count` and `share_of_previous`; the first stage shows only its count. Default `ChartTooltip` kept.
- Spec wins over the screenshot: Model and Superseded columns, and the spec's confounding note under tailored vs base.
- Time in stage shows whichever stages the API returns (so Saved appears, terminal stages do not).
- Formatting: percent to a whole number, days to one decimal with ".0" dropped (singular for 1), flags per draft one decimal, cost two decimals with `$`, latency in seconds to one decimal. Stage names use `stageLabel()`; feature names use a small label map.
- Empty states, one per section: tiles show zeros; funnel "No applications have reached Applied yet"; time table "No completed stages yet"; comparison "No applications have been applied yet"; AI table "No AI calls yet".
- Error state added: a one-line message per section when its query fails. The spec lists only loading and empty states; this was approved at planning so a failed query does not leave a blank or stuck section.
- No cache invalidation from other pages. The default `staleTime` of 0 refetches when the page is opened.
- Tests mock Recharts' `ResponsiveContainer` with a fixed size, because it measures zero in jsdom; Playwright covers the real rendering.
- Files: `lib/metrics.ts`, `hooks/useMetrics.ts`, `components/insights/` (StatTiles, FunnelCard, TimeInStageCard, ResumeComparisonCard, AIPerformanceCard, SectionState), `pages/InsightsPage.tsx`, `components/ui/chart.tsx`, `pages/insights.test.tsx`.

## Notes

<!-- Constraints, references and anything the next session needs. -->

- One chart only. Everything else is a table or a tile.
- Always show the sample size next to a rate.
- Keep the chart's default hover tooltips.
- Where the spec and `insights.png` disagree, the spec wins. The screenshot has no Model or Superseded column and a shorter tailored-vs-base note; the spec requires both columns and the confounding note.
- Existing: the nav link, the `/insights` route and a stub `frontend/src/pages/InsightsPage.tsx`. Not yet installed: the shadcn chart component (`components/ui/chart.tsx`) and `recharts`, which the project overview lists as allowed via the chart component.
- Endpoints (feature 14): `GET /metrics/pipeline` and `GET /metrics/ai`. Schemas in `backend/app/schemas/metrics.py`.
- References:
  - `docs/project-overview.md` (Telemetry, UI/UX Guidelines)
  - `docs/features/14-metrics-endpoints-spec.md`
  - `docs/screenshots/insights.png`
  - `docs/reference/v0-prototype/` (layout only)
- Frontend feature: verify in a browser with the Playwright MCP against `make dev` and `make seed` data before reporting done.

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
