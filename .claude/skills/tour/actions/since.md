# Since

What changed in the big picture since a commit or tag. It shows only what is new, so the user can catch up without re-reading everything. It is not a commit log. Follow `conventions.md`.

## 1. Pick the reference

1. If the argument is given, it is the ref (a commit, tag or branch). Check it with `git rev-parse --verify <ref>^{commit}`. If it fails, say so and stop.
2. If there is no argument, use the newest saved map: `Glob` `.tour/*.md`, `Read` the frontmatter of each, and take the `commit:` of the one with the latest `generated:`. Say which file it came from and its date. Check that the commit still exists (`git rev-parse --verify`); if it does not (rebased away), say so and ask for a ref.
3. If there is no argument and no saved map, do not guess. Say that no map has been saved, show `git log --oneline -15` so the user can pick a ref, and mention `/tour <action> --save` as the way to set a reference point. Stop.

Print: `Since <short ref sha> (<date>, <N> commits behind HEAD)`. If the ref is HEAD, say nothing has changed and stop.

Only committed changes count. If the working tree is dirty, say so once and that it is not included.

## 2. Gather the facts

```
git log --oneline --no-merges <ref>..HEAD
git diff --name-status <ref>..HEAD -- backend/app backend/alembic backend/scripts backend/evals frontend/src docs
git diff <ref>..HEAD -- backend/app/api backend/app/main.py frontend/src/routes.tsx
```

From the diffs, work out:

- **Routes**: lines added or removed that start with `@router.` or `include_router`, with the file and the handler name.
- **Tables and columns**: new files in `backend/alembic/versions/` (read them) and changes to `backend/app/models/`. Note new triggers or constraints.
- **Services, repositories**: files added (`A`) or removed (`D`) in those folders, and for modified files whether public methods were added or removed.
- **Prompts**: new modules in `backend/app/ai/prompts/` and their versions.
- **Frontend**: added pages, components, hooks and routes in `routes.tsx`.
- **Tests**: new test files and the count of added `def test_` and `it(` lines.
- **Docs**: specs added, and whether `docs/architecture.md` changed.

Use an `Explore` subagent (convention 4) when the diff touches more than about 40 files. Otherwise read directly.

## 3. Output

```
Tour since | ...stamp
Since 1e2c80f (2026-11-19, 7 commits behind HEAD)

## The big picture
Three to six bullets: what the app can do now that it could not before. Plain language, one line each.

## New
Routes:      METHOD /path  (`api/x.py:NN`)  what it does
Tables:      ...
Services:    ...
Prompts:     ...
Pages and components: ...
Tests:       N new tests in M files, covering ...

## Changed
Existing things whose behavior changed, with what changed and `file:line`. Only changes that matter at the level of "how the app works". Skip renames, formatting and test-only churn.

## Removed
(only if any)

## Paths worth walking
One to three flows that are new or now cross new files: /tour paths <flow>

## Doc drift
Only if real. Most useful here: structural files changed (routes, models, services) but docs/architecture.md did not. Say which sections the new code belongs in.
```

Every item in New and Changed carries a `file:line` at HEAD. Group by the feature spec the change belongs to when a spec in `docs/features/` names it.

## `--save`

Saves as `.tour/since.md`. Note: the saved file's stamp is HEAD now, so the next `/tour since` with no argument will start from here.
