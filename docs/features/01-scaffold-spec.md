# Project Scaffold

## Overview

Set up the repo skeleton so the backend, frontend and database run locally with one command and CI is green. No domain features yet.

## Requirements

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
- Approved while building, beyond the overview's original list (now added to it): `cn` (replaces clsx and tailwind-merge), `shadcn`, `@fontsource-variable/geist`, `@tailwindcss/vite`, `@eslint/js`, `@testing-library/dom`, `@types/*`, `@vitejs/plugin-react`.

## Verification

1. **Automated.** `make test` and `make lint` pass: the health test, the database-unreachable test, the request-logging test and the frontend smoke test; `ruff check`, `ruff format --check` and eslint are clean. `npm run build` succeeds.
2. **Setup from scratch.** Drop both databases and delete `.env`, `backend/.venv` and `frontend/node_modules`, then run `make setup`.
   - Both databases exist and `alembic current` shows the empty revision at head.
   - The only table is `alembic_version`.
   - `.env` is created from `.env.example`, and an existing `.env` is never overwritten.
3. **Backend by hand (`make dev`).**
   - `curl -i localhost:8000/health` returns 200, `{"status":"ok"}` and an `X-Request-ID` header.
   - The `api` output shows exactly one JSON log line per request (request ID, method, path, status, `latency_ms`), and the ID matches the header.
   - `/docs` loads and lists `/health`.
   - With the database unreachable, `/health` returns a non-200 and not `ok`.
   - `curl localhost:5173/api/health` returns the same body, which shows the proxy strips the `/api` prefix.
4. **Frontend in a real browser (Playwright MCP).**
   - Open `/` and compare the nav bar and page frame with `docs/screenshots/applications-list.png`: brand on the left, Applications, Resume and Insights, active link underlined.
   - Click through Resume and Insights, open `/applications/1`, and reload on a deep link such as `/resume`.
   - The console shows no errors or warnings and there are no failed network requests, on every page.
   - Attach a screenshot of each page. If the Playwright MCP is not available, stop and say so.
5. **Rules and hygiene.**
   - `git status` shows no `.env`, and a grep for the key prefix (`sk-ant`) across the working tree, excluding this spec, is empty.
   - The migration contains no `create_table`.
   - `app/services/` has no `fastapi` imports and `app/api/` has no SQL.
6. **CI.** Validate the workflow YAML and run its commands locally. Ask before pushing a branch to run it on GitHub.
7. **Docs.** `docs/features/current.md` is updated and the `docs/AI_WORKFLOW.md` entry is drafted for review.
