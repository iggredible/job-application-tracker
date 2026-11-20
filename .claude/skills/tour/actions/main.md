# Main

The whole app on one page, for someone who wants the shape before the details. It should fit in about one screen of terminal plus one diagram. Follow `conventions.md`.

## Method

Read directly, no subagent: this action is small by design and reads only entry points and listings, not every file. Depth lives in the other actions.

1. `docs/architecture.md` ("System overview" and "Backend layers") and the entry of `docs/project-overview.md`, to know what the app is meant to be.
2. `Makefile` for how it starts (`make dev`, `make seed`, `make eval`).
3. Entry points in code: `backend/app/main.py` (app and routers), `frontend/src/main.tsx` and `frontend/src/routes.tsx`, `backend/scripts/`, `backend/evals/`.
4. The route list (convention 2), and file listings per layer for counts.
5. The AI path: the wrapper in `backend/app/ai/` and which services call it.
6. The transitions table (`backend/app/services/transitions.py`), since the pipeline stages are the spine of the app.

## Output

```
Tour main | ...stamp

## What this is
Two sentences: what the app does and for whom.

## Entry points
| Entry | Starts | Where |
| make dev | API on :8000 and web on :5173 | `Makefile:NN`, `backend/app/main.py:NN`, `frontend/src/main.tsx:NN` |
| make seed | sample data | `backend/scripts/...:NN` |
| make eval | prompt eval against the real model | `backend/evals/...:NN` |

## The main flow
One chain or tree diagram, about ten nodes: from a saved job posting through analysis, tailoring, review, and applied, to insights. Mark where the AI is called and where a person approves.

## Major components
| Layer | Role (one line) | Count | Entry file |
Backend: api, services, repositories, models, schemas, ai, core. Frontend: pages, components, hooks, lib.

## Rules that shape the code
Three to five of the CLAUDE.md "never be broken" rules, each with the file:line that holds it (for example the transitions table, the append-only triggers, the AI wrapper).

## Key files
| File | Concern |
Ten to twelve rows. Pick files someone must know to work in the app. One-line concerns.

## Doc drift          (only if found; at most three items, the rest via /tour backend and /tour frontend)

## Where to go next
- /tour backend, /tour frontend: the inventories
- /tour paths: the flows (name the two most central)
- /tour tests: what is guaranteed
- /tour since <ref>: what is new
```

Keep it short. If a section would run long, cut it and point to the action that covers it.
