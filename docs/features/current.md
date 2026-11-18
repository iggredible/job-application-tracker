# Current Feature

Feature 01: Project scaffold (next up; the pre-build doc review is finished)

## Status

<!-- Not started | In progress | Completed -->

Not started

## Goals

Set up the repo skeleton so the backend, frontend and database run locally with one command and CI is green. No domain features. See `01-scaffold-spec.md`.

## Decisions

Made in the doc review before feature 1 (each is already written into the overview, architecture and specs):

- **Seed and creation are the two exceptions to the `change_stage()` rule.** The seed backdates history through repositories; creation uses the column default plus the initial event.
- **The AI wrapper logs through a sink.** The app's sink writes `ai_calls`; the eval uses an in-memory sink, so it never touches the database. `analyze()` and `tailor()` are pure functions in `services/generation.py`.
- **Marking as applied with the base resume saves an immutable snapshot**, because the base resume stays editable. A snapshot is a `resumes` row with `application_id` set and `ai_call_id` null.
- **Saved → Applied goes through `POST /applications/{id}/apply`.** The generic stage endpoint rejects it. The API returns the stage options, hint, displayed resume and submittable resumes, so the frontend has no rules.
- **Guardrail:** word-boundary matching, numbers in the summary, a posting-keyword-in-draft flag. `guardrail_flags` stays as generated (used by metrics); the flags the user sees are derived from the current text.
- **Superseded drafts** (still `draft`, with a newer sibling) are a derived outcome, never auto-rejected.
- **Metrics:** funnel counts a skipped stage as passed; stage time uses completed intervals only; AI metrics group by feature, prompt version and model; edit ratio is 1 − similarity with `autojunk=False`.
- **Prompt versions:** the examples section is in `tailor_resume` v1 from the start; v2 is reserved for the eval-driven change.
- **Triggers** enforce append-only on `timeline_events` and `ai_calls` and the immutability of `draft_markdown`. `TRUNCATE` is still allowed.
- **Tooling:** honcho runs the Procfile, SQLAlchemy is sync with psycopg 3, a separate test database uses `TEST_DATABASE_URL`, and the Approved Packages table in the overview lists what needs no extra approval.
- **Advisory lock** per application and feature stops duplicate AI calls. This is the cheapest option and can be dropped for a disabled button alone.
- **Known limits, accepted:** editing the posting text does not invalidate an analysis; no delete and no undo of terminal stages.

## Notes

- Start feature 1 by writing its plan and waiting for approval. No application code exists yet.
- Confirm in feature 5 which JSON Schema constraints structured outputs support; caps are enforced in code regardless.
- The directory is now a git repo. `docs/reference/v0-prototype/` is the reference code; `docs/reference/ui/` holds only a README.

## History

- Doc review before feature 1: resolved contradictions between CLAUDE.md, the overview, the architecture and the specs, and fixed design gaps (snapshot, guardrail holes, metrics rules).
