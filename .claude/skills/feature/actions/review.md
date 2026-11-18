# Review

Review the work as someone who did not write it. This action works best in a fresh session.

1. Read `docs/features/current.md`, the spec, `CLAUDE.md` and `docs/architecture.md`.
2. Run `git diff main` and read every changed file.
3. Report under these headings:
   - **Goals met**: each goal, with where it is implemented
   - **Goals missing or incomplete**
   - **Rule violations**: layering (business rules in routes, SQL in services, decisions in repositories), writes to `applications.stage` outside `change_stage()`, updates or deletes on append-only tables, stored values that should be calculated, AI calls outside the wrapper, business rules in the frontend
   - **Scope creep**: anything built that the spec does not list
   - **Bugs and risks**: edge cases, error handling, missing validation
   - **Tests**: requirements with no test, and tests that would still pass if the code were wrong
   - **UI**: differences from the referenced screenshot that the spec does not explain
4. End with a verdict: ready to complete, or needs changes, with the changes listed in priority order.

Do not change any code in this action.
