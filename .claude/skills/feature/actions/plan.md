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
5. Verify the user understands the plan, unless the argument is `--sudo` (see "Recap check" below). With `--sudo`, skip the check and go to step 6.
6. Wait for approval. When changes are requested, revise the plan, run the recap check again on what changed (unless `--sudo`), and wait again.
7. Once approved:
   - Set `## Status` to Planned
   - Record each decision made during planning under `## Decisions`, with its reason
   - Commit the `current.md` change on the current branch (for example `docs: plan feature NN`), so the Planned record travels with the feature

## Arguments

The only argument is `--sudo`. Anything else: say `--sudo` is the only valid argument, and stop.

## Recap check

A plan is easy to approve without reading it. Unless `--sudo` is passed, the user must recite the plan in their own words before approval counts.

1. After laying out the plan (steps 3 and 4), end with a request to recap it in their own words. Do not ask "do you approve?" yet.
2. The recap does not have to be complete or perfect. It has to be correct, and it has to say something concrete about the plan: at least two specific points, such as what gets built and where, what the migration adds, or what a test proves. "Looks good" or a repeat of the plan's headings does not count. Ask again.
3. If the user says "approve", "yes" or "go ahead" before a recap passes, do not accept it. Ask for the recap.
4. Check every claim in the recap against the plan you proposed and against the code and docs it refers to. Read the file again when you check; do not cite from memory. If a claim is vague, ask what they mean instead of marking it right or wrong.
5. If everything they said is correct, reply "You understood the plan. Do you approve?" and wait. Only an explicit yes after that counts as approval.
6. If anything is incorrect, do not accept approval. For each error:
   - Quote what the user said.
   - Say what the plan says, or what the code or spec says.
   - Give the proof: file path, line number, and the method or function name when there is one. For something in the plan, quote the plan line.
   - Then ask for the recap again.
   You may explain or clarify, but the user has to produce a correct recap themselves. Do not rewrite it for them and ask them to confirm.
7. Repeat until the recap is correct. The user can say the evidence is wrong. Re-read the file and check. If you were wrong, say so, drop the correction and fix the plan if it was affected. If the plan changed, the recap has to be checked against the revised plan.
8. Correct only what the user got wrong. Parts of the plan they left out are not errors.
