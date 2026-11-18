# Start

1. Read `docs/features/current.md`. If Status is not Planned, stop and say to run `/feature plan` first.
2. Make sure the working tree is clean and you are on `main`. If not, stop and report.
3. Create and check out a branch named `feature/NN-short-name`, taken from the H1.
4. Set `## Status` to In progress.
5. Write the tests from the approved plan first. Run them and confirm they fail for the right reason.
6. Implement the feature, one goal at a time, until the tests pass.
7. Run `make test` and `make lint`. Fix anything that fails.
8. Record any new decision under `## Decisions` as you make it.
9. Stop and report:
   - Which goals are done
   - Anything that differs from the approved plan, and why
   - What to check by hand in the browser

Do not commit. Do not start anything the spec does not list.

If something does not work after three attempts, stop and explain the problem. Do not keep trying variations.
