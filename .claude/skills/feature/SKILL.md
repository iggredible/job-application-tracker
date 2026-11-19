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
| `review` | Independent review by the `feature-agent` subagent, findings ranked by severity |
| `explain` | Explain what changed and how it fits together |
| `complete` | Record what happened, commit, push the branch and reset `current.md` (you merge) |

Read `actions/<action>.md` in this skill's folder and follow it exactly. The one exception is `review`, below.

### `review` runs in a subagent

Do not read `actions/review.md` or `current.md`, and do not look at the diff yourself. The reviewer must stay independent of this session.

1. Launch the `feature-agent` subagent (a fresh agent, never a fork) with exactly this prompt and nothing else, with no summary of the work and no hints about what to check:

   > Review the feature currently in progress. Follow `.claude/skills/feature/actions/review.md`.

2. Print the agent's report to the user verbatim. Do not summarize, reorder, soften or drop findings, and do not argue with them. You may add one line after the report only to say that it is the reviewer's output.
3. Do not fix anything in the same invocation. Wait for the user to decide which findings to act on.

If no action is given, or it is not in the table, list the actions and stop.

## Rules for every action

- Follow `CLAUDE.md`. Its rules override anything inferred from a screenshot or the reference UI code.
- Build only what the loaded spec lists. If something seems missing, ask.
- Do one action per invocation. Do not continue to the next action without being asked.
