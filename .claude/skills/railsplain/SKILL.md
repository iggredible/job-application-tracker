---
name: railsplain
description: Explain any part of this Python + React codebase in Rails terms, with an analogy for each piece and a note on where the analogy breaks
argument-hint: [file | folder | concept | flow | question]   e.g. services/applications.py, Depends, useMutation, "how does a stage change work"
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Agent, Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git rev-parse:*), Bash(git status:*), Bash(uv run python:*)
---

# Railsplain

The user knows Rails very well and is not at home in Python or React. This project is FastAPI + SQLAlchemy + Postgres on the backend and React + TypeScript on the frontend. Explain the thing they ask about by mapping it onto the Rails thing they already know, then say where the mapping stops being true.

This skill is read-only. Never edit files, run tests, run migrations, or call an AI model.

## Task

Requested: $ARGUMENTS

Work out which kind of target this is:

| Argument | What to do |
| --- | --- |
| Empty | The whole app. Describe it as if it were a Rails app: what `app/` would hold, the request cycle, the jobs and models. Use the layer table in `docs/architecture.md` as the starting point, then read the code |
| A file or folder (`services/applications.py`, `frontend/src/hooks`) | Read it. Say which Rails file or folder it is closest to, then walk through its main parts |
| A concept or tool name (`Depends`, `Pydantic`, `useMutation`, `Alembic`, `pytest fixture`, `uv`) | Give the Rails equivalent, then show one real use of it from this repo |
| A flow or question ("how does a stage change work") | Follow it through the code in request order, one Rails-flavoured line per hop |

If the argument could mean two things, pick the likelier one and say which you picked. Do not ask.

## How to explain

1. **Start with the analogy.** One sentence: "X is this app's version of Rails' Y." Put it before any detail.
2. **Show the Rails you would write.** When it helps, give a 3 to 8 line Ruby sketch of the Rails equivalent next to the real Python or TypeScript, so the user can compare shapes. Label the sketch "Rails would be:" and keep it short. Never paste more than about 10 lines of real source; quote the one line that is the point.
3. **Walk the real code.** Say what it does, in plain words, with a `file:line` on every claim. Only cite lines you read in this run. If you cannot find something, write "not found" and say what you searched. Describe what the code does, not what its name suggests.
4. **Say where the analogy breaks.** Every analogy is a little wrong. Add a "Not like Rails:" line for each difference that could mislead (see "Places the analogy breaks" below). This is the part that stops the user from importing a wrong assumption.
5. **Stay on the target.** Explain what was asked. Add one "Next" line with the one or two things worth asking about next. Do not tour the whole app unless asked.

Keep it short. A file explanation fits on one screen; a flow gets a chain diagram; the whole app gets one tree. Use box-drawing text for diagrams, about ten nodes at most, no Mermaid:

```
Browser click
  │  POST /applications/{id}/stage
  ▼
api/applications.py        ≈ controller action
  ▼
services/applications.py   ≈ service object
  ▼
repositories/timeline.py   ≈ query object + AR writes
```

If the project's Rails analogy for a project rule matters, include it. For example, `applications.stage` changing only through `ApplicationService.change_stage()` is "no one calls `update(stage:)`; everything goes through one state-machine service". Read `CLAUDE.md` for the rules and `docs/architecture.md` for the layers. Where the doc and the code disagree, the code is the truth: say so in one line.

## Rosetta table

Use these as the default mappings. Check against the code before leaning on one, and use a closer match if the code offers it.

### Backend

| Here | Rails |
| --- | --- |
| FastAPI app (`app/main.py`) | `config/application.rb` + `config/routes.rb` + Rack middleware stack |
| `api/*.py` router, `@router.get/post(...)` | Controller with the route declared on the action. Routes live next to the handler, not in `routes.rb` |
| Handler function parameters | Strong params, already parsed and type-checked before your code runs |
| `Depends(get_session)` | `before_action` that sets an instance variable, but explicit and per-handler. It is also dependency injection, which Rails lacks |
| Pydantic model in `schemas/` | Strong parameters + a serializer (jbuilder or AMS) in one class. Validates input and shapes output |
| `services/` | Service objects (`app/services`). Here this is where all business rules live, thicker than most Rails apps |
| `repositories/` | Query objects / scopes plus the persistence calls. Rails would put these on the model; here they are split out on purpose |
| SQLAlchemy model in `models/` | ActiveRecord model with the columns declared in the class. No behaviour: it is closer to a schema than to an AR model |
| SQLAlchemy `Session` | The AR connection plus a unit of work. Nothing is saved until `commit()`; closest to `ActiveRecord::Base.transaction` held open for a whole request |
| `session.execute(select(...))` | `Model.where(...)` but explicit, with no lazy relation chaining |
| Alembic migration (`alembic/versions`) | Rails migration. Written by hand here; there is no `schema.rb`, the migrations are the schema |
| `pydantic-settings` (`core/config.py`) | `Rails.application.credentials` / `ENV.fetch` with a typed config object |
| `core/clock.py` injected `Clock` | `Time.current` wrapped so tests can freeze it, like `travel_to` but passed in as an argument |
| `ai/` client wrapper | A small gateway class around an HTTP client (a Faraday wrapper) that logs every call |
| `ai/prompts/` | Versioned prompt templates, like view templates that are never edited in place |
| DB triggers on `timeline_events` | Database-level `readonly` enforcement, stricter than `attr_readonly` |
| `pytest`, `conftest.py` fixtures | RSpec / Minitest; a fixture is a `let` or `before` block that is injected by parameter name |
| `tests/fakes.py` fake AI client | A stubbed gateway, like WebMock stubs but as a real class |
| `uv`, `pyproject.toml`, `uv.lock` | Bundler, `Gemfile`, `Gemfile.lock` |
| `ruff` | RuboCop |
| `make dev` + honcho | `bin/dev` + Foreman |

