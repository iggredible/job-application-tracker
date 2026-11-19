# Start

1. Read `docs/features/current.md`. If Status is not Planned, stop and say to run `/feature plan` first.
2. Make sure the working tree is clean and `main` is an ancestor of HEAD (`git merge-base --is-ancestor main HEAD`), so the branch is not behind `main`. You do not have to be on `main`: `load` and `plan` commit their `current.md` changes on the branch they ran on (often a worktree branch), and the Planned record must come with the feature. If the tree is dirty or the branch is behind `main`, stop and report.
3. Create and check out a branch named `feature/NN-short-name`, taken from the H1, starting from the current HEAD. Do not branch from `main` if that would lose the Planned record.
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
