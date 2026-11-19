# Plan

1. Read `docs/features/current.md`. If Goals are empty, stop and say to run `/feature load <number>` first.
2. Read the spec again, `docs/architecture.md`, and the existing code this feature touches.
3. Propose a plan. Do not write or change any code. Include:
   - The files to create or change, grouped by layer (`api`, `schemas`, `services`, `repositories`, `models`, `ai`, frontend)
   - The migration, if any, and exactly which tables and columns it adds
   - The tests to write, each named after the requirement it proves
   - Any dependency that is not already in the project overview
   - Anything in the spec that is unclear, and what you would assume
4. State how the plan follows the layering rules and the rules that must never be broken in `CLAUDE.md`.
5. Wait for approval. When changes are requested, revise the plan and wait again.
6. Once approved:
   - Set `## Status` to Planned
   - Record each decision made during planning under `## Decisions`, with its reason
   - Commit the `current.md` change on the current branch (for example `docs: plan feature NN`), so the Planned record travels with the feature
