# Insights Page

## Overview

One page that shows how the job search and the AI are performing, built from the two metrics endpoints.

## Requirements

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

## References

- `@docs/project-overview.md` (Telemetry, UI/UX Guidelines)
- `@docs/features/14-metrics-endpoints-spec.md`
- `@docs/screenshots/insights.png`

## Notes

- One chart only. Everything else is a table or a tile.
- Always show the sample size next to a rate.
- Keep the chart's default hover tooltips.
