# Prompt Eval

## Overview

A script that runs the real model against fixed fixtures and scores the output with the existing deterministic checks. It answers whether a prompt version is better than the last one.

## Requirements

- `uv run python -m evals.run`, run by hand; requires `ANTHROPIC_API_KEY`
- An `eval` target in the Makefile
- Fixtures in `evals/fixtures/<name>/`: `posting.txt`, `resume.md` and `expect.json` with a `forbidden_skills` list
- 3 to 5 fixtures, including one trap whose posting demands a skill the resume does not have
- For each fixture, run the analysis and tailoring prompts through `analyze()` and `tailor()` in `services/generation.py`, the same pure functions the app's services call
- Retrieval is off, so runs are comparable
- The eval does not write to the app database. It passes the in-memory log sink to the AI client and never opens a database session
- Score with the existing guardrail and keyword coverage functions
- A fixture passes when:
  - There are zero flags on employer, title, dates and numbers
  - None of its forbidden skills appear in the draft
  - Draft coverage is higher than base resume coverage (equal is enough when the base resume is already at 100%)
- Other skill flags are reported but do not fail the fixture
- Print a table: fixture, flags, coverage before and after, pass or fail
- Write results to `evals/results/` in a file named with the prompt version and model
- Exit with a non-zero code if any fixture fails
- A unit test for the scoring logic using fake outputs, which does run in CI

## References

- `@docs/project-overview.md` (AI Design: Eval)
- `@docs/features/09-guardrail-spec.md`
- `@docs/features/07-keyword-coverage-spec.md`

## Notes

- The eval itself does not run in CI. It costs money and its outputs vary between runs.
- Process: run `v1` and commit the results, improve the prompt as `v2`, run again, commit, and summarize the difference in `docs/AI_WORKFLOW.md`.
