---
name: feature
description: Run the per-feature workflow for this project - load a spec, plan, build, test, review, explain or complete
argument-hint: load <number>|plan|start|test|review|explain|complete
disable-model-invocation: true
---

# Feature Workflow

Takes one feature spec from `docs/features/` through plan, build, test, review and merge. One feature at a time, in numeric order.

## Working file

`docs/features/current.md` tracks the feature in progress. Read it at the start of every action.

It has these sections:

- `# Current Feature` - H1 with the feature number and name when one is active
- `## Status` - Not started | Planned | In progress | Completed
- `## Goals` - what the spec requires, as bullets
- `## Decisions` - choices made while planning or building, with the reason
- `## Notes` - constraints, references and anything the next session needs
- `## History` - one line per completed feature, earliest first (append only)

## Task

Requested: $ARGUMENTS

The first word is the action. Anything after it is that action's argument.

| Action | What it does |
| --- | --- |
| `load <number>` | Load a feature spec into `current.md` |
| `plan` | Propose an implementation plan and wait for approval |
| `start` | Create a branch, write tests first, then implement |
| `test` | Run all checks and confirm the spec's tests exist |
| `review` | Check the work against the spec and the project rules |
| `explain` | Explain what changed and how it fits together |
| `complete` | Record what happened, commit, push the branch and reset `current.md` (you merge) |

Read `actions/<action>.md` in this skill's folder and follow it exactly.

If no action is given, or it is not in the table, list the actions and stop.

## Rules for every action

- Follow `CLAUDE.md`. Its rules override anything inferred from a screenshot or the reference UI code.
- Build only what the loaded spec lists. If something seems missing, ask.
- Do one action per invocation. Do not continue to the next action without being asked.
