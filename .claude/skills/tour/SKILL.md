---
name: tour
description: Explain how this codebase fits together - the whole app, the frontend, the backend, one flow at a time, what the tests assert, and what changed since a commit
argument-hint: main | frontend [name] | backend [name] | paths [flow] [--ui] [--vim] | states [drafts] | tests [feature] | since [ref]   (add --save .tour/; add --ui to watch a path in a browser; add --vim to open each stop's files in Vim)
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Agent, Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git rev-parse:*), Bash(git status:*), Bash(uv run python:*), Bash(curl:*), Bash(lsof:*), mcp__playwright__*, mcp__vim-mcp__*
---

# Tour

Helps the user keep up with code they did not write. Most of this codebase was built by Claude, one feature at a time, and the user is losing track of what exists and how it connects. Each action explains one slice of it. The user is a Rails developer, so Rails analogies help (see `conventions.md`).

This skill is read-only. The only thing it ever writes is a file in `.tour/`, and only when the user passes `--save`. The one exception is `paths <flow> --ui`: it drives the running app in a browser, so the app itself writes dummy rows to the dev database, exactly as if a person had clicked. It writes no files, takes no screenshots, and the rules for it are in `actions/paths.md`. `paths <flow> --vim` controls the user's Vim through vim-mcp, only to open files read-only so they can follow the stops. It never edits, saves or quits.

## Task

Requested: $ARGUMENTS

The first word is the action. Anything after it is that action's argument. `--save`, `--ui` and `--vim` can appear anywhere and are not part of the argument. `--ui` and `--vim` apply only to `paths`; with any other action, say so in one line and run the action without them. Without `--vim`, never use vim-mcp.

| Action | What it does |
| --- | --- |
| `main` | The whole app on one page: entry points, the main flow, the major components, one diagram, key files. The default when no action is given |
| `frontend [name]` | Every page and component: what it does, props, data it touches, where it is used. With a name, a deep dive on one |
| `backend [name]` | Routes, services, repositories, models, prompts: what each does and how they connect. With a name, a deep dive on one |
| `paths [flow] [--ui] [--vim]` | Lists the user flows. Pick one and it walks you through the files in order, one stop per turn. With `--ui`, a flow that has a UI part is first run live in a browser (Playwright) with dummy data. With `--vim`, each stop opens its files, read-only, in your running Vim (vim-mcp) |
| `states [drafts]` | The state machine of an application's stages as a diagram: start and terminal states, every transition, and the condition on each. `drafts` shows the review lifecycle of AI output instead. `show-states` is an alias |
| `tests [feature]` | The behaviors the tests assert, grouped by feature. With a feature, the full list for that one |
| `since [ref]` | What changed in the big picture since a commit or tag. With no ref, since the newest saved map |

Treat `show-states` as `states`. If the first word is not in the table, list the actions and stop.

Read `conventions.md` in this skill's folder first, then `actions/<action>.md`, and follow both exactly.

## Rules for every action

- Do one action per invocation. Do not continue to another action unless asked.
- Never edit source, docs, or config. Never run tests, migrations, `make seed` or anything that writes to the database or calls an AI model. The only exception is the browser run of `paths <flow> --ui`, within the limits in `actions/paths.md` (dummy data only, no AI call without asking, `SELECT`-only database checks). The other is `paths <flow> --vim`, which may send Vim only the window and read-only open commands listed in `actions/paths.md`.
- Saved files in `.tour/` are for the user to read later. Never use them as input to a new tour. Rebuild from the code every time. The one exception is `since`, which reads the commit stamp from a saved file.
- Follow `CLAUDE.md`. Where `docs/architecture.md` and the code disagree, the code is the truth and the disagreement is a finding.
