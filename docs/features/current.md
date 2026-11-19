# Current Feature: 05 AI Foundation

## Status

<!-- Not started | Planned | In progress | Completed -->

Not started

## Goals

<!-- What the spec requires, as bullets. -->

- Migration for `ai_calls` and the `ai_feature` enum, with the `application_id` index and a trigger that rejects UPDATE and DELETE
- An `AIClient` interface (a Protocol) that services depend on. A call returns the validated output and the `ai_call_id`, so artifacts can store the foreign key
- A log sink interface (a Protocol). The app's sink writes `ai_calls`. An in-memory sink exists for the eval (feature 16)
- An Anthropic implementation using the official Python SDK
- Every call uses structured outputs with a Pydantic output model, and the result is validated before it is returned
- Model name from `ANTHROPIC_MODEL` and key from `ANTHROPIC_API_KEY`; never hard-code either
- Do not set temperature
- Write one row per call through the log sink (`ai_calls` in the app) with: feature, prompt version, model, full request, response, token counts, latency, stop reason, `schema_valid`, error and estimated cost
- Failed calls are logged too: API error, refusal, output cut off at the token limit, validation error
- After logging a failure, raise a typed `AIError` for the service to handle
- The log row must persist even if the caller's transaction rolls back
- Estimated cost comes from a small price table in config keyed by model; null when the model is not in the table
- Prompt templates live in `ai/prompts/` as modules that expose a `VERSION` and a `render()` function
- A `FakeAIClient` for tests, injected through a FastAPI dependency (the provider function lives in `api/`). It writes through the same log sink, so rows and foreign keys behave as in production
- Tests: a successful call logs a full row; each failure type logs a row with `schema_valid` false; the log row survives a rollback in the caller; the trigger rejects UPDATE and DELETE; no test makes a network call

## Decisions

<!-- Choices made while planning or building, with the reason. -->

## Notes

<!-- Constraints, references and anything the next session needs. -->

- Spec: `docs/features/05-ai-foundation-spec.md`. No UI, so no Playwright check or screenshot comparison.
- References: `docs/project-overview.md` (AI Design: Call Shape, Rules; Schema for `ai_calls` and `ai_feature`; Approved Packages; Important Development Notes), `docs/architecture.md` (AI call path).
- Structured outputs docs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs (fetch the latest before implementing).
- Check the stop reason before parsing the response.
- Do not rely on JSON-schema constraints such as `maxItems` or `minLength`. Check the current docs for what structured outputs support, and enforce caps, lowercase and deduplication in code after parsing.
- Set `max_tokens` high enough for a full resume so normal calls are not cut off.
- `ai_calls` is append-only. No update or delete in the repository.
- The log sink commits in its own transaction, so tests clean up by truncating tables, not by rolling back.
- `anthropic` is an approved backend package. `.env.example` must list `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`.
- Migration creates only `ai_calls`, the `ai_feature` enum and what this feature uses. `retrieved_example_ids` is part of the table shape in the schema.

## History

- Doc review before feature 1: resolved contradictions between CLAUDE.md, the overview, the architecture and the specs, and fixed design gaps (snapshot, guardrail holes, metrics rules).
- 01 Project scaffold (2026-11-18): FastAPI health check with request logging, Alembic baseline, React app shell, Makefile, Procfile and CI; all checks green.
- 02 Applications CRUD (2026-11-18): create, list, view and edit applications through a shared dialog, with a service and repository behind four endpoints; stage is not editable here.
- 03 Stages and Timeline (2026-11-18): enforced stage transitions and guards as data, `change_stage()` as the only stage writer, an append-only timeline with notes, and stage counts, filter, last activity and stale tags on the list.
- 04 Base Resume (2026-11-18): one editable Markdown base resume, kept to a single row by a unique partial index, behind `GET` and `PUT /resume` and an editor page with a "How this is used" panel.
