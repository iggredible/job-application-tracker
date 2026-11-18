# Job Application Tracker

Tracks job applications through a hiring pipeline, analyzes postings, and tailors a base resume with AI. A person approves every AI output.

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
make test    # backend and frontend tests
make lint    # backend and frontend lint
```

`make setup` copies `.env.example` to `.env` if there is no `.env`. Put `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` there; `.env` is not committed.

The web app proxies `/api/*` to the API and strips the `/api` prefix. API docs are at <http://localhost:8000/docs>.
