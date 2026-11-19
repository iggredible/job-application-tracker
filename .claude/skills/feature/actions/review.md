# Review

Review the work as someone who did not write it. Read-only: do not change any code.

## Steps

1. Read `docs/features/current.md`, the spec, `CLAUDE.md` and `docs/architecture.md`.
2. Run `git diff main` and read every changed file.
3. Check the diff against the goals, the rules and the UI screenshot named in the spec.
4. Write the report in the format below.

## What to check

- **Goals**: each spec goal is implemented and tested.
- **Rules**: layering (business rules in routes, SQL in services, decisions in repositories), writes to `applications.stage` outside `change_stage()`, updates or deletes on append-only tables, stored values that should be calculated, AI calls outside the wrapper, business rules in the frontend.
- **Scope**: anything built that the spec does not list.
- **Bugs**: edge cases, error handling, missing validation.
- **Tests**: requirements with no test, and tests that would still pass if the code were wrong.
- **UI**: differences from the referenced screenshot that the spec does not explain.

## Severity

- **Blocker**: breaks a "never broken" rule in `CLAUDE.md`, a spec goal is missing or wrong, or data can be lost or corrupted. Must be fixed before completing.
- **Major**: a real bug, a layering violation, scope creep, or a requirement with no meaningful test. Should be fixed before completing.
- **Minor**: an edge case, a weak test, or a UI difference. Fix or consciously defer.
- **Nit**: style or naming. Never block on these.

## Report format

Keep it short. Do not restate the spec or describe what the code does. Do not pad: if a severity level has no findings, omit it.

```
Verdict: READY | NEEDS CHANGES (<n> blocker, <n> major, <n> minor, <n> nit)

Goals: <met>/<total> met. <only the goals that are missing or incomplete, one line each>

## Blocker
1. <what is wrong> (`path:line`) [category]
   Fix: <one line>

## Major
...

## Minor
...

## Nit
...
```

Rules for the report:

- One numbered list per severity, most severe first. Number continuously across sections so findings can be referred to as "#3".
- Each finding is one line for the problem, one line for the fix. Add a third line only when the failure is not obvious, as a concrete input that goes wrong.
- `[category]` is one of: goal, rule, scope, bug, test, ui.
- Every finding cites `path:line`. Drop anything you cannot point to.
- Verdict is READY only when there are no blockers and no majors.
