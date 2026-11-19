# Load

1. Read the argument after `load`.
   - A number such as `3` or `03`: find the file in `docs/features/` whose name starts with that number.
   - A file name: use that file in `docs/features/`.
   - Empty or no match: stop and say `load` needs a feature number.
2. Check the order. Read `## History` in `docs/features/current.md`.
   - If an earlier-numbered feature is not listed there, stop and say which one is missing.
   - If this feature is already listed, stop and say so.
   - If another feature is active and not completed, stop and say which.
3. Read the spec and every file it references: the overview sections, other specs and the screenshots.
4. Update `docs/features/current.md`:
   - H1: `# Current Feature: NN <spec title>`
   - `## Status`: Not started
   - `## Goals`: the spec's requirements as bullets, kept in the spec's wording
   - `## Notes`: the spec's notes and the paths of its references
   - Clear `## Decisions`
5. Commit the `current.md` change on the current branch (for example `docs: load feature NN`), so the record travels with the feature.
6. Reply with a short summary of the feature and any questions about the spec. Do not plan or write code.
