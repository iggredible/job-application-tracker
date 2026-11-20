# Tour conventions

Every action follows these. They exist so the user can trust what they read and jump to the code to check it.

## 1. Stamp every output

Start with one line, from these commands:

```
git rev-parse --short HEAD
git rev-parse --abbrev-ref HEAD
git status --porcelain
```

Format: `Tour <action> | <short sha> on <branch> | <date> | <N> uncommitted files` (leave out the last part when N is 0). This tells the user which version of the code the tour describes.

## 2. Facts from commands, explanation from reading

Do not list things by eye when a command can list them. The model explains; commands enumerate.

| Fact | How to get it |
| --- | --- |
| API routes (method, path, operationId) | `cd backend && uv run python -c "from app.main import app; s=app.openapi()['paths']; [print(m.upper(), p, op['operationId']) for p in sorted(s) for m, op in s[p].items()]"` |
| Where a route's handler is | The operationId starts with the handler's function name. `Grep` for `def <name>` and the `@router.` line above it in `backend/app/api/` |
| Frontend routes | `frontend/src/routes.tsx` |
| Files per layer | `Glob` over `backend/app/{api,services,repositories,models,schemas,ai,core}`, `backend/alembic/versions`, `backend/scripts`, `backend/evals`, `frontend/src/{pages,components,hooks,lib}` |
| Test cases | `Grep` for `^\s*(async )?def test_` in `backend/tests` and `^\s*(it|test|describe)\(` in `frontend/src` |
| Feature list | `docs/features/NN-*-spec.md`, titles from their first heading |
| What changed | `git diff --name-status`, `git log --oneline` |

If `uv run` fails (for example no virtualenv), say so and fall back to `Grep` for `@router.` in `backend/app/api/`. Do not make up the route list.

Skip `__pycache__`, `node_modules`, `.venv`, `*.test.tsx` (except in `tests`), and `ui/` internals (shadcn is stock code, list names and a count only).

## 3. A file:line on every claim

- Every sentence that says what the code does ends with a reference like `backend/app/services/applications.py:156`. Use `symbol` plus reference when it helps: `ApplicationService.change_stage` (`services/applications.py:156`).
- Only cite a line you actually read in this run. Never cite from memory or by guessing an offset. If you cannot find where something lives, write "not found" and say what you searched.
- Describe what the code does, not what its name suggests. If name and behavior disagree, say so.
- Do not paste source. Quote at most one short line when it is the point.

## 4. Subagents

- Actions that read many files (`main`, `frontend`, `backend`, `tests`, large `since`) run the mapping in an `Explore` subagent so the file reads stay out of the main session. Give it the exact commands from section 2, the output format from the action file, and these rules: every claim has a `file:line` it read, say "not found" instead of guessing, and report the result, not file dumps.
- Subagent output is a draft. Before presenting, `Read` at least three of its cited locations, chosen from different files, and confirm each says what the draft claims. Fix or drop anything that does not. Say "spot-checked 3 citations" in one line at the end.
- `paths` never uses a subagent. The point is that the code is in the conversation.
- Deep dives on a single named thing read directly. They are small.

## 5. Doc drift

After mapping, compare the map with the docs and report only disagreements. Sources: `docs/architecture.md` (layer table, "State and guards", "Frontend", "Testing"), the schema in `docs/project-overview.md`, and the rules in `CLAUDE.md`. For each: what the doc says (`file:line`), what the code does (`file:line`), and which looks stale. If nothing disagrees, write "No drift found in: <what was compared>". Do not pad.

Rules for layer boundaries:

- Report cross-layer imports as observations, never as "violations". Wiring is legitimate: an `api/` module importing a repository to build a service for `Depends` is not the same as running a query there. Say what the doc forbids, what the code does, and let the user decide.
- The `applications.stage` rule is enforced by `backend/tests/test_architecture.py`. Cite that test. Do not re-implement it with grep, and do not run it.

## 6. Diagrams

Small. One per flow or map, about ten nodes at most. Split rather than grow past that. Use box-drawing characters, which any terminal shows as plain text.

Structure (what contains or composes what), as a tree:

```
ApplicationDetailPage
├── WorkflowSteps
│   └── PostingAnalysisCard
├── ChangeStageMenu
└── Timeline
```

Sequence (what calls what, in order), as a chain:

```
ChangeStageMenu.tsx
  │  POST /applications/{id}/stage
  ▼
api/applications.py
  ▼
services/applications.py
  ▼
repositories/timeline.py → timeline_events
```

No wide boxes and no diagram that needs scrolling sideways. Mermaid is not used, with one exception: `states` generates a Mermaid `stateDiagram-v2` and renders it in the terminal with termaid, because a state machine diagram is the standard way to show states (see `actions/states.md`).

## 7. Plain language

- One sentence says what a thing does, from the user's point of view, before any detail.
- Name the Rails equivalent in a few words where one exists: service ≈ service object, repository ≈ query object, `Depends` ≈ `before_action`, Pydantic schema ≈ strong parameters plus serializer, Alembic migration ≈ Rails migration, TanStack Query hook (`useQuery`/`useMutation`) ≈ no direct match; closest is a cached fetch with Turbo-style revalidation (say so when it matters).
- Say which parts are deterministic and which call the LLM when it matters to the claim.
- "Things worth knowing" and "Doc drift" appear only when there is something to say.

## 8. `--save`

Only when `--save` is in the arguments. Never otherwise.

1. Write the same content you printed to `.tour/<action>[-<argument-slug>].md`, creating the folder if needed. For `paths`, save the whole walk with every stop, not only the first.
2. Put this frontmatter first:

   ```
   ---
   commit: <full sha from git rev-parse HEAD>
   branch: <branch>
   generated: <YYYY-MM-DD>
   action: <action>
   argument: <argument or none>
   dirty: <true if git status --porcelain is not empty>
   ---
   ```

3. Overwrite the file for the same action and argument. Do not create dated copies.
4. Tell the user the path and the commit it is stamped with. If `.tour/` is not in `.gitignore`, say so and stop short of editing it.

Saving needs a write permission prompt. That is intended.