### Frontend

| Here | Rails |
| --- | --- |
| React app in the browser | A Rails app with all the views moved to the client. The backend only returns JSON, like `render json:` everywhere |
| Component (`*.tsx`) | A view partial with its own logic, closer to a ViewComponent than an `.erb` |
| Props | The locals passed to a partial, or ViewComponent initializer arguments |
| `useState` | An instance variable that, when you change it, re-renders the component. Closest is a Stimulus value that re-renders |
| `useEffect` | A Stimulus `connect()` / `disconnect()` pair plus a dependency list |
| Custom hook (`hooks/useX.ts`) | A helper module or concern for the view layer. Shares stateful logic between components |
| `useQuery` (TanStack Query) | A cached `fetch` with Turbo-style revalidation. No Rails match; think `Rails.cache.fetch` with auto-refresh |
| `useMutation` | A form submit that then expires the cache keys it touched (`invalidateQueries` ≈ `expire_fragment`) |
| `lib/api.ts` fetch wrapper | A typed API client, like an `ActiveResource` / Faraday client |
| `lib/*.ts` types | The serializer's shape written as TypeScript types, mirroring the Pydantic schemas |
| `react-router` (`routes.tsx`) | `config/routes.rb`, but it picks components client-side and never reloads the page |
| `pages/` | Controllers + their `show`/`index` views merged: one file per screen |
| shadcn/ui `components/ui/` | A vendored component library you own and can edit, like copying a gem into `app/components` |
| Tailwind classes | Utility CSS in the markup instead of stylesheets; no Sass partials |
| Vite | Propshaft/esbuild + `bin/dev` asset watcher with hot reload |
| Vitest + Testing Library | Capybara-style tests that render a component and click it, without a real browser or server |
| TypeScript | Sorbet / RBS: types checked at build time, erased at runtime |

## Places the analogy breaks

Mention these whenever they apply. They are the usual causes of a wrong mental model.

- **Explicit over implicit.** Rails autoloads and infers by name; Python imports every dependency by hand and FastAPI wires only what is declared in the signature. There is no convention-based discovery, so if it is not imported or declared, it is not there.
- **No callbacks or magic.** There is no `after_save`, no `has_many` that loads on access, no `method_missing`. A behaviour you cannot find in the model is in a service. Side effects are in plain sight.
- **The session is a unit of work.** SQLAlchemy tracks changes and flushes them; writes are not saved until the commit, and a failure rolls back the lot. It is not "each `save` hits the DB".
- **Types are validated at the edge.** Pydantic rejects bad input before the handler runs, with a 422. Rails would let it in and rely on model validations.
- **Async vs sync.** FastAPI can run `async def` handlers, but every handler in `backend/app/api/` is a plain `def` (checked: 43 `def`, 0 `async def`), so they behave like ordinary blocking Rails actions, run in a thread pool. Re-check with `Grep` if the user asks about concurrency.
- **Stateless frontend, state in the URL and the server.** There are no server-rendered views and no session cookie logic in the page. React state is gone on reload; the server cache (TanStack Query) is the source of truth for what is displayed.
- **Re-render, not mutate.** React re-runs the component function when state changes. Think "the view is a function of state", not "update the DOM".
- **Business rules are not in the browser.** This project's rule is that the frontend only renders what the API returns, so a decision you find in a `.tsx` file is a bug to flag, not a pattern.

## Output shape

```
Railsplain: <target> | <short sha> on <branch>

<One-sentence analogy.>

**Rails would be:**
<short Ruby sketch, only when it helps>

**In this repo:**
<the walk-through, file:line on each claim, diagram if a flow>

**Not like Rails:**
- <difference that could mislead>

**Next:** <one or two follow-ups, e.g. `/railsplain Depends`>
```

Get the stamp from `git rev-parse --short HEAD` and `git rev-parse --abbrev-ref HEAD`. Leave out a section that has nothing to say rather than padding it.

## Rules

- Do one target per invocation. Do not continue to another unless asked.
- Facts from commands, explanation from reading. List files with `Glob`. For the API route list, run `cd backend && uv run python -c "from app.main import app; s=app.openapi()['paths']; [print(m.upper(), p, op['operationId']) for p in sorted(s) for m, op in s[p].items()]"`, and fall back to `Grep` for `@router.` if `uv run` fails. Do not invent the list.
- Skip `__pycache__`, `node_modules`, `.venv`, and `components/ui/` internals (shadcn is stock code: name it, do not explain it).
- For a broad target (the whole app, a whole folder of 10+ files), run the file reading in an `Explore` subagent so the reads stay out of this session. Give it the exact question, and require a `file:line` for every claim and "not found" instead of a guess. Treat its output as a draft: `Read` at least three of its cited lines from different files and confirm them before presenting, and say "spot-checked 3 citations" at the end. For a single file or concept, read directly.
- If the analogy is weak, say so. "No good Rails match; the closest is X, but it differs in Y" is better than a forced comparison.
- Do not teach Python or React for its own sake. Only explain the language feature when it is the thing blocking the user's understanding of the code, and then do it with a Ruby comparison (list comprehension ≈ `map`, decorator ≈ a method that wraps a method, `with` ≈ a block with `ensure`, type hints ≈ RBS, `None` ≈ `nil`, `__init__` ≈ `initialize`, a dataclass ≈ `Struct`/`Data.define`).
- Follow `CLAUDE.md`. Where `docs/architecture.md` and the code disagree, the code is the truth.
