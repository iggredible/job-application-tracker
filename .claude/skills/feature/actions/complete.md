# Complete

1. Read `docs/features/current.md`. If Status is not In progress, stop and report.
2. Run `make test` and `make lint`. If either fails, stop and report. Do not complete a failing feature.
3. If the structure of the code changed, update `docs/architecture.md` to match, including real module names.
4. Update `docs/features/current.md`:
   - Append one line for this feature to the end of `## History`: number, name, date and a one-sentence summary
   - Reset the H1 to `# Current Feature`
   - Set `## Status` to Not started
   - Clear Goals, Decisions and Notes, keeping the placeholder comments
5. Show the proposed commit message and wait for approval. Use a conventional prefix (`feat:`, `fix:`, `chore:`, `docs:`).
5a. The commit message must be short: fewer than 20 words.
6. Commit all changes on the feature branch.
7. Push the feature branch. Do not merge it and do not push `main`: the user merges (usually as a pull request), because the session may run in a worktree where `main` is checked out elsewhere.
8. Tell the user the commands to delete the feature branch locally and on the remote after the merge. Use `-D` for a squash merge.
9. Report the commit and the branch, confirm CI was triggered on the push or pull request, and name the next feature number.
