# Current Feature: 05 AI Foundation

## Status

<!-- Not started | Planned | In progress | Completed -->

Planned

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

- Migration `0005_create_ai_calls` adds the `ai_feature` enum, the full `ai_calls` table, `ai_calls_application_idx` and a BEFORE UPDATE OR DELETE trigger (modelled on 0003). No FKs from `resumes` or `posting_analyses` to `ai_calls`; features 6 and 8 add them.
- Layout: `models/ai_call.py`, `repositories/ai_calls.py` (`add` and `get` only), `ai/{types,cost,client,sinks}.py`, `ai/prompts/__init__.py` (`RenderedPrompt`, `PromptModule` Protocol), `api/ai.py` (`get_ai_client`). `core/db.py` gains `get_session_factory()`. `ai/` imports no FastAPI and reaches the database only through the repository.
- `AIClient.generate(feature, prompt, output_model, application_id=None, retrieved_example_ids=None)` returns `AIResult(output, ai_call_id)`. Failures raise an `AIError` subclass (API error, refusal, truncated, validation) that carries the `ai_call_id`.
- Order inside a call: check `stop_reason` first, then validate with Pydantic, then write exactly one log record, then return or raise.
- `DatabaseLogSink` opens its own session and commits, so the row survives a rollback in the caller. `application_id` must point at a committed application.
- Sync Anthropic client, because the app uses sync SQLAlchemy. `max_tokens` defaults to 8192 (a full resume fits), overridable per call. No temperature.
- On failure `response_json` stays null (as in the schema); the failure kind and a truncated message go in `error`. If the sink itself fails, the exception propagates: no model call without a log row.
- No real prompts in this feature. Features 6 and 8 add them; this feature adds only the structure.
- `FakeAIClient` lives in `backend/tests/fakes.py` and writes through the real `DatabaseLogSink`. Tests override `get_ai_client` with it.
- No network in tests: an autouse fixture makes `httpx.HTTPTransport.handle_request` raise (TestClient uses its own transport, so it is unaffected).
- Prices come from https://platform.claude.com/docs/en/about-claude/pricing (fetched 2026-11-19), $ per million tokens (input, output): `claude-sonnet-5-5` 2/10, `claude-opus-5-5` 4/20, `claude-haiku-5-5` 0.10/0.50, `claude-fable-5-2` 8/40. The table is flat. Haiku 5.5 bills $0.50/$2.50 for prompts over 100,000 tokens; ignored because postings and resumes are far below that (comment in code). Caching, batch and fast-mode discounts are ignored. Model IDs are from the session's model list; the page lists display names only.
- Model for local use: Sonnet 5.5 (`ANTHROPIC_MODEL=claude-sonnet-5-5`, set in the gitignored `.env`; never hard-coded). Feature 16's eval is the place to compare against Haiku.
- Added at the user's request, outside the spec: `backend/scripts/ai_smoke.py`, a hand-run script (not in `make test`, so tests still make no network call). It makes three real calls through `AnthropicAIClient` with the `InMemoryLogSink` (never the app database, since `ai_calls` is append-only): a success, a truncation (tiny `max_tokens`) and an API error (invalid model name). Its output is compared with the stub, which is corrected wherever they differ. A refusal cannot be triggered on demand, so that case stays stub-only.
- Confirm the SDK shape at `start`: install `anthropic`, read the `parse()` signature (`output_format` vs `output_config.format`) and the `usage` fields before writing the adapter. The docs fetch did not settle this.

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
- The API key lives only in a gitignored `.env` in the worktree root (backend reads `../.env`). The main checkout needs its own `.env` before `make dev` or the smoke script runs there.

## History

- Doc review before feature 1: resolved contradictions between CLAUDE.md, the overview, the architecture and the specs, and fixed design gaps (snapshot, guardrail holes, metrics rules).
- 01 Project scaffold (2026-11-18): FastAPI health check with request logging, Alembic baseline, React app shell, Makefile, Procfile and CI; all checks green.
- 02 Applications CRUD (2026-11-18): create, list, view and edit applications through a shared dialog, with a service and repository behind four endpoints; stage is not editable here.
- 03 Stages and Timeline (2026-11-18): enforced stage transitions and guards as data, `change_stage()` as the only stage writer, an append-only timeline with notes, and stage counts, filter, last activity and stale tags on the list.
- 04 Base Resume (2026-11-18): one editable Markdown base resume, kept to a single row by a unique partial index, behind `GET` and `PUT /resume` and an editor page with a "How this is used" panel.
