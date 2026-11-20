# Backend

An inventory of the backend with the explanation the user is missing. Follow `conventions.md`.

## Mode

- No argument: overview of everything below.
- A name (a service, route, table, prompt, or a path fragment like `timeline` or `/stage`): deep dive. Match case-insensitively against file names, class names, route paths and table names. If nothing matches, say so and list the closest names. If several match, list them and stop.

## Overview

Map in a subagent (convention 4). Cover these, in this order, each from the facts in convention 2:

1. **Routes.** One row per route: `METHOD /path` → handler (`api/<file>.py:line`) → the service method it calls (`services/<file>.py:line`). Group by `api/` file. Note the status codes the handler can raise.
2. **Services.** One entry per file in `services/`: what business rule it owns, its public methods, which repositories it uses, whether it calls the AI wrapper. Name rules that are held as data (for example the transitions table) separately from rules held in code.
3. **Repositories.** One entry per file: which table(s) it queries and the notable queries. Say if any makes a decision (CLAUDE.md says they must not).
4. **Models and schema.** One entry per table: columns that matter, constraints, and what triggers or append-only rules apply (read the migrations in `backend/alembic/versions/`). Say which tables are append-only and which derived values are never stored.
5. **AI.** The wrapper and its log sink, each prompt module and its version, and the output schemas. Say which services call it.
6. **Core, scripts, evals.** One line each: config, db, clock, logging, middleware, `scripts/`, `evals/`.

### Output

```
Tour backend | ...stamp

## Request flow
(one chain diagram: api -> services -> repositories -> models, with ai/ off to the side)

## Routes
| Route | Handler | Calls |

## Services
### ApplicationService  (`services/applications.py:NN`)
What it does: ...
Public methods: ...
Uses: ...    Calls AI: yes/no

## Repositories
## Tables
## AI
## Core, scripts, evals

## Counts
routes N, services N, repositories N, tables N, prompts N

## Doc drift          (only if found)
## Things worth knowing   (only if real)
```

"Things worth knowing" examples: a service with no caller, two services doing nearly the same job, a route that does more than parse and call one service, a table nothing writes to, a prompt module with no caller.

## Deep dive

Read the thing directly (no subagent) and its tests (`Grep` the test files for its name). Report:

1. **Purpose** in two sentences.
2. **How it is reached**: the route or caller chain from the outside, as a short chain diagram.
3. **What it does**: the steps in order, each with `file:line`. For a service method, include the guards, effects, transaction and error cases. For a table, the columns, constraints, triggers and who writes and reads it.
4. **Depends on** and **Used by**.
5. **Tests**: test files and the behaviors they assert (names, with `file:line`), or "no direct test".
6. **Where to look first** if the user wants to change it.
