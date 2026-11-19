# Current Feature: 12 Example Retrieval

## Status

<!-- Not started | Planned | In progress | Completed -->

Not started

## Goals

<!-- What the spec requires, as bullets. -->

- Migration adding `applications.posting_tsv` as a generated column with a GIN index
- An `ExampleRetriever` interface and a `FullTextRetriever` implementation, so vector search can replace it later
- Build the search query from the approved analysis keywords, combined with OR. Quote multi-word keywords so they stay phrases
- Rank matches with `ts_rank` and take the top 3
- Only consider applications that have an approved tailored resume; use the most recently approved one. A base-resume snapshot is not a tailored resume
- Exclude the application being tailored
- Add the examples to the prompt's examples section, each labeled with that posting's keywords, with a line stating they show style and emphasis only and are not a source of facts. This fills a section that `tailor_resume` v1 already has, so the prompt version does not change
- Record the example resume ids in `ai_calls.retrieved_example_ids`
- When nothing matches, tailoring runs with no examples
- In the Tailored resume section header, show "N past examples used" for the displayed resume
- Tests against a real PostgreSQL test database: ranking order, the exclusion rules and the empty case

## Decisions

<!-- Choices made while planning or building, with the reason. -->

## Notes

<!-- Constraints, references and anything the next session needs. -->

- Spec: `docs/features/12-retrieval-spec.md`
- References: `docs/project-overview.md` (AI Design: Retrieval; Features E; schema for `applications` and `resumes`), `docs/architecture.md` (AI call path, Retrieval, "Snapshots are not tailored resumes"), `docs/features/08-tailored-draft-spec.md`, `docs/screenshots/detail-step-2.png` ("Prompt v1 · 2 past examples used · Generated Nov 16"), PostgreSQL full-text search: https://www.postgresql.org/docs/16/textsearch.html
- Do not use `plainto_tsquery` on the keyword list. It requires every term to match and returns nothing.
- Prefer `websearch_to_tsquery` with `or` between terms. It accepts raw input such as `c++` or `ci/cd` without syntax errors. The English configuration drops punctuation (`c++` becomes `c`), which is accepted for the MVP.
- This feature is the first to drop if the schedule slips. Keep it isolated behind the interface. Nothing after it depends on it.
- Already in place: `ai_calls.retrieved_example_ids` (JSONB, default `[]`), the `retrieved_example_ids` argument on `AIClient.generate()`, and `examples` on `ai/prompts/tailor_resume.render()` (empty block `<examples>\n</examples>` today). `applications.posting_tsv` does not exist yet.
- Retrieval lives in `services/retrieval.py`. It is deterministic and does not call the LLM. Select tailored resumes with the repository's tailored predicate (`application_id` set and `ai_call_id` set), never snapshots.
- Rejected and unreviewed drafts are never used as examples (overview, Features E).

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
