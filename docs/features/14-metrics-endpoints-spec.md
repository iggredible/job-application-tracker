# Metrics Endpoints

## Overview

Expose process and AI telemetry as two read-only endpoints. Every number is a query over the event logs; nothing is stored.

## Requirements

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

## References

- `@docs/project-overview.md` (Telemetry, Derived Values)
- `@docs/features/10-review-flow-spec.md` (outcome and edit ratio helpers)
- `@docs/screenshots/insights.png` (every number shown must be available from these endpoints)

## Notes

- These endpoints never write.
- Reuse the outcome and edit ratio helpers and the stale rule. Do not reimplement them in SQL.
- Guardrail flags are read from `guardrail_flags` as generated, not from the current flags.
- Base-resume snapshots are excluded from the AI metrics (use the "tailored" predicate). In the tailored vs base comparison, a submitted snapshot counts as base.
- The tailored vs base comparison is confounded, because the user may tailor for better-fit jobs. The endpoint returns the counts as they are, and the page says so.
