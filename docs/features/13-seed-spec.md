# Seed Data

## Overview

Fill an empty database with realistic sample data so the list, the timeline and the Insights page have something to show.

## Requirements

- `python -m scripts.seed`, with a `--reset` flag that truncates all tables first
- A `seed` target in the Makefile
- Refuse to run on a non-empty database unless `--reset` is passed
- Use a fixed random seed so every run produces the same data
- One fictional base resume (`application_id` null, status `approved`). Base-resume snapshots for applications submitted with the base resume are separate rows and are not counted here
- About 40 applications with fictional companies, spread across all sources
- Timeline events backdated over roughly 10 weeks, following only valid transitions
- A spread of current stages, including some stale applications with no activity in 14+ days
- About half the applications get an approved posting analysis and a tailored resume
- Tailored resume outcomes are mixed: approved unchanged, edited then approved, rejected, pending and a few superseded
- A few tailored resumes carry guardrail flags
- `ai_calls` rows for each seeded analysis and resume, with model `seed` and prompt versions `v1` and `v2`
- The `v2` tailoring rows have lower edit ratios and fewer flags than `v1`, so the Insights page shows a prompt improvement
- Applications past Saved (except those withdrawn from Saved) have a submitted resume: some base (each with its snapshot row), some tailored, with a higher response rate for tailored
- A test that seeds an empty database and checks every stage history is valid

## References

- `@docs/project-overview.md` (Seed Data)
- `@docs/screenshots/insights.png` (the kind of numbers the seed should produce)

## Notes

- The seed script makes no AI calls.
- No real personal data.
- This script is the documented exception to the `change_stage()` rule. It inserts stage and timeline rows through repositories with explicit timestamps. The data must still satisfy every rule the services enforce, and the history test replays each timeline against the transition table.
- `--reset` uses `TRUNCATE`, which the append-only triggers allow.
