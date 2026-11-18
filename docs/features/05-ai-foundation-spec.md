# AI Foundation

## Overview

Build the single wrapper that every LLM call goes through, with structured outputs and a full call log. This feature has no UI. It establishes the pattern the two AI features use.

## Requirements

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

## References

- `@docs/project-overview.md` (AI Design: Call Shape, Rules)
- `@docs/architecture.md` (AI call path)
- Structured outputs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs (fetch the latest before implementing)

## Notes

- Check the stop reason before parsing the response.
- Do not rely on JSON-schema constraints such as `maxItems` or `minLength`. Check the current docs for what structured outputs support, and enforce caps, lowercase and deduplication in code after parsing.
- Set `max_tokens` high enough for a full resume so normal calls are not cut off.
- `ai_calls` is append-only. No update or delete in the repository.
