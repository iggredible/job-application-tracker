# Job Application Tracker

Tracks job applications through a hiring pipeline, analyzes postings, and tailors a base resume with AI. A person approves every AI output.

- **Track.** One list of applications, an enforced stage pipeline (Saved, Applied, Screening, Interviewing, Offer, Accepted, Rejected, Withdrawn) and an append-only timeline for each.
- **Analyze.** The AI reads a pasted job posting and returns requirements and keywords. Code measures how many keywords the base resume already covers.
- **Tailor.** The AI rewrites the base resume for one posting. A deterministic guardrail flags any employer, title, date, number, skill or keyword that the base resume does not contain. The user edits the draft, then approves or rejects it.
- **Measure.** An Insights page shows the funnel, time in stage, response rates and how each prompt version performs, all calculated from the event logs.

This is a single-user app with no authentication.

## Prerequisites

- Python 3.12 (uv installs it if missing)
- [uv](https://docs.astral.sh/uv/)
- Node.js
- PostgreSQL 16, running locally

## Commands

```bash
make setup   # create the dev and test databases, run migrations, install dependencies
make dev     # start the API (port 8000) and the web app (port 5173)
make seed    # fill an empty dev database with about 40 fictional applications (make seed ARGS=--reset wipes it first)
make test    # backend and frontend tests
make lint    # backend and frontend lint
make eval    # run the prompt eval against the real model (costs money, run by hand)
```

`make setup` copies `.env.example` to `.env` if there is no `.env`. Put `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` there; `.env` is not committed. Analyzing and tailoring need them. Everything else, including `make seed` and `make test`, works without them, and no test makes a network call.

The web app proxies `/api/*` to the API and strips the `/api` prefix. API docs are at <http://localhost:8000/docs>.

To try the app, follow [docs/demo.md](docs/demo.md).

### The eval

`make eval` runs the real model on four fixed postings and resumes, one of them a trap whose posting demands a skill the resume lacks. It scores each draft with the same guardrail and keyword coverage code the app uses, prints a table and writes `backend/evals/results/`. It needs `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`, uses an in-memory log, never touches the database, and never runs in CI.

`make eval ARGS=--prompts=v2` measures the `v2` tailoring prompt. The app itself runs `v1` of both prompts. Results and what they mean are in [docs/AI_WORKFLOW.md](docs/AI_WORKFLOW.md).

## Architecture

The full description is in [docs/architecture.md](docs/architecture.md). In short:

- A React single-page app (Vite, TanStack Query, shadcn/ui) talks over HTTP and JSON to a FastAPI backend, which is the only part that talks to PostgreSQL 16 or the Anthropic API.
- The backend is layered, and dependencies point inward only: `api/` (HTTP only) calls `services/` (all business rules), which call `repositories/` (all queries) over `models/` (tables). `ai/` holds the one client wrapper and the versioned prompts.
- The frontend holds no business rules. Allowed stages, guard results and step status all come from the API.
- Stages and guards are data tables, not if-statements, and `ApplicationService.change_stage()` is the only code that writes a stage.
- `timeline_events` and `ai_calls` are append-only, enforced by database triggers. Every metric is calculated on request from them and never stored.

Every AI step is followed by a deterministic check and a person's decision:

| Step | Kind |
| --- | --- |
| Stages, transitions, guards, timeline | Deterministic (plain code) |
| Extract requirements and keywords from a posting | Non-deterministic (LLM) |
| Keyword coverage | Deterministic |
| Retrieve past examples (full-text search) | Deterministic |
| Write a tailored resume | Non-deterministic (LLM) |
| Render the draft to Markdown | Deterministic |
| Guardrail check | Deterministic |
| Approve or reject | Human |
| All metrics | Deterministic |

Only two steps call the LLM, and only when the user clicks Analyze or Tailor resume.

## Observability

The app does not ship Prometheus, Grafana or Datadog. Two things it already produces would plug into them:

- **Request logs.** Middleware writes one JSON line per request to the log, with `request_id`, `method`, `path`, `status_code` and `latency_ms`. A log shipper (the Datadog Agent, or Promtail with Loki and Grafana) can ingest the lines as they are. A request count and a latency histogram by path and status come straight from those fields. To scrape `/metrics` from Prometheus instead, a Prometheus client library would be added to the middleware, which needs a new dependency.
- **The event log.** `timeline_events` and `ai_calls` are append-only tables, and every metric on the Insights page is a query over them. Grafana's PostgreSQL data source, or a Datadog custom query, could run the same queries to chart the funnel, time in stage, AI cost, latency and guardrail flags by prompt version. Because the rows are never updated, a chart of them cannot drift.

## Out of scope

- Authentication or multiple users
- Scraping postings from a URL (paste the text)
- Uploading or parsing resume PDFs (Markdown only)
- Email or calendar integration
- Payments
- Docker and deployment
- External observability stacks (Prometheus, Grafana, Datadog)
- Vector search, resume export and interview prep
- Deleting applications, and undoing a terminal stage (a mistake is corrected with a note)
- Re-running an analysis automatically when the posting text is edited

## More

- [docs/demo.md](docs/demo.md): a walk through the app
- [docs/AI_WORKFLOW.md](docs/AI_WORKFLOW.md): how it was built with Claude Code, and the eval results
- [docs/project-overview.md](docs/project-overview.md) and `docs/features/`: the specification, one spec per feature
