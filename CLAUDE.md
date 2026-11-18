# Job Application Tracker

A single-user web app that tracks job applications through a hiring pipeline, analyzes postings, and tailors a base resume with AI. A person approves every AI output.

## Read before working

- `docs/project-overview.md`: what to build, domain rules, schema, UI guidelines
- `docs/architecture.md`: layers, deterministic vs non-deterministic parts, key decisions
- `docs/features/NN-*-spec.md`: one spec per feature, built in numeric order
- `docs/features/current.md`: status and decisions for the feature in progress
- `docs/screenshots/`: finished pages. `docs/reference/v0-prototype/`: reference code, never imported

## Commands

- `make setup`: create the database, run migrations, install dependencies
- `make dev`: start the API and the web app
- `make test`: backend and frontend tests
- `make lint`: backend and frontend lint
- `make seed`: load sample data (from feature 13)
- `make eval`: run the prompt eval against the real model (from feature 16)

## Feature Implementation Workflow

1. Read the feature spec and the files it references.
2. Plan first. Wait for approval before writing code.
3. Write the tests first, then the implementation.
4. Run `make test` and `make lint` before reporting done.
4a. For any feature that changes the frontend, also verify it in a real browser with the Playwright MCP against `make dev` and the seed or sample data: walk the feature's user flow, check the result against the named screenshot in `docs/screenshots/`, and check the browser console for errors. Report what was checked and attach screenshots. If the Playwright MCP is not available, say so and stop; do not report the feature done on tests alone.
5. Before reporting a feature done, without being asked, update `docs/features/current.md` and add the feature's entry to `docs/AI_WORKFLOW.md`: two or three lines on what went wrong or changed, how it was caught, and what was changed as a result. Draft it from the session and tell the user it needs their review, because the log is written in their voice.
6. Small, focused commits with clear messages.

Build only what the current spec lists. If something seems missing, ask; do not add it.

## Architecture rules

- Request flow: `api/ -> services/ -> repositories/ -> models/`. Dependencies point inward only.
- `api/` handles HTTP only. No database access and no business rules.
- `services/` hold all business rules. No FastAPI imports and no SQL.
- `repositories/` hold all queries. No decisions. &lt;!— This is the repository patern from Domain-Driven Design. It’s like Rails’ query objects + AR persistence —&gt;
- `models/` defines tables and columns.
- The frontend holds no business rules. It renders what the API returns.

## Rules that must never be broken

- `applications.stage` changes only through `ApplicationService.change_stage()`. Two documented exceptions: creating an application (the column default is `saved`, and the service writes the initial event) and the seed script (feature 13, which backdates history). &lt;!— state transition rules —&gt;
- `timeline_events` and `ai_calls` are append-only. Never update or delete rows. Database triggers block UPDATE and DELETE on both tables, and block changes to `resumes.draft_markdown`.
- Transitions and guards are defined as data, not as if-statements.
- Metrics, keyword coverage, AI outcome, edit ratio and step status are calculated on request. Never store them.
- `resumes.draft_markdown` never changes after creation.

## AI rules

- Every LLM call goes through the wrapper in `ai/`, which logs one row per call, including failures, to a log sink. The app's sink writes `ai_calls`. The eval (feature 16) passes an in-memory sink, so it never writes to the app database.
- Every call uses structured outputs and Pydantic validation.
- Every AI output is saved as `draft`. Only a user action sets `approved` or `rejected`.
- Tailoring never invents facts. The base resume is the only source of facts.
- Prompts are versioned modules in `ai/prompts/`. Changing a prompt means a new version.
- Model and key come from `ANTHROPIC_MODEL` and `ANTHROPIC_API_KEY`. Never hard-code or expose them.
- Do not set temperature.
- Tests mock all AI calls. No test makes a network call.

## UI rules

- Use shadcn/ui components with Tailwind. No custom design work.
- Screenshots show finished pages with sample data. Build only what the current spec lists.
- Where a spec and a screenshot disagree, the spec wins.
- Use `docs/reference/v0-prototype/` for layout and component choices only. Do not copy its mock data or Next.js code.

## Dependencies and migrations

- Ask before adding a dependency not listed in the project overview.
- Never edit an applied migration; create a new one.
- Each migration creates only the tables and columns its feature uses.

## Definition of done

1. Tests added or updated; `make test` and `make lint` pass.
1a. Frontend features: verified in the browser with the Playwright MCP (user flow, screenshot comparison, no console errors).
2. New endpoints appear correctly in `/docs`.
3. `docs/features/current.md` and `docs/AI_WORKFLOW.md` are updated.
