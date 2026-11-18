# README and AI Workflow Write-Up

## Overview

Finish the documentation and confirm the project runs from a clean checkout. No new features.

## Requirements

- `README.md`:
  - What the app does and that it is single-user with no authentication
  - Prerequisites: Python 3.12, uv, Node, PostgreSQL 16
  - The `make` commands: `setup`, `dev`, `seed`, `test`, `lint`, `eval`
  - A short architecture summary with the deterministic vs non-deterministic table
  - A note on how the event log and structured request logs would plug into Prometheus, Grafana or Datadog
  - What is out of scope
- `docs/architecture.md` matches the code as built, including real module names
- `docs/AI_WORKFLOW.md`:
  - How the spec, plan and build loop worked
  - What was reviewed line by line and what was verified through tests
  - What went wrong and what changed as a result
  - Eval results for prompt `v1` vs `v2`
  - What would come next
- `docs/demo.md`: the demo path from `make setup` and `make seed` through analysis, tailoring, guardrail, approval, mark as applied and Insights
- Verify the demo path on a clean checkout
- Compare each page with its screenshot and note any intended differences
- CI is green

## References

- `@docs/project-overview.md`
- `@docs/architecture.md`
- `@docs/features/current.md`
- `@docs/screenshots/`

## Notes

- `docs/AI_WORKFLOW.md` should already contain notes from each feature. This step edits and completes it.
