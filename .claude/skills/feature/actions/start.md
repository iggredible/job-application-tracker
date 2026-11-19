# Start

1. Read `docs/features/current.md`. If Status is not Planned, stop and say to run `/feature plan` first.
2. Make sure the working tree is clean and `main` is an ancestor of HEAD. If not, stop and report.
3. Create and check out a branch named `feature/NN-short-name`, taken from the H1, from the current HEAD.
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

## Keep It Simple

- Write the minimum code needed to solve the exact request.
- Do not create new files, helpers, or abstractions unless asked.
- Only change lines directly required by the task.

## Installing packages

The approved list is "Approved Packages" in `docs/project-overview.md`. Anything on it can be installed without asking. Anything else needs the user's approval first.

This covers every install path: `pip install`, `uv add`, `npm install`, `pnpm add`, `npx shadcn add` when it pulls in new packages, and edits to `pyproject.toml`, `requirements*.txt` or `package.json`. It includes packages you add on purpose as a peer dependency or as `@types/*` for an unlisted package.

Before installing an unapproved package:

1. Stop. Do not install it, not even temporarily or to try it out.
2. Ask the user for approval and give:
   - The package name and, if relevant, the version
   - Whether it is a runtime or dev dependency
   - Why it is needed, tied to the specific goal or test in the plan that requires it
   - Why the approved packages or the standard library cannot do the job
   - The alternative if the user declines
3. Wait for an explicit yes. A yes for one package does not cover another.
4. After approval, install it and record it under `## Decisions` in `docs/features/current.md` with the justification.

If the user declines, use the alternative or stop and report. Do not work around the refusal by copying the package's code into the repo.

If something does not work after three attempts, stop and explain the problem. Do not keep trying variations.
