# Current Feature: 01 Project Scaffold

## Status

In progress

## Goals

Set up the repo skeleton so the backend, frontend and database run locally with one command and CI is green. No domain features yet.

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

## Decisions

Made while planning (approved):

- **Python pinned to 3.12** (`.python-version`, `requires-python = ">=3.12,<3.13"`), because the system `python3` is 3.15 and the spec says 3.12.
- **`anthropic` is not added in this feature.** It is approved but nothing here uses it; feature 5 adds it.
- **Health check follows the layers:** `api/health.py` -> `services/health.py` (raises `DatabaseUnavailable`, no FastAPI) -> `repositories/health.py` (`SELECT 1`).
- **Extra test: health returns non-ok when the database is unreachable.** It proves the "confirms the database connection" requirement; counted as part of the health test.
- **Databases:** `job_tracker` and `job_tracker_test`, created by `make setup` only if missing, with default URLs over the local socket and no password.
- **`make setup` copies `.env.example` to `.env` only if `.env` is missing.** `Settings` reads `../.env` because the backend runs from `backend/`; CI supplies env vars directly.
- **Frontend lint is eslint only** (`npm run lint`); no Prettier. Backend lint is `ruff check` plus `ruff format --check`.
- **Logging:** stdlib logger `app.request` with a JSON formatter to stdout; uvicorn's access log is disabled so there is one line per request.
- **`.gitignore` gets `dist/`** (it only had Next.js-era root entries).
- **CI:** one `ci.yml`, two jobs (backend with a `postgres:16` service, frontend), actions pinned to major versions.
- **Frontend smoke test:** one file, covering the three nav links and a route change to `/resume`.
- **The API key never goes in a tracked file.** It lives only in the gitignored `.env`; `.env.example` has a blank placeholder.

## Notes

- Spec: `docs/features/01-scaffold-spec.md`
- References: `docs/project-overview.md` (Tech Stack, Suggested Project Structure), `docs/architecture.md` (Backend layers), `docs/screenshots/applications-list.png` (nav bar and page frame only)
- No Docker. PostgreSQL 16 is installed locally.
- Do not create any domain tables in this feature.
- The packages in the project overview's Approved Packages table are allowed. Ask before adding anything else.
- Later features add `seed` and `eval` targets to the Makefile.
- Doc-review decisions made before feature 1 (seed/creation exceptions to `change_stage()`, AI log sink, immutable snapshot, triggers, tooling) are already written into the overview, architecture and specs.
- Confirm in feature 5 which JSON Schema constraints structured outputs support; caps are enforced in code regardless.
- `docs/reference/v0-prototype/` is the reference code (never imported); `docs/reference/ui/` holds only a README.
- This feature changes the frontend, so the Playwright MCP browser check applies (nav bar and page frame against `applications-list.png`, console clean).

## History

- Doc review before feature 1: resolved contradictions between CLAUDE.md, the overview, the architecture and the specs, and fixed design gaps (snapshot, guardrail holes, metrics rules).
