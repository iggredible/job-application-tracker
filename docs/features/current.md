# Current Feature: 09a Guardrail Markdown Fix

## Status

<!-- Not started | Planned | In progress | Completed -->

Planned

## Goals

<!-- What the spec requires, as bullets. -->

- Normalize the text. Currently it catches "Lowercase, en and em dashes as hyphens, every run of whitespace as one space.". Make it to catch `**` and remove them from the text.
- `**Lead** Software` becomes `lead software`. The marks are removed with no space added, so the spaces that were there stay as they were
- The change applies to both sides of every phrase match, so a bold employer, title or skill in the base resume is found, and a bold value in the draft is found in a plain base resume
- No other Markdown mark is removed. Single `*`, `_`, backticks, and link syntax stay as they are
- No change to the matching rule: whole tokens or phrases on word boundaries, never raw substrings. `Go` still does not match `Google`, and `5` does not match `2025`
- A value that is not in the base resume is still flagged. The fix must not make the check weaker
- No change to `check()` or `current_flags()` signatures, the `Flag` shape, the stored `guardrail_flags`, the API, the frontend, or any prompt
- Flags already stored on existing drafts do not change. This affects new drafts
- Unit tests, written first and confirmed failing for the right reason:
  - A bold employer in the base resume gives no employer flag
  - A bold skill in the base resume gives no skill flag
  - A title that is not in the base resume is still flagged
  - `current_flags` keeps no flag for a bold-in-base value and still keeps a flag for a value that is not in the base
  - The existing `Go` / `Google` and `5` / `2025` tests still pass

## Decisions

<!-- Choices made while planning or building, with the reason. -->

- Change only `_normalize()` in `backend/app/services/guardrail.py`: add `.replace("**", "")` before the whitespace is collapsed. Reason: every phrase match goes through it, so one change covers `check()` and `current_flags()` on both sides, and no space is added.
- Remove `**` only, not `_`, single `*`, backticks or links. Reason: `_` appears in names such as `snake_case`, and the spec limits the fix to `**`. A `***x***` leaves one `*` on each side, which is accepted.
- Do not touch `coverage.py`. Reason: it has its own `_normalize`, and it is out of the spec. It may have the same bold-mark problem, which is not checked.
- Tests go in `backend/tests/test_guardrail.py`, using a small `BOLD_BASE` string next to `BASE`: bold employer, bold skill, a missing title still flagged with a bold base, `current_flags` with a bold keyword in the base, and the existing `Go`/`Google` and `5`/`2025` tests unchanged.
- Add one test, `test_removing_bold_marks_adds_no_space`, for the "no space added" requirement. It guards against a wrong fix and cannot fail before the fix. The title-not-in-base test is a guard too.
- Do not add a test for the real Cryoport title line. Reason: it is not in the spec, and the employer and title checks share `add_structural`, so the employer test covers that path.
- If the seed or the eval flag counts change in `make test`, report it. Do not change them silently.

## Notes

<!-- Constraints, references and anything the next session needs. -->

- Bug fix for feature 09, not a new feature. Spec: `docs/features/09a-guardrail-markdown-fix-spec.md`.
- Seen on application 42, draft 45: the title is found in the base resume when `**` is removed from the base text, and not found when it is kept.
- Only `_found()` is affected. Dates and numbers are read from the raw text with regular expressions that already ignore `*` (`(?<!\w)` and `(?<![\w$.,])`), so they need no change.
- No migration, no frontend change and no prompt change, so no new prompt version and no browser check.
- Commit prefix: `fix:`.
- References: `docs/features/09-guardrail-spec.md` (the feature this fixes), `backend/app/services/guardrail.py` (`_normalize`, `_found`).

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
- 17 README and AI Workflow Write-Up (2026-11-19): README, architecture and demo docs, the AI workflow write-up and a measured `tailor_resume` v2 prompt that only the eval uses, with the demo verified on a clean checkout.
