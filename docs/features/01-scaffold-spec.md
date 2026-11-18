# Project Initial Scaffolding

## Overview

Set up the repo skeleton so the backend, frontend, and database run locally with one command and CI is green. No domain features yet.

## Requirements

- Look at `docs/project-overview.md` and `docs/architecture.md` for the big picture
- Monorepo layout from the project overview: `backend/`, `frontend/`, `docs/`
- Backend: Python 3.12, FastAPI, managed with uv
- `GET /health` returns `{"status": "ok"}` and confirms the database connection
- SQLAlchemy 2.0 session setup in `core/`; Alembic initialized with an empty first migration
- Config read from environment variables in `core/config.py`
- Request-logging middleware: one JSON log line per request with request ID, method, path, status code and latency in ms; return the ID in an `X-Request-ID` header
- Frontend: Vite + React + TypeScript, Tailwind, shadcn/ui initialized, React Router, TanStack Query
- App shell with a top nav bar (Applications, Resume, Insights) and placeholder pages for `/`, `/applications/:id`, `/resume` and `/insights`
- Vite dev proxy from `/api` to the backend on port 8000, stripping the `/api` prefix (backend routes have no prefix)
- `Procfile` with `api` and `web` processes, run by honcho (a backend dev dependency)
- `Makefile` with these targets:
  - `setup`: create the dev and test databases, run migrations, install backend and frontend dependencies
  - `dev`: start both processes from the Procfile
  - `test`: backend and frontend tests
  - `lint`: backend and frontend lint
- `.env.example` with `DATABASE_URL`, `TEST_DATABASE_URL`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (the repo's `.gitignore` already keeps this file out of the `.env*` ignore rule)
- GitHub Actions: backend ruff + pytest against a PostgreSQL 16 service container; frontend lint, build and Vitest
- One backend test (health check) and one frontend smoke test
- A pytest fixture that connects to `TEST_DATABASE_URL`, runs migrations once and truncates tables between tests (no rollback-per-test, because the AI call log commits in its own transaction later)
- README stub: prerequisites, the `make` commands, and a line stating this is a single-user app with no authentication

## References

- `@docs/project-overview.md` (Tech Stack, Suggested Project Structure)
- `@docs/architecture.md` (Backend layers)
- `@docs/screenshots/applications-list.png` (nav bar and page frame only)

## Notes

- No Docker. PostgreSQL 16 is installed locally.
- Do not create any domain tables in this feature.
- The packages in the project overview's Approved Packages table are allowed. Ask before adding anything else.
- Later features add `seed` and `eval` targets to the Makefile.
